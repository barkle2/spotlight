from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import (
    __company__,
    __copyright__,
    __description__,
    __original_filename__,
    __product__,
    __version__,
)
from .config import (
    COLOR_PATTERN,
    ClickSettings,
    PointerSettings,
    Settings,
    SpotlightSettings,
    WheelSettings,
)


HASH_CHUNK_BYTES = 1024 * 1024


def executable_path() -> Path | None:
    """배포된 실행 파일 경로. 소스에서 실행 중이면 None."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ColorEditor(QWidget):
    def __init__(self, color: str) -> None:
        super().__init__()
        self.edit = QLineEdit(color)
        self.edit.setMaxLength(7)
        self.button = QPushButton("색상 선택")
        self.button.clicked.connect(self.choose_color)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        layout.addWidget(self.button)
        self._update_button()
        self.edit.textChanged.connect(self._update_button)

    def choose_color(self) -> None:
        initial = QColor(self.value())
        selected = QColorDialog.getColor(initial, self, "색상 선택")
        if selected.isValid():
            self.edit.setText(selected.name().upper())

    def _update_button(self) -> None:
        color = QColor(self.edit.text())
        if color.isValid():
            self.button.setStyleSheet(
                f"background-color: {color.name()}; color: "
                f"{'black' if color.lightness() > 130 else 'white'};"
            )
        else:
            self.button.setStyleSheet("")

    def value(self) -> str:
        value = self.edit.text().strip().upper()
        if not COLOR_PATTERN.match(value):
            raise ValueError("색상은 #RRGGBB 형식이어야 합니다.")
        return value


def spin(value: int, minimum: int, maximum: int, suffix: str = "") -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    if suffix:
        widget.setSuffix(suffix)
    return widget


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, on_apply, on_pointer_preview, parent=None) -> None:
        super().__init__(parent)
        self.on_apply = on_apply
        self.on_pointer_preview = on_pointer_preview
        self.applied_settings = settings
        self.about_tab_index = -1
        self.hash_computed = False
        self.setWindowTitle("Spotlight 설정")
        self.setMinimumWidth(460)
        self.tabs = QTabWidget()
        self._build_pointer_tab(settings)
        self._build_spotlight_tab(settings)
        self._build_click_tab(settings)
        self._build_wheel_tab(settings)
        self._build_about_tab()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        apply_button = self.buttons.button(QDialogButtonBox.Apply)
        apply_button.setEnabled(True)
        apply_button.clicked.connect(self._apply)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.buttons)

    def _build_pointer_tab(self, settings: Settings) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.pointer_size = QSlider(Qt.Horizontal)
        self.pointer_size.setRange(1, 15)
        self.pointer_size.setSingleStep(1)
        self.pointer_size.setPageStep(1)
        self.pointer_size.setTickInterval(1)
        self.pointer_size.setTickPosition(QSlider.TicksBelow)
        self.pointer_size.setValue(settings.pointer.size)
        self.pointer_size_value = QLabel(str(settings.pointer.size))
        slider_row = QHBoxLayout()
        slider_row.addWidget(self.pointer_size, 1)
        slider_row.addWidget(self.pointer_size_value)
        form.addRow("포인터 크기", slider_row)
        form.addRow(QLabel("1은 32px이며 단계마다 16px씩 증가합니다."))
        self.pointer_size.valueChanged.connect(self._apply_pointer_size)
        self.tabs.addTab(page, "포인터")

    def _apply_pointer_size(self, size: int) -> None:
        self.pointer_size_value.setText(str(size))
        try:
            self.on_pointer_preview(size)
        except Exception as exc:
            self.notify_preview_error(str(exc), self.applied_settings.pointer.size)

    def notify_preview_error(self, message: str, fallback_size: int) -> None:
        """프리뷰 적용 실패 통지.

        포인터 프리뷰는 디바운스되어 슬라이더 콜백보다 늦게 실행되므로,
        실패는 이 메서드를 통해 뒤늦게 전달된다. 슬라이더를 되돌린 뒤 알린다.
        """
        self.pointer_size.blockSignals(True)
        self.pointer_size.setValue(fallback_size)
        self.pointer_size.blockSignals(False)
        self.pointer_size_value.setText(str(fallback_size))
        QMessageBox.warning(self, "설정 오류", message)

    def _build_spotlight_tab(self, settings: Settings) -> None:
        page = QWidget()
        form = QFormLayout(page)
        current = settings.spotlight
        self.spotlight_enabled = QCheckBox("강조 원 표시")
        self.spotlight_enabled.setChecked(current.enabled)
        self.spotlight_diameter = spin(current.diameter, 20, 1000, " px")
        self.spotlight_color = ColorEditor(current.color)
        self.spotlight_opacity = spin(current.opacity, 0, 100, " %")
        self.spotlight_style = QComboBox()
        self.spotlight_style.addItem("채움", "fill")
        self.spotlight_style.addItem("테두리", "outline")
        self.spotlight_style.setCurrentIndex(
            max(0, self.spotlight_style.findData(current.style))
        )
        self.spotlight_border = spin(current.border_width, 1, 50, " px")
        form.addRow(self.spotlight_enabled)
        form.addRow("원 크기", self.spotlight_diameter)
        form.addRow("색상", self.spotlight_color)
        form.addRow("불투명도", self.spotlight_opacity)
        form.addRow("표시 방식", self.spotlight_style)
        form.addRow("테두리 두께", self.spotlight_border)
        self.spotlight_border_label = form.labelForField(self.spotlight_border)
        self.spotlight_style.currentIndexChanged.connect(
            self._update_spotlight_border_enabled
        )
        self._update_spotlight_border_enabled()
        self.tabs.addTab(page, "강조 원")

    def _update_spotlight_border_enabled(self) -> None:
        enabled = self.spotlight_style.currentData() == "outline"
        self.spotlight_border.setEnabled(enabled)
        self.spotlight_border_label.setEnabled(enabled)

    def _build_click_tab(self, settings: Settings) -> None:
        page = QWidget()
        form = QFormLayout(page)
        current = settings.click
        self.click_enabled = QCheckBox("클릭 효과 사용")
        self.click_enabled.setChecked(current.enabled)
        self.left_color = ColorEditor(current.left_color)
        self.right_color = ColorEditor(current.right_color)
        self.click_duration = spin(current.duration_ms, 50, 2000, " ms")
        form.addRow(self.click_enabled)
        form.addRow("왼쪽 클릭 색상", self.left_color)
        form.addRow("오른쪽 클릭 색상", self.right_color)
        form.addRow("지속 시간", self.click_duration)
        self.tabs.addTab(page, "클릭")

    def _build_wheel_tab(self, settings: Settings) -> None:
        page = QWidget()
        form = QFormLayout(page)
        current = settings.wheel
        self.wheel_enabled = QCheckBox("휠 효과 사용")
        self.wheel_enabled.setChecked(current.enabled)
        self.wheel_color = ColorEditor(current.color)
        self.wheel_duration = spin(current.duration_ms, 50, 2000, " ms")
        self.wheel_line_width = spin(current.line_width, 1, 50, " px")
        form.addRow(self.wheel_enabled)
        form.addRow("색상", self.wheel_color)
        form.addRow("지속 시간", self.wheel_duration)
        form.addRow("선 두께", self.wheel_line_width)
        self.tabs.addTab(page, "휠")

    def _build_about_tab(self) -> None:
        """제품 정보 표시 전용 탭.

        표시 항목은 packaging/version_info.py 의 VERSIONINFO 리소스와
        동일한 값이며, src/spotlight/__init__.py 를 단일 출처로 사용한다.
        """
        page = QWidget()
        form = QFormLayout(page)

        title = QLabel(f"<b>{__product__}</b>")
        form.addRow(title)

        form.addRow("설명", QLabel(__description__))
        form.addRow("버전", QLabel(__version__))
        form.addRow("배포", QLabel(__company__))
        form.addRow("파일명", QLabel(__original_filename__))

        copyright_label = QLabel(__copyright__)
        copyright_label.setWordWrap(True)
        form.addRow("저작권", copyright_label)

        # 해시는 64자 16진수이므로 등폭 글꼴로 줄바꿈해 표시한다.
        # 클립보드 API를 사용하지 않고 텍스트 선택만 허용한다. 사용자는
        # 선택 후 Ctrl+C 로 복사할 수 있고, 앱은 클립보드 권한을 갖지 않는다.
        self.about_hash = QLabel(self._initial_hash_text())
        self.about_hash.setWordWrap(True)
        self.about_hash.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.about_hash.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")
        form.addRow("SHA-256", self.about_hash)

        hash_note = QLabel("배포 시 공지된 해시와 대조해 파일 변조 여부를 확인할 수 있습니다.")
        hash_note.setWordWrap(True)
        form.addRow("", hash_note)

        self.about_tab_index = self.tabs.count()
        self.tabs.addTab(page, "정보")
        # 다이얼로그 열기가 느려지지 않도록 정보 탭을 처음 열 때 계산한다.
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _initial_hash_text(self) -> str:
        return "정보 탭을 열면 계산합니다." if executable_path() else "실행 파일에서만 표시됩니다."

    def _on_tab_changed(self, index: int) -> None:
        if index == self.about_tab_index:
            self.ensure_executable_hash()

    def ensure_executable_hash(self) -> None:
        """실행 파일 해시를 한 번만 계산해 표시한다."""
        if self.hash_computed:
            return
        executable = executable_path()
        if executable is None:
            self.hash_computed = True
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.about_hash.setText(file_sha256(executable))
        except OSError as exc:
            self.about_hash.setText(f"계산할 수 없습니다: {exc.strerror or exc}")
        finally:
            QApplication.restoreOverrideCursor()
            self.hash_computed = True

    def current_settings(self) -> Settings:
        return Settings(
            pointer=PointerSettings(size=self.pointer_size.value()),
            spotlight=SpotlightSettings(
                enabled=self.spotlight_enabled.isChecked(),
                diameter=self.spotlight_diameter.value(),
                color=self.spotlight_color.value(),
                opacity=self.spotlight_opacity.value(),
                style=str(self.spotlight_style.currentData()),
                border_width=self.spotlight_border.value(),
            ),
            click=ClickSettings(
                enabled=self.click_enabled.isChecked(),
                left_color=self.left_color.value(),
                right_color=self.right_color.value(),
                duration_ms=self.click_duration.value(),
            ),
            wheel=WheelSettings(
                enabled=self.wheel_enabled.isChecked(),
                color=self.wheel_color.value(),
                duration_ms=self.wheel_duration.value(),
                line_width=self.wheel_line_width.value(),
            ),
        )

    def _apply(self) -> bool:
        try:
            settings = self.current_settings()
            self.on_apply(settings)
            self.applied_settings = settings
            return True
        except Exception as exc:
            QMessageBox.warning(self, "설정 오류", str(exc))
            return False

    def _accept(self) -> None:
        if self._apply():
            self.accept()

    def reject(self) -> None:
        try:
            # 취소는 즉시 되돌려야 하므로 디바운스를 우회한다.
            self.on_pointer_preview(self.applied_settings.pointer.size, immediate=True)
        except Exception as exc:
            QMessageBox.warning(self, "설정 오류", str(exc))
            return
        super().reject()
