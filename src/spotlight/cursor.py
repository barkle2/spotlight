"""Windows 시스템 커서의 확대·복원과 복구 표식을 관리합니다.

현재 사용자 커서 파일을 읽기 전용으로 조회하고 경로를 검증합니다.
단일 실행 잠금 아래에서 커서 14종을 준비하고 복구 표식을 등록한 뒤
시스템 커서를 변경합니다. 복원은 현재 Windows 커서 설정을 기준으로
수행하며, 복원 성공을 확인한 뒤에만 복구 표식을 삭제합니다.
"""

import os
from pathlib import Path
import winreg
import json
import logging
import re
import tempfile
import uuid
import ctypes
from ctypes import wintypes
from collections.abc import Callable

from .config import get_config_path, MIN_CURSOR_LEVEL, MAX_CURSOR_LEVEL
from .instance import SingleInstanceLock

CURSOR_REGISTRY_KEY = r"Control Panel\Cursors"

# 현재 사용자 커서 구성의 레지스트리 값 이름과 Windows 식별자입니다.
# 이 목록의 14종을 확대 대상으로 사용하며, 목록 정의 자체는 커서를 변경하지 않습니다.
SYSTEM_CURSOR_IDS = {
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


def cursor_size_from_level(level: int) -> int:
    """1~15단계를 32~256픽셀 크기로 변환합니다."""
    # bool이 정수로 취급되는 것을 막기 위해 정확한 타입을 검사합니다.
    if type(level) is not int:
        raise ValueError("포인터 크기 단계는 정수여야 합니다.")

    if not MIN_CURSOR_LEVEL <= level <= MAX_CURSOR_LEVEL:
        raise ValueError("포인터 크기 단계는 1~15 범위여야 합니다.")

    return 32 + (level - 1) * 16


def validate_cursor_path(
    value: object,
    registry_type: int,
) -> Path | None:
    """사용 가능한 커서 파일 경로를 반환하고 잘못된 값은 거부합니다.

    None은 후속 로드 단계에서 기본 커서를 사용해야 한다는 의미입니다.
    확장자·실존 검사는 파일 내용의 안전성이나 로드 성공을 보장하지
    않으므로 실제 로드 실패도 별도로 처리해야 합니다.
    """
    if type(registry_type) is not int:
        return None

    if registry_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        return None

    if not isinstance(value, str) or not value:
        return None

    # 환경변수 확장형 레지스트리 값만 확장합니다.
    expanded = (
        os.path.expandvars(value)
        if registry_type == winreg.REG_EXPAND_SZ
        else value
    )

    try:
        candidate = Path(expanded)

        if candidate.suffix.lower() not in (".cur", ".ani"):
            return None

        # 실제 대상 경로까지 해석하고 파일 존재를 확인합니다.
        resolved = candidate.resolve(strict=True)

        # 심볼릭 링크 등의 실제 대상도 허용 확장자인지 확인합니다.
        if resolved.suffix.lower() not in (".cur", ".ani"):
            return None

        if not resolved.is_file():
            return None

        return resolved

    except (OSError, RuntimeError, ValueError):
        # 없는 파일·잘못된 경로·경로 해석 오류는 기본 커서 대상으로 둡니다.
        return None


def read_cursor_paths() -> dict[str, Path | None]:
    """현재 사용자 커서 경로를 읽기 전용으로 조회·검증합니다."""
    paths: dict[str, Path | None] = {
        name: None for name in SYSTEM_CURSOR_IDS
    }

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            CURSOR_REGISTRY_KEY,
            0,
            winreg.KEY_READ,
        ) as key:
            for name in SYSTEM_CURSOR_IDS:
                try:
                    value, registry_type = winreg.QueryValueEx(key, name)
                except OSError:
                    # 일부 값이 없어도 다른 커서 값은 계속 확인합니다.
                    continue

                paths[name] = validate_cursor_path(value, registry_type)

    except OSError:
        # 키가 없거나 읽기 권한이 없으면 모든 대상을 기본 커서로 둡니다.
        # 레지스트리에 값을 쓰거나 사용자 설정을 변경하지 않습니다.
        pass

    return paths

