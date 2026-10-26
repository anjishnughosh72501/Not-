"""
ui/general_tab.py - Start on login, open on launch, and pause/resume daemon control.
"""

from __future__ import annotations
import sys
import os
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt

from settings_store import SettingsManager

RUN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MarkSnap"


def set_windows_startup(enable: bool) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            exe_path = sys.executable
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "marksnap.py"))
            cmd = f'"{exe_path}" "{script_path}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"[GeneralTab] Startup registry error: {e}")
        return False


class GeneralTab(QWidget):
    def __init__(self, settings_mgr: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Startup & Launch Behavior
        grp_startup = QGroupBox("System Startup & Launch")
        layout_start = QVBoxLayout(grp_startup)
        layout_start.setSpacing(10)

        self.chk_startup = QCheckBox("Start MarkSnap automatically on Windows login")
        self.chk_startup.stateChanged.connect(self.on_startup_changed)
        layout_start.addWidget(self.chk_startup)

        self.chk_open_library = QCheckBox("Open the Library window when MarkSnap launches")
        self.chk_open_library.stateChanged.connect(self.save_settings)
        layout_start.addWidget(self.chk_open_library)

        main_layout.addWidget(grp_startup)

        # Pause / Resume Control
        grp_status = QGroupBox("Service Control")
        layout_status = QVBoxLayout(grp_status)
        layout_status.setSpacing(10)

        self.status_lbl = QLabel("Current Status: Active and listening for gestures")
        self.status_lbl.setStyleSheet("font-weight: bold; color: #4CAF50;")
        layout_status.addWidget(self.status_lbl)

        self.btn_pause = QPushButton("Pause MarkSnap")
        self.btn_pause.setFixedWidth(180)
        self.btn_pause.clicked.connect(self.toggle_pause)
        layout_status.addWidget(self.btn_pause)

        pause_desc = QLabel("Pausing temporarily disables the overlay hotkey without shutting down the daemon.")
        pause_desc.setStyleSheet("color: #888888; font-size: 11px;")
        layout_status.addWidget(pause_desc)

        main_layout.addWidget(grp_status)
        main_layout.addStretch()

    def load_settings(self):
        data = self.settings_mgr.get_data()
        gen = data.get("general", {})

        self.chk_startup.setChecked(gen.get("start_on_login", False))
        self.chk_open_library.setChecked(gen.get("open_library_on_launch", False))

        is_paused = gen.get("paused", False)
        self._update_pause_ui(is_paused)

    def on_startup_changed(self):
        enabled = self.chk_startup.isChecked()
        success = set_windows_startup(enabled)
        if not success:
            QMessageBox.warning(self, "Registry Error", "Could not update the Windows startup registry key.")
        self.save_settings()

    def toggle_pause(self):
        data = self.settings_mgr.get_data()
        currently_paused = data.get("general", {}).get("paused", False)
        new_paused = not currently_paused
        data["general"]["paused"] = new_paused
        self.settings_mgr.save(data)
        self._update_pause_ui(new_paused)

    def _update_pause_ui(self, is_paused: bool):
        if is_paused:
            self.status_lbl.setText("Current Status: PAUSED (Hotkey disabled)")
            self.status_lbl.setStyleSheet("font-weight: bold; color: #FF9800;")
            self.btn_pause.setText("Resume MarkSnap")
            self.btn_pause.setStyleSheet("background-color: #2E7D32; color: white;")
        else:
            self.status_lbl.setText("Current Status: Active and listening for gestures")
            self.status_lbl.setStyleSheet("font-weight: bold; color: #4CAF50;")
            self.btn_pause.setText("Pause MarkSnap")
            self.btn_pause.setStyleSheet("background-color: #C62828; color: white;")

    def save_settings(self):
        data = self.settings_mgr.get_data()
        data["general"]["start_on_login"] = self.chk_startup.isChecked()
        data["general"]["open_library_on_launch"] = self.chk_open_library.isChecked()
        self.settings_mgr.save(data)
