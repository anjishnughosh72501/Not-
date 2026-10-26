"""
ui/appearance_tab.py - Ink and gesture visual customization with live preview.
"""

from __future__ import annotations
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox,
    QSpinBox, QGroupBox, QPushButton, QColorDialog, QFrame
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor

from settings_store import SettingsManager


class LiveStrokePreview(QFrame):
    """Draws sample strokes representing user-chosen ink and gesture styles."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ink_color = "#FF2222"
        self.gesture_color = "#00E5FF"
        self.stroke_width = 3
        self.setFixedHeight(120)
        self.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 6px;")

    def update_params(self, ink: str, gesture: str, width: int):
        self.ink_color = ink
        self.gesture_color = gesture
        self.stroke_width = width
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw Plain Ink Sample
        pen_ink = QPen(QColor(self.ink_color), self.stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen_ink)
        painter.drawPolyline([QPointF(30, 40), QPointF(80, 20), QPointF(140, 60), QPointF(200, 30)])

        painter.setPen(QColor("#AAAAAA"))
        painter.drawText(30, 85, "Plain Ink Stroke (Left-drag)")

        # Draw Gesture Stroke Sample
        pen_gest = QPen(QColor(self.gesture_color), self.stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen_gest)
        painter.drawPolyline([QPointF(250, 40), QPointF(300, 20), QPointF(360, 60), QPointF(420, 30)])

        painter.setPen(QColor("#AAAAAA"))
        painter.drawText(250, 85, "Gesture Stroke (Right-drag)")


class AppearanceTab(QWidget):
    def __init__(self, settings_mgr: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Stroke Styling
        style_grp = QGroupBox("Stroke Styles & Colors")
        style_layout = QVBoxLayout(style_grp)

        row_colors = QHBoxLayout()

        # Ink Color
        lbl_ink = QLabel("Plain Ink Color:")
        row_colors.addWidget(lbl_ink)
        self.btn_ink_color = QPushButton()
        self.btn_ink_color.setFixedSize(60, 26)
        self.btn_ink_color.clicked.connect(self.choose_ink_color)
        row_colors.addWidget(self.btn_ink_color)

        row_colors.addSpacing(20)

        # Gesture Color
        lbl_gest = QLabel("Gesture Color:")
        row_colors.addWidget(lbl_gest)
        self.btn_gest_color = QPushButton()
        self.btn_gest_color.setFixedSize(60, 26)
        self.btn_gest_color.clicked.connect(self.choose_gesture_color)
        row_colors.addWidget(self.btn_gest_color)

        row_colors.addSpacing(20)

        # Stroke Width
        lbl_w = QLabel("Stroke Width (px):")
        row_colors.addWidget(lbl_w)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 15)
        self.spin_width.setValue(3)
        self.spin_width.valueChanged.connect(self.on_style_changed)
        row_colors.addWidget(self.spin_width)

        row_colors.addStretch()
        style_layout.addLayout(row_colors)

        # Live Stroke Preview
        self.preview = LiveStrokePreview()
        style_layout.addWidget(self.preview)

        main_layout.addWidget(style_grp)

        # Overlay Feedback & Toast Notifications
        fb_grp = QGroupBox("Feedback & Notifications")
        fb_layout = QVBoxLayout(fb_grp)
        fb_layout.setSpacing(10)

        self.chk_toast = QCheckBox("Show toast notification after an action")
        self.chk_toast.stateChanged.connect(self.save_settings)
        fb_layout.addWidget(self.chk_toast)

        self.chk_flash = QCheckBox("Flash recognized shape name for 400ms before acting")
        self.chk_flash.stateChanged.connect(self.save_settings)
        fb_layout.addWidget(self.chk_flash)

        self.chk_hints = QCheckBox("Show top hint banner on the frozen overlay")
        self.chk_hints.stateChanged.connect(self.save_settings)
        fb_layout.addWidget(self.chk_hints)

        self.chk_sound = QCheckBox("Play sound effect on action complete")
        self.chk_sound.stateChanged.connect(self.save_settings)
        fb_layout.addWidget(self.chk_sound)

        # Toast position & duration
        toast_row = QHBoxLayout()
        toast_row.addWidget(QLabel("Toast Position:"))
        self.combo_toast_pos = QComboBox()
        self.combo_toast_pos.addItems(["bottom-right", "bottom-left", "top-right", "top-left"])
        self.combo_toast_pos.currentIndexChanged.connect(self.save_settings)
        toast_row.addWidget(self.combo_toast_pos)

        toast_row.addSpacing(20)
        toast_row.addWidget(QLabel("Toast Duration (ms):"))
        self.spin_toast_dur = QSpinBox()
        self.spin_toast_dur.setRange(500, 10000)
        self.spin_toast_dur.setSingleStep(500)
        self.spin_toast_dur.setValue(2000)
        self.spin_toast_dur.valueChanged.connect(self.save_settings)
        toast_row.addWidget(self.spin_toast_dur)
        toast_row.addStretch()

        fb_layout.addLayout(toast_row)
        main_layout.addWidget(fb_grp)
        main_layout.addStretch()

    def load_settings(self):
        data = self.settings_mgr.get_data()
        app = data.get("appearance", {})

        self.ink_color = app.get("ink_color", "#FF2222")
        self.gesture_color = app.get("gesture_color", "#00E5FF")
        self.stroke_width = app.get("stroke_width", 3)

        self._update_color_button(self.btn_ink_color, self.ink_color)
        self._update_color_button(self.btn_gest_color, self.gesture_color)
        self.spin_width.setValue(self.stroke_width)

        self.chk_toast.setChecked(app.get("show_toast", True))
        self.chk_flash.setChecked(app.get("flash_shape", True))
        self.chk_hints.setChecked(app.get("show_hints", True))
        self.chk_sound.setChecked(app.get("play_sound", False))

        pos = app.get("toast_position", "bottom-right")
        idx = self.combo_toast_pos.findText(pos)
        if idx >= 0:
            self.combo_toast_pos.setCurrentIndex(idx)

        self.spin_toast_dur.setValue(app.get("toast_duration", 2000))
        self.preview.update_params(self.ink_color, self.gesture_color, self.stroke_width)

    def _update_color_button(self, btn: QPushButton, hex_code: str):
        btn.setStyleSheet(f"background-color: {hex_code}; border: 1px solid #777; border-radius: 4px;")

    def choose_ink_color(self):
        col = QColorDialog.getColor(QColor(self.ink_color), self, "Select Ink Color")
        if col.isValid():
            self.ink_color = col.name()
            self._update_color_button(self.btn_ink_color, self.ink_color)
            self.on_style_changed()

    def choose_gesture_color(self):
        col = QColorDialog.getColor(QColor(self.gesture_color), self, "Select Gesture Color")
        if col.isValid():
            self.gesture_color = col.name()
            self._update_color_button(self.btn_gest_color, self.gesture_color)
            self.on_style_changed()

    def on_style_changed(self):
        self.stroke_width = self.spin_width.value()
        self.preview.update_params(self.ink_color, self.gesture_color, self.stroke_width)
        self.save_settings()

    def save_settings(self):
        data = self.settings_mgr.get_data()
        data["appearance"]["ink_color"] = self.ink_color
        data["appearance"]["gesture_color"] = self.gesture_color
        data["appearance"]["stroke_width"] = self.spin_width.value()

        data["appearance"]["show_toast"] = self.chk_toast.isChecked()
        data["appearance"]["flash_shape"] = self.chk_flash.isChecked()
        data["appearance"]["show_hints"] = self.chk_hints.isChecked()
        data["appearance"]["play_sound"] = self.chk_sound.isChecked()
        data["appearance"]["toast_position"] = self.combo_toast_pos.currentText()
        data["appearance"]["toast_duration"] = self.spin_toast_dur.value()

        self.settings_mgr.save(data)
