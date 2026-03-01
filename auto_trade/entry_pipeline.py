from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Optional

from .entry_pipeline_models import (
    EntryBudgetResult,
    EntryPhase,
    EntryPipelineResult,
    EntryQuantityResult,
)
from .event_logging import StructuredLogEvent, log_structured_event
from .order_gateway import create_order_with_retry, round_price_by_tick_size
from .order_gateway_models import (
    GatewayCallResult,
    OrderCreateRequest,
    PositionMode,
    RetryPolicy,
    SymbolFilterRules,
)
from .state_machine import apply_symbol_event
from .state_machine_models import SymbolState


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _is_positive_finite(value: float) -> bool:
    return math.isfinite(float(value)) and float(value) > 0.0


FIRST_ENTRY_BUDGET_BASE_RATIO = 0.5
ENTRY_MODE_TO_FIRST_ENTRY_BUDGET_MULTIPLIER: dict[str, float] = {
    "AGGRESSIVE": 2.0,
    "CONSERVATIVE": 1.0,
}
DEFAULT_ENTRY_MODE = "CONSERVATIVE"


def _resolve_entry_trigger_order_type(
    *,
    side: str,
    target_price: float,
    reference_mark_price: Optional[float],
) -> str:
    normalized_side = str(side or "").strip().upper()
    current_mark = float(reference_mark_price) if _is_positive_finite(float(reference_mark_price or 0.0)) else None
    if normalized_side == "SELL":
        if current_mark is None:
            return "TAKE_PROFIT"
        return "TAKE_PROFIT" if float(target_price) >= current_mark else "STOP"
    if current_mark is None:
        return "STOP"
    return "STOP" if float(target_price) >= current_mark else "TAKE_PROFIT"


def _resolve_entry_trigger_price(
    *,
    side: str,
    order_type: str,
    target_price: float,
    tick_size: float,
) -> float:
    target = float(target_price)
    tick = float(tick_size)
    if not _is_positive_finite(target) or not _is_positive_finite(tick):
        return target
    normalized_side = str(side or "").strip().upper()
    normalized_order_type = str(order_type or "").strip().upper()
    trigger_raw = target
    # One-tick lead rule:
    # - TAKE_PROFIT SELL / STOP BUY  : trigger when >= stopPrice -> use target - 1tick
    # - STOP SELL / TAKE_PROFIT BUY  : trigger when <= stopPrice -> use target + 1tick
    if normalized_order_type == "TAKE_PROFIT":
        trigger_raw = target - tick if normalized_side == "SELL" else target + tick
    elif normalized_order_type == "STOP":
        trigger_raw = target + tick if normalized_side == "SELL" else target - tick
    rounded = round_price_by_tick_size(trigger_raw, tick)
    if rounded is None or float(rounded) <= 0.0:
        return target
    return float(rounded)


def _normalize_entry_mode_token(entry_mode: Any) -> str:
    normalized = str(entry_mode or "").strip().upper()
    if normalized in ENTRY_MODE_TO_FIRST_ENTRY_BUDGET_MULTIPLIER:
        return normalized
    return DEFAULT_ENTRY_MODE


def _resolve_first_entry_budget_multiplier(entry_mode: str) -> float:
    normalized = _normalize_entry_mode_token(entry_mode)
    return float(ENTRY_MODE_TO_FIRST_ENTRY_BUDGET_MULTIPLIER.get(normalized, 1.0))


def _resolve_second_entry_budget_multiplier(entry_mode: str) -> float:
    return _resolve_first_entry_budget_multiplier(entry_mode)


def compute_first_entry_budget(
    wallet_balance_usdt: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
) -> EntryBudgetResult:
    if not _is_positive_finite(wallet_balance_usdt):
        return EntryBudgetResult(
            ok=False,
            budget_usdt=None,
            reason_code="INVALID_WALLET_BALANCE",
            failure_reason="wallet balance must be positive finite number",
        )
    mode_multiplier = _resolve_first_entry_budget_multiplier(entry_mode)
    budget = float(wallet_balance_usdt) * float(FIRST_ENTRY_BUDGET_BASE_RATIO) * float(mode_multiplier)
    if budget <= 0:
        return EntryBudgetResult(
            ok=False,
            budget_usdt=None,
            reason_code="FIRST_ENTRY_BUDGET_NON_POSITIVE",
            failure_reason="first entry budget is not positive",
        )
    return EntryBudgetResult(
        ok=True,
        budget_usdt=budget,
        reason_code="FIRST_ENTRY_BUDGET_READY",
        failure_reason="-",
    )


