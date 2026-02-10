from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

PARSE_OK = "OK"


@dataclass(frozen=True)
class LeadingMarketMessage:
    ticker: str
    symbol: str
    funding_rate_pct: float
    funding_countdown: str
    ranking_change_pct: float
    ranking_direction: str
    ranking_position: int
    category: str


@dataclass(frozen=True)
class RiskManagementMessage:
    symbol: str


@dataclass(frozen=True)
class LeadingMarketParseResult:
    ok: bool
    data: Optional[LeadingMarketMessage]
    failure_code: str
    failure_reason: str


@dataclass(frozen=True)
class LeadingTickerParseResult:
    ok: bool
    ticker: Optional[str]
    failure_code: str
    failure_reason: str


@dataclass(frozen=True)
class RiskManagementParseResult:
    ok: bool
    data: Optional[RiskManagementMessage]
    failure_code: str
    failure_reason: str


@dataclass(frozen=True)
class MessageIdCheckResult:
    is_duplicate_or_old: bool
    accepted: bool
    reason_code: str
    updated_last_message_ids: Mapping[int, int]
