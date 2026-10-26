"""
run_companion.py - Root entry point for MarkSnap Companion App.
"""

from __future__ import annotations
import sys
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.main_window import main

if __name__ == "__main__":
    main()
