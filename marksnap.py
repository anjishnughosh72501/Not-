"""
marksnap.py - Single-Process Dev Entry Point for MarkSnap.

Provides:
- `python marksnap.py`: Launches the unified MarkSnap background application with tray and hotkeys.
- `python marksnap.py --background`: Starts quietly minimized to system tray.
- `python marksnap.py --once`: Immediate capture and annotate session for debugging.
"""

from __future__ import annotations
import sys
import os
import argparse

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtWidgets import QApplication
import mss
from PIL import Image

from settings_store import SettingsManager
from library_store import LibraryStore
from ui.main_window import MainWindow
from ui.overlay_window import AnnotateOverlayWindow


def main():
    parser = argparse.ArgumentParser(description="MarkSnap Premium Screen Capture")
    parser.add_argument("--background", action="store_true", help="Start minimized to the system tray")
    parser.add_argument("--once", action="store_true", help="Launch annotate mode once immediately")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings_mgr = SettingsManager()
    library_store = LibraryStore()

    if args.once:
        import ctypes
        u32 = ctypes.windll.user32
        vx = u32.GetSystemMetrics(76)
        vy = u32.GetSystemMetrics(77)
        vw = u32.GetSystemMetrics(78)
        vh = u32.GetSystemMetrics(79)

        with mss.mss() as sct:
            sct_img = sct.grab({"left": vx, "top": vy, "width": vw, "height": vh})
            base_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        overlay = AnnotateOverlayWindow(base_img, settings_mgr, library_store)
        overlay.closed.connect(lambda saved: app.quit())
        overlay.show()
    else:
        window = MainWindow(settings_mgr, library_store, start_hidden=args.background)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
