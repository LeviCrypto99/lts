import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import font as tkfont, messagebox
from typing import Dict, Optional, Tuple

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

BASE_WIDTH = 1328
BASE_HEIGHT = 800

LOGO_POS = (BASE_WIDTH / 2, 156)
TITLE_POS = (BASE_WIDTH / 2, 267)
API_LABEL_POS = (267, 295)
API_ENTRY_POS = (267, 324)
SECRET_LABEL_POS = (267, 400)
SECRET_ENTRY_POS = (267, 429)
NOTE_POS = (BASE_WIDTH / 2, 492)
LOGIN_BTN_POS = (BASE_WIDTH / 2, 545)
CHECK_POS = (BASE_WIDTH / 2, 620)
REQUIRED_POS = (BASE_WIDTH / 2, 655)
REQUIRED2_POS = (BASE_WIDTH / 2, 690)

INFO_PANEL_POS = (29, 32)
INFO_PANEL_SIZE = (371, 174)
HELP_PANEL_POS = (944, 93)
HELP_PANEL_SIZE = (348, 220)

FORM_OFFSET_Y = 32

ENTRY_W = 811
ENTRY_H = 51
LOGIN_W = 417
LOGIN_H = 60
HELP_BTN_W = 278
HELP_BTN_H = 39

ANIM_DURATION_MS = 500
ANIM_OFFSET = 40
FPS = 60

CANVAS_BG = "#0b1020"
BG_COLOR = "#ffffff"
BORDER_COLOR = "#1a2233"
TEXT_COLOR = "#111217"
UI_TEXT_COLOR = "#f6f8fc"
NOTE_COLOR = "#d2d8e4"
BUTTON_BG = "#000000"
BUTTON_FG = "white"
BUTTON_DISABLED_BG = "#3a3a3a"
BUTTON_DISABLED_FG = "#9a9a9a"
PANEL_FILL = "#0b1220"
PANEL_BORDER = "#c4cedf"
PANEL_ALPHA = 165
PANEL_BORDER_ALPHA = 210
MONTH_COLOR = "#f4c36a"

FONT_FAMILY = "Malgun Gothic"
SUBSCRIBER_WEBHOOK_URL = (
    "https://script.google.com/macros/s/AKfycbyKBEsD_GQ125wrjPm8kUrcRvnZSuZ4DlHZTg-lEr1X_UX-CiY2U9W9g3Pd6JBc6xIS/exec"
)
SUBSCRIBER_REQUEST_TIMEOUT_SEC = 8

# Subscriber request window (ex_image.png) layout constants.
SUB_TITLEBAR_OFFSET = 24
SUB_WINDOW_WIDTH = 1148
SUB_WINDOW_HEIGHT = 687

SUB_PANEL_LEFT = 221
SUB_PANEL_TOP = 119 - SUB_TITLEBAR_OFFSET
SUB_PANEL_RIGHT = 957
SUB_PANEL_BOTTOM = 595 - SUB_TITLEBAR_OFFSET
SUB_PANEL_WIDTH = SUB_PANEL_RIGHT - SUB_PANEL_LEFT + 1
SUB_PANEL_HEIGHT = SUB_PANEL_BOTTOM - SUB_PANEL_TOP + 1

SUB_ENTRY_WIDTH = 663
SUB_ENTRY_HEIGHT = 35
SUB_ENTRY_API_POS = (254, 263 - SUB_TITLEBAR_OFFSET)
SUB_ENTRY1_POS = (254, 331 - SUB_TITLEBAR_OFFSET)
SUB_ENTRY2_POS = (253, 399 - SUB_TITLEBAR_OFFSET)
SUB_ENTRY3_POS = (254, 467 - SUB_TITLEBAR_OFFSET)

SUB_LABEL_API_POS = (300, 234 - SUB_TITLEBAR_OFFSET)
SUB_LABEL1_POS = (300, 302 - SUB_TITLEBAR_OFFSET)
SUB_LABEL2_POS = (300, 370 - SUB_TITLEBAR_OFFSET)
SUB_LABEL3_POS = (302, 438 - SUB_TITLEBAR_OFFSET)

SUB_ICON_API_POS = (254, 228 - SUB_TITLEBAR_OFFSET)
SUB_ICON1_POS = (254, 296 - SUB_TITLEBAR_OFFSET)
SUB_ICON2_POS = (256, 364 - SUB_TITLEBAR_OFFSET)
SUB_ICON3_POS = (257, 432 - SUB_TITLEBAR_OFFSET)
SUB_ICON_API_SIZE = (30, 30)
SUB_ICON1_SIZE = (31, 31)
SUB_ICON2_SIZE = (30, 31)
SUB_ICON3_SIZE = (28, 26)

SUB_INSTR1_POS = (592, 134 - SUB_TITLEBAR_OFFSET)
SUB_INSTR2_POS = (593, 181 - SUB_TITLEBAR_OFFSET)

SUB_SUBMIT_RECT = (424, 510 - SUB_TITLEBAR_OFFSET, 746, 544 - SUB_TITLEBAR_OFFSET)

SUB_HELP_LEFT_RECT = (84, 552 - SUB_TITLEBAR_OFFSET, 404, 588 - SUB_TITLEBAR_OFFSET)
SUB_HELP_RIGHT_RECT = (414, 552 - SUB_TITLEBAR_OFFSET, 734, 588 - SUB_TITLEBAR_OFFSET)
SUB_HELP_API_RECT = (744, 552 - SUB_TITLEBAR_OFFSET, 1064, 588 - SUB_TITLEBAR_OFFSET)
SUB_SUBMIT_TEXT_POS = (585, 527 - SUB_TITLEBAR_OFFSET)
SUB_HELP_LEFT_TEXT_POS = (261, 570 - SUB_TITLEBAR_OFFSET)
SUB_HELP_RIGHT_TEXT_POS = (618, 570 - SUB_TITLEBAR_OFFSET)


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _hex_to_rgba(color: str, alpha: int) -> Tuple[int, int, int, int]:
    color = color.lstrip("#")
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    return r, g, b, alpha


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _rgb_to_hex(color: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _lighten_hex(color: str, amount: int) -> str:
    if not color.startswith("#") or len(color) != 7:
        return color
    r, g, b = _hex_to_rgb(color)
    r = min(255, r + amount)
    g = min(255, g + amount)
    b = min(255, b + amount)
    return _rgb_to_hex((r, g, b))


def _round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float, **kwargs):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r,
        y1,
        x2 - r,
        y1,
        x2,
        y1,
        x2,
        y1 + r,
        x2,
        y2 - r,
        x2,
        y2,
        x2 - r,
        y2,
        x1 + r,
        y2,
        x1,
        y2,
        x1,
        y2 - r,
        x1,
        y1 + r,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)


