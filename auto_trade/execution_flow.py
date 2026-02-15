from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Optional, Sequence

from .event_logging import StructuredLogEvent, log_structured_event
from .execution_models import (
    EntryFillSyncResult,
    ExecutionEntryPhase,
    ExecutionOrderStatus,
    ExitFiveSecondRuleDecision,
    ExitPartialFillTracker,
    ExitPartialFillUpdateResult,
    OcoCancelExecutionResult,
    OcoCancelPlanResult,
    PnlEvaluationResult,
    PnlBranch,
    RiskManagementPlanResult,
)
from .order_gateway import cancel_order_with_retry
from .order_gateway_models import GatewayCallResult, OrderCancelRequest, RetryPolicy
from .state_machine import apply_symbol_event
from .state_machine_models import SymbolState


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _is_positive_finite(value: float) -> bool:
    return math.isfinite(float(value)) and float(value) > 0.0


def evaluate_pnl_branch(
    *,
    avg_entry_price: float,
    mark_price: float,
) -> PnlEvaluationResult:
    if not _is_positive_finite(avg_entry_price):
        return PnlEvaluationResult(
            ok=False,
            roi_pct=None,
            branch="PNL_UNAVAILABLE",
            reason_code="INVALID_AVG_ENTRY_PRICE",
            failure_reason="avg_entry_price must be positive finite",
        )
    if not _is_positive_finite(mark_price):
        return PnlEvaluationResult(
            ok=False,
            roi_pct=None,
            branch="PNL_UNAVAILABLE",
            reason_code="INVALID_MARK_PRICE",
            failure_reason="mark_price must be positive finite",
        )

    roi_pct = (float(avg_entry_price) - float(mark_price)) / float(avg_entry_price) * 100.0
    if roi_pct < 0.0:
        branch: PnlBranch = "PNL_NEGATIVE"
    elif roi_pct == 0.0:
        branch = "PNL_ZERO"
    else:
        branch = "PNL_POSITIVE"
    return PnlEvaluationResult(
        ok=True,
        roi_pct=roi_pct,
        branch=branch,
        reason_code="PNL_BRANCH_READY",
        failure_reason="-",
    )


def _entry_sync_no_change(
    *,
    phase: ExecutionEntryPhase,
    order_status: ExecutionOrderStatus,
    current_state: SymbolState,
    reason_code: str,
    keep_entry_order: bool = False,
    activate_tp_monitor: bool = False,
    start_second_entry_monitor: bool = False,
    switch_to_phase2_breakeven_only: bool = False,
    submit_mdd_stop: bool = False,
) -> EntryFillSyncResult:
    return EntryFillSyncResult(
        phase=phase,
        order_status=order_status,
        previous_state=current_state,
        current_state=current_state,
        changed=False,
        reason_code=reason_code,
        keep_entry_order=keep_entry_order,
        activate_tp_monitor=activate_tp_monitor,
        start_second_entry_monitor=start_second_entry_monitor,
        switch_to_phase2_breakeven_only=switch_to_phase2_breakeven_only,
        submit_mdd_stop=submit_mdd_stop,
    )


def _entry_sync_from_transition(
    *,
    phase: ExecutionEntryPhase,
    order_status: ExecutionOrderStatus,
    previous_state: SymbolState,
    symbol_event: str,
    reason_code: str,
    keep_entry_order: bool = False,
    activate_tp_monitor: bool = False,
    start_second_entry_monitor: bool = False,
    switch_to_phase2_breakeven_only: bool = False,
    submit_mdd_stop: bool = False,
) -> EntryFillSyncResult:
    transition = apply_symbol_event(previous_state, symbol_event)  # type: ignore[arg-type]
    if not transition.accepted:
        return _entry_sync_no_change(
            phase=phase,
            order_status=order_status,
            current_state=previous_state,
            reason_code=f"{reason_code}_TRANSITION_REJECTED_{transition.reason_code}",
            keep_entry_order=keep_entry_order,
            activate_tp_monitor=activate_tp_monitor,
            start_second_entry_monitor=start_second_entry_monitor,
            switch_to_phase2_breakeven_only=switch_to_phase2_breakeven_only,
            submit_mdd_stop=submit_mdd_stop,
        )
    return EntryFillSyncResult(
        phase=phase,
        order_status=order_status,
        previous_state=previous_state,
        current_state=transition.current_state,
        changed=transition.changed,
        reason_code=reason_code,
        keep_entry_order=keep_entry_order,
        activate_tp_monitor=activate_tp_monitor,
        start_second_entry_monitor=start_second_entry_monitor,
        switch_to_phase2_breakeven_only=switch_to_phase2_breakeven_only,
        submit_mdd_stop=submit_mdd_stop,
    )


