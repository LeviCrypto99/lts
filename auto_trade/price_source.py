from __future__ import annotations

import math
from typing import Any

from .event_logging import StructuredLogEvent, log_structured_event
from .price_source_models import (
    MarkPriceReadResult,
    MarkPriceRecord,
    PriceSourceGuardResult,
    PriceSourceMode,
    PriceSourceModeResult,
    PriceSourceState,
    PriceSourceUpdateResult,
    SafetyLockDecision,
)
from .state_machine import set_safety_lock
from .state_machine_models import GlobalState


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _is_valid_mark_price(value: float) -> bool:
    return math.isfinite(float(value)) and float(value) > 0.0


def _is_valid_timestamp(value: int) -> bool:
    return int(value) > 0


def _age_seconds(now: int, last_received_at: int) -> int:
    if int(last_received_at) <= 0:
        return 10**9
    return max(0, int(now) - int(last_received_at))


def _copy_state(
    state: PriceSourceState,
    *,
    mode: PriceSourceMode | None = None,
    ws_last_received_at: int | None = None,
    rest_last_received_at: int | None = None,
    ws_mark_prices: dict[str, MarkPriceRecord] | None = None,
    rest_mark_prices: dict[str, MarkPriceRecord] | None = None,
) -> PriceSourceState:
    return PriceSourceState(
        mode=state.mode if mode is None else mode,
        ws_last_received_at=(
            state.ws_last_received_at if ws_last_received_at is None else int(ws_last_received_at)
        ),
        rest_last_received_at=(
            state.rest_last_received_at
            if rest_last_received_at is None
            else int(rest_last_received_at)
        ),
        ws_mark_prices=dict(state.ws_mark_prices) if ws_mark_prices is None else dict(ws_mark_prices),
        rest_mark_prices=(
            dict(state.rest_mark_prices) if rest_mark_prices is None else dict(rest_mark_prices)
        ),
    )


def record_ws_mark_price(
    state: PriceSourceState,
    *,
    symbol: str,
    mark_price: float,
    received_at: int,
) -> PriceSourceUpdateResult:
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return PriceSourceUpdateResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="INVALID_SYMBOL",
            source="WS",
            symbol=None,
        )
    if not _is_valid_mark_price(mark_price):
        return PriceSourceUpdateResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="INVALID_MARK_PRICE",
            source="WS",
            symbol=normalized_symbol,
        )
    if not _is_valid_timestamp(received_at):
        return PriceSourceUpdateResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="INVALID_RECEIVED_AT",
            source="WS",
            symbol=normalized_symbol,
        )

    ws_prices = dict(state.ws_mark_prices)
    ws_prices[normalized_symbol] = MarkPriceRecord(
        mark_price=float(mark_price),
        received_at=int(received_at),
    )
    current = _copy_state(
        state,
        mode="WS_PRIMARY",
        ws_last_received_at=max(int(state.ws_last_received_at), int(received_at)),
        ws_mark_prices=ws_prices,
    )
    changed = current != state
    reason_code = (
        "WS_PRICE_RECORDED_AND_MODE_RECOVERED"
        if state.mode != "WS_PRIMARY"
        else "WS_PRICE_RECORDED"
    )
    return PriceSourceUpdateResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code=reason_code,
        source="WS",
        symbol=normalized_symbol,
    )


def record_rest_mark_price(
    state: PriceSourceState,
    *,
    symbol: str,
    mark_price: float,
    received_at: int,
) -> PriceSourceUpdateResult:
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return PriceSourceUpdateResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="INVALID_SYMBOL",
            source="REST",
            symbol=None,
        )
    if not _is_valid_mark_price(mark_price):
        return PriceSourceUpdateResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="INVALID_MARK_PRICE",
            source="REST",
            symbol=normalized_symbol,
        )
    if not _is_valid_timestamp(received_at):
        return PriceSourceUpdateResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="INVALID_RECEIVED_AT",
            source="REST",
            symbol=normalized_symbol,
        )

    rest_prices = dict(state.rest_mark_prices)
    rest_prices[normalized_symbol] = MarkPriceRecord(
        mark_price=float(mark_price),
        received_at=int(received_at),
    )
    current = _copy_state(
        state,
        rest_last_received_at=max(int(state.rest_last_received_at), int(received_at)),
        rest_mark_prices=rest_prices,
    )
    return PriceSourceUpdateResult(
        previous=state,
        current=current,
        changed=current != state,
        reason_code="REST_PRICE_RECORDED",
        source="REST",
        symbol=normalized_symbol,
    )


