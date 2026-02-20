from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from .event_logging import LOG_FIELD_EMPTY, StructuredLogEvent, log_structured_event

ENTRY_SIGNAL_CHANNEL_ID_DEFAULT = -1003782821900
RISK_SIGNAL_CHANNEL_ID_DEFAULT = -1003761851285

COOLDOWN_MINUTES_DEFAULT = 10
SECOND_ENTRY_PERCENT_DEFAULT = 15.0
MARGIN_BUFFER_PCT_DEFAULT = 0.01

WS_STALE_FALLBACK_SECONDS_DEFAULT = 5
STALE_MARK_PRICE_SECONDS_DEFAULT = 15

RATE_LIMIT_FAIL_THRESHOLD_DEFAULT = 5
RATE_LIMIT_RECOVERY_THRESHOLD_DEFAULT = 3

ENTRY_SIGNAL_CHANNEL_ID_ENV = "LTS_ENTRY_SIGNAL_CHANNEL_ID"
RISK_SIGNAL_CHANNEL_ID_ENV = "LTS_RISK_SIGNAL_CHANNEL_ID"
COOLDOWN_MINUTES_ENV = "LTS_COOLDOWN_MINUTES"
SECOND_ENTRY_PERCENT_ENV = "LTS_SECOND_ENTRY_PERCENT"
MARGIN_BUFFER_PCT_ENV = "LTS_MARGIN_BUFFER_PCT"
WS_STALE_FALLBACK_SECONDS_ENV = "LTS_WS_STALE_FALLBACK_SECONDS"
STALE_MARK_PRICE_SECONDS_ENV = "LTS_STALE_MARK_PRICE_SECONDS"
RATE_LIMIT_FAIL_THRESHOLD_ENV = "LTS_RATE_LIMIT_FAIL_THRESHOLD"
RATE_LIMIT_RECOVERY_THRESHOLD_ENV = "LTS_RATE_LIMIT_RECOVERY_THRESHOLD"


@dataclass(frozen=True)
class AutoTradeSettings:
    entry_signal_channel_id: int
    risk_signal_channel_id: int
    cooldown_minutes: int
    second_entry_percent: float
    margin_buffer_pct: float
    ws_stale_fallback_seconds: int
    stale_mark_price_seconds: int
    rate_limit_fail_threshold: int
    rate_limit_recovery_threshold: int


