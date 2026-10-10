"""Spotlight 아이콘과 트레이의 정보·설정·종료 메뉴를 제공합니다.

아이콘은 트레이·정보/설정 창·EXE용 ICO 생성에 공통으로 사용합니다.
메뉴는 앱에서 전달한 콜백을 호출하며, 더블 클릭은 설정 창을 엽니다.
"""

from collections.abc import Callable
from PySide6.QtCore import QObject, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import __version__

def create_spotlight_icon() -> QIcon:
    """큰 노란 원과 흰색 커서를 여러 크기의 아이콘으로 만듭니다."""
    icon = QIcon()

    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 같은 디자인을 각 크기에 맞춰 확대·축소합니다.
            painter.scale(size / 32.0, size / 32.0)

            # 32×32 영역 전체에 노란 강조 원을 그립니다.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFD54F"))
            painter.drawEllipse(QRectF(0.0, 0.0, 32.0, 32.0))

            # 화살표 끝은 원 중심에 고정하고 전체를 비례 확대합니다.
            # 네 번째 점인 꼬리 끝을 아이콘 하단 Y=32에 맞춥니다.
            cursor_shape = QPolygonF([
                QPointF(16.0, 16.0),
                QPointF(16.0, 30.3),
                QPointF(19.4, 26.9),
                QPointF(21.9, 32.0),
                QPointF(25.3, 30.3),
                QPointF(22.7, 25.3),
                QPointF(27.8, 25.3),
            ])

            # 흰색 커서에 짙은 외곽선을 넣어 윤곽을 구분합니다.
            outline = QPen(QColor("#182235"))
            outline.setWidthF(1.2)
            outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

            painter.setPen(outline)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawPolygon(cursor_shape)

        finally:
            painter.end()

        icon.addPixmap(pixmap)

    return icon

class SpotlightTray(QObject):
    """정보·설정·종료 메뉴와 더블 클릭을 연결합니다."""

    def __init__(
        self,
        application: QApplication,
        open_settings: Callable[[], None] | None = None,
        open_info: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(application)

        self.open_settings_callback = open_settings
        self.open_info_callback = open_info

        icon = create_spotlight_icon()

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip(f"Spotlight {__version__}")

        # 트레이가 메뉴를 소유하지 않으므로 참조를 유지합니다.
        self.menu = QMenu()

        self.info_action = QAction("정보", self.menu)
        self.info_action.setEnabled(open_info is not None)
        self.info_action.triggered.connect(self.show_info)
        self.menu.addAction(self.info_action)

        self.settings_action = QAction("설정", self.menu)
        self.settings_action.setEnabled(open_settings is not None)
        self.settings_action.triggered.connect(self.show_settings)
        self.menu.addAction(self.settings_action)

        self.menu.addSeparator()

        self.quit_action = QAction("종료", self.menu)
        self.quit_action.triggered.connect(application.quit)
        self.menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self.handle_activation)

    def show_info(self) -> None:
        """앱에서 관리하는 정보 창을 엽니다."""
        if self.open_info_callback is not None:
            self.open_info_callback()

    def show_settings(self) -> None:
        """앱에서 관리하는 설정 창을 엽니다."""
        if self.open_settings_callback is not None:
            self.open_settings_callback()

    def handle_activation(
        self, reason: QSystemTrayIcon.ActivationReason
    ) -> None:
        """트레이 더블 클릭 시 설정 창을 엽니다."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings()

    def start(self) -> None:
        """트레이 아이콘을 표시합니다."""
        self.tray_icon.show()

    def stop(self) -> None:
        """메뉴와 트레이 아이콘을 숨깁니다."""
        self.menu.close()
        self.tray_icon.hide()