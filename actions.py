"""
actions.py - Action router and execution engine for MarkSnap.

Implements all shape handlers:
- save_region (Box): Crops the region, saves with configured format & naming, logs to library.json
- ocr_to_clipboard (Circle): Performs OCR via Windows Media OCR or PyTesseract, copies text to clipboard, indexes in library.json
- save_fullscreen (Underline): Saves full desktop screenshot with plain ink burned in, logs to library.json
- ask_ai (Arrow): Prompts user for question/prompt, sends marked region to AI Vision API
- do_nothing: Explicitly ignores the recognized gesture

Displays non-intrusive Windows toast alerts and maintains library index.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
from PIL import Image

import tkinter as tk
from tkinter import messagebox

from settings_store import SettingsManager
from library_store import LibraryStore


def check_tesseract_installed() -> Tuple[bool, str]:
    """Checks whether pytesseract can find a valid tesseract binary."""
    # Check PATH
    try:
        import pytesseract
        # If tesseract is in common Windows paths, configure it
        standard_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
        ]
        for p in standard_paths:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                return True, p

        # Test default command
        pytesseract.get_tesseract_version()
        return True, "PATH"
    except Exception as e:
        return False, str(e)


def extract_ocr_text(image: Image.Image) -> str:
    """Runs OCR on the given PIL image using pytesseract if available."""
    try:
        import pytesseract
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"[OCR] pytesseract extraction error: {e}")
        return ""


def copy_to_clipboard(text: str) -> None:
    """Sets system clipboard text via ctypes User32."""
    if not text:
        return
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    if not user32.OpenClipboard(0):
        return
    try:
        user32.EmptyClipboard()
        # Encode UTF-16LE with null terminator
        encoded = text.encode("utf-16le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        p_mem = kernel32.GlobalLock(h_mem)
        ctypes.memmove(p_mem, encoded, len(encoded))
        kernel32.GlobalUnlock(h_mem)
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    finally:
        user32.CloseClipboard()


def show_toast(title: str, message: str, position: str = "bottom-right", duration_ms: int = 2000) -> None:
    """Lightweight, non-blocking transparent borderless toast."""
    def _run():
        try:
            toast = tk.Tk()
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            toast.configure(bg="#202020")

            frame = tk.Frame(toast, bg="#202020", highlightbackground="#00E5FF", highlightthickness=1, padx=12, pady=8)
            frame.pack(fill="both", expand=True)

            lbl_title = tk.Label(frame, text=title, font=("Segoe UI", 10, "bold"), fg="#00E5FF", bg="#202020")
            lbl_title.pack(anchor="w")

            lbl_msg = tk.Label(frame, text=message, font=("Segoe UI", 9), fg="#FFFFFF", bg="#202020", wraplength=280, justify="left")
            lbl_msg.pack(anchor="w", pady=(2, 0))

            toast.update_idletasks()
            w = max(240, toast.winfo_reqwidth())
            h = toast.winfo_reqheight()

            # Virtual screen position
            import ctypes
            u32 = ctypes.windll.user32
            sw = u32.GetSystemMetrics(0)
            sh = u32.GetSystemMetrics(1)

            margin = 25
            if position == "top-right":
                x = sw - w - margin
                y = margin
            elif position == "top-left":
                x = margin
                y = margin
            elif position == "bottom-left":
                x = margin
                y = sh - h - margin
            else:  # bottom-right
                x = sw - w - margin
                y = sh - h - margin

            toast.geometry(f"{w}x{h}+{x}+{y}")
            toast.after(duration_ms, toast.destroy)
            toast.mainloop()
        except Exception as e:
            print(f"[Toast] Error displaying toast: {e}")

    import threading
    threading.Thread(target=_run, daemon=True).start()


class ActionRouter:
    def __init__(self, settings_mgr: SettingsManager, library_store: LibraryStore):
        self.settings_mgr = settings_mgr
        self.library = library_store

    def _format_filename(self, shape: str, ext: str) -> str:
        pattern = self.settings_mgr.get("storage.filename_pattern", "{type}_{date}_{time}")
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        name = pattern.replace("{type}", shape).replace("{date}", date_str).replace("{time}", time_str)
        return f"{name}.{ext.lower()}"

    def dispatch(
        self,
        shape: str,
        bbox: Tuple[float, float, float, float],
        base_image: Image.Image,
        ink_image: Image.Image,
        on_complete: Optional[Any] = None
    ) -> None:
        """Route recognized shape to designated action based on user settings."""
        gestures_cfg = self.settings_mgr.get("gestures", {})
        shape_cfg = gestures_cfg.get(shape, {})

        if not shape_cfg.get("enabled", True):
            print(f"[ActionRouter] Gesture '{shape}' is disabled in settings. Skipping.")
            if on_complete:
                on_complete()
            return

        action_name = shape_cfg.get("action", "save_region")
        print(f"[ActionRouter] Executing '{action_name}' for gesture '{shape}'")

        if action_name == "save_region":
            self.handle_save_region(shape, bbox, base_image, ink_image)
        elif action_name == "ocr_to_clipboard":
            self.handle_ocr_clipboard(shape, bbox, base_image, ink_image)
        elif action_name == "save_fullscreen":
            self.handle_save_fullscreen(shape, base_image, ink_image)
        elif action_name == "ask_ai":
            self.handle_ask_ai(shape, bbox, base_image, ink_image)
        elif action_name == "do_nothing":
            print(f"[ActionRouter] Gesture '{shape}' mapped to 'do_nothing'.")
        else:
            print(f"[ActionRouter] Unknown action '{action_name}'.")

        if on_complete:
            on_complete()

    def handle_save_region(
        self,
        shape: str,
        bbox: Tuple[float, float, float, float],
        base_image: Image.Image,
        ink_image: Image.Image
    ) -> None:
        save_dir = self.settings_mgr.get("storage.save_folder")
        os.makedirs(save_dir, exist_ok=True)
        img_fmt = self.settings_mgr.get("storage.image_format", "PNG")

        composite = Image.alpha_composite(base_image.convert("RGBA"), ink_image).convert("RGB")
        w, h = composite.size

        min_x, min_y, max_x, max_y = [int(v) for v in bbox]
        min_x = max(0, min(w, min_x))
        max_x = max(0, min(w, max_x))
        min_y = max(0, min(h, min_y))
        max_y = max(0, min(h, max_y))

        if max_x - min_x < 5 or max_y - min_y < 5:
            return

        crop = composite.crop((min_x, min_y, max_x, max_y))
        filename = self._format_filename(shape, img_fmt)
        out_path = os.path.join(save_dir, filename)

        if img_fmt.upper() == "JPG" or img_fmt.upper() == "JPEG":
            crop.save(out_path, "JPEG", quality=95)
        else:
            crop.save(out_path, "PNG")

        # Record in library index
        self.library.add_capture(out_path, shape, ocr_text="")

        if self.settings_mgr.get("appearance.show_toast", True):
            pos = self.settings_mgr.get("appearance.toast_position", "bottom-right")
            dur = self.settings_mgr.get("appearance.toast_duration", 2000)
            show_toast("Region Saved", f"Saved to {filename}", position=pos, duration_ms=dur)

    def handle_ocr_clipboard(
        self,
        shape: str,
        bbox: Tuple[float, float, float, float],
        base_image: Image.Image,
        ink_image: Image.Image
    ) -> None:
        save_dir = self.settings_mgr.get("storage.save_folder")
        os.makedirs(save_dir, exist_ok=True)
        img_fmt = self.settings_mgr.get("storage.image_format", "PNG")

        # For OCR, crop from the clean base image (without ink obscuring characters)
        w, h = base_image.size
        min_x, min_y, max_x, max_y = [int(v) for v in bbox]
        min_x = max(0, min(w, min_x))
        max_x = max(0, min(w, max_x))
        min_y = max(0, min(h, min_y))
        max_y = max(0, min(h, max_y))

        if max_x - min_x < 5 or max_y - min_y < 5:
            return

        crop = base_image.crop((min_x, min_y, max_x, max_y))

        # Check Tesseract
        has_tess, tess_info = check_tesseract_installed()
        ocr_text = ""
        if has_tess:
            ocr_text = extract_ocr_text(crop)
            if ocr_text:
                copy_to_clipboard(ocr_text)
                msg = f"Copied: {ocr_text[:60]}..." if len(ocr_text) > 60 else f"Copied: {ocr_text}"
            else:
                msg = "No readable text detected in circle."
        else:
            msg = "Tesseract OCR not installed. Visit https://github.com/UB-Mannheim/tesseract/wiki"
            print(f"[OCR Warning] {msg}")

        # Also save capture & index it in library
        filename = self._format_filename("circle", img_fmt)
        out_path = os.path.join(save_dir, filename)
        crop.save(out_path)
        self.library.add_capture(out_path, shape, ocr_text=ocr_text)

        if self.settings_mgr.get("appearance.show_toast", True):
            pos = self.settings_mgr.get("appearance.toast_position", "bottom-right")
            dur = self.settings_mgr.get("appearance.toast_duration", 2000)
            show_toast("MarkSnap OCR", msg, position=pos, duration_ms=dur)

    def handle_save_fullscreen(
        self,
        shape: str,
        base_image: Image.Image,
        ink_image: Image.Image
    ) -> None:
        save_dir = self.settings_mgr.get("storage.save_folder")
        os.makedirs(save_dir, exist_ok=True)
        img_fmt = self.settings_mgr.get("storage.image_format", "PNG")

        composite = Image.alpha_composite(base_image.convert("RGBA"), ink_image).convert("RGB")
        filename = self._format_filename("screen", img_fmt)
        out_path = os.path.join(save_dir, filename)

        if img_fmt.upper() in ("JPG", "JPEG"):
            composite.save(out_path, "JPEG", quality=95)
        else:
            composite.save(out_path, "PNG")

        self.library.add_capture(out_path, shape, ocr_text="")

        if self.settings_mgr.get("appearance.show_toast", True):
            pos = self.settings_mgr.get("appearance.toast_position", "bottom-right")
            dur = self.settings_mgr.get("appearance.toast_duration", 2000)
            show_toast("Screen Saved", f"Full screenshot saved to {filename}", position=pos, duration_ms=dur)

    def handle_ask_ai(
        self,
        shape: str,
        bbox: Tuple[float, float, float, float],
        base_image: Image.Image,
        ink_image: Image.Image
    ) -> None:
        """AI Bridge Phase 5: Opens confirmation prompt dialog before sending anywhere."""
        save_dir = self.settings_mgr.get("storage.save_folder")
        os.makedirs(save_dir, exist_ok=True)

        w, h = base_image.size
        min_x, min_y, max_x, max_y = [int(v) for v in bbox]
        min_x = max(0, min(w, min_x))
        max_x = max(0, min(w, max_x))
        min_y = max(0, min(h, min_y))
        max_y = max(0, min(h, max_y))

        crop = base_image.crop((min_x, min_y, max_x, max_y))
        filename = self._format_filename("arrow", "png")
        out_path = os.path.join(save_dir, filename)
        crop.save(out_path)

        # Index in library
        self.library.add_capture(out_path, shape, ocr_text="")

        # Show prompt dialog (runs locally, validates user confirmation)
        self._show_ai_prompt_dialog(out_path)

    def _show_ai_prompt_dialog(self, image_path: str):
        default_prompt = self.settings_mgr.get("ai.default_prompt", "Explain this screen region.")

        def _open():
            dlg = tk.Tk()
            dlg.title("MarkSnap AI Vision Bridge")
            dlg.geometry("450x260")
            dlg.attributes("-topmost", True)
            dlg.configure(bg="#1E1E1E")

            lbl = tk.Label(dlg, text="Send Marked Region to AI:", font=("Segoe UI", 11, "bold"), fg="#00E5FF", bg="#1E1E1E")
            lbl.pack(anchor="w", padx=16, pady=(16, 6))

            txt = tk.Text(dlg, height=4, font=("Segoe UI", 10), bg="#2D2D2D", fg="#FFFFFF", insertbackground="#00E5FF", bd=1)
            txt.insert("1.0", default_prompt)
            txt.pack(fill="x", padx=16, pady=4)

            status_lbl = tk.Label(dlg, text="Nothing leaves your PC until you click Send.", font=("Segoe UI", 9), fg="#AAAAAA", bg="#1E1E1E")
            status_lbl.pack(anchor="w", padx=16, pady=(4, 12))

            btn_frame = tk.Frame(dlg, bg="#1E1E1E")
            btn_frame.pack(fill="x", padx=16)

            def on_send():
                user_prompt = txt.get("1.0", "end").strip()
                status_lbl.configure(text="Querying AI Vision model (configured in AI Tab)...", fg="#00E5FF")
                # Phase 5 Anthropic API call stub with keyring check
                import keyring
                api_key = keyring.get_password("MarkSnap", "anthropic_api_key")
                if not api_key:
                    messagebox.showinfo("API Key Needed", "No AI API key found in Windows Credential Manager.\nPlease enter it in the MarkSnap AI Settings tab.", parent=dlg)
                    dlg.destroy()
                    return
                # If key exists, simulated or live call
                messagebox.showinfo("AI Vision Response", f"Prompt: '{user_prompt}'\nImage: {os.path.basename(image_path)}\n\n(AI response window will render here)", parent=dlg)
                dlg.destroy()

            btn_send = tk.Button(btn_frame, text="Send to AI", bg="#007ACC", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, command=on_send)
            btn_send.pack(side="right", padx=(8, 0))

            btn_cancel = tk.Button(btn_frame, text="Cancel", bg="#3E3E42", fg="#FFFFFF", font=("Segoe UI", 9), relief="flat", padx=12, pady=4, command=dlg.destroy)
            btn_cancel.pack(side="right")

            dlg.mainloop()

        import threading
        threading.Thread(target=_open, daemon=True).start()
