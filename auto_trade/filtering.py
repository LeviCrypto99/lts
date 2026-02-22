from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .event_logging import StructuredLogEvent, log_structured_event
from .filtering_models import CommonFilterResult

FILTER_PASS = "FILTER_PASS"
_KST_TZ = ZoneInfo("Asia/Seoul")
_ENTRY_BLOCK_START_MINUTE_OF_DAY = (8 * 60) + 30
_ENTRY_BLOCK_END_MINUTE_OF_DAY = (10 * 60) + 1
_ENTRY_BLOCK_WINDOW_LABEL = "08:30~10:00"
_ENTRY_ALLOW_FROM_LABEL = "10:01"

_CATEGORY_EXCLUDED_KEYWORDS = [
    "meme",
    "defi",
    "pump.fun",
    "dex",
    "탈중앙화 거래소",
    "binance alpha spotlight",
]


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_direction(value: str) -> str:
    return (value or "").strip()


def _normalized_category_lower(category: str) -> str:
    return (category or "").strip().lower()


def _normalized_category_compact(category: str) -> str:
    # Normalize whitespace variants so "정보 없음" and "정보없음" are treated equally.
    return "".join(_normalized_category_lower(category).split())


def _match_excluded_keyword(category: str) -> Optional[str]:
    lowered = _normalized_category_lower(category)
    for keyword in _CATEGORY_EXCLUDED_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def _normalize_epoch_seconds(value: Any) -> Optional[int]:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resolve_signal_time_kst(signal_received_at_local: Optional[int]) -> datetime:
    epoch_seconds = _normalize_epoch_seconds(signal_received_at_local)
    if epoch_seconds is None:
        epoch_seconds = int(time.time())
    return datetime.fromtimestamp(epoch_seconds, tz=_KST_TZ)


def _evaluate_kst_entry_block_window(signal_received_at_local: Optional[int]) -> tuple[bool, str]:
    signal_time_kst = _resolve_signal_time_kst(signal_received_at_local)
    minute_of_day = int(signal_time_kst.hour) * 60 + int(signal_time_kst.minute)
    blocked = _ENTRY_BLOCK_START_MINUTE_OF_DAY <= minute_of_day < _ENTRY_BLOCK_END_MINUTE_OF_DAY
    kst_time = signal_time_kst.strftime("%H:%M:%S")
    if blocked:
        return (
            True,
            (
                f"kst_time={kst_time} is within blocked entry window "
                f"{_ENTRY_BLOCK_WINDOW_LABEL}; allow from {_ENTRY_ALLOW_FROM_LABEL}"
            ),
        )
    return (
        False,
        f"kst_time={kst_time} is outside blocked entry window {_ENTRY_BLOCK_WINDOW_LABEL}",
    )


def evaluate_common_filters(
    *,
    category: str,
    ranking_direction: str,
    ranking_position: int,
    funding_rate_pct: float,
    signal_received_at_local: Optional[int] = None,
) -> CommonFilterResult:
    blocked_by_time, blocked_reason = _evaluate_kst_entry_block_window(signal_received_at_local)
    if blocked_by_time:
        return CommonFilterResult(
            passed=False,
            reason_code="KST_MORNING_ENTRY_BLOCK",
            failure_reason=blocked_reason,
        )

    matched_keyword = _match_excluded_keyword(category)
    if matched_keyword is not None:
        return CommonFilterResult(
            passed=False,
            reason_code="CATEGORY_EXCLUDED_KEYWORD",
            failure_reason=f"matched excluded keyword: {matched_keyword}",
        )

    normalized_category = _normalized_category_lower(category)
    normalized_category_compact = _normalized_category_compact(category)
    if normalized_category_compact == "정보없음":
        return CommonFilterResult(
            passed=False,
            reason_code="CATEGORY_UNKNOWN",
            failure_reason=f"category is 정보없음 variant: {normalized_category or '-'}",
        )

    direction = _normalize_direction(ranking_direction)
    if direction == "상승":
        if 1 <= int(ranking_position) <= 5:
            return CommonFilterResult(
                passed=False,
                reason_code="RANKING_TOP5_RISE",
                failure_reason="rising rank is in top 5",
            )
    elif direction == "하락":
        pass
    else:
        return CommonFilterResult(
            passed=False,
            reason_code="RANKING_DIRECTION_INVALID",
            failure_reason=f"unsupported ranking direction: {direction or '-'}",
        )

    if float(funding_rate_pct) <= -0.1:
        return CommonFilterResult(
            passed=False,
            reason_code="FUNDING_TOO_NEGATIVE",
            failure_reason=f"funding_rate_pct={funding_rate_pct} <= -0.1",
        )

    return CommonFilterResult(
        passed=True,
        reason_code=FILTER_PASS,
        failure_reason="-",
    )


def evaluate_common_filters_with_logging(
    *,
    category: str,
    ranking_direction: str,
    ranking_position: int,
    funding_rate_pct: float,
    signal_received_at_local: Optional[int] = None,
    symbol: Optional[str] = None,
) -> CommonFilterResult:
    signal_time_kst = _resolve_signal_time_kst(signal_received_at_local).strftime("%H:%M:%S")
    result = evaluate_common_filters(
        category=category,
        ranking_direction=ranking_direction,
        ranking_position=ranking_position,
        funding_rate_pct=funding_rate_pct,
        signal_received_at_local=signal_received_at_local,
    )
    if result.passed:
        log_structured_event(
            StructuredLogEvent(
                component="common_filter",
                event="evaluate_common_filters",
                input_data=(
                    f"category={_normalize(category)} direction={_normalize(ranking_direction)} "
                    f"rank={ranking_position} funding_rate_pct={funding_rate_pct} "
                    f"signal_received_at_local={_normalize(signal_received_at_local)} "
                    f"signal_time_kst={signal_time_kst}"
                ),
                decision="apply_time_category_ranking_funding_rules",
                result="pass",
                state_before="filtering",
                state_after="passed",
                failure_reason="-",
            ),
            symbol=symbol if symbol is not None else "-",
            reason_code=result.reason_code,
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="common_filter",
            event="evaluate_common_filters",
            input_data=(
                f"category={_normalize(category)} direction={_normalize(ranking_direction)} "
                f"rank={ranking_position} funding_rate_pct={funding_rate_pct} "
                f"signal_received_at_local={_normalize(signal_received_at_local)} "
                f"signal_time_kst={signal_time_kst}"
            ),
            decision="apply_time_category_ranking_funding_rules",
            result="reject",
            state_before="filtering",
            state_after="rejected",
            failure_reason=result.reason_code,
        ),
        symbol=symbol if symbol is not None else "-",
        detail=result.failure_reason,
        reason_code=result.reason_code,
    )
    return result
