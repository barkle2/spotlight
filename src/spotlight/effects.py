"""클릭·휠 효과의 표시 위치·애니메이션·수명을 관리합니다.

효과는 입력이 발생한 Qt 전역 논리 좌표에 고정됩니다.
클릭은 채움 또는 테두리로, 휠은 확대·축소하는 테두리로 표시합니다.
관리자는 두 종류를 합하여 최대 3개까지 유지하며,
한도를 넘으면 가장 오래된 효과를 먼저 정리합니다.
"""

from PySide6.QtCore import (
    QObject, QPoint, QRectF, Qt, QTimer, Signal, QElapsedTimer
)
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from .config import (
    MAX_DIAMETER,
    MIN_DIAMETER,
    normalize_color,
    validate_integer,
    MIN_LINE_WIDTH,
    MAX_LINE_WIDTH,
)


MAX_EFFECTS = 3
DEFAULT_DURATION_MS = 180
DEFAULT_LEFT_COLOR = "#00AAFF"
DEFAULT_RIGHT_COLOR = "#FF6600"


class ClickEffectWindow(QWidget):
    """입력 위치에 고정된 채움 또는 테두리 효과 창입니다.

    배경은 투명하고 원의 색상은 불투명하게 표시합니다.
    마우스 입력과 포커스를 받지 않으며, 만료 시 관리자에게 알립니다.
    표시 중에는 생성 당시의 위치와 설정값을 유지합니다.
    """

    expired = Signal(object)

    def __init__(
        self,
        position: QPoint,
        diameter: int,
        color: str,
        duration_ms: int,
        style: str = "fill",
        line_width: int = 3,
    ) -> None:
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

        self.diameter = diameter
        # 생성 당시 값을 보관하여 표시 중 설정이 바뀌어도 유지합니다.
        self.style = style
        self.line_width = line_width
        self.padding = 2
        self.color = QColor(color)
        self.color.setAlpha(255)

        window_size = diameter + self.padding * 2
        self.setFixedSize(window_size, window_size)

        # 생성 시 받은 Qt 전역 좌표로 위치를 고정합니다.
        # 이후 커서가 움직여도 이 창의 위치는 갱신하지 않습니다.
        self.move(
            position.x() - window_size // 2,
            position.y() - window_size // 2,
        )

        self.expiration_timer = QTimer(self)
        self.expiration_timer.setSingleShot(True)
        self.expiration_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.expiration_timer.setInterval(duration_ms)
        self.expiration_timer.timeout.connect(self.notify_expiration)

    def start(self) -> None:
        """효과를 표시하고 만료 타이머를 시작합니다."""
        self.show()
        self.expiration_timer.start()

    def notify_expiration(self) -> None:
        """관리자에게 만료를 알려 목록과 창을 함께 정리하게 합니다."""
        self.expired.emit(self)

    def stop(self) -> None:
        """타이머를 중지하고 효과 창을 닫습니다."""
        self.expiration_timer.stop()
        self.close()

    def paintEvent(self, event: QPaintEvent) -> None:
        """채움 또는 내부가 투명한 테두리 원을 그립니다."""
        painter = QPainter(self)

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rectangle = QRectF(
                self.padding,
                self.padding,
                self.diameter,
                self.diameter,
            )

            if self.style == "fill":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.color)
            else:
                pen = QPen(self.color)
                pen.setWidthF(self.line_width)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

                # 선은 경로 양쪽으로 그려집니다.
                # 경로를 반두께만큼 안쪽으로 줄여 바깥 지름을 유지합니다.
                inset = self.line_width / 2.0
                rectangle.adjust(inset, inset, -inset, -inset)

            painter.drawEllipse(rectangle)
        finally:
            painter.end()

class WheelEffectWindow(ClickEffectWindow):
    """입력 위치에 고정된 확대·축소 테두리 효과 창입니다.

    위 방향은 생성 당시 강조 원 지름의 50%에서 100%로 확대하고,
    아래 방향은 100%에서 50%로 축소합니다.
    화면 갱신 타이머와 만료 타이머를 각각 관리하며,
    테두리 바깥 지름은 생성 당시 강조 원 지름을 넘지 않습니다.
    """

    def __init__(
        self,
        position: QPoint,
        diameter: int,
        color: str,
        duration_ms: int,
        direction: str,
        line_width: int,
    ) -> None:
        # 휠 효과의 최대 지름을 강조 원 지름으로 제한합니다.
        maximum_diameter = diameter

        super().__init__(
            position=position,
            diameter=maximum_diameter,
            color=color,
            duration_ms=duration_ms,
            style="outline",
            line_width=line_width,
        )

        self.base_diameter = diameter
        self.duration_ms = duration_ms
        self.direction = direction
        self.elapsed_timer = QElapsedTimer()

        # 만료 타이머와 별도로 애니메이션 화면만 갱신합니다.
        self.repaint_timer = QTimer(self)
        self.repaint_timer.setInterval(16)
        self.repaint_timer.timeout.connect(self.update)

    def start(self) -> None:
        """경과시간 측정·화면 갱신·만료 처리를 시작합니다."""
        self.elapsed_timer.start()
        self.repaint_timer.start()
        super().start()

    def stop(self) -> None:
        """화면 갱신과 만료 타이머를 함께 정리합니다."""
        self.repaint_timer.stop()
        super().stop()

    def paintEvent(self, event: QPaintEvent) -> None:
        """생성 시 강조 원 범위 안에서 휠 테두리를 확대·축소합니다."""
        elapsed = (
            self.elapsed_timer.elapsed()
            if self.elapsed_timer.isValid()
            else 0
        )
        progress = min(1.0, max(0.0, elapsed / self.duration_ms))

        # 위: 50% → 100%, 아래: 100% → 50%.
        # 효과의 바깥 지름은 강조 원 지름을 넘지 않습니다.
        if self.direction == "up":
            scale = 0.5 + 0.5 * progress
        else:
            scale = 1.0 - 0.5 * progress

        current_diameter = self.base_diameter * scale

        # 아주 작은 원에서는 두꺼운 선 때문에 경로 크기가
        # 음수가 되지 않도록 현재 반지름 이하로 제한합니다.
        effective_line_width = min(
            float(self.line_width),
            current_diameter / 2.0,
        )

        rectangle = QRectF(
            (self.width() - current_diameter) / 2.0,
            (self.height() - current_diameter) / 2.0,
            current_diameter,
            current_diameter,
        )

        # 선의 바깥쪽도 계산한 지름 안에 들어오도록 보정합니다.
        inset = effective_line_width / 2.0
        rectangle.adjust(inset, inset, -inset, -inset)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            pen = QPen(self.color)
            pen.setWidthF(effective_line_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rectangle)
        finally:
            painter.end()

