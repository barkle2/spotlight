"""프로그램 식별 정보와 실행 파일 해시 계산을 제공합니다."""

import hashlib
from pathlib import Path
import sys

from . import __version__


# 정보 창과 EXE 속성에서 사용하는 공통 식별 정보입니다.
PRODUCT_NAME = "Spotlight"
PRODUCT_DESCRIPTION = "마우스 강조 및 포인터 확대 프로그램"
PRODUCT_VERSION = __version__
PUBLISHER = "고용노동부 김동현"
COPYRIGHT = "Copyright © 2026 고용노동부 김동현"
EXECUTABLE_NAME = "Spotlight.exe"


def get_runtime_file_path() -> Path:
    """현재 실행 방식에 맞는 해시 계산 대상 파일을 반환합니다.

    패키징한 프로그램에서는 실제 실행 중인 EXE를 선택합니다.
    소스 실행에서는 Python 인터프리터 대신 프로젝트 실행 파일을
    선택합니다. 두 해시는 정보 화면에서 구분하여 표시해야 합니다.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "run_spotlight.py"


def calculate_file_sha256(path: Path) -> str:
    """파일을 작은 블록으로 읽어 SHA-256을 계산합니다.

    큰 EXE 전체를 메모리에 올리지 않습니다.
    파일을 읽지 못하면 예외를 전달하여 정보 화면에서
    계산 실패를 표시하도록 합니다.
    """
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest().upper()