from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional, Sequence

import requests

from .event_logging import LOG_FIELD_EMPTY, StructuredLogEvent, log_structured_event
from .telegram_receiver_models import (
    TelegramPollResult,
    TelegramSignalEvent,
    TelegramUpdateParseResult,
)

TELEGRAM_API_BASE_URL_DEFAULT = "https://api.telegram.org"
TELEGRAM_POLL_LIMIT_DEFAULT = 100
TELEGRAM_POLL_TIMEOUT_SECONDS_DEFAULT = 2
TELEGRAM_REQUEST_TIMEOUT_SECONDS_DEFAULT = 10


def _normalize(value: object) -> str:
    text = " ".join(str(value).split())
    return text if text else LOG_FIELD_EMPTY


def _log_receiver_event(
    *,
    event: str,
    input_data: str,
    decision: str,
    result: str,
    failure_reason: str = LOG_FIELD_EMPTY,
    state_before: str = LOG_FIELD_EMPTY,
    state_after: str = LOG_FIELD_EMPTY,
    **context: object,
) -> None:
    log_structured_event(
        StructuredLogEvent(
            component="telegram_receiver",
            event=event,
            input_data=input_data,
            decision=decision,
            result=result,
            state_before=state_before,
            state_after=state_after,
            failure_reason=failure_reason,
        ),
        **context,
    )


def _read_update_id(update: Mapping[str, Any]) -> Optional[int]:
    try:
        return int(update.get("update_id"))
    except (TypeError, ValueError):
        return None


def _read_message_container(update: Mapping[str, Any]) -> tuple[Optional[str], Optional[Mapping[str, Any]]]:
    for key in ("channel_post", "message"):
        payload = update.get(key)
        if isinstance(payload, Mapping):
            return key, payload
    return None, None


def parse_telegram_update(
    update: Mapping[str, Any],
    *,
    allowed_channel_ids: Sequence[int],
    received_at_local: Optional[int] = None,
) -> TelegramUpdateParseResult:
    update_id = _read_update_id(update)
    if update_id is None:
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="UPDATE_ID_MISSING",
            failure_reason="update_id_missing_or_invalid",
        )

    message_source, message_payload = _read_message_container(update)
    if message_payload is None:
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="MESSAGE_CONTAINER_MISSING",
            failure_reason="message_container_missing",
            update_id=update_id,
        )

    chat_payload = message_payload.get("chat")
    if not isinstance(chat_payload, Mapping):
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="CHAT_PAYLOAD_MISSING",
            failure_reason="chat_payload_missing",
            update_id=update_id,
        )

    try:
        channel_id = int(chat_payload.get("id"))
    except (TypeError, ValueError):
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="CHANNEL_ID_INVALID",
            failure_reason="channel_id_invalid",
            update_id=update_id,
        )

    allowed_set = {int(value) for value in allowed_channel_ids}
    if channel_id not in allowed_set:
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="CHANNEL_NOT_TARGET",
            failure_reason="channel_not_target",
            update_id=update_id,
        )

    try:
        message_id = int(message_payload.get("message_id"))
    except (TypeError, ValueError):
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="MESSAGE_ID_INVALID",
            failure_reason="message_id_missing_or_invalid",
            update_id=update_id,
        )

    text_value = message_payload.get("text")
    if text_value is None:
        text_value = message_payload.get("caption")
    message_text = str(text_value or "").strip()
    if not message_text:
        return TelegramUpdateParseResult(
            accepted=False,
            reason_code="MESSAGE_TEXT_MISSING",
            failure_reason="message_text_missing",
            update_id=update_id,
        )

    event = TelegramSignalEvent(
        update_id=update_id,
        channel_id=channel_id,
        message_id=message_id,
        message_text=message_text,
        received_at_local=int(received_at_local if received_at_local is not None else time.time()),
    )
    return TelegramUpdateParseResult(
        accepted=True,
        reason_code="OK",
        event=event,
        update_id=update_id,
    )


def parse_telegram_update_with_logging(
    update: Mapping[str, Any],
    *,
    allowed_channel_ids: Sequence[int],
    received_at_local: Optional[int] = None,
    loop_label: str = "loop",
) -> TelegramUpdateParseResult:
    result = parse_telegram_update(
        update,
        allowed_channel_ids=allowed_channel_ids,
        received_at_local=received_at_local,
    )
    update_id = _read_update_id(update)
    _log_receiver_event(
        event="parse_telegram_update",
        input_data=f"update_id={_normalize(update_id)}",
        decision="validate_update_payload_and_channel",
        result=result.reason_code,
        failure_reason=result.failure_reason if not result.accepted else LOG_FIELD_EMPTY,
        state_before="parsing",
        state_after="accepted" if result.accepted else "rejected",
        loop_label=loop_label,
        allowed_channels=",".join(str(int(value)) for value in allowed_channel_ids),
        message_source="channel_post_or_message",
    )
    return result


