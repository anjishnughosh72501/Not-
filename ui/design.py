"""
ui/design.py - Design system tokens, color palettes, and QSS generator for MarkSnap.

Follows a premium, restrained aesthetic (similar to CleanShot X and macOS Markup)
with WCAG AA contrast compliance and support for live system theme switching.
"""

from __future__ import annotations
import sys
from typing import Dict, Any

def is_windows_dark_mode() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        return True

def is_reduced_motion() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        # SPI_GETCLIENTAREAANIMATION = 0x1042
        animation = wintypes.BOOL()
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(animation), 0)
        return not animation.value
    except Exception:
        return False

# Semantic design tokens
DARK_TOKENS = {
    "bg": "#16171A",
    "surface": "#1F2024",
    "surface_raised": "#28292E",
    "surface_overlay": "#1E1F24",
    "border": "#32343A",
    "border_subtle": "#27292F",
    "border_focus": "#6366F1",
    "text": "#F3F4F6",
    "text_muted": "#9CA3AF",
    "text_dim": "#6B7280",
    "accent": "#6366F1",           # Refined Indigo
    "accent_hover": "#4F46E5",
    "accent_light": "#818CF8",
    "accent_subtle": "#2E2F45",
    "accent_glow": "rgba(99, 102, 241, 0.35)",
    "success": "#10B981",
    "success_subtle": "#14382D",
    "warning": "#F59E0B",
    "warning_subtle": "#3D2B13",
    "danger": "#EF4444",
    "danger_subtle": "#3A1B1D",
    "danger_hover": "#DC2626",
    "scrim": "rgba(0, 0, 0, 0.22)",
    "shadow": "rgba(0, 0, 0, 0.45)",
}

LIGHT_TOKENS = {
    "bg": "#F8F9FB",
    "surface": "#FFFFFF",
    "surface_raised": "#F3F4F6",
    "surface_overlay": "#FFFFFF",
    "border": "#E5E7EB",
    "border_subtle": "#F0F2F5",
    "border_focus": "#4F46E5",
    "text": "#111827",
    "text_muted": "#4B5563",
    "text_dim": "#9CA3AF",
    "accent": "#4F46E5",
    "accent_hover": "#4338CA",
    "accent_light": "#6366F1",
    "accent_subtle": "#EEF2FF",
    "accent_glow": "rgba(79, 70, 229, 0.25)",
    "success": "#059669",
    "success_subtle": "#ECFDF5",
    "warning": "#D97706",
    "warning_subtle": "#FFFBEB",
    "danger": "#DC2626",
    "danger_subtle": "#FEF2F2",
    "danger_hover": "#B91C1C",
    "scrim": "rgba(0, 0, 0, 0.16)",
    "shadow": "rgba(0, 0, 0, 0.10)",
}

def get_tokens(theme_mode: str = "system") -> Dict[str, str]:
    if theme_mode == "dark":
        return DARK_TOKENS
    elif theme_mode == "light":
        return LIGHT_TOKENS
    return DARK_TOKENS if is_windows_dark_mode() else LIGHT_TOKENS

def generate_stylesheet(theme_mode: str = "system") -> str:
    t = get_tokens(theme_mode)
    return f"""
QWidget {{
    background-color: {t["bg"]};
    color: {t["text"]};
    font-family: "Segoe UI Variable", "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
    outline: none;
}}

/* Window & Dialogs */
QMainWindow, QDialog {{
    background-color: {t["bg"]};
}}

/* Sidebar & Navigation */
#Sidebar {{
    background-color: {t["surface"]};
    border-right: 1px solid {t["border_subtle"]};
}}

#Sidebar QPushButton {{
    text-align: left;
    padding: 10px 14px;
    border-radius: 8px;
    background-color: transparent;
    color: {t["text_muted"]};
    font-weight: 500;
    border: none;
}}

#Sidebar QPushButton:hover {{
    background-color: {t["surface_raised"]};
    color: {t["text"]};
}}

#Sidebar QPushButton:checked {{
    background-color: {t["accent_subtle"]};
    color: {t["accent"]};
    font-weight: 600;
}}

/* Surface Panels */
QFrame#ContentPanel, QFrame#CardFrame {{
    background-color: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 10px;
}}

/* Buttons */
QPushButton {{
    background-color: {t["surface_raised"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    padding: 7px 15px;
    border-radius: 7px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {t["border_subtle"]};
    border-color: {t["accent"]};
    color: {t["text"]};
}}

QPushButton:pressed {{
    background-color: {t["accent_subtle"]};
    border-color: {t["accent"]};
}}

QPushButton:disabled {{
    background-color: {t["surface"]};
    color: {t["text_dim"]};
    border-color: {t["border_subtle"]};
}}

QPushButton#PrimaryButton {{
    background-color: {t["accent"]};
    color: #FFFFFF;
    border: 1px solid {t["accent_hover"]};
    font-weight: 600;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {t["accent_hover"]};
}}

QPushButton#PrimaryButton:pressed {{
    background-color: {t["accent"]};
}}

QPushButton#DangerButton {{
    background-color: {t["danger"]};
    color: #FFFFFF;
    border: none;
}}

QPushButton#DangerButton:hover {{
    background-color: {t["danger_hover"]};
}}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: {t["surface_raised"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    padding: 6px 10px;
    border-radius: 6px;
    selection-background-color: {t["accent"]};
    selection-color: #FFFFFF;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1.5px solid {t["accent"]};
    background-color: {t["surface"]};
}}

/* Group Boxes */
QGroupBox {{
    background-color: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {t["accent"]};
}}

/* Checkboxes */
QCheckBox {{
    spacing: 8px;
    color: {t["text"]};
}}

QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1.5px solid {t["border"]};
    background-color: {t["surface_raised"]};
}}

QCheckBox::indicator:hover {{
    border-color: {t["accent"]};
}}

QCheckBox::indicator:checked {{
    background-color: {t["accent"]};
    border-color: {t["accent"]};
    image: none;
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {t["border"]};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t["text_dim"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0px;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 5px;
    background: {t["border"]};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {t["accent"]};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {t["text"]};
    border: 2px solid {t["accent"]};
    width: 15px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 8px;
}}

/* Tooltips */
QToolTip {{
    background-color: {t["surface_overlay"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
}}
"""
