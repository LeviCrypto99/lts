from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from .event_logging import StructuredLogEvent, log_structured_event
from .symbol_mapping_models import MAP_OK, MappingFailureAction, SymbolCandidateResult, SymbolValidationResult

_NON_ALNUM_PATTERN = re.compile(r"[^A-Z0-9]")
_ZERO_WIDTH_CHARS = {
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\u2060",  # WORD JOINER
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE
}

MAPPING_ACTION_IGNORE_KEEP_STATE = "IGNORE_KEEP_STATE"
MAPPING_ACTION_RESET_AND_EXCLUDE = "RESET_AND_EXCLUDE"


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _sanitize_token(value: str) -> str:
    trimmed = (value or "").strip()
    chars = []
    for ch in trimmed:
        if ch in _ZERO_WIDTH_CHARS:
            continue
        code = ord(ch)
        if code < 32 or code == 127:
            continue
        chars.append(ch)
    return "".join(chars).upper()


def map_ticker_to_candidate_symbol(raw_ticker: str) -> SymbolCandidateResult:
    normalized_ticker = _sanitize_token(raw_ticker)
    if not normalized_ticker:
        return SymbolCandidateResult(
            ok=False,
            raw_ticker=raw_ticker,
            normalized_ticker=None,
            candidate_symbol=None,
            failure_code="TICKER_EMPTY",
            failure_reason="ticker is empty after sanitize",
        )
    if _NON_ALNUM_PATTERN.search(normalized_ticker):
        return SymbolCandidateResult(
            ok=False,
            raw_ticker=raw_ticker,
            normalized_ticker=normalized_ticker,
            candidate_symbol=None,
            failure_code="TICKER_INVALID_CHARACTERS",
            failure_reason="ticker contains non-alphanumeric characters",
        )

    candidate_symbol = f"{normalized_ticker}USDT"
    return SymbolCandidateResult(
        ok=True,
        raw_ticker=raw_ticker,
        normalized_ticker=normalized_ticker,
        candidate_symbol=candidate_symbol,
        failure_code=MAP_OK,
        failure_reason="-",
    )


def validate_candidate_symbol_usdt_m(
    candidate_symbol: str,
    exchange_info: Optional[Mapping[str, Any]],
    *,
    exchange_info_error: Optional[str] = None,
) -> SymbolValidationResult:
    symbol = (candidate_symbol or "").strip().upper()
    if not symbol:
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=False,
            status=None,
            failure_code="EMPTY_CANDIDATE_SYMBOL",
            failure_reason="candidate symbol is empty",
        )

    if exchange_info_error:
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=False,
            status=None,
            failure_code="EXCHANGE_INFO_UNAVAILABLE",
            failure_reason=f"exchangeInfo error: {exchange_info_error}",
        )
    if exchange_info is None:
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=False,
            status=None,
            failure_code="EXCHANGE_INFO_UNAVAILABLE",
            failure_reason="exchangeInfo is missing",
        )

    symbols = exchange_info.get("symbols")
    if not isinstance(symbols, list):
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=False,
            status=None,
            failure_code="EXCHANGE_INFO_INVALID",
            failure_reason="symbols list is missing in exchangeInfo",
        )

    found_record = None
    for item in symbols:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("symbol", "")).upper() == symbol:
            found_record = item
            break

    if found_record is None:
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=False,
            status=None,
            failure_code="SYMBOL_NOT_FOUND",
            failure_reason="symbol not found in exchangeInfo",
        )

    status = str(found_record.get("status", "")).upper() or None
    quote_asset = str(found_record.get("quoteAsset", "")).upper()
    contract_type = str(found_record.get("contractType", "")).upper()

    if quote_asset != "USDT":
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=True,
            status=status,
            failure_code="SYMBOL_NOT_USDT_M",
            failure_reason=f"quoteAsset is {quote_asset or '-'}",
        )

    if contract_type and contract_type != "PERPETUAL":
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=True,
            status=status,
            failure_code="SYMBOL_NOT_PERPETUAL",
            failure_reason=f"contractType is {contract_type}",
        )

    if status != "TRADING":
        return SymbolValidationResult(
            ok=False,
            symbol=symbol,
            exists=True,
            status=status,
            failure_code="SYMBOL_NOT_TRADING",
            failure_reason=f"status is {status or '-'}",
        )

    return SymbolValidationResult(
        ok=True,
        symbol=symbol,
        exists=True,
        status=status,
        failure_code=MAP_OK,
        failure_reason="-",
    )


