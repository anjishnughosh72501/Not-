"""
ui/toast.py - Lightweight, non-blocking in-app notification toasts and snackbars.
"""

from __future__ import annotations
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QColor, QFont

from ui.design import get_tokens


class ToastNotification(QWidget):
    """Clean, non-modal notification banner that auto-dismisses with optional undo action."""
    def __init__(
        self,
        title: str,
        message: str,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        duration_ms: int = 2500,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)

        tokens = get_tokens()

        # Container
        self.container = QWidget(self)
        self.container.setObjectName("ToastContainer")
        self.container.setStyleSheet(f"""
            QWidget#ToastContainer {{
                background-color: {tokens["surface_overlay"]};
                border: 1px solid {tokens["border"]};
                border-radius: 10px;
            }}
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Text column
        col = QVBoxLayout()
        col.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {tokens['accent']}; font-weight: 600; font-size: 13px;")
        col.addWidget(lbl_title)

        if message:
            lbl_msg = QLabel(message)
            lbl_msg.setStyleSheet(f"color: {tokens['text_muted']}; font-size: 12px;")
            col.addWidget(lbl_msg)

        layout.addLayout(col)

        # Action button (e.g. "Undo", "Open", "Copy")
        if action_text and action_callback:
            btn_act = QPushButton(action_text)
            btn_act.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tokens['accent_subtle']};
                    color: {tokens['accent']};
                    border: 1px solid {tokens['accent']};
                    font-weight: 600;
                    padding: 5px 10px;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {tokens['accent']};
                    color: #FFFFFF;
                }}
            """)
            btn_act.clicked.connect(lambda: [action_callback(), self.close()])
            layout.addWidget(btn_act)

        # Main wrapper layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(self.container)

        self.adjustSize()

        # Auto-dismiss timer
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.close)

    def show_at_corner(self, position: str = "bottom-right", margin: int = 24):
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()

        w = self.width()
        h = self.height()

        if position == "top-right":
            x = screen.right() - w - margin
            y = screen.top() + margin
        elif position == "top-left":
            x = screen.left() + margin
            y = screen.top() + margin
        elif position == "bottom-left":
            x = screen.left() + margin
            y = screen.bottom() - h - margin
        else: # bottom-right
            x = screen.right() - w - margin
            y = screen.bottom() - h - margin

        self.move(x, y)
        self.show()


_active_toasts = []

def show_app_toast(
    title: str,
    message: str = "",
    action_text: Optional[str] = None,
    action_callback: Optional[Callable[[], None]] = None,
    position: str = "bottom-right",
    duration_ms: int = 2500
) -> ToastNotification:
    """Helper to instantiate and display non-blocking toast."""
    toast = ToastNotification(
        title=title,
        message=message,
        action_text=action_text,
        action_callback=action_callback,
        duration_ms=duration_ms
    )
    toast.show_at_corner(position=position)
    _active_toasts.append(toast)
    QTimer.singleShot(duration_ms + 500, lambda: _active_toasts.remove(toast) if toast in _active_toasts else None)
    return toast
