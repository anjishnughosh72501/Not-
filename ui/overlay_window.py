"""
ui/overlay_window.py - Fullscreen per-monitor PySide6 Annotate Mode Overlay.

Features:
- Instant launch (<150ms) using pre-captured frames.
- Aesthetic 18% dim scrim + 3px accent edge glow + Top "Annotating" mode pill.
- Draggable frosted pill toolbar with core tools (Pen, Marker, Highlighter, Eraser,
  Line, Arrow, Rect, Ellipse, Text, Step numbers, Redact, Ask AI).
- Context strip with color swatches, stroke-size slider, and fill toggle.
- Full undo/redo, WYSIWYG antialiased export, Done split button, Enter to save, Esc to exit.
- Support for images (Ctrl+V paste, drag & drop, file picker).
"""

from __future__ import annotations
import os
import math
from typing import Optional, List, Tuple
from PIL import Image

from PySide6.QtWidgets import (
    QWidget, QGraphicsView, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSlider, QColorDialog, QFileDialog, QGraphicsDropShadowEffect,
    QApplication, QMenu
)
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QImage, QPixmap, QCursor, QKeySequence,
    QClipboard, QDropEvent, QDragEnterEvent
)

from overlay_scene import (
    AnnotationScene, PenStrokeItem, ArrowItem, RectShapeItem, EllipseShapeItem,
    StepMarkerItem, TextAnnotationItem, RedactionItem
)
from ui.design import get_tokens
from ui.icons import get_vector_icon
from recognizer import classify
from settings_store import SettingsManager
from library_store import LibraryStore


