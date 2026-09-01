"""[LEGACY] pynput 프로토타입 시절 검증 스크립트.

v0.2.0에서 제품 코드는 pynput을 완전히 제거하고 Windows Raw Input API로
전환했다. 이 스크립트는 pynput 리스너/컨트롤러 동작을 검증하던 것으로
현재 제품 구조와 맞지 않는다.

Raw Input 전환 이후의 검증은 validation/RAW_INPUT_MANUAL_CHECKLIST.md 를
사용한다. 이 파일은 이력 보존 목적으로만 남겨 둔다.

실행하려면 pynput을 별도로 설치해야 한다(제품 의존성이 아니다).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget
try:
    from pynput import mouse
except ImportError as exc:  # pragma: no cover - legacy tool
    raise SystemExit(
        "[LEGACY] 이 스크립트는 pynput이 필요합니다. "
        "제품에서는 v0.2.0부터 pynput을 제거했으므로 기본 설치되지 않습니다.\n"
        "Raw Input 전환 이후 검증은 validation/RAW_INPUT_MANUAL_CHECKLIST.md 를 사용하십시오."
    ) from exc

from spotlight.app import SpotlightApplication


ARTIFACTS = Path(__file__).parent / "artifacts"


class InputTarget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Spotlight stage 3 input target")
        self.resize(420, 260)
        self.clicks = 0
        self.wheels = 0

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicks += 1

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.wheels += 1


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    spotlight = SpotlightApplication(
        app,
        settings_file=Path(__file__).parent / "fixtures" / "stage2_settings.ini",
        recovery_file=ARTIFACTS / "stage3_cursor_recovery.json",
    )
    target = InputTarget()
    target.show()
    target.move(700, 380)
    app.processEvents()
    target_center = target.mapToGlobal(target.rect().center())
    spotlight.start()

    controller = mouse.Controller()
    original_position = controller.position
    worker_error: list[str] = []

    def synthesize() -> None:
        try:
            time.sleep(0.7)
            controller.position = (target_center.x(), target_center.y())
            for _ in range(4):
                controller.click(mouse.Button.left)
            controller.click(mouse.Button.right)
            controller.scroll(0, 1)
            controller.scroll(0, -1)
            time.sleep(0.5)
            controller.position = original_position
        except Exception as exc:
            worker_error.append(repr(exc))

    def capture() -> None:
        QApplication.primaryScreen().grabWindow(0).save(
            str(ARTIFACTS / "stage3_effects_capture.png")
        )
        spotlight.overlay.grab().save(
            str(ARTIFACTS / "stage3_overlay_surface.png")
        )

    def raise_overlay() -> None:
        spotlight.overlay.raise_()

    def add_visible_probe_effect() -> None:
        spotlight.overlay.add_wheel(400, 300, 1)

    result: dict[str, object] = {}

    def finish() -> None:
        result.update(spotlight.report())
        result.update(
            {
                "target_clicks": target.clicks,
                "target_wheels": target.wheels,
                "worker_errors": worker_error,
            }
        )
        spotlight.stop()
        result["input_listener_stopped"] = spotlight.input_stopped
        result["cursor_restored"] = not spotlight.cursor_manager.applied
        result["recovery_file_exists"] = spotlight.cursor_manager.recovery_file.exists()
        result["checks"] = {
            "all_effect_types_detected": set(result["effect_kind_counts"])
            >= {"click-left", "click-right", "wheel-out", "wheel-in"},
            "maximum_three_effects": result["effects_max_active"] == 3,
            "input_passed_through": target.clicks >= 5 and target.wheels >= 2,
            "listener_stopped": spotlight.input_stopped,
            "cursor_restored": not spotlight.cursor_manager.applied,
            "no_recovery_file": not spotlight.cursor_manager.recovery_file.exists(),
            "no_worker_error": not worker_error,
        }
        (ARTIFACTS / "stage3_probe.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        app.quit()

    QTimer.singleShot(450, raise_overlay)
    QTimer.singleShot(700, add_visible_probe_effect)
    QTimer.singleShot(850, capture)
    QTimer.singleShot(1700, finish)
    worker = threading.Thread(target=synthesize, daemon=True)
    worker.start()
    exit_code = app.exec()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code if all(result.get("checks", {}).values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
