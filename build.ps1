$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

python packaging/create_icon.py
python -m PyInstaller --noconfirm --clean spotlight.spec

Write-Host "Build complete: $ProjectRoot\dist\spotlight.exe"