def sync_entry_fill_state(
    current_state: SymbolState,
    *,
    phase: ExecutionEntryPhase,
    order_status: ExecutionOrderStatus,
    has_position: bool = False,
) -> EntryFillSyncResult:
    if phase == "FIRST_ENTRY":
        if order_status == "PARTIALLY_FILLED":
            return _entry_sync_from_transition(
                phase=phase,
                order_status=order_status,
                previous_state=current_state,
                symbol_event="PARTIAL_FILL",
                reason_code="FIRST_ENTRY_PARTIAL_FILLED_SYNC",
                keep_entry_order=True,
                activate_tp_monitor=True,
            )
        if order_status == "FILLED":
            return _entry_sync_from_transition(
                phase=phase,
                order_status=order_status,
                previous_state=current_state,
                symbol_event="FIRST_ENTRY_FILLED",
                reason_code="FIRST_ENTRY_FILLED_SYNC",
                activate_tp_monitor=True,
                start_second_entry_monitor=True,
            )
        if order_status in ("CANCELED", "EXPIRED") and not has_position:
            return _entry_sync_from_transition(
                phase=phase,
                order_status=order_status,
                previous_state=current_state,
                symbol_event="CANCEL_ENTRY_NO_POSITION",
                reason_code="FIRST_ENTRY_CANCELED_NO_POSITION_SYNC",
            )
        return _entry_sync_no_change(
            phase=phase,
            order_status=order_status,
            current_state=current_state,
            reason_code="FIRST_ENTRY_STATUS_NO_TRANSITION",
            keep_entry_order=current_state == "ENTRY_ORDER",
        )

    # SECOND_ENTRY phase
    if order_status == "PARTIALLY_FILLED":
        if current_state == "PHASE2":
            return _entry_sync_no_change(
                phase=phase,
                order_status=order_status,
                current_state=current_state,
                reason_code="SECOND_ENTRY_PARTIAL_ALREADY_PHASE2",
                switch_to_phase2_breakeven_only=True,
            )
        return _entry_sync_from_transition(
            phase=phase,
            order_status=order_status,
            previous_state=current_state,
            symbol_event="SECOND_ENTRY_PARTIAL_OR_FILLED",
            reason_code="SECOND_ENTRY_PARTIAL_FILLED_SYNC",
            switch_to_phase2_breakeven_only=True,
        )

    if order_status == "FILLED":
        if current_state == "PHASE2":
            return _entry_sync_no_change(
                phase=phase,
                order_status=order_status,
                current_state=current_state,
                reason_code="SECOND_ENTRY_FILLED_PHASE2_CONFIRM",
                switch_to_phase2_breakeven_only=True,
                submit_mdd_stop=True,
            )
        return _entry_sync_from_transition(
            phase=phase,
            order_status=order_status,
            previous_state=current_state,
            symbol_event="SECOND_ENTRY_PARTIAL_OR_FILLED",
            reason_code="SECOND_ENTRY_FILLED_SYNC",
            switch_to_phase2_breakeven_only=True,
            submit_mdd_stop=True,
        )

    return _entry_sync_no_change(
        phase=phase,
        order_status=order_status,
        current_state=current_state,
        reason_code="SECOND_ENTRY_STATUS_NO_TRANSITION",
        switch_to_phase2_breakeven_only=current_state == "PHASE2",
    )


