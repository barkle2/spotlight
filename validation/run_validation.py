from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget
from pynput import mouse

from environment_probe import collect_environment


ARTIFACTS = Path(__file__).parent / "artifacts"
RESULT_FILE = ARTIFACTS / "gui_input_probe.json"


class Overlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.pointer = QPoint(self.width() // 2, self.height() // 2)
        self.click_flash = False

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 0, 180), 4))
        painter.setBrush(QColor(255, 255, 0, 45))
        painter.drawEllipse(self.pointer, 60, 60)
        if self.click_flash:
            painter.setPen(QPen(QColor(255, 59, 48, 255), 5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.pointer, 45, 45)


class ValidationWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Spotlight validation target")
        self.resize(360, 220)
        self.received_clicks = 0
        self.received_wheels = 0

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.received_clicks += 1

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.received_wheels += 1


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    app = QApplication(sys.argv)
    target = ValidationWindow()
    target.show()
    overlay = Overlay()
    overlay.show()

    events: list[dict[str, object]] = []

    def on_click(x, y, button, pressed):
        events.append(
            {"type": "click", "button": str(button), "pressed": bool(pressed)}
        )
        if pressed:
            overlay.click_flash = True
            overlay.update()
            QTimer.singleShot(180, lambda: (setattr(overlay, "click_flash", False), overlay.update()))

    def on_scroll(x, y, dx, dy):
        events.append({"type": "wheel", "dx": int(dx), "dy": int(dy)})

    listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    listener.start()
    controller = mouse.Controller()
    original_position = controller.position
    capture_info: dict[str, object] = {"captured": False, "colored_pixels": 0}

    def capture_overlay() -> None:
        pixmap = QApplication.primaryScreen().grabWindow(0)
        capture_path = ARTIFACTS / "overlay_capture.png"
        saved = pixmap.save(str(capture_path))
        image = pixmap.toImage()
        center_x, center_y = overlay.pointer.x(), overlay.pointer.y()
        colored = 0
        for y in range(max(0, center_y - 70), min(image.height(), center_y + 71)):
            for x in range(max(0, center_x - 70), min(image.width(), center_x + 71)):
                color = image.pixelColor(x, y)
                if color.red() > 180 and color.green() > 150 and color.blue() < 120:
                    colored += 1
        capture_info.update(
            {"captured": bool(saved), "colored_pixels": colored, "path": str(capture_path)}
        )

    QTimer.singleShot(300, capture_overlay)
    QTimer.singleShot(500, lambda: (target.raise_(), target.activateWindow()))

    def synthesize() -> None:
        time.sleep(0.8)
        center = target.mapToGlobal(target.rect().center())
        controller.position = (center.x(), center.y())
        controller.click(mouse.Button.left)
        controller.click(mouse.Button.right)
        controller.scroll(0, 1)
        controller.scroll(0, -1)
        time.sleep(0.8)
        controller.position = original_position
        QTimer.singleShot(0, app.quit)

    worker = threading.Thread(target=synthesize, daemon=True)
    worker.start()
    QTimer.singleShot(7000, app.quit)
    app.exec()
    listener.stop()
    listener.join(timeout=2)

    click_events = [e for e in events if e["type"] == "click" and e["pressed"]]
    wheel_events = [e for e in events if e["type"] == "wheel"]
    screens = [
        {
            "name": screen.name(),
            "geometry": [
                screen.geometry().x(),
                screen.geometry().y(),
                screen.geometry().width(),
                screen.geometry().height(),
            ],
            "logical_dpi": screen.logicalDotsPerInch(),
            "device_pixel_ratio": screen.devicePixelRatio(),
        }
        for screen in QApplication.screens()
    ]
    result = {
        "environment": collect_environment(),
        "screens": screens,
        "overlay": {
            "translucent": overlay.testAttribute(Qt.WA_TranslucentBackground),
            "mouse_transparent": overlay.testAttribute(Qt.WA_TransparentForMouseEvents),
            "window_transparent_for_input": bool(
                overlay.windowFlags() & Qt.WindowTransparentForInput
            ),
            "tool_window": bool(overlay.windowFlags() & Qt.Tool),
            "always_on_top": bool(overlay.windowFlags() & Qt.WindowStaysOnTopHint),
        },
        "global_input": {
            "pressed_click_events": click_events,
            "wheel_events": wheel_events,
            "target_received_clicks": target.received_clicks,
            "target_received_wheels": target.received_wheels,
        },
        "desktop_capture": capture_info,
    }
    result["checks"] = {
        "overlay_flags": all(result["overlay"].values()),
        "left_and_right_detected": {e["button"] for e in click_events}
        >= {"Button.left", "Button.right"},
        "wheel_both_directions_detected": {int(e["dy"]) > 0 for e in wheel_events}
        >= {True, False},
        "input_passed_to_target": target.received_clicks >= 2
        and target.received_wheels >= 2,
        "overlay_visible_in_desktop_capture": bool(capture_info["captured"])
        and int(capture_info["colored_pixels"]) > 0,
    }
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
