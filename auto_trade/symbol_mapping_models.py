from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MAP_OK = "OK"


@dataclass(frozen=True)
class SymbolCandidateResult:
    ok: bool
    raw_ticker: str
    normalized_ticker: Optional[str]
    candidate_symbol: Optional[str]
    failure_code: str
    failure_reason: str


@dataclass(frozen=True)
class SymbolValidationResult:
    ok: bool
    symbol: str
    exists: bool
    status: Optional[str]
    failure_code: str
    failure_reason: str


@dataclass(frozen=True)
class MappingFailureAction:
    action: str
    reason_code: str
