# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(SPECPATH).parent


def normalized(name):
    return str(PurePosixPath(name.replace("\\", "/"))).lower()


def filtered(entries, variant):
    if variant == "baseline":
        return list(entries)

    safe_parts = (
        "pyside6/translations/",
        "pyside6/plugins/imageformats/qicns.dll",
        "pyside6/plugins/imageformats/qpdf.dll",
        "pyside6/plugins/imageformats/qtiff.dll",
        "pyside6/plugins/imageformats/qwebp.dll",
        "pyside6/plugins/imageformats/qwbmp.dll",
        "pyside6/plugins/imageformats/qtga.dll",
        "pyside6/plugins/platforms/qoffscreen.dll",
        "pyside6/plugins/platforms/qminimal.dll",
        "pyside6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
        "pyside6/plugins/generic/qtuiotouchplugin.dll",
        "pyside6/plugins/tls/",
        "pyside6/plugins/networkinformation/",
        "pyside6/qt6pdf.dll",
        "pyside6/qt6virtualkeyboard.dll",
        "pyside6/qt6qml.dll",
        "pyside6/qt6qmlmeta.dll",
        "pyside6/qt6qmlmodels.dll",
        "pyside6/qt6qmlworkerscript.dll",
        "pyside6/qt6quick.dll",
    )
    minimal_parts = safe_parts + (
        "pyside6/plugins/imageformats/qgif.dll",
        "pyside6/plugins/imageformats/qjpeg.dll",
        "pyside6/plugins/imageformats/qsvg.dll",
        "pyside6/plugins/iconengines/qsvgicon.dll",
        "pyside6/plugins/platforms/qdirect2d.dll",
        "pyside6/plugins/styles/qmodernwindowsstyle.dll",
        "pyside6/opengl32sw.dll",
        "pyside6/qt6network.dll",
        "pyside6/qt6svg.dll",
        "pyside6/qt6opengl.dll",
        "pyside6/qtnetwork.pyd",
    )
    blocked = safe_parts if variant == "safe" else minimal_parts
    return [entry for entry in entries if not any(part in normalized(entry[0]) for part in blocked)]


a = Analysis(
    [str(PROJECT_ROOT / "run_spotlight.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)


def make_exe(variant):
    return EXE(
        pyz,
        a.scripts,
        filtered(a.binaries, variant),
        filtered(a.datas, variant),
        [],
        name=f"spotlight-{variant}",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=[str(PROJECT_ROOT / "assets" / "spotlight.ico")],
    )


baseline = make_exe("baseline")
safe = make_exe("safe")
minimal = make_exe("minimal")