MAX_RECOVERY_BYTES = 4096
RECOVERY_TOKEN_PATTERN = re.compile(r"\A[0-9a-f]{32}\Z")
logger = logging.getLogger(__name__)


def get_recovery_marker_path() -> Path:
    """사용자 설정 폴더의 복구 표식 경로를 반환합니다."""
    return get_config_path().with_name("cursor-recovery.json")


def _validate_recovery_marker(value: object) -> dict:
    """우리 프로그램의 복구 표식 형식인지 검사합니다."""
    if not isinstance(value, dict):
        raise ValueError("복구 표식은 JSON 객체여야 합니다.")

    if value.get("application") != "Spotlight":
        raise ValueError("Spotlight 복구 표식이 아닙니다.")

    version = value.get("version")
    if type(version) is not int or version != 1:
        raise ValueError("지원하지 않는 복구 표식 버전입니다.")

    if value.get("restore_with") != "SPI_SETCURSORS":
        raise ValueError("지원하지 않는 커서 복원 방식입니다.")

    token = value.get("token")
    if not isinstance(token, str):
        raise ValueError("복구 표식 토큰이 없습니다.")

    if RECOVERY_TOKEN_PATTERN.fullmatch(token) is None:
        raise ValueError("복구 표식 토큰 형식이 잘못되었습니다.")

    # 형식과 토큰은 표식 비교용이며 작성자 인증 수단은 아닙니다.
    return value


def _read_recovery_marker(path: Path) -> dict | None:
    """표식을 읽어 검증하고, 파일이 없으면 None을 반환합니다."""
    if path.is_symlink():
        raise ValueError("심볼릭 링크인 복구 표식은 처리하지 않습니다.")

    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_RECOVERY_BYTES + 1)
    except FileNotFoundError:
        return None

    if len(data) > MAX_RECOVERY_BYTES:
        raise ValueError("복구 표식이 허용 크기를 초과했습니다.")

    value = json.loads(data.decode("utf-8"))
    return _validate_recovery_marker(value)


def _delete_recovery_marker(path: Path, expected: dict) -> None:
    """복원 대상으로 확인했던 표식과 일치할 때만 삭제합니다."""
    current = _read_recovery_marker(path)

    if current is None:
        return

    if current != expected:
        raise ValueError("복원 도중 표식 내용이 바뀌어 삭제하지 않습니다.")

    path.unlink()


