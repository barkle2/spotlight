from __future__ import annotations

import argparse
import ctypes
import json
import time
from ctypes import wintypes
from pathlib import Path

from cursor_size_probe import active_cursor_image, reload_cursors


IMAGE_CURSOR = 2
IDC_ARROW = 32512
OCR_NORMAL = 32512
LR_SHARED = 0x8000
ARTIFACTS = Path(__file__).parent / "artifacts"
RECOVERY_FILE = ARTIFACTS / "system_cursor_recovery.json"
RESULT_FILE = ARTIFACTS / "system_cursor_probe.json"


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.CopyImage.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.CopyImage.restype = wintypes.HANDLE
user32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
user32.SetSystemCursor.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL


def load_shared_arrow() -> int:
    handle = user32.LoadImageW(
        None, ctypes.cast(IDC_ARROW, wintypes.LPCWSTR), IMAGE_CURSOR, 0, 0, LR_SHARED
    )
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def create_resized_cursor(source: int, size: int) -> int:
    handle = user32.CopyImage(source, IMAGE_CURSOR, size, size, 0)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def install_normal_cursor(cursor: int) -> None:
    if not user32.SetSystemCursor(cursor, OCR_NORMAL):
        raise ctypes.WinError(ctypes.get_last_error())


def nudge_pointer() -> list[int]:
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    user32.SetCursorPos(point.x + 1, point.y)
    user32.SetCursorPos(point.x, point.y)
    return [int(point.x), int(point.y)]


def move_pointer(x: int, y: int) -> None:
    if not user32.SetCursorPos(x, y):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(0.15)


def recover() -> dict[str, object]:
    restored = reload_cursors()
    RECOVERY_FILE.unlink(missing_ok=True)
    time.sleep(0.2)
    nudge_pointer()
    return {
        "reload_succeeded": restored,
        "active_cursor": active_cursor_image(),
    }


def run(size: int, hold_seconds: float) -> dict[str, object]:
    if not 32 <= size <= 256:
        raise ValueError("size must be between 32 and 256")
    ARTIFACTS.mkdir(exist_ok=True)
    RECOVERY_FILE.write_text(
        json.dumps({"restore_with": "SPI_SETCURSORS"}, indent=2), encoding="utf-8"
    )
    original_position = nudge_pointer()
    move_pointer(10, 10)
    result: dict[str, object] = {
        "target_size": size,
        "active_cursor_before": active_cursor_image(),
        "original_pointer_position": original_position,
    }
    try:
        source = load_shared_arrow()
        resized = create_resized_cursor(source, size)
        install_normal_cursor(resized)
        move_pointer(11, 10)
        move_pointer(10, 10)
        time.sleep(hold_seconds)
        result["active_cursor_applied"] = active_cursor_image()
    finally:
        result["reload_for_restore"] = reload_cursors()
        time.sleep(0.2)
        move_pointer(11, 10)
        move_pointer(10, 10)
        result["active_cursor_restored"] = active_cursor_image()
        move_pointer(*original_position)
        RECOVERY_FILE.unlink(missing_ok=True)
        RESULT_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    result["apply_size_matches"] = (
        result.get("active_cursor_applied", {}).get("width") == size
        and result.get("active_cursor_applied", {}).get("height") == size
    )
    result["restore_matches_before"] = (
        result.get("active_cursor_restored") == result.get("active_cursor_before")
    )
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=48)
    parser.add_argument("--hold-seconds", type=float, default=1.0)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    result = recover() if args.recover else run(args.size, args.hold_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
