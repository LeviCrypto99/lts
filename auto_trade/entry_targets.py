from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import math
import time

from .entry_target_models import EntryMode, EntryTargetResult
from .event_logging import StructuredLogEvent, log_structured_event

_REFERENCE_SOURCE_AGGRESSIVE = "PREV_CONFIRMED_3M_HIGH_BY_CLOSE_TIME"
_REFERENCE_SOURCE_AGGRESSIVE_FALLBACK = "PREV_CONFIRMED_3M_HIGH_LEN_MINUS_2_FALLBACK"


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _extract_reference_timestamp(candles: list[Mapping[str, Any]], index: int) -> Optional[str]:
    candle = candles[index]
    for column in ("datetime", "close_time", "timestamp"):
        if column in candle:
            return str(candle[column])
    return None


def _to_epoch_millis(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _resolve_reference_index(
    records: list[Mapping[str, Any]],
    *,
    evaluation_time_ms: Optional[int],
) -> tuple[int, bool]:
    # Legacy fallback: treat the latest row as an open candle and use len-2.
    fallback_index = len(records) - 2

    normalized_eval_ms = _to_epoch_millis(evaluation_time_ms)
    effective_eval_ms = normalized_eval_ms if normalized_eval_ms is not None else int(time.time() * 1000)
    last_close_ms = _to_epoch_millis(records[-1].get("close_time"))
    if last_close_ms is None:
        return fallback_index, False
    if last_close_ms <= effective_eval_ms:
        return len(records) - 1, True
    return fallback_index, True


def _to_records(candles: Sequence[Mapping[str, Any]] | Any) -> list[dict[str, Any]]:
    if hasattr(candles, "to_dict"):
        try:
            rows = candles.to_dict("records")
            return [dict(row) for row in rows]
        except Exception:
            pass

    try:
        rows = list(candles)
    except TypeError as exc:
        raise ValueError("candle input is not iterable") from exc

    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("candle rows must be mapping objects")
        record = dict(row)
        for column in ("high", "low", "close"):
            if column not in record:
                raise ValueError(f"missing candle columns: {column}")
            try:
                record[column] = float(record[column])
            except (TypeError, ValueError) as exc:
                raise ValueError("candle columns contain non-numeric values") from exc
        records.append(record)
    return records


def calculate_entry_target(
    *,
    mode: EntryMode,
    candles: Sequence[Mapping[str, Any]] | Any,
    atr_length: int = 3,
    atr_multiplier: float = 1.0,
    evaluation_time_ms: Optional[int] = None,
) -> EntryTargetResult:
    try:
        records = _to_records(candles)
    except ValueError as exc:
        return EntryTargetResult(
            ok=False,
            mode=mode,
            target_price=None,
            reference_index=None,
            reference_source=None,
            reference_timestamp=None,
            reason_code="INVALID_CANDLE_INPUT",
            failure_reason=str(exc),
        )

    if len(records) < 2:
        return EntryTargetResult(
            ok=False,
            mode=mode,
            target_price=None,
            reference_index=None,
            reference_source=None,
            reference_timestamp=None,
            reason_code="INSUFFICIENT_CANDLES",
            failure_reason="need at least 2 candles for previous confirmed 3m candle",
        )

    reference_index, resolved_by_close_time = _resolve_reference_index(
        records,
        evaluation_time_ms=evaluation_time_ms,
    )
    reference_timestamp = _extract_reference_timestamp(records, reference_index)
    aggressive_reference_source = (
        _REFERENCE_SOURCE_AGGRESSIVE
        if resolved_by_close_time
        else _REFERENCE_SOURCE_AGGRESSIVE_FALLBACK
    )

    if mode not in ("AGGRESSIVE", "CONSERVATIVE"):
        return EntryTargetResult(
            ok=False,
            mode=mode,
            target_price=None,
            reference_index=None,
            reference_source=None,
            reference_timestamp=None,
            reason_code="INVALID_MODE",
            failure_reason=f"unsupported mode: {mode}",
        )

    target = float(records[reference_index]["high"])
    if not math.isfinite(target):
        return EntryTargetResult(
            ok=False,
            mode=mode,
            target_price=None,
            reference_index=reference_index,
            reference_source=aggressive_reference_source,
            reference_timestamp=reference_timestamp,
            reason_code="TARGET_NOT_FINITE",
            failure_reason="aggressive baseline target is not finite",
        )
    return EntryTargetResult(
        ok=True,
        mode=mode,
        target_price=target,
        reference_index=reference_index,
        reference_source=aggressive_reference_source,
        reference_timestamp=reference_timestamp,
        reason_code="TARGET_READY",
        failure_reason="-",
    )


def calculate_entry_target_with_logging(
    *,
    mode: EntryMode,
    candles: Sequence[Mapping[str, Any]] | Any,
    atr_length: int = 3,
    atr_multiplier: float = 1.0,
    symbol: Optional[str] = None,
    evaluation_time_ms: Optional[int] = None,
) -> EntryTargetResult:
    result = calculate_entry_target(
        mode=mode,
        candles=candles,
        atr_length=atr_length,
        atr_multiplier=atr_multiplier,
        evaluation_time_ms=evaluation_time_ms,
    )
    candle_count = len(candles) if hasattr(candles, "__len__") else -1
    eval_time_text = evaluation_time_ms if evaluation_time_ms is not None else "-"

    if result.ok:
        log_structured_event(
            StructuredLogEvent(
                component="entry_target",
                event="calculate_entry_target",
                input_data=(
                    f"mode={_normalize(mode)} candle_count={candle_count} "
                    f"atr_length={atr_length} atr_multiplier={atr_multiplier} "
                    f"evaluation_time_ms={eval_time_text}"
                ),
                decision="select_prev_confirmed_3m_reference_and_compute_target",
                result=f"target_ready price={result.target_price}",
                state_before="target_pending",
                state_after="target_ready",
                failure_reason="-",
            ),
            symbol=symbol if symbol is not None else "-",
            reference_source=result.reference_source if result.reference_source is not None else "-",
            reference_timestamp=result.reference_timestamp if result.reference_timestamp is not None else "-",
            reference_index=result.reference_index if result.reference_index is not None else "-",
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="entry_target",
            event="calculate_entry_target",
            input_data=(
                f"mode={_normalize(mode)} candle_count={candle_count} "
                f"atr_length={atr_length} atr_multiplier={atr_multiplier} "
                f"evaluation_time_ms={eval_time_text}"
            ),
            decision="select_prev_confirmed_3m_reference_and_compute_target",
            result="target_rejected",
            state_before="target_pending",
            state_after="target_rejected",
            failure_reason=result.reason_code,
        ),
        symbol=symbol if symbol is not None else "-",
        detail=result.failure_reason,
        reason_code=result.reason_code,
        reference_source=result.reference_source if result.reference_source is not None else "-",
        reference_timestamp=result.reference_timestamp if result.reference_timestamp is not None else "-",
        reference_index=result.reference_index if result.reference_index is not None else "-",
    )
    return result
