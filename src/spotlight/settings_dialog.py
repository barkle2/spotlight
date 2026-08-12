from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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

from .config import (
    ClickSettings,
    PointerSettings,
    Settings,
    SpotlightSettings,
    WheelSettings,
)


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
        try:
            valid = len(value) == 7 and value.startswith("#") and int(value[1:], 16) >= 0
        except ValueError:
            valid = False
        if not valid:
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
        self.setWindowTitle("Spotlight 설정")
        self.setMinimumWidth(460)
        self.tabs = QTabWidget()
        self._build_pointer_tab(settings)
        self._build_spotlight_tab(settings)
        self._build_click_tab(settings)
        self._build_wheel_tab(settings)

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
            previous_size = self.applied_settings.pointer.size
            self.pointer_size.blockSignals(True)
            self.pointer_size.setValue(previous_size)
            self.pointer_size.blockSignals(False)
            self.pointer_size_value.setText(str(previous_size))
            QMessageBox.warning(self, "설정 오류", str(exc))

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
            self.on_pointer_preview(self.applied_settings.pointer.size)
        except Exception as exc:
            QMessageBox.warning(self, "설정 오류", str(exc))
            return
        super().reject()
