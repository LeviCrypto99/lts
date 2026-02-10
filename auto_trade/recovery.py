from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Mapping, Optional, Sequence

from .event_logging import StructuredLogEvent, log_structured_event
from .recovery_models import (
    ExchangeSnapshot,
    ExitReconcileExecutionResult,
    ExitReconcilePlan,
    PersistentRecoveryState,
    RecoveryRunResult,
    RecoveryRuntimeState,
    RecoverySnapshotResult,
    RecoveryTransitionResult,
)
from .state_machine import update_account_activity
from .state_machine_models import GlobalState, GlobalTransitionResult


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _state_label(state: RecoveryRuntimeState) -> str:
    return (
        f"recovery_locked={state.recovery_locked}/paused={state.signal_loop_paused}/"
        f"running={state.signal_loop_running}/persisted={state.persisted_loaded}/"
        f"snapshot={state.snapshot_loaded}/monitor_queue_cleared={state.monitoring_queue_cleared}/"
        f"entry_locked={state.global_state.entry_locked}/safety_locked={state.global_state.safety_locked}"
    )


def _empty_global_transition(state: GlobalState) -> GlobalTransitionResult:
    return GlobalTransitionResult(
        previous=state,
        current=state,
        changed=False,
        reason_code="NO_CHANGE",
    )


def _is_nonzero_position(item: Mapping[str, Any]) -> bool:
    try:
        qty = float(item.get("positionAmt", 0.0))
    except (TypeError, ValueError):
        return False
    return abs(qty) > 1e-12


