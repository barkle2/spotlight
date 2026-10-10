"""강조원·클릭·휠·포인터 설정 화면을 제공합니다.

입력값을 공통 설정 모델로 검증하고, 프리뷰와 적용을 앱에 요청합니다.
설정 파일 저장과 실제 효과·시스템 커서 변경은 앱의 콜백이 담당합니다.
취소하면 창을 열었을 때 또는 마지막 적용 시점의 설정으로 복구합니다.
"""

from .cursor import cursor_size_from_level
from collections.abc import Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QColorDialog,
    QHBoxLayout,
    QPushButton,
    QSlider,
)

from .config import (
    HighlightSettings,
    MAX_DIAMETER,
    MAX_LINE_WIDTH,
    MIN_DIAMETER,
    MIN_LINE_WIDTH,
    MAX_CLICK_DURATION_MS,
    MIN_CLICK_DURATION_MS,
    MIN_WHEEL_DURATION_MS,
    MAX_WHEEL_DURATION_MS,
    MIN_CURSOR_LEVEL,
    MAX_CURSOR_LEVEL,
    normalize_color,    
)


class SettingsDialog(QDialog):
    """편집 중인 입력값과 마지막 적용값을 구분하여 관리합니다.

    프리뷰는 저장 없이 실행 화면에 반영합니다.
    적용 콜백이 성공한 경우에만 applied_settings를 갱신하여
    이후 취소·X·Esc의 복구 기준으로 사용합니다.
    """

    def __init__(
        self,
        settings: HighlightSettings,
        preview_callback: Callable[[HighlightSettings], None],
        apply_callback: Callable[[HighlightSettings], bool],
    ) -> None:
        super().__init__()

        self.setWindowTitle("Spotlight 설정")
        self.setMinimumWidth(480)

        # 취소하면 창을 열었을 때 또는 마지막 적용 시점의 값으로 복구합니다.
        self.applied_settings = settings
        self.preview_callback = preview_callback
        self.apply_callback = apply_callback

        # 입력 필드 초기화 중에는 중간 값으로 프리뷰하지 않습니다.
        self.loading = False

        self.enabled_checkbox = QCheckBox("강조 원 표시")

        self.diameter_spinbox = QSpinBox()
        self.diameter_spinbox.setRange(MIN_DIAMETER, MAX_DIAMETER)

        self.color_edit = QLineEdit()
        self.color_edit.setPlaceholderText("#RRGGBB")

        self.opacity_spinbox = QSpinBox()
        self.opacity_spinbox.setRange(0, 100)
        self.opacity_spinbox.setSuffix(" %")

        self.style_combobox = QComboBox()
        self.style_combobox.addItem("채움", "fill")
        self.style_combobox.addItem("테두리", "outline")

        self.line_width_spinbox = QSpinBox()
        self.line_width_spinbox.setRange(MIN_LINE_WIDTH, MAX_LINE_WIDTH)

        self.click_enabled_checkbox = QCheckBox("클릭 효과 표시")
        self.left_click_color_edit = QLineEdit()
        self.right_click_color_edit = QLineEdit()

        self.click_duration_spinbox = QSpinBox()
        self.click_duration_spinbox.setRange(
            MIN_CLICK_DURATION_MS, MAX_CLICK_DURATION_MS
        )
        self.click_duration_spinbox.setSuffix(" ms")
        self.click_style_combobox = QComboBox()
        self.click_style_combobox.addItem("채움", "fill")
        self.click_style_combobox.addItem("테두리", "outline")

        self.click_line_width_spinbox = QSpinBox()
        self.click_line_width_spinbox.setRange(
            MIN_LINE_WIDTH, MAX_LINE_WIDTH
        )

        self.wheel_enabled_checkbox = QCheckBox("휠 효과 표시")
        self.wheel_color_edit = QLineEdit()
        self.wheel_duration_spinbox = QSpinBox()
        self.wheel_duration_spinbox.setRange(
            MIN_WHEEL_DURATION_MS, MAX_WHEEL_DURATION_MS
        )
        self.wheel_duration_spinbox.setSuffix(" ms")

        self.wheel_line_width_spinbox = QSpinBox()
        self.wheel_line_width_spinbox.setRange(
            MIN_LINE_WIDTH, MAX_LINE_WIDTH
        )

        self.cursor_enabled_checkbox = QCheckBox("포인터 확대 사용")

        self.cursor_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.cursor_level_slider.setRange(
            MIN_CURSOR_LEVEL, MAX_CURSOR_LEVEL
        )
        self.cursor_level_slider.setSingleStep(1)
        self.cursor_level_slider.setPageStep(1)
        self.cursor_level_slider.setTickInterval(1)
        self.cursor_level_slider.setTickPosition(
            QSlider.TickPosition.TicksBelow
        )

        # 드래그 중 시스템 커서 14종을 계속 교체하지 않도록
        # 실제 값 변경은 슬라이더를 놓았을 때 반영합니다.
        self.cursor_level_slider.setTracking(False)
        self.cursor_level_slider.setToolTip(
            "1~15단계. 슬라이더를 놓으면 포인터 크기가 반영됩니다."
        )

        self.cursor_level_label = QLabel()

        self.cursor_size_widget = QWidget()
        cursor_size_layout = QVBoxLayout(self.cursor_size_widget)
        cursor_size_layout.setContentsMargins(0, 0, 0, 0)
        cursor_size_layout.addWidget(self.cursor_level_slider)
        cursor_size_layout.addWidget(self.cursor_level_label)

        # 움직이는 동안에는 표시 문구만 갱신합니다.
        self.cursor_level_slider.sliderMoved.connect(
            self.update_cursor_level_label
        )

        # 기능별 입력 필드를 나누되 설정 모델과 저장 흐름은 공유합니다.
        self.tabs = QTabWidget()

        highlight_page = QWidget()
        highlight_form = QFormLayout(highlight_page)
        highlight_form.addRow("활성화", self.enabled_checkbox)
        highlight_form.addRow("지름", self.diameter_spinbox)
        highlight_form.addRow(
            "색상", self.create_color_selector(self.color_edit)
        )
        highlight_form.addRow("불투명도", self.opacity_spinbox)
        highlight_form.addRow("표시 방식", self.style_combobox)
        highlight_form.addRow("선 두께", self.line_width_spinbox)
        self.tabs.addTab(highlight_page, "강조원")

        click_page = QWidget()
        click_form = QFormLayout(click_page)
        click_form.addRow("활성화", self.click_enabled_checkbox)
        click_form.addRow(
            "왼쪽 색상", self.create_color_selector(self.left_click_color_edit)
        )
        click_form.addRow(
            "오른쪽 색상", self.create_color_selector(self.right_click_color_edit)
        )
        click_form.addRow("지속 시간", self.click_duration_spinbox)
        click_form.addRow("표시 방식", self.click_style_combobox)
        click_form.addRow("선 두께", self.click_line_width_spinbox)
        self.tabs.addTab(click_page, "클릭")

        wheel_page = QWidget()
        wheel_form = QFormLayout(wheel_page)
        wheel_form.addRow("활성화", self.wheel_enabled_checkbox)        
        wheel_form.addRow(
            "색상", self.create_color_selector(self.wheel_color_edit)
        )
        wheel_form.addRow("지속 시간", self.wheel_duration_spinbox)
        wheel_form.addRow("선 두께", self.wheel_line_width_spinbox)
        self.tabs.addTab(wheel_page, "휠")

        pointer_page = QWidget()
        pointer_form = QFormLayout(pointer_page)
        pointer_form.addRow("활성화", self.cursor_enabled_checkbox)
        pointer_form.addRow("크기", self.cursor_size_widget)        
        self.tabs.addTab(pointer_page, "포인터")

        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText("확인")
        self.buttons.button(
            QDialogButtonBox.StandardButton.Apply
        ).setText("적용")
        self.buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("취소")

        self.reset_button = QPushButton("전체 초기화")
        self.reset_button.setAutoDefault(False)
        self.reset_button.setToolTip(
            "모든 설정을 기본값으로 미리 표시합니다. "
            "적용 또는 확인을 눌러야 저장됩니다."
        )
        self.reset_button.clicked.connect(self.reset_to_defaults)

        # 초기화는 왼쪽, 확인·적용·취소는 오른쪽에 배치합니다.
        button_row = QHBoxLayout()
        button_row.addWidget(self.reset_button)
        button_row.addStretch()
        button_row.addWidget(self.buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.validation_label)
        layout.addLayout(button_row)

        # 유효한 입력값만 실제 강조 원에 프리뷰합니다.
        self.enabled_checkbox.toggled.connect(self.preview)
        self.diameter_spinbox.valueChanged.connect(self.preview)
        self.color_edit.textChanged.connect(self.preview)
        self.opacity_spinbox.valueChanged.connect(self.preview)
        self.style_combobox.currentIndexChanged.connect(self.preview)
        self.line_width_spinbox.valueChanged.connect(self.preview)
        self.click_enabled_checkbox.toggled.connect(self.preview)
        self.left_click_color_edit.textChanged.connect(self.preview)
        self.right_click_color_edit.textChanged.connect(self.preview)
        self.click_duration_spinbox.valueChanged.connect(self.preview)
        self.click_style_combobox.currentIndexChanged.connect(self.preview)
        self.click_line_width_spinbox.valueChanged.connect(self.preview)
        self.wheel_enabled_checkbox.toggled.connect(self.preview)        
        self.wheel_color_edit.textChanged.connect(self.preview)
        self.wheel_duration_spinbox.valueChanged.connect(self.preview)
        self.wheel_line_width_spinbox.valueChanged.connect(self.preview)
        self.cursor_enabled_checkbox.toggled.connect(self.preview)
        self.cursor_level_slider.valueChanged.connect(self.preview)        

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(
            QDialogButtonBox.StandardButton.Apply
        ).clicked.connect(self.apply_changes)

        self.load_fields(settings)

    def create_color_selector(self, color_edit: QLineEdit) -> QWidget:
        """색상 견본·색상 코드 입력·팔레트를 하나로 구성합니다.

        팔레트에서 선택한 색상을 기존 입력 필드에 기록하여
        공통 색상 검증과 프리뷰·적용·취소 흐름을 사용합니다.
        팔레트를 취소하면 입력값을 변경하지 않습니다.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()

        swatch = QLabel()
        swatch.setFixedSize(28, 28)
        swatch.setToolTip("현재 선택한 색상")

        color_edit.setPlaceholderText("#RRGGBB")
        color_edit.setMaximumWidth(110)

        palette_button = QPushButton("색상 선택")
        palette_button.setAutoDefault(False)

        top_row.addWidget(swatch)
        top_row.addWidget(color_edit)
        top_row.addWidget(palette_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        def update_swatch(text: str) -> None:
            """검증된 색상만 견본에 표시하여 잘못된 입력을 구분합니다."""
            try:
                color = normalize_color(text)
            except ValueError:
                swatch.setText("?")
                swatch.setStyleSheet(
                    "background-color: #EEEEEE;"
                    "color: #333333;"
                    "border: 1px solid #888888;"
                )
                return

            swatch.clear()
            swatch.setStyleSheet(
                f"background-color: {color};"
                "border: 1px solid #888888;"
            )

        def choose_palette_color() -> None:
            """팔레트에서 확인한 색상만 반영하고 취소하면 유지합니다."""
            try:
                initial_color = normalize_color(color_edit.text())
            except ValueError:
                initial_color = "#FFFF00"

            selected = QColorDialog.getColor(
                QColor(initial_color),
                self,
                "색상 선택",
            )

            # 팔레트 취소는 잘못된 QColor를 반환하므로 값을 바꾸지 않습니다.
            if selected.isValid():
                color_edit.setText(selected.name().upper())

        palette_button.clicked.connect(choose_palette_color)
        color_edit.textChanged.connect(update_swatch)

        update_swatch(color_edit.text())

        return container

    def update_cursor_level_label(self, level: int | None = None) -> None:
        """선택 중인 단계와 실제 커서 이미지 크기를 표시합니다."""
        if level is None:
            level = self.cursor_level_slider.value()

        size = cursor_size_from_level(level)
        self.cursor_level_label.setText(
            f"{level}단계 · {size} × {size}px"
        )

    def load_fields(self, settings: HighlightSettings) -> None:
        """설정을 입력 필드에 표시하고 초기화 중 프리뷰를 막습니다."""
        self.loading = True

        try:
            self.enabled_checkbox.setChecked(settings.enabled)
            self.diameter_spinbox.setValue(settings.diameter)
            self.color_edit.setText(settings.color)
            self.opacity_spinbox.setValue(settings.opacity)
            self.style_combobox.setCurrentIndex(
                self.style_combobox.findData(settings.style)
            )
            self.line_width_spinbox.setValue(settings.line_width)
            self.line_width_spinbox.setEnabled(settings.style == "outline")
            self.click_enabled_checkbox.setChecked(settings.click_enabled)
            self.left_click_color_edit.setText(settings.left_click_color)
            self.right_click_color_edit.setText(settings.right_click_color)
            self.click_duration_spinbox.setValue(settings.click_duration_ms)
            self.click_style_combobox.setCurrentIndex(
                self.click_style_combobox.findData(settings.click_style)
            )
            self.click_line_width_spinbox.setValue(settings.click_line_width)
            self.click_line_width_spinbox.setEnabled(
                settings.click_style == "outline"
            )
            self.wheel_enabled_checkbox.setChecked(settings.wheel_enabled)            
            self.wheel_color_edit.setText(settings.wheel_color)
            self.wheel_duration_spinbox.setValue(settings.wheel_duration_ms)
            self.wheel_line_width_spinbox.setValue(settings.wheel_line_width)
            self.cursor_enabled_checkbox.setChecked(settings.cursor_enabled)
            self.cursor_level_slider.setValue(settings.cursor_level)
            self.cursor_level_slider.setEnabled(settings.cursor_enabled)
            self.update_cursor_level_label()            

            self.validation_label.clear()
        finally:
            self.loading = False

    def read_fields(self) -> HighlightSettings:
        """네 기능 탭의 입력값을 검증된 설정 객체로 반환합니다.

        HighlightSettings 생성 과정에서 타입·범위·색상을 검증합니다.
        유효하지 않은 입력은 ValueError로 호출부에 전달합니다.
        이 메서드는 실행 상태를 바꾸거나 설정 파일을 저장하지 않습니다.
        """
        return HighlightSettings(
            enabled=self.enabled_checkbox.isChecked(),
            diameter=self.diameter_spinbox.value(),
            color=self.color_edit.text(),
            opacity=self.opacity_spinbox.value(),
            style=self.style_combobox.currentData(),
            line_width=self.line_width_spinbox.value(),
            click_enabled=self.click_enabled_checkbox.isChecked(),
            left_click_color=self.left_click_color_edit.text(),
            right_click_color=self.right_click_color_edit.text(),
            click_duration_ms=self.click_duration_spinbox.value(),
            click_style=self.click_style_combobox.currentData(),
            click_line_width=self.click_line_width_spinbox.value(),
            wheel_enabled=self.wheel_enabled_checkbox.isChecked(),            
            wheel_color=self.wheel_color_edit.text(),
            wheel_duration_ms=self.wheel_duration_spinbox.value(),
            wheel_line_width=self.wheel_line_width_spinbox.value(),
            cursor_enabled=self.cursor_enabled_checkbox.isChecked(),
            cursor_level=self.cursor_level_slider.value(),            
        )

    def preview(self) -> None:
        """유효한 값은 프리뷰하고 잘못된 값은 화면에 안내합니다."""
        if self.loading:
            return

        self.update_cursor_level_label()

        self.line_width_spinbox.setEnabled(
            self.style_combobox.currentData() == "outline"
        )

        self.click_line_width_spinbox.setEnabled(
            self.click_style_combobox.currentData() == "outline"
        )        

        self.cursor_level_slider.setEnabled(
            self.cursor_enabled_checkbox.isChecked()
        )

        try:
            settings = self.read_fields()
        except ValueError as error:
            # 색상 입력 도중 매번 팝업을 띄우지 않습니다.
            # 마지막으로 유효했던 프리뷰 화면은 그대로 유지합니다.
            self.validation_label.setText(str(error))
            return

        self.validation_label.clear()
        self.preview_callback(settings)

    def reset_to_defaults(self) -> None:
        """모든 설정을 기본값으로 표시하고 저장 없이 프리뷰합니다.

        필드 변경 중에는 load_fields가 중간 프리뷰를 막습니다.
        전체 필드를 채운 뒤 한 번만 프리뷰하여 포인터 변경을 줄입니다.
        마지막 적용값은 유지하므로 취소·X·Esc로 복구할 수 있습니다.
        """
        defaults = HighlightSettings()
        self.load_fields(defaults)
        self.preview()        

    def apply_changes(self) -> bool:
        """입력 검증과 적용이 성공하면 취소 기준값을 갱신합니다.

        앱의 적용 콜백이 실행 상태 반영과 설정 파일 저장을 담당합니다.
        입력 검증 또는 적용이 실패하면 False를 반환하고,
        성공하면 마지막 적용값을 갱신한 뒤 True를 반환합니다.
        """
        try:
            settings = self.read_fields()
        except ValueError as error:
            QMessageBox.warning(self, "설정값 확인", str(error))
            return False

        # 적용 콜백이 실패하면 마지막 적용값을 유지합니다.
        # 실행 상태 반영과 저장이 성공한 뒤에만 취소 기준을 갱신합니다.
        if not self.apply_callback(settings):
            return False

        self.applied_settings = settings
        self.validation_label.clear()
        return True

    def accept(self) -> None:
        """확인 버튼은 적용 성공 시에만 창을 닫습니다."""
        if self.apply_changes():
            super().accept()

    def reject(self) -> None:
        """취소·Esc·창 닫기 시 마지막 적용값으로 복구합니다."""
        self.preview_callback(self.applied_settings)
        super().reject()

    def open_settings(self) -> None:
        """이미 열려 있으면 활성화하고, 새로 열 때 적용값을 표시합니다."""
        if not self.isVisible():
            self.load_fields(self.applied_settings)
            self.show()

        self.raise_()
        self.activateWindow()

    def stop(self) -> None:
        """프로그램 종료 시 reject()를 호출하여 설정 창을 닫습니다.

        reject()는 마지막 적용값으로 프리뷰 복구를 요청합니다.
        앱 종료 중에는 앱의 종료 플래그가 해당 요청을 차단하며,
        실제 시스템 커서 복원은 커서 컨트롤러의 종료 처리가 담당합니다.
        """
        self.reject()