def compute_second_entry_budget(
    available_usdt: float,
    *,
    margin_buffer_pct: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
) -> EntryBudgetResult:
    if not _is_positive_finite(available_usdt):
        return EntryBudgetResult(
            ok=False,
            budget_usdt=None,
            reason_code="INVALID_AVAILABLE_BALANCE",
            failure_reason="available balance must be positive finite number",
        )
    if not math.isfinite(float(margin_buffer_pct)):
        return EntryBudgetResult(
            ok=False,
            budget_usdt=None,
            reason_code="INVALID_MARGIN_BUFFER",
            failure_reason="margin_buffer_pct must be finite",
        )
    if float(margin_buffer_pct) < 0.0 or float(margin_buffer_pct) >= 1.0:
        return EntryBudgetResult(
            ok=False,
            budget_usdt=None,
            reason_code="MARGIN_BUFFER_OUT_OF_RANGE",
            failure_reason="margin_buffer_pct must be >= 0 and < 1",
        )
    mode_multiplier = _resolve_second_entry_budget_multiplier(entry_mode)
    budget = float(available_usdt) * (1.0 - float(margin_buffer_pct)) * float(mode_multiplier)
    if budget <= 0:
        return EntryBudgetResult(
            ok=False,
            budget_usdt=None,
            reason_code="SECOND_ENTRY_BUDGET_NON_POSITIVE",
            failure_reason="available balance after buffer is not positive",
        )
    return EntryBudgetResult(
        ok=True,
        budget_usdt=budget,
        reason_code="SECOND_ENTRY_BUDGET_READY",
        failure_reason="-",
    )


def compute_entry_quantity(
    *,
    budget_usdt: float,
    target_price: float,
) -> EntryQuantityResult:
    if not _is_positive_finite(budget_usdt):
        return EntryQuantityResult(
            ok=False,
            quantity=None,
            reason_code="INVALID_ENTRY_BUDGET",
            failure_reason="budget_usdt must be positive finite number",
        )
    if not _is_positive_finite(target_price):
        return EntryQuantityResult(
            ok=False,
            quantity=None,
            reason_code="INVALID_TARGET_PRICE",
            failure_reason="target_price must be positive finite number",
        )
    quantity = float(budget_usdt) / float(target_price)
    if not _is_positive_finite(quantity):
        return EntryQuantityResult(
            ok=False,
            quantity=None,
            reason_code="ENTRY_QUANTITY_NOT_FINITE",
            failure_reason="calculated quantity is not finite",
        )
    return EntryQuantityResult(
        ok=True,
        quantity=quantity,
        reason_code="ENTRY_QUANTITY_READY",
        failure_reason="-",
    )


def _reset_result(
    *,
    phase: EntryPhase,
    current_state: SymbolState,
    reason_code: str,
    failure_reason: str,
    gateway_attempts: int,
    gateway_reason_code: str,
    budget_usdt: Optional[float],
    raw_quantity: Optional[float],
) -> EntryPipelineResult:
    transition = apply_symbol_event(current_state, "RESET")
    return EntryPipelineResult(
        phase=phase,
        success=False,
        action="RESET_AND_EXCLUDE",
        reason_code=reason_code,
        failure_reason=failure_reason,
        previous_state=current_state,
        current_state=transition.current_state,
        state_transition_reason=transition.reason_code,
        gateway_attempts=gateway_attempts,
        gateway_reason_code=gateway_reason_code,
        budget_usdt=budget_usdt,
        raw_quantity=raw_quantity,
        refreshed_available_usdt=None,
    )


