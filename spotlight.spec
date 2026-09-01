# -*- mode: python ; coding: utf-8 -*-
#
# 보안 검토 반영본
#   upx=False : UPX 압축은 백신 휴리스틱 최대 트리거이며, 번들 DLL
#               (Qt/Microsoft/PSF/OpenSSL)의 정식 서명을 파괴한다.
#   version=  : VERSIONINFO 리소스 포함 (제품·회사·버전 식별)
#   excludes  : pynput 전 계열 제외 (Raw Input 전환 완료로 안전)


a = Analysis(
    ["run_spotlight.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pynput", "pynput.keyboard", "pynput.mouse"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="spotlight",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/spotlight.ico"],
    version="packaging/version_info.py",
)