def plan_risk_management_action(
    *,
    current_state: SymbolState,
    symbol_matches_active: bool,
    has_position: bool,
    has_open_entry_order: bool,
    pnl_branch: PnlBranch,
    has_tp_order: bool,
    second_entry_fully_filled: bool,
) -> RiskManagementPlanResult:
    if not symbol_matches_active:
        return RiskManagementPlanResult(
            actionable=False,
            action_code="IGNORE_DIFFERENT_SYMBOL",
            reason_code="RISK_SYMBOL_MISMATCH",
            cancel_entry_orders=False,
            submit_market_exit=False,
            submit_breakeven_stop_market=False,
            keep_tp_order=False,
            create_tp_limit_once=False,
            keep_phase2_breakeven_limit=False,
            keep_existing_mdd_stop=False,
            reset_state=False,
        )

    if current_state == "MONITORING":
        return RiskManagementPlanResult(
            actionable=True,
            action_code="RESET_MONITORING",
            reason_code="RISK_MONITORING_RESET",
            cancel_entry_orders=False,
            submit_market_exit=False,
            submit_breakeven_stop_market=False,
            keep_tp_order=False,
            create_tp_limit_once=False,
            keep_phase2_breakeven_limit=False,
            keep_existing_mdd_stop=False,
            reset_state=True,
        )

    if current_state == "ENTRY_ORDER" and not has_position:
        return RiskManagementPlanResult(
            actionable=True,
            action_code="CANCEL_ENTRY_AND_RESET",
            reason_code="RISK_ENTRY_ORDER_NO_POSITION",
            cancel_entry_orders=True,
            submit_market_exit=False,
            submit_breakeven_stop_market=False,
            keep_tp_order=False,
            create_tp_limit_once=False,
            keep_phase2_breakeven_limit=False,
            keep_existing_mdd_stop=False,
            reset_state=True,
        )

    if not has_position:
        return RiskManagementPlanResult(
            actionable=False,
            action_code="IGNORE_NO_POSITION",
            reason_code="RISK_NO_POSITION",
            cancel_entry_orders=False,
            submit_market_exit=False,
            submit_breakeven_stop_market=False,
            keep_tp_order=False,
            create_tp_limit_once=False,
            keep_phase2_breakeven_limit=False,
            keep_existing_mdd_stop=False,
            reset_state=False,
        )

    if pnl_branch in ("PNL_NEGATIVE", "PNL_ZERO"):
        return RiskManagementPlanResult(
            actionable=True,
            action_code="MARKET_EXIT_PRIORITY",
            reason_code="RISK_PNL_LE_ZERO_MARKET_EXIT",
            cancel_entry_orders=has_open_entry_order,
            submit_market_exit=True,
            submit_breakeven_stop_market=False,
            keep_tp_order=False,
            create_tp_limit_once=False,
            keep_phase2_breakeven_limit=False,
            keep_existing_mdd_stop=False,
            reset_state=False,
        )

    if pnl_branch == "PNL_POSITIVE":
        if current_state == "PHASE2":
            return RiskManagementPlanResult(
                actionable=True,
                action_code="PHASE2_KEEP_BREAKEVEN_LIMIT",
                reason_code="RISK_PHASE2_PNL_POSITIVE",
                cancel_entry_orders=False,
                submit_market_exit=False,
                submit_breakeven_stop_market=False,
                keep_tp_order=False,
                create_tp_limit_once=False,
                keep_phase2_breakeven_limit=True,
                keep_existing_mdd_stop=second_entry_fully_filled,
                reset_state=False,
            )

        return RiskManagementPlanResult(
            actionable=True,
            action_code="PHASE1_STOP_AND_TP_POLICY",
            reason_code="RISK_PHASE1_PNL_POSITIVE",
            cancel_entry_orders=has_open_entry_order,
            submit_market_exit=False,
            submit_breakeven_stop_market=True,
            keep_tp_order=has_tp_order,
            # For positive-PNL risk signals, TP should be armed by phase1 trigger-order logic
            # (0.1% buffer + target price) instead of immediate limit submission.
            create_tp_limit_once=False,
            keep_phase2_breakeven_limit=False,
            keep_existing_mdd_stop=False,
            reset_state=False,
        )

    return RiskManagementPlanResult(
        actionable=False,
        action_code="IGNORE_PNL_UNAVAILABLE",
        reason_code="RISK_PNL_UNAVAILABLE",
        cancel_entry_orders=False,
        submit_market_exit=False,
        submit_breakeven_stop_market=False,
        keep_tp_order=False,
        create_tp_limit_once=False,
        keep_phase2_breakeven_limit=False,
        keep_existing_mdd_stop=False,
        reset_state=False,
    )