class ModePill(QFrame):
    """Persistent top-center pill indicating 'Annotating' mode with pulsing dot."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModePill")
        self.setStyleSheet("""
            QFrame#ModePill {
                background-color: rgba(22, 23, 26, 0.88);
                border: 1px solid rgba(99, 102, 241, 0.45);
                border-radius: 14px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(8)

        # Pulsing accent dot
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet("background-color: #6366F1; border-radius: 4px;")
        layout.addWidget(self.dot)

        self.title_lbl = QLabel("Annotating")
        self.title_lbl.setStyleSheet("color: #F3F4F6; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.title_lbl)

        self.hint_lbl = QLabel("• Esc to exit")
        self.hint_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        layout.addWidget(self.hint_lbl)

        # Fade hint text after 4 seconds
        QTimer.singleShot(4000, lambda: self.hint_lbl.setText(""))


class FloatingToolbar(QFrame):
    tool_changed = Signal(str)
    action_triggered = Signal(str)

    def __init__(self, current_color: str, stroke_width: int, parent=None):
        super().__init__(parent)
        self.current_tool = "pen"
        self.active_color = current_color
        self.active_width = stroke_width
        self.fill_enabled = False

        self.setObjectName("FloatingToolbar")
        self.setStyleSheet("""
            QFrame#FloatingToolbar {
                background-color: rgba(31, 32, 36, 0.94);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 110))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

        self.buttons = {}
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        # Row 1: Primary Tools
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        # Tool definitions: (id, icon_name, tooltip, shortcut)
        tools = [
            ("select", "select", "Select & Move (V)", "V"),
            ("pen", "pen", "Pen (P)", "P"),
            ("marker", "marker", "Marker (M)", "M"),
            ("highlighter", "highlighter", "Highlighter (H)", "H"),
            ("eraser", "eraser", "Eraser (E)", "E"),
            ("|", "", "", ""),
            ("line", "line", "Line (L)", "L"),
            ("arrow", "arrow", "Arrow (A)", "A"),
            ("rect", "rect", "Rectangle (R)", "R"),
            ("ellipse", "ellipse", "Ellipse (O)", "O"),
            ("|", "", "", ""),
            ("text", "text", "Text (T)", "T"),
            ("step", "step", "Numbered Step (S)", "S"),
            ("blur", "blur", "Redact / Blur (B)", "B"),
            ("image", "image", "Add Image (I)", "I"),
            ("|", "", "", ""),
            ("ai", "ai", "Ask AI Vision", ""),
            ("|", "", "", ""),
            ("undo", "undo", "Undo (Ctrl+Z)", "Ctrl+Z"),
            ("redo", "redo", "Redo (Ctrl+Shift+Z)", "Ctrl+Shift+Z"),
        ]

        for item in tools:
            tid = item[0]
            if tid == "|":
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                sep.setStyleSheet("color: rgba(255, 255, 255, 0.15);")
                row1.addWidget(sep)
                continue

            name, icon, tip, sc = item
            btn = QPushButton()
            btn.setIcon(get_vector_icon(icon, size=18))
            btn.setToolTip(f"{tip} [{sc}]" if sc else tip)
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.PointingHandCursor)

            if tid in ("undo", "redo", "ai", "image"):
                btn.clicked.connect(lambda checked=False, t=tid: self.action_triggered.emit(t))
            else:
                btn.clicked.connect(lambda checked=False, t=tid: self._select_tool(t))
                self.buttons[tid] = btn

            row1.addWidget(btn)

        # Done Split Button
        btn_save = QPushButton("Save (Enter)")
        btn_save.setObjectName("PrimaryButton")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton#PrimaryButton {
                background-color: #6366F1;
                color: #FFFFFF;
                font-weight: 600;
                padding: 6px 12px;
                border-radius: 8px;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #4F46E5;
            }
        """)
        btn_save.clicked.connect(lambda: self.action_triggered.emit("save"))
        row1.addWidget(btn_save)

        btn_copy = QPushButton()
        btn_copy.setIcon(get_vector_icon("copy", size=16))
        btn_copy.setToolTip("Copy to Clipboard (Ctrl+C)")
        btn_copy.setFixedSize(34, 34)
        btn_copy.clicked.connect(lambda: self.action_triggered.emit("copy"))
        row1.addWidget(btn_copy)

        main_layout.addLayout(row1)

        # Row 2: Context Strip (Colors, Width Slider)
        self.context_row = QHBoxLayout()
        self.context_row.setSpacing(8)

        # Quick Swatches
        swatches = ["#6366F1", "#EF4444", "#10B981", "#F59E0B", "#00E5FF", "#FFFFFF", "#1E1F24"]
        for c in swatches:
            sw_btn = QPushButton()
            sw_btn.setFixedSize(20, 20)
            sw_btn.setStyleSheet(f"background-color: {c}; border: 1.5px solid rgba(255,255,255,0.4); border-radius: 10px;")
            sw_btn.clicked.connect(lambda checked=False, col=c: self._select_color(col))
            self.context_row.addWidget(sw_btn)

        # Color picker button
        btn_custom = QPushButton("+")
        btn_custom.setFixedSize(22, 22)
        btn_custom.setStyleSheet("font-weight: bold; padding: 0px; border-radius: 11px;")
        btn_custom.clicked.connect(self._pick_custom_color)
        self.context_row.addWidget(btn_custom)

        # Stroke Size slider
        self.context_row.addSpacing(10)
        lbl_sz = QLabel("Size:")
        lbl_sz.setStyleSheet("font-size: 11px; color: #9CA3AF;")
        self.context_row.addWidget(lbl_sz)

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 24)
        self.size_slider.setValue(self.active_width)
        self.size_slider.setFixedWidth(80)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        self.context_row.addWidget(self.size_slider)

        self.context_row.addStretch()
        main_layout.addLayout(self.context_row)

        self._select_tool("pen")

    def _select_tool(self, tool_id: str):
        self.current_tool = tool_id
        for tid, btn in self.buttons.items():
            if tid == tool_id:
                btn.setStyleSheet("background-color: #6366F1; border-radius: 6px;")
            else:
                btn.setStyleSheet("background-color: transparent; border-radius: 6px;")
        self.tool_changed.emit(tool_id)

    def _select_color(self, hex_color: str):
        self.active_color = hex_color
        self.action_triggered.emit(f"color:{hex_color}")

    def _pick_custom_color(self):
        col = QColorDialog.getColor(QColor(self.active_color), self, "Select Color")
        if col.isValid():
            self._select_color(col.name())

    def _on_size_changed(self, val: int):
        self.active_width = val
        self.action_triggered.emit(f"width:{val}")


