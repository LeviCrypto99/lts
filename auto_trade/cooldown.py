from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .event_logging import StructuredLogEvent, log_structured_event


@dataclass(frozen=True)
class CooldownCheckResult:
    should_ignore: bool
    reason_code: str
    last_received_at: int
    remaining_seconds: int


@dataclass(frozen=True)
class CooldownRecordDecision:
    should_record: bool
    reason_code: str


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def check_symbol_cooldown(
    cooldown_by_symbol: Mapping[str, int],
    *,
    symbol: str,
    received_at: int,
    cooldown_minutes: int,
) -> CooldownCheckResult:
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return CooldownCheckResult(
            should_ignore=True,
            reason_code="INVALID_SYMBOL",
            last_received_at=0,
            remaining_seconds=0,
        )

    cooldown_window_sec = max(0, int(cooldown_minutes)) * 60
    last_received_at = int(cooldown_by_symbol.get(normalized_symbol, 0))
    if cooldown_window_sec <= 0 or last_received_at <= 0:
        return CooldownCheckResult(
            should_ignore=False,
            reason_code="COOLDOWN_NOT_ACTIVE",
            last_received_at=last_received_at,
            remaining_seconds=0,
        )

    elapsed = int(received_at) - last_received_at
    remaining = cooldown_window_sec - elapsed
    if remaining > 0:
        return CooldownCheckResult(
            should_ignore=True,
            reason_code="IN_COOLDOWN_WINDOW",
            last_received_at=last_received_at,
            remaining_seconds=remaining,
        )

    return CooldownCheckResult(
        should_ignore=False,
        reason_code="COOLDOWN_EXPIRED",
        last_received_at=last_received_at,
        remaining_seconds=0,
    )


def record_symbol_cooldown(
    cooldown_by_symbol: Mapping[str, int],
    *,
    symbol: str,
    received_at: int,
) -> Mapping[str, int]:
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return dict(cooldown_by_symbol)
    updated = dict(cooldown_by_symbol)
    updated[normalized_symbol] = int(received_at)
    return updated


def decide_cooldown_recording(
    *,
    blocked_by_entry_lock: bool,
    blocked_by_safety_lock: bool,
    candidate_symbol: str | None,
) -> CooldownRecordDecision:
    if blocked_by_entry_lock:
        return CooldownRecordDecision(
            should_record=False,
            reason_code="BLOCKED_BY_ENTRY_LOCK",
        )
    if blocked_by_safety_lock:
        return CooldownRecordDecision(
            should_record=False,
            reason_code="BLOCKED_BY_SAFETY_LOCK",
        )
    if not (candidate_symbol or "").strip():
        return CooldownRecordDecision(
            should_record=False,
            reason_code="CANDIDATE_SYMBOL_UNAVAILABLE",
        )
    return CooldownRecordDecision(
        should_record=True,
        reason_code="RECORD_BY_SYMBOL",
    )


def check_symbol_cooldown_with_logging(
    cooldown_by_symbol: Mapping[str, int],
    *,
    symbol: str,
    received_at: int,
    cooldown_minutes: int,
) -> CooldownCheckResult:
    result = check_symbol_cooldown(
        cooldown_by_symbol,
        symbol=symbol,
        received_at=received_at,
        cooldown_minutes=cooldown_minutes,
    )
    if result.should_ignore:
        log_structured_event(
            StructuredLogEvent(
                component="cooldown",
                event="check_symbol_cooldown",
                input_data=(
                    f"symbol={_normalize(symbol)} received_at={received_at} "
                    f"cooldown_minutes={cooldown_minutes}"
                ),
                decision="compare_received_time_with_last_symbol_timestamp",
                result="ignore_signal",
                state_before="checking",
                state_after="blocked",
                failure_reason=result.reason_code,
            ),
            remaining_seconds=result.remaining_seconds,
            last_received_at=result.last_received_at,
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="cooldown",
            event="check_symbol_cooldown",
            input_data=(
                f"symbol={_normalize(symbol)} received_at={received_at} "
                f"cooldown_minutes={cooldown_minutes}"
            ),
            decision="compare_received_time_with_last_symbol_timestamp",
            result="allow_signal",
            state_before="checking",
            state_after="allowed",
            failure_reason="-",
        ),
        reason_code=result.reason_code,
        last_received_at=result.last_received_at,
    )
    return result


def record_symbol_cooldown_with_logging(
    cooldown_by_symbol: Mapping[str, int],
    *,
    symbol: str,
    received_at: int,
) -> Mapping[str, int]:
    updated = record_symbol_cooldown(
        cooldown_by_symbol,
        symbol=symbol,
        received_at=received_at,
    )
    log_structured_event(
        StructuredLogEvent(
            component="cooldown",
            event="record_symbol_cooldown",
            input_data=f"symbol={_normalize(symbol)} received_at={received_at}",
            decision="store_latest_symbol_timestamp",
            result="recorded",
            state_before="allowed",
            state_after="recorded",
            failure_reason="-",
        ),
        updated_timestamp=updated.get((symbol or "").strip().upper(), "-"),
    )
    return updated


def decide_cooldown_recording_with_logging(
    *,
    blocked_by_entry_lock: bool,
    blocked_by_safety_lock: bool,
    candidate_symbol: str | None,
) -> CooldownRecordDecision:
    result = decide_cooldown_recording(
        blocked_by_entry_lock=blocked_by_entry_lock,
        blocked_by_safety_lock=blocked_by_safety_lock,
        candidate_symbol=candidate_symbol,
    )
    log_structured_event(
        StructuredLogEvent(
            component="cooldown",
            event="decide_cooldown_recording",
            input_data=(
                f"blocked_by_entry_lock={blocked_by_entry_lock} "
                f"blocked_by_safety_lock={blocked_by_safety_lock} "
                f"candidate_symbol={_normalize(candidate_symbol)}"
            ),
            decision="apply_cooldown_recording_rules",
            result="record" if result.should_record else "skip",
            state_before="deciding",
            state_after="decided",
            failure_reason=result.reason_code if not result.should_record else "-",
        ),
        reason_code=result.reason_code,
    )
    return result
