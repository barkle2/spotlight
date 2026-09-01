# Spotlight 검증 도구

이 폴더에는 제품 코드와 분리된 기술 검증용 스크립트만 둔다.

## 실행 환경

- 가상환경: `.venv`
- 결과 산출물: `artifacts/`
- 환경 수집: `environment_probe.py`
- 포인터 크기 레지스트리 검증: `cursor_size_probe.py`
- 단일 시스템 커서 확대 검증: `system_cursor_probe.py`
- 전체 시스템 커서 확대 검증: `all_system_cursors_probe.py`
- 빌드 산출물 문자열 검사: `scan_pyz_strings.py`

## Raw Input 전환 이후 검증

제품이 pynput을 제거하고 Windows Raw Input API로 전환(v0.2.0)했으므로
입력 감지 검증은 수동 체크리스트를 사용한다.

- `RAW_INPUT_MANUAL_CHECKLIST.md` — F-1~F-7, E-1~E-4, S-1~S-13

## 폐기된 스크립트

아래는 pynput 프로토타입 시절 스크립트로, 현재 제품 구조와 맞지 않는다.
이력 보존 목적으로만 남겨 두며 실행에는 pynput 별도 설치가 필요하다.

- `run_validation.py`
- `stage3_probe.py`

## 안전 원칙

- 포인터 크기 검증은 변경 전 레지스트리 상태를 복구 파일에 저장한다.
- 검증 중에는 크기 2만 잠시 적용하고 `finally` 블록에서 원래 상태로 복원한다.
- 원래 `CursorBaseSize` 값이 없었다면 복원 시 해당 값을 삭제한다.
- 종합 검증은 원래 마우스 위치를 저장하고 합성 입력 후 되돌린다.
