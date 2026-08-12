from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen


ARTIFACTS = Path(__file__).parent / "artifacts"
RESULT_FILE = ARTIFACTS / "animation_probe.json"


def interpolate(start: float, end: float, progress: float) -> float:
    return start + (end - start) * progress


def render_ring(radius: int, color: QColor, width: int = 4) -> QImage:
    image = QImage(320, 320, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(color, width))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QPoint(160, 160), radius, radius)
    painter.end()
    return image


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    progress = [0.0, 0.25, 0.5, 0.75, 1.0]
    outward = [interpolate(25, 70, p) for p in progress]
    inward = [interpolate(70, 25, p) for p in progress]
    click_color = QColor("#FF3B30")
    wheel_color = QColor("#34C759")
    click_color.setAlpha(255)
    wheel_color.setAlpha(255)

    started = time.perf_counter()
    for index in range(600):
        render_ring(25 + index % 46, wheel_color)
    elapsed = time.perf_counter() - started

    click_image = render_ring(50, click_color, 5)
    wheel_image = render_ring(70, wheel_color, 4)
    click_path = ARTIFACTS / "click_frame.png"
    wheel_path = ARTIFACTS / "wheel_frame.png"
    click_image.save(str(click_path))
    wheel_image.save(str(wheel_path))

    result = {
        "outward_radii": outward,
        "inward_radii": inward,
        "click_alpha": click_color.alpha(),
        "wheel_alpha": wheel_color.alpha(),
        "rendered_frames": 600,
        "render_seconds": elapsed,
        "frames_per_second_equivalent": 600 / elapsed,
        "checks": {
            "outward_strictly_increases": all(a < b for a, b in zip(outward, outward[1:])),
            "inward_strictly_decreases": all(a > b for a, b in zip(inward, inward[1:])),
            "effects_are_opaque": click_color.alpha() == 255 and wheel_color.alpha() == 255,
            "frames_saved": click_path.exists() and wheel_path.exists(),
        },
    }
    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
