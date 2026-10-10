"""빌드 보고서와 실제 배포 파일을 대조하고 검사 결과를 저장합니다.

EXE의 해시·크기·버전 정보, 빌드 설정 해시, 필수·제외 모듈,
미사용 Qt 파일 잔존 여부와 PE 섹션의 UPX 흔적을 검사합니다.
실제 GUI 동작·커서 복원·기관 보안 검토는 별도 검증으로 관리합니다.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

import pefile
from PyInstaller.archive.readers import CArchiveReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from spotlight.app_info import (
    PRODUCT_NAME,
    PRODUCT_DESCRIPTION,
    PRODUCT_VERSION,
    PUBLISHER,
    COPYRIGHT,
    EXECUTABLE_NAME,
    calculate_file_sha256,
)


def read_version_fields(executable: Path) -> dict[str, str]:
    """EXE의 Windows 문자열 버전 리소스를 읽습니다."""
    pe = pefile.PE(str(executable))

    try:
        fields = {}

        for block in getattr(pe, "FileInfo", []):
            for entry in block:
                if entry.Key != b"StringFileInfo":
                    continue

                for table in entry.StringTable:
                    for key, value in table.entries.items():
                        fields[key.decode("utf-8")] = value.decode("utf-8")

        return fields
    finally:
        pe.close()


def main() -> int:
    """지정한 빌드의 산출물을 검사하고 JSON 보고서를 저장합니다.

    빌드 ID와 EXE 경로를 확인한 뒤 각 검사 결과를 수집합니다.
    수집한 결과가 모두 통과하면 0, 실패 항목이 있으면 1을 반환합니다.
    보고서 입력·경로 검증·결과 저장 오류는 예외로 전달합니다.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-report", type=Path, required=True)
    args = parser.parse_args()

    # PowerShell이 저장한 UTF-8 BOM도 허용합니다.
    build = json.loads(
        args.build_report.read_text(encoding="utf-8-sig")
    )
    build_id = build["build_id"]

    # 보고서 파일명이 임의 경로가 되지 않도록 형식을 제한합니다.
    if re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{8}", build_id) is None:
        raise ValueError("빌드 ID 형식이 잘못되었습니다.")

    executable = Path(build["executable"]).resolve()
    expected_path = (
        PROJECT_ROOT / "dist" / build_id / "Spotlight" / EXECUTABLE_NAME
    ).resolve()

    if executable != expected_path:
        raise ValueError("빌드 ID와 EXE 경로가 일치하지 않습니다.")

    checks = []

    def record(name: str, passed: bool, detail: object) -> None:
        """검사 이름·통과 여부·상세 내용을 공통 형식으로 수집합니다."""        
        checks.append({
            "name": name,
            "passed": bool(passed),
            "detail": detail,
        })

    # 각 검사 실패도 보고서에 남기고 다른 검사를 이어갑니다.
    try:
        file_hash = calculate_file_sha256(executable)
        record(
            "executable_hash",
            file_hash == build["executable_sha256"],
            file_hash,
        )
        record(
            "executable_size",
            executable.stat().st_size == build["executable_bytes"],
            executable.stat().st_size,
        )
    except OSError as error:
        record("executable_file", False, str(error))

    try:
        spec_path = PROJECT_ROOT / "packaging" / "Spotlight.spec"
        spec_hash = calculate_file_sha256(spec_path)
        record(
            "build_spec_hash",
            spec_hash == build["spec_sha256"],
            spec_hash,
        )
    except OSError as error:
        record("build_spec_hash", False, str(error))

    expected_fields = {
        "CompanyName": PUBLISHER,
        "FileDescription": PRODUCT_DESCRIPTION,
        "FileVersion": PRODUCT_VERSION,
        "InternalName": PRODUCT_NAME,
        "LegalCopyright": COPYRIGHT,
        "OriginalFilename": EXECUTABLE_NAME,
        "ProductName": PRODUCT_NAME,
        "ProductVersion": PRODUCT_VERSION,
    }

    try:
        fields = read_version_fields(executable)
        for key, expected in expected_fields.items():
            record(
                f"version_{key}",
                fields.get(key) == expected,
                fields.get(key),
            )
    except (OSError, pefile.PEFormatError, UnicodeError) as error:
        record("version_resource", False, str(error))

    try:
        archive = CArchiveReader(str(executable))
        modules = set(archive.open_embedded_archive("PYZ.pyz").toc)

        required = {
            "spotlight.app",
            "spotlight.app_info",
            "spotlight.config",
            "spotlight.cursor",
            "spotlight.effects",
            "spotlight.info_dialog",
            "spotlight.input",
            "spotlight.settings_dialog",
            "spotlight.smoke",
            "spotlight.tray",
        }
        record(
            "required_modules",
            required <= modules,
            sorted(required - modules),
        )

        forbidden = sorted(
            name for name in modules
            if name == "pynput" or name.startswith("pynput.")
            or name == "keyboard" or name.startswith("keyboard.")
        )
        record("excluded_input_modules", not forbidden, forbidden)

    except Exception as error:
        record("module_archive", False, str(error))

    internal_path = executable.parent / "_internal"
    record(
        "runtime_directory",
        internal_path.is_dir(),
        str(internal_path),
    )

    # EXE와 동봉된 DLL·PYD의 PE 섹션 이름에서 UPX 흔적을 검사합니다.
    # 이 검사는 모든 압축 방식이나 악성코드 여부를 판정하지 않습니다.
    binary_paths = sorted(
        path for path in executable.parent.rglob("*")
        if path.is_file()
        and path.suffix.lower() in (".exe", ".dll", ".pyd")
    )

    # 빌드 설정이 바뀌어 미사용 플러그인이 다시 포함되는지 검사합니다.
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
    unwanted_files = [
        str(path.relative_to(executable.parent))
        for path in binary_paths
        if path.name.lower() in unused_qt_files
    ]
    record("unused_qt_modules_excluded", not unwanted_files, unwanted_files)

    # 배포판은 대상 PC에 설치된 Visual C++ 런타임을 사용합니다.
    # 하위 폴더까지 검사해 Microsoft 런타임 재동봉을 감지합니다.
    microsoft_runtime_prefixes = (
        "msvcp",
        "vcruntime",
        "concrt",
        "vcomp",
        "vccorlib",
        "vcamp",
    )
    bundled_microsoft_runtime = [
        str(path.relative_to(executable.parent))
        for path in binary_paths
        if path.suffix.lower() == ".dll"
        and path.name.lower().startswith(microsoft_runtime_prefixes)
    ]
    record(
        "microsoft_runtime_not_bundled",
        not bundled_microsoft_runtime,
        bundled_microsoft_runtime,
    )    

    upx_hits = []
    unreadable = []

    for path in binary_paths:
        try:
            pe = pefile.PE(str(path), fast_load=True)
            try:
                sections = [
                    section.Name.rstrip(b"\0").decode(
                        "ascii", errors="replace"
                    )
                    for section in pe.sections
                ]
                if any(name.upper().startswith("UPX") for name in sections):
                    upx_hits.append(str(path))
            finally:
                pe.close()
        except (OSError, pefile.PEFormatError) as error:
            unreadable.append(f"{path}: {error}")

    record(
        "upx_section_scan",
        bool(binary_paths) and not upx_hits and not unreadable,
        {
            "scanned_files": len(binary_paths),
            "upx_hits": upx_hits,
            "unreadable": unreadable,
        },
    )

    passed = all(check["passed"] for check in checks)
    report = {
        "kind": "artifact_checks",
        "status": "passed" if passed else "failed",
        "build_id": build_id,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "executable": str(executable),
        "checks": checks,
    }

    report_directory = PROJECT_ROOT / "docs" / "validation"
    report_directory.mkdir(parents=True, exist_ok=True)
    report_path = report_directory / f"{build_id}-artifact-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = "ARTIFACT_CHECKS_PASS" if passed else "ARTIFACT_CHECKS_FAIL"
    print(f"{result}: {len(checks)} checks")
    print(f"ARTIFACT_REPORT: {report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())