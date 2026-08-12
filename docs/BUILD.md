# Spotlight 빌드

## 준비

Python 3.14 이상 환경에서 런타임 및 빌드 의존성을 설치합니다.

```powershell
python -m pip install -r requirements-build.txt
```

## 빌드

프로젝트 루트에서 다음 명령을 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

빌드 스크립트는 트레이 아이콘과 동일한 `assets/spotlight.ico`를 생성하고 PyInstaller로 콘솔 창 없는 단일 실행 파일을 만듭니다.

결과 파일:

```text
dist\spotlight.exe
```

`build` 폴더는 PyInstaller 중간 산출물이며 배포할 필요가 없습니다.

## 검증

빌드된 EXE의 자동 종료 스모크 테스트 예시입니다.

```powershell
.\dist\spotlight.exe --smoke-test `
  --report validation\artifacts\exe_smoke.json `
  --settings-path validation\artifacts\exe_smoke.ini `
  --recovery-path validation\artifacts\exe_smoke_recovery.json
```

보고서에서 `cursor_restored`가 `true`이고 `recovery_file_exists`가 `false`인지 확인합니다.