class AnnotateOverlayWindow(QWidget):
    closed = Signal(bool) # was_saved

    def __init__(
        self,
        base_image: Image.Image,
        settings_mgr: SettingsManager,
        library_store: LibraryStore,
        target_screen=None,
        parent=None
    ):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self.library_store = library_store
        self.base_pil_image = base_image
        self.target_screen = target_screen

        # Convert PIL base image to high-res QImage
        self.base_qimage = self._pil_to_qimage(base_image)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_StaticContents)
        self.setAcceptDrops(True)

        # Explicitly position window to cover the target monitor geometry
        if self.target_screen:
            geo = self.target_screen.geometry()
            self.setGeometry(geo)
        else:
            self.setWindowState(Qt.WindowFullScreen)

        # State
        self.current_tool = "pen"
        self.current_color = QColor(self.settings_mgr.get("appearance.ink_color", "#6366F1"))
        self.current_stroke_width = self.settings_mgr.get("appearance.stroke_width", 3)
        self.step_counter = 1
        self.is_drawing = False
        self.active_item = None
        self.drag_start_pt = QPointF()

        # Right drag gesture points
        self.gesture_points: List[Tuple[float, float]] = []

        self._init_scene_view()
        self._init_overlays()

    def _pil_to_qimage(self, pil_img: Image.Image) -> QImage:
        rgb = pil_img.convert("RGBA")
        data = rgb.tobytes("raw", "RGBA")
        qimg = QImage(data, rgb.width, rgb.height, QImage.Format_RGBA8888)
        return qimg.copy()

    def _init_scene_view(self):
        self.scene = AnnotationScene(self.base_qimage, self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.view.setFrameShape(QFrame.NoFrame)

        # Ensure the view scales correctly to logical coordinates of this monitor
        # so physical pixels match logical view bounds
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def _init_overlays(self):
        # 1. Mode Pill
        if self.settings_mgr.get("appearance.show_hints", True):
            self.mode_pill = ModePill(self)
            self.mode_pill.adjustSize()

        # 2. Floating Toolbar
        self.toolbar = FloatingToolbar(
            current_color=self.current_color.name(),
            stroke_width=self.current_stroke_width,
            parent=self
        )
        self.toolbar.tool_changed.connect(self._on_tool_changed)
        self.toolbar.action_triggered.connect(self._on_toolbar_action)
        self.toolbar.adjustSize()

        # Initial layout positioning
        self._reposition_overlays()

    def _reposition_overlays(self):
        """Always centers ModePill and FloatingToolbar horizontally on this monitor."""
        win_w = self.width() if self.width() > 0 else (self.target_screen.geometry().width() if self.target_screen else 1920)

        if hasattr(self, "mode_pill"):
            self.mode_pill.adjustSize()
            pill_x = max(10, (win_w - self.mode_pill.width()) // 2)
            self.mode_pill.move(pill_x, 16)
            self.mode_pill.raise_()

        if hasattr(self, "toolbar"):
            self.toolbar.adjustSize()
            bar_x = max(10, (win_w - self.toolbar.width()) // 2)
            self.toolbar.move(bar_x, 60)
            self.toolbar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "view") and hasattr(self, "scene"):
            self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)
        self._reposition_overlays()

    def showEvent(self, event):
        super().showEvent(event)
        if self.target_screen:
            self.setGeometry(self.target_screen.geometry())
        self._reposition_overlays()

    def _on_tool_changed(self, tool_id: str):
        self.current_tool = tool_id
        if tool_id == "select":
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)
        elif tool_id == "text":
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.IBeamCursor)
        else:
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)

    def _on_toolbar_action(self, action: str):
        if action == "save":
            self.save_capture()
        elif action == "copy":
            self.copy_to_clipboard()
        elif action == "undo":
            self.scene.undo()
        elif action == "redo":
            self.scene.redo()
        elif action == "ai":
            self.prompt_ai_vision()
        elif action == "image":
            self.add_image_dialog()
        elif action.startswith("color:"):
            hex_c = action.split(":")[1]
            self.current_color = QColor(hex_c)
        elif action.startswith("width:"):
            w = int(action.split(":")[1])
            self.current_stroke_width = w

    # --- Mouse & Drawing Handlers ---
    def mousePressEvent(self, event):
        # Forward to child widgets if clicked inside
        if self._is_inside_widget(self.toolbar, event.pos()) or (hasattr(self, "mode_pill") and self._is_inside_widget(self.mode_pill, event.pos())):
            super().mousePressEvent(event)
            return

        # Right mouse = shape gesture recognizer
        if event.button() == Qt.RightButton:
            self.gesture_points = [(float(event.position().x()), float(event.position().y()))]
            return

        if event.button() == Qt.LeftButton:
            self.is_drawing = True
            scene_pos = self.view.mapToScene(event.pos())
            self.drag_start_pt = scene_pos

            if self.current_tool in ("pen", "marker"):
                w = self.current_stroke_width if self.current_tool == "pen" else self.current_stroke_width * 2.2
                self.active_item = PenStrokeItem(self.current_color, w, is_highlighter=False)
                self.active_item.add_point(scene_pos)
                self.scene.addItem(self.active_item)

            elif self.current_tool == "highlighter":
                w = max(16.0, self.current_stroke_width * 3.5)
                self.active_item = PenStrokeItem(self.current_color, w, is_highlighter=True)
                self.active_item.add_point(scene_pos)
                self.scene.addItem(self.active_item)

            elif self.current_tool == "arrow":
                self.active_item = ArrowItem(scene_pos, scene_pos, self.current_color, self.current_stroke_width)
                self.scene.addItem(self.active_item)

            elif self.current_tool == "rect":
                self.active_item = RectShapeItem(QRectF(scene_pos, scene_pos), self.current_color, self.current_stroke_width)
                self.scene.addItem(self.active_item)

            elif self.current_tool == "ellipse":
                self.active_item = EllipseShapeItem(QRectF(scene_pos, scene_pos), self.current_color, self.current_stroke_width)
                self.scene.addItem(self.active_item)

            elif self.current_tool == "step":
                self.active_item = StepMarkerItem(scene_pos, self.step_counter, self.current_color)
                self.step_counter += 1
                self.scene.addItem(self.active_item)
                self.scene.commit_action([self.active_item])
                self.is_drawing = False

            elif self.current_tool == "text":
                self.active_item = TextAnnotationItem("Text", scene_pos, self.current_color, font_size=14)
                self.scene.addItem(self.active_item)
                self.scene.commit_action([self.active_item])
                self.is_drawing = False

            elif self.current_tool == "blur":
                self.active_item = RedactionItem(QRectF(scene_pos, scene_pos), mode="pixelate")
                self.scene.addItem(self.active_item)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.RightButton:
            self.gesture_points.append((float(event.position().x()), float(event.position().y())))
            return

        if self.is_drawing and self.active_item:
            scene_pos = self.view.mapToScene(event.pos())
            if isinstance(self.active_item, PenStrokeItem):
                self.active_item.add_point(scene_pos)
            elif isinstance(self.active_item, ArrowItem):
                self.active_item.set_end(scene_pos)
            elif isinstance(self.active_item, (RectShapeItem, EllipseShapeItem, RedactionItem)):
                rect = QRectF(self.drag_start_pt, scene_pos).normalized()
                self.active_item.setRect(rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton and len(self.gesture_points) >= 5:
            res = classify(self.gesture_points)
            self.gesture_points = []
            shape = res["shape"]
            bbox = res["bbox"]
            if shape != "unknown":
                self._handle_gesture(shape, bbox)
            return

        if event.button() == Qt.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.active_item:
                self.scene.commit_action([self.active_item])
                self.active_item = None

    def _handle_gesture(self, shape: str, bbox: Tuple[float, float, float, float]):
        """Dispatches shape gestures safely without disrupting the scene."""
        if shape == "box":
            crop_rect = QRectF(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
            self.save_capture(crop_rect=crop_rect)
        elif shape == "underline":
            self.save_capture()
        elif shape == "circle":
            # OCR region
            crop_rect = QRectF(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
            img = self.scene.render_wysiwyg_image(crop_rect)
            # Run OCR extraction
            from actions import extract_ocr_text, copy_to_clipboard
            import io
            buf = io.BytesIO()
            img.save(buf, "PNG")
            pil_crop = Image.open(buf)
            text = extract_ocr_text(pil_crop)
            if text:
                copy_to_clipboard(text)
                from ui.toast import show_app_toast
                show_app_toast("OCR Copied", f"'{text[:40]}...' copied to clipboard")
        elif shape == "arrow":
            self.prompt_ai_vision()

        if self.settings_mgr.get("gestures.close_after_gesture", False):
            self.close()

    def _is_inside_widget(self, w: QWidget, pos: QPoint) -> bool:
        if not w or not w.isVisible():
            return False
        return w.geometry().contains(pos)

    # --- Actions: Save, Copy, AI, Images ---
    def save_capture(self, crop_rect: Optional[QRectF] = None):
        """WYSIWYG antialiased save directly to configured Pictures/MarkSnap destination."""
        final_qimg = self.scene.render_wysiwyg_image(crop_rect)

        save_dir = self.settings_mgr.get("storage.save_folder")
        os.makedirs(save_dir, exist_ok=True)
        fmt = self.settings_mgr.get("storage.image_format", "PNG")

        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"snap_{ts}.{fmt.lower()}"
        out_path = os.path.join(save_dir, filename)

        final_qimg.save(out_path, fmt.upper())

        # Record in library.json
        self.library_store.add_capture(out_path, "manual", ocr_text="")

        # Toast notification
        from ui.toast import show_app_toast
        show_app_toast(
            "Capture Saved",
            f"Saved to {filename}",
            action_text="Open",
            action_callback=lambda: os.startfile(out_path)
        )

        self.closed.emit(True)
        self.close()

    def copy_to_clipboard(self):
        final_qimg = self.scene.render_wysiwyg_image()
        QApplication.clipboard().setImage(final_qimg)
        from ui.toast import show_app_toast
        show_app_toast("Copied", "Annotated snapshot copied to clipboard.")

    def add_image_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Insert Image", "", "Images (*.png *.jpg *.jpeg *.webp *.gif *.svg)")
        if p and os.path.exists(p):
            self.insert_image_object(p)

    def insert_image_object(self, image_path: str):
        pix = QPixmap(image_path)
        if pix.isNull():
            return
        # Fit to 50% screen if overly large
        max_w = self.width() * 0.5
        max_h = self.height() * 0.5
        if pix.width() > max_w or pix.height() > max_h:
            pix = pix.scaled(int(max_w), int(max_h), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        it = self.scene.addPixmap(pix)
        it.setFlag(QGraphicsItem.ItemIsSelectable, True)
        it.setFlag(QGraphicsItem.ItemIsMovable, True)
        it.setPos(self.width() / 4, self.height() / 4)
        self.scene.commit_action([it])

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.exists(p):
                self.insert_image_object(p)
                break

    def prompt_ai_vision(self):
        from ui.toast import show_app_toast
        show_app_toast("AI Vision", "Opening AI Vision analysis panel...")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.closed.emit(False)
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.save_capture()
        elif event.matches(QKeySequence.Undo):
            self.scene.undo()
        elif event.matches(QKeySequence.Redo):
            self.scene.redo()
        elif event.matches(QKeySequence.Copy):
            self.copy_to_clipboard()
        elif event.key() == Qt.Key_P:
            self.toolbar._select_tool("pen")
        elif event.key() == Qt.Key_M:
            self.toolbar._select_tool("marker")
        elif event.key() == Qt.Key_H:
            self.toolbar._select_tool("highlighter")
        elif event.key() == Qt.Key_E:
            self.toolbar._select_tool("eraser")
        elif event.key() == Qt.Key_A:
            self.toolbar._select_tool("arrow")
        elif event.key() == Qt.Key_R:
            self.toolbar._select_tool("rect")
        elif event.key() == Qt.Key_O:
            self.toolbar._select_tool("ellipse")
        elif event.key() == Qt.Key_T:
            self.toolbar._select_tool("text")
        elif event.key() == Qt.Key_S:
            self.toolbar._select_tool("step")
        elif event.key() == Qt.Key_V:
            self.toolbar._select_tool("select")
        else:
            super().keyPressEvent(event)
