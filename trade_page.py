from __future__ import annotations

import hashlib
import hmac
import math
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
from collections import Counter
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk
from typing import Callable, Dict, Optional, Tuple

import requests

from PIL import Image, ImageDraw, ImageTk

BASE_WIDTH = 1328
BASE_HEIGHT = 800

FONT_FAMILY = "Malgun Gothic"
CANVAS_BG = "#0b1020"
BACKGROUND_OFF_COLOR = "#222226"

TOP_ICON_GAP = 38
TOP_ICON_ROW_OFFSET_X = 16
EXIT_ICON_OFFSET_X = 12
EXIT_ICON_POS = (BASE_WIDTH - 24 - TOP_ICON_GAP + EXIT_ICON_OFFSET_X + TOP_ICON_ROW_OFFSET_X, 28)
EXIT_ICON_SIZE = 34
BG_TOGGLE_POS = (BASE_WIDTH - 24 - TOP_ICON_GAP * 2 + TOP_ICON_ROW_OFFSET_X, 28)
BG_TOGGLE_SIZE = 34

ANIM_DURATION_MS = 500
ANIM_OFFSET = 40
FPS = 60

PANEL_FILL = "#0b1220"
PANEL_BORDER = "#c4cedf"
PANEL_ALPHA = 165
PANEL_BORDER_ALPHA = 210
PANEL_RADIUS = 18
PANEL_BORDER_WIDTH = 2

STATUS_REFRESH_MS = 5000
BALANCE_SYNC_INTERVAL_SEC = 10 * 60
SUBSCRIBER_WEBHOOK_URL = (
    "https://script.google.com/macros/s/AKfycbyKBEsD_GQ125wrjPm8kUrcRvnZSuZ4DlHZTg-lEr1X_UX-CiY2U9W9g3Pd6JBc6xIS/exec"
)
SUBSCRIBER_REQUEST_TIMEOUT_SEC = 8

START_FILL = "#00b050"
STOP_FILL = "#ff0000"
SAVE_SETTINGS_FILL = "#00b050"
SAVE_SETTINGS_DISABLED_FILL = "#5f5f5f"
RESET_SETTINGS_FILL = "#7a7a7a"
BUTTON_TEXT_COLOR = "#ffffff"
BUTTON_ACTIVE_BORDER = "#1f5eff"
BUTTON_HOVER_LIFT = 6
BUTTON_HOVER_LIGHTEN = 26
BUTTON_HOVER_ANIM_MS = 120
BUTTON_HOVER_ANIM_STEPS = 6

UI_TEXT_COLOR = "#f6f8fc"
HIGHLIGHT_TEXT = "#ff0000"
WALLET_VALUE_COLOR = "#00ff7f"
TRADE_LOG_PATH = Path(tempfile.gettempdir()) / "LTS-Trade.log"

# Base layout coordinates (scaled from image/ex_image/ex_image.png).
CHART_RECT = (49, 112, 770, 446)
TABLE_RECT = (47, 466, 765, 753)

CAUTION_RECT = (779, 80, 1321, 256)
WALLET_RECT = (819, 263, 1292, 590)
WALLET_TEXT_Y_RATIO = 0.2
WALLET_SETTINGS_LINE_GAP = 12
WALLET_CONTENT_Y_OFFSET = 12
START_BUTTON_RECT = (872, 503, 1042, 555)
STOP_BUTTON_RECT = (1090, 503, 1260, 555)
MONITOR_RECT = (768, 600, 1325, 781)

FILTER_LABEL_FILL = "#ffffff"
FILTER_LABEL_OUTLINE = "#000000"
FILTER_LABEL_TEXT = "#000000"
FILTER_TEXT_OFFSET = 0
COMBOBOX_PADDING_Y = 2

# Monitor list layout (scaled from image/ex_image/ex_image.png).
MONITOR_REF_WIDTH = 557
MONITOR_REF_HEIGHT = 181

MONITOR_TITLE_TOP = 0 / MONITOR_REF_HEIGHT
MONITOR_TITLE_BOTTOM = 24 / MONITOR_REF_HEIGHT
MONITOR_TITLE_TEXT_Y = 12 / MONITOR_REF_HEIGHT
MONITOR_HEADER_TOP = 26 / MONITOR_REF_HEIGHT
MONITOR_HEADER_TEXT_Y = 36 / MONITOR_REF_HEIGHT
MONITOR_HEADER_LINE_Y = 47 / MONITOR_REF_HEIGHT

MONITOR_COL_SYMBOL_X = 29 / MONITOR_REF_WIDTH
MONITOR_COL_FILTER_X = (96 + 24) / MONITOR_REF_WIDTH
MONITOR_COL_STATUS_X = 271 / MONITOR_REF_WIDTH
MONITOR_COL_ENTRY_X = 388 / MONITOR_REF_WIDTH

# Active positions table layout (scaled from image/ex_image/ex_image.png).
TABLE_REF_WIDTH = 849
TABLE_REF_HEIGHT = 348

TABLE_TITLE_TOP = 17 / TABLE_REF_HEIGHT
TABLE_TITLE_BOTTOM = 58 / TABLE_REF_HEIGHT
TABLE_TITLE_TEXT_Y = 39.5 / TABLE_REF_HEIGHT
TABLE_HEADER_TOP = 60 / TABLE_REF_HEIGHT
TABLE_HEADER_TEXT_Y = 76 / TABLE_REF_HEIGHT
TABLE_HEADER_LINE_Y = 88 / TABLE_REF_HEIGHT

TABLE_ROW_LINE1_Y = 112 / TABLE_REF_HEIGHT
TABLE_ROW_LINE2_Y = 132 / TABLE_REF_HEIGHT
TABLE_ROW_BAR_TOP = 98 / TABLE_REF_HEIGHT
TABLE_ROW_BAR_BOTTOM = 139 / TABLE_REF_HEIGHT

TABLE_COL_SYMBOL_X = 59 / TABLE_REF_WIDTH
TABLE_COL_SIZE_X = 179 / TABLE_REF_WIDTH
TABLE_COL_ENTRY_X = 301 / TABLE_REF_WIDTH
TABLE_COL_CURRENT_X = 440 / TABLE_REF_WIDTH
TABLE_COL_PNL_X = 588 / TABLE_REF_WIDTH

TABLE_BAR_X1 = 34 / TABLE_REF_WIDTH
TABLE_BAR_X2 = 48 / TABLE_REF_WIDTH

TABLE_CLOSE_BUTTON_CENTER_X = 750 / TABLE_REF_WIDTH
TABLE_CLOSE_BUTTON_WIDTH = 78 / TABLE_REF_WIDTH
TABLE_CLOSE_BUTTON_HEIGHT = 24 / TABLE_REF_HEIGHT

TABLE_TITLE_FILL = "#e6f0ff"
TABLE_TITLE_BORDER = "#1f5eff"
TABLE_HEADER_FILL = "#17152f"
TABLE_HEADER_TEXT = "#ffffff"
TABLE_ROW_TEXT = "#ffffff"
TABLE_LINE_COLOR = "#ffffff"
TABLE_POS_COLOR = "#00b050"
TABLE_NEG_COLOR = "#ff0000"

# Close position window (close_position.png) layout constants.
CLOSE_WINDOW_WIDTH = 1199
CLOSE_WINDOW_HEIGHT = 720

CLOSE_SIDE_INDICATOR_RECT = (307, 256, 323, 288)
CLOSE_SYMBOL_POS = (334, 265)
CLOSE_LABEL_POS = (343, 297)
CLOSE_SIZE_POS = (326, 326)
CLOSE_SLIDER_RECT = (321, 423, 798, 457)
CLOSE_SLIDER_WIDTH_FACTOR = 1.0
CLOSE_SLIDER_THICKNESS_SCALE = 0.55
CLOSE_SLIDER_HANDLE_SCALE = 0.8
CLOSE_EXPECTED_POS = (772, 462)
CLOSE_BUTTON_RECT = (990, 435, 1140, 476)
CLOSE_INFO_LINE_GAP = 28
CLOSE_PERCENT_BOX_SIZE = (92, 28)
CLOSE_PERCENT_BUTTON_SIZE = (54, 22)
CLOSE_PERCENT_BUTTON_GAP = 12
CLOSE_PERCENT_BUTTON_OUTLINE = "#8f8f8f"
CLOSE_PERCENT_HOVER_LIGHTEN = 18
CLOSE_BUTTON_DOWN_SHIFT = 0.5

CLOSE_LONG_TEXT_COLOR = "#ff5050"
CLOSE_SHORT_TEXT_COLOR = "#00b050"
CLOSE_BUTTON_FILL = "#4d4d4d"
CLOSE_BUTTON_DISABLED = "#3a3a3a"
CLOSE_BUTTON_TEXT = "청산"
CLOSE_INPUT_BG = "#595959"
CLOSE_TEXT_COLOR = "#ffffff"

MDD_LABEL_RECT = (90, 156, 390, 188)
MDD_DROPDOWN_RECT = (90, 196, 390, 228)
TP_LABEL_RECT = (430, 156, 730, 188)
TP_DROPDOWN_RECT = (430, 196, 730, 228)
RISK_LABEL_RECT = (260, 262, 560, 294)
RISK_DROPDOWN_RECT = (260, 302, 560, 334)
SAVE_SETTINGS_BUTTON_RECT = (190, 352, 400, 388)
RESET_SETTINGS_BUTTON_RECT = (420, 352, 630, 388)

DEFAULT_MDD = "15%"
DEFAULT_TP_RATIO = "5%"
DEFAULT_RISK_FILTER = "보수적"


