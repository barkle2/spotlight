from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spotlight.config import DEFAULT_SETTINGS, load_settings, save_settings


class ConfigTests(unittest.TestCase):
    def test_defaults_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = load_settings(Path(directory) / "settings.ini")
        self.assertEqual(settings.pointer.size, 1)
        self.assertEqual(settings.spotlight.diameter, 120)
        self.assertEqual(settings.click.duration_ms, 180)
        self.assertEqual(settings.wheel.duration_ms, 250)

    def test_invalid_values_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            path.write_text(
                DEFAULT_SETTINGS.replace("size=1", "size=99")
                .replace("opacity=30", "opacity=-1")
                .replace("color=#FFFF00", "color=invalid"),
                encoding="utf-8",
            )
            settings = load_settings(path)
        self.assertEqual(settings.pointer.size, 1)
        self.assertEqual(settings.spotlight.opacity, 30)
        self.assertEqual(settings.spotlight.color, "#FFFF00")

    def test_valid_overrides_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            path.write_text(
                DEFAULT_SETTINGS.replace("size=1", "size=5")
                .replace("diameter=120", "diameter=240")
                .replace("style=fill", "style=outline"),
                encoding="utf-8",
            )
            settings = load_settings(path)
        self.assertEqual(settings.pointer.size, 5)
        self.assertEqual(settings.spotlight.diameter, 240)
        self.assertEqual(settings.spotlight.style, "outline")

    def test_save_and_reload_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            original = load_settings(path)
            save_settings(original, path)
            reloaded = load_settings(path)
        self.assertEqual(reloaded, original)

    def test_obsolete_effect_size_keys_are_removed_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            path.write_text(
                DEFAULT_SETTINGS.replace(
                    "right_color=#007AFF",
                    "right_color=#007AFF\ndiameter=999",
                ).replace(
                    "color=#34C759",
                    "color=#34C759\ninner_diameter=10\nouter_diameter=999",
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)
            save_settings(settings, path)
            saved = path.read_text(encoding="utf-8")

        self.assertNotIn("diameter=999", saved)
        self.assertNotIn("inner_diameter", saved)
        self.assertNotIn("outer_diameter", saved)


if __name__ == "__main__":
    unittest.main()
