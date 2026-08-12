from __future__ import annotations

import ctypes
import json
import os
import time
import winreg
from ctypes import wintypes
from pathlib import Path


IMAGE_CURSOR = 2
LR_SHARED = 0x8000
SPI_SETCURSORS = 0x0057
SPIF_SENDCHANGE = 0x0002
CURSOR_KEY = r"Control Panel\Cursors"

SYSTEM_CURSORS = {
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
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadCursorFromFileW.argtypes = [wintypes.LPCWSTR]
user32.LoadCursorFromFileW.restype = wintypes.HANDLE
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
user32.DestroyCursor.argtypes = [wintypes.HANDLE]
user32.DestroyCursor.restype = wintypes.BOOL
user32.SystemParametersInfoW.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    wintypes.LPVOID,
    wintypes.UINT,
]
user32.SystemParametersInfoW.restype = wintypes.BOOL


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


gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = wintypes.BOOL
user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wintypes.BOOL
gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID]
gdi32.GetObjectW.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL


def pointer_level_to_pixels(level: int) -> int:
    if not 1 <= level <= 15:
        raise ValueError("포인터 크기는 1부터 15까지여야 합니다.")
    return 32 + (level - 1) * 16


def reload_saved_system_cursors() -> bool:
    return bool(user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, SPIF_SENDCHANGE))


def active_cursor_image_size() -> list[int] | None:
    cursor = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
    if not user32.GetCursorInfo(ctypes.byref(cursor)):
        return None
    icon = ICONINFO()
    if not user32.GetIconInfo(cursor.hCursor, ctypes.byref(icon)):
        return None
    try:
        handle = icon.hbmColor or icon.hbmMask
        bitmap = BITMAP()
        if not handle or not gdi32.GetObjectW(
            handle, ctypes.sizeof(BITMAP), ctypes.byref(bitmap)
        ):
            return None
        height = int(bitmap.bmHeight) if icon.hbmColor else int(bitmap.bmHeight) // 2
        return [int(bitmap.bmWidth), height]
    finally:
        if icon.hbmMask:
            gdi32.DeleteObject(icon.hbmMask)
        if icon.hbmColor:
            gdi32.DeleteObject(icon.hbmColor)


class CursorManager:
    def __init__(self, recovery_file: Path) -> None:
        self.recovery_file = recovery_file
        self.applied = False
        self.applied_level: int | None = None
        self.applied_count = 0

    def recover_if_needed(self) -> bool:
        if not self.recovery_file.exists():
            return False
        restored = reload_saved_system_cursors()
        if restored:
            self.recovery_file.unlink(missing_ok=True)
        return restored

    def _configured_path(self, name: str) -> str:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_KEY) as key:
            try:
                value, _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                return ""
        return os.path.expandvars(str(value))

    def _load_source(self, name: str, resource_id: int) -> tuple[int, bool]:
        path = self._configured_path(name)
        if path:
            handle = user32.LoadCursorFromFileW(path)
            if handle:
                return int(handle), True
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
        return int(handle), False

    def _write_recovery_marker(self, level: int, pixels: int) -> None:
        self.recovery_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.recovery_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "restore_with": "SPI_SETCURSORS",
                    "level": level,
                    "pixels": pixels,
                    "created_at": time.time(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, self.recovery_file)

    def apply(self, level: int) -> int:
        pixels = pointer_level_to_pixels(level)
        if self.applied:
            self.restore()
        self._write_recovery_marker(level, pixels)
        installed = 0
        try:
            for name, resource_id in SYSTEM_CURSORS.items():
                source, owned = self._load_source(name, resource_id)
                try:
                    resized = user32.CopyImage(source, IMAGE_CURSOR, pixels, pixels, 0)
                    if not resized:
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    if owned:
                        user32.DestroyCursor(source)
                if not user32.SetSystemCursor(resized, resource_id):
                    user32.DestroyCursor(resized)
                    raise ctypes.WinError(ctypes.get_last_error())
                installed += 1
        except Exception:
            reload_saved_system_cursors()
            self.recovery_file.unlink(missing_ok=True)
            raise

        self.applied = True
        self.applied_level = level
        self.applied_count = installed
        return installed

    def restore(self) -> bool:
        if not self.applied and not self.recovery_file.exists():
            return True
        restored = reload_saved_system_cursors()
        if restored:
            self.recovery_file.unlink(missing_ok=True)
            self.applied = False
            self.applied_level = None
            self.applied_count = 0
        return restored
