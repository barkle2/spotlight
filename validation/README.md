# Spotlight 검증 도구

이 폴더에는 제품 코드와 분리된 기술 검증용 스크립트만 둔다.

## 실행 환경

- 가상환경: `.venv`
- 결과 산출물: `artifacts/`
- 종합 실행: `run_validation.py`
- 포인터 크기 레지스트리 검증: `cursor_size_probe.py`
- 단일 시스템 커서 확대 검증: `system_cursor_probe.py`
- 전체 시스템 커서 확대 검증: `all_system_cursors_probe.py`

## 안전 원칙

- 포인터 크기 검증은 변경 전 레지스트리 상태를 복구 파일에 저장한다.
- 검증 중에는 크기 2만 잠시 적용하고 `finally` 블록에서 원래 상태로 복원한다.
- 원래 `CursorBaseSize` 값이 없었다면 복원 시 해당 값을 삭제한다.
- 종합 검증은 원래 마우스 위치를 저장하고 합성 입력 후 되돌린다.
