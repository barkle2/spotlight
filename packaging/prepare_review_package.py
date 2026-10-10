"""검증한 EXE를 바탕으로 두 종류의 검토용 배포판을 만듭니다.

일반사용자용에는 실행 파일과 사용자 문서를 포함합니다.
개발자용에는 일반사용자용 전체와 소스·빌드·검증 자료를 포함합니다.
제3자 원본 소스는 별도 공통 자료 ZIP으로 제공합니다.

이 도구는 배포 파일을 구성하고 복사·압축 결과를 검사합니다.
기관 보안 검토나 라이선스 준비 완료를 판정하지는 않습니다.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD_ID = "20261010-015418-69047fee"
EXPECTED_EXE_HASH = (
    "55341CA5499F5C9347969C588DD8C888"
    "7951BF78C7C3EB1B6EDC21A3649AE561"
)

THIRD_PARTY_ARCHIVES = (
    "pyside-setup-everywhere-src-6.11.2.zip",
    "qtbase-everywhere-src-6.11.2.zip",
    "qtimageformats-everywhere-src-6.11.2.zip",
    "qtsvg-everywhere-src-6.11.2.zip",
    "qttranslations-everywhere-src-6.11.2.zip",
    "mesa-11.2.2.tar.xz",
)


def file_hash(path: Path) -> str:
    """파일을 나누어 읽고 SHA-256을 반환합니다."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def read_json(path: Path) -> dict:
    """PowerShell이 기록한 UTF-8 BOM도 허용합니다."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    """사람이 읽기 쉬운 UTF-8 JSON으로 기록합니다."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_file(source: Path, destination: Path) -> None:
    """파일을 복사하고 원본과 복사본의 해시가 같은지 확인합니다."""
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"일반 파일이 아닙니다: {source}")

    if destination.exists():
        raise FileExistsError(f"복사 대상이 이미 있습니다: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    if file_hash(source) != file_hash(destination):
        raise RuntimeError(f"복사 결과가 원본과 다릅니다: {destination}")


def copy_tree(
    source: Path,
    destination: Path,
    suffixes: set[str] | None = None,
) -> None:
    """폴더를 복사하되 링크와 캐시를 제외합니다.

    suffixes가 지정되면 해당 확장자만 복사합니다.
    실행 런타임은 확장자 제한 없이 전체를 복사합니다.
    링크·정션은 다른 위치의 파일을 포함할 수 있어 거부합니다.
    """
    if source.is_symlink() or source.is_junction() or not source.is_dir():
        raise ValueError(f"일반 폴더가 아닙니다: {source}")

    for item in sorted(source.iterdir()):
        if item.is_symlink() or item.is_junction():
            raise ValueError(f"링크는 동봉하지 않습니다: {item}")

        if item.name in {"__pycache__", ".git", ".venv", "venv"}:
            continue

        target = destination / item.name

        if item.is_dir():
            copy_tree(item, target, suffixes)
        elif item.is_file():
            if suffixes is None or item.suffix.lower() in suffixes:
                copy_file(item, target)


def create_archive(directory: Path) -> dict:
    """파일 해시 목록을 기록하고 ZIP 내부 파일까지 대조합니다."""
    inventory = {
        path.relative_to(directory).as_posix(): file_hash(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }

    # 목록 자체는 자기 해시를 포함할 수 없으므로 별도로 검사합니다.
    manifest = directory / "file-manifest.json"
    write_json(
        manifest,
        {
            "status": "review_only",
            "build_id": BUILD_ID,
            "files": inventory,
        },
    )

    archive = directory.parent / f"{directory.name}.zip"

    # x 모드는 기존 ZIP 덮어쓰기를 방지합니다.
    with zipfile.ZipFile(
        archive, "x", compression=zipfile.ZIP_DEFLATED
    ) as package:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                package.write(
                    path,
                    f"{directory.name}/{path.relative_to(directory).as_posix()}",
                )

    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError(f"ZIP CRC 검사 실패: {archive}")

        expected_names = {
            f"{directory.name}/{name}"
            for name in (*inventory, "file-manifest.json")
        }

        names = package.namelist()
        if len(names) != len(expected_names) or set(names) != expected_names:
            raise RuntimeError(f"ZIP 파일 목록 불일치: {archive}")

        for name, expected_hash in inventory.items():
            with package.open(f"{directory.name}/{name}") as stream:
                actual_hash = hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest().upper()

            if actual_hash != expected_hash:
                raise RuntimeError(f"ZIP 내부 파일 해시 불일치: {name}")

        if package.read(
            f"{directory.name}/file-manifest.json"
        ) != manifest.read_bytes():
            raise RuntimeError("ZIP 내부 해시 목록이 원본과 다릅니다.")

    return {
        "path": str(archive),
        "sha256": file_hash(archive),
        "bytes": archive.stat().st_size,
        "file_count": len(expected_names),
        "archive_checks_passed": True,
    }


def check_candidate() -> tuple[Path, tuple[Path, ...]]:
    """현재 EXE와 해당 EXE의 빌드·검증보고서를 확인합니다."""
    application = ROOT / "dist" / BUILD_ID / "Spotlight"
    executable = application / "Spotlight.exe"

    reports = (
        ROOT / "build" / BUILD_ID / "build-report.json",
        ROOT / "docs" / "validation" / f"{BUILD_ID}-artifact-report.json",
        ROOT / "docs" / "validation" / f"{BUILD_ID}-smoke-report.json",
    )

    build, artifact, smoke = (read_json(path) for path in reports)

    if file_hash(executable) != EXPECTED_EXE_HASH:
        raise RuntimeError("기준 EXE의 해시가 변경됐습니다.")

    for report in (build, artifact, smoke):
        if Path(report["executable"]).resolve() != executable.resolve():
            raise RuntimeError("보고서의 EXE 경로가 기준 후보와 다릅니다.")

    if (
        build["build_id"] != BUILD_ID
        or build["executable_sha256"].upper() != EXPECTED_EXE_HASH
        or artifact["build_id"] != BUILD_ID
    ):
        raise RuntimeError("보고서의 빌드 식별 정보가 다릅니다.")

    artifact_checks = artifact.get("checks", [])
    smoke_checks = smoke.get("checks", {})

    if (
        artifact.get("status") != "passed"
        or len(artifact_checks) != 17
        or not all(item.get("passed") is True for item in artifact_checks)
        or smoke.get("status") != "passed"
        or smoke.get("exit_code") != 0
        or len(smoke_checks) != 10
        or not all(value is True for value in smoke_checks.values())
        or smoke.get("errors")
    ):
        raise RuntimeError("필수 검증보고서가 통과 상태가 아닙니다.")

    # 빌드 설정은 당시 보고서와 대조할 수 있습니다.
    # 나머지 소스 전체의 빌드 당시 해시는 기록되어 있지 않습니다.
    if file_hash(ROOT / "packaging" / "Spotlight.spec") != (
        build["spec_sha256"].upper()
    ):
        raise RuntimeError("현재 spec이 기준 빌드 당시와 다릅니다.")

    return application, reports


def main() -> None:
    """새 검토 폴더에 배포판과 공통 자료를 순서대로 구성합니다."""
    application, reports = check_candidate()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = ROOT / "dist" / f"review-{stamp}-{uuid.uuid4().hex[:8]}"
    output.mkdir(parents=True, exist_ok=False)

    user_package = output / "Spotlight-user"
    developer_package = output / "Spotlight-developer"
    third_party_package = output / "Spotlight-third-party-sources"

    # 일반사용자용: 실행에 필요한 런타임 전체를 함께 복사합니다.
    copy_file(application / "Spotlight.exe", user_package / "Spotlight.exe")
    copy_tree(application / "_internal", user_package / "_internal")

    for name in (
        "사용설명서.html",
        "라이선스_안내.md",
        "제3자_소스_제공.md",
    ):
        copy_file(ROOT / "docs" / name, user_package / name)

    copy_tree(ROOT / "docs" / "licenses", user_package / "licenses")

    # 개발자용은 일반사용자용 파일을 동일하게 포함합니다.
    # 개발 프로젝트는 별도 하위 폴더에 두어 실행 배포본과 구분합니다.
    copy_tree(user_package, developer_package)
    project = developer_package / "project"

    for name in ("run_spotlight.py", "requirements.txt"):
        copy_file(ROOT / name, project / name)

    copy_tree(ROOT / "src", project / "src", {".py"})
    copy_tree(
        ROOT / "packaging",
        project / "packaging",
        {".py", ".ps1", ".spec", ".txt"},
    )
    copy_tree(ROOT / "validation", project / "validation", {".py"})
    copy_file(
        ROOT / "assets" / "spotlight.ico",
        project / "assets" / "spotlight.ico",
    )
    copy_file(
        ROOT / "docs" / "create_manual.py",
        project / "docs" / "create_manual.py",
    )
    copy_tree(
        ROOT / "docs" / "manual-images",
        project / "docs" / "manual-images",
        {".png"},
    )

    for name in ("소스코드_설명서.md", "검증보고서.md"):
        copy_file(ROOT / "docs" / name, developer_package / name)

    for report in reports:
        copy_file(report, developer_package / "검증보고서" / report.name)

    # 현재 루트 README는 이전 버전 문서이므로 그대로 동봉하지 않습니다.
    (project / "README.md").write_text(
        "# Spotlight 개발 자료\n\n"
        "- 상태: 1.0.0 검토용 배포판\n"
        "- 실행 환경: Windows 11, 64비트 Python 3.13\n"
        "- 기준 Python: 3.13.13\n"
        "- 명령은 이 README가 있는 project 폴더에서 실행합니다.\n\n"
        "## 소스 실행\n\n"
        "```powershell\n"
        "python -m pip install -r requirements.txt\n"
        "python run_spotlight.py\n"
        "```\n\n"
        "## EXE 빌드\n\n"
        "```powershell\n"
        "python -m pip install -r packaging/requirements-build.txt\n"
        "powershell -NoProfile -ExecutionPolicy Bypass "
        "-File packaging/build.ps1\n"
        "```\n\n"
        "- 빌드 결과는 project/dist, 보고서는 project/build에 생성됩니다.\n"
        "- 빌드 후에는 새 결과에 대해 산출물·스모크 검증을 수행합니다.\n"
        "- 상세 구조와 처리 흐름은 상위 폴더의 소스코드 설명서를 참고합니다.\n"
        "- 동봉 소스는 묶음 생성 시점의 파일입니다. 기존 EXE 빌드 당시의 "
        "전체 소스와 동일한지는 별도 확인이 필요합니다.\n"
        "- prepare_review_package.py는 원 작업공간의 기준 빌드와 보고서를 "
        "사용하는 도구입니다. 새 빌드에는 기준 정보를 갱신해야 합니다.\n",
        encoding="utf-8",
    )

    # 큰 제3자 소스는 두 실행 배포판에 중복해서 넣지 않습니다.
    for name in THIRD_PARTY_ARCHIVES:
        copy_file(
            ROOT / "docs" / "third-party-sources" / name,
            third_party_package / name,
        )

    copy_file(
        ROOT / "docs" / "제3자_소스_제공.md",
        third_party_package / "제3자_소스_제공.md",
    )

    results = {
        "user": create_archive(user_package),
        "developer": create_archive(developer_package),
        "third_party_sources": create_archive(third_party_package),
    }

    report_path = output / "review-package-report.json"
    write_json(
        report_path,
        {
            "status": "review_only",
            "build_id": BUILD_ID,
            "executable_sha256": EXPECTED_EXE_HASH,
            "packages": results,
            "remaining": [
                "두 배포판의 압축 해제 실행 및 사용자 최종 검토",
                "동봉 소스와 기준 EXE 빌드 당시 소스의 대응 확인",
                "제3자 라이선스 자료 및 대응 소스의 최종 대조",
                "배포 대상 PC의 Visual C++ x64 런타임 설치 및 실행 확인",
                "기관 보안 검토는 추후 예정",
            ],
        },
    )

    for kind, result in results.items():
        print(f"PACKAGE_CREATED [{kind}]: {result['path']}")
    print(f"PACKAGE_REPORT: {report_path}")


if __name__ == "__main__":
    main()