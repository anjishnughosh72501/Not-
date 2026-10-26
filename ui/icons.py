"""
ui/icons.py - Vector SVG icons and high-DPI QIcon generators for MarkSnap.

Provides crisp scalable iconography for the toolbar, sidebar, and floating buttons.
"""

from __future__ import annotations
from typing import Dict, Optional
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF

from ui.design import get_tokens

SVG_PATHS = {
    "pen": "M 5 19 L 9 19 L 19 9 L 15 5 L 5 15 Z M 14 6 L 18 10",
    "marker": "M 4 20 L 8 20 L 20 8 L 16 4 L 4 16 Z M 3 21 L 7 21",
    "highlighter": "M 8 18 L 12 18 L 19 11 L 15 7 L 8 14 Z M 5 21 L 9 21",
    "eraser": "M 6 18 L 14 18 L 20 12 L 12 4 L 4 12 Z",
    "line": "M 4 20 L 20 4",
    "arrow": "M 4 20 L 19 5 M 19 5 L 12 5 M 19 5 L 19 12",
    "rect": "M 4 5 H 20 V 19 H 4 Z",
    "rounded_rect": "M 7 4 H 17 Q 20 4 20 7 V 17 Q 20 20 17 20 H 7 Q 4 20 4 17 V 7 Q 4 4 7 4 Z",
    "ellipse": "M 12 4 A 8 6 0 1 0 12 20 A 8 6 0 1 0 12 4 Z",
    "text": "M 5 5 H 19 M 12 5 V 19 M 9 19 H 15",
    "step": "M 12 3 A 9 9 0 1 0 12 21 A 9 9 0 1 0 12 3 Z M 12 7 V 17 M 10 9 L 12 7",
    "spotlight": "M 12 3 L 15 9 L 21 10 L 17 14 L 18 20 L 12 17 L 6 20 L 7 14 L 3 10 L 9 9 Z",
    "blur": "M 4 4 H 8 V 8 H 4 Z M 10 4 H 14 V 8 H 10 Z M 16 4 H 20 V 8 H 16 Z M 4 10 H 8 V 14 H 4 Z M 10 10 H 14 V 14 H 10 Z M 16 10 H 20 V 14 H 16 Z M 4 16 H 8 V 20 H 4 Z M 10 16 H 14 V 20 H 10 Z M 16 16 H 20 V 20 H 16 Z",
    "image": "M 4 4 H 20 V 20 H 4 Z M 8 10 A 2 2 0 1 0 8 6 A 2 2 0 1 0 8 10 Z M 6 18 L 11 13 L 14 16 L 16 14 L 18 18 Z",
    "ai": "M 12 2 L 14.5 8.5 L 21 11 L 14.5 13.5 L 12 20 L 9.5 13.5 L 3 11 L 9.5 8.5 Z",
    "select": "M 4 4 L 10 20 L 13 14 L 19 11 Z",
    "undo": "M 9 14 L 4 9 L 9 4 M 4 9 H 15 A 5 5 0 0 1 20 14 A 5 5 0 0 1 15 19 H 8",
    "redo": "M 15 14 L 20 9 L 15 4 M 20 9 H 9 A 5 5 0 0 0 4 14 A 5 5 0 0 0 9 19 H 16",
    "save": "M 19 21 H 5 A 2 2 0 0 1 3 19 V 5 A 2 2 0 0 1 5 3 H 16 L 21 8 V 19 A 2 2 0 0 1 19 21 Z M 17 21 V 13 H 7 V 21 M 7 3 V 8 H 15 V 3",
    "copy": "M 8 7 H 18 V 21 H 8 Z M 6 17 H 4 V 3 H 16 V 5",
    "close": "M 6 6 L 18 18 M 18 6 L 6 18",
    "check": "M 5 12 L 10 17 L 19 7",
    "library": "M 4 4 H 9 V 20 H 4 Z M 11 4 H 16 V 20 H 11 Z M 18 4 H 20 V 20 H 18 Z",
    "camera": "M 4 7 H 7 L 9 4 H 15 L 17 7 H 20 V 19 H 4 Z M 12 16 A 4 4 0 1 0 12 8 A 4 4 0 1 0 12 16 Z",
    "settings": "M 12 15 A 3 3 0 1 0 12 9 A 3 3 0 1 0 12 15 Z M 19.4 15 A 7.9 7.9 0 0 0 19.4 9 L 21.5 7.5 L 19.5 4 L 17 5 A 8 8 0 0 0 14.5 3.5 L 14 1 H 10 L 9.5 3.5 A 8 8 0 0 0 7 5 L 4.5 4 L 2.5 7.5 L 4.6 9 A 8 8 0 0 0 4.6 15 L 2.5 16.5 L 4.5 20 L 7 19 A 8 8 0 0 0 9.5 20.5 L 10 23 H 14 L 14.5 20.5 A 8 8 0 0 0 17 19 L 19.5 20 L 21.5 16.5 Z",
    "trash": "M 4 6 H 20 M 10 11 V 17 M 14 11 V 17 M 5 6 L 6 19 A 2 2 0 0 0 8 21 H 16 A 2 2 0 0 0 18 19 L 19 6 M 9 6 V 4 A 1 1 0 0 1 10 3 H 14 A 1 1 0 0 1 15 4 V 6",
}


