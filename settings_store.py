"""
settings_store.py - Atomic settings management with schema migration and debounced saving.
"""

from __future__ import annotations
import json
import os
import sys
import tempfile
import threading
import time
from typing import Dict, Any, Callable, List, Optional

CURRENT_SCHEMA_VERSION = 2

DEFAULT_SETTINGS: Dict[str, Any] = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "hotkeys": {
        "open_overlay": "ctrl+shift+d"
    },
    "launcher": {
        "show_floating_button": True,
        "size": "M",                    # "S" (40px), "M" (52px), "L" (64px)
        "opacity": 85,                  # 30 to 100%
        "idle_fade": True,              # Dims to 40% after 3s idle
        "snap_edges": True,
        "hide_fullscreen": True
    },
    "gestures": {
        "box": {
            "enabled": True,
            "action": "save_region"
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
        "sensitivity": 50,
        "close_after_gesture": False    # Default: stay in annotate mode so user can keep working
    },
    "appearance": {
        "theme_mode": "system",         # "system", "dark", "light"
        "scrim_dim": 18,                # 0 to 40% dark overlay
        "frosted_blur": False,          # Optional light blur computed off main thread
        "accent_glow": True,            # Subtle accent border pulse
        "show_hints": True,             # Mode pill & key hints
        "play_sound": False,            # Optional soft notification chime
        "ink_color": "#6366F1",         # Refined Indigo
        "gesture_color": "#00E5FF",
        "stroke_width": 3,
        "show_toast": True,
        "flash_shape": True,
        "toast_position": "bottom-right",
        "toast_duration": 2500
    },
    "storage": {
        "save_folder": os.path.join(os.path.expanduser("~"), "Pictures", "MarkSnap"),
        "filename_pattern": "{type}_{date}_{time}",
        "image_format": "PNG",          # "PNG" or "JPG"
        "auto_delete_enabled": False,
        "auto_delete_days": 30
    },
    "ai": {
        "model": "claude-3-5-sonnet-20241022",
        "default_prompt": "Explain this screen region clearly and concisely."
    },
    "general": {
        "start_on_login": False,
        "open_library_on_launch": False,
        "first_run_completed": False,
        "paused": False
    }
}


def get_default_settings_path() -> str:
    app_dir = os.path.join(os.path.expanduser("~"), ".marksnap")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "settings.json")


def migrate_settings(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate older schema versions to CURRENT_SCHEMA_VERSION non-destructively."""
    version = raw.get("schema_version", 1)
    data = json.loads(json.dumps(raw))

    if version < 2:
        # Migrate version 1 -> 2
        data["schema_version"] = 2
        if "launcher" not in data:
            data["launcher"] = json.loads(json.dumps(DEFAULT_SETTINGS["launcher"]))
        if "appearance" in data:
            data["appearance"].setdefault("theme_mode", "system")
            data["appearance"].setdefault("scrim_dim", 18)
            data["appearance"].setdefault("frosted_blur", False)
            data["appearance"].setdefault("accent_glow", True)
        if "gestures" in data:
            data["gestures"].setdefault("close_after_gesture", False)
        if "general" in data:
            data["general"].setdefault("first_run_completed", False)

    return data


class SettingsManager:
    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or get_default_settings_path()
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._last_mtime = 0.0
        self._debounce_timer: Optional[threading.Timer] = None
        self._pending_data: Optional[Dict[str, Any]] = None

        self._data: Dict[str, Any] = self._load()

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
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
                    migrated = migrate_settings(content)
                    return self._merge_defaults(migrated, DEFAULT_SETTINGS)
            except Exception as e:
                print(f"[SettingsManager] Error loading {self.filepath}: {e}, using defaults.")

        self._save_atomic(DEFAULT_SETTINGS)
        return json.loads(json.dumps(DEFAULT_SETTINGS))

    def save(self, data: Dict[str, Any], debounce_ms: int = 0) -> None:
        """
        Save settings. If debounce_ms > 0, debounces disk write to avoid disk thrashing.
        """
        with self._lock:
            self._data = data

        if debounce_ms <= 0:
            self._flush_save(data)
        else:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._pending_data = data
            self._debounce_timer = threading.Timer(debounce_ms / 1000.0, lambda: self._flush_save(self._pending_data))
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _flush_save(self, data: Optional[Dict[str, Any]]) -> None:
        if data is None:
            return
        with self._lock:
            self._save_atomic(data)
            if os.path.exists(self.filepath):
                self._last_mtime = os.path.getmtime(self.filepath)
        self._notify_callbacks()

    def _save_atomic(self, data: Dict[str, Any]) -> None:
        dir_name = os.path.dirname(self.filepath)
        os.makedirs(dir_name, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.filepath)
        self._last_mtime = os.path.getmtime(self.filepath)

    def add_change_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)

    def _notify_callbacks(self) -> None:
        data_copy = self.get_data()
        for cb in self._callbacks:
            try:
                cb(data_copy)
            except Exception as e:
                print(f"[SettingsManager] Callback error: {e}")