def _position_symbols(positions: Sequence[Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for item in positions:
        symbol = _normalize_symbol(item.get("symbol"))
        if symbol and _is_nonzero_position(item):
            result.add(symbol)
    return result


def _open_order_symbols(open_orders: Sequence[Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for item in open_orders:
        symbol = _normalize_symbol(item.get("symbol"))
        if symbol:
            result.add(symbol)
    return result


def _symbol_state_from_snapshot(*, has_any_position: bool, has_any_open_order: bool) -> str:
    if has_any_position:
        return "PHASE1"
    if has_any_open_order:
        return "ENTRY_ORDER"
    return "IDLE"


def begin_recovery(state: RecoveryRuntimeState) -> RecoveryTransitionResult:
    current = replace(
        state,
        recovery_locked=True,
        signal_loop_paused=True,
        signal_loop_running=False,
        persisted_loaded=False,
        snapshot_loaded=False,
        monitoring_queue_cleared=False,
    )
    changed = current != state
    return RecoveryTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code="RECOVERY_LOCK_ENABLED" if changed else "RECOVERY_LOCK_ALREADY_ENABLED",
        failure_reason="-" if changed else "NO_CHANGE",
    )


def restore_persisted_runtime(
    state: RecoveryRuntimeState,
    *,
    persisted: PersistentRecoveryState,
) -> RecoveryTransitionResult:
    current = replace(
        state,
        persisted_loaded=True,
        last_message_ids=dict(persisted.last_message_ids),
        cooldown_by_symbol=dict(persisted.cooldown_by_symbol),
        received_at_by_symbol=dict(persisted.received_at_by_symbol),
        message_id_by_symbol=dict(persisted.message_id_by_symbol),
    )
    changed = current != state
    return RecoveryTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code="RECOVERY_PERSISTED_STATE_RESTORED" if changed else "RECOVERY_PERSISTED_STATE_NO_CHANGE",
        failure_reason="-" if changed else "NO_CHANGE",
    )


def apply_exchange_snapshot(
    state: RecoveryRuntimeState,
    *,
    snapshot: ExchangeSnapshot,
) -> RecoverySnapshotResult:
    if int(snapshot.open_order_count) < 0:
        return RecoverySnapshotResult(
            previous=state,
            current=state,
            changed=False,
            reason_code="RECOVERY_SNAPSHOT_INVALID_OPEN_ORDER_COUNT",
            failure_reason="open_order_count must be >= 0",
            global_transition=_empty_global_transition(state.global_state),
        )

    if not snapshot.ok:
        return RecoverySnapshotResult(
            previous=state,
            current=state,
            changed=False,
            reason_code=f"RECOVERY_SNAPSHOT_FETCH_FAILED_{snapshot.reason_code}",
            failure_reason=snapshot.failure_reason or snapshot.reason_code,
            global_transition=_empty_global_transition(state.global_state),
        )

    has_any_open_order = int(snapshot.open_order_count) > 0
    global_transition = update_account_activity(
        state.global_state,
        has_any_position=bool(snapshot.has_any_position),
        has_any_open_order=has_any_open_order,
    )
    current = replace(
        state,
        snapshot_loaded=True,
        global_state=global_transition.current,
        position_mode=snapshot.position_mode,
        active_symbol_state=_symbol_state_from_snapshot(
            has_any_position=bool(snapshot.has_any_position),
            has_any_open_order=has_any_open_order,
        ),
    )
    changed = current != state
    return RecoverySnapshotResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code="RECOVERY_SNAPSHOT_APPLIED" if changed else "RECOVERY_SNAPSHOT_NO_CHANGE",
        failure_reason="-",
        global_transition=global_transition,
    )


def plan_exit_reconciliation(snapshot: ExchangeSnapshot) -> ExitReconcilePlan:
    if not snapshot.ok:
        return ExitReconcilePlan(
            action_code="NONE",
            reason_code="RECOVERY_PLAN_SKIPPED_SNAPSHOT_FAILED",
            cancel_symbols=[],
            register_symbols=[],
            require_exit_registration=False,
        )

    open_symbols = _open_order_symbols(snapshot.open_orders)
    position_symbols = _position_symbols(snapshot.positions)
    cancel_symbols = sorted(symbol for symbol in open_symbols if symbol not in position_symbols)
    register_symbols = sorted(symbol for symbol in position_symbols if symbol not in open_symbols)
    require_exit_registration = bool(register_symbols)

    if cancel_symbols and require_exit_registration:
        return ExitReconcilePlan(
            action_code="CANCEL_AND_REQUIRE_EXIT_REGISTRATION",
            reason_code="RECOVERY_RECONCILE_CANCEL_AND_REGISTER_EXIT",
            cancel_symbols=cancel_symbols,
            register_symbols=register_symbols,
            require_exit_registration=True,
        )
    if cancel_symbols:
        return ExitReconcilePlan(
            action_code="CANCEL_UNNEEDED_ORDERS",
            reason_code="RECOVERY_RECONCILE_CANCEL_UNNEEDED_ORDERS",
            cancel_symbols=cancel_symbols,
            register_symbols=[],
            require_exit_registration=False,
        )
    if require_exit_registration:
        return ExitReconcilePlan(
            action_code="REQUIRE_EXIT_REGISTRATION",
            reason_code="RECOVERY_RECONCILE_REQUIRE_EXIT_REGISTRATION",
            cancel_symbols=[],
            register_symbols=register_symbols,
            require_exit_registration=True,
        )
    return ExitReconcilePlan(
        action_code="NONE",
        reason_code="RECOVERY_RECONCILE_NO_ACTION",
        cancel_symbols=[],
        register_symbols=[],
        require_exit_registration=False,
    )


def clear_monitoring_queue(
    state: RecoveryRuntimeState,
    *,
    cleared_count: int,
) -> RecoveryTransitionResult:
    current = replace(
        state,
        monitoring_queue_cleared=True,
    )
    changed = current != state
    return RecoveryTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code="RECOVERY_MONITORING_QUEUE_CLEARED",
        failure_reason="-" if int(cleared_count) >= 0 else "INVALID_CLEARED_COUNT",
    )


def complete_recovery(
    state: RecoveryRuntimeState,
    *,
    price_source_ready: bool,
    reconciliation_ok: bool,
) -> RecoveryTransitionResult:
    pending_reason = "-"
    if not state.persisted_loaded:
        pending_reason = "RECOVERY_WAIT_PERSISTED_STATE"
    elif not state.snapshot_loaded:
        pending_reason = "RECOVERY_WAIT_EXCHANGE_SNAPSHOT"
    elif not reconciliation_ok:
        pending_reason = "RECOVERY_WAIT_RECONCILIATION"
    elif not state.monitoring_queue_cleared:
        pending_reason = "RECOVERY_WAIT_MONITOR_QUEUE_CLEAR"
    elif not price_source_ready:
        pending_reason = "RECOVERY_WAIT_PRICE_SOURCE_HEALTHY"

    if pending_reason != "-":
        current = replace(
            state,
            recovery_locked=True,
            signal_loop_paused=True,
            signal_loop_running=False,
        )
        changed = current != state
        return RecoveryTransitionResult(
            previous=state,
            current=current,
            changed=changed,
            reason_code=pending_reason,
            failure_reason=pending_reason,
        )

    current = replace(
        state,
        recovery_locked=False,
        signal_loop_paused=False,
        signal_loop_running=True,
    )
    changed = current != state
    return RecoveryTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code="RECOVERY_COMPLETED_SIGNAL_LOOP_RESUMED",
        failure_reason="-",
    )


