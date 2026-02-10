from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

EntryMode = Literal["AGGRESSIVE", "CONSERVATIVE"]


@dataclass(frozen=True)
class EntryTargetResult:
    ok: bool
    mode: Optional[EntryMode]
    target_price: Optional[float]
    reference_index: Optional[int]
    reference_source: Optional[str]
    reference_timestamp: Optional[str]
    reason_code: str
    failure_reason: str