def _skip_second_entry_result(
    *,
    current_state: SymbolState,
    reason_code: str,
    failure_reason: str,
    gateway_attempts: int,
    gateway_reason_code: str,
    budget_usdt: Optional[float],
    raw_quantity: Optional[float],
    refreshed_available_usdt: Optional[float],
) -> EntryPipelineResult:
    return EntryPipelineResult(
        phase="SECOND_ENTRY",
        success=False,
        action="SECOND_ENTRY_SKIPPED_KEEP_STATE",
        reason_code=reason_code,
        failure_reason=failure_reason,
        previous_state=current_state,
        current_state=current_state,
        state_transition_reason="SECOND_ENTRY_KEEP_STATE",
        gateway_attempts=gateway_attempts,
        gateway_reason_code=gateway_reason_code,
        budget_usdt=budget_usdt,
        raw_quantity=raw_quantity,
        refreshed_available_usdt=refreshed_available_usdt,
    )


def run_first_entry_pipeline(
    *,
    current_state: SymbolState,
    symbol: str,
    target_price: float,
    wallet_balance_usdt: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    create_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    new_client_order_id: Optional[str] = None,
    reference_mark_price: Optional[float] = None,
) -> EntryPipelineResult:
    if current_state not in ("MONITORING", "ENTRY_ORDER"):
        return _reset_result(
            phase="FIRST_ENTRY",
            current_state=current_state,
            reason_code="FIRST_ENTRY_INVALID_STATE",
            failure_reason=f"expected MONITORING/ENTRY_ORDER, got {current_state}",
            gateway_attempts=0,
            gateway_reason_code="NO_GATEWAY_CALL",
            budget_usdt=None,
            raw_quantity=None,
        )

    budget_result = compute_first_entry_budget(
        wallet_balance_usdt,
        entry_mode=entry_mode,
    )
    if not budget_result.ok:
        return _reset_result(
            phase="FIRST_ENTRY",
            current_state=current_state,
            reason_code="FIRST_ENTRY_BUDGET_REJECTED",
            failure_reason=budget_result.reason_code,
            gateway_attempts=0,
            gateway_reason_code="NO_GATEWAY_CALL",
            budget_usdt=None,
            raw_quantity=None,
        )
    quantity_result = compute_entry_quantity(
        budget_usdt=float(budget_result.budget_usdt),
        target_price=target_price,
    )
    if not quantity_result.ok:
        return _reset_result(
            phase="FIRST_ENTRY",
            current_state=current_state,
            reason_code="FIRST_ENTRY_QUANTITY_REJECTED",
            failure_reason=quantity_result.reason_code,
            gateway_attempts=0,
            gateway_reason_code="NO_GATEWAY_CALL",
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=None,
        )

    order_type = _resolve_entry_trigger_order_type(
        side="SELL",
        target_price=float(target_price),
        reference_mark_price=reference_mark_price,
    )
    request = OrderCreateRequest(
        symbol=symbol,
        side="SELL",
        order_type=order_type,  # type: ignore[arg-type]
        purpose="ENTRY",
        quantity=quantity_result.quantity,
        price=target_price,
        stop_price=_resolve_entry_trigger_price(
            side="SELL",
            order_type=order_type,
            target_price=float(target_price),
            tick_size=float(filter_rules.tick_size),
        ),
        reference_price=target_price,
        new_client_order_id=new_client_order_id,
    )
    gateway_result = create_order_with_retry(
        request,
        filter_rules=filter_rules,
        position_mode=position_mode,
        call=create_call,
        retry_policy=retry_policy,
    )
    if gateway_result.success:
        if current_state == "MONITORING":
            transition = apply_symbol_event(current_state, "SUBMIT_ENTRY_ORDER")
            if not transition.accepted:
                return _reset_result(
                    phase="FIRST_ENTRY",
                    current_state=current_state,
                    reason_code="FIRST_ENTRY_STATE_TRANSITION_REJECTED",
                    failure_reason=transition.reason_code,
                    gateway_attempts=gateway_result.attempts,
                    gateway_reason_code=gateway_result.reason_code,
                    budget_usdt=budget_result.budget_usdt,
                    raw_quantity=quantity_result.quantity,
                )
            next_state = transition.current_state
            transition_reason = transition.reason_code
        else:
            next_state = current_state
            transition_reason = "FIRST_ENTRY_KEEP_STATE"
        return EntryPipelineResult(
            phase="FIRST_ENTRY",
            success=True,
            action="ENTRY_SUBMITTED",
            reason_code="FIRST_ENTRY_SUBMITTED",
            failure_reason="-",
            previous_state=current_state,
            current_state=next_state,
            state_transition_reason=transition_reason,
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
            refreshed_available_usdt=None,
        )

    if current_state == "ENTRY_ORDER":
        return EntryPipelineResult(
            phase="FIRST_ENTRY",
            success=False,
            action="FIRST_ENTRY_SKIPPED_KEEP_STATE",
            reason_code="FIRST_ENTRY_CREATE_FAILED_KEEP_STATE",
            failure_reason=gateway_result.reason_code,
            previous_state=current_state,
            current_state=current_state,
            state_transition_reason="FIRST_ENTRY_KEEP_STATE",
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
            refreshed_available_usdt=None,
        )

    if gateway_result.reason_code == "INSUFFICIENT_MARGIN":
        return _reset_result(
            phase="FIRST_ENTRY",
            current_state=current_state,
            reason_code="FIRST_ENTRY_INSUFFICIENT_MARGIN_RESET",
            failure_reason="insufficient margin on first entry",
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
        )

    return _reset_result(
        phase="FIRST_ENTRY",
        current_state=current_state,
        reason_code="FIRST_ENTRY_CREATE_FAILED_RESET",
        failure_reason=gateway_result.reason_code,
        gateway_attempts=gateway_result.attempts,
        gateway_reason_code=gateway_result.reason_code,
        budget_usdt=budget_result.budget_usdt,
        raw_quantity=quantity_result.quantity,
    )