def stop_signal_loop(state: RecoveryRuntimeState) -> RecoveryTransitionResult:
    current = replace(
        state,
        recovery_locked=False,
        signal_loop_paused=True,
        signal_loop_running=False,
    )
    changed = current != state
    return RecoveryTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code="UI_STOP_SIGNAL_LOOP",
        failure_reason="-" if changed else "NO_CHANGE",
    )


def _fail_run(
    *,
    reason_code: str,
    failure_reason: str,
    state: RecoveryRuntimeState,
    snapshot_reason_code: str,
    reconcile_plan_reason_code: str,
    reconcile_execution_reason_code: str,
) -> RecoveryRunResult:
    return RecoveryRunResult(
        success=False,
        reason_code=reason_code,
        failure_reason=failure_reason,
        state=state,
        snapshot_reason_code=snapshot_reason_code,
        reconcile_plan_reason_code=reconcile_plan_reason_code,
        reconcile_execution_reason_code=reconcile_execution_reason_code,
    )


def run_recovery_startup(
    state: RecoveryRuntimeState,
    *,
    load_persisted_state: Callable[[], PersistentRecoveryState],
    fetch_exchange_snapshot: Callable[[], ExchangeSnapshot],
    check_price_source_ready: Callable[[], bool],
    execute_exit_reconciliation: Optional[Callable[[ExitReconcilePlan], ExitReconcileExecutionResult]] = None,
    cleared_monitoring_queue_count: int = 0,
) -> RecoveryRunResult:
    current = begin_recovery(state).current
    snapshot_reason_code = "RECOVERY_SNAPSHOT_NOT_REQUESTED"
    reconcile_plan_reason_code = "RECOVERY_RECONCILE_NOT_PLANNED"
    reconcile_execution_reason_code = "RECOVERY_RECONCILE_NOT_EXECUTED"

    try:
        persisted = load_persisted_state()
    except Exception as exc:
        return _fail_run(
            reason_code="RECOVERY_PERSISTED_LOAD_EXCEPTION",
            failure_reason=f"{type(exc).__name__}",
            state=current,
            snapshot_reason_code=snapshot_reason_code,
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    if not isinstance(persisted, PersistentRecoveryState):
        return _fail_run(
            reason_code="RECOVERY_PERSISTED_LOAD_INVALID_TYPE",
            failure_reason=type(persisted).__name__,
            state=current,
            snapshot_reason_code=snapshot_reason_code,
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    current = restore_persisted_runtime(current, persisted=persisted).current

    try:
        snapshot = fetch_exchange_snapshot()
    except Exception as exc:
        return _fail_run(
            reason_code="RECOVERY_SNAPSHOT_FETCH_EXCEPTION",
            failure_reason=f"{type(exc).__name__}",
            state=current,
            snapshot_reason_code="RECOVERY_SNAPSHOT_FETCH_EXCEPTION",
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    if not isinstance(snapshot, ExchangeSnapshot):
        return _fail_run(
            reason_code="RECOVERY_SNAPSHOT_INVALID_TYPE",
            failure_reason=type(snapshot).__name__,
            state=current,
            snapshot_reason_code="RECOVERY_SNAPSHOT_INVALID_TYPE",
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    snapshot_result = apply_exchange_snapshot(current, snapshot=snapshot)
    current = snapshot_result.current
    snapshot_reason_code = snapshot_result.reason_code
    if snapshot_result.reason_code.startswith("RECOVERY_SNAPSHOT_FETCH_FAILED"):
        return _fail_run(
            reason_code=snapshot_result.reason_code,
            failure_reason=snapshot_result.failure_reason,
            state=current,
            snapshot_reason_code=snapshot_reason_code,
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    reconcile_plan = plan_exit_reconciliation(snapshot)
    reconcile_plan_reason_code = reconcile_plan.reason_code
    if reconcile_plan.has_action:
        if execute_exit_reconciliation is None:
            return _fail_run(
                reason_code="RECOVERY_RECONCILE_HANDLER_MISSING",
                failure_reason=reconcile_plan.action_code,
                state=current,
                snapshot_reason_code=snapshot_reason_code,
                reconcile_plan_reason_code=reconcile_plan_reason_code,
                reconcile_execution_reason_code=reconcile_execution_reason_code,
            )
        try:
            reconcile_execution = execute_exit_reconciliation(reconcile_plan)
        except Exception as exc:
            return _fail_run(
                reason_code="RECOVERY_RECONCILE_EXCEPTION",
                failure_reason=f"{type(exc).__name__}",
                state=current,
                snapshot_reason_code=snapshot_reason_code,
                reconcile_plan_reason_code=reconcile_plan_reason_code,
                reconcile_execution_reason_code="RECOVERY_RECONCILE_EXCEPTION",
            )
        reconcile_execution_reason_code = reconcile_execution.reason_code
        if not reconcile_execution.success:
            return _fail_run(
                reason_code="RECOVERY_RECONCILE_FAILED_KEEP_LOCK",
                failure_reason=reconcile_execution.failure_reason or reconcile_execution.reason_code,
                state=current,
                snapshot_reason_code=snapshot_reason_code,
                reconcile_plan_reason_code=reconcile_plan_reason_code,
                reconcile_execution_reason_code=reconcile_execution_reason_code,
            )
    else:
        reconcile_execution = ExitReconcileExecutionResult(
            success=True,
            reason_code="RECOVERY_RECONCILE_NO_ACTION",
            failure_reason="-",
            canceled_symbols=[],
        )
        reconcile_execution_reason_code = reconcile_execution.reason_code

    current = clear_monitoring_queue(
        current,
        cleared_count=cleared_monitoring_queue_count,
    ).current

    try:
        price_source_ready = bool(check_price_source_ready())
    except Exception as exc:
        return _fail_run(
            reason_code="RECOVERY_PRICE_SOURCE_CHECK_EXCEPTION",
            failure_reason=f"{type(exc).__name__}",
            state=current,
            snapshot_reason_code=snapshot_reason_code,
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    complete_result = complete_recovery(
        current,
        price_source_ready=price_source_ready,
        reconciliation_ok=reconcile_execution.success,
    )
    current = complete_result.current
    if current.recovery_locked:
        return _fail_run(
            reason_code=complete_result.reason_code,
            failure_reason=complete_result.failure_reason,
            state=current,
            snapshot_reason_code=snapshot_reason_code,
            reconcile_plan_reason_code=reconcile_plan_reason_code,
            reconcile_execution_reason_code=reconcile_execution_reason_code,
        )

    return RecoveryRunResult(
        success=True,
        reason_code=complete_result.reason_code,
        failure_reason="-",
        state=current,
        snapshot_reason_code=snapshot_reason_code,
        reconcile_plan_reason_code=reconcile_plan_reason_code,
        reconcile_execution_reason_code=reconcile_execution_reason_code,
    )


def begin_recovery_with_logging(
    state: RecoveryRuntimeState,
    *,
    loop_label: str = "loop",
) -> RecoveryTransitionResult:
    result = begin_recovery(state)
    log_structured_event(
        StructuredLogEvent(
            component="recovery",
            event="begin_recovery",
            input_data=f"state={_state_label(state)}",
            decision="enable_recovery_lock_and_pause_signal_loop",
            result=result.reason_code,
            state_before=_state_label(result.previous),
            state_after=_state_label(result.current),
            failure_reason=result.failure_reason,
        ),
        loop_label=loop_label,
        changed=result.changed,
    )
    return result


def apply_exchange_snapshot_with_logging(
    state: RecoveryRuntimeState,
    *,
    snapshot: ExchangeSnapshot,
    loop_label: str = "loop",
) -> RecoverySnapshotResult:
    result = apply_exchange_snapshot(
        state,
        snapshot=snapshot,
    )
    log_structured_event(
        StructuredLogEvent(
            component="recovery",
            event="apply_exchange_snapshot",
            input_data=(
                f"snapshot_ok={snapshot.ok} open_order_count={snapshot.open_order_count} "
                f"has_any_position={snapshot.has_any_position} position_mode={snapshot.position_mode}"
            ),
            decision="recompute_entry_lock_from_exchange_snapshot",
            result=result.reason_code,
            state_before=_state_label(result.previous),
            state_after=_state_label(result.current),
            failure_reason=result.failure_reason,
        ),
        loop_label=loop_label,
        changed=result.changed,
        global_transition_reason=result.global_transition.reason_code,
    )
    return result


def plan_exit_reconciliation_with_logging(
    *,
    snapshot: ExchangeSnapshot,
    loop_label: str = "loop",
) -> ExitReconcilePlan:
    result = plan_exit_reconciliation(snapshot)
    log_structured_event(
        StructuredLogEvent(
            component="recovery",
            event="plan_exit_reconciliation",
            input_data=(
                f"snapshot_ok={snapshot.ok} open_order_count={snapshot.open_order_count} "
                f"has_any_position={snapshot.has_any_position}"
            ),
            decision="derive_cancel_and_exit_registration_plan",
            result=result.action_code,
            state_before="plan_pending",
            state_after="plan_ready",
            failure_reason="-" if result.has_action or result.reason_code == "RECOVERY_RECONCILE_NO_ACTION" else result.reason_code,
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        cancel_symbol_count=len(result.cancel_symbols),
        register_symbol_count=len(result.register_symbols),
        require_exit_registration=result.require_exit_registration,
    )
    return result


def complete_recovery_with_logging(
    state: RecoveryRuntimeState,
    *,
    price_source_ready: bool,
    reconciliation_ok: bool,
    loop_label: str = "loop",
) -> RecoveryTransitionResult:
    result = complete_recovery(
        state,
        price_source_ready=price_source_ready,
        reconciliation_ok=reconciliation_ok,
    )
    log_structured_event(
        StructuredLogEvent(
            component="recovery",
            event="complete_recovery",
            input_data=(
                f"price_source_ready={price_source_ready} reconciliation_ok={reconciliation_ok} "
                f"state={_state_label(state)}"
            ),
            decision="release_recovery_lock_only_when_all_gates_ready",
            result=result.reason_code,
            state_before=_state_label(result.previous),
            state_after=_state_label(result.current),
            failure_reason=result.failure_reason,
        ),
        loop_label=loop_label,
        changed=result.changed,
    )
    return result


def stop_signal_loop_with_logging(
    state: RecoveryRuntimeState,
    *,
    loop_label: str = "loop",
) -> RecoveryTransitionResult:
    result = stop_signal_loop(state)
    log_structured_event(
        StructuredLogEvent(
            component="recovery",
            event="stop_signal_loop",
            input_data=f"state={_state_label(state)}",
            decision="pause_signal_loop_by_ui_stop",
            result=result.reason_code,
            state_before=_state_label(result.previous),
            state_after=_state_label(result.current),
            failure_reason=result.failure_reason,
        ),
        loop_label=loop_label,
        changed=result.changed,
    )
    return result


def run_recovery_startup_with_logging(
    state: RecoveryRuntimeState,
    *,
    load_persisted_state: Callable[[], PersistentRecoveryState],
    fetch_exchange_snapshot: Callable[[], ExchangeSnapshot],
    check_price_source_ready: Callable[[], bool],
    execute_exit_reconciliation: Optional[Callable[[ExitReconcilePlan], ExitReconcileExecutionResult]] = None,
    cleared_monitoring_queue_count: int = 0,
    loop_label: str = "loop",
) -> RecoveryRunResult:
    result = run_recovery_startup(
        state,
        load_persisted_state=load_persisted_state,
        fetch_exchange_snapshot=fetch_exchange_snapshot,
        check_price_source_ready=check_price_source_ready,
        execute_exit_reconciliation=execute_exit_reconciliation,
        cleared_monitoring_queue_count=cleared_monitoring_queue_count,
    )
    log_structured_event(
        StructuredLogEvent(
            component="recovery",
            event="run_recovery_startup",
            input_data=f"cleared_monitoring_queue_count={cleared_monitoring_queue_count}",
            decision="execute_fixed_recovery_sequence_1_to_9",
            result=result.reason_code,
            state_before=_state_label(state),
            state_after=_state_label(result.state),
            failure_reason=result.failure_reason if not result.success else "-",
        ),
        loop_label=loop_label,
        success=result.success,
        snapshot_reason_code=result.snapshot_reason_code,
        reconcile_plan_reason_code=result.reconcile_plan_reason_code,
        reconcile_execution_reason_code=result.reconcile_execution_reason_code,
    )
    return result
