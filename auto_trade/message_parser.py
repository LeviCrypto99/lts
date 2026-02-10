from __future__ import annotations

import re
from typing import Mapping, Optional

from .event_logging import StructuredLogEvent, log_structured_event
from .message_models import (
    LeadingMarketMessage,
    LeadingMarketParseResult,
    LeadingTickerParseResult,
    MessageIdCheckResult,
    PARSE_OK,
    RiskManagementMessage,
    RiskManagementParseResult,
)

_NON_ALNUM_PATTERN = re.compile(r"[^A-Z0-9]")
_TITLE_TICKER_PATTERN = re.compile(r"\(([^()]+)\)")
_PERCENT_PATTERN = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
_TIME_PATTERN = re.compile(r"/\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2})")
_DIRECTION_RANK_PATTERN = re.compile(r"\(([^()]+)\)\s*상위\s*(\d+)\s*위")
_RISK_SYMBOL_PATTERN = re.compile(r"Binance\s*[:：]\s*([^\s]+)", re.IGNORECASE)

_ZERO_WIDTH_CHARS = {
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\u2060",  # WORD JOINER
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE
}


def _log_text_preview(text: str, limit: int = 180) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}...(+{len(compact) - limit} chars)"


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _split_label_payload(line: str) -> Optional[str]:
    parts = re.split(r"\s*[:：]\s*", line, maxsplit=1)
    if len(parts) != 2:
        return None
    return parts[1].strip()


def _sanitize_symbol_token(value: str) -> str:
    value = value.strip()
    sanitized_chars = []
    for ch in value:
        if ch in _ZERO_WIDTH_CHARS:
            continue
        code = ord(ch)
        if code < 32 or code == 127:
            continue
        sanitized_chars.append(ch)
    return "".join(sanitized_chars).upper()


def _normalize_alnum_token(value: str) -> tuple[Optional[str], Optional[str]]:
    normalized = _sanitize_symbol_token(value)
    if not normalized:
        return None, "EMPTY_TOKEN"
    if _NON_ALNUM_PATTERN.search(normalized):
        return None, "INVALID_CHARACTERS"
    return normalized, None


def _find_first_line(lines: list[str], markers: tuple[str, ...]) -> Optional[str]:
    for line in lines:
        for marker in markers:
            if marker in line:
                return line
    return None


def parse_leading_market_ticker(message_text: str) -> LeadingTickerParseResult:
    lines = _split_lines(message_text)
    if not lines:
        return LeadingTickerParseResult(False, None, "EMPTY_MESSAGE", "message is empty")

    title_line = _find_first_line(lines, ("🔥",))
    if title_line is None:
        return LeadingTickerParseResult(False, None, "TITLE_LINE_NOT_FOUND", "missing leading-market title")

    title_match = _TITLE_TICKER_PATTERN.search(title_line)
    if title_match is None:
        return LeadingTickerParseResult(False, None, "TICKER_NOT_FOUND", "missing ticker in title")

    raw_ticker = title_match.group(1)
    ticker, ticker_failure = _normalize_alnum_token(raw_ticker)
    if ticker is None:
        return LeadingTickerParseResult(
            False,
            None,
            "TICKER_NORMALIZE_FAILED",
            f"ticker normalization failed: {ticker_failure}",
        )

    return LeadingTickerParseResult(
        True,
        ticker,
        PARSE_OK,
        "-",
    )


