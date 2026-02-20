from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Optional
from urllib.parse import parse_qs, urlparse

import requests

BOT_TOKEN_ENV = "LTS_TELEGRAM_BOT_TOKEN"
ENTRY_CHANNEL_ENV = "LTS_ENTRY_SIGNAL_CHANNEL_ID"
RISK_CHANNEL_ENV = "LTS_RISK_SIGNAL_CHANNEL_ID"
RELAY_TOKEN_ENV = "LTS_SIGNAL_RELAY_TOKEN"

HOST_ENV = "LTS_SIGNAL_RELAY_HOST"
PORT_ENV = "LTS_SIGNAL_RELAY_PORT"
POLL_TIMEOUT_ENV = "LTS_SIGNAL_RELAY_TELEGRAM_POLL_TIMEOUT"
REQUEST_TIMEOUT_ENV = "LTS_SIGNAL_RELAY_TELEGRAM_REQUEST_TIMEOUT"
POLL_LIMIT_ENV = "LTS_SIGNAL_RELAY_TELEGRAM_POLL_LIMIT"
MAX_EVENTS_ENV = "LTS_SIGNAL_RELAY_MAX_EVENTS"
MAX_RESPONSE_LIMIT_ENV = "LTS_SIGNAL_RELAY_MAX_RESPONSE_LIMIT"
SYNC_MAX_BATCHES_ENV = "LTS_SIGNAL_RELAY_SYNC_MAX_BATCHES"
OFFSET_PATH_ENV = "LTS_SIGNAL_RELAY_OFFSET_PATH"

TELEGRAM_API_BASE_URL = "https://api.telegram.org"

DEFAULT_ENTRY_CHANNEL = -1003782821900
DEFAULT_RISK_CHANNEL = -1003761851285
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_POLL_TIMEOUT = 2
DEFAULT_REQUEST_TIMEOUT = 10
DEFAULT_POLL_LIMIT = 100
DEFAULT_MAX_EVENTS = 5000
DEFAULT_MAX_RESPONSE_LIMIT = 100
DEFAULT_SYNC_MAX_BATCHES = 300
DEFAULT_OFFSET_PATH = "/tmp/lts-signal-relay-offset.json"
ERROR_LOG_THROTTLE_SEC = 5
IDLE_SIGNALS_LOG_THROTTLE_SEC = 60


def _log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [relay] {message}", flush=True)


