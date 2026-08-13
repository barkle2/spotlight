$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

py -3 packaging/create_icon.py
py -3 -m PyInstaller --noconfirm --clean `
    --distpath dist/variants `
    --workpath build/variants `
    packaging/spotlight_variants.spec

Get-ChildItem dist/variants/spotlight-*.exe |
    Sort-Object Length -Descending |
    Select-Object Name, Length, @{Name="SizeMB"; Expression={[math]::Round($_.Length / 1MB, 2)}}
