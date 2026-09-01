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

보고서에서 다음을 확인합니다.

| 키 | 기대값 | 의미 |
|---|---|---|
| `cursor_restored` | `true` | 종료 시 시스템 커서 복원 완료 |
| `recovery_file_exists` | `false` | 복구 표식 정리 완료 |
| `cursor_count_applied` | `14` | 시스템 커서 14종 적용 (`No` 포함) |
| `input_error_count` | `0` | Raw Input 처리 중 예외 미발생 |

## 보안 관련 빌드 설정

`spotlight.spec`과 `packaging/spotlight_variants.spec`은 아래 정책을 따릅니다.
빌드 스크립트가 시작 시 이를 점검하며, 위반 시 빌드를 중단합니다.

| 설정 | 값 | 이유 |
|---|---|---|
| `upx` | `False` | UPX 압축은 백신 휴리스틱의 최대 트리거이며, 번들 DLL(Qt·Microsoft·PSF·OpenSSL)의 정식 디지털 서명을 파괴합니다. |
| `version` | `packaging/version_info.py` | VERSIONINFO 리소스를 포함해 파일 속성에서 제품·회사·버전을 식별할 수 있게 합니다. |
| `excludes` | `pynput` 전 계열 | Raw Input 전환으로 불필요해진 입력 후킹 라이브러리의 재유입을 차단합니다. |

배포 전 `packaging/version_info.py`의 `CompanyName`을 실제 배포 주체로 확인·수정하십시오.

## 코드서명

미서명 실행파일은 변조 여부를 검증할 수단이 없으므로 배포 요건을 충족하지 않습니다.
인증서를 확보한 뒤 다음과 같이 서명까지 함께 수행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1 `
    -SignThumbprint "<인증서 지문>" `
    -TimestampUrl "<RFC 3161 타임스탬프 서버 URL>"
```

빌드 스크립트가 `signtool.exe`를 Windows SDK 경로에서 자동으로 찾고,
서명 후 실행 가능 여부까지 재확인합니다. 서명하면 SHA-256이 변경되므로
자산 대장과 EDR 허용 목록의 해시를 함께 갱신해야 합니다.

## 빌드 산출물 검증

```powershell
python validation\scan_pyz_strings.py dist\spotlight.exe
```

`pynput`, `SetWindowsHookEx`, `GetAsyncKeyState`, `ToUnicodeEx`,
`KeyTranslator`, `WH_KEYBOARD_LL` 등이 검출되지 않아야 합니다.
