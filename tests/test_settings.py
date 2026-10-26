"""
tests/test_settings.py - Automated tests for schema migration and debounced saving.
"""

import os
import json
import tempfile
import time
from settings_store import SettingsManager, migrate_settings, CURRENT_SCHEMA_VERSION

def test_migration_v1_to_v2():
    v1_data = {
        "hotkeys": {"open_overlay": "ctrl+shift+d"},
        "appearance": {"ink_color": "#FF0000"}
    }
    migrated = migrate_settings(v1_data)
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "launcher" in migrated
    assert migrated["launcher"]["show_floating_button"] is True
    assert migrated["appearance"]["scrim_dim"] == 18
    assert migrated["appearance"]["ink_color"] == "#FF0000"

def test_settings_debounced_save():
    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        path = tf.name
    try:
        mgr = SettingsManager(path)
        data = mgr.get_data()
        data["appearance"]["stroke_width"] = 9
        mgr.save(data, debounce_ms=100)
        
        # Immediate read from file before debounce completes
        with open(path, "r") as f:
            raw = json.load(f)
        assert raw["appearance"]["stroke_width"] != 9
        
        # Wait for debounce timer
        time.sleep(0.2)
        with open(path, "r") as f:
            raw2 = json.load(f)
        assert raw2["appearance"]["stroke_width"] == 9
    finally:
        if os.path.exists(path):
            os.remove(path)