def run_second_entry_pipeline(
    *,
    current_state: SymbolState,
    symbol: str,
    second_target_price: float,
    available_usdt: float,
    margin_buffer_pct: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    create_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    refresh_available_usdt: Optional[Callable[[], float]] = None,
    retry_policy: Optional[RetryPolicy] = None,
    new_client_order_id: Optional[str] = None,
    reference_mark_price: Optional[float] = None,
) -> EntryPipelineResult:
    if current_state != "PHASE1":
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_INVALID_STATE",
            failure_reason=f"expected PHASE1, got {current_state}",
            gateway_attempts=0,
            gateway_reason_code="NO_GATEWAY_CALL",
            budget_usdt=None,
            raw_quantity=None,
            refreshed_available_usdt=None,
        )

    normalized_mode = _normalize_entry_mode_token(entry_mode)
    budget_result = compute_second_entry_budget(
        available_usdt,
        margin_buffer_pct=margin_buffer_pct,
        entry_mode=normalized_mode,
    )
    if not budget_result.ok:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_BUDGET_REJECTED_KEEP_STATE",
            failure_reason=budget_result.reason_code,
            gateway_attempts=0,
            gateway_reason_code="NO_GATEWAY_CALL",
            budget_usdt=None,
            raw_quantity=None,
            refreshed_available_usdt=None,
        )
    quantity_result = compute_entry_quantity(
        budget_usdt=float(budget_result.budget_usdt),
        target_price=second_target_price,
    )
    if not quantity_result.ok:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_QUANTITY_REJECTED_KEEP_STATE",
            failure_reason=quantity_result.reason_code,
            gateway_attempts=0,
            gateway_reason_code="NO_GATEWAY_CALL",
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=None,
            refreshed_available_usdt=None,
        )

    order_type = _resolve_entry_trigger_order_type(
        side="SELL",
        target_price=float(second_target_price),
        reference_mark_price=reference_mark_price,
    )
    request = OrderCreateRequest(
        symbol=symbol,
        side="SELL",
        order_type=order_type,  # type: ignore[arg-type]
        purpose="ENTRY",
        quantity=quantity_result.quantity,
        price=second_target_price,
        stop_price=_resolve_entry_trigger_price(
            side="SELL",
            order_type=order_type,
            target_price=float(second_target_price),
            tick_size=float(filter_rules.tick_size),
        ),
        reference_price=second_target_price,
        new_client_order_id=new_client_order_id,
    )
    gateway_result = create_order_with_retry(
        request,
        filter_rules=filter_rules,
        position_mode=position_mode,
        call=create_call,
        retry_policy=retry_policy,
    )
    if gateway_result.success:
        transition = apply_symbol_event(current_state, "SUBMIT_SECOND_ENTRY_ORDER")
        if not transition.accepted:
            return _skip_second_entry_result(
                current_state=current_state,
                reason_code="SECOND_ENTRY_STATE_TRANSITION_REJECTED_KEEP_STATE",
                failure_reason=transition.reason_code,
                gateway_attempts=gateway_result.attempts,
                gateway_reason_code=gateway_result.reason_code,
                budget_usdt=budget_result.budget_usdt,
                raw_quantity=quantity_result.quantity,
                refreshed_available_usdt=None,
            )
        return EntryPipelineResult(
            phase="SECOND_ENTRY",
            success=True,
            action="ENTRY_SUBMITTED",
            reason_code="SECOND_ENTRY_SUBMITTED",
            failure_reason="-",
            previous_state=current_state,
            current_state=transition.current_state,
            state_transition_reason=transition.reason_code,
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
            refreshed_available_usdt=None,
        )

    if gateway_result.reason_code != "INSUFFICIENT_MARGIN":
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_CREATE_FAILED_KEEP_STATE",
            failure_reason=gateway_result.reason_code,
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
            refreshed_available_usdt=None,
        )

    if refresh_available_usdt is None:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_INSUFFICIENT_MARGIN_SKIP_KEEP_STATE",
            failure_reason="no available balance refresher",
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
            refreshed_available_usdt=None,
        )

    try:
        refreshed_available = float(refresh_available_usdt())
    except Exception:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_REFRESH_AVAILABLE_FAILED_KEEP_STATE",
            failure_reason="available balance refresh failed",
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=budget_result.budget_usdt,
            raw_quantity=quantity_result.quantity,
            refreshed_available_usdt=None,
        )
    refreshed_budget = compute_second_entry_budget(
        refreshed_available,
        margin_buffer_pct=margin_buffer_pct,
        entry_mode=normalized_mode,
    )
    if not refreshed_budget.ok:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_REFRESH_BUDGET_REJECTED_KEEP_STATE",
            failure_reason=refreshed_budget.reason_code,
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=None,
            raw_quantity=None,
            refreshed_available_usdt=refreshed_available,
        )

    refreshed_quantity = compute_entry_quantity(
        budget_usdt=float(refreshed_budget.budget_usdt),
        target_price=second_target_price,
    )
    if not refreshed_quantity.ok:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_REFRESH_QUANTITY_REJECTED_KEEP_STATE",
            failure_reason=refreshed_quantity.reason_code,
            gateway_attempts=gateway_result.attempts,
            gateway_reason_code=gateway_result.reason_code,
            budget_usdt=refreshed_budget.budget_usdt,
            raw_quantity=None,
            refreshed_available_usdt=refreshed_available,
        )

    refreshed_request = OrderCreateRequest(
        symbol=symbol,
        side="SELL",
        order_type=order_type,  # type: ignore[arg-type]
        purpose="ENTRY",
        quantity=refreshed_quantity.quantity,
        price=second_target_price,
        stop_price=_resolve_entry_trigger_price(
            side="SELL",
            order_type=order_type,
            target_price=float(second_target_price),
            tick_size=float(filter_rules.tick_size),
        ),
        reference_price=second_target_price,
        new_client_order_id=new_client_order_id,
    )
    refreshed_gateway_result = create_order_with_retry(
        refreshed_request,
        filter_rules=filter_rules,
        position_mode=position_mode,
        call=create_call,
        retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
    )
    if not refreshed_gateway_result.success:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_MARGIN_REFRESH_RETRY_FAILED_KEEP_STATE",
            failure_reason=refreshed_gateway_result.reason_code,
            gateway_attempts=gateway_result.attempts + refreshed_gateway_result.attempts,
            gateway_reason_code=refreshed_gateway_result.reason_code,
            budget_usdt=refreshed_budget.budget_usdt,
            raw_quantity=refreshed_quantity.quantity,
            refreshed_available_usdt=refreshed_available,
        )

    transition = apply_symbol_event(current_state, "SUBMIT_SECOND_ENTRY_ORDER")
    if not transition.accepted:
        return _skip_second_entry_result(
            current_state=current_state,
            reason_code="SECOND_ENTRY_REFRESH_STATE_TRANSITION_REJECTED_KEEP_STATE",
            failure_reason=transition.reason_code,
            gateway_attempts=gateway_result.attempts + refreshed_gateway_result.attempts,
            gateway_reason_code=refreshed_gateway_result.reason_code,
            budget_usdt=refreshed_budget.budget_usdt,
            raw_quantity=refreshed_quantity.quantity,
            refreshed_available_usdt=refreshed_available,
        )
    return EntryPipelineResult(
        phase="SECOND_ENTRY",
        success=True,
        action="ENTRY_SUBMITTED",
        reason_code="SECOND_ENTRY_SUBMITTED_AFTER_MARGIN_REFRESH",
        failure_reason="-",
        previous_state=current_state,
        current_state=transition.current_state,
        state_transition_reason=transition.reason_code,
        gateway_attempts=gateway_result.attempts + refreshed_gateway_result.attempts,
        gateway_reason_code=refreshed_gateway_result.reason_code,
        budget_usdt=refreshed_budget.budget_usdt,
        raw_quantity=refreshed_quantity.quantity,
        refreshed_available_usdt=refreshed_available,
    )


