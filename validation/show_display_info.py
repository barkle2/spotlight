"""화면 배치와 Qt 배율 정보를 읽기 전용으로 출력합니다."""

import json
import os
import sys

import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtGui import QCursor, QGuiApplication


def rectangle_info(rectangle) -> dict:
    """Qt 논리 좌표의 사각형을 출력용 정보로 변환합니다."""
    return {
        "x": rectangle.x(),
        "y": rectangle.y(),
        "width": rectangle.width(),
        "height": rectangle.height(),
    }


def main() -> int:
    """창을 표시하거나 설정을 바꾸지 않고 화면 정보를 조회합니다."""
    application = QGuiApplication(sys.argv)
    primary = application.primaryScreen()
    cursor_position = QCursor.pos()
    cursor_screen = application.screenAt(cursor_position)

    screens = []

    for screen in application.screens():
        screens.append({
            "name": screen.name(),
            "primary": screen == primary,
            "logical_geometry": rectangle_info(screen.geometry()),
            "available_geometry": rectangle_info(
                screen.availableGeometry()
            ),
            "device_pixel_ratio": screen.devicePixelRatio(),
            "logical_dpi": round(screen.logicalDotsPerInch(), 2),
        })

    # 배율에 영향을 줄 수 있는 항목만 확인합니다.
    environment_names = (
        "QT_SCALE_FACTOR",
        "QT_SCREEN_SCALE_FACTORS",
        "QT_ENABLE_HIGHDPI_SCALING",
        "QT_FONT_DPI",
        "QT_QPA_PLATFORM",
    )

    report = {
        "pyside_version": PySide6.__version__,
        "qt_version": qVersion(),
        "platform": application.platformName(),
        "screens": screens,
        "cursor": {
            "x": cursor_position.x(),
            "y": cursor_position.y(),
            "screen": (
                cursor_screen.name()
                if cursor_screen is not None
                else None
            ),
        },
        "qt_environment": {
            name: os.environ[name]
            for name in environment_names
            if name in os.environ
        },
    }

    # 한글·장치 이름의 콘솔 인코딩 문제를 피하도록 ASCII로 출력합니다.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())