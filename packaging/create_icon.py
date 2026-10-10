"""현재 트레이 디자인으로 Windows EXE용 ICO 파일을 생성합니다."""

import os
from pathlib import Path
import struct
import sys
import tempfile

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = PROJECT_ROOT / "assets" / "spotlight.ico"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def create_ico_data() -> bytes:
    """트레이 아이콘의 여러 크기를 하나의 ICO 파일로 구성합니다."""
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from spotlight.tray import create_spotlight_icon

    icon = create_spotlight_icon()
    images = []

    for size in ICON_SIZES:
        pixmap = icon.pixmap(size, size)

        if pixmap.isNull() or (
            pixmap.width() != size or pixmap.height() != size
        ):
            raise RuntimeError(f"{size}px 아이콘 생성에 실패했습니다.")

        # PNG 인코딩은 PySide6를 사용하며 추가 이미지 라이브러리는 없습니다.
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError("이미지 버퍼를 열지 못했습니다.")

        try:
            if not pixmap.save(buffer, "PNG"):
                raise RuntimeError(f"{size}px 이미지 저장에 실패했습니다.")
            images.append(bytes(buffer.data()))
        finally:
            buffer.close()

    # ICO 헤더: 예약값, 아이콘 종류, 이미지 개수.
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = []
    offset = len(header) + 16 * len(images)

    for size, image in zip(ICON_SIZES, images):
        # ICO의 너비·높이 필드에서 0은 256픽셀을 의미합니다.
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(image),
                offset,
            )
        )
        offset += len(image)

    return header + b"".join(entries) + b"".join(images)


def save_icon(data: bytes) -> None:
    """완성된 임시 파일로 교체하여 불완전한 아이콘 저장을 방지합니다."""
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=ICON_PATH.parent,
            prefix="spotlight-icon-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, ICON_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    """화면에 창을 띄우지 않고 아이콘 파일만 생성합니다."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application = QApplication([])

    data = create_ico_data()
    save_icon(data)

    print(f"ICON_CREATED: {ICON_PATH}")
    print("ICON_SIZES: " + ", ".join(map(str, ICON_SIZES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())