class RoundedPanel(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        radius: int = 14,
        border_width: int = 2,
        border_color: str = "#000000",
        fill_color: str = "white",
    ) -> None:
        super().__init__(master, bg=CANVAS_BG, highlightthickness=0)
        self.radius = radius
        self.border_width = border_width
        self.border_color = border_color
        self.fill_color = fill_color
        self.content = tk.Frame(self, bg=fill_color)
        self._window = self.create_window(0, 0, window=self.content, anchor="nw")

    def resize(self, width: float, height: float, scale: float) -> None:
        self.configure(width=width, height=height)
        self.delete("shape")
        radius = int(self.radius * scale)
        _round_rect(
            self,
            0,
            0,
            width,
            height,
            radius,
            fill=self.fill_color,
            outline=self.border_color,
            width=self.border_width,
            tags="shape",
        )
        pad = self.border_width
        self.coords(self._window, pad, pad)
        self.itemconfigure(self._window, width=max(1, width - pad * 2), height=max(1, height - pad * 2))
        self.tag_lower("shape")


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        text: str,
        font: tkfont.Font,
        radius: int = 12,
        bg: str = BUTTON_BG,
        fg: str = BUTTON_FG,
        disabled_bg: str = BUTTON_DISABLED_BG,
        disabled_fg: str = BUTTON_DISABLED_FG,
        hover_bg: Optional[str] = None,
        command=None,
    ) -> None:
        super().__init__(master, bg=CANVAS_BG, highlightthickness=0)
        self._text = text
        self._font = font
        self._radius = radius
        self._bg = bg
        self._hover_bg = hover_bg or _lighten_hex(bg, 26)
        self._fg = fg
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._command = command
        self._state = "normal"
        self._width = 0
        self._height = 0
        self._last_scale = 1.0
        self._current_bg = bg
        self._anim_job: Optional[str] = None
        self._hover_steps = 6
        self._hover_duration_ms = 120
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def set_state(self, state: str) -> None:
        self._state = state
        self.configure(cursor="hand2" if state == "normal" else "")
        if state != "normal":
            self._cancel_animation()
            self._current_bg = self._bg
        self._redraw()

    def resize(self, width: float, height: float, scale: float) -> None:
        self._width = int(width)
        self._height = int(height)
        self._last_scale = scale
        self.configure(width=width, height=height)
        self._redraw(scale, width, height)

    def _redraw(self, scale: Optional[float] = None, width: Optional[float] = None, height: Optional[float] = None) -> None:
        scale = self._last_scale if scale is None else scale
        width = max(1, int(width or self._width or self.winfo_width()))
        height = max(1, int(height or self._height or self.winfo_height()))
        self.delete("all")
        radius = int(self._radius * scale)
        fill = self._current_bg if self._state == "normal" else self._disabled_bg
        fg = self._fg if self._state == "normal" else self._disabled_fg
        _round_rect(self, 0, 0, width, height, radius, fill=fill, outline=fill)
        self.create_text(width / 2, height / 2, text=self._text, font=self._font, fill=fg)

    def _on_click(self, _event: tk.Event) -> None:
        if self._state != "normal" or self._command is None:
            return
        self._command()

    def _on_enter(self, _event: tk.Event) -> None:
        if self._state != "normal":
            return
        self._animate_to(self._hover_bg)

    def _on_leave(self, _event: tk.Event) -> None:
        if self._state != "normal":
            return
        self._animate_to(self._bg)

    def _cancel_animation(self) -> None:
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None

    def _animate_to(self, target: str) -> None:
        if not target.startswith("#") or not self._current_bg.startswith("#"):
            self._current_bg = target
            self._redraw()
            return
        if self._current_bg == target:
            return
        self._cancel_animation()
        start = _hex_to_rgb(self._current_bg)
        end = _hex_to_rgb(target)
        steps = self._hover_steps
        step_ms = max(1, self._hover_duration_ms // steps)

        def step(i: int) -> None:
            t = i / steps
            color = tuple(int(s + (e - s) * t) for s, e in zip(start, end))
            self._current_bg = _rgb_to_hex(color)
            self._redraw()
            if i < steps:
                self._anim_job = self.after(step_ms, lambda: step(i + 1))
            else:
                self._anim_job = None

        step(1)


class EntryRow:
    def __init__(
        self,
        master: tk.Widget,
        fonts: Dict[str, tkfont.Font],
        with_eye: bool = False,
        on_eye=None,
        on_paste=None,
    ) -> None:
        self.outer = tk.Frame(master, bg=BORDER_COLOR, highlightthickness=0)
        self.inner = tk.Frame(self.outer, bg=BG_COLOR, highlightthickness=0)
        self.entry = tk.Entry(
            self.inner,
            bd=0,
            relief="flat",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            font=fonts["entry"],
        )
        self.eye_button: Optional[tk.Button] = None
        if with_eye:
            self.eye_button = tk.Button(
                self.inner,
                text="👁",
                bg=BG_COLOR,
                fg=TEXT_COLOR,
                font=fonts["icon"],
                bd=0,
                relief="flat",
                highlightthickness=0,
                activebackground=BG_COLOR,
                activeforeground=TEXT_COLOR,
                cursor="hand2",
                command=on_eye,
            )
        self.paste_button = tk.Button(
            self.inner,
            text="📋",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=fonts["icon"],
            bd=0,
            relief="flat",
            highlightthickness=0,
            activebackground=BG_COLOR,
            activeforeground=TEXT_COLOR,
            cursor="hand2",
            command=on_paste,
        )

    def place(self, x: float, y: float, width: float, height: float, scale: float) -> None:
        self.outer.place(x=x, y=y, width=width, height=height, anchor="nw")
        border = max(1, int(2 * scale))
        inner_w = max(1, int(width - 2 * border))
        inner_h = max(1, int(height - 2 * border))
        self.inner.place(x=border, y=border, width=inner_w, height=inner_h, anchor="nw")

        pad_x = max(6, int(8 * scale))
        icon_w = max(20, int(inner_h * 0.7))
        icon_pad = max(4, int(4 * scale))

        right_x = inner_w - pad_x
        self.paste_button.place(
            x=right_x,
            y=inner_h / 2,
            width=icon_w,
            height=icon_w,
            anchor="e",
        )
        right_x -= icon_w + icon_pad

        if self.eye_button is not None:
            self.eye_button.place(
                x=right_x,
                y=inner_h / 2,
                width=icon_w,
                height=icon_w,
                anchor="e",
            )
            right_x -= icon_w + icon_pad

        entry_w = max(1, int(right_x - pad_x))
        self.entry.place(x=pad_x, y=0, width=entry_w, height=inner_h, anchor="nw")


class SubscriberEntry:
    def __init__(self, master: tk.Widget, font: tkfont.Font, placeholder: str) -> None:
        self.frame = tk.Frame(master, bg=BG_COLOR, highlightthickness=0, bd=0)
        self.entry = tk.Entry(
            self.frame,
            bd=0,
            relief="flat",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            font=font,
        )
        self._placeholder = placeholder
        self._has_placeholder = True
        self.entry.insert(0, placeholder)
        self.entry.bind("<FocusIn>", self._clear_placeholder)
        self.entry.bind("<FocusOut>", self._restore_placeholder)

    def place(self, x: int, y: int, width: int, height: int) -> None:
        self.frame.place(x=x, y=y, width=width, height=height, anchor="nw")
        pad_x = 10
        self.entry.place(x=pad_x, y=0, width=max(1, width - pad_x), height=height, anchor="nw")

    def get_value(self) -> str:
        if self._has_placeholder:
            return ""
        return self.entry.get().strip()

    def _clear_placeholder(self, _event: Optional[tk.Event] = None) -> None:
        if not self._has_placeholder:
            return
        self.entry.delete(0, tk.END)
        self._has_placeholder = False

    def _restore_placeholder(self, _event: Optional[tk.Event] = None) -> None:
        if self.entry.get():
            self._has_placeholder = False
            return
        self.entry.insert(0, self._placeholder)
        self._has_placeholder = True


class SubscriberRequestWindow(tk.Toplevel):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        parent = master.winfo_toplevel()
        self.title(parent.title() or "LTS Launcher v1.4.0")
        self.configure(bg=CANVAS_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self._center_over_parent(parent)

        self.canvas = tk.Canvas(self, bg=CANVAS_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._fonts = {
            "instruction": tkfont.Font(self, family=FONT_FAMILY, size=14, weight="bold"),
            "label": tkfont.Font(self, family=FONT_FAMILY, size=12, weight="bold"),
            "entry": tkfont.Font(self, family=FONT_FAMILY, size=11, weight="normal"),
            "button": tkfont.Font(self, family=FONT_FAMILY, size=11, weight="bold"),
            "footer": tkfont.Font(self, family=FONT_FAMILY, size=11, weight="normal"),
        }

        self._load_images()
        self._draw_static()
        self._create_entries()
        self._bind_buttons()

    def _center_over_parent(self, parent: tk.Tk) -> None:
        parent.update_idletasks()
        try:
            base_x = parent.winfo_x()
            base_y = parent.winfo_y()
            base_w = parent.winfo_width()
            base_h = parent.winfo_height()
            x = base_x + max(0, (base_w - SUB_WINDOW_WIDTH) // 2)
            y = base_y + max(0, (base_h - SUB_WINDOW_HEIGHT) // 2)
        except tk.TclError:
            x = 0
            y = 0
        self.geometry(f"{SUB_WINDOW_WIDTH}x{SUB_WINDOW_HEIGHT}+{x}+{y}")

    def _load_images(self) -> None:
        base_dir = Path(__file__).resolve().parent
        bg_path = base_dir / "image" / "login_page" / "subscribe_request_bg.jpg"
        bg = Image.open(bg_path).convert("RGBA")
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        bg = bg.resize((SUB_WINDOW_WIDTH, SUB_WINDOW_HEIGHT), resample)
        self._bg_photo = ImageTk.PhotoImage(bg)

        icons_dir = base_dir / "image" / "login_page"
        self._icon_api = self._load_icon(icons_dir / "api_icon.png", SUB_ICON_API_SIZE)
        self._icon_tv = self._load_icon(icons_dir / "tradingview_icon.png", SUB_ICON1_SIZE)
        self._icon_telegram = self._load_icon(icons_dir / "telegram_icon.png", SUB_ICON2_SIZE)
        self._icon_binance = self._load_icon(icons_dir / "binance_icon.png", SUB_ICON3_SIZE)

    def _load_icon(self, path: Path, size: Tuple[int, int]) -> ImageTk.PhotoImage:
        img = Image.open(path).convert("RGBA")
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        img = img.resize(size, resample)
        return ImageTk.PhotoImage(img)

    def _draw_static(self) -> None:
        self.canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")
        instr_line1 = "아래 양식에 맞게 내용을 작성하신 뒤"
        instr_line2 = "등록요청 버튼을 눌러주세요"
        instr_font = self._fonts["instruction"]
        line_height = instr_font.metrics("linespace")
        text_w = max(instr_font.measure(instr_line1), instr_font.measure(instr_line2))
        pad_x, pad_y = 18, 8
        top = int(SUB_INSTR1_POS[1] - line_height / 2 - pad_y)
        bottom = int(SUB_INSTR2_POS[1] + line_height / 2 + pad_y)
        box_w = int(text_w + pad_x * 2)
        box_h = max(1, bottom - top)
        box_img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(box_img)
        rect = (0, 0, box_w - 1, box_h - 1)
        fill = (0, 0, 0, 140)
        if hasattr(draw, "rounded_rectangle"):
            draw.rounded_rectangle(rect, radius=12, fill=fill)
        else:
            draw.rectangle(rect, fill=fill)
        self._instr_bg_photo = ImageTk.PhotoImage(box_img)
        self.canvas.create_image(SUB_INSTR1_POS[0], top, image=self._instr_bg_photo, anchor="n")

        self.canvas.create_text(
            SUB_INSTR1_POS[0],
            SUB_INSTR1_POS[1],
            text=instr_line1,
            fill=UI_TEXT_COLOR,
            font=instr_font,
            anchor="center",
        )
        self.canvas.create_text(
            SUB_INSTR2_POS[0],
            SUB_INSTR2_POS[1],
            text=instr_line2,
            fill=UI_TEXT_COLOR,
            font=instr_font,
            anchor="center",
        )

        self.canvas.create_text(
            SUB_LABEL_API_POS[0],
            SUB_LABEL_API_POS[1],
            text="API KEY",
            fill=UI_TEXT_COLOR,
            font=self._fonts["label"],
            anchor="nw",
        )
        self.canvas.create_text(
            SUB_LABEL1_POS[0],
            SUB_LABEL1_POS[1],
            text="트레이딩 뷰 ID",
            fill=UI_TEXT_COLOR,
            font=self._fonts["label"],
            anchor="nw",
        )
        self.canvas.create_text(
            SUB_LABEL2_POS[0],
            SUB_LABEL2_POS[1],
            text="텔레그램 ID",
            fill=UI_TEXT_COLOR,
            font=self._fonts["label"],
            anchor="nw",
        )
        self.canvas.create_text(
            SUB_LABEL3_POS[0],
            SUB_LABEL3_POS[1],
            text="바이낸스 UID",
            fill=UI_TEXT_COLOR,
            font=self._fonts["label"],
            anchor="nw",
        )

        self.canvas.create_image(SUB_ICON_API_POS[0], SUB_ICON_API_POS[1], image=self._icon_api, anchor="nw")
        self.canvas.create_image(SUB_ICON1_POS[0], SUB_ICON1_POS[1], image=self._icon_tv, anchor="nw")
        self.canvas.create_image(SUB_ICON2_POS[0], SUB_ICON2_POS[1], image=self._icon_telegram, anchor="nw")
        self.canvas.create_image(SUB_ICON3_POS[0], SUB_ICON3_POS[1], image=self._icon_binance, anchor="nw")

        self._submit_rect_id = self.canvas.create_rectangle(
            SUB_SUBMIT_RECT[0],
            SUB_SUBMIT_RECT[1],
            SUB_SUBMIT_RECT[2],
            SUB_SUBMIT_RECT[3],
            fill=BUTTON_BG,
            outline="",
            tags=("submit_btn",),
        )
        submit_cx = (SUB_SUBMIT_RECT[0] + SUB_SUBMIT_RECT[2]) / 2
        submit_cy = (SUB_SUBMIT_RECT[1] + SUB_SUBMIT_RECT[3]) / 2
        self._submit_text_id = self.canvas.create_text(
            submit_cx,
            submit_cy,
            text="💎 구독자 등록 요청하기",
            fill=BUTTON_FG,
            font=self._fonts["button"],
            anchor="center",
            tags=("submit_btn",),
        )

        self._help_left_id = self.canvas.create_rectangle(
            SUB_HELP_LEFT_RECT[0],
            SUB_HELP_LEFT_RECT[1],
            SUB_HELP_LEFT_RECT[2],
            SUB_HELP_LEFT_RECT[3],
            fill=BUTTON_BG,
            outline="",
            tags=("help_left",),
        )
        self._help_right_id = self.canvas.create_rectangle(
            SUB_HELP_RIGHT_RECT[0],
            SUB_HELP_RIGHT_RECT[1],
            SUB_HELP_RIGHT_RECT[2],
            SUB_HELP_RIGHT_RECT[3],
            fill=BUTTON_BG,
            outline="",
            tags=("help_right",),
        )
        self._help_api_id = self.canvas.create_rectangle(
            SUB_HELP_API_RECT[0],
            SUB_HELP_API_RECT[1],
            SUB_HELP_API_RECT[2],
            SUB_HELP_API_RECT[3],
            fill=BUTTON_BG,
            outline="",
            tags=("help_api",),
        )
        help_left_cx = (SUB_HELP_LEFT_RECT[0] + SUB_HELP_LEFT_RECT[2]) / 2
        help_left_cy = (SUB_HELP_LEFT_RECT[1] + SUB_HELP_LEFT_RECT[3]) / 2
        help_right_cx = (SUB_HELP_RIGHT_RECT[0] + SUB_HELP_RIGHT_RECT[2]) / 2
        help_right_cy = (SUB_HELP_RIGHT_RECT[1] + SUB_HELP_RIGHT_RECT[3]) / 2
        help_api_cx = (SUB_HELP_API_RECT[0] + SUB_HELP_API_RECT[2]) / 2
        help_api_cy = (SUB_HELP_API_RECT[1] + SUB_HELP_API_RECT[3]) / 2
        self.canvas.create_text(
            help_left_cx,
            help_left_cy,
            text="❓ 바이낸스 UID는 어떻게 확인할 수 있나요?",
            fill=BUTTON_FG,
            font=self._fonts["button"],
            anchor="center",
            tags=("help_left",),
        )
        self.canvas.create_text(
            help_right_cx,
            help_right_cy,
            text="❓ 트레이딩뷰 ID는 어떻게 확인할 수 있나요?",
            fill=BUTTON_FG,
            font=self._fonts["button"],
            anchor="center",
            tags=("help_right",),
        )
        self.canvas.create_text(
            help_api_cx,
            help_api_cy,
            text="🔑 API Key 발급 가이드",
            fill=BUTTON_FG,
            font=self._fonts["button"],
            anchor="center",
            tags=("help_api",),
        )

    def _create_entries(self) -> None:
        self._entry_api = SubscriberEntry(self, self._fonts["entry"], "로그인에 사용하실 API KEY를 입력해주세요")
        self._entry_tv = SubscriberEntry(self, self._fonts["entry"], "트레이딩뷰 ID를 입력해주세요")
        self._entry_telegram = SubscriberEntry(self, self._fonts["entry"], "텔레그램 ID를 입력해주세요")
        self._entry_binance = SubscriberEntry(self, self._fonts["entry"], "바이낸스 UID를 입력해주세요")

        self._entry_api.place(SUB_ENTRY_API_POS[0], SUB_ENTRY_API_POS[1], SUB_ENTRY_WIDTH, SUB_ENTRY_HEIGHT)
        self._entry_tv.place(SUB_ENTRY1_POS[0], SUB_ENTRY1_POS[1], SUB_ENTRY_WIDTH, SUB_ENTRY_HEIGHT)
        self._entry_telegram.place(SUB_ENTRY2_POS[0], SUB_ENTRY2_POS[1], SUB_ENTRY_WIDTH, SUB_ENTRY_HEIGHT)
        self._entry_binance.place(SUB_ENTRY3_POS[0], SUB_ENTRY3_POS[1], SUB_ENTRY_WIDTH, SUB_ENTRY_HEIGHT)

    def _bind_buttons(self) -> None:
        self._button_anim_jobs: Dict[int, str] = {}
        buttons = {
            "submit_btn": self._submit_rect_id,
            "help_left": self._help_left_id,
            "help_right": self._help_right_id,
            "help_api": self._help_api_id,
        }
        for tag, rect_id in buttons.items():
            self.canvas.tag_bind(
                tag,
                "<Enter>",
                lambda _event, rid=rect_id: self._on_button_hover(rid, True),
            )
            self.canvas.tag_bind(
                tag,
                "<Leave>",
                lambda _event, rid=rect_id: self._on_button_hover(rid, False),
            )
        self.canvas.tag_bind("submit_btn", "<Button-1>", self._on_submit_click)
        self.canvas.tag_bind("help_left", "<Button-1>", self._on_binance_help_click)
        self.canvas.tag_bind("help_right", "<Button-1>", self._on_tradingview_help_click)
        self.canvas.tag_bind("help_api", "<Button-1>", self._on_api_help_click)

    def _on_button_hover(self, rect_id: int, hovering: bool) -> None:
        self.canvas.configure(cursor="hand2" if hovering else "")
        target = "#1a1a1a" if hovering else BUTTON_BG
        self._animate_button_fill(rect_id, target)

    def _animate_button_fill(self, rect_id: int, target_hex: str) -> None:
        if self._button_anim_jobs.get(rect_id):
            self.after_cancel(self._button_anim_jobs[rect_id])
            self._button_anim_jobs.pop(rect_id, None)
        current = self.canvas.itemcget(rect_id, "fill") or BUTTON_BG
        if current == target_hex:
            return
        start = self._hex_to_rgb(current)
        end = self._hex_to_rgb(target_hex)
        steps = 6
        duration_ms = 120
        step_ms = max(1, duration_ms // steps)

        def step(i: int) -> None:
            t = i / steps
            color = tuple(int(s + (e - s) * t) for s, e in zip(start, end))
            self.canvas.itemconfigure(rect_id, fill=self._rgb_to_hex(color))
            if i < steps:
                self._button_anim_jobs[rect_id] = self.after(step_ms, lambda: step(i + 1))
            else:
                self._button_anim_jobs.pop(rect_id, None)

        step(1)

    @staticmethod
    def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
        color = color.lstrip("#")
        return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    @staticmethod
    def _rgb_to_hex(color: Tuple[int, int, int]) -> str:
        return "#{:02x}{:02x}{:02x}".format(*color)

    def _on_binance_help_click(self, _event: Optional[tk.Event] = None) -> None:
        self._open_help_pdf("binance_uid_check.pdf")

    def _on_tradingview_help_click(self, _event: Optional[tk.Event] = None) -> None:
        self._open_help_pdf("tradingview_id_check.pdf")

    def _on_api_help_click(self, _event: Optional[tk.Event] = None) -> None:
        self._open_help_pdf("binance_copy_api_guide.pdf")

    def _open_help_pdf(self, filename: str) -> None:
        base_dir = Path(__file__).resolve().parent
        pdf_path = base_dir / "image" / "login_page" / filename
        if not pdf_path.exists():
            messagebox.showerror("파일 없음", f"PDF 파일을 찾을 수 없습니다:\n{pdf_path}", parent=self)
            return
        try:
            self._open_file(pdf_path)
        except Exception as exc:
            messagebox.showerror("열기 실패", f"PDF를 열 수 없습니다:\n{exc}", parent=self)

    @staticmethod
    def _open_file(path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _on_submit_click(self, _event: Optional[tk.Event] = None) -> None:
        missing = []
        if not self._entry_api.get_value():
            missing.append("API KEY")
        if not self._entry_tv.get_value():
            missing.append("트레이딩뷰 닉네임")
        if not self._entry_telegram.get_value():
            missing.append("텔레그램 닉네임")
        if not self._entry_binance.get_value():
            missing.append("바이낸스 UID")

        if missing:
            missing_text = ", ".join(missing)
            messagebox.showwarning(
                "입력 확인",
                f"{missing_text}이 공란입니다. 모든 항목을 작성해주세요.",
                parent=self,
            )
            self.lift()
            self.focus_force()
            return

        confirmed = messagebox.askyesno(
            "등록 요청 확인",
            "입력하신 정보로 구독자 등록 요청을 전송합니다. 오타가 있는지 확인하십시오. "
            "등록 요청을 전송하시겠습니까?",
            parent=self,
        )
        self.lift()
        self.focus_force()
        if not confirmed:
            return

        api_key = self._entry_api.get_value()
        tv_nick = self._entry_tv.get_value()
        tg_nick = self._entry_telegram.get_value()
        uid = self._entry_binance.get_value()
        if self._send_subscriber_request(api_key, tv_nick, tg_nick, uid):
            messagebox.showinfo(
                "전송 완료",
                "구독요청 전송이 완료되었습니다. 등록여부는 작성하신 텔레그램으로 안내됩니다.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "전송 실패",
                "구독요청 전송에 실패했습니다. 사용자님의 인터넷 연결상태를 확인하시거나 관리자에게 문의하십시오.",
                parent=self,
            )
        self.lift()
        self.focus_force()

    def _send_subscriber_request(self, api_key: str, tv_nick: str, tg_nick: str, uid: str) -> bool:
        payload = {"api_key": api_key, "tv_nick": tv_nick, "tg_nick": tg_nick, "uid": uid}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            SUBSCRIBER_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=SUBSCRIBER_REQUEST_TIMEOUT_SEC) as response:
                status = getattr(response, "status", None) or response.getcode()
                return 200 <= status < 300
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
            return False



class LoginPage(tk.Frame):
    def __init__(self, master: tk.Widget, current_version: str = "", latest_version: str = "") -> None:
        super().__init__(master, bg=CANVAS_BG)
        self.root = self.winfo_toplevel()
        self._supports_alpha = self._init_alpha_support()
        self._anim_offset = 0
        self._secret_visible = False
        self._current_version = current_version or "--"
        self._latest_version = latest_version or "--"
        self._remember_var = tk.BooleanVar(value=True)
        self._required_var = tk.BooleanVar(value=False)
        self._required2_var = tk.BooleanVar(value=False)
        self._subscriber_window: Optional[SubscriberRequestWindow] = None

        self._base_fonts = {
            "title": (16, "bold"),
            "label": (12, "bold"),
            "entry": (12, "normal"),
            "note": (10, "bold"),
            "button": (14, "bold"),
            "checkbox": (11, "normal"),
            "icon": (12, "normal"),
            "info": (11, "bold"),
            "time": (11, "bold"),
            "help": (11, "bold"),
            "help_button": (11, "bold"),
        }
        self.fonts: Dict[str, tkfont.Font] = {
            name: tkfont.Font(self, family=FONT_FAMILY, size=size, weight=weight)
            for name, (size, weight) in self._base_fonts.items()
        }

        self.canvas = tk.Canvas(self, bg=CANVAS_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.bg_original = self._load_background()
        self.bg_photo: Optional[ImageTk.PhotoImage] = None
        self._last_bg_size: Optional[Tuple[int, int]] = None
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw")

        self.logo_original = self._load_logo()
        self.logo_photo: Optional[ImageTk.PhotoImage] = None
        self._last_logo_scale: Optional[float] = None
        self.logo_item = self.canvas.create_image(0, 0, anchor="center")

        self.info_panel_photo: Optional[ImageTk.PhotoImage] = None
        self._last_info_panel_size: Optional[Tuple[int, int]] = None
        self.info_panel_item = self.canvas.create_image(0, 0, anchor="nw")
        self.info_status_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.info_price_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.info_version_current_id = self.canvas.create_text(
            0,
            0,
            text=f"현재 버전 : {self._current_version}",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.info_version_latest_id = self.canvas.create_text(
            0,
            0,
            text=f"최신 버전 : {self._latest_version}",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.time_month_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=MONTH_COLOR,
            font=self.fonts["time"],
            anchor="e",
        )
        self.time_rest_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=UI_TEXT_COLOR,
            font=self.fonts["time"],
            anchor="w",
        )

        self.help_title1_id = self.canvas.create_text(
            0,
            0,
            text="🔑 아직 API 키가 없으신가요?",
            fill=UI_TEXT_COLOR,
            font=self.fonts["help"],
            anchor="nw",
        )
        self.help_title2_id = self.canvas.create_text(
            0,
            0,
            text="💎 API키는 있지만 로그인이 안되시나요?",
            fill=UI_TEXT_COLOR,
            font=self.fonts["help"],
            anchor="nw",
        )

        self.title_text_id = self.canvas.create_text(
            0,
            0,
            text="연결하실 API키를 입력하십시오",
            fill=UI_TEXT_COLOR,
            font=self.fonts["title"],
            anchor="center",
        )
        self.api_label_id = self.canvas.create_text(
            0,
            0,
            text="API Key",
            fill=UI_TEXT_COLOR,
            font=self.fonts["label"],
            anchor="nw",
        )
        self.secret_label_id = self.canvas.create_text(
            0,
            0,
            text="SECRET KEY  (Private)",
            fill=UI_TEXT_COLOR,
            font=self.fonts["label"],
            anchor="nw",
        )
        self.note_text_id = self.canvas.create_text(
            0,
            0,
            text="* Secret Key는 개발자조차도 열어볼 수 없도록 암호화되어 사용자의 PC 보안 금고에만 보관됩니다.",
            fill=NOTE_COLOR,
            font=self.fonts["note"],
            anchor="center",
        )
        self.remember_text_id = self.canvas.create_text(
            0,
            0,
            text=self._remember_text(),
            fill=UI_TEXT_COLOR,
            font=self.fonts["checkbox"],
            anchor="center",
        )
        self.required_text_id = self.canvas.create_text(
            0,
            0,
            text=self._required_text(),
            fill=UI_TEXT_COLOR,
            font=self.fonts["checkbox"],
            anchor="center",
        )
        self.required2_text_id = self.canvas.create_text(
            0,
            0,
            text=self._required2_text(),
            fill=UI_TEXT_COLOR,
            font=self.fonts["checkbox"],
            anchor="center",
        )

        self.api_row = EntryRow(self.canvas, self.fonts, on_paste=self._paste_api)
        self.secret_row = EntryRow(
            self.canvas,
            self.fonts,
            with_eye=True,
            on_eye=self._toggle_secret,
            on_paste=self._paste_secret,
        )
        self.secret_row.entry.configure(show="*")

        self.login_button = RoundedButton(
            self.canvas,
            text="Login",
            font=self.fonts["button"],
            radius=18,
        )
        self.help_button1 = RoundedButton(
            self.canvas,
            text="🔑 API Key 발급 가이드",
            font=self.fonts["help_button"],
            radius=12,
            command=self._open_api_guide,
        )
        self.help_button2 = RoundedButton(
            self.canvas,
            text="💎 구독자 등록 요청",
            font=self.fonts["help_button"],
            radius=12,
            command=self._open_subscriber_request,
        )
        self.help_button1.set_state("normal")
        self.help_button2.set_state("normal")

        self._bind_checkbox(self.remember_text_id, self._toggle_remember)
        self._bind_checkbox(self.required_text_id, self._toggle_required)
        self._bind_checkbox(self.required2_text_id, self._toggle_required2)

        self._update_login_state()
        self._refresh_market_info()
        self._refresh_clock()

        self.canvas.bind("<Configure>", self._on_resize)
        self._layout()

    def _load_logo(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        logo_path = base_dir / "image" / "login_page" / "logo1.png"
        return Image.open(logo_path).convert("RGBA")

    def _load_background(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        bg_path = base_dir / "image" / "login_page" / "login_bg.png"
        return Image.open(bg_path).convert("RGBA")

    def _open_api_guide(self) -> None:
        base_dir = Path(__file__).resolve().parent
        pdf_path = base_dir / "image" / "login_page" / "binance_copy_api_guide.pdf"
        if not pdf_path.exists():
            messagebox.showerror("파일 없음", f"PDF 파일을 찾을 수 없습니다:\n{pdf_path}")
            return
        try:
            self._open_file(pdf_path)
        except Exception as exc:
            messagebox.showerror("열기 실패", f"PDF를 열 수 없습니다:\n{exc}")

    def _open_subscriber_request(self) -> None:
        if self._subscriber_window is not None and self._subscriber_window.winfo_exists():
            self._subscriber_window.lift()
            self._subscriber_window.focus_force()
            return
        self._subscriber_window = SubscriberRequestWindow(self.root)
        self._subscriber_window.protocol("WM_DELETE_WINDOW", self._close_subscriber_request)

    def _close_subscriber_request(self) -> None:
        if self._subscriber_window is None:
            return
        try:
            self._subscriber_window.destroy()
        finally:
            self._subscriber_window = None

    def _open_file(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _bind_checkbox(self, item_id: int, callback) -> None:
        self.canvas.tag_bind(item_id, "<Button-1>", callback)
        self.canvas.tag_bind(item_id, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(item_id, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _init_alpha_support(self) -> bool:
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            return False
        return True

    def _remember_text(self) -> str:
        return ("[ v ] " if self._remember_var.get() else "[   ] ") + "계정 정보 기억하기 (Auto-fill)"

    def _toggle_remember(self, _event: Optional[tk.Event] = None) -> None:
        self._remember_var.set(not self._remember_var.get())
        self.canvas.itemconfigure(self.remember_text_id, text=self._remember_text())

    def _required_text(self) -> str:
        prefix = "[ v ] " if self._required_var.get() else "[   ] "
        return prefix + "(필수) 자동매매로 인한 손실에 대한 책임은 본인에게 있음을 확인합니다."

    def _toggle_required(self, _event: Optional[tk.Event] = None) -> None:
        self._required_var.set(not self._required_var.get())
        self.canvas.itemconfigure(self.required_text_id, text=self._required_text())
        self._update_login_state()

    def _required2_text(self) -> str:
        prefix = "[ v ] " if self._required2_var.get() else "[   ] "
        return prefix + "(필수) 사용자의 부주의로 인한 키 유출로 발생하는 손실은 당사가 책임지지 않는것에 동의합니다."

    def _toggle_required2(self, _event: Optional[tk.Event] = None) -> None:
        self._required2_var.set(not self._required2_var.get())
        self.canvas.itemconfigure(self.required2_text_id, text=self._required2_text())
        self._update_login_state()

    def _update_login_state(self) -> None:
        enabled = self._required_var.get() and self._required2_var.get()
        self.login_button.set_state("normal" if enabled else "disabled")

    def _paste_text(self, entry: tk.Entry) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def _paste_api(self) -> None:
        self._paste_text(self.api_row.entry)

    def _paste_secret(self) -> None:
        self._paste_text(self.secret_row.entry)

    def _toggle_secret(self) -> None:
        self._secret_visible = not self._secret_visible
        self.secret_row.entry.configure(show="" if self._secret_visible else "*")

    def _fetch_market_info(self) -> dict:
        try:
            import ccxt  # type: ignore
        except Exception:
            return {"online": False}

        try:
            exchange = ccxt.binance({"enableRateLimit": True})
            start = time.perf_counter()
            ticker = exchange.fetch_ticker("BTC/USDT")
            ping_ms = int((time.perf_counter() - start) * 1000)
            last = ticker.get("last") or ticker.get("close")
            percent = ticker.get("percentage")
            if percent is None:
                open_price = ticker.get("open")
                if open_price:
                    percent = (last - open_price) / open_price * 100
            return {
                "online": True,
                "ping_ms": ping_ms,
                "last": last,
                "percent": percent,
            }
        except Exception:
            return {"online": False}

    def _refresh_market_info(self) -> None:
        info = self._fetch_market_info()
        if not info.get("online"):
            status_text = "❌ Offline (--)"
            price_text = "$--"
            change_text = "(--%)"
        else:
            ping_ms = info.get("ping_ms", 0)
            status_text = f"📡 Online ({ping_ms}ms)"
            last = info.get("last") or 0
            price_text = f"$ {last:,.2f}"
            percent = info.get("percent")
            if percent is None:
                change_text = "(--%)"
            else:
                sign = "+" if percent >= 0 else ""
                change_text = f"({sign}{percent:.1f}%)"
        self.canvas.itemconfigure(self.info_status_id, text=status_text)
        self.canvas.itemconfigure(self.info_price_id, text=f"BTC/USDT : {price_text} {change_text}")
        self.after(30000, self._refresh_market_info)

    def _refresh_clock(self) -> None:
        now = datetime.now(timezone(timedelta(hours=9)))
        month = now.strftime("%b")
        hour = now.strftime("%I").lstrip("0") or "12"
        rest = f" {now.day} {now.year} {hour}:{now.strftime('%M')} {now.strftime('%p')}"
        self.canvas.itemconfigure(self.time_month_id, text=month)
        self.canvas.itemconfigure(self.time_rest_id, text=rest)
        self.after(1000, self._refresh_clock)

    def animate_in(self) -> None:
        self._anim_offset = ANIM_OFFSET
        if self._supports_alpha:
            try:
                self.root.attributes("-alpha", 0.0)
            except tk.TclError:
                self._supports_alpha = False

        frame_interval = int(1000 / FPS)
        total_frames = max(1, int(ANIM_DURATION_MS / frame_interval))

        def step(frame: int = 0) -> None:
            t = min(1.0, frame / total_frames)
            eased = _ease_out_cubic(t)
            self._anim_offset = ANIM_OFFSET * (1 - eased)
            if self._supports_alpha:
                try:
                    self.root.attributes("-alpha", eased)
                except tk.TclError:
                    self._supports_alpha = False
            self._layout()
            if frame < total_frames:
                self.after(frame_interval, step, frame + 1)
            else:
                if self._supports_alpha:
                    try:
                        self.root.attributes("-alpha", 1.0)
                    except tk.TclError:
                        self._supports_alpha = False
                self._anim_offset = 0
                self._layout()

        step()

    def _on_resize(self, _event: tk.Event) -> None:
        self._layout()

    def _set_font_scale(self, scale: float) -> None:
        for name, (base_size, _weight) in self._base_fonts.items():
            size = max(8, int(base_size * scale))
            self.fonts[name].configure(size=size)

    def _update_logo(self, scale: float) -> None:
        if self._last_logo_scale == scale:
            return
        self._last_logo_scale = scale
        logo_scale = 0.5
        target_w = max(1, int(self.logo_original.width * scale * logo_scale))
        target_h = max(1, int(self.logo_original.height * scale * logo_scale))
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self.logo_original.resize((target_w, target_h), resample)
        self.logo_photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfigure(self.logo_item, image=self.logo_photo)

    def _update_background(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        size = (width, height)
        if self._last_bg_size == size:
            return
        self._last_bg_size = size
        scale = max(width / self.bg_original.width, height / self.bg_original.height)
        target_w = max(1, int(self.bg_original.width * scale))
        target_h = max(1, int(self.bg_original.height * scale))
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self.bg_original.resize((target_w, target_h), resample)
        left = max(0, (target_w - width) // 2)
        top = max(0, (target_h - height) // 2)
        cropped = resized.crop((left, top, left + width, top + height))
        self.bg_photo = ImageTk.PhotoImage(cropped)
        self.canvas.itemconfigure(self.bg_item, image=self.bg_photo)
        self.canvas.coords(self.bg_item, 0, 0)

    def _update_info_panel(self, width: int, height: int, scale: float) -> None:
        size = (max(1, int(width)), max(1, int(height)))
        if self._last_info_panel_size == size:
            return
        self._last_info_panel_size = size
        radius = max(6, int(18 * scale))
        border = max(1, int(2 * scale))
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        inset = max(0, border // 2)
        rect = (inset, inset, size[0] - inset - 1, size[1] - inset - 1)
        if hasattr(draw, "rounded_rectangle"):
            draw.rounded_rectangle(
                rect,
                radius=radius,
                fill=_hex_to_rgba(PANEL_FILL, PANEL_ALPHA),
                outline=_hex_to_rgba(PANEL_BORDER, PANEL_BORDER_ALPHA),
                width=border,
            )
        else:
            draw.rectangle(
                rect,
                fill=_hex_to_rgba(PANEL_FILL, PANEL_ALPHA),
                outline=_hex_to_rgba(PANEL_BORDER, PANEL_BORDER_ALPHA),
                width=border,
            )
        self.info_panel_photo = ImageTk.PhotoImage(img)
        self.canvas.itemconfigure(self.info_panel_item, image=self.info_panel_photo)

    def _layout(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self._update_background(width, height)
        scale = min(width / BASE_WIDTH, height / BASE_HEIGHT)
        pad_x = (width - BASE_WIDTH * scale) / 2
        pad_y = (height - BASE_HEIGHT * scale) / 2

        self._set_font_scale(scale)
        self._update_logo(scale)

        info_w = INFO_PANEL_SIZE[0] * scale
        info_h = INFO_PANEL_SIZE[1] * scale
        info_x = pad_x + INFO_PANEL_POS[0] * scale
        info_y = pad_y + (INFO_PANEL_POS[1] + self._anim_offset) * scale
        self._update_info_panel(int(info_w), int(info_h), scale)
        self.canvas.coords(self.info_panel_item, info_x, info_y)

        info_center_x = info_x + info_w / 2
        self.canvas.coords(self.info_status_id, info_center_x, info_y + info_h * 0.22)
        self.canvas.coords(self.info_price_id, info_center_x, info_y + info_h * 0.42)
        time_y = info_y + info_h * 0.62
        time_x = info_center_x - max(0, int(50 * scale))
        self.canvas.coords(self.time_month_id, time_x, time_y)
        self.canvas.coords(self.time_rest_id, time_x, time_y)
        self.canvas.coords(self.info_version_current_id, info_center_x, info_y + info_h * 0.80)
        self.canvas.coords(self.info_version_latest_id, info_center_x, info_y + info_h * 0.92)

        help_x = pad_x + HELP_PANEL_POS[0] * scale
        help_y = pad_y + (HELP_PANEL_POS[1] + self._anim_offset) * scale
        help_pad_x = max(8, int(12 * scale))
        help_cursor_y = help_y
        self.canvas.coords(self.help_title1_id, help_x + help_pad_x, help_cursor_y)
        help_cursor_y += max(10, int(22 * scale))
        btn_w = HELP_BTN_W * scale
        btn_h = HELP_BTN_H * scale
        self.help_button1.place(x=help_x + help_pad_x, y=help_cursor_y, width=btn_w, height=btn_h, anchor="nw")
        self.help_button1.resize(btn_w, btn_h, scale)
        help_cursor_y += btn_h + max(10, int(16 * scale))
        self.canvas.coords(self.help_title2_id, help_x + help_pad_x, help_cursor_y)
        help_cursor_y += max(10, int(22 * scale))
        self.help_button2.place(x=help_x + help_pad_x, y=help_cursor_y, width=btn_w, height=btn_h, anchor="nw")
        self.help_button2.resize(btn_w, btn_h, scale)

        self.canvas.coords(
            self.logo_item,
            pad_x + LOGO_POS[0] * scale,
            pad_y + (LOGO_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.title_text_id,
            pad_x + TITLE_POS[0] * scale,
            pad_y + (TITLE_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.api_label_id,
            pad_x + API_LABEL_POS[0] * scale,
            pad_y + (API_LABEL_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.api_row.place(
            pad_x + API_ENTRY_POS[0] * scale,
            pad_y + (API_ENTRY_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
            ENTRY_W * scale,
            ENTRY_H * scale,
            scale,
        )
        self.canvas.coords(
            self.secret_label_id,
            pad_x + SECRET_LABEL_POS[0] * scale,
            pad_y + (SECRET_LABEL_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.secret_row.place(
            pad_x + SECRET_ENTRY_POS[0] * scale,
            pad_y + (SECRET_ENTRY_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
            ENTRY_W * scale,
            ENTRY_H * scale,
            scale,
        )
        self.canvas.coords(
            self.note_text_id,
            pad_x + NOTE_POS[0] * scale,
            pad_y + (NOTE_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        login_w = LOGIN_W * scale
        login_h = LOGIN_H * scale
        self.login_button.place(
            x=pad_x + LOGIN_BTN_POS[0] * scale,
            y=pad_y + (LOGIN_BTN_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
            width=login_w,
            height=login_h,
            anchor="center",
        )
        self.login_button.resize(login_w, login_h, scale)
        self.canvas.coords(
            self.remember_text_id,
            pad_x + CHECK_POS[0] * scale,
            pad_y + (CHECK_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.required_text_id,
            pad_x + REQUIRED_POS[0] * scale,
            pad_y + (REQUIRED_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.required2_text_id,
            pad_x + REQUIRED2_POS[0] * scale,
            pad_y + (REQUIRED2_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )

        wrap = max(240, int(ENTRY_W * scale))
        self.canvas.itemconfigure(self.title_text_id, width=wrap)
        self.canvas.itemconfigure(self.note_text_id, width=wrap)
        self.canvas.itemconfigure(self.required_text_id, width=wrap)
        self.canvas.itemconfigure(self.required2_text_id, width=wrap)