def compute_first_entry_budget_with_logging(
    wallet_balance_usdt: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
) -> EntryBudgetResult:
    normalized_mode = _normalize_entry_mode_token(entry_mode)
    mode_multiplier = _resolve_first_entry_budget_multiplier(normalized_mode)
    result = compute_first_entry_budget(
        wallet_balance_usdt,
        entry_mode=normalized_mode,
    )
    log_structured_event(
        StructuredLogEvent(
            component="entry_pipeline",
            event="compute_first_entry_budget",
            input_data=(
                f"wallet_balance_usdt={wallet_balance_usdt} "
                f"entry_mode={normalized_mode}"
            ),
            decision="wallet_balance_times_50pct_then_apply_entry_mode_multiplier",
            result="ready" if result.ok else "rejected",
            state_before="budget_pending",
            state_after="budget_ready" if result.ok else "budget_rejected",
            failure_reason=result.reason_code if not result.ok else "-",
        ),
        reason_code=result.reason_code,
        budget_usdt=result.budget_usdt if result.budget_usdt is not None else "-",
        entry_mode=normalized_mode,
        mode_multiplier=mode_multiplier,
    )
    return result


def compute_second_entry_budget_with_logging(
    available_usdt: float,
    *,
    margin_buffer_pct: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
) -> EntryBudgetResult:
    normalized_mode = _normalize_entry_mode_token(entry_mode)
    mode_multiplier = _resolve_second_entry_budget_multiplier(normalized_mode)
    result = compute_second_entry_budget(
        available_usdt,
        margin_buffer_pct=margin_buffer_pct,
        entry_mode=normalized_mode,
    )
    log_structured_event(
        StructuredLogEvent(
            component="entry_pipeline",
            event="compute_second_entry_budget",
            input_data=(
                f"available_usdt={available_usdt} margin_buffer_pct={margin_buffer_pct} "
                f"entry_mode={normalized_mode}"
            ),
            decision="available_balance_apply_margin_buffer_then_apply_entry_mode_multiplier",
            result="ready" if result.ok else "rejected",
            state_before="budget_pending",
            state_after="budget_ready" if result.ok else "budget_rejected",
            failure_reason=result.reason_code if not result.ok else "-",
        ),
        reason_code=result.reason_code,
        budget_usdt=result.budget_usdt if result.budget_usdt is not None else "-",
        entry_mode=normalized_mode,
        mode_multiplier=mode_multiplier,
    )
    return result


