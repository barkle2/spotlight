from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _parse(argv: list[str]):
    """app.parse_args 를 stderr 억제 상태로 호출한다."""
    from spotlight.app import parse_args

    with contextlib.redirect_stderr(io.StringIO()):
        return parse_args(argv)


class CliPathValidationTests(unittest.TestCase):
    """M-6: CLI 경로 인자가 임의 파일 조작 통로가 되지 않아야 한다.

    권한 경계를 넘지는 않으나, 원격 경로는 SMB 인증을 유발하고
    경로 인자는 테스트 하네스 전용이므로 일반 실행에서 차단한다.
    """

    def test_unc_paths_are_rejected(self) -> None:
        from spotlight.app import local_path

        for value in [
            r"\\attacker\share\out.json",
            "//attacker/share/out.json",
            r"  \\attacker\share\out.json  ",
            '"\\\\attacker\\share\\out.json"',
        ]:
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    local_path(value)

    def test_local_paths_are_accepted(self) -> None:
        from spotlight.app import local_path

        for value in ["out.json", r"C:\Temp\out.json", "sub/dir/out.json"]:
            with self.subTest(value=value):
                self.assertIsInstance(local_path(value), Path)

    def test_empty_path_is_rejected(self) -> None:
        from spotlight.app import local_path

        with self.assertRaises(Exception):
            local_path("   ")

    def test_path_options_require_smoke_test(self) -> None:
        for argv in [
            ["--report", "out.json"],
            ["--settings-path", "settings.ini"],
            ["--recovery-path", "recovery.json"],
            ["--report", "out.json", "--settings-path", "s.ini"],
        ]:
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit):
                    _parse(argv)

    def test_path_options_allowed_with_smoke_test(self) -> None:
        args = _parse(["--smoke-test", "--report", "out.json"])
        self.assertEqual(args.report, Path("out.json"))

        args = _parse(
            ["--settings-smoke-test", "--recovery-path", "recovery.json"]
        )
        self.assertEqual(args.recovery_path, Path("recovery.json"))

    def test_plain_launch_still_works(self) -> None:
        args = _parse([])
        self.assertIsNone(args.report)
        self.assertIsNone(args.settings_path)
        self.assertIsNone(args.recovery_path)


class RecoveryMarkerTests(unittest.TestCase):
    """M-5: 복구 마커는 우리가 기록한 형식일 때만 삭제 대상이어야 한다."""

    def _marker_check(self, path: Path) -> bool:
        from spotlight.cursor import is_recovery_marker

        return is_recovery_marker(path)

    def test_valid_marker_is_recognized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cursor_recovery.json"
            target.write_text(
                json.dumps(
                    {
                        "restore_with": "SPI_SETCURSORS",
                        "level": 3,
                        "pixels": 64,
                        "created_at": 0,
                        "pid": 1234,
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(self._marker_check(target))

    def test_foreign_files_are_not_markers(self) -> None:
        """임의 파일을 지정해도 마커로 인정되지 않아야 한다."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)

            document = base / "report.hwp"
            document.write_text("업무 자료", encoding="utf-8")

            other_json = base / "config.json"
            other_json.write_text(json.dumps({"key": "value"}), encoding="utf-8")

            wrong_signature = base / "fake.json"
            wrong_signature.write_text(
                json.dumps({"restore_with": "SOMETHING_ELSE"}), encoding="utf-8"
            )

            oversized = base / "big.json"
            oversized.write_text(
                json.dumps({"restore_with": "SPI_SETCURSORS", "pad": "x" * 8000}),
                encoding="utf-8",
            )

            missing = base / "does-not-exist.json"

            for target in (
                document,
                other_json,
                wrong_signature,
                oversized,
                missing,
            ):
                with self.subTest(target=target.name):
                    self.assertFalse(self._marker_check(target))

    def test_json_array_is_not_a_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "array.json"
            target.write_text(json.dumps(["SPI_SETCURSORS"]), encoding="utf-8")
            self.assertFalse(self._marker_check(target))


if __name__ == "__main__":
    unittest.main()