def _read_int_env(
    key: str,
    default: int,
    *,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    raw = os.environ.get(key)
    if raw is None:
        _log(f"config default_used key={key} value={default} reason=missing")
        return default
    try:
        value = int(raw)
    except ValueError:
        _log(f"config default_used key={key} value={default} reason=invalid_int raw={raw!r}")
        return default
    if minimum is not None and value < minimum:
        _log(
            "config default_used "
            f"key={key} value={default} reason=below_minimum raw={value} minimum={minimum}"
        )
        return default
    if maximum is not None and value > maximum:
        _log(
            "config default_used "
            f"key={key} value={default} reason=above_maximum raw={value} maximum={maximum}"
        )
        return default
    _log(f"config loaded key={key} value={value}")
    return value


def _read_str_env(key: str, default: str = "") -> str:
    raw = os.environ.get(key)
    if raw is None:
        if default:
            _log(f"config default_used key={key} value={default!r} reason=missing")
        else:
            _log(f"config missing key={key}")
        return default
    value = str(raw).strip()
    if not value:
        if default:
            _log(f"config default_used key={key} value={default!r} reason=empty")
            return default
        _log(f"config missing key={key} reason=empty")
        return ""
    _log(f"config loaded key={key} value={value!r}")
    return value


@dataclass(frozen=True)
class RelayEvent:
    event_id: int
    update_id: int
    channel_id: int
    message_id: int
    message_text: str
    received_at_local: int

    def to_json(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "update_id": self.update_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "message_text": self.message_text,
            "received_at_local": self.received_at_local,
        }


class RelayStore:
    def __init__(self, *, max_events: int) -> None:
        self._max_events = max(100, int(max_events))
        self._lock = threading.Lock()
        self._events: Deque[RelayEvent] = deque()
        # Seed event ids from current epoch-ms so clients with stale high after_id
        # can resume without requiring process restart after relay redeploys.
        self._next_event_id = max(1, int(time.time() * 1000))
        self._latest_update_id = 0
        self._recent_message_keys: Deque[tuple[int, int]] = deque()
        self._recent_message_set: set[tuple[int, int]] = set()
        self._max_recent_keys = self._max_events * 2
        _log(
            "store initialized "
            f"max_events={self._max_events} max_recent_keys={self._max_recent_keys} "
            f"seed_event_id={self._next_event_id}"
        )

    def add_event(
        self,
        *,
        update_id: int,
        channel_id: int,
        message_id: int,
        message_text: str,
        received_at_local: int,
    ) -> tuple[bool, str, Optional[int]]:
        normalized_text = str(message_text or "").strip()
        if not normalized_text:
            return False, "MESSAGE_TEXT_EMPTY", None

        key = (int(channel_id), int(message_id))
        with self._lock:
            if key in self._recent_message_set:
                return False, "DUPLICATE_MESSAGE_KEY", None
            event_id = self._next_event_id
            self._next_event_id += 1
            event = RelayEvent(
                event_id=event_id,
                update_id=int(update_id),
                channel_id=int(channel_id),
                message_id=int(message_id),
                message_text=normalized_text,
                received_at_local=int(received_at_local),
            )
            self._events.append(event)
            self._latest_update_id = max(self._latest_update_id, int(update_id))
            self._recent_message_keys.append(key)
            self._recent_message_set.add(key)

            while len(self._events) > self._max_events:
                dropped = self._events.popleft()
                dropped_key = (dropped.channel_id, dropped.message_id)
                if dropped_key in self._recent_message_set:
                    self._recent_message_set.discard(dropped_key)
                try:
                    self._recent_message_keys.remove(dropped_key)
                except ValueError:
                    pass

            while len(self._recent_message_keys) > self._max_recent_keys:
                old_key = self._recent_message_keys.popleft()
                self._recent_message_set.discard(old_key)

            return True, "ACCEPTED", event_id

    def list_events(self, *, after_id: int, limit: int) -> tuple[list[RelayEvent], int, int]:
        normalized_after = max(0, int(after_id))
        normalized_limit = max(1, int(limit))
        with self._lock:
            selected = [event for event in self._events if event.event_id > normalized_after][:normalized_limit]
            latest_event_id = self._events[-1].event_id if self._events else 0
        next_after_id = normalized_after
        if selected:
            next_after_id = selected[-1].event_id
        else:
            next_after_id = max(normalized_after, latest_event_id)
        return selected, next_after_id, latest_event_id

    def latest_event_id(self) -> int:
        with self._lock:
            return self._events[-1].event_id if self._events else 0

    def latest_update_id(self) -> int:
        with self._lock:
            return int(self._latest_update_id)


class OffsetPersistence:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        _log(f"offset persistence initialized path={self.path}")

    def load(self) -> int:
        with self._lock:
            if not self.path.exists():
                _log("offset load default_used value=0 reason=file_missing")
                return 0
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                _log(f"offset load failed reason=read_error error={exc!r}")
                return 0
            if not isinstance(data, dict):
                _log("offset load failed reason=invalid_payload_type")
                return 0
            value = data.get("last_update_id")
            try:
                normalized = max(0, int(value))
            except (TypeError, ValueError):
                _log(f"offset load failed reason=invalid_value raw={value!r}")
                return 0
            _log(f"offset loaded last_update_id={normalized}")
            return normalized

    def save(self, offset: int) -> None:
        normalized = max(0, int(offset))
        payload = {
            "last_update_id": normalized,
            "saved_at": int(time.time()),
        }
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            except Exception as exc:
                _log(f"offset save failed value={normalized} error={exc!r}")
                return
        _log(f"offset saved last_update_id={normalized}")


class TelegramPoller:
    def __init__(
        self,
        *,
        bot_token: str,
        allowed_channels: tuple[int, int],
        poll_timeout_sec: int,
        request_timeout_sec: int,
        limit: int,
        sync_max_batches: int,
        store: RelayStore,
        offset_store: OffsetPersistence,
    ) -> None:
        self.bot_token = str(bot_token).strip()
        self.allowed_channels = {int(value) for value in allowed_channels}
        self.poll_timeout_sec = max(0, int(poll_timeout_sec))
        self.request_timeout_sec = max(1, int(request_timeout_sec))
        self.limit = max(1, min(int(limit), 100))
        self.sync_max_batches = max(1, int(sync_max_batches))
        self.store = store
        self.offset_store = offset_store
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error_log_at = 0.0
        self._next_update_id = max(0, int(self.offset_store.load()))
        self._session = requests.Session()
        _log(
            "telegram poller initialized "
            f"allowed_channels={sorted(self.allowed_channels)} "
            f"poll_timeout={self.poll_timeout_sec} request_timeout={self.request_timeout_sec} "
            f"limit={self.limit} start_offset={self._next_update_id}"
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            _log("telegram poller start skipped reason=already_running")
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        _log("telegram poller thread started")

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        try:
            self._session.close()
        except Exception:
            pass
        _log("telegram poller stopped")

    def _build_get_updates_url(self) -> str:
        return f"{TELEGRAM_API_BASE_URL}/bot{self.bot_token}/getUpdates"

    def _call_get_updates(self, *, offset: int, timeout_sec: int) -> tuple[bool, str, list[dict[str, Any]], int]:
        params = {
            "offset": max(0, int(offset)),
            "timeout": max(0, int(timeout_sec)),
            "limit": self.limit,
        }
        url = self._build_get_updates_url()
        try:
            response = self._session.get(url, params=params, timeout=self.request_timeout_sec)
        except requests.RequestException:
            return False, "REQUEST_EXCEPTION", [], max(0, int(offset))
        if int(getattr(response, "status_code", 0)) != 200:
            return False, f"HTTP_{int(getattr(response, 'status_code', 0))}", [], max(0, int(offset))
        try:
            payload = response.json()
        except ValueError:
            return False, "INVALID_JSON", [], max(0, int(offset))
        if not isinstance(payload, dict):
            return False, "INVALID_PAYLOAD", [], max(0, int(offset))
        if payload.get("ok") is not True:
            description = str(payload.get("description") or "telegram_api_error")
            return False, f"TELEGRAM_API_{description}", [], max(0, int(offset))
        raw_updates = payload.get("result")
        if not isinstance(raw_updates, list):
            return False, "INVALID_RESULT_TYPE", [], max(0, int(offset))
        next_offset = max(0, int(offset))
        normalized_updates: list[dict[str, Any]] = []
        for item in raw_updates:
            if not isinstance(item, dict):
                continue
            update_id_raw = item.get("update_id")
            try:
                update_id = int(update_id_raw)
            except (TypeError, ValueError):
                continue
            next_offset = max(next_offset, update_id + 1)
            normalized_updates.append(item)
        return True, "OK" if normalized_updates else "NO_UPDATES", normalized_updates, next_offset

    @staticmethod
    def _extract_message_container(update: dict[str, Any]) -> Optional[dict[str, Any]]:
        channel_post = update.get("channel_post")
        if isinstance(channel_post, dict):
            return channel_post
        message = update.get("message")
        if isinstance(message, dict):
            return message
        return None

    def _ingest_update(self, update: dict[str, Any]) -> tuple[bool, str]:
        try:
            update_id = int(update.get("update_id"))
        except (TypeError, ValueError):
            return False, "UPDATE_ID_INVALID"

        message = self._extract_message_container(update)
        if message is None:
            return False, "MESSAGE_CONTAINER_MISSING"

        chat = message.get("chat")
        if not isinstance(chat, dict):
            return False, "CHAT_MISSING"
        try:
            channel_id = int(chat.get("id"))
        except (TypeError, ValueError):
            return False, "CHANNEL_ID_INVALID"
        if channel_id not in self.allowed_channels:
            return False, "CHANNEL_NOT_TARGET"

        try:
            message_id = int(message.get("message_id"))
        except (TypeError, ValueError):
            return False, "MESSAGE_ID_INVALID"

        text_raw = message.get("text")
        if text_raw is None:
            text_raw = message.get("caption")
        message_text = str(text_raw or "").strip()
        if not message_text:
            return False, "MESSAGE_TEXT_EMPTY"

        accepted, reason, event_id = self.store.add_event(
            update_id=update_id,
            channel_id=channel_id,
            message_id=message_id,
            message_text=message_text,
            received_at_local=int(time.time()),
        )
        if not accepted:
            return False, reason
        _log(
            "event accepted "
            f"event_id={event_id} update_id={update_id} channel_id={channel_id} message_id={message_id}"
        )
        return True, "ACCEPTED"

    def _sync_fresh_start_offset(self) -> None:
        if self._next_update_id > 0:
            _log(
                "telegram start-sync skipped "
                f"reason=offset_already_persisted current_offset={self._next_update_id}"
            )
            return
        _log("telegram start-sync begin mode=discard_backlog")
        synced_offset = self._next_update_id
        batch_count = 0
        discarded_updates = 0
        final_reason = "NO_UPDATES"
        while batch_count < self.sync_max_batches and not self._stop_event.is_set():
            batch_count += 1
            ok, reason, updates, next_offset = self._call_get_updates(offset=synced_offset, timeout_sec=0)
            if not ok:
                _log(
                    "telegram start-sync failed "
                    f"batch={batch_count} offset={synced_offset} reason={reason}"
                )
                break
            synced_offset = max(synced_offset, next_offset)
            discarded_updates += len(updates)
            final_reason = reason
            if reason == "NO_UPDATES":
                break
        self._next_update_id = max(self._next_update_id, synced_offset)
        self.offset_store.save(self._next_update_id)
        _log(
            "telegram start-sync done "
            f"offset={self._next_update_id} discarded_updates={discarded_updates} "
            f"batches={batch_count} reason={final_reason}"
        )

    def _run_loop(self) -> None:
        _log("telegram poll loop entered")
        self._sync_fresh_start_offset()
        while not self._stop_event.is_set():
            ok, reason, updates, next_offset = self._call_get_updates(
                offset=self._next_update_id,
                timeout_sec=self.poll_timeout_sec,
            )
            if not ok:
                now = time.time()
                if now - self._last_error_log_at >= ERROR_LOG_THROTTLE_SEC:
                    self._last_error_log_at = now
                    _log(
                        "telegram poll failed "
                        f"offset={self._next_update_id} reason={reason}"
                    )
                time.sleep(1)
                continue

            if next_offset > self._next_update_id:
                self._next_update_id = int(next_offset)
                self.offset_store.save(self._next_update_id)

            if reason == "NO_UPDATES":
                continue

            accepted_count = 0
            rejected_count = 0
            for update in updates:
                accepted, ingest_reason = self._ingest_update(update)
                if accepted:
                    accepted_count += 1
                else:
                    rejected_count += 1
                    if ingest_reason not in ("CHANNEL_NOT_TARGET", "DUPLICATE_MESSAGE_KEY"):
                        _log(f"event rejected reason={ingest_reason}")
            _log(
                "telegram poll processed "
                f"updates={len(updates)} accepted={accepted_count} rejected={rejected_count} "
                f"next_offset={self._next_update_id}"
            )
        _log("telegram poll loop exited")


@dataclass(frozen=True)
class RelayConfig:
    host: str
    port: int
    relay_token: str
    max_response_limit: int


@dataclass(frozen=True)
class RelayContext:
    config: RelayConfig
    store: RelayStore
    poller: TelegramPoller


class RelayRequestHandler(BaseHTTPRequestHandler):
    context: RelayContext
    _idle_signals_log_lock = threading.Lock()
    _idle_signals_last_log_at = 0.0

    def log_message(self, format: str, *args: Any) -> None:
        message = format % args
        # Suppress noisy successful long-poll access logs for the hot path.
        if self.path.startswith("/api/v1/signals") and " 200 " in message:
            return
        _log(f"http access client={self.client_address[0]} message={message}")

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _is_authorized(self) -> tuple[bool, str]:
        token = self.context.config.relay_token
        if not token:
            return True, "TOKEN_NOT_REQUIRED"
        provided = str(self.headers.get("X-LTS-Relay-Token") or "").strip()
        if provided and provided == token:
            return True, "TOKEN_MATCHED"
        return False, "TOKEN_MISMATCH"

    def _handle_health(self) -> None:
        payload = {
            "ok": True,
            "service": "lts-signal-relay",
            "latest_event_id": self.context.store.latest_event_id(),
            "latest_update_id": self.context.store.latest_update_id(),
            "timestamp": int(time.time()),
        }
        self._write_json(HTTPStatus.OK, payload)

    def _handle_latest_offset(self) -> None:
        authorized, reason = self._is_authorized()
        if not authorized:
            _log(f"http unauthorized path=/api/v1/offset/latest reason={reason}")
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "reason": "UNAUTHORIZED"})
            return
        latest_event_id = self.context.store.latest_event_id()
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "latest_event_id": latest_event_id,
                "timestamp": int(time.time()),
            },
        )
        _log(f"http latest_offset served latest_event_id={latest_event_id}")

    def _handle_signals(self, query: dict[str, list[str]]) -> None:
        authorized, reason = self._is_authorized()
        if not authorized:
            _log(f"http unauthorized path=/api/v1/signals reason={reason}")
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "reason": "UNAUTHORIZED"})
            return

        after_id = self._safe_int((query.get("after_id") or ["0"])[0], default=0)
        limit = self._safe_int(
            (query.get("limit") or [str(self.context.config.max_response_limit)])[0],
            default=self.context.config.max_response_limit,
        )
        normalized_limit = max(1, min(int(limit), int(self.context.config.max_response_limit)))
        client_id = str((query.get("client_id") or ["anonymous"])[0]).strip() or "anonymous"

        events, next_after_id, latest_event_id = self.context.store.list_events(
            after_id=max(0, int(after_id)),
            limit=normalized_limit,
        )
        payload = {
            "ok": True,
            "events": [event.to_json() for event in events],
            "next_after_id": next_after_id,
            "latest_event_id": latest_event_id,
            "timestamp": int(time.time()),
        }
        self._write_json(HTTPStatus.OK, payload)
        event_count = len(events)
        if event_count > 0:
            _log(
                "http signals served "
                f"client_id={client_id} after_id={after_id} limit={normalized_limit} "
                f"events={event_count} next_after_id={next_after_id} latest_event_id={latest_event_id}"
            )
            return

        now = time.time()
        should_log_idle = False
        handler_cls = type(self)
        with handler_cls._idle_signals_log_lock:
            if now - handler_cls._idle_signals_last_log_at >= IDLE_SIGNALS_LOG_THROTTLE_SEC:
                handler_cls._idle_signals_last_log_at = now
                should_log_idle = True
        if should_log_idle:
            _log(
                "http signals idle "
                f"client_id={client_id} after_id={after_id} limit={normalized_limit} "
                f"events=0 next_after_id={next_after_id} latest_event_id={latest_event_id} "
                f"throttle_sec={IDLE_SIGNALS_LOG_THROTTLE_SEC}"
            )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/health":
            self._handle_health()
            return
        if path == "/api/v1/offset/latest":
            self._handle_latest_offset()
            return
        if path == "/api/v1/signals":
            self._handle_signals(query)
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "reason": "NOT_FOUND", "path": path})
        _log(f"http not_found path={path}")