def poll_telegram_updates(
    *,
    bot_token: str,
    allowed_channel_ids: Sequence[int],
    last_update_id: int = 0,
    poll_timeout_seconds: int = TELEGRAM_POLL_TIMEOUT_SECONDS_DEFAULT,
    request_timeout_seconds: int = TELEGRAM_REQUEST_TIMEOUT_SECONDS_DEFAULT,
    limit: int = TELEGRAM_POLL_LIMIT_DEFAULT,
    base_url: str = TELEGRAM_API_BASE_URL_DEFAULT,
    request_get: Callable[..., requests.Response] = requests.get,
    now_provider: Callable[[], float] = time.time,
) -> TelegramPollResult:
    token = str(bot_token or "").strip()
    if not token:
        return TelegramPollResult(
            ok=False,
            reason_code="BOT_TOKEN_MISSING",
            next_update_id=max(0, int(last_update_id)),
            failure_reason="bot_token_missing",
        )

    offset = max(0, int(last_update_id))
    url = f"{base_url.rstrip('/')}/bot{token}/getUpdates"
    params = {
        "offset": offset,
        "timeout": max(0, int(poll_timeout_seconds)),
        "limit": max(1, min(int(limit), 100)),
    }

    try:
        response = request_get(url, params=params, timeout=max(1, int(request_timeout_seconds)))
    except requests.RequestException:
        return TelegramPollResult(
            ok=False,
            reason_code="REQUEST_FAILED",
            next_update_id=offset,
            failure_reason="request_exception",
        )

    if int(getattr(response, "status_code", 0)) != 200:
        return TelegramPollResult(
            ok=False,
            reason_code="HTTP_STATUS_ERROR",
            next_update_id=offset,
            failure_reason=f"http_status_{getattr(response, 'status_code', 'unknown')}",
        )

    try:
        payload = response.json()
    except ValueError:
        return TelegramPollResult(
            ok=False,
            reason_code="INVALID_JSON",
            next_update_id=offset,
            failure_reason="json_decode_failed",
        )

    if not isinstance(payload, Mapping):
        return TelegramPollResult(
            ok=False,
            reason_code="INVALID_PAYLOAD",
            next_update_id=offset,
            failure_reason="payload_not_mapping",
        )

    if payload.get("ok") is not True:
        description = payload.get("description")
        return TelegramPollResult(
            ok=False,
            reason_code="TELEGRAM_API_ERROR",
            next_update_id=offset,
            failure_reason=_normalize(description),
        )

    updates = payload.get("result")
    if not isinstance(updates, list):
        return TelegramPollResult(
            ok=False,
            reason_code="INVALID_RESULT_TYPE",
            next_update_id=offset,
            failure_reason="result_not_list",
        )

    accepted_events: list[TelegramSignalEvent] = []
    next_update_id = offset
    received_at_local = int(now_provider())
    for raw in updates:
        if not isinstance(raw, Mapping):
            continue
        update_id = _read_update_id(raw)
        if update_id is not None:
            next_update_id = max(next_update_id, update_id + 1)
        parsed = parse_telegram_update(
            raw,
            allowed_channel_ids=allowed_channel_ids,
            received_at_local=received_at_local,
        )
        if parsed.accepted and parsed.event is not None:
            accepted_events.append(parsed.event)

    if not updates:
        return TelegramPollResult(
            ok=True,
            reason_code="NO_UPDATES",
            next_update_id=next_update_id,
            events=tuple(),
        )

    return TelegramPollResult(
        ok=True,
        reason_code="OK",
        next_update_id=next_update_id,
        events=tuple(accepted_events),
    )


def poll_telegram_updates_with_logging(
    *,
    bot_token: str,
    allowed_channel_ids: Sequence[int],
    last_update_id: int = 0,
    poll_timeout_seconds: int = TELEGRAM_POLL_TIMEOUT_SECONDS_DEFAULT,
    request_timeout_seconds: int = TELEGRAM_REQUEST_TIMEOUT_SECONDS_DEFAULT,
    limit: int = TELEGRAM_POLL_LIMIT_DEFAULT,
    base_url: str = TELEGRAM_API_BASE_URL_DEFAULT,
    request_get: Callable[..., requests.Response] = requests.get,
    now_provider: Callable[[], float] = time.time,
    loop_label: str = "loop",
) -> TelegramPollResult:
    state_before = f"offset={max(0, int(last_update_id))}"
    result = poll_telegram_updates(
        bot_token=bot_token,
        allowed_channel_ids=allowed_channel_ids,
        last_update_id=last_update_id,
        poll_timeout_seconds=poll_timeout_seconds,
        request_timeout_seconds=request_timeout_seconds,
        limit=limit,
        base_url=base_url,
        request_get=request_get,
        now_provider=now_provider,
    )
    state_after = f"offset={int(result.next_update_id)}"
    _log_receiver_event(
        event="poll_telegram_updates",
        input_data=(
            f"offset={max(0, int(last_update_id))} "
            f"poll_timeout={max(0, int(poll_timeout_seconds))} "
            f"limit={max(1, min(int(limit), 100))}"
        ),
        decision="call_get_updates_and_filter_channels",
        result=result.reason_code,
        failure_reason=result.failure_reason if not result.ok else LOG_FIELD_EMPTY,
        state_before=state_before,
        state_after=state_after,
        event_count=len(result.events),
        loop_label=loop_label,
    )
    return result
