"""
win32_hotkey.py - Pure Win32 RegisterHotKey integration via native QAbstractNativeEventFilter.

Eliminates need for administrator privileges and prevents keyboard hooking issues.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
from typing import Dict, Callable, Optional, Tuple
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

user32 = ctypes.windll.user32

# Modifier constants for Win32 RegisterHotKey
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

# Common key mappings to virtual key codes
VK_MAP: Dict[str, int] = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "pause": 0x13, "capslock": 0x14, "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "printscreen": 0x2C,
    "insert": 0x2D, "delete": 0x2E, "del": 0x2E,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE
}

for i in range(12):
    VK_MAP[f"f{i+1}"] = 0x70 + i


def parse_hotkey_string(hotkey_str: str) -> Optional[Tuple[int, int]]:
    """Parse 'ctrl+shift+d' into (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        return None

    mods = MOD_NOREPEAT
    key_part = ""

    for p in parts:
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p in ("shift",):
            mods |= MOD_SHIFT
        elif p in ("alt",):
            mods |= MOD_ALT
        elif p in ("win", "windows", "super"):
            mods |= MOD_WIN
        else:
            key_part = p

    if not key_part:
        return None

    vk = 0
    if len(key_part) == 1 and ("a" <= key_part <= "z"):
        vk = ord(key_part.upper())
    elif len(key_part) == 1 and ("0" <= key_part <= "9"):
        vk = ord(key_part)
    elif key_part in VK_MAP:
        vk = VK_MAP[key_part]
    else:
        return None

    return mods, vk


class NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, handler: Callable[[int], None]):
        super().__init__()
        self.handler = handler

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG" or eventType == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                hotkey_id = int(msg.wParam)
                self.handler(hotkey_id)
                return True, 0
        return False, 0


class Win32HotkeyManager(QObject):
    hotkey_triggered = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered: Dict[int, str] = {}
        self._next_id = 100
        self._native_filter = NativeHotkeyFilter(self._on_hotkey_msg)

    def get_native_filter(self) -> NativeHotkeyFilter:
        return self._native_filter

    def register(self, hotkey_str: str) -> Tuple[bool, Optional[int], str]:
        """
        Registers a global hotkey via RegisterHotKey.
        Returns (success, hotkey_id, error_message).
        """
        parsed = parse_hotkey_string(hotkey_str)
        if not parsed:
            return False, None, f"Invalid hotkey combination: '{hotkey_str}'"

        mods, vk = parsed
        hotkey_id = self._next_id
        self._next_id += 1

        success = bool(user32.RegisterHotKey(None, hotkey_id, mods, vk))
        if not success:
            err = ctypes.GetLastError()
            return False, None, f"Hotkey '{hotkey_str}' is already taken by another application (Error {err})."

        self._registered[hotkey_id] = hotkey_str
        return True, hotkey_id, ""

    def unregister(self, hotkey_id: int) -> bool:
        if hotkey_id in self._registered:
            user32.UnregisterHotKey(None, hotkey_id)
            del self._registered[hotkey_id]
            return True
        return False

    def unregister_all(self) -> None:
        for hid in list(self._registered.keys()):
            self.unregister(hid)

    def _on_hotkey_msg(self, hotkey_id: int) -> None:
        if hotkey_id in self._registered:
            self.hotkey_triggered.emit(hotkey_id)
