"""
ui/hotkeys_tab.py - Hotkey recording, conflict validation, and reset to defaults.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from settings_store import SettingsManager


def key_event_to_string(event: QKeyEvent) -> Optional[str]:
    """Translates a Qt key event into a standard string representation e.g. ctrl+shift+d."""
    modifiers = []
    if event.modifiers() & Qt.ControlModifier:
        modifiers.append("ctrl")
    if event.modifiers() & Qt.ShiftModifier:
        modifiers.append("shift")
    if event.modifiers() & Qt.AltModifier:
        modifiers.append("alt")

    key = event.key()

    # Ignore modifier-only presses
    if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
        return None

    # Handle alphanumeric and special keys
    if Qt.Key_A <= key <= Qt.Key_Z:
        key_str = chr(key).lower()
    elif Qt.Key_0 <= key <= Qt.Key_9:
        key_str = chr(key)
    elif key == Qt.Key_F1: key_str = "f1"
    elif key == Qt.Key_F2: key_str = "f2"
    elif key == Qt.Key_F3: key_str = "f3"
    elif key == Qt.Key_F4: key_str = "f4"
    elif key == Qt.Key_F5: key_str = "f5"
    elif key == Qt.Key_F6: key_str = "f6"
    elif key == Qt.Key_F7: key_str = "f7"
    elif key == Qt.Key_F8: key_str = "f8"
    elif key == Qt.Key_F9: key_str = "f9"
    elif key == Qt.Key_F10: key_str = "f10"
    elif key == Qt.Key_F11: key_str = "f11"
    elif key == Qt.Key_F12: key_str = "f12"
    elif key == Qt.Key_Space: key_str = "space"
    elif key == Qt.Key_Return: key_str = "enter"
    else:
        key_str = event.text().lower()

    if not key_str:
        return None

    modifiers.append(key_str)
    return "+".join(modifiers)


class HotkeysTab(QWidget):
    def __init__(self, settings_mgr: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self.is_recording = False
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        grp = QGroupBox("Global Hotkey Shortcuts")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(12)

        desc = QLabel("Configure the system-wide shortcut to invoke MarkSnap over any application:")
        desc.setStyleSheet("color: #AAAAAA;")
        grp_layout.addWidget(desc)

        row = QHBoxLayout()
        row.setSpacing(10)

        lbl = QLabel("Freeze Screen & Open Overlay:")
        lbl.setMinimumWidth(200)
        row.addWidget(lbl)

        self.hotkey_display = QLineEdit()
        self.hotkey_display.setReadOnly(True)
        self.hotkey_display.setPlaceholderText("ctrl+shift+d")
        self.hotkey_display.setStyleSheet("font-weight: bold; color: #00E5FF; padding: 6px;")
        row.addWidget(self.hotkey_display, 1)

        self.btn_record = QPushButton("Record")
        self.btn_record.clicked.connect(self.toggle_recording)
        row.addWidget(self.btn_record)

        self.btn_reset = QPushButton("Reset to Default")
        self.btn_reset.clicked.connect(self.reset_default)
        row.addWidget(self.btn_reset)

        grp_layout.addLayout(row)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 11px;")
        grp_layout.addWidget(self.status_lbl)

        layout.addWidget(grp)
        layout.addStretch()

    def load_settings(self):
        hotkey = self.settings_mgr.get("hotkeys.open_overlay", "ctrl+shift+d")
        self.hotkey_display.setText(hotkey)
        self.status_lbl.setText("Ready. Changes are applied automatically to the background capture app.")

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.btn_record.setText("Listening... (Press Keys)")
            self.btn_record.setStyleSheet("background-color: #A93226; color: white;")
            self.hotkey_display.setText("Press combination...")
            self.grabKeyboard()
        else:
            self.stop_recording()

    def stop_recording(self):
        self.is_recording = False
        self.btn_record.setText("Record")
        self.btn_record.setStyleSheet("")
        self.releaseKeyboard()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_recording:
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Escape:
            self.stop_recording()
            self.load_settings()
            return

        comb = key_event_to_string(event)
        if comb:
            self.stop_recording()
            self.save_hotkey(comb)

    def save_hotkey(self, combo: str):
        # Validate combination has at least one modifier
        if "+" not in combo:
            QMessageBox.warning(self, "Invalid Hotkey", "Hotkeys should combine a modifier (Ctrl, Shift, or Alt) with a key.")
            self.load_settings()
            return

        data = self.settings_mgr.get_data()
        data["hotkeys"]["open_overlay"] = combo
        try:
            self.settings_mgr.save(data)
            self.hotkey_display.setText(combo)
            self.status_lbl.setText(f"Successfully bound '{combo}'. Live background app updated.")
            self.status_lbl.setStyleSheet("color: #4CAF50;")
        except Exception as e:
            self.status_lbl.setText(f"Error saving hotkey: {e}")
            self.status_lbl.setStyleSheet("color: #FF5252;")

    def reset_default(self):
        self.save_hotkey("ctrl+shift+d")
