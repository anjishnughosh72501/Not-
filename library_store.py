"""
library_store.py - Index management and search for MarkSnap captures.

Maintains library.json:
- Captures metadata: id, filename, filepath, type, timestamp, ocr_text, tags, thumbnail_path
- Rebuild index to synchronize folder state
- Instant text/tag/type search
"""

from __future__ import annotations
import os
import json
import uuid
import tempfile
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from PIL import Image

THUMBNAIL_SIZE = (240, 160)


def get_default_library_path() -> str:
    app_dir = os.path.join(os.path.expanduser("~"), ".marksnap")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "library.json")


def get_thumbnails_dir() -> str:
    thumbs_dir = os.path.join(os.path.expanduser("~"), ".marksnap", "thumbnails")
    os.makedirs(thumbs_dir, exist_ok=True)
    return thumbs_dir


class LibraryStore:
    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or get_default_library_path()
        self.thumbs_dir = get_thumbnails_dir()
        self._lock = threading.Lock()
        self.items: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[LibraryStore] Error loading {self.filepath}: {e}")
        return []

    def _save_atomic(self) -> None:
        dir_name = os.path.dirname(self.filepath)
        os.makedirs(dir_name, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(self.items, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.filepath)

    def generate_thumbnail(self, image_path: str, item_id: str) -> Optional[str]:
        if not os.path.exists(image_path):
            return None
        try:
            thumb_path = os.path.join(self.thumbs_dir, f"{item_id}.jpg")
            with Image.open(image_path) as img:
                img_copy = img.copy()
                img_copy.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                # Convert RGBA to RGB for JPEG thumb
                if img_copy.mode in ("RGBA", "P"):
                    img_copy = img_copy.convert("RGB")
                img_copy.save(thumb_path, "JPEG", quality=85)
            return thumb_path
        except Exception as e:
            print(f"[LibraryStore] Failed thumbnail generation for {image_path}: {e}")
            return None

    def add_capture(
        self,
        filepath: str,
        capture_type: str,
        ocr_text: str = "",
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Record a new capture into the library."""
        with self._lock:
            item_id = str(uuid.uuid4())
            stat = os.stat(filepath) if os.path.exists(filepath) else None
            timestamp = datetime.now().isoformat()
            thumb_path = self.generate_thumbnail(filepath, item_id) or ""

            entry: Dict[str, Any] = {
                "id": item_id,
                "filename": os.path.basename(filepath),
                "filepath": os.path.abspath(filepath),
                "type": capture_type,  # "box", "circle", "underline", "arrow", "manual"
                "timestamp": timestamp,
                "file_size": stat.st_size if stat else 0,
                "ocr_text": ocr_text or "",
                "tags": tags or [],
                "thumbnail_path": thumb_path
            }
            # Insert newest first
            self.items.insert(0, entry)
            self._save_atomic()
            return entry

    def update_item(self, item_id: str, tags: Optional[List[str]] = None, ocr_text: Optional[str] = None, filename: Optional[str] = None) -> bool:
        with self._lock:
            for item in self.items:
                if item["id"] == item_id:
                    if tags is not None:
                        item["tags"] = tags
                    if ocr_text is not None:
                        item["ocr_text"] = ocr_text
                    if filename is not None:
                        item["filename"] = filename
                        item["filepath"] = os.path.join(os.path.dirname(item["filepath"]), filename)
                    self._save_atomic()
                    return True
        return False

    def remove_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for i, item in enumerate(self.items):
                if item["id"] == item_id:
                    removed = self.items.pop(i)
                    if removed.get("thumbnail_path") and os.path.exists(removed["thumbnail_path"]):
                        try:
                            os.remove(removed["thumbnail_path"])
                        except Exception:
                            pass
                    self._save_atomic()
                    return removed
        return None

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.items)

    def search(
        self,
        query: str = "",
        gesture_type: str = "all",
        tag: str = "",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = []
            q = query.strip().lower()
            tag_filter = tag.strip().lower()

            for item in self.items:
                # Gesture filter
                if gesture_type != "all" and item.get("type", "").lower() != gesture_type.lower():
                    continue

                # Tag filter
                if tag_filter:
                    item_tags = [t.lower() for t in item.get("tags", [])]
                    if tag_filter not in item_tags:
                        continue

                # Date filter
                if date_from or date_to:
                    try:
                        ts = datetime.fromisoformat(item["timestamp"])
                        if date_from and ts < date_from:
                            continue
                        if date_to and ts > date_to:
                            continue
                    except Exception:
                        pass

                # Query filter (matches filename, tags, or OCR text)
                if q:
                    filename_match = q in item.get("filename", "").lower()
                    ocr_match = q in item.get("ocr_text", "").lower()
                    tags_match = any(q in t.lower() for t in item.get("tags", []))
                    if not (filename_match or ocr_match or tags_match):
                        continue

                results.append(item)
            return results

    def rebuild_index(self, save_folder: str) -> int:
        """
        Scans save_folder, adds any unindexed image files, removes missing ones,
        and regenerates thumbnails. Returns the count of active indexed items.
        """
        with self._lock:
            if not os.path.exists(save_folder):
                self.items = []
                self._save_atomic()
                return 0

            # Existing paths mapped by normalized abspath
            existing_by_path = {os.path.normpath(item["filepath"]): item for item in self.items}
            new_items: List[Dict[str, Any]] = []

            # Scan directory for image files
            valid_exts = {".png", ".jpg", ".jpeg"}
            for root, _, files in os.walk(save_folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in valid_exts:
                        full_p = os.path.normpath(os.path.join(root, f))
                        if full_p in existing_by_path:
                            entry = existing_by_path[full_p]
                            # Check thumbnail existence
                            if not entry.get("thumbnail_path") or not os.path.exists(entry["thumbnail_path"]):
                                entry["thumbnail_path"] = self.generate_thumbnail(full_p, entry["id"]) or ""
                            new_items.append(entry)
                        else:
                            # Brand new item found on disk
                            stat = os.stat(full_p)
                            item_id = str(uuid.uuid4())
                            # Infer gesture type from prefix if present
                            lower_f = f.lower()
                            c_type = "manual"
                            for prefix in ("box", "circle", "underline", "arrow"):
                                if lower_f.startswith(prefix):
                                    c_type = prefix
                                    break

                            thumb_p = self.generate_thumbnail(full_p, item_id) or ""
                            entry = {
                                "id": item_id,
                                "filename": f,
                                "filepath": full_p,
                                "type": c_type,
                                "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "file_size": stat.st_size,
                                "ocr_text": "",
                                "tags": [],
                                "thumbnail_path": thumb_p
                            }
                            new_items.append(entry)

            # Sort newest first by timestamp
            new_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            self.items = new_items
            self._save_atomic()
            return len(self.items)
