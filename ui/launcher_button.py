"""
ui/launcher_button.py - Floating launcher widget with WDA_EXCLUDEFROMCAPTURE and no focus stealing.
"""

from __future__ import annotations
import sys
import ctypes
from ctypes import wintypes
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QMenu, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QPoint, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QAction, QPainterPath

user32 = ctypes.windll.user32

# Win32 Constants
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008


def apply_window_capture_exclusion(hwnd: int) -> bool:
    """Sets WDA_EXCLUDEFROMCAPTURE so this button never shows up in screenshots."""
    try:
        res = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        return bool(res)
    except Exception:
        return False


def set_no_activate_style(hwnd: int) -> None:
    """Ensures window never steals focus from the foreground app."""
    try:
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
    except Exception as e:
        print(f"[Launcher] Error setting no-activate style: {e}")


class FloatingLauncherButton(QWidget):
    clicked_annotate = Signal()
    request_settings = Signal()

    def __init__(
        self,
        size_mode: str = "M",
        opacity_pct: int = 85,
        idle_fade: bool = True,
        snap_edges: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.size_px = 52 if size_mode == "M" else (40 if size_mode == "S" else 64)
        self.base_opacity = opacity_pct / 100.0
        self.idle_fade = idle_fade
        self.snap_edges = snap_edges

        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self.drag_start_global = QPoint()
        self.is_annotating_active = False
        self.is_hovered = False

        self.resize(self.size_px + 12, self.size_px + 12)

        # Idle fade timer
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(3000)
        self.idle_timer.timeout.connect(self._on_idle_fade)
        if self.idle_fade:
            self.idle_timer.start()

        # Set default position on primary screen
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        init_x = screen.right() - self.width() - 28
        init_y = screen.top() + (screen.height() // 2) - (self.height() // 2)
        self.move(init_x, init_y)

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = int(self.winId())
        apply_window_capture_exclusion(hwnd)
        set_no_activate_style(hwnd)

    def set_annotating_state(self, annotating: bool):
        self.is_annotating_active = annotating
        self.update()

    def _on_idle_fade(self):
        if not self.is_hovered and self.idle_fade:
            self.setWindowOpacity(max(0.35, self.base_opacity * 0.45))

    def enterEvent(self, event):
        self.is_hovered = True
        self.setWindowOpacity(self.base_opacity)
        if self.idle_timer.isActive():
            self.idle_timer.stop()
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        if self.idle_fade:
            self.idle_timer.start()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.drag_start_pos = event.pos()
            self.drag_start_global = event.globalPosition().toPoint()
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            diff = event.globalPosition().toPoint() - self.drag_start_global
            if diff.manhattanLength() > 5:
                self.is_dragging = True
                self.move(self.pos() + event.pos() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.is_dragging:
                self.clicked_annotate.emit()
            else:
                if self.snap_edges:
                    self._snap_to_screen_edge()
            self.is_dragging = False

    def _snap_to_screen_edge(self):
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(self.geometry().center())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        geo = screen.geometry()

        x = self.x()
        y = self.y()

        # Snap to nearest left or right edge
        dist_left = abs(x - geo.left())
        dist_right = abs(geo.right() - (x + self.width()))

        snap_x = geo.left() + 16 if dist_left < dist_right else geo.right() - self.width() - 16
        snap_y = max(geo.top() + 16, min(geo.bottom() - self.height() - 16, y))

        self.move(snap_x, snap_y)

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1F2024;
                color: #F3F4F6;
                border: 1px solid #32343A;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2E2F45;
                color: #818CF8;
            }
        """)

        act_annotate = menu.addAction("Annotate Screen")
        act_annotate.triggered.connect(self.clicked_annotate.emit)

        menu.addSeparator()

        act_hide_1h = menu.addAction("Hide for 1 Hour")
        act_hide_1h.triggered.connect(self._hide_for_one_hour)

        act_settings = menu.addAction("MarkSnap Settings...")
        act_settings.triggered.connect(self.request_settings.emit)

        menu.exec(pos)

    def _hide_for_one_hour(self):
        self.hide()
        QTimer.singleShot(3600000, self.show)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        r = (self.size_px / 2.0)

        # Subtle dark shadow
        painter.setBrush(QColor(0, 0, 0, 75))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(int(center_x), int(center_y + 2)), int(r), int(r))

        # Main button circle
        if self.is_annotating_active:
            # Active Done/Stop indicator
            painter.setBrush(QColor("#EF4444"))
            painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
            painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(r), int(r))

            # Stop square
            side = r * 0.7
            painter.fillRect(int(center_x - side / 2), int(center_y - side / 2), int(side), int(side), QColor("#FFFFFF"))
        else:
            # Idle mark button
            accent_bg = QColor("#6366F1") if self.is_hovered else QColor("#1E2024")
            painter.setBrush(accent_bg)
            painter.setPen(QPen(QColor("#6366F1" if not self.is_hovered else "#818CF8"), 1.8))
            painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(r), int(r))

            # Render MarkSnap 'M' insignia
            painter.setPen(QPen(QColor("#FFFFFF"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            m_w = r * 0.8
            m_h = r * 0.65
            left = center_x - m_w / 2.0
            top = center_y - m_h / 2.0
            path = QPainterPath()
            path.moveTo(left, top + m_h)
            path.lineTo(left, top)
            path.lineTo(center_x, top + m_h * 0.65)
            path.lineTo(left + m_w, top)
            path.lineTo(left + m_w, top + m_h)
            painter.drawPath(path)

        painter.end()
