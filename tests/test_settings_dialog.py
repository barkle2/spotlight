from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from spotlight.config import Settings
from spotlight.settings_dialog import SettingsDialog, executable_path, file_sha256



def make_preview_recorder():
    """포인터 프리뷰 콜백 기록기.

    L-2(프리뷰 디바운스) 패치로 콜백 계약이 (size, immediate=False)로
    확장되었다. 취소 경로는 immediate=True로 호출된다.
    """
    calls = []

    def recorder(size, immediate=False):
        calls.append(size)

    return calls, recorder


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_pointer_slider_previews_without_applying(self) -> None:
        applied = []
        previews, recorder = make_preview_recorder()
        dialog = SettingsDialog(Settings(), applied.append, recorder)
        dialog.spotlight_diameter.setValue(240)

        dialog.pointer_size.setValue(5)

        self.assertEqual(dialog.pointer_size.minimum(), 1)
        self.assertEqual(dialog.pointer_size.maximum(), 15)
        self.assertEqual(dialog.pointer_size_value.text(), "5")
        self.assertEqual(previews, [5])
        self.assertEqual(applied, [])
        dialog.close()

    def test_apply_button_is_enabled_on_pointer_tab(self) -> None:
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

        self.assertTrue(dialog.buttons.button(QDialogButtonBox.Apply).isEnabled())
        dialog.close()

    def test_border_width_is_enabled_only_for_outline_style(self) -> None:
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

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
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

        settings = dialog.current_settings()

        self.assertFalse(hasattr(dialog, "click_diameter"))
        self.assertFalse(hasattr(settings.click, "diameter"))
        dialog.close()

    def test_wheel_sizes_are_not_configurable(self) -> None:
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

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
        previews, recorder = make_preview_recorder()
        dialog = SettingsDialog(Settings(), lambda settings: None, recorder)
        dialog.pointer_size.setValue(5)

        dialog.reject()

        self.assertEqual(previews, [5, 1])
        dialog.close()
    def test_cancel_requests_immediate_preview(self) -> None:
        """취소는 디바운스를 우회해 즉시 복원을 요청해야 한다 (L-2)."""
        calls = []
        dialog = SettingsDialog(
            Settings(),
            lambda settings: None,
            lambda size, immediate=False: calls.append((size, immediate)),
        )
        dialog.pointer_size.setValue(5)

        dialog.reject()

        self.assertEqual(calls[0], (5, False))
        self.assertEqual(calls[-1], (1, True))
        dialog.close()

    def test_notify_preview_error_reverts_slider(self) -> None:
        """디바운스된 프리뷰 실패 통지 시 슬라이더를 되돌려야 한다 (L-2)."""
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )
        dialog.pointer_size.setValue(9)

        with mock.patch.object(QMessageBox, "warning", return_value=None):
            dialog.notify_preview_error("테스트 오류", 3)

        self.assertEqual(dialog.pointer_size.value(), 3)
        self.assertEqual(dialog.pointer_size_value.text(), "3")
        dialog.close()
    def test_about_tab_is_present(self) -> None:
        """설정 창에 정보 탭이 마지막으로 추가되어야 한다."""
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]

        self.assertEqual(labels, ["포인터", "강조 원", "클릭", "휠", "정보"])
        dialog.close()

    def test_about_tab_does_not_affect_settings(self) -> None:
        """정보 탭은 표시 전용이며 저장 대상 설정을 바꾸지 않아야 한다."""
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

        before = dialog.current_settings()
        dialog.tabs.setCurrentIndex(dialog.tabs.count() - 1)
        after = dialog.current_settings()

        self.assertEqual(before, after)
        dialog.close()
    def test_about_tab_shows_product_metadata(self) -> None:
        """정보 탭은 VERSIONINFO 항목과 실행 파일 해시만 표시한다."""
        import spotlight
        from PySide6.QtWidgets import QLabel

        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )
        page = dialog.tabs.widget(dialog.about_tab_index)
        texts = " ".join(label.text() for label in page.findChildren(QLabel))

        self.assertIn(spotlight.__product__, texts)
        self.assertIn(spotlight.__description__, texts)
        self.assertIn(spotlight.__version__, texts)
        self.assertIn(spotlight.__company__, texts)
        self.assertIn(spotlight.__original_filename__, texts)
        self.assertIn(spotlight.__copyright__, texts)
        self.assertIn("SHA-256", texts)

        # 실행 환경·경로 정보는 노출하지 않는다.
        for leaked in ("AppData", "Python", "PySide", "C:\\"):
            self.assertNotIn(leaked, texts)
        dialog.close()

    def test_hash_is_not_computed_on_dialog_open(self) -> None:
        """다이얼로그 열기가 해시 계산으로 느려지지 않아야 한다."""
        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

        self.assertFalse(dialog.hash_computed)
        dialog.close()

    def test_hash_field_is_selectable_but_read_only(self) -> None:
        """클립보드 API 없이 사용자가 직접 선택해 복사할 수 있어야 한다."""
        from PySide6.QtCore import Qt

        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )

        flags = dialog.about_hash.textInteractionFlags()
        self.assertTrue(flags & Qt.TextSelectableByMouse)
        self.assertFalse(flags & Qt.TextEditable)
        dialog.close()

    def test_hash_placeholder_when_running_from_source(self) -> None:
        """소스 실행 중에는 계산 대상 실행 파일이 없다."""
        self.assertIsNone(executable_path())

        dialog = SettingsDialog(
            Settings(), lambda settings: None, lambda size, immediate=False: None
        )
        dialog.tabs.setCurrentIndex(dialog.about_tab_index)

        self.assertNotIn("SHA", dialog.about_hash.text())
        self.assertTrue(dialog.hash_computed)
        dialog.close()

    def test_file_sha256_matches_hashlib(self) -> None:
        import hashlib
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "sample.bin"
            target.write_bytes(b"spotlight" * 200000)

            self.assertEqual(
                file_sha256(target),
                hashlib.sha256(target.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
