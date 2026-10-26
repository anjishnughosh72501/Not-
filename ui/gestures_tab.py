"""
ui/gestures_tab.py - Gesture enablement, action mapping, sensitivity slider, and 'Try it' canvas.
"""

from __future__ import annotations
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox,
    QSlider, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor

from settings_store import SettingsManager
from recognizer import classify, Point

ACTION_OPTIONS = [
    ("Save region as PNG", "save_region"),
    ("OCR region to clipboard", "ocr_to_clipboard"),
    ("Save full screen", "save_fullscreen"),
    ("Send to AI Vision", "ask_ai"),
    ("Do nothing", "do_nothing")
]


class GestureTryCanvas(QFrame):
    """Interactive canvas to practice drawing shapes with immediate recognition feedback."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: List[Point] = []
        self.sensitivity = 50
        self.last_result = "Draw a shape above..."
        self.setFixedSize(380, 160)
        self.setStyleSheet("background-color: #1A1A1A; border: 1px dashed #00E5FF; border-radius: 6px;")

    def set_sensitivity(self, val: int):
        self.sensitivity = val

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.points = [(float(event.position().x()), float(event.position().y()))]
            self.last_result = "Drawing..."
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.points.append((float(event.position().x()), float(event.position().y())))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and len(self.points) >= 5:
            res = classify(self.points, sensitivity=self.sensitivity)
            shape = res["shape"].upper()
            conf = res["confidence"] * 100
            self.last_result = f"Recognized: {shape} ({conf:.0f}% confidence)"
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw stroke
        if len(self.points) > 1:
            pen = QPen(QColor("#00E5FF"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            for i in range(1, len(self.points)):
                p1 = QPointF(self.points[i - 1][0], self.points[i - 1][1])
                p2 = QPointF(self.points[i][0], self.points[i][1])
                painter.drawLine(p1, p2)

        # Draw result text banner
        painter.setPen(QColor("#FFFF00" if "Recognized" in self.last_result else "#888888"))
        painter.drawText(self.rect().adjusted(10, 10, -10, -10), Qt.AlignBottom | Qt.AlignLeft, self.last_result)


class GesturesTab(QWidget):
    def __init__(self, settings_mgr: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self.controls: Dict[str, Dict[str, Any]] = {}
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Gestures config box
        grp = QGroupBox("Gesture Vocabulary & Action Routing")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(10)

        for shape_key, label_text in [
            ("box", "Box (closed loop, near-rectangular)"),
            ("circle", "Circle (closed loop, smooth)"),
            ("underline", "Underline (flat horizontal stroke)"),
            ("arrow", "Arrow / Line (directed stroke)")
        ]:
            row = QHBoxLayout()
            chk = QCheckBox(label_text)
            chk.setStyleSheet("font-weight: 500;")
            chk.stateChanged.connect(self.save_settings)
            row.addWidget(chk, 2)

            combo = QComboBox()
            for text, val in ACTION_OPTIONS:
                combo.addItem(text, val)
            combo.currentIndexChanged.connect(self.save_settings)
            row.addWidget(combo, 2)

            grp_layout.addLayout(row)
            self.controls[shape_key] = {"check": chk, "combo": combo}

        main_layout.addWidget(grp)

        # Sensitivity and Try-It area
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)

        # Sensitivity Box
        sens_grp = QGroupBox("Recognition Sensitivity")
        sens_layout = QVBoxLayout(sens_grp)

        self.sens_label = QLabel("Sensitivity: Normal (50)")
        sens_layout.addWidget(self.sens_label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.on_sensitivity_change)
        sens_layout.addWidget(self.slider)

        sens_desc = QLabel("Strict (fewer false positives) <------> Loose (easier to trigger)")
        sens_desc.setStyleSheet("color: #888888; font-size: 10px;")
        sens_layout.addWidget(sens_desc)
        sens_layout.addStretch()

        bottom_row.addWidget(sens_grp, 1)

        # Try-It Box
        try_grp = QGroupBox("Try It (Interactive Canvas)")
        try_layout = QVBoxLayout(try_grp)
        self.try_canvas = GestureTryCanvas()
        try_layout.addWidget(self.try_canvas)
        bottom_row.addWidget(try_grp, 1)

        main_layout.addLayout(bottom_row)
        main_layout.addStretch()

    def load_settings(self):
        data = self.settings_mgr.get_data()
        gestures = data.get("gestures", {})

        for shape, ctrl in self.controls.items():
            cfg = gestures.get(shape, {})
            ctrl["check"].setChecked(cfg.get("enabled", True))
            act = cfg.get("action", "save_region")
            idx = ctrl["combo"].findData(act)
            if idx >= 0:
                ctrl["combo"].setCurrentIndex(idx)

        sens = gestures.get("sensitivity", 50)
        self.slider.setValue(sens)
        self.try_canvas.set_sensitivity(sens)
        self._update_sens_label(sens)

    def on_sensitivity_change(self, val: int):
        self._update_sens_label(val)
        self.try_canvas.set_sensitivity(val)
        self.save_settings()

    def _update_sens_label(self, val: int):
        if val < 35:
            desc = "Strict"
        elif val > 65:
            desc = "Loose"
        else:
            desc = "Normal"
        self.sens_label.setText(f"Sensitivity: {desc} ({val})")

    def save_settings(self):
        data = self.settings_mgr.get_data()
        for shape, ctrl in self.controls.items():
            data["gestures"][shape]["enabled"] = ctrl["check"].isChecked()
            data["gestures"][shape]["action"] = ctrl["combo"].currentData()

        data["gestures"]["sensitivity"] = self.slider.value()
        self.settings_mgr.save(data)
