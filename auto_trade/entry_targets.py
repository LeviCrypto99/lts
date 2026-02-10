from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import math

from indicators import calculate_atr_bands

from .entry_target_models import EntryMode, EntryTargetResult
from .event_logging import StructuredLogEvent, log_structured_event

_REFERENCE_SOURCE_AGGRESSIVE = "PREV_CONFIRMED_3M_HIGH"
_REFERENCE_SOURCE_CONSERVATIVE = "PREV_CONFIRMED_3M_ATR_UPPER"


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _extract_reference_timestamp(candles: list[Mapping[str, Any]], index: int) -> Optional[str]:
    candle = candles[index]
    for column in ("datetime", "close_time", "timestamp"):
        if column in candle:
            return str(candle[column])
    return None


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

    reference_index = len(records) - 2
    reference_timestamp = _extract_reference_timestamp(records, reference_index)

    if mode == "AGGRESSIVE":
        target = float(records[reference_index]["high"])
        if not math.isfinite(target):
            return EntryTargetResult(
                ok=False,
                mode=mode,
                target_price=None,
                reference_index=reference_index,
                reference_source=_REFERENCE_SOURCE_AGGRESSIVE,
                reference_timestamp=reference_timestamp,
                reason_code="TARGET_NOT_FINITE",
                failure_reason="aggressive target is not finite",
            )
        return EntryTargetResult(
            ok=True,
            mode=mode,
            target_price=target,
            reference_index=reference_index,
            reference_source=_REFERENCE_SOURCE_AGGRESSIVE,
            reference_timestamp=reference_timestamp,
            reason_code="TARGET_READY",
            failure_reason="-",
        )

    if mode == "CONSERVATIVE":
        if len(records) < atr_length:
            return EntryTargetResult(
                ok=False,
                mode=mode,
                target_price=None,
                reference_index=reference_index,
                reference_source=_REFERENCE_SOURCE_CONSERVATIVE,
                reference_timestamp=reference_timestamp,
                reason_code="INSUFFICIENT_CANDLES_FOR_ATR",
                failure_reason=f"need at least {atr_length} candles for ATR",
            )
        upper, _, _ = calculate_atr_bands(records, length=atr_length, multiplier=atr_multiplier)
        target = float(upper[reference_index])
        if not math.isfinite(target):
            return EntryTargetResult(
                ok=False,
                mode=mode,
                target_price=None,
                reference_index=reference_index,
                reference_source=_REFERENCE_SOURCE_CONSERVATIVE,
                reference_timestamp=reference_timestamp,
                reason_code="TARGET_NOT_FINITE",
                failure_reason="conservative target is not finite",
            )
        return EntryTargetResult(
            ok=True,
            mode=mode,
            target_price=target,
            reference_index=reference_index,
            reference_source=_REFERENCE_SOURCE_CONSERVATIVE,
            reference_timestamp=reference_timestamp,
            reason_code="TARGET_READY",
            failure_reason="-",
        )

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


def calculate_entry_target_with_logging(
    *,
    mode: EntryMode,
    candles: Sequence[Mapping[str, Any]] | Any,
    atr_length: int = 3,
    atr_multiplier: float = 1.0,
    symbol: Optional[str] = None,
) -> EntryTargetResult:
    result = calculate_entry_target(
        mode=mode,
        candles=candles,
        atr_length=atr_length,
        atr_multiplier=atr_multiplier,
    )
    candle_count = len(candles) if hasattr(candles, "__len__") else -1

    if result.ok:
        log_structured_event(
            StructuredLogEvent(
                component="entry_target",
                event="calculate_entry_target",
                input_data=(
                    f"mode={_normalize(mode)} candle_count={candle_count} "
                    f"atr_length={atr_length} atr_multiplier={atr_multiplier}"
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
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="entry_target",
            event="calculate_entry_target",
            input_data=(
                f"mode={_normalize(mode)} candle_count={candle_count} "
                f"atr_length={atr_length} atr_multiplier={atr_multiplier}"
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
    )
    return result