def plan_oco_mutual_cancel(
    *,
    filled_order_id: int,
    open_exit_order_ids: Sequence[int],
) -> OcoCancelPlanResult:
    targets = [int(order_id) for order_id in open_exit_order_ids if int(order_id) != int(filled_order_id)]
    if not targets:
        return OcoCancelPlanResult(
            has_targets=False,
            reason_code="OCO_NO_REMAINING_ORDERS",
            cancel_target_order_ids=[],
        )
    return OcoCancelPlanResult(
        has_targets=True,
        reason_code="OCO_CANCEL_TARGETS_READY",
        cancel_target_order_ids=targets,
    )


def execute_oco_mutual_cancel(
    *,
    symbol: str,
    cancel_order_ids: Sequence[int],
    cancel_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
) -> OcoCancelExecutionResult:
    failed: list[int] = []
    attempted = 0
    policy = retry_policy if retry_policy is not None else RetryPolicy(max_attempts=3)

    for order_id in cancel_order_ids:
        attempted += 1
        result = cancel_order_with_retry(
            OrderCancelRequest(symbol=symbol, order_id=int(order_id)),
            call=cancel_call,
            retry_policy=policy,
        )
        if not result.success:
            failed.append(int(order_id))

    if failed:
        return OcoCancelExecutionResult(
            success=False,
            reason_code="OCO_CANCEL_FAILED_LOCK",
            attempted_count=attempted,
            failed_order_ids=failed,
            lock_new_orders=True,
        )
    return OcoCancelExecutionResult(
        success=True,
        reason_code="OCO_CANCEL_COMPLETED",
        attempted_count=attempted,
        failed_order_ids=[],
        lock_new_orders=False,
    )


def update_exit_partial_fill_tracker(
    tracker: ExitPartialFillTracker,
    *,
    is_exit_order: bool,
    order_id: int,
    order_status: ExecutionOrderStatus,
    executed_qty: float,
    updated_at: int,
) -> ExitPartialFillUpdateResult:
    if not is_exit_order:
        return ExitPartialFillUpdateResult(
            previous=tracker,
            current=tracker,
            changed=False,
            reason_code="NOT_EXIT_ORDER",
        )

    if int(updated_at) <= 0:
        return ExitPartialFillUpdateResult(
            previous=tracker,
            current=tracker,
            changed=False,
            reason_code="INVALID_UPDATE_TIME",
        )

    qty = float(executed_qty) if math.isfinite(float(executed_qty)) and float(executed_qty) >= 0 else 0.0

    if order_status == "PARTIALLY_FILLED":
        if not tracker.active or tracker.order_id != int(order_id):
            partial_started_at = int(updated_at)
        elif qty > tracker.last_executed_qty:
            partial_started_at = int(updated_at)
        else:
            partial_started_at = tracker.partial_started_at
        current = ExitPartialFillTracker(
            active=True,
            order_id=int(order_id),
            partial_started_at=partial_started_at,
            last_update_at=int(updated_at),
            last_executed_qty=qty,
        )
        return ExitPartialFillUpdateResult(
            previous=tracker,
            current=current,
            changed=current != tracker,
            reason_code="EXIT_PARTIAL_TRACK_UPDATED",
        )

    if order_status in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
        current = ExitPartialFillTracker()
        return ExitPartialFillUpdateResult(
            previous=tracker,
            current=current,
            changed=current != tracker,
            reason_code="EXIT_PARTIAL_TRACK_CLEARED",
        )

    return ExitPartialFillUpdateResult(
        previous=tracker,
        current=tracker,
        changed=False,
        reason_code="EXIT_PARTIAL_TRACK_NO_CHANGE",
    )


