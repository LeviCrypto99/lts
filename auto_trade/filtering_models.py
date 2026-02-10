from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommonFilterResult:
    passed: bool
    reason_code: str
    failure_reason: str
