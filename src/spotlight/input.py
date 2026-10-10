"""Windows Raw Input으로 마우스 좌우 클릭과 세로 휠을 감지합니다.

숨겨진 수신 창에 마우스 장치만 등록하여 다른 앱 사용 중에도
입력을 받습니다. 효과 위치는 Qt 전역 논리 좌표로 전달하며,
원래 클릭·스크롤과 Windows 기본 메시지 처리를 유지합니다.
"""

import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget


WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0

RIDEV_REMOVE = 0x00000001
RIDEV_INPUTSINK = 0x00000100

RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_RIGHT_BUTTON_DOWN = 0x0004

RI_MOUSE_WHEEL = 0x0400
WHEEL_DELTA = 120

UINT_ERROR = 0xFFFFFFFF
MAX_PACKET_BYTES = 64 * 1024


class RAWINPUTDEVICE(ctypes.Structure):
    """Raw Input 장치 종류와 수신 창을 지정합니다."""

    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    """입력 패킷의 타입·크기·장치 정보를 담습니다."""

    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class MouseButtonParts(ctypes.Structure):
    """버튼 변화와 휠 데이터의 Windows 구조입니다."""

    _fields_ = [
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT),
    ]


class MouseButtons(ctypes.Union):
    """Windows RAWMOUSE의 버튼 공용체를 표현합니다."""

    _anonymous_ = ("parts",)
    _fields_ = [
        ("ulButtons", wintypes.ULONG),
        ("parts", MouseButtonParts),
    ]


class RAWMOUSE(ctypes.Structure):
    """Windows의 정렬 규칙을 유지한 마우스 패킷 구조입니다."""

    _anonymous_ = ("buttons",)
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("buttons", MouseButtons),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RawMouseInput(QWidget):
    """마우스 입력을 Qt 신호로 전달하는 숨겨진 수신 창입니다.

    좌우 버튼을 누르면 clicked 신호를, 누적 휠 입력이 한 단계에
    도달하면 wheel_moved 신호를 보냅니다.
    입력 처리 오류는 횟수를 기록하고 최초 오류만 신호로 알립니다.
    """

    clicked = Signal(str, object)
    wheel_moved = Signal(int, object)    
    input_error = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.registered = False
        self.wheel_remainder = 0        
        self.error_count = 0
        self.error_reported = False

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)

        self.user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(RAWINPUTDEVICE),
            wintypes.UINT,
            wintypes.UINT,
        ]
        self.user32.RegisterRawInputDevices.restype = wintypes.BOOL

        self.user32.GetRawInputData.argtypes = [
            wintypes.HANDLE,
            wintypes.UINT,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.UINT),
            wintypes.UINT,
        ]
        self.user32.GetRawInputData.restype = wintypes.UINT

    def register_device(self, flags: int, target: int | None) -> None:
        """마우스 장치만 등록하거나 해제합니다."""
        device = RAWINPUTDEVICE(
            usUsagePage=0x01,
            usUsage=0x02,
            dwFlags=flags,
            hwndTarget=target,
        )

        success = self.user32.RegisterRawInputDevices(
            ctypes.byref(device),
            1,
            ctypes.sizeof(RAWINPUTDEVICE),
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def start(self) -> None:
        """다른 앱 사용 중에도 입력을 받도록 숨겨진 HWND를 등록합니다."""
        if self.registered:
            return

        # winId()로 native 창을 만들되 show()는 호출하지 않습니다.
        # NOLEGACY 플래그를 사용하지 않아 원래 클릭 처리를 유지합니다.
        self.register_device(RIDEV_INPUTSINK, int(self.winId()))
        self.registered = True
        self.wheel_remainder = 0        
        self.error_reported = False

    def read_mouse_data(self, raw_handle: int) -> tuple[int, int]:
        """입력 패킷을 검증하고 버튼 비트와 휠 입력량을 반환합니다.

        먼저 필요한 버퍼 크기를 조회한 뒤 실제 데이터를 복사합니다.
        크기·헤더·마우스 구조를 확인한 후 데이터를 해석합니다.
        마우스 이외의 패킷은 (0, 0)을 반환하고,
        API 실패나 잘못된 패킷은 예외로 호출부에 전달합니다.
        휠 입력량은 16비트 부호 있는 정수로 해석합니다.
        """
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        required_size = wintypes.UINT(0)

        # 크기만 먼저 조회하여 패킷에 필요한 버퍼를 준비합니다.
        # 허용 범위를 확인한 뒤에만 메모리를 할당합니다.
        result = self.user32.GetRawInputData(
            raw_handle,
            RID_INPUT,
            None,
            ctypes.byref(required_size),
            header_size,
        )

        if result == UINT_ERROR:
            raise ctypes.WinError(ctypes.get_last_error())

        if result != 0:
            raise ValueError("Raw Input 크기 조회 반환값이 잘못되었습니다.")

        if not header_size <= required_size.value <= MAX_PACKET_BYTES:
            raise ValueError("Raw Input 패킷 크기가 허용 범위를 벗어났습니다.")

        buffer = ctypes.create_string_buffer(required_size.value)

        # 준비한 버퍼에 데이터를 복사하고 실제 복사 크기를 검증합니다.
        # 구조체로 해석하기 전에 헤더와 마우스 데이터가 충분한지 확인합니다.
        copied = self.user32.GetRawInputData(
            raw_handle,
            RID_INPUT,
            buffer,
            ctypes.byref(required_size),
            header_size,
        )

        if copied == UINT_ERROR:
            raise ctypes.WinError(ctypes.get_last_error())

        if copied != required_size.value or copied > len(buffer):
            raise ValueError("Raw Input 복사 크기가 일치하지 않습니다.")

        if copied < header_size:
            raise ValueError("Raw Input 헤더가 부족합니다.")

        header = RAWINPUTHEADER.from_buffer_copy(buffer.raw)

        if header.dwSize != copied:
            raise ValueError("Raw Input 헤더의 크기가 일치하지 않습니다.")

        if header.dwType != RIM_TYPEMOUSE:
            return 0, 0

        if copied < header_size + ctypes.sizeof(RAWMOUSE):
            raise ValueError("Raw Input 마우스 데이터가 부족합니다.")

        mouse = RAWMOUSE.from_buffer_copy(buffer.raw, header_size)

        # Windows 구조의 필드는 USHORT지만 휠 입력량은 signed short입니다.
        # 16비트 부호를 해석해야 아래 방향이 음수로 반환됩니다.
        wheel_delta = ctypes.c_short(mouse.usButtonData).value

        return mouse.usButtonFlags, wheel_delta

    def read_button_flags(self, raw_handle: int) -> int:
        """기존 버튼 조회 호출을 유지하기 위한 함수입니다."""
        flags, _ = self.read_mouse_data(raw_handle)
        return flags

    def emit_wheel_steps(self, delta: int, position) -> None:
        """작은 휠 입력을 누적해 120 단위로 효과 신호를 보냅니다."""
        self.wheel_remainder += delta

        # 반대 방향 입력은 기존 잔여값과 부호 합산으로 상쇄됩니다.
        # 한 메시지에 여러 스텝이 들어오면 필요한 만큼 신호를 보냅니다.
        while abs(self.wheel_remainder) >= WHEEL_DELTA:
            step = (
                WHEEL_DELTA
                if self.wheel_remainder > 0
                else -WHEEL_DELTA
            )

            # 신호 처리 전에 차감하여 중복 처리 가능성을 줄입니다.
            self.wheel_remainder -= step
            self.wheel_moved.emit(step, position)    
    
    def nativeEvent(self, event_type, message) -> tuple[bool, int]:
        """WM_INPUT을 해석하여 클릭·휠 신호를 전달합니다.

        등록 상태와 메시지 종류를 확인한 뒤 관련 마우스 입력만 처리합니다.
        예외는 이 메서드에서 기록하며 Windows 메시지 처리로 전파하지 않습니다.
        반환값 (False, 0)은 메시지를 소비하지 않고 기본 처리를 이어가게 합니다.
        """
        if not self.registered:
            return False, 0

        try:
            native_message = wintypes.MSG.from_address(int(message))

            if native_message.message != WM_INPUT:
                return False, 0

            flags, wheel_delta = self.read_mouse_data(native_message.lParam)

            relevant_flags = (
                RI_MOUSE_LEFT_BUTTON_DOWN
                | RI_MOUSE_RIGHT_BUTTON_DOWN
                | RI_MOUSE_WHEEL
            )

            if flags & relevant_flags:
                # 클릭·휠 모두 Qt 전역 논리 좌표를 사용합니다.
                position = QCursor.pos()

                if flags & RI_MOUSE_LEFT_BUTTON_DOWN:
                    self.clicked.emit("left", position)

                if flags & RI_MOUSE_RIGHT_BUTTON_DOWN:
                    self.clicked.emit("right", position)

                if flags & RI_MOUSE_WHEEL and wheel_delta != 0:
                    self.emit_wheel_steps(wheel_delta, position)

        except Exception as error:
            self.error_count += 1

            if not self.error_reported:
                self.error_reported = True
                self.input_error.emit(str(error))

        # 원래 클릭·스크롤과 Windows 기본 처리를 유지합니다.
        return False, 0

    def stop(self) -> None:
        """마우스 입력 등록을 해제하고 숨겨진 창을 닫습니다."""
        if self.registered:
            # REMOVE에서는 hwndTarget이 반드시 NULL이어야 합니다.
            self.register_device(RIDEV_REMOVE, None)
            self.registered = False
        
        self.wheel_remainder = 0
        self.close()