class CursorRecovery:
    """잠금·복원 성공·표식 삭제 순서를 관리합니다."""

    def __init__(
        self,
        marker_path: Path,
        instance_lock: SingleInstanceLock,
        restore_callback: Callable[[], bool],
    ) -> None:
        self.marker_path = marker_path
        self.instance_lock = instance_lock
        self.restore_callback = restore_callback

    def _require_lock(self) -> None:
        """단일 실행 잠금을 보유한 경우에만 복구 파일에 접근합니다."""
        if not isinstance(self.instance_lock, SingleInstanceLock):
            raise RuntimeError("SingleInstanceLock 객체가 필요합니다.")

        if self.instance_lock.handle is None:
            raise RuntimeError("커서 복구 작업 전에 실행 잠금이 필요합니다.")

    def prepare(self) -> None:
        """커서를 변경하기 전에 완성된 복구 표식을 새로 등록합니다."""
        self._require_lock()
        path = self.marker_path

        # 손상된 파일이나 다른 파일도 임의로 덮어쓰지 않습니다.
        # 기존 표식은 먼저 restore_pending()으로 복구해야 합니다.
        if os.path.lexists(path):
            raise FileExistsError("기존 복구 표식을 먼저 확인해야 합니다.")

        marker = {
            "application": "Spotlight",
            "version": 1,
            "restore_with": "SPI_SETCURSORS",
            "token": uuid.uuid4().hex,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix="cursor-recovery-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                json.dump(marker, stream, ensure_ascii=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

            # 완성된 파일을 새 이름으로 등록합니다.
            # 같은 이름이 이미 생겼다면 실패하므로 덮어쓰지 않습니다.
            # 지원하지 않는 파일시스템에서는 예외를 전달하고 중단합니다.
            os.link(temporary_path, path)

        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "임시 복구 표식 정리 실패: %s",
                        temporary_path,
                        exc_info=True,
                    )

    def restore_pending(self) -> bool:
        """유효한 표식이 있으면 복원 성공 후 삭제합니다.

        표식이 없으면 False, 복원과 표식 정리가 끝나면 True입니다.
        오류가 발생하면 예외를 전달하고 남은 표식을 보존합니다.
        """
        self._require_lock()

        marker = _read_recovery_marker(self.marker_path)
        if marker is None:
            return False

        # 주입된 복원 콜백을 호출하고, 명시적인 성공 결과를 확인합니다.
        # 실패하거나 예외가 발생하면 복구 표식을 남겨 재시도할 수 있게 합니다.
        if self.restore_callback() is not True:
            raise RuntimeError("커서 복원에 실패해 표식을 유지합니다.")

        self._require_lock()
        _delete_recovery_marker(self.marker_path, marker)
        return True

IMAGE_CURSOR = 2
LR_LOADFROMFILE = 0x0010
SPI_SETCURSORS = 0x0057