def parse_leading_market_message(message_text: str) -> LeadingMarketParseResult:
    ticker_result = parse_leading_market_ticker(message_text)
    if not ticker_result.ok or ticker_result.ticker is None:
        return LeadingMarketParseResult(
            False,
            None,
            ticker_result.failure_code,
            ticker_result.failure_reason,
        )
    ticker = ticker_result.ticker
    symbol = f"{ticker}USDT"
    lines = _split_lines(message_text)

    funding_line = _find_first_line(lines, ("⏱", "펀딩비"))
    if funding_line is None:
        return LeadingMarketParseResult(False, None, "FUNDING_LINE_NOT_FOUND", "missing funding line")
    funding_payload = _split_label_payload(funding_line)
    if funding_payload is None:
        return LeadingMarketParseResult(False, None, "FUNDING_PAYLOAD_NOT_FOUND", "missing funding payload")
    funding_match = _PERCENT_PATTERN.search(funding_payload)
    if funding_match is None:
        return LeadingMarketParseResult(False, None, "FUNDING_PARSE_FAILED", "invalid funding percent")
    time_match = _TIME_PATTERN.search(funding_payload)
    if time_match is None:
        return LeadingMarketParseResult(False, None, "COUNTDOWN_PARSE_FAILED", "invalid funding countdown")
    funding_rate_pct = float(funding_match.group(1))
    funding_countdown = time_match.group(1)

    ranking_line = _find_first_line(lines, ("🥇", "등락률"))
    if ranking_line is None:
        return LeadingMarketParseResult(False, None, "RANKING_LINE_NOT_FOUND", "missing ranking line")
    ranking_payload = _split_label_payload(ranking_line)
    if ranking_payload is None:
        return LeadingMarketParseResult(False, None, "RANKING_PAYLOAD_NOT_FOUND", "missing ranking payload")
    ranking_pct_match = _PERCENT_PATTERN.search(ranking_payload)
    ranking_dir_match = _DIRECTION_RANK_PATTERN.search(ranking_payload)
    if ranking_pct_match is None or ranking_dir_match is None:
        return LeadingMarketParseResult(False, None, "RANKING_PARSE_FAILED", "invalid ranking payload")
    ranking_change_pct = float(ranking_pct_match.group(1))
    ranking_direction = ranking_dir_match.group(1).strip()
    ranking_position = int(ranking_dir_match.group(2))

    category_line = _find_first_line(lines, ("🏷", "카테고리"))
    if category_line is None:
        return LeadingMarketParseResult(False, None, "CATEGORY_LINE_NOT_FOUND", "missing category line")
    category_payload = _split_label_payload(category_line)
    if category_payload is None:
        return LeadingMarketParseResult(False, None, "CATEGORY_PAYLOAD_NOT_FOUND", "missing category payload")
    category = category_payload.strip()
    if not category:
        return LeadingMarketParseResult(False, None, "CATEGORY_PARSE_FAILED", "empty category")

    return LeadingMarketParseResult(
        True,
        LeadingMarketMessage(
            ticker=ticker,
            symbol=symbol,
            funding_rate_pct=funding_rate_pct,
            funding_countdown=funding_countdown,
            ranking_change_pct=ranking_change_pct,
            ranking_direction=ranking_direction,
            ranking_position=ranking_position,
            category=category,
        ),
        PARSE_OK,
        "-",
    )


def parse_risk_management_message(message_text: str) -> RiskManagementParseResult:
    text = message_text or ""
    if not text.strip():
        return RiskManagementParseResult(False, None, "EMPTY_MESSAGE", "message is empty")

    symbol_match = _RISK_SYMBOL_PATTERN.search(text)
    if symbol_match is None:
        return RiskManagementParseResult(False, None, "RISK_SYMBOL_NOT_FOUND", "missing Binance symbol token")

    raw_symbol = symbol_match.group(1).strip()
    sanitized = _sanitize_symbol_token(raw_symbol)
    if sanitized.endswith(".P"):
        sanitized = sanitized[:-2]

    symbol, symbol_failure = _normalize_alnum_token(sanitized)
    if symbol is None:
        return RiskManagementParseResult(
            False,
            None,
            "RISK_SYMBOL_NORMALIZE_FAILED",
            f"symbol normalization failed: {symbol_failure}",
        )

    return RiskManagementParseResult(
        True,
        RiskManagementMessage(symbol=symbol),
        PARSE_OK,
        "-",
    )


def check_message_id_dedup(
    last_message_ids: Mapping[int, int],
    *,
    channel_id: int,
    message_id: int,
) -> MessageIdCheckResult:
    if message_id <= 0:
        return MessageIdCheckResult(
            is_duplicate_or_old=True,
            accepted=False,
            reason_code="INVALID_MESSAGE_ID",
            updated_last_message_ids=dict(last_message_ids),
        )

    current_last = int(last_message_ids.get(channel_id, 0))
    if message_id <= current_last:
        return MessageIdCheckResult(
            is_duplicate_or_old=True,
            accepted=False,
            reason_code="OLD_OR_DUPLICATE_MESSAGE",
            updated_last_message_ids=dict(last_message_ids),
        )

    updated = dict(last_message_ids)
    updated[channel_id] = message_id
    return MessageIdCheckResult(
        is_duplicate_or_old=False,
        accepted=True,
        reason_code="NEW_MESSAGE_ACCEPTED",
        updated_last_message_ids=updated,
    )


