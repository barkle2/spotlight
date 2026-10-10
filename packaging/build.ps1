<#
Spotlight의 폴더형 EXE와 빌드 보고서를 생성합니다.

-Python에는 사용할 Python 명령 또는 실행 파일의 전체 경로를 지정합니다.
설치 버전과 UPX 설정을 검사한 뒤 아이콘·버전 리소스를 생성하고 빌드합니다.
매번 고유한 출력 폴더를 사용하며, 외부 명령 실패 시 빌드를 중단합니다.
빌드 성공은 실행 검증 완료를 의미하지 않으며, 코드서명은 수행하지 않습니다.
#>
param(
    [string]$Python = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)
$pythonCommand = Get-Command $Python -CommandType Application -ErrorAction Stop |
    Select-Object -First 1
$pythonPath = $pythonCommand.Source
$specPath = Join-Path $PSScriptRoot "Spotlight.spec"

function Invoke-CheckedPython {
    param([string[]]$Arguments)

    # PyInstaller의 정상 진행 로그도 stderr로 출력됩니다.
    # stderr 출력 자체 대신 실제 종료코드로 실패를 판정합니다.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        & $pythonPath @Arguments

        if ($LASTEXITCODE -ne 0) {
            throw "Python command failed. Exit code: $LASTEXITCODE"
        }
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

# 설치 버전과 모든 spec의 UPX 설정을 실제 빌드 전에 검사합니다.
$preflightCode = @'
import ast
import importlib.metadata
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
expected = {
    "PySide6": "6.11.2",
    "pyinstaller": "6.22.3",
    "pyinstaller-hooks-contrib": "2026.8",
}
versions = {
    name: importlib.metadata.version(name)
    for name in expected
}
if versions != expected:
    raise RuntimeError(f"Build package versions differ: {versions}")

specs = sorted((root / "packaging").glob("*.spec"))
if not specs:
    raise RuntimeError("No spec files found.")

for path in specs:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    build_calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        for keyword in node.keywords:
            if keyword.arg == "upx":
                value = keyword.value
                if not (
                    isinstance(value, ast.Constant)
                    and value.value is False
                ):
                    raise RuntimeError(f"UPX must be False: {path.name}")

        if (
            isinstance(node.func, ast.Name)
            and node.func.id in ("EXE", "COLLECT")
        ):
            build_calls.append(node)
            value = next(
                (k.value for k in node.keywords if k.arg == "upx"),
                None,
            )
            if not (
                isinstance(value, ast.Constant)
                and value.value is False
            ):
                raise RuntimeError(
                    f"Explicit upx=False is required: {path.name}"
                )

    if not build_calls:
        raise RuntimeError(f"No EXE/COLLECT calls: {path.name}")

print(json.dumps({
    "python": sys.version.split()[0],
    "python_executable": sys.executable,
    "packages": versions,
    "checked_specs": [p.name for p in specs],
}, ensure_ascii=True))
'@

Push-Location -LiteralPath $projectRoot

try {
    if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
        throw "Spotlight.spec is missing."
    }

    # 코드의 따옴표가 변형되지 않도록 표준 입력으로 전달합니다.
    $environmentJson = $preflightCode | & $pythonPath -B - $projectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Build preflight failed."
    }
    $environmentInfo = $environmentJson | ConvertFrom-Json

    $upxCommand = Get-Command "upx" -ErrorAction SilentlyContinue
    if ($null -ne $upxCommand) {
        Write-Warning "UPX exists in PATH; this build keeps UPX disabled."
    }

    # 고유 출력 폴더를 사용해 이전 EXE를 새 빌드 결과로 오인하지 않습니다.
    $buildId = (
        (Get-Date -Format "yyyyMMdd-HHmmss") + "-" +
        [guid]::NewGuid().ToString("N").Substring(0, 8)
    )
    $buildDirectory = Join-Path $projectRoot "build\$buildId"
    $distDirectory = Join-Path $projectRoot "dist\$buildId"

    if (
        (Test-Path -LiteralPath $buildDirectory) -or
        (Test-Path -LiteralPath $distDirectory)
    ) {
        throw "Build output directory already exists."
    }

    [System.IO.Directory]::CreateDirectory($buildDirectory) | Out-Null
    $startedUtc = [DateTime]::UtcNow.ToString("o")

    # 현재 디자인과 식별 정보로 빌드 리소스를 다시 생성합니다.
    Invoke-CheckedPython -Arguments @(
        "-B", "packaging/create_icon.py"
    )
    Invoke-CheckedPython -Arguments @(
        "-B", "packaging/version_info.py"
    )

    Invoke-CheckedPython -Arguments @(
        "-B", "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath", (Join-Path $buildDirectory "work"),
        "--distpath", $distDirectory,
        $specPath
    )

    $executablePath = Join-Path $distDirectory "Spotlight\Spotlight.exe"
    $internalPath = Join-Path $distDirectory "Spotlight\_internal"

    if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
        throw "The new Spotlight.exe was not created."
    }
    if (-not (Test-Path -LiteralPath $internalPath -PathType Container)) {
        throw "The runtime dependency directory was not created."
    }

    $executableFile = Get-Item -LiteralPath $executablePath
    if ($executableFile.Length -le 0) {
        throw "The executable is empty."
    }

    # 빌드 성공과 실행 검증 완료를 구분하여 보고서에 기록합니다.
    $report = [ordered]@{
        status = "built_pending_validation"
        build_id = $buildId
        started_utc = $startedUtc
        finished_utc = [DateTime]::UtcNow.ToString("o")
        environment = $environmentInfo
        spec_sha256 = (
            Get-FileHash -LiteralPath $specPath -Algorithm SHA256
        ).Hash
        executable = $executablePath
        executable_bytes = $executableFile.Length
        executable_sha256 = (
            Get-FileHash -LiteralPath $executablePath -Algorithm SHA256
        ).Hash
        upx_enabled = $false
        signing_requested = $false
    }

    $reportPath = Join-Path $buildDirectory "build-report.json"
    $report | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath $reportPath -Encoding UTF8

    Write-Host "BUILD_CREATED: $executablePath"
    Write-Host "BUILD_REPORT: $reportPath"
    Write-Host "STATUS: built_pending_validation"
}
catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
finally {
    Pop-Location
}