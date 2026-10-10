"""프로그램 정보와 실행 파일 해시를 별도 창에 표시합니다."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from .app_info import (
    PRODUCT_NAME,
    PRODUCT_DESCRIPTION,
    PRODUCT_VERSION,
    PUBLISHER,
    COPYRIGHT,
    EXECUTABLE_NAME,
    get_runtime_file_path,
    calculate_file_sha256,
)


class InfoDialog(QDialog):
    """설정 변경 없이 식별 정보만 보여주는 창입니다."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Spotlight 정보")
        self.setMinimumWidth(520)

        # 같은 창을 다시 열 때 성공한 해시를 재사용합니다.
        # 계산에 실패한 경우에는 다음 열기에서 다시 시도합니다.
        self.hash_loaded = False
        self.file_path = get_runtime_file_path()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        values = (
            ("제품명", PRODUCT_NAME),
            ("설명", PRODUCT_DESCRIPTION),
            ("버전", PRODUCT_VERSION),
            ("배포 주체", PUBLISHER),
            ("배포 파일명", EXECUTABLE_NAME),
            ("저작권", COPYRIGHT),
        )

        for title, value in values:
            label = QLabel(value)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form.addRow(title, label)

        layout.addLayout(form)

        # 소스 실행과 배포 EXE의 해시를 명확히 구분합니다.
        if getattr(sys, "frozen", False):
            note = "현재 실행 중인 EXE 파일의 SHA-256입니다."
        else:
            note = (
                "소스 실행 중입니다. 아래 값은 run_spotlight.py의 "
                "SHA-256이며, 배포 EXE의 해시가 아닙니다."
            )

        note_label = QLabel(note)
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        layout.addWidget(QLabel("SHA-256"))

        self.hash_edit = QPlainTextEdit()
        self.hash_edit.setReadOnly(True)
        self.hash_edit.setMaximumHeight(90)
        self.hash_edit.setPlainText("정보 창을 열면 계산합니다.")
        layout.addWidget(self.hash_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText("닫기")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_info(self) -> None:
        """기존 창을 앞으로 가져오고 필요한 경우 해시를 계산합니다."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()

        self.raise_()
        self.activateWindow()

        if self.hash_loaded:
            return

        try:
            file_hash = calculate_file_sha256(self.file_path)
        except OSError:
            # 예외 문자열에는 로컬 경로가 포함될 수 있으므로
            # 정보 창에는 경로 없는 안내만 표시합니다.
            self.hash_edit.setPlainText(
                "SHA-256을 계산하지 못했습니다.\n"
                "파일 접근 권한과 실행 상태를 확인한 뒤 다시 열어 주세요."
            )
            return

        self.hash_edit.setPlainText(file_hash)
        self.hash_loaded = True

    def stop(self) -> None:
        """프로그램 종료 시 정보 창을 닫습니다."""
        self.close()