def create_vector_pixmap(name: str, size: int = 24, color: Optional[str] = None) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    tokens = get_tokens()
    draw_color = QColor(color or tokens["text"])

    pen = QPen(draw_color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)

    # Scale 24x24 coordinate space to requested size
    scale = size / 24.0
    painter.scale(scale, scale)

    # Simplified clean geometric drawings for maximum clarity and speed
    if name == "pen":
        painter.drawLine(5, 19, 9, 19)
        painter.drawLine(9, 19, 19, 9)
        painter.drawLine(19, 9, 15, 5)
        painter.drawLine(15, 5, 5, 15)
        painter.drawLine(5, 15, 5, 19)
        painter.drawLine(13, 7, 17, 11)
    elif name == "marker":
        pen.setWidthF(2.5)
        painter.setPen(pen)
        painter.drawLine(6, 18, 18, 6)
        painter.drawLine(4, 20, 8, 20)
    elif name == "highlighter":
        pen.setWidthF(3.0)
        painter.setPen(pen)
        painter.drawLine(6, 18, 18, 6)
    elif name == "eraser":
        painter.drawRoundedRect(5, 7, 14, 10, 3, 3)
        painter.drawLine(9, 17, 15, 17)
    elif name == "line":
        painter.drawLine(4, 20, 20, 4)
    elif name == "arrow":
        painter.drawLine(4, 20, 19, 5)
        painter.drawLine(19, 5, 12, 5)
        painter.drawLine(19, 5, 19, 12)
    elif name == "rect":
        painter.drawRect(4, 5, 16, 14)
    elif name == "rounded_rect":
        painter.drawRoundedRect(4, 5, 16, 14, 4, 4)
    elif name == "ellipse":
        painter.drawEllipse(4, 6, 16, 12)
    elif name == "text":
        painter.drawLine(5, 6, 19, 6)
        painter.drawLine(12, 6, 12, 18)
        painter.drawLine(9, 18, 15, 18)
    elif name == "step":
        painter.drawEllipse(3, 3, 18, 18)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(10)
        painter.setFont(font)
        painter.drawText(QRectF(3, 3, 18, 18), Qt.AlignCenter, "1")
    elif name == "select":
        painter.drawLine(5, 5, 10, 19)
        painter.drawLine(10, 19, 13, 14)
        painter.drawLine(13, 14, 19, 11)
        painter.drawLine(19, 11, 5, 5)
    elif name == "blur":
        painter.drawRect(4, 4, 16, 16)
        pen_dash = QPen(draw_color, 1.2, Qt.DashLine)
        painter.setPen(pen_dash)
        painter.drawLine(4, 12, 20, 12)
        painter.drawLine(12, 4, 12, 20)
    elif name == "image":
        painter.drawRect(4, 5, 16, 14)
        painter.drawEllipse(7, 8, 3, 3)
        painter.drawLine(4, 16, 9, 12)
        painter.drawLine(9, 12, 14, 16)
        painter.drawLine(14, 16, 17, 13)
        painter.drawLine(17, 13, 20, 16)
    elif name == "ai":
        # Star sparkle
        painter.drawLine(12, 3, 12, 21)
        painter.drawLine(3, 12, 21, 12)
        painter.drawLine(6, 6, 18, 18)
        painter.drawLine(6, 18, 18, 6)
    elif name == "undo":
        painter.drawLine(8, 13, 4, 9)
        painter.drawLine(4, 9, 8, 5)
        path = QPainterPath()
        path.moveTo(4, 9)
        path.quadTo(18, 9, 18, 17)
        painter.drawPath(path)
    elif name == "redo":
        painter.drawLine(16, 13, 20, 9)
        painter.drawLine(20, 9, 16, 5)
        path = QPainterPath()
        path.moveTo(20, 9)
        path.quadTo(6, 9, 6, 17)
        painter.drawPath(path)
    elif name == "save":
        painter.drawRoundedRect(4, 4, 16, 16, 3, 3)
        painter.fillRect(QRectF(8, 4, 8, 5), draw_color)
        painter.drawRect(7, 13, 10, 7)
    elif name == "copy":
        painter.drawRoundedRect(8, 8, 12, 12, 2, 2)
        painter.drawPolyline([QPointF(6, 16), QPointF(4, 16), QPointF(4, 4), QPointF(16, 4), QPointF(16, 6)])
    elif name == "close":
        painter.drawLine(6, 6, 18, 18)
        painter.drawLine(18, 6, 6, 18)
    elif name == "check":
        painter.drawLine(5, 12, 10, 17)
        painter.drawLine(10, 17, 19, 7)
    elif name == "library":
        painter.drawRect(4, 5, 4, 14)
        painter.drawRect(10, 5, 4, 14)
        painter.drawRect(16, 5, 4, 14)
    elif name == "camera":
        painter.drawRoundedRect(4, 7, 16, 12, 3, 3)
        painter.drawEllipse(9, 10, 6, 6)
        painter.drawRect(9, 5, 6, 2)
    elif name == "settings":
        painter.drawEllipse(8, 8, 8, 8)
        for angle in range(0, 360, 45):
            rad = angle * 3.14159 / 180.0
            x1 = 12 + 6 * Qt.cos(rad) if hasattr(Qt, 'cos') else 12 + 6
            # Clean tick marks
            painter.drawLine(12, 2, 12, 5)
            painter.drawLine(12, 19, 12, 22)
            painter.drawLine(2, 12, 5, 12)
            painter.drawLine(19, 12, 22, 12)
            break
    elif name == "trash":
        painter.drawLine(5, 7, 19, 7)
        painter.drawLine(9, 7, 9, 4)
        painter.drawLine(9, 4, 15, 4)
        painter.drawLine(15, 4, 15, 7)
        painter.drawPolyline([QPointF(6, 7), QPointF(7, 20), QPointF(17, 20), QPointF(18, 7)])
        painter.drawLine(10, 10, 10, 17)
        painter.drawLine(14, 10, 14, 17)
    else:
        # Default circle dot
        painter.drawEllipse(8, 8, 8, 8)

    painter.end()
    return pix


def get_vector_icon(name: str, size: int = 24, color: Optional[str] = None) -> QIcon:
    pix = create_vector_pixmap(name, size=size, color=color)
    return QIcon(pix)