def run_first_entry_pipeline_with_logging(
    *,
    current_state: SymbolState,
    symbol: str,
    target_price: float,
    wallet_balance_usdt: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    create_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    new_client_order_id: Optional[str] = None,
    reference_mark_price: Optional[float] = None,
    loop_label: str = "loop",
) -> EntryPipelineResult:
    normalized_mode = _normalize_entry_mode_token(entry_mode)
    mode_multiplier = _resolve_first_entry_budget_multiplier(normalized_mode)
    result = run_first_entry_pipeline(
        current_state=current_state,
        symbol=symbol,
        target_price=target_price,
        wallet_balance_usdt=wallet_balance_usdt,
        entry_mode=normalized_mode,
        filter_rules=filter_rules,
        position_mode=position_mode,
        create_call=create_call,
        retry_policy=retry_policy,
        new_client_order_id=new_client_order_id,
        reference_mark_price=reference_mark_price,
    )
    log_structured_event(
        StructuredLogEvent(
            component="entry_pipeline",
            event="run_first_entry_pipeline",
            input_data=(
                f"symbol={_normalize(symbol)} target_price={target_price} "
                f"wallet_balance_usdt={wallet_balance_usdt} entry_mode={normalized_mode} "
                f"state={current_state}"
            ),
            decision="build_first_entry_order_and_apply_failure_policy",
            result="submitted" if result.success else "failed",
            state_before=result.previous_state,
            state_after=result.current_state,
            failure_reason=result.reason_code if not result.success else "-",
        ),
        loop_label=loop_label,
        action=result.action,
        reason_code=result.reason_code,
        gateway_reason_code=result.gateway_reason_code,
        gateway_attempts=result.gateway_attempts,
        budget_usdt=result.budget_usdt if result.budget_usdt is not None else "-",
        raw_quantity=result.raw_quantity if result.raw_quantity is not None else "-",
        entry_mode=normalized_mode,
        mode_multiplier=mode_multiplier,
        reference_mark_price=reference_mark_price if reference_mark_price is not None else "-",
    )
    return result


