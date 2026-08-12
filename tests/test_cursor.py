from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spotlight.cursor import pointer_level_to_pixels


class CursorSizeTests(unittest.TestCase):
    def test_levels_map_to_expected_pixels(self) -> None:
        self.assertEqual(pointer_level_to_pixels(1), 32)
        self.assertEqual(pointer_level_to_pixels(2), 48)
        self.assertEqual(pointer_level_to_pixels(15), 256)

    def test_invalid_levels_raise(self) -> None:
        with self.assertRaises(ValueError):
            pointer_level_to_pixels(0)
        with self.assertRaises(ValueError):
            pointer_level_to_pixels(16)


if __name__ == "__main__":
    unittest.main()