def update_price_source_mode(
    state: PriceSourceState,
    *,
    now: int,
    ws_stale_fallback_seconds: int,
) -> PriceSourceModeResult:
    threshold = max(1, int(ws_stale_fallback_seconds))
    ws_age_seconds = _age_seconds(now, state.ws_last_received_at)

    next_mode = "WS_PRIMARY"
    if int(state.ws_last_received_at) <= 0 or ws_age_seconds >= threshold:
        next_mode = "REST_FALLBACK"

    current = _copy_state(state, mode=next_mode)
    changed = next_mode != state.mode
    if next_mode == "REST_FALLBACK":
        reason_code = "WS_STALE_SWITCH_TO_REST" if changed else "REST_FALLBACK_CONTINUE"
    else:
        reason_code = "WS_RECOVERED_SWITCH_TO_PRIMARY" if changed else "WS_PRIMARY_CONTINUE"

    return PriceSourceModeResult(
        previous_mode=state.mode,
        current_mode=next_mode,
        changed=changed,
        ws_age_seconds=ws_age_seconds,
        reason_code=reason_code,
        state=current,
    )


def get_mark_price(
    state: PriceSourceState,
    *,
    symbol: str,
    now: int,
    ws_stale_fallback_seconds: int,
) -> MarkPriceReadResult:
    normalized_symbol = _normalize_symbol(symbol)
    mode_result = update_price_source_mode(
        state,
        now=now,
        ws_stale_fallback_seconds=ws_stale_fallback_seconds,
    )
    current_state = mode_result.state

    if not normalized_symbol:
        return MarkPriceReadResult(
            symbol="",
            mark_price=None,
            source="UNAVAILABLE",
            used_mode=current_state.mode,
            reason_code="INVALID_SYMBOL",
            price_received_at=0,
            price_age_seconds=0,
            state=current_state,
        )

    preferred_is_ws = current_state.mode == "WS_PRIMARY"
    primary_prices = current_state.ws_mark_prices if preferred_is_ws else current_state.rest_mark_prices
    secondary_prices = current_state.rest_mark_prices if preferred_is_ws else current_state.ws_mark_prices

    primary_record = primary_prices.get(normalized_symbol)
    if primary_record is not None:
        return MarkPriceReadResult(
            symbol=normalized_symbol,
            mark_price=primary_record.mark_price,
            source="WS" if preferred_is_ws else "REST",
            used_mode=current_state.mode,
            reason_code="PRIMARY_SOURCE_PRICE",
            price_received_at=primary_record.received_at,
            price_age_seconds=_age_seconds(now, primary_record.received_at),
            state=current_state,
        )

    secondary_record = secondary_prices.get(normalized_symbol)
    if secondary_record is not None:
        return MarkPriceReadResult(
            symbol=normalized_symbol,
            mark_price=secondary_record.mark_price,
            source="REST" if preferred_is_ws else "WS",
            used_mode=current_state.mode,
            reason_code="SECONDARY_SOURCE_FALLBACK",
            price_received_at=secondary_record.received_at,
            price_age_seconds=_age_seconds(now, secondary_record.received_at),
            state=current_state,
        )

    return MarkPriceReadResult(
        symbol=normalized_symbol,
        mark_price=None,
        source="UNAVAILABLE",
        used_mode=current_state.mode,
        reason_code="MARK_PRICE_UNAVAILABLE",
        price_received_at=0,
        price_age_seconds=0,
        state=current_state,
    )