def evaluate_exit_five_second_rule(
    tracker: ExitPartialFillTracker,
    *,
    is_exit_order: bool,
    now: int,
    stall_seconds: int = 5,
    risk_market_exit_in_same_loop: bool = False,
) -> ExitFiveSecondRuleDecision:
    threshold = max(1, int(stall_seconds))
    if not is_exit_order:
        return ExitFiveSecondRuleDecision(
            should_force_market_exit=False,
            reason_code="NOT_EXIT_ORDER",
            remaining_seconds=0,
        )
    if risk_market_exit_in_same_loop:
        return ExitFiveSecondRuleDecision(
            should_force_market_exit=False,
            reason_code="RISK_MARKET_EXIT_PRIORITY",
            remaining_seconds=0,
        )
    if not tracker.active:
        return ExitFiveSecondRuleDecision(
            should_force_market_exit=False,
            reason_code="EXIT_PARTIAL_TRACK_INACTIVE",
            remaining_seconds=0,
        )
    elapsed = max(0, int(now) - int(tracker.partial_started_at))
    remaining = max(0, threshold - elapsed)
    if elapsed >= threshold:
        return ExitFiveSecondRuleDecision(
            should_force_market_exit=True,
            reason_code="EXIT_PARTIAL_STALLED_5S",
            remaining_seconds=0,
        )
    return ExitFiveSecondRuleDecision(
        should_force_market_exit=False,
        reason_code="EXIT_PARTIAL_WAITING",
        remaining_seconds=remaining,
    )


def evaluate_pnl_branch_with_logging(
    *,
    avg_entry_price: float,
    mark_price: float,
) -> PnlEvaluationResult:
    result = evaluate_pnl_branch(
        avg_entry_price=avg_entry_price,
        mark_price=mark_price,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="evaluate_pnl_branch",
            input_data=f"avg_entry_price={avg_entry_price} mark_price={mark_price}",
            decision="compute_short_roi_and_classify_branch",
            result=result.branch if result.ok else "unavailable",
            state_before="pnl_pending",
            state_after="pnl_ready" if result.ok else "pnl_unavailable",
            failure_reason=result.reason_code if not result.ok else "-",
        ),
        reason_code=result.reason_code,
        roi_pct=result.roi_pct if result.roi_pct is not None else "-",
    )
    return result


def sync_entry_fill_state_with_logging(
    current_state: SymbolState,
    *,
    phase: ExecutionEntryPhase,
    order_status: ExecutionOrderStatus,
    has_position: bool = False,
    loop_label: str = "loop",
) -> EntryFillSyncResult:
    result = sync_entry_fill_state(
        current_state,
        phase=phase,
        order_status=order_status,
        has_position=has_position,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="sync_entry_fill_state",
            input_data=(
                f"phase={phase} order_status={order_status} current_state={current_state} "
                f"has_position={has_position}"
            ),
            decision="apply_fill_state_transition_rules",
            result=result.reason_code,
            state_before=result.previous_state,
            state_after=result.current_state,
            failure_reason="-",
        ),
        loop_label=loop_label,
        changed=result.changed,
        activate_tp_monitor=result.activate_tp_monitor,
        start_second_entry_monitor=result.start_second_entry_monitor,
        switch_to_phase2_breakeven_only=result.switch_to_phase2_breakeven_only,
        submit_mdd_stop=result.submit_mdd_stop,
    )
    return result


def plan_risk_management_action_with_logging(
    *,
    current_state: SymbolState,
    symbol_matches_active: bool,
    has_position: bool,
    has_open_entry_order: bool,
    pnl_branch: PnlBranch,
    has_tp_order: bool,
    second_entry_fully_filled: bool,
    loop_label: str = "loop",
) -> RiskManagementPlanResult:
    result = plan_risk_management_action(
        current_state=current_state,
        symbol_matches_active=symbol_matches_active,
        has_position=has_position,
        has_open_entry_order=has_open_entry_order,
        pnl_branch=pnl_branch,
        has_tp_order=has_tp_order,
        second_entry_fully_filled=second_entry_fully_filled,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="plan_risk_management_action",
            input_data=(
                f"state={current_state} symbol_matches_active={symbol_matches_active} "
                f"has_position={has_position} has_open_entry_order={has_open_entry_order} "
                f"pnl_branch={pnl_branch} has_tp_order={has_tp_order} "
                f"second_entry_fully_filled={second_entry_fully_filled}"
            ),
            decision="apply_risk_management_priority_rules",
            result=result.action_code,
            state_before=current_state,
            state_after=current_state if not result.reset_state else "IDLE",
            failure_reason="-" if result.actionable else result.reason_code,
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        submit_market_exit=result.submit_market_exit,
        submit_breakeven_stop_market=result.submit_breakeven_stop_market,
        create_tp_limit_once=result.create_tp_limit_once,
    )
    return result


