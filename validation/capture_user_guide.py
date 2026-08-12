from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from spotlight.config import Settings
from spotlight.overlay import SpotlightOverlay
from spotlight.settings_dialog import SettingsDialog
from spotlight.tray import SpotlightTray


OUTPUT = ROOT / "docs" / "images"


def process(app: QApplication) -> None:
    app.processEvents()
    app.processEvents()


def capture_settings(app: QApplication) -> None:
    dialog = SettingsDialog(Settings(), lambda settings: None, lambda size: None)
    dialog.resize(540, 360)
    dialog.show()
    names = ("pointer", "spotlight-fill", "click", "wheel")
    for index, name in enumerate(names):
        dialog.tabs.setCurrentIndex(index)
        process(app)
        dialog.grab().save(str(OUTPUT / f"settings-{name}.png"))

    dialog.tabs.setCurrentIndex(1)
    dialog.spotlight_style.setCurrentIndex(
        dialog.spotlight_style.findData("outline")
    )
    process(app)
    dialog.grab().save(str(OUTPUT / "settings-spotlight-outline.png"))
    dialog.close()


def capture_tray_menu(app: QApplication) -> None:
    tray = SpotlightTray(app, lambda: None)
    menu = tray.contextMenu()
    menu.popup(QPoint(40, 40))
    process(app)
    menu.grab().save(str(OUTPUT / "tray-menu.png"))
    menu.close()


def save_overlay(widget: SpotlightOverlay, name: str) -> None:
    image = QImage(widget.size(), QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor("#28313B"))
    painter = QPainter(image)
    widget.render(painter, QPoint())
    painter.end()
    image.save(str(OUTPUT / name))


def capture_effects(app: QApplication) -> None:
    settings = Settings()
    overlay = SpotlightOverlay(settings.spotlight, settings.click, settings.wheel)
    overlay.setGeometry(0, 0, 520, 320)
    overlay.pointer = QPoint(260, 160)
    overlay.show()
    process(app)

    overlay.add_click(260, 160, "left")
    process(app)
    save_overlay(overlay, "click-effect.png")

    overlay.effects.clear()
    overlay.add_wheel(260, 160, 1)
    process(app)
    save_overlay(overlay, "wheel-effect.png")
    overlay.close()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 9))
    capture_tray_menu(app)
    capture_settings(app)
    capture_effects(app)
    print(f"사용설명서 이미지 생성 완료: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
