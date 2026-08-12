from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spotlight.overlay import Effect


class EffectTests(unittest.TestCase):
    def make_effect(self, start: float, end: float) -> Effect:
        return Effect(
            kind="test",
            position=QPointF(10, 20),
            started_at=100.0,
            duration_ms=200,
            start_diameter=start,
            end_diameter=end,
            color=QColor("#FF0000"),
            line_width=4,
        )

    def test_outward_interpolation(self) -> None:
        effect = self.make_effect(50, 150)
        self.assertEqual(effect.diameter(100.0), 50)
        self.assertAlmostEqual(effect.diameter(100.1), 100)
        self.assertEqual(effect.diameter(100.2), 150)

    def test_inward_interpolation(self) -> None:
        effect = self.make_effect(150, 50)
        self.assertAlmostEqual(effect.diameter(100.1), 100)

    def test_expiration(self) -> None:
        effect = self.make_effect(50, 150)
        self.assertFalse(effect.expired(100.19))
        self.assertTrue(effect.expired(100.2))


if __name__ == "__main__":
    unittest.main()
