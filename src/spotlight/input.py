from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from pynput import mouse


class GlobalMouseInput(QObject):
    clicked = Signal(int, int, str)
    scrolled = Signal(int, int, int)

    def __init__(self) -> None:
        super().__init__()
        self.listener: mouse.Listener | None = None
        self.started = False

    def start(self) -> None:
        if self.started:
            return
        self.listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self.listener.start()
        self.started = True

    def stop(self) -> bool:
        if self.listener is None:
            self.started = False
            return True
        listener = self.listener
        listener.stop()
        listener.join(timeout=1.0)
        stopped = not listener.is_alive()
        self.listener = None
        self.started = False
        return stopped

    def _on_click(self, x: int, y: int, button, pressed: bool) -> None:
        if not pressed:
            return
        if button == mouse.Button.left:
            self.clicked.emit(round(x), round(y), "left")
        elif button == mouse.Button.right:
            self.clicked.emit(round(x), round(y), "right")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if dy:
            self.scrolled.emit(round(x), round(y), int(dy))