def _build_context() -> RelayContext:
    bot_token = _read_str_env(BOT_TOKEN_ENV, "")
    if not bot_token:
        raise RuntimeError(f"{BOT_TOKEN_ENV} is required for relay server startup")

    entry_channel_id = _read_int_env(ENTRY_CHANNEL_ENV, DEFAULT_ENTRY_CHANNEL)
    risk_channel_id = _read_int_env(RISK_CHANNEL_ENV, DEFAULT_RISK_CHANNEL)
    host = _read_str_env(HOST_ENV, DEFAULT_HOST)
    port = _read_int_env(PORT_ENV, DEFAULT_PORT, minimum=1, maximum=65535)
    poll_timeout = _read_int_env(POLL_TIMEOUT_ENV, DEFAULT_POLL_TIMEOUT, minimum=0, maximum=60)
    request_timeout = _read_int_env(REQUEST_TIMEOUT_ENV, DEFAULT_REQUEST_TIMEOUT, minimum=1, maximum=120)
    poll_limit = _read_int_env(POLL_LIMIT_ENV, DEFAULT_POLL_LIMIT, minimum=1, maximum=100)
    max_events = _read_int_env(MAX_EVENTS_ENV, DEFAULT_MAX_EVENTS, minimum=100, maximum=200000)
    max_response_limit = _read_int_env(
        MAX_RESPONSE_LIMIT_ENV,
        DEFAULT_MAX_RESPONSE_LIMIT,
        minimum=1,
        maximum=1000,
    )
    sync_max_batches = _read_int_env(SYNC_MAX_BATCHES_ENV, DEFAULT_SYNC_MAX_BATCHES, minimum=1, maximum=5000)
    offset_path = _read_str_env(OFFSET_PATH_ENV, DEFAULT_OFFSET_PATH)
    relay_token = _read_str_env(RELAY_TOKEN_ENV, "")

    store = RelayStore(max_events=max_events)
    offset_store = OffsetPersistence(offset_path)
    poller = TelegramPoller(
        bot_token=bot_token,
        allowed_channels=(entry_channel_id, risk_channel_id),
        poll_timeout_sec=poll_timeout,
        request_timeout_sec=request_timeout,
        limit=poll_limit,
        sync_max_batches=sync_max_batches,
        store=store,
        offset_store=offset_store,
    )
    config = RelayConfig(
        host=host,
        port=port,
        relay_token=relay_token,
        max_response_limit=max_response_limit,
    )
    _log(
        "context built "
        f"host={host} port={port} entry_channel_id={entry_channel_id} "
        f"risk_channel_id={risk_channel_id} max_events={max_events} "
        f"max_response_limit={max_response_limit} relay_token_set={bool(relay_token)}"
    )
    return RelayContext(config=config, store=store, poller=poller)


def run() -> int:
    try:
        context = _build_context()
    except Exception as exc:
        _log(f"startup failed error={exc!r}")
        return 1

    RelayRequestHandler.context = context
    server = ThreadingHTTPServer((context.config.host, int(context.config.port)), RelayRequestHandler)
    server.daemon_threads = True
    _log(f"http server starting host={context.config.host} port={context.config.port}")
    context.poller.start()

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        _log("shutdown requested reason=keyboard_interrupt")
    except Exception as exc:
        _log(f"http server crashed error={exc!r}")
    finally:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        context.poller.stop()
        _log("shutdown completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