def resolve_mapping_failure_action(
    *,
    is_monitoring: bool,
    has_open_order: bool,
    has_position: bool,
) -> MappingFailureAction:
    if is_monitoring or has_open_order or has_position:
        return MappingFailureAction(
            action=MAPPING_ACTION_IGNORE_KEEP_STATE,
            reason_code="ACTIVE_SYMBOL_STATE",
        )
    return MappingFailureAction(
        action=MAPPING_ACTION_RESET_AND_EXCLUDE,
        reason_code="PRE_FILTER_STAGE",
    )


def map_ticker_to_candidate_symbol_with_logging(
    raw_ticker: str,
    *,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> SymbolCandidateResult:
    result = map_ticker_to_candidate_symbol(raw_ticker)
    if result.ok:
        log_structured_event(
            StructuredLogEvent(
                component="symbol_mapping",
                event="map_ticker_to_symbol",
                input_data=f"raw_ticker={_normalize(raw_ticker)}",
                decision="sanitize_and_validate_alnum_ticker",
                result=f"mapped symbol={result.candidate_symbol}",
                state_before="mapping",
                state_after="mapped",
                failure_reason="-",
            ),
            channel_id=channel_id if channel_id is not None else "-",
            message_id=message_id if message_id is not None else "-",
            normalized_ticker=result.normalized_ticker if result.normalized_ticker is not None else "-",
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="symbol_mapping",
            event="map_ticker_to_symbol",
            input_data=f"raw_ticker={_normalize(raw_ticker)}",
            decision="sanitize_and_validate_alnum_ticker",
            result="mapping_failed",
            state_before="mapping",
            state_after="rejected",
            failure_reason=result.failure_code,
        ),
        channel_id=channel_id if channel_id is not None else "-",
        message_id=message_id if message_id is not None else "-",
        detail=result.failure_reason,
        normalized_ticker=result.normalized_ticker if result.normalized_ticker is not None else "-",
    )
    return result


def validate_candidate_symbol_usdt_m_with_logging(
    candidate_symbol: str,
    exchange_info: Optional[Mapping[str, Any]],
    *,
    exchange_info_error: Optional[str] = None,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> SymbolValidationResult:
    result = validate_candidate_symbol_usdt_m(
        candidate_symbol,
        exchange_info,
        exchange_info_error=exchange_info_error,
    )
    if result.ok:
        log_structured_event(
            StructuredLogEvent(
                component="symbol_mapping",
                event="validate_symbol",
                input_data=f"candidate_symbol={_normalize(candidate_symbol)}",
                decision="check_exchangeinfo_presence_and_trading_status",
                result="validated",
                state_before="mapped",
                state_after="validated",
                failure_reason="-",
            ),
            channel_id=channel_id if channel_id is not None else "-",
            message_id=message_id if message_id is not None else "-",
            symbol=result.symbol,
            status=result.status if result.status is not None else "-",
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="symbol_mapping",
            event="validate_symbol",
            input_data=f"candidate_symbol={_normalize(candidate_symbol)}",
            decision="check_exchangeinfo_presence_and_trading_status",
            result="validation_failed",
            state_before="mapped",
            state_after="rejected",
            failure_reason=result.failure_code,
        ),
        channel_id=channel_id if channel_id is not None else "-",
        message_id=message_id if message_id is not None else "-",
        exists=result.exists,
        status=result.status if result.status is not None else "-",
        detail=result.failure_reason,
    )
    return result


def resolve_mapping_failure_action_with_logging(
    *,
    is_monitoring: bool,
    has_open_order: bool,
    has_position: bool,
    symbol: Optional[str] = None,
) -> MappingFailureAction:
    result = resolve_mapping_failure_action(
        is_monitoring=is_monitoring,
        has_open_order=has_open_order,
        has_position=has_position,
    )
    log_structured_event(
        StructuredLogEvent(
            component="symbol_mapping",
            event="resolve_mapping_failure_action",
            input_data=(
                f"is_monitoring={is_monitoring} "
                f"has_open_order={has_open_order} has_position={has_position}"
            ),
            decision="choose_keep_or_reset_by_symbol_activity",
            result=result.action,
            state_before="mapping_failed",
            state_after="mapping_failed",
            failure_reason="-",
        ),
        symbol=symbol if symbol is not None else "-",
        reason_code=result.reason_code,
    )
    return result