def plan_oco_mutual_cancel_with_logging(
    *,
    filled_order_id: int,
    open_exit_order_ids: Sequence[int],
    loop_label: str = "loop",
) -> OcoCancelPlanResult:
    result = plan_oco_mutual_cancel(
        filled_order_id=filled_order_id,
        open_exit_order_ids=open_exit_order_ids,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="plan_oco_mutual_cancel",
            input_data=(
                f"filled_order_id={filled_order_id} "
                f"open_exit_order_count={len(open_exit_order_ids)}"
            ),
            decision="exclude_filled_order_and_prepare_cancel_targets",
            result="targets_ready" if result.has_targets else "no_remaining",
            state_before="oco_pending",
            state_after="oco_planned",
            failure_reason="-" if result.has_targets else result.reason_code,
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        cancel_target_count=len(result.cancel_target_order_ids),
    )
    return result


def execute_oco_mutual_cancel_with_logging(
    *,
    symbol: str,
    cancel_order_ids: Sequence[int],
    cancel_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    loop_label: str = "loop",
) -> OcoCancelExecutionResult:
    result = execute_oco_mutual_cancel(
        symbol=symbol,
        cancel_order_ids=cancel_order_ids,
        cancel_call=cancel_call,
        retry_policy=retry_policy,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="execute_oco_mutual_cancel",
            input_data=(
                f"symbol={_normalize(symbol)} cancel_target_count={len(cancel_order_ids)} "
                f"retry_max_attempts={(retry_policy.max_attempts if retry_policy is not None else 3)}"
            ),
            decision="cancel_remaining_exit_orders_with_retry",
            result="success" if result.success else "failed",
            state_before="oco_cancel_pending",
            state_after="oco_cancel_done",
            failure_reason=result.reason_code if not result.success else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        attempted_count=result.attempted_count,
        failed_count=len(result.failed_order_ids),
        lock_new_orders=result.lock_new_orders,
    )
    return result


def update_exit_partial_fill_tracker_with_logging(
    tracker: ExitPartialFillTracker,
    *,
    is_exit_order: bool,
    order_id: int,
    order_status: ExecutionOrderStatus,
    executed_qty: float,
    updated_at: int,
    loop_label: str = "loop",
) -> ExitPartialFillUpdateResult:
    result = update_exit_partial_fill_tracker(
        tracker,
        is_exit_order=is_exit_order,
        order_id=order_id,
        order_status=order_status,
        executed_qty=executed_qty,
        updated_at=updated_at,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="update_exit_partial_fill_tracker",
            input_data=(
                f"is_exit_order={is_exit_order} order_id={order_id} "
                f"order_status={order_status} executed_qty={executed_qty} updated_at={updated_at}"
            ),
            decision="update_or_clear_exit_partial_fill_tracker",
            result=result.reason_code,
            state_before="tracker_active" if tracker.active else "tracker_idle",
            state_after="tracker_active" if result.current.active else "tracker_idle",
            failure_reason="-",
        ),
        loop_label=loop_label,
        changed=result.changed,
        partial_started_at=result.current.partial_started_at,
        last_executed_qty=result.current.last_executed_qty,
    )
    return result


def evaluate_exit_five_second_rule_with_logging(
    tracker: ExitPartialFillTracker,
    *,
    is_exit_order: bool,
    now: int,
    stall_seconds: int = 5,
    risk_market_exit_in_same_loop: bool = False,
    loop_label: str = "loop",
) -> ExitFiveSecondRuleDecision:
    result = evaluate_exit_five_second_rule(
        tracker,
        is_exit_order=is_exit_order,
        now=now,
        stall_seconds=stall_seconds,
        risk_market_exit_in_same_loop=risk_market_exit_in_same_loop,
    )
    log_structured_event(
        StructuredLogEvent(
            component="execution_flow",
            event="evaluate_exit_five_second_rule",
            input_data=(
                f"is_exit_order={is_exit_order} now={now} stall_seconds={stall_seconds} "
                f"risk_market_exit_in_same_loop={risk_market_exit_in_same_loop}"
            ),
            decision="apply_exit_partial_stall_5s_rule",
            result="force_market_exit" if result.should_force_market_exit else "wait_or_skip",
            state_before="rule_check",
            state_after="rule_done",
            failure_reason=result.reason_code if not result.should_force_market_exit else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        remaining_seconds=result.remaining_seconds,
    )
    return result
