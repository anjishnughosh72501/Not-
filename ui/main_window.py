"""
ui/main_window.py - Single-instance PySide6 companion window for MarkSnap.
"""

from __future__ import annotations
import sys
import os

# Add project root directory to sys.path so ui/ scripts can run directly from any folder
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QSystemTrayIcon, QMenu
)
from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtGui import QIcon, QAction, QPixmap, QColor, QPainter

from settings_store import SettingsManager
from library_store import LibraryStore
from ui.theme import is_windows_dark_mode, DARK_STYLESHEET, LIGHT_STYLESHEET
from ui.library_tab import LibraryTab
from ui.hotkeys_tab import HotkeysTab
from ui.gestures_tab import GesturesTab
from ui.appearance_tab import AppearanceTab
from ui.storage_tab import StorageTab
from ui.ai_tab import AITab
from ui.general_tab import GeneralTab


def create_tray_icon_pixmap() -> QPixmap:
    """Generates a clean vector-like tray icon on the fly."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    # Cyan rounded badge
    painter.setBrush(QColor("#00E5FF"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)

    # Inner camera/snap 'M' mark
    painter.setPen(QColor("#111111"))
    painter.setBrush(Qt.NoBrush)
    painter.drawText(pix.rect(), Qt.AlignCenter, "M")
    painter.end()
    return pix


class MainWindow(QMainWindow):
    def __init__(self, settings_mgr: SettingsManager, library_store: LibraryStore):
        super().__init__()
        self.settings_mgr = settings_mgr
        self.library_store = library_store

        self.setWindowTitle("MarkSnap Companion")
        self.resize(1000, 680)
        self.setMinimumSize(850, 550)

        # Apply Theme
        if is_windows_dark_mode():
            self.setStyleSheet(DARK_STYLESHEET)
        else:
            self.setStyleSheet(LIGHT_STYLESHEET)

        self._setup_ui()
        self._setup_tray()

    def _setup_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Tabs
        self.library_tab = LibraryTab(self.library_store, self.settings_mgr)
        self.hotkeys_tab = HotkeysTab(self.settings_mgr)
        self.gestures_tab = GesturesTab(self.settings_mgr)
        self.appearance_tab = AppearanceTab(self.settings_mgr)
        self.storage_tab = StorageTab(self.settings_mgr)
        self.ai_tab = AITab(self.settings_mgr)
        self.general_tab = GeneralTab(self.settings_mgr)

        self.tabs.addTab(self.library_tab, "Library")
        self.tabs.addTab(self.hotkeys_tab, "Hotkeys")
        self.tabs.addTab(self.gestures_tab, "Gestures")
        self.tabs.addTab(self.appearance_tab, "Appearance")
        self.tabs.addTab(self.storage_tab, "Storage")
        self.tabs.addTab(self.ai_tab, "AI Vision")
        self.tabs.addTab(self.general_tab, "General")

        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _setup_tray(self):
        icon = QIcon(create_tray_icon_pixmap())
        self.setWindowIcon(icon)

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("MarkSnap Companion")

        tray_menu = QMenu()
        act_open = QAction("Open MarkSnap", self)
        act_open.triggered.connect(self.show_and_focus)
        tray_menu.addAction(act_open)

        tray_menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(act_quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_and_focus()

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # Minimize to tray instead of quitting companion app
        event.ignore()
        self.hide()
        if self.tray.isVisible():
            self.tray.showMessage(
                "MarkSnap",
                "MarkSnap is still running in the background. Click the tray icon to reopen.",
                QSystemTrayIcon.Information,
                1500
            )


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Enforce Single-Instance using QSharedMemory
    shared_mem = QSharedMemory("MarkSnapCompanionSingleInstanceKey")
    if not shared_mem.create(1):
        # Another instance already running
        print("[MarkSnap UI] Another instance of MarkSnap Companion is already running.")
        sys.exit(0)

    settings_mgr = SettingsManager()
    library_store = LibraryStore()

    window = MainWindow(settings_mgr, library_store)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
