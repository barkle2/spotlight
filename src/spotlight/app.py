"""Spotlight의 시작·설정 반영·입력 수신·종료 흐름을 연결합니다.

단일 실행 잠금과 이전 커서 복구를 확인한 뒤 화면과 입력을 준비합니다.
설정 프리뷰와 저장을 구분하고, 종료 시 자원 정리와 커서 복원을 시도합니다.
일반 실행은 사용자 설정을, EXE 스모크는 분리된 시험 설정을 사용합니다.
"""

import argparse
from pathlib import Path

from PySide6.QtCore import QTimer
from .smoke import SmokeSession

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .info_dialog import InfoDialog
from . import __version__
from .config import (
    HighlightSettings,
    get_config_path,
    load_settings,
    save_settings,
)
from .cursor import CursorController
from .effects import ClickEffectManager
from .input import RawMouseInput
from .instance import SingleInstanceLock
from .overlay import SpotlightOverlay
from .settings_dialog import SettingsDialog
from .tray import SpotlightTray, create_spotlight_icon

def run() -> int:
    """앱을 실행하고 자원 정리 후 종료 코드를 반환합니다.

    첫 실행만 커서 복구와 기능 초기화를 수행합니다.
    일반 모드의 중복 실행은 안내 후 0을 반환합니다.
    스모크 모드의 중복 실행과 시작·입력·정리·시험 실패는 1로 처리합니다.
    자원 정리와 잠금 해제를 시도한 뒤 스모크 보고서를 확정합니다.
    """

    # 일반 실행에서는 기존 설정을 사용합니다.
    # 시험 모드는 보고서 경로를 함께 지정해야 합니다.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-report", type=Path)
    options, _ = parser.parse_known_args()

    if options.smoke_test != (options.smoke_report is not None):
        parser.error("--smoke-test와 --smoke-report를 함께 지정해야 합니다.")

    application = None
    instance_lock = None
    cursor_controller = None
    overlay = None
    settings_dialog = None
    info_dialog = None    
    tray = None
    click_effects = None
    raw_input = None
    smoke_session = None    
    shutting_down = False
    exit_code = 1

    try:
        instance_lock = SingleInstanceLock()
        is_first_instance = instance_lock.acquire()

        # 잠금을 획득한 첫 실행만 설정·복구 경로를 준비합니다.
        # Qt 초기화 실패 시에도 아래 컨트롤러로 복원을 시도합니다.
        if is_first_instance:
            if options.smoke_test:
                smoke_session = SmokeSession(
                    instance_lock,
                    options.smoke_report,
                )
                cursor_controller = CursorController(
                    instance_lock,
                    marker_path=smoke_session.marker_path,
                    api=smoke_session.api,
                )
            else:
                cursor_controller = CursorController(instance_lock)

        application = QApplication(sys.argv)
        # 이후 생성되는 정보·설정 창에 Spotlight 아이콘을 사용합니다.
        application.setWindowIcon(create_spotlight_icon())
        application.setApplicationName("Spotlight")
        application.setApplicationVersion(__version__)
        application.setQuitOnLastWindowClosed(False)

        # 오버레이·입력을 시작하기 전에 이전 실행의 변경을 복구합니다.
        if is_first_instance:
            cursor_controller.restore()

        if not is_first_instance:
            if options.smoke_test:
                # 자동 시험은 중복 실행 안내창을 기다리지 않고 실패합니다.
                print("[Spotlight smoke] Already running.", file=sys.stderr)
                exit_code = 1
            else:
                QMessageBox.information(
                    None,
                    "Spotlight",
                    "Spotlight가 이미 실행 중입니다.\n"
                    "기존 트레이 아이콘을 사용해 주세요.",
                )
                exit_code = 0

        elif not QSystemTrayIcon.isSystemTrayAvailable():
            if smoke_session is not None:
                smoke_session.record_error("System tray is unavailable.")
            else:
                QMessageBox.critical(
                    None,
                    "Spotlight 실행 오류",
                    "시스템 트레이를 사용할 수 없어 프로그램을 종료합니다.",
                )

        else:
            config_path = (
                smoke_session.settings_path
                if smoke_session is not None
                else get_config_path()
            )
            saved_settings, load_warning = load_settings(config_path)
            overlay = SpotlightOverlay()

            def apply_runtime_settings(settings: HighlightSettings) -> None:
                """검증된 설정을 커서와 강조 원의 실행 상태에 반영합니다.

                확대가 켜져 있고 단계가 달라진 경우 시스템 커서를 변경합니다.
                확대를 끄면 현재 Windows 설정으로 복원합니다.
                설정 파일 저장과 적용 기준값 갱신은 수행하지 않습니다.
                """
                if settings.cursor_enabled:
                    # 색상·휠 설정만 바뀌면 같은 커서를 다시 적용하지 않습니다.
                    if (
                        not cursor_controller.changed
                        or cursor_controller.applied_level != settings.cursor_level
                    ):
                        cursor_controller.apply(settings.cursor_level)

                elif cursor_controller.changed:
                    cursor_controller.restore()

                overlay.apply_settings(settings)

            def rollback_settings(previous: HighlightSettings) -> bool:
                """전달받은 설정으로 실행 상태 복구를 시도합니다.

                성공하면 True를 반환합니다.
                실패하면 오류를 알리고 종료를 요청하여 최종 복원을 시도합니다.
                """
                try:
                    apply_runtime_settings(previous)
                    return True
                except Exception:
                    traceback.print_exc()
                    QMessageBox.critical(
                        settings_dialog,
                        "설정 복구 실패",
                        "이전 상태를 복구하지 못했습니다.\n"
                        "프로그램을 종료하며 커서 복원을 다시 시도합니다.",
                    )
                    application.exit(1)
                    return False

            def preview_settings(settings: HighlightSettings) -> None:
                """저장 없이 설정을 미리 반영합니다.

                반영에 실패하면 직전 프리뷰 상태로 복구를 시도합니다.
                종료 중에는 요청을 무시하여 커서를 다시 변경하지 않습니다.
                """
                if shutting_down:
                    return

                previous = overlay.settings

                try:
                    apply_runtime_settings(settings)
                except Exception:
                    traceback.print_exc()
                    if rollback_settings(previous):
                        QMessageBox.warning(
                            settings_dialog,
                            "설정 프리뷰 실패",
                            "설정을 미리 적용하지 못했습니다.\n"
                            "직전 상태로 복구했습니다.",
                        )

            def apply_settings(settings: HighlightSettings) -> bool:
                """실행 상태 반영과 파일 저장이 성공하면 적용값을 확정합니다.

                실패하면 최근 저장한 설정으로 실행 상태 복구를 시도하고
                False를 반환합니다. 성공하면 saved_settings를 갱신하고
                True를 반환하며, 종료 중에는 적용하지 않습니다.
                """
                nonlocal saved_settings

                if shutting_down:
                    return False

                try:
                    apply_runtime_settings(settings)
                    save_settings(config_path, settings)
                except Exception:
                    traceback.print_exc()
                    if rollback_settings(saved_settings):
                        QMessageBox.warning(
                            settings_dialog,
                            "설정 적용 실패",
                            "설정을 적용하거나 저장하지 못했습니다.\n"
                            "최근 적용값으로 복구했습니다.",
                        )
                    return False

                saved_settings = settings
                return True

            # 파일에 저장된 확대 활성화 여부까지 반영합니다.
            apply_runtime_settings(saved_settings)

            settings_dialog = SettingsDialog(
                settings=saved_settings,
                preview_callback=preview_settings,
                apply_callback=apply_settings,
            )

            # 정보 창은 한 번 생성하고 메뉴 선택 시 재사용합니다.
            info_dialog = InfoDialog()

            tray = SpotlightTray(
                application,
                open_settings=settings_dialog.open_settings,
                open_info=info_dialog.open_info,
            )
            tray.start()
            overlay.start()

            click_effects = ClickEffectManager(application)
            click_effects.start()

            def show_click_effect(button: str, position) -> None:
                """현재 프리뷰 설정으로 새 클릭 효과를 표시합니다."""
                settings = overlay.settings
                if not settings.click_enabled:
                    return

                color = (
                    settings.left_click_color
                    if button == "left"
                    else settings.right_click_color
                )
                click_effects.show_click(
                    button,
                    position,
                    diameter=settings.diameter,
                    color=color,
                    duration_ms=settings.click_duration_ms,
                    style=settings.click_style,
                    line_width=settings.click_line_width,
                )

            def show_wheel_effect(delta: int, position) -> None:
                """휠 효과가 활성화된 경우 현재 설정으로 표시합니다."""
                settings = overlay.settings

                # 표시만 막고 원래 스크롤과 입력 수신은 유지합니다.
                if not settings.wheel_enabled:
                    return

                click_effects.show_wheel(
                    delta,
                    position,
                    diameter=settings.diameter,
                    color=settings.wheel_color,
                    duration_ms=settings.wheel_duration_ms,
                    line_width=settings.wheel_line_width,
                )

            def report_input_error(message: str) -> None:
                """입력 오류 안내를 표준 오류 출력에 기록합니다.

                콘솔 없는 EXE에서는 실행 진입점이 준비한 로그에 기록됩니다.
                """                
                print(
                    f"[Spotlight Raw Input] {message}",
                    file=sys.stderr,
                )

            raw_input = RawMouseInput()
            raw_input.clicked.connect(show_click_effect)
            raw_input.wheel_moved.connect(show_wheel_effect)
            raw_input.input_error.connect(report_input_error)
            raw_input.start()

            if smoke_session is not None:
                # stop() 전에 등록 성공 상태를 보관합니다.
                smoke_session.input_registered = raw_input.registered
                QTimer.singleShot(2000, application.quit)            

            if load_warning is not None:
                if smoke_session is not None:
                    smoke_session.record_error(load_warning)
                else:
                    QMessageBox.warning(
                        None,
                        "설정 파일 확인",
                        load_warning,
                    )

            exit_code = application.exec()

            if raw_input.error_count:
                print(
                    f"[Spotlight Raw Input] errors={raw_input.error_count}",
                    file=sys.stderr,
                )
                exit_code = 1

    except Exception as error:
        traceback.print_exc()

        if smoke_session is not None:
            smoke_session.record_error(f"Startup: {error}")

        # 자동 시험에서는 오류창 때문에 종료가 멈추지 않도록 합니다.
        if application is not None and not options.smoke_test:
            QMessageBox.critical(
                None,
                "Spotlight 실행 오류",
                "프로그램 실행 중 오류가 발생했습니다.\n"
                "콘솔 또는 Spotlight 설정 폴더의 logs 기록을 확인해 주세요.",
            )
        exit_code = 1

    finally:
        # 정리 중 설정 창의 프리뷰가 커서를 다시 변경하지 않게 합니다.
        shutting_down = True

        if smoke_session is not None and raw_input is not None:
            smoke_session.input_error_count = raw_input.error_count

        # 한 자원의 정리 실패가 다른 자원과 커서 복원을 막지 않습니다.
        for resource in (
            raw_input,
            click_effects,
            info_dialog,
            settings_dialog,
            overlay,
            tray,
            cursor_controller,
        ):
            if resource is not None:
                try:
                    resource.stop()
                except Exception as error:
                    traceback.print_exc()
                    if smoke_session is not None:
                        smoke_session.record_error(
                            f"{type(resource).__name__} cleanup: {error}"
                        )
                    exit_code = 1

        if instance_lock is not None:
            try:
                instance_lock.close()
            except Exception as error:
                traceback.print_exc()
                if smoke_session is not None:
                    smoke_session.record_error(f"Lock cleanup: {error}")
                exit_code = 1

    # 복원과 잠금 해제를 모두 시도한 후 최종 상태를 판정합니다.
    if smoke_session is not None:
        try:
            passed = smoke_session.finish(exit_code)
            print("EXE_SMOKE_PASS" if passed else "EXE_SMOKE_FAIL")
            print(f"SMOKE_REPORT: {smoke_session.report_path}")

            if not passed:
                exit_code = 1
        except Exception:
            traceback.print_exc()
            exit_code = 1

    return exit_code