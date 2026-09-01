from __future__ import annotations

import argparse
import ctypes
import json
import signal
import sys
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .config import Settings, load_settings, recovery_path, save_settings, settings_path
from .cursor import CursorManager, active_cursor_image_size, pointer_level_to_pixels
from .input import GlobalMouseInput
from .overlay import SpotlightOverlay
from .settings_dialog import SettingsDialog
from .tray import SpotlightTray


ERROR_ALREADY_EXISTS = 183
SINGLE_INSTANCE_NAME = "Local\\Spotlight.SingleInstance"
POINTER_PREVIEW_DEBOUNCE_MS = 150

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL


def acquire_single_instance() -> int | None:
    """세션당 1개 인스턴스만 허용한다. 획득 실패 시 None.

    시스템 커서는 세션 전역 자원이라 여러 인스턴스가 조율 없이 조작하면
    복구 마커를 서로 지워 자동 복구가 무력화된다.
    'Local\\' 접두사로 세션 단위 범위를 지정한다. 'Global\\'을 쓰면
    다중 사용자 세션에서 서로를 차단해 잘못된 동작이 된다.
    """
    handle = _kernel32.CreateMutexW(None, True, SINGLE_INSTANCE_NAME)
    if not handle:
        return None
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return int(handle)


def release_single_instance(handle: int | None) -> None:
    if handle is not None:
        _kernel32.CloseHandle(wintypes.HANDLE(handle))


class SpotlightApplication:
    def __init__(
        self,
        qt_app: QApplication,
        settings_file: Path | None = None,
        recovery_file: Path | None = None,
    ) -> None:
        self.qt_app = qt_app
        self.settings_file = settings_file or settings_path()
        self.settings = load_settings(self.settings_file)
        self.cursor_manager = CursorManager(recovery_file or recovery_path())
        self.cursor_manager.recover_if_needed()
        self.overlay = SpotlightOverlay(
            self.settings.spotlight, self.settings.click, self.settings.wheel
        )
        self.mouse_input = GlobalMouseInput()
        self.mouse_input.clicked.connect(self.overlay.add_click)
        self.mouse_input.scrolled.connect(self.overlay.add_wheel)
        self.input_stopped = True
        self.settings_dialog: SettingsDialog | None = None
        self.tray = SpotlightTray(qt_app, self.open_settings)
        self._stopped = False
        # 슬라이더 valueChanged에 apply()를 직결하면 1->15 드래그 시
        # 커서 작업이 14종 x 14회 = 약 196회 연속 발생한다.
        self._pending_preview: int | None = None
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(POINTER_PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._apply_pending_preview)

    def start(self) -> None:
        self.cursor_manager.apply(self.settings.pointer.size)
        self.overlay.start()
        self.mouse_input.start()
        self.input_stopped = False
        self.tray.show()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._preview_timer.stop()
        self._pending_preview = None
        self.input_stopped = self.mouse_input.stop()
        self.overlay.stop()
        self.tray.hide()
        self.cursor_manager.restore()

    def open_settings(self) -> None:
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        self.settings_dialog = SettingsDialog(
            self.settings, self.apply_settings, self.preview_pointer_size
        )
        self.settings_dialog.finished.connect(self._settings_closed)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _settings_closed(self) -> None:
        self.settings_dialog = None

    def preview_pointer_size(self, size: int, immediate: bool = False) -> None:
        """포인터 크기 프리뷰. 기본은 디바운스, 취소 복원 시에는 즉시 적용."""
        if immediate:
            self._preview_timer.stop()
            self._pending_preview = None
            if self.cursor_manager.applied_level != size:
                self.cursor_manager.apply(size)  # 예외는 호출자에게 전파
            return
        self._pending_preview = size
        self._preview_timer.start()

    def _apply_pending_preview(self) -> None:
        size = self._pending_preview
        self._pending_preview = None
        if size is None or self.cursor_manager.applied_level == size:
            return
        try:
            self.cursor_manager.apply(size)
        except Exception as exc:
            dialog = self.settings_dialog
            fallback = self.cursor_manager.applied_level or self.settings.pointer.size
            if dialog is not None:
                dialog.notify_preview_error(str(exc), fallback)

    def apply_settings(self, updated: Settings) -> None:
        previous = self.settings
        pointer_changed = updated.pointer.size != previous.pointer.size
        try:
            if pointer_changed:
                self.cursor_manager.apply(updated.pointer.size)
            self.overlay.apply_settings(updated.spotlight, updated.click, updated.wheel)
            save_settings(updated, self.settings_file)
            self.settings = updated
        except Exception:
            if pointer_changed:
                self.cursor_manager.apply(previous.pointer.size)
            self.overlay.apply_settings(previous.spotlight, previous.click, previous.wheel)
            save_settings(previous, self.settings_file)
            raise

    def report(self) -> dict[str, object]:
        return {
            "settings_path": str(self.settings_file),
            "pointer_level": self.settings.pointer.size,
            "pointer_pixels": pointer_level_to_pixels(self.settings.pointer.size),
            "spotlight_diameter": self.settings.spotlight.diameter,
            "effects_total": self.overlay.total_effects,
            "effects_active": len(self.overlay.effects),
            "effects_max_active": self.overlay.max_active_effects,
            "effect_kind_counts": dict(self.overlay.effect_kind_counts),
            "input_listener_started": self.mouse_input.started,
            "input_error_count": self.mouse_input.error_count,
            "cursor_count_applied": self.cursor_manager.applied_count,
            "active_cursor_image_size": active_cursor_image_size(),
            "overlay_visible": self.overlay.isVisible(),
            "overlay_geometry": [
                self.overlay.x(),
                self.overlay.y(),
                self.overlay.width(),
                self.overlay.height(),
            ],
            "overlay_mouse_transparent": self.overlay.testAttribute(
                Qt.WA_TransparentForMouseEvents
            ),
            "tray_visible": self.tray.isVisible(),
            "tray_actions": [
                action.text()
                for action in self.tray.contextMenu().actions()
                if not action.isSeparator()
            ],
            "system_tray_available": QSystemTrayIcon.isSystemTrayAvailable(),
        }