class WindowsCursorApi:
    """Windows 커서 API와 프로그램 소유 핸들을 관리합니다."""

    def __init__(self, instance_lock: SingleInstanceLock) -> None:
        self.instance_lock = instance_lock
        self.owned_handles: set[int] = set()

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)

        # 이름 인자는 파일 문자열 포인터 또는 정수 리소스 식별자입니다.
        self.user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            ctypes.c_void_p,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.LoadImageW.restype = wintypes.HANDLE

        self.user32.LoadCursorW.argtypes = [
            wintypes.HINSTANCE,
            ctypes.c_void_p,
        ]
        self.user32.LoadCursorW.restype = wintypes.HANDLE

        self.user32.CopyImage.argtypes = [
            wintypes.HANDLE,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.CopyImage.restype = wintypes.HANDLE        

        self.user32.SetSystemCursor.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        self.user32.SetSystemCursor.restype = wintypes.BOOL

        self.user32.DestroyCursor.argtypes = [wintypes.HANDLE]
        self.user32.DestroyCursor.restype = wintypes.BOOL

        self.user32.SystemParametersInfoW.argtypes = [
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            wintypes.UINT,
        ]
        self.user32.SystemParametersInfoW.restype = wintypes.BOOL

    def _require_lock(self) -> None:
        """단일 실행 잠금을 보유했는지 확인합니다."""
        if not isinstance(self.instance_lock, SingleInstanceLock):
            raise RuntimeError("SingleInstanceLock 객체가 필요합니다.")

        if self.instance_lock.handle is None:
            raise RuntimeError("커서 작업 전에 실행 잠금이 필요합니다.")

    def load_scaled_cursor(
        self,
        cursor_name: str,
        level: int,
        path: Path | None = None,
    ) -> int:
        """파일 또는 기본 리소스에서 지정 크기의 커서를 로드합니다."""
        self._require_lock()

        if cursor_name not in SYSTEM_CURSOR_IDS:
            raise ValueError("지원하지 않는 시스템 커서 이름입니다.")

        size = cursor_size_from_level(level)
        handle = None

        # 호출부에서 검증했더라도 API에 전달하기 전에 다시 확인합니다.
        valid_path = (
            validate_cursor_path(str(path), winreg.REG_SZ)
            if path is not None
            else None
        )

        if valid_path is not None:
            name_buffer = ctypes.create_unicode_buffer(str(valid_path))

            # LR_SHARED를 사용하지 않아 프로그램이 정리할 핸들을 받습니다.
            handle = self.user32.LoadImageW(
                None,
                ctypes.cast(name_buffer, ctypes.c_void_p),
                IMAGE_CURSOR,
                size,
                size,
                LR_LOADFROMFILE,
            )

            if not handle:
                logger.warning(
                    "커서 파일 로드 실패, 기본 리소스 사용: %s",
                    cursor_name,
                )

        if not handle:
            resource_id = ctypes.c_void_p(SYSTEM_CURSOR_IDS[cursor_name])

            # 기본 커서는 Windows가 관리하는 공유 원본으로 읽습니다.
            shared_handle = self.user32.LoadCursorW(None, resource_id)

            if not shared_handle:
                raise ctypes.WinError(ctypes.get_last_error())

            # 공유 원본은 변경·해제하지 않습니다.
            # flags=0으로 지정 크기의 별도 소유 복사본을 만듭니다.
            handle = self.user32.CopyImage(
                shared_handle,
                IMAGE_CURSOR,
                size,
                size,
                0,
            )

        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        owned_handle = int(handle)
        self.owned_handles.add(owned_handle)
        return owned_handle

    def set_system_cursor(self, cursor_name: str, handle: int) -> None:
        """프로그램 소유 커서를 시스템 커서로 적용합니다.

        복구 표식을 먼저 생성한 컨트롤러에서만 호출하도록 연결합니다.
        """
        self._require_lock()

        if cursor_name not in SYSTEM_CURSOR_IDS:
            raise ValueError("지원하지 않는 시스템 커서 이름입니다.")

        if handle not in self.owned_handles:
            raise ValueError("프로그램이 소유하지 않은 커서 핸들입니다.")

        success = self.user32.SetSystemCursor(
            handle,
            SYSTEM_CURSOR_IDS[cursor_name],
        )

        if not success:
            # 실패 시에는 후속 정리 대상에 남깁니다.
            raise ctypes.WinError(ctypes.get_last_error())

        # 성공한 SetSystemCursor는 Windows가 전달한 핸들을 파괴합니다.
        # 이후 DestroyCursor를 다시 호출하지 않도록 소유 목록에서 뺍니다.
        self.owned_handles.remove(handle)

    def destroy_cursor(self, handle: int) -> None:
        """사용하지 않은 프로그램 소유 커서 핸들을 해제합니다."""
        if handle not in self.owned_handles:
            raise ValueError("이미 해제됐거나 소유하지 않은 커서 핸들입니다.")

        if not self.user32.DestroyCursor(handle):
            raise ctypes.WinError(ctypes.get_last_error())

        self.owned_handles.remove(handle)

    def restore_system_cursors(self) -> bool:
        """현재 Windows 설정의 커서를 다시 로드합니다."""
        self._require_lock()

        # 레지스트리를 이전 값으로 되돌리지 않습니다.
        # Windows에서 사용자가 새로 선택한 현재 설정을 기준으로 복원합니다.
        success = self.user32.SystemParametersInfoW(
            SPI_SETCURSORS,
            0,
            None,
            0,
        )

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        return True


class CursorController:
    """커서 사전 로드·복구 표식·시스템 변경·정리를 연결합니다."""

    def __init__(
        self,
        instance_lock: SingleInstanceLock,
        marker_path: Path | None = None,
        api: WindowsCursorApi | None = None,
    ) -> None:
        # API 객체는 이 컨트롤러 전용으로 사용하여 소유 핸들을 함께 관리합니다.
        # 모의 검증에는 대체 객체를, EXE 스모크에는 실제 API 호출을 계측하는 객체를 사용합니다.
        self.api = api if api is not None else WindowsCursorApi(instance_lock)
        self.changed = False
        self.applied_level: int | None = None

        path = (
            marker_path
            if marker_path is not None
            else get_recovery_marker_path()
        )
        self.recovery = CursorRecovery(
            marker_path=path,
            instance_lock=instance_lock,
            restore_callback=self._reload_windows,
        )

    def _reload_windows(self) -> bool:
        """현재 Windows 설정을 복원한 후 메모리 상태를 해제합니다."""
        if self.api.restore_system_cursors() is not True:
            raise RuntimeError("Windows 커서 복원에 실패했습니다.")

        self.changed = False
        self.applied_level = None
        return True

    def _release_unused_handles(self) -> None:
        """남은 모든 소유 핸들의 정리를 시도합니다."""
        first_error = None

        # 정리 과정에서 소유 목록이 바뀌므로 복사해 순회합니다.
        for handle in list(self.api.owned_handles):
            try:
                self.api.destroy_cursor(handle)
            except Exception as error:
                logger.exception("커서 핸들 정리 실패: %s", handle)
                if first_error is None:
                    first_error = error

        if first_error is not None:
            raise RuntimeError(
                "일부 커서 핸들을 정리하지 못했습니다."
            ) from first_error

    def restore(self) -> bool:
        """이전 표식 또는 현재 변경 상태에 따라 커서를 복원합니다."""
        self.recovery._require_lock()

        try:
            restored = self.recovery.restore_pending()
        except Exception:
            # 표식 오류가 있어도 우리가 변경한 상태가 남아 있다면
            # 커서 복원은 시도합니다. 잘못된 표식은 삭제하지 않습니다.
            if self.changed:
                self._reload_windows()
            raise

        if not restored and self.changed:
            # 현재 프로세스의 변경 사실은 알고 있지만 표식이 사라진 경우,
            # 메모리 상태를 근거로 복원하고 다른 파일은 건드리지 않습니다.
            return self._reload_windows()

        return restored

    def apply(self, level: int) -> None:
        """14종을 준비하고 표식 생성 후 시스템 커서를 변경합니다."""
        self.recovery._require_lock()

        # 잘못된 단계로 기존 커서를 먼저 복원하지 않도록 선행 검증합니다.
        cursor_size_from_level(level)

        # 이전 변경을 복원하지 못하면 새 변경을 시작하지 않습니다.
        self.restore()
        self._release_unused_handles()

        prepared: list[tuple[str, int]] = []

        try:
            paths = read_cursor_paths()

            # 하나라도 로드하지 못하면 시스템 변경 전에 중단합니다.
            for name in SYSTEM_CURSOR_IDS:
                handle = self.api.load_scaled_cursor(
                    name,
                    level,
                    paths[name],
                )
                prepared.append((name, handle))

            # 표식 저장에 실패하면 아래 시스템 변경을 실행하지 않습니다.
            self.recovery.prepare()

            # 첫 API 호출이 부분적으로 실패할 가능성까지 복원 대상으로 둡니다.
            self.changed = True

            try:
                for name, handle in prepared:
                    self.api.set_system_cursor(name, handle)

            except Exception:
                try:
                    self.restore()
                except Exception as restore_error:
                    raise RuntimeError(
                        "커서 변경 중 오류가 발생했고 복구도 완료하지 못했습니다. "
                        "남아 있는 복구 표식을 보존합니다."
                    ) from restore_error

                # 복원에 성공해도 적용 실패를 성공으로 처리하지 않습니다.
                raise

            self.applied_level = level

        finally:
            # 성공적으로 전달한 핸들은 API 소유 목록에서 빠져 있습니다.
            # 미사용·실패한 핸들만 정리합니다.
            self._release_unused_handles()

    def stop(self) -> None:
        """복원을 시도하고, 복원 오류와 별개로 핸들도 정리합니다."""
        try:
            self.restore()
        finally:
            self._release_unused_handles()