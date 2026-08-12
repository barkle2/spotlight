from __future__ import annotations

import argparse
import ctypes
import json
import time
import winreg
from ctypes import wintypes
from pathlib import Path


CURSOR_KEY = r"Control Panel\Cursors"
CURSOR_VALUE = "CursorBaseSize"
SPI_SETCURSORS = 0x0057
SPIF_SENDCHANGE = 0x0002
ARTIFACTS = Path(__file__).parent / "artifacts"
RECOVERY_FILE = ARTIFACTS / "cursor_recovery.json"
RESULT_FILE = ARTIFACTS / "cursor_probe.json"


def level_to_base_size(level: int) -> int:
    if not 1 <= level <= 15:
        raise ValueError("pointer level must be between 1 and 15")
    return 32 + (level - 1) * 16


def read_state() -> dict[str, object]:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_KEY) as key:
        try:
            value, kind = winreg.QueryValueEx(key, CURSOR_VALUE)
            return {"exists": True, "value": int(value), "kind": int(kind)}
        except FileNotFoundError:
            return {"exists": False, "value": 32, "kind": winreg.REG_DWORD}


def reload_cursors() -> bool:
    return bool(
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETCURSORS, 0, None, SPIF_SENDCHANGE
        )
    )


def write_base_size(value: int) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, CURSOR_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, CURSOR_VALUE, 0, winreg.REG_DWORD, value)


def restore_state(state: dict[str, object]) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, CURSOR_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        if state["exists"]:
            winreg.SetValueEx(
                key, CURSOR_VALUE, 0, int(state["kind"]), int(state["value"])
            )
        else:
            try:
                winreg.DeleteValue(key, CURSOR_VALUE)
            except FileNotFoundError:
                pass
    reload_cursors()


def cursor_metrics() -> dict[str, int]:
    user32 = ctypes.windll.user32
    return {
        "sm_cxcursor": int(user32.GetSystemMetrics(13)),
        "sm_cycursor": int(user32.GetSystemMetrics(14)),
    }


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HANDLE),
        ("hbmColor", wintypes.HANDLE),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", wintypes.LPVOID),
    ]


def active_cursor_image() -> dict[str, object]:
    gdi32 = ctypes.windll.gdi32
    gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID]
    gdi32.GetObjectW.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi32.DeleteObject.restype = wintypes.BOOL
    info = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
    if not ctypes.windll.user32.GetCursorInfo(ctypes.byref(info)):
        return {"available": False}
    icon = ICONINFO()
    if not ctypes.windll.user32.GetIconInfo(info.hCursor, ctypes.byref(icon)):
        return {"available": False}
    try:
        handle = icon.hbmColor or icon.hbmMask
        bitmap = BITMAP()
        if not handle or not gdi32.GetObjectW(
            handle, ctypes.sizeof(BITMAP), ctypes.byref(bitmap)
        ):
            return {"available": False}
        height = int(bitmap.bmHeight)
        if not icon.hbmColor:
            height //= 2
        return {
            "available": True,
            "width": int(bitmap.bmWidth),
            "height": height,
            "hotspot": [int(icon.xHotspot), int(icon.yHotspot)],
        }
    finally:
        if icon.hbmMask:
            gdi32.DeleteObject(icon.hbmMask)
        if icon.hbmColor:
            gdi32.DeleteObject(icon.hbmColor)


def run(level: int, hold_seconds: float) -> dict[str, object]:
    ARTIFACTS.mkdir(exist_ok=True)
    original = read_state()
    RECOVERY_FILE.write_text(
        json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result: dict[str, object] = {
        "target_level": level,
        "target_base_size": level_to_base_size(level),
        "original": original,
        "metrics_before": cursor_metrics(),
        "active_cursor_before": active_cursor_image(),
    }
    try:
        write_base_size(level_to_base_size(level))
        result["reload_after_apply"] = reload_cursors()
        time.sleep(hold_seconds)
        result["applied"] = read_state()
        result["metrics_applied"] = cursor_metrics()
        result["active_cursor_applied"] = active_cursor_image()
    finally:
        restore_state(original)
        result["restored"] = read_state()
        result["metrics_restored"] = cursor_metrics()
        result["active_cursor_restored"] = active_cursor_image()
        result["restoration_matches"] = read_state() == original
        RECOVERY_FILE.unlink(missing_ok=True)
        RESULT_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def recover() -> dict[str, object]:
    if not RECOVERY_FILE.exists():
        return {"recovered": False, "reason": "no recovery file"}
    state = json.loads(RECOVERY_FILE.read_text(encoding="utf-8"))
    restore_state(state)
    RECOVERY_FILE.unlink(missing_ok=True)
    return {"recovered": True, "state": read_state()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=2)
    parser.add_argument("--hold-seconds", type=float, default=1.0)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    result = recover() if args.recover else run(args.level, args.hold_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