def _hex_to_rgba(value: str, alpha: int) -> Tuple[int, int, int, int]:
    value = value.lstrip("#")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r, g, b, alpha


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(color: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _lighten_hex(value: str, amount: int) -> str:
    if not value.startswith("#") or len(value) != 7:
        return value
    r, g, b = _hex_to_rgb(value)
    r = min(255, r + amount)
    g = min(255, g + amount)
    b = min(255, b + amount)
    return _rgb_to_hex((r, g, b))


def _round_rect_points(x1: float, y1: float, x2: float, y2: float, radius: float) -> list:
    r = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
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


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _trim_text(value: str, limit: int = 600) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(+{len(text) - limit} chars)"


def _log_trade(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        with open(TRADE_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass


class TradePage(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        api_key: str = "",
        secret_key: str = "",
        background_enabled: bool = True,
    ) -> None:
        super().__init__(master, bg=CANVAS_BG)
        self.root = self.winfo_toplevel()
        self._supports_alpha = self._init_alpha_support()
        self._anim_offset = 0
        self._background_enabled = background_enabled
        self._api_key = api_key.strip()
        self._secret_key = secret_key.strip()
        self._bg_toggle_original = self._load_background_toggle_icon()
        self._bg_toggle_photo: Optional[ImageTk.PhotoImage] = None
        self._last_bg_toggle_size: Optional[int] = None
        self._last_bg_toggle_enabled: Optional[bool] = None
        self._exit_icon_original = self._load_exit_icon()
        self._exit_icon_photo: Optional[ImageTk.PhotoImage] = None
        self._last_exit_icon_size: Optional[int] = None
        self._base_fonts = {
            "tab": (12, "normal"),
            "caution_title": (12, "bold"),
            "caution_body": (11, "normal"),
            "caution_highlight": (11, "bold"),
            "wallet": (12, "normal"),
            "wallet_value": (12, "bold"),
            "button": (14, "bold"),
            "dropdown": (10, "normal"),
            "filter_label": (11, "normal"),
            "table_title": (12, "bold"),
            "table_header": (10, "bold"),
            "table_row": (11, "normal"),
            "table_row_sub": (10, "normal"),
            "table_pnl": (11, "bold"),
            "table_pnl_sub": (10, "bold"),
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

        self.bg_toggle_item = self.canvas.create_image(0, 0, anchor="ne", tags=("bg_toggle",))
        self.canvas.tag_bind("bg_toggle", "<Button-1>", self._toggle_background)
        self.canvas.tag_bind("bg_toggle", "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("bg_toggle", "<Leave>", lambda _event: self.canvas.configure(cursor=""))

        self.exit_item = self.canvas.create_image(0, 0, anchor="ne", tags=("exit_app",))
        self.canvas.tag_bind("exit_app", "<Button-1>", self._request_exit)
        self.canvas.tag_bind("exit_app", "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("exit_app", "<Leave>", lambda _event: self.canvas.configure(cursor=""))

        self._panel_photos: Dict[str, ImageTk.PhotoImage] = {}
        self._panel_sizes: Dict[str, Tuple[int, int]] = {}
        self._close_button_photos: Dict[Tuple[int, int, bool], ImageTk.PhotoImage] = {}

        self._trade_state = "start"
        self._button_hover = {
            "start": False,
            "stop": False,
            "filter_save": False,
            "filter_reset": False,
        }
        self._button_lift = {
            "start": 0.0,
            "stop": 0.0,
            "filter_save": 0.0,
            "filter_reset": 0.0,
        }
        self._button_anim_jobs: Dict[str, Optional[str]] = {
            "start": None,
            "stop": None,
            "filter_save": None,
            "filter_reset": None,
        }
        self._wallet_value = "N"
        self._wallet_unit = "USDT"
        self._wallet_value_color = WALLET_VALUE_COLOR
        self._wallet_balance: Optional[float] = None
        self._wallet_fetch_started = False
        self._positions: list[dict] = []
        self._position_map: Dict[str, dict] = {}
        self._refresh_in_progress = False
        self._refresh_job: Optional[str] = None
        self._sheet_balance_sync_next_at = 0.0
        self._sheet_balance_sync_pending = True
        self._sheet_balance_sync_in_progress = False
        self._sheet_balance_sync_lock = threading.Lock()
        self._exchange_filters: Dict[str, Tuple[float, float]] = {}
        self._saved_filter_settings: Optional[dict] = None
        self._save_enabled = False
        self._close_window: Optional["ClosePositionWindow"] = None

        exit_manager = getattr(self.root, "_exit_manager", None)
        if exit_manager is not None:
            exit_manager.set_position_checker(self.has_open_positions)

        self._style = ttk.Style(self)
        self._configure_combobox_style("TradeFilter.TCombobox", COMBOBOX_PADDING_Y)

        self._create_widgets()
        self._saved_filter_settings = self._default_filter_settings()
        self._save_enabled = False
        self._bind_clickables()
        self._apply_background_mode()

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._clear_combo_focus, add="+")
        self._layout()

        self._start_wallet_fetch()
        self._start_status_refresh()

    def _create_widgets(self) -> None:
        self.chart_container = tk.Frame(self.canvas, bg=PANEL_FILL, highlightthickness=0, bd=0)
        self.chart_window = self.canvas.create_window(0, 0, window=self.chart_container, anchor="nw", state="hidden")

        self.mdd_dropdown = ttk.Combobox(
            self.canvas,
            values=["15%"],
            state="readonly",
            style="TradeFilter.TCombobox",
            justify="center",
        )
        self.mdd_dropdown.set(DEFAULT_MDD)
        self._bind_combobox_focus(self.mdd_dropdown)
        self.mdd_dropdown.bind("<<ComboboxSelected>>", self._on_filter_change, add="+")
        self.mdd_dropdown_window = self.canvas.create_window(0, 0, window=self.mdd_dropdown, anchor="nw")

        self.tp_ratio_dropdown = ttk.Combobox(
            self.canvas,
            values=["3%", "5%"],
            state="readonly",
            style="TradeFilter.TCombobox",
            justify="center",
        )
        self.tp_ratio_dropdown.set(DEFAULT_TP_RATIO)
        self._bind_combobox_focus(self.tp_ratio_dropdown)
        self.tp_ratio_dropdown.bind("<<ComboboxSelected>>", self._on_filter_change, add="+")
        self.tp_ratio_dropdown_window = self.canvas.create_window(0, 0, window=self.tp_ratio_dropdown, anchor="nw")

        self.risk_filter_dropdown = ttk.Combobox(
            self.canvas,
            values=["공격적", "보수적"],
            state="readonly",
            style="TradeFilter.TCombobox",
            justify="center",
        )
        self.risk_filter_dropdown.set(DEFAULT_RISK_FILTER)
        self._bind_combobox_focus(self.risk_filter_dropdown)
        self.risk_filter_dropdown.bind("<<ComboboxSelected>>", self._on_filter_change, add="+")
        self.risk_filter_dropdown_window = self.canvas.create_window(0, 0, window=self.risk_filter_dropdown, anchor="nw")

    def _load_background(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        bg_path = base_dir / "image" / "trade_page" / "trade_page_bg.png"
        return Image.open(bg_path).convert("RGBA")

    def _load_background_toggle_icon(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        icon_path = base_dir / "image" / "login_page" / "background_on_off.png"
        return Image.open(icon_path).convert("RGBA")

    def _load_exit_icon(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        icon_path = base_dir / "image" / "trade_page" / "exit.png"
        return Image.open(icon_path).convert("RGBA")

    def _toggle_background(self, _event: Optional[tk.Event] = None) -> None:
        self._background_enabled = not self._background_enabled
        self._apply_background_mode()
        self._layout()

    def _request_exit(self, _event: Optional[tk.Event] = None) -> None:
        exit_manager = getattr(self.root, "_exit_manager", None)
        if exit_manager is not None:
            exit_manager.request_exit()
            return
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def has_open_positions(self) -> bool:
        return bool(self._positions)

    def _apply_background_mode(self) -> None:
        bg_color = CANVAS_BG if self._background_enabled else BACKGROUND_OFF_COLOR
        self.configure(bg=bg_color)
        self.canvas.configure(bg=bg_color)
        if self._background_enabled:
            self._last_bg_size = None
        else:
            self.canvas.itemconfigure(self.bg_item, image="")

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

    def _init_alpha_support(self) -> bool:
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            return False
        return True

    def _bind_clickables(self) -> None:
        self._bind_tag(
            "trade_start",
            self._handle_start_click,
            on_enter=lambda _e: self._set_button_hover("start", True),
            on_leave=lambda _e: self._set_button_hover("start", False),
        )
        self._bind_tag(
            "trade_stop",
            lambda _e: self._set_trade_state("stop"),
            on_enter=lambda _e: self._set_button_hover("stop", True),
            on_leave=lambda _e: self._set_button_hover("stop", False),
        )
        self._bind_tag(
            "filter_save",
            self._handle_filter_save,
            on_enter=lambda _e: self._set_button_hover("filter_save", True),
            on_leave=lambda _e: self._set_button_hover("filter_save", False),
            enabled=lambda: self._save_enabled,
        )
        self._bind_tag(
            "filter_reset",
            self._handle_filter_reset,
            on_enter=lambda _e: self._set_button_hover("filter_reset", True),
            on_leave=lambda _e: self._set_button_hover("filter_reset", False),
        )

    def _bind_tag(self, tag: str, handler, on_enter=None, on_leave=None, enabled: Optional[Callable[[], bool]] = None) -> None:
        def is_enabled() -> bool:
            return enabled() if enabled is not None else True

        def handle_click(event: tk.Event) -> None:
            if not is_enabled():
                return
            handler(event)

        def handle_enter(event: tk.Event) -> None:
            if is_enabled():
                self.canvas.configure(cursor="hand2")
                if on_enter is not None:
                    on_enter(event)
            else:
                self.canvas.configure(cursor="")

        def handle_leave(event: tk.Event) -> None:
            self.canvas.configure(cursor="")
            if on_leave is not None:
                on_leave(event)

        self.canvas.tag_bind(tag, "<Button-1>", handle_click)
        self.canvas.tag_bind(tag, "<Enter>", handle_enter)
        self.canvas.tag_bind(tag, "<Leave>", handle_leave)

    def _set_button_hover(self, key: str, hovering: bool) -> None:
        if self._button_hover.get(key) == hovering:
            return
        self._button_hover[key] = hovering
        target = -BUTTON_HOVER_LIFT if hovering else 0.0
        self._animate_button_lift(key, target)

    def _set_close_button_hover(self, key: str, hovering: bool) -> None:
        if self._button_hover.get(key) == hovering:
            return
        self._button_hover[key] = hovering
        target = -BUTTON_HOVER_LIFT if hovering else 0.0
        self._animate_button_lift(key, target)

    def _animate_button_lift(self, key: str, target: float) -> None:
        if key not in self._button_lift:
            return
        job = self._button_anim_jobs.get(key)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        start = self._button_lift.get(key, 0.0)
        if abs(start - target) < 0.1:
            self._button_lift[key] = target
            self._layout()
            self._button_anim_jobs[key] = None
            return
        steps = BUTTON_HOVER_ANIM_STEPS
        step_ms = max(1, BUTTON_HOVER_ANIM_MS // steps)

        def step(i: int) -> None:
            t = i / steps
            self._button_lift[key] = start + (target - start) * t
            self._layout()
            if i < steps:
                self._button_anim_jobs[key] = self.after(step_ms, lambda: step(i + 1))
            else:
                self._button_anim_jobs[key] = None

        step(1)

    def _configure_combobox_style(self, style_name: str, padding_y: int) -> None:
        self._style.configure(
            style_name,
            font=self.fonts["dropdown"],
            foreground="#000000",
            fieldbackground="#ffffff",
            background="#ffffff",
            padding=(0, padding_y, 0, padding_y),
        )
        self._style.map(
            style_name,
            foreground=[("readonly", "#000000")],
            fieldbackground=[("readonly", "#ffffff")],
            selectforeground=[("readonly", "#000000")],
            selectbackground=[("readonly", "#ffffff")],
        )

    def _bind_combobox_focus(self, combobox: ttk.Combobox) -> None:
        def clear_selection(_event=None) -> None:
            combobox.selection_clear()

        combobox.bind("<FocusOut>", clear_selection, add="+")
        combobox.bind("<<ComboboxSelected>>", lambda _e: self.after(1, clear_selection), add="+")

    def _clear_combo_focus(self, _event: tk.Event) -> None:
        self.canvas.focus_set()
        for widget in (
            self.mdd_dropdown,
            self.tp_ratio_dropdown,
            self.risk_filter_dropdown,
        ):
            widget.selection_clear()

    def _set_trade_state(self, value: str) -> None:
        if self._trade_state != value:
            self._trade_state = value
            self._layout()

    def _handle_start_click(self, _event=None) -> None:
        self._set_trade_state("start")

    @staticmethod
    def _default_filter_settings() -> dict:
        return {
            "mdd": DEFAULT_MDD,
            "tp_ratio": DEFAULT_TP_RATIO,
            "risk_filter": DEFAULT_RISK_FILTER,
        }

    def _current_filter_settings(self) -> dict:
        return {
            "mdd": self.mdd_dropdown.get(),
            "tp_ratio": self.tp_ratio_dropdown.get(),
            "risk_filter": self.risk_filter_dropdown.get(),
        }

    def _update_filter_save_state(self) -> None:
        current = self._current_filter_settings()
        saved = self._saved_filter_settings or self._default_filter_settings()
        enabled = current != saved
        if enabled != self._save_enabled:
            self._save_enabled = enabled
            if not enabled:
                self._button_hover["filter_save"] = False
                self._button_lift["filter_save"] = 0.0
            self._layout()

    def _on_filter_change(self, _event=None) -> None:
        self._update_filter_save_state()

    def _handle_filter_save(self, _event=None) -> None:
        if not self._save_enabled:
            return
        self._saved_filter_settings = self._current_filter_settings()
        self._update_filter_save_state()

    def _handle_filter_reset(self, _event=None) -> None:
        defaults = self._default_filter_settings()
        self.mdd_dropdown.set(defaults["mdd"])
        self.tp_ratio_dropdown.set(defaults["tp_ratio"])
        self.risk_filter_dropdown.set(defaults["risk_filter"])
        self._update_filter_save_state()

    def _on_resize(self, _event: tk.Event) -> None:
        self._layout()

    def _set_font_scale(self, scale: float) -> None:
        for name, (base_size, weight) in self._base_fonts.items():
            size = max(8, int(base_size * scale))
            self.fonts[name].configure(size=size, weight=weight)
        text_height = self.fonts["dropdown"].metrics("linespace")
        filter_height = (MDD_DROPDOWN_RECT[3] - MDD_DROPDOWN_RECT[1]) * scale
        filter_padding = max(0, int((filter_height - text_height) / 2))
        self._configure_combobox_style("TradeFilter.TCombobox", filter_padding)

    def _update_background(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if not self._background_enabled:
            self.canvas.itemconfigure(self.bg_item, image="")
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
        self.canvas.tag_lower(self.bg_item)

    def _update_background_toggle_icon(self, scale: float) -> None:
        size = max(16, int(BG_TOGGLE_SIZE * scale))
        if self._last_bg_toggle_size == size and self._last_bg_toggle_enabled == self._background_enabled:
            return
        self._last_bg_toggle_size = size
        self._last_bg_toggle_enabled = self._background_enabled
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self._bg_toggle_original.resize((size, size), resample)
        if not self._background_enabled:
            overlay = Image.new("RGBA", resized.size, (0, 0, 0, 140))
            resized = Image.alpha_composite(resized, overlay)
        self._bg_toggle_photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfigure(self.bg_toggle_item, image=self._bg_toggle_photo)

    def _update_exit_icon(self, scale: float) -> None:
        size = max(16, int(EXIT_ICON_SIZE * scale))
        if self._last_exit_icon_size == size:
            return
        self._last_exit_icon_size = size
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self._exit_icon_original.resize((size, size), resample)
        self._exit_icon_photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfigure(self.exit_item, image=self._exit_icon_photo)

    def _panel_image(self, name: str, width: int, height: int, scale: float) -> ImageTk.PhotoImage:
        size = (max(1, int(width)), max(1, int(height)))
        if self._panel_sizes.get(name) == size:
            return self._panel_photos[name]
        self._panel_sizes[name] = size
        radius = max(6, int(PANEL_RADIUS * scale))
        border = max(1, int(PANEL_BORDER_WIDTH * scale))
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
        self._panel_photos[name] = ImageTk.PhotoImage(img)
        return self._panel_photos[name]

    def _close_button_image(self, width: int, height: int, hover: bool) -> ImageTk.PhotoImage:
        size = (max(1, int(width)), max(1, int(height)))
        key = (size[0], size[1], hover)
        if key in self._close_button_photos:
            return self._close_button_photos[key]
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        radius = max(4, int(min(size) * 0.25))
        fill_alpha = 140 if not hover else 190
        border_alpha = 190 if not hover else 230
        fill = (0, 0, 0, fill_alpha)
        outline = (255, 255, 255, border_alpha)
        rect = (1, 1, size[0] - 2, size[1] - 2)
        if hasattr(draw, "rounded_rectangle"):
            draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=1)
        else:
            draw.rectangle(rect, fill=fill, outline=outline, width=1)
        photo = ImageTk.PhotoImage(img)
        self._close_button_photos[key] = photo
        return photo

    def _scale_rect(self, rect: Tuple[int, int, int, int], scale: float, pad_x: float, pad_y: float) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = rect
        return (
            pad_x + x1 * scale,
            pad_y + y1 * scale,
            pad_x + x2 * scale,
            pad_y + y2 * scale,
        )

    def _layout(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        scale = min(width / BASE_WIDTH, height / BASE_HEIGHT)
        pad_x = (width - BASE_WIDTH * scale) / 2
        pad_y = (height - BASE_HEIGHT * scale) / 2

        self._set_font_scale(scale)
        self._update_background(width, height)
        self._update_background_toggle_icon(scale)
        self._update_exit_icon(scale)

        self.canvas.delete("ui")

        content_pad_y = pad_y + self._anim_offset * scale
        self._draw_chart(scale, pad_x, content_pad_y)
        self._draw_table(scale, pad_x, content_pad_y)
        self._draw_caution(scale, pad_x, content_pad_y)
        self._draw_wallet(scale, pad_x, content_pad_y)
        self._draw_monitor_list(scale, pad_x, content_pad_y)

        self.canvas.coords(
            self.bg_toggle_item,
            pad_x + BG_TOGGLE_POS[0] * scale,
            pad_y + (BG_TOGGLE_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.tag_raise(self.bg_toggle_item)
        self.canvas.coords(
            self.exit_item,
            pad_x + EXIT_ICON_POS[0] * scale,
            pad_y + (EXIT_ICON_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.tag_raise(self.exit_item)

    def _draw_chart(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(CHART_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("chart", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        inset = max(2, int(3 * scale))
        self.canvas.coords(self.chart_window, x1 + inset, y1 + inset)
        self.canvas.itemconfigure(
            self.chart_window,
            width=max(1, int((x2 - x1) - inset * 2)),
            height=max(1, int((y2 - y1) - inset * 2)),
        )
        state = "normal" if self.chart_container.winfo_children() else "hidden"
        self.canvas.itemconfigure(self.chart_window, state=state)

        self._draw_filter_controls(scale, pad_x, pad_y)

    def _draw_filter_label(
        self,
        rect: Tuple[int, int, int, int],
        text: str,
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        border = max(1, int(1 * scale))
        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=FILTER_LABEL_FILL,
            outline=FILTER_LABEL_OUTLINE,
            width=border,
            tags="ui",
        )
        inner_y1 = y1 + border
        inner_y2 = y2 - border
        self.canvas.create_text(
            (x1 + x2) / 2,
            (inner_y1 + inner_y2) / 2 + FILTER_TEXT_OFFSET * scale,
            text=text,
            font=self.fonts["filter_label"],
            fill=FILTER_LABEL_TEXT,
            anchor="center",
            tags="ui",
        )

    def _position_dropdown(
        self,
        window_id: int,
        rect: Tuple[int, int, int, int],
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        self.canvas.coords(window_id, x1, y1)
        self.canvas.itemconfigure(
            window_id,
            width=max(1, int(x2 - x1)),
            height=max(1, int(y2 - y1)),
        )
        self.canvas.tag_raise(window_id)

    def _draw_filter_controls(self, scale: float, pad_x: float, pad_y: float) -> None:
        def offset_rect(rect: Tuple[int, int, int, int], offset_y: float) -> Tuple[int, int, int, int]:
            x1, y1, x2, y2 = rect
            return (x1, y1 + offset_y, x2, y2 + offset_y)

        control_rects = [
            MDD_LABEL_RECT,
            MDD_DROPDOWN_RECT,
            TP_LABEL_RECT,
            TP_DROPDOWN_RECT,
            RISK_LABEL_RECT,
            RISK_DROPDOWN_RECT,
        ]
        min_y = min(rect[1] for rect in control_rects)
        max_y = max(rect[3] for rect in control_rects)
        controls_center_y = (min_y + max_y) / 2
        chart_center_y = (CHART_RECT[1] + CHART_RECT[3]) / 2
        offset_y = chart_center_y - controls_center_y

        self._draw_filter_label(offset_rect(MDD_LABEL_RECT, offset_y), "MDD (전체 시드대비 최대 손실범위)", scale, pad_x, pad_y)
        self._draw_filter_label(offset_rect(TP_LABEL_RECT, offset_y), "TP-Ratio (포지션 수익 실현 범위)", scale, pad_x, pad_y)
        self._draw_filter_label(offset_rect(RISK_LABEL_RECT, offset_y), "위험 종목 필터링 성향", scale, pad_x, pad_y)

        self._position_dropdown(self.mdd_dropdown_window, offset_rect(MDD_DROPDOWN_RECT, offset_y), scale, pad_x, pad_y)
        self._position_dropdown(self.tp_ratio_dropdown_window, offset_rect(TP_DROPDOWN_RECT, offset_y), scale, pad_x, pad_y)
        self._position_dropdown(self.risk_filter_dropdown_window, offset_rect(RISK_DROPDOWN_RECT, offset_y), scale, pad_x, pad_y)
        save_enabled = self._save_enabled
        save_fill = SAVE_SETTINGS_FILL if save_enabled else SAVE_SETTINGS_DISABLED_FILL
        self._draw_rounded_button(
            offset_rect(SAVE_SETTINGS_BUTTON_RECT, offset_y),
            "설정 저장",
            save_fill,
            "filter_save",
            active=False,
            hover=self._button_hover.get("filter_save", False) if save_enabled else False,
            lift=self._button_lift.get("filter_save", 0.0) if save_enabled else 0.0,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        self._draw_rounded_button(
            offset_rect(RESET_SETTINGS_BUTTON_RECT, offset_y),
            "기본값 변환",
            RESET_SETTINGS_FILL,
            "filter_reset",
            active=False,
            hover=self._button_hover.get("filter_reset", False),
            lift=self._button_lift.get("filter_reset", 0.0),
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )

    def _draw_table(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(TABLE_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("table", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        width = x2 - x1
        height = y2 - y1

        y_shift = -TABLE_TITLE_TOP

        def rx(ratio: float) -> float:
            return x1 + width * ratio

        def ry(ratio: float) -> float:
            return y1 + height * (ratio + y_shift)

        border = max(1, int(2 * scale))

        title_top = ry(TABLE_TITLE_TOP)
        title_bottom = ry(TABLE_TITLE_BOTTOM)
        title_text_y = ry(TABLE_TITLE_TEXT_Y)
        header_top = ry(TABLE_HEADER_TOP)
        header_text_y = ry(TABLE_HEADER_TEXT_Y)
        header_line_y = ry(TABLE_HEADER_LINE_Y)

        # Title bar with rounded top corners
        radius = max(6, int(PANEL_RADIUS * scale))
        title_points = _round_rect_points(x1, title_top, x2, title_bottom, radius)
        self.canvas.create_polygon(
            title_points,
            fill=TABLE_TITLE_FILL,
            outline=TABLE_TITLE_BORDER,
            width=border,
            smooth=True,
            splinesteps=36,
            tags="ui",
        )
        if title_bottom - title_top > radius:
            self.canvas.create_rectangle(
                x1,
                title_top + radius,
                x2,
                title_bottom,
                fill=TABLE_TITLE_FILL,
                outline="",
                tags="ui",
            )
        self.canvas.create_text(
            (x1 + x2) / 2,
            title_text_y,
            text="활성화된 포지션",
            font=self.fonts["table_title"],
            fill="#000000",
            anchor="center",
            tags="ui",
        )

        # Header background and divider lines
        self.canvas.create_line(x1, header_top, x2, header_top, fill=TABLE_TITLE_BORDER, width=border, tags="ui")
        self.canvas.create_rectangle(x1, header_top, x2, header_line_y, fill=TABLE_HEADER_FILL, outline="", tags="ui")
        self.canvas.create_line(x1, header_line_y, x2, header_line_y, fill=TABLE_LINE_COLOR, width=max(1, int(1 * scale)), tags="ui")

        # Header labels (left-aligned to column starts)
        headers = [
            ("종목", TABLE_COL_SYMBOL_X),
            ("사이즈", TABLE_COL_SIZE_X),
            ("진입가격", TABLE_COL_ENTRY_X),
            ("현재가격", TABLE_COL_CURRENT_X),
            ("PNL", TABLE_COL_PNL_X),
        ]
        for label, x_ratio in headers:
            self.canvas.create_text(
                rx(x_ratio),
                header_text_y,
                text=label,
                font=self.fonts["table_header"],
                fill=TABLE_HEADER_TEXT,
                anchor="w",
                tags="ui",
            )

        self._draw_active_positions(rx, ry)

    def _draw_active_positions(self, rx, ry) -> None:
        if not self._positions:
            return
        table_w = rx(1) - rx(0)
        table_h = ry(1) - ry(0)
        base_table_w = TABLE_RECT[2] - TABLE_RECT[0]
        scale = table_w / base_table_w if base_table_w else 1.0
        row_step = (TABLE_ROW_BAR_BOTTOM - TABLE_ROW_BAR_TOP) + (TABLE_ROW_BAR_TOP - TABLE_HEADER_LINE_Y)
        drawn = 0

        for raw_position in self._positions:
            position = self._format_position_display(raw_position)
            if not position:
                continue
            offset = row_step * drawn
            if TABLE_ROW_BAR_BOTTOM + offset > 1.0:
                break

            bar_color = TABLE_POS_COLOR if position["side"] == "long" else TABLE_NEG_COLOR
            self.canvas.create_rectangle(
                rx(TABLE_BAR_X1),
                ry(TABLE_ROW_BAR_TOP + offset),
                rx(TABLE_BAR_X2),
                ry(TABLE_ROW_BAR_BOTTOM + offset),
                fill=bar_color,
                outline="",
                tags="ui",
            )

            line1_y = ry(TABLE_ROW_LINE1_Y + offset)
            line2_y = ry(TABLE_ROW_LINE2_Y + offset)

            self.canvas.create_text(
                rx(TABLE_COL_SYMBOL_X),
                line1_y,
                text=position["symbol"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(TABLE_COL_SYMBOL_X),
                line2_y,
                text=position["perp_text"],
                font=self.fonts["table_row_sub"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )

            self.canvas.create_text(
                rx(TABLE_COL_SIZE_X),
                line1_y,
                text=position["size_text"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(TABLE_COL_ENTRY_X),
                line1_y,
                text=position["entry_text"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(TABLE_COL_CURRENT_X),
                line1_y,
                text=position["current_text"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )

            pnl_color = TABLE_POS_COLOR if position["pnl_value"] >= 0 else TABLE_NEG_COLOR
            self.canvas.create_text(
                rx(TABLE_COL_PNL_X),
                line1_y,
                text=position["pnl_text"],
                font=self.fonts["table_pnl"],
                fill=pnl_color,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(TABLE_COL_PNL_X),
                line2_y,
                text=position["pnl_pct_text"],
                font=self.fonts["table_pnl_sub"],
                fill=pnl_color,
                anchor="w",
                tags="ui",
            )

            position_key = position.get("key")
            if position_key:
                tag_key = f"close_btn_{position_key.replace(':', '_')}"
                if tag_key not in self._button_lift:
                    self._button_lift[tag_key] = 0.0
                    self._button_hover[tag_key] = False
                    self._button_anim_jobs[tag_key] = None
                btn_center_x = rx(TABLE_CLOSE_BUTTON_CENTER_X)
                btn_center_y = (line1_y + line2_y) / 2
                btn_w = table_w * TABLE_CLOSE_BUTTON_WIDTH
                btn_h = table_h * TABLE_CLOSE_BUTTON_HEIGHT
                lift = self._button_lift.get(tag_key, 0.0)
                btn_x1 = btn_center_x - btn_w / 2
                btn_y1 = btn_center_y - btn_h / 2 + lift * scale
                btn_img = self._close_button_image(btn_w, btn_h, self._button_hover.get(tag_key, False))
                self.canvas.create_image(btn_x1, btn_y1, image=btn_img, anchor="nw", tags=("ui", tag_key))
                self.canvas.create_text(
                    btn_center_x,
                    btn_center_y + lift * scale,
                    text="청산",
                    font=self.fonts["table_row_sub"],
                    fill="#ffffff",
                    anchor="center",
                    tags=("ui", tag_key),
                )
                self._bind_tag(
                    tag_key,
                    lambda _e, key=position_key: self._open_close_position(key),
                    on_enter=lambda _e, k=tag_key: self._set_close_button_hover(k, True),
                    on_leave=lambda _e, k=tag_key: self._set_close_button_hover(k, False),
                )

            drawn += 1

    def _draw_monitor_list(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(MONITOR_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("monitor", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        width = x2 - x1
        height = y2 - y1

        def rx(ratio: float) -> float:
            return x1 + width * ratio

        def ry(ratio: float) -> float:
            return y1 + height * ratio

        border = max(1, int(2 * scale))

        title_top = ry(MONITOR_TITLE_TOP)
        title_bottom = ry(MONITOR_TITLE_BOTTOM)
        title_text_y = ry(MONITOR_TITLE_TEXT_Y)
        header_top = ry(MONITOR_HEADER_TOP)
        header_text_y = ry(MONITOR_HEADER_TEXT_Y)
        header_line_y = ry(MONITOR_HEADER_LINE_Y)

        radius = max(6, int(PANEL_RADIUS * scale))
        title_points = _round_rect_points(x1, title_top, x2, title_bottom, radius)
        self.canvas.create_polygon(
            title_points,
            fill=TABLE_TITLE_FILL,
            outline=TABLE_TITLE_BORDER,
            width=border,
            smooth=True,
            splinesteps=36,
            tags="ui",
        )
        if title_bottom - title_top > radius:
            self.canvas.create_rectangle(
                x1,
                title_top + radius,
                x2,
                title_bottom,
                fill=TABLE_TITLE_FILL,
                outline="",
                tags="ui",
            )
        self.canvas.create_text(
            (x1 + x2) / 2,
            title_text_y,
            text="타점 모니터링 리스트",
            font=self.fonts["table_title"],
            fill="#000000",
            anchor="center",
            tags="ui",
        )

        self.canvas.create_line(x1, header_top, x2, header_top, fill=TABLE_TITLE_BORDER, width=border, tags="ui")
        self.canvas.create_rectangle(x1, header_top, x2, header_line_y, fill=TABLE_HEADER_FILL, outline="", tags="ui")
        self.canvas.create_line(
            x1,
            header_line_y,
            x2,
            header_line_y,
            fill=TABLE_LINE_COLOR,
            width=max(1, int(1 * scale)),
            tags="ui",
        )

        headers = [
            ("종목", MONITOR_COL_SYMBOL_X),
            ("필터링 성향", MONITOR_COL_FILTER_X),
            ("상태", MONITOR_COL_STATUS_X),
            ("진입 예정가", MONITOR_COL_ENTRY_X),
        ]
        for label, x_ratio in headers:
            self.canvas.create_text(
                rx(x_ratio),
                header_text_y,
                text=label,
                font=self.fonts["table_header"],
                fill=TABLE_HEADER_TEXT,
                anchor="w",
                tags="ui",
            )

    def _draw_caution(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(CAUTION_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("caution", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        center_x = (x1 + x2) / 2
        box_h = y2 - y1
        line_gap = max(2, int(4 * scale))
        title_font = self.fonts["caution_title"]
        body_font = self.fonts["caution_body"]
        highlight_font = self.fonts["caution_highlight"]
        title_h = title_font.metrics("linespace")
        body_h = body_font.metrics("linespace")

        lines = [
            ("⚠️ 주의사항 ⚠️", title_font, "#ff0000"),
            ("보안을 위해 중앙서버 방식으로 통제되는 프로그램이 아니므로", body_font, UI_TEXT_COLOR),
            ("진행중인 포지션은 프로그램을 종료하셔도", body_font, UI_TEXT_COLOR),
            ("포지션이 자동으로 종료되지 않습니다.", highlight_font, HIGHLIGHT_TEXT),
            ("수동 제어를 원하시는 경우 바이낸스 모바일 혹은 PC에서 포지션을 닫아주세요.", body_font, UI_TEXT_COLOR),
        ]
        total_height = title_h + body_h * 4 + line_gap * (len(lines) - 1)
        start_y = y1 + (box_h - total_height) / 2

        cursor_y = start_y
        for text, font, color in lines:
            self.canvas.create_text(
                center_x,
                cursor_y,
                text=text,
                font=font,
                fill=color,
                anchor="n",
                tags="ui",
            )
            cursor_y += font.metrics("linespace") + line_gap

    def _draw_wallet(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(WALLET_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("wallet", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        center_x = (x1 + x2) / 2
        label = "나의 지갑 잔고 :"
        value = self._wallet_value
        suffix = self._wallet_unit
        font = self.fonts["wallet"]
        value_font = self.fonts["wallet_value"]
        suffix_font = self.fonts["wallet"]
        suffix_color = UI_TEXT_COLOR

        label_w = font.measure(label + " ")
        value_w = value_font.measure(value + " ")
        suffix_w = suffix_font.measure(suffix)
        total_w = label_w + value_w + suffix_w
        text_y = y1 + (y2 - y1) * WALLET_TEXT_Y_RATIO + WALLET_CONTENT_Y_OFFSET * scale
        start_x = center_x - total_w / 2

        self.canvas.create_text(
            start_x + label_w / 2,
            text_y,
            text=label,
            font=font,
            fill=UI_TEXT_COLOR,
            anchor="center",
            tags="ui",
        )
        self.canvas.create_text(
            start_x + label_w + value_w / 2,
            text_y,
            text=value,
            font=value_font,
            fill=self._wallet_value_color,
            anchor="center",
            tags="ui",
        )
        self.canvas.create_text(
            start_x + label_w + value_w + suffix_w / 2,
            text_y,
            text=suffix,
            font=suffix_font,
            fill=suffix_color,
            anchor="center",
            tags="ui",
        )

        settings = self._saved_filter_settings or self._default_filter_settings()
        line_font = self.fonts["wallet"]
        value_line_font = self.fonts["wallet_value"]
        line_height = max(line_font.metrics("linespace"), value_line_font.metrics("linespace"))
        line_gap = WALLET_SETTINGS_LINE_GAP * scale
        cursor_y = text_y + line_height + line_gap

        lines = [
            ("MDD :", settings.get("mdd") or "N%"),
            ("TP-Ratio :", settings.get("tp_ratio") or "N%"),
            ("필터링 성향 :", settings.get("risk_filter") or "보수적/공격적"),
        ]

        for label_text, value_text in lines:
            label_w = line_font.measure(label_text + " ")
            value_w = value_line_font.measure(value_text)
            total_w = label_w + value_w
            start_x = center_x - total_w / 2
            self.canvas.create_text(
                start_x + label_w / 2,
                cursor_y,
                text=label_text,
                font=line_font,
                fill=UI_TEXT_COLOR,
                anchor="center",
                tags="ui",
            )
            self.canvas.create_text(
                start_x + label_w + value_w / 2,
                cursor_y,
                text=value_text,
                font=value_line_font,
                fill=UI_TEXT_COLOR,
                anchor="center",
                tags="ui",
            )
            cursor_y += line_height + line_gap

        self._draw_trade_buttons(scale, pad_x, pad_y)

    def _draw_trade_buttons(self, scale: float, pad_x: float, pad_y: float) -> None:
        self._draw_rounded_button(
            START_BUTTON_RECT,
            "START",
            START_FILL,
            "trade_start",
            active=self._trade_state == "start",
            hover=self._button_hover.get("start", False),
            lift=self._button_lift.get("start", 0.0),
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        self._draw_rounded_button(
            STOP_BUTTON_RECT,
            "Stop",
            STOP_FILL,
            "trade_stop",
            active=self._trade_state == "stop",
            hover=self._button_hover.get("stop", False),
            lift=self._button_lift.get("stop", 0.0),
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )

    def _draw_rounded_button(
        self,
        rect: Tuple[int, int, int, int],
        text: str,
        fill: str,
        tag: str,
        active: bool,
        hover: bool,
        lift: float,
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        if lift:
            offset = lift * scale
            y1 += offset
            y2 += offset
        radius = max(6, int(10 * scale))
        border = max(1, int((3 if active else 1) * scale))
        outline = BUTTON_ACTIVE_BORDER if active else "#000000"
        fill_color = _lighten_hex(fill, BUTTON_HOVER_LIGHTEN) if hover else fill
        points = _round_rect_points(x1, y1, x2, y2, radius)
        self.canvas.create_polygon(
            points,
            fill=fill_color,
            outline=outline,
            width=border,
            smooth=True,
            splinesteps=36,
            tags=("ui", tag),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            font=self.fonts["button"],
            fill=BUTTON_TEXT_COLOR,
            anchor="center",
            tags=("ui", tag),
        )

    def _start_wallet_fetch(self) -> None:
        if self._wallet_fetch_started:
            return
        self._wallet_fetch_started = True
        if not self._api_key or not self._secret_key:
            self._set_wallet_failure()
            return
        thread = threading.Thread(target=self._fetch_wallet_balance, daemon=True)
        thread.start()

    def _submit_close_order(self, position: dict, quantity_text: str) -> Tuple[bool, str]:
        if not self._api_key or not self._secret_key:
            return False, "API 키 정보가 필요합니다."
        symbol = position.get("symbol")
        if not symbol:
            return False, "종목 정보를 찾을 수 없습니다."
        try:
            quantity = float(quantity_text)
        except (TypeError, ValueError):
            return False, "수량이 올바르지 않습니다."
        if quantity <= 0:
            return False, "수량이 올바르지 않습니다."
        position_amt = self._safe_float(position.get("positionAmt")) or 0.0
        side = "SELL" if position_amt > 0 else "BUY"
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity_text,
        }
        position_side = position.get("positionSide")
        if isinstance(position_side, str) and position_side:
            position_side = position_side.upper()
        else:
            position_side = ""
        if position_side and position_side != "BOTH":
            params["positionSide"] = position_side
        else:
            params["reduceOnly"] = "true"
        result = self._binance_signed_post("https://fapi.binance.com", "/fapi/v1/order", params)
        if not isinstance(result, dict) or "orderId" not in result:
            if isinstance(result, dict):
                _log_trade(
                    "Close order rejected: "
                    f"symbol={symbol} side={side} qty={quantity_text} "
                    f"positionSide={position_side} response={result!r}"
                )
                return False, str(result.get("msg") or "청산 주문에 실패했습니다.")
            _log_trade(
                "Close order failed: "
                f"symbol={symbol} side={side} qty={quantity_text} positionSide={position_side} response=None"
            )
            return False, "청산 주문에 실패했습니다."
        return True, ""

    def _fetch_wallet_balance(self) -> None:
        try:
            restrictions = self._fetch_api_restrictions()
            if not restrictions:
                self._set_wallet_failure_async()
                return
            if not (restrictions.get("enableReading") and restrictions.get("enableFutures")):
                self._set_wallet_failure_async()
                return
            balance = self._fetch_futures_balance()
            if balance is None:
                self._set_wallet_failure_async()
                return
            self._sync_wallet_balance_to_sheet(balance)
            positions = self._fetch_open_positions()
            self.after(0, lambda: self._set_wallet_value(balance))
            self.after(0, lambda: self._set_positions(positions or []))
        except Exception:
            self._set_wallet_failure_async()

    def _fetch_api_restrictions(self) -> Optional[dict]:
        return self._binance_signed_get("https://api.binance.com", "/sapi/v1/account/apiRestrictions")

    def _fetch_futures_balance(self) -> Optional[float]:
        data = self._binance_signed_get("https://fapi.binance.com", "/fapi/v2/balance")
        if not isinstance(data, list):
            return None
        for item in data:
            if item.get("asset") == "USDT":
                try:
                    return float(item.get("balance", 0))
                except (TypeError, ValueError):
                    return None
        return None

    def _fetch_open_positions(self) -> Optional[list[dict]]:
        data = self._binance_signed_get("https://fapi.binance.com", "/fapi/v2/positionRisk")
        if data is None or not isinstance(data, list):
            return None
        positions = []
        for item in data:
            position_amt = self._safe_float(item.get("positionAmt"))
            if position_amt is None or abs(position_amt) <= 1e-9:
                continue
            positions.append(item)
        positions.sort(key=lambda item: item.get("symbol", ""))
        return positions

    def _sync_wallet_balance_to_sheet(self, balance: float) -> None:
        if not self._api_key:
            return

        now = time.time()
        with self._sheet_balance_sync_lock:
            due = self._sheet_balance_sync_pending or now >= self._sheet_balance_sync_next_at
            if not due or self._sheet_balance_sync_in_progress:
                return
            self._sheet_balance_sync_in_progress = True

        success = False
        payload = {
            "action": "update_balance",
            "api_key": self._api_key,
            "balance": round(float(balance), 2),
        }

        try:
            response = requests.post(
                SUBSCRIBER_WEBHOOK_URL,
                json=payload,
                timeout=SUBSCRIBER_REQUEST_TIMEOUT_SEC,
            )
            response.raise_for_status()
            data = response.json()
            success = isinstance(data, dict) and data.get("result") == "updated"
        except (requests.RequestException, TypeError, ValueError):
            success = False
        finally:
            with self._sheet_balance_sync_lock:
                self._sheet_balance_sync_in_progress = False
                if success:
                    self._sheet_balance_sync_pending = False
                    self._sheet_balance_sync_next_at = time.time() + BALANCE_SYNC_INTERVAL_SEC
                else:
                    self._sheet_balance_sync_pending = True

    def _binance_signed_get(self, base_url: str, path: str, params: Optional[dict] = None) -> Optional[dict]:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        query = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def _binance_signed_post(self, base_url: str, path: str, params: Optional[dict] = None) -> Optional[dict]:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        query = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = requests.post(url, headers=headers, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"POST {path} failed status={response.status_code} params={params} detail={detail!r}"
                )
                return data if isinstance(data, dict) else None
            if data is None:
                _log_trade(
                    f"POST {path} returned non-JSON response status={response.status_code} "
                    f"params={params} body={_trim_text(response.text)!r}"
                )
            return data
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    data = response.json()
                except ValueError:
                    data = None
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"POST {path} request error status={response.status_code} "
                    f"params={params} detail={detail!r}"
                )
            else:
                _log_trade(f"POST {path} request error params={params} error={exc!r}")
            return None

    @staticmethod
    def _binance_public_get(base_url: str, path: str, params: Optional[dict] = None) -> Optional[dict]:
        params = dict(params or {})
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{query}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_symbol_filters(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        if symbol in self._exchange_filters:
            return self._exchange_filters[symbol]
        data = self._binance_public_get("https://fapi.binance.com", "/fapi/v1/exchangeInfo", {"symbol": symbol})
        min_qty = None
        step_size = None
        if isinstance(data, dict):
            for item in data.get("symbols", []):
                if item.get("symbol") != symbol:
                    continue
                for filt in item.get("filters", []):
                    if filt.get("filterType") == "LOT_SIZE":
                        min_qty = self._safe_float(filt.get("minQty"))
                        step_size = self._safe_float(filt.get("stepSize"))
                        break
                break
        self._exchange_filters[symbol] = (min_qty, step_size)
        return min_qty, step_size

    @staticmethod
    def _format_amount(value: float, decimals: int = 3) -> str:
        text = f"{value:.{decimals}f}"
        return text.rstrip("0").rstrip(".")

    @staticmethod
    def _format_price(value: float) -> str:
        return f"{value:,.2f}"

    @staticmethod
    def _format_leverage(value: float) -> str:
        if value.is_integer():
            return str(int(value))
        return TradePage._format_amount(value, 2)

    @staticmethod
    def _calc_roi(pnl: float, amount: float, entry_price: float, leverage: float) -> float:
        if amount <= 0 or entry_price <= 0:
            return 0.0
        if leverage > 0:
            return pnl * leverage / (amount * entry_price) * 100
        return pnl / (amount * entry_price) * 100

    @staticmethod
    def _position_key(position: dict) -> Optional[str]:
        symbol = position.get("symbol")
        if not symbol:
            return None
        try:
            position_amt = float(position.get("positionAmt", 0))
        except (TypeError, ValueError):
            return None
        if abs(position_amt) <= 1e-9:
            return None
        position_side = position.get("positionSide")
        if isinstance(position_side, str) and position_side and position_side.upper() != "BOTH":
            side_key = position_side.upper()
        else:
            side_key = "LONG" if position_amt > 0 else "SHORT"
        return f"{symbol}:{side_key}"

    def _format_position_display(self, position: dict) -> Optional[dict]:
        symbol = position.get("symbol")
        if not symbol:
            return None
        position_amt = self._safe_float(position.get("positionAmt"))
        if position_amt is None or abs(position_amt) <= 1e-9:
            return None
        position_key = self._position_key(position)
        entry_price = self._safe_float(position.get("entryPrice")) or 0.0
        mark_price = self._safe_float(position.get("markPrice"))
        if mark_price is None:
            mark_price = entry_price
        pnl_value = self._safe_float(position.get("unRealizedProfit")) or 0.0
        leverage_value = self._safe_float(position.get("leverage")) or 1.0

        side = "long" if position_amt > 0 else "short"
        base_asset = symbol[:-4] if symbol.endswith("USDT") else symbol
        size_text = f"{self._format_amount(abs(position_amt))} {base_asset}"
        entry_text = self._format_price(entry_price)
        current_text = self._format_price(mark_price)

        pnl_sign = "+" if pnl_value >= 0 else "-"
        pnl_text = f"{pnl_sign}{abs(pnl_value):,.2f} USDT"
        roi_value = self._calc_roi(pnl_value, abs(position_amt), entry_price, leverage_value)
        roi_sign = "+" if roi_value >= 0 else "-"
        pnl_pct_text = f"{roi_sign}{abs(roi_value):.3f}%"

        return {
            "key": position_key,
            "symbol": symbol,
            "side": side,
            "perp_text": f"Perp x{self._format_leverage(leverage_value)}",
            "size_text": size_text,
            "entry_text": entry_text,
            "current_text": current_text,
            "pnl_text": pnl_text,
            "pnl_pct_text": pnl_pct_text,
            "pnl_value": pnl_value,
        }

    def _set_positions(self, positions: list[dict]) -> None:
        self._positions = positions or []
        self._position_map = {}
        for position in self._positions:
            key = self._position_key(position)
            if key:
                self._position_map[key] = position
        self._layout()
        self._sync_close_window()

    def _sync_close_window(self) -> None:
        window = self._close_window
        if window is None:
            return
        try:
            if not window.winfo_exists():
                self._close_window = None
                return
        except tk.TclError:
            self._close_window = None
            return
        window.sync_position(self._position_map)

    def _open_close_position(self, position_key: str) -> None:
        position = self._position_map.get(position_key)
        if not position:
            return
        if self._close_window is not None and self._close_window.winfo_exists():
            try:
                self._close_window.destroy()
            except tk.TclError:
                pass
            self._close_window = None
        self._close_window = ClosePositionWindow(self, position)

    def _set_wallet_value(self, balance: float) -> None:
        self._wallet_balance = balance
        self._wallet_value = f"{balance:,.2f}"
        self._wallet_unit = "USDT"
        self._wallet_value_color = WALLET_VALUE_COLOR
        self._layout()

    def _set_wallet_failure(self) -> None:
        self._wallet_balance = None
        self._wallet_value = "연결실패"
        self._wallet_unit = ""
        self._wallet_value_color = HIGHLIGHT_TEXT
        self._positions = []
        self._layout()

    def _set_wallet_failure_async(self) -> None:
        self.after(0, self._set_wallet_failure)

    def _start_status_refresh(self) -> None:
        if self._refresh_job is None:
            self._refresh_job = self.after(STATUS_REFRESH_MS, self._schedule_status_refresh)

    def _schedule_status_refresh(self) -> None:
        self._refresh_job = None
        if not self._api_key or not self._secret_key:
            return
        if self._refresh_in_progress:
            self._start_status_refresh()
            return
        self._refresh_in_progress = True
        thread = threading.Thread(target=self._refresh_status, daemon=True)
        thread.start()

    def _refresh_status(self) -> None:
        try:
            balance = self._fetch_futures_balance()
            positions = self._fetch_open_positions()
            if balance is not None:
                self._sync_wallet_balance_to_sheet(balance)
        except Exception:
            balance = None
            positions = None

        def apply() -> None:
            if balance is not None:
                self._set_wallet_value(balance)
            if positions is not None:
                self._set_positions(positions)
            self._refresh_in_progress = False
            self._start_status_refresh()

        self.after(0, apply)


class ClosePositionWindow(tk.Toplevel):
    def __init__(self, master: TradePage, position: dict) -> None:
        super().__init__(master)
        parent = master.winfo_toplevel()
        self._trade_page = master
        self._position = position
        self._position_key = TradePage._position_key(position)
        self._symbol = str(position.get("symbol") or "")
        position_amt = TradePage._safe_float(position.get("positionAmt")) or 0.0
        self._position_size = abs(position_amt)
        self._side = "long" if position_amt > 0 else "short"
        self._asset = self._symbol[:-4] if self._symbol.endswith("USDT") else self._symbol
        self._pnl_value = TradePage._safe_float(position.get("unRealizedProfit")) or 0.0
        self._entry_price = TradePage._safe_float(position.get("entryPrice")) or 0.0
        mark_price = TradePage._safe_float(position.get("markPrice"))
        if mark_price is None:
            mark_price = self._entry_price
        self._mark_price = mark_price
        self._leverage = TradePage._safe_float(position.get("leverage")) or 1.0
        self._symbol_display = f"{self._symbol} X{TradePage._format_leverage(self._leverage)}"

        self._min_qty: Optional[float] = None
        self._step_size: Optional[float] = None
        self._close_pct = 100.0
        self._current_qty = self._position_size
        self._close_enabled = False
        self._close_hover = False
        self._close_lift = 0.0
        self._close_anim_job: Optional[str] = None
        self._dragging_slider = False
        self._entry_value_id: Optional[int] = None
        self._current_value_id: Optional[int] = None
        self._size_value_id: Optional[int] = None
        self._pct_btn_rects: Dict[int, int] = {}
        self._pct_btn_hover: Dict[int, bool] = {}

        self._resolve_layout()

        self.title("포지션 청산")
        self.configure(bg=self._panel_bg)
        self.resizable(False, False)
        self.transient(parent)
        self._center_over_parent(parent)

        self.canvas = tk.Canvas(
            self,
            width=self._window_width,
            height=self._window_height,
            bg=self._panel_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._fonts = {
            "symbol": tkfont.Font(self, family=FONT_FAMILY, size=16, weight="bold"),
            "label": tkfont.Font(self, family=FONT_FAMILY, size=12, weight="normal"),
            "close_label": tkfont.Font(self, family=FONT_FAMILY, size=12, weight="bold"),
            "expected": tkfont.Font(self, family=FONT_FAMILY, size=12, weight="bold"),
            "entry": tkfont.Font(self, family=FONT_FAMILY, size=12, weight="bold"),
            "tick": tkfont.Font(self, family=FONT_FAMILY, size=10, weight="normal"),
            "button": tkfont.Font(self, family=FONT_FAMILY, size=12, weight="bold"),
            "percent": tkfont.Font(self, family=FONT_FAMILY, size=11, weight="bold"),
        }

        self._compute_content_shift()
        self._apply_layout_offsets()

        self._draw_static()
        self._bind_events()

        self._apply_percent(self._close_pct)
        threading.Thread(target=self._load_symbol_filters, daemon=True).start()

    def destroy(self) -> None:
        try:
            if getattr(self._trade_page, "_close_window", None) is self:
                self._trade_page._close_window = None
        finally:
            super().destroy()

    def _center_over_parent(self, parent: tk.Tk) -> None:
        parent.update_idletasks()
        try:
            base_x = parent.winfo_x()
            base_y = parent.winfo_y()
            base_w = parent.winfo_width()
            base_h = parent.winfo_height()
            x = base_x + max(0, (base_w - self._window_width) // 2)
            y = base_y + max(0, (base_h - self._window_height) // 2)
        except tk.TclError:
            x = 0
            y = 0
        self.geometry(f"{self._window_width}x{self._window_height}+{x}+{y}")

    def _resolve_layout(self) -> None:
        self._window_width = CLOSE_WINDOW_WIDTH
        self._window_height = CLOSE_WINDOW_HEIGHT
        self._offset_x = 0
        self._offset_y = 0
        self._content_dx = 0.0
        self._content_dy = 0.0
        self._panel_bg = "#3f3f3f"

        base_dir = Path(__file__).resolve().parent
        bg_path = base_dir / "image" / "ex_image" / "close_position.png"
        try:
            img = Image.open(bg_path).convert("RGB")
        except Exception:
            self._apply_layout_offsets()
            return

        w, h = img.size
        px = img.load()
        cx, cy = w // 2, h // 2
        counts = Counter()
        for y in range(max(0, cy - 60), min(h, cy + 60), 2):
            for x in range(max(0, cx - 120), min(w, cx + 120), 2):
                r, g, b = px[x, y]
                if r + g + b > 650:
                    continue
                key = (r // 6, g // 6, b // 6)
                counts[key] += 1
        if counts:
            key = counts.most_common(1)[0][0]
            target = (key[0] * 6 + 3, key[1] * 6 + 3, key[2] * 6 + 3)
        else:
            target = px[cx, cy]

        tol = 18
        scan_w = int(w * 0.7)
        scan_h = int(h * 0.7)
        scan_left = max(0, cx - scan_w // 2)
        scan_right = min(w, cx + scan_w // 2)
        scan_top = max(0, cy - scan_h // 2)
        scan_bottom = min(h, cy + scan_h // 2)

        min_x = w
        min_y = h
        max_x = -1
        max_y = -1
        hits = 0
        for y in range(scan_top, scan_bottom):
            for x in range(scan_left, scan_right):
                r, g, b = px[x, y]
                if max(abs(r - target[0]), abs(g - target[1]), abs(b - target[2])) <= tol:
                    hits += 1
                    if x < min_x:
                        min_x = x
                    if x > max_x:
                        max_x = x
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y
        if hits > 1000 and min_x <= max_x and min_y <= max_y:
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            if 200 < width < w and 200 < height < h:
                self._window_width = width
                self._window_height = height
                self._offset_x = min_x
                self._offset_y = min_y
                self._panel_bg = _rgb_to_hex(target)

        # Layout offsets are applied after font metrics are available.

    def _base_offset_point(self, pos: Tuple[float, float]) -> Tuple[float, float]:
        return pos[0] - self._offset_x, pos[1] - self._offset_y

    def _base_offset_rect(self, rect: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        return (
            rect[0] - self._offset_x,
            rect[1] - self._offset_y,
            rect[2] - self._offset_x,
            rect[3] - self._offset_y,
        )

    def _offset_point(self, pos: Tuple[float, float]) -> Tuple[float, float]:
        x, y = self._base_offset_point(pos)
        return x + self._content_dx, y + self._content_dy

    def _offset_rect(self, rect: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = self._base_offset_rect(rect)
        return (
            x1 + self._content_dx,
            y1 + self._content_dy,
            x2 + self._content_dx,
            y2 + self._content_dy,
        )

    def _compute_content_shift(self) -> None:
        # Reset any previous shift before measuring.
        self._content_dx = 0.0
        self._content_dy = 0.0

        side_rect = self._base_offset_rect(CLOSE_SIDE_INDICATOR_RECT)
        symbol_pos = self._base_offset_point(CLOSE_SYMBOL_POS)
        close_label_pos = self._base_offset_point(CLOSE_LABEL_POS)
        info_label_x = self._base_offset_point(CLOSE_SIZE_POS)[0]
        info_start_y = self._base_offset_point(CLOSE_SIZE_POS)[1]
        info_value_x = self._base_offset_point(CLOSE_EXPECTED_POS)[0]
        slider_rect = self._base_offset_rect(CLOSE_SLIDER_RECT)
        expected_label_pos = self._base_offset_point((CLOSE_SLIDER_RECT[0], CLOSE_EXPECTED_POS[1]))
        expected_value_pos = self._base_offset_point(CLOSE_EXPECTED_POS)
        label_height = self._fonts["label"].metrics("linespace")
        expected_width = self._fonts["expected"].measure("+0.00 USDT")

        percent_btn_h = CLOSE_PERCENT_BUTTON_SIZE[1]
        percent_row_y = slider_rect[3] + 8
        expected_shift = max(0, (percent_row_y + percent_btn_h + 8) - expected_label_pos[1])
        expected_value_y = expected_value_pos[1] + expected_shift

        btn_w = CLOSE_BUTTON_RECT[2] - CLOSE_BUTTON_RECT[0]
        btn_h = CLOSE_BUTTON_RECT[3] - CLOSE_BUTTON_RECT[1]
        btn_center_x = (slider_rect[0] + slider_rect[2]) / 2
        btn_y1 = expected_value_y + self._fonts["expected"].metrics("linespace") + 16 + (btn_h * CLOSE_BUTTON_DOWN_SHIFT)
        close_button_rect = (
            btn_center_x - btn_w / 2,
            btn_y1,
            btn_center_x + btn_w / 2,
            btn_y1 + btn_h,
        )

        left = min(side_rect[0], symbol_pos[0], info_label_x, slider_rect[0], expected_label_pos[0], close_button_rect[0])
        right = max(info_value_x, slider_rect[2], expected_value_pos[0] + expected_width, close_button_rect[2])
        top = min(symbol_pos[1], close_label_pos[1], info_start_y)
        bottom = max(slider_rect[3], expected_label_pos[1] + expected_shift + label_height, close_button_rect[3])

        content_w = right - left
        content_h = bottom - top
        if content_w <= 0 or content_h <= 0:
            return

        self._content_dx = (self._window_width - content_w) / 2 - left
        self._content_dy = (self._window_height - content_h) / 2 - top

    def _apply_layout_offsets(self) -> None:
        self._side_indicator_rect = self._offset_rect(CLOSE_SIDE_INDICATOR_RECT)
        self._symbol_pos = self._offset_point(CLOSE_SYMBOL_POS)
        self._close_label_pos = self._offset_point(CLOSE_LABEL_POS)
        self._info_label_x = self._offset_point(CLOSE_SIZE_POS)[0]
        self._info_start_y = self._offset_point(CLOSE_SIZE_POS)[1]
        self._info_value_x = self._offset_point(CLOSE_EXPECTED_POS)[0]
        self._slider_rect = self._offset_rect(CLOSE_SLIDER_RECT)
        self._expected_label_pos = self._offset_point((CLOSE_SLIDER_RECT[0], CLOSE_EXPECTED_POS[1]))
        self._expected_value_pos = self._offset_point(CLOSE_EXPECTED_POS)
        self._close_button_rect = self._offset_rect(CLOSE_BUTTON_RECT)

    def _draw_static(self) -> None:
        self.canvas.create_rectangle(
            0,
            0,
            self._window_width,
            self._window_height,
            fill=self._panel_bg,
            outline="",
        )

        side_color = TABLE_POS_COLOR if self._side == "long" else TABLE_NEG_COLOR
        side_rect = self._side_indicator_rect
        rect_h = side_rect[3] - side_rect[1]
        symbol_h = self._fonts["symbol"].metrics("linespace")
        rect_center_y = self._symbol_pos[1] + symbol_h / 2
        side_rect = (
            side_rect[0],
            rect_center_y - rect_h / 2,
            side_rect[2],
            rect_center_y + rect_h / 2,
        )
        self._side_indicator_id = self.canvas.create_rectangle(
            *side_rect,
            fill=side_color,
            outline="",
        )

        self._symbol_text_id = self.canvas.create_text(
            self._symbol_pos[0],
            self._symbol_pos[1],
            text=self._symbol_display,
            font=self._fonts["symbol"],
            fill=CLOSE_TEXT_COLOR,
            anchor="nw",
        )

        close_label = "Close Long" if self._side == "long" else "Close Short"
        close_color = CLOSE_LONG_TEXT_COLOR if self._side == "long" else CLOSE_SHORT_TEXT_COLOR
        self._close_label_id = self.canvas.create_text(
            self._close_label_pos[0],
            self._close_label_pos[1],
            text=close_label,
            font=self._fonts["close_label"],
            fill=close_color,
            anchor="nw",
        )

        info_labels = [
            ("진입가격", TradePage._format_price(self._entry_price), "entry"),
            ("현재가격", TradePage._format_price(self._mark_price), "current"),
            ("사이즈", f"{self._format_qty(self._position_size)} {self._asset}".strip(), "size"),
        ]
        for idx, (label, value, key) in enumerate(info_labels):
            y = self._info_start_y + idx * CLOSE_INFO_LINE_GAP
            self.canvas.create_text(
                self._info_label_x,
                y,
                text=label,
                font=self._fonts["label"],
                fill=CLOSE_TEXT_COLOR,
                anchor="nw",
            )
            value_id = self.canvas.create_text(
                self._info_value_x,
                y,
                text=value,
                font=self._fonts["label"],
                fill=CLOSE_TEXT_COLOR,
                anchor="ne",
            )
            if key == "entry":
                self._entry_value_id = value_id
            elif key == "current":
                self._current_value_id = value_id
            elif key == "size":
                self._size_value_id = value_id

        self._track_x1, self._track_y1, self._track_x2, self._track_y2 = self._slider_rect
        if 0.0 < CLOSE_SLIDER_WIDTH_FACTOR < 1.0:
            mid_x = (self._track_x1 + self._track_x2) / 2
            new_w = (self._track_x2 - self._track_x1) * CLOSE_SLIDER_WIDTH_FACTOR
            self._track_x1 = mid_x - new_w / 2
            self._track_x2 = mid_x + new_w / 2
        self._track_y = (self._track_y1 + self._track_y2) / 2
        base_width = max(4, int((self._track_y2 - self._track_y1) / 2))
        self._track_width = max(2, int(base_width * CLOSE_SLIDER_THICKNESS_SCALE))

        # Percent box between size and slider.
        label_height = self._fonts["label"].metrics("linespace")
        info_bottom = self._info_start_y + (len(info_labels) - 1) * CLOSE_INFO_LINE_GAP + label_height
        box_w, box_h = CLOSE_PERCENT_BOX_SIZE
        box_x = (self._track_x1 + self._track_x2) / 2 - box_w / 2
        box_y = info_bottom + 20
        max_box_y = self._track_y1 - box_h - 8
        if box_y > max_box_y:
            box_y = max_box_y
        self._percent_box_rect = (box_x, box_y, box_x + box_w, box_y + box_h)
        self._percent_box_id = self.canvas.create_rectangle(
            *self._percent_box_rect,
            fill=CLOSE_INPUT_BG,
            outline="#2b2b2b",
            width=1,
        )
        self._percent_value_id = self.canvas.create_text(
            (self._percent_box_rect[0] + self._percent_box_rect[2]) / 2,
            (self._percent_box_rect[1] + self._percent_box_rect[3]) / 2,
            text="0%",
            font=self._fonts["entry"],
            fill=CLOSE_TEXT_COLOR,
            anchor="center",
        )

        btn_w, btn_h = CLOSE_PERCENT_BUTTON_SIZE
        percent_row_y = self._track_y2 + 8
        needed = percent_row_y + btn_h + 8
        expected_shift = max(0, needed - self._expected_label_pos[1])
        expected_label_y = self._expected_label_pos[1] + expected_shift
        expected_value_y = self._expected_value_pos[1] + expected_shift

        self.canvas.create_text(
            self._expected_label_pos[0],
            expected_label_y,
            text="예상 수익 :",
            font=self._fonts["label"],
            fill=CLOSE_TEXT_COLOR,
            anchor="nw",
        )

        self._expected_profit_id = self.canvas.create_text(
            self._expected_value_pos[0],
            expected_value_y,
            text="--",
            font=self._fonts["expected"],
            fill=CLOSE_TEXT_COLOR,
            anchor="nw",
        )

        slider_color = CLOSE_TEXT_COLOR
        self._slider_base_id = self.canvas.create_line(
            self._track_x1,
            self._track_y,
            self._track_x2,
            self._track_y,
            fill=slider_color,
            width=self._track_width,
            capstyle="round",
        )
        self._slider_fill_id = self.canvas.create_line(
            self._track_x1,
            self._track_y,
            self._track_x1,
            self._track_y,
            fill=slider_color,
            width=self._track_width,
            capstyle="round",
        )
        handle_r = max(5, int(self._track_width * 1.2 * CLOSE_SLIDER_HANDLE_SCALE))
        self._slider_handle_id = self.canvas.create_oval(
            self._track_x1 - handle_r,
            self._track_y - handle_r,
            self._track_x1 + handle_r,
            self._track_y + handle_r,
            fill=CLOSE_TEXT_COLOR,
            outline="",
        )

        percent_values = (0, 25, 50, 75, 100)
        total_w = btn_w * len(percent_values) + CLOSE_PERCENT_BUTTON_GAP * (len(percent_values) - 1)
        start_x = (self._track_x1 + self._track_x2) / 2 - total_w / 2
        for idx, pct in enumerate(percent_values):
            x1 = start_x + idx * (btn_w + CLOSE_PERCENT_BUTTON_GAP)
            y1 = percent_row_y
            x2 = x1 + btn_w
            y2 = y1 + btn_h
            tag = f"pct_btn_{pct}"
            rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=self._panel_bg,
                outline=CLOSE_PERCENT_BUTTON_OUTLINE,
                width=1,
                tags=("pct_btn", tag, "pct_btn_rect"),
            )
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=f"{pct}%",
                font=self._fonts["tick"],
                fill=CLOSE_TEXT_COLOR,
                anchor="center",
                tags=("pct_btn", tag, "pct_btn_text"),
            )
            self._pct_btn_rects[pct] = rect_id
            self._pct_btn_hover[pct] = False

        btn_base_w = self._close_button_rect[2] - self._close_button_rect[0]
        btn_base_h = self._close_button_rect[3] - self._close_button_rect[1]
        btn_center_x = (self._track_x1 + self._track_x2) / 2
        btn_y1 = expected_value_y + self._fonts["expected"].metrics("linespace") + 16 + (btn_base_h * CLOSE_BUTTON_DOWN_SHIFT)
        btn_y2 = btn_y1 + btn_base_h
        self._close_button_rect = (
            btn_center_x - btn_base_w / 2,
            btn_y1,
            btn_center_x + btn_base_w / 2,
            btn_y2,
        )

        self._draw_close_button()

    def _bind_events(self) -> None:
        self.canvas.tag_bind("close_btn", "<Button-1>", self._on_close_click)
        self.canvas.tag_bind("close_btn", "<Enter>", lambda _e: self._set_close_hover(True))
        self.canvas.tag_bind("close_btn", "<Leave>", lambda _e: self._set_close_hover(False))
        for pct in (0, 25, 50, 75, 100):
            tag = f"pct_btn_{pct}"
            self.canvas.tag_bind(tag, "<Button-1>", lambda _e, value=pct: self._apply_percent(value))
            self.canvas.tag_bind(tag, "<Enter>", lambda _e, value=pct: self._set_percent_hover(value, True))
            self.canvas.tag_bind(tag, "<Leave>", lambda _e, value=pct: self._set_percent_hover(value, False))
        self.canvas.bind("<Button-1>", self._on_canvas_click, add="+")
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag, add="+")
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release, add="+")

    def _load_symbol_filters(self) -> None:
        min_qty, step_size = self._trade_page._get_symbol_filters(self._symbol)
        self.after(0, lambda: self._apply_filters(min_qty, step_size))

    def _apply_filters(self, min_qty: Optional[float], step_size: Optional[float]) -> None:
        self._min_qty = min_qty
        self._step_size = step_size
        self._apply_percent(self._close_pct)

    def sync_position(self, position_map: Dict[str, dict]) -> None:
        if not self._position_key:
            return
        position = position_map.get(self._position_key)
        if not position:
            self._set_position_unavailable()
            return
        self._apply_position_update(position)

    def _apply_position_update(self, position: dict) -> None:
        position_amt = TradePage._safe_float(position.get("positionAmt")) or 0.0
        if abs(position_amt) <= 1e-9:
            self._set_position_unavailable()
            return
        self._position = position
        self._position_size = abs(position_amt)
        self._pnl_value = TradePage._safe_float(position.get("unRealizedProfit")) or 0.0
        self._entry_price = TradePage._safe_float(position.get("entryPrice")) or 0.0
        mark_price = TradePage._safe_float(position.get("markPrice"))
        if mark_price is None:
            mark_price = self._entry_price
        self._mark_price = mark_price
        self._leverage = TradePage._safe_float(position.get("leverage")) or 1.0

        symbol_display = f"{self._symbol} X{TradePage._format_leverage(self._leverage)}"
        if symbol_display != self._symbol_display:
            self._symbol_display = symbol_display
            if getattr(self, "_symbol_text_id", None) is not None:
                self.canvas.itemconfigure(self._symbol_text_id, text=self._symbol_display)

        if self._entry_value_id is not None:
            self.canvas.itemconfigure(self._entry_value_id, text=TradePage._format_price(self._entry_price))
        if self._current_value_id is not None:
            self.canvas.itemconfigure(self._current_value_id, text=TradePage._format_price(self._mark_price))
        if self._size_value_id is not None:
            size_text = f"{self._format_qty(self._position_size)} {self._asset}".strip()
            self.canvas.itemconfigure(self._size_value_id, text=size_text)

        self._apply_percent(self._close_pct)

    def _set_position_unavailable(self) -> None:
        self._position = {}
        self._position_size = 0.0
        self._current_qty = 0.0
        self._pnl_value = 0.0
        if self._entry_value_id is not None:
            self.canvas.itemconfigure(self._entry_value_id, text="--")
        if self._current_value_id is not None:
            self.canvas.itemconfigure(self._current_value_id, text="--")
        if self._size_value_id is not None:
            self.canvas.itemconfigure(self._size_value_id, text="--")
        if self._expected_profit_id is not None:
            self.canvas.itemconfigure(self._expected_profit_id, text="--", fill=CLOSE_TEXT_COLOR)
        self._close_enabled = False
        self._close_hover = False
        self._draw_close_button()

    def _decimal_places(self) -> int:
        if not self._step_size or self._step_size <= 0:
            return 3
        text = f"{self._step_size:.10f}".rstrip("0").rstrip(".")
        if "." in text:
            return len(text.split(".")[1])
        return 0

    def _format_qty(self, qty: float) -> str:
        decimals = self._decimal_places()
        text = f"{qty:.{decimals}f}"
        return text.rstrip("0").rstrip(".") if "." in text else text

    def _quantize_qty(self, qty: float) -> float:
        if not self._step_size or self._step_size <= 0:
            return qty
        return math.floor(qty / self._step_size) * self._step_size

    def _apply_percent(self, pct: float) -> None:
        pct = max(0.0, min(100.0, pct))
        qty = self._position_size * pct / 100 if self._position_size > 0 else 0.0
        qty = min(qty, self._position_size)
        self._current_qty = self._quantize_qty(qty)
        self._close_pct = pct
        self._refresh_dynamic()

    def _refresh_dynamic(self) -> None:
        self._update_slider_visual()
        self._update_expected_profit()
        self._draw_close_button()

    def _update_slider_visual(self) -> None:
        handle_x = self._track_x1 + (self._track_x2 - self._track_x1) * (self._close_pct / 100 if self._close_pct else 0)
        self.canvas.coords(self._slider_fill_id, self._track_x1, self._track_y, handle_x, self._track_y)
        handle_r = max(5, int(self._track_width * 1.2 * CLOSE_SLIDER_HANDLE_SCALE))
        self.canvas.coords(
            self._slider_handle_id,
            handle_x - handle_r,
            self._track_y - handle_r,
            handle_x + handle_r,
            self._track_y + handle_r,
        )
        if getattr(self, "_percent_value_id", None) is not None:
            self.canvas.itemconfigure(self._percent_value_id, text=f"{self._close_pct:.0f}%")

    def _update_expected_profit(self) -> None:
        min_ok = self._min_qty is None or self._current_qty >= (self._min_qty - 1e-12)
        if self._current_qty <= 0 or not min_ok:
            self._close_enabled = False
            self._close_hover = False
            self.canvas.itemconfigure(self._expected_profit_id, text="--", fill=CLOSE_TEXT_COLOR)
            return
        portion = self._current_qty / self._position_size if self._position_size > 0 else 0.0
        expected = self._pnl_value * portion
        expected_text = f"{expected:+,.2f} USDT"
        self._close_enabled = True
        expected_color = TABLE_POS_COLOR if expected >= 0 else TABLE_NEG_COLOR
        self.canvas.itemconfigure(self._expected_profit_id, text=expected_text, fill=expected_color)

    def _draw_close_button(self) -> None:
        self.canvas.delete("close_btn")
        x1, y1, x2, y2 = self._close_button_rect
        if self._close_lift:
            y1 += self._close_lift
            y2 += self._close_lift
        fill = CLOSE_BUTTON_FILL if self._close_enabled else CLOSE_BUTTON_DISABLED
        if self._close_enabled and self._close_hover:
            fill = _lighten_hex(fill, BUTTON_HOVER_LIGHTEN)
        outline = "#ffffff"
        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=fill,
            outline=outline,
            width=1,
            tags=("close_btn",),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=CLOSE_BUTTON_TEXT,
            font=self._fonts["button"],
            fill=CLOSE_TEXT_COLOR,
            anchor="center",
            tags=("close_btn",),
        )

    def _set_close_hover(self, hovering: bool) -> None:
        if not self._close_enabled:
            return
        if self._close_hover == hovering:
            return
        self._close_hover = hovering
        target = -BUTTON_HOVER_LIFT if hovering else 0.0
        self._animate_close_lift(target)

    def _set_percent_hover(self, pct: int, hovering: bool) -> None:
        if self._pct_btn_hover.get(pct) == hovering:
            return
        rect_id = self._pct_btn_rects.get(pct)
        if rect_id is None:
            return
        self._pct_btn_hover[pct] = hovering
        fill = self._panel_bg
        if hovering:
            fill = _lighten_hex(fill, CLOSE_PERCENT_HOVER_LIGHTEN)
        try:
            self.canvas.itemconfigure(rect_id, fill=fill)
        except tk.TclError:
            pass

    def _animate_close_lift(self, target: float) -> None:
        if self._close_anim_job is not None:
            try:
                self.after_cancel(self._close_anim_job)
            except tk.TclError:
                pass
        start = self._close_lift
        if abs(start - target) < 0.1:
            self._close_lift = target
            self._refresh_dynamic()
            self._close_anim_job = None
            return
        steps = BUTTON_HOVER_ANIM_STEPS
        step_ms = max(1, BUTTON_HOVER_ANIM_MS // steps)

        def step(i: int) -> None:
            t = i / steps
            self._close_lift = start + (target - start) * t
            self._refresh_dynamic()
            if i < steps:
                self._close_anim_job = self.after(step_ms, lambda: step(i + 1))
            else:
                self._close_anim_job = None

        step(1)

    def _point_in_slider(self, x: float, y: float) -> bool:
        return self._track_x1 - 8 <= x <= self._track_x2 + 8 and self._track_y1 - 10 <= y <= self._track_y2 + 10

    def _on_canvas_click(self, event: tk.Event) -> None:
        current_tags = self.canvas.gettags("current")
        if "close_btn" in current_tags:
            return
        if "pct_btn" in current_tags:
            return
        if self._point_in_slider(event.x, event.y):
            self._dragging_slider = True
            self._apply_percent(self._percent_from_x(event.x))

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if not self._dragging_slider:
            return
        self._apply_percent(self._percent_from_x(event.x))

    def _on_canvas_release(self, _event: tk.Event) -> None:
        self._dragging_slider = False

    def _percent_from_x(self, x: float) -> float:
        ratio = (x - self._track_x1) / (self._track_x2 - self._track_x1)
        return max(0.0, min(100.0, ratio * 100))

    def _on_close_click(self, _event: Optional[tk.Event] = None) -> None:
        if not self._close_enabled:
            return
        qty = self._quantize_qty(self._current_qty)
        qty_text = self._format_qty(qty)
        ok, msg = self._trade_page._submit_close_order(self._position, qty_text)
        if not ok:
            messagebox.showerror("청산 실패", f"{msg}\n로그: {TRADE_LOG_PATH}", parent=self)
            return
        threading.Thread(target=self._trade_page._refresh_status, daemon=True).start()
        self.destroy()
