"""공통 식별 정보로 PyInstaller용 Windows 버전 리소스를 생성합니다."""

import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "packaging" / "version_info.txt"

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spotlight.app_info import (
    PRODUCT_NAME,
    PRODUCT_DESCRIPTION,
    PRODUCT_VERSION,
    PUBLISHER,
    COPYRIGHT,
    EXECUTABLE_NAME,
)


def create_version_info_text() -> str:
    """공통 식별 정보로 EXE 속성의 버전 리소스 표현을 반환합니다.

    정보 창과 같은 제품명·버전·배포 주체·저작권을 사용합니다.
    반환 문자열은 빌드 도구가 해석하는 데이터이며,
    이 함수에서는 파일을 저장하거나 EXE를 생성하지 않습니다.
    """
    parts = PRODUCT_VERSION.split(".")

    if len(parts) != 3 or not all(part.isdecimal() for part in parts):
        raise ValueError("버전은 1.0.0처럼 세 숫자로 구성해야 합니다.")

    numbers = tuple(int(part) for part in parts)
    if any(number > 65535 for number in numbers):
        raise ValueError("버전의 각 숫자는 0~65535 범위여야 합니다.")

    # Windows 숫자 버전은 네 항목이므로 마지막 값을 0으로 지정합니다.
    version_tuple = numbers + (0,)

    values = {
        "CompanyName": PUBLISHER,
        "FileDescription": PRODUCT_DESCRIPTION,
        "FileVersion": PRODUCT_VERSION,
        "InternalName": PRODUCT_NAME,
        "LegalCopyright": COPYRIGHT,
        "OriginalFilename": EXECUTABLE_NAME,
        "ProductName": PRODUCT_NAME,
        "ProductVersion": PRODUCT_VERSION,
    }

    # repr로 따옴표와 특수문자를 처리하여 유효한 리소스 표현을 만듭니다.
    strings = ",\n".join(
        f"          StringStruct({key!r}, {value!r})"
        for key, value in values.items()
    )

    # 0412는 한국어, 04B0은 Unicode 코드페이지 1200입니다.
    # 이 텍스트는 PyInstaller가 제공하는 리소스 클래스로 해석합니다.
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple!r},
    prodvers={version_tuple!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('041204B0', [
{strings}
      ])
    ]),
    VarFileInfo([
      VarStruct('Translation', [1042, 1200])
    ])
  ]
)
"""


def save_version_info(text: str) -> None:
    """완성한 임시 파일로 교체하여 리소스 파일을 저장합니다."""
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=OUTPUT_PATH.parent,
            prefix="version-info-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, OUTPUT_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    """현재 식별 정보를 읽어 빌드용 리소스 파일을 생성합니다."""
    save_version_info(create_version_info_text())
    print(f"VERSION_INFO_CREATED: {OUTPUT_PATH}")
    print(f"VERSION: {PRODUCT_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())