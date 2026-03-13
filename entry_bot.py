from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from datetime import datetime
from typing import Any, Callable, Mapping, Optional
from zoneinfo import ZoneInfo

import requests

import config
from log_rotation import append_rotating_log_line
from runtime_paths import get_log_path

TRADE_LOG_PATH = get_log_path("LTS-Trade.log")

ENTRY_SIGNAL_CHANNEL_ID_DEFAULT = -1003782821900
RISK_SIGNAL_CHANNEL_ID_DEFAULT = -1003761851285

ENTRY_SIGNAL_CHANNEL_ID_ENV = "LTS_ENTRY_SIGNAL_CHANNEL_ID"
RISK_SIGNAL_CHANNEL_ID_ENV = "LTS_RISK_SIGNAL_CHANNEL_ID"
SIGNAL_RELAY_BASE_URL_ENV = "LTS_SIGNAL_RELAY_BASE_URL"
SIGNAL_RELAY_CLIENT_ID_ENV = "LTS_SIGNAL_RELAY_CLIENT_ID"
SIGNAL_RELAY_TOKEN_ENV = "LTS_SIGNAL_RELAY_TOKEN"
SIGNAL_RELAY_REQUEST_TIMEOUT_ENV = "LTS_SIGNAL_RELAY_REQUEST_TIMEOUT_SEC"
SIGNAL_RELAY_POLL_LIMIT_ENV = "LTS_SIGNAL_RELAY_POLL_LIMIT"

SIGNAL_RELAY_REQUEST_TIMEOUT_SEC = 5
SIGNAL_RELAY_POLL_LIMIT = 100
POLL_INTERVAL_SEC = 1.0
BALANCE_REFRESH_INTERVAL_SEC = 15.0
SNAPSHOT_REFRESH_INTERVAL_SEC = 5.0
PENDING_ENTRY_MONITOR_INTERVAL_SEC = 10.0
ENTRY_SUBMIT_GUARD_SEC = 3.0
SIGNED_QUERY_RATE_LIMIT_BACKOFF_SEC = 15.0
SIGNED_QUERY_RATE_LIMIT_BACKOFF_LOG_THROTTLE_SEC = 10.0
ENTRY_MODE_STOP_AFTER_SUBMIT = False

FUTURES_ORDER_PATH = "/fapi/v1/order"
FUTURES_OPEN_ORDERS_PATH = "/fapi/v1/openOrders"
FUTURES_ALGO_ORDER_PATH = "/fapi/v1/algoOrder"
FUTURES_OPEN_ALGO_ORDERS_PATH = "/fapi/v1/openAlgoOrders"
POSITION_RISK_PATH = "/fapi/v2/positionRisk"
POSITION_MODE_PATH = "/fapi/v1/positionSide/dual"
LEVERAGE_SET_PATH = "/fapi/v1/leverage"
MARGIN_TYPE_SET_PATH = "/fapi/v1/marginType"
FUTURES_LAST_PRICE_PATH = "/fapi/v1/ticker/price"
SERVER_TIME_SYNC_PATH = "/fapi/v1/time"

SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT = 1
RECENT_KLINE_LIMIT = 20
ENTRY_BUDGET_RATIO = 0.45
ENTRY_IMMEDIATE_TRIGGER_REJECT_ERROR_CODE = -2021
STOP_FAMILY_WORKING_TYPE = "CONTRACT_PRICE"

FIRST_ENTRY_CLIENT_ID_PREFIX = "LTS-E1-"
ENTRY_CLIENT_ID_PREFIXES = ("LTS-E1-", "LTS-E2-")
ALGO_ORDER_TYPES = {"STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT", "TRAILING_STOP_MARKET"}

_TITLE_TICKER_PATTERN = re.compile(r"\(([^()]+)\)")
_PERCENT_PATTERN = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
_TIME_PATTERN = re.compile(r"/\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2})")
_DIRECTION_RANK_PATTERN = re.compile(r"\(([^()]+)\)\s*상위\s*(\d+)\s*위")
_RISK_SYMBOL_PATTERN = re.compile(r"Binance\s*[:：]\s*([^\s]+)", re.IGNORECASE)
_NON_ALNUM_PATTERN = re.compile(r"[^A-Z0-9]")
_ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
_RATE_LIMIT_BAN_UNTIL_PATTERN = re.compile(r"banned until (\d+)", re.IGNORECASE)

_KST_TZ = ZoneInfo("Asia/Seoul")
_ENTRY_BLOCK_START_MINUTE_OF_DAY = (8 * 60) + 30
_ENTRY_BLOCK_END_MINUTE_OF_DAY = (10 * 60) + 1
_CATEGORY_EXCLUDED_KEYWORDS = [
    "meme",
    "defi",
    "pump.fun",
    "dex",
    "탈중앙화 거래소",
    "binance alpha spotlight",
]
_LONG_DIRECTION_ALIASES = {"롱", "long", "매수", "상방"}


