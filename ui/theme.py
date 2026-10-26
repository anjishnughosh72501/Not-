"""
ui/theme.py - Dark / Light theme detection and styles for MarkSnap companion app.
"""

from __future__ import annotations
import sys

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


DARK_STYLESHEET = """
QWidget {
    background-color: #202020;
    color: #F0F0F0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #333333;
    background: #252525;
    top: -1px;
}

QTabBar::tab {
    background: #1A1A1A;
    color: #AAAAAA;
    padding: 8px 16px;
    border: 1px solid #333333;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #252525;
    color: #00E5FF;
    border-top: 2px solid #00E5FF;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background: #282828;
    color: #FFFFFF;
}

QPushButton {
    background-color: #333333;
    color: #FFFFFF;
    border: 1px solid #444444;
    padding: 6px 14px;
    border-radius: 4px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #404040;
    border-color: #00E5FF;
}

QPushButton:pressed {
    background-color: #007ACC;
}

QPushButton:disabled {
    background-color: #262626;
    color: #666666;
    border-color: #333333;
}

QLineEdit, QComboBox, QSpinBox, QTextEdit {
    background-color: #2C2C2C;
    color: #FFFFFF;
    border: 1px solid #3D3D3D;
    padding: 5px 8px;
    border-radius: 4px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #00E5FF;
}

QGroupBox {
    border: 1px solid #383838;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #00E5FF;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #555555;
    background-color: #2C2C2C;
}

QCheckBox::indicator:checked {
    background-color: #007ACC;
    border-color: #00E5FF;
}

QScrollBar:vertical {
    border: none;
    background: #202020;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #444444;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #666666;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #F8F9FA;
    color: #212529;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #CED4DA;
    background: #FFFFFF;
    top: -1px;
}

QTabBar::tab {
    background: #E9ECEF;
    color: #495057;
    padding: 8px 16px;
    border: 1px solid #CED4DA;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    color: #0066CC;
    border-top: 2px solid #0066CC;
    font-weight: bold;
}

QPushButton {
    background-color: #E9ECEF;
    color: #212529;
    border: 1px solid #CED4DA;
    padding: 6px 14px;
    border-radius: 4px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #DEE2E6;
    border-color: #0066CC;
}

QPushButton:pressed {
    background-color: #0066CC;
    color: #FFFFFF;
}

QLineEdit, QComboBox, QSpinBox, QTextEdit {
    background-color: #FFFFFF;
    color: #212529;
    border: 1px solid #CED4DA;
    padding: 5px 8px;
    border-radius: 4px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #0066CC;
}

QGroupBox {
    border: 1px solid #DEE2E6;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #0066CC;
}
"""
