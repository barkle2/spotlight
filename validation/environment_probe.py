from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


def collect_environment() -> dict[str, object]:
    try:
        from PySide6 import QtCore

        pyside_version = QtCore.__version__
    except Exception:
        pyside_version = None

    try:
        import pynput

        pynput_version = getattr(pynput, "__version__", "installed")
    except Exception:
        pynput_version = None

    return {
        "platform": platform.platform(),
        "windows_version": platform.version(),
        "python": sys.version.split()[0],
        "architecture": platform.machine(),
        "pyside6": pyside_version,
        "pynput": pynput_version,
        "local_app_data_available": bool(os.environ.get("LOCALAPPDATA")),
    }


def main() -> int:
    result = collect_environment()
    output = Path(__file__).parent / "artifacts" / "environment.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

