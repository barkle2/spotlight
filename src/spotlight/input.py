from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QWidget


HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02
RIDEV_REMOVE = 0x00000001
RIDEV_INPUTSINK = 0x00000100
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP = 0x0002
RI_MOUSE_RIGHT_BUTTON_DOWN = 0x0004
RI_MOUSE_RIGHT_BUTTON_UP = 0x0008
RI_MOUSE_WHEEL = 0x0400
RI_MOUSE_HWHEEL = 0x0800
WHEEL_DELTA = 120


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = (
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    )


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = (
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    )


class _RAWBUTTONS(ctypes.Structure):
    _fields_ = (
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT),
    )


class _RAWBUTTONUNION(ctypes.Union):
    _anonymous_ = ("buttons",)
    _fields_ = (
        ("ulButtons", wintypes.ULONG),
        ("buttons", _RAWBUTTONS),
    )


class RAWMOUSE(ctypes.Structure):
    _anonymous_ = ("button_data",)
    _fields_ = (
        ("usFlags", wintypes.USHORT),
        ("button_data", _RAWBUTTONUNION),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    )


class _RAWINPUTUNION(ctypes.Union):
    _fields_ = (("mouse", RAWMOUSE),)


class RAWINPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = (
        ("header", RAWINPUTHEADER),
        ("data", _RAWINPUTUNION),
    )


class _RawInputWidget(QWidget):
    def __init__(self, mouse_input: GlobalMouseInput) -> None:
        super().__init__()
        self.mouse_input = mouse_input
        self.setAttribute(Qt.WA_DontShowOnScreen)

    def nativeEvent(self, event_type, message: int) -> tuple[bool, int]:
        if event_type == b"windows_generic_MSG":
            native_message = ctypes.cast(
                int(message), ctypes.POINTER(wintypes.MSG)
            ).contents
            if native_message.message == WM_INPUT:
                self.mouse_input._handle_raw_input(native_message.lParam)
        return False, 0


class GlobalMouseInput(QObject):
    clicked = Signal(int, int, str)
    scrolled = Signal(int, int, int)

    def __init__(self) -> None:
        super().__init__()
        self.widget: _RawInputWidget | None = None
        self.started = False
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.RegisterRawInputDevices.argtypes = (
            ctypes.POINTER(RAWINPUTDEVICE),
            wintypes.UINT,
            wintypes.UINT,
        )
        self._user32.RegisterRawInputDevices.restype = wintypes.BOOL
        self._user32.GetRawInputData.argtypes = (
            wintypes.HANDLE,
            wintypes.UINT,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.UINT),
            wintypes.UINT,
        )
        self._user32.GetRawInputData.restype = wintypes.UINT
        self._user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
        self._user32.GetCursorPos.restype = wintypes.BOOL

    def start(self) -> None:
        if self.started:
            return
        self.widget = _RawInputWidget(self)
        hwnd = int(self.widget.winId())
        device = RAWINPUTDEVICE(
            HID_USAGE_PAGE_GENERIC,
            HID_USAGE_GENERIC_MOUSE,
            RIDEV_INPUTSINK,
            hwnd,
        )
        if not self._user32.RegisterRawInputDevices(
            ctypes.byref(device), 1, ctypes.sizeof(RAWINPUTDEVICE)
        ):
            error = ctypes.get_last_error()
            self.widget.close()
            self.widget.deleteLater()
            self.widget = None
            raise ctypes.WinError(error)
        self.started = True

    def stop(self) -> bool:
        if self.widget is None:
            self.started = False
            return True
        device = RAWINPUTDEVICE(
            HID_USAGE_PAGE_GENERIC,
            HID_USAGE_GENERIC_MOUSE,
            RIDEV_REMOVE,
            None,
        )
        stopped = bool(
            self._user32.RegisterRawInputDevices(
                ctypes.byref(device), 1, ctypes.sizeof(RAWINPUTDEVICE)
            )
        )
        self.widget.close()
        self.widget.deleteLater()
        self.widget = None
        self.started = False
        return stopped

    def _handle_raw_input(self, raw_input_handle: int) -> None:
        size = wintypes.UINT()
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        result = self._user32.GetRawInputData(
            raw_input_handle, RID_INPUT, None, ctypes.byref(size), header_size
        )
        if result == wintypes.UINT(-1).value or size.value == 0:
            return
        buffer = ctypes.create_string_buffer(size.value)
        result = self._user32.GetRawInputData(
            raw_input_handle,
            RID_INPUT,
            buffer,
            ctypes.byref(size),
            header_size,
        )
        if result == wintypes.UINT(-1).value or result < ctypes.sizeof(RAWINPUT):
            return
        raw_input = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents
        if raw_input.header.dwType != RIM_TYPEMOUSE:
            return
        flags = raw_input.mouse.usButtonFlags
        if not flags:
            return
        point = wintypes.POINT()
        if not self._user32.GetCursorPos(ctypes.byref(point)):
            return
        if flags & RI_MOUSE_LEFT_BUTTON_DOWN:
            self.clicked.emit(point.x, point.y, "left")
        if flags & RI_MOUSE_RIGHT_BUTTON_DOWN:
            self.clicked.emit(point.x, point.y, "right")
        if flags & RI_MOUSE_WHEEL:
            delta = ctypes.c_short(raw_input.mouse.usButtonData).value
            if delta:
                self.scrolled.emit(point.x, point.y, int(delta / WHEEL_DELTA))
