"""
marksnap.py - MarkSnap Background Capture Application

A background Windows overlay where the drawn shape is the command.
Features:
- Light blur on the background screen when annotate mode is on.
- Enter key to save the annotated snap, Esc to dismiss/cancel.
- Floating translucent hotbar with tool selection:
    * Pens (Ballpoint, Fineliner, Marker)
    * Highlighters (Yellow, Green, Cyan)
    * Pointer / Arrow
    * Ask AI mode button right beside it
    * Color palette & stroke size options
- Watches settings.json for live updates.
- Records all captures and OCR text to library.json.
- Dispatches actions via actions.py.
"""

from __future__ import annotations
import sys
import os
import argparse
import ctypes
import threading
import time
import math
from typing import List, Tuple, Optional, Dict, Any

import mss
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import keyboard
import tkinter as tk

from recognizer import classify, Point
from settings_store import SettingsManager
from library_store import LibraryStore
from actions import ActionRouter, show_toast


def enable_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        if user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return
    except Exception:
        pass

    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(76)
    vy = user32.GetSystemMetrics(77)
    vw = user32.GetSystemMetrics(78)
    vh = user32.GetSystemMetrics(79)
    return vx, vy, vw, vh


class MarkSnapOverlay:
    def __init__(self, settings_mgr: SettingsManager, library_store: LibraryStore, debug: bool = False):
        self.settings_mgr = settings_mgr
        self.library_store = library_store
        self.router = ActionRouter(settings_mgr, library_store)
        self.debug = debug

        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None
        self.base_image: Optional[Image.Image] = None       # Sharp capture (for crystal clear saving)
        self.display_image: Optional[Image.Image] = None    # Lightly blurred (for background annotation mode)
        self.ink_image: Optional[Image.Image] = None        # High-res RGBA ink buffer
        self.ink_draw: Optional[ImageDraw.ImageDraw] = None

        # Virtual bounds
        self.vx = 0
        self.vy = 0
        self.vw = 0
        self.vh = 0

        # State
        self.is_active = False
        self.current_ink_points: List[Tuple[int, int]] = []
        self.current_gesture_points: List[Point] = []
        self.gesture_line_ids: List[int] = []

        # Tool selection: "pen", "highlighter", "pointer", "ai"
        self.current_tool = "pen"
        self.current_pen_type = "ballpoint"  # "ballpoint", "fineliner", "marker"
        self.pen_color = self.settings_mgr.get("appearance.ink_color", "#FF2222")
        self.highlighter_color = "#FFEB3B"  # Yellow default
        self.gesture_color = self.settings_mgr.get("appearance.gesture_color", "#00E5FF")
        self.stroke_width = self.settings_mgr.get("appearance.stroke_width", 3)

        # AI Mode selection state
        self.ai_mode_active = False
        self.ai_selection_start: Optional[Tuple[int, int]] = None
        self.ai_selection_rect_id: Optional[int] = None

        # Hotbar UI widget references
        self.hotbar_frame: Optional[tk.Frame] = None
        self.tool_buttons: Dict[str, tk.Button] = {}

        # Debug HUD items
        self.debug_text_id: Optional[int] = None
        self.crosshair_x_id: Optional[int] = None
        self.crosshair_y_id: Optional[int] = None

        # Listen for live settings changes
        self.settings_mgr.add_change_listener(self._on_settings_reloaded)

    def _on_settings_reloaded(self, new_settings: dict):
        self.pen_color = new_settings.get("appearance", {}).get("ink_color", "#FF2222")
        self.gesture_color = new_settings.get("appearance", {}).get("gesture_color", "#00E5FF")
        self.stroke_width = new_settings.get("appearance", {}).get("stroke_width", 3)

    def capture_screen(self) -> Tuple[Image.Image, int, int, int, int]:
        vx, vy, vw, vh = get_virtual_screen_bounds()
        monitor_dict = {"left": vx, "top": vy, "width": vw, "height": vh}
        with mss.mss() as sct:
            sct_img = sct.grab(monitor_dict)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return img, vx, vy, vw, vh

    def _hex_to_rgb(self, hex_code: str) -> Tuple[int, int, int]:
        hex_code = hex_code.lstrip("#")
        if len(hex_code) == 3:
            hex_code = "".join([c * 2 for c in hex_code])
        if len(hex_code) >= 6:
            return int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
        return 255, 34, 34

    def show(self):
        if self.is_active:
            return
        if self.settings_mgr.get("general.paused", False):
            print("[MarkSnap] MarkSnap is currently paused. Ignoring hotkey.")
            return

        self.is_active = True
        self.current_tool = "pen"
        self.ai_mode_active = False

        # Capture original screen
        self.base_image, self.vx, self.vy, self.vw, self.vh = self.capture_screen()

        # Apply a light aesthetic blur (radius 3) to visually indicate Annotate Mode is ON
        # Keeps UI legible while clearly distinguishing background from annotation surface
        self.display_image = self.base_image.filter(ImageFilter.BoxBlur(3))

        self.ink_image = Image.new("RGBA", (self.vw, self.vh), (0, 0, 0, 0))
        self.ink_draw = ImageDraw.Draw(self.ink_image)

        self.root = tk.Tk()
        self.root.title("MarkSnap Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.vw,
            height=self.vh,
            cursor="crosshair",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.tk_image = ImageTk.PhotoImage(self.display_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # Build floating hotbar on top of the canvas
        self._build_floating_hotbar()

        # Top instruction bar
        self._render_status_bar()

        # Key bindings: Enter saves, Esc cancels
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<Return>", self.on_return)

        # Mouse ink & gestures
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)

        # Right mouse button always triggers shape gesture recognition regardless of active tool
        self.canvas.bind("<ButtonPress-3>", self.on_right_down)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_up)

        if self.debug:
            self.canvas.bind("<Motion>", self.on_mouse_move)
            self._setup_debug_visuals()

        self.root.focus_force()
        self.root.mainloop()

    # -----------------------------------------------------------------------
    # Floating Hotbar
    # -----------------------------------------------------------------------

    def _build_floating_hotbar(self):
        """Constructs modern floating toolbar for selecting pens, highlighters, pointers, and AI mode."""
        self.hotbar_frame = tk.Frame(
            self.root,
            bg="#18181A",
            bd=0,
            highlightbackground="#2A2A2E",
            highlightthickness=1,
            padx=8,
            pady=6
        )

        def make_btn(parent, text: str, cmd, key: str, tooltip: str = "", width: int = 4):
            btn = tk.Button(
                parent,
                text=text,
                command=cmd,
                bg="#252528",
                fg="#E0E0E0",
                activebackground="#007ACC",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                padx=8,
                pady=4,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2"
            )
            btn.pack(side="left", padx=3)
            self.tool_buttons[key] = btn
            return btn

        # --- Section 1: Pens Group ---
        grp_pens = tk.Frame(self.hotbar_frame, bg="#18181A")
        grp_pens.pack(side="left", padx=(0, 6))

        lbl_pen = tk.Label(grp_pens, text="PEN", bg="#18181A", fg="#777777", font=("Segoe UI", 7, "bold"))
        lbl_pen.pack(anchor="w", padx=2)

        pen_sub = tk.Frame(grp_pens, bg="#18181A")
        pen_sub.pack(side="left")

        make_btn(pen_sub, "Ballpoint", lambda: self.select_pen("ballpoint"), "ballpoint")
        make_btn(pen_sub, "Fineliner", lambda: self.select_pen("fineliner"), "fineliner")
        make_btn(pen_sub, "Marker", lambda: self.select_pen("marker"), "marker")

        # Separator
        tk.Frame(self.hotbar_frame, bg="#333338", width=1, height=28).pack(side="left", padx=6, fill="y")

        # --- Section 2: Highlighter Group ---
        grp_hl = tk.Frame(self.hotbar_frame, bg="#18181A")
        grp_hl.pack(side="left", padx=(0, 6))

        lbl_hl = tk.Label(grp_hl, text="HIGHLIGHTER", bg="#18181A", fg="#777777", font=("Segoe UI", 7, "bold"))
        lbl_hl.pack(anchor="w", padx=2)

        hl_sub = tk.Frame(grp_hl, bg="#18181A")
        hl_sub.pack(side="left")

        make_btn(hl_sub, "Yellow", lambda: self.select_highlighter("#FFEB3B"), "hl_yellow")
        make_btn(hl_sub, "Green", lambda: self.select_highlighter("#00E676"), "hl_green")
        make_btn(hl_sub, "Cyan", lambda: self.select_highlighter("#00E5FF"), "hl_cyan")

        # Separator
        tk.Frame(self.hotbar_frame, bg="#333338", width=1, height=28).pack(side="left", padx=6, fill="y")

        # --- Section 3: Pointer / Arrow Tool ---
        grp_pointer = tk.Frame(self.hotbar_frame, bg="#18181A")
        grp_pointer.pack(side="left", padx=(0, 6))

        lbl_ptr = tk.Label(grp_pointer, text="POINTER", bg="#18181A", fg="#777777", font=("Segoe UI", 7, "bold"))
        lbl_ptr.pack(anchor="w", padx=2)

        ptr_sub = tk.Frame(grp_pointer, bg="#18181A")
        ptr_sub.pack(side="left")

        make_btn(ptr_sub, "Arrow Pointer", self.select_pointer, "pointer")

        # Separator
        tk.Frame(self.hotbar_frame, bg="#333338", width=1, height=28).pack(side="left", padx=6, fill="y")

        # --- Section 4: Ask AI Mode (Right beside pointers) ---
        grp_ai = tk.Frame(self.hotbar_frame, bg="#18181A")
        grp_ai.pack(side="left", padx=(0, 6))

        lbl_ai = tk.Label(grp_ai, text="AI VISION", bg="#18181A", fg="#00E5FF", font=("Segoe UI", 7, "bold"))
        lbl_ai.pack(anchor="w", padx=2)

        btn_ai = tk.Button(
            grp_ai,
            text="Ask AI Mode",
            command=self.select_ai_mode,
            bg="#1E293B",
            fg="#38BDF8",
            activebackground="#0284C7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        )
        btn_ai.pack(side="left", padx=2)
        self.tool_buttons["ai_mode"] = btn_ai

        # Separator
        tk.Frame(self.hotbar_frame, bg="#333338", width=1, height=28).pack(side="left", padx=6, fill="y")

        # --- Section 5: Save (Enter) & Cancel (Esc) Buttons ---
        grp_actions = tk.Frame(self.hotbar_frame, bg="#18181A")
        grp_actions.pack(side="left", padx=(4, 0))

        lbl_act = tk.Label(grp_actions, text="ACTIONS", bg="#18181A", fg="#777777", font=("Segoe UI", 7, "bold"))
        lbl_act.pack(anchor="w", padx=2)

        btn_save = tk.Button(
            grp_actions,
            text="Save (Enter)",
            command=self.on_return,
            bg="#16A34A",
            fg="#FFFFFF",
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        )
        btn_save.pack(side="left", padx=2)

        btn_esc = tk.Button(
            grp_actions,
            text="Cancel (Esc)",
            command=self.on_escape,
            bg="#374151",
            fg="#D1D5DB",
            relief="flat",
            bd=0,
            padx=8,
            pady=4,
            font=("Segoe UI", 9),
            cursor="hand2"
        )
        btn_esc.pack(side="left", padx=2)

        # Position the hotbar at top-center of primary screen
        self.root.update_idletasks()
        hotbar_w = self.hotbar_frame.winfo_reqwidth()
        hotbar_h = self.hotbar_frame.winfo_reqheight()

        center_x = max(20, (self.vw - hotbar_w) // 2)
        top_y = 36  # Just below status bar

        # Create window inside Canvas
        self.canvas.create_window(center_x, top_y, anchor="nw", window=self.hotbar_frame)

        # Highlight default tool
        self._update_tool_buttons_ui()

    def _update_tool_buttons_ui(self):
        # Reset all button styles
        for key, btn in self.tool_buttons.items():
            if key == "ai_mode":
                if self.current_tool == "ai":
                    btn.configure(bg="#0284C7", fg="#FFFFFF")
                else:
                    btn.configure(bg="#1E293B", fg="#38BDF8")
            else:
                btn.configure(bg="#252528", fg="#E0E0E0")

        # Highlight active tool
        if self.current_tool == "pen":
            btn_key = self.current_pen_type
            if btn_key in self.tool_buttons:
                self.tool_buttons[btn_key].configure(bg="#007ACC", fg="#FFFFFF")
        elif self.current_tool == "highlighter":
            if self.highlighter_color == "#FFEB3B" and "hl_yellow" in self.tool_buttons:
                self.tool_buttons["hl_yellow"].configure(bg="#B45309", fg="#FEF08A")
            elif self.highlighter_color == "#00E676" and "hl_green" in self.tool_buttons:
                self.tool_buttons["hl_green"].configure(bg="#15803D", fg="#BBF7D0")
            elif self.highlighter_color == "#00E5FF" and "hl_cyan" in self.tool_buttons:
                self.tool_buttons["hl_cyan"].configure(bg="#0E7490", fg="#CFFAFE")
        elif self.current_tool == "pointer":
            if "pointer" in self.tool_buttons:
                self.tool_buttons["pointer"].configure(bg="#007ACC", fg="#FFFFFF")

    def select_pen(self, pen_type: str):
        self.current_tool = "pen"
        self.current_pen_type = pen_type
        self.ai_mode_active = False
        self._update_tool_buttons_ui()

    def select_highlighter(self, color_hex: str):
        self.current_tool = "highlighter"
        self.highlighter_color = color_hex
        self.ai_mode_active = False
        self._update_tool_buttons_ui()

    def select_pointer(self):
        self.current_tool = "pointer"
        self.ai_mode_active = False
        self._update_tool_buttons_ui()

    def select_ai_mode(self):
        self.current_tool = "ai"
        self.ai_mode_active = True
        self._update_tool_buttons_ui()

    # -----------------------------------------------------------------------
    # Status Hint Bar
    # -----------------------------------------------------------------------

    def _render_status_bar(self):
        hint_text = "ANNOTATE MODE (Screen Frozen & Blurred)  |  Left-Drag: Use Selected Tool  |  Right-Drag: Shape Gestures  |  Enter: Save Snap  |  Esc: Exit"
        self.canvas.create_rectangle(0, 0, self.vw, 26, fill="#0F172A", outline="")
        self.canvas.create_text(
            self.vw // 2, 13,
            text=hint_text,
            fill="#38BDF8",
            font=("Segoe UI", 9, "bold")
        )

    def _setup_debug_visuals(self):
        self.crosshair_x_id = self.canvas.create_line(0, 0, self.vw, 0, fill="#FFFF00", dash=(4, 4))
        self.crosshair_y_id = self.canvas.create_line(0, 0, 0, self.vh, fill="#FFFF00", dash=(4, 4))
        self.debug_text_id = self.canvas.create_text(
            20, 40,
            anchor=tk.NW,
            text=f"DEBUG MODE\nVirtual: {self.vw}x{self.vh} at ({self.vx}, {self.vy})",
            fill="#FFFF00",
            font=("Consolas", 11, "bold")
        )

    def on_mouse_move(self, event: tk.Event):
        cx, cy = event.x, event.y
        sx = cx + self.vx
        sy = cy + self.vy
        if self.crosshair_x_id and self.crosshair_y_id:
            self.canvas.coords(self.crosshair_x_id, 0, cy, self.vw, cy)
            self.canvas.coords(self.crosshair_y_id, cx, 0, cx, self.vh)
        if self.debug_text_id:
            debug_info = (
                f"[DEBUG MODE]\n"
                f"Tool: {self.current_tool.upper()} (Pen: {self.current_pen_type})\n"
                f"Canvas Pos: ({cx}, {cy})\n"
                f"Screen Pos: ({sx}, {sy})\n"
                f"Virtual Bounds: {self.vw}x{self.vh} at ({self.vx}, {self.vy})"
            )
            self.canvas.itemconfigure(self.debug_text_id, text=debug_info)

    # -----------------------------------------------------------------------
    # Left-Drag: Tool Handlers (Pen, Highlighter, Pointer, Ask AI)
    # -----------------------------------------------------------------------

    def on_left_down(self, event: tk.Event):
        # Ignore clicks inside floating hotbar
        if self._is_inside_hotbar(event.x, event.y):
            return

        if self.current_tool == "ai":
            self.ai_selection_start = (event.x, event.y)
            if self.ai_selection_rect_id:
                self.canvas.delete(self.ai_selection_rect_id)
                self.ai_selection_rect_id = None
        else:
            self.current_ink_points = [(event.x, event.y)]

    def on_left_drag(self, event: tk.Event):
        if self._is_inside_hotbar(event.x, event.y):
            return

        if self.current_tool == "ai":
            if not self.ai_selection_start:
                return
            x0, y0 = self.ai_selection_start
            x1, y1 = event.x, event.y
            if self.ai_selection_rect_id:
                self.canvas.coords(self.ai_selection_rect_id, x0, y0, x1, y1)
            else:
                self.ai_selection_rect_id = self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    outline="#38BDF8",
                    width=2,
                    dash=(4, 4)
                )
            return

        if not self.current_ink_points:
            self.current_ink_points = [(event.x, event.y)]
            return

        x0, y0 = self.current_ink_points[-1]
        x1, y1 = event.x, event.y
        self.current_ink_points.append((x1, y1))

        if self.current_tool == "pen":
            width = 2 if self.current_pen_type == "ballpoint" else (4 if self.current_pen_type == "fineliner" else 8)
            color = self.pen_color
            self.canvas.create_line(x0, y0, x1, y1, fill=color, width=width, capstyle=tk.ROUND, joinstyle=tk.ROUND)
            if self.ink_draw:
                r, g, b = self._hex_to_rgb(color)
                self.ink_draw.line([(x0, y0), (x1, y1)], fill=(r, g, b, 255), width=width)

        elif self.current_tool == "highlighter":
            # Semitransparent wide stroke
            hl_width = 18
            color = self.highlighter_color
            self.canvas.create_line(x0, y0, x1, y1, fill=color, width=hl_width, capstyle=tk.PROJECTING, joinstyle=tk.ROUND, stipple="gray50")
            if self.ink_draw:
                r, g, b = self._hex_to_rgb(color)
                self.ink_draw.line([(x0, y0), (x1, y1)], fill=(r, g, b, 90), width=hl_width)

        elif self.current_tool == "pointer":
            # Draw dynamic line that will become an arrow on release
            self.canvas.create_line(x0, y0, x1, y1, fill="#F59E0B", width=3, capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def on_left_up(self, event: tk.Event):
        if self.current_tool == "ai" and self.ai_selection_start:
            x0, y0 = self.ai_selection_start
            x1, y1 = event.x, event.y
            self.ai_selection_start = None
            min_x = min(x0, x1)
            max_x = max(x0, x1)
            min_y = min(y0, y1)
            max_y = max(y0, y1)

            if (max_x - min_x > 15) and (max_y - min_y > 15):
                bbox = (float(min_x), float(min_y), float(max_x), float(max_y))
                self.router.dispatch("arrow", bbox, self.base_image, self.ink_image, on_complete=self.close)
            else:
                if self.ai_selection_rect_id:
                    self.canvas.delete(self.ai_selection_rect_id)
                    self.ai_selection_rect_id = None
            return

        if self.current_tool == "pointer" and len(self.current_ink_points) >= 2:
            start_p = self.current_ink_points[0]
            end_p = self.current_ink_points[-1]
            # Draw sharp callout arrow
            self._draw_canvas_arrow(start_p, end_p, color="#F59E0B", width=4)
            self._draw_pil_arrow(start_p, end_p, color=(245, 158, 11, 255), width=4)

        self.current_ink_points = []

    def _draw_canvas_arrow(self, p1: Tuple[int, int], p2: Tuple[int, int], color: str, width: int):
        self.canvas.create_line(
            p1[0], p1[1], p2[0], p2[1],
            fill=color,
            width=width,
            arrow=tk.LAST,
            arrowshape=(16, 20, 6)
        )

    def _draw_pil_arrow(self, p1: Tuple[int, int], p2: Tuple[int, int], color: Tuple[int, int, int, int], width: int):
        if not self.ink_draw:
            return
        x0, y0 = p1
        x1, y1 = p2
        self.ink_draw.line([(x0, y0), (x1, y1)], fill=color, width=width)

        # Arrowhead math
        dx = x1 - x0
        dy = y1 - y0
        angle = math.atan2(dy, dx)
        arrow_len = 20.0
        arrow_angle = math.pi / 6.0

        left_x = x1 - arrow_len * math.cos(angle - arrow_angle)
        left_y = y1 - arrow_len * math.sin(angle - arrow_angle)
        right_x = x1 - arrow_len * math.cos(angle + arrow_angle)
        right_y = y1 - arrow_len * math.sin(angle + arrow_angle)

        self.ink_draw.polygon([(x1, y1), (left_x, left_y), (right_x, right_y)], fill=color)

    def _is_inside_hotbar(self, x: int, y: int) -> bool:
        if not self.hotbar_frame:
            return False
        try:
            hx = self.hotbar_frame.winfo_x()
            hy = self.hotbar_frame.winfo_y()
            hw = self.hotbar_frame.winfo_width()
            hh = self.hotbar_frame.winfo_height()
            return (hx <= x <= hx + hw) and (hy <= y <= hy + hh)
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Right-Drag: Gesture Recognition (Box, Circle, Underline, Arrow)
    # -----------------------------------------------------------------------

    def on_right_down(self, event: tk.Event):
        self.current_gesture_points = [(float(event.x), float(event.y))]
        self._clear_gesture_lines()

    def on_right_drag(self, event: tk.Event):
        if not self.current_gesture_points:
            self.current_gesture_points = [(float(event.x), float(event.y))]
            return

        x0, y0 = self.current_gesture_points[-1]
        x1, y1 = float(event.x), float(event.y)
        self.current_gesture_points.append((x1, y1))

        line_id = self.canvas.create_line(
            x0, y0, x1, y1,
            fill=self.gesture_color,
            width=max(2, self.stroke_width),
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
        self.gesture_line_ids.append(line_id)

    def on_right_up(self, event: tk.Event):
        points = list(self.current_gesture_points)
        self.current_gesture_points = []

        if len(points) < 5:
            self._clear_gesture_lines()
            return

        sensitivity = self.settings_mgr.get("gestures.sensitivity", 50)
        result = classify(points, sensitivity=sensitivity)
        shape = result["shape"]
        bbox = result["bbox"]

        print(f"[MarkSnap] Recognized gesture: {shape.upper()} (conf: {result['confidence']:.2f})")

        gesture_enabled = self.settings_mgr.get(f"gestures.{shape}.enabled", True)
        if not gesture_enabled:
            print(f"[MarkSnap] Gesture '{shape}' is disabled in settings. Skipping.")
            self._clear_gesture_lines()
            return

        should_flash = self.settings_mgr.get("appearance.flash_shape", True)
        if should_flash and shape != "unknown":
            self._flash_recognition(shape, bbox, lambda: self._dispatch_and_close(shape, bbox))
        else:
            self._dispatch_and_close(shape, bbox)

    def _clear_gesture_lines(self):
        for line_id in self.gesture_line_ids:
            self.canvas.delete(line_id)
        self.gesture_line_ids.clear()

    def _flash_recognition(self, shape: str, bbox: Tuple[float, float, float, float], on_complete):
        min_x, min_y, max_x, max_y = bbox
        mid_x = (min_x + max_x) / 2
        mid_y = (min_y + max_y) / 2

        badge_bg = self.canvas.create_rectangle(
            mid_x - 70, mid_y - 20, mid_x + 70, mid_y + 20,
            fill="#111111", outline=self.gesture_color, width=2
        )
        badge_txt = self.canvas.create_text(
            mid_x, mid_y,
            text=f"Shape: {shape.upper()}",
            fill=self.gesture_color,
            font=("Segoe UI", 11, "bold")
        )

        def finish():
            try:
                self.canvas.delete(badge_bg)
                self.canvas.delete(badge_txt)
            except Exception:
                pass
            self._clear_gesture_lines()
            on_complete()

        self.root.after(400, finish)

    def _dispatch_and_close(self, shape: str, bbox: Tuple[float, float, float, float]):
        self.router.dispatch(
            shape, bbox, self.base_image, self.ink_image,
            on_complete=self.close
        )

    # -----------------------------------------------------------------------
    # Dismiss / Save Actions
    # -----------------------------------------------------------------------

    def on_escape(self, event: tk.Event = None):
        """Cancel and dismiss annotate mode."""
        print("[MarkSnap] Esc pressed: Exiting annotate mode.")
        self.close()

    def on_return(self, event: tk.Event = None):
        """Enter saves the full screen with all drawn annotations."""
        print("[MarkSnap] Enter pressed: Saving annotated snap.")
        self.router.handle_save_fullscreen("manual", self.base_image, self.ink_image)
        self.close()

    def close(self):
        self.is_active = False
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None


# ---------------------------------------------------------------------------
# Background Hotkey Coordinator
# ---------------------------------------------------------------------------

class BackgroundCaptureApp:
    def __init__(self, settings_mgr: SettingsManager, library_store: LibraryStore, debug: bool = False):
        self.settings_mgr = settings_mgr
        self.library_store = library_store
        self.debug = debug
        self.overlay = MarkSnapOverlay(settings_mgr, library_store, debug=debug)
        self.active_hotkey = ""
        self._lock = threading.Lock()

        # Listen for hotkey setting changes live
        self.settings_mgr.add_change_listener(self._on_settings_change)

    def _on_settings_change(self, settings_data: dict):
        new_hotkey = settings_data.get("hotkeys", {}).get("open_overlay", "ctrl+shift+d").lower()
        if new_hotkey != self.active_hotkey:
            self._update_hotkey_registration(new_hotkey)

    def _update_hotkey_registration(self, new_hotkey: str):
        with self._lock:
            try:
                if self.active_hotkey:
                    keyboard.remove_hotkey(self.active_hotkey)
                    print(f"[MarkSnap] Removed old hotkey: {self.active_hotkey}")
            except Exception as e:
                print(f"[MarkSnap] Warning unhooking hotkey: {e}")

            try:
                keyboard.add_hotkey(new_hotkey, self._trigger_overlay)
                self.active_hotkey = new_hotkey
                print(f"[MarkSnap] Successfully registered live hotkey: {new_hotkey}")
            except Exception as e:
                print(f"[MarkSnap] Failed to register hotkey {new_hotkey}: {e}")

    def _trigger_overlay(self):
        if not self.overlay.is_active:
            threading.Thread(target=self.overlay.show, daemon=True).start()

    def run(self):
        initial_hotkey = self.settings_mgr.get("hotkeys.open_overlay", "ctrl+shift+d").lower()
        self._update_hotkey_registration(initial_hotkey)
        print(f"[MarkSnap Daemon] Running with hotkey '{initial_hotkey}'. Press Ctrl+C in terminal to stop.")
        try:
            keyboard.wait()
        except KeyboardInterrupt:
            print("[MarkSnap Daemon] Shutting down.")


def main():
    enable_dpi_awareness()

    parser = argparse.ArgumentParser(description="MarkSnap: Shape-driven screen capture")
    parser.add_argument("--debug", action="store_true", help="Enable coordinate crosshairs and metrics")
    parser.add_argument("--once", action="store_true", help="Launch overlay once immediately")
    args = parser.parse_args()

    settings_mgr = SettingsManager()
    library_store = LibraryStore()

    if args.once:
        overlay = MarkSnapOverlay(settings_mgr, library_store, debug=args.debug)
        overlay.show()
    else:
        app = BackgroundCaptureApp(settings_mgr, library_store, debug=args.debug)
        app.run()


if __name__ == "__main__":
    main()
