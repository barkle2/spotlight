from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from spotlight.tray import create_tray_icon


def main() -> int:
    app = QApplication.instance() or QApplication([])
    destination = ROOT / "assets" / "spotlight.ico"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pixmap = create_tray_icon().pixmap(QSize(64, 64))
    if not pixmap.save(str(destination), "ICO"):
        raise RuntimeError(f"아이콘을 저장하지 못했습니다: {destination}")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