def _log_config_event(
    event: str,
    input_data: str,
    decision: str,
    result: str,
    *,
    state_before: str = LOG_FIELD_EMPTY,
    state_after: str = LOG_FIELD_EMPTY,
    failure_reason: str = LOG_FIELD_EMPTY,
    **context: object,
) -> None:
    log_structured_event(
        StructuredLogEvent(
            component="config",
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


def _read_int(
    env: Mapping[str, str],
    key: str,
    default: int,
    *,
    minimum: Optional[int] = None,
) -> int:
    raw = env.get(key)
    if raw is None:
        _log_config_event(
            "setting_default_used",
            input_data=f"{key}=<missing>",
            decision="use_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            key=key,
            value=default,
        )
        return default
    try:
        value = int(raw)
    except ValueError:
        _log_config_event(
            "setting_parse_failed",
            input_data=f"{key}={raw}",
            decision="fallback_to_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            failure_reason="invalid_int",
            key=key,
            raw=raw,
            fallback=default,
        )
        return default
    if minimum is not None and value < minimum:
        _log_config_event(
            "setting_below_minimum",
            input_data=f"{key}={value}",
            decision="fallback_to_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            failure_reason="below_minimum",
            key=key,
            raw=value,
            minimum=minimum,
            fallback=default,
        )
        return default
    _log_config_event(
        "setting_loaded",
        input_data=f"{key}={raw}",
        decision="accept_input",
        result=f"value={value}",
        state_before="loading",
        state_after="loading",
        key=key,
        value=value,
    )
    return value


def _read_float(
    env: Mapping[str, str],
    key: str,
    default: float,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    raw = env.get(key)
    if raw is None:
        _log_config_event(
            "setting_default_used",
            input_data=f"{key}=<missing>",
            decision="use_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            key=key,
            value=default,
        )
        return default
    try:
        value = float(raw)
    except ValueError:
        _log_config_event(
            "setting_parse_failed",
            input_data=f"{key}={raw}",
            decision="fallback_to_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            failure_reason="invalid_float",
            key=key,
            raw=raw,
            fallback=default,
        )
        return default
    if minimum is not None and value < minimum:
        _log_config_event(
            "setting_below_minimum",
            input_data=f"{key}={value}",
            decision="fallback_to_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            failure_reason="below_minimum",
            key=key,
            raw=value,
            minimum=minimum,
            fallback=default,
        )
        return default
    if maximum is not None and value > maximum:
        _log_config_event(
            "setting_above_maximum",
            input_data=f"{key}={value}",
            decision="fallback_to_default",
            result=f"value={default}",
            state_before="loading",
            state_after="loading",
            failure_reason="above_maximum",
            key=key,
            raw=value,
            maximum=maximum,
            fallback=default,
        )
        return default
    _log_config_event(
        "setting_loaded",
        input_data=f"{key}={raw}",
        decision="accept_input",
        result=f"value={value}",
        state_before="loading",
        state_after="loading",
        key=key,
        value=value,
    )
    return value


def load_auto_trade_settings(env: Optional[Mapping[str, str]] = None) -> AutoTradeSettings:
    source = env if env is not None else os.environ
    _log_config_event(
        "settings_load_started",
        input_data=f"env_source={'custom' if env is not None else 'os.environ'}",
        decision="begin_settings_load",
        result="started",
        state_before="idle",
        state_after="loading",
    )

    settings = AutoTradeSettings(
        entry_signal_channel_id=_read_int(
            source,
            ENTRY_SIGNAL_CHANNEL_ID_ENV,
            ENTRY_SIGNAL_CHANNEL_ID_DEFAULT,
        ),
        risk_signal_channel_id=_read_int(
            source,
            RISK_SIGNAL_CHANNEL_ID_ENV,
            RISK_SIGNAL_CHANNEL_ID_DEFAULT,
        ),
        cooldown_minutes=_read_int(
            source,
            COOLDOWN_MINUTES_ENV,
            COOLDOWN_MINUTES_DEFAULT,
            minimum=1,
        ),
        second_entry_percent=_read_float(
            source,
            SECOND_ENTRY_PERCENT_ENV,
            SECOND_ENTRY_PERCENT_DEFAULT,
            minimum=0.0,
        ),
        margin_buffer_pct=_read_float(
            source,
            MARGIN_BUFFER_PCT_ENV,
            MARGIN_BUFFER_PCT_DEFAULT,
            minimum=0.0,
            maximum=0.5,
        ),
        ws_stale_fallback_seconds=_read_int(
            source,
            WS_STALE_FALLBACK_SECONDS_ENV,
            WS_STALE_FALLBACK_SECONDS_DEFAULT,
            minimum=1,
        ),
        stale_mark_price_seconds=_read_int(
            source,
            STALE_MARK_PRICE_SECONDS_ENV,
            STALE_MARK_PRICE_SECONDS_DEFAULT,
            minimum=2,
        ),
        rate_limit_fail_threshold=_read_int(
            source,
            RATE_LIMIT_FAIL_THRESHOLD_ENV,
            RATE_LIMIT_FAIL_THRESHOLD_DEFAULT,
            minimum=1,
        ),
        rate_limit_recovery_threshold=_read_int(
            source,
            RATE_LIMIT_RECOVERY_THRESHOLD_ENV,
            RATE_LIMIT_RECOVERY_THRESHOLD_DEFAULT,
            minimum=1,
        ),
    )
    _log_config_event(
        "settings_load_completed",
        input_data="all_settings_processed",
        decision="finalize_settings",
        result="settings_ready",
        state_before="loading",
        state_after="loaded",
        entry_signal_channel_id=settings.entry_signal_channel_id,
        risk_signal_channel_id=settings.risk_signal_channel_id,
        cooldown_minutes=settings.cooldown_minutes,
        second_entry_percent=settings.second_entry_percent,
        margin_buffer_pct=settings.margin_buffer_pct,
        ws_stale_fallback_seconds=settings.ws_stale_fallback_seconds,
        stale_mark_price_seconds=settings.stale_mark_price_seconds,
        rate_limit_fail_threshold=settings.rate_limit_fail_threshold,
        rate_limit_recovery_threshold=settings.rate_limit_recovery_threshold,
    )
    return settings
