from __future__ import annotations

from typing import Any

from .event_logging import StructuredLogEvent, log_structured_event
from .state_machine_models import (
    GlobalState,
    GlobalTransitionResult,
    SymbolEvent,
    SymbolState,
    SymbolTransitionResult,
)

_SYMBOL_TRANSITIONS: dict[tuple[SymbolState, SymbolEvent], SymbolState] = {
    ("IDLE", "START_MONITORING"): "MONITORING",
    ("IDLE", "RESET"): "IDLE",
    ("MONITORING", "SUBMIT_ENTRY_ORDER"): "ENTRY_ORDER",
    ("MONITORING", "RESET"): "IDLE",
    ("ENTRY_ORDER", "PARTIAL_FILL"): "ENTRY_ORDER",
    ("ENTRY_ORDER", "FIRST_ENTRY_FILLED"): "PHASE1",
    ("ENTRY_ORDER", "CANCEL_ENTRY_NO_POSITION"): "IDLE",
    ("ENTRY_ORDER", "RESET"): "IDLE",
    ("PHASE1", "SUBMIT_SECOND_ENTRY_ORDER"): "PHASE1",
    ("PHASE1", "SECOND_ENTRY_PARTIAL_OR_FILLED"): "PHASE2",
    ("PHASE1", "RESET"): "IDLE",
    ("PHASE2", "RESET"): "IDLE",
}

_VALID_SYMBOL_STATES: set[SymbolState] = {"IDLE", "MONITORING", "ENTRY_ORDER", "PHASE1", "PHASE2"}


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _global_transition_reason(previous: GlobalState, current: GlobalState) -> str:
    if previous.safety_locked != current.safety_locked:
        return "SAFETY_LOCK_CHANGED"
    if previous.entry_state != current.entry_state:
        return "ENTRY_LOCK_CHANGED"
    if previous.global_mode != current.global_mode:
        return "GLOBAL_MODE_CHANGED"
    return "NO_CHANGE"


def update_account_activity(
    state: GlobalState,
    *,
    has_any_position: bool,
    has_any_open_order: bool,
) -> GlobalTransitionResult:
    current = GlobalState(
        has_any_position=bool(has_any_position),
        has_any_open_order=bool(has_any_open_order),
        safety_locked=state.safety_locked,
    )
    changed = current != state
    return GlobalTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code=_global_transition_reason(state, current),
    )


def set_safety_lock(state: GlobalState, *, enabled: bool) -> GlobalTransitionResult:
    current = GlobalState(
        has_any_position=state.has_any_position,
        has_any_open_order=state.has_any_open_order,
        safety_locked=bool(enabled),
    )
    changed = current != state
    return GlobalTransitionResult(
        previous=state,
        current=current,
        changed=changed,
        reason_code=_global_transition_reason(state, current),
    )


def apply_symbol_event(current_state: SymbolState, event: SymbolEvent) -> SymbolTransitionResult:
    if current_state not in _VALID_SYMBOL_STATES:
        return SymbolTransitionResult(
            previous_state=current_state,
            current_state=current_state,
            event=event,
            accepted=False,
            changed=False,
            reason_code="INVALID_STATE",
        )

    next_state = _SYMBOL_TRANSITIONS.get((current_state, event))
    if next_state is None:
        return SymbolTransitionResult(
            previous_state=current_state,
            current_state=current_state,
            event=event,
            accepted=False,
            changed=False,
            reason_code="INVALID_TRANSITION",
        )

    changed = next_state != current_state
    return SymbolTransitionResult(
        previous_state=current_state,
        current_state=next_state,
        event=event,
        accepted=True,
        changed=changed,
        reason_code="TRANSITION_APPLIED" if changed else "NO_STATE_CHANGE",
    )


def update_account_activity_with_logging(
    state: GlobalState,
    *,
    has_any_position: bool,
    has_any_open_order: bool,
) -> GlobalTransitionResult:
    result = update_account_activity(
        state,
        has_any_position=has_any_position,
        has_any_open_order=has_any_open_order,
    )
    log_structured_event(
        StructuredLogEvent(
            component="state_machine_global",
            event="update_account_activity",
            input_data=f"has_any_position={has_any_position} has_any_open_order={has_any_open_order}",
            decision="recompute_entry_lock_from_account_snapshot",
            result="changed" if result.changed else "no_change",
            state_before=f"{result.previous.entry_state}/{result.previous.global_mode}",
            state_after=f"{result.current.entry_state}/{result.current.global_mode}",
            failure_reason="-" if result.reason_code != "NO_CHANGE" else "NO_CHANGE",
        ),
        reason_code=result.reason_code,
        entry_locked=result.current.entry_locked,
        safety_locked=result.current.safety_locked,
        global_blocked=result.current.global_blocked,
    )
    return result


def set_safety_lock_with_logging(state: GlobalState, *, enabled: bool) -> GlobalTransitionResult:
    result = set_safety_lock(state, enabled=enabled)
    log_structured_event(
        StructuredLogEvent(
            component="state_machine_global",
            event="set_safety_lock",
            input_data=f"enabled={enabled}",
            decision="set_or_release_safety_lock",
            result="changed" if result.changed else "no_change",
            state_before=f"{result.previous.entry_state}/{result.previous.global_mode}",
            state_after=f"{result.current.entry_state}/{result.current.global_mode}",
            failure_reason="-" if result.reason_code != "NO_CHANGE" else "NO_CHANGE",
        ),
        reason_code=result.reason_code,
        safety_locked=result.current.safety_locked,
        global_blocked=result.current.global_blocked,
    )
    return result


def apply_symbol_event_with_logging(current_state: SymbolState, event: SymbolEvent) -> SymbolTransitionResult:
    result = apply_symbol_event(current_state, event)
    log_structured_event(
        StructuredLogEvent(
            component="state_machine_symbol",
            event="apply_symbol_event",
            input_data=f"state={_normalize(current_state)} event={_normalize(event)}",
            decision="check_transition_table",
            result="accepted" if result.accepted else "rejected",
            state_before=result.previous_state,
            state_after=result.current_state,
            failure_reason="-" if result.accepted else result.reason_code,
        ),
        reason_code=result.reason_code,
        changed=result.changed,
    )
    return result
