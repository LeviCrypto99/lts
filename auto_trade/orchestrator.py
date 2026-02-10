from __future__ import annotations

from dataclasses import replace
import zlib
from typing import Any, Callable, Mapping, Optional, Sequence

from .cooldown import (
    check_symbol_cooldown_with_logging,
    decide_cooldown_recording_with_logging,
    record_symbol_cooldown_with_logging,
)
from .entry_pipeline import run_first_entry_pipeline_with_logging, run_second_entry_pipeline_with_logging
from .entry_target_models import EntryMode
from .entry_targets import calculate_entry_target_with_logging
from .event_logging import StructuredLogEvent, log_structured_event
from .execution_flow import (
    evaluate_exit_five_second_rule_with_logging,
    evaluate_pnl_branch_with_logging,
    execute_oco_mutual_cancel_with_logging,
    plan_oco_mutual_cancel_with_logging,
    plan_risk_management_action_with_logging,
    sync_entry_fill_state_with_logging,
    update_exit_partial_fill_tracker_with_logging,
)
from .filtering import evaluate_common_filters_with_logging
from .message_parser import (
    check_message_id_dedup_with_logging,
    parse_leading_market_ticker_with_logging,
    parse_leading_market_message_with_logging,
    parse_risk_management_message_with_logging,
)
from .orchestrator_models import (
    AutoTradeRuntime,
    ExitFiveSecondProcessResult,
    FillSyncProcessResult,
    LeadingSignalProcessResult,
    OcoCancelProcessResult,
    PriceGuardProcessResult,
    RecoveryStartupProcessResult,
    RiskSignalProcessResult,
    TelegramMessageProcessResult,
    TriggerCycleProcessResult,
)
from .order_gateway import round_price_by_tick_size
from .order_gateway_models import GatewayCallResult, RetryPolicy, SymbolFilterRules
from .price_source import (
    apply_price_source_guard_with_logging,
    record_rest_mark_price_with_logging,
    record_ws_mark_price_with_logging,
)
from .recovery import run_recovery_startup_with_logging
from .recovery_models import (
    ExchangeSnapshot,
    ExitReconcileExecutionResult,
    ExitReconcilePlan,
    PersistentRecoveryState,
    RecoveryRuntimeState,
)
from .state_machine import apply_symbol_event_with_logging, update_account_activity_with_logging
from .symbol_mapping import (
    map_ticker_to_candidate_symbol_with_logging,
    validate_candidate_symbol_usdt_m_with_logging,
)
from .trigger_engine import evaluate_trigger_loop_with_logging
from .trigger_models import TriggerCandidate

_LEADING_FIELD_PARSE_FAILURE_CODES = frozenset(
    {
        "FUNDING_LINE_NOT_FOUND",
        "FUNDING_PAYLOAD_NOT_FOUND",
        "FUNDING_PARSE_FAILED",
        "COUNTDOWN_PARSE_FAILED",
        "RANKING_LINE_NOT_FOUND",
        "RANKING_PAYLOAD_NOT_FOUND",
        "RANKING_PARSE_FAILED",
        "CATEGORY_LINE_NOT_FOUND",
        "CATEGORY_PAYLOAD_NOT_FOUND",
        "CATEGORY_PARSE_FAILED",
    }
)


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_symbol(value: str) -> str:
    return (value or "").strip().upper()


def _state_label(runtime: AutoTradeRuntime) -> str:
    return (
        f"recovery_locked={runtime.recovery_locked}/paused={runtime.signal_loop_paused}/"
        f"running={runtime.signal_loop_running}/entry_locked={runtime.global_state.entry_locked}/"
        f"safety_locked={runtime.global_state.safety_locked}/symbol_state={runtime.symbol_state}/"
        f"active_symbol={_normalize(runtime.active_symbol)}/"
        f"new_orders_locked={runtime.new_orders_locked}/"
        f"rate_limit_locked={runtime.rate_limit_locked}/"
        f"auth_error_locked={runtime.auth_error_locked}/"
        f"second_entry_pending={runtime.second_entry_order_pending}"
    )