class ClickEffectManager(QObject):
    """클릭·휠 효과를 같은 목록에서 최대 3개까지 관리합니다.

    한도를 넘으면 가장 오래된 효과를 제거합니다.
    만료·시작 실패·프로그램 종료 시 타이머와 창을 정리하고,
    창 객체의 삭제는 Qt 이벤트 처리에 맡깁니다.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.running = False
        self.effects: list[ClickEffectWindow] = []

    def start(self) -> None:
        """새 클릭·휠 효과를 생성할 수 있는 상태로 전환합니다."""
        self.running = True

    def show_click(
        self,
        button: str,
        position: QPoint,
        diameter: int = 120,
        color: str | None = None,
        duration_ms: int = DEFAULT_DURATION_MS,
        style: str = "fill",
        line_width: int = 3,
    ) -> None:
        """좌우 버튼과 Qt 전역 좌표에 따라 고정 효과를 생성합니다."""
        if not self.running:
            return

        if button not in ("left", "right"):
            raise ValueError("버튼은 left 또는 right여야 합니다.")

        if not isinstance(position, QPoint):
            raise TypeError("클릭 위치는 QPoint여야 합니다.")

        validate_integer(
            "클릭 효과 지름", diameter, MIN_DIAMETER, MAX_DIAMETER
        )
        validate_integer("클릭 효과 시간", duration_ms, 50, 2000)

        if style not in ("fill", "outline"):
            raise ValueError("클릭 표시 방식은 fill 또는 outline이어야 합니다.")

        validate_integer(
            "클릭 선 두께", line_width, MIN_LINE_WIDTH, MAX_LINE_WIDTH
        )

        if color is None:
            color = (
                DEFAULT_LEFT_COLOR
                if button == "left"
                else DEFAULT_RIGHT_COLOR
            )

        color = normalize_color(color)
        
        effect = ClickEffectWindow(
            position=QPoint(position),
            diameter=diameter,
            color=color,
            duration_ms=duration_ms,
            style=style,
            line_width=line_width,
        )
        
        self._add_effect(effect)

    def show_wheel(
        self,
        delta: int,
        position: QPoint,
        diameter: int = 120,
        color: str = "#00CC66",
        duration_ms: int = 250,
        line_width: int = 3,
    ) -> None:
        """휠 방향에 따른 고정 위치 애니메이션을 생성합니다."""
        if not self.running:
            return

        if type(delta) is not int:
            raise ValueError("휠 입력량은 정수여야 합니다.")

        if delta == 0:
            return

        if not isinstance(position, QPoint):
            raise TypeError("휠 위치는 QPoint여야 합니다.")

        validate_integer(
            "휠 효과 지름", diameter, MIN_DIAMETER, MAX_DIAMETER
        )
        validate_integer("휠 효과 시간", duration_ms, 50, 2000)
        validate_integer(
            "휠 선 두께", line_width, MIN_LINE_WIDTH, MAX_LINE_WIDTH
        )

        effect = WheelEffectWindow(
            position=QPoint(position),
            diameter=diameter,
            color=normalize_color(color),
            duration_ms=duration_ms,
            direction="up" if delta > 0 else "down",
            line_width=line_width,
        )
        self._add_effect(effect)

    def _add_effect(self, effect: ClickEffectWindow) -> None:
        """효과를 공통 목록에 등록하고 표시를 시작합니다.

        한도에 도달하면 가장 오래된 효과를 먼저 제거합니다.
        표시 시작이 실패하면 새 효과도 정리하고 예외를 전달합니다.
        """
        effect.expired.connect(self.remove_effect)

        if len(self.effects) >= MAX_EFFECTS:
            self.remove_effect(self.effects[0])

        self.effects.append(effect)

        try:
            effect.start()
        except Exception:
            self.remove_effect(effect)
            raise

    def remove_effect(self, effect: ClickEffectWindow) -> None:
        """관리 중인 효과를 목록에서 빼고 타이머·창을 정리합니다."""
        if effect not in self.effects:
            return

        self.effects.remove(effect)
        effect.stop()

        # Qt 이벤트 처리 중 안전한 시점에 창 객체를 삭제합니다.
        effect.deleteLater()

    def stop(self) -> None:
        """새 효과를 막고 표시 중인 모든 효과를 정리합니다."""
        self.running = False

        # 제거 과정에서 목록이 바뀌므로 복사한 목록을 순회합니다.
        for effect in list(self.effects):
            self.remove_effect(effect)