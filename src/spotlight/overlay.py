"""설정값에 따라 마우스 포인터 주변의 강조 원을 표시합니다."""

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from .config import HighlightSettings


class SpotlightOverlay(QWidget):
    """입력을 방해하지 않는 설정 가능한 강조 창입니다."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 실행 여부와 설정의 활성화 여부를 구분합니다.
        # 설정 변경만으로 종료된 창이 다시 나타나지 않도록 합니다.
        self.running = False
        self.padding = 2

        self.position_timer = QTimer(self)
        self.position_timer.setInterval(16)
        self.position_timer.timeout.connect(self.update_position)

        # 기본 설정으로 초기화하고, 앱에서 읽은 설정은 별도로 반영합니다.
        self.apply_settings(HighlightSettings())

    def apply_settings(self, settings: HighlightSettings) -> None:
        """검증된 설정을 반영하고 실행 중이면 표시 상태를 갱신합니다."""
        if not isinstance(settings, HighlightSettings):
            raise TypeError("HighlightSettings 객체가 필요합니다.")

        self.settings = settings

        window_size = settings.diameter + self.padding * 2
        self.setFixedSize(window_size, window_size)

        self.highlight_color = QColor(settings.color)
        self.highlight_color.setAlphaF(settings.opacity / 100.0)

        self.update_position()
        self.update()

        if self.running:
            self.refresh_visibility()

    def refresh_visibility(self) -> None:
        """실행·활성화 상태에 맞춰 창과 추적 타이머를 조절합니다."""
        if self.running and self.settings.enabled:
            self.update_position()
            self.show()
            self.position_timer.start()
        else:
            # 비활성화 상태에서는 위치 추적도 중지합니다.
            self.position_timer.stop()
            self.hide()

    def start(self) -> None:
        """강조 기능을 시작합니다."""
        self.running = True
        self.refresh_visibility()

    def stop(self) -> None:
        """위치 추적을 중지하고 강조 창을 닫습니다."""
        self.running = False
        self.position_timer.stop()
        self.close()

    def update_position(self) -> None:
        """강조 원 중심을 커서의 Qt 전역 논리 좌표에 맞춥니다."""
        cursor_position = QCursor.pos()

        target_x = cursor_position.x() - self.width() // 2
        target_y = cursor_position.y() - self.height() // 2

        if self.x() != target_x or self.y() != target_y:
            self.move(target_x, target_y)

    def paintEvent(self, event: QPaintEvent) -> None:
        """설정에 따라 채워진 원 또는 테두리 원을 그립니다."""
        painter = QPainter(self)

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rectangle = QRectF(
                self.padding,
                self.padding,
                self.settings.diameter,
                self.settings.diameter,
            )

            if self.settings.style == "fill":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.highlight_color)
            else:
                pen = QPen(self.highlight_color)
                pen.setWidthF(self.settings.line_width)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

                # 선은 경로 양쪽으로 그려지므로 두께의 절반만큼
                # 경로를 안쪽으로 줄여 원의 바깥 지름을 유지합니다.
                inset = self.settings.line_width / 2.0
                rectangle.adjust(inset, inset, -inset, -inset)

            painter.drawEllipse(rectangle)
        finally:
            painter.end()