def _log_orchestrator_event(
    *,
    event: str,
    input_data: str,
    decision: str,
    result: str,
    state_before: str,
    state_after: str,
    failure_reason: str,
    **context: object,
) -> None:
    log_structured_event(
        StructuredLogEvent(
            component="orchestrator",
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


def _runtime_from_recovery(runtime: AutoTradeRuntime, recovery_state: RecoveryRuntimeState) -> AutoTradeRuntime:
    return replace(
        runtime,
        recovery_locked=recovery_state.recovery_locked,
        signal_loop_paused=recovery_state.signal_loop_paused,
        signal_loop_running=recovery_state.signal_loop_running,
        global_state=recovery_state.global_state,
        symbol_state=recovery_state.active_symbol_state,
        position_mode=recovery_state.position_mode,
        last_message_ids=dict(recovery_state.last_message_ids),
        cooldown_by_symbol=dict(recovery_state.cooldown_by_symbol),
        received_at_by_symbol=dict(recovery_state.received_at_by_symbol),
        message_id_by_symbol=dict(recovery_state.message_id_by_symbol),
    )


def _build_entry_client_order_id(
    *,
    symbol: str,
    trigger_kind: str,
    message_id: int,
) -> str:
    normalized_symbol = _normalize_symbol(symbol)
    trigger_code = "F1" if str(trigger_kind or "").strip().upper() == "FIRST_ENTRY" else "S2"
    symbol_hash = format(zlib.crc32(normalized_symbol.encode("utf-8")) & 0xFFFFFFFF, "08x")
    client_order_id = f"LTS-{trigger_code}-{max(0, int(message_id))}-{symbol_hash}"
    return client_order_id[:36]


def _can_allow_second_entry_while_entry_locked(runtime: AutoTradeRuntime) -> bool:
    if runtime.global_state.safety_locked:
        return False
    if runtime.symbol_state != "PHASE1":
        return False
    if runtime.second_entry_order_pending:
        return False
    if runtime.global_state.has_any_open_order:
        return False
    if not runtime.global_state.has_any_position:
        return False
    active_symbol = _normalize_symbol(str(runtime.active_symbol or ""))
    if not active_symbol:
        return False
    if not runtime.pending_trigger_candidates:
        return False
    for candidate in runtime.pending_trigger_candidates.values():
        candidate_symbol = _normalize_symbol(str(candidate.symbol or ""))
        trigger_kind = str(candidate.trigger_kind or "").strip().upper()
        if candidate_symbol != active_symbol:
            return False
        if trigger_kind != "SECOND_ENTRY":
            return False
    return True


def _record_candidate_cooldown_with_logging(
    runtime: AutoTradeRuntime,
    *,
    symbol: str,
    received_at_local: int,
    message_id: int,
    blocked_by_entry_lock: bool,
    blocked_by_safety_lock: bool,
    event: str,
    decision: str,
    loop_label: str,
    failure_code: Optional[str] = None,
) -> tuple[AutoTradeRuntime, str]:
    normalized_symbol = _normalize_symbol(symbol)
    cooldown_record_decision = decide_cooldown_recording_with_logging(
        blocked_by_entry_lock=blocked_by_entry_lock,
        blocked_by_safety_lock=blocked_by_safety_lock,
        candidate_symbol=normalized_symbol,
    )
    if not cooldown_record_decision.should_record:
        _log_orchestrator_event(
            event=event,
            input_data=(
                f"symbol={normalized_symbol} received_at_local={received_at_local} "
                f"message_id={message_id}"
            ),
            decision=decision,
            result="cooldown_record_skipped",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=cooldown_record_decision.reason_code,
            loop_label=loop_label,
            failure_code=_normalize(failure_code) if failure_code else "-",
        )
        return runtime, f"SKIPPED_{cooldown_record_decision.reason_code}"

    cooldown_check = check_symbol_cooldown_with_logging(
        runtime.cooldown_by_symbol,
        symbol=normalized_symbol,
        received_at=received_at_local,
        cooldown_minutes=runtime.settings.cooldown_minutes,
    )
    if cooldown_check.should_ignore:
        _log_orchestrator_event(
            event=event,
            input_data=(
                f"symbol={normalized_symbol} received_at_local={received_at_local} "
                f"message_id={message_id}"
            ),
            decision=decision,
            result="cooldown_skip_in_window",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=cooldown_check.reason_code,
            loop_label=loop_label,
            failure_code=_normalize(failure_code) if failure_code else "-",
            remaining_seconds=cooldown_check.remaining_seconds,
        )
        return runtime, f"BLOCKED_{cooldown_check.reason_code}"

    recorded_cooldown = record_symbol_cooldown_with_logging(
        runtime.cooldown_by_symbol,
        symbol=normalized_symbol,
        received_at=received_at_local,
    )
    received_at_by_symbol = dict(runtime.received_at_by_symbol)
    received_at_by_symbol[normalized_symbol] = int(received_at_local)
    message_id_by_symbol = dict(runtime.message_id_by_symbol)
    message_id_by_symbol[normalized_symbol] = int(message_id)
    updated = replace(
        runtime,
        cooldown_by_symbol=recorded_cooldown,
        received_at_by_symbol=received_at_by_symbol,
        message_id_by_symbol=message_id_by_symbol,
    )
    _log_orchestrator_event(
        event=event,
        input_data=(
            f"symbol={normalized_symbol} received_at_local={received_at_local} "
            f"message_id={message_id}"
        ),
        decision=decision,
        result="cooldown_recorded",
        state_before=_state_label(runtime),
        state_after=_state_label(updated),
        failure_reason="-",
        loop_label=loop_label,
        failure_code=_normalize(failure_code) if failure_code else "-",
    )
    return updated, "RECORDED"


def run_recovery_startup_flow(
    runtime: AutoTradeRuntime,
    *,
    load_persisted_state: Callable[[], PersistentRecoveryState],
    fetch_exchange_snapshot: Callable[[], ExchangeSnapshot],
    check_price_source_ready: Callable[[], bool],
    execute_exit_reconciliation: Optional[Callable[[ExitReconcilePlan], ExitReconcileExecutionResult]] = None,
    cleared_monitoring_queue_count: int = 0,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, RecoveryStartupProcessResult]:
    before = _state_label(runtime)
    seed = RecoveryRuntimeState(
        recovery_locked=runtime.recovery_locked,
        signal_loop_paused=runtime.signal_loop_paused,
        signal_loop_running=runtime.signal_loop_running,
        persisted_loaded=False,
        snapshot_loaded=False,
        monitoring_queue_cleared=False,
        global_state=runtime.global_state,
        position_mode=runtime.position_mode,
        active_symbol_state=runtime.symbol_state,
        last_message_ids=dict(runtime.last_message_ids),
        cooldown_by_symbol=dict(runtime.cooldown_by_symbol),
        received_at_by_symbol=dict(runtime.received_at_by_symbol),
        message_id_by_symbol=dict(runtime.message_id_by_symbol),
    )
    recovery_result = run_recovery_startup_with_logging(
        seed,
        load_persisted_state=load_persisted_state,
        fetch_exchange_snapshot=fetch_exchange_snapshot,
        check_price_source_ready=check_price_source_ready,
        execute_exit_reconciliation=execute_exit_reconciliation,
        cleared_monitoring_queue_count=cleared_monitoring_queue_count,
        loop_label=loop_label,
    )
    current = _runtime_from_recovery(runtime, recovery_result.state)
    if recovery_result.success:
        current = replace(
            current,
            active_symbol=None,
            pending_trigger_candidates={},
            new_orders_locked=False,
            rate_limit_locked=False,
            auth_error_locked=False,
            second_entry_order_pending=False,
        )
    process_result = RecoveryStartupProcessResult(
        success=recovery_result.success,
        reason_code=recovery_result.reason_code,
        failure_reason=recovery_result.failure_reason,
    )
    _log_orchestrator_event(
        event="run_recovery_startup_flow",
        input_data=f"cleared_monitoring_queue_count={cleared_monitoring_queue_count}",
        decision="bind_recovery_result_back_to_runtime",
        result=process_result.reason_code,
        state_before=before,
        state_after=_state_label(current),
        failure_reason=process_result.failure_reason if not process_result.success else "-",
        success=process_result.success,
        loop_label=loop_label,
    )
    return current, process_result


def handle_leading_market_signal(
    runtime: AutoTradeRuntime,
    *,
    channel_id: int,
    message_id: int,
    message_text: str,
    received_at_local: int,
    exchange_info: Mapping[str, Any],
    candles: Sequence[Mapping[str, Any]],
    entry_mode: EntryMode,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, LeadingSignalProcessResult]:
    before_state = runtime.symbol_state
    if runtime.recovery_locked or runtime.signal_loop_paused:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code="RECOVERY_LOCKED_SIGNAL_PAUSED",
            failure_reason="signal loop is paused by recovery lock",
            symbol=None,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="gate_by_recovery_lock_and_signal_pause",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    dedup = check_message_id_dedup_with_logging(
        runtime.last_message_ids,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not dedup.accepted:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=dedup.reason_code,
            failure_reason=dedup.reason_code,
            symbol=None,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="drop_duplicate_or_old_message",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    current = replace(runtime, last_message_ids=dict(dedup.updated_last_message_ids))

    parse_result = parse_leading_market_message_with_logging(
        message_text,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not parse_result.ok or parse_result.data is None:
        symbol_for_parse_failure: Optional[str] = None
        if parse_result.failure_code in _LEADING_FIELD_PARSE_FAILURE_CODES:
            ticker_parse = parse_leading_market_ticker_with_logging(
                message_text,
                channel_id=channel_id,
                message_id=message_id,
            )
            if ticker_parse.ok and ticker_parse.ticker is not None:
                mapped_for_parse_failure = map_ticker_to_candidate_symbol_with_logging(
                    ticker_parse.ticker,
                    channel_id=channel_id,
                    message_id=message_id,
                )
                if mapped_for_parse_failure.ok and mapped_for_parse_failure.candidate_symbol is not None:
                    symbol_for_parse_failure = _normalize_symbol(mapped_for_parse_failure.candidate_symbol)
                    validate_candidate_symbol_usdt_m_with_logging(
                        mapped_for_parse_failure.candidate_symbol,
                        exchange_info,
                        channel_id=channel_id,
                        message_id=message_id,
                    )
                    blocked_by_entry_lock = (
                        current.global_state.entry_locked
                        or current.new_orders_locked
                        or current.rate_limit_locked
                        or current.auth_error_locked
                    )
                    blocked_by_safety_lock = current.global_state.safety_locked
                    current, _ = _record_candidate_cooldown_with_logging(
                        current,
                        symbol=symbol_for_parse_failure,
                        received_at_local=received_at_local,
                        message_id=message_id,
                        blocked_by_entry_lock=blocked_by_entry_lock,
                        blocked_by_safety_lock=blocked_by_safety_lock,
                        event="handle_leading_market_signal_parse_failure_cooldown",
                        decision="record_cooldown_when_candidate_symbol_is_resolved",
                        loop_label=loop_label,
                        failure_code=parse_result.failure_code,
                    )
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"LEADING_PARSE_FAILED_{parse_result.failure_code}",
            failure_reason=parse_result.failure_reason,
            symbol=symbol_for_parse_failure,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="parse_leading_market_message",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    mapped = map_ticker_to_candidate_symbol_with_logging(
        parse_result.data.ticker,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not mapped.ok or mapped.candidate_symbol is None:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"SYMBOL_MAP_FAILED_{mapped.failure_code}",
            failure_reason=mapped.failure_reason,
            symbol=None,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"ticker={_normalize(parse_result.data.ticker)}",
            decision="map_ticker_to_candidate_symbol",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    validated = validate_candidate_symbol_usdt_m_with_logging(
        mapped.candidate_symbol,
        exchange_info,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not validated.ok:
        symbol = _normalize_symbol(validated.symbol or mapped.candidate_symbol)
        blocked_by_entry_lock = (
            current.global_state.entry_locked
            or current.new_orders_locked
            or current.rate_limit_locked
            or current.auth_error_locked
        )
        blocked_by_safety_lock = current.global_state.safety_locked
        current, cooldown_status = _record_candidate_cooldown_with_logging(
            current,
            symbol=symbol,
            received_at_local=received_at_local,
            message_id=message_id,
            blocked_by_entry_lock=blocked_by_entry_lock,
            blocked_by_safety_lock=blocked_by_safety_lock,
            event="handle_leading_market_signal_symbol_validate_failure_cooldown",
            decision="record_cooldown_when_candidate_symbol_validation_failed",
            loop_label=loop_label,
            failure_code=validated.failure_code,
        )
        if cooldown_status.startswith("BLOCKED_"):
            cooldown_reason = cooldown_status.removeprefix("BLOCKED_")
            result = LeadingSignalProcessResult(
                accepted=False,
                reason_code=f"COOLDOWN_BLOCKED_{cooldown_reason}",
                failure_reason=cooldown_reason,
                symbol=symbol,
                trigger_registered=False,
                symbol_state_before=before_state,
                symbol_state_after=current.symbol_state,
            )
            _log_orchestrator_event(
                event="handle_leading_market_signal",
                input_data=f"symbol={_normalize(mapped.candidate_symbol)}",
                decision="validate_candidate_symbol_usdt_m",
                result="rejected",
                state_before=_state_label(runtime),
                state_after=_state_label(current),
                failure_reason=result.reason_code,
                loop_label=loop_label,
            )
            return current, result
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"SYMBOL_VALIDATE_FAILED_{validated.failure_code}",
            failure_reason=validated.failure_reason,
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={_normalize(mapped.candidate_symbol)}",
            decision="validate_candidate_symbol_usdt_m",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    symbol = validated.symbol
    if (
        current.symbol_state == "MONITORING"
        and (
            _normalize_symbol(current.active_symbol or "") == symbol
            or symbol in current.pending_trigger_candidates
        )
    ):
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code="SYMBOL_ALREADY_MONITORING",
            failure_reason="symbol is already in monitoring set",
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={symbol}",
            decision="ignore_duplicate_signal_for_symbol_already_monitoring",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    blocked_by_entry_lock = (
        current.global_state.entry_locked
        or current.new_orders_locked
        or current.rate_limit_locked
        or current.auth_error_locked
    )
    blocked_by_safety_lock = current.global_state.safety_locked
    cooldown_record_decision = decide_cooldown_recording_with_logging(
        blocked_by_entry_lock=blocked_by_entry_lock,
        blocked_by_safety_lock=blocked_by_safety_lock,
        candidate_symbol=symbol,
    )
    if not cooldown_record_decision.should_record:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"COOLDOWN_RECORD_SKIPPED_{cooldown_record_decision.reason_code}",
            failure_reason=cooldown_record_decision.reason_code,
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={symbol}",
            decision="evaluate_cooldown_recording_rule",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    cooldown_check = check_symbol_cooldown_with_logging(
        current.cooldown_by_symbol,
        symbol=symbol,
        received_at=received_at_local,
        cooldown_minutes=current.settings.cooldown_minutes,
    )
    if cooldown_check.should_ignore:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"COOLDOWN_BLOCKED_{cooldown_check.reason_code}",
            failure_reason=cooldown_check.reason_code,
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={symbol} received_at_local={received_at_local}",
            decision="check_symbol_cooldown_window",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
            remaining_seconds=cooldown_check.remaining_seconds,
        )
        return current, result

    common_filter = evaluate_common_filters_with_logging(
        category=parse_result.data.category,
        ranking_direction=parse_result.data.ranking_direction,
        ranking_position=parse_result.data.ranking_position,
        funding_rate_pct=parse_result.data.funding_rate_pct,
        symbol=symbol,
    )
    if not common_filter.passed:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"COMMON_FILTER_REJECTED_{common_filter.reason_code}",
            failure_reason=common_filter.failure_reason,
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={symbol}",
            decision="apply_common_filter_rules",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    target_result = calculate_entry_target_with_logging(
        mode=entry_mode,
        candles=candles,
        symbol=symbol,
    )
    if not target_result.ok or target_result.target_price is None:
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"ENTRY_TARGET_REJECTED_{target_result.reason_code}",
            failure_reason=target_result.failure_reason,
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={symbol} mode={entry_mode}",
            decision="calculate_entry_target",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    symbol_state_after = current.symbol_state
    if current.symbol_state == "IDLE":
        transition = apply_symbol_event_with_logging(current.symbol_state, "START_MONITORING")
        if not transition.accepted:
            result = LeadingSignalProcessResult(
                accepted=False,
                reason_code=f"MONITORING_TRANSITION_REJECTED_{transition.reason_code}",
                failure_reason=transition.reason_code,
                symbol=symbol,
                trigger_registered=False,
                symbol_state_before=before_state,
                symbol_state_after=current.symbol_state,
            )
            _log_orchestrator_event(
                event="handle_leading_market_signal",
                input_data=f"symbol={symbol}",
                decision="transition_idle_to_monitoring",
                result="rejected",
                state_before=_state_label(runtime),
                state_after=_state_label(current),
                failure_reason=result.reason_code,
                loop_label=loop_label,
            )
            return current, result
        symbol_state_after = transition.current_state
    elif current.symbol_state not in ("MONITORING",):
        result = LeadingSignalProcessResult(
            accepted=False,
            reason_code=f"SYMBOL_STATE_BLOCKED_{current.symbol_state}",
            failure_reason=f"current_state={current.symbol_state}",
            symbol=symbol,
            trigger_registered=False,
            symbol_state_before=before_state,
            symbol_state_after=current.symbol_state,
        )
        _log_orchestrator_event(
            event="handle_leading_market_signal",
            input_data=f"symbol={symbol}",
            decision="gate_by_symbol_state",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    recorded_cooldown = record_symbol_cooldown_with_logging(
        current.cooldown_by_symbol,
        symbol=symbol,
        received_at=received_at_local,
    )
    received_at_by_symbol = dict(current.received_at_by_symbol)
    received_at_by_symbol[symbol] = int(received_at_local)
    message_id_by_symbol = dict(current.message_id_by_symbol)
    message_id_by_symbol[symbol] = int(message_id)
    pending = dict(current.pending_trigger_candidates)
    pending[symbol] = TriggerCandidate(
        symbol=symbol,
        trigger_kind="FIRST_ENTRY",
        target_price=float(target_result.target_price),
        received_at_local=int(received_at_local),
        message_id=int(message_id),
        entry_mode=str(entry_mode),
    )
    current = replace(
        current,
        symbol_state=symbol_state_after,
        active_symbol=symbol,
        cooldown_by_symbol=recorded_cooldown,
        received_at_by_symbol=received_at_by_symbol,
        message_id_by_symbol=message_id_by_symbol,
        pending_trigger_candidates=pending,
        second_entry_order_pending=False,
    )
    result = LeadingSignalProcessResult(
        accepted=True,
        reason_code="LEADING_SIGNAL_TRIGGER_REGISTERED",
        failure_reason="-",
        symbol=symbol,
        trigger_registered=True,
        symbol_state_before=before_state,
        symbol_state_after=current.symbol_state,
    )
    _log_orchestrator_event(
        event="handle_leading_market_signal",
        input_data=(
            f"channel_id={channel_id} message_id={message_id} symbol={symbol} "
            f"received_at_local={received_at_local}"
        ),
        decision="register_first_entry_trigger_from_leading_market",
        result="accepted",
        state_before=_state_label(runtime),
        state_after=_state_label(current),
        failure_reason="-",
        loop_label=loop_label,
        pending_trigger_count=len(current.pending_trigger_candidates),
    )
    return current, result


def run_trigger_entry_cycle(
    runtime: AutoTradeRuntime,
    *,
    mark_prices: Mapping[str, float],
    wallet_balance_usdt: float,
    available_usdt: float,
    filter_rules_by_symbol: Mapping[str, SymbolFilterRules],
    position_mode: PositionMode,
    create_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    pre_order_setup: Optional[Callable[[str, str, str], tuple[bool, str, str, bool]]] = None,
    refresh_available_usdt: Optional[Callable[[], float]] = None,
    retry_policy: Optional[RetryPolicy] = None,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, TriggerCycleProcessResult]:
    before_state = runtime.symbol_state
    if runtime.recovery_locked or runtime.signal_loop_paused:
        result = TriggerCycleProcessResult(
            attempted=False,
            success=False,
            reason_code="RECOVERY_LOCKED_SIGNAL_PAUSED",
            failure_reason="signal loop is paused by recovery lock",
            selected_symbol=None,
            selected_trigger_kind=None,
            pipeline_reason_code="NO_PIPELINE_CALL",
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="run_trigger_entry_cycle",
            input_data=f"pending_candidates={len(runtime.pending_trigger_candidates)}",
            decision="gate_by_recovery_lock_and_signal_pause",
            result="skipped",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    allow_second_entry_under_entry_lock = False
    if runtime.global_state.global_blocked:
        allow_second_entry_under_entry_lock = _can_allow_second_entry_while_entry_locked(runtime)
        if allow_second_entry_under_entry_lock:
            _log_orchestrator_event(
                event="run_trigger_entry_cycle",
                input_data=(
                    f"pending_candidates={len(runtime.pending_trigger_candidates)} "
                    f"active_symbol={_normalize(runtime.active_symbol)}"
                ),
                decision="allow_phase1_second_entry_under_entry_lock",
                result="allowed",
                state_before=_state_label(runtime),
                state_after=_state_label(runtime),
                failure_reason="-",
                loop_label=loop_label,
                entry_locked=runtime.global_state.entry_locked,
                safety_locked=runtime.global_state.safety_locked,
                has_any_position=runtime.global_state.has_any_position,
                has_any_open_order=runtime.global_state.has_any_open_order,
            )

    if (
        (runtime.global_state.global_blocked and not allow_second_entry_under_entry_lock)
        or runtime.new_orders_locked
        or runtime.rate_limit_locked
        or runtime.auth_error_locked
    ):
        result = TriggerCycleProcessResult(
            attempted=False,
            success=False,
            reason_code="GLOBAL_BLOCKED_OR_NEW_ORDER_LOCKED",
            failure_reason="global_blocked_or_new_orders_locked",
            selected_symbol=None,
            selected_trigger_kind=None,
            pipeline_reason_code="NO_PIPELINE_CALL",
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="run_trigger_entry_cycle",
            input_data=f"pending_candidates={len(runtime.pending_trigger_candidates)}",
            decision="gate_by_global_block_or_new_order_lock",
            result="skipped",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    if not runtime.pending_trigger_candidates:
        result = TriggerCycleProcessResult(
            attempted=False,
            success=False,
            reason_code="NO_PENDING_TRIGGER_CANDIDATES",
            failure_reason="no candidates",
            selected_symbol=None,
            selected_trigger_kind=None,
            pipeline_reason_code="NO_PIPELINE_CALL",
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="run_trigger_entry_cycle",
            input_data="pending_candidates=0",
            decision="run_trigger_loop",
            result="no_trigger",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    raw_candidates = list(runtime.pending_trigger_candidates.values())
    candidates: list[TriggerCandidate] = []
    for candidate in raw_candidates:
        candidate_symbol = _normalize_symbol(candidate.symbol)
        filter_rules_for_candidate = filter_rules_by_symbol.get(candidate_symbol)
        if filter_rules_for_candidate is None:
            result = TriggerCycleProcessResult(
                attempted=True,
                success=False,
                reason_code="MISSING_SYMBOL_FILTER_RULES",
                failure_reason=f"symbol={candidate_symbol}",
                selected_symbol=candidate_symbol,
                selected_trigger_kind=candidate.trigger_kind,
                pipeline_reason_code="NO_PIPELINE_CALL",
                symbol_state_before=before_state,
                symbol_state_after=before_state,
            )
            _log_orchestrator_event(
                event="run_trigger_entry_cycle",
                input_data=f"selected_symbol={candidate_symbol}",
                decision="resolve_symbol_filter_rules_for_trigger_candidates",
                result="failed",
                state_before=_state_label(runtime),
                state_after=_state_label(runtime),
                failure_reason=result.reason_code,
                loop_label=loop_label,
            )
            return runtime, result
        normalized_target_price = round_price_by_tick_size(
            float(candidate.target_price),
            float(filter_rules_for_candidate.tick_size),
        )
        if normalized_target_price is None or normalized_target_price <= 0:
            result = TriggerCycleProcessResult(
                attempted=True,
                success=False,
                reason_code="INVALID_NORMALIZED_TARGET_PRICE",
                failure_reason=f"symbol={candidate_symbol} raw_target={candidate.target_price}",
                selected_symbol=candidate_symbol,
                selected_trigger_kind=candidate.trigger_kind,
                pipeline_reason_code="NO_PIPELINE_CALL",
                symbol_state_before=before_state,
                symbol_state_after=before_state,
            )
            _log_orchestrator_event(
                event="run_trigger_entry_cycle",
                input_data=(
                    f"selected_symbol={candidate_symbol} raw_target={candidate.target_price} "
                    f"tick_size={filter_rules_for_candidate.tick_size}"
                ),
                decision="normalize_trigger_target_price_by_tick_size",
                result="failed",
                state_before=_state_label(runtime),
                state_after=_state_label(runtime),
                failure_reason=result.reason_code,
                loop_label=loop_label,
            )
            return runtime, result
        candidates.append(
            replace(
                candidate,
                symbol=candidate_symbol,
                target_price=float(normalized_target_price),
            )
        )
    trigger_loop = evaluate_trigger_loop_with_logging(
        candidates,
        mark_prices,
        loop_label=loop_label,
    )
    if trigger_loop.selected_candidate is None:
        result = TriggerCycleProcessResult(
            attempted=True,
            success=False,
            reason_code=trigger_loop.reason_code,
            failure_reason=trigger_loop.reason_code,
            selected_symbol=None,
            selected_trigger_kind=None,
            pipeline_reason_code="NO_PIPELINE_CALL",
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="run_trigger_entry_cycle",
            input_data=f"candidate_count={len(candidates)} mark_price_count={len(mark_prices)}",
            decision="evaluate_trigger_loop",
            result="no_trigger",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    selected = trigger_loop.selected_candidate
    selected_symbol = _normalize_symbol(selected.symbol)
    filter_rules = filter_rules_by_symbol.get(selected_symbol)
    if filter_rules is None:
        result = TriggerCycleProcessResult(
            attempted=True,
            success=False,
            reason_code="MISSING_SYMBOL_FILTER_RULES",
            failure_reason=f"symbol={selected_symbol}",
            selected_symbol=selected_symbol,
            selected_trigger_kind=selected.trigger_kind,
            pipeline_reason_code="NO_PIPELINE_CALL",
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="run_trigger_entry_cycle",
            input_data=f"selected_symbol={selected_symbol}",
            decision="resolve_symbol_filter_rules",
            result="failed",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    if pre_order_setup is not None:
        setup_ok, setup_reason, setup_failure, setup_reset = pre_order_setup(
            selected_symbol,
            str(selected.trigger_kind),
            loop_label,
        )
        if not setup_ok:
            if setup_reset:
                current = replace(
                    runtime,
                    symbol_state="IDLE",
                    active_symbol=None,
                    pending_trigger_candidates={},
                    second_entry_order_pending=False,
                )
            else:
                pending = {
                    key: value
                    for key, value in runtime.pending_trigger_candidates.items()
                    if _normalize_symbol(str(key)) != selected_symbol
                }
                next_symbol_state = runtime.symbol_state
                next_active_symbol = runtime.active_symbol
                selected_is_active = _normalize_symbol(str(runtime.active_symbol or "")) == selected_symbol
                selected_trigger_kind = str(selected.trigger_kind or "").strip().upper()
                if runtime.symbol_state == "MONITORING":
                    if not pending:
                        next_symbol_state = "IDLE"
                        next_active_symbol = None
                    elif selected_is_active and selected_trigger_kind == "FIRST_ENTRY":
                        next_candidate = max(
                            pending.values(),
                            key=lambda item: (
                                int(item.received_at_local),
                                int(item.message_id),
                                _normalize_symbol(item.symbol),
                            ),
                        )
                        next_active_symbol = _normalize_symbol(next_candidate.symbol)
                current = replace(
                    runtime,
                    symbol_state=next_symbol_state,
                    active_symbol=next_active_symbol,
                    pending_trigger_candidates=pending,
                    second_entry_order_pending=(
                        runtime.second_entry_order_pending
                        if next_symbol_state != "IDLE"
                        else False
                    ),
                )
            result = TriggerCycleProcessResult(
                attempted=True,
                success=False,
                reason_code=f"PRE_ORDER_SETUP_FAILED_{_normalize(setup_reason)}",
                failure_reason=_normalize(setup_failure),
                selected_symbol=selected_symbol,
                selected_trigger_kind=selected.trigger_kind,
                pipeline_reason_code="NO_PIPELINE_CALL_PRE_ORDER_SETUP",
                symbol_state_before=before_state,
                symbol_state_after=current.symbol_state,
            )
            _log_orchestrator_event(
                event="run_trigger_entry_cycle",
                input_data=(
                    f"selected_symbol={selected_symbol} trigger_kind={selected.trigger_kind} "
                    f"setup_reason={_normalize(setup_reason)} reset={setup_reset}"
                ),
                decision="run_pre_order_setup_hook_before_pipeline",
                result="failed",
                state_before=_state_label(runtime),
                state_after=_state_label(current),
                failure_reason=result.reason_code,
                loop_label=loop_label,
            )
            return current, result

    entry_client_order_id = _build_entry_client_order_id(
        symbol=selected_symbol,
        trigger_kind=str(selected.trigger_kind),
        message_id=int(selected.message_id),
    )
    if selected.trigger_kind == "FIRST_ENTRY":
        pipeline = run_first_entry_pipeline_with_logging(
            current_state=runtime.symbol_state,
            symbol=selected_symbol,
            target_price=selected.target_price,
            wallet_balance_usdt=wallet_balance_usdt,
            filter_rules=filter_rules,
            position_mode=position_mode,
            create_call=create_call,
            retry_policy=retry_policy,
            new_client_order_id=entry_client_order_id,
            loop_label=loop_label,
        )
    elif selected.trigger_kind == "SECOND_ENTRY":
        pipeline = run_second_entry_pipeline_with_logging(
            current_state=runtime.symbol_state,
            symbol=selected_symbol,
            second_target_price=selected.target_price,
            available_usdt=available_usdt,
            margin_buffer_pct=runtime.settings.margin_buffer_pct,
            filter_rules=filter_rules,
            position_mode=position_mode,
            create_call=create_call,
            refresh_available_usdt=refresh_available_usdt,
            retry_policy=retry_policy,
            new_client_order_id=entry_client_order_id,
            loop_label=loop_label,
        )
    else:
        result = TriggerCycleProcessResult(
            attempted=True,
            success=False,
            reason_code=f"UNSUPPORTED_TRIGGER_KIND_{selected.trigger_kind}",
            failure_reason=f"trigger_kind={selected.trigger_kind}",
            selected_symbol=selected_symbol,
            selected_trigger_kind=selected.trigger_kind,
            pipeline_reason_code="NO_PIPELINE_CALL",
            symbol_state_before=before_state,
            symbol_state_after=before_state,
        )
        _log_orchestrator_event(
            event="run_trigger_entry_cycle",
            input_data=f"selected_symbol={selected_symbol} trigger_kind={selected.trigger_kind}",
            decision="dispatch_to_entry_pipeline",
            result="failed",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    current = replace(
        runtime,
        symbol_state=pipeline.current_state,
        active_symbol=selected_symbol if pipeline.success else runtime.active_symbol,
        pending_trigger_candidates={},
        position_mode=position_mode,
        second_entry_order_pending=(
            True
            if pipeline.success and selected.trigger_kind == "SECOND_ENTRY"
            else runtime.second_entry_order_pending
        ),
    )
    if pipeline.success:
        global_transition = update_account_activity_with_logging(
            current.global_state,
            has_any_position=current.global_state.has_any_position,
            has_any_open_order=True,
        )
        current = replace(current, global_state=global_transition.current)
    elif pipeline.current_state == "IDLE":
        current = replace(current, active_symbol=None)

    result = TriggerCycleProcessResult(
        attempted=True,
        success=pipeline.success,
        reason_code=(
            "TRIGGER_EXECUTED_AND_ORDER_SUBMITTED" if pipeline.success else f"TRIGGER_PIPELINE_FAILED_{pipeline.reason_code}"
        ),
        failure_reason="-" if pipeline.success else pipeline.failure_reason,
        selected_symbol=selected_symbol,
        selected_trigger_kind=selected.trigger_kind,
        pipeline_reason_code=pipeline.reason_code,
        symbol_state_before=before_state,
        symbol_state_after=current.symbol_state,
    )
    _log_orchestrator_event(
        event="run_trigger_entry_cycle",
        input_data=(
            f"selected_symbol={selected_symbol} trigger_kind={selected.trigger_kind} "
            f"wallet_balance_usdt={wallet_balance_usdt} available_usdt={available_usdt}"
        ),
        decision="run_entry_pipeline_for_selected_trigger",
        result="success" if result.success else "failed",
        state_before=_state_label(runtime),
        state_after=_state_label(current),
        failure_reason=result.reason_code if not result.success else "-",
        loop_label=loop_label,
        pipeline_reason_code=pipeline.reason_code,
    )
    return current, result


def sync_entry_fill_flow(
    runtime: AutoTradeRuntime,
    *,
    phase: str,
    order_status: str,
    has_position: bool,
    has_any_open_order: Optional[bool] = None,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, FillSyncProcessResult]:
    sync_result = sync_entry_fill_state_with_logging(
        runtime.symbol_state,
        phase=phase,  # type: ignore[arg-type]
        order_status=order_status,  # type: ignore[arg-type]
        has_position=has_position,
        loop_label=loop_label,
    )
    second_entry_order_pending = runtime.second_entry_order_pending
    if phase == "SECOND_ENTRY":
        if order_status in ("FILLED", "PARTIALLY_FILLED", "CANCELED", "REJECTED", "EXPIRED"):
            second_entry_order_pending = False
    if sync_result.current_state == "IDLE":
        second_entry_order_pending = False

    current = replace(
        runtime,
        symbol_state=sync_result.current_state,
        second_entry_order_pending=second_entry_order_pending,
    )
    if has_any_open_order is not None:
        global_transition = update_account_activity_with_logging(
            current.global_state,
            has_any_position=has_position,
            has_any_open_order=bool(has_any_open_order),
        )
        current = replace(current, global_state=global_transition.current)
    if sync_result.current_state == "IDLE":
        current = replace(
            current,
            active_symbol=None,
            pending_trigger_candidates={},
            second_entry_order_pending=False,
        )

    result = FillSyncProcessResult(
        accepted=True,
        reason_code=sync_result.reason_code,
        failure_reason="-",
        symbol_state_before=sync_result.previous_state,
        symbol_state_after=sync_result.current_state,
    )
    _log_orchestrator_event(
        event="sync_entry_fill_flow",
        input_data=f"phase={phase} order_status={order_status} has_position={has_position}",
        decision="apply_fill_sync_and_update_runtime_state",
        result=sync_result.reason_code,
        state_before=_state_label(runtime),
        state_after=_state_label(current),
        failure_reason="-",
        loop_label=loop_label,
    )
    return current, result


def handle_risk_management_signal(
    runtime: AutoTradeRuntime,
    *,
    channel_id: int,
    message_id: int,
    message_text: str,
    avg_entry_price: float,
    mark_price: float,
    has_position: bool,
    has_open_entry_order: bool,
    has_tp_order: bool,
    second_entry_fully_filled: bool,
    exchange_info: Optional[Mapping[str, Any]] = None,
    exchange_info_error: Optional[str] = None,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, RiskSignalProcessResult]:
    before = runtime
    dedup = check_message_id_dedup_with_logging(
        runtime.last_message_ids,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not dedup.accepted:
        result = RiskSignalProcessResult(
            accepted=False,
            actionable=False,
            reason_code=dedup.reason_code,
            failure_reason=dedup.reason_code,
            symbol=None,
            pnl_branch="PNL_UNAVAILABLE",
            action_code="IGNORE_DUPLICATE",
            reset_state=False,
        )
        _log_orchestrator_event(
            event="handle_risk_management_signal",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="drop_duplicate_or_old_message",
            result="rejected",
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return runtime, result

    current = replace(runtime, last_message_ids=dict(dedup.updated_last_message_ids))
    parsed = parse_risk_management_message_with_logging(
        message_text,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not parsed.ok or parsed.data is None:
        result = RiskSignalProcessResult(
            accepted=False,
            actionable=False,
            reason_code=f"RISK_PARSE_FAILED_{parsed.failure_code}",
            failure_reason=parsed.failure_reason,
            symbol=None,
            pnl_branch="PNL_UNAVAILABLE",
            action_code="IGNORE_PARSE_FAILED",
            reset_state=False,
        )
        _log_orchestrator_event(
            event="handle_risk_management_signal",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="parse_risk_management_message",
            result="rejected",
            state_before=_state_label(before),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result

    validated = validate_candidate_symbol_usdt_m_with_logging(
        parsed.data.symbol,
        exchange_info,
        exchange_info_error=exchange_info_error,
        channel_id=channel_id,
        message_id=message_id,
    )
    if not validated.ok:
        result = RiskSignalProcessResult(
            accepted=False,
            actionable=False,
            reason_code=f"RISK_SYMBOL_VALIDATE_FAILED_{validated.failure_code}",
            failure_reason=validated.failure_reason,
            symbol=_normalize_symbol(validated.symbol or parsed.data.symbol),
            pnl_branch="PNL_UNAVAILABLE",
            action_code="IGNORE_SYMBOL_VALIDATE_FAILED",
            reset_state=False,
        )
        _log_orchestrator_event(
            event="handle_risk_management_signal",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="validate_risk_symbol_with_exchange_info",
            result="rejected",
            state_before=_state_label(before),
            state_after=_state_label(current),
            failure_reason=result.reason_code,
            loop_label=loop_label,
        )
        return current, result
    risk_symbol = _normalize_symbol(validated.symbol or parsed.data.symbol)

    pnl_result = evaluate_pnl_branch_with_logging(
        avg_entry_price=avg_entry_price,
        mark_price=mark_price,
    )
    symbol_matches_context = (
        risk_symbol == _normalize_symbol(current.active_symbol or "")
        or (
            current.symbol_state == "MONITORING"
            and risk_symbol in {
                _normalize_symbol(str(key))
                for key in current.pending_trigger_candidates.keys()
            }
        )
    )
    plan = plan_risk_management_action_with_logging(
        current_state=current.symbol_state,
        symbol_matches_active=symbol_matches_context,
        has_position=has_position,
        has_open_entry_order=has_open_entry_order,
        pnl_branch=pnl_result.branch,
        has_tp_order=has_tp_order,
        second_entry_fully_filled=second_entry_fully_filled,
        loop_label=loop_label,
    )
    if plan.reset_state:
        if current.symbol_state == "MONITORING":
            pending = {
                key: value
                for key, value in current.pending_trigger_candidates.items()
                if _normalize_symbol(str(key)) != risk_symbol
            }
            if pending:
                next_candidate = max(
                    pending.values(),
                    key=lambda item: (
                        int(item.received_at_local),
                        int(item.message_id),
                        _normalize_symbol(item.symbol),
                    ),
                )
                current = replace(
                    current,
                    symbol_state="MONITORING",
                    active_symbol=_normalize_symbol(next_candidate.symbol),
                    pending_trigger_candidates=pending,
                    second_entry_order_pending=False,
                )
            else:
                current = replace(
                    current,
                    symbol_state="IDLE",
                    active_symbol=None,
                    pending_trigger_candidates={},
                    second_entry_order_pending=False,
                )
        else:
            current = replace(
                current,
                symbol_state="IDLE",
                active_symbol=None,
                pending_trigger_candidates={},
                second_entry_order_pending=False,
            )
    result = RiskSignalProcessResult(
        accepted=True,
        actionable=plan.actionable,
        reason_code=plan.reason_code,
        failure_reason="-" if plan.actionable else plan.reason_code,
        symbol=risk_symbol,
        pnl_branch=pnl_result.branch,
        action_code=plan.action_code,
        reset_state=plan.reset_state,
        cancel_entry_orders=plan.cancel_entry_orders,
        submit_market_exit=plan.submit_market_exit,
        submit_breakeven_stop_market=plan.submit_breakeven_stop_market,
        create_tp_limit_once=plan.create_tp_limit_once,
        keep_tp_order=plan.keep_tp_order,
        keep_phase2_breakeven_limit=plan.keep_phase2_breakeven_limit,
        keep_existing_mdd_stop=plan.keep_existing_mdd_stop,
    )
    _log_orchestrator_event(
        event="handle_risk_management_signal",
        input_data=f"symbol={_normalize(risk_symbol)} avg_entry_price={avg_entry_price} mark_price={mark_price}",
        decision="evaluate_pnl_and_plan_risk_management_action",
        result=result.action_code,
        state_before=_state_label(before),
        state_after=_state_label(current),
        failure_reason=result.reason_code if not result.actionable else "-",
        loop_label=loop_label,
        pnl_branch=result.pnl_branch,
    )
    return current, result


def process_telegram_message(
    runtime: AutoTradeRuntime,
    *,
    channel_id: int,
    message_id: int,
    message_text: str,
    received_at_local: int,
    exchange_info: Optional[Mapping[str, Any]] = None,
    candles: Optional[Sequence[Mapping[str, Any]]] = None,
    entry_mode: EntryMode = "AGGRESSIVE",
    risk_context: Optional[Mapping[str, Any]] = None,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, TelegramMessageProcessResult]:
    if int(channel_id) == int(runtime.settings.entry_signal_channel_id):
        if exchange_info is None or candles is None:
            result = TelegramMessageProcessResult(
                handled=False,
                message_type="LEADING",
                reason_code="LEADING_SIGNAL_CONTEXT_MISSING",
                failure_reason="exchange_info_or_candles_missing",
            )
            _log_orchestrator_event(
                event="process_telegram_message",
                input_data=f"channel_id={channel_id} message_id={message_id}",
                decision="route_to_leading_signal_handler",
                result="rejected",
                state_before=_state_label(runtime),
                state_after=_state_label(runtime),
                failure_reason=result.reason_code,
                loop_label=loop_label,
            )
            return runtime, result
        updated, leading_result = handle_leading_market_signal(
            runtime,
            channel_id=channel_id,
            message_id=message_id,
            message_text=message_text,
            received_at_local=received_at_local,
            exchange_info=exchange_info,
            candles=candles,
            entry_mode=entry_mode,
            loop_label=loop_label,
        )
        result = TelegramMessageProcessResult(
            handled=leading_result.accepted,
            message_type="LEADING",
            reason_code=leading_result.reason_code,
            failure_reason=leading_result.failure_reason,
            symbol=leading_result.symbol,
        )
        return updated, result

    if int(channel_id) == int(runtime.settings.risk_signal_channel_id):
        ctx = dict(risk_context or {})
        required_keys = (
            "avg_entry_price",
            "mark_price",
            "has_position",
            "has_open_entry_order",
            "has_tp_order",
            "second_entry_fully_filled",
        )
        missing = [key for key in required_keys if key not in ctx]
        if missing:
            result = TelegramMessageProcessResult(
                handled=False,
                message_type="RISK",
                reason_code="RISK_SIGNAL_CONTEXT_MISSING",
                failure_reason=",".join(missing),
            )
            _log_orchestrator_event(
                event="process_telegram_message",
                input_data=f"channel_id={channel_id} message_id={message_id}",
                decision="route_to_risk_signal_handler",
                result="rejected",
                state_before=_state_label(runtime),
                state_after=_state_label(runtime),
                failure_reason=result.reason_code,
                loop_label=loop_label,
                missing_keys=",".join(missing),
            )
            return runtime, result
        exchange_info_for_risk = ctx.get("exchange_info")
        exchange_info_error_for_risk = ctx.get("exchange_info_error")
        normalized_exchange_info_error = (
            str(exchange_info_error_for_risk)
            if exchange_info_error_for_risk not in (None, "")
            else None
        )
        updated, risk_result = handle_risk_management_signal(
            runtime,
            channel_id=channel_id,
            message_id=message_id,
            message_text=message_text,
            avg_entry_price=float(ctx["avg_entry_price"]),
            mark_price=float(ctx["mark_price"]),
            has_position=bool(ctx["has_position"]),
            has_open_entry_order=bool(ctx["has_open_entry_order"]),
            has_tp_order=bool(ctx["has_tp_order"]),
            second_entry_fully_filled=bool(ctx["second_entry_fully_filled"]),
            exchange_info=(
                exchange_info_for_risk
                if isinstance(exchange_info_for_risk, Mapping)
                else None
            ),
            exchange_info_error=normalized_exchange_info_error,
            loop_label=loop_label,
        )
        result = TelegramMessageProcessResult(
            handled=risk_result.accepted,
            message_type="RISK",
            reason_code=risk_result.reason_code,
            failure_reason=risk_result.failure_reason,
            symbol=risk_result.symbol,
            action_code=risk_result.action_code,
            pnl_branch=risk_result.pnl_branch,
            reset_state=risk_result.reset_state,
            cancel_entry_orders=risk_result.cancel_entry_orders,
            submit_market_exit=risk_result.submit_market_exit,
            submit_breakeven_stop_market=risk_result.submit_breakeven_stop_market,
            create_tp_limit_once=risk_result.create_tp_limit_once,
        )
        return updated, result

    result = TelegramMessageProcessResult(
        handled=False,
        message_type="UNSUPPORTED",
        reason_code="UNSUPPORTED_CHANNEL_ID",
        failure_reason=f"channel_id={channel_id}",
    )
    _log_orchestrator_event(
        event="process_telegram_message",
        input_data=f"channel_id={channel_id} message_id={message_id}",
        decision="route_by_configured_channel_ids",
        result="ignored",
        state_before=_state_label(runtime),
        state_after=_state_label(runtime),
        failure_reason=result.reason_code,
        loop_label=loop_label,
    )
    return runtime, result


def apply_price_source_and_guard(
    runtime: AutoTradeRuntime,
    *,
    ws_prices: Mapping[str, float],
    rest_prices: Mapping[str, float],
    received_at: int,
    ws_received_at: Optional[int] = None,
    rest_received_at: Optional[int] = None,
    now: int,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, PriceGuardProcessResult]:
    current = runtime
    ws_timestamp = int(ws_received_at) if ws_received_at is not None else int(received_at)
    rest_timestamp = int(rest_received_at) if rest_received_at is not None else int(received_at)
    for symbol, price in ws_prices.items():
        ws_update = record_ws_mark_price_with_logging(
            current.price_state,
            symbol=symbol,
            mark_price=float(price),
            received_at=ws_timestamp,
            loop_label=loop_label,
        )
        current = replace(current, price_state=ws_update.current)
    for symbol, price in rest_prices.items():
        rest_update = record_rest_mark_price_with_logging(
            current.price_state,
            symbol=symbol,
            mark_price=float(price),
            received_at=rest_timestamp,
            loop_label=loop_label,
        )
        current = replace(current, price_state=rest_update.current)

    guard = apply_price_source_guard_with_logging(
        current.global_state,
        current.price_state,
        now=now,
        stale_mark_price_seconds=current.settings.stale_mark_price_seconds,
        has_monitoring=current.symbol_state == "MONITORING",
        loop_label=loop_label,
    )
    current = replace(current, global_state=guard.global_transition.current)
    result = PriceGuardProcessResult(
        success=True,
        reason_code=guard.decision.reason_code,
        failure_reason="-",
        safety_action=guard.decision.action,
        safety_locked=guard.global_transition.current.safety_locked,
        global_blocked=guard.global_transition.current.global_blocked,
    )
    _log_orchestrator_event(
        event="apply_price_source_and_guard",
        input_data=(
            f"ws_count={len(ws_prices)} rest_count={len(rest_prices)} "
            f"received_at={received_at} ws_received_at={ws_timestamp} "
            f"rest_received_at={rest_timestamp} now={now}"
        ),
        decision="record_prices_then_apply_safety_guard",
        result=result.reason_code,
        state_before=_state_label(runtime),
        state_after=_state_label(current),
        failure_reason="-",
        loop_label=loop_label,
    )
    return current, result


def execute_oco_cancel_flow(
    runtime: AutoTradeRuntime,
    *,
    symbol: str,
    filled_order_id: int,
    open_exit_order_ids: Sequence[int],
    cancel_call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, OcoCancelProcessResult]:
    plan = plan_oco_mutual_cancel_with_logging(
        filled_order_id=filled_order_id,
        open_exit_order_ids=open_exit_order_ids,
        loop_label=loop_label,
    )
    if not plan.has_targets:
        result = OcoCancelProcessResult(
            success=True,
            reason_code=plan.reason_code,
            failure_reason="-",
            lock_new_orders=False,
        )
        _log_orchestrator_event(
            event="execute_oco_cancel_flow",
            input_data=f"symbol={_normalize(symbol)} filled_order_id={filled_order_id}",
            decision="plan_oco_and_cancel_remaining_orders",
            result=plan.reason_code,
            state_before=_state_label(runtime),
            state_after=_state_label(runtime),
            failure_reason="-",
            loop_label=loop_label,
        )
        return runtime, result

    execution = execute_oco_mutual_cancel_with_logging(
        symbol=symbol,
        cancel_order_ids=plan.cancel_target_order_ids,
        cancel_call=cancel_call,
        retry_policy=retry_policy,
        loop_label=loop_label,
    )
    current = replace(runtime, new_orders_locked=runtime.new_orders_locked or execution.lock_new_orders)
    result = OcoCancelProcessResult(
        success=execution.success,
        reason_code=execution.reason_code,
        failure_reason=execution.reason_code if not execution.success else "-",
        lock_new_orders=execution.lock_new_orders,
    )
    _log_orchestrator_event(
        event="execute_oco_cancel_flow",
        input_data=(
            f"symbol={_normalize(symbol)} filled_order_id={filled_order_id} "
            f"cancel_target_count={len(plan.cancel_target_order_ids)}"
        ),
        decision="execute_oco_cancel_targets_with_retry",
        result=result.reason_code,
        state_before=_state_label(runtime),
        state_after=_state_label(current),
        failure_reason=result.failure_reason if not result.success else "-",
        loop_label=loop_label,
    )
    return current, result


def update_exit_partial_and_check_five_second(
    runtime: AutoTradeRuntime,
    *,
    is_exit_order: bool,
    order_id: int,
    order_status: str,
    executed_qty: float,
    updated_at: int,
    now: int,
    risk_market_exit_in_same_loop: bool,
    loop_label: str = "loop",
) -> tuple[AutoTradeRuntime, ExitFiveSecondProcessResult]:
    update_result = update_exit_partial_fill_tracker_with_logging(
        runtime.exit_partial_tracker,
        is_exit_order=is_exit_order,
        order_id=order_id,
        order_status=order_status,  # type: ignore[arg-type]
        executed_qty=executed_qty,
        updated_at=updated_at,
        loop_label=loop_label,
    )
    current = replace(runtime, exit_partial_tracker=update_result.current)
    decision = evaluate_exit_five_second_rule_with_logging(
        current.exit_partial_tracker,
        is_exit_order=is_exit_order,
        now=now,
        stall_seconds=5,
        risk_market_exit_in_same_loop=risk_market_exit_in_same_loop,
        loop_label=loop_label,
    )
    result = ExitFiveSecondProcessResult(
        decision=decision,
        reason_code=decision.reason_code,
    )
    _log_orchestrator_event(
        event="update_exit_partial_and_check_five_second",
        input_data=(
            f"is_exit_order={is_exit_order} order_id={order_id} order_status={order_status} "
            f"executed_qty={executed_qty} updated_at={updated_at} now={now}"
        ),
        decision="update_partial_tracker_and_apply_5s_rule",
        result=decision.reason_code,
        state_before=_state_label(runtime),
        state_after=_state_label(current),
        failure_reason="-" if not decision.should_force_market_exit else "-",
        loop_label=loop_label,
        should_force_market_exit=decision.should_force_market_exit,
    )
    return current, result
