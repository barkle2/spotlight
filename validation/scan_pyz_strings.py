from __future__ import annotations

import argparse
import io
import marshal
import struct
import zlib
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


SIGNATURES = (
    "SetWindowsHookEx",
    "GetAsyncKeyState",
    "ToUnicodeEx",
    "GetKeyboardLayout",
    "KeyTranslator",
    "WH_KEYBOARD_LL",
    "KBDLLHOOKSTRUCT",
    "MSLLHOOKSTRUCT",
    "pynput",
)


def extract_pyz(executable: Path) -> bytes:
    archive = CArchiveReader(str(executable))
    pyz_names = [name for name in archive.toc if name.upper().endswith("PYZ.PYZ")]
    if len(pyz_names) != 1:
        raise RuntimeError(f"expected one PYZ.pyz entry, found: {pyz_names}")
    return archive.extract(pyz_names[0])


def read_pyz_modules(pyz_data: bytes) -> dict[str, bytes]:
    if len(pyz_data) < 12 or pyz_data[:4] != b"PYZ\x00":
        raise RuntimeError("invalid PYZ header")
    toc_offset = struct.unpack(">I", pyz_data[8:12])[0]
    stream = io.BytesIO(pyz_data)
    stream.seek(toc_offset)
    toc = marshal.load(stream)
    modules: dict[str, bytes] = {}
    entries = toc.items() if isinstance(toc, dict) else toc
    for name, entry in entries:
        _, position, length = entry
        compressed = pyz_data[position : position + length]
        modules[name] = zlib.decompress(compressed)
    return modules


def scan_modules(modules: dict[str, bytes]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for module_name, module_data in modules.items():
        for signature in SIGNATURES:
            if (
                signature.encode("ascii") in module_data
                or signature.encode("utf-16-le") in module_data
            ):
                findings.append((signature, module_name))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan every module in a PyInstaller PYZ archive for forbidden strings"
    )
    parser.add_argument("executable", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    modules = read_pyz_modules(extract_pyz(args.executable))
    findings = scan_modules(modules)
    print(f"Executable: {args.executable}")
    print(f"PYZ modules scanned: {len(modules)}")
    for signature, module_name in findings:
        print(f"FOUND {signature}: {module_name}")
    print(f"Detections: {len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
