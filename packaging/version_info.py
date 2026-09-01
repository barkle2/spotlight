# -*- coding: utf-8 -*-
# PyInstaller VERSIONINFO 리소스 정의
#
# 분석보고서 V-1 대응의 일부. 서명과 별개로, 파일 속성에서 제품/버전을
# 식별할 수 있게 한다. 배포 전 CompanyName을 기관명으로 교체할 것.
#
# 버전 갱신 시 filevers / prodvers / FileVersion / ProductVersion 을
# src/spotlight/__init__.py 의 __version__ 과 함께 맞출 것.

VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(0, 2, 0, 0),
        prodvers=(0, 2, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,      # VOS_NT_WINDOWS32
        fileType=0x1,    # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "041204B0",  # 한국어(0x0412) + Unicode(1200)
                    [
                        StringStruct("CompanyName", "지능정보화기획팀"),
                        StringStruct("FileDescription", "Spotlight 커서 강조 도구"),
                        StringStruct("FileVersion", "0.2.0.0"),
                        StringStruct("InternalName", "spotlight"),
                        StringStruct("OriginalFilename", "spotlight.exe"),
                        StringStruct("ProductName", "Spotlight"),
                        StringStruct("ProductVersion", "0.2.0.0"),
                        StringStruct("LegalCopyright", "Copyright (c) 2026 Donghyun Kim"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0412, 1200])]),
    ],
)
