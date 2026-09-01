from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spotlight.cursor import (
    ALLOWED_CURSOR_SUFFIXES,
    SYSTEM_CURSORS,
    pointer_level_to_pixels,
)


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
    def test_system_cursor_set_is_complete(self) -> None:
        """Windows 표준 OCR_ 커서 14종이 모두 정의되어야 한다."""
        expected = {
            "Arrow": 32512,
            "IBeam": 32513,
            "Wait": 32514,
            "Crosshair": 32515,
            "UpArrow": 32516,
            "SizeNWSE": 32642,
            "SizeNESW": 32643,
            "SizeWE": 32644,
            "SizeNS": 32645,
            "SizeAll": 32646,
            "No": 32648,
            "Hand": 32649,
            "AppStarting": 32650,
            "Help": 32651,
        }
        self.assertEqual(SYSTEM_CURSORS, expected)
        self.assertEqual(len(SYSTEM_CURSORS), 14)

    def test_allowed_cursor_suffixes_are_restricted(self) -> None:
        """M-4: 레지스트리 경로는 커서 파일 확장자로만 제한되어야 한다."""
        self.assertEqual(ALLOWED_CURSOR_SUFFIXES, {".cur", ".ani"})


if __name__ == "__main__":
    unittest.main()