def run_second_entry_pipeline_with_logging(
    *,
    current_state: SymbolState,
    symbol: str,
    second_target_price: float,
    available_usdt: float,
    margin_buffer_pct: float,
    entry_mode: str = DEFAULT_ENTRY_MODE,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    create_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    refresh_available_usdt: Optional[Callable[[], float]] = None,
    retry_policy: Optional[RetryPolicy] = None,
    new_client_order_id: Optional[str] = None,
    reference_mark_price: Optional[float] = None,
    loop_label: str = "loop",
) -> EntryPipelineResult:
    normalized_mode = _normalize_entry_mode_token(entry_mode)
    mode_multiplier = _resolve_second_entry_budget_multiplier(normalized_mode)
    result = run_second_entry_pipeline(
        current_state=current_state,
        symbol=symbol,
        second_target_price=second_target_price,
        available_usdt=available_usdt,
        margin_buffer_pct=margin_buffer_pct,
        entry_mode=normalized_mode,
        filter_rules=filter_rules,
        position_mode=position_mode,
        create_call=create_call,
        refresh_available_usdt=refresh_available_usdt,
        retry_policy=retry_policy,
        new_client_order_id=new_client_order_id,
        reference_mark_price=reference_mark_price,
    )
    log_structured_event(
        StructuredLogEvent(
            component="entry_pipeline",
            event="run_second_entry_pipeline",
            input_data=(
                f"symbol={_normalize(symbol)} second_target_price={second_target_price} "
                f"available_usdt={available_usdt} margin_buffer_pct={margin_buffer_pct} "
                f"entry_mode={normalized_mode} state={current_state}"
            ),
            decision="build_second_entry_order_and_apply_skip_policy",
            result="submitted" if result.success else "failed",
            state_before=result.previous_state,
            state_after=result.current_state,
            failure_reason=result.reason_code if not result.success else "-",
        ),
        loop_label=loop_label,
        action=result.action,
        reason_code=result.reason_code,
        gateway_reason_code=result.gateway_reason_code,
        gateway_attempts=result.gateway_attempts,
        budget_usdt=result.budget_usdt if result.budget_usdt is not None else "-",
        raw_quantity=result.raw_quantity if result.raw_quantity is not None else "-",
        entry_mode=normalized_mode,
        mode_multiplier=mode_multiplier,
        refreshed_available_usdt=(
            result.refreshed_available_usdt
            if result.refreshed_available_usdt is not None
            else "-"
        ),
        reference_mark_price=reference_mark_price if reference_mark_price is not None else "-",
    )
    return result