def _log_entry(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        append_rotating_log_line(TRADE_LOG_PATH, f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _safe_float(value: object) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _safe_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


def _trim_text(value: object, limit: int = 200) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(+{len(text) - limit} chars)"


def _mask_api_key(api_key: str) -> str:
    text = str(api_key or "").strip()
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def _normalize_symbol(value: str) -> str:
    return str(value or "").strip().upper()


def _read_env_int(key: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _find_first_line(lines: list[str], markers: tuple[str, ...]) -> Optional[str]:
    for line in lines:
        for marker in markers:
            if marker in line:
                return line
    return None


def _split_label_payload(line: str) -> Optional[str]:
    parts = re.split(r"\s*[:：]\s*", line, maxsplit=1)
    if len(parts) != 2:
        return None
    return parts[1].strip()


def _sanitize_symbol_token(value: str) -> str:
    text = str(value or "").strip()
    cleaned: list[str] = []
    for char in text:
        if char in _ZERO_WIDTH_CHARS:
            continue
        code = ord(char)
        if code < 32 or code == 127:
            continue
        cleaned.append(char)
    return "".join(cleaned).upper()


def _normalize_alnum_token(value: str) -> tuple[Optional[str], Optional[str]]:
    normalized = _sanitize_symbol_token(value)
    if not normalized:
        return None, "EMPTY_TOKEN"
    if _NON_ALNUM_PATTERN.search(normalized):
        return None, "INVALID_CHARACTERS"
    return normalized, None


def _normalize_market_direction_token(value: str) -> str:
    return "".join(str(value or "").strip().lower().split())


def _is_long_market_direction(value: str) -> bool:
    normalized = _normalize_market_direction_token(value)
    if not normalized:
        return False
    for alias in _LONG_DIRECTION_ALIASES:
        if normalized == alias or normalized.startswith(alias):
            return True
    return False


def _match_excluded_keyword(category: str) -> Optional[str]:
    lowered = str(category or "").strip().lower()
    for keyword in _CATEGORY_EXCLUDED_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def _resolve_signal_time_kst(signal_received_at_local: Optional[int]) -> datetime:
    epoch_seconds = _safe_int(signal_received_at_local)
    if epoch_seconds <= 0:
        epoch_seconds = int(time.time())
    return datetime.fromtimestamp(epoch_seconds, tz=_KST_TZ)


def _round_price_by_tick_size(price: float, tick_size: float) -> Optional[float]:
    price_value = _safe_float(price)
    tick_value = _safe_float(tick_size)
    if price_value is None or price_value <= 0:
        return None
    if tick_value is None or tick_value <= 0:
        return None
    units = round(price_value / tick_value)
    adjusted = units * tick_value
    if adjusted <= 0:
        return None
    return float(adjusted)


def _floor_quantity_by_step_size(quantity: float, step_size: float) -> Optional[float]:
    quantity_value = _safe_float(quantity)
    step_value = _safe_float(step_size)
    if quantity_value is None or quantity_value <= 0:
        return None
    if step_value is None or step_value <= 0:
        return None
    units = math.floor(quantity_value / step_value)
    adjusted = units * step_value
    if adjusted <= 0:
        return None
    return float(adjusted)


def _format_order_value_by_increment(
    value: float,
    increment: float,
    *,
    rounding_mode: str,
) -> Optional[str]:
    value_float = _safe_float(value)
    increment_float = _safe_float(increment)
    if value_float is None or value_float <= 0:
        return None
    if increment_float is None or increment_float <= 0:
        return None
    try:
        increment_decimal = Decimal(str(increment_float)).normalize()
        quantized = Decimal(str(value_float)).quantize(
            increment_decimal,
            rounding=rounding_mode,
        )
    except (InvalidOperation, ValueError):
        return None
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _extract_client_order_id(row: Mapping[str, Any]) -> str:
    return str(
        row.get("clientOrderId")
        or row.get("origClientOrderId")
        or row.get("newClientOrderId")
        or row.get("clientAlgoId")
        or ""
    ).strip().upper()


def _is_entry_client_order_id(client_order_id: object) -> bool:
    token = str(client_order_id or "").strip().upper()
    if not token:
        return False
    return any(token.startswith(prefix) for prefix in ENTRY_CLIENT_ID_PREFIXES)


def _normalize_order_type_token(value: object) -> str:
    return str(value or "").strip().upper()


def _is_algo_order_type(value: object) -> bool:
    return _normalize_order_type_token(value) in ALGO_ORDER_TYPES


def _normalize_open_order_row(row: Mapping[str, Any], *, is_algo_order: bool) -> Optional[dict[str, Any]]:
    symbol = _normalize_symbol(row.get("symbol"))
    if not symbol:
        return None
    normalized = dict(row)
    normalized["symbol"] = symbol
    normalized["_algo_order"] = bool(is_algo_order)

    order_id = _safe_int(normalized.get("orderId"))
    if order_id <= 0:
        algo_id = _safe_int(normalized.get("algoId"))
        if algo_id > 0:
            order_id = algo_id
            normalized["orderId"] = algo_id
    if order_id <= 0:
        return None

    order_type = _normalize_order_type_token(
        normalized.get("type") or normalized.get("orderType") or normalized.get("origType")
    )
    if order_type:
        normalized["type"] = order_type

    side = _normalize_symbol(normalized.get("side") or normalized.get("orderSide") or normalized.get("S"))
    if side:
        normalized["side"] = side

    client_order_id = str(
        normalized.get("clientOrderId")
        or normalized.get("origClientOrderId")
        or normalized.get("newClientOrderId")
        or normalized.get("clientAlgoId")
        or ""
    ).strip()
    if client_order_id:
        normalized["clientOrderId"] = client_order_id

    working_type = _normalize_symbol(normalized.get("workingType") or normalized.get("wt"))
    if working_type:
        normalized["workingType"] = working_type

    for key in ("stopPrice", "triggerPrice", "activatePrice", "AP", "ap", "sp"):
        stop_price = _safe_float(normalized.get(key))
        if stop_price is None or stop_price <= 0:
            continue
        normalized["stopPrice"] = str(stop_price)
        break

    return normalized


def _is_entry_order_row(row: Mapping[str, Any]) -> bool:
    side = _normalize_symbol(row.get("side"))
    reduce_only = _to_bool(row.get("reduceOnly"))
    close_position = _to_bool(row.get("closePosition"))
    client_order_id = _extract_client_order_id(row)
    is_entry_by_prefix = _is_entry_client_order_id(client_order_id)
    is_exit = bool(not is_entry_by_prefix and (side == "BUY" or reduce_only or close_position))
    return not is_exit


@dataclass(frozen=True)
class LeadingSignal:
    ticker: str
    symbol: str
    funding_rate_pct: float
    funding_countdown: str
    ranking_change_pct: float
    ranking_direction: str
    ranking_position: int
    category: str
    market_direction: str


@dataclass(frozen=True)
class RiskSignal:
    symbol: str


@dataclass(frozen=True)
class SymbolFilterRules:
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: Optional[float] = None


@dataclass(frozen=True)
class AccountSnapshot:
    wallet_balance: Optional[float] = None
    positions: list[dict[str, Any]] = field(default_factory=list)
    open_orders: list[dict[str, Any]] = field(default_factory=list)


def parse_leading_market_message(message_text: str) -> tuple[Optional[LeadingSignal], str]:
    lines = _split_lines(message_text)
    if not lines:
        return None, "empty_message"

    title_line = _find_first_line(lines, ("🔥",))
    if title_line is None:
        return None, "title_line_not_found"

    title_match = _TITLE_TICKER_PATTERN.search(title_line)
    if title_match is None:
        return None, "ticker_not_found"

    ticker, ticker_failure = _normalize_alnum_token(title_match.group(1))
    if ticker is None:
        return None, f"ticker_normalize_failed:{ticker_failure}"

    funding_line = _find_first_line(lines, ("⏱", "펀딩비"))
    if funding_line is None:
        return None, "funding_line_not_found"
    funding_payload = _split_label_payload(funding_line)
    if funding_payload is None:
        return None, "funding_payload_not_found"
    funding_match = _PERCENT_PATTERN.search(funding_payload)
    time_match = _TIME_PATTERN.search(funding_payload)
    if funding_match is None or time_match is None:
        return None, "funding_parse_failed"

    ranking_line = _find_first_line(lines, ("🥇", "등락률"))
    if ranking_line is None:
        return None, "ranking_line_not_found"
    ranking_payload = _split_label_payload(ranking_line)
    if ranking_payload is None:
        return None, "ranking_payload_not_found"
    ranking_pct_match = _PERCENT_PATTERN.search(ranking_payload)
    ranking_dir_match = _DIRECTION_RANK_PATTERN.search(ranking_payload)
    if ranking_pct_match is None or ranking_dir_match is None:
        return None, "ranking_parse_failed"

    category_line = _find_first_line(lines, ("🏷", "카테고리"))
    if category_line is None:
        return None, "category_line_not_found"
    category_payload = _split_label_payload(category_line)
    if category_payload is None:
        return None, "category_payload_not_found"
    category = category_payload.strip()
    if not category:
        return None, "category_empty"

    market_direction = ""
    direction_line = _find_first_line(lines, ("🧭", "방향"))
    if direction_line is not None:
        direction_payload = _split_label_payload(direction_line)
        if direction_payload is None:
            return None, "direction_payload_not_found"
        market_direction = direction_payload.strip()
        if not market_direction:
            return None, "direction_empty"

    return (
        LeadingSignal(
            ticker=ticker,
            symbol=f"{ticker}USDT",
            funding_rate_pct=float(funding_match.group(1)),
            funding_countdown=time_match.group(1),
            ranking_change_pct=float(ranking_pct_match.group(1)),
            ranking_direction=ranking_dir_match.group(1).strip(),
            ranking_position=int(ranking_dir_match.group(2)),
            category=category,
            market_direction=market_direction,
        ),
        "ok",
    )


def parse_risk_management_message(message_text: str) -> tuple[Optional[RiskSignal], str]:
    text = str(message_text or "")
    if not text.strip():
        return None, "empty_message"
    symbol_match = _RISK_SYMBOL_PATTERN.search(text)
    if symbol_match is None:
        return None, "risk_symbol_not_found"
    sanitized = _sanitize_symbol_token(symbol_match.group(1).strip())
    if sanitized.endswith(".P"):
        sanitized = sanitized[:-2]
    symbol, symbol_failure = _normalize_alnum_token(sanitized)
    if symbol is None:
        return None, f"risk_symbol_normalize_failed:{symbol_failure}"
    return RiskSignal(symbol=symbol), "ok"


def evaluate_common_filters(
    *,
    category: str,
    ranking_direction: str,
    ranking_position: int,
    funding_rate_pct: float,
    market_direction: str,
    signal_received_at_local: Optional[int],
) -> tuple[bool, str]:
    signal_time_kst = _resolve_signal_time_kst(signal_received_at_local)
    minute_of_day = signal_time_kst.hour * 60 + signal_time_kst.minute
    if _ENTRY_BLOCK_START_MINUTE_OF_DAY <= minute_of_day < _ENTRY_BLOCK_END_MINUTE_OF_DAY:
        return False, f"kst_morning_entry_block:{signal_time_kst.strftime('%H:%M:%S')}"

    if _is_long_market_direction(market_direction):
        return False, f"long_direction_block:{market_direction}"

    matched_keyword = _match_excluded_keyword(category)
    if matched_keyword is not None:
        return False, f"category_excluded_keyword:{matched_keyword}"

    normalized_category_compact = "".join(str(category or "").strip().lower().split())
    if normalized_category_compact == "정보없음":
        return False, "category_unknown"

    direction = str(ranking_direction or "").strip()
    if direction == "상승":
        if 1 <= int(ranking_position) <= 5:
            return False, "ranking_top5_rise"
    elif direction != "하락":
        return False, f"ranking_direction_invalid:{direction or '-'}"

    if float(funding_rate_pct) <= -0.1:
        return False, f"funding_too_negative:{funding_rate_pct}"

    return True, "filter_pass"


def calculate_entry_target(
    candles: list[Mapping[str, Any]],
    *,
    evaluation_time_ms: Optional[int],
) -> tuple[Optional[float], str]:
    if len(candles) < 2:
        return None, "insufficient_candles"
    fallback_index = len(candles) - 2
    effective_eval_ms = _safe_int(evaluation_time_ms) or int(time.time() * 1000)
    last_close_ms = _safe_int(candles[-1].get("close_time"))
    reference_index = fallback_index
    if last_close_ms > 0 and last_close_ms <= effective_eval_ms:
        reference_index = len(candles) - 1
    target = _safe_float(candles[reference_index].get("high"))
    if target is None or target <= 0:
        return None, "target_not_finite"
    return float(target), "target_ready"


class EntryRelayBot:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        leverage_getter: Callable[[], object],
        snapshot_callback: Optional[Callable[[AccountSnapshot], None]] = None,
        auto_stop_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self._secret_key = str(secret_key or "").strip()
        self._leverage_getter = leverage_getter
        self._snapshot_callback = snapshot_callback
        self._auto_stop_callback = auto_stop_callback

        self._state_lock = threading.Lock()
        self._server_time_lock = threading.Lock()
        self._exchange_info_lock = threading.Lock()
        self._session = requests.Session()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._server_time_offset_ms = 0
        self._relay_base_url = self._resolve_relay_base_url()
        self._relay_token = self._resolve_relay_token()
        self._relay_client_id = self._resolve_relay_client_id()
        self._entry_channel_id = _read_env_int(
            ENTRY_SIGNAL_CHANNEL_ID_ENV,
            ENTRY_SIGNAL_CHANNEL_ID_DEFAULT,
            minimum=-999999999999999,
            maximum=999999999999999,
        )
        self._risk_channel_id = _read_env_int(
            RISK_SIGNAL_CHANNEL_ID_ENV,
            RISK_SIGNAL_CHANNEL_ID_DEFAULT,
            minimum=-999999999999999,
            maximum=999999999999999,
        )
        self._relay_request_timeout_sec = _read_env_int(
            SIGNAL_RELAY_REQUEST_TIMEOUT_ENV,
            SIGNAL_RELAY_REQUEST_TIMEOUT_SEC,
            minimum=1,
            maximum=30,
        )
        self._relay_poll_limit = _read_env_int(
            SIGNAL_RELAY_POLL_LIMIT_ENV,
            SIGNAL_RELAY_POLL_LIMIT,
            minimum=1,
            maximum=500,
        )
        self._signal_offset = 0
        self._last_message_ids: dict[int, int] = {}
        self._exchange_info_cache: Optional[dict[str, Any]] = None
        self._exchange_info_cache_at = 0.0
        self._last_balance_refresh_at = 0.0
        self._last_snapshot_refresh_at = 0.0
        self._last_pending_entry_monitor_at = 0.0
        self._snapshot = AccountSnapshot()
        self._awaiting_entry_fill = False
        self._entry_submit_guard_until = 0.0
        self._signed_query_backoff_until = 0.0
        self._signed_query_backoff_last_log_at = 0.0

        _log_entry(
            "Entry relay bot initialized: "
            f"api_key={_mask_api_key(self._api_key)} relay_base_url={self._relay_base_url or '-'} "
            f"relay_client_id={self._relay_client_id} relay_token_set={bool(self._relay_token)} "
            f"entry_channel_id={self._entry_channel_id} risk_channel_id={self._risk_channel_id}"
        )

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def latest_snapshot(self) -> AccountSnapshot:
        with self._state_lock:
            return AccountSnapshot(
                wallet_balance=self._snapshot.wallet_balance,
                positions=[dict(item) for item in self._snapshot.positions],
                open_orders=[dict(item) for item in self._snapshot.open_orders],
            )

    def refresh_snapshot_once(self) -> AccountSnapshot:
        return self._refresh_account_snapshot(force_balance=True, force_orders=True)

    def refresh_wallet_balance_once(self) -> AccountSnapshot:
        _log_entry("Wallet balance refresh requested: reason=trade_page_initial_load")
        return self._refresh_account_snapshot(force_balance=True, force_orders=False)

    def start(self) -> tuple[bool, str]:
        if not self._api_key or not self._secret_key:
            _log_entry("Entry relay bot start rejected: reason=api_credentials_missing")
            return False, "API KEY와 SECRET KEY가 필요합니다."
        if not self._relay_base_url:
            _log_entry("Entry relay bot start rejected: reason=relay_base_url_missing")
            return False, "신호 중계 주소가 설정되어 있지 않습니다."
        if self.is_running():
            _log_entry("Entry relay bot start ignored: reason=already_running")
            return False, "이미 실행중입니다."

        self._signal_offset = self._sync_signal_relay_offset_for_fresh_start()
        snapshot = self.latest_snapshot()
        with self._state_lock:
            self._awaiting_entry_fill = False
            self._entry_submit_guard_until = 0.0
            self._last_pending_entry_monitor_at = 0.0

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="EntryRelayBot", daemon=True)
        self._thread.start()
        _log_entry(
            "Entry relay bot started: "
            f"signal_offset={self._signal_offset} entry_mode_stop_after_submit={ENTRY_MODE_STOP_AFTER_SUBMIT} "
            f"cached_wallet_balance={snapshot.wallet_balance if snapshot.wallet_balance is not None else '-'}"
        )
        return True, "-"

    def stop(self, reason: str) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        _log_entry(f"Entry relay bot stopped: reason={reason}")

    def _run_loop(self) -> None:
        _log_entry("Entry relay loop entered.")
        try:
            while not self._stop_event.is_set():
                snapshot = self.latest_snapshot()
                self._process_relay_events(snapshot)
                if self._stop_event.wait(POLL_INTERVAL_SEC):
                    break
        except Exception as exc:
            _log_entry(f"Entry relay loop crashed: error={exc!r}")
        finally:
            _log_entry("Entry relay loop exited.")

    def _should_auto_stop_after_fill(self, snapshot: AccountSnapshot) -> bool:
        with self._state_lock:
            awaiting_entry_fill = bool(self._awaiting_entry_fill)
            guard_until = float(self._entry_submit_guard_until)
        if awaiting_entry_fill and snapshot.positions:
            _log_entry(
                "Entry relay auto-stop triggered: "
                f"reason=entry_fill_detected position_count={len(snapshot.positions)}"
            )
            self._stop_event.set()
            if callable(self._auto_stop_callback):
                try:
                    self._auto_stop_callback("entry_filled")
                except Exception as exc:
                    _log_entry(f"Entry relay auto-stop callback failed: error={exc!r}")
            return True

        pending_symbols = self._entry_order_symbols(snapshot.open_orders)
        if not pending_symbols and not snapshot.positions:
            if awaiting_entry_fill and time.time() < guard_until:
                return False
            with self._state_lock:
                if self._awaiting_entry_fill:
                    self._awaiting_entry_fill = False
                    self._entry_submit_guard_until = 0.0
                    self._last_pending_entry_monitor_at = 0.0
                    _log_entry("Entry relay pending-entry latch cleared: reason=no_open_entry_orders_and_no_position")
        return False

    def _should_refresh_pending_entry_snapshot(self) -> bool:
        with self._state_lock:
            awaiting_entry_fill = bool(self._awaiting_entry_fill)
            last_refresh_at = float(self._last_pending_entry_monitor_at)
        if not awaiting_entry_fill:
            return False
        now = time.time()
        if last_refresh_at <= 0:
            with self._state_lock:
                self._last_pending_entry_monitor_at = now
            _log_entry(
                "Pending entry monitor armed: "
                f"interval_sec={PENDING_ENTRY_MONITOR_INTERVAL_SEC:.1f}"
            )
            return False
        if now - last_refresh_at < PENDING_ENTRY_MONITOR_INTERVAL_SEC:
            return False
        with self._state_lock:
            self._last_pending_entry_monitor_at = now
        _log_entry("Pending entry monitor refresh triggered.")
        return True

    def _process_relay_events(self, snapshot: AccountSnapshot) -> None:
        events = self._poll_signal_relay_updates()
        if not events:
            return
        current_snapshot = snapshot
        for event in events:
            if self._stop_event.is_set():
                return
            channel_id = _safe_int(event.get("channel_id"))
            message_id = _safe_int(event.get("message_id"))
            message_text = str(event.get("message_text") or "").strip()
            received_at_local = _safe_int(event.get("received_at_local")) or int(time.time())
            if channel_id == 0 or message_id <= 0 or not message_text:
                continue
            previous_message_id = self._last_message_ids.get(channel_id, 0)
            if message_id <= previous_message_id:
                _log_entry(
                    "Signal event skipped: "
                    f"reason=duplicate_or_old channel_id={channel_id} message_id={message_id} "
                    f"last_message_id={previous_message_id}"
                )
                continue
            self._last_message_ids[channel_id] = message_id
            if channel_id == self._entry_channel_id:
                current_snapshot = self._handle_entry_signal(
                    message_id=message_id,
                    message_text=message_text,
                    received_at_local=received_at_local,
                    snapshot=current_snapshot,
                )
            elif channel_id == self._risk_channel_id:
                current_snapshot = self._handle_risk_signal(
                    message_id=message_id,
                    message_text=message_text,
                    snapshot=current_snapshot,
                )

    def _handle_entry_signal(
        self,
        *,
        message_id: int,
        message_text: str,
        received_at_local: int,
        snapshot: AccountSnapshot,
    ) -> AccountSnapshot:
        leading_signal, parse_reason = parse_leading_market_message(message_text)
        if leading_signal is None:
            _log_entry(
                "Entry signal ignored: "
                f"reason=parse_failed message_id={message_id} failure={parse_reason}"
            )
            return snapshot

        exchange_info = self._fetch_exchange_info_snapshot()
        symbol = self._validate_symbol_usdt_m(leading_signal.symbol, exchange_info)
        if not symbol:
            _log_entry(
                "Entry signal ignored: "
                f"reason=symbol_validate_failed message_id={message_id} symbol={leading_signal.symbol}"
            )
            return snapshot

        passed, filter_reason = evaluate_common_filters(
            category=leading_signal.category,
            ranking_direction=leading_signal.ranking_direction,
            ranking_position=leading_signal.ranking_position,
            funding_rate_pct=leading_signal.funding_rate_pct,
            market_direction=leading_signal.market_direction,
            signal_received_at_local=received_at_local,
        )
        if not passed:
            _log_entry(
                "Entry signal rejected by common filter: "
                f"symbol={symbol} message_id={message_id} reason={filter_reason}"
            )
            return snapshot

        candles = self._fetch_recent_3m_candles(symbol)
        target_price, target_reason = calculate_entry_target(
            candles,
            evaluation_time_ms=int(received_at_local) * 1000,
        )
        if target_price is None:
            _log_entry(
                "Entry signal ignored: "
                f"reason=target_calc_failed symbol={symbol} message_id={message_id} failure={target_reason}"
            )
            return snapshot

        filter_rules = self._get_symbol_filter_rule(symbol, exchange_info)
        if filter_rules is None:
            _log_entry(
                "Entry signal ignored: "
                f"reason=filter_rule_missing symbol={symbol} message_id={message_id}"
            )
            return snapshot

        snapshot = self._refresh_account_snapshot(force_balance=True, force_orders=True)
        if snapshot.positions:
            _log_entry(
                "Entry signal ignored: "
                f"reason=position_exists message_id={message_id} position_count={len(snapshot.positions)}"
            )
            return snapshot
        pending_symbols = self._entry_order_symbols(snapshot.open_orders)
        if pending_symbols:
            _log_entry(
                "Entry signal ignored: "
                f"reason=open_entry_order_exists message_id={message_id} "
                f"pending_symbols={','.join(sorted(pending_symbols))}"
            )
            return snapshot

        wallet_balance = snapshot.wallet_balance
        if wallet_balance is None or wallet_balance <= 0:
            wallet_balance = self._fetch_futures_balance()
        if wallet_balance is None or wallet_balance <= 0:
            _log_entry(
                "Entry signal ignored: "
                f"reason=wallet_balance_unavailable symbol={symbol} message_id={message_id}"
            )
            return snapshot

        position_mode = self._fetch_position_mode()
        if position_mode not in {"ONE_WAY", "HEDGE"}:
            _log_entry(
                "Entry signal ignored: "
                f"reason=position_mode_unknown symbol={symbol} message_id={message_id}"
            )
            return snapshot

        target_leverage = self._selected_leverage_value()
        if not self._ensure_symbol_trading_setup(symbol=symbol, target_leverage=target_leverage):
            _log_entry(
                "Entry signal ignored: "
                f"reason=pre_order_setup_failed symbol={symbol} message_id={message_id} leverage={target_leverage}"
            )
            return snapshot

        reference_mark_price = self._fetch_mark_price(symbol)
        if reference_mark_price is None or reference_mark_price <= 0:
            _log_entry(
                "Entry signal ignored: "
                f"reason=mark_price_unavailable symbol={symbol} message_id={message_id}"
            )
            return snapshot

        budget_usdt = float(wallet_balance) * ENTRY_BUDGET_RATIO * float(target_leverage)
        if budget_usdt <= 0:
            _log_entry(
                "Entry signal ignored: "
                f"reason=budget_non_positive symbol={symbol} message_id={message_id} "
                f"wallet_balance={wallet_balance} leverage={target_leverage}"
            )
            return snapshot

        client_order_id = self._generate_first_entry_client_order_id(symbol)
        success = self._submit_first_entry_order(
            symbol=symbol,
            target_price=float(target_price),
            budget_usdt=float(budget_usdt),
            filter_rules=filter_rules,
            position_mode=position_mode,
            reference_mark_price=float(reference_mark_price),
            client_order_id=client_order_id,
        )
        if not success:
            return snapshot

        with self._state_lock:
            self._awaiting_entry_fill = True
            self._entry_submit_guard_until = time.time() + ENTRY_SUBMIT_GUARD_SEC
            self._last_pending_entry_monitor_at = time.time()
        _log_entry(
            "Entry order submitted: "
            f"symbol={symbol} message_id={message_id} target_price={target_price} "
            f"budget_usdt={budget_usdt:.4f} leverage={target_leverage} "
            f"entry_mode_stop_after_submit={ENTRY_MODE_STOP_AFTER_SUBMIT}"
        )
        if ENTRY_MODE_STOP_AFTER_SUBMIT:
            with self._state_lock:
                self._awaiting_entry_fill = False
                self._entry_submit_guard_until = 0.0
                self._last_pending_entry_monitor_at = 0.0
            self._stop_event.set()
            if callable(self._auto_stop_callback):
                try:
                    self._auto_stop_callback("entry_order_submitted")
                except Exception as exc:
                    _log_entry(f"Entry relay auto-stop callback failed: error={exc!r}")
        else:
            _log_entry(
                "Entry relay kept running after submit: "
                "reason=risk_signal_cancel_support"
            )
        return self.latest_snapshot()

    def _handle_risk_signal(
        self,
        *,
        message_id: int,
        message_text: str,
        snapshot: AccountSnapshot,
    ) -> AccountSnapshot:
        risk_signal, parse_reason = parse_risk_management_message(message_text)
        if risk_signal is None:
            _log_entry(
                "Risk signal ignored: "
                f"reason=parse_failed message_id={message_id} failure={parse_reason}"
            )
            return snapshot
        symbol = self._validate_symbol_usdt_m(risk_signal.symbol, self._fetch_exchange_info_snapshot())
        if not symbol:
            _log_entry(
                "Risk signal ignored: "
                f"reason=symbol_validate_failed message_id={message_id} symbol={risk_signal.symbol}"
            )
            return snapshot
        snapshot = self._refresh_account_snapshot(force_balance=False, force_orders=True)
        pending_by_symbol = self._entry_orders_by_symbol(snapshot.open_orders)
        if not pending_by_symbol:
            _log_entry(
                "Risk signal ignored: "
                f"reason=no_open_entry_orders message_id={message_id}"
            )
            return snapshot
        if snapshot.positions:
            _log_entry(
                "Risk signal ignored: "
                f"reason=position_exists message_id={message_id} position_count={len(snapshot.positions)}"
            )
            return snapshot
        if symbol not in pending_by_symbol:
            _log_entry(
                "Risk signal ignored: "
                f"reason=symbol_mismatch message_id={message_id} symbol={symbol} "
                f"pending_symbols={','.join(sorted(pending_by_symbol.keys()))}"
            )
            return snapshot

        cancel_attempts = 0
        cancel_success = 0
        for row in pending_by_symbol[symbol]:
            order_id = _safe_int(row.get("orderId"))
            if order_id <= 0:
                continue
            cancel_attempts += 1
            if self._cancel_order(symbol=symbol, order_id=order_id, is_algo=bool(row.get("_algo_order"))):
                cancel_success += 1
        _log_entry(
            "Risk signal cancel summary: "
            f"symbol={symbol} message_id={message_id} attempted={cancel_attempts} success={cancel_success}"
        )
        refreshed = self._refresh_account_snapshot(force_balance=False, force_orders=True)
        if not self._entry_order_symbols(refreshed.open_orders):
            with self._state_lock:
                self._awaiting_entry_fill = False
                self._last_pending_entry_monitor_at = 0.0
        return refreshed

    def _selected_leverage_value(self) -> int:
        raw = self._leverage_getter()
        if isinstance(raw, str):
            match = re.search(r"(\d+)", raw)
            if match:
                value = int(match.group(1))
                if value > 0:
                    return value
        parsed = _safe_int(raw)
        return parsed if parsed > 0 else 1

    def _generate_first_entry_client_order_id(self, symbol: str) -> str:
        timestamp = int(time.time() * 1000)
        symbol_token = re.sub(r"[^A-Z0-9]", "", _normalize_symbol(symbol))[:6] or "PAIR"
        return f"{FIRST_ENTRY_CLIENT_ID_PREFIX}{symbol_token}-{timestamp}"

    def _submit_first_entry_order(
        self,
        *,
        symbol: str,
        target_price: float,
        budget_usdt: float,
        filter_rules: SymbolFilterRules,
        position_mode: str,
        reference_mark_price: float,
        client_order_id: str,
    ) -> bool:
        quantity = budget_usdt / float(target_price)
        order_type = self._resolve_entry_trigger_order_type(
            side="SELL",
            target_price=target_price,
            reference_mark_price=reference_mark_price,
        )
        params, failure_reason = self._build_entry_order_params(
            symbol=symbol,
            target_price=target_price,
            quantity=quantity,
            order_type=order_type,
            filter_rules=filter_rules,
            position_mode=position_mode,
            client_order_id=client_order_id,
        )
        if params is None:
            _log_entry(
                "Entry order submit failed before gateway call: "
                f"symbol={symbol} order_type={order_type} failure={failure_reason}"
            )
            return False

        payload = self._create_order(params)
        if self._is_order_create_success(payload):
            _log_entry(
                "Trigger entry order submit success: "
                f"symbol={symbol} type={order_type} client_order_id={client_order_id}"
            )
            return True

        error_code, error_message = self._extract_exchange_error(payload)
        if int(error_code) != ENTRY_IMMEDIATE_TRIGGER_REJECT_ERROR_CODE:
            _log_entry(
                "Trigger entry order submit failed: "
                f"symbol={symbol} type={order_type} error_code={error_code} message={error_message or '-'}"
            )
            return False

        _log_entry(
            "Trigger entry order rejected by immediate-trigger rule; "
            f"switching to limit fallback: symbol={symbol} target_price={target_price}"
        )
        fallback_params, fallback_failure = self._build_entry_order_params(
            symbol=symbol,
            target_price=target_price,
            quantity=quantity,
            order_type="LIMIT",
            filter_rules=filter_rules,
            position_mode=position_mode,
            client_order_id=client_order_id,
        )
        if fallback_params is None:
            _log_entry(
                "Limit fallback build failed: "
                f"symbol={symbol} failure={fallback_failure}"
            )
            return False
        fallback_payload = self._create_order(fallback_params)
        if self._is_order_create_success(fallback_payload):
            _log_entry(
                "Limit fallback entry order submit success: "
                f"symbol={symbol} client_order_id={client_order_id}"
            )
            return True
        fallback_error_code, fallback_error_message = self._extract_exchange_error(fallback_payload)
        _log_entry(
            "Limit fallback entry order submit failed: "
            f"symbol={symbol} error_code={fallback_error_code} message={fallback_error_message or '-'}"
        )
        return False

    def _build_entry_order_params(
        self,
        *,
        symbol: str,
        target_price: float,
        quantity: float,
        order_type: str,
        filter_rules: SymbolFilterRules,
        position_mode: str,
        client_order_id: str,
    ) -> tuple[Optional[dict[str, Any]], str]:
        adjusted_price = _round_price_by_tick_size(target_price, filter_rules.tick_size)
        if adjusted_price is None or adjusted_price <= 0:
            return None, "invalid_price"
        formatted_price = _format_order_value_by_increment(
            adjusted_price,
            filter_rules.tick_size,
            rounding_mode=ROUND_HALF_UP,
        )
        if not formatted_price:
            return None, "invalid_price_format"
        adjusted_quantity = _floor_quantity_by_step_size(quantity, filter_rules.step_size)
        if adjusted_quantity is None or adjusted_quantity <= 0:
            return None, "invalid_quantity"
        formatted_quantity = _format_order_value_by_increment(
            adjusted_quantity,
            filter_rules.step_size,
            rounding_mode=ROUND_DOWN,
        )
        if not formatted_quantity:
            return None, "invalid_quantity_format"
        if adjusted_quantity < float(filter_rules.min_qty):
            return None, "min_qty_not_met"
        if (
            filter_rules.min_notional is not None
            and float(filter_rules.min_notional) > 0
            and adjusted_quantity * adjusted_price < float(filter_rules.min_notional)
        ):
            return (
                None,
                "min_notional_not_met:"
                f"notional={adjusted_quantity * adjusted_price:.4f}"
                f"<min_notional={float(filter_rules.min_notional):.4f}",
            )

        params: dict[str, Any] = {
            "symbol": symbol,
            "side": "SELL",
            "type": _normalize_order_type_token(order_type),
            "price": formatted_price,
            "quantity": formatted_quantity,
            "newClientOrderId": client_order_id,
        }
        normalized_order_type = _normalize_order_type_token(order_type)
        if normalized_order_type == "LIMIT":
            params["timeInForce"] = "GTC"
        elif normalized_order_type in {"STOP", "TAKE_PROFIT"}:
            trigger_price = self._resolve_entry_trigger_price(
                side="SELL",
                order_type=normalized_order_type,
                target_price=adjusted_price,
                tick_size=filter_rules.tick_size,
            )
            adjusted_stop_price = _round_price_by_tick_size(trigger_price, filter_rules.tick_size)
            if adjusted_stop_price is None or adjusted_stop_price <= 0:
                return None, "invalid_stop_price"
            formatted_stop_price = _format_order_value_by_increment(
                adjusted_stop_price,
                filter_rules.tick_size,
                rounding_mode=ROUND_HALF_UP,
            )
            if not formatted_stop_price:
                return None, "invalid_stop_price_format"
            params["stopPrice"] = formatted_stop_price
            params["workingType"] = STOP_FAMILY_WORKING_TYPE
            params["timeInForce"] = "GTC"
        else:
            return None, f"unsupported_order_type:{normalized_order_type}"

        if position_mode == "HEDGE":
            params["positionSide"] = "SHORT"
        else:
            params["reduceOnly"] = "false"
        return params, "-"

    @staticmethod
    def _resolve_entry_trigger_order_type(
        *,
        side: str,
        target_price: float,
        reference_mark_price: Optional[float],
    ) -> str:
        normalized_side = str(side or "").strip().upper()
        current_mark = _safe_float(reference_mark_price)
        if normalized_side == "SELL":
            if current_mark is None:
                return "TAKE_PROFIT"
            return "TAKE_PROFIT" if float(target_price) >= current_mark else "STOP"
        if current_mark is None:
            return "STOP"
        return "STOP" if float(target_price) >= current_mark else "TAKE_PROFIT"

    @staticmethod
    def _resolve_entry_trigger_price(
        *,
        side: str,
        order_type: str,
        target_price: float,
        tick_size: float,
    ) -> float:
        target = float(target_price)
        tick = float(tick_size)
        normalized_side = str(side or "").strip().upper()
        normalized_order_type = str(order_type or "").strip().upper()
        trigger_raw = target
        if normalized_order_type == "TAKE_PROFIT":
            trigger_raw = target - tick if normalized_side == "SELL" else target + tick
        elif normalized_order_type == "STOP":
            trigger_raw = target + tick if normalized_side == "SELL" else target - tick
        rounded = _round_price_by_tick_size(trigger_raw, tick)
        if rounded is None or rounded <= 0:
            return target
        return float(rounded)

    def _resolve_relay_base_url(self) -> str:
        from_env = str(os.environ.get(SIGNAL_RELAY_BASE_URL_ENV, "") or "").strip().rstrip("/")
        if from_env:
            return from_env
        return str(getattr(config, "SIGNAL_RELAY_BASE_URL_DEFAULT", "") or "").strip().rstrip("/")

    def _resolve_relay_token(self) -> str:
        from_env = str(os.environ.get(SIGNAL_RELAY_TOKEN_ENV, "") or "").strip()
        if from_env:
            return from_env
        return str(getattr(config, "SIGNAL_RELAY_TOKEN_DEFAULT", "") or "").strip()

    def _resolve_relay_client_id(self) -> str:
        from_env = str(os.environ.get(SIGNAL_RELAY_CLIENT_ID_ENV, "") or "").strip()
        if from_env:
            return from_env
        if self._api_key:
            return f"api-{hashlib.sha256(self._api_key.encode('utf-8')).hexdigest()[:12]}"
        return "anonymous-client"

    def _build_signal_relay_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._relay_token:
            headers["X-LTS-Relay-Token"] = self._relay_token
        return headers

    def _sync_signal_relay_offset_for_fresh_start(self) -> int:
        baseline_offset = max(0, int(self._signal_offset))
        endpoint = f"{self._relay_base_url}/api/v1/offset/latest"
        try:
            response = self._session.get(
                endpoint,
                headers=self._build_signal_relay_headers(),
                timeout=self._relay_request_timeout_sec,
            )
        except requests.RequestException as exc:
            _log_entry(f"Signal relay start-sync failed: endpoint={endpoint} error={exc!r}")
            return baseline_offset
        if int(response.status_code) != 200:
            _log_entry(
                "Signal relay start-sync failed: "
                f"endpoint={endpoint} status={response.status_code}"
            )
            return baseline_offset
        try:
            payload = response.json()
        except ValueError:
            _log_entry(
                "Signal relay start-sync failed: "
                f"endpoint={endpoint} reason=invalid_json body={_trim_text(response.text)!r}"
            )
            return baseline_offset
        latest_event_id = _safe_int(payload.get("latest_event_id")) if isinstance(payload, dict) else 0
        synced_offset = max(baseline_offset, latest_event_id)
        _log_entry(
            "Signal relay start-sync done: "
            f"baseline_offset={baseline_offset} synced_offset={synced_offset} latest_event_id={latest_event_id}"
        )
        return synced_offset

    def _poll_signal_relay_updates(self) -> list[dict[str, Any]]:
        endpoint = f"{self._relay_base_url}/api/v1/signals"
        previous_offset = max(0, int(self._signal_offset))
        params = {
            "after_id": previous_offset,
            "limit": max(1, int(self._relay_poll_limit)),
            "client_id": self._relay_client_id,
        }
        try:
            response = self._session.get(
                endpoint,
                params=params,
                headers=self._build_signal_relay_headers(),
                timeout=self._relay_request_timeout_sec,
            )
        except requests.RequestException as exc:
            _log_entry(f"Signal relay poll failed: endpoint={endpoint} error={exc!r}")
            return []
        if int(response.status_code) != 200:
            _log_entry(
                "Signal relay poll failed: "
                f"endpoint={endpoint} status={response.status_code}"
            )
            return []
        try:
            payload = response.json()
        except ValueError:
            _log_entry(
                "Signal relay poll failed: "
                f"endpoint={endpoint} reason=invalid_json body={_trim_text(response.text)!r}"
            )
            return []
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            _log_entry(
                "Signal relay poll failed: "
                f"endpoint={endpoint} reason=invalid_payload payload={payload!r}"
            )
            return []
        raw_events = payload.get("events")
        if not isinstance(raw_events, list):
            _log_entry(
                "Signal relay poll failed: "
                f"endpoint={endpoint} reason=invalid_events_type events_type={type(raw_events).__name__}"
            )
            return []
        next_after_id = _safe_int(payload.get("next_after_id"))
        latest_event_id = _safe_int(payload.get("latest_event_id"))
        max_event_id_seen = previous_offset
        events: list[dict[str, Any]] = []
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            event_id = _safe_int(raw_event.get("event_id"))
            if event_id > max_event_id_seen:
                max_event_id_seen = event_id
            channel_id = _safe_int(raw_event.get("channel_id"))
            if channel_id not in {self._entry_channel_id, self._risk_channel_id}:
                continue
            message_id = _safe_int(raw_event.get("message_id"))
            message_text = str(raw_event.get("message_text") or "").strip()
            if message_id <= 0 or not message_text:
                continue
            events.append(
                {
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "message_text": message_text,
                    "received_at_local": _safe_int(raw_event.get("received_at_local")) or int(time.time()),
                }
            )
        synced_offset = max(previous_offset, next_after_id, latest_event_id, max_event_id_seen)
        if synced_offset > previous_offset:
            self._signal_offset = synced_offset
        if events:
            _log_entry(
                "Signal relay poll success: "
                f"accepted={len(events)} previous_offset={previous_offset} synced_offset={self._signal_offset}"
            )
        return events

    def _refresh_account_snapshot(
        self,
        *,
        force_balance: bool = False,
        force_orders: bool = False,
    ) -> AccountSnapshot:
        now = time.time()
        previous = self.latest_snapshot()
        wallet_balance = previous.wallet_balance
        if force_balance or now - self._last_balance_refresh_at >= BALANCE_REFRESH_INTERVAL_SEC:
            fetched_balance = self._fetch_futures_balance()
            if fetched_balance is not None:
                wallet_balance = fetched_balance
            self._last_balance_refresh_at = now

        positions = previous.positions
        open_orders = previous.open_orders
        if force_orders or now - self._last_snapshot_refresh_at >= SNAPSHOT_REFRESH_INTERVAL_SEC:
            fetched_positions = self._fetch_open_positions()
            fetched_orders = self._fetch_open_orders()
            if fetched_positions is not None:
                positions = fetched_positions
            if fetched_orders is not None:
                open_orders = fetched_orders
            self._last_snapshot_refresh_at = now

        snapshot = AccountSnapshot(
            wallet_balance=wallet_balance,
            positions=[dict(item) for item in positions],
            open_orders=[dict(item) for item in open_orders],
        )
        with self._state_lock:
            self._snapshot = snapshot
        if callable(self._snapshot_callback):
            try:
                self._snapshot_callback(snapshot)
            except Exception as exc:
                _log_entry(f"Snapshot callback failed: error={exc!r}")
        return snapshot

    def _entry_orders_by_symbol(self, open_orders: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in open_orders:
            symbol = _normalize_symbol(row.get("symbol"))
            if not symbol or not _is_entry_order_row(row):
                continue
            grouped.setdefault(symbol, []).append(row)
        return grouped

    def _entry_order_symbols(self, open_orders: list[dict[str, Any]]) -> set[str]:
        return set(self._entry_orders_by_symbol(open_orders).keys())

    def _fetch_exchange_info_snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._exchange_info_lock:
            if self._exchange_info_cache is not None and now - self._exchange_info_cache_at < 60:
                return self._exchange_info_cache
        payload = self._binance_public_get("https://fapi.binance.com", "/fapi/v1/exchangeInfo")
        if isinstance(payload, dict):
            with self._exchange_info_lock:
                self._exchange_info_cache = payload
                self._exchange_info_cache_at = now
            return payload
        with self._exchange_info_lock:
            return self._exchange_info_cache or {"symbols": []}

    def _validate_symbol_usdt_m(self, symbol: str, exchange_info: Mapping[str, Any]) -> str:
        target = _normalize_symbol(symbol)
        symbols = exchange_info.get("symbols")
        if not isinstance(symbols, list):
            return ""
        for item in symbols:
            if not isinstance(item, Mapping):
                continue
            if _normalize_symbol(item.get("symbol")) != target:
                continue
            quote_asset = _normalize_symbol(item.get("quoteAsset"))
            contract_type = _normalize_symbol(item.get("contractType"))
            status = _normalize_symbol(item.get("status"))
            if quote_asset == "USDT" and contract_type == "PERPETUAL" and status == "TRADING":
                return target
        return ""

    def _get_symbol_filter_rule(
        self,
        symbol: str,
        exchange_info: Mapping[str, Any],
    ) -> Optional[SymbolFilterRules]:
        symbols = exchange_info.get("symbols")
        if not isinstance(symbols, list):
            return None
        target = _normalize_symbol(symbol)
        for item in symbols:
            if not isinstance(item, Mapping):
                continue
            if _normalize_symbol(item.get("symbol")) != target:
                continue
            tick_size = None
            step_size = None
            min_qty = None
            min_notional = None
            for filt in item.get("filters", []):
                if not isinstance(filt, Mapping):
                    continue
                filter_type = str(filt.get("filterType") or "").strip()
                if filter_type == "PRICE_FILTER":
                    tick_size = _safe_float(filt.get("tickSize"))
                elif filter_type == "LOT_SIZE":
                    step_size = _safe_float(filt.get("stepSize"))
                    min_qty = _safe_float(filt.get("minQty"))
                elif filter_type in {"MIN_NOTIONAL", "NOTIONAL"}:
                    min_notional = _safe_float(filt.get("notional") or filt.get("minNotional"))
            if tick_size and step_size and min_qty:
                return SymbolFilterRules(
                    tick_size=float(tick_size),
                    step_size=float(step_size),
                    min_qty=float(min_qty),
                    min_notional=float(min_notional) if min_notional is not None else None,
                )
        return None

    def _fetch_recent_3m_candles(self, symbol: str, limit: int = RECENT_KLINE_LIMIT) -> list[dict[str, Any]]:
        payload = self._binance_public_get(
            "https://fapi.binance.com",
            "/fapi/v1/klines",
            {"symbol": _normalize_symbol(symbol), "interval": "3m", "limit": max(2, int(limit))},
        )
        if not isinstance(payload, list):
            _log_entry(
                "Kline fetch failed: "
                f"symbol={symbol} payload_type={type(payload).__name__ if payload is not None else 'NoneType'}"
            )
            return []
        candles: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 7:
                continue
            high = _safe_float(row[2])
            low = _safe_float(row[3])
            close = _safe_float(row[4])
            if high is None or low is None or close is None:
                continue
            candles.append(
                {
                    "timestamp": _safe_int(row[0]),
                    "close_time": _safe_int(row[6]),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                }
            )
        return candles

    def _fetch_mark_price(self, symbol: str) -> Optional[float]:
        payload = self._binance_public_get(
            "https://fapi.binance.com",
            FUTURES_LAST_PRICE_PATH,
            {"symbol": _normalize_symbol(symbol)},
        )
        if not isinstance(payload, Mapping):
            return None
        return _safe_float(payload.get("price") or payload.get("lastPrice") or payload.get("markPrice"))

    def _fetch_futures_balance(self) -> Optional[float]:
        payload = self._binance_signed_get("https://fapi.binance.com", "/fapi/v2/balance")
        if not isinstance(payload, list):
            return None
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("asset") or "").strip().upper() != "USDT":
                continue
            return _safe_float(item.get("balance"))
        return None

    def _fetch_open_positions(self) -> Optional[list[dict[str, Any]]]:
        payload = self._binance_signed_get("https://fapi.binance.com", POSITION_RISK_PATH)
        if not isinstance(payload, list):
            return None
        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            position_amt = _safe_float(item.get("positionAmt"))
            if position_amt is None or abs(position_amt) <= 1e-9:
                continue
            rows.append(dict(item))
        return rows

    def _fetch_open_orders(self) -> Optional[list[dict[str, Any]]]:
        regular_payload = self._binance_signed_get("https://fapi.binance.com", FUTURES_OPEN_ORDERS_PATH)
        algo_payload = self._binance_signed_get("https://fapi.binance.com", FUTURES_OPEN_ALGO_ORDERS_PATH)
        merged: list[dict[str, Any]] = []
        if isinstance(regular_payload, list):
            for row in regular_payload:
                if not isinstance(row, Mapping):
                    continue
                normalized = _normalize_open_order_row(row, is_algo_order=False)
                if normalized is not None:
                    merged.append(normalized)
        if isinstance(algo_payload, list):
            for row in algo_payload:
                if not isinstance(row, Mapping):
                    continue
                normalized = _normalize_open_order_row(row, is_algo_order=True)
                if normalized is not None:
                    merged.append(normalized)
        if not merged and not isinstance(regular_payload, list) and not isinstance(algo_payload, list):
            return None
        return merged

    @staticmethod
    def _parse_position_mode(payload: object) -> str:
        if not isinstance(payload, Mapping):
            return "UNKNOWN"
        raw = payload.get("dualSidePosition")
        if isinstance(raw, bool):
            return "HEDGE" if raw else "ONE_WAY"
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "false"}:
                return "HEDGE" if lowered == "true" else "ONE_WAY"
        return "UNKNOWN"

    def _fetch_position_mode(self) -> str:
        return self._parse_position_mode(
            self._binance_signed_get("https://fapi.binance.com", POSITION_MODE_PATH)
        )

    def _fetch_symbol_setup(self, symbol: str) -> tuple[bool, int, str]:
        payload = self._binance_signed_get(
            "https://fapi.binance.com",
            POSITION_RISK_PATH,
            {"symbol": _normalize_symbol(symbol)},
        )
        rows = []
        if isinstance(payload, list):
            rows = [
                item
                for item in payload
                if isinstance(item, Mapping) and _normalize_symbol(item.get("symbol")) == _normalize_symbol(symbol)
            ]
        if not rows:
            payload = self._binance_signed_get("https://fapi.binance.com", POSITION_RISK_PATH)
            if isinstance(payload, list):
                rows = [
                    item
                    for item in payload
                    if isinstance(item, Mapping) and _normalize_symbol(item.get("symbol")) == _normalize_symbol(symbol)
                ]
        if not rows:
            return False, 0, "UNKNOWN"
        leverage = _safe_int(rows[0].get("leverage"))
        margin_type = _normalize_symbol(rows[0].get("marginType"))
        if margin_type == "CROSSED":
            margin_type = "CROSS"
        if leverage <= 0 or margin_type not in {"ISOLATED", "CROSS"}:
            return False, 0, "UNKNOWN"
        return True, leverage, margin_type

    def _extract_exchange_error(self, payload: object) -> tuple[int, str]:
        if not isinstance(payload, Mapping):
            return 0, ""
        code = payload.get("code")
        message = payload.get("msg")
        return int(code) if isinstance(code, int) else 0, str(message) if isinstance(message, str) else ""

    @staticmethod
    def _extract_rate_limit_backoff_sec(payload: object, *, status_code: int) -> float:
        message = ""
        if isinstance(payload, Mapping):
            message = str(payload.get("msg") or "")
        elif isinstance(payload, str):
            message = payload

        if int(status_code) not in {418, 429} and "too many requests" not in message.lower():
            return 0.0

        ban_until_match = _RATE_LIMIT_BAN_UNTIL_PATTERN.search(message)
        if ban_until_match is not None:
            ban_until_ms = _safe_int(ban_until_match.group(1))
            if ban_until_ms > 0:
                wait_sec = max(0.0, (ban_until_ms / 1000.0) - time.time())
                if wait_sec > 0:
                    return wait_sec

        return SIGNED_QUERY_RATE_LIMIT_BACKOFF_SEC

    def _should_skip_signed_get_due_to_backoff(self, path: str) -> bool:
        remaining_sec = float(self._signed_query_backoff_until) - time.time()
        if remaining_sec <= 0:
            return False
        now = time.time()
        if now - float(self._signed_query_backoff_last_log_at) >= SIGNED_QUERY_RATE_LIMIT_BACKOFF_LOG_THROTTLE_SEC:
            self._signed_query_backoff_last_log_at = now
            _log_entry(
                "Signed GET skipped during rate-limit backoff: "
                f"path={path} remaining_sec={remaining_sec:.2f}"
            )
        return True

    def _note_signed_get_rate_limit_backoff(self, *, path: str, payload: object, status_code: int) -> None:
        backoff_sec = self._extract_rate_limit_backoff_sec(payload, status_code=status_code)
        if backoff_sec <= 0:
            return
        new_until = time.time() + backoff_sec
        if new_until <= float(self._signed_query_backoff_until):
            return
        self._signed_query_backoff_until = new_until
        self._signed_query_backoff_last_log_at = 0.0
        _log_entry(
            "Signed GET rate-limit backoff enabled: "
            f"path={path} status={status_code} backoff_sec={backoff_sec:.2f}"
        )

    @staticmethod
    def _is_margin_type_no_change_reason(error_code: int, error_message: str) -> bool:
        return int(error_code) == -4046 or "no need to change margin type" in str(error_message or "").lower()

    @staticmethod
    def _is_leverage_no_change_reason(error_code: int, error_message: str) -> bool:
        lowered = str(error_message or "").lower()
        if "no need to change leverage" in lowered:
            return True
        return int(error_code) == -4028 and "already" in lowered and "leverage" in lowered

    def _set_symbol_leverage(self, symbol: str, target_leverage: int) -> bool:
        payload = self._binance_signed_post(
            "https://fapi.binance.com",
            LEVERAGE_SET_PATH,
            {"symbol": _normalize_symbol(symbol), "leverage": max(1, int(target_leverage))},
        )
        error_code, error_message = self._extract_exchange_error(payload)
        if error_code < 0 and not self._is_leverage_no_change_reason(error_code, error_message):
            _log_entry(
                "Pre-order leverage set failed: "
                f"symbol={symbol} target_leverage={target_leverage} error_code={error_code} "
                f"message={error_message or '-'}"
            )
            return False
        _log_entry(
            "Pre-order leverage set ok: "
            f"symbol={symbol} target_leverage={target_leverage} error_code={error_code}"
        )
        return True

    def _set_symbol_margin_type_isolated(self, symbol: str) -> bool:
        payload = self._binance_signed_post(
            "https://fapi.binance.com",
            MARGIN_TYPE_SET_PATH,
            {"symbol": _normalize_symbol(symbol), "marginType": "ISOLATED"},
        )
        error_code, error_message = self._extract_exchange_error(payload)
        if error_code < 0 and not self._is_margin_type_no_change_reason(error_code, error_message):
            _log_entry(
                "Pre-order margin type set failed: "
                f"symbol={symbol} error_code={error_code} message={error_message or '-'}"
            )
            return False
        _log_entry(
            "Pre-order margin type set ok: "
            f"symbol={symbol} error_code={error_code}"
        )
        return True

    def _ensure_symbol_trading_setup(self, *, symbol: str, target_leverage: int) -> bool:
        ok, current_leverage, margin_type = self._fetch_symbol_setup(symbol)
        if not ok:
            _log_entry(f"Pre-order setup fetch failed: symbol={symbol}")
            return False
        if current_leverage != int(target_leverage):
            if not self._set_symbol_leverage(symbol, target_leverage):
                return False
        if margin_type != "ISOLATED":
            if not self._set_symbol_margin_type_isolated(symbol):
                return False
        return True

    def _prepare_algo_create_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        adapted = dict(params)
        adapted["algoType"] = "CONDITIONAL"
        if "stopPrice" in adapted:
            if "triggerPrice" not in adapted:
                adapted["triggerPrice"] = adapted.get("stopPrice")
            adapted.pop("stopPrice", None)
        if "newClientOrderId" in adapted:
            adapted["clientAlgoId"] = adapted.get("newClientOrderId")
            adapted.pop("newClientOrderId", None)
        return adapted

    def _prepare_algo_reference_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        adapted = dict(params)
        if "orderId" in adapted and "algoId" not in adapted:
            adapted["algoId"] = adapted.get("orderId")
            adapted.pop("orderId", None)
        if "origClientOrderId" in adapted and "clientAlgoId" not in adapted:
            adapted["clientAlgoId"] = adapted.get("origClientOrderId")
            adapted.pop("origClientOrderId", None)
        return adapted

    def _create_order(self, params: Mapping[str, Any]) -> Optional[object]:
        path = FUTURES_ALGO_ORDER_PATH if _is_algo_order_type(params.get("type")) else FUTURES_ORDER_PATH
        request_params = self._prepare_algo_create_params(params) if path == FUTURES_ALGO_ORDER_PATH else dict(params)
        _log_entry(
            "Gateway create endpoint selected: "
            f"path={path} symbol={request_params.get('symbol')} type={request_params.get('type')}"
        )
        return self._binance_signed_post("https://fapi.binance.com", path, request_params)

    @staticmethod
    def _is_order_create_success(payload: object) -> bool:
        return isinstance(payload, Mapping) and (
            payload.get("orderId") is not None or payload.get("algoId") is not None
        )

    @staticmethod
    def _is_algo_endpoint_required_payload(payload: object) -> bool:
        if not isinstance(payload, Mapping):
            return False
        code = payload.get("code")
        if isinstance(code, int) and int(code) == -4120:
            return True
        return "algo order" in str(payload.get("msg") or "").lower()

    @staticmethod
    def _is_order_not_found_payload(payload: object) -> bool:
        if not isinstance(payload, Mapping):
            return False
        code = payload.get("code")
        if isinstance(code, int) and int(code) in (-2011, -2013):
            return True
        message = str(payload.get("msg") or "").lower()
        return "unknown order" in message or "does not exist" in message

    def _cancel_order(self, *, symbol: str, order_id: int, is_algo: bool) -> bool:
        primary_path = FUTURES_ALGO_ORDER_PATH if is_algo else FUTURES_ORDER_PATH
        fallback_path = FUTURES_ORDER_PATH if is_algo else FUTURES_ALGO_ORDER_PATH
        params = {"symbol": _normalize_symbol(symbol), "orderId": int(order_id)}
        primary_params = self._prepare_algo_reference_params(params) if primary_path == FUTURES_ALGO_ORDER_PATH else params
        payload = self._binance_signed_delete("https://fapi.binance.com", primary_path, primary_params)
        if isinstance(payload, Mapping) and (
            payload.get("orderId") is not None
            or payload.get("algoId") is not None
            or _normalize_symbol(payload.get("status")) in {"CANCELED", "EXPIRED"}
        ):
            return True
        if self._is_algo_endpoint_required_payload(payload) or self._is_order_not_found_payload(payload):
            fallback_params = self._prepare_algo_reference_params(params) if fallback_path == FUTURES_ALGO_ORDER_PATH else params
            payload = self._binance_signed_delete("https://fapi.binance.com", fallback_path, fallback_params)
            if isinstance(payload, Mapping) and (
                payload.get("orderId") is not None
                or payload.get("algoId") is not None
                or _normalize_symbol(payload.get("status")) in {"CANCELED", "EXPIRED"}
            ):
                return True
        error_code, error_message = self._extract_exchange_error(payload)
        _log_entry(
            "Cancel order failed: "
            f"symbol={symbol} order_id={order_id} error_code={error_code} message={error_message or '-'}"
        )
        return False

    def _current_signed_timestamp_ms(self) -> int:
        with self._server_time_lock:
            offset_ms = int(self._server_time_offset_ms)
        return int(time.time() * 1000) + offset_ms

    @staticmethod
    def _is_server_time_sync_error_payload(payload: object) -> bool:
        if not isinstance(payload, Mapping):
            return False
        code = payload.get("code")
        if isinstance(code, int) and code == -1021:
            return True
        message = str(payload.get("msg") or "").lower()
        return "timestamp for this request" in message or "outside of the recvwindow" in message

    def _sync_server_time_offset_ms(self) -> bool:
        payload = self._binance_public_get("https://fapi.binance.com", SERVER_TIME_SYNC_PATH)
        if not isinstance(payload, Mapping):
            return False
        server_time = _safe_int(payload.get("serverTime"))
        if server_time <= 0:
            return False
        local_time = int(time.time() * 1000)
        with self._server_time_lock:
            self._server_time_offset_ms = int(server_time - local_time)
        _log_entry(
            "Server time offset synchronized: "
            f"server_time={server_time} local_time={local_time} offset_ms={self._server_time_offset_ms}"
        )
        return True

    @staticmethod
    def _strip_signed_request_params(params: Mapping[str, Any]) -> dict[str, Any]:
        cleaned = dict(params)
        cleaned.pop("timestamp", None)
        cleaned.pop("recvWindow", None)
        return cleaned

    def _binance_public_get(
        self,
        base_url: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[object]:
        query = urllib.parse.urlencode(dict(params or {}), doseq=True)
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{query}"
        try:
            response = self._session.get(url, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                _log_entry(
                    f"GET {path} public failed status={response.status_code} "
                    f"params={params or {}} detail={_trim_text(data if data is not None else response.text)!r}"
                )
                return None
            return data
        except requests.RequestException as exc:
            _log_entry(f"GET {path} public request error params={params or {}} error={exc!r}")
            return None

    def _binance_signed_get(
        self,
        base_url: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        *,
        _time_sync_retry_count: int = SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT,
    ) -> Optional[object]:
        if self._should_skip_signed_get_due_to_backoff(path):
            return None
        request_params = dict(params or {})
        request_params["timestamp"] = self._current_signed_timestamp_ms()
        request_params["recvWindow"] = 5000
        query = urllib.parse.urlencode(request_params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = self._session.get(url, headers=headers, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    if self._sync_server_time_offset_ms():
                        return self._binance_signed_get(
                            base_url,
                            path,
                            self._strip_signed_request_params(request_params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                self._note_signed_get_rate_limit_backoff(
                    path=path,
                    payload=data if data is not None else response.text,
                    status_code=int(response.status_code),
                )
                _log_entry(
                    f"GET {path} failed status={response.status_code} params={request_params} "
                    f"detail={_trim_text(data if data is not None else response.text)!r}"
                )
                return data if isinstance(data, (dict, list)) else None
            if self._signed_query_backoff_until > 0:
                self._signed_query_backoff_until = 0.0
                self._signed_query_backoff_last_log_at = 0.0
                _log_entry(f"Signed GET rate-limit backoff cleared: path={path}")
            return data
        except requests.RequestException as exc:
            _log_entry(f"GET {path} request error params={request_params} error={exc!r}")
            return None

    def _binance_signed_post(
        self,
        base_url: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        *,
        _time_sync_retry_count: int = SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT,
    ) -> Optional[object]:
        request_params = dict(params or {})
        request_params["timestamp"] = self._current_signed_timestamp_ms()
        request_params["recvWindow"] = 5000
        query = urllib.parse.urlencode(request_params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = self._session.post(url, headers=headers, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    if self._sync_server_time_offset_ms():
                        return self._binance_signed_post(
                            base_url,
                            path,
                            self._strip_signed_request_params(request_params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                _log_entry(
                    f"POST {path} failed status={response.status_code} params={request_params} "
                    f"detail={_trim_text(data if data is not None else response.text)!r}"
                )
                return data if isinstance(data, Mapping) else None
            return data
        except requests.RequestException as exc:
            _log_entry(f"POST {path} request error params={request_params} error={exc!r}")
            return None

    def _binance_signed_delete(
        self,
        base_url: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        *,
        _time_sync_retry_count: int = SIGNED_REQUEST_TIME_SYNC_RETRY_COUNT,
    ) -> Optional[object]:
        request_params = dict(params or {})
        request_params["timestamp"] = self._current_signed_timestamp_ms()
        request_params["recvWindow"] = 5000
        query = urllib.parse.urlencode(request_params, doseq=True)
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._api_key}
        try:
            response = self._session.delete(url, headers=headers, timeout=10)
            try:
                data = response.json()
            except ValueError:
                data = None
            if not response.ok:
                if _time_sync_retry_count > 0 and self._is_server_time_sync_error_payload(data):
                    if self._sync_server_time_offset_ms():
                        return self._binance_signed_delete(
                            base_url,
                            path,
                            self._strip_signed_request_params(request_params),
                            _time_sync_retry_count=_time_sync_retry_count - 1,
                        )
                _log_entry(
                    f"DELETE {path} failed status={response.status_code} params={request_params} "
                    f"detail={_trim_text(data if data is not None else response.text)!r}"
                )
                return data if isinstance(data, Mapping) else None
            return data if isinstance(data, Mapping) else {}
        except requests.RequestException as exc:
            _log_entry(f"DELETE {path} request error params={request_params} error={exc!r}")
            return None
