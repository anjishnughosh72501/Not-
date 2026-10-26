"""
ui/main_window.py - Unified Single-Process Application Shell for MarkSnap.

Features:
- Premium collapsible left sidebar with vector stroke icons:
  * Library (masonry capture browser, tags, Recycle Bin, double-click preview)
  * Capture (Hotkeys, Launcher settings, Gestures, 'Try Annotate Now' trigger)
  * Appearance (Theme override, Scrim dimming, Accent pulse, Stroke customization)
  * Storage (Folders, file patterns, format, auto-delete)
  * AI Vision (Keyring credentials, model picker, streaming vision test)
  * General (Startup, launcher toggle, pause/resume daemon)
- Integrated Win32 RegisterHotKey manager (no admin rights, no low-level hooks).
- Integrated FloatingLauncherButton with WDA_EXCLUDEFROMCAPTURE and WS_EX_NOACTIVATE.
- Live single-writer library reloading.
- System tray integration with stateful icons and action shortcuts.
"""

from __future__ import annotations
import sys
import os
from typing import Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QSystemTrayIcon, QMenu, QFrame
)
from PySide6.QtCore import Qt, QSharedMemory, QTimer
from PySide6.QtGui import QIcon, QAction, QPixmap, QColor, QPainter

import mss
from PIL import Image

from settings_store import SettingsManager
from library_store import LibraryStore
from win32_hotkey import Win32HotkeyManager
from ui.design import generate_stylesheet, get_tokens
from ui.icons import get_vector_icon
from ui.overlay_window import AnnotateOverlayWindow
from ui.launcher_button import FloatingLauncherButton
from ui.library_tab import LibraryTab
from ui.hotkeys_tab import HotkeysTab
from ui.gestures_tab import GesturesTab
from ui.appearance_tab import AppearanceTab
from ui.storage_tab import StorageTab
from ui.ai_tab import AITab
from ui.general_tab import GeneralTab


def create_tray_icon() -> QIcon:
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#6366F1"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 7, 7)
    p.setPen(QColor("#FFFFFF"))
    font = p.font()
    font.setBold(True)
    font.setPixelSize(18)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignCenter, "M")
    p.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, settings_mgr: SettingsManager, library_store: LibraryStore, start_hidden: bool = False):
        super().__init__()
        self.settings_mgr = settings_mgr
        self.library_store = library_store
        self.active_overlay: Optional[AnnotateOverlayWindow] = None

        self.setWindowTitle("MarkSnap")
        self.resize(1080, 720)
        self.setMinimumSize(900, 580)

        # Apply design system stylesheet
        theme = self.settings_mgr.get("appearance.theme_mode", "system")
        self.setStyleSheet(generate_stylesheet(theme))

        # Setup Core Subsystems
        self._setup_hotkey_manager()
        self._setup_launcher_button()
        self._setup_ui()
        self._setup_tray()

        if not start_hidden:
            self.show()

    def _setup_hotkey_manager(self):
        self.hotkey_mgr = Win32HotkeyManager(self)
        QApplication.instance().installNativeEventFilter(self.hotkey_mgr.get_native_filter())
        self.hotkey_mgr.hotkey_triggered.connect(self.trigger_annotate_mode)

        hotkey_str = self.settings_mgr.get("hotkeys.open_overlay", "ctrl+shift+d")
        success, hid, err = self.hotkey_mgr.register(hotkey_str)
        if not success:
            print(f"[MarkSnap Hotkey Warning] {err}")

    def _setup_launcher_button(self):
        cfg = self.settings_mgr.get("launcher", {})
        show_btn = cfg.get("show_floating_button", True)
        self.launcher_btn = FloatingLauncherButton(
            size_mode=cfg.get("size", "M"),
            opacity_pct=cfg.get("opacity", 85),
            idle_fade=cfg.get("idle_fade", True),
            snap_edges=cfg.get("snap_edges", True)
        )
        self.launcher_btn.clicked_annotate.connect(self.trigger_annotate_mode)
        self.launcher_btn.request_settings.connect(self.show_and_focus)

        if show_btn:
            self.launcher_btn.show()

    def _setup_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 16)
        sb_layout.setSpacing(6)

        # App Brand Header
        brand_row = QHBoxLayout()
        lbl_logo = QLabel(" MarkSnap")
        lbl_logo.setStyleSheet("font-size: 17px; font-weight: 700; color: #6366F1;")
        brand_row.addWidget(lbl_logo)
        sb_layout.addLayout(brand_row)

        sb_layout.addSpacing(14)

        # Primary Trigger Button
        self.btn_annotate_now = QPushButton(" Annotate (Ctrl+Shift+D)")
        self.btn_annotate_now.setObjectName("PrimaryButton")
        self.btn_annotate_now.setCursor(Qt.PointingHandCursor)
        self.btn_annotate_now.clicked.connect(self.trigger_annotate_mode)
        sb_layout.addWidget(self.btn_annotate_now)

        sb_layout.addSpacing(14)

        # Nav items
        self.nav_buttons = []
        nav_items = [
            ("Library", "library", 0),
            ("Capture & Keys", "camera", 1),
            ("Appearance", "pen", 2),
            ("Storage", "save", 3),
            ("AI Vision", "ai", 4),
            ("General", "settings", 5)
        ]

        for text, icon, idx in nav_items:
            btn = QPushButton(f"  {text}")
            btn.setIcon(get_vector_icon(icon, size=18))
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_tab(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # Status badge at bottom
        self.status_badge = QLabel("• Daemon Active")
        self.status_badge.setStyleSheet("color: #10B981; font-size: 11px; padding: 6px;")
        sb_layout.addWidget(self.status_badge)

        main_layout.addWidget(sidebar)

        # --- Page Stack ---
        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentPanel")

        # 0. Library Tab
        self.tab_library = LibraryTab(self.library_store, self.settings_mgr)
        self.stack.addWidget(self.tab_library)

        # 1. Capture (Combines Hotkeys and Gestures)
        tab_capture = QWidget()
        cap_layout = QVBoxLayout(tab_capture)
        cap_layout.setContentsMargins(16, 16, 16, 16)
        self.tab_hotkeys = HotkeysTab(self.settings_mgr)
        self.tab_gestures = GesturesTab(self.settings_mgr)
        cap_layout.addWidget(self.tab_hotkeys)
        cap_layout.addWidget(self.tab_gestures)
        self.stack.addWidget(tab_capture)

        # 2. Appearance
        self.tab_appearance = AppearanceTab(self.settings_mgr)
        self.stack.addWidget(self.tab_appearance)

        # 3. Storage
        self.tab_storage = StorageTab(self.settings_mgr)
        self.stack.addWidget(self.tab_storage)

        # 4. AI Vision
        self.tab_ai = AITab(self.settings_mgr)
        self.stack.addWidget(self.tab_ai)

        # 5. General
        self.tab_general = GeneralTab(self.settings_mgr)
        self.stack.addWidget(self.tab_general)

        main_layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._switch_tab(0)

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _setup_tray(self):
        icon = create_tray_icon()
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("MarkSnap Screen Capture")

        menu = QMenu()
        act_annot = menu.addAction("Annotate Screen")
        act_annot.triggered.connect(self.trigger_annotate_mode)

        act_lib = menu.addAction("Open Library")
        act_lib.triggered.connect(lambda: [self._switch_tab(0), self.show_and_focus()])

        menu.addSeparator()

        act_open = menu.addAction("Settings & Preferences")
        act_open.triggered.connect(self.show_and_focus)

        menu.addSeparator()

        act_quit = menu.addAction("Quit MarkSnap")
        act_quit.triggered.connect(QApplication.instance().quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_and_focus()

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def trigger_annotate_mode(self):
        """Freezes screen and opens the premium PySide6 Annotation overlay instantly."""
        if self.active_overlay and self.active_overlay.isVisible():
            return
        if self.settings_mgr.get("general.paused", False):
            return

        # Notify launcher button
        if hasattr(self, "launcher_btn"):
            self.launcher_btn.set_annotating_state(True)

        # Grab virtual desktop
        import ctypes
        u32 = ctypes.windll.user32
        vx = u32.GetSystemMetrics(76)
        vy = u32.GetSystemMetrics(77)
        vw = u32.GetSystemMetrics(78)
        vh = u32.GetSystemMetrics(79)

        with mss.mss() as sct:
            sct_img = sct.grab({"left": vx, "top": vy, "width": vw, "height": vh})
            base_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        self.active_overlay = AnnotateOverlayWindow(
            base_image=base_img,
            settings_mgr=self.settings_mgr,
            library_store=self.library_store
        )
        self.active_overlay.closed.connect(self._on_overlay_closed)
        self.active_overlay.show()

    def _on_overlay_closed(self, was_saved: bool):
        if hasattr(self, "launcher_btn"):
            self.launcher_btn.set_annotating_state(False)
        self.active_overlay = None

    def closeEvent(self, event):
        # Minimize to tray instead of quitting
        event.ignore()
        self.hide()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    shared_mem = QSharedMemory("MarkSnapCompanionSingleInstanceKey")
    if not shared_mem.create(1):
        print("[MarkSnap] Another instance is already active.")
        sys.exit(0)

    start_hidden = "--background" in sys.argv
    settings_mgr = SettingsManager()
    library_store = LibraryStore()

    window = MainWindow(settings_mgr, library_store, start_hidden=start_hidden)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
