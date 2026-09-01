from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import spotlight


VERSION_INFO = ROOT / "packaging" / "version_info.py"


def _version_info_strings() -> dict[str, str]:
    """packaging/version_info.py 의 StringStruct 값을 추출한다.

    PyInstaller 버전 파일은 VSVersionInfo 등 전용 심볼을 쓰므로 import 할 수
    없다. 문자열 파싱으로만 확인한다.
    """
    text = VERSION_INFO.read_text(encoding="utf-8")
    pairs = re.findall(r'StringStruct\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)', text)
    return dict(pairs)


class MetadataTests(unittest.TestCase):
    """__init__.py 와 VERSIONINFO 리소스의 값이 어긋나지 않아야 한다.

    두 곳이 달라지면 실행 파일 속성과 프로그램 정보 탭이 서로 다른 값을
    표시하게 되어 자산 식별이 어긋난다.
    """

    def test_version_is_semantic(self) -> None:
        self.assertRegex(spotlight.__version__, r"\A\d+\.\d+\.\d+\Z")

    def test_metadata_matches_version_info(self) -> None:
        strings = _version_info_strings()
        self.assertEqual(strings.get("ProductName"), spotlight.__product__)
        self.assertEqual(strings.get("CompanyName"), spotlight.__company__)
        self.assertEqual(strings.get("FileDescription"), spotlight.__description__)

    def test_version_numbers_match_version_info(self) -> None:
        strings = _version_info_strings()
        expected = f"{spotlight.__version__}.0"
        self.assertEqual(strings.get("FileVersion"), expected)
        self.assertEqual(strings.get("ProductVersion"), expected)

    def test_filevers_tuple_matches_version(self) -> None:
        text = VERSION_INFO.read_text(encoding="utf-8")
        major, minor, patch = spotlight.__version__.split(".")
        expected = f"({major}, {minor}, {patch}, 0)"
        self.assertIn(f"filevers={expected}", text.replace(" ", " "))
        self.assertIn(f"prodvers={expected}", text.replace(" ", " "))

    def test_filename_and_copyright_match_version_info(self) -> None:
        strings = _version_info_strings()
        self.assertEqual(
            strings.get("OriginalFilename"), spotlight.__original_filename__
        )
        self.assertEqual(strings.get("LegalCopyright"), spotlight.__copyright__)

    def test_company_is_not_placeholder(self) -> None:
        """배포 주체가 비어 있거나 예시값으로 남아 있으면 안 된다."""
        self.assertTrue(spotlight.__company__.strip())
        self.assertNotIn("TODO", spotlight.__company__.upper())
        self.assertNotIn("EXAMPLE", spotlight.__company__.upper())


if __name__ == "__main__":
    unittest.main()
