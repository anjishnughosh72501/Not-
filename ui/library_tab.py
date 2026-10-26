"""
ui/library_tab.py - Capture browser with thumbnail grid, filters, search, and preview.
"""

from __future__ import annotations
import os
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QScrollArea, QGridLayout, QFrame, QMenu, QMessageBox,
    QInputDialog, QApplication, QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QClipboard, QAction

import send2trash

from library_store import LibraryStore
from settings_store import SettingsManager


BADGE_COLORS = {
    "box": "#4CAF50",
    "circle": "#00BCD4",
    "underline": "#FF9800",
    "arrow": "#E91E63",
    "manual": "#9C27B0"
}


class ThumbnailCard(QFrame):
    clicked = Signal(str, object)  # item_id, mouse event

    def __init__(self, item: Dict[str, Any], is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.item = item
        self.item_id = item["id"]
        self.is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(210, 180)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Image preview
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setFixedSize(198, 115)
        self.img_lbl.setStyleSheet("background-color: #181818; border-radius: 4px;")

        thumb_p = self.item.get("thumbnail_path")
        if thumb_p and os.path.exists(thumb_p):
            pix = QPixmap(thumb_p)
            scaled = pix.scaled(self.img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_lbl.setPixmap(scaled)
        elif os.path.exists(self.item.get("filepath", "")):
            pix = QPixmap(self.item["filepath"])
            scaled = pix.scaled(self.img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_lbl.setPixmap(scaled)
        else:
            self.img_lbl.setText("Image not found")

        layout.addWidget(self.img_lbl)

        # Badge and filename row
        info_row = QHBoxLayout()
        info_row.setSpacing(6)

        c_type = self.item.get("type", "manual")
        badge_color = BADGE_COLORS.get(c_type, "#777777")

        badge = QLabel(f" {c_type.upper()} ")
        badge.setStyleSheet(f"background-color: {badge_color}; color: white; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px;")
        info_row.addWidget(badge)

        name = self.item.get("filename", "")
        if len(name) > 18:
            name = name[:16] + "..."
        self.title_lbl = QLabel(name)
        self.title_lbl.setStyleSheet("font-weight: 500; font-size: 11px;")
        info_row.addWidget(self.title_lbl, 1)

        layout.addLayout(info_row)
        self.update_style()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()

    def update_style(self):
        if self.is_selected:
            self.setStyleSheet("QFrame { background-color: #2D3A4B; border: 2px solid #00E5FF; border-radius: 6px; }")
        else:
            self.setStyleSheet("QFrame { background-color: #262626; border: 1px solid #383838; border-radius: 6px; } QFrame:hover { border-color: #666666; }")

    def mousePressEvent(self, event):
        self.clicked.emit(self.item_id, event)


class LibraryTab(QWidget):
    def __init__(self, library_store: LibraryStore, settings_mgr: SettingsManager, parent=None):
        super().__init__(parent)
        self.library = library_store
        self.settings_mgr = settings_mgr
        self.selected_ids: List[str] = []
        self.current_preview_item: Optional[Dict[str, Any]] = None

        self._setup_ui()
        self.refresh_items()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top Control Bar (Search, Filters, Rebuild)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search filenames, tags, or OCR text...")
        self.search_box.textChanged.connect(self.on_filter_changed)
        top_bar.addWidget(self.search_box, 3)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Gestures", "Box", "Circle", "Underline", "Arrow", "Manual"])
        self.type_combo.currentIndexChanged.connect(self.on_filter_changed)
        top_bar.addWidget(self.type_combo, 1)

        self.tag_box = QLineEdit()
        self.tag_box.setPlaceholderText("Filter tag...")
        self.tag_box.textChanged.connect(self.on_filter_changed)
        top_bar.addWidget(self.tag_box, 1)

        self.btn_rebuild = QPushButton("Rebuild Index")
        self.btn_rebuild.setToolTip("Rescan capture folder to sync outside changes")
        self.btn_rebuild.clicked.connect(self.rebuild_index)
        top_bar.addWidget(self.btn_rebuild)

        main_layout.addLayout(top_bar)

        # Splitter: Left Grid, Right Preview Pane
        self.splitter = QSplitter(Qt.Horizontal)

        # Left Container (Thumbnail Scroll Area)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #333333; background: #1C1C1C; }")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(self.grid_container)

        left_layout.addWidget(self.scroll)
        self.splitter.addWidget(left_container)

        # Right Container (Detailed Preview & Actions)
        self.preview_panel = QFrame()
        self.preview_panel.setStyleSheet("QFrame { background-color: #242424; border: 1px solid #333333; border-radius: 6px; }")
        self._setup_preview_panel()
        self.splitter.addWidget(self.preview_panel)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        main_layout.addWidget(self.splitter, 1)

    def _setup_preview_panel(self):
        layout = QVBoxLayout(self.preview_panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.preview_title = QLabel("Select a capture to inspect")
        self.preview_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00E5FF;")
        layout.addWidget(self.preview_title)

        # Large image view
        self.large_preview = QLabel()
        self.large_preview.setAlignment(Qt.AlignCenter)
        self.large_preview.setMinimumSize(250, 180)
        self.large_preview.setStyleSheet("background-color: #151515; border-radius: 4px;")
        layout.addWidget(self.large_preview)

        # Action Buttons
        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)

        self.btn_copy_img = QPushButton("Copy Image")
        self.btn_copy_img.clicked.connect(self.copy_image_action)
        btn_grid.addWidget(self.btn_copy_img, 0, 0)

        self.btn_copy_txt = QPushButton("Copy OCR Text")
        self.btn_copy_txt.clicked.connect(self.copy_ocr_action)
        btn_grid.addWidget(self.btn_copy_txt, 0, 1)

        self.btn_open_file = QPushButton("Open File")
        self.btn_open_file.clicked.connect(self.open_file_action)
        btn_grid.addWidget(self.btn_open_file, 1, 0)

        self.btn_show_folder = QPushButton("Show in Folder")
        self.btn_show_folder.clicked.connect(self.show_in_folder_action)
        btn_grid.addWidget(self.btn_show_folder, 1, 1)

        self.btn_rename = QPushButton("Rename")
        self.btn_rename.clicked.connect(self.rename_action)
        btn_grid.addWidget(self.btn_rename, 2, 0)

        self.btn_add_tag = QPushButton("Add Tag")
        self.btn_add_tag.clicked.connect(self.add_tag_action)
        btn_grid.addWidget(self.btn_add_tag, 2, 1)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet("QPushButton { background-color: #A93226; color: white; } QPushButton:hover { background-color: #C0392B; }")
        self.btn_delete.clicked.connect(self.delete_action)
        btn_grid.addWidget(self.btn_delete, 3, 0, 1, 2)

        layout.addLayout(btn_grid)

        # Metadata & OCR Text display
        self.meta_lbl = QLabel("")
        self.meta_lbl.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        layout.addWidget(self.meta_lbl)

        layout.addWidget(QLabel("OCR Detected Text:"))
        self.ocr_display = QTextEdit()
        self.ocr_display.setReadOnly(True)
        self.ocr_display.setMaximumHeight(90)
        layout.addWidget(self.ocr_display)

    def refresh_items(self):
        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        q = self.search_box.text()
        raw_type = self.type_combo.currentText()
        gesture_type = "all" if raw_type == "All Gestures" else raw_type.lower()
        tag = self.tag_box.text()

        items = self.library.search(query=q, gesture_type=gesture_type, tag=tag)

        cols = 3
        for idx, it in enumerate(items):
            row = idx // cols
            col = idx % cols
            is_sel = it["id"] in self.selected_ids
            card = ThumbnailCard(it, is_selected=is_sel)
            card.clicked.connect(self.on_card_clicked)
            self.grid_layout.addWidget(card, row, col)

        if items and not self.current_preview_item:
            self.show_preview(items[0])

    def on_filter_changed(self):
        self.refresh_items()

    def on_card_clicked(self, item_id: str, event):
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        shift = bool(event.modifiers() & Qt.ShiftModifier)

        if ctrl:
            if item_id in self.selected_ids:
                self.selected_ids.remove(item_id)
            else:
                self.selected_ids.append(item_id)
        else:
            self.selected_ids = [item_id]

        # Update card visuals
        all_items = self.library.get_all()
        target_item = None
        for it in all_items:
            if it["id"] == item_id:
                target_item = it
                break

        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, ThumbnailCard):
                w.set_selected(w.item_id in self.selected_ids)

        if target_item:
            self.show_preview(target_item)

    def show_preview(self, item: Dict[str, Any]):
        self.current_preview_item = item
        self.preview_title.setText(item.get("filename", "Capture Preview"))

        f_path = item.get("filepath", "")
        if os.path.exists(f_path):
            pix = QPixmap(f_path)
            scaled = pix.scaled(self.large_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.large_preview.setPixmap(scaled)
        else:
            self.large_preview.setText("File not on disk")

        tags_str = ", ".join(item.get("tags", [])) or "None"
        ts = item.get("timestamp", "")
        size_kb = item.get("file_size", 0) / 1024.0
        self.meta_lbl.setText(f"Date: {ts[:19]}\nSize: {size_kb:.1f} KB\nTags: {tags_str}")

        self.ocr_display.setText(item.get("ocr_text", "(No OCR text stored)"))

    def copy_image_action(self):
        if not self.current_preview_item:
            return
        p = self.current_preview_item.get("filepath", "")
        if os.path.exists(p):
            QApplication.clipboard().setImage(QImage(p))
            QMessageBox.information(self, "Copied", "Image copied to system clipboard.")

    def copy_ocr_action(self):
        if not self.current_preview_item:
            return
        txt = self.current_preview_item.get("ocr_text", "")
        if txt:
            QApplication.clipboard().setText(txt)
            QMessageBox.information(self, "Copied", "OCR text copied to clipboard.")
        else:
            QMessageBox.warning(self, "No Text", "No OCR text detected for this capture.")

    def open_file_action(self):
        if not self.current_preview_item:
            return
        p = self.current_preview_item.get("filepath", "")
        if os.path.exists(p):
            os.startfile(p)

    def show_in_folder_action(self):
        if not self.current_preview_item:
            return
        p = self.current_preview_item.get("filepath", "")
        if os.path.exists(p):
            subprocess.run(["explorer", "/select,", os.path.normpath(p)])

    def rename_action(self):
        if not self.current_preview_item:
            return
        old_name = self.current_preview_item.get("filename", "")
        new_name, ok = QInputDialog.getText(self, "Rename Capture", "Enter new filename:", text=old_name)
        if ok and new_name.strip() and new_name != old_name:
            old_p = self.current_preview_item.get("filepath", "")
            new_p = os.path.join(os.path.dirname(old_p), new_name)
            try:
                os.rename(old_p, new_p)
                self.library.update_item(self.current_preview_item["id"], filename=new_name)
                self.current_preview_item["filename"] = new_name
                self.current_preview_item["filepath"] = new_p
                self.refresh_items()
                self.show_preview(self.current_preview_item)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename: {e}")

    def add_tag_action(self):
        if not self.current_preview_item:
            return
        tag, ok = QInputDialog.getText(self, "Add Tag", "Tag name:")
        if ok and tag.strip():
            tags = list(self.current_preview_item.get("tags", []))
            if tag.strip() not in tags:
                tags.append(tag.strip())
                self.library.update_item(self.current_preview_item["id"], tags=tags)
                self.current_preview_item["tags"] = tags
                self.refresh_items()
                self.show_preview(self.current_preview_item)

    def delete_action(self):
        targets = list(self.selected_ids)
        if not targets and self.current_preview_item:
            targets = [self.current_preview_item["id"]]
        if not targets:
            return

        cnt = len(targets)
        reply = QMessageBox.question(
            self, "Recycle Bin",
            f"Are you sure you want to move {cnt} capture{'s' if cnt > 1 else ''} to the Recycle Bin?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            all_items = {it["id"]: it for it in self.library.get_all()}
            for item_id in targets:
                if item_id in all_items:
                    fpath = all_items[item_id].get("filepath", "")
                    if os.path.exists(fpath):
                        try:
                            send2trash.send2trash(os.path.normpath(fpath))
                        except Exception as e:
                            print(f"[Library] send2trash error: {e}")
                    self.library.remove_item(item_id)

            self.selected_ids.clear()
            self.current_preview_item = None
            self.refresh_items()
            QMessageBox.information(self, "Deleted", "Items moved to the Recycle Bin.")

    def rebuild_index(self):
        save_folder = self.settings_mgr.get("storage.save_folder")
        count = self.library.rebuild_index(save_folder)
        self.refresh_items()
        QMessageBox.information(self, "Index Rebuilt", f"Indexed {count} capture files in '{save_folder}'.")