DEBUG_PATH_OPTIONS = ("report", "settings_path", "recovery_path")


def local_path(value: str) -> Path:
    """CLI로 받은 경로를 검증한다.

    원격(UNC) 경로를 그대로 파일 조작에 넘기면 SMB 연결이 발생해
    사용자 자격증명이 지정된 호스트로 전송된다. 로컬 경로만 허용한다.
    """
    text = value.strip().strip('"')
    if not text:
        raise argparse.ArgumentTypeError("경로가 비어 있습니다.")
    if text.startswith("\\\\") or text.startswith("//"):
        raise argparse.ArgumentTypeError("원격(UNC) 경로는 사용할 수 없습니다.")
    path = Path(text)
    if str(path.drive).startswith("\\\\"):
        raise argparse.ArgumentTypeError("원격(UNC) 경로는 사용할 수 없습니다.")
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spotlight cursor highlighter")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--settings-smoke-test", action="store_true")
    parser.add_argument("--report", type=local_path)
    parser.add_argument("--settings-path", type=local_path)
    parser.add_argument("--recovery-path", type=local_path)
    args = parser.parse_args(argv)

    # 경로 인자는 스모크 테스트 하네스 전용이다. 일반 실행에서 허용하면
    # 임의 위치에 파일을 만들거나 덮어쓰는 통로가 되므로 함께 요구한다.
    if not (args.smoke_test or args.settings_smoke_test):
        used = [
            name.replace("_", "-")
            for name in DEBUG_PATH_OPTIONS
            if getattr(args, name) is not None
        ]
        if used:
            parser.error(
                "--"
                + ", --".join(used)
                + " 은(는) --smoke-test 또는 --settings-smoke-test 와 함께만 사용할 수 있습니다."
            )
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    QCoreApplication.setApplicationName("Spotlight")
    QCoreApplication.setOrganizationName("Spotlight")
    qt_app = QApplication(sys.argv[:1])
    qt_app.setQuitOnLastWindowClosed(False)

    smoke_test = args.smoke_test or args.settings_smoke_test
    if not QSystemTrayIcon.isSystemTrayAvailable() and not smoke_test:
        QMessageBox.critical(None, "Spotlight", "시스템 트레이를 사용할 수 없습니다.")
        return 1

    application: SpotlightApplication | None = None
    report: dict[str, object] = {}
    exit_code = 1

    instance_lock = acquire_single_instance()
    if instance_lock is None:
        # 스모크 테스트는 CI 병렬 실행을 막지 않도록 계속 진행하되 사실을 남긴다.
        if not smoke_test:
            QMessageBox.information(
                None, "Spotlight", "Spotlight가 이미 실행 중입니다."
            )
            return 0
        report["single_instance_conflict"] = True

    try:
        application = SpotlightApplication(
            qt_app,
            settings_file=args.settings_path,
            recovery_file=args.recovery_path,
        )
        qt_app.aboutToQuit.connect(application.stop)
        signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
        signal.signal(signal.SIGTERM, lambda *_: qt_app.quit())
        signal_timer = QTimer()
        signal_timer.setInterval(250)
        signal_timer.timeout.connect(lambda: None)
        signal_timer.start()

        application.start()
        if args.settings_smoke_test:
            QTimer.singleShot(250, application.open_settings)

            def change_settings() -> None:
                dialog = application.settings_dialog
                if dialog is None:
                    report["settings_dialog_error"] = "dialog not created"
                    return
                dialog.pointer_size.setValue(2)
                dialog.spotlight_diameter.setValue(180)
                report["settings_apply_succeeded"] = dialog._apply()
                dialog.accept()

            QTimer.singleShot(500, change_settings)
            QTimer.singleShot(850, lambda: report.update(application.report()))
            QTimer.singleShot(1200, qt_app.quit)
        elif args.smoke_test:
            QTimer.singleShot(600, lambda: report.update(application.report()))
            QTimer.singleShot(1000, qt_app.quit)
        exit_code = qt_app.exec()
    except Exception as exc:
        report["error"] = repr(exc)
        if not smoke_test:
            QMessageBox.critical(None, "Spotlight 오류", str(exc))
    finally:
        # stop()이 예외를 던지면 리포트 기록이 건너뛰어지고 원래 예외까지 가려진다.
        # 정리 단계는 각각 독립적으로 보호한다.
        if application is not None:
            try:
                application.stop()
            except Exception as exc:
                report["stop_error"] = repr(exc)
            try:
                report["cursor_restored"] = not application.cursor_manager.applied
                report["recovery_file_exists"] = (
                    application.cursor_manager.recovery_file.exists()
                )
            except Exception as exc:
                report["cursor_state_error"] = repr(exc)
        release_single_instance(instance_lock)
        if args.report:
            try:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except OSError:
                pass
    return exit_code
