"""소스 및 패키징된 Spotlight의 실행 진입점입니다."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import traceback


def main() -> int:
    """프로그램을 실행하고 콘솔이 없으면 출력·오류를 파일에 남깁니다."""
    project_directory = Path(__file__).resolve().parent
    source_directory = project_directory / "src"
    sys.path.insert(0, str(source_directory))

    previous_stdout = sys.stdout
    previous_stderr = sys.stderr
    log_stream = None

    try:
        # 콘솔 실행은 기존 출력을 유지합니다.
        # 콘솔 없는 EXE에서만 실행별 로그 파일을 준비합니다.
        if previous_stdout is None or previous_stderr is None:
            from spotlight.config import get_config_path

            log_directory = get_config_path().parent / "logs"
            log_directory.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).strftime(
                "%Y%m%d-%H%M%S-%f"
            )
            log_path = log_directory / (
                f"spotlight-{timestamp}-{os.getpid()}.log"
            )
            log_stream = log_path.open(
                "x",
                encoding="utf-8",
                buffering=1,
            )
            log_stream.write("Spotlight windowed execution log.\n")

            # 존재하는 출력 스트림은 바꾸지 않습니다.
            if previous_stdout is None:
                sys.stdout = log_stream
            if previous_stderr is None:
                sys.stderr = log_stream

        from spotlight.app import run
        return run()

    except Exception:
        # 앱 import 단계의 오류도 파일이 준비됐다면 기록합니다.
        if log_stream is not None:
            traceback.print_exc(file=log_stream)
        raise

    finally:
        # 닫힌 파일이 전역 표준 스트림으로 남지 않게 원래 값을 복원합니다.
        sys.stdout = previous_stdout
        sys.stderr = previous_stderr

        if log_stream is not None:
            log_stream.close()


if __name__ == "__main__":
    raise SystemExit(main())