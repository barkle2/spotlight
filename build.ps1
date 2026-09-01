<#
.SYNOPSIS
    Spotlight build script (security-reviewed, v0.2.0)

.DESCRIPTION
    Preflight -> icon -> PyInstaller build -> pynput residue check
    -> smoke test -> optional code signing -> SHA-256 output.

    NOTE: All messages are ASCII-only on purpose.
    Windows PowerShell 5.1 reads .ps1 files as ANSI unless the file has a
    UTF-8 BOM, which garbles non-ASCII text and breaks string parsing.

.PARAMETER SignThumbprint
    Certificate thumbprint used for code signing.
    If omitted, the signing step is skipped.

.PARAMETER TimestampUrl
    RFC 3161 timestamp server. Required when signing.
    Without a timestamp the signature becomes invalid once the
    certificate expires.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1 `
        -SignThumbprint "A1B2C3D4E5F6..." `
        -TimestampUrl "http://timestamp.digicert.com"
#>

param(
    [string]$SignThumbprint = "",
    [string]$TimestampUrl = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Find-SignTool {
    # signtool.exe ships with the Windows SDK and is NOT on PATH by default.
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $roots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "${env:ProgramFiles}\Windows Kits\10\bin"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $found = Get-ChildItem $root -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -like "*\x64\*" } |
                 Sort-Object FullName -Descending |
                 Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

Write-Host "=== 1. Preflight ===" -ForegroundColor Cyan

if ($env:OS -ne "Windows_NT") {
    throw "This script must run on Windows. PyInstaller does not cross-compile."
}

python --version
python -c "import PyInstaller; print('PyInstaller', PyInstaller.__version__)"
python -c "import PySide6; print('PySide6', PySide6.__version__)"

# UPX is the single strongest AV heuristic trigger and it also destroys the
# Authenticode signatures of the bundled Qt / Microsoft / PSF / OpenSSL DLLs.
# The spec sets upx=False; warn if UPX is present so it is not re-enabled.
$upx = Get-Command upx -ErrorAction SilentlyContinue
if ($upx) {
    Write-Host "  [WARN] UPX found on PATH: $($upx.Source)" -ForegroundColor Yellow
    Write-Host "         Do NOT set upx=True in spotlight.spec." -ForegroundColor Yellow
}

# Confirm the security-reviewed spec is in use.
$specText = Get-Content ".\spotlight.spec" -Raw
if ($specText -match "upx\s*=\s*True") {
    throw "spotlight.spec has upx=True. Set it to False before building."
}
if ($specText -notmatch "version\s*=") {
    Write-Host "  [WARN] spotlight.spec has no version= parameter." -ForegroundColor Yellow
    Write-Host "         VERSIONINFO will be missing from the executable." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 2. Icon ===" -ForegroundColor Cyan
if (Test-Path ".\packaging\create_icon.py") {
    python packaging/create_icon.py
} else {
    Write-Host "  [WARN] packaging\create_icon.py not found - skipped." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 3. PyInstaller build ===" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean spotlight.spec

$exePath = Join-Path $ProjectRoot "dist\spotlight.exe"
if (-not (Test-Path $exePath)) {
    throw "Build output not found: $exePath"
}

Write-Host ""
Write-Host "=== 4. pynput residue check ===" -ForegroundColor Cyan
$verifyScript = Join-Path $ProjectRoot "validation\scan_pyz_strings.py"
if (-not (Test-Path $verifyScript)) {
    throw "Verification script not found: $verifyScript"
}
python $verifyScript $exePath
if ($LASTEXITCODE -ne 0) {
    # Exit code 1 means either forbidden strings were found or the scan itself
    # raised. Read the output above to tell them apart - do not assume residue.
    throw "Verification step failed (exit $LASTEXITCODE). See output above."
}

Write-Host ""
Write-Host "=== 5. Smoke test ===" -ForegroundColor Cyan
$reportPath = Join-Path $ProjectRoot "dist\smoke-report.json"
Remove-Item $reportPath -ErrorAction SilentlyContinue
& $exePath --smoke-test --report $reportPath
if (Test-Path $reportPath) {
    $report = Get-Content $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "  cursor_count_applied  : $($report.cursor_count_applied)  (expected 14)"
    Write-Host "  input_listener_started: $($report.input_listener_started)"
    Write-Host "  input_error_count     : $($report.input_error_count)  (expected 0)"
    Write-Host "  cursor_restored       : $($report.cursor_restored)"
    if ($report.cursor_count_applied -ne 14) {
        Write-Host "  [WARN] cursor_count_applied is not 14." -ForegroundColor Yellow
    }
} else {
    Write-Host "  [WARN] Smoke report was not produced." -ForegroundColor Yellow
}

if ($SignThumbprint) {
    Write-Host ""
    Write-Host "=== 6. Code signing ===" -ForegroundColor Cyan

    if (-not $TimestampUrl) {
        throw "TimestampUrl is required. Without it the signature dies with the certificate."
    }

    $signTool = Find-SignTool
    if (-not $signTool) {
        throw "signtool.exe not found. Install 'Windows SDK Signing Tools for Desktop Apps'."
    }
    Write-Host "  signtool: $signTool"

    & $signTool sign /fd SHA256 /sha1 $SignThumbprint `
        /tr $TimestampUrl /td SHA256 $exePath
    if ($LASTEXITCODE -ne 0) { throw "Signing failed." }

    & $signTool verify /pa /v $exePath
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed." }

    Write-Host ""
    Write-Host "=== 7. Post-signing run check ===" -ForegroundColor Cyan
    # The signature is appended after the PyInstaller archive, so the
    # bootloader must be re-verified after signing.
    Remove-Item $reportPath -ErrorAction SilentlyContinue
    & $exePath --smoke-test --report $reportPath
    if ($LASTEXITCODE -ne 0) {
        throw "Executable failed to run after signing. Bootloader may not locate its archive."
    }
    Write-Host "  Post-signing run OK."
} else {
    Write-Host ""
    Write-Host "=== 6. Code signing SKIPPED ===" -ForegroundColor Yellow
    Write-Host "  An unsigned binary does not meet the deployment requirement (V-1)."
    Write-Host "  Re-run with -SignThumbprint and -TimestampUrl to sign."
}

Write-Host ""
Write-Host "=== Output ===" -ForegroundColor Cyan
$hash = (Get-FileHash $exePath -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $exePath).Length
Write-Host "  Path     : $exePath"
Write-Host "  Size     : $('{0:N0}' -f $size) bytes"
Write-Host "  SHA-256  : $hash"
Write-Host ""
Write-Host "  Record this hash in the asset register, EDR allowlist and report." -ForegroundColor Green
Write-Host "  Then run functional checks S-1 through S-12." -ForegroundColor Green
