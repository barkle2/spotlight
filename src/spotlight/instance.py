"""Windows 이름 있는 뮤텍스로 중복 실행을 차단합니다."""

import ctypes
from ctypes import wintypes


MUTEX_NAME = r"Local\Spotlight.SingleInstance"
ERROR_ALREADY_EXISTS = 183


class SingleInstanceLock:
    """실행 중임을 나타내는 뮤텍스 핸들을 유지합니다."""

    def __init__(self) -> None:
        self.handle = None

        # use_last_error로 Windows API의 오류코드를 안전하게 조회합니다.
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # 64비트 환경에서 핸들이 잘리지 않도록 반환형을 명시합니다.
        self.kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self.kernel32.CreateMutexW.restype = wintypes.HANDLE

        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def acquire(self) -> bool:
        """최초 실행이면 True, 이미 실행 중이면 False를 반환합니다."""
        if self.handle is not None:
            raise RuntimeError("중복 실행 잠금을 이미 확인했습니다.")

        ctypes.set_last_error(0)

        # 소유권을 얻거나 기다리지 않고, 이름 있는 객체의 존재로 판단합니다.
        # 최초 실행은 반환된 핸들을 종료까지 유지해야 합니다.
        handle = self.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        error_code = ctypes.get_last_error()

        if not handle:
            raise ctypes.WinError(error_code)

        self.handle = handle

        if error_code == ERROR_ALREADY_EXISTS:
            # 두 번째 실행이 만든 참조만 닫습니다.
            # 첫 번째 실행의 핸들과 프로그램 상태에는 영향을 주지 않습니다.
            self.close()
            return False

        return True

    def close(self) -> None:
        """이 프로세스의 뮤텍스 핸들을 닫습니다."""
        if self.handle is None:
            return

        if not self.kernel32.CloseHandle(self.handle):
            raise ctypes.WinError(ctypes.get_last_error())

        # 닫힌 핸들을 다시 닫지 않도록 성공 후 비웁니다.
        # 소유권을 획득하지 않았으므로 ReleaseMutex는 호출하지 않습니다.
        self.handle = None