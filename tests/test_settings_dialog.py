from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from spotlight.config import Settings
from spotlight.settings_dialog import SettingsDialog


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_pointer_slider_previews_without_applying(self) -> None:
        applied = []
        previews = []
        dialog = SettingsDialog(Settings(), applied.append, previews.append)
        dialog.spotlight_diameter.setValue(240)

        dialog.pointer_size.setValue(5)

        self.assertEqual(dialog.pointer_size.minimum(), 1)
        self.assertEqual(dialog.pointer_size.maximum(), 15)
        self.assertEqual(dialog.pointer_size_value.text(), "5")
        self.assertEqual(previews, [5])
        self.assertEqual(applied, [])
        dialog.close()

    def test_apply_button_is_enabled_on_pointer_tab(self) -> None:
        dialog = SettingsDialog(Settings(), lambda settings: None, lambda size: None)

        self.assertTrue(dialog.buttons.button(QDialogButtonBox.Apply).isEnabled())
        dialog.close()

    def test_border_width_is_enabled_only_for_outline_style(self) -> None:
        dialog = SettingsDialog(Settings(), lambda settings: None, lambda size: None)

        self.assertFalse(dialog.spotlight_border.isEnabled())
        self.assertFalse(dialog.spotlight_border_label.isEnabled())
        dialog.spotlight_style.setCurrentIndex(
            dialog.spotlight_style.findData("outline")
        )
        self.assertTrue(dialog.spotlight_border.isEnabled())
        self.assertTrue(dialog.spotlight_border_label.isEnabled())
        dialog.spotlight_style.setCurrentIndex(dialog.spotlight_style.findData("fill"))
        self.assertFalse(dialog.spotlight_border.isEnabled())
        dialog.close()

    def test_click_size_is_not_configurable(self) -> None:
        dialog = SettingsDialog(Settings(), lambda settings: None, lambda size: None)

        settings = dialog.current_settings()

        self.assertFalse(hasattr(dialog, "click_diameter"))
        self.assertFalse(hasattr(settings.click, "diameter"))
        dialog.close()

    def test_wheel_sizes_are_not_configurable(self) -> None:
        dialog = SettingsDialog(Settings(), lambda settings: None, lambda size: None)

        settings = dialog.current_settings()

        self.assertFalse(hasattr(dialog, "inner_diameter"))
        self.assertFalse(hasattr(dialog, "outer_diameter"))
        self.assertFalse(hasattr(settings.wheel, "outer_diameter"))
        self.assertFalse(hasattr(settings.wheel, "inner_diameter"))
        dialog.close()

    def test_apply_commits_pointer_preview(self) -> None:
        applied = []
        dialog = SettingsDialog(Settings(), applied.append, lambda size: None)
        dialog.pointer_size.setValue(5)

        self.assertTrue(dialog._apply())

        self.assertEqual(applied[-1].pointer.size, 5)
        self.assertEqual(dialog.applied_settings.pointer.size, 5)
        dialog.close()

    def test_cancel_restores_last_applied_pointer_size(self) -> None:
        previews = []
        dialog = SettingsDialog(Settings(), lambda settings: None, previews.append)
        dialog.pointer_size.setValue(5)

        dialog.reject()

        self.assertEqual(previews, [5, 1])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
