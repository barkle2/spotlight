"""시험 전용 설정과 커서 적용·복원 결과를 관리합니다."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

from .config import HighlightSettings, save_settings
from .cursor import (
    SYSTEM_CURSOR_IDS,
    WindowsCursorApi,
    get_recovery_marker_path,
)
from .instance import SingleInstanceLock


class SmokeCursorApi(WindowsCursorApi):
    """기존 Windows API를 사용하면서 성공한 호출만 기록합니다."""

    def __init__(self, instance_lock: SingleInstanceLock) -> None:
        super().__init__(instance_lock)
        self.applied_names: list[str] = []
        self.restore_succeeded = False

    def set_system_cursor(self, cursor_name: str, handle: int) -> None:
        """실제 적용이 성공한 뒤에만 해당 커서 이름을 기록합니다."""
        super().set_system_cursor(cursor_name, handle)
        self.applied_names.append(cursor_name)

    def restore_system_cursors(self) -> bool:
        """실제 Windows 복원이 성공한 뒤에만 성공 상태를 기록합니다."""
        result = super().restore_system_cursors()
        self.restore_succeeded = result is True
        return result


class SmokeSession:
    """잠금 획득 후 시험용 파일을 준비하고 종료 결과를 판정합니다."""

    def __init__(
        self,
        instance_lock: SingleInstanceLock,
        report_path: Path,
    ) -> None:
        if (
            not isinstance(instance_lock, SingleInstanceLock)
            or instance_lock.handle is None
        ):
            raise RuntimeError("스모크 시험 전에 단일 실행 잠금이 필요합니다.")

        self.instance_lock = instance_lock
        self.report_path = report_path.resolve()

        if self.report_path.exists():
            raise FileExistsError(
                "기존 시험 보고서를 덮어쓰지 않습니다. 새 경로를 사용해 주세요."
            )

        # 정상 사용 중 남은 표식을 시험용 표식과 혼동하지 않습니다.
        # 기존 표식은 일반 실행으로 먼저 복구해야 합니다.
        if os.path.lexists(get_recovery_marker_path()):
            raise RuntimeError(
                "기존 커서 복구 표식이 있습니다. "
                "일반 실행 후 정상 종료하여 먼저 복구해 주세요."
            )

        self.api = SmokeCursorApi(instance_lock)
        self.input_registered = False
        self.input_error_count = 0
        self.errors: list[str] = []

        # 사용자 settings.ini와 분리된 시험 경로를 사용합니다.
        # 복원 실패 시 표식을 보존해야 하므로 자동 삭제 객체는 쓰지 않습니다.
        self.directory = Path(
            tempfile.mkdtemp(prefix="Spotlight-smoke-")
        )
        self.settings_path = self.directory / "settings.ini"
        self.marker_path = self.directory / "cursor-recovery.json"

        # 실제 14종 적용을 시험하도록 확대를 켠 시험 설정을 저장합니다.
        save_settings(
            self.settings_path,
            HighlightSettings(cursor_enabled=True, cursor_level=3),
        )

    def record_error(self, message: str) -> None:
        """시작 또는 종료 과정의 오류를 최종 보고서에 포함합니다."""
        self.errors.append(message)

    def finish(self, exit_code: int) -> bool:
        """정리 완료 상태를 검사하고 JSON 보고서를 저장합니다.

        앱이 자원 정리와 잠금 해제를 시도한 뒤 호출해야 합니다.
        실제 커서 적용·복원, 입력 등록·오류, 표식·핸들·잠금 상태와
        종료 코드를 판정하며, 모든 항목이 통과하면 True를 반환합니다.
        보고서 저장 실패는 예외로 전달합니다.
        이 메서드 자체는 커서를 복원하거나 자원을 정리하지 않습니다.
        """
        applied_names = sorted(set(self.api.applied_names))

        checks = {
            "frozen_executable": bool(getattr(sys, "frozen", False)),
            "cursor_14_applied": applied_names == sorted(SYSTEM_CURSOR_IDS),
            "input_registered": self.input_registered,
            "input_errors_zero": self.input_error_count == 0,
            "cursor_restored": self.api.restore_succeeded,
            "recovery_marker_removed": not os.path.lexists(self.marker_path),
            "unused_cursor_handles_empty": not self.api.owned_handles,
            "instance_lock_released": self.instance_lock.handle is None,
            "normal_exit": exit_code == 0,
            "no_errors": not self.errors,
        }
        passed = all(checks.values())

        report = {
            "kind": "exe_smoke",
            "status": "passed" if passed else "failed",
            "checked_utc": datetime.now(timezone.utc).isoformat(),
            "executable": sys.executable,
            "test_directory": str(self.directory),
            "settings_path": str(self.settings_path),
            "recovery_marker": str(self.marker_path),
            "cursor_names": applied_names,
            "cursor_apply_calls": len(self.api.applied_names),
            "input_error_count": self.input_error_count,
            "exit_code": exit_code,
            "checks": checks,
            "errors": self.errors,
        }

        # 실패한 시험의 복구 표식과 경로를 그대로 남깁니다.
        # 성공한 경우에도 결과 확인 전 시험 폴더를 임의로 삭제하지 않습니다.
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return passed