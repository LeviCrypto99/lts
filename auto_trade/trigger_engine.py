from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence

from .event_logging import StructuredLogEvent, log_structured_event
from .trigger_models import SymbolTriggerEvaluation, TriggerCandidate, TriggerKind, TriggerLoopResult

TRIGGER_BUFFER_RATIO_DEFAULT = 0.005


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _validate_positive_price(value: float) -> bool:
    return math.isfinite(value) and value > 0


def compute_trigger_threshold(
    trigger_kind: TriggerKind,
    target_price: float,
    *,
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
) -> float:
    if trigger_kind in ("FIRST_ENTRY", "SECOND_ENTRY"):
        return target_price * (1.0 - trigger_buffer_ratio)
    if trigger_kind == "TP":
        return target_price * (1.0 + trigger_buffer_ratio)
    if trigger_kind == "BREAKEVEN":
        return target_price * (1.0 + trigger_buffer_ratio)
    raise ValueError(f"unsupported trigger kind: {trigger_kind}")


def is_trigger_satisfied(
    trigger_kind: TriggerKind,
    *,
    current_mark_price: float,
    target_price: float,
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
) -> bool:
    threshold = compute_trigger_threshold(
        trigger_kind,
        target_price,
        trigger_buffer_ratio=trigger_buffer_ratio,
    )
    if trigger_kind in ("FIRST_ENTRY", "SECOND_ENTRY"):
        return current_mark_price >= threshold
    if trigger_kind == "TP":
        return current_mark_price <= threshold
    if trigger_kind == "BREAKEVEN":
        return current_mark_price >= threshold
    return False


def evaluate_symbol_trigger(
    candidate: TriggerCandidate,
    *,
    current_mark_price: Optional[float],
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
) -> SymbolTriggerEvaluation:
    symbol = _normalize_symbol(candidate.symbol)
    threshold = compute_trigger_threshold(
        candidate.trigger_kind,
        candidate.target_price,
        trigger_buffer_ratio=trigger_buffer_ratio,
    )

    if not _validate_positive_price(candidate.target_price):
        return SymbolTriggerEvaluation(
            symbol=symbol,
            trigger_kind=candidate.trigger_kind,
            target_price=candidate.target_price,
            threshold_price=threshold,
            current_mark_price=current_mark_price,
            satisfied=False,
            reason_code="INVALID_TARGET_PRICE",
        )
    if current_mark_price is None:
        return SymbolTriggerEvaluation(
            symbol=symbol,
            trigger_kind=candidate.trigger_kind,
            target_price=candidate.target_price,
            threshold_price=threshold,
            current_mark_price=None,
            satisfied=False,
            reason_code="MARK_PRICE_MISSING",
        )
    if not _validate_positive_price(current_mark_price):
        return SymbolTriggerEvaluation(
            symbol=symbol,
            trigger_kind=candidate.trigger_kind,
            target_price=candidate.target_price,
            threshold_price=threshold,
            current_mark_price=current_mark_price,
            satisfied=False,
            reason_code="INVALID_MARK_PRICE",
        )

    satisfied = is_trigger_satisfied(
        candidate.trigger_kind,
        current_mark_price=current_mark_price,
        target_price=candidate.target_price,
        trigger_buffer_ratio=trigger_buffer_ratio,
    )
    return SymbolTriggerEvaluation(
        symbol=symbol,
        trigger_kind=candidate.trigger_kind,
        target_price=candidate.target_price,
        threshold_price=threshold,
        current_mark_price=current_mark_price,
        satisfied=satisfied,
        reason_code="TRIGGER_SATISFIED" if satisfied else "TRIGGER_NOT_REACHED",
    )


def _select_tiebreak_winner(candidates: Sequence[TriggerCandidate]) -> tuple[TriggerCandidate, str]:
    if len(candidates) == 1:
        return candidates[0], "SINGLE_TRIGGER"

    # Deterministic ordering:
    # 1) latest received_at_local wins
    # 2) if equal, larger message_id wins
    # 3) fallback lexicographic symbol for complete determinism
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            int(item.received_at_local),
            int(item.message_id),
            _normalize_symbol(item.symbol),
        ),
        reverse=True,
    )
    winner = sorted_candidates[0]
    if any(item.received_at_local != winner.received_at_local for item in sorted_candidates[1:]):
        return winner, "MULTI_TRIGGER_TIEBREAK_RECEIVED_AT"
    if any(item.message_id != winner.message_id for item in sorted_candidates[1:]):
        return winner, "MULTI_TRIGGER_TIEBREAK_MESSAGE_ID"
    return winner, "MULTI_TRIGGER_TIEBREAK_FALLBACK_SYMBOL"


def evaluate_trigger_loop(
    candidates: Sequence[TriggerCandidate],
    mark_prices: Mapping[str, float],
    *,
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
) -> TriggerLoopResult:
    evaluations: dict[str, SymbolTriggerEvaluation] = {}
    satisfied_candidates: list[TriggerCandidate] = []

    for candidate in candidates:
        symbol = _normalize_symbol(candidate.symbol)
        current_price = mark_prices.get(symbol)
        evaluation = evaluate_symbol_trigger(
            candidate,
            current_mark_price=current_price,
            trigger_buffer_ratio=trigger_buffer_ratio,
        )
        evaluations[symbol] = evaluation
        if evaluation.satisfied:
            satisfied_candidates.append(candidate)

    if not satisfied_candidates:
        return TriggerLoopResult(
            selected_candidate=None,
            reason_code="NO_TRIGGER_IN_LOOP",
            satisfied_symbols=[],
            dropped_symbols=[],
            evaluations=evaluations,
        )

    winner, reason_code = _select_tiebreak_winner(satisfied_candidates)
    winner_symbol = _normalize_symbol(winner.symbol)
    dropped = [
        _normalize_symbol(item.symbol)
        for item in satisfied_candidates
        if _normalize_symbol(item.symbol) != winner_symbol
    ]

    return TriggerLoopResult(
        selected_candidate=winner,
        reason_code=reason_code,
        satisfied_symbols=[_normalize_symbol(item.symbol) for item in satisfied_candidates],
        dropped_symbols=dropped,
        evaluations=evaluations,
    )


def evaluate_trigger_loop_with_logging(
    candidates: Sequence[TriggerCandidate],
    mark_prices: Mapping[str, float],
    *,
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
    loop_label: str = "loop",
) -> TriggerLoopResult:
    result = evaluate_trigger_loop(
        candidates,
        mark_prices,
        trigger_buffer_ratio=trigger_buffer_ratio,
    )
    selected_symbol = (
        _normalize_symbol(result.selected_candidate.symbol)
        if result.selected_candidate is not None
        else "-"
    )
    log_structured_event(
        StructuredLogEvent(
            component="trigger_engine",
            event="evaluate_trigger_loop",
            input_data=(
                f"candidate_count={len(candidates)} mark_price_count={len(mark_prices)} "
                f"trigger_buffer_ratio={trigger_buffer_ratio}"
            ),
            decision="evaluate_candidates_and_apply_tiebreak",
            result="selected" if result.selected_candidate is not None else "no_trigger",
            state_before="loop_eval",
            state_after="loop_eval_done",
            failure_reason="-" if result.selected_candidate is not None else result.reason_code,
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        selected_symbol=selected_symbol,
        satisfied_symbols=",".join(result.satisfied_symbols) if result.satisfied_symbols else "-",
        dropped_symbols=",".join(result.dropped_symbols) if result.dropped_symbols else "-",
    )
    return result
