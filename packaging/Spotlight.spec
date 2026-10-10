# Spotlight 폴더형 검증 EXE의 빌드 설정입니다.
# Analysis, PYZ, EXE, COLLECT는 PyInstaller가 제공하는 객체입니다.

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parent
ICON_PATH = PROJECT_ROOT / "assets" / "spotlight.ico"
VERSION_PATH = PROJECT_ROOT / "packaging" / "version_info.txt"

# 필수 파일이 없으면 기본 아이콘이나 잘못된 정보로 빌드하지 않습니다.
for required_path in (
    PROJECT_ROOT / "run_spotlight.py",
    ICON_PATH,
    VERSION_PATH,
):
    if not required_path.is_file():
        raise FileNotFoundError(f"빌드 필수 파일이 없습니다: {required_path}")

analysis = Analysis(
    [str(PROJECT_ROOT / "run_spotlight.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["spotlight.app"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 사용하지 않는 입력 라이브러리와 다른 Qt 바인딩을 제외합니다.
    excludes=["pynput", "keyboard", "PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)

# 현재 QWidget 기반 프로그램에서 사용하지 않는 플러그인과
# 그 전용 의존성을 배포 수집 목록에서 제외합니다.
unused_qt_files = {
    "qtvirtualkeyboardplugin.dll",
    "qt6virtualkeyboard.dll",
    "qt6qml.dll",
    "qt6qmlmeta.dll",
    "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll",
    "qt6quick.dll",
    "qpdf.dll",
    "qt6pdf.dll",
}

# Microsoft Visual C++ 런타임은 대상 PC의 설치본을 사용합니다.
# Python·PySide·Shiboken 하위 폴더에 수집된 파일도 함께 제외합니다.
microsoft_runtime_prefixes = (
    "msvcp",
    "vcruntime",
    "concrt",
    "vcomp",
    "vccorlib",
    "vcamp",
)


def is_microsoft_runtime(filename: str) -> bool:
    """배포 대상 경로에서 Visual C++ 런타임 DLL을 판별합니다."""
    name = Path(filename).name.lower()
    return (
        name.endswith(".dll")
        and name.startswith(microsoft_runtime_prefixes)
    )


analysis.binaries = [
    entry
    for entry in analysis.binaries
    if Path(entry[0]).name.lower() not in unused_qt_files
    and not is_microsoft_runtime(entry[0])
]

# 수집 방식이 달라져 데이터 목록에 들어간 경우에도 동봉하지 않습니다.
analysis.datas = [
    entry
    for entry in analysis.datas
    if not is_microsoft_runtime(entry[0])
]

archive = PYZ(analysis.pure)

executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Spotlight",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # 배포용 EXE는 콘솔 창을 표시하지 않습니다.
    # 출력·오류는 실행 진입점에서 사용자 설정 폴더의 logs에 기록합니다.
    console=False,
    icon=str(ICON_PATH),
    version=str(VERSION_PATH),
    uac_admin=False,
    uac_uiaccess=False,
    contents_directory="_internal",
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Spotlight",
)