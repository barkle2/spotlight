from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .config import ClickSettings, SpotlightSettings, WheelSettings


@dataclass
class Effect:
    kind: str
    position: QPointF
    started_at: float
    duration_ms: int
    start_diameter: float
    end_diameter: float
    color: QColor
    line_width: int

    def progress(self, now: float) -> float:
        return min(1.0, max(0.0, (now - self.started_at) * 1000 / self.duration_ms))

    def diameter(self, now: float) -> float:
        progress = self.progress(now)
        return self.start_diameter + (self.end_diameter - self.start_diameter) * progress

    def expired(self, now: float) -> bool:
        return self.progress(now) >= 1.0


class SpotlightOverlay(QWidget):
    def __init__(
        self,
        spotlight: SpotlightSettings,
        click: ClickSettings,
        wheel: WheelSettings,
    ) -> None:
        super().__init__()
        self.spotlight = spotlight
        self.click = click
        self.wheel = wheel
        self.pointer = QPoint()
        self.effects: list[Effect] = []
        self.total_effects = 0
        self.max_active_effects = 0
        self.effect_kind_counts: dict[str, int] = {}
        self.setWindowTitle("Spotlight Overlay")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._set_virtual_geometry()

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _set_virtual_geometry(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        virtual = QRect(screens[0].geometry())
        for screen in screens[1:]:
            virtual = virtual.united(screen.geometry())
        self.setGeometry(virtual)

    def start(self) -> None:
        self._track_pointer()
        self.show()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()
        self.effects.clear()
        self.hide()

    def apply_settings(
        self,
        spotlight: SpotlightSettings,
        click: ClickSettings,
        wheel: WheelSettings,
    ) -> None:
        self.spotlight = spotlight
        self.click = click
        self.wheel = wheel
        self.start()
        self.update()

    def _tick(self) -> None:
        self._track_pointer()
        if self.effects:
            now = time.monotonic()
            self.effects = [effect for effect in self.effects if not effect.expired(now)]
            self.update()

    def _track_pointer(self) -> None:
        global_position = QCursor.pos()
        local_position = global_position - self.geometry().topLeft()
        if local_position == self.pointer:
            return
        previous = QPoint(self.pointer)
        self.pointer = local_position
        radius = self.spotlight.diameter // 2 + self.spotlight.border_width + 4
        if previous.x() > -5000 and self.spotlight.enabled:
            self.update(QRect(previous.x() - radius, previous.y() - radius, radius * 2, radius * 2))
        if self.spotlight.enabled:
            self.update(QRect(self.pointer.x() - radius, self.pointer.y() - radius, radius * 2, radius * 2))

    def _local_event_position(self, x: int, y: int) -> QPointF:
        origin = self.geometry().topLeft()
        return QPointF(x - origin.x(), y - origin.y())

    def _append_effect(self, effect: Effect) -> None:
        self.effects.append(effect)
        if len(self.effects) > 3:
            self.effects = self.effects[-3:]
        self.total_effects += 1
        self.effect_kind_counts[effect.kind] = self.effect_kind_counts.get(effect.kind, 0) + 1
        self.max_active_effects = max(self.max_active_effects, len(self.effects))
        self.update()

    def add_click(self, x: int, y: int, button: str) -> None:
        if not self.click.enabled or button not in {"left", "right"}:
            return
        color = QColor(
            self.click.left_color if button == "left" else self.click.right_color
        )
        color.setAlpha(255)
        self._append_effect(
            Effect(
                kind=f"click-{button}",
                position=self._local_event_position(x, y),
                started_at=time.monotonic(),
                duration_ms=self.click.duration_ms,
                start_diameter=self.spotlight.diameter * 0.65,
                end_diameter=self.spotlight.diameter,
                color=color,
                line_width=5,
            )
        )

    def add_wheel(self, x: int, y: int, delta: int) -> None:
        if not self.wheel.enabled or delta == 0:
            return
        outward = delta > 0
        outer_diameter = self.spotlight.diameter
        inner_diameter = max(1, round(outer_diameter * 0.25))
        color = QColor(self.wheel.color)
        color.setAlpha(255)
        self._append_effect(
            Effect(
                kind="wheel-out" if outward else "wheel-in",
                position=self._local_event_position(x, y),
                started_at=time.monotonic(),
                duration_ms=self.wheel.duration_ms,
                start_diameter=(
                    inner_diameter if outward else outer_diameter
                ),
                end_diameter=(
                    outer_diameter if outward else inner_diameter
                ),
                color=color,
                line_width=self.wheel.line_width,
            )
        )

    @staticmethod
    def _circle_rect(position: QPointF, diameter: float) -> QRectF:
        radius = diameter / 2
        return QRectF(
            QPointF(position.x() - radius, position.y() - radius),
            QPointF(position.x() + radius, position.y() + radius),
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.spotlight.enabled:
            color = QColor(self.spotlight.color)
            color.setAlpha(round(255 * self.spotlight.opacity / 100))
            if self.spotlight.style == "outline":
                painter.setPen(QPen(color, self.spotlight.border_width))
                painter.setBrush(Qt.NoBrush)
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
            painter.drawEllipse(
                self._circle_rect(QPointF(self.pointer), self.spotlight.diameter)
            )

        now = time.monotonic()
        painter.setBrush(Qt.NoBrush)
        for effect in self.effects:
            painter.setPen(QPen(effect.color, effect.line_width))
            painter.drawEllipse(
                self._circle_rect(effect.position, effect.diameter(now))
            )
