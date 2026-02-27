from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
from collections import Counter
from dataclasses import replace
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import requests
import config
from log_rotation import append_rotating_log_line
from runtime_paths import get_log_path

from PIL import Image, ImageDraw, ImageTk
from auto_trade import (
    AutoTradeRuntime,
    GatewayCallResult,
    SymbolFilterRules,
    ExchangeSnapshot,
    ExitReconcileExecutionResult,
    ExitReconcilePlan,
    PersistentRecoveryState,
    process_telegram_message,
    run_trigger_entry_cycle,
    load_auto_trade_settings,
    RecoveryRuntimeState,
    run_recovery_startup_with_logging,
    stop_signal_loop_with_logging,
    parse_leading_market_message,
    parse_risk_management_message,
    poll_telegram_updates_with_logging,
    TriggerCandidate,
    apply_price_source_and_guard,
    sync_entry_fill_flow,
    execute_oco_cancel_flow,
    update_exit_partial_and_check_five_second,
    evaluate_exit_five_second_rule,
    get_mark_price_with_logging,
    update_account_activity_with_logging,
    create_order_with_retry_with_logging,
    cancel_order_with_retry_with_logging,
    query_order_with_retry_with_logging,
    OrderCreateRequest,
    OrderCancelRequest,
    OrderQueryRequest,
    RetryPolicy,
    TRIGGER_BUFFER_RATIO_DEFAULT,
    floor_quantity_by_step_size,
    round_price_by_tick_size,
)

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
WALLET_LIMIT_EXCEEDED_COLOR = HIGHLIGHT_TEXT
AUTO_TRADE_WALLET_STOP_THRESHOLD_USDT_DEFAULT = 2000.0
AUTO_TRADE_WALLET_STOP_THRESHOLD_ENV = "LTS_AUTO_TRADE_WALLET_STOP_THRESHOLD_USDT"
AUTO_TRADE_WALLET_START_WARNING_MESSAGE = (
    "※경고 : 현재 지갑 잔액이 2000USDT 이상입니다. "
    "AUM 관리를 위해 시드를 500~1000 USDT로 낮춰주세요."
)
TRADE_LOG_PATH = get_log_path("LTS-Trade.log")
AUTO_TRADE_PERSIST_PATH = Path(tempfile.gettempdir()) / "LTS-auto-trade-state.json"
AUTO_TRADE_SIGNAL_INBOX_PATH = Path(tempfile.gettempdir()) / "LTS-auto-trade-signal-inbox.jsonl"
SIGNAL_LOOP_INTERVAL_SEC = 1.0
TP_TRIGGER_SUBMISSION_GUARD_SEC = 20.0
TP_SPLIT_ORDER_COUNT = 10
TP_SPLIT_STEP_RATIO = 0.001
PHASE2_TP_START_RATIO = -0.01
PHASE2_TP_STEP_RATIO = 0.001
ENTRY_CANCEL_SYNC_GUARD_SEC = 3.0
EXCHANGE_INFO_CACHE_TTL_SEC = 60
ACCOUNT_SNAPSHOT_CACHE_TTL_SEC = 0.9
ACCOUNT_SNAPSHOT_STALE_FALLBACK_SEC = 30
ACCOUNT_REST_UNHEALTHY_FORCE_MIN_INTERVAL_SEC = 3.0
FUTURES_BALANCE_CACHE_TTL_SEC = 1.5
POSITION_ZERO_CONFIRM_REQUIRED_SNAPSHOTS = 2
RECENT_KLINE_LIMIT = 20
TELEGRAM_BOT_TOKEN_ENV = "LTS_TELEGRAM_BOT_TOKEN"
TELEGRAM_POLL_TIMEOUT_SEC = 2
TELEGRAM_REQUEST_TIMEOUT_SEC = 10
TELEGRAM_POLL_LIMIT = 100
TELEGRAM_POLL_ERROR_LOG_THROTTLE_SEC = 5
TELEGRAM_START_SYNC_MAX_BATCHES = 300
SIGNAL_SOURCE_MODE_ENV = "LTS_SIGNAL_SOURCE_MODE"
SIGNAL_SOURCE_MODE_TELEGRAM = "telegram"
SIGNAL_SOURCE_MODE_RELAY = "relay"
SIGNAL_RELAY_BASE_URL_ENV = "LTS_SIGNAL_RELAY_BASE_URL"
SIGNAL_RELAY_CLIENT_ID_ENV = "LTS_SIGNAL_RELAY_CLIENT_ID"
SIGNAL_RELAY_TOKEN_ENV = "LTS_SIGNAL_RELAY_TOKEN"
SIGNAL_RELAY_REQUEST_TIMEOUT_ENV = "LTS_SIGNAL_RELAY_REQUEST_TIMEOUT_SEC"
SIGNAL_RELAY_POLL_LIMIT_ENV = "LTS_SIGNAL_RELAY_POLL_LIMIT"
SIGNAL_RELAY_REQUEST_TIMEOUT_SEC = 5
SIGNAL_RELAY_POLL_LIMIT = 100
SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC = 5
# Trigger/monitoring price basis uses last traded price stream.
BINANCE_FUTURES_MARK_PRICE_STREAM_URL = "wss://fstream.binance.com/ws/!ticker@arr"
FUTURES_LAST_PRICE_PATH = "/fapi/v1/ticker/price"
WS_RECONNECT_BACKOFF_SEC = 3
BINANCE_FUTURES_USER_STREAM_BASE_URL = "wss://fstream.binance.com/ws"
USER_STREAM_LISTEN_KEY_PATH = "/fapi/v1/listenKey"
USER_STREAM_KEEPALIVE_SEC = 30 * 60
USER_STREAM_HEALTHY_GRACE_SEC = 12
ACCOUNT_REST_RECONCILE_INTERVAL_SEC = 20
ACCOUNT_REST_BACKOFF_BASE_SEC = 2
ACCOUNT_REST_BACKOFF_MAX_SEC = 20
QUERY_CANCEL_RETRY_MAX_ATTEMPTS = 2
QUERY_CANCEL_RETRYABLE_REASON_CODES = (
    "NETWORK_ERROR",
    "TIMEOUT",
    "SERVER_ERROR",
    "TEMPORARY_UNAVAILABLE",
)
SERVER_TIME_SYNC_PATH = "/fapi/v1/time"
SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT = 1
AUTH_ERROR_POPUP_THROTTLE_SEC = 60
POSITION_RISK_PATH = "/fapi/v2/positionRisk"
POSITION_MODE_PATH = "/fapi/v1/positionSide/dual"
MULTI_ASSETS_MARGIN_MODE_PATH = "/fapi/v1/multiAssetsMargin"
LEVERAGE_SET_PATH = "/fapi/v1/leverage"
MARGIN_TYPE_SET_PATH = "/fapi/v1/marginType"
FUTURES_ORDER_PATH = "/fapi/v1/order"
FUTURES_OPEN_ORDERS_PATH = "/fapi/v1/openOrders"
FUTURES_CANCEL_ALL_OPEN_ORDERS_PATH = "/fapi/v1/allOpenOrders"
FUTURES_ALGO_ORDER_PATH = "/fapi/v1/algoOrder"
FUTURES_OPEN_ALGO_ORDERS_PATH = "/fapi/v1/openAlgoOrders"
FUTURES_CANCEL_ALL_OPEN_ALGO_ORDERS_PATH = "/fapi/v1/algoOpenOrders"
ALGO_ORDER_TYPES = {"STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT", "TRAILING_STOP_MARKET"}
ENTRY_MODE_AGGRESSIVE = "AGGRESSIVE"
ENTRY_MODE_CONSERVATIVE = "CONSERVATIVE"
ENTRY_MODE_TO_TARGET_LEVERAGE = {
    ENTRY_MODE_AGGRESSIVE: 2,
    ENTRY_MODE_CONSERVATIVE: 1,
}

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
MONITOR_EMPTY_TEXT_Y = 96 / MONITOR_REF_HEIGHT
MONITOR_ROW_FIRST_Y = 66 / MONITOR_REF_HEIGHT
MONITOR_ROW_STEP = 24 / MONITOR_REF_HEIGHT
MONITOR_MAX_ROWS = 5

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
TP_RATIO_OPTIONS = ["0.5%", "3%", "5%"]


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
        append_rotating_log_line(TRADE_LOG_PATH, line)
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
        self._single_asset_mode_ready = False
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

        self._trade_state = "stop"
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
        self._wallet_over_auto_stop_limit = False
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
        self._auto_trade_state = RecoveryRuntimeState()
        self._auto_trade_runtime_lock = threading.Lock()
        self._auto_trade_starting = False
        self._auto_trade_last_message_ids: dict[int, int] = {}
        self._auto_trade_cooldown_by_symbol: dict[str, int] = {}
        self._auto_trade_received_at_by_symbol: dict[str, int] = {}
        self._auto_trade_message_id_by_symbol: dict[str, int] = {}
        self._auto_trade_monitoring_queue: list[str] = []
        self._auto_trade_settings = load_auto_trade_settings()
        self._orchestrator_runtime = AutoTradeRuntime(settings=self._auto_trade_settings)
        self._signal_queue_lock = threading.Lock()
        self._signal_event_queue: list[dict] = []
        self._signal_loop_thread: Optional[threading.Thread] = None
        self._signal_loop_stop = threading.Event()
        self._exchange_info_cache: Optional[dict] = None
        self._exchange_info_cache_at: float = 0.0
        self._signal_inbox_offset = 0
        self._telegram_bot_token = os.environ.get(TELEGRAM_BOT_TOKEN_ENV, "").strip()
        self._telegram_update_offset = 0
        self._telegram_last_poll_error_log_at = 0.0
        self._signal_relay_base_url = self._resolve_signal_relay_base_url()
        self._signal_relay_token = self._resolve_signal_relay_token()
        self._signal_source_mode = self._resolve_signal_source_mode()
        self._signal_relay_client_id = self._resolve_signal_relay_client_id()
        self._signal_relay_update_offset = 0
        self._signal_relay_request_timeout_sec = self._read_env_int_or_default(
            SIGNAL_RELAY_REQUEST_TIMEOUT_ENV,
            SIGNAL_RELAY_REQUEST_TIMEOUT_SEC,
            minimum=1,
            maximum=30,
        )
        self._signal_relay_poll_limit = self._read_env_int_or_default(
            SIGNAL_RELAY_POLL_LIMIT_ENV,
            SIGNAL_RELAY_POLL_LIMIT,
            minimum=1,
            maximum=500,
        )
        self._auto_trade_wallet_stop_threshold_usdt = self._read_env_float_or_default(
            AUTO_TRADE_WALLET_STOP_THRESHOLD_ENV,
            AUTO_TRADE_WALLET_STOP_THRESHOLD_USDT_DEFAULT,
            minimum=0.0,
            log_scope="Wallet auto-stop config",
        )
        self._signal_relay_last_poll_error_log_at = 0.0
        self._last_monitor_snapshot = ""
        self._last_auto_trade_status_snapshot = ""
        self._rate_limit_fail_streak = 0
        self._rate_limit_recover_streak = 0
        self._auth_error_recover_streak = 0
        self._filter_controls_locked = False
        self._account_snapshot_cache_lock = threading.Lock()
        self._open_orders_cache: Optional[list[dict]] = None
        self._open_orders_cache_at = 0.0
        self._positions_cache: Optional[list[dict]] = None
        self._positions_cache_at = 0.0
        self._positions_cache_dust_symbols: set[str] = set()
        self._last_account_rest_reconcile_at = 0.0
        self._account_snapshot_rest_backoff_until = 0.0
        self._account_snapshot_rest_backoff_sec = 0.0
        self._account_snapshot_last_user_stream_force_at = 0.0
        self._account_snapshot_last_user_stream_force_cycle_id = 0
        self._account_snapshot_invalidation_seq = 0
        self._signal_loop_snapshot_cycle_seq = 0
        self._futures_balance_cache_lock = threading.Lock()
        self._futures_balance_cache: Optional[list[dict]] = None
        self._futures_balance_cache_at = 0.0
        self._ws_price_lock = threading.Lock()
        self._ws_price_by_symbol: dict[str, float] = {}
        self._ws_price_received_at = 0
        self._ws_loop_thread: Optional[threading.Thread] = None
        self._ws_loop_stop = threading.Event()
        self._user_stream_lock = threading.Lock()
        self._user_stream_thread: Optional[threading.Thread] = None
        self._user_stream_stop = threading.Event()
        self._user_stream_connected = False
        self._user_stream_last_activity_at = 0.0
        self._user_stream_last_keepalive_at = 0.0
        self._user_stream_listen_key = ""
        self._user_stream_positions_by_symbol: dict[str, dict] = {}
        self._user_stream_open_orders_by_symbol: dict[str, dict[int, dict]] = {}
        self._user_stream_last_snapshot_signature = ""
        self._oco_last_filled_exit_order_by_symbol: dict[str, int] = {}
        self._last_open_exit_order_ids_by_symbol: dict[str, set[int]] = {}
        self._pending_oco_retry_symbols: set[str] = set()
        self._entry_order_ref_by_symbol: dict[str, int] = {}
        self._entry_cancel_sync_guard_until_by_symbol: dict[str, float] = {}
        self._second_entry_skip_latch: set[str] = set()
        self._second_entry_fully_filled_symbols: set[str] = set()
        self._phase1_tp_filled_symbols: set[str] = set()
        self._tp_trigger_submit_guard_by_symbol: dict[str, dict[str, object]] = {}
        self._last_position_qty_by_symbol: dict[str, float] = {}
        self._last_position_entry_price_by_symbol: dict[str, float] = {}
        self._position_zero_confirm_streak_by_symbol: dict[str, int] = {}
        self._last_safety_action_code = ""
        self._last_safety_action_at = 0
        self._server_time_offset_ms = 0
        self._server_time_offset_lock = threading.Lock()
        self._auth_error_popup_last_at = 0.0
        self._auth_error_popup_open = False
        self._last_dust_symbols: set[str] = set()

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

        self._hydrate_auto_trade_state_from_disk()
        self._sync_orchestrator_runtime_from_recovery_state()
        _log_trade(
            "Signal source configured: "
            f"mode={self._signal_source_mode} "
            f"relay_base_url={self._signal_relay_base_url or '-'} "
            f"relay_client_id={self._signal_relay_client_id} "
            f"relay_token_set={bool(self._signal_relay_token)}"
        )
        _log_trade(
            "Telegram receiver configured: "
            f"enabled={bool(self._telegram_bot_token and self._signal_source_mode == SIGNAL_SOURCE_MODE_TELEGRAM)} "
            f"channel_entry={self._auto_trade_settings.entry_signal_channel_id} "
            f"channel_risk={self._auto_trade_settings.risk_signal_channel_id}"
        )
        _log_trade(
            "Trigger price basis configured: "
            f"source=LAST_PRICE ws_stream=!ticker@arr rest_path={FUTURES_LAST_PRICE_PATH} "
            f"primary_mode=ONE_TICK_LEAD "
            f"fallback_buffer_pct={TRIGGER_BUFFER_RATIO_DEFAULT * 100:.1f}"
        )
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
            values=TP_RATIO_OPTIONS,
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
            self._handle_stop_click,
            on_enter=lambda _e: self._set_button_hover("stop", True),
            on_leave=lambda _e: self._set_button_hover("stop", False),
        )
        self._bind_tag(
            "filter_save",
            self._handle_filter_save,
            on_enter=lambda _e: self._set_button_hover("filter_save", True),
            on_leave=lambda _e: self._set_button_hover("filter_save", False),
            enabled=lambda: self._save_enabled and not self._filter_controls_locked,
        )
        self._bind_tag(
            "filter_reset",
            self._handle_filter_reset,
            on_enter=lambda _e: self._set_button_hover("filter_reset", True),
            on_leave=lambda _e: self._set_button_hover("filter_reset", False),
            enabled=lambda: not self._filter_controls_locked,
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
        changed = self._trade_state != value
        if changed:
            self._trade_state = value
            self._layout()
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        self._refresh_filter_controls_lock_from_runtime(runtime)

    def _confirm_yes_no(self, *, title: str, message: str) -> bool:
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

    def _show_info_message(self, *, title: str, message: str) -> None:
        showinfo = getattr(messagebox, "showinfo", None)
        if not callable(showinfo):
            _log_trade(
                "Info dialog unavailable: "
                f"title={title} reason=showinfo_not_callable"
            )
            return
        try:
            showinfo(title, message, parent=self)
        except tk.TclError as exc:
            _log_trade(f"Info dialog failed: title={title} error={exc!r}")

    def _show_warning_message(self, *, title: str, message: str) -> None:
        showwarning = getattr(messagebox, "showwarning", None)
        if not callable(showwarning):
            _log_trade(
                "Warning dialog unavailable: "
                f"title={title} reason=showwarning_not_callable fallback=showinfo"
            )
            self._show_info_message(title=title, message=message)
            return
        try:
            showwarning(title, message, parent=self)
        except tk.TclError as exc:
            _log_trade(f"Warning dialog failed: title={title} error={exc!r}")
            self._show_info_message(title=title, message=message)

    def _build_start_confirmation_message(self) -> str:
        settings = self._saved_filter_settings or self._default_filter_settings()
        mdd_value = str(settings.get("mdd") or "N%")
        tp_ratio_value = str(settings.get("tp_ratio") or "N%")
        risk_filter_value = str(settings.get("risk_filter") or "보수적/공격적")
        if self._wallet_balance is not None:
            wallet_text = f"{self._wallet_balance:,.2f} USDT"
        else:
            wallet_value = str(self._wallet_value or "N").strip() or "N"
            wallet_unit = str(self._wallet_unit or "").strip()
            wallet_text = f"{wallet_value} {wallet_unit}".strip()
        return (
            f"나의 지갑 잔고 : {wallet_text}\n"
            f"MDD : {mdd_value}\n"
            f"TP-Ratio : {tp_ratio_value}\n"
            f"필터링 성향 : {risk_filter_value}\n\n"
            "자동매매를 실행하시겠습니까?"
        )

    @staticmethod
    def _build_stop_confirmation_message() -> str:
        return (
            "현재 자동매매가 실행중입니다.\n\n"
            "자동매매를 취소하시면 현재 보유중인 포지션이 있을경우 수동으로 청산해야 하며 "
            "이후 수신되는 신호에 대한 자동매매는 중지됩니다. 중지하시겠습니까?"
        )

    def _clear_monitoring_targets_for_stop(
        self,
        *,
        reason_code: str = "STOP_BUTTON_CLEAR_MONITORING",
    ) -> tuple[int, int]:
        with self._auto_trade_runtime_lock:
            pending_count = len(self._orchestrator_runtime.pending_trigger_candidates)
            queue_count = len(self._auto_trade_monitoring_queue)
            self._auto_trade_monitoring_queue.clear()
        self._reset_runtime_after_external_clear(reason_code=reason_code)
        return pending_count, queue_count

    def _execute_auto_trade_stop(
        self,
        *,
        stop_source: str,
        trigger_reason: str,
        loop_label: str,
        clear_reason_code: str,
    ) -> None:
        signal_loop_stopped = self._stop_signal_loop_thread()
        pending_count, queue_count = self._clear_monitoring_targets_for_stop(
            reason_code=clear_reason_code,
        )
        dropped_events = self._clear_signal_event_queue_for_stop(loop_label=loop_label)

        with self._auto_trade_runtime_lock:
            transition = stop_signal_loop_with_logging(
                self._auto_trade_state,
                loop_label=loop_label,
            )
            self._auto_trade_state = transition.current
            self._auto_trade_starting = False
            self._sync_orchestrator_runtime_from_recovery_state_locked()
        self._set_trade_state("stop")
        self._persist_auto_trade_runtime()
        _log_trade(
            "Auto-trade stop executed: "
            f"source={stop_source} trigger={trigger_reason} reason={transition.reason_code} "
            f"recovery_locked={transition.current.recovery_locked} "
            f"signal_loop_paused={transition.current.signal_loop_paused} "
            f"signal_loop_stopped={signal_loop_stopped} "
            f"cleared_pending_monitoring={pending_count} cleared_monitor_queue={queue_count} "
            f"dropped_signal_events={dropped_events}"
        )

    def _is_wallet_over_auto_stop_limit(self, balance: float) -> bool:
        return float(balance) >= float(self._auto_trade_wallet_stop_threshold_usdt)

    def _request_wallet_limit_auto_stop_if_needed(
        self,
        *,
        balance: Optional[float],
        positions: Optional[list[dict]],
        source: str,
    ) -> None:
        if balance is None or positions is None:
            return
        if not self._is_wallet_over_auto_stop_limit(float(balance)):
            return
        if positions:
            return
        with self._auto_trade_runtime_lock:
            running = bool(self._auto_trade_state.signal_loop_running)
        if not running:
            return
        _log_trade(
            "Wallet limit auto-stop triggered: "
            f"balance={float(balance):.2f} threshold={self._auto_trade_wallet_stop_threshold_usdt:.2f} "
            f"position_count={len(positions)} source={source}"
        )
        self._execute_auto_trade_stop(
            stop_source=source,
            trigger_reason="WALLET_LIMIT_EXCEEDED",
            loop_label=f"{source}-wallet-limit-stop",
            clear_reason_code="WALLET_LIMIT_AUTO_STOP_CLEAR_MONITORING",
        )

    def _handle_start_click(self, _event=None) -> None:
        with self._auto_trade_runtime_lock:
            already_running = bool(self._auto_trade_starting or self._auto_trade_state.signal_loop_running)
        if self._trade_state == "start" or already_running:
            _log_trade(
                "Auto-trade start ignored: "
                f"reason=already_running trade_state={self._trade_state} "
                f"signal_loop_running={self._auto_trade_state.signal_loop_running} "
                f"auto_trade_starting={self._auto_trade_starting}"
            )
            self._show_info_message(title="자동매매 안내", message="이미 실행중입니다.")
            return
        wallet_balance = self._wallet_balance
        if wallet_balance is not None and self._is_wallet_over_auto_stop_limit(float(wallet_balance)):
            _log_trade(
                "Auto-trade start blocked: "
                f"reason=wallet_limit_warning balance={float(wallet_balance):.2f} "
                f"threshold={self._auto_trade_wallet_stop_threshold_usdt:.2f}"
            )
            self._show_warning_message(
                title="자동매매 경고",
                message=AUTO_TRADE_WALLET_START_WARNING_MESSAGE,
            )
            return
        message = self._build_start_confirmation_message()
        _log_trade(
            "Auto-trade start confirmation opened: "
            f"trade_state={self._trade_state} wallet={self._wallet_value} {self._wallet_unit}"
        )
        confirmed = self._confirm_yes_no(
            title="자동매매 시작 확인",
            message=message,
        )
        if not confirmed:
            _log_trade("Auto-trade start canceled by user.")
            return
        _log_trade("Auto-trade start confirmed by user.")
        self._set_trade_state("start")
        self._request_auto_trade_startup()

    def _handle_stop_click(self, _event=None) -> None:
        with self._auto_trade_runtime_lock:
            running = bool(self._auto_trade_starting or self._auto_trade_state.signal_loop_running)
        if self._trade_state != "start" and not running:
            _log_trade(
                "Auto-trade stop ignored: "
                "reason=already_stopped trade_state=stop signal_loop_running=False"
            )
            self._show_info_message(
                title="자동매매 안내",
                message="자동매매가 현재 중지상태 입니다.",
            )
            return

        _log_trade(
            "Auto-trade stop confirmation opened: "
            f"trade_state={self._trade_state} running={running}"
        )
        confirmed = self._confirm_yes_no(
            title="자동매매 중지 확인",
            message=self._build_stop_confirmation_message(),
        )
        if not confirmed:
            _log_trade("Auto-trade stop canceled by user.")
            return
        self._execute_auto_trade_stop(
            stop_source="ui-stop",
            trigger_reason="USER_REQUEST",
            loop_label="ui-stop",
            clear_reason_code="STOP_BUTTON_CLEAR_MONITORING",
        )

    def _request_auto_trade_startup(self) -> None:
        with self._auto_trade_runtime_lock:
            if self._auto_trade_starting:
                _log_trade("Auto-trade start ignored: recovery startup is already in progress.")
                return
            self._auto_trade_starting = True
        _log_trade("Auto-trade start requested: running recovery startup sequence.")
        thread = threading.Thread(target=self._run_auto_trade_startup, daemon=True)
        thread.start()

    def _run_auto_trade_startup(self) -> None:
        with self._auto_trade_runtime_lock:
            state = self._auto_trade_state
            queue_count = len(self._auto_trade_monitoring_queue)

        result = run_recovery_startup_with_logging(
            state,
            load_persisted_state=self._load_recovery_persisted_state,
            fetch_exchange_snapshot=self._fetch_recovery_exchange_snapshot,
            check_price_source_ready=self._check_recovery_price_source_ready,
            execute_exit_reconciliation=self._execute_recovery_exit_reconciliation,
            cleared_monitoring_queue_count=queue_count,
            loop_label="ui-start",
        )
        synced_offset: Optional[int] = None
        if result.success:
            synced_offset = self._sync_signal_source_offset_for_fresh_start()

        def apply_result() -> None:
            offset_sync_applied = False
            previous_offset = 0
            updated_offset = 0
            with self._auto_trade_runtime_lock:
                self._auto_trade_state = result.state
                self._auto_trade_starting = False
                self._auto_trade_monitoring_queue.clear()
                if result.success and synced_offset is not None:
                    if self._signal_source_mode == SIGNAL_SOURCE_MODE_RELAY:
                        previous_offset = int(self._signal_relay_update_offset)
                        updated_offset = max(previous_offset, int(synced_offset))
                        self._signal_relay_update_offset = updated_offset
                    else:
                        previous_offset = int(self._telegram_update_offset)
                        updated_offset = max(previous_offset, int(synced_offset))
                        self._telegram_update_offset = updated_offset
                    offset_sync_applied = True
                self._sync_orchestrator_runtime_from_recovery_state_locked()
            if offset_sync_applied:
                _log_trade(
                    "Signal source offset updated for fresh start: "
                    f"source={self._signal_source_mode} previous_offset={previous_offset} "
                    f"updated_offset={updated_offset}"
                )
            self._set_trade_state("start" if result.success else "stop")
            if result.success:
                self._clear_signal_event_queue_for_fresh_start(loop_label="ui-start")
                self._start_signal_loop_thread()
            else:
                self._stop_signal_loop_thread()
            self._persist_auto_trade_runtime()
            _log_trade(
                "Auto-trade recovery finished: "
                f"success={result.success} reason={result.reason_code} "
                f"snapshot={result.snapshot_reason_code} "
                f"reconcile_plan={result.reconcile_plan_reason_code} "
                f"reconcile_exec={result.reconcile_execution_reason_code} "
                f"failure={result.failure_reason}"
            )

        self.after(0, apply_result)

    def _load_recovery_persisted_state(self) -> PersistentRecoveryState:
        self._hydrate_auto_trade_state_from_disk()
        with self._auto_trade_runtime_lock:
            return PersistentRecoveryState(
                last_message_ids=dict(self._auto_trade_last_message_ids),
                cooldown_by_symbol=dict(self._auto_trade_cooldown_by_symbol),
                received_at_by_symbol=dict(self._auto_trade_received_at_by_symbol),
                message_id_by_symbol=dict(self._auto_trade_message_id_by_symbol),
            )

    def _fetch_recovery_exchange_snapshot(self) -> ExchangeSnapshot:
        if not self._api_key or not self._secret_key:
            return ExchangeSnapshot(
                ok=False,
                reason_code="SNAPSHOT_AUTH_MISSING",
                failure_reason="api_key_or_secret_missing",
                open_orders=[],
                positions=[],
                open_order_count=0,
                has_any_position=False,
                position_mode="UNKNOWN",
            )

        open_orders, _ = self._fetch_open_order_rows_from_endpoints(
            loop_label="recovery-snapshot-open-orders",
        )
        if open_orders is None:
            return ExchangeSnapshot(
                ok=False,
                reason_code="SNAPSHOT_OPEN_ORDERS_FETCH_FAILED",
                failure_reason="open_orders_not_list",
                open_orders=[],
                positions=[],
                open_order_count=0,
                has_any_position=False,
                position_mode="UNKNOWN",
            )

        raw_positions = self._binance_signed_get("https://fapi.binance.com", POSITION_RISK_PATH)
        if not isinstance(raw_positions, list):
            return ExchangeSnapshot(
                ok=False,
                reason_code="SNAPSHOT_POSITIONS_FETCH_FAILED",
                failure_reason="positions_not_list",
                open_orders=open_orders,
                positions=[],
                open_order_count=len(open_orders),
                has_any_position=False,
                position_mode="UNKNOWN",
            )
        positions = [item for item in raw_positions if isinstance(item, dict)]
        effective_positions = [item for item in positions if self._is_nonzero_position_row(item)]
        has_any_position = bool(effective_positions)
        if len(effective_positions) != len(positions):
            _log_trade(
                "Recovery snapshot dust filtered: "
                f"raw_positions={len(positions)} effective_positions={len(effective_positions)}"
            )

        raw_position_mode = self._binance_signed_get("https://fapi.binance.com", POSITION_MODE_PATH)
        position_mode = self._parse_position_mode(raw_position_mode)
        if position_mode == "UNKNOWN":
            return ExchangeSnapshot(
                ok=False,
                reason_code="SNAPSHOT_POSITION_MODE_FETCH_FAILED",
                failure_reason="position_mode_unknown",
                open_orders=open_orders,
                positions=effective_positions,
                open_order_count=len(open_orders),
                has_any_position=has_any_position,
                position_mode="UNKNOWN",
            )

        return ExchangeSnapshot(
            ok=True,
            reason_code="SNAPSHOT_READY",
            failure_reason="-",
            open_orders=open_orders,
            positions=effective_positions,
            open_order_count=len(open_orders),
            has_any_position=has_any_position,
            position_mode=position_mode,
        )

    def _is_nonzero_position_row(self, position: Mapping[str, object]) -> bool:
        try:
            amount = float(position.get("positionAmt", 0.0))
        except (TypeError, ValueError):
            return False
        if abs(amount) <= 1e-12:
            return False
        symbol = str(position.get("symbol") or "").strip().upper()
        if not symbol:
            return True
        rule = self._get_symbol_filter_rule(symbol)
        if rule is None:
            return True
        normalized_qty = floor_quantity_by_step_size(abs(amount), rule.step_size)
        if normalized_qty is None:
            return False
        return float(normalized_qty) >= float(rule.min_qty) - 1e-12

    @staticmethod
    def _parse_position_mode(payload: object) -> str:
        if not isinstance(payload, dict):
            return "UNKNOWN"
        raw = payload.get("dualSidePosition")
        if isinstance(raw, bool):
            return "HEDGE" if raw else "ONE_WAY"
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in ("true", "false"):
                return "HEDGE" if lowered == "true" else "ONE_WAY"
        return "UNKNOWN"

    @staticmethod
    def _parse_percent_text(value: object, default_ratio: float) -> float:
        if not isinstance(value, str):
            return float(default_ratio)
        text = value.strip().replace("%", "")
        if not text:
            return float(default_ratio)
        try:
            parsed = float(text) / 100.0
        except (TypeError, ValueError):
            return float(default_ratio)
        if parsed <= 0:
            return float(default_ratio)
        return float(parsed)

    @staticmethod
    def _format_order_price(value: float) -> str:
        text = f"{value:.8f}"
        return text.rstrip("0").rstrip(".")

    @staticmethod
    def _allocate_split_exit_quantities(
        total_quantity: float,
        *,
        split_count: int,
        step_size: float,
        min_qty: float,
    ) -> list[float]:
        qty = float(total_quantity)
        step = float(step_size)
        minimum = float(min_qty)
        if qty <= 0.0 or step <= 0.0 or minimum <= 0.0 or split_count <= 0:
            return []

        total_units = int(math.floor((qty / step) + 1e-12))
        if total_units <= 0:
            return []
        min_units = max(1, int(math.ceil((minimum / step) - 1e-12)))
        max_orders_by_min = total_units // min_units
        if max_orders_by_min <= 0:
            return []

        effective_count = min(int(split_count), int(max_orders_by_min))
        selected_units: list[int] = []
        for candidate_count in range(effective_count, 0, -1):
            base_units = total_units // candidate_count
            remainder = total_units % candidate_count
            candidate_units = [
                int(base_units + (1 if idx < remainder else 0))
                for idx in range(candidate_count)
            ]
            if candidate_units and min(candidate_units) >= min_units:
                selected_units = candidate_units
                break
        if not selected_units:
            return []

        quantities: list[float] = []
        for units in selected_units:
            adjusted = floor_quantity_by_step_size(float(units) * step, step)
            if adjusted is None or adjusted < minimum - 1e-12:
                continue
            quantities.append(float(adjusted))
        return quantities

    @staticmethod
    def _dedupe_prices_with_tolerance(prices: list[float], *, tolerance: float) -> list[float]:
        unique: list[float] = []
        margin = max(float(tolerance), 1e-12)
        for value in prices:
            candidate = float(value)
            if any(abs(candidate - current) <= margin for current in unique):
                continue
            unique.append(candidate)
        return unique

    @staticmethod
    def _compute_one_tick_lead_trigger_price(
        *,
        target_price: float,
        is_short: bool,
        tick_size: float,
    ) -> Optional[float]:
        target = float(target_price)
        tick = float(tick_size)
        if target <= 0.0 or tick <= 0.0:
            return None
        # Use one-tick lead instead of a fixed 0.5% buffer.
        trigger_raw = target + tick if is_short else target - tick
        if trigger_raw <= 0.0:
            return None
        rounded = round_price_by_tick_size(trigger_raw, tick)
        if rounded is None or rounded <= 0.0:
            return None
        return float(rounded)

    def _build_split_tp_plan_for_symbol(
        self,
        *,
        symbol: str,
        position_amt: float,
        avg_entry: float,
        tick_size: float,
        step_size: float,
        min_qty: float,
        phase: str,
        tp_ratio: float,
        loop_label: str,
    ) -> list[dict[str, float]]:
        target = str(symbol or "").strip().upper()
        state = str(phase or "").strip().upper()
        if not target or state not in ("PHASE1", "PHASE2"):
            return []
        if abs(float(position_amt)) <= 1e-12 or float(avg_entry) <= 0.0:
            return []
        if float(tick_size) <= 0.0 or float(step_size) <= 0.0 or float(min_qty) <= 0.0:
            return []

        is_short = float(position_amt) < 0.0
        desired_targets: list[float] = []
        if state == "PHASE1":
            for idx in range(TP_SPLIT_ORDER_COUNT):
                ratio = float(tp_ratio) + (float(TP_SPLIT_STEP_RATIO) * float(idx))
                if ratio <= 0.0:
                    continue
                raw_target = float(avg_entry) * (1.0 - ratio if is_short else 1.0 + ratio)
                rounded = round_price_by_tick_size(raw_target, float(tick_size))
                if rounded is not None and rounded > 0.0:
                    desired_targets.append(float(rounded))
        else:
            for idx in range(TP_SPLIT_ORDER_COUNT):
                pnl_ratio = float(PHASE2_TP_START_RATIO) + (float(PHASE2_TP_STEP_RATIO) * float(idx))
                raw_target = float(avg_entry) * (1.0 - pnl_ratio if is_short else 1.0 + pnl_ratio)
                rounded = round_price_by_tick_size(raw_target, float(tick_size))
                if rounded is not None and rounded > 0.0:
                    desired_targets.append(float(rounded))

        desired_targets = self._dedupe_prices_with_tolerance(
            desired_targets,
            tolerance=max(float(tick_size) * 0.25, 1e-12),
        )
        if not desired_targets:
            _log_trade(
                "Split TP plan unavailable: "
                f"symbol={target} state={state} reason=no_rounded_targets loop={loop_label}"
            )
            return []

        quantities = self._allocate_split_exit_quantities(
            abs(float(position_amt)),
            split_count=min(TP_SPLIT_ORDER_COUNT, len(desired_targets)),
            step_size=float(step_size),
            min_qty=float(min_qty),
        )
        if not quantities:
            _log_trade(
                "Split TP plan unavailable: "
                f"symbol={target} state={state} reason=quantity_allocation_failed "
                f"position_qty={abs(float(position_amt))} step_size={step_size} min_qty={min_qty} loop={loop_label}"
            )
            return []

        effective_count = min(len(desired_targets), len(quantities))
        if effective_count <= 0:
            return []
        if effective_count < TP_SPLIT_ORDER_COUNT:
            _log_trade(
                "Split TP plan reduced order count: "
                f"symbol={target} state={state} requested={TP_SPLIT_ORDER_COUNT} "
                f"effective={effective_count} loop={loop_label}"
            )

        plan: list[dict[str, float]] = []
        for idx in range(effective_count):
            target_price = float(desired_targets[idx])
            trigger_price = self._compute_one_tick_lead_trigger_price(
                target_price=float(target_price),
                is_short=is_short,
                tick_size=float(tick_size),
            )
            if trigger_price is None or trigger_price <= 0.0:
                continue
            quantity = float(quantities[idx])
            if quantity <= 0.0:
                continue
            plan.append(
                {
                    "target_price": float(target_price),
                    "trigger_price": float(trigger_price),
                    "quantity": float(quantity),
                }
            )

        _log_trade(
            "Split TP plan built: "
            f"symbol={target} state={state} order_count={len(plan)} "
            f"target_first={plan[0]['target_price'] if plan else '-'} "
            f"target_last={plan[-1]['target_price'] if plan else '-'} "
            f"trigger_mode=ONE_TICK_LEAD "
            f"qty_total={sum(item['quantity'] for item in plan):.12f} loop={loop_label}"
        )
        return plan

    @staticmethod
    def _build_split_tp_plan_signature(*, phase: str, plan: list[dict[str, float]]) -> str:
        state = str(phase or "").strip().upper()
        if not plan:
            return f"{state}|empty"
        fragments = [
            f"{item['target_price']:.12f}:{item['trigger_price']:.12f}:{item['quantity']:.12f}"
            for item in plan
        ]
        return f"{state}|{'|'.join(fragments)}"

    @staticmethod
    def _empty_exit_rebuild_templates() -> dict[str, bool]:
        return {
            "tp_limit": False,
            "breakeven_limit": False,
            "breakeven_stop": False,
            "mdd_stop": False,
        }

    def _normalize_exit_rebuild_templates(
        self,
        templates: Optional[Mapping[str, object]],
    ) -> dict[str, bool]:
        normalized = self._empty_exit_rebuild_templates()
        if isinstance(templates, Mapping):
            for key in normalized:
                normalized[key] = bool(templates.get(key))
        return normalized

    def _collect_active_exit_rebuild_templates(
        self,
        *,
        symbol: str,
        position: Mapping[str, object],
        open_orders: list[dict],
        loop_label: str,
    ) -> dict[str, bool]:
        target = str(symbol or "").strip().upper()
        templates = self._empty_exit_rebuild_templates()
        if not target:
            return templates

        position_amt = self._safe_float(position.get("positionAmt"))
        entry_price = self._safe_float(position.get("entryPrice"))
        if (
            position_amt is None
            or entry_price is None
            or abs(float(position_amt)) <= 1e-12
            or float(entry_price) <= 0.0
        ):
            _log_trade(
                "Exit rebuild template scan skipped: "
                f"symbol={target} reason=invalid_position_snapshot loop={loop_label}"
            )
            return templates

        is_short = float(position_amt) < 0.0
        close_side = "BUY" if is_short else "SELL"
        rule = self._get_symbol_filter_rule(target)
        if rule is not None:
            tolerance = max(float(rule.tick_size) * 0.55, 1e-12)
        else:
            tolerance = max(abs(float(entry_price)) * 1e-6, 1e-12)
        _, exit_orders = self._classify_orders_for_symbol(target, open_orders)
        for row in exit_orders:
            side = str(row.get("side") or "").strip().upper()
            if side and side != close_side:
                continue
            order_type = str(row.get("type") or "").strip().upper()
            if order_type == "TAKE_PROFIT":
                price = self._safe_float(row.get("price"))
                if price is not None and float(price) > 0.0 and abs(float(price) - float(entry_price)) <= tolerance * 2:
                    templates["breakeven_limit"] = True
                else:
                    templates["tp_limit"] = True
                continue
            if order_type == "TAKE_PROFIT_MARKET":
                templates["tp_limit"] = True
                continue
            if order_type == "LIMIT":
                price = self._safe_float(row.get("price"))
                if price is None or float(price) <= 0.0:
                    continue
                if abs(float(price) - float(entry_price)) <= tolerance * 2:
                    templates["breakeven_limit"] = True
                else:
                    templates["tp_limit"] = True
                continue
            if order_type not in ("STOP_MARKET", "STOP"):
                continue
            stop_price, stop_source = self._select_effective_stop_price(row)
            if stop_price is None:
                continue
            if stop_source and stop_source != "stopPrice":
                order_id = self._safe_int(row.get("orderId"))
                _log_trade(
                    "Exit template stop price fallback used: "
                    f"symbol={target} order_id={order_id} source={stop_source} "
                    f"stop_price={stop_price} loop={loop_label}"
                )
            if abs(float(stop_price) - float(entry_price)) <= tolerance * 2:
                templates["breakeven_stop"] = True
            else:
                templates["mdd_stop"] = True

        _log_trade(
            "Exit rebuild templates collected: "
            f"symbol={target} tp_limit={templates['tp_limit']} "
            f"breakeven_limit={templates['breakeven_limit']} "
            f"breakeven_stop={templates['breakeven_stop']} "
            f"mdd_stop={templates['mdd_stop']} loop={loop_label}"
        )
        return templates

    def _apply_phase_policy_to_exit_rebuild_templates(
        self,
        *,
        symbol: str,
        runtime_symbol_state: str,
        templates: Optional[Mapping[str, object]],
        loop_label: str,
    ) -> dict[str, bool]:
        target = str(symbol or "").strip().upper()
        state = str(runtime_symbol_state or "").strip().upper()
        normalized = self._normalize_exit_rebuild_templates(templates)
        if state == "PHASE1":
            normalized["breakeven_limit"] = False
            normalized["mdd_stop"] = False
            if target in self._phase1_tp_filled_symbols:
                normalized["breakeven_stop"] = True
        elif state == "PHASE2":
            if normalized["breakeven_limit"]:
                normalized["tp_limit"] = True
                normalized["breakeven_limit"] = False
            normalized["breakeven_stop"] = False
            if target not in self._second_entry_fully_filled_symbols:
                normalized["mdd_stop"] = False

        _log_trade(
            "Exit rebuild templates after phase policy: "
            f"symbol={target} state={state or '-'} tp_limit={normalized['tp_limit']} "
            f"breakeven_limit={normalized['breakeven_limit']} "
            f"breakeven_stop={normalized['breakeven_stop']} "
            f"mdd_stop={normalized['mdd_stop']} loop={loop_label}"
        )
        return normalized

    def _submit_recovery_exit_orders_for_symbol(
        self,
        *,
        symbol: str,
        position: Mapping[str, object],
        runtime_symbol_state: str,
        active_exit_templates: Optional[Mapping[str, object]],
        loop_label: str,
    ) -> tuple[bool, str]:
        target = str(symbol or "").strip().upper()
        if not target:
            return False, "symbol_empty"
        position_amt = self._safe_float(position.get("positionAmt"))
        entry_price = self._safe_float(position.get("entryPrice"))
        if (
            position_amt is None
            or entry_price is None
            or abs(float(position_amt)) <= 1e-12
            or float(entry_price) <= 0.0
        ):
            return False, "position_amount_or_entry_invalid"

        templates = self._apply_phase_policy_to_exit_rebuild_templates(
            symbol=target,
            runtime_symbol_state=runtime_symbol_state,
            templates=active_exit_templates,
            loop_label=f"{loop_label}-phase-policy",
        )
        if not any(templates.values()):
            _log_trade(
                "Exit rebuild skipped: "
                f"symbol={target} reason=no_active_exit_templates state={runtime_symbol_state} loop={loop_label}"
            )
            return True, "NO_ACTIVE_EXIT_TEMPLATES"

        position_row = dict(position)
        position_row["symbol"] = target
        positions = [position_row]

        if templates["breakeven_stop"]:
            success = self._submit_breakeven_stop_market(
                symbol=target,
                positions=positions,
                loop_label=f"{loop_label}-breakeven-stop",
            )
            _log_trade(
                "Exit rebuild order result: "
                f"symbol={target} type=BREAKEVEN_STOP_MARKET success={success} loop={loop_label}"
            )
            if not success:
                return False, "breakeven_stop_market_registration_failed"

        if templates["mdd_stop"]:
            success = self._submit_mdd_stop_market(
                symbol=target,
                positions=positions,
                loop_label=f"{loop_label}-mdd-stop",
            )
            _log_trade(
                "Exit rebuild order result: "
                f"symbol={target} type=MDD_STOP_MARKET success={success} loop={loop_label}"
            )
            if not success:
                return False, "mdd_stop_market_registration_failed"

        if templates["tp_limit"]:
            state = str(runtime_symbol_state or "").strip().upper()
            filter_rule = self._get_symbol_filter_rule(target)
            if filter_rule is None:
                return False, "tp_split_filter_rule_missing"
            split_plan = self._build_split_tp_plan_for_symbol(
                symbol=target,
                position_amt=float(position_amt),
                avg_entry=float(entry_price),
                tick_size=float(filter_rule.tick_size),
                step_size=float(filter_rule.step_size),
                min_qty=float(filter_rule.min_qty),
                phase=state,
                tp_ratio=self._parse_percent_text(
                    (self._saved_filter_settings or self._default_filter_settings()).get("tp_ratio"),
                    0.05,
                ),
                loop_label=f"{loop_label}-split-plan",
            )
            attempted, succeeded = self._submit_split_tp_triggers(
                symbol=target,
                positions=positions,
                split_plan=split_plan,
                loop_label=f"{loop_label}-tp-trigger-split",
            )
            success = bool(attempted > 0 and attempted == succeeded)
            _log_trade(
                "Exit rebuild order result: "
                f"symbol={target} type=TP_TRIGGER_SPLIT success={success} "
                f"attempted={attempted} succeeded={succeeded} state={state or '-'} loop={loop_label}"
            )
            if not success:
                return False, "tp_trigger_split_registration_failed"

        if templates["breakeven_limit"]:
            if str(runtime_symbol_state or "").strip().upper() == "PHASE2":
                _log_trade(
                    "Exit rebuild breakeven_limit converted to split TP in phase2: "
                    f"symbol={target} loop={loop_label}"
                )
            else:
                success = self._submit_breakeven_limit_once(
                    symbol=target,
                    positions=positions,
                    loop_label=f"{loop_label}-breakeven-limit",
                )
                _log_trade(
                    "Exit rebuild order result: "
                    f"symbol={target} type=BREAKEVEN_LIMIT success={success} loop={loop_label}"
                )
                if not success:
                    return False, "breakeven_limit_registration_failed"

        return True, "-"

    def _cancel_all_open_orders_for_symbol(
        self,
        *,
        symbol: str,
        loop_label: str,
    ) -> tuple[bool, str]:
        target = str(symbol or "").strip().upper()
        if not target:
            return False, "symbol_empty"
        params = {"symbol": target}
        outcomes: list[tuple[str, object]] = []
        for path in (FUTURES_CANCEL_ALL_OPEN_ORDERS_PATH, FUTURES_CANCEL_ALL_OPEN_ALGO_ORDERS_PATH):
            response = self._binance_signed_delete("https://fapi.binance.com", path, dict(params))
            outcomes.append((path, response))
            if response is None:
                _log_trade(
                    "Recovery cancel-all orders failed: "
                    f"symbol={target} path={path} reason=network loop={loop_label}"
                )
                return False, f"path={path} network_error"
            if isinstance(response, dict) and isinstance(response.get("code"), int) and int(response["code"]) < 0:
                if self._is_order_not_found_payload(response):
                    _log_trade(
                        "Recovery cancel-all orders skipped missing orders: "
                        f"symbol={target} path={path} response={response!r} loop={loop_label}"
                    )
                    continue
                _log_trade(
                    "Recovery cancel-all orders rejected: "
                    f"symbol={target} path={path} response={response!r} loop={loop_label}"
                )
                return False, f"path={path} code={response.get('code')}"
        _log_trade(
            "Recovery cancel-all orders done: "
            f"symbol={target} paths={','.join(path for path, _ in outcomes)} loop={loop_label}"
        )
        return True, "-"

    def _execute_recovery_exit_reconciliation(
        self,
        plan: ExitReconcilePlan,
    ) -> ExitReconcileExecutionResult:
        canceled_symbols: list[str] = []
        pre_reconcile_open_orders = self._fetch_open_orders() or []
        cancel_required = plan.action_code in ("CANCEL_UNNEEDED_ORDERS", "CANCEL_AND_REQUIRE_EXIT_REGISTRATION")
        if cancel_required:
            for symbol in plan.cancel_symbols:
                canceled, failure_reason = self._cancel_all_open_orders_for_symbol(
                    symbol=symbol,
                    loop_label="recovery-cancel-open-orders",
                )
                if not canceled:
                    return ExitReconcileExecutionResult(
                        success=False,
                        reason_code="RECOVERY_CANCEL_OPEN_ORDERS_FAILED",
                        failure_reason=f"symbol={symbol} {failure_reason}",
                        canceled_symbols=canceled_symbols,
                    )
                canceled_symbols.append(symbol)

        if plan.require_exit_registration:
            positions = self._fetch_open_positions() or []
            positions_by_symbol = {
                str(item.get("symbol", "")).upper(): item
                for item in positions
                if isinstance(item, dict)
            }
            with self._auto_trade_runtime_lock:
                runtime_symbol_state = self._orchestrator_runtime.symbol_state

            for symbol in plan.register_symbols:
                position = positions_by_symbol.get(symbol)
                if position is None:
                    return ExitReconcileExecutionResult(
                        success=False,
                        reason_code="RECOVERY_EXIT_REGISTRATION_POSITION_MISSING",
                        failure_reason=f"symbol={symbol}",
                        canceled_symbols=canceled_symbols,
                    )
                active_templates = self._collect_active_exit_rebuild_templates(
                    symbol=symbol,
                    position=position,
                    open_orders=pre_reconcile_open_orders,
                    loop_label="recovery-exit-template-scan",
                )
                ok, reason = self._submit_recovery_exit_orders_for_symbol(
                    symbol=symbol,
                    position=position,
                    runtime_symbol_state=runtime_symbol_state,
                    active_exit_templates=active_templates,
                    loop_label="recovery-exit-registration",
                )
                _log_trade(
                    "Recovery exit registration: "
                    f"symbol={symbol} state={runtime_symbol_state} "
                    f"tp_limit={active_templates['tp_limit']} "
                    f"breakeven_limit={active_templates['breakeven_limit']} "
                    f"breakeven_stop={active_templates['breakeven_stop']} "
                    f"mdd_stop={active_templates['mdd_stop']} "
                    f"result={'ok' if ok else 'failed'} reason={reason}"
                )
                if not ok:
                    return ExitReconcileExecutionResult(
                        success=False,
                        reason_code="RECOVERY_EXIT_REGISTRATION_FAILED",
                        failure_reason=f"symbol={symbol} reason={reason}",
                        canceled_symbols=canceled_symbols,
                    )

        return ExitReconcileExecutionResult(
            success=True,
            reason_code="RECOVERY_RECONCILE_DONE",
            failure_reason="-",
            canceled_symbols=canceled_symbols,
        )

    def _check_recovery_price_source_ready(self) -> bool:
        payload = self._binance_public_get(
            "https://fapi.binance.com",
            FUTURES_LAST_PRICE_PATH,
            {"symbol": "BTCUSDT"},
        )
        if not isinstance(payload, dict):
            return False
        mark_price = self._safe_float(
            payload.get("price")
            or payload.get("lastPrice")
            or payload.get("markPrice")
        )
        return mark_price is not None and mark_price > 0.0

    @staticmethod
    def _read_env_int_or_default(
        key: str,
        default: int,
        *,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
        log_scope: str = "Signal relay config",
    ) -> int:
        raw = os.environ.get(key)
        if raw is None:
            _log_trade(f"{log_scope} default used: key={key} value={default} reason=missing")
            return default
        try:
            value = int(raw)
        except ValueError:
            _log_trade(f"{log_scope} default used: key={key} value={default} reason=invalid_int raw={raw!r}")
            return default
        if minimum is not None and value < minimum:
            _log_trade(
                f"{log_scope} default used: "
                f"key={key} value={default} reason=below_minimum raw={value} minimum={minimum}"
            )
            return default
        if maximum is not None and value > maximum:
            _log_trade(
                f"{log_scope} default used: "
                f"key={key} value={default} reason=above_maximum raw={value} maximum={maximum}"
            )
            return default
        _log_trade(f"{log_scope} loaded: key={key} value={value}")
        return value

    @staticmethod
    def _read_env_float_or_default(
        key: str,
        default: float,
        *,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None,
        log_scope: str = "Config",
    ) -> float:
        raw = os.environ.get(key)
        if raw is None:
            _log_trade(f"{log_scope} default used: key={key} value={default} reason=missing")
            return default
        try:
            value = float(raw)
        except ValueError:
            _log_trade(f"{log_scope} default used: key={key} value={default} reason=invalid_float raw={raw!r}")
            return default
        if minimum is not None and value < minimum:
            _log_trade(
                f"{log_scope} default used: "
                f"key={key} value={default} reason=below_minimum raw={value} minimum={minimum}"
            )
            return default
        if maximum is not None and value > maximum:
            _log_trade(
                f"{log_scope} default used: "
                f"key={key} value={default} reason=above_maximum raw={value} maximum={maximum}"
            )
            return default
        _log_trade(f"{log_scope} loaded: key={key} value={value}")
        return value

    @staticmethod
    def _normalize_relay_base_url(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.rstrip("/")

    def _resolve_signal_relay_base_url(self) -> str:
        from_env = self._normalize_relay_base_url(os.environ.get(SIGNAL_RELAY_BASE_URL_ENV, ""))
        if from_env:
            _log_trade(
                "Signal relay base URL loaded: "
                f"source=env key={SIGNAL_RELAY_BASE_URL_ENV} value={from_env}"
            )
            return from_env

        from_config = self._normalize_relay_base_url(getattr(config, "SIGNAL_RELAY_BASE_URL_DEFAULT", ""))
        if from_config:
            _log_trade(
                "Signal relay base URL loaded: "
                "source=config key=SIGNAL_RELAY_BASE_URL_DEFAULT "
                f"value={from_config}"
            )
            return from_config

        _log_trade(
            "Signal relay base URL missing: "
            f"env_key={SIGNAL_RELAY_BASE_URL_ENV} config_key=SIGNAL_RELAY_BASE_URL_DEFAULT"
        )
        return ""

    def _resolve_signal_relay_token(self) -> str:
        from_env = str(os.environ.get(SIGNAL_RELAY_TOKEN_ENV, "") or "").strip()
        if from_env:
            _log_trade(
                "Signal relay token loaded: "
                f"source=env key={SIGNAL_RELAY_TOKEN_ENV} token_set={bool(from_env)}"
            )
            return from_env

        from_config = str(getattr(config, "SIGNAL_RELAY_TOKEN_DEFAULT", "") or "").strip()
        if from_config:
            _log_trade(
                "Signal relay token loaded: "
                "source=config key=SIGNAL_RELAY_TOKEN_DEFAULT token_set=True"
            )
            return from_config

        _log_trade(
            "Signal relay token missing: "
            f"env_key={SIGNAL_RELAY_TOKEN_ENV} config_key=SIGNAL_RELAY_TOKEN_DEFAULT"
        )
        return ""

    def _resolve_signal_source_mode(self) -> str:
        requested = str(os.environ.get(SIGNAL_SOURCE_MODE_ENV, "") or "").strip().lower()
        if requested in (SIGNAL_SOURCE_MODE_RELAY, SIGNAL_SOURCE_MODE_TELEGRAM):
            _log_trade(f"Signal source mode loaded from env: mode={requested}")
            return requested

        from_config = str(getattr(config, "SIGNAL_SOURCE_MODE_DEFAULT", "") or "").strip().lower()
        if from_config in (SIGNAL_SOURCE_MODE_RELAY, SIGNAL_SOURCE_MODE_TELEGRAM):
            if from_config == SIGNAL_SOURCE_MODE_RELAY and not self._signal_relay_base_url:
                _log_trade(
                    "Signal source mode warning: "
                    f"requested={SIGNAL_SOURCE_MODE_RELAY} source=config "
                    "reason=relay_base_url_missing"
                )
            _log_trade(f"Signal source mode loaded from config: mode={from_config}")
            return from_config

        if self._signal_relay_base_url:
            _log_trade(
                "Signal source mode selected: "
                f"mode={SIGNAL_SOURCE_MODE_RELAY} reason=relay_base_url_present"
            )
            return SIGNAL_SOURCE_MODE_RELAY
        _log_trade(
            "Signal source mode selected: "
            f"mode={SIGNAL_SOURCE_MODE_TELEGRAM} reason=default_fallback"
        )
        return SIGNAL_SOURCE_MODE_TELEGRAM

    def _resolve_signal_relay_client_id(self) -> str:
        from_env = str(os.environ.get(SIGNAL_RELAY_CLIENT_ID_ENV, "") or "").strip()
        if from_env:
            return from_env
        api_key = str(self._api_key or "").strip()
        if api_key:
            return f"api-{hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:12]}"
        return "anonymous-client"

    def _build_signal_relay_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        token = str(self._signal_relay_token or "").strip()
        if token:
            headers["X-LTS-Relay-Token"] = token
        return headers

    def _sync_signal_source_offset_for_fresh_start(self) -> Optional[int]:
        if self._signal_source_mode == SIGNAL_SOURCE_MODE_RELAY:
            return self._sync_signal_relay_offset_for_fresh_start()
        return self._sync_telegram_update_offset_for_fresh_start()

    def _sync_signal_relay_offset_for_fresh_start(self) -> Optional[int]:
        relay_base_url = self._normalize_relay_base_url(self._signal_relay_base_url)
        baseline_offset = max(0, int(self._signal_relay_update_offset))
        if not relay_base_url:
            _log_trade("Signal relay start-sync skipped: relay_base_url_missing.")
            return baseline_offset

        endpoint = f"{relay_base_url}/api/v1/offset/latest"
        _log_trade(
            "Signal relay start-sync begin: "
            f"baseline_offset={baseline_offset} endpoint={endpoint}"
        )
        try:
            response = requests.get(
                endpoint,
                headers=self._build_signal_relay_headers(),
                timeout=self._signal_relay_request_timeout_sec,
            )
        except requests.RequestException as exc:
            _log_trade(
                "Signal relay start-sync failed: "
                f"reason=request_exception error={exc!r} endpoint={endpoint}"
            )
            return baseline_offset

        if int(response.status_code) != 200:
            _log_trade(
                "Signal relay start-sync failed: "
                f"reason=http_status_{response.status_code} endpoint={endpoint}"
            )
            return baseline_offset

        try:
            payload = response.json()
        except ValueError:
            _log_trade(
                "Signal relay start-sync failed: "
                f"reason=invalid_json endpoint={endpoint} body={_trim_text(response.text, 200)!r}"
            )
            return baseline_offset

        if not isinstance(payload, dict):
            _log_trade(
                "Signal relay start-sync failed: "
                f"reason=invalid_payload_type endpoint={endpoint} payload_type={type(payload).__name__}"
            )
            return baseline_offset

        latest_event_id = self._safe_int(payload.get("latest_event_id")) or 0
        synced_offset = max(baseline_offset, int(latest_event_id))
        _log_trade(
            "Signal relay start-sync done: "
            f"baseline_offset={baseline_offset} synced_offset={synced_offset} "
            f"latest_event_id={latest_event_id}"
        )
        return synced_offset

    def _sync_telegram_update_offset_for_fresh_start(self) -> Optional[int]:
        token = (self._telegram_bot_token or "").strip()
        if not token:
            _log_trade("Telegram start-sync skipped: bot_token_missing.")
            return None

        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
            baseline_offset = max(0, int(self._telegram_update_offset))
            entry_channel_id = int(runtime.settings.entry_signal_channel_id)
            risk_channel_id = int(runtime.settings.risk_signal_channel_id)

        allowed_channel_ids = (entry_channel_id, risk_channel_id)
        synced_offset = baseline_offset
        accepted_events = 0
        batch_count = 0
        final_reason = "NO_UPDATES"

        _log_trade(
            "Telegram start-sync begin: "
            f"baseline_offset={baseline_offset} entry_channel_id={entry_channel_id} "
            f"risk_channel_id={risk_channel_id}"
        )

        while batch_count < TELEGRAM_START_SYNC_MAX_BATCHES:
            batch_count += 1
            poll_result = poll_telegram_updates_with_logging(
                bot_token=token,
                allowed_channel_ids=allowed_channel_ids,
                last_update_id=synced_offset,
                poll_timeout_seconds=0,
                request_timeout_seconds=TELEGRAM_REQUEST_TIMEOUT_SEC,
                limit=TELEGRAM_POLL_LIMIT,
                loop_label="ui-start-telegram-sync",
            )
            if not poll_result.ok:
                _log_trade(
                    "Telegram start-sync failed: "
                    f"reason={poll_result.reason_code} failure={poll_result.failure_reason} "
                    f"batch={batch_count} offset={synced_offset}"
                )
                return synced_offset

            next_offset = max(synced_offset, int(poll_result.next_update_id))
            progressed = next_offset > synced_offset
            synced_offset = next_offset
            accepted_events += len(poll_result.events)
            final_reason = poll_result.reason_code

            if poll_result.reason_code == "NO_UPDATES":
                break
            if not progressed:
                _log_trade(
                    "Telegram start-sync halted: "
                    f"reason=NO_OFFSET_PROGRESS batch={batch_count} offset={synced_offset}"
                )
                break

        capped = batch_count >= TELEGRAM_START_SYNC_MAX_BATCHES and final_reason != "NO_UPDATES"
        _log_trade(
            "Telegram start-sync done: "
            f"baseline_offset={baseline_offset} synced_offset={synced_offset} "
            f"accepted_events={accepted_events} batches={batch_count} "
            f"capped={capped} backlog_ignored=True reason={final_reason}"
        )
        return synced_offset

    def _persist_auto_trade_runtime(self) -> None:
        with self._auto_trade_runtime_lock:
            payload = {
                "last_message_ids": {str(k): int(v) for k, v in self._auto_trade_last_message_ids.items()},
                "cooldown_by_symbol": {str(k): int(v) for k, v in self._auto_trade_cooldown_by_symbol.items()},
                "received_at_by_symbol": {
                    str(k): int(v) for k, v in self._auto_trade_received_at_by_symbol.items()
                },
                "message_id_by_symbol": {
                    str(k): int(v) for k, v in self._auto_trade_message_id_by_symbol.items()
                },
            }
        try:
            with AUTO_TRADE_PERSIST_PATH.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
            _log_trade(
                "Auto-trade state persisted: "
                f"path={AUTO_TRADE_PERSIST_PATH} "
                f"last_message_ids={len(payload['last_message_ids'])} "
                f"cooldown_by_symbol={len(payload['cooldown_by_symbol'])} "
                f"received_at_by_symbol={len(payload['received_at_by_symbol'])} "
                f"message_id_by_symbol={len(payload['message_id_by_symbol'])}"
            )
        except Exception as exc:
            _log_trade(f"Auto-trade state persist failed: path={AUTO_TRADE_PERSIST_PATH} error={exc!r}")

    def _hydrate_auto_trade_state_from_disk(self) -> None:
        if not AUTO_TRADE_PERSIST_PATH.exists():
            return
        try:
            with AUTO_TRADE_PERSIST_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            _log_trade(f"Auto-trade state load failed: path={AUTO_TRADE_PERSIST_PATH} error={exc!r}")
            return

        if not isinstance(payload, dict):
            _log_trade(f"Auto-trade state load ignored: path={AUTO_TRADE_PERSIST_PATH} reason=invalid_payload")
            return

        last_message_ids = self._normalize_int_map(payload.get("last_message_ids"))
        cooldown_by_symbol = self._normalize_symbol_int_map(payload.get("cooldown_by_symbol"))
        received_at_by_symbol = self._normalize_symbol_int_map(payload.get("received_at_by_symbol"))
        message_id_by_symbol = self._normalize_symbol_int_map(payload.get("message_id_by_symbol"))
        with self._auto_trade_runtime_lock:
            self._auto_trade_last_message_ids = last_message_ids
            self._auto_trade_cooldown_by_symbol = cooldown_by_symbol
            self._auto_trade_received_at_by_symbol = received_at_by_symbol
            self._auto_trade_message_id_by_symbol = message_id_by_symbol
        _log_trade(
            "Auto-trade state loaded: "
            f"path={AUTO_TRADE_PERSIST_PATH} "
            f"last_message_ids={len(last_message_ids)} "
            f"cooldown_by_symbol={len(cooldown_by_symbol)} "
            f"received_at_by_symbol={len(received_at_by_symbol)} "
            f"message_id_by_symbol={len(message_id_by_symbol)}"
        )

    @staticmethod
    def _normalize_int_map(value: object) -> dict[int, int]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[int, int] = {}
        for key, raw in value.items():
            try:
                normalized[int(key)] = int(raw)
            except (TypeError, ValueError):
                continue
        return normalized

    @staticmethod
    def _normalize_symbol_int_map(value: object) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, int] = {}
        for key, raw in value.items():
            symbol = str(key or "").strip().upper()
            if not symbol:
                continue
            try:
                normalized[symbol] = int(raw)
            except (TypeError, ValueError):
                continue
        return normalized

    def _sync_orchestrator_runtime_from_recovery_state(self) -> None:
        with self._auto_trade_runtime_lock:
            self._sync_orchestrator_runtime_from_recovery_state_locked()

    def _sync_orchestrator_runtime_from_recovery_state_locked(self) -> None:
        self._orchestrator_runtime = replace(
            self._orchestrator_runtime,
            settings=self._auto_trade_settings,
            recovery_locked=self._auto_trade_state.recovery_locked,
            signal_loop_paused=self._auto_trade_state.signal_loop_paused,
            signal_loop_running=self._auto_trade_state.signal_loop_running,
            global_state=self._auto_trade_state.global_state,
            symbol_state=self._auto_trade_state.active_symbol_state,
            position_mode=self._auto_trade_state.position_mode,
            last_message_ids=dict(self._auto_trade_last_message_ids),
            cooldown_by_symbol=dict(self._auto_trade_cooldown_by_symbol),
            received_at_by_symbol=dict(self._auto_trade_received_at_by_symbol),
            message_id_by_symbol=dict(self._auto_trade_message_id_by_symbol),
        )

    def _sync_recovery_state_from_orchestrator_locked(self) -> None:
        self._auto_trade_last_message_ids = dict(self._orchestrator_runtime.last_message_ids)
        self._auto_trade_cooldown_by_symbol = dict(self._orchestrator_runtime.cooldown_by_symbol)
        self._auto_trade_received_at_by_symbol = dict(self._orchestrator_runtime.received_at_by_symbol)
        self._auto_trade_message_id_by_symbol = dict(self._orchestrator_runtime.message_id_by_symbol)
        self._auto_trade_state = replace(
            self._auto_trade_state,
            global_state=self._orchestrator_runtime.global_state,
            active_symbol_state=self._orchestrator_runtime.symbol_state,
            position_mode=self._orchestrator_runtime.position_mode,
            last_message_ids=dict(self._orchestrator_runtime.last_message_ids),
            cooldown_by_symbol=dict(self._orchestrator_runtime.cooldown_by_symbol),
            received_at_by_symbol=dict(self._orchestrator_runtime.received_at_by_symbol),
            message_id_by_symbol=dict(self._orchestrator_runtime.message_id_by_symbol),
        )

    def _start_signal_loop_thread(self) -> None:
        with self._auto_trade_runtime_lock:
            thread = self._signal_loop_thread
            if thread is not None and thread.is_alive():
                return
            try:
                if AUTO_TRADE_SIGNAL_INBOX_PATH.exists():
                    self._signal_inbox_offset = AUTO_TRADE_SIGNAL_INBOX_PATH.stat().st_size
                else:
                    self._signal_inbox_offset = 0
            except Exception:
                self._signal_inbox_offset = 0
            self._signal_loop_stop.clear()
            self._signal_loop_thread = threading.Thread(target=self._signal_loop_worker, daemon=True)
            self._signal_loop_thread.start()
            self._start_ws_price_thread_locked()
            self._start_user_stream_thread_locked()
        _log_trade("Signal loop thread started.")

    def _stop_signal_loop_thread(self) -> bool:
        self._signal_loop_stop.set()
        self._ws_loop_stop.set()
        self._user_stream_stop.set()
        with self._user_stream_lock:
            self._user_stream_connected = False
            self._user_stream_last_activity_at = 0.0
        _log_trade("Signal loop stop requested.")
        thread = self._signal_loop_thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            timeout_sec = 12.0
            deadline = time.time() + timeout_sec
            while thread.is_alive() and time.time() < deadline:
                thread.join(timeout=0.2)
            if thread.is_alive():
                _log_trade(
                    "Signal loop stop wait timeout: "
                    f"reason=thread_still_alive timeout_sec={timeout_sec:.1f}"
                )
                return False
            _log_trade("Signal loop thread joined.")
        return True

    def _start_ws_price_thread_locked(self) -> None:
        thread = self._ws_loop_thread
        if thread is not None and thread.is_alive():
            return
        self._ws_loop_stop.clear()
        self._ws_loop_thread = threading.Thread(target=self._ws_price_worker, daemon=True)
        self._ws_loop_thread.start()
        _log_trade("WS price worker start requested.")

    def _start_user_stream_thread_locked(self) -> None:
        if not self._api_key:
            _log_trade("User stream worker start skipped: api_key_missing.")
            return
        thread = self._user_stream_thread
        if thread is not None and thread.is_alive():
            return
        self._user_stream_stop.clear()
        self._user_stream_thread = threading.Thread(target=self._user_stream_worker, daemon=True)
        self._user_stream_thread.start()
        _log_trade("User stream worker start requested.")

    def _is_user_stream_healthy(self) -> bool:
        with self._user_stream_lock:
            connected = bool(self._user_stream_connected)
            has_listen_key = bool(self._user_stream_listen_key)
            last_activity_at = float(self._user_stream_last_activity_at)
        if not connected or not has_listen_key:
            return False
        if last_activity_at <= 0:
            return False
        return (time.time() - last_activity_at) <= float(USER_STREAM_HEALTHY_GRACE_SEC)

    def _snapshot_user_stream_account_rows(self) -> tuple[list[dict], list[dict], int]:
        with self._user_stream_lock:
            open_orders: list[dict] = []
            for symbol in sorted(self._user_stream_open_orders_by_symbol.keys()):
                by_id = self._user_stream_open_orders_by_symbol.get(symbol, {})
                if not isinstance(by_id, dict):
                    continue
                for order_id in sorted(by_id.keys()):
                    row = by_id.get(order_id)
                    if isinstance(row, dict):
                        open_orders.append(dict(row))
            positions = [
                dict(row)
                for symbol, row in sorted(self._user_stream_positions_by_symbol.items())
                if isinstance(row, dict)
            ]
            activity_at = int(float(self._user_stream_last_activity_at or 0.0))
        return open_orders, positions, activity_at

    def _apply_user_stream_snapshot_to_account_cache(self, *, reason: str, received_at: int) -> None:
        open_orders, positions, last_activity = self._snapshot_user_stream_account_rows()
        applied_at = int(received_at if received_at > 0 else max(last_activity, int(time.time())))

        effective_positions: list[dict] = []
        dust_symbols: set[str] = set()
        for row in positions:
            symbol = str(row.get("symbol") or "").strip().upper()
            if self._is_nonzero_position_row(row):
                effective_positions.append(row)
            elif symbol:
                dust_symbols.add(symbol)

        with self._account_snapshot_cache_lock:
            self._open_orders_cache = self._copy_account_rows(open_orders)
            self._open_orders_cache_at = float(applied_at)
            self._positions_cache = self._copy_account_rows(effective_positions)
            self._positions_cache_at = float(applied_at)
            self._positions_cache_dust_symbols = set(dust_symbols)

        self._last_dust_symbols = set(dust_symbols)
        signature = (
            f"orders={len(open_orders)}|positions={len(effective_positions)}|dust={len(dust_symbols)}|"
            f"reason={reason}"
        )
        if signature != self._user_stream_last_snapshot_signature:
            self._user_stream_last_snapshot_signature = signature
            _log_trade(
                "User stream snapshot applied: "
                f"reason={reason} open_order_count={len(open_orders)} "
                f"position_count={len(effective_positions)} dust_count={len(dust_symbols)} "
                f"received_at={applied_at}"
            )

    def _binance_user_stream_request(
        self,
        method: str,
        *,
        listen_key: str = "",
        timeout: int = 10,
    ) -> Optional[object]:
        if not self._api_key:
            return None
        path = USER_STREAM_LISTEN_KEY_PATH
        headers = {"X-MBX-APIKEY": self._api_key}
        params: dict[str, str] = {}
        normalized_listen_key = str(listen_key or "").strip()
        if normalized_listen_key:
            params["listenKey"] = normalized_listen_key
        url = f"https://fapi.binance.com{path}"
        method_name = str(method or "").strip().upper()
        try:
            response = requests.request(
                method_name,
                url,
                headers=headers,
                params=params or None,
                timeout=timeout,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if not response.ok:
                detail = payload if isinstance(payload, dict) else _trim_text(response.text)
                _log_trade(
                    "User stream request failed: "
                    f"method={method_name} path={path} status={response.status_code} "
                    f"params={params} detail={detail!r}"
                )
                return payload if isinstance(payload, dict) else None
            return payload if payload is not None else {}
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                detail = payload if isinstance(payload, dict) else _trim_text(response.text)
                _log_trade(
                    "User stream request error: "
                    f"method={method_name} path={path} status={response.status_code} "
                    f"params={params} detail={detail!r}"
                )
            else:
                _log_trade(
                    "User stream request exception: "
                    f"method={method_name} path={path} params={params} error={exc!r}"
                )
            return None

    def _create_user_stream_listen_key(self) -> str:
        payload = self._binance_user_stream_request("POST")
        if not isinstance(payload, dict):
            _log_trade("User stream listenKey create failed: payload_invalid.")
            return ""
        listen_key = str(payload.get("listenKey") or "").strip()
        if not listen_key:
            _log_trade(f"User stream listenKey create failed: payload={payload!r}")
            return ""
        _log_trade("User stream listenKey created.")
        return listen_key

    def _keepalive_user_stream_listen_key(self, listen_key: str) -> bool:
        payload = self._binance_user_stream_request("PUT", listen_key=listen_key)
        if payload is None:
            _log_trade("User stream keepalive failed: response_none.")
            return False
        if isinstance(payload, dict):
            error_code, error_message = self._extract_exchange_error_from_payload(payload)
            if error_code < 0:
                _log_trade(
                    "User stream keepalive rejected: "
                    f"code={error_code} message={error_message or '-'}"
                )
                return False
        _log_trade("User stream keepalive success.")
        return True

    def _close_user_stream_listen_key(self, listen_key: str) -> None:
        payload = self._binance_user_stream_request("DELETE", listen_key=listen_key)
        if payload is None:
            _log_trade("User stream listenKey close skipped: response_none.")
            return
        if isinstance(payload, dict):
            error_code, error_message = self._extract_exchange_error_from_payload(payload)
            if error_code < 0:
                _log_trade(
                    "User stream listenKey close rejected: "
                    f"code={error_code} message={error_message or '-'}"
                )
                return
        _log_trade("User stream listenKey closed.")

    def _sync_user_stream_activity(self, *, connected: bool, listen_key: str = "", touch: bool = False) -> None:
        now = time.time()
        with self._user_stream_lock:
            self._user_stream_connected = bool(connected)
            self._user_stream_listen_key = str(listen_key or "").strip()
            if touch:
                self._user_stream_last_activity_at = now
            if not connected:
                self._user_stream_last_activity_at = 0.0
                self._user_stream_last_keepalive_at = 0.0

    def _user_stream_worker(self) -> None:
        try:
            import websocket  # type: ignore[import-not-found]
        except Exception:
            _log_trade(
                "User stream worker disabled: websocket-client not installed, using REST account snapshot fallback."
            )
            return

        _log_trade("User stream worker entered.")
        while not self._user_stream_stop.is_set():
            listen_key = self._create_user_stream_listen_key()
            if not listen_key:
                if not self._user_stream_stop.is_set():
                    time.sleep(WS_RECONNECT_BACKOFF_SEC)
                continue

            self._sync_user_stream_activity(connected=True, listen_key=listen_key, touch=True)
            ws = None
            reconnect_required = False
            try:
                ws_url = f"{BINANCE_FUTURES_USER_STREAM_BASE_URL}/{listen_key}"
                ws = websocket.create_connection(ws_url, timeout=10)
                ws.settimeout(5)
                with self._user_stream_lock:
                    self._user_stream_last_keepalive_at = time.time()
                _log_trade("User stream connected.")

                while not self._user_stream_stop.is_set():
                    now = time.time()
                    with self._user_stream_lock:
                        keepalive_due = (now - float(self._user_stream_last_keepalive_at)) >= USER_STREAM_KEEPALIVE_SEC
                    if keepalive_due:
                        keepalive_ok = self._keepalive_user_stream_listen_key(listen_key)
                        with self._user_stream_lock:
                            if keepalive_ok:
                                self._user_stream_last_keepalive_at = now
                                self._user_stream_last_activity_at = now
                        if not keepalive_ok:
                            reconnect_required = True
                            break

                    try:
                        raw = ws.recv()
                    except Exception as exc:
                        if "timed out" in str(exc).lower():
                            with self._user_stream_lock:
                                self._user_stream_last_activity_at = now
                            continue
                        reconnect_required = True
                        _log_trade(f"User stream recv error: {exc!r}")
                        break
                    if raw is None:
                        continue
                    should_reconnect = self._apply_user_stream_message(raw)
                    if should_reconnect:
                        reconnect_required = True
                        break
            except Exception as exc:
                reconnect_required = True
                _log_trade(f"User stream connection error: {exc!r}")
            finally:
                try:
                    if ws is not None:
                        ws.close()
                except Exception:
                    pass
                self._sync_user_stream_activity(connected=False)
                self._close_user_stream_listen_key(listen_key)

            if reconnect_required and not self._user_stream_stop.is_set():
                time.sleep(WS_RECONNECT_BACKOFF_SEC)
        _log_trade("User stream worker exited.")

    def _apply_user_stream_message(self, raw: object) -> bool:
        try:
            payload = json.loads(str(raw))
        except Exception:
            _log_trade(f"User stream payload parse failed: raw={_trim_text(str(raw), 200)!r}")
            return False
        if not isinstance(payload, dict):
            return False

        received_at = int(time.time())
        with self._user_stream_lock:
            self._user_stream_last_activity_at = float(received_at)

        event_name = str(payload.get("e") or "").strip()
        event_upper = event_name.upper()
        if event_upper == "LISTENKEYEXPIRED":
            _log_trade("User stream listenKey expired event received: reconnect required.")
            return True
        if event_upper == "ACCOUNT_UPDATE":
            self._apply_user_stream_account_update(payload, received_at=received_at)
            return False
        if event_upper == "ORDER_TRADE_UPDATE":
            self._apply_user_stream_order_update(payload, received_at=received_at)
            return False
        return False

    def _apply_user_stream_account_update(self, payload: Mapping[str, object], *, received_at: int) -> None:
        account_data = payload.get("a")
        if not isinstance(account_data, dict):
            _log_trade("User stream account update ignored: account_payload_invalid.")
            return
        rows = account_data.get("P")
        if not isinstance(rows, list):
            _log_trade("User stream account update ignored: positions_payload_invalid.")
            return

        event_time_ms = self._safe_int(payload.get("E")) or int(time.time() * 1000)
        updated_symbols = 0
        removed_symbols = 0
        with self._user_stream_lock:
            for item in rows:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("s") or "").strip().upper()
                if not symbol:
                    continue
                position_amt = self._safe_float(item.get("pa"))
                if position_amt is None or abs(float(position_amt)) <= 1e-12:
                    if self._user_stream_positions_by_symbol.pop(symbol, None) is not None:
                        removed_symbols += 1
                    continue

                existing = self._user_stream_positions_by_symbol.get(symbol, {})
                leverage = str(existing.get("leverage") or "1")
                margin_type = str(item.get("mt") or existing.get("marginType") or "CROSS").strip().upper()
                if margin_type == "CROSSED":
                    margin_type = "CROSS"
                position_side = str(item.get("ps") or existing.get("positionSide") or "BOTH").strip().upper() or "BOTH"
                entry_price = self._safe_float(item.get("ep")) or self._safe_float(existing.get("entryPrice")) or 0.0
                unrealized = self._safe_float(item.get("up")) or self._safe_float(existing.get("unRealizedProfit")) or 0.0
                mark_price = self._safe_float(existing.get("markPrice")) or 0.0
                with self._ws_price_lock:
                    ws_mark = self._ws_price_by_symbol.get(symbol)
                if ws_mark is not None and ws_mark > 0:
                    mark_price = float(ws_mark)

                row = {
                    "symbol": symbol,
                    "positionAmt": str(float(position_amt)),
                    "entryPrice": str(float(entry_price)),
                    "markPrice": str(float(mark_price)),
                    "unRealizedProfit": str(float(unrealized)),
                    "leverage": leverage,
                    "positionSide": position_side,
                    "marginType": margin_type or "CROSS",
                    "updateTime": int(event_time_ms),
                }
                self._user_stream_positions_by_symbol[symbol] = row
                updated_symbols += 1
            self._user_stream_last_activity_at = float(received_at)

        self._apply_user_stream_snapshot_to_account_cache(reason="ACCOUNT_UPDATE", received_at=received_at)
        _log_trade(
            "User stream account update applied: "
            f"updated_symbols={updated_symbols} removed_symbols={removed_symbols} event_time={event_time_ms}"
        )

    def _apply_user_stream_order_update(self, payload: Mapping[str, object], *, received_at: int) -> None:
        order_data = payload.get("o")
        if not isinstance(order_data, dict):
            _log_trade("User stream order update ignored: order_payload_invalid.")
            return
        symbol = str(order_data.get("s") or "").strip().upper()
        order_id = self._safe_int(order_data.get("i"))
        status = str(order_data.get("X") or "").strip().upper()
        if not symbol or order_id <= 0:
            _log_trade("User stream order update ignored: symbol_or_order_id_invalid.")
            return

        terminal_statuses = {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}
        updated = False
        removed = False
        with self._user_stream_lock:
            by_symbol = self._user_stream_open_orders_by_symbol.setdefault(symbol, {})
            if status in terminal_statuses:
                removed = by_symbol.pop(order_id, None) is not None
                if not by_symbol:
                    self._user_stream_open_orders_by_symbol.pop(symbol, None)
            else:
                order_type = str(order_data.get("o") or "").strip().upper()
                row = {
                    "symbol": symbol,
                    "orderId": int(order_id),
                    "status": status or "NEW",
                    "type": order_type,
                    "side": str(order_data.get("S") or "").strip().upper(),
                    "price": str(order_data.get("p") or "0"),
                    "stopPrice": str(order_data.get("sp") or "0"),
                    "triggerPrice": str(
                        order_data.get("triggerPrice")
                        or order_data.get("tp")
                        or "0"
                    ),
                    "activatePrice": str(
                        order_data.get("activatePrice")
                        or order_data.get("AP")
                        or order_data.get("ap")
                        or "0"
                    ),
                    "origQty": str(order_data.get("q") or "0"),
                    "executedQty": str(order_data.get("z") or "0"),
                    "reduceOnly": bool(order_data.get("R")),
                    "closePosition": bool(order_data.get("cp")),
                    "positionSide": str(order_data.get("ps") or "BOTH").strip().upper() or "BOTH",
                    "updateTime": int(self._safe_int(order_data.get("T")) or self._safe_int(payload.get("E"))),
                }
                if order_type in ALGO_ORDER_TYPES:
                    stop_price, stop_source = self._select_effective_stop_price(row)
                    if stop_price is not None:
                        row["stopPrice"] = str(stop_price)
                        if stop_source and stop_source != "stopPrice":
                            row["_stop_price_source"] = stop_source
                            _log_trade(
                                "User stream stop price fallback applied: "
                                f"symbol={symbol} order_id={order_id} source={stop_source} stop_price={stop_price}"
                            )
                by_symbol[order_id] = row
                updated = True
            self._user_stream_last_activity_at = float(received_at)

        self._apply_user_stream_snapshot_to_account_cache(reason="ORDER_TRADE_UPDATE", received_at=received_at)
        _log_trade(
            "User stream order update applied: "
            f"symbol={symbol} order_id={order_id} status={status or '-'} "
            f"updated={updated} removed={removed}"
        )

    def _ws_price_worker(self) -> None:
        try:
            import websocket  # type: ignore[import-not-found]
        except Exception:
            _log_trade(
                "WS price worker disabled: websocket-client not installed, using REST fallback only."
            )
            return

        _log_trade("WS price worker entered.")
        while not self._ws_loop_stop.is_set():
            ws = None
            try:
                ws = websocket.create_connection(BINANCE_FUTURES_MARK_PRICE_STREAM_URL, timeout=10)
                ws.settimeout(5)
                _log_trade("WS price connected.")
                while not self._ws_loop_stop.is_set():
                    try:
                        raw = ws.recv()
                    except Exception:
                        break
                    if raw is None:
                        continue
                    self._apply_ws_mark_price_message(raw)
            except Exception as exc:
                _log_trade(f"WS price connection error: {exc!r}")
            finally:
                try:
                    if ws is not None:
                        ws.close()
                except Exception:
                    pass
            if not self._ws_loop_stop.is_set():
                time.sleep(WS_RECONNECT_BACKOFF_SEC)
        _log_trade("WS price worker exited.")

    def _apply_ws_mark_price_message(self, raw: object) -> None:
        try:
            payload = json.loads(str(raw))
        except Exception:
            return

        now = int(time.time())
        updates: dict[str, float] = {}
        if isinstance(payload, list):
            iterable = payload
        elif isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                iterable = data
            else:
                iterable = [payload]
        else:
            return

        for item in iterable:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("s") or item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            mark_price = self._safe_float(
                item.get("c")
                or item.get("lastPrice")
                or item.get("price")
                or item.get("markPrice")
            )
            if mark_price is None or mark_price <= 0:
                # Compatibility fallback when unexpected payload uses mark-price stream field.
                if "c" not in item and "P" not in item:
                    mark_price = self._safe_float(item.get("p"))
                if mark_price is None or mark_price <= 0:
                    continue
            updates[symbol] = float(mark_price)

        if not updates:
            return
        with self._ws_price_lock:
            self._ws_price_by_symbol.update(updates)
            self._ws_price_received_at = now

    def _snapshot_ws_prices(self, symbols: list[str]) -> tuple[dict[str, float], int]:
        targets = {str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()}
        with self._ws_price_lock:
            if not targets:
                return {}, int(self._ws_price_received_at)
            result: dict[str, float] = {}
            for symbol in targets:
                value = self._ws_price_by_symbol.get(symbol)
                if value is not None and value > 0:
                    result[symbol] = float(value)
            ws_received_at = int(self._ws_price_received_at)
        return result, ws_received_at

    def _apply_latest_ws_mark_prices_to_positions(self, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        with self._ws_price_lock:
            ws_prices = dict(self._ws_price_by_symbol)
        if not ws_prices:
            return self._copy_account_rows(rows)
        enriched: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            updated = dict(row)
            symbol = str(updated.get("symbol") or "").strip().upper()
            mark_price = ws_prices.get(symbol)
            if mark_price is not None and mark_price > 0:
                updated["markPrice"] = str(float(mark_price))
            enriched.append(updated)
        return enriched

    def inject_test_signal(
        self,
        *,
        channel_id: int,
        message_id: int,
        message_text: str,
        received_at_local: Optional[int] = None,
    ) -> None:
        event = {
            "channel_id": int(channel_id),
            "message_id": int(message_id),
            "message_text": str(message_text),
            "received_at_local": int(received_at_local) if received_at_local is not None else int(time.time()),
        }
        self._enqueue_signal_event(event)

    def _enqueue_signal_event(self, event: Mapping[str, object]) -> None:
        with self._signal_queue_lock:
            self._signal_event_queue.append(dict(event))
        _log_trade(
            "Signal queued: "
            f"channel_id={event.get('channel_id')} message_id={event.get('message_id')} "
            f"received_at_local={event.get('received_at_local')}"
        )

    def _drain_signal_events(self, max_count: int = 20) -> list[dict]:
        with self._signal_queue_lock:
            if not self._signal_event_queue:
                return []
            count = min(max_count, len(self._signal_event_queue))
            drained = self._signal_event_queue[:count]
            del self._signal_event_queue[:count]
        return drained

    def _drop_queued_signal_events_for_safety_lock(self, *, loop_label: str) -> int:
        with self._signal_queue_lock:
            dropped_count = len(self._signal_event_queue)
            if dropped_count:
                self._signal_event_queue.clear()
        if dropped_count:
            _log_trade(
                "Safety lock signal drop applied: "
                f"dropped_events={dropped_count} loop={loop_label}"
            )
        return dropped_count

    def _clear_signal_event_queue_for_fresh_start(self, *, loop_label: str) -> int:
        with self._signal_queue_lock:
            dropped_count = len(self._signal_event_queue)
            if dropped_count:
                self._signal_event_queue.clear()
        _log_trade(
            "Fresh-start signal queue reset: "
            f"dropped_events={dropped_count} loop={loop_label}"
        )
        return dropped_count

    def _clear_signal_event_queue_for_stop(self, *, loop_label: str) -> int:
        with self._signal_queue_lock:
            dropped_count = len(self._signal_event_queue)
            if dropped_count:
                self._signal_event_queue.clear()
        _log_trade(
            "Stop signal queue reset: "
            f"dropped_events={dropped_count} loop={loop_label}"
        )
        return dropped_count

    def _signal_loop_worker(self) -> None:
        _log_trade("Signal loop worker entered.")
        while not self._signal_loop_stop.is_set():
            with self._auto_trade_runtime_lock:
                paused = self._auto_trade_state.signal_loop_paused
                running = self._auto_trade_state.signal_loop_running
            if not running or paused:
                time.sleep(SIGNAL_LOOP_INTERVAL_SEC)
                continue
            try:
                self._signal_loop_tick()
            except Exception as exc:
                _log_trade(f"Signal loop tick error: {exc!r}")
            time.sleep(SIGNAL_LOOP_INTERVAL_SEC)
        _log_trade("Signal loop worker exited.")

    def _signal_loop_tick(self) -> None:
        self._signal_loop_snapshot_cycle_seq += 1
        snapshot_cycle_id = self._signal_loop_snapshot_cycle_seq
        self._poll_signal_source_updates()
        self._poll_signal_inbox_file()
        open_orders, positions = self._fetch_loop_account_snapshot(
            loop_label="signal-loop-pre-sync-snapshot",
            snapshot_cycle_id=snapshot_cycle_id,
        )
        pre_sync_invalidation_seq = self._get_account_snapshot_invalidation_seq()
        self._run_fill_sync_pass(
            open_orders=open_orders,
            positions=positions,
            risk_market_exit_in_same_loop=False,
            loop_label="signal-loop-pre-sync",
        )
        if self._get_account_snapshot_invalidation_seq() != pre_sync_invalidation_seq:
            open_orders, positions = self._fetch_loop_account_snapshot(
                loop_label="signal-loop-price-guard-snapshot",
                snapshot_cycle_id=snapshot_cycle_id,
            )
            _log_trade(
                "Signal loop price guard snapshot refreshed: "
                f"reason=pre_sync_cache_invalidated cycle_id={snapshot_cycle_id}"
            )
        guard_result = self._apply_price_guard_for_loop(
            open_orders=open_orders,
            positions=positions,
            loop_label="signal-loop-price-guard",
        )
        if guard_result is not None:
            self._execute_safety_action_if_needed(
                guard_result=guard_result,
                open_orders=open_orders,
                positions=positions,
                loop_label="signal-loop-safety-action",
            )

        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        if runtime.global_state.safety_locked:
            self._drop_queued_signal_events_for_safety_lock(loop_label="signal-loop-safety-lock")
            self._refresh_filter_controls_lock_from_runtime(runtime)
            return

        events = self._drain_signal_events()
        risk_market_exit_in_same_loop = False
        if events:
            _log_trade(f"Signal loop tick: processing_events={len(events)}")
        for event in events:
            risk_market_exit_in_same_loop = (
                self._process_signal_event(event) or risk_market_exit_in_same_loop
            )
        self._run_trigger_cycle_once()

        open_orders, positions = self._fetch_loop_account_snapshot(
            loop_label="signal-loop-post-sync-snapshot",
            snapshot_cycle_id=snapshot_cycle_id,
        )
        self._run_fill_sync_pass(
            open_orders=open_orders,
            positions=positions,
            risk_market_exit_in_same_loop=risk_market_exit_in_same_loop,
            loop_label="signal-loop-post-sync",
        )
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        self._refresh_filter_controls_lock_from_runtime(runtime)

    @staticmethod
    def _copy_account_rows(rows: list[dict]) -> list[dict]:
        return [dict(item) for item in rows if isinstance(item, dict)]

    @staticmethod
    def _is_account_snapshot_mutation_path(path: str) -> bool:
        normalized = str(path or "").strip()
        return normalized in (
            FUTURES_ORDER_PATH,
            FUTURES_CANCEL_ALL_OPEN_ORDERS_PATH,
            FUTURES_ALGO_ORDER_PATH,
            FUTURES_CANCEL_ALL_OPEN_ALGO_ORDERS_PATH,
        )

    def _invalidate_account_snapshot_cache(self, *, reason: str, loop_label: str) -> None:
        stale_at = max(0.0, time.time() - (ACCOUNT_SNAPSHOT_CACHE_TTL_SEC + 0.1))
        with self._account_snapshot_cache_lock:
            self._open_orders_cache_at = stale_at
            self._positions_cache_at = stale_at
            self._account_snapshot_invalidation_seq += 1
            invalidation_seq = int(self._account_snapshot_invalidation_seq)
        _log_trade(
            "Account snapshot cache invalidated: "
            f"reason={reason} loop={loop_label} invalidation_seq={invalidation_seq}"
        )

    def _get_account_snapshot_invalidation_seq(self) -> int:
        with self._account_snapshot_cache_lock:
            return int(self._account_snapshot_invalidation_seq)

    def _has_account_snapshot_within(self, *, max_age_sec: float) -> bool:
        threshold = max(0.0, float(max_age_sec))
        now = time.time()
        with self._account_snapshot_cache_lock:
            open_orders_ready = (
                self._open_orders_cache is not None
                and max(0.0, now - float(self._open_orders_cache_at)) <= threshold
            )
            positions_ready = (
                self._positions_cache is not None
                and max(0.0, now - float(self._positions_cache_at)) <= threshold
            )
        return bool(open_orders_ready and positions_ready)

    def _has_recent_account_snapshot(self) -> bool:
        return self._has_account_snapshot_within(max_age_sec=ACCOUNT_SNAPSHOT_STALE_FALLBACK_SEC)

    @staticmethod
    def _is_rate_limit_payload(payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        code = payload.get("code")
        if isinstance(code, int) and code == -1003:
            return True
        message = str(payload.get("msg") or "").lower()
        return "too many requests" in message or "way too many requests" in message

    def _note_account_rest_backoff(self, *, context: str) -> None:
        now = time.time()
        previous = float(self._account_snapshot_rest_backoff_sec)
        if previous <= 0:
            next_backoff = float(ACCOUNT_REST_BACKOFF_BASE_SEC)
        else:
            next_backoff = min(float(ACCOUNT_REST_BACKOFF_MAX_SEC), previous * 2.0)
        self._account_snapshot_rest_backoff_sec = float(next_backoff)
        self._account_snapshot_rest_backoff_until = max(
            float(self._account_snapshot_rest_backoff_until),
            now + float(next_backoff),
        )
        _log_trade(
            "Account REST backoff updated: "
            f"context={context} backoff_sec={next_backoff:.2f} "
            f"until={self._account_snapshot_rest_backoff_until:.2f}"
        )

    def _clear_account_rest_backoff(self, *, context: str) -> None:
        if self._account_snapshot_rest_backoff_sec <= 0 and self._account_snapshot_rest_backoff_until <= 0:
            return
        self._account_snapshot_rest_backoff_sec = 0.0
        self._account_snapshot_rest_backoff_until = 0.0
        _log_trade(f"Account REST backoff cleared: context={context}")

    def _fetch_loop_account_snapshot(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "signal-loop-snapshot",
        snapshot_cycle_id: Optional[int] = None,
    ) -> tuple[list[dict], list[dict]]:
        if not self._api_key or not self._secret_key:
            return [], []
        now = time.time()
        user_stream_healthy = self._is_user_stream_healthy()
        periodic_reconcile_due = (
            now - float(self._last_account_rest_reconcile_at)
        ) >= float(ACCOUNT_REST_RECONCILE_INTERVAL_SEC)
        should_force_rest = bool(force_refresh)
        force_reason = "FORCE_REFRESH"
        if not should_force_rest and not user_stream_healthy:
            should_force_rest = True
            force_reason = "USER_STREAM_UNHEALTHY"
            if (
                snapshot_cycle_id is not None
                and int(snapshot_cycle_id) == int(self._account_snapshot_last_user_stream_force_cycle_id)
            ):
                should_force_rest = False
                _log_trade(
                    "Account snapshot REST reconcile skipped in same signal-loop cycle: "
                    f"reason=USER_STREAM_UNHEALTHY_ALREADY_FORCED cycle_id={snapshot_cycle_id} "
                    f"loop={loop_label}"
                )
        elif not should_force_rest and periodic_reconcile_due:
            should_force_rest = True
            force_reason = "PERIODIC_RECONCILE"

        if should_force_rest and now < float(self._account_snapshot_rest_backoff_until):
            should_force_rest = False
            _log_trade(
                "Account snapshot REST reconcile deferred by backoff: "
                f"reason={force_reason} backoff_until={self._account_snapshot_rest_backoff_until:.2f} "
                f"now={now:.2f} loop={loop_label}"
            )

        if should_force_rest and force_reason == "USER_STREAM_UNHEALTHY":
            min_force_interval = float(ACCOUNT_REST_UNHEALTHY_FORCE_MIN_INTERVAL_SEC)
            elapsed_since_unhealthy_force = now - float(self._account_snapshot_last_user_stream_force_at)
            has_short_term_snapshot = self._has_account_snapshot_within(max_age_sec=min_force_interval)
            if has_short_term_snapshot and elapsed_since_unhealthy_force < min_force_interval:
                should_force_rest = False
                _log_trade(
                    "Account snapshot REST reconcile throttled: "
                    "reason=USER_STREAM_UNHEALTHY "
                    f"elapsed_sec={elapsed_since_unhealthy_force:.2f} "
                    f"min_interval_sec={min_force_interval:.2f} loop={loop_label}"
                )
            else:
                self._account_snapshot_last_user_stream_force_at = now
                if snapshot_cycle_id is not None:
                    self._account_snapshot_last_user_stream_force_cycle_id = int(snapshot_cycle_id)

        open_orders, open_orders_refreshed, open_orders_rate_limited = self._fetch_open_orders_with_meta(
            force_refresh=should_force_rest,
            loop_label=f"{loop_label}-open-orders",
        )
        positions, positions_refreshed, positions_rate_limited = self._fetch_open_positions_with_meta(
            force_refresh=should_force_rest,
            loop_label=f"{loop_label}-positions",
        )
        if should_force_rest:
            rest_refresh_applied = bool(open_orders_refreshed and positions_refreshed)
            rate_limited = bool(open_orders_rate_limited or positions_rate_limited)
            if rest_refresh_applied:
                self._last_account_rest_reconcile_at = now
                self._clear_account_rest_backoff(context=f"{loop_label}-rest-reconcile")
                _log_trade(
                    "Account snapshot REST reconcile applied: "
                    f"reason={force_reason} open_order_count={len(open_orders)} "
                    f"position_count={len(positions)} loop={loop_label}"
                )
            else:
                _log_trade(
                    "Account snapshot REST reconcile incomplete: "
                    f"reason={force_reason} open_orders_ready={open_orders is not None} "
                    f"positions_ready={positions is not None} "
                    f"open_orders_refreshed={open_orders_refreshed} "
                    f"positions_refreshed={positions_refreshed} "
                    f"rate_limited={rate_limited} loop={loop_label}"
                )
        if open_orders is None or positions is None:
            _log_trade(
                "Loop account snapshot unavailable: "
                f"force_refresh={force_refresh} rest_forced={should_force_rest} "
                f"user_stream_healthy={user_stream_healthy} "
                f"open_orders_ready={open_orders is not None} positions_ready={positions is not None} "
                f"loop={loop_label}"
            )
        return open_orders or [], positions or []

    def _apply_price_guard_for_loop(
        self,
        *,
        open_orders: list[dict],
        positions: list[dict],
        loop_label: str,
    ):
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        symbols = self._collect_price_symbols(runtime, open_orders=open_orders, positions=positions)
        if not symbols:
            symbols = ["BTCUSDT"]
        now = int(time.time())
        ws_prices, ws_received_at = self._snapshot_ws_prices(symbols)
        rest_prices = self._fetch_mark_prices(symbols)
        updated, result = apply_price_source_and_guard(
            runtime,
            ws_prices=ws_prices,
            rest_prices=rest_prices,
            received_at=now,
            ws_received_at=ws_received_at if ws_received_at > 0 else None,
            rest_received_at=now,
            now=now,
            loop_label=loop_label,
        )
        with self._auto_trade_runtime_lock:
            self._orchestrator_runtime = updated
            self._sync_recovery_state_from_orchestrator_locked()
        return result

    def _collect_price_symbols(
        self,
        runtime: AutoTradeRuntime,
        *,
        open_orders: list[dict],
        positions: list[dict],
    ) -> list[str]:
        symbols: set[str] = set()
        symbols.update(str(symbol).strip().upper() for symbol in runtime.pending_trigger_candidates.keys())
        if runtime.active_symbol:
            symbols.add(str(runtime.active_symbol).strip().upper())
        for row in open_orders:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol:
                symbols.add(symbol)
        for row in positions:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol:
                symbols.add(symbol)
        return sorted(symbol for symbol in symbols if symbol)

    def _execute_safety_action_if_needed(
        self,
        *,
        guard_result,
        open_orders: list[dict],
        positions: list[dict],
        loop_label: str,
    ) -> None:
        action = str(guard_result.safety_action or "NONE")
        now = int(time.time())
        if not guard_result.safety_locked:
            if self._last_safety_action_code:
                _log_trade("Safety lock released: clear safety action latch.")
            self._last_safety_action_code = ""
            self._last_safety_action_at = 0
            return

        should_execute = (
            action != "NONE"
            and (
                action != self._last_safety_action_code
                or now - self._last_safety_action_at >= 5
            )
        )
        if not should_execute:
            return

        _log_trade(
            "Safety action dispatch: "
            f"action={action} positions={len(positions)} open_orders={len(open_orders)} "
            f"safety_locked={guard_result.safety_locked} global_blocked={guard_result.global_blocked}"
        )
        if action == "FORCE_MARKET_EXIT":
            self._force_market_exit_all_positions(
                positions=positions,
                loop_label=f"{loop_label}-force-market-exit",
            )
        elif action == "CANCEL_OPEN_ORDERS_AND_RESET":
            symbols = sorted(
                {
                    str(row.get("symbol") or "").strip().upper()
                    for row in open_orders
                    if str(row.get("symbol") or "").strip()
                }
            )
            self._cancel_open_orders_for_symbols(
                symbols=symbols,
                loop_label=f"{loop_label}-cancel-open-orders",
            )
            self._reset_runtime_after_external_clear(reason_code="SAFETY_CANCEL_AND_RESET")
        elif action == "RESET_ONLY":
            self._reset_runtime_after_external_clear(reason_code="SAFETY_RESET_ONLY")

        self._last_safety_action_code = action
        self._last_safety_action_at = now

    def _refresh_filter_controls_lock_from_runtime(self, runtime: AutoTradeRuntime) -> None:
        should_lock = bool(
            self._trade_state == "start"
            or self._auto_trade_starting
            or runtime.signal_loop_running
            or runtime.symbol_state != "IDLE"
            or runtime.global_state.has_any_open_order
            or runtime.global_state.has_any_position
        )
        if should_lock == self._filter_controls_locked:
            return
        self._filter_controls_locked = should_lock
        self.after(0, lambda: self._set_filter_controls_lock_ui(should_lock))

    def _set_filter_controls_lock_ui(self, locked: bool) -> None:
        state = "disabled" if locked else "readonly"
        for widget in (self.mdd_dropdown, self.tp_ratio_dropdown, self.risk_filter_dropdown):
            try:
                widget.configure(state=state)
            except tk.TclError:
                continue
        if locked:
            for key in ("filter_save", "filter_reset"):
                self._button_hover[key] = False
                self._button_lift[key] = 0.0
        _log_trade(
            "Filter controls state updated: "
            f"locked={locked} trade_state={self._trade_state} "
            f"signal_loop_running={self._orchestrator_runtime.signal_loop_running} "
            f"symbol_state={self._orchestrator_runtime.symbol_state}"
        )
        self._layout()

    def _poll_signal_source_updates(self) -> None:
        if self._signal_source_mode == SIGNAL_SOURCE_MODE_RELAY:
            self._poll_signal_relay_updates()
            return
        self._poll_telegram_bot_updates()

    def _poll_signal_relay_updates(self) -> None:
        relay_base_url = self._normalize_relay_base_url(self._signal_relay_base_url)
        if not relay_base_url:
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade("Signal relay poll skipped: reason=relay_base_url_missing.")
            return

        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
            entry_channel_id = int(runtime.settings.entry_signal_channel_id)
            risk_channel_id = int(runtime.settings.risk_signal_channel_id)
        allowed_channel_ids = {entry_channel_id, risk_channel_id}

        endpoint = f"{relay_base_url}/api/v1/signals"
        previous_offset = max(0, int(self._signal_relay_update_offset))
        params = {
            "after_id": previous_offset,
            "limit": max(1, int(self._signal_relay_poll_limit)),
            "client_id": self._signal_relay_client_id,
        }
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers=self._build_signal_relay_headers(),
                timeout=self._signal_relay_request_timeout_sec,
            )
        except requests.RequestException as exc:
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade(
                    "Signal relay poll failed: "
                    f"reason=request_exception error={exc!r} endpoint={endpoint}"
                )
            return

        if int(response.status_code) != 200:
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade(
                    "Signal relay poll failed: "
                    f"reason=http_status_{response.status_code} endpoint={endpoint}"
                )
            return

        try:
            payload = response.json()
        except ValueError:
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade(
                    "Signal relay poll failed: "
                    f"reason=invalid_json endpoint={endpoint} body={_trim_text(response.text, 200)!r}"
                )
            return

        if not isinstance(payload, dict):
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade(
                    "Signal relay poll failed: "
                    f"reason=invalid_payload_type endpoint={endpoint} payload_type={type(payload).__name__}"
                )
            return

        if payload.get("ok") is not True:
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade(
                    "Signal relay poll failed: "
                    f"reason=relay_not_ok endpoint={endpoint} payload={payload!r}"
                )
            return

        raw_events = payload.get("events")
        if not isinstance(raw_events, list):
            now = time.time()
            if now - self._signal_relay_last_poll_error_log_at >= SIGNAL_RELAY_POLL_ERROR_LOG_THROTTLE_SEC:
                self._signal_relay_last_poll_error_log_at = now
                _log_trade(
                    "Signal relay poll failed: "
                    f"reason=invalid_events_type endpoint={endpoint} events_type={type(raw_events).__name__}"
                )
            return

        next_after_id = max(0, self._safe_int(payload.get("next_after_id")))
        latest_event_id = max(0, self._safe_int(payload.get("latest_event_id")))
        accepted_count = 0
        skipped_count = 0
        max_event_id_seen = previous_offset

        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                skipped_count += 1
                continue
            event_id = max(0, self._safe_int(raw_event.get("event_id")))
            if event_id > max_event_id_seen:
                max_event_id_seen = event_id
            channel_id = self._safe_int(raw_event.get("channel_id"))
            if channel_id not in allowed_channel_ids:
                skipped_count += 1
                continue
            message_id = self._safe_int(raw_event.get("message_id"))
            if message_id <= 0:
                skipped_count += 1
                continue
            message_text = str(raw_event.get("message_text") or "").strip()
            if not message_text:
                skipped_count += 1
                continue
            received_at_local = self._safe_int(raw_event.get("received_at_local")) or int(time.time())
            self._enqueue_signal_event(
                {
                    "channel_id": int(channel_id),
                    "message_id": int(message_id),
                    "message_text": message_text,
                    "received_at_local": int(received_at_local),
                }
            )
            accepted_count += 1

        synced_offset = max(previous_offset, next_after_id, latest_event_id, max_event_id_seen)
        if synced_offset > previous_offset:
            self._signal_relay_update_offset = synced_offset

        if accepted_count > 0 or skipped_count > 0:
            _log_trade(
                "Signal relay poll success: "
                f"events={len(raw_events)} accepted={accepted_count} skipped={skipped_count} "
                f"previous_offset={previous_offset} synced_offset={self._signal_relay_update_offset} "
                f"next_after_id={next_after_id} latest_event_id={latest_event_id}"
            )

    def _poll_telegram_bot_updates(self) -> None:
        if self._signal_source_mode != SIGNAL_SOURCE_MODE_TELEGRAM:
            return
        if not self._telegram_bot_token:
            return
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
            last_update_id = int(self._telegram_update_offset)
            entry_channel_id = int(runtime.settings.entry_signal_channel_id)
            risk_channel_id = int(runtime.settings.risk_signal_channel_id)

        poll_result = poll_telegram_updates_with_logging(
            bot_token=self._telegram_bot_token,
            allowed_channel_ids=(entry_channel_id, risk_channel_id),
            last_update_id=last_update_id,
            poll_timeout_seconds=TELEGRAM_POLL_TIMEOUT_SEC,
            request_timeout_seconds=TELEGRAM_REQUEST_TIMEOUT_SEC,
            limit=TELEGRAM_POLL_LIMIT,
            loop_label="ui-signal-loop",
        )

        with self._auto_trade_runtime_lock:
            if poll_result.next_update_id > self._telegram_update_offset:
                self._telegram_update_offset = int(poll_result.next_update_id)

        if not poll_result.ok:
            now = time.time()
            if now - self._telegram_last_poll_error_log_at >= TELEGRAM_POLL_ERROR_LOG_THROTTLE_SEC:
                self._telegram_last_poll_error_log_at = now
                _log_trade(
                    "Telegram poll failed: "
                    f"reason={poll_result.reason_code} failure={poll_result.failure_reason} "
                    f"next_update_id={poll_result.next_update_id}"
                )
            return

        if poll_result.reason_code == "NO_UPDATES":
            return

        if poll_result.events:
            _log_trade(
                "Telegram poll success: "
                f"events={len(poll_result.events)} next_update_id={poll_result.next_update_id}"
            )
        for event in poll_result.events:
            self._enqueue_signal_event(
                {
                    "channel_id": int(event.channel_id),
                    "message_id": int(event.message_id),
                    "message_text": str(event.message_text),
                    "received_at_local": int(event.received_at_local),
                }
            )

    def _poll_signal_inbox_file(self) -> None:
        if not AUTO_TRADE_SIGNAL_INBOX_PATH.exists():
            return
        try:
            with AUTO_TRADE_SIGNAL_INBOX_PATH.open("r", encoding="utf-8") as handle:
                handle.seek(self._signal_inbox_offset)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    self._signal_inbox_offset = handle.tell()
                    payload = line.strip()
                    if not payload:
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        _log_trade(f"Signal inbox invalid JSON skipped: {payload!r}")
                        continue
                    if not isinstance(event, dict):
                        _log_trade(f"Signal inbox invalid payload skipped: {payload!r}")
                        continue
                    if "channel_id" not in event or "message_id" not in event or "message_text" not in event:
                        _log_trade(f"Signal inbox missing required keys skipped: {payload!r}")
                        continue
                    normalized = {
                        "channel_id": int(event["channel_id"]),
                        "message_id": int(event["message_id"]),
                        "message_text": str(event["message_text"]),
                        "received_at_local": int(event.get("received_at_local", int(time.time()))),
                    }
                    self._enqueue_signal_event(normalized)
        except Exception as exc:
            _log_trade(f"Signal inbox poll failed: path={AUTO_TRADE_SIGNAL_INBOX_PATH} error={exc!r}")

    def _process_signal_event(self, event: Mapping[str, object]) -> bool:
        channel_id = int(event.get("channel_id", 0))
        message_id = int(event.get("message_id", 0))
        message_text = str(event.get("message_text", ""))
        received_at_local = int(event.get("received_at_local", int(time.time())))
        risk_market_exit_submitted = False
        cancel_entry_reset_ready = True
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        runtime_before_update = runtime

        if channel_id == runtime.settings.entry_signal_channel_id:
            leading_preview = parse_leading_market_message(message_text)
            preview_symbol = ""
            if leading_preview.ok and leading_preview.data is not None:
                preview_symbol = leading_preview.data.symbol
            exchange_info = self._fetch_exchange_info_snapshot()
            candles = self._fetch_recent_3m_candles(preview_symbol) if preview_symbol else []
            updated, result = process_telegram_message(
                runtime,
                channel_id=channel_id,
                message_id=message_id,
                message_text=message_text,
                received_at_local=received_at_local,
                exchange_info=exchange_info,
                candles=candles,
                entry_mode=self._selected_entry_mode(),
                loop_label="signal-loop-leading",
            )
        elif channel_id == runtime.settings.risk_signal_channel_id:
            risk_context = self._build_risk_context(message_text, runtime.active_symbol)
            updated, result = process_telegram_message(
                runtime,
                channel_id=channel_id,
                message_id=message_id,
                message_text=message_text,
                received_at_local=received_at_local,
                risk_context=risk_context,
                loop_label="signal-loop-risk",
            )
        else:
            updated, result = process_telegram_message(
                runtime,
                channel_id=channel_id,
                message_id=message_id,
                message_text=message_text,
                received_at_local=received_at_local,
                loop_label="signal-loop-unknown",
            )

        with self._auto_trade_runtime_lock:
            self._orchestrator_runtime = updated
            if result.message_type == "LEADING" and result.handled and result.symbol:
                symbol = str(result.symbol).strip().upper()
                self._second_entry_skip_latch.discard(symbol)
                self._second_entry_fully_filled_symbols.discard(symbol)
                self._phase1_tp_filled_symbols.discard(symbol)
                self._entry_order_ref_by_symbol.pop(symbol, None)
                self._clear_entry_cancel_sync_guard(symbol)
                self._last_open_exit_order_ids_by_symbol.pop(symbol, None)
                self._oco_last_filled_exit_order_by_symbol.pop(symbol, None)
            self._sync_recovery_state_from_orchestrator_locked()
        if result.message_type == "RISK" and result.handled:
            risk_market_exit_submitted, cancel_entry_reset_ready = self._execute_risk_signal_actions(
                result=result,
                loop_label="signal-loop-risk-actions",
            )
            if result.reset_state and result.cancel_entry_orders and not cancel_entry_reset_ready:
                with self._auto_trade_runtime_lock:
                    current = self._orchestrator_runtime
                    self._orchestrator_runtime = replace(
                        runtime_before_update,
                        last_message_ids=dict(current.last_message_ids),
                        cooldown_by_symbol=dict(current.cooldown_by_symbol),
                        received_at_by_symbol=dict(current.received_at_by_symbol),
                        message_id_by_symbol=dict(current.message_id_by_symbol),
                    )
                    self._sync_recovery_state_from_orchestrator_locked()
                _log_trade(
                    "Risk reset deferred: "
                    f"channel_id={channel_id} message_id={message_id} "
                    f"symbol={result.symbol or '-'} reason=entry_cancel_not_confirmed"
                )
        self._persist_auto_trade_runtime()
        _log_trade(
            "Signal processed: "
            f"channel_id={channel_id} message_id={message_id} handled={result.handled} "
            f"type={result.message_type} reason={result.reason_code} failure={result.failure_reason} "
            f"symbol={result.symbol or '-'} action={result.action_code}"
        )
        return risk_market_exit_submitted

    def _selected_entry_mode(self) -> str:
        risk_filter = (self.risk_filter_dropdown.get() or "").strip()
        return "CONSERVATIVE" if risk_filter == "보수적" else "AGGRESSIVE"

    def _run_trigger_cycle_once(self) -> None:
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        if not runtime.pending_trigger_candidates:
            return

        symbols = sorted(runtime.pending_trigger_candidates.keys())
        filter_rules = self._build_filter_rules_by_symbols(symbols)
        if len(filter_rules) != len(symbols):
            missing = sorted(set(symbols) - set(filter_rules))
            _log_trade(f"Trigger cycle skipped: missing_filter_rules={','.join(missing)}")
            return
        now = int(time.time())
        runtime_with_price = runtime
        mark_prices: dict[str, float] = {}
        for symbol in symbols:
            read = get_mark_price_with_logging(
                runtime_with_price.price_state,
                symbol=symbol,
                now=now,
                ws_stale_fallback_seconds=runtime.settings.ws_stale_fallback_seconds,
                loop_label="signal-loop-trigger-price-read",
            )
            runtime_with_price = replace(runtime_with_price, price_state=read.state)
            if read.mark_price is not None and read.mark_price > 0:
                mark_prices[symbol] = float(read.mark_price)
        if len(mark_prices) != len(symbols):
            missing = sorted(set(symbols) - set(mark_prices))
            _log_trade(f"Trigger cycle skipped: missing_mark_prices={','.join(missing)}")
            with self._auto_trade_runtime_lock:
                self._orchestrator_runtime = runtime_with_price
                self._sync_recovery_state_from_orchestrator_locked()
            return

        wallet_balance = self._wallet_balance
        if wallet_balance is None:
            fetched = self._fetch_futures_balance(loop_label="signal-loop-trigger-wallet-balance")
            wallet_balance = fetched if fetched is not None else 0.0
        available_balance = self._fetch_futures_available_balance(
            loop_label="signal-loop-trigger-available-balance"
        )
        if available_balance is None:
            available_balance = wallet_balance
        position_mode = runtime.position_mode
        if position_mode not in ("ONE_WAY", "HEDGE"):
            position_mode = self._fetch_position_mode()
        if position_mode not in ("ONE_WAY", "HEDGE"):
            _log_trade(
                "Trigger cycle blocked: unresolved position mode, "
                "candidate-level rejection will be applied."
            )
            updated, result = run_trigger_entry_cycle(
                runtime_with_price,
                mark_prices=mark_prices,
                wallet_balance_usdt=float(wallet_balance),
                available_usdt=float(available_balance),
                filter_rules_by_symbol=filter_rules,
                # Position mode is unresolved; pre-order hook will reject before pipeline execution.
                position_mode="ONE_WAY",
                create_call=self._gateway_create_order_call,
                has_open_entry_order_for_symbol=self._has_open_entry_order_for_symbol,
                pre_order_setup=self._reject_pre_order_when_position_mode_unknown,
                loop_label="signal-loop-trigger-mode-unknown",
            )
            with self._auto_trade_runtime_lock:
                self._orchestrator_runtime = updated
                self._sync_recovery_state_from_orchestrator_locked()
            self._persist_auto_trade_runtime()
            _log_trade(
                "Trigger cycle processed under unresolved position mode: "
                f"attempted={result.attempted} success={result.success} reason={result.reason_code} "
                f"pipeline={result.pipeline_reason_code} symbol={result.selected_symbol} "
                f"trigger={result.selected_trigger_kind}"
            )
            return

        updated, result = run_trigger_entry_cycle(
            runtime_with_price,
            mark_prices=mark_prices,
            wallet_balance_usdt=float(wallet_balance),
            available_usdt=float(available_balance),
            filter_rules_by_symbol=filter_rules,
            position_mode=position_mode,
            create_call=self._gateway_create_order_call,
            has_open_entry_order_for_symbol=self._has_open_entry_order_for_symbol,
            pre_order_setup=self._run_pre_order_setup_hook,
            loop_label="signal-loop-trigger",
        )
        if (
            result.success
            and result.selected_symbol
            and result.selected_trigger_kind in ("FIRST_ENTRY", "SECOND_ENTRY")
        ):
            self._arm_entry_cancel_sync_guard(
                symbol=str(result.selected_symbol),
                trigger_kind=str(result.selected_trigger_kind),
                loop_label="signal-loop-trigger",
            )
        with self._auto_trade_runtime_lock:
            self._orchestrator_runtime = updated
            self._sync_recovery_state_from_orchestrator_locked()
        if result.selected_trigger_kind == "SECOND_ENTRY" and result.selected_symbol:
            symbol = str(result.selected_symbol).strip().upper()
            if result.success:
                self._second_entry_skip_latch.discard(symbol)
            else:
                self._second_entry_skip_latch.add(symbol)
                _log_trade(
                    "Second-entry trigger skipped and latched: "
                    f"symbol={symbol} pipeline_reason={result.pipeline_reason_code}"
                )
        self._persist_auto_trade_runtime()
        _log_trade(
            "Trigger cycle processed: "
            f"attempted={result.attempted} success={result.success} "
            f"reason={result.reason_code} pipeline={result.pipeline_reason_code} "
            f"symbol={result.selected_symbol} trigger={result.selected_trigger_kind}"
        )

    def _arm_entry_cancel_sync_guard(
        self,
        *,
        symbol: str,
        trigger_kind: str,
        loop_label: str,
    ) -> None:
        target = str(symbol or "").strip().upper()
        if not target:
            return
        expires_at = time.time() + float(ENTRY_CANCEL_SYNC_GUARD_SEC)
        self._entry_cancel_sync_guard_store()[target] = expires_at
        _log_trade(
            "Entry cancel sync guard armed: "
            f"symbol={target} trigger={str(trigger_kind or '').strip().upper() or '-'} "
            f"guard_sec={ENTRY_CANCEL_SYNC_GUARD_SEC:.1f} expires_at={expires_at:.2f} "
            f"loop={loop_label}"
        )

    def _entry_cancel_sync_guard_store(self) -> dict[str, float]:
        store = getattr(self, "_entry_cancel_sync_guard_until_by_symbol", None)
        if isinstance(store, dict):
            return store
        store = {}
        setattr(self, "_entry_cancel_sync_guard_until_by_symbol", store)
        return store

    def _clear_entry_cancel_sync_guard(self, symbol: str) -> None:
        target = str(symbol or "").strip().upper()
        if not target:
            return
        self._entry_cancel_sync_guard_store().pop(target, None)

    def _entry_cancel_sync_guard_remaining(self, symbol: str) -> float:
        target = str(symbol or "").strip().upper()
        if not target:
            return 0.0
        store = self._entry_cancel_sync_guard_store()
        expires_at = float(store.get(target, 0.0))
        if expires_at <= 0.0:
            return 0.0
        remaining = expires_at - time.time()
        if remaining <= 0.0:
            store.pop(target, None)
            return 0.0
        return float(remaining)

    def _has_open_entry_order_for_symbol(self, symbol: str) -> bool:
        target = str(symbol or "").strip().upper()
        if not target:
            return False
        open_orders = self._fetch_open_orders() or []
        entry_orders, _ = self._classify_orders_for_symbol(target, open_orders)
        has_open_entry_order = bool(entry_orders)
        if has_open_entry_order:
            _log_trade(
                "Second-entry gate blocked by open entry orders: "
                f"symbol={target} entry_order_count={len(entry_orders)} open_order_count={len(open_orders)}"
            )
        return has_open_entry_order

    def _build_filter_rules_by_symbols(self, symbols: list[str]) -> dict[str, SymbolFilterRules]:
        rules: dict[str, SymbolFilterRules] = {}
        for symbol in symbols:
            rule = self._get_symbol_filter_rule(symbol)
            if rule is not None:
                rules[symbol] = rule
        return rules

    def _get_symbol_filter_rule(self, symbol: str) -> Optional[SymbolFilterRules]:
        exchange_info = self._fetch_exchange_info_snapshot()
        symbols = exchange_info.get("symbols", [])
        if not isinstance(symbols, list):
            return None
        target = (symbol or "").strip().upper()
        for item in symbols:
            if not isinstance(item, dict):
                continue
            if str(item.get("symbol", "")).upper() != target:
                continue
            tick_size = None
            step_size = None
            min_qty = None
            min_notional = None
            for filt in item.get("filters", []):
                if not isinstance(filt, dict):
                    continue
                if filt.get("filterType") == "PRICE_FILTER":
                    tick_size = self._safe_float(filt.get("tickSize"))
                elif filt.get("filterType") == "LOT_SIZE":
                    step_size = self._safe_float(filt.get("stepSize"))
                    min_qty = self._safe_float(filt.get("minQty"))
                elif filt.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL"):
                    min_notional = self._safe_float(filt.get("notional") or filt.get("minNotional"))
            if tick_size and step_size and min_qty:
                return SymbolFilterRules(
                    tick_size=float(tick_size),
                    step_size=float(step_size),
                    min_qty=float(min_qty),
                    min_notional=float(min_notional) if min_notional is not None else None,
                )
        return None

    def _fetch_mark_prices(self, symbols: list[str]) -> dict[str, float]:
        result: dict[str, float] = {}
        for symbol in symbols:
            payload = self._binance_public_get(
                "https://fapi.binance.com",
                FUTURES_LAST_PRICE_PATH,
                {"symbol": symbol},
            )
            if not isinstance(payload, dict):
                continue
            mark_price = self._safe_float(
                payload.get("price")
                or payload.get("lastPrice")
                or payload.get("markPrice")
            )
            if mark_price is None or mark_price <= 0:
                continue
            result[symbol] = float(mark_price)
        return result

    def _build_risk_context(self, message_text: str, active_symbol: Optional[str]) -> dict[str, object]:
        symbol = (active_symbol or "").strip().upper()
        parsed = parse_risk_management_message(message_text)
        if parsed.ok and parsed.data is not None:
            symbol = parsed.data.symbol
        exchange_info = self._fetch_exchange_info_snapshot()
        positions = self._fetch_open_positions() or []
        open_orders = self._fetch_open_orders() or []

        target_position = None
        if symbol:
            for item in positions:
                if str(item.get("symbol", "")).upper() == symbol:
                    target_position = item
                    break
        if target_position is None and positions:
            target_position = positions[0]
            symbol = str(target_position.get("symbol", "")).upper()

        has_position = target_position is not None
        avg_entry_price = self._safe_float((target_position or {}).get("entryPrice")) or 0.0
        mark_price = self._safe_float((target_position or {}).get("markPrice")) or 0.0
        if mark_price <= 0 and symbol:
            payload = self._binance_public_get("https://fapi.binance.com", FUTURES_LAST_PRICE_PATH, {"symbol": symbol})
            if isinstance(payload, dict):
                mark_price = (
                    self._safe_float(
                        payload.get("price")
                        or payload.get("lastPrice")
                        or payload.get("markPrice")
                    )
                    or 0.0
                )

        has_open_entry_order = False
        has_tp_order = False
        for order in open_orders:
            if not isinstance(order, dict):
                continue
            if str(order.get("symbol", "")).upper() != symbol:
                continue
            order_type = str(order.get("type", "")).upper()
            reduce_only = self._to_bool(order.get("reduceOnly"))
            close_position = self._to_bool(order.get("closePosition"))
            side = str(order.get("side", "")).upper()
            price = self._safe_float(order.get("price"))
            if (
                order_type in ("TAKE_PROFIT", "TAKE_PROFIT_MARKET")
                or (order_type == "LIMIT" and side == "BUY" and reduce_only)
                or (
                    order_type == "LIMIT"
                    and side == "BUY"
                    and price is not None
                    and avg_entry_price > 0
                    and price < avg_entry_price
                )
            ):
                has_tp_order = True
            if side == "SELL" and not reduce_only and not close_position:
                has_open_entry_order = True
        second_entry_fully_filled = False
        if symbol:
            second_entry_fully_filled = symbol in self._second_entry_fully_filled_symbols
            if not second_entry_fully_filled:
                symbol_entry_orders, _ = self._classify_orders_for_symbol(symbol, open_orders)
                second_entry_fully_filled = (
                    self._orchestrator_runtime.symbol_state == "PHASE2"
                    and not symbol_entry_orders
                )

        return {
            "avg_entry_price": float(avg_entry_price),
            "mark_price": float(mark_price if mark_price > 0 else avg_entry_price),
            "has_position": bool(has_position),
            "has_open_entry_order": bool(has_open_entry_order),
            "has_tp_order": bool(has_tp_order),
            "second_entry_fully_filled": bool(second_entry_fully_filled),
            "exchange_info": exchange_info,
        }

    def _run_fill_sync_pass(
        self,
        *,
        open_orders: list[dict],
        positions: list[dict],
        risk_market_exit_in_same_loop: bool,
        loop_label: str,
    ) -> None:
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime

        account_transition = update_account_activity_with_logging(
            runtime.global_state,
            has_any_position=bool(positions),
            has_any_open_order=bool(open_orders),
        )
        current = replace(runtime, global_state=account_transition.current)
        current, open_orders = self._retry_pending_oco_cancellations(
            current,
            open_orders=open_orders,
            loop_label=f"{loop_label}-oco-retry",
        )
        account_transition = update_account_activity_with_logging(
            current.global_state,
            has_any_position=bool(positions),
            has_any_open_order=bool(open_orders),
        )
        current = replace(current, global_state=account_transition.current)
        if self._last_dust_symbols:
            self._cancel_open_orders_for_symbols(
                symbols=sorted(self._last_dust_symbols),
                loop_label=f"{loop_label}-dust-cleanup",
            )
            open_orders = self._fetch_open_orders() or []
            account_transition = update_account_activity_with_logging(
                current.global_state,
                has_any_position=bool(positions),
                has_any_open_order=bool(open_orders),
            )
            current = replace(current, global_state=account_transition.current)
            _log_trade(
                "Dust cleanup applied: "
                f"symbols={','.join(sorted(self._last_dust_symbols))}"
            )
        active_symbol = self._resolve_active_symbol_snapshot(current, open_orders=open_orders, positions=positions)
        if active_symbol and active_symbol != (current.active_symbol or ""):
            current = replace(current, active_symbol=active_symbol)
            _log_trade(f"Active symbol synchronized from exchange snapshot: symbol={active_symbol}")

        if active_symbol:
            current = self._sync_entry_fill_by_symbol(
                current,
                symbol=active_symbol,
                open_orders=open_orders,
                positions=positions,
                loop_label=loop_label,
            )
            current = self._run_exit_supervision(
                current,
                symbol=active_symbol,
                open_orders=open_orders,
                positions=positions,
                risk_market_exit_in_same_loop=risk_market_exit_in_same_loop,
                loop_label=loop_label,
            )
            current, open_orders, positions = self._handle_position_quantity_reconciliation(
                current,
                symbol=active_symbol,
                open_orders=open_orders,
                positions=positions,
                loop_label=f"{loop_label}-position-sync",
            )
            active_symbol = str(current.active_symbol or "").strip().upper()

            has_position = self._get_symbol_position(positions, active_symbol) is not None
            entry_orders, exit_orders = self._classify_orders_for_symbol(active_symbol, open_orders)
            if (
                current.symbol_state in ("ENTRY_ORDER", "PHASE1", "PHASE2")
                and not has_position
                and not entry_orders
                and not exit_orders
            ):
                guard_remaining = self._entry_cancel_sync_guard_remaining(active_symbol)
                if current.symbol_state == "ENTRY_ORDER" and guard_remaining > 0.0:
                    _log_trade(
                        "Fill sync fallback reset deferred: "
                        f"symbol={active_symbol} state={current.symbol_state} "
                        f"reason=entry_cancel_sync_guard remaining_sec={guard_remaining:.2f}"
                    )
                elif not self._has_recent_account_snapshot():
                    _log_trade(
                        "Fill sync fallback reset deferred: "
                        f"symbol={active_symbol} state={current.symbol_state} "
                        "reason=account_snapshot_unavailable"
                    )
                else:
                    _log_trade(
                        "Fill sync fallback reset: "
                        f"symbol={active_symbol} state={current.symbol_state} reason=no_position_no_orders"
                    )
                    current = replace(
                        current,
                        symbol_state="IDLE",
                        active_symbol=None,
                        pending_trigger_candidates={},
                        second_entry_order_pending=False,
                    )
                    self._entry_order_ref_by_symbol.pop(active_symbol, None)
                    self._clear_entry_cancel_sync_guard(active_symbol)
                    self._second_entry_skip_latch.discard(active_symbol)
                    self._second_entry_fully_filled_symbols.discard(active_symbol)
                    self._phase1_tp_filled_symbols.discard(active_symbol)
                    self._last_open_exit_order_ids_by_symbol.pop(active_symbol, None)
                    self._oco_last_filled_exit_order_by_symbol.pop(active_symbol, None)

        if current != runtime:
            with self._auto_trade_runtime_lock:
                self._orchestrator_runtime = current
                self._sync_recovery_state_from_orchestrator_locked()

    def _retry_pending_oco_cancellations(
        self,
        runtime: AutoTradeRuntime,
        *,
        open_orders: list[dict],
        loop_label: str,
    ) -> tuple[AutoTradeRuntime, list[dict]]:
        if not self._pending_oco_retry_symbols:
            return runtime, open_orders

        current = runtime
        for symbol in sorted(self._pending_oco_retry_symbols):
            _, exit_orders = self._classify_orders_for_symbol(symbol, open_orders)
            exit_order_ids = [
                self._safe_int(order.get("orderId"))
                for order in exit_orders
                if self._safe_int(order.get("orderId")) > 0
            ]
            if not exit_order_ids:
                self._pending_oco_retry_symbols.discard(symbol)
                _log_trade(
                    "OCO retry symbol cleared: "
                    f"symbol={symbol} reason=no_remaining_exit_orders loop={loop_label}"
                )
                continue

            failed_ids: list[int] = []
            for order_id in sorted(exit_order_ids):
                success = self._cancel_order_with_gateway(
                    symbol=symbol,
                    order_id=int(order_id),
                    loop_label=f"{loop_label}-{symbol}-order-{order_id}",
                )
                if not success:
                    failed_ids.append(int(order_id))

            if failed_ids:
                _log_trade(
                    "OCO retry pending: "
                    f"symbol={symbol} failed_order_ids={','.join(str(value) for value in failed_ids)} "
                    f"loop={loop_label}"
                )
                continue

            self._pending_oco_retry_symbols.discard(symbol)
            open_orders = self._fetch_open_orders() or []
            _log_trade(
                "OCO retry completed: "
                f"symbol={symbol} canceled_count={len(exit_order_ids)} loop={loop_label}"
            )

        if current.new_orders_locked and not self._pending_oco_retry_symbols:
            current = replace(current, new_orders_locked=False)
            _log_trade(f"OCO retry lock released: loop={loop_label}")
        return current, open_orders

    def _handle_position_quantity_reconciliation(
        self,
        runtime: AutoTradeRuntime,
        *,
        symbol: str,
        open_orders: list[dict],
        positions: list[dict],
        loop_label: str,
    ) -> tuple[AutoTradeRuntime, list[dict], list[dict]]:
        target = str(symbol or "").strip().upper()
        if not target:
            return runtime, open_orders, positions

        position = self._get_symbol_position(positions, target)
        current_qty = abs(self._safe_float(position.get("positionAmt")) or 0.0) if position is not None else 0.0
        current_entry = self._safe_float(position.get("entryPrice")) if position is not None else None
        current_entry_price: Optional[float] = (
            float(current_entry) if current_entry is not None and float(current_entry) > 0.0 else None
        )
        previous_qty = self._last_position_qty_by_symbol.get(target)
        previous_entry_price = self._last_position_entry_price_by_symbol.get(target)

        def _sync_position_baseline() -> None:
            self._last_position_qty_by_symbol[target] = current_qty
            if current_entry_price is not None:
                self._last_position_entry_price_by_symbol[target] = float(current_entry_price)
            else:
                self._last_position_entry_price_by_symbol.pop(target, None)

        if previous_qty is None:
            _sync_position_baseline()
            if current_qty > 1e-12:
                self._position_zero_confirm_streak_by_symbol.pop(target, None)
            return runtime, open_orders, positions

        if abs(float(current_qty) - float(previous_qty)) <= 1e-12:
            _sync_position_baseline()
            if current_qty > 1e-12:
                self._position_zero_confirm_streak_by_symbol.pop(target, None)
            return runtime, open_orders, positions

        _log_trade(
            "Position quantity change detected: "
            f"symbol={target} previous_qty={previous_qty} current_qty={current_qty} "
            f"state={runtime.symbol_state} loop={loop_label}"
        )

        if current_qty <= 1e-12:
            if runtime.symbol_state == "ENTRY_ORDER":
                entry_orders, _ = self._classify_orders_for_symbol(target, open_orders)
                if entry_orders:
                    _sync_position_baseline()
                    self._position_zero_confirm_streak_by_symbol.pop(target, None)
                    _log_trade(
                        "Position quantity zero transition ignored during entry wait: "
                        f"symbol={target} previous_qty={previous_qty} current_qty={current_qty} "
                        f"entry_order_count={len(entry_orders)} state={runtime.symbol_state} "
                        f"reason=entry_order_pending loop={loop_label}"
                    )
                    return runtime, open_orders, positions
            previous_streak = int(self._position_zero_confirm_streak_by_symbol.pop(target, 0))
            if previous_streak > 0:
                _log_trade(
                    "Position zero confirmation bypassed for immediate cancel: "
                    f"symbol={target} previous_streak={previous_streak} "
                    f"state={runtime.symbol_state} loop={loop_label}"
                )
            canceled_all, cancel_reason = self._cancel_all_open_orders_for_symbol(
                symbol=target,
                loop_label=f"{loop_label}-qty-zero-cancel-all",
            )
            _log_trade(
                "Position zero immediate cancel-all result: "
                f"symbol={target} success={canceled_all} reason={cancel_reason} "
                f"state={runtime.symbol_state} loop={loop_label}"
            )
            if not canceled_all:
                self._cancel_open_orders_for_symbols(
                    symbols=[target],
                    loop_label=f"{loop_label}-qty-zero-cancel-fallback",
                )
            open_orders = self._fetch_open_orders() or []
            refreshed_positions = self._fetch_open_positions() or []
            self._entry_order_ref_by_symbol.pop(target, None)
            self._clear_entry_cancel_sync_guard(target)
            self._second_entry_skip_latch.discard(target)
            self._second_entry_fully_filled_symbols.discard(target)
            self._phase1_tp_filled_symbols.discard(target)
            self._last_open_exit_order_ids_by_symbol.pop(target, None)
            self._oco_last_filled_exit_order_by_symbol.pop(target, None)
            self._pending_oco_retry_symbols.discard(target)
            self._last_position_qty_by_symbol.pop(target, None)
            self._last_position_entry_price_by_symbol.pop(target, None)
            self._tp_trigger_submit_guard_by_symbol.pop(target, None)
            _log_trade(
                "Exit partial tracker cleared on position-zero reset: "
                f"symbol={target} reason=POSITION_ZERO_RESET loop={loop_label}"
            )
            current = replace(
                runtime,
                symbol_state="IDLE",
                active_symbol=None,
                pending_trigger_candidates={},
                second_entry_order_pending=False,
                new_orders_locked=runtime.new_orders_locked and bool(self._pending_oco_retry_symbols),
                exit_partial_tracker=runtime.exit_partial_tracker.__class__(),
            )
            account_transition = update_account_activity_with_logging(
                current.global_state,
                has_any_position=bool(refreshed_positions),
                has_any_open_order=bool(open_orders),
            )
            current = replace(current, global_state=account_transition.current)
            _log_trade(
                "Position quantity reconciled to zero: "
                f"symbol={target} state_reset=IDLE open_order_count={len(open_orders)} loop={loop_label}"
            )
            return current, open_orders, refreshed_positions

        cleared_streak = int(self._position_zero_confirm_streak_by_symbol.pop(target, 0))
        if cleared_streak > 0:
            _log_trade(
                "Position zero confirmation cleared: "
                f"symbol={target} streak={cleared_streak} state={runtime.symbol_state} loop={loop_label}"
            )

        if runtime.symbol_state not in ("PHASE1", "PHASE2"):
            _sync_position_baseline()
            self._phase1_tp_filled_symbols.discard(target)
            self._tp_trigger_submit_guard_by_symbol.pop(target, None)
            _log_trade(
                "Position quantity change noted without exit rebuild: "
                f"symbol={target} state={runtime.symbol_state} loop={loop_label}"
            )
            return runtime, open_orders, positions

        if self._should_defer_exit_rebuild_for_partial_wait(
            runtime,
            symbol=target,
            open_orders=open_orders,
            loop_label=loop_label,
        ):
            _sync_position_baseline()
            self._tp_trigger_submit_guard_by_symbol.pop(target, None)
            _log_trade(
                "Position quantity change baseline updated: "
                f"symbol={target} current_qty={current_qty} reason=exit_partial_waiting loop={loop_label}"
            )
            return runtime, open_orders, positions

        # Quantity-only reduction from TP fill should not tear down remaining exits.
        entry_change_tolerance = 1e-12
        filter_rule = self._get_symbol_filter_rule(target)
        if filter_rule is not None:
            entry_change_tolerance = max(float(filter_rule.tick_size) * 0.55, 1e-12)
        elif current_entry_price is not None:
            entry_change_tolerance = max(abs(float(current_entry_price)) * 1e-6, 1e-12)
        elif previous_entry_price is not None:
            entry_change_tolerance = max(abs(float(previous_entry_price)) * 1e-6, 1e-12)
        entry_price_changed = True
        if current_entry_price is not None and previous_entry_price is not None:
            entry_price_changed = (
                abs(float(current_entry_price) - float(previous_entry_price)) > float(entry_change_tolerance)
            )
        if not entry_price_changed:
            _sync_position_baseline()
            _log_trade(
                "Position quantity change noted without exit rebuild: "
                f"symbol={target} previous_qty={previous_qty} current_qty={current_qty} "
                f"previous_entry={previous_entry_price} current_entry={current_entry_price} "
                f"reason=avg_entry_unchanged loop={loop_label}"
            )
            return runtime, open_orders, positions

        active_exit_templates = self._collect_active_exit_rebuild_templates(
            symbol=target,
            position=position or {},
            open_orders=open_orders,
            loop_label=f"{loop_label}-template-scan",
        )

        self._cancel_exit_orders_for_symbol(
            symbol=target,
            open_orders=open_orders,
            loop_label=f"{loop_label}-qty-change-cancel-exit",
        )
        open_orders = self._fetch_open_orders() or []
        refreshed_positions = self._fetch_open_positions() or positions
        refreshed_position = self._get_symbol_position(refreshed_positions, target)
        if refreshed_position is not None:
            rebuilt, rebuild_reason = self._submit_recovery_exit_orders_for_symbol(
                symbol=target,
                position=refreshed_position,
                runtime_symbol_state=runtime.symbol_state,
                active_exit_templates=active_exit_templates,
                loop_label=f"{loop_label}-exit-rebuild",
            )
            _log_trade(
                "Position quantity change exit rebuild attempted: "
                f"symbol={target} success={rebuilt} reason={rebuild_reason} "
                f"state={runtime.symbol_state} loop={loop_label}"
            )
            open_orders = self._fetch_open_orders() or open_orders
        else:
            _log_trade(
                "Position quantity change exit rebuild skipped: "
                f"symbol={target} reason=position_not_found_after_refresh loop={loop_label}"
            )

        _sync_position_baseline()
        account_transition = update_account_activity_with_logging(
            runtime.global_state,
            has_any_position=bool(refreshed_positions),
            has_any_open_order=bool(open_orders),
        )
        updated_runtime = replace(runtime, global_state=account_transition.current)
        return updated_runtime, open_orders, refreshed_positions

    def _should_defer_exit_rebuild_for_partial_wait(
        self,
        runtime: AutoTradeRuntime,
        *,
        symbol: str,
        open_orders: list[dict],
        loop_label: str,
    ) -> bool:
        tracker = runtime.exit_partial_tracker
        if not tracker.active:
            return False
        tracked_order_id = self._safe_int(tracker.order_id)
        if tracked_order_id <= 0:
            return False
        _, exit_orders = self._classify_orders_for_symbol(symbol, open_orders)
        tracked_order: Optional[dict[str, Any]] = None
        for row in exit_orders:
            order_id = self._safe_int(row.get("orderId"))
            if order_id == tracked_order_id:
                tracked_order = row
                break
        if tracked_order is None:
            return False
        decision = evaluate_exit_five_second_rule(
            tracker,
            is_exit_order=True,
            now=int(time.time()),
            stall_seconds=5,
            risk_market_exit_in_same_loop=False,
        )
        if decision.reason_code != "EXIT_PARTIAL_WAITING":
            return False
        tracked_status = str(tracked_order.get("status") or "").strip().upper() or "NEW"
        tracked_executed_qty = self._safe_float(tracked_order.get("executedQty")) or 0.0
        _log_trade(
            "Position quantity change exit rebuild deferred: "
            f"symbol={symbol} order_id={tracked_order_id} order_status={tracked_status} "
            f"executed_qty={tracked_executed_qty} remaining_seconds={decision.remaining_seconds} "
            f"reason={decision.reason_code} loop={loop_label}"
        )
        return True

    def _resolve_active_symbol_snapshot(
        self,
        runtime: AutoTradeRuntime,
        *,
        open_orders: list[dict],
        positions: list[dict],
    ) -> str:
        if runtime.active_symbol:
            return str(runtime.active_symbol).strip().upper()
        for row in positions:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol:
                return symbol
        for row in open_orders:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol:
                return symbol
        return ""

    def _sync_entry_fill_by_symbol(
        self,
        runtime: AutoTradeRuntime,
        *,
        symbol: str,
        open_orders: list[dict],
        positions: list[dict],
        loop_label: str,
    ) -> AutoTradeRuntime:
        current = runtime
        entry_orders, _ = self._classify_orders_for_symbol(symbol, open_orders)
        has_position = self._get_symbol_position(positions, symbol) is not None
        has_any_open_order = bool(open_orders)

        if current.symbol_state == "ENTRY_ORDER":
            first_status = self._infer_entry_order_status(
                symbol=symbol,
                entry_orders=entry_orders,
                has_position=has_position,
                loop_label=f"{loop_label}-first-query",
            )
            current, sync_result = sync_entry_fill_flow(
                current,
                phase="FIRST_ENTRY",
                order_status=first_status,
                has_position=has_position,
                has_any_open_order=has_any_open_order,
                loop_label=f"{loop_label}-first-sync",
            )
            _log_trade(
                "First-entry fill sync: "
                f"symbol={symbol} status={first_status} reason={sync_result.reason_code} "
                f"state_after={sync_result.symbol_state_after}"
            )

        if current.symbol_state in ("PHASE1", "PHASE2"):
            has_second_candidate = self._has_second_entry_candidate(current, symbol)
            should_sync_second = bool(current.second_entry_order_pending or has_second_candidate)
            if should_sync_second:
                second_status = self._infer_second_entry_order_status(
                    symbol=symbol,
                    entry_orders=entry_orders,
                    has_position=has_position,
                    second_entry_pending=current.second_entry_order_pending,
                    loop_label=f"{loop_label}-second-query",
                )
                if second_status is not None:
                    current, sync_result = sync_entry_fill_flow(
                        current,
                        phase="SECOND_ENTRY",
                        order_status=second_status,
                        has_position=has_position,
                        has_any_open_order=has_any_open_order,
                        loop_label=f"{loop_label}-second-sync",
                    )
                    _log_trade(
                        "Second-entry fill sync: "
                        f"symbol={symbol} status={second_status} reason={sync_result.reason_code} "
                        f"state_after={sync_result.symbol_state_after}"
                    )
                    if second_status in ("CANCELED", "EXPIRED", "REJECTED"):
                        self._second_entry_skip_latch.add(symbol)
                        self._second_entry_fully_filled_symbols.discard(symbol)
                    if second_status in ("FILLED", "PARTIALLY_FILLED"):
                        self._second_entry_skip_latch.discard(symbol)
                    if second_status == "FILLED":
                        self._second_entry_fully_filled_symbols.add(symbol)
                        self._phase1_tp_filled_symbols.discard(symbol)
                    elif second_status in ("PARTIALLY_FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                        self._second_entry_fully_filled_symbols.discard(symbol)

            current = self._register_second_entry_trigger_if_needed(
                current,
                symbol=symbol,
                positions=positions,
                loop_label=f"{loop_label}-register-second",
            )
        if current.symbol_state in ("IDLE", "ENTRY_ORDER", "PHASE1"):
            self._second_entry_fully_filled_symbols.discard(symbol)
        if current.symbol_state != "PHASE1":
            self._phase1_tp_filled_symbols.discard(symbol)

        return current

    def _classify_orders_for_symbol(
        self,
        symbol: str,
        open_orders: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        target = str(symbol or "").strip().upper()
        entry_orders: list[dict] = []
        exit_orders: list[dict] = []
        for row in open_orders:
            if str(row.get("symbol") or "").strip().upper() != target:
                continue
            side = str(row.get("side") or "").strip().upper()
            reduce_only = self._to_bool(row.get("reduceOnly"))
            close_position = self._to_bool(row.get("closePosition"))
            order_type = str(row.get("type") or "").strip().upper()
            is_stop_family = order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT")
            is_exit = bool(
                side == "BUY"
                or reduce_only
                or close_position
                or is_stop_family
            )
            if is_exit:
                exit_orders.append(row)
            else:
                entry_orders.append(row)
        return entry_orders, exit_orders

    def _infer_entry_order_status(
        self,
        *,
        symbol: str,
        entry_orders: list[dict],
        has_position: bool,
        loop_label: str,
    ) -> str:
        target = str(symbol or "").strip().upper()
        if entry_orders:
            self._clear_entry_cancel_sync_guard(target)
            latest = max(
                entry_orders,
                key=lambda row: (
                    self._safe_int(row.get("updateTime")),
                    self._safe_int(row.get("orderId")),
                ),
            )
            order_id = self._safe_int(latest.get("orderId"))
            if order_id > 0:
                self._entry_order_ref_by_symbol[target] = order_id
            statuses = {
                str(row.get("status") or "").strip().upper()
                for row in entry_orders
            }
            if "PARTIALLY_FILLED" in statuses:
                return "PARTIALLY_FILLED"
            if "NEW" in statuses:
                return "NEW"
            if "FILLED" in statuses:
                return "FILLED"
            if "CANCELED" in statuses:
                return "CANCELED"
            return "NEW"

        cached_order_id = self._entry_order_ref_by_symbol.get(target)
        if cached_order_id is not None:
            queried = self._query_order_status_by_id(
                symbol=target,
                order_id=int(cached_order_id),
                loop_label=loop_label,
            )
            if queried:
                if queried in ("NEW", "PARTIALLY_FILLED", "FILLED"):
                    self._clear_entry_cancel_sync_guard(target)
                if queried in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
                    self._entry_order_ref_by_symbol.pop(target, None)
                    self._clear_entry_cancel_sync_guard(target)
                return queried
        if has_position:
            self._clear_entry_cancel_sync_guard(target)
            return "FILLED"
        guard_remaining = self._entry_cancel_sync_guard_remaining(target)
        if guard_remaining > 0.0:
            _log_trade(
                "Entry fill sync canceled fallback deferred: "
                f"symbol={target} reason=entry_cancel_sync_guard "
                f"remaining_sec={guard_remaining:.2f} loop={loop_label}"
            )
            return "NEW"
        return "CANCELED"

    def _infer_second_entry_order_status(
        self,
        *,
        symbol: str,
        entry_orders: list[dict],
        has_position: bool,
        second_entry_pending: bool,
        loop_label: str,
    ) -> Optional[str]:
        target = str(symbol or "").strip().upper()
        if entry_orders:
            statuses = {
                str(row.get("status") or "").strip().upper()
                for row in entry_orders
            }
            latest = max(
                entry_orders,
                key=lambda row: (
                    self._safe_int(row.get("updateTime")),
                    self._safe_int(row.get("orderId")),
                ),
            )
            order_id = self._safe_int(latest.get("orderId"))
            if order_id > 0:
                self._entry_order_ref_by_symbol[target] = order_id
            if "PARTIALLY_FILLED" in statuses:
                return "PARTIALLY_FILLED"
            if "NEW" in statuses:
                return "NEW"
            if "FILLED" in statuses:
                return "FILLED"
            if "CANCELED" in statuses:
                return "CANCELED"
            return "NEW"

        if not second_entry_pending:
            return None

        cached_order_id = self._entry_order_ref_by_symbol.get(target)
        if cached_order_id is not None:
            queried = self._query_order_status_by_id(
                symbol=target,
                order_id=int(cached_order_id),
                loop_label=loop_label,
            )
            if queried:
                if queried in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
                    self._entry_order_ref_by_symbol.pop(target, None)
                    self._clear_entry_cancel_sync_guard(target)
                return queried
        return "FILLED" if has_position else "CANCELED"

    @staticmethod
    def _safe_int(value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _get_symbol_position(positions: list[dict], symbol: str) -> Optional[dict]:
        target = str(symbol or "").strip().upper()
        for row in positions:
            if str(row.get("symbol") or "").strip().upper() != target:
                continue
            return row
        return None

    @staticmethod
    def _has_second_entry_candidate(runtime: AutoTradeRuntime, symbol: str) -> bool:
        target = str(symbol or "").strip().upper()
        for key, candidate in runtime.pending_trigger_candidates.items():
            if str(key or "").strip().upper() != target:
                continue
            if str(candidate.trigger_kind or "").strip().upper() == "SECOND_ENTRY":
                return True
        return False

    def _register_second_entry_trigger_if_needed(
        self,
        runtime: AutoTradeRuntime,
        *,
        symbol: str,
        positions: list[dict],
        loop_label: str,
    ) -> AutoTradeRuntime:
        if runtime.symbol_state != "PHASE1":
            return runtime
        if runtime.second_entry_order_pending:
            return runtime
        target = str(symbol or "").strip().upper()
        if not target:
            return runtime
        if target in self._second_entry_skip_latch:
            return runtime
        if self._has_second_entry_candidate(runtime, target):
            return runtime
        position = self._get_symbol_position(positions, target)
        if position is None:
            return runtime
        avg_entry_price = self._safe_float(position.get("entryPrice"))
        if avg_entry_price is None or avg_entry_price <= 0:
            return runtime

        second_target = float(avg_entry_price) * (1.0 + float(runtime.settings.second_entry_percent) / 100.0)
        message_id = self._safe_int(runtime.message_id_by_symbol.get(target))
        if message_id <= 0:
            message_id = self._safe_int(runtime.last_message_ids.get(runtime.settings.entry_signal_channel_id))
        received_at = self._safe_int(runtime.received_at_by_symbol.get(target)) or int(time.time())
        pending = dict(runtime.pending_trigger_candidates)
        pending[target] = TriggerCandidate(
            symbol=target,
            trigger_kind="SECOND_ENTRY",
            target_price=float(second_target),
            received_at_local=int(received_at),
            message_id=int(message_id),
            entry_mode=self._selected_entry_mode(),
        )
        updated = replace(runtime, pending_trigger_candidates=pending)
        _log_trade(
            "Second-entry trigger registered: "
            f"symbol={target} avg_entry={avg_entry_price} second_target={second_target} "
            f"received_at={received_at} message_id={message_id} loop={loop_label}"
        )
        return updated

    def _cancel_orders_by_ids(
        self,
        *,
        symbol: str,
        order_ids: list[int],
        loop_label: str,
        reason: str,
    ) -> None:
        unique_ids = sorted({int(value) for value in order_ids if int(value) > 0})
        if not unique_ids:
            return
        _log_trade(
            "Canceling orders by policy: "
            f"symbol={symbol} reason={reason} order_ids={','.join(str(value) for value in unique_ids)} "
            f"loop={loop_label}"
        )
        for order_id in unique_ids:
            self._cancel_order_with_gateway(
                symbol=symbol,
                order_id=int(order_id),
                loop_label=f"{loop_label}-{reason}-order-{order_id}",
            )

    def _enforce_phase_exit_policy(
        self,
        runtime: AutoTradeRuntime,
        *,
        symbol: str,
        open_orders: list[dict],
        positions: list[dict],
        loop_label: str,
    ) -> AutoTradeRuntime:
        target = str(symbol or "").strip().upper()
        if not target:
            return runtime
        if runtime.symbol_state not in ("PHASE1", "PHASE2"):
            self._tp_trigger_submit_guard_by_symbol.pop(target, None)
            self._phase1_tp_filled_symbols.discard(target)
            return runtime

        position = self._get_symbol_position(positions, target)
        if position is None:
            return runtime
        position_amt = self._safe_float(position.get("positionAmt")) or 0.0
        if abs(position_amt) <= 1e-12:
            return runtime
        avg_entry = self._safe_float(position.get("entryPrice")) or 0.0
        if avg_entry <= 0:
            return runtime
        mark_price = self._safe_float(position.get("markPrice")) or avg_entry
        if mark_price <= 0:
            return runtime
        is_short = position_amt < 0
        close_side = "BUY" if is_short else "SELL"
        state = str(runtime.symbol_state or "").strip().upper()

        filter_rule = self._get_symbol_filter_rule(target)
        if filter_rule is None:
            return runtime
        tick_size = float(filter_rule.tick_size)
        tolerance = max(tick_size * 0.55, 1e-12)

        tp_ratio = self._parse_percent_text(
            (self._saved_filter_settings or self._default_filter_settings()).get("tp_ratio"),
            0.05,
        )
        mdd_ratio = self._parse_percent_text(
            (self._saved_filter_settings or self._default_filter_settings()).get("mdd"),
            0.15,
        )

        breakeven_target = round_price_by_tick_size(avg_entry, tick_size)
        mdd_target = round_price_by_tick_size(
            avg_entry * (1.0 + mdd_ratio if is_short else 1.0 - mdd_ratio),
            tick_size,
        )
        if breakeven_target is None or mdd_target is None:
            _log_trade(
                "Phase exit policy skipped: "
                f"symbol={target} reason=target_rounding_failed avg_entry={avg_entry} tick_size={tick_size}"
            )
            return runtime

        _entry_orders, exit_orders = self._classify_orders_for_symbol(target, open_orders)
        tp_trigger_rows: list[dict[str, float]] = []
        tp_limit_rows: list[dict[str, float]] = []
        tp_market_order_ids: list[int] = []
        breakeven_stop_order_ids: list[int] = []
        mdd_stop_order_ids: list[int] = []
        mdd_stop_prices: list[float] = []

        for row in exit_orders:
            order_id = self._safe_int(row.get("orderId"))
            if order_id <= 0:
                continue
            order_type = str(row.get("type") or "").strip().upper()
            side = str(row.get("side") or "").strip().upper()
            if side != close_side:
                continue
            if order_type == "TAKE_PROFIT":
                trigger_price, stop_source = self._select_effective_stop_price(row)
                order_price = self._safe_float(row.get("price"))
                if trigger_price is None or trigger_price <= 0:
                    continue
                if order_price is None or order_price <= 0:
                    continue
                if stop_source and stop_source != "stopPrice":
                    _log_trade(
                        "Phase policy TP trigger price fallback used: "
                        f"symbol={target} order_id={order_id} source={stop_source} "
                        f"trigger_price={trigger_price} loop={loop_label}"
                    )
                tp_trigger_rows.append(
                    {
                        "order_id": float(order_id),
                        "price": float(order_price),
                        "trigger_price": float(trigger_price),
                    }
                )
                continue
            if order_type == "TAKE_PROFIT_MARKET":
                tp_market_order_ids.append(order_id)
                continue
            if order_type == "LIMIT":
                price = self._safe_float(row.get("price"))
                if price is None or price <= 0:
                    continue
                tp_limit_rows.append(
                    {
                        "order_id": float(order_id),
                        "price": float(price),
                    }
                )
                continue
            if order_type not in ("STOP_MARKET", "STOP"):
                continue
            stop_price, stop_source = self._select_effective_stop_price(row)
            if stop_price is None:
                continue
            if stop_source and stop_source != "stopPrice":
                _log_trade(
                    "Phase policy stop price fallback used: "
                    f"symbol={target} order_id={order_id} source={stop_source} "
                    f"stop_price={stop_price} loop={loop_label}"
                )
            if abs(float(stop_price) - float(breakeven_target)) <= tolerance * 2:
                breakeven_stop_order_ids.append(order_id)
            else:
                mdd_stop_order_ids.append(order_id)
                mdd_stop_prices.append(float(stop_price))

        split_plan = self._build_split_tp_plan_for_symbol(
            symbol=target,
            position_amt=float(position_amt),
            avg_entry=float(avg_entry),
            tick_size=float(filter_rule.tick_size),
            step_size=float(filter_rule.step_size),
            min_qty=float(filter_rule.min_qty),
            phase=state,
            tp_ratio=float(tp_ratio),
            loop_label=f"{loop_label}-plan",
        )
        mdd_stop_aligned = bool(mdd_stop_order_ids) and all(
            abs(float(price) - float(mdd_target)) <= tolerance * 2 for price in mdd_stop_prices
        )

        tp_trigger_used_ids: set[int] = set()
        tp_limit_used_ids: set[int] = set()
        missing_split_plan: list[dict[str, float]] = []
        for desired in split_plan:
            desired_target = float(desired.get("target_price") or 0.0)
            desired_trigger = float(desired.get("trigger_price") or 0.0)
            matched = False
            for row in tp_trigger_rows:
                order_id = int(row.get("order_id") or 0)
                if order_id <= 0 or order_id in tp_trigger_used_ids:
                    continue
                if abs(float(row.get("price") or 0.0) - desired_target) > tolerance:
                    continue
                if abs(float(row.get("trigger_price") or 0.0) - desired_trigger) > tolerance * 2:
                    continue
                tp_trigger_used_ids.add(order_id)
                matched = True
                break
            if matched:
                continue
            for row in tp_limit_rows:
                order_id = int(row.get("order_id") or 0)
                if order_id <= 0 or order_id in tp_limit_used_ids:
                    continue
                if abs(float(row.get("price") or 0.0) - desired_target) > tolerance:
                    continue
                tp_limit_used_ids.add(order_id)
                matched = True
                break
            if not matched:
                missing_split_plan.append(dict(desired))

        stale_tp_order_ids = [
            int(row.get("order_id") or 0)
            for row in tp_trigger_rows
            if int(row.get("order_id") or 0) > 0 and int(row.get("order_id") or 0) not in tp_trigger_used_ids
        ]
        stale_tp_order_ids.extend(
            int(row.get("order_id") or 0)
            for row in tp_limit_rows
            if int(row.get("order_id") or 0) > 0 and int(row.get("order_id") or 0) not in tp_limit_used_ids
        )
        stale_tp_order_ids.extend(int(order_id) for order_id in tp_market_order_ids if int(order_id) > 0)
        stale_tp_order_ids = sorted({int(value) for value in stale_tp_order_ids if int(value) > 0})
        if stale_tp_order_ids:
            self._cancel_orders_by_ids(
                symbol=target,
                order_ids=stale_tp_order_ids,
                loop_label=loop_label,
                reason=f"{state.lower()}_refresh_split_tp_orders",
            )
            self._tp_trigger_submit_guard_by_symbol.pop(target, None)

        if state == "PHASE1":
            if mdd_stop_order_ids:
                self._cancel_orders_by_ids(
                    symbol=target,
                    order_ids=mdd_stop_order_ids,
                    loop_label=loop_label,
                    reason="phase1_disable_mdd_stop",
                )

            if target in self._phase1_tp_filled_symbols and not breakeven_stop_order_ids:
                stop_submitted = self._submit_breakeven_stop_market(
                    symbol=target,
                    positions=positions,
                    loop_label=f"{loop_label}-phase1-first-tp-breakeven-stop",
                )
                _log_trade(
                    "Phase1 first TP breakeven stop ensured: "
                    f"symbol={target} submitted={stop_submitted} loop={loop_label}"
                )

            if not split_plan:
                return runtime

            tp_open_order_count = len(tp_trigger_rows) + len(tp_limit_rows)
            if (
                missing_split_plan
                and target in self._phase1_tp_filled_symbols
                and tp_open_order_count > 0
                and not stale_tp_order_ids
            ):
                self._tp_trigger_submit_guard_by_symbol.pop(target, None)
                _log_trade(
                    "Phase1 split TP replenish skipped after TP fill: "
                    f"symbol={target} mark_price={mark_price} desired={len(split_plan)} "
                    f"existing_tp={tp_open_order_count} missing={len(missing_split_plan)} loop={loop_label}"
                )
                return runtime

            if missing_split_plan:
                plan_signature = self._build_split_tp_plan_signature(phase=state, plan=split_plan)
                guard = self._tp_trigger_submit_guard_by_symbol.get(target)
                if isinstance(guard, Mapping):
                    guard_signature = str(guard.get("signature") or "")
                    guard_age = max(0.0, time.time() - float(guard.get("submitted_at") or 0.0))
                    if (
                        guard_signature == plan_signature
                        and guard_age <= float(TP_TRIGGER_SUBMISSION_GUARD_SEC)
                        and not stale_tp_order_ids
                    ):
                        _log_trade(
                            "Phase1 split TP submit skipped by guard: "
                            f"symbol={target} age_sec={guard_age:.2f} missing={len(missing_split_plan)} loop={loop_label}"
                        )
                        return runtime
                attempted, succeeded = self._submit_split_tp_triggers(
                    symbol=target,
                    positions=positions,
                    split_plan=missing_split_plan,
                    loop_label=f"{loop_label}-phase1-split-tp",
                )
                if attempted > 0 and succeeded == attempted:
                    self._tp_trigger_submit_guard_by_symbol[target] = {
                        "submitted_at": float(time.time()),
                        "signature": plan_signature,
                        "submitted_count": int(succeeded),
                    }
                else:
                    self._tp_trigger_submit_guard_by_symbol.pop(target, None)
                _log_trade(
                    "Phase1 split TP ensured: "
                    f"symbol={target} mark_price={mark_price} desired={len(split_plan)} missing={len(missing_split_plan)} "
                    f"attempted={attempted} succeeded={succeeded} loop={loop_label}"
                )
            else:
                self._tp_trigger_submit_guard_by_symbol.pop(target, None)
            return runtime

        # PHASE2 policy.
        if breakeven_stop_order_ids:
            self._cancel_orders_by_ids(
                symbol=target,
                order_ids=breakeven_stop_order_ids,
                loop_label=loop_label,
                reason="phase2_disable_breakeven_stop",
            )

        if split_plan and missing_split_plan:
            plan_signature = self._build_split_tp_plan_signature(phase=state, plan=split_plan)
            guard = self._tp_trigger_submit_guard_by_symbol.get(target)
            if isinstance(guard, Mapping):
                guard_signature = str(guard.get("signature") or "")
                guard_age = max(0.0, time.time() - float(guard.get("submitted_at") or 0.0))
                if (
                    guard_signature == plan_signature
                    and guard_age <= float(TP_TRIGGER_SUBMISSION_GUARD_SEC)
                    and not stale_tp_order_ids
                ):
                    _log_trade(
                        "Phase2 split TP submit skipped by guard: "
                        f"symbol={target} age_sec={guard_age:.2f} missing={len(missing_split_plan)} loop={loop_label}"
                    )
                    return runtime
            attempted, succeeded = self._submit_split_tp_triggers(
                symbol=target,
                positions=positions,
                split_plan=missing_split_plan,
                loop_label=f"{loop_label}-phase2-split-tp",
            )
            if attempted > 0 and succeeded == attempted:
                self._tp_trigger_submit_guard_by_symbol[target] = {
                    "submitted_at": float(time.time()),
                    "signature": plan_signature,
                    "submitted_count": int(succeeded),
                }
            else:
                self._tp_trigger_submit_guard_by_symbol.pop(target, None)
            _log_trade(
                "Phase2 split TP ensured: "
                f"symbol={target} mark_price={mark_price} desired={len(split_plan)} missing={len(missing_split_plan)} "
                f"attempted={attempted} succeeded={succeeded} loop={loop_label}"
            )
        elif split_plan:
            self._tp_trigger_submit_guard_by_symbol.pop(target, None)

        second_entry_fully_filled = target in self._second_entry_fully_filled_symbols
        if second_entry_fully_filled:
            if not mdd_stop_aligned:
                if mdd_stop_order_ids:
                    self._cancel_orders_by_ids(
                        symbol=target,
                        order_ids=mdd_stop_order_ids,
                        loop_label=loop_label,
                        reason="phase2_refresh_mdd_stop",
                    )
                submitted = self._submit_mdd_stop_market(
                    symbol=target,
                    positions=positions,
                    loop_label=f"{loop_label}-phase2-mdd-stop",
                )
                _log_trade(
                    "Phase2 MDD stop evaluated: "
                    f"symbol={target} target={mdd_target} submitted={submitted} fully_filled={second_entry_fully_filled}"
                )
        elif mdd_stop_order_ids:
            self._cancel_orders_by_ids(
                symbol=target,
                order_ids=mdd_stop_order_ids,
                loop_label=loop_label,
                reason="phase2_disable_mdd_until_second_filled",
            )
        return runtime

    def _run_exit_supervision(
        self,
        runtime: AutoTradeRuntime,
        *,
        symbol: str,
        open_orders: list[dict],
        positions: list[dict],
        risk_market_exit_in_same_loop: bool,
        loop_label: str,
    ) -> AutoTradeRuntime:
        target = str(symbol or "").strip().upper()
        if not target:
            return runtime
        current = runtime
        current = self._enforce_phase_exit_policy(
            current,
            symbol=target,
            open_orders=open_orders,
            positions=positions,
            loop_label=f"{loop_label}-phase-policy",
        )
        refreshed_open_orders = self._fetch_open_orders() or open_orders
        open_orders = refreshed_open_orders
        _, exit_orders = self._classify_orders_for_symbol(target, open_orders)
        now = int(time.time())
        current_exit_ids = {
            self._safe_int(order.get("orderId"))
            for order in exit_orders
            if self._safe_int(order.get("orderId")) > 0
        }
        tracker = current.exit_partial_tracker
        if tracker.active:
            tracked_order_id = self._safe_int(tracker.order_id)
            if tracked_order_id <= 0 or tracked_order_id not in current_exit_ids:
                _log_trade(
                    "Exit partial tracker cleared before five-second evaluation: "
                    f"symbol={target} tracked_order_id={tracked_order_id} "
                    f"active_exit_order_count={len(current_exit_ids)} "
                    f"reason=STALE_TRACKER_ORDER_MISMATCH loop={loop_label}"
                )
                current = replace(current, exit_partial_tracker=tracker.__class__())

        for row in exit_orders:
            order_id = self._safe_int(row.get("orderId"))
            if order_id <= 0:
                continue
            order_status = str(row.get("status") or "").strip().upper() or "NEW"
            executed_qty = self._safe_float(row.get("executedQty")) or 0.0
            updated_at = self._safe_int(row.get("updateTime")) or now
            current, five_second = update_exit_partial_and_check_five_second(
                current,
                is_exit_order=True,
                order_id=int(order_id),
                order_status=order_status,
                executed_qty=float(executed_qty),
                updated_at=int(updated_at),
                now=now,
                risk_market_exit_in_same_loop=risk_market_exit_in_same_loop,
                loop_label=f"{loop_label}-five-second",
            )
            if five_second.decision.should_force_market_exit:
                _log_trade(
                    "Exit partial 5-second rule triggered: "
                    f"symbol={target} order_id={order_id} reason={five_second.reason_code}"
                )
                self._cancel_order_with_gateway(
                    symbol=target,
                    order_id=int(order_id),
                    loop_label=f"{loop_label}-five-second-cancel",
                )
                self._submit_market_exit_for_symbol(
                    symbol=target,
                    positions=positions,
                    loop_label=f"{loop_label}-five-second-market-exit",
                )
                break

        previous_exit_ids = self._last_open_exit_order_ids_by_symbol.get(target, set())
        removed_ids = sorted(previous_exit_ids - current_exit_ids)
        if removed_ids and current_exit_ids:
            filled_exit = self._resolve_filled_exit_order_id(
                symbol=target,
                removed_order_ids=removed_ids,
                loop_label=f"{loop_label}-oco-detect-fill",
            )
            if filled_exit is None:
                _log_trade(
                    "OCO cancel skipped: "
                    f"symbol={target} removed_exit_orders={','.join(str(value) for value in removed_ids)} "
                    "reason=no_filled_exit_order_confirmed"
                )
            else:
                filled_order_id = int(filled_exit.get("order_id") or 0)
                filled_order_type = str(filled_exit.get("order_type") or "").strip().upper()
                already_handled = self._oco_last_filled_exit_order_by_symbol.get(target) == int(filled_order_id)
                if filled_order_id > 0 and not already_handled:
                    if filled_order_type in ("TAKE_PROFIT", "TAKE_PROFIT_MARKET", "LIMIT"):
                        if str(current.symbol_state or "").strip().upper() == "PHASE1":
                            self._phase1_tp_filled_symbols.add(target)
                            _log_trade(
                                "Phase1 TP fill detected, breakeven stop arm enabled: "
                                f"symbol={target} filled_order_id={filled_order_id} type={filled_order_type} "
                                f"loop={loop_label}"
                            )
                        self._oco_last_filled_exit_order_by_symbol[target] = int(filled_order_id)
                        _log_trade(
                            "OCO cancel bypassed for split TP continuity: "
                            f"symbol={target} filled_order_id={filled_order_id} type={filled_order_type} "
                            f"remaining_exit_order_count={len(current_exit_ids)} loop={loop_label}"
                        )
                    else:
                        current, oco_result = execute_oco_cancel_flow(
                            current,
                            symbol=target,
                            filled_order_id=int(filled_order_id),
                            open_exit_order_ids=sorted(current_exit_ids),
                            cancel_call=self._gateway_cancel_order_call,
                            retry_policy=self._query_cancel_retry_policy(),
                            loop_label=f"{loop_label}-oco-cancel",
                        )
                        self._oco_last_filled_exit_order_by_symbol[target] = int(filled_order_id)
                        if oco_result.lock_new_orders:
                            self._pending_oco_retry_symbols.add(target)
                        elif oco_result.success:
                            self._pending_oco_retry_symbols.discard(target)
                        _log_trade(
                            "OCO cancel flow executed: "
                            f"symbol={target} filled_order_id={int(filled_order_id)} "
                            f"success={oco_result.success} reason={oco_result.reason_code} "
                            f"lock_new_orders={oco_result.lock_new_orders} "
                            f"pending_retry_symbols={','.join(sorted(self._pending_oco_retry_symbols)) or '-'}"
                        )

        if current_exit_ids:
            self._last_open_exit_order_ids_by_symbol[target] = set(current_exit_ids)
        else:
            self._last_open_exit_order_ids_by_symbol.pop(target, None)
            self._oco_last_filled_exit_order_by_symbol.pop(target, None)
            self._pending_oco_retry_symbols.discard(target)
        return current

    def _resolve_filled_exit_order_id(
        self,
        *,
        symbol: str,
        removed_order_ids: list[int],
        loop_label: str,
    ) -> Optional[dict[str, object]]:
        for order_id in sorted((int(value) for value in removed_order_ids), reverse=True):
            payload = self._query_order_payload_by_id(
                symbol=symbol,
                order_id=int(order_id),
                loop_label=f"{loop_label}-order-{int(order_id)}",
            )
            status = str(payload.get("status") or "").strip().upper() if isinstance(payload, Mapping) else ""
            if status == "FILLED":
                order_type = str(payload.get("type") or payload.get("orderType") or "").strip().upper()
                return {
                    "order_id": int(order_id),
                    "order_type": str(order_type or "-"),
                    "payload": dict(payload),
                }
            if status:
                _log_trade(
                    "Removed exit order status checked: "
                    f"symbol={symbol} order_id={int(order_id)} status={status} "
                    f"type={str(payload.get('type') or payload.get('orderType') or '-').strip().upper()}"
                )
            else:
                _log_trade(
                    "Removed exit order status unresolved: "
                    f"symbol={symbol} order_id={int(order_id)}"
                )
        return None

    def _execute_risk_signal_actions(
        self,
        *,
        result,
        loop_label: str,
    ) -> tuple[bool, bool]:
        symbol = str(result.symbol or "").strip().upper()
        if not symbol:
            return False, True
        open_orders, positions = self._fetch_loop_account_snapshot()
        risk_market_exit_submitted = False
        cancel_entry_reset_ready = True

        if result.cancel_entry_orders:
            open_orders, positions = self._fetch_loop_account_snapshot(
                force_refresh=True,
                loop_label=f"{loop_label}-cancel-entry-pre-refresh",
            )
            cancel_result = self._cancel_entry_orders_for_symbol(
                symbol=symbol,
                open_orders=open_orders,
                loop_label=f"{loop_label}-cancel-entry",
            )
            open_orders, positions = self._fetch_loop_account_snapshot(
                force_refresh=True,
                loop_label=f"{loop_label}-cancel-entry-post-refresh",
            )
            remaining_entry_orders, _ = self._classify_orders_for_symbol(symbol, open_orders)
            remaining_entry_order_ids = [
                self._safe_int(row.get("orderId"))
                for row in remaining_entry_orders
                if self._safe_int(row.get("orderId")) > 0
            ]
            snapshot_ready = self._has_recent_account_snapshot()
            if remaining_entry_orders:
                cancel_entry_reset_ready = False
                _log_trade(
                    "Risk entry cancel verification failed: "
                    f"symbol={symbol} reason=entry_orders_still_open "
                    f"remaining_order_ids={','.join(str(value) for value in sorted(remaining_entry_order_ids)) or '-'} "
                    f"attempted={int(cancel_result['attempted_count'])} "
                    f"success={int(cancel_result['success_count'])} "
                    f"failed_order_ids={','.join(str(value) for value in cancel_result['failed_order_ids']) or '-'} "
                    f"loop={loop_label}"
                )
            elif not snapshot_ready:
                cancel_entry_reset_ready = False
                _log_trade(
                    "Risk entry cancel verification deferred: "
                    f"symbol={symbol} reason=account_snapshot_unavailable "
                    f"attempted={int(cancel_result['attempted_count'])} "
                    f"success={int(cancel_result['success_count'])} "
                    f"failed_order_ids={','.join(str(value) for value in cancel_result['failed_order_ids']) or '-'} "
                    f"loop={loop_label}"
                )
            else:
                self._entry_order_ref_by_symbol.pop(symbol, None)
                self._clear_entry_cancel_sync_guard(symbol)
                _log_trade(
                    "Risk entry cancel verification passed: "
                    f"symbol={symbol} attempted={int(cancel_result['attempted_count'])} "
                    f"success={int(cancel_result['success_count'])} "
                    f"used_cached_ref={bool(cancel_result['used_cached_order_ref'])} "
                    f"loop={loop_label}"
                )

        if result.submit_market_exit:
            risk_market_exit_submitted = self._submit_market_exit_for_symbol(
                symbol=symbol,
                positions=positions,
                loop_label=f"{loop_label}-market-exit",
            )
            open_orders, positions = self._fetch_loop_account_snapshot()

        if result.submit_breakeven_stop_market:
            self._submit_breakeven_stop_market(
                symbol=symbol,
                positions=positions,
                loop_label=f"{loop_label}-breakeven-stop",
            )
            open_orders, positions = self._fetch_loop_account_snapshot()
            if (
                str(getattr(result, "action_code", "")).strip().upper() == "PHASE1_STOP_AND_TP_POLICY"
                and not bool(result.create_tp_limit_once)
            ):
                _log_trade(
                    "Risk positive TP deferred to phase1 trigger: "
                    f"symbol={symbol} reason=use_phase1_tp_trigger_buffer"
                )

        if result.create_tp_limit_once:
            self._submit_tp_limit_once(
                symbol=symbol,
                positions=positions,
                loop_label=f"{loop_label}-tp-limit",
            )

        if result.reset_state:
            if result.cancel_entry_orders and not cancel_entry_reset_ready:
                _log_trade(
                    "Risk state reset skipped: "
                    f"symbol={symbol} reason=entry_cancel_not_confirmed loop={loop_label}"
                )
            else:
                self._second_entry_skip_latch.discard(symbol)
                self._second_entry_fully_filled_symbols.discard(symbol)
                self._phase1_tp_filled_symbols.discard(symbol)
                self._entry_order_ref_by_symbol.pop(symbol, None)
                self._clear_entry_cancel_sync_guard(symbol)
                self._last_open_exit_order_ids_by_symbol.pop(symbol, None)
                self._oco_last_filled_exit_order_by_symbol.pop(symbol, None)
                self._pending_oco_retry_symbols.discard(symbol)
                self._last_position_qty_by_symbol.pop(symbol, None)
                self._position_zero_confirm_streak_by_symbol.pop(symbol, None)
        return risk_market_exit_submitted, cancel_entry_reset_ready

    def _cancel_open_orders_for_symbols(
        self,
        *,
        symbols: list[str],
        loop_label: str,
    ) -> None:
        if not symbols:
            return
        open_orders = self._fetch_open_orders() or []
        for symbol in symbols:
            target = str(symbol or "").strip().upper()
            if not target:
                continue
            for row in open_orders:
                if str(row.get("symbol") or "").strip().upper() != target:
                    continue
                order_id = self._safe_int(row.get("orderId"))
                if order_id <= 0:
                    continue
                self._cancel_order_with_gateway(
                    symbol=target,
                    order_id=order_id,
                    loop_label=f"{loop_label}-{target}",
                )

    def _cancel_exit_orders_for_symbol(
        self,
        *,
        symbol: str,
        open_orders: list[dict],
        loop_label: str,
    ) -> None:
        target = str(symbol or "").strip().upper()
        if not target:
            return
        _, exit_orders = self._classify_orders_for_symbol(target, open_orders)
        exit_order_ids = [
            self._safe_int(row.get("orderId"))
            for row in exit_orders
            if self._safe_int(row.get("orderId")) > 0
        ]
        if not exit_order_ids:
            _log_trade(
                "Exit-order cancel skipped on quantity change: "
                f"symbol={target} reason=no_exit_orders loop={loop_label}"
            )
            return
        self._cancel_orders_by_ids(
            symbol=target,
            order_ids=exit_order_ids,
            loop_label=loop_label,
            reason="position_qty_change_exit_only",
        )

    @staticmethod
    def _is_exit_filter_failure_reason(reason_code: str) -> bool:
        normalized = str(reason_code or "").strip().upper()
        filter_failures = {
            "INVALID_FILTER_TICK_SIZE",
            "INVALID_FILTER_STEP_SIZE",
            "INVALID_FILTER_MIN_QTY",
            "INVALID_FILTER_MIN_NOTIONAL",
            "INVALID_PRICE_INPUT",
            "PRICE_NON_POSITIVE_AFTER_ROUND",
            "INVALID_QUANTITY_INPUT",
            "QUANTITY_NON_POSITIVE_AFTER_FLOOR",
            "LOT_SIZE_MIN_QTY_NOT_MET",
            "MIN_NOTIONAL_REFERENCE_PRICE_REQUIRED",
            "MIN_NOTIONAL_NOT_MET",
            "LIMIT_PRICE_REQUIRED",
            "STOP_PRICE_REQUIRED",
        }
        return normalized in filter_failures

    @staticmethod
    def _is_transient_gateway_failure_reason(reason_code: str) -> bool:
        normalized = str(reason_code or "").strip().upper()
        return normalized in {
            "NETWORK_ERROR",
            "TIMEOUT",
            "RATE_LIMIT",
            "SERVER_ERROR",
            "TEMPORARY_UNAVAILABLE",
        }

    def _handle_exit_filter_failure(
        self,
        *,
        symbol: str,
        reason_code: str,
        filter_rule: SymbolFilterRules,
        position_amt: float,
        positions: list[dict],
        order_context: str,
        loop_label: str,
    ) -> None:
        target = str(symbol or "").strip().upper()
        absolute_qty = abs(float(position_amt))
        normalized_qty = floor_quantity_by_step_size(absolute_qty, filter_rule.step_size)
        min_qty = float(filter_rule.min_qty)
        normalized_text = "-" if normalized_qty is None else str(normalized_qty)
        _log_trade(
            "Exit order filter failure detected: "
            f"context={order_context} symbol={target} reason={reason_code} "
            f"position_qty={absolute_qty} normalized_qty={normalized_text} min_qty={min_qty} "
            f"loop={loop_label}"
        )

        if normalized_qty is None or float(normalized_qty) < min_qty - 1e-12:
            self._last_dust_symbols.add(target)
            self._cancel_open_orders_for_symbols(
                symbols=[target],
                loop_label=f"{loop_label}-dust-cancel",
            )
            self._reset_runtime_after_external_clear(
                reason_code=f"DUST_RESET_{order_context}_{str(reason_code or '').upper()}",
            )
            _log_trade(
                "Exit order filter failure dust reset applied: "
                f"context={order_context} symbol={target} loop={loop_label}"
            )
            return

        success = self._submit_market_exit_for_symbol(
            symbol=target,
            positions=positions,
            loop_label=f"{loop_label}-fallback-market-exit",
        )
        _log_trade(
            "Exit order filter failure fallback market-exit attempted: "
            f"context={order_context} symbol={target} success={success} loop={loop_label}"
        )

    def _cancel_entry_orders_for_symbol(
        self,
        *,
        symbol: str,
        open_orders: list[dict],
        loop_label: str,
    ) -> dict[str, object]:
        target = str(symbol or "").strip().upper()
        if not target:
            return {
                "attempted_count": 0,
                "success_count": 0,
                "failed_order_ids": [],
                "used_cached_order_ref": False,
            }
        entry_orders, _ = self._classify_orders_for_symbol(target, open_orders)
        attempted_order_ids: list[int] = []
        success_order_ids: list[int] = []
        failed_order_ids: list[int] = []
        for row in entry_orders:
            order_id = self._safe_int(row.get("orderId"))
            if order_id <= 0:
                continue
            attempted_order_ids.append(int(order_id))
            cancel_ok = self._cancel_order_with_gateway(
                symbol=target,
                order_id=order_id,
                loop_label=f"{loop_label}-order-{order_id}",
            )
            if cancel_ok:
                success_order_ids.append(int(order_id))
            else:
                failed_order_ids.append(int(order_id))

        used_cached_order_ref = False
        cached_order_id = self._safe_int(self._entry_order_ref_by_symbol.get(target))
        if (
            cached_order_id > 0
            and cached_order_id not in attempted_order_ids
            and (not entry_orders or not attempted_order_ids)
        ):
            used_cached_order_ref = True
            attempted_order_ids.append(int(cached_order_id))
            cancel_ok = self._cancel_order_with_gateway(
                symbol=target,
                order_id=int(cached_order_id),
                loop_label=f"{loop_label}-cached-order-{int(cached_order_id)}",
            )
            if cancel_ok:
                success_order_ids.append(int(cached_order_id))
            else:
                failed_order_ids.append(int(cached_order_id))
            _log_trade(
                "Entry-order cancel fallback attempted with cached order ref: "
                f"symbol={target} order_id={int(cached_order_id)} success={cancel_ok} loop={loop_label}"
            )

        if not attempted_order_ids:
            _log_trade(
                "Entry-order cancel skipped: "
                f"symbol={target} reason=no_entry_orders_identified loop={loop_label}"
            )
        _log_trade(
            "Entry-order cancel summary: "
            f"symbol={target} snapshot_entry_count={len(entry_orders)} "
            f"attempted={len(attempted_order_ids)} success={len(success_order_ids)} "
            f"failed_order_ids={','.join(str(value) for value in failed_order_ids) or '-'} "
            f"used_cached_ref={used_cached_order_ref} loop={loop_label}"
        )
        return {
            "attempted_count": len(attempted_order_ids),
            "success_count": len(success_order_ids),
            "failed_order_ids": failed_order_ids,
            "used_cached_order_ref": used_cached_order_ref,
        }

    def _force_market_exit_all_positions(
        self,
        *,
        positions: list[dict],
        loop_label: str,
    ) -> None:
        rows = list(positions)
        if not rows:
            rows = self._fetch_open_positions() or []
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            self._submit_market_exit_for_symbol(
                symbol=symbol,
                positions=rows,
                loop_label=f"{loop_label}-{symbol}",
            )

    def _submit_market_exit_for_symbol(
        self,
        *,
        symbol: str,
        positions: list[dict],
        loop_label: str,
    ) -> bool:
        position = self._get_symbol_position(positions, symbol)
        if position is None:
            _log_trade(f"Market exit skipped: symbol={symbol} reason=position_missing")
            return False
        position_amt = self._safe_float(position.get("positionAmt"))
        if position_amt is None or abs(position_amt) <= 1e-12:
            _log_trade(f"Market exit skipped: symbol={symbol} reason=position_zero")
            return False
        side = "BUY" if position_amt < 0 else "SELL"
        quantity = abs(float(position_amt))
        reference_price = self._safe_float(position.get("markPrice")) or self._safe_float(position.get("entryPrice")) or 0.0
        filter_rule = self._get_symbol_filter_rule(symbol)
        if filter_rule is None:
            _log_trade(f"Market exit skipped: symbol={symbol} reason=missing_filter_rule")
            return False
        position_mode = self._current_position_mode()
        if position_mode not in ("ONE_WAY", "HEDGE"):
            _log_trade(f"Market exit skipped: symbol={symbol} reason=unknown_position_mode")
            return False

        request = OrderCreateRequest(
            symbol=symbol,
            side=side,
            order_type="MARKET",
            purpose="EXIT",
            quantity=quantity,
            reference_price=reference_price if reference_price > 0 else None,
        )
        retry = create_order_with_retry_with_logging(
            request,
            filter_rules=filter_rule,
            position_mode=position_mode,
            call=self._gateway_create_order_call,
            retry_policy=self._default_retry_policy(),
            loop_label=loop_label,
        )
        _log_trade(
            "Market exit order result: "
            f"symbol={symbol} side={side} qty={quantity} success={retry.success} "
            f"reason={retry.reason_code} attempts={retry.attempts}"
        )
        return retry.success

    def _submit_breakeven_stop_market(
        self,
        *,
        symbol: str,
        positions: list[dict],
        loop_label: str,
    ) -> bool:
        position = self._get_symbol_position(positions, symbol)
        if position is None:
            return False
        avg_entry = self._safe_float(position.get("entryPrice")) or 0.0
        if avg_entry <= 0:
            return False
        return self._submit_stop_market_exit(
            symbol=symbol,
            positions=positions,
            stop_price=float(avg_entry),
            order_context="BREAKEVEN_STOP_MARKET",
            loop_label=loop_label,
        )

    def _submit_stop_market_exit(
        self,
        *,
        symbol: str,
        positions: list[dict],
        stop_price: float,
        order_context: str,
        loop_label: str,
    ) -> bool:
        position = self._get_symbol_position(positions, symbol)
        if position is None:
            return False
        position_amt = self._safe_float(position.get("positionAmt")) or 0.0
        if abs(position_amt) <= 1e-12:
            return False
        if float(stop_price) <= 0:
            return False
        side = "BUY" if position_amt < 0 else "SELL"
        filter_rule = self._get_symbol_filter_rule(symbol)
        if filter_rule is None:
            return False
        position_mode = self._current_position_mode()
        if position_mode not in ("ONE_WAY", "HEDGE"):
            return False

        request = OrderCreateRequest(
            symbol=symbol,
            side=side,
            order_type="STOP_MARKET",
            purpose="EXIT",
            stop_price=float(stop_price),
            close_position=True,
            reference_price=float(stop_price),
        )
        retry = create_order_with_retry_with_logging(
            request,
            filter_rules=filter_rule,
            position_mode=position_mode,
            call=self._gateway_create_order_call,
            retry_policy=self._default_retry_policy(),
            loop_label=loop_label,
        )
        _log_trade(
            "STOP_MARKET result: "
            f"context={order_context} symbol={symbol} stop_price={stop_price} success={retry.success} "
            f"reason={retry.reason_code} attempts={retry.attempts}"
        )
        if not retry.success and self._is_exit_filter_failure_reason(retry.reason_code):
            self._handle_exit_filter_failure(
                symbol=symbol,
                reason_code=retry.reason_code,
                filter_rule=filter_rule,
                position_amt=position_amt,
                positions=positions,
                order_context=order_context,
                loop_label=loop_label,
            )
        return retry.success

    def _submit_mdd_stop_market(
        self,
        *,
        symbol: str,
        positions: list[dict],
        loop_label: str,
    ) -> bool:
        position = self._get_symbol_position(positions, symbol)
        if position is None:
            return False
        position_amt = self._safe_float(position.get("positionAmt")) or 0.0
        if abs(position_amt) <= 1e-12:
            return False
        avg_entry = self._safe_float(position.get("entryPrice")) or 0.0
        if avg_entry <= 0:
            return False
        mdd_ratio = self._parse_percent_text(
            (self._saved_filter_settings or self._default_filter_settings()).get("mdd"),
            0.15,
        )
        stop_price = avg_entry * (1.0 + mdd_ratio if position_amt < 0 else 1.0 - mdd_ratio)
        if stop_price <= 0:
            return False
        return self._submit_stop_market_exit(
            symbol=symbol,
            positions=positions,
            stop_price=float(stop_price),
            order_context="MDD_STOP_MARKET",
            loop_label=loop_label,
        )

    def _submit_tp_limit_once(
        self,
        *,
        symbol: str,
        positions: list[dict],
        loop_label: str,
        target_price_override: Optional[float] = None,
        trigger_price_override: Optional[float] = None,
        quantity_override: Optional[float] = None,
        allow_market_fallback: bool = True,
    ) -> bool:
        position = self._get_symbol_position(positions, symbol)
        if position is None:
            return False
        position_amt = self._safe_float(position.get("positionAmt")) or 0.0
        if abs(position_amt) <= 1e-12:
            return False
        avg_entry = self._safe_float(position.get("entryPrice")) or 0.0
        if avg_entry <= 0:
            return False
        filter_rule = self._get_symbol_filter_rule(symbol)
        if filter_rule is None:
            return False
        is_short = position_amt < 0
        if target_price_override is None:
            tp_ratio = self._parse_percent_text(
                (self._saved_filter_settings or self._default_filter_settings()).get("tp_ratio"),
                0.05,
            )
            target_price = avg_entry * (1.0 - tp_ratio if is_short else 1.0 + tp_ratio)
        else:
            target_price = float(target_price_override)
        if target_price <= 0:
            return False
        if trigger_price_override is None:
            trigger_price = self._compute_one_tick_lead_trigger_price(
                target_price=float(target_price),
                is_short=is_short,
                tick_size=float(filter_rule.tick_size) if filter_rule is not None else 0.0,
            )
        else:
            trigger_price = float(trigger_price_override)
        if trigger_price is None or float(trigger_price) <= 0:
            return False
        trigger_price = float(trigger_price)
        side = "BUY" if is_short else "SELL"
        quantity = abs(position_amt) if quantity_override is None else abs(float(quantity_override))
        if quantity <= 1e-12:
            _log_trade(
                "TP trigger skipped: "
                f"symbol={symbol} reason=quantity_non_positive quantity={quantity} loop={loop_label}"
            )
            return False

        rounded_target_price = round_price_by_tick_size(float(target_price), float(filter_rule.tick_size))
        if rounded_target_price is None or rounded_target_price <= 0:
            return False
        target_price = float(rounded_target_price)
        rounded_trigger_price = round_price_by_tick_size(float(trigger_price), float(filter_rule.tick_size))
        if rounded_trigger_price is None or rounded_trigger_price <= 0:
            return False
        trigger_price = float(rounded_trigger_price)
        position_mode = self._current_position_mode()
        if position_mode not in ("ONE_WAY", "HEDGE"):
            return False

        request = OrderCreateRequest(
            symbol=symbol,
            side=side,
            order_type="TAKE_PROFIT",
            purpose="EXIT",
            quantity=quantity,
            price=target_price,
            stop_price=trigger_price,
            reference_price=target_price,
            time_in_force="GTC",
        )
        retry = create_order_with_retry_with_logging(
            request,
            filter_rules=filter_rule,
            position_mode=position_mode,
            call=self._gateway_create_order_call,
            retry_policy=self._default_retry_policy(),
            loop_label=loop_label,
        )
        _log_trade(
            "TP trigger result: "
            f"symbol={symbol} trigger_price={trigger_price} target_price={target_price} qty={quantity} "
            f"success={retry.success} reason={retry.reason_code} attempts={retry.attempts}"
        )
        if not retry.success and self._is_exit_filter_failure_reason(retry.reason_code):
            self._handle_exit_filter_failure(
                symbol=symbol,
                reason_code=retry.reason_code,
                filter_rule=filter_rule,
                position_amt=position_amt,
                positions=positions,
                order_context="TP_TRIGGER",
                loop_label=loop_label,
            )
        elif not retry.success and not self._is_transient_gateway_failure_reason(retry.reason_code):
            last_result = getattr(retry, "last_result", None)
            last_error_code = getattr(last_result, "error_code", None)
            if last_error_code == -2021:
                _log_trade(
                    "TP trigger rejected as immediate-trigger: "
                    f"symbol={symbol} error_code={last_error_code} "
                    f"fallback_market_exit_skipped={not bool(allow_market_fallback)}"
                )
            if allow_market_fallback:
                fallback_success = self._submit_market_exit_for_symbol(
                    symbol=symbol,
                    positions=positions,
                    loop_label=f"{loop_label}-trigger-reject-market-fallback",
                )
                _log_trade(
                    "TP trigger reject fallback market-exit attempted: "
                    f"symbol={symbol} reason={retry.reason_code} error_code={last_error_code} "
                    f"success={fallback_success} loop={loop_label}"
                )
            else:
                _log_trade(
                    "TP trigger reject fallback market-exit skipped: "
                    f"symbol={symbol} reason={retry.reason_code} error_code={last_error_code} loop={loop_label}"
                )
        return retry.success

    def _submit_split_tp_triggers(
        self,
        *,
        symbol: str,
        positions: list[dict],
        split_plan: list[dict[str, float]],
        loop_label: str,
    ) -> tuple[int, int]:
        target = str(symbol or "").strip().upper()
        if not target or not split_plan:
            return 0, 0
        attempted = 0
        succeeded = 0
        for idx, order in enumerate(split_plan, start=1):
            attempted += 1
            target_price = float(order.get("target_price") or 0.0)
            trigger_price = float(order.get("trigger_price") or 0.0)
            quantity = float(order.get("quantity") or 0.0)
            if target_price <= 0.0 or trigger_price <= 0.0 or quantity <= 0.0:
                _log_trade(
                    "Split TP trigger skipped invalid order: "
                    f"symbol={target} index={idx} target={target_price} trigger={trigger_price} qty={quantity} "
                    f"loop={loop_label}"
                )
                continue
            success = self._submit_tp_limit_once(
                symbol=target,
                positions=positions,
                loop_label=f"{loop_label}-split-{idx}",
                target_price_override=target_price,
                trigger_price_override=trigger_price,
                quantity_override=quantity,
                allow_market_fallback=False,
            )
            if success:
                succeeded += 1
        _log_trade(
            "Split TP trigger submit summary: "
            f"symbol={target} attempted={attempted} succeeded={succeeded} loop={loop_label}"
        )
        return attempted, succeeded

    def _submit_breakeven_limit_once(
        self,
        *,
        symbol: str,
        positions: list[dict],
        loop_label: str,
        target_price_override: Optional[float] = None,
    ) -> bool:
        position = self._get_symbol_position(positions, symbol)
        if position is None:
            return False
        position_amt = self._safe_float(position.get("positionAmt")) or 0.0
        if abs(position_amt) <= 1e-12:
            return False
        avg_entry = self._safe_float(position.get("entryPrice")) or 0.0
        if avg_entry <= 0:
            return False
        target_price = float(target_price_override) if target_price_override is not None else float(avg_entry)
        if target_price <= 0:
            return False
        side = "BUY" if position_amt < 0 else "SELL"
        quantity = abs(position_amt)

        filter_rule = self._get_symbol_filter_rule(symbol)
        if filter_rule is None:
            return False
        rounded_target_price = round_price_by_tick_size(float(target_price), float(filter_rule.tick_size))
        if rounded_target_price is None or rounded_target_price <= 0:
            return False
        target_price = float(rounded_target_price)
        position_mode = self._current_position_mode()
        if position_mode not in ("ONE_WAY", "HEDGE"):
            return False

        request = OrderCreateRequest(
            symbol=symbol,
            side=side,
            order_type="LIMIT",
            purpose="EXIT",
            quantity=quantity,
            price=target_price,
            reference_price=target_price,
            time_in_force="GTC",
        )
        retry = create_order_with_retry_with_logging(
            request,
            filter_rules=filter_rule,
            position_mode=position_mode,
            call=self._gateway_create_order_call,
            retry_policy=self._default_retry_policy(),
            loop_label=loop_label,
        )
        _log_trade(
            "Breakeven LIMIT result: "
            f"symbol={symbol} target_price={target_price} qty={quantity} "
            f"success={retry.success} reason={retry.reason_code} attempts={retry.attempts}"
        )
        if not retry.success and self._is_exit_filter_failure_reason(retry.reason_code):
            self._handle_exit_filter_failure(
                symbol=symbol,
                reason_code=retry.reason_code,
                filter_rule=filter_rule,
                position_amt=position_amt,
                positions=positions,
                order_context="BREAKEVEN_LIMIT",
                loop_label=loop_label,
            )
        elif not retry.success and not self._is_transient_gateway_failure_reason(retry.reason_code):
            fallback_success = self._submit_market_exit_for_symbol(
                symbol=symbol,
                positions=positions,
                loop_label=f"{loop_label}-limit-reject-market-fallback",
            )
            _log_trade(
                "Breakeven LIMIT reject fallback market-exit attempted: "
                f"symbol={symbol} reason={retry.reason_code} success={fallback_success} loop={loop_label}"
            )
        return retry.success

    def _cancel_order_with_gateway(
        self,
        *,
        symbol: str,
        order_id: int,
        loop_label: str,
    ) -> bool:
        retry = cancel_order_with_retry_with_logging(
            OrderCancelRequest(symbol=symbol, order_id=int(order_id)),
            call=self._gateway_cancel_order_call,
            retry_policy=self._query_cancel_retry_policy(),
            loop_label=loop_label,
        )
        _log_trade(
            "Cancel order result: "
            f"symbol={symbol} order_id={order_id} success={retry.success} "
            f"reason={retry.reason_code} attempts={retry.attempts}"
        )
        return retry.success

    def _query_order_payload_by_id(
        self,
        *,
        symbol: str,
        order_id: int,
        loop_label: str,
    ) -> Optional[dict]:
        retry = query_order_with_retry_with_logging(
            OrderQueryRequest(symbol=symbol, order_id=int(order_id)),
            call=self._gateway_query_order_call,
            retry_policy=self._query_cancel_retry_policy(),
            loop_label=loop_label,
        )
        if not retry.success:
            _log_trade(
                "Query order result: "
                f"symbol={symbol} order_id={order_id} success={retry.success} "
                f"reason={retry.reason_code} attempts={retry.attempts} "
                "policy=query_cancel_reduced"
            )
            return None
        payload = retry.last_result.payload
        if not isinstance(payload, dict):
            return None
        return payload

    def _query_order_status_by_id(
        self,
        *,
        symbol: str,
        order_id: int,
        loop_label: str,
    ) -> str:
        payload = self._query_order_payload_by_id(
            symbol=symbol,
            order_id=order_id,
            loop_label=loop_label,
        )
        if not isinstance(payload, dict):
            return ""
        status = str(payload.get("status") or "").strip().upper()
        return status

    def _reset_runtime_after_external_clear(self, *, reason_code: str) -> None:
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
            updated = replace(
                runtime,
                symbol_state="IDLE",
                active_symbol=None,
                pending_trigger_candidates={},
                second_entry_order_pending=False,
            )
            self._orchestrator_runtime = updated
            self._sync_recovery_state_from_orchestrator_locked()
        self._entry_order_ref_by_symbol.clear()
        self._entry_cancel_sync_guard_until_by_symbol.clear()
        self._second_entry_skip_latch.clear()
        self._second_entry_fully_filled_symbols.clear()
        self._phase1_tp_filled_symbols.clear()
        self._last_open_exit_order_ids_by_symbol.clear()
        self._oco_last_filled_exit_order_by_symbol.clear()
        self._pending_oco_retry_symbols.clear()
        self._last_position_qty_by_symbol.clear()
        self._last_position_entry_price_by_symbol.clear()
        self._position_zero_confirm_streak_by_symbol.clear()
        _log_trade(f"Runtime reset after external clear: reason={reason_code}")

    @staticmethod
    def _default_retry_policy() -> RetryPolicy:
        return RetryPolicy(max_attempts=3)

    @staticmethod
    def _query_cancel_retry_policy() -> RetryPolicy:
        return RetryPolicy(
            max_attempts=QUERY_CANCEL_RETRY_MAX_ATTEMPTS,
            retryable_reason_codes=QUERY_CANCEL_RETRYABLE_REASON_CODES,
        )

    def _current_position_mode(self) -> str:
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
        position_mode = runtime.position_mode
        if position_mode in ("ONE_WAY", "HEDGE"):
            return str(position_mode)
        fetched = self._fetch_position_mode()
        if fetched in ("ONE_WAY", "HEDGE"):
            with self._auto_trade_runtime_lock:
                self._orchestrator_runtime = replace(self._orchestrator_runtime, position_mode=fetched)
                self._sync_recovery_state_from_orchestrator_locked()
            return fetched
        return "UNKNOWN"

    def _update_rate_limit_tracking(self, *, success: bool, reason_code: str, context: str) -> None:
        normalized_reason = str(reason_code or "").strip().upper()
        popup_required = False
        auth_lock_changed = False
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
            lock_changed = False
            if normalized_reason == "RATE_LIMIT":
                self._rate_limit_fail_streak += 1
                self._rate_limit_recover_streak = 0
                if (
                    self._rate_limit_fail_streak >= runtime.settings.rate_limit_fail_threshold
                    and not runtime.rate_limit_locked
                ):
                    runtime = replace(runtime, rate_limit_locked=True)
                    lock_changed = True
            elif normalized_reason == "AUTH_ERROR":
                self._rate_limit_fail_streak = 0
                self._rate_limit_recover_streak = 0
            else:
                self._rate_limit_fail_streak = 0
                if runtime.rate_limit_locked and success:
                    self._rate_limit_recover_streak += 1
                    if self._rate_limit_recover_streak >= runtime.settings.rate_limit_recovery_threshold:
                        runtime = replace(runtime, rate_limit_locked=False)
                        lock_changed = True
                        self._rate_limit_recover_streak = 0
                else:
                    self._rate_limit_recover_streak = 0

            if normalized_reason == "AUTH_ERROR":
                self._auth_error_recover_streak = 0
                if not runtime.auth_error_locked:
                    runtime = replace(runtime, auth_error_locked=True)
                    lock_changed = True
                    auth_lock_changed = True
                    popup_required = True
            elif runtime.auth_error_locked and success:
                self._auth_error_recover_streak += 1
                if self._auth_error_recover_streak >= runtime.settings.rate_limit_recovery_threshold:
                    runtime = replace(runtime, auth_error_locked=False)
                    lock_changed = True
                    auth_lock_changed = True
                    self._auth_error_recover_streak = 0
            elif runtime.auth_error_locked:
                self._auth_error_recover_streak = 0
            else:
                self._auth_error_recover_streak = 0

            if lock_changed:
                self._orchestrator_runtime = runtime
                self._sync_recovery_state_from_orchestrator_locked()
            rate_limit_locked = runtime.rate_limit_locked
            auth_error_locked = runtime.auth_error_locked

        if auth_lock_changed and not auth_error_locked:
            self._auth_error_popup_open = False
            _log_trade("AUTH_ERROR lock released after recovery threshold reached.")
        if popup_required:
            self._show_auth_error_popup_async(context=context)

        _log_trade(
            "Gateway lock tracker updated: "
            f"context={context} success={success} reason={normalized_reason or '-'} "
            f"fail_streak={self._rate_limit_fail_streak} recover_streak={self._rate_limit_recover_streak} "
            f"auth_recover_streak={self._auth_error_recover_streak} "
            f"rate_limit_locked={rate_limit_locked} auth_error_locked={auth_error_locked}"
        )

    def _show_auth_error_popup_async(self, *, context: str) -> None:
        now = time.time()
        if self._auth_error_popup_open:
            return
        if now - self._auth_error_popup_last_at < AUTH_ERROR_POPUP_THROTTLE_SEC:
            return
        self._auth_error_popup_last_at = now
        _log_trade(
            "AUTH_ERROR lock popup scheduled: "
            f"context={context} throttle_sec={AUTH_ERROR_POPUP_THROTTLE_SEC}"
        )

        def show_popup() -> None:
            self._auth_error_popup_open = True
            try:
                messagebox.showerror(
                    "API 권한 오류",
                    "Binance API 권한 오류가 감지되어 신규 진입이 잠금되었습니다.\n"
                    "API 키 권한/허용 IP를 확인한 뒤 복구해 주세요.",
                    parent=self,
                )
            except Exception as exc:
                _log_trade(f"AUTH_ERROR popup failed: error={exc!r}")
            finally:
                self._auth_error_popup_open = False

        self.after(0, show_popup)

    def _fetch_exchange_info_snapshot(self) -> dict:
        now = time.time()
        if self._exchange_info_cache is not None and now - self._exchange_info_cache_at < EXCHANGE_INFO_CACHE_TTL_SEC:
            return self._exchange_info_cache
        payload = self._binance_public_get(
            "https://fapi.binance.com",
            "/fapi/v1/exchangeInfo",
            caller="fetch_exchange_info_snapshot",
        )
        if isinstance(payload, dict):
            self._exchange_info_cache = payload
            self._exchange_info_cache_at = now
            return payload
        return self._exchange_info_cache or {"symbols": []}

    def _fetch_recent_3m_candles(self, symbol: str, limit: int = RECENT_KLINE_LIMIT) -> list[dict]:
        normalized = (symbol or "").strip().upper()
        if not normalized:
            return []
        requested_limit = max(2, int(limit))
        payload = self._binance_public_get(
            "https://fapi.binance.com",
            "/fapi/v1/klines",
            {"symbol": normalized, "interval": "3m", "limit": requested_limit},
            caller="fetch_recent_3m_candles",
        )
        if not isinstance(payload, list):
            payload_type = type(payload).__name__ if payload is not None else "NoneType"
            _log_trade(
                "Kline fetch returned non-list payload: "
                f"symbol={normalized} payload_type={payload_type} limit={requested_limit}"
            )
            return []
        candles: list[dict] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 7:
                continue
            high = self._safe_float(row[2])
            low = self._safe_float(row[3])
            close = self._safe_float(row[4])
            if high is None or low is None or close is None:
                continue
            candles.append(
                {
                    "timestamp": int(row[0]),
                    "close_time": int(row[6]),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                }
            )
        if len(candles) < 2:
            _log_trade(
                "Kline fetch insufficient candles: "
                f"symbol={normalized} usable={len(candles)} raw_rows={len(payload)} limit={requested_limit}"
            )
        return candles

    def _fetch_open_orders(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> Optional[list[dict]]:
        rows, _from_rest, _rate_limited = self._fetch_open_orders_with_meta(
            force_refresh=force_refresh,
            loop_label=loop_label,
        )
        return rows

    def _fetch_open_orders_with_meta(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> tuple[Optional[list[dict]], bool, bool]:
        if not self._api_key or not self._secret_key:
            return [], False, False
        now = time.time()
        cached_rows: Optional[list[dict]] = None
        cache_age = float("inf")
        with self._account_snapshot_cache_lock:
            if self._open_orders_cache is not None:
                cached_rows = self._copy_account_rows(self._open_orders_cache)
                cache_age = max(0.0, now - float(self._open_orders_cache_at))
        user_stream_healthy = self._is_user_stream_healthy()
        if (
            not force_refresh
            and cached_rows is not None
            and (
                cache_age <= ACCOUNT_SNAPSHOT_CACHE_TTL_SEC
                or (user_stream_healthy and cache_age <= ACCOUNT_SNAPSHOT_STALE_FALLBACK_SEC)
            )
        ):
            if cache_age > ACCOUNT_SNAPSHOT_CACHE_TTL_SEC and user_stream_healthy:
                _log_trade(
                    "Open orders cache reused under healthy user stream: "
                    f"age_sec={cache_age:.2f} loop={loop_label}"
                )
            return cached_rows, False, False

        rows, rate_limited = self._fetch_open_order_rows_from_endpoints(
            loop_label=f"{loop_label}-rest-open-orders",
        )
        if rows is not None:
            with self._account_snapshot_cache_lock:
                self._open_orders_cache = self._copy_account_rows(rows)
                self._open_orders_cache_at = now
            if force_refresh and rate_limited:
                self._note_account_rest_backoff(context=f"open_orders:{loop_label}")
                _log_trade(
                    "Open orders refresh rate-limited while partial/merged rows returned: "
                    f"loop={loop_label}"
                )
            return rows, True, rate_limited
        if force_refresh and rate_limited:
            self._note_account_rest_backoff(context=f"open_orders:{loop_label}")

        if cached_rows is not None and cache_age <= ACCOUNT_SNAPSHOT_STALE_FALLBACK_SEC:
            _log_trade(
                "Open orders snapshot fallback used: "
                f"age_sec={cache_age:.2f} force_refresh={force_refresh} loop={loop_label}"
            )
            return cached_rows, False, rate_limited

        _log_trade(
            "Open orders snapshot unavailable: "
            f"force_refresh={force_refresh} cache_age_sec={cache_age:.2f} loop={loop_label}"
        )
        return None, False, rate_limited

    def _fetch_futures_balance_rows(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> Optional[list[dict]]:
        if not self._api_key or not self._secret_key:
            return None
        now = time.time()
        cached_rows: Optional[list[dict]] = None
        cache_age = float("inf")
        with self._futures_balance_cache_lock:
            if self._futures_balance_cache is not None:
                cached_rows = [dict(item) for item in self._futures_balance_cache if isinstance(item, dict)]
                cache_age = max(0.0, now - float(self._futures_balance_cache_at))
        if not force_refresh and cached_rows is not None and cache_age <= FUTURES_BALANCE_CACHE_TTL_SEC:
            _log_trade(
                "Futures balance cache reused: "
                f"age_sec={cache_age:.2f} force_refresh={force_refresh} loop={loop_label}"
            )
            return cached_rows

        payload = self._binance_signed_get("https://fapi.binance.com", "/fapi/v2/balance")
        if not isinstance(payload, list):
            return None
        rows = [dict(item) for item in payload if isinstance(item, dict)]
        with self._futures_balance_cache_lock:
            self._futures_balance_cache = [dict(item) for item in rows]
            self._futures_balance_cache_at = now
        return rows

    def _fetch_futures_available_balance(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> Optional[float]:
        rows = self._fetch_futures_balance_rows(
            force_refresh=force_refresh,
            loop_label=f"{loop_label}-available",
        )
        if rows is None:
            return None
        for item in rows:
            if item.get("asset") != "USDT":
                continue
            value = self._safe_float(item.get("availableBalance"))
            if value is not None:
                return float(value)
        return None

    def _fetch_position_mode(self) -> str:
        if not self._api_key or not self._secret_key:
            return "UNKNOWN"
        payload = self._binance_signed_get("https://fapi.binance.com", POSITION_MODE_PATH)
        return self._parse_position_mode(payload)

    @staticmethod
    def _parse_multi_assets_margin_mode(payload: object) -> Optional[bool]:
        if not isinstance(payload, dict):
            return None
        raw = payload.get("multiAssetsMargin")
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in ("true", "false"):
                return lowered == "true"
        return None

    def _fetch_multi_assets_margin_mode(self) -> tuple[Optional[bool], str]:
        if not self._api_key or not self._secret_key:
            return None, "api_credentials_missing"
        payload = self._binance_signed_get("https://fapi.binance.com", MULTI_ASSETS_MARGIN_MODE_PATH)
        if payload is None:
            return None, "multi_assets_mode_fetch_response_none"
        mode = self._parse_multi_assets_margin_mode(payload)
        if mode is not None:
            return mode, "-"
        error_code, error_message = self._extract_exchange_error_from_payload(payload)
        if error_code < 0:
            reason_code = self._map_exchange_reason_code(error_code, error_message)
            return (
                None,
                f"multi_assets_mode_fetch_failed_{reason_code}:error_code={error_code} message={error_message or '-'}",
            )
        return None, f"multi_assets_mode_fetch_unexpected_payload_type:{type(payload).__name__}"

    def _set_multi_assets_margin_mode(self, *, enabled: bool) -> tuple[bool, str, str]:
        payload = self._binance_signed_post(
            "https://fapi.binance.com",
            MULTI_ASSETS_MARGIN_MODE_PATH,
            {"multiAssetsMargin": "true" if enabled else "false"},
        )
        if payload is None:
            return False, "MULTI_ASSETS_MODE_SET_FAILED_NETWORK_ERROR", "multi_assets_mode_set_response_none"
        error_code, error_message = self._extract_exchange_error_from_payload(payload)
        if error_code < 0:
            reason_code = self._map_exchange_reason_code(error_code, error_message)
            return (
                False,
                f"MULTI_ASSETS_MODE_SET_FAILED_{reason_code}",
                f"error_code={error_code} message={error_message or '-'}",
            )
        return True, "MULTI_ASSETS_MODE_SET_OK", "-"

    def _ensure_single_asset_mode_on_login(self) -> bool:
        if not self._api_key or not self._secret_key:
            _log_trade("Login asset mode sync skipped: reason=api_credentials_missing")
            self._single_asset_mode_ready = False
            return False
        _log_trade("Login asset mode sync started: target=single_asset")
        current_mode, fetch_failure = self._fetch_multi_assets_margin_mode()
        if current_mode is None:
            _log_trade(
                "Login asset mode sync skipped: "
                f"reason=multi_assets_mode_fetch_failed failure={fetch_failure}"
            )
            self._single_asset_mode_ready = False
            return False
        if current_mode is False:
            _log_trade("Login asset mode sync skipped: reason=already_single_asset")
            self._single_asset_mode_ready = True
            return True
        ok, reason_code, failure_reason = self._set_multi_assets_margin_mode(enabled=False)
        if not ok:
            _log_trade(
                "Login asset mode sync failed: "
                f"reason={reason_code} failure={failure_reason}"
            )
            self._single_asset_mode_ready = False
            return False
        _log_trade(
            "Login asset mode sync applied: "
            f"previous_mode=multi_asset current_mode=single_asset reason={reason_code}"
        )
        self._single_asset_mode_ready = True
        return True

    @staticmethod
    def _extract_exchange_error_from_payload(payload: object) -> tuple[int, str]:
        if not isinstance(payload, dict):
            return 0, ""
        code_raw = payload.get("code")
        message_raw = payload.get("msg")
        code = int(code_raw) if isinstance(code_raw, int) else 0
        message = str(message_raw) if isinstance(message_raw, str) else ""
        return code, message

    @staticmethod
    def _is_open_order_block_reason(*, error_code: int, error_message: str) -> bool:
        if int(error_code) in (-4047, -4067):
            return True
        lowered = str(error_message or "").lower()
        return ("open order" in lowered) or ("open orders" in lowered) or ("existing open" in lowered)

    @staticmethod
    def _is_margin_type_no_change_reason(*, error_code: int, error_message: str) -> bool:
        if int(error_code) == -4046:
            return True
        lowered = str(error_message or "").lower()
        return "no need to change margin type" in lowered

    @staticmethod
    def _is_leverage_no_change_reason(*, error_code: int, error_message: str) -> bool:
        lowered = str(error_message or "").lower()
        if "no need to change leverage" in lowered:
            return True
        if int(error_code) == -4028 and "already" in lowered and "leverage" in lowered:
            return True
        return False

    def _fetch_symbol_leverage_and_margin_type(
        self,
        *,
        symbol: str,
        loop_label: str,
    ) -> tuple[bool, int, str, str]:
        target = str(symbol or "").strip().upper()
        if not target:
            return False, 0, "UNKNOWN", "symbol_empty"
        if not self._api_key or not self._secret_key:
            return False, 0, "UNKNOWN", "api_credentials_missing"

        rows: list[dict] = []
        payload = self._binance_signed_get("https://fapi.binance.com", POSITION_RISK_PATH, {"symbol": target})
        if isinstance(payload, list):
            rows = [
                item
                for item in payload
                if isinstance(item, dict) and str(item.get("symbol") or "").strip().upper() == target
            ]
        elif isinstance(payload, dict):
            error_code, error_message = self._extract_exchange_error_from_payload(payload)
            reason_code = self._map_exchange_reason_code(error_code, error_message)
            self._update_rate_limit_tracking(
                success=False,
                reason_code=reason_code,
                context="pre_order_fetch_symbol_setup",
            )
            return (
                False,
                0,
                "UNKNOWN",
                f"position_risk_error_code={error_code} message={error_message or '-'}",
            )

        if not rows:
            fallback = self._binance_signed_get("https://fapi.binance.com", POSITION_RISK_PATH)
            if isinstance(fallback, list):
                rows = [
                    item
                    for item in fallback
                    if isinstance(item, dict) and str(item.get("symbol") or "").strip().upper() == target
                ]
            elif isinstance(fallback, dict):
                error_code, error_message = self._extract_exchange_error_from_payload(fallback)
                reason_code = self._map_exchange_reason_code(error_code, error_message)
                self._update_rate_limit_tracking(
                    success=False,
                    reason_code=reason_code,
                    context="pre_order_fetch_symbol_setup",
                )
                return (
                    False,
                    0,
                    "UNKNOWN",
                    f"position_risk_fallback_error_code={error_code} message={error_message or '-'}",
                )

        if not rows:
            self._update_rate_limit_tracking(
                success=False,
                reason_code="EXCHANGE_REJECTED",
                context="pre_order_fetch_symbol_setup",
            )
            return False, 0, "UNKNOWN", f"symbol_not_found_in_position_risk:{target}"

        leverage_raw = self._safe_float(rows[0].get("leverage"))
        margin_type_raw = str(rows[0].get("marginType") or "").strip().upper()
        margin_type = "CROSS" if margin_type_raw in ("CROSS", "CROSSED") else margin_type_raw
        if leverage_raw is None or leverage_raw <= 0:
            self._update_rate_limit_tracking(
                success=False,
                reason_code="EXCHANGE_REJECTED",
                context="pre_order_fetch_symbol_setup",
            )
            return False, 0, "UNKNOWN", f"invalid_leverage_value:{rows[0].get('leverage')!r}"
        if margin_type not in ("ISOLATED", "CROSS"):
            self._update_rate_limit_tracking(
                success=False,
                reason_code="EXCHANGE_REJECTED",
                context="pre_order_fetch_symbol_setup",
            )
            return False, 0, "UNKNOWN", f"invalid_margin_type:{margin_type or '-'}"

        leverage = int(round(float(leverage_raw)))
        self._update_rate_limit_tracking(
            success=True,
            reason_code="OK",
            context="pre_order_fetch_symbol_setup",
        )
        _log_trade(
            "Pre-order setup snapshot fetched: "
            f"symbol={target} leverage={leverage} margin_type={margin_type} loop={loop_label}"
        )
        return True, leverage, margin_type, "-"

    @staticmethod
    def _normalize_entry_mode(value: object) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in ENTRY_MODE_TO_TARGET_LEVERAGE:
            return normalized
        return "-"

    def _resolve_entry_mode_for_symbol_setup(
        self,
        *,
        symbol: str,
        trigger_kind: str,
        loop_label: str,
    ) -> str:
        target = str(symbol or "").strip().upper()
        normalized_trigger = str(trigger_kind or "").strip().upper()
        mode = "-"
        mode_source = "fallback"
        with self._auto_trade_runtime_lock:
            runtime = self._orchestrator_runtime
            candidate = runtime.pending_trigger_candidates.get(target)
        if candidate is not None:
            candidate_trigger = str(candidate.trigger_kind or "").strip().upper()
            if candidate_trigger == normalized_trigger:
                candidate_mode = self._normalize_entry_mode(candidate.entry_mode)
                if candidate_mode != "-":
                    mode = candidate_mode
                    mode_source = "pending_candidate"
        if mode == "-":
            fallback_mode = self._normalize_entry_mode(self._selected_entry_mode())
            if fallback_mode != "-":
                mode = fallback_mode
                mode_source = "ui_selected_mode"
            else:
                mode = ENTRY_MODE_CONSERVATIVE
                mode_source = "safe_default"
        _log_trade(
            "Pre-order entry mode resolved: "
            f"symbol={target} trigger={normalized_trigger or '-'} mode={mode} source={mode_source} loop={loop_label}"
        )
        return mode

    @staticmethod
    def _resolve_target_leverage_for_entry_mode(entry_mode: str) -> int:
        normalized = str(entry_mode or "").strip().upper()
        return int(ENTRY_MODE_TO_TARGET_LEVERAGE.get(normalized, 1))

    def _set_symbol_leverage_target(
        self,
        *,
        symbol: str,
        target_leverage: int,
        loop_label: str,
    ) -> tuple[bool, bool, str, str]:
        leverage_value = max(1, int(target_leverage))
        payload = self._binance_signed_post(
            "https://fapi.binance.com",
            LEVERAGE_SET_PATH,
            {"symbol": symbol, "leverage": leverage_value},
        )
        if payload is None:
            self._update_rate_limit_tracking(
                success=False,
                reason_code="NETWORK_ERROR",
                context="pre_order_set_leverage",
            )
            return False, False, "LEVERAGE_SET_FAILED_NETWORK_ERROR", "leverage_set_response_none"

        error_code, error_message = self._extract_exchange_error_from_payload(payload)
        if error_code < 0:
            if self._is_leverage_no_change_reason(error_code=error_code, error_message=error_message):
                self._update_rate_limit_tracking(
                    success=True,
                    reason_code="OK",
                    context="pre_order_set_leverage",
                )
                _log_trade(
                    "Pre-order leverage already set: "
                    f"symbol={symbol} target_leverage={leverage_value} "
                    f"error_code={error_code} message={error_message or '-'} loop={loop_label}"
                )
                return True, False, "LEVERAGE_ALREADY_TARGET", "-"
            reason_code = self._map_exchange_reason_code(error_code, error_message)
            self._update_rate_limit_tracking(
                success=False,
                reason_code=reason_code,
                context="pre_order_set_leverage",
            )
            open_order_blocked = self._is_open_order_block_reason(
                error_code=error_code,
                error_message=error_message,
            )
            failure_reason = f"error_code={error_code} message={error_message or '-'}"
            _log_trade(
                "Pre-order leverage set failed: "
                f"symbol={symbol} target_leverage={leverage_value} "
                f"reason={reason_code} open_order_blocked={open_order_blocked} "
                f"{failure_reason} loop={loop_label}"
            )
            return False, open_order_blocked, f"LEVERAGE_SET_FAILED_{reason_code}", failure_reason

        self._update_rate_limit_tracking(
            success=True,
            reason_code="OK",
            context="pre_order_set_leverage",
        )
        _log_trade(
            "Pre-order leverage set success: "
            f"symbol={symbol} target_leverage={leverage_value} payload={payload!r} loop={loop_label}"
        )
        return True, False, "LEVERAGE_SET_OK", "-"

    def _set_symbol_margin_type_isolated(
        self,
        *,
        symbol: str,
        loop_label: str,
    ) -> tuple[bool, bool, str, str]:
        payload = self._binance_signed_post(
            "https://fapi.binance.com",
            MARGIN_TYPE_SET_PATH,
            {"symbol": symbol, "marginType": "ISOLATED"},
        )
        if payload is None:
            self._update_rate_limit_tracking(
                success=False,
                reason_code="NETWORK_ERROR",
                context="pre_order_set_margin_type",
            )
            return False, False, "MARGIN_TYPE_SET_FAILED_NETWORK_ERROR", "margin_type_set_response_none"

        error_code, error_message = self._extract_exchange_error_from_payload(payload)
        if error_code < 0:
            if self._is_margin_type_no_change_reason(error_code=error_code, error_message=error_message):
                self._update_rate_limit_tracking(
                    success=True,
                    reason_code="OK",
                    context="pre_order_set_margin_type",
                )
                _log_trade(
                    "Pre-order margin type already set: "
                    f"symbol={symbol} error_code={error_code} message={error_message or '-'} loop={loop_label}"
                )
                return True, False, "MARGIN_TYPE_ALREADY_ISOLATED", "-"
            reason_code = self._map_exchange_reason_code(error_code, error_message)
            self._update_rate_limit_tracking(
                success=False,
                reason_code=reason_code,
                context="pre_order_set_margin_type",
            )
            open_order_blocked = self._is_open_order_block_reason(
                error_code=error_code,
                error_message=error_message,
            )
            failure_reason = f"error_code={error_code} message={error_message or '-'}"
            _log_trade(
                "Pre-order margin type set failed: "
                f"symbol={symbol} reason={reason_code} open_order_blocked={open_order_blocked} "
                f"{failure_reason} loop={loop_label}"
            )
            return False, open_order_blocked, f"MARGIN_TYPE_SET_FAILED_{reason_code}", failure_reason

        self._update_rate_limit_tracking(
            success=True,
            reason_code="OK",
            context="pre_order_set_margin_type",
        )
        _log_trade(
            "Pre-order margin type set success: "
            f"symbol={symbol} payload={payload!r} loop={loop_label}"
        )
        return True, False, "MARGIN_TYPE_SET_OK", "-"

    def _apply_symbol_trading_setup_once(
        self,
        *,
        symbol: str,
        current_leverage: int,
        target_leverage: int,
        entry_mode: str,
        margin_type: str,
        loop_label: str,
    ) -> tuple[bool, bool, str, str]:
        target = str(symbol or "").strip().upper()
        current_margin_type = str(margin_type or "").strip().upper()
        normalized_entry_mode = self._normalize_entry_mode(entry_mode)
        if int(current_leverage) == int(target_leverage) and current_margin_type == "ISOLATED":
            return True, False, "SYMBOL_SETUP_ALREADY_ALIGNED", "-"

        if int(current_leverage) != int(target_leverage):
            ok, open_order_blocked, reason_code, failure_reason = self._set_symbol_leverage_target(
                symbol=target,
                target_leverage=int(target_leverage),
                loop_label=f"{loop_label}-set-leverage",
            )
            if not ok:
                return False, open_order_blocked, reason_code, failure_reason

        if current_margin_type != "ISOLATED":
            ok, open_order_blocked, reason_code, failure_reason = self._set_symbol_margin_type_isolated(
                symbol=target,
                loop_label=f"{loop_label}-set-margin",
            )
            if not ok:
                return False, open_order_blocked, reason_code, failure_reason

        _log_trade(
            "Pre-order symbol setup aligned with mode: "
            f"symbol={target} entry_mode={normalized_entry_mode} "
            f"target_leverage={int(target_leverage)} margin_type=ISOLATED loop={loop_label}"
        )
        return True, False, "SYMBOL_SETUP_UPDATED", "-"

    def _ensure_symbol_trading_setup_for_entry(
        self,
        *,
        symbol: str,
        entry_mode: str,
        target_leverage: int,
        loop_label: str,
    ) -> tuple[bool, str, str]:
        target = str(symbol or "").strip().upper()
        normalized_entry_mode = self._normalize_entry_mode(entry_mode)
        desired_leverage = max(1, int(target_leverage))
        snapshot_ok, leverage, margin_type, snapshot_failure = self._fetch_symbol_leverage_and_margin_type(
            symbol=target,
            loop_label=f"{loop_label}-snapshot",
        )
        if not snapshot_ok:
            _log_trade(
                "Pre-order setup snapshot failed: "
                f"symbol={target} entry_mode={normalized_entry_mode} "
                f"target_leverage={desired_leverage} failure={snapshot_failure} loop={loop_label}"
            )
            return False, "SYMBOL_SETUP_FETCH_FAILED", snapshot_failure

        if int(leverage) == desired_leverage and str(margin_type).upper() == "ISOLATED":
            _log_trade(
                "Pre-order setup skipped (already aligned): "
                f"symbol={target} entry_mode={normalized_entry_mode} "
                f"target_leverage={desired_leverage} leverage={leverage} margin_type={margin_type} loop={loop_label}"
            )
            return True, "SYMBOL_SETUP_ALREADY_ALIGNED", "-"

        cancel_attempted = False
        for attempt in (1, 2):
            setup_ok, open_order_blocked, reason_code, failure_reason = self._apply_symbol_trading_setup_once(
                symbol=target,
                current_leverage=leverage,
                target_leverage=desired_leverage,
                entry_mode=normalized_entry_mode,
                margin_type=margin_type,
                loop_label=f"{loop_label}-attempt-{attempt}",
            )
            if setup_ok:
                _log_trade(
                    "Pre-order setup applied: "
                    f"symbol={target} entry_mode={normalized_entry_mode} "
                    f"target_leverage={desired_leverage} attempt={attempt} reason={reason_code} loop={loop_label}"
                )
                return True, reason_code, "-"
            if open_order_blocked and not cancel_attempted:
                cancel_attempted = True
                _log_trade(
                    "Pre-order setup blocked by open orders; retrying after symbol cancel: "
                    f"symbol={target} entry_mode={normalized_entry_mode} "
                    f"target_leverage={desired_leverage} reason={reason_code} failure={failure_reason} "
                    f"loop={loop_label}"
                )
                self._cancel_open_orders_for_symbols(
                    symbols=[target],
                    loop_label=f"{loop_label}-cancel-open-orders",
                )
                snapshot_ok, leverage, margin_type, snapshot_failure = self._fetch_symbol_leverage_and_margin_type(
                    symbol=target,
                    loop_label=f"{loop_label}-snapshot-retry",
                )
                if not snapshot_ok:
                    return False, "SYMBOL_SETUP_FETCH_FAILED_AFTER_CANCEL", snapshot_failure
                continue
            return False, reason_code, failure_reason

        return False, "SYMBOL_SETUP_APPLY_FAILED", "setup_retry_exhausted"

    def _run_pre_order_setup_hook(
        self,
        symbol: str,
        trigger_kind: str,
        loop_label: str,
    ) -> tuple[bool, str, str, bool]:
        target = str(symbol or "").strip().upper()
        normalized_trigger = str(trigger_kind or "").strip().upper()
        if not target:
            return False, "INVALID_SYMBOL", "symbol_empty", False
        entry_mode = self._resolve_entry_mode_for_symbol_setup(
            symbol=target,
            trigger_kind=normalized_trigger,
            loop_label=loop_label,
        )
        target_leverage = self._resolve_target_leverage_for_entry_mode(entry_mode)
        _log_trade(
            "Pre-order target leverage resolved: "
            f"symbol={target} trigger={normalized_trigger or '-'} "
            f"entry_mode={entry_mode} target_leverage={target_leverage} loop={loop_label}"
        )
        setup_ok, reason_code, failure_reason = self._ensure_symbol_trading_setup_for_entry(
            symbol=target,
            entry_mode=entry_mode,
            target_leverage=target_leverage,
            loop_label=f"{loop_label}-pre-order-{normalized_trigger}",
        )
        if setup_ok:
            return True, reason_code, "-", False
        return False, reason_code, failure_reason, True

    def _reject_pre_order_when_position_mode_unknown(
        self,
        symbol: str,
        trigger_kind: str,
        loop_label: str,
    ) -> tuple[bool, str, str, bool]:
        target = str(symbol or "").strip().upper()
        normalized_trigger = str(trigger_kind or "").strip().upper()
        _log_trade(
            "Pre-order setup rejected: "
            f"reason=position_mode_unknown symbol={target or '-'} trigger={normalized_trigger or '-'} loop={loop_label}"
        )
        return False, "POSITION_MODE_UNKNOWN", "position_mode_unknown", False

    @staticmethod
    def _to_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "1", "yes"):
                return True
            if lowered in ("false", "0", "no"):
                return False
        return bool(value)

    @staticmethod
    def _normalize_order_type_token(value: object) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _is_algo_order_type(value: object) -> bool:
        return TradePage._normalize_order_type_token(value) in ALGO_ORDER_TYPES

    @staticmethod
    def _is_algo_endpoint_required_payload(payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        code = payload.get("code")
        if isinstance(code, int) and int(code) == -4120:
            return True
        message = str(payload.get("msg") or "").lower()
        return "algo order" in message and "endpoint" in message

    @staticmethod
    def _is_order_not_found_payload(payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        code = payload.get("code")
        if isinstance(code, int) and int(code) in (-2011, -2013):
            return True
        message = str(payload.get("msg") or "").lower()
        return "unknown order" in message or "does not exist" in message

    @staticmethod
    def _strip_gateway_internal_params(params: Mapping[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for raw_key, value in dict(params).items():
            key = str(raw_key)
            if key.startswith("_"):
                continue
            cleaned[key] = value
        return cleaned

    @staticmethod
    def _prepare_algo_create_params(params: Mapping[str, Any]) -> dict[str, Any]:
        adapted = dict(params)
        adapted["algoType"] = "CONDITIONAL"
        if "stopPrice" in adapted:
            if "triggerPrice" not in adapted:
                adapted["triggerPrice"] = adapted.get("stopPrice")
            adapted.pop("stopPrice", None)
        if "newClientOrderId" in adapted:
            if not str(adapted.get("clientAlgoId") or "").strip():
                adapted["clientAlgoId"] = adapted.get("newClientOrderId")
            adapted.pop("newClientOrderId", None)
        for bool_key in ("closePosition", "reduceOnly"):
            if isinstance(adapted.get(bool_key), bool):
                adapted[bool_key] = "true" if bool(adapted[bool_key]) else "false"
        return adapted

    @staticmethod
    def _prepare_algo_reference_params(params: Mapping[str, Any]) -> dict[str, Any]:
        adapted = dict(params)
        if "orderId" in adapted and "algoId" not in adapted:
            adapted["algoId"] = adapted.get("orderId")
            adapted.pop("orderId", None)
        if "origClientOrderId" in adapted and "clientAlgoId" not in adapted:
            adapted["clientAlgoId"] = adapted.get("origClientOrderId")
            adapted.pop("origClientOrderId", None)
        if "newClientOrderId" in adapted and "clientAlgoId" not in adapted:
            adapted["clientAlgoId"] = adapted.get("newClientOrderId")
            adapted.pop("newClientOrderId", None)
        return adapted

    def _prepare_reference_params_for_path(
        self,
        *,
        path: str,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        if str(path) == FUTURES_ALGO_ORDER_PATH:
            return self._prepare_algo_reference_params(params)
        return dict(params)

    @staticmethod
    def _normalize_open_order_row(row: Mapping[str, Any], *, is_algo_order: bool) -> Optional[dict]:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            return None
        normalized = dict(row)
        normalized["symbol"] = symbol
        normalized["_algo_order"] = bool(is_algo_order)

        order_id = 0
        try:
            order_id = int(normalized.get("orderId") or 0)
        except (TypeError, ValueError):
            order_id = 0
        if order_id <= 0:
            try:
                algo_id = int(normalized.get("algoId") or 0)
            except (TypeError, ValueError):
                algo_id = 0
            if algo_id > 0:
                order_id = algo_id
                normalized["orderId"] = int(algo_id)

        status = str(normalized.get("status") or "").strip().upper()
        if not status:
            fallback_status = str(
                normalized.get("orderStatus")
                or normalized.get("algoStatus")
                or ""
            ).strip().upper()
            if fallback_status:
                status = fallback_status
                normalized["status"] = fallback_status

        order_type = str(normalized.get("type") or "").strip().upper()
        if order_type:
            normalized["type"] = order_type
        else:
            fallback_type = str(
                normalized.get("orderType")
                or normalized.get("origType")
                or ""
            ).strip().upper()
            if fallback_type:
                order_type = fallback_type
                normalized["type"] = fallback_type
                normalized["_type_source"] = "orderType" if normalized.get("orderType") else "origType"

        side = str(normalized.get("side") or "").strip().upper()
        if not side:
            fallback_side = str(
                normalized.get("orderSide")
                or normalized.get("S")
                or ""
            ).strip().upper()
            if fallback_side:
                normalized["side"] = fallback_side

        orig_qty = TradePage._safe_float(normalized.get("origQty"))
        if (orig_qty is None or orig_qty <= 0.0) and is_algo_order:
            qty_fallback = TradePage._safe_float(
                normalized.get("quantity")
                or normalized.get("origQuantity")
            )
            if qty_fallback is not None and qty_fallback > 0.0:
                normalized["origQty"] = str(float(qty_fallback))

        update_time = 0
        try:
            update_time = int(normalized.get("updateTime") or 0)
        except (TypeError, ValueError):
            update_time = 0
        if update_time <= 0:
            for key in ("time", "timestamp", "workingTime", "createTime"):
                try:
                    candidate = int(normalized.get(key) or 0)
                except (TypeError, ValueError):
                    candidate = 0
                if candidate > 0:
                    normalized["updateTime"] = candidate
                    break

        if order_type in ALGO_ORDER_TYPES:
            stop_price, stop_source = TradePage._select_effective_stop_price(normalized)
            if stop_price is not None:
                normalized["stopPrice"] = str(stop_price)
                if stop_source and stop_source != "stopPrice":
                    normalized["_stop_price_source"] = stop_source
        return normalized

    def _merge_open_order_rows(
        self,
        *,
        regular_rows: list[dict],
        algo_rows: list[dict],
        loop_label: str,
    ) -> list[dict]:
        merged: list[dict] = []
        seen: set[tuple[str, int, str, str, str]] = set()
        for rows, is_algo_order in ((regular_rows, False), (algo_rows, True)):
            for raw in rows:
                normalized = self._normalize_open_order_row(raw, is_algo_order=is_algo_order)
                if normalized is None:
                    continue
                symbol = str(normalized.get("symbol") or "").strip().upper()
                order_id = self._safe_int(normalized.get("orderId"))
                stop_source = str(normalized.get("_stop_price_source") or "").strip()
                type_source = str(normalized.get("_type_source") or "").strip()
                if stop_source:
                    _log_trade(
                        "Open-order stop price fallback applied: "
                        f"symbol={symbol} order_id={order_id} source={stop_source} "
                        f"stop_price={normalized.get('stopPrice')} loop={loop_label}"
                    )
                if type_source:
                    _log_trade(
                        "Open-order type fallback applied: "
                        f"symbol={symbol} order_id={order_id} source={type_source} "
                        f"type={normalized.get('type')} loop={loop_label}"
                    )
                client_order_id = str(
                    normalized.get("clientOrderId")
                    or normalized.get("origClientOrderId")
                    or normalized.get("newClientOrderId")
                    or ""
                ).strip()
                order_type = str(normalized.get("type") or "").strip().upper()
                side = str(normalized.get("side") or "").strip().upper()
                key = (symbol, int(order_id), client_order_id, order_type, side)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(normalized)
        _log_trade(
            "Open-order rows merged: "
            f"regular={len(regular_rows)} algo={len(algo_rows)} merged={len(merged)} loop={loop_label}"
        )
        return merged

    def _fetch_open_order_rows_from_endpoints(
        self,
        *,
        loop_label: str,
    ) -> tuple[Optional[list[dict]], bool]:
        regular_payload = self._binance_signed_get("https://fapi.binance.com", FUTURES_OPEN_ORDERS_PATH)
        algo_payload = self._binance_signed_get("https://fapi.binance.com", FUTURES_OPEN_ALGO_ORDERS_PATH)

        regular_rows = [item for item in regular_payload if isinstance(item, dict)] if isinstance(regular_payload, list) else None
        algo_rows = [item for item in algo_payload if isinstance(item, dict)] if isinstance(algo_payload, list) else None
        rate_limited = self._is_rate_limit_payload(regular_payload) or self._is_rate_limit_payload(algo_payload)

        if regular_rows is None and algo_rows is None:
            _log_trade(
                "Open-order endpoint fetch failed: "
                f"regular_type={type(regular_payload).__name__} "
                f"algo_type={type(algo_payload).__name__} loop={loop_label}"
            )
            return None, rate_limited

        merged = self._merge_open_order_rows(
            regular_rows=regular_rows or [],
            algo_rows=algo_rows or [],
            loop_label=loop_label,
        )
        if regular_rows is None or algo_rows is None:
            _log_trade(
                "Open-order endpoint partial fetch: "
                f"regular_ok={regular_rows is not None} algo_ok={algo_rows is not None} "
                f"merged={len(merged)} loop={loop_label}"
            )
        return merged, rate_limited

    def _is_cached_algo_order(self, *, symbol: str, order_id: int) -> bool:
        target = str(symbol or "").strip().upper()
        if not target or int(order_id) <= 0:
            return False
        with self._account_snapshot_cache_lock:
            rows = self._copy_account_rows(self._open_orders_cache or [])
        for row in rows:
            if str(row.get("symbol") or "").strip().upper() != target:
                continue
            if self._safe_int(row.get("orderId")) != int(order_id):
                continue
            if bool(row.get("_algo_order")):
                return True
            if self._is_algo_order_type(row.get("type")):
                return True
        return False

    def _resolve_order_reference_path(self, params: Mapping[str, Any]) -> str:
        order_type_hint = self._normalize_order_type_token(params.get("_orderType") or params.get("type"))
        if self._is_algo_order_type(order_type_hint):
            return FUTURES_ALGO_ORDER_PATH
        symbol = str(params.get("symbol") or "").strip().upper()
        order_id = self._safe_int(params.get("orderId"))
        if self._is_cached_algo_order(symbol=symbol, order_id=order_id):
            return FUTURES_ALGO_ORDER_PATH
        return FUTURES_ORDER_PATH

    def _resolve_create_order_path(self, params: Mapping[str, Any]) -> str:
        order_type = self._normalize_order_type_token(params.get("type"))
        if self._is_algo_order_type(order_type):
            return FUTURES_ALGO_ORDER_PATH
        return FUTURES_ORDER_PATH

    def _gateway_create_order_call(self, params: Mapping[str, Any]) -> GatewayCallResult:
        raw_params = self._strip_gateway_internal_params(params)
        path = self._resolve_create_order_path(raw_params)
        request_params = (
            self._prepare_algo_create_params(raw_params)
            if path == FUTURES_ALGO_ORDER_PATH
            else dict(raw_params)
        )
        _log_trade(
            "Gateway create endpoint selected: "
            f"path={path} symbol={request_params.get('symbol')} type={request_params.get('type')}"
        )
        response = self._binance_signed_post("https://fapi.binance.com", path, request_params)
        if isinstance(response, dict) and ("orderId" in response or "algoId" in response):
            result = GatewayCallResult(ok=True, reason_code="OK", payload=response)
            self._update_rate_limit_tracking(success=True, reason_code=result.reason_code, context="gateway_create")
            return result
        if response is None:
            result = GatewayCallResult(ok=False, reason_code="NETWORK_ERROR")
            self._update_rate_limit_tracking(success=False, reason_code=result.reason_code, context="gateway_create")
            return result
        error_code = response.get("code") if isinstance(response, dict) else None
        error_message = response.get("msg") if isinstance(response, dict) else None
        reason_code = self._map_exchange_reason_code(error_code, error_message)
        result = GatewayCallResult(
            ok=False,
            reason_code=reason_code,
            payload=response if isinstance(response, dict) else None,
            error_code=int(error_code) if isinstance(error_code, int) else None,
            error_message=str(error_message) if error_message is not None else None,
        )
        self._update_rate_limit_tracking(success=False, reason_code=result.reason_code, context="gateway_create")
        return result

    def _gateway_cancel_order_call(self, params: Mapping[str, Any]) -> GatewayCallResult:
        raw_params = self._strip_gateway_internal_params(params)
        primary_path = self._resolve_order_reference_path(params)
        fallback_path = FUTURES_ALGO_ORDER_PATH if primary_path == FUTURES_ORDER_PATH else FUTURES_ORDER_PATH
        primary_params = self._prepare_reference_params_for_path(path=primary_path, params=raw_params)

        _log_trade(
            "Gateway cancel endpoint selected: "
            f"path={primary_path} symbol={raw_params.get('symbol')} order_id={raw_params.get('orderId')}"
        )
        response = self._binance_signed_delete("https://fapi.binance.com", primary_path, primary_params)
        if isinstance(response, dict) and (
            "orderId" in response
            or "algoId" in response
            or str(response.get("status", "")).upper() in ("CANCELED", "EXPIRED")
        ):
            result = GatewayCallResult(ok=True, reason_code="OK", payload=response)
            self._update_rate_limit_tracking(success=True, reason_code=result.reason_code, context="gateway_cancel")
            return result

        should_retry_other_endpoint = self._is_algo_endpoint_required_payload(response) or self._is_order_not_found_payload(response)
        if should_retry_other_endpoint and response is not None:
            fallback_params = self._prepare_reference_params_for_path(path=fallback_path, params=raw_params)
            _log_trade(
                "Gateway cancel fallback endpoint attempt: "
                f"primary={primary_path} fallback={fallback_path} "
                f"symbol={raw_params.get('symbol')} order_id={raw_params.get('orderId')} "
                f"response={response!r}"
            )
            fallback_response = self._binance_signed_delete(
                "https://fapi.binance.com",
                fallback_path,
                fallback_params,
            )
            if isinstance(fallback_response, dict) and (
                "orderId" in fallback_response
                or "algoId" in fallback_response
                or str(fallback_response.get("status", "")).upper() in ("CANCELED", "EXPIRED")
            ):
                result = GatewayCallResult(ok=True, reason_code="OK", payload=fallback_response)
                self._update_rate_limit_tracking(success=True, reason_code=result.reason_code, context="gateway_cancel")
                return result
            if fallback_response is not None:
                response = fallback_response

        if response is None:
            result = GatewayCallResult(ok=False, reason_code="NETWORK_ERROR")
            self._update_rate_limit_tracking(success=False, reason_code=result.reason_code, context="gateway_cancel")
            return result
        error_code = response.get("code") if isinstance(response, dict) else None
        error_message = response.get("msg") if isinstance(response, dict) else None
        reason_code = self._map_exchange_reason_code(error_code, error_message)
        result = GatewayCallResult(
            ok=False,
            reason_code=reason_code,
            payload=response if isinstance(response, dict) else None,
            error_code=int(error_code) if isinstance(error_code, int) else None,
            error_message=str(error_message) if error_message is not None else None,
        )
        self._update_rate_limit_tracking(success=False, reason_code=result.reason_code, context="gateway_cancel")
        return result

    def _gateway_query_order_call(self, params: Mapping[str, Any]) -> GatewayCallResult:
        raw_params = self._strip_gateway_internal_params(params)
        primary_path = self._resolve_order_reference_path(params)
        fallback_path = FUTURES_ALGO_ORDER_PATH if primary_path == FUTURES_ORDER_PATH else FUTURES_ORDER_PATH
        primary_params = self._prepare_reference_params_for_path(path=primary_path, params=raw_params)
        _log_trade(
            "Gateway query endpoint selected: "
            f"path={primary_path} symbol={raw_params.get('symbol')} order_id={raw_params.get('orderId')}"
        )
        response = self._binance_signed_get("https://fapi.binance.com", primary_path, primary_params)
        if isinstance(response, dict) and (response.get("orderId") is not None or response.get("algoId") is not None):
            result = GatewayCallResult(ok=True, reason_code="OK", payload=response)
            self._update_rate_limit_tracking(success=True, reason_code=result.reason_code, context="gateway_query")
            return result

        should_retry_other_endpoint = self._is_algo_endpoint_required_payload(response) or self._is_order_not_found_payload(response)
        if should_retry_other_endpoint and response is not None:
            fallback_params = self._prepare_reference_params_for_path(path=fallback_path, params=raw_params)
            _log_trade(
                "Gateway query fallback endpoint attempt: "
                f"primary={primary_path} fallback={fallback_path} "
                f"symbol={raw_params.get('symbol')} order_id={raw_params.get('orderId')} "
                f"response={response!r}"
            )
            fallback_response = self._binance_signed_get(
                "https://fapi.binance.com",
                fallback_path,
                fallback_params,
            )
            if isinstance(fallback_response, dict) and (
                fallback_response.get("orderId") is not None or fallback_response.get("algoId") is not None
            ):
                result = GatewayCallResult(ok=True, reason_code="OK", payload=fallback_response)
                self._update_rate_limit_tracking(success=True, reason_code=result.reason_code, context="gateway_query")
                return result
            if fallback_response is not None:
                response = fallback_response

        if response is None:
            result = GatewayCallResult(ok=False, reason_code="NETWORK_ERROR")
            self._update_rate_limit_tracking(success=False, reason_code=result.reason_code, context="gateway_query")
            return result
        error_code = response.get("code") if isinstance(response, dict) else None
        error_message = response.get("msg") if isinstance(response, dict) else None
        reason_code = self._map_exchange_reason_code(error_code, error_message)
        result = GatewayCallResult(
            ok=False,
            reason_code=reason_code,
            payload=response if isinstance(response, dict) else None,
            error_code=int(error_code) if isinstance(error_code, int) else None,
            error_message=str(error_message) if error_message is not None else None,
        )
        self._update_rate_limit_tracking(success=False, reason_code=result.reason_code, context="gateway_query")
        return result

    @staticmethod
    def _map_exchange_reason_code(error_code: object, error_message: object) -> str:
        if isinstance(error_code, int):
            if error_code in (-2014, -2015):
                return "AUTH_ERROR"
            if error_code == -2019:
                return "INSUFFICIENT_MARGIN"
            if error_code in (-1003, -1015):
                return "RATE_LIMIT"
            if error_code in (-1021, -1022):
                return "TEMPORARY_UNAVAILABLE"
            if error_code <= -2000:
                return "EXCHANGE_REJECTED"
        if isinstance(error_message, str):
            lowered = error_message.lower()
            if "invalid api-key" in lowered or "permission" in lowered:
                return "AUTH_ERROR"
            if "insufficient margin" in lowered:
                return "INSUFFICIENT_MARGIN"
            if "rate limit" in lowered or "too many requests" in lowered:
                return "RATE_LIMIT"
        return "EXCHANGE_REJECTED"

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
        if self._filter_controls_locked:
            _log_trade("Filter settings save ignored: reason=controls_locked")
            return
        if not self._save_enabled:
            return
        self._saved_filter_settings = self._current_filter_settings()
        _log_trade(
            "Filter settings saved: "
            f"mdd={self._saved_filter_settings.get('mdd')} "
            f"tp_ratio={self._saved_filter_settings.get('tp_ratio')} "
            f"risk_filter={self._saved_filter_settings.get('risk_filter')}"
        )
        self._update_filter_save_state()

    def _handle_filter_reset(self, _event=None) -> None:
        if self._filter_controls_locked:
            _log_trade("Filter settings reset ignored: reason=controls_locked")
            return
        defaults = self._default_filter_settings()
        self.mdd_dropdown.set(defaults["mdd"])
        self.tp_ratio_dropdown.set(defaults["tp_ratio"])
        self.risk_filter_dropdown.set(defaults["risk_filter"])
        _log_trade(
            "Filter settings reset to defaults: "
            f"mdd={defaults.get('mdd')} tp_ratio={defaults.get('tp_ratio')} risk_filter={defaults.get('risk_filter')}"
        )
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
        controls_locked = self._filter_controls_locked
        save_enabled = self._save_enabled and not controls_locked
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
        reset_enabled = not controls_locked
        reset_fill = RESET_SETTINGS_FILL if reset_enabled else SAVE_SETTINGS_DISABLED_FILL
        self._draw_rounded_button(
            offset_rect(RESET_SETTINGS_BUTTON_RECT, offset_y),
            "기본값 변환",
            reset_fill,
            "filter_reset",
            active=False,
            hover=self._button_hover.get("filter_reset", False) if reset_enabled else False,
            lift=self._button_lift.get("filter_reset", 0.0) if reset_enabled else 0.0,
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

        self._draw_monitor_rows(rx, ry)

    @staticmethod
    def _format_monitor_price(value: float) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "-"
        if numeric <= 0:
            return "-"
        text = f"{numeric:.8f}".rstrip("0").rstrip(".")
        return text if text else "0"

    @staticmethod
    def _entry_mode_to_label(entry_mode: object) -> str:
        normalized = str(entry_mode or "").strip().upper()
        if normalized == "CONSERVATIVE":
            return "보수적"
        if normalized == "AGGRESSIVE":
            return "공격적"
        return "-"

    @staticmethod
    def _trigger_kind_to_label(trigger_kind: object) -> str:
        normalized = str(trigger_kind or "").strip().upper()
        if normalized == "FIRST_ENTRY":
            return "1차진입"
        if normalized == "SECOND_ENTRY":
            return "2차진입"
        if normalized == "TP":
            return "TP"
        if normalized == "BREAKEVEN":
            return "본절"
        return normalized if normalized else "-"

    def _log_monitor_snapshot_if_changed(self, rows: list[dict[str, str]]) -> None:
        snapshot = "|".join(
            f"{row['symbol']},{row['filter_mode']},{row['status']},{row['target_price']}" for row in rows
        )
        if snapshot == self._last_monitor_snapshot:
            return
        self._last_monitor_snapshot = snapshot
        _log_trade(
            "Monitor board refreshed: "
            f"row_count={len(rows)} snapshot={snapshot if snapshot else '-'}"
        )

    def _build_monitor_rows(self) -> list[dict[str, str]]:
        with self._auto_trade_runtime_lock:
            candidates = list(self._orchestrator_runtime.pending_trigger_candidates.values())
        if not candidates:
            self._log_monitor_snapshot_if_changed([])
            return []

        ordered = sorted(
            candidates,
            key=lambda item: (int(item.received_at_local), int(item.message_id)),
            reverse=True,
        )
        default_mode = "보수적" if (self.risk_filter_dropdown.get() or "").strip() == "보수적" else "공격적"
        rows: list[dict[str, str]] = []
        for candidate in ordered[:MONITOR_MAX_ROWS]:
            mode_label = self._entry_mode_to_label(getattr(candidate, "entry_mode", None))
            if mode_label == "-":
                mode_label = default_mode
            rows.append(
                {
                    "symbol": str(candidate.symbol or "").strip().upper(),
                    "filter_mode": mode_label,
                    "status": self._trigger_kind_to_label(candidate.trigger_kind),
                    "target_price": self._format_monitor_price(candidate.target_price),
                }
            )
        self._log_monitor_snapshot_if_changed(rows)
        return rows

    def _draw_monitor_rows(self, rx, ry) -> None:
        rows = self._build_monitor_rows()
        if not rows:
            self.canvas.create_text(
                (rx(0) + rx(1)) / 2,
                ry(MONITOR_EMPTY_TEXT_Y),
                text="모니터링 대상 없음",
                font=self.fonts["table_row_sub"],
                fill=TABLE_ROW_TEXT,
                anchor="center",
                tags="ui",
            )
            return

        for idx, row in enumerate(rows[:MONITOR_MAX_ROWS]):
            y = ry(MONITOR_ROW_FIRST_Y + idx * MONITOR_ROW_STEP)
            self.canvas.create_text(
                rx(MONITOR_COL_SYMBOL_X),
                y,
                text=row["symbol"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(MONITOR_COL_FILTER_X),
                y,
                text=row["filter_mode"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(MONITOR_COL_STATUS_X),
                y,
                text=row["status"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
                anchor="w",
                tags="ui",
            )
            self.canvas.create_text(
                rx(MONITOR_COL_ENTRY_X),
                y,
                text=row["target_price"],
                font=self.fonts["table_row"],
                fill=TABLE_ROW_TEXT,
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
        auto_trade_status_text = self._current_auto_trade_status_text()
        self._log_auto_trade_status_snapshot_if_changed(auto_trade_status_text)

        lines = [
            ("MDD :", settings.get("mdd") or "N%"),
            ("TP-Ratio :", settings.get("tp_ratio") or "N%"),
            ("필터링 성향 :", settings.get("risk_filter") or "보수적/공격적"),
            ("현재 자동매매 상태 :", auto_trade_status_text),
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

    def _current_auto_trade_status_text(self) -> str:
        with self._auto_trade_runtime_lock:
            running = bool(self._auto_trade_starting or self._auto_trade_state.signal_loop_running)
        return "🚀실행중" if running else "❌중단됨"

    def _log_auto_trade_status_snapshot_if_changed(self, status_text: str) -> None:
        normalized = str(status_text or "").strip()
        if normalized == self._last_auto_trade_status_snapshot:
            return
        self._last_auto_trade_status_snapshot = normalized
        _log_trade(f"Wallet auto-trade status refreshed: status={normalized}")

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
        result = self._binance_signed_post("https://fapi.binance.com", FUTURES_ORDER_PATH, params)
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
            if not self._ensure_single_asset_mode_on_login():
                _log_trade("Wallet fetch skipped: reason=single_asset_mode_not_ready")
                return
            restrictions = self._fetch_api_restrictions()
            if not restrictions:
                self._set_wallet_failure_async()
                return
            if not (restrictions.get("enableReading") and restrictions.get("enableFutures")):
                self._set_wallet_failure_async()
                return
            balance = self._fetch_futures_balance(loop_label="wallet-fetch-balance")
            if balance is None:
                self._set_wallet_failure_async()
                return
            self._sync_wallet_balance_to_sheet(balance)
            positions = self._fetch_open_positions()
            positions_rows = positions or []

            def apply_wallet_snapshot() -> None:
                self._set_wallet_value(balance)
                self._set_positions(positions_rows)
                self._request_wallet_limit_auto_stop_if_needed(
                    balance=balance,
                    positions=positions_rows,
                    source="wallet-fetch",
                )

            self.after(0, apply_wallet_snapshot)
        except Exception:
            self._set_wallet_failure_async()

    def _fetch_api_restrictions(self) -> Optional[dict]:
        return self._binance_signed_get("https://api.binance.com", "/sapi/v1/account/apiRestrictions")

    def _fetch_futures_balance(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> Optional[float]:
        rows = self._fetch_futures_balance_rows(
            force_refresh=force_refresh,
            loop_label=f"{loop_label}-wallet",
        )
        if rows is None:
            return None
        for item in rows:
            if item.get("asset") == "USDT":
                try:
                    return float(item.get("balance", 0))
                except (TypeError, ValueError):
                    return None
        return None

    def _fetch_open_positions(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> Optional[list[dict]]:
        rows, _from_rest, _rate_limited = self._fetch_open_positions_with_meta(
            force_refresh=force_refresh,
            loop_label=loop_label,
        )
        return rows

    def _fetch_open_positions_with_meta(
        self,
        *,
        force_refresh: bool = False,
        loop_label: str = "-",
    ) -> tuple[Optional[list[dict]], bool, bool]:
        if not self._api_key or not self._secret_key:
            return [], False, False
        now = time.time()
        cached_positions: Optional[list[dict]] = None
        cached_dust_symbols: set[str] = set()
        cache_age = float("inf")
        with self._account_snapshot_cache_lock:
            if self._positions_cache is not None:
                cached_positions = self._copy_account_rows(self._positions_cache)
                cached_dust_symbols = set(self._positions_cache_dust_symbols)
                cache_age = max(0.0, now - float(self._positions_cache_at))
        user_stream_healthy = self._is_user_stream_healthy()
        if (
            not force_refresh
            and cached_positions is not None
            and (
                cache_age <= ACCOUNT_SNAPSHOT_CACHE_TTL_SEC
                or (user_stream_healthy and cache_age <= ACCOUNT_SNAPSHOT_STALE_FALLBACK_SEC)
            )
        ):
            self._last_dust_symbols = set(cached_dust_symbols)
            if cache_age > ACCOUNT_SNAPSHOT_CACHE_TTL_SEC and user_stream_healthy:
                _log_trade(
                    "Positions cache reused under healthy user stream: "
                    f"age_sec={cache_age:.2f} loop={loop_label}"
                )
            return self._apply_latest_ws_mark_prices_to_positions(cached_positions), False, False

        data = self._binance_signed_get("https://fapi.binance.com", POSITION_RISK_PATH)
        rate_limited = self._is_rate_limit_payload(data)
        if isinstance(data, list):
            positions = []
            dust_symbols: set[str] = set()
            for item in data:
                position_amt = self._safe_float(item.get("positionAmt"))
                if position_amt is None or abs(position_amt) <= 1e-9:
                    continue
                symbol = str(item.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                rule = self._get_symbol_filter_rule(symbol)
                if rule is not None:
                    normalized_qty = floor_quantity_by_step_size(abs(float(position_amt)), rule.step_size)
                    if normalized_qty is None or float(normalized_qty) < float(rule.min_qty) - 1e-12:
                        dust_symbols.add(symbol)
                        continue
                positions.append(item)
            positions.sort(key=lambda item: item.get("symbol", ""))
            if dust_symbols:
                _log_trade(
                    "Dust positions ignored by state sync: "
                    f"symbols={','.join(sorted(dust_symbols))}"
                )
            self._last_dust_symbols = set(dust_symbols)
            with self._account_snapshot_cache_lock:
                self._positions_cache = self._copy_account_rows(positions)
                self._positions_cache_at = now
                self._positions_cache_dust_symbols = set(dust_symbols)
            return self._apply_latest_ws_mark_prices_to_positions(positions), True, rate_limited
        if force_refresh and rate_limited:
            self._note_account_rest_backoff(context=f"positions:{loop_label}")

        if cached_positions is not None and cache_age <= ACCOUNT_SNAPSHOT_STALE_FALLBACK_SEC:
            self._last_dust_symbols = set(cached_dust_symbols)
            _log_trade(
                "Positions snapshot fallback used: "
                f"age_sec={cache_age:.2f} force_refresh={force_refresh} loop={loop_label}"
            )
            return self._apply_latest_ws_mark_prices_to_positions(cached_positions), False, rate_limited

        _log_trade(
            "Positions snapshot unavailable: "
            f"force_refresh={force_refresh} cache_age_sec={cache_age:.2f} loop={loop_label}"
        )
        return None, False, rate_limited

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

    def _current_signed_timestamp_ms(self) -> int:
        with self._server_time_offset_lock:
            offset_ms = int(self._server_time_offset_ms)
        return int(time.time() * 1000) + offset_ms

    @staticmethod
    def _is_server_time_sync_error_payload(payload: object) -> bool:
        if not isinstance(payload, dict):
            return False
        code = payload.get("code")
        if isinstance(code, int) and code == -1021:
            return True
        message = payload.get("msg")
        if isinstance(message, str):
            lowered = message.lower()
            if "timestamp for this request" in lowered or "outside of the recvwindow" in lowered:
                return True
        return False

    def _sync_server_time_offset_ms(self) -> bool:
        payload = self._binance_public_get("https://fapi.binance.com", SERVER_TIME_SYNC_PATH)
        if not isinstance(payload, dict):
            _log_trade("Server time sync failed: invalid payload.")
            return False
        server_time = self._safe_int(payload.get("serverTime"))
        if server_time <= 0:
            _log_trade(f"Server time sync failed: invalid serverTime payload={payload!r}")
            return False
        local_time = int(time.time() * 1000)
        offset_ms = int(server_time) - int(local_time)
        with self._server_time_offset_lock:
            self._server_time_offset_ms = int(offset_ms)
        _log_trade(
            "Server time offset synchronized: "
            f"server_time={server_time} local_time={local_time} offset_ms={offset_ms}"
        )
        return True

    @staticmethod
    def _strip_signed_request_params(params: Mapping[str, Any]) -> dict[str, Any]:
        cleaned = dict(params)
        cleaned.pop("timestamp", None)
        cleaned.pop("recvWindow", None)
        return cleaned

    def _binance_signed_get(
        self,
        base_url: str,
        path: str,
        params: Optional[dict] = None,
        *,
        _time_sync_retry_count: int = SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT,
    ) -> Optional[object]:
        params = dict(params or {})
        params["timestamp"] = self._current_signed_timestamp_ms()
        params["recvWindow"] = 5000
        query = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    synced = self._sync_server_time_offset_ms()
                    _log_trade(
                        "GET server-time drift detected: "
                        f"path={path} synced={synced} retry_count={_time_sync_retry_count}"
                    )
                    if synced:
                        return self._binance_signed_get(
                            base_url,
                            path,
                            self._strip_signed_request_params(params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(f"GET {path} failed status={response.status_code} params={params} detail={detail!r}")
                if isinstance(data, (dict, list)):
                    return data
                return None
            if data is None:
                _log_trade(
                    f"GET {path} returned non-JSON response status={response.status_code} "
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
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    synced = self._sync_server_time_offset_ms()
                    _log_trade(
                        "GET request exception with server-time drift: "
                        f"path={path} synced={synced} retry_count={_time_sync_retry_count}"
                    )
                    if synced:
                        return self._binance_signed_get(
                            base_url,
                            path,
                            self._strip_signed_request_params(params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"GET {path} request error status={response.status_code} "
                    f"params={params} detail={detail!r}"
                )
                if isinstance(data, (dict, list)):
                    return data
            else:
                _log_trade(f"GET {path} request error params={params} error={exc!r}")
            return None

    def _binance_signed_post(
        self,
        base_url: str,
        path: str,
        params: Optional[dict] = None,
        *,
        _time_sync_retry_count: int = SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT,
    ) -> Optional[object]:
        params = dict(params or {})
        params["timestamp"] = self._current_signed_timestamp_ms()
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
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    synced = self._sync_server_time_offset_ms()
                    _log_trade(
                        "POST server-time drift detected: "
                        f"path={path} synced={synced} retry_count={_time_sync_retry_count}"
                    )
                    if synced:
                        return self._binance_signed_post(
                            base_url,
                            path,
                            self._strip_signed_request_params(params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"POST {path} failed status={response.status_code} params={params} detail={detail!r}"
                )
                return data if isinstance(data, dict) else None
            if self._is_account_snapshot_mutation_path(path):
                self._invalidate_account_snapshot_cache(
                    reason=f"POST_MUTATION_{path}",
                    loop_label="signed-post",
                )
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
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    synced = self._sync_server_time_offset_ms()
                    _log_trade(
                        "POST request exception with server-time drift: "
                        f"path={path} synced={synced} retry_count={_time_sync_retry_count}"
                    )
                    if synced:
                        return self._binance_signed_post(
                            base_url,
                            path,
                            self._strip_signed_request_params(params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"POST {path} request error status={response.status_code} "
                    f"params={params} detail={detail!r}"
                )
            else:
                _log_trade(f"POST {path} request error params={params} error={exc!r}")
            if self._is_account_snapshot_mutation_path(path):
                self._invalidate_account_snapshot_cache(
                    reason=f"POST_MUTATION_UNKNOWN_{path}",
                    loop_label="signed-post-exception",
                )
            return None

    def _binance_signed_delete(
        self,
        base_url: str,
        path: str,
        params: Optional[dict] = None,
        *,
        _time_sync_retry_count: int = SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT,
    ) -> Optional[object]:
        params = dict(params or {})
        params["timestamp"] = self._current_signed_timestamp_ms()
        params["recvWindow"] = 5000
        query = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = requests.delete(url, headers=headers, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    synced = self._sync_server_time_offset_ms()
                    _log_trade(
                        "DELETE server-time drift detected: "
                        f"path={path} synced={synced} retry_count={_time_sync_retry_count}"
                    )
                    if synced:
                        return self._binance_signed_delete(
                            base_url,
                            path,
                            self._strip_signed_request_params(params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"DELETE {path} failed status={response.status_code} params={params} detail={detail!r}"
                )
                return data if isinstance(data, dict) else None
            if self._is_account_snapshot_mutation_path(path):
                self._invalidate_account_snapshot_cache(
                    reason=f"DELETE_MUTATION_{path}",
                    loop_label="signed-delete",
                )
            return data if isinstance(data, dict) else {}
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    data = response.json()
                except ValueError:
                    data = None
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    synced = self._sync_server_time_offset_ms()
                    _log_trade(
                        "DELETE request exception with server-time drift: "
                        f"path={path} synced={synced} retry_count={_time_sync_retry_count}"
                    )
                    if synced:
                        return self._binance_signed_delete(
                            base_url,
                            path,
                            self._strip_signed_request_params(params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                detail = data if isinstance(data, dict) else _trim_text(response.text)
                _log_trade(
                    f"DELETE {path} request error status={response.status_code} "
                    f"params={params} detail={detail!r}"
                )
            else:
                _log_trade(f"DELETE {path} request error params={params} error={exc!r}")
            if self._is_account_snapshot_mutation_path(path):
                self._invalidate_account_snapshot_cache(
                    reason=f"DELETE_MUTATION_UNKNOWN_{path}",
                    loop_label="signed-delete-exception",
                )
            return None

    def _binance_public_get(
        self,
        base_url: str,
        path: str,
        params: Optional[dict] = None,
        *,
        caller: str = "-",
    ) -> Optional[object]:
        params = dict(params or {})
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{query}"
        try:
            response = requests.get(url, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                detail = data if isinstance(data, (dict, list)) else _trim_text(response.text)
                _log_trade(
                    f"GET {path} public failed status={response.status_code} "
                    f"params={params} caller={caller} detail={detail!r}"
                )
                return None
            if data is None:
                _log_trade(
                    f"GET {path} public returned non-JSON response status={response.status_code} "
                    f"params={params} caller={caller} body={_trim_text(response.text)!r}"
                )
                return None
            return data
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    data = response.json()
                except ValueError:
                    data = None
                detail = data if isinstance(data, (dict, list)) else _trim_text(response.text)
                _log_trade(
                    f"GET {path} public request error status={response.status_code} "
                    f"params={params} caller={caller} detail={detail!r}"
                )
            else:
                _log_trade(
                    f"GET {path} public request error params={params} caller={caller} error={exc!r}"
                )
            return None

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _select_effective_stop_price(row: Mapping[str, Any]) -> tuple[Optional[float], str]:
        for key in ("stopPrice", "triggerPrice", "activatePrice", "AP", "ap", "sp"):
            value = TradePage._safe_float(row.get(key))
            if value is None or float(value) <= 0.0:
                continue
            return float(value), key
        return None, ""

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
        if not math.isfinite(float(value)):
            return "-"
        text = f"{float(value):,.8f}"
        trimmed = text.rstrip("0").rstrip(".")
        if trimmed in ("", "-0"):
            return "0"
        return trimmed

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
        numeric_balance = float(balance)
        over_limit = self._is_wallet_over_auto_stop_limit(numeric_balance)
        self._wallet_balance = numeric_balance
        self._wallet_value = f"{numeric_balance:,.2f}"
        self._wallet_unit = "USDT"
        self._wallet_value_color = WALLET_LIMIT_EXCEEDED_COLOR if over_limit else WALLET_VALUE_COLOR
        if over_limit != self._wallet_over_auto_stop_limit:
            self._wallet_over_auto_stop_limit = over_limit
            _log_trade(
                "Wallet auto-stop threshold state changed: "
                f"over_limit={over_limit} balance={numeric_balance:.2f} "
                f"threshold={self._auto_trade_wallet_stop_threshold_usdt:.2f}"
            )
        self._layout()

    def _set_wallet_failure(self) -> None:
        self._wallet_balance = None
        self._wallet_value = "연결실패"
        self._wallet_unit = ""
        self._wallet_value_color = HIGHLIGHT_TEXT
        self._wallet_over_auto_stop_limit = False
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
            if not self._single_asset_mode_ready and not self._ensure_single_asset_mode_on_login():
                _log_trade("Status refresh skipped: reason=single_asset_mode_not_ready")
                balance = None
                positions = None
            else:
                balance = self._fetch_futures_balance(loop_label="status-refresh-balance")
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
            if balance is not None and positions is not None:
                self._request_wallet_limit_auto_stop_if_needed(
                    balance=balance,
                    positions=positions,
                    source="status-refresh",
                )
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
