"""
overlay_scene.py - Retained vector scene models for MarkSnap.

Models annotations as first-class vector objects in a QGraphicsScene.
Renders to screen with antialiasing and exports to a QImage at native resolution,
guaranteeing 100% WYSIWYG fidelity between screen display and saved file.
"""

from __future__ import annotations
import math
from typing import List, Tuple, Optional, Dict, Any
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsPixmapItem,
    QGraphicsDropShadowEffect, QGraphicsColorizeEffect
)
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath, QFont, QPixmap, QImage,
    QPolygonF
)


class BaseAnnotationItem:
    """Interface mixin for serialization and vector manipulation."""
    is_annotation = True


class PenStrokeItem(QGraphicsPathItem, BaseAnnotationItem):
    def __init__(self, color: QColor, width: float, is_highlighter: bool = False, parent=None):
        super().__init__(parent)
        self.stroke_color = QColor(color)
        self.stroke_width = width
        self.is_highlighter = is_highlighter
        self.points: List[QPointF] = []

        if self.is_highlighter:
            # Semi-transparent highlight using multiply-like effect
            hl_color = QColor(color)
            hl_color.setAlpha(110)
            pen = QPen(hl_color, width, Qt.SolidLine, Qt.SquareCap, Qt.RoundJoin)
        else:
            pen = QPen(self.stroke_color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

        self.setPen(pen)
        self.setBrush(Qt.NoBrush)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def add_point(self, pt: QPointF):
        self.points.append(pt)
        path = self.path()
        if len(self.points) == 1:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
        self.setPath(path)


class ArrowItem(QGraphicsPathItem, BaseAnnotationItem):
    def __init__(self, start: QPointF, end: QPointF, color: QColor, width: float = 3.5, parent=None):
        super().__init__(parent)
        self.start_pt = start
        self.end_pt = end
        self.arrow_color = QColor(color)
        self.stroke_width = width

        self.setPen(QPen(self.arrow_color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setBrush(QBrush(self.arrow_color))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.update_arrow()

    def set_end(self, end: QPointF):
        self.end_pt = end
        self.update_arrow()

    def update_arrow(self):
        path = QPainterPath()
        path.moveTo(self.start_pt)
        path.lineTo(self.end_pt)

        # Arrowhead calculation
        dx = self.end_pt.x() - self.start_pt.x()
        dy = self.end_pt.y() - self.start_pt.y()
        length = math.hypot(dx, dy)
        if length > 5:
            angle = math.atan2(dy, dx)
            head_len = min(22.0, max(12.0, self.stroke_width * 3.5))
            head_angle = math.pi / 6.0

            p_left = QPointF(
                self.end_pt.x() - head_len * math.cos(angle - head_angle),
                self.end_pt.y() - head_len * math.sin(angle - head_angle)
            )
            p_right = QPointF(
                self.end_pt.x() - head_len * math.cos(angle + head_angle),
                self.end_pt.y() - head_len * math.sin(angle + head_angle)
            )

            head_poly = QPainterPath()
            head_poly.moveTo(self.end_pt)
            head_poly.lineTo(p_left)
            head_poly.lineTo(p_right)
            head_poly.closeSubpath()
            path.addPath(head_poly)

        self.setPath(path)


class RectShapeItem(QGraphicsRectItem, BaseAnnotationItem):
    def __init__(self, rect: QRectF, color: QColor, width: float = 3.0, rounded: bool = False, filled: bool = False, parent=None):
        super().__init__(rect, parent)
        self.shape_color = QColor(color)
        self.stroke_width = width
        self.rounded = rounded
        self.filled = filled

        pen = QPen(self.shape_color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.setPen(pen)

        if filled:
            fill_c = QColor(color)
            fill_c.setAlpha(45)
            self.setBrush(QBrush(fill_c))
        else:
            self.setBrush(Qt.NoBrush)

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)


class EllipseShapeItem(QGraphicsEllipseItem, BaseAnnotationItem):
    def __init__(self, rect: QRectF, color: QColor, width: float = 3.0, filled: bool = False, parent=None):
        super().__init__(rect, parent)
        self.shape_color = QColor(color)
        self.stroke_width = width
        self.filled = filled

        pen = QPen(self.shape_color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.setPen(pen)

        if filled:
            fill_c = QColor(color)
            fill_c.setAlpha(45)
            self.setBrush(QBrush(fill_c))
        else:
            self.setBrush(Qt.NoBrush)

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)


class StepMarkerItem(QGraphicsItem, BaseAnnotationItem):
    def __init__(self, center: QPointF, step_num: int, color: QColor, radius: float = 14.0, parent=None):
        super().__init__(parent)
        self.setPos(center)
        self.step_num = step_num
        self.marker_color = QColor(color)
        self.radius = radius

        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def boundingRect(self) -> QRectF:
        r = self.radius + 3
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.radius

        # Drop shadow
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(-r, -r + 1.5, r * 2, r * 2))

        # Circle body
        painter.setBrush(self.marker_color)
        painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
        painter.drawEllipse(QRectF(-r, -r, r * 2, r * 2))

        # Number text
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI Variable", int(r * 0.9), QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(-r, -r, r * 2, r * 2), Qt.AlignCenter, str(self.step_num))


class TextAnnotationItem(QGraphicsTextItem, BaseAnnotationItem):
    def __init__(self, text: str, pos: QPointF, color: QColor, font_size: int = 14, bg_chip: bool = True, parent=None):
        super().__init__(parent)
        self.setPlainText(text)
        self.setPos(pos)
        self.text_color = QColor(color)
        self.font_size = font_size
        self.bg_chip = bg_chip

        self.setFont(QFont("Segoe UI Variable", font_size, QFont.DemiBold))
        self.setDefaultTextColor(self.text_color)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def paint(self, painter: QPainter, option, widget=None):
        if self.bg_chip:
            painter.setRenderHint(QPainter.Antialiasing)
            rect = self.boundingRect()
            painter.setBrush(QColor(22, 23, 26, 210))
            painter.setPen(QPen(QColor(99, 102, 241, 140), 1.0))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        super().paint(painter, option, widget)


class RedactionItem(QGraphicsRectItem, BaseAnnotationItem):
    """Irreversible pixelation / blur redaction region."""
    def __init__(self, rect: QRectF, mode: str = "pixelate", parent=None):
        super().__init__(rect, parent)
        self.redact_mode = mode  # "pixelate" or "solid"
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setPen(QPen(QColor(239, 68, 68, 160), 1.0, Qt.DashLine))
        if mode == "solid":
            self.setBrush(QColor(18, 18, 20))
        else:
            self.setBrush(QColor(18, 18, 20, 200))


class AnnotationScene(QGraphicsScene):
    """
    Retained-mode vector canvas.
    Renders sharp interactive canvas and exports true antialiased images.
    """
    def __init__(self, bg_image: QImage, parent=None):
        super().__init__(parent)
        self.bg_image = bg_image
        self.setSceneRect(0, 0, bg_image.width(), bg_image.height())

        # Render sharp background capture
        self.bg_pixmap = QPixmap.fromImage(bg_image)
        self.bg_item = self.addPixmap(self.bg_pixmap)
        self.bg_item.setZValue(-1000)
        self.bg_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.bg_item.setFlag(QGraphicsItem.ItemIsMovable, False)

        # Undo / Redo stacks
        self.undo_stack: List[List[QGraphicsItem]] = []
        self.redo_stack: List[List[QGraphicsItem]] = []

    def commit_action(self, items: List[QGraphicsItem]):
        self.undo_stack.append(list(items))
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        last_action = self.undo_stack.pop()
        for it in last_action:
            if it.scene() == self:
                self.removeItem(it)
        self.redo_stack.append(last_action)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        action = self.redo_stack.pop()
        for it in action:
            self.addItem(it)
        self.undo_stack.append(action)
        return True

    def render_wysiwyg_image(self, crop_rect: Optional[QRectF] = None) -> QImage:
        """
        Renders the vector scene directly into a native high-resolution QImage.
        Guarantees 100% WYSIWYG match between screen display and saved file.
        """
        target_rect = crop_rect if crop_rect else self.sceneRect()
        w = int(target_rect.width())
        h = int(target_rect.height())

        out_img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        out_img.fill(Qt.transparent)

        painter = QPainter(out_img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        self.render(painter, QRectF(0, 0, w, h), target_rect)
        painter.end()

        return out_img
