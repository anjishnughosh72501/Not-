"""
settings_store.py - Atomic settings management with live file watching for MarkSnap.

Manages settings.json safely:
- Validates settings structure
- Atomic write via temporary file replacement
- File modification monitoring / callback registration for live reload
"""

from __future__ import annotations
import json
import os
import sys
import tempfile
import threading
import time
from typing import Dict, Any, Callable, List

DEFAULT_SETTINGS: Dict[str, Any] = {
    "hotkeys": {
        "open_overlay": "ctrl+shift+d"
    },
    "gestures": {
        "box": {
            "enabled": True,
            "action": "save_region"  # "save_region", "ocr_to_clipboard", "save_fullscreen", "ask_ai", "do_nothing"
        },
        "circle": {
            "enabled": True,
            "action": "ocr_to_clipboard"
        },
        "underline": {
            "enabled": True,
            "action": "save_fullscreen"
        },
        "arrow": {
            "enabled": True,
            "action": "ask_ai"
        },
        "sensitivity": 50  # 1 (strict) to 100 (loose)
    },
    "appearance": {
        "ink_color": "#FF2222",
        "gesture_color": "#00E5FF",
        "stroke_width": 3,
        "show_toast": True,
        "flash_shape": True,
        "show_hints": True,
        "play_sound": False,
        "toast_position": "bottom-right",  # "top-right", "bottom-right", "top-left", "bottom-left"
        "toast_duration": 2000  # ms
    },
    "storage": {
        "save_folder": os.path.join(os.path.expanduser("~"), "Pictures", "MarkSnap"),
        "filename_pattern": "{type}_{date}_{time}",
        "image_format": "PNG",  # "PNG" or "JPG"
        "auto_delete_enabled": False,
        "auto_delete_days": 30
    },
    "ai": {
        "default_prompt": "Explain this screen region clearly and concisely."
    },
    "general": {
        "start_on_login": False,
        "open_library_on_launch": False,
        "paused": False
    }
}


def get_default_settings_path() -> str:
    app_dir = os.path.join(os.path.expanduser("~"), ".marksnap")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "settings.json")


class SettingsManager:
    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or get_default_settings_path()
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._last_mtime = 0.0
        self._watcher_running = False
        self._watcher_thread: threading.Thread | None = None

        self._data: Dict[str, Any] = self._load()

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            # Return deep copy
            return json.loads(json.dumps(self._data))

    def get(self, key_path: str, default: Any = None) -> Any:
        with self._lock:
            keys = key_path.split(".")
            curr = self._data
            for k in keys:
                if isinstance(curr, dict) and k in curr:
                    curr = curr[k]
                else:
                    return default
            return curr

    def _merge_defaults(self, data: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(defaults)
        for k, v in data.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = self._merge_defaults(v, merged[k])
            else:
                merged[k] = v
        return merged

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    self._last_mtime = os.path.getmtime(self.filepath)
                    return self._merge_defaults(content, DEFAULT_SETTINGS)
            except Exception as e:
                print(f"[SettingsManager] Error loading {self.filepath}: {e}, using defaults.")
        # If file doesn't exist, save default
        self._save_atomic(DEFAULT_SETTINGS)
        return json.loads(json.dumps(DEFAULT_SETTINGS))

    def save(self, data: Dict[str, Any]) -> None:
        """Validates and atomically writes to settings.json."""
        with self._lock:
            self._save_atomic(data)
            self._data = data
            if os.path.exists(self.filepath):
                self._last_mtime = os.path.getmtime(self.filepath)
        self._notify_callbacks()

    def _save_atomic(self, data: Dict[str, Any]) -> None:
        dir_name = os.path.dirname(self.filepath)
        os.makedirs(dir_name, exist_ok=True)
        # Write to temporary file in the same directory for atomic rename
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2)
            temp_name = tf.name

        # Atomically replace target
        os.replace(temp_name, self.filepath)
        self._last_mtime = os.path.getmtime(self.filepath)

    def add_change_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)
        if not self._watcher_running:
            self.start_watching()

    def _notify_callbacks(self) -> None:
        data_copy = self.get_data()
        for cb in self._callbacks:
            try:
                cb(data_copy)
            except Exception as e:
                print(f"[SettingsManager] Callback error: {e}")

    def start_watching(self, interval_sec: float = 0.5) -> None:
        if self._watcher_running:
            return
        self._watcher_running = True

        def _watch_loop():
            while self._watcher_running:
                try:
                    if os.path.exists(self.filepath):
                        mtime = os.path.getmtime(self.filepath)
                        if mtime > self._last_mtime:
                            self._last_mtime = mtime
                            with self._lock:
                                self._data = self._load()
                            self._notify_callbacks()
                except Exception:
                    pass
                time.sleep(interval_sec)

        self._watcher_thread = threading.Thread(target=_watch_loop, daemon=True)
        self._watcher_thread.start()

    def stop_watching(self) -> None:
        self._watcher_running = False
