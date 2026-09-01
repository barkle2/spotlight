from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget


HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02
RIDEV_REMOVE = 0x00000001
RIDEV_INPUTSINK = 0x00000100
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_RIGHT_BUTTON_DOWN = 0x0004
RI_MOUSE_WHEEL = 0x0400
WHEEL_DELTA = 120

# 참고: 버튼 UP(0x0002/0x0008)과 수평 휠(RI_MOUSE_HWHEEL, 0x0800)은
# 시각 이펙트 대상이 아니므로 구독하지 않는다. 미사용 상수는 정의하지 않는다.


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
    # usFlags 뒤 정렬 패딩 2바이트는 ctypes 기본 정렬이 처리한다.
    # _pack_ 을 지정하면 구조가 어긋나므로 지정하지 않는다.
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
    """WM_INPUT 수신 전용 숨김 창."""

    def __init__(self, mouse_input: GlobalMouseInput) -> None:
        super().__init__()
        self.mouse_input = mouse_input
        self.setAttribute(Qt.WA_DontShowOnScreen)

    def nativeEvent(self, event_type, message: int) -> tuple[bool, int]:
        if event_type == b"windows_generic_MSG":
            # 이 경로는 모든 네이티브 메시지가 통과한다. 예외가 Qt 디스패처로
            # 전파되면 이벤트 루프가 불안정해지므로 여기서 차단하고 계수만 남긴다.
            try:
                native_message = wintypes.MSG.from_address(int(message))
                if native_message.message == WM_INPUT:
                    self.mouse_input._handle_raw_input(native_message.lParam)
            except Exception:
                self.mouse_input.error_count += 1
        return False, 0


class GlobalMouseInput(QObject):
    clicked = Signal(int, int, str)
    scrolled = Signal(int, int, int)

    def __init__(self) -> None:
        super().__init__()
        self.widget: _RawInputWidget | None = None
        self.started = False
        self.error_count = 0
        self._wheel_residual = 0
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

    def start(self) -> None:
        if self.started:
            return
        self._wheel_residual = 0
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
        self._wheel_residual = 0
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

        # 좌표는 Qt 논리 좌표로 취득한다. GetCursorPos는 물리 픽셀을 돌려주므로
        # 논리 좌표를 쓰는 오버레이(geometry/QCursor.pos)와 고DPI에서 어긋난다.
        position = QCursor.pos()
        x, y = position.x(), position.y()

        if flags & RI_MOUSE_LEFT_BUTTON_DOWN:
            self.clicked.emit(x, y, "left")
        if flags & RI_MOUSE_RIGHT_BUTTON_DOWN:
            self.clicked.emit(x, y, "right")
        if flags & RI_MOUSE_WHEEL:
            delta = ctypes.c_short(raw_input.mouse.usButtonData).value
            if delta:
                # 고해상도 휠은 120 미만 델타를 보낸다. 잔여분을 누적해
                # 노치가 찰 때만 발신하여 이벤트 소실을 막는다.
                self._wheel_residual += delta
                notches = int(self._wheel_residual / WHEEL_DELTA)
                if notches:
                    self._wheel_residual -= notches * WHEEL_DELTA
                    self.scrolled.emit(x, y, notches)
