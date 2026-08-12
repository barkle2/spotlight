from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def create_tray_icon() -> QIcon:
    size = 64
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#FFD60A"))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setBrush(QColor("#202124"))
    painter.drawEllipse(18, 18, 28, 28)
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawEllipse(27, 27, 10, 10)
    painter.end()
    return QIcon(pixmap)


class SpotlightTray(QSystemTrayIcon):
    def __init__(self, app: QApplication, open_settings) -> None:
        super().__init__(create_tray_icon(), app)
        self.setToolTip("Spotlight")
        menu = QMenu()
        settings_action = QAction("설정", menu)
        settings_action.triggered.connect(open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        exit_action = QAction("프로그램 종료", menu)
        exit_action.triggered.connect(app.quit)
        menu.addAction(exit_action)
        self.setContextMenu(menu)
