from __future__ import annotations

import ctypes
import json
import os
import time
import winreg
from ctypes import wintypes
from pathlib import Path

from cursor_size_probe import reload_cursors


IMAGE_CURSOR = 2
LR_SHARED = 0x8000
CURSOR_KEY = r"Control Panel\Cursors"
ARTIFACTS = Path(__file__).parent / "artifacts"
RECOVERY_FILE = ARTIFACTS / "all_system_cursors_recovery.json"
RESULT_FILE = ARTIFACTS / "all_system_cursors_probe.json"

CURSORS = {
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

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadCursorFromFileW.argtypes = [wintypes.LPCWSTR]
user32.LoadCursorFromFileW.restype = wintypes.HANDLE
user32.CopyImage.argtypes = [
    wintypes.HANDLE, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.CopyImage.restype = wintypes.HANDLE
user32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
user32.SetSystemCursor.restype = wintypes.BOOL


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD), ("hbmMask", wintypes.HANDLE),
        ("hbmColor", wintypes.HANDLE),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG), ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG), ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD), ("bmBitsPixel", wintypes.WORD),
        ("bmBits", wintypes.LPVOID),
    ]


user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wintypes.BOOL


gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID]
gdi32.GetObjectW.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL


def cursor_image_size(handle: int) -> list[int] | None:
    icon = ICONINFO()
    if not user32.GetIconInfo(handle, ctypes.byref(icon)):
        return None
    try:
        bitmap_handle = icon.hbmColor or icon.hbmMask
        bitmap = BITMAP()
        if not bitmap_handle or not gdi32.GetObjectW(
            bitmap_handle, ctypes.sizeof(BITMAP), ctypes.byref(bitmap)
        ):
            return None
        height = int(bitmap.bmHeight) if icon.hbmColor else int(bitmap.bmHeight) // 2
        return [int(bitmap.bmWidth), height]
    finally:
        if icon.hbmMask:
            gdi32.DeleteObject(icon.hbmMask)
        if icon.hbmColor:
            gdi32.DeleteObject(icon.hbmColor)


def configured_path(name: str) -> str:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_KEY) as key:
        try:
            value, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return ""
    return os.path.expandvars(str(value))


def load_source(name: str, resource_id: int) -> tuple[int, str]:
    path = configured_path(name)
    if path:
        handle = user32.LoadCursorFromFileW(path)
        if handle:
            return int(handle), path
    handle = user32.LoadImageW(
        None,
        ctypes.cast(ctypes.c_void_p(resource_id), wintypes.LPCWSTR),
        IMAGE_CURSOR,
        0,
        0,
        LR_SHARED,
    )
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle), f"system-resource:{resource_id}"


def run(size: int = 48) -> dict[str, object]:
    ARTIFACTS.mkdir(exist_ok=True)
    RECOVERY_FILE.write_text(
        json.dumps({"restore_with": "SPI_SETCURSORS"}, indent=2), encoding="utf-8"
    )
    results: dict[str, object] = {}
    try:
        for name, resource_id in CURSORS.items():
            item: dict[str, object] = {"id": resource_id}
            try:
                source, source_description = load_source(name, resource_id)
                item["source"] = source_description
                resized = user32.CopyImage(source, IMAGE_CURSOR, size, size, 0)
                if not resized:
                    raise ctypes.WinError(ctypes.get_last_error())
                item["copy_succeeded"] = True
                item["copied_image_size"] = cursor_image_size(int(resized))
                if not user32.SetSystemCursor(resized, resource_id):
                    raise ctypes.WinError(ctypes.get_last_error())
                item["install_succeeded"] = True
            except Exception as exc:
                item["error"] = repr(exc)
                item.setdefault("copy_succeeded", False)
                item.setdefault("install_succeeded", False)
            results[name] = item
        time.sleep(0.5)
    finally:
        restored = reload_cursors()
        RECOVERY_FILE.unlink(missing_ok=True)
    summary = {
        "target_size": size,
        "cursor_count": len(CURSORS),
        "copy_success_count": sum(bool(v.get("copy_succeeded")) for v in results.values()),
        "install_success_count": sum(bool(v.get("install_succeeded")) for v in results.values()),
        "size_match_count": sum(v.get("copied_image_size") == [size, size] for v in results.values()),
        "restore_succeeded": restored,
        "results": results,
    }
    RESULT_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