def decide_price_source_safety_lock(
    price_state: PriceSourceState,
    *,
    now: int,
    stale_mark_price_seconds: int,
    has_any_position: bool,
    has_any_open_order: bool,
    has_monitoring: bool,
) -> SafetyLockDecision:
    threshold = max(1, int(stale_mark_price_seconds))
    ws_age_seconds = _age_seconds(now, price_state.ws_last_received_at)
    rest_age_seconds = _age_seconds(now, price_state.rest_last_received_at)

    ws_stale = int(price_state.ws_last_received_at) <= 0 or ws_age_seconds >= threshold
    rest_stale = int(price_state.rest_last_received_at) <= 0 or rest_age_seconds >= threshold
    stale_detected = ws_stale and rest_stale

    if stale_detected:
        if has_any_position:
            return SafetyLockDecision(
                target_safety_locked=True,
                stale_detected=True,
                action="FORCE_MARKET_EXIT",
                reason_code="DUAL_SOURCE_STALE_FORCE_MARKET_EXIT",
                ws_age_seconds=ws_age_seconds,
                rest_age_seconds=rest_age_seconds,
            )
        if has_any_open_order or has_monitoring:
            return SafetyLockDecision(
                target_safety_locked=True,
                stale_detected=True,
                action="CANCEL_OPEN_ORDERS_AND_RESET",
                reason_code="DUAL_SOURCE_STALE_CANCEL_AND_RESET",
                ws_age_seconds=ws_age_seconds,
                rest_age_seconds=rest_age_seconds,
            )
        return SafetyLockDecision(
            target_safety_locked=True,
            stale_detected=True,
            action="RESET_ONLY",
            reason_code="DUAL_SOURCE_STALE_RESET_ONLY",
            ws_age_seconds=ws_age_seconds,
            rest_age_seconds=rest_age_seconds,
        )

    return SafetyLockDecision(
        target_safety_locked=False,
        stale_detected=False,
        action="NONE",
        reason_code="MARK_PRICE_HEALTHY_OR_DEGRADED",
        ws_age_seconds=ws_age_seconds,
        rest_age_seconds=rest_age_seconds,
    )


def apply_price_source_guard(
    global_state: GlobalState,
    price_state: PriceSourceState,
    *,
    now: int,
    stale_mark_price_seconds: int,
    has_monitoring: bool,
) -> PriceSourceGuardResult:
    decision = decide_price_source_safety_lock(
        price_state,
        now=now,
        stale_mark_price_seconds=stale_mark_price_seconds,
        has_any_position=global_state.has_any_position,
        has_any_open_order=global_state.has_any_open_order,
        has_monitoring=has_monitoring,
    )
    transition = set_safety_lock(global_state, enabled=decision.target_safety_locked)
    return PriceSourceGuardResult(
        decision=decision,
        global_transition=transition,
    )


