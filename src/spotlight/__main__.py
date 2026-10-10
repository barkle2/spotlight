"""python -m spotlight 방식으로 실행할 때 사용하는 진입점입니다."""

from .app import run


if __name__ == "__main__":
    raise SystemExit(run())