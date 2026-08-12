from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .config import Settings, load_settings, recovery_path, save_settings, settings_path
from .cursor import CursorManager, active_cursor_image_size, pointer_level_to_pixels
from .input import GlobalMouseInput
from .overlay import SpotlightOverlay
from .settings_dialog import SettingsDialog
from .tray import SpotlightTray


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

    def preview_pointer_size(self, size: int) -> None:
        if self.cursor_manager.applied_level != size:
            self.cursor_manager.apply(size)

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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spotlight cursor highlighter")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--settings-smoke-test", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--settings-path", type=Path)
    parser.add_argument("--recovery-path", type=Path)
    return parser.parse_args(argv)


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
        if application is not None:
            application.stop()
            report["cursor_restored"] = not application.cursor_manager.applied
            report["recovery_file_exists"] = application.cursor_manager.recovery_file.exists()
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    return exit_code
