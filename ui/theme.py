"""
ui/theme.py - Backwards compatibility bridge and dynamic theme monitoring.
"""

from __future__ import annotations
from ui.design import is_windows_dark_mode, generate_stylesheet, get_tokens

DARK_STYLESHEET = generate_stylesheet("dark")
LIGHT_STYLESHEET = generate_stylesheet("light")
