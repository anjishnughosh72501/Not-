"""
ui/storage_tab.py - Storage directory, naming pattern, format, and auto-delete settings.
"""

from __future__ import annotations
import os
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

from settings_store import SettingsManager


class StorageTab(QWidget):
    def __init__(self, settings_mgr: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # File Destination & Format
        grp_dest = QGroupBox("Capture Storage & Formats")
        layout_dest = QVBoxLayout(grp_dest)
        layout_dest.setSpacing(10)

        # Folder picker
        row_folder = QHBoxLayout()
        row_folder.addWidget(QLabel("Save Folder:"))
        self.txt_folder = QLineEdit()
        self.txt_folder.editingFinished.connect(self.save_settings)
        row_folder.addWidget(self.txt_folder, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_folder)
        row_folder.addWidget(self.btn_browse)
        layout_dest.addLayout(row_folder)

        # Pattern & Format row
        row_opts = QHBoxLayout()
        row_opts.addWidget(QLabel("Filename Pattern:"))
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setPlaceholderText("{type}_{date}_{time}")
        self.txt_pattern.editingFinished.connect(self.save_settings)
        row_opts.addWidget(self.txt_pattern, 2)

        row_opts.addSpacing(16)
        row_opts.addWidget(QLabel("Format:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG", "JPG"])
        self.combo_format.currentIndexChanged.connect(self.save_settings)
        row_opts.addWidget(self.combo_format, 1)

        layout_dest.addLayout(row_opts)

        pattern_desc = QLabel("Variables: {type} = gesture shape, {date} = YYYYMMDD, {time} = HHMMSS")
        pattern_desc.setStyleSheet("color: #888888; font-size: 11px;")
        layout_dest.addWidget(pattern_desc)

        main_layout.addWidget(grp_dest)

        # Auto-Delete Retention Box
        grp_retention = QGroupBox("Retention & Cleanup")
        layout_ret = QVBoxLayout(grp_retention)
        layout_ret.setSpacing(10)

        self.chk_autodelete = QCheckBox("Enable auto-deletion of older captures")
        self.chk_autodelete.stateChanged.connect(self.on_autodelete_toggled)
        layout_ret.addWidget(self.chk_autodelete)

        row_days = QHBoxLayout()
        row_days.addWidget(QLabel("Delete captures older than:"))
        self.spin_days = QSpinBox()
        self.spin_days.setRange(1, 365)
        self.spin_days.setValue(30)
        self.spin_days.setSuffix(" days")
        self.spin_days.valueChanged.connect(self.save_settings)
        row_days.addWidget(self.spin_days)
        row_days.addStretch()
        layout_ret.addLayout(row_days)

        warning_lbl = QLabel("Warning: Auto-delete permanently removes files older than the retention period. Off by default.")
        warning_lbl.setStyleSheet("color: #E67E22; font-size: 11px;")
        layout_ret.addWidget(warning_lbl)

        main_layout.addWidget(grp_retention)
        main_layout.addStretch()

    def load_settings(self):
        data = self.settings_mgr.get_data()
        st = data.get("storage", {})

        self.txt_folder.setText(st.get("save_folder", ""))
        self.txt_pattern.setText(st.get("filename_pattern", "{type}_{date}_{time}"))

        fmt = st.get("image_format", "PNG")
        idx = self.combo_format.findText(fmt)
        if idx >= 0:
            self.combo_format.setCurrentIndex(idx)

        enabled = st.get("auto_delete_enabled", False)
        self.chk_autodelete.setChecked(enabled)
        self.spin_days.setEnabled(enabled)
        self.spin_days.setValue(st.get("auto_delete_days", 30))

    def browse_folder(self):
        curr = self.txt_folder.text()
        chosen = QFileDialog.getExistingDirectory(self, "Select Save Folder", curr)
        if chosen:
            self.txt_folder.setText(os.path.normpath(chosen))
            self.save_settings()

    def on_autodelete_toggled(self):
        enabled = self.chk_autodelete.isChecked()
        self.spin_days.setEnabled(enabled)
        if enabled:
            reply = QMessageBox.warning(
                self, "Enable Auto-Delete",
                "Are you sure you want to enable automatic deletion of older captures? Files will be cleaned up based on age.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.chk_autodelete.setChecked(False)
                self.spin_days.setEnabled(False)
                return
        self.save_settings()

    def save_settings(self):
        target_dir = self.txt_folder.text().strip()
        if not target_dir:
            return

        data = self.settings_mgr.get_data()
        data["storage"]["save_folder"] = target_dir
        data["storage"]["filename_pattern"] = self.txt_pattern.text().strip() or "{type}_{date}_{time}"
        data["storage"]["image_format"] = self.combo_format.currentText()
        data["storage"]["auto_delete_enabled"] = self.chk_autodelete.isChecked()
        data["storage"]["auto_delete_days"] = self.spin_days.value()

        self.settings_mgr.save(data)