def parse_leading_market_message_with_logging(
    message_text: str,
    *,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> LeadingMarketParseResult:
    result = parse_leading_market_message(message_text)
    if result.ok and result.data is not None:
        log_structured_event(
            StructuredLogEvent(
                component="message_parser",
                event="parse_leading_market",
                input_data=f"text={_log_text_preview(message_text)}",
                decision="parse_fields_and_normalize",
                result=f"ok symbol={result.data.symbol}",
                state_before="received",
                state_after="parsed",
                failure_reason="-",
            ),
            channel_id=channel_id if channel_id is not None else "-",
            message_id=message_id if message_id is not None else "-",
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="message_parser",
            event="parse_leading_market",
            input_data=f"text={_log_text_preview(message_text)}",
            decision="parse_fields_and_normalize",
            result="rejected",
            state_before="received",
            state_after="rejected",
            failure_reason=result.failure_code,
        ),
        channel_id=channel_id if channel_id is not None else "-",
        message_id=message_id if message_id is not None else "-",
        detail=result.failure_reason,
    )
    return result


def parse_leading_market_ticker_with_logging(
    message_text: str,
    *,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> LeadingTickerParseResult:
    result = parse_leading_market_ticker(message_text)
    if result.ok and result.ticker is not None:
        log_structured_event(
            StructuredLogEvent(
                component="message_parser",
                event="parse_leading_market_ticker",
                input_data=f"text={_log_text_preview(message_text)}",
                decision="extract_title_ticker_and_normalize",
                result=f"ok ticker={result.ticker}",
                state_before="received",
                state_after="parsed",
                failure_reason="-",
            ),
            channel_id=channel_id if channel_id is not None else "-",
            message_id=message_id if message_id is not None else "-",
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="message_parser",
            event="parse_leading_market_ticker",
            input_data=f"text={_log_text_preview(message_text)}",
            decision="extract_title_ticker_and_normalize",
            result="rejected",
            state_before="received",
            state_after="rejected",
            failure_reason=result.failure_code,
        ),
        channel_id=channel_id if channel_id is not None else "-",
        message_id=message_id if message_id is not None else "-",
        detail=result.failure_reason,
    )
    return result


def parse_risk_management_message_with_logging(
    message_text: str,
    *,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> RiskManagementParseResult:
    result = parse_risk_management_message(message_text)
    if result.ok and result.data is not None:
        log_structured_event(
            StructuredLogEvent(
                component="message_parser",
                event="parse_risk_management",
                input_data=f"text={_log_text_preview(message_text)}",
                decision="extract_and_normalize_symbol",
                result=f"ok symbol={result.data.symbol}",
                state_before="received",
                state_after="parsed",
                failure_reason="-",
            ),
            channel_id=channel_id if channel_id is not None else "-",
            message_id=message_id if message_id is not None else "-",
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="message_parser",
            event="parse_risk_management",
            input_data=f"text={_log_text_preview(message_text)}",
            decision="extract_and_normalize_symbol",
            result="rejected",
            state_before="received",
            state_after="rejected",
            failure_reason=result.failure_code,
        ),
        channel_id=channel_id if channel_id is not None else "-",
        message_id=message_id if message_id is not None else "-",
        detail=result.failure_reason,
    )
    return result


def check_message_id_dedup_with_logging(
    last_message_ids: Mapping[int, int],
    *,
    channel_id: int,
    message_id: int,
) -> MessageIdCheckResult:
    result = check_message_id_dedup(
        last_message_ids,
        channel_id=channel_id,
        message_id=message_id,
    )
    if result.accepted:
        log_structured_event(
            StructuredLogEvent(
                component="message_dedup",
                event="check_message_id",
                input_data=f"channel_id={channel_id} message_id={message_id}",
                decision="compare_with_last_processed_id",
                result="accepted",
                state_before="checking",
                state_after="accepted",
                failure_reason="-",
            ),
            reason_code=result.reason_code,
        )
        return result

    log_structured_event(
        StructuredLogEvent(
            component="message_dedup",
            event="check_message_id",
            input_data=f"channel_id={channel_id} message_id={message_id}",
            decision="compare_with_last_processed_id",
            result="rejected",
            state_before="checking",
            state_after="rejected",
            failure_reason=result.reason_code,
        ),
        reason_code=result.reason_code,
    )
    return result
