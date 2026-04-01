from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk
from typing import Dict, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageTk

from entry_bot import AccountSnapshot, EntryRelayBot
from log_rotation import append_rotating_log_line
from runtime_paths import get_log_path

BASE_WIDTH = 1328
BASE_HEIGHT = 800

FONT_FAMILY = "Malgun Gothic"
CANVAS_BG = "#0b1020"
BACKGROUND_OFF_COLOR = "#222226"
PANEL_FILL = "#0b1220"
PANEL_BORDER = "#c4cedf"
PANEL_ALPHA = 165
PANEL_BORDER_ALPHA = 210
PANEL_RADIUS = 18
PANEL_BORDER_WIDTH = 2
BALANCE_SYNC_INTERVAL_SEC = 10 * 60
SUBSCRIBER_WEBHOOK_URL = (
    "https://script.google.com/macros/s/AKfycbyKBEsD_GQ125wrjPm8kUrcRvnZSuZ4DlHZTg-lEr1X_UX-CiY2U9W9g3Pd6JBc6xIS/exec"
)
SUBSCRIBER_REQUEST_TIMEOUT_SEC = 8

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

SAVE_SETTINGS_FILL = "#00b050"
SAVE_SETTINGS_DISABLED_FILL = "#5f5f5f"
START_FILL = "#00b050"
STOP_FILL = "#ff0000"
BUTTON_TEXT_COLOR = "#ffffff"
BUTTON_ACTIVE_BORDER = "#1f5eff"
BUTTON_HOVER_LIFT = 6
BUTTON_HOVER_LIGHTEN = 26
BUTTON_HOVER_ANIM_MS = 120
BUTTON_HOVER_ANIM_STEPS = 6

UI_TEXT_COLOR = "#f6f8fc"
WALLET_VALUE_COLOR = "#00ff7f"
WALLET_WARNING_COLOR = "#ff4d4f"
WALLET_WARNING_TEXT = "API를 재확인하십시오"

CHART_BASE_RECT = (49, 112, 770, 446)
TABLE_RECT = (47, 466, 765, 753)
SECTION_STACK_VERTICAL_SHIFT = 32
CHART_RECT = (
    CHART_BASE_RECT[0],
    CHART_BASE_RECT[1] - SECTION_STACK_VERTICAL_SHIFT,
    CHART_BASE_RECT[2],
    CHART_BASE_RECT[3] - SECTION_STACK_VERTICAL_SHIFT,
)
STRATEGY_GUIDE_BOTTOM_GAP = 54
STRATEGY_GUIDE_PANEL_RECT = (
    TABLE_RECT[0],
    TABLE_RECT[1] - SECTION_STACK_VERTICAL_SHIFT,
    TABLE_RECT[2],
    TABLE_RECT[3] - STRATEGY_GUIDE_BOTTOM_GAP,
)
WALLET_BASE_RECT = (819, 263, 1292, 590)
START_BUTTON_BASE_RECT = (872, 503, 1042, 555)
STOP_BUTTON_BASE_RECT = (1090, 503, 1260, 555)
WALLET_VERTICAL_SHIFT_RATIO = 0.52
WALLET_VERTICAL_SHIFT = int(WALLET_BASE_RECT[1] * WALLET_VERTICAL_SHIFT_RATIO)
WALLET_RECT = (
    WALLET_BASE_RECT[0],
    WALLET_BASE_RECT[1] - WALLET_VERTICAL_SHIFT,
    WALLET_BASE_RECT[2],
    WALLET_BASE_RECT[3] - WALLET_VERTICAL_SHIFT,
)
MANAGER_CONNECTION_TOP_GAP = 8
MANAGER_CONNECTION_HEIGHT = 110
MANAGER_CONNECTION_RECT = (
    WALLET_RECT[0],
    WALLET_RECT[3] + MANAGER_CONNECTION_TOP_GAP,
    WALLET_RECT[2],
    WALLET_RECT[3] + MANAGER_CONNECTION_TOP_GAP + MANAGER_CONNECTION_HEIGHT,
)
MANAGER_CONNECTION_TITLE = "관리자 연결"
MANAGER_CONNECTION_BUTTON_RECTS = {
    "manager_contact_a": (848, 526, 1052, 558),
    "manager_contact_b": (1060, 526, 1264, 558),
}
MANAGER_CONNECTION_ITEMS = (
    (
        "manager_contact_a",
        "관리자 연락처 A",
        "manager_contact_a",
        "https://t.me/crypto_LEVI9",
    ),
    (
        "manager_contact_b",
        "관리자 연락처 B",
        "manager_contact_b",
        "https://t.me/LEVI_kimbob",
    ),
)
CHANNEL_INFO_TOP_GAP = 16
CHANNEL_INFO_RECT = (
    WALLET_RECT[0],
    MANAGER_CONNECTION_RECT[3] + CHANNEL_INFO_TOP_GAP,
    WALLET_RECT[2],
    TABLE_RECT[3],
)
CHANNEL_INFO_TITLE = "채널정보"
CHANNEL_INFO_TITLE_HEIGHT = 28
CHANNEL_INFO_BUTTON_RECTS = {
    "channel_long_alert": (848, 644, 1052, 676),
    "channel_short_alert": (1060, 644, 1264, 676),
    "channel_short_risk": (848, 707, 1052, 739),
    "channel_official_notice": (1060, 707, 1264, 739),
}
CHANNEL_INFO_ITEMS = (
    (
        "channel_long_alert",
        "📈롱포지션 알림채널",
        "long_position_alert_channel",
        "https://t.me/+G7Y1QvJ6zHBiMWVl",
    ),
    (
        "channel_short_alert",
        "📉숏포지션 알림채널",
        "short_position_alert_channel",
        "https://t.me/+ZNJ1Mf5AgwxjZmI9",
    ),
    (
        "channel_short_risk",
        "💥숏포지션 리스크관리 채널",
        "short_position_risk_management_channel",
        "https://t.me/+GZhGHaQBVmhkMmRl",
    ),
    (
        "channel_official_notice",
        "🔈LEVIA 공식 공지채널",
        "levia_official_notice_channel",
        "https://t.me/+7q67SFWYCTU1MzJl",
    ),
)
SECTION_TITLE_HEIGHT = 34

WALLET_SETTINGS_LINE_GAP = 12
WALLET_TEXT_CENTER_OFFSET_Y = 10
START_BUTTON_RECT = (
    START_BUTTON_BASE_RECT[0],
    START_BUTTON_BASE_RECT[1] - WALLET_VERTICAL_SHIFT,
    START_BUTTON_BASE_RECT[2],
    START_BUTTON_BASE_RECT[3] - WALLET_VERTICAL_SHIFT,
)
STOP_BUTTON_RECT = (
    STOP_BUTTON_BASE_RECT[0],
    STOP_BUTTON_BASE_RECT[1] - WALLET_VERTICAL_SHIFT,
    STOP_BUTTON_BASE_RECT[2],
    STOP_BUTTON_BASE_RECT[3] - WALLET_VERTICAL_SHIFT,
)

FILTER_LABEL_FILL = "#ffffff"
FILTER_LABEL_OUTLINE = "#000000"
FILTER_LABEL_TEXT = "#000000"
FILTER_TEXT_OFFSET = 0
COMBOBOX_PADDING_Y = 2

TABLE_REF_WIDTH = 849
TABLE_REF_HEIGHT = 348
TABLE_HEADER_TOP = 60 / TABLE_REF_HEIGHT
TABLE_HEADER_TEXT_Y = 76 / TABLE_REF_HEIGHT
TABLE_HEADER_LINE_Y = 88 / TABLE_REF_HEIGHT

TABLE_COL_SYMBOL_X = 59 / TABLE_REF_WIDTH
TABLE_COL_SIZE_X = 179 / TABLE_REF_WIDTH
TABLE_COL_ENTRY_X = 301 / TABLE_REF_WIDTH
TABLE_COL_CURRENT_X = 440 / TABLE_REF_WIDTH
TABLE_COL_PNL_X = 588 / TABLE_REF_WIDTH

TABLE_TITLE_FILL = "#e6f0ff"
TABLE_TITLE_BORDER = "#1f5eff"
TABLE_HEADER_FILL = "#17152f"
TABLE_HEADER_TEXT = "#ffffff"
TABLE_ROW_TEXT = "#ffffff"
TABLE_LINE_COLOR = "#ffffff"

STRATEGY_GUIDE_BUTTON_RECTS = {
    "guide_long": (82, 616, 258, 670),
    "guide_short": (319, 616, 495, 670),
    "guide_dca": (556, 616, 732, 670),
}
STRATEGY_GUIDE_TITLE = "전략 가이드북"
STRATEGY_GUIDE_ITEMS = (
    ("guide_long", "📈롱포지션 전략 가이드북"),
    ("guide_short", "📉숏포지션 전략 가이드북"),
    ("guide_dca", "🔄DCA 전략지표 가이드문서"),
)
STRATEGY_GUIDE_BUTTON_HEIGHT = 54
STRATEGY_GUIDE_LABEL_OFFSET = 22
STRATEGY_GUIDE_CONTENT_TOP_PADDING = 22
STRATEGY_GUIDE_CONTENT_BOTTOM_PADDING = 22

LEVERAGE_LABEL_RECT = (260, 262, 560, 294)
LEVERAGE_DROPDOWN_RECT = (260, 302, 560, 334)
SAVE_SETTINGS_BUTTON_RECT = (305, 368, 515, 404)

DEFAULT_LEVERAGE = "1배"
LEVERAGE_OPTIONS = ["2배", "1배"]
TRADE_STATE_LABELS = {
    "start": "실행중",
    "stop": "중단됨",
}

TRADE_LOG_PATH = get_log_path("LTS-Trade.log")


def _log_trade(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        append_rotating_log_line(TRADE_LOG_PATH, f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _hex_to_rgba(value: str, alpha: int) -> Tuple[int, int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(color: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _lighten_hex(value: str, amount: int) -> str:
    if not value.startswith("#") or len(value) != 7:
        return value
    r, g, b = _hex_to_rgb(value)
    return _rgb_to_hex((min(255, r + amount), min(255, g + amount), min(255, b + amount)))


def _round_rect_points(x1: float, y1: float, x2: float, y2: float, radius: float) -> list[float]:
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
        self._api_key = str(api_key or "").strip()
        self._secret_key = str(secret_key or "").strip()
        self._api_key_present = bool(str(api_key or "").strip())
        self._secret_key_present = bool(str(secret_key or "").strip())
        self._background_enabled = background_enabled
        self._supports_alpha = self._init_alpha_support()
        self._anim_offset = 0.0

        self._bg_toggle_original = self._load_background_toggle_icon()
        self._exit_icon_original = self._load_exit_icon()
        self.bg_original = self._load_background()
        self.bg_photo: Optional[ImageTk.PhotoImage] = None
        self._bg_toggle_photo: Optional[ImageTk.PhotoImage] = None
        self._exit_icon_photo: Optional[ImageTk.PhotoImage] = None
        self._last_bg_size: Optional[Tuple[int, int]] = None
        self._last_bg_toggle_size: Optional[int] = None
        self._last_bg_toggle_enabled: Optional[bool] = None
        self._last_exit_icon_size: Optional[int] = None

        self._panel_photos: Dict[str, ImageTk.PhotoImage] = {}
        self._panel_sizes: Dict[str, Tuple[int, int]] = {}

        self._button_hover: Dict[str, bool] = {
            "start": False,
            "stop": False,
            "filter_save": False,
            "guide_long": False,
            "guide_short": False,
            "guide_dca": False,
            "manager_contact_a": False,
            "manager_contact_b": False,
            "channel_long_alert": False,
            "channel_short_alert": False,
            "channel_short_risk": False,
            "channel_official_notice": False,
        }
        self._button_lift: Dict[str, float] = {
            "start": 0.0,
            "stop": 0.0,
            "filter_save": 0.0,
            "guide_long": 0.0,
            "guide_short": 0.0,
            "guide_dca": 0.0,
            "manager_contact_a": 0.0,
            "manager_contact_b": 0.0,
            "channel_long_alert": 0.0,
            "channel_short_alert": 0.0,
            "channel_short_risk": 0.0,
            "channel_official_notice": 0.0,
        }
        self._button_anim_jobs: Dict[str, Optional[str]] = {
            "start": None,
            "stop": None,
            "filter_save": None,
            "guide_long": None,
            "guide_short": None,
            "guide_dca": None,
            "manager_contact_a": None,
            "manager_contact_b": None,
            "channel_long_alert": None,
            "channel_short_alert": None,
            "channel_short_risk": None,
            "channel_official_notice": None,
        }

        self._trade_state = "stop"
        self._wallet_value = "--"
        self._wallet_unit = ""
        self._wallet_value_color = WALLET_VALUE_COLOR
        self._wallet_warning_visible = False
        self._sheet_balance_sync_next_at = 0.0
        self._sheet_balance_sync_pending = True
        self._sheet_balance_sync_in_progress = False
        self._sheet_balance_sync_lock = threading.Lock()
        self._save_enabled = False
        self._saved_filter_settings: Optional[dict] = None
        self._entry_bot = EntryRelayBot(
            api_key=self._api_key,
            secret_key=self._secret_key,
            leverage_getter=self._selected_leverage_label,
            snapshot_callback=self._schedule_entry_snapshot_update,
        )

        self._base_fonts = {
            "wallet": (12, "normal"),
            "wallet_value": (12, "bold"),
            "button": (14, "bold"),
            "dropdown": (10, "normal"),
            "filter_label": (11, "normal"),
            "table_title": (12, "bold"),
            "table_header": (10, "bold"),
            "table_row": (11, "normal"),
        }
        self.fonts: Dict[str, tkfont.Font] = {
            name: tkfont.Font(self, family=FONT_FAMILY, size=size, weight=weight)
            for name, (size, weight) in self._base_fonts.items()
        }

        self.canvas = tk.Canvas(self, bg=CANVAS_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw")
        self.bg_toggle_item = self.canvas.create_image(0, 0, anchor="ne", tags=("bg_toggle",))
        self.exit_item = self.canvas.create_image(0, 0, anchor="ne", tags=("exit_app",))

        self._style = ttk.Style(self)
        self.leverage_dropdown = ttk.Combobox(
            self.canvas,
            values=LEVERAGE_OPTIONS,
            state="readonly",
            justify="center",
        )
        self.leverage_dropdown_window = self.canvas.create_window(0, 0, window=self.leverage_dropdown, anchor="nw")

        self.leverage_dropdown.set(DEFAULT_LEVERAGE)
        self._saved_filter_settings = self._default_filter_settings()

        self._configure_combobox_style("TradeFilter.TCombobox", COMBOBOX_PADDING_Y)
        self.leverage_dropdown.configure(style="TradeFilter.TCombobox")
        self._bind_combobox_focus(self.leverage_dropdown)
        self.leverage_dropdown.bind("<<ComboboxSelected>>", self._on_filter_change, add="+")

        self.canvas.tag_bind("bg_toggle", "<Button-1>", self._toggle_background)
        self.canvas.tag_bind("bg_toggle", "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("bg_toggle", "<Leave>", lambda _event: self.canvas.configure(cursor=""))
        self.canvas.tag_bind("exit_app", "<Button-1>", self._request_exit)
        self.canvas.tag_bind("exit_app", "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("exit_app", "<Leave>", lambda _event: self.canvas.configure(cursor=""))

        self._bind_clickables()

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._clear_combo_focus, add="+")
        self._apply_background_mode()
        self._refresh_filter_controls_lock()
        self._update_filter_save_state()
        self._layout()
        _log_trade(
            "Trade page initialized: "
            f"entry_backend=single_symbol_first_entry api_key_present={self._api_key_present} "
            f"secret_key_present={self._secret_key_present} "
            f"trade_state={self._trade_state} trade_state_label={self._trade_state_display_text()} "
            "strategy_panel=strategy_guides "
            f"section_stack_vertical_shift={SECTION_STACK_VERTICAL_SHIFT} "
            f"chart_panel_top={CHART_RECT[1]} "
            f"strategy_guide_panel_bottom={STRATEGY_GUIDE_PANEL_RECT[3]} "
            f"strategy_guide_bottom_gap={STRATEGY_GUIDE_BOTTOM_GAP} "
            f"strategy_guide_panel_height={STRATEGY_GUIDE_PANEL_RECT[3] - STRATEGY_GUIDE_PANEL_RECT[1]} "
            "strategy_guide_layout=centered_in_panel "
            f"manager_connection_panel=contacts manager_connection_item_count={len(MANAGER_CONNECTION_ITEMS)} "
            f"channel_info_panel=telegram_channels channel_info_item_count={len(CHANNEL_INFO_ITEMS)} "
            "channel_info_layout=2x2 "
            "wallet_text_layout=centered_above_buttons "
            f"wallet_text_center_offset_y={WALLET_TEXT_CENTER_OFFSET_Y} "
            f"manager_connection_top_gap={MANAGER_CONNECTION_TOP_GAP} "
            f"manager_connection_height={MANAGER_CONNECTION_HEIGHT} "
            f"channel_info_top_gap={CHANNEL_INFO_TOP_GAP} "
            f"channel_info_title_height={CHANNEL_INFO_TITLE_HEIGHT} "
            f"wallet_vertical_shift={WALLET_VERTICAL_SHIFT} "
            f"wallet_vertical_shift_ratio={WALLET_VERTICAL_SHIFT_RATIO:.2f}"
        )
        if self._api_key and self._secret_key:
            self._start_initial_snapshot_fetch()

    def _load_background(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        return Image.open(base_dir / "image" / "trade_page" / "trade_page_bg.png").convert("RGBA")

    def _load_background_toggle_icon(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        return Image.open(base_dir / "image" / "login_page" / "background_on_off.png").convert("RGBA")

    def _load_exit_icon(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        return Image.open(base_dir / "image" / "trade_page" / "exit.png").convert("RGBA")

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
            on_enter=lambda _event: self._set_button_hover("start", True),
            on_leave=lambda _event: self._set_button_hover("start", False),
        )
        self._bind_tag(
            "trade_stop",
            self._handle_stop_click,
            on_enter=lambda _event: self._set_button_hover("stop", True),
            on_leave=lambda _event: self._set_button_hover("stop", False),
        )
        self._bind_tag(
            "filter_save",
            self._handle_filter_save,
            on_enter=lambda _event: self._set_button_hover("filter_save", True),
            on_leave=lambda _event: self._set_button_hover("filter_save", False),
            enabled=lambda: self._save_enabled,
        )
        self._bind_tag(
            "guide_long",
            self._handle_long_strategy_guide,
            on_enter=lambda _event: self._set_button_hover("guide_long", True),
            on_leave=lambda _event: self._set_button_hover("guide_long", False),
        )
        self._bind_tag(
            "guide_short",
            self._handle_short_strategy_guide,
            on_enter=lambda _event: self._set_button_hover("guide_short", True),
            on_leave=lambda _event: self._set_button_hover("guide_short", False),
        )
        self._bind_tag(
            "guide_dca",
            self._handle_dca_strategy_guide,
            on_enter=lambda _event: self._set_button_hover("guide_dca", True),
            on_leave=lambda _event: self._set_button_hover("guide_dca", False),
        )
        self._bind_external_link_items(MANAGER_CONNECTION_ITEMS, self._handle_manager_connection_link)
        self._bind_external_link_items(CHANNEL_INFO_ITEMS, self._handle_channel_info_link)

    def _bind_external_link_items(self, items, handler) -> None:
        for tag, _label, option, url in items:
            self._bind_tag(
                tag,
                lambda _event, option=option, url=url, click_handler=handler: click_handler(option=option, url=url),
                on_enter=lambda _event, button_tag=tag: self._set_button_hover(button_tag, True),
                on_leave=lambda _event, button_tag=tag: self._set_button_hover(button_tag, False),
            )

    def _bind_tag(self, tag: str, handler, on_enter=None, on_leave=None, enabled=None) -> None:
        def is_enabled() -> bool:
            return enabled() if callable(enabled) else True

        def handle_click(event: tk.Event) -> None:
            if is_enabled():
                handler(event)

        def handle_enter(event: tk.Event) -> None:
            if not is_enabled():
                self.canvas.configure(cursor="")
                return
            self.canvas.configure(cursor="hand2")
            if on_enter is not None:
                on_enter(event)

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
        self._animate_button_lift(key, -BUTTON_HOVER_LIFT if hovering else 0.0)

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

        step_ms = max(1, BUTTON_HOVER_ANIM_MS // BUTTON_HOVER_ANIM_STEPS)

        def step(idx: int) -> None:
            t = idx / BUTTON_HOVER_ANIM_STEPS
            self._button_lift[key] = start + (target - start) * t
            self._layout()
            if idx < BUTTON_HOVER_ANIM_STEPS:
                self._button_anim_jobs[key] = self.after(step_ms, lambda: step(idx + 1))
            else:
                self._button_anim_jobs[key] = None

        step(1)

    def _toggle_background(self, _event: Optional[tk.Event] = None) -> None:
        self._background_enabled = not self._background_enabled
        _log_trade(f"Background mode toggled: enabled={self._background_enabled}")
        self._apply_background_mode()
        self._layout()

    def _request_exit(self, _event: Optional[tk.Event] = None) -> None:
        _log_trade("Exit requested from trade page.")
        exit_manager = getattr(self.root, "_exit_manager", None)
        if exit_manager is not None:
            exit_manager.request_exit()
            return
        try:
            self.root.destroy()
        except tk.TclError:
            pass

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
                return
            if self._supports_alpha:
                try:
                    self.root.attributes("-alpha", 1.0)
                except tk.TclError:
                    self._supports_alpha = False
            self._anim_offset = 0.0
            self._layout()

        step()

    def _apply_background_mode(self) -> None:
        bg_color = CANVAS_BG if self._background_enabled else BACKGROUND_OFF_COLOR
        self.configure(bg=bg_color)
        self.canvas.configure(bg=bg_color)
        if self._background_enabled:
            self._last_bg_size = None
            return
        self.canvas.itemconfigure(self.bg_item, image="")

    @staticmethod
    def _default_filter_settings() -> dict:
        return {
            "leverage": DEFAULT_LEVERAGE,
        }

    def _current_filter_settings(self) -> dict:
        return {
            "leverage": self.leverage_dropdown.get(),
        }

    def _settings_locked(self) -> bool:
        return self._trade_state == "start"

    def _trade_state_display_text(self) -> str:
        return TRADE_STATE_LABELS.get(self._trade_state, "-")

    def _refresh_filter_controls_lock(self) -> None:
        locked = self._settings_locked()
        desired_state = "disabled" if locked else "readonly"
        for combobox in (self.leverage_dropdown,):
            if str(combobox.cget("state")) != desired_state:
                combobox.configure(state=desired_state)

        if not locked:
            return

        self.canvas.focus_set()
        self.leverage_dropdown.selection_clear()
        self._button_hover["filter_save"] = False
        self._button_lift["filter_save"] = 0.0

    def _update_filter_save_state(self) -> None:
        current = self._current_filter_settings()
        saved = self._saved_filter_settings or self._default_filter_settings()
        enabled = current != saved and not self._settings_locked()
        if enabled == self._save_enabled:
            return
        self._save_enabled = enabled
        if not enabled:
            self._button_hover["filter_save"] = False
            self._button_lift["filter_save"] = 0.0
        self._layout()

    def _on_filter_change(self, _event=None) -> None:
        if self._settings_locked():
            _log_trade(
                "Filter change blocked: "
                f"reason=auto_trade_running trade_state={self._trade_state}"
            )
            self._refresh_filter_controls_lock()
            self._update_filter_save_state()
            return
        _log_trade(
            "Filter changed: "
            f"leverage={self.leverage_dropdown.get()}"
        )
        self._update_filter_save_state()

    def _handle_filter_save(self, _event=None) -> None:
        if self._settings_locked():
            _log_trade(
                "Filter save blocked: "
                f"reason=auto_trade_running trade_state={self._trade_state}"
            )
            self._show_info_message("자동매매 안내", "자동매매 실행중에는 설정을 변경할 수 없습니다.")
            return
        if not self._save_enabled:
            return
        self._saved_filter_settings = self._current_filter_settings()
        _log_trade(
            "Filter settings saved: "
            f"leverage={self._saved_filter_settings['leverage']}"
        )
        self._show_info_message("설정 저장", "레버리지 설정이 저장되었습니다.")
        self._update_filter_save_state()

    def _set_trade_state(self, value: str) -> None:
        if value not in {"start", "stop"}:
            return
        if self._trade_state == value:
            return
        self._trade_state = value
        _log_trade(
            "Trade state changed: "
            f"state={self._trade_state} display={self._trade_state_display_text()}"
        )
        self._refresh_filter_controls_lock()
        self._update_filter_save_state()
        self._layout()

    def _confirm_yes_no(self, title: str, message: str) -> bool:
        askyesno = getattr(messagebox, "askyesno", None)
        if not callable(askyesno):
            _log_trade(
                "Confirmation dialog unavailable: "
                f"title={title} reason=askyesno_not_callable default=True"
            )
            return True
        try:
            return bool(askyesno(title, message, parent=self))
        except tk.TclError as exc:
            _log_trade(f"Confirmation dialog failed: title={title} error={exc!r} default=False")
            return False

    def _build_start_confirmation_message(self) -> str:
        settings = self._current_filter_settings()
        wallet_value = str(self._wallet_value or "--").strip() or "--"
        wallet_unit = str(self._wallet_unit or "").strip()
        wallet_text = f"{wallet_value} {wallet_unit}".strip()
        return (
            f"나의 지갑 잔고 : {wallet_text}\n"
            f"레버리지 : {settings.get('leverage') or DEFAULT_LEVERAGE}\n\n"
            "자동매매를 실행하시겠습니까?"
        )

    @staticmethod
    def _build_stop_confirmation_message() -> str:
        return (
            "현재 자동매매가 실행중입니다.\n\n"
            "자동매매를 취소하시면 현재 보유중인 포지션이 있을경우 수동으로 청산해야 하며 "
            "이후 수신되는 신호에 대한 자동매매는 중지됩니다. 중지하시겠습니까?"
        )

    def _handle_start_click(self, _event=None) -> None:
        if self._trade_state == "start":
            _log_trade("Auto-trade start ignored: reason=already_running trade_state=start")
            self._show_info_message("자동매매 안내", "이미 실행중입니다.")
            return
        _log_trade(
            "Auto-trade start confirmation opened: "
            f"trade_state={self._trade_state} wallet={self._wallet_value} {self._wallet_unit}"
        )
        confirmed = self._confirm_yes_no("자동매매 시작 확인", self._build_start_confirmation_message())
        if not confirmed:
            _log_trade("Auto-trade start canceled by user.")
            return
        started, message = self._entry_bot.start()
        if not started:
            _log_trade(f"Auto-trade start failed: failure={message}")
            self._show_info_message("자동매매 안내", message)
            return
        _log_trade("Auto-trade start confirmed by user.")
        self._set_trade_state("start")

    def _handle_stop_click(self, _event=None) -> None:
        if self._trade_state != "start":
            _log_trade("Auto-trade stop ignored: reason=already_stopped trade_state=stop")
            self._show_info_message("자동매매 안내", "자동매매가 현재 중지상태 입니다.")
            return
        _log_trade(
            "Auto-trade stop confirmation opened: "
            f"trade_state={self._trade_state}"
        )
        confirmed = self._confirm_yes_no("자동매매 중지 확인", self._build_stop_confirmation_message())
        if not confirmed:
            _log_trade("Auto-trade stop canceled by user.")
            return
        _log_trade("Auto-trade stop confirmed by user.")
        self._entry_bot.stop("user_stop")
        self._set_trade_state("stop")

    def _show_info_message(self, title: str, message: str) -> None:
        try:
            messagebox.showinfo(title, message, parent=self)
        except tk.TclError as exc:
            _log_trade(f"Info dialog failed: title={title} error={exc!r}")

    def _selected_leverage_label(self) -> str:
        saved = self._saved_filter_settings or {}
        return str(self.leverage_dropdown.get() or saved.get("leverage") or DEFAULT_LEVERAGE)

    def _start_initial_snapshot_fetch(self) -> None:
        def worker() -> None:
            try:
                self._entry_bot.refresh_wallet_balance_once()
            except Exception as exc:
                _log_trade(f"Initial wallet balance fetch failed: error={exc!r}")

        threading.Thread(target=worker, name="TradePageInitialSnapshot", daemon=True).start()

    def _schedule_entry_snapshot_update(self, snapshot: AccountSnapshot) -> None:
        try:
            self.after(0, lambda payload=snapshot: self._apply_entry_snapshot_update(payload))
        except tk.TclError:
            pass

    def _apply_entry_snapshot_update(self, snapshot: AccountSnapshot) -> None:
        balance = snapshot.wallet_balance
        if balance is None or balance < 0:
            if not self._wallet_warning_visible:
                _log_trade("Wallet balance display switched to warning state: reason=fetch_failed")
            self._wallet_warning_visible = True
            self._wallet_value = WALLET_WARNING_TEXT
            self._wallet_unit = ""
            self._wallet_value_color = WALLET_WARNING_COLOR
        else:
            if self._wallet_warning_visible:
                _log_trade(f"Wallet balance display recovered: balance={float(balance):.2f}")
            self._wallet_warning_visible = False
            self._wallet_value = f"{float(balance):,.2f}"
            self._wallet_unit = "USDT"
            self._wallet_value_color = WALLET_VALUE_COLOR
            self._schedule_wallet_balance_sheet_sync(float(balance))
        self._layout()

    def _schedule_wallet_balance_sheet_sync(self, balance: float) -> None:
        if not self._api_key:
            return

        now = time.time()
        with self._sheet_balance_sync_lock:
            due = self._sheet_balance_sync_pending or now >= self._sheet_balance_sync_next_at
            if not due or self._sheet_balance_sync_in_progress:
                return
            self._sheet_balance_sync_in_progress = True

        _log_trade(
            "Wallet balance sheet sync scheduled: "
            f"balance={float(balance):.2f} pending={self._sheet_balance_sync_pending}"
        )

        def worker() -> None:
            self._sync_wallet_balance_to_sheet(balance)

        threading.Thread(target=worker, name="TradePageBalanceSheetSync", daemon=True).start()

    def _sync_wallet_balance_to_sheet(self, balance: float) -> None:
        success = False
        payload = {
            "action": "update_balance",
            "api_key": self._api_key,
            "balance": round(float(balance), 2),
        }

        _log_trade(
            "Wallet balance sheet sync started: "
            f"balance={payload['balance']:.2f} timeout={SUBSCRIBER_REQUEST_TIMEOUT_SEC}"
        )

        try:
            response = requests.post(
                SUBSCRIBER_WEBHOOK_URL,
                json=payload,
                timeout=SUBSCRIBER_REQUEST_TIMEOUT_SEC,
            )
            response.raise_for_status()
            data = response.json()
            success = isinstance(data, dict) and data.get("result") == "updated"
            _log_trade(
                "Wallet balance sheet sync completed: "
                f"success={success} response={data if isinstance(data, dict) else '-'}"
            )
        except (requests.RequestException, TypeError, ValueError) as exc:
            _log_trade(f"Wallet balance sheet sync failed: error={exc!r}")
        finally:
            with self._sheet_balance_sync_lock:
                self._sheet_balance_sync_in_progress = False
                if success:
                    self._sheet_balance_sync_pending = False
                    self._sheet_balance_sync_next_at = time.time() + BALANCE_SYNC_INTERVAL_SEC
                else:
                    self._sheet_balance_sync_pending = True

    def destroy(self) -> None:
        try:
            self._entry_bot.stop("widget_destroy")
        except Exception as exc:
            _log_trade(f"Entry bot stop on destroy failed: error={exc!r}")
        super().destroy()

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
        combobox.bind("<<ComboboxSelected>>", lambda _event: self.after(1, clear_selection), add="+")

    def _clear_combo_focus(self, _event: tk.Event) -> None:
        self.canvas.focus_set()
        self.leverage_dropdown.selection_clear()

    def _on_resize(self, _event: tk.Event) -> None:
        self._layout()

    def _set_font_scale(self, scale: float) -> None:
        for name, (base_size, weight) in self._base_fonts.items():
            self.fonts[name].configure(size=max(8, int(base_size * scale)), weight=weight)
        text_height = self.fonts["dropdown"].metrics("linespace")
        filter_height = (LEVERAGE_DROPDOWN_RECT[3] - LEVERAGE_DROPDOWN_RECT[1]) * scale
        padding_y = max(0, int((filter_height - text_height) / 2))
        self._configure_combobox_style("TradeFilter.TCombobox", padding_y)

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
            resized = Image.alpha_composite(resized, Image.new("RGBA", resized.size, (0, 0, 0, 140)))
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

    def _scale_rect(self, rect: Tuple[int, int, int, int], scale: float, pad_x: float, pad_y: float) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = rect
        return pad_x + x1 * scale, pad_y + y1 * scale, pad_x + x2 * scale, pad_y + y2 * scale

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
        self._draw_strategy_guides_panel(scale, pad_x, content_pad_y)
        self._draw_wallet(scale, pad_x, content_pad_y)
        self._draw_manager_connection_panel(scale, pad_x, content_pad_y)
        self._draw_channel_info_panel(scale, pad_x, content_pad_y)

        self.canvas.coords(
            self.bg_toggle_item,
            pad_x + BG_TOGGLE_POS[0] * scale,
            pad_y + (BG_TOGGLE_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.exit_item,
            pad_x + EXIT_ICON_POS[0] * scale,
            pad_y + (EXIT_ICON_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.tag_raise(self.bg_toggle_item)
        self.canvas.tag_raise(self.exit_item)

    def _draw_chart(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(CHART_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("chart", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        self._draw_filter_controls(scale, pad_x, pad_y)

    def _draw_filter_label(self, rect: Tuple[int, int, int, int], text: str, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        border = max(1, int(scale))
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
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2 + FILTER_TEXT_OFFSET * scale,
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
        self.canvas.itemconfigure(window_id, width=max(1, int(x2 - x1)), height=max(1, int(y2 - y1)))
        self.canvas.tag_raise(window_id)

    def _set_window_visibility(self, window_id: int, visible: bool) -> None:
        self.canvas.itemconfigure(window_id, state="normal" if visible else "hidden")

    def _draw_filter_controls(self, scale: float, pad_x: float, pad_y: float) -> None:
        def offset_rect(rect: Tuple[int, int, int, int], offset_y: float) -> Tuple[int, int, int, int]:
            x1, y1, x2, y2 = rect
            return x1, y1 + offset_y, x2, y2 + offset_y

        control_rects = [
            LEVERAGE_LABEL_RECT,
            LEVERAGE_DROPDOWN_RECT,
        ]
        min_y = min(rect[1] for rect in control_rects)
        max_y = max(rect[3] for rect in control_rects)
        offset_y = ((CHART_RECT[1] + CHART_RECT[3]) / 2) - ((min_y + max_y) / 2)

        self._set_window_visibility(self.leverage_dropdown_window, True)

        self._draw_filter_label(offset_rect(LEVERAGE_LABEL_RECT, offset_y), "레버리지", scale, pad_x, pad_y)
        self._position_dropdown(
            self.leverage_dropdown_window,
            offset_rect(LEVERAGE_DROPDOWN_RECT, offset_y),
            scale,
            pad_x,
            pad_y,
        )

        save_fill = SAVE_SETTINGS_FILL if self._save_enabled else SAVE_SETTINGS_DISABLED_FILL
        self._draw_rounded_button(
            offset_rect(SAVE_SETTINGS_BUTTON_RECT, offset_y),
            "설정 저장",
            save_fill,
            "filter_save",
            active=False,
            hover=self._button_hover.get("filter_save", False) and self._save_enabled,
            lift=self._button_lift.get("filter_save", 0.0) if self._save_enabled else 0.0,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )

    def _draw_strategy_guides_panel(self, scale: float, pad_x: float, pad_y: float) -> None:
        self._draw_titled_panel(
            panel_key="strategy_guides",
            rect=STRATEGY_GUIDE_PANEL_RECT,
            title=STRATEGY_GUIDE_TITLE,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        content_top = (
            STRATEGY_GUIDE_PANEL_RECT[1]
            + SECTION_TITLE_HEIGHT
            + STRATEGY_GUIDE_CONTENT_TOP_PADDING
        )
        content_bottom = STRATEGY_GUIDE_PANEL_RECT[3] - STRATEGY_GUIDE_CONTENT_BOTTOM_PADDING
        content_center_y = (content_top + content_bottom) / 2
        button_y1 = int(
            round(content_center_y - ((STRATEGY_GUIDE_BUTTON_HEIGHT - STRATEGY_GUIDE_LABEL_OFFSET) / 2))
        )
        button_y2 = button_y1 + STRATEGY_GUIDE_BUTTON_HEIGHT
        for tag, label in STRATEGY_GUIDE_ITEMS:
            base_rect = STRATEGY_GUIDE_BUTTON_RECTS[tag]
            rect = (base_rect[0], button_y1, base_rect[2], button_y2)
            bx1, by1, bx2, _ = self._scale_rect(rect, scale, pad_x, pad_y)
            self.canvas.create_text(
                (bx1 + bx2) / 2,
                by1 - (STRATEGY_GUIDE_LABEL_OFFSET * scale),
                text=label,
                font=self.fonts["table_header"],
                fill=UI_TEXT_COLOR,
                anchor="center",
                tags="ui",
            )
            self._draw_rounded_button(
                rect,
                label,
                "#000000",
                tag,
                active=False,
                hover=self._button_hover.get(tag, False),
                lift=self._button_lift.get(tag, 0.0),
                scale=scale,
                pad_x=pad_x,
                pad_y=pad_y,
                font_name="table_header",
            )

    def _draw_manager_connection_panel(self, scale: float, pad_x: float, pad_y: float) -> None:
        self._draw_titled_panel(
            panel_key="manager_connection",
            rect=MANAGER_CONNECTION_RECT,
            title=MANAGER_CONNECTION_TITLE,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        self._draw_link_button_items(
            MANAGER_CONNECTION_ITEMS,
            MANAGER_CONNECTION_BUTTON_RECTS,
            scale,
            pad_x,
            pad_y,
        )

    def _draw_channel_info_panel(self, scale: float, pad_x: float, pad_y: float) -> None:
        self._draw_titled_panel(
            panel_key="channel_info",
            rect=CHANNEL_INFO_RECT,
            title=CHANNEL_INFO_TITLE,
            title_height=CHANNEL_INFO_TITLE_HEIGHT,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        self._draw_link_button_items(
            CHANNEL_INFO_ITEMS,
            CHANNEL_INFO_BUTTON_RECTS,
            scale,
            pad_x,
            pad_y,
        )

    def _draw_link_button_items(
        self,
        items,
        button_rects: Dict[str, Tuple[int, int, int, int]],
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> None:
        for tag, label, _option, _url in items:
            rect = button_rects[tag]
            bx1, by1, bx2, _ = self._scale_rect(rect, scale, pad_x, pad_y)
            self.canvas.create_text(
                (bx1 + bx2) / 2,
                by1 - (16 * scale),
                text=label,
                font=self.fonts["table_header"],
                fill=UI_TEXT_COLOR,
                anchor="center",
                tags="ui",
            )
            self._draw_rounded_button(
                rect,
                label,
                "#000000",
                tag,
                active=False,
                hover=self._button_hover.get(tag, False),
                lift=self._button_lift.get(tag, 0.0),
                scale=scale,
                pad_x=pad_x,
                pad_y=pad_y,
                font_name="table_header",
            )

    def _draw_titled_panel(
        self,
        *,
        panel_key: str,
        rect: Tuple[int, int, int, int],
        title: str,
        title_height: Optional[float] = None,
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        panel = self._panel_image(panel_key, int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        radius = max(6, int(PANEL_RADIUS * scale))
        border = max(1, int(2 * scale))
        title_top = y1
        effective_title_height = SECTION_TITLE_HEIGHT if title_height is None else title_height
        title_bottom = min(y2, y1 + effective_title_height * scale)

        self.canvas.create_polygon(
            _round_rect_points(x1, title_top, x2, title_bottom, radius),
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
            (title_top + title_bottom) / 2,
            text=title,
            font=self.fonts["table_title"],
            fill="#000000",
            anchor="center",
            tags="ui",
        )
        return x1, y1, x2, y2

    def _draw_wallet(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(WALLET_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("wallet", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        center_x = (x1 + x2) / 2
        label = "나의 지갑 잔고 :"
        value = self._wallet_value
        suffix = self._wallet_unit

        label_w = self.fonts["wallet"].measure(label + " ")
        value_w = self.fonts["wallet_value"].measure(value + (" " if suffix else ""))
        suffix_w = self.fonts["wallet"].measure(suffix)
        total_w = label_w + value_w + suffix_w
        settings = self._current_filter_settings()
        line_font = self.fonts["wallet"]
        value_font = self.fonts["wallet_value"]
        line_height = max(line_font.metrics("linespace"), value_font.metrics("linespace"))
        line_gap = WALLET_SETTINGS_LINE_GAP * scale
        rows = [
            {
                "label": "레버리지 :",
                "value": settings.get("leverage") or "-",
                "height": float(line_height),
            },
            {
                "label": "현재 구동상태 :",
                "value": self._trade_state_display_text(),
                "height": float(line_height),
            },
        ]
        start_button_y1 = self._scale_rect(START_BUTTON_RECT, scale, pad_x, pad_y)[1]
        stop_button_y1 = self._scale_rect(STOP_BUTTON_RECT, scale, pad_x, pad_y)[1]
        text_area_top = y1
        text_area_bottom = min(start_button_y1, stop_button_y1)
        wallet_row_height = float(line_height)
        text_block_height = wallet_row_height + sum(row["height"] for row in rows) + len(rows) * line_gap
        row_top = (
            text_area_top
            + max(0.0, (text_area_bottom - text_area_top - text_block_height) / 2)
            + WALLET_TEXT_CENTER_OFFSET_Y * scale
        )
        text_y = row_top + wallet_row_height / 2
        start_x = center_x - total_w / 2

        self.canvas.create_text(
            start_x + label_w / 2,
            text_y,
            text=label,
            font=self.fonts["wallet"],
            fill=UI_TEXT_COLOR,
            anchor="center",
            tags="ui",
        )
        self.canvas.create_text(
            start_x + label_w + value_w / 2,
            text_y,
            text=value,
            font=self.fonts["wallet_value"],
            fill=self._wallet_value_color,
            anchor="center",
            tags="ui",
        )
        self.canvas.create_text(
            start_x + label_w + value_w + suffix_w / 2,
            text_y,
            text=suffix,
            font=self.fonts["wallet"],
            fill=UI_TEXT_COLOR,
            anchor="center",
            tags="ui",
        )

        row_top += wallet_row_height + line_gap

        for row in rows:
            center_y = row_top + row["height"] / 2
            label_text = str(row["label"])
            value_text = str(row["value"])
            label_w = line_font.measure(label_text + " ")
            value_w = value_font.measure(value_text)
            total_w = label_w + value_w
            start_x = center_x - total_w / 2
            self.canvas.create_text(
                start_x + label_w / 2,
                center_y,
                text=label_text,
                font=line_font,
                fill=UI_TEXT_COLOR,
                anchor="center",
                tags="ui",
            )
            self.canvas.create_text(
                start_x + label_w + value_w / 2,
                center_y,
                text=value_text,
                font=value_font,
                fill=UI_TEXT_COLOR,
                anchor="center",
                tags="ui",
            )
            row_top += row["height"] + line_gap

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
        font_name: str = "button",
    ) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        if lift:
            offset = lift * scale
            y1 += offset
            y2 += offset
        radius = max(6, int(10 * scale))
        border = max(1, int((3 if active else 1) * scale))
        fill_color = _lighten_hex(fill, BUTTON_HOVER_LIGHTEN) if hover else fill
        self.canvas.create_polygon(
            _round_rect_points(x1, y1, x2, y2, radius),
            fill=fill_color,
            outline=BUTTON_ACTIVE_BORDER if active else "#000000",
            width=border,
            smooth=True,
            splinesteps=36,
            tags=("ui", tag),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            font=self.fonts[font_name],
            fill=BUTTON_TEXT_COLOR,
            anchor="center",
            tags=("ui", tag),
        )

    def _handle_long_strategy_guide(self, _event=None) -> None:
        self._open_strategy_guide_pdf(option="long_strategy_guide", filename="long.pdf")

    def _handle_short_strategy_guide(self, _event=None) -> None:
        self._open_strategy_guide_pdf(option="short_strategy_guide", filename="short.pdf")

    def _handle_dca_strategy_guide(self, _event=None) -> None:
        self._open_strategy_guide_pdf(option="dca_strategy_guide", filename="dca.pdf")

    def _handle_manager_connection_link(self, *, option: str, url: str) -> None:
        self._open_external_link(
            log_prefix="Manager connection",
            option=option,
            url=url,
            error_prefix="관리자 링크를 열 수 없습니다",
        )

    def _handle_channel_info_link(self, *, option: str, url: str) -> None:
        self._open_external_link(
            log_prefix="Channel info",
            option=option,
            url=url,
            error_prefix="채널 링크를 열 수 없습니다",
        )

    def _open_external_link(self, *, log_prefix: str, option: str, url: str, error_prefix: str) -> None:
        _log_trade(f"{log_prefix} button clicked: option={option} url={url}")
        try:
            self._open_url(url)
            _log_trade(f"{log_prefix} url opened: option={option} url={url}")
        except Exception as exc:
            _log_trade(f"{log_prefix} url open failed: option={option} url={url} error={exc!r}")
            messagebox.showerror("열기 실패", f"{error_prefix}:\n{exc}", parent=self)

    def _open_strategy_guide_pdf(self, *, option: str, filename: str) -> None:
        _log_trade(f"Strategy guide button clicked: option={option}")
        base_dir = Path(__file__).resolve().parent
        pdf_path = base_dir / "image" / "login_page" / filename
        if not pdf_path.exists():
            _log_trade(f"Strategy guide pdf missing: option={option} path={pdf_path}")
            messagebox.showerror("파일 없음", f"PDF 파일을 찾을 수 없습니다:\n{pdf_path}", parent=self)
            return
        try:
            self._open_file(pdf_path)
            _log_trade(f"Strategy guide pdf opened: option={option} path={pdf_path}")
        except Exception as exc:
            _log_trade(f"Strategy guide pdf open failed: option={option} path={pdf_path} error={exc!r}")
            messagebox.showerror("열기 실패", f"PDF를 열 수 없습니다:\n{exc}", parent=self)

    @staticmethod
    def _open_file(path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    @staticmethod
    def _open_url(url: str) -> None:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
            return
        if not webbrowser.open_new_tab(url):
            raise RuntimeError("기본 브라우저를 실행하지 못했습니다.")