def record_ws_mark_price_with_logging(
    state: PriceSourceState,
    *,
    symbol: str,
    mark_price: float,
    received_at: int,
    loop_label: str = "loop",
) -> PriceSourceUpdateResult:
    result = record_ws_mark_price(
        state,
        symbol=symbol,
        mark_price=mark_price,
        received_at=received_at,
    )
    failed = result.reason_code.startswith("INVALID")
    log_structured_event(
        StructuredLogEvent(
            component="price_source",
            event="record_ws_mark_price",
            input_data=(
                f"symbol={_normalize(symbol)} mark_price={mark_price} "
                f"received_at={received_at}"
            ),
            decision="validate_and_store_ws_mark_price",
            result="updated" if not failed else "rejected",
            state_before=state.mode,
            state_after=result.current.mode,
            failure_reason=result.reason_code if failed else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        changed=result.changed,
        ws_last_received_at=result.current.ws_last_received_at,
        rest_last_received_at=result.current.rest_last_received_at,
    )
    return result


def record_rest_mark_price_with_logging(
    state: PriceSourceState,
    *,
    symbol: str,
    mark_price: float,
    received_at: int,
    loop_label: str = "loop",
) -> PriceSourceUpdateResult:
    result = record_rest_mark_price(
        state,
        symbol=symbol,
        mark_price=mark_price,
        received_at=received_at,
    )
    failed = result.reason_code.startswith("INVALID")
    log_structured_event(
        StructuredLogEvent(
            component="price_source",
            event="record_rest_mark_price",
            input_data=(
                f"symbol={_normalize(symbol)} mark_price={mark_price} "
                f"received_at={received_at}"
            ),
            decision="validate_and_store_rest_mark_price",
            result="updated" if not failed else "rejected",
            state_before=state.mode,
            state_after=result.current.mode,
            failure_reason=result.reason_code if failed else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        changed=result.changed,
        ws_last_received_at=result.current.ws_last_received_at,
        rest_last_received_at=result.current.rest_last_received_at,
    )
    return result


def update_price_source_mode_with_logging(
    state: PriceSourceState,
    *,
    now: int,
    ws_stale_fallback_seconds: int,
    loop_label: str = "loop",
) -> PriceSourceModeResult:
    result = update_price_source_mode(
        state,
        now=now,
        ws_stale_fallback_seconds=ws_stale_fallback_seconds,
    )
    log_structured_event(
        StructuredLogEvent(
            component="price_source",
            event="update_price_source_mode",
            input_data=(
                f"now={now} ws_stale_fallback_seconds={ws_stale_fallback_seconds} "
                f"ws_last_received_at={state.ws_last_received_at}"
            ),
            decision="select_ws_or_rest_source_by_ws_staleness",
            result=result.current_mode,
            state_before=result.previous_mode,
            state_after=result.current_mode,
            failure_reason="-",
        ),
        loop_label=loop_label,
        changed=result.changed,
        reason_code=result.reason_code,
        ws_age_seconds=result.ws_age_seconds,
    )
    return result


def get_mark_price_with_logging(
    state: PriceSourceState,
    *,
    symbol: str,
    now: int,
    ws_stale_fallback_seconds: int,
    loop_label: str = "loop",
) -> MarkPriceReadResult:
    result = get_mark_price(
        state,
        symbol=symbol,
        now=now,
        ws_stale_fallback_seconds=ws_stale_fallback_seconds,
    )
    failed = result.mark_price is None
    log_structured_event(
        StructuredLogEvent(
            component="price_source",
            event="get_mark_price",
            input_data=(
                f"symbol={_normalize(symbol)} now={now} "
                f"ws_stale_fallback_seconds={ws_stale_fallback_seconds}"
            ),
            decision="prefer_source_mode_then_fallback_to_secondary",
            result="resolved" if not failed else "missing",
            state_before=state.mode,
            state_after=result.used_mode,
            failure_reason=result.reason_code if failed else "-",
        ),
        loop_label=loop_label,
        source=result.source,
        reason_code=result.reason_code,
        price_received_at=result.price_received_at,
        price_age_seconds=result.price_age_seconds,
    )
    return result


def apply_price_source_guard_with_logging(
    global_state: GlobalState,
    price_state: PriceSourceState,
    *,
    now: int,
    stale_mark_price_seconds: int,
    has_monitoring: bool,
    loop_label: str = "loop",
) -> PriceSourceGuardResult:
    result = apply_price_source_guard(
        global_state,
        price_state,
        now=now,
        stale_mark_price_seconds=stale_mark_price_seconds,
        has_monitoring=has_monitoring,
    )
    is_safety_lock_on = result.decision.target_safety_locked
    log_structured_event(
        StructuredLogEvent(
            component="price_source",
            event="apply_price_source_guard",
            input_data=(
                f"now={now} stale_mark_price_seconds={stale_mark_price_seconds} "
                f"has_monitoring={has_monitoring}"
            ),
            decision="detect_dual_source_stale_and_apply_safety_lock",
            result="safety_lock_on" if is_safety_lock_on else "safety_lock_off",
            state_before=f"{result.global_transition.previous.entry_state}/{result.global_transition.previous.global_mode}",
            state_after=f"{result.global_transition.current.entry_state}/{result.global_transition.current.global_mode}",
            failure_reason=result.decision.reason_code if is_safety_lock_on else "-",
        ),
        loop_label=loop_label,
        reason_code=result.decision.reason_code,
        action=result.decision.action,
        stale_detected=result.decision.stale_detected,
        ws_age_seconds=result.decision.ws_age_seconds,
        rest_age_seconds=result.decision.rest_age_seconds,
        changed=result.global_transition.changed,
        safety_locked=result.global_transition.current.safety_locked,
        global_blocked=result.global_transition.current.global_blocked,
    )
    return result
