from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from .state_machine_models import SymbolState

EntryPhase = Literal["FIRST_ENTRY", "SECOND_ENTRY"]
EntryPipelineAction = Literal[
    "ENTRY_SUBMITTED",
    "RESET_AND_EXCLUDE",
    "SECOND_ENTRY_SKIPPED_KEEP_STATE",
]


@dataclass(frozen=True)
class EntryBudgetResult:
    ok: bool
    budget_usdt: Optional[float]
    reason_code: str
    failure_reason: str


@dataclass(frozen=True)
class EntryQuantityResult:
    ok: bool
    quantity: Optional[float]
    reason_code: str
    failure_reason: str


@dataclass(frozen=True)
class EntryPipelineResult:
    phase: EntryPhase
    success: bool
    action: EntryPipelineAction
    reason_code: str
    failure_reason: str
    previous_state: SymbolState
    current_state: SymbolState
    state_transition_reason: str
    gateway_attempts: int
    gateway_reason_code: str
    budget_usdt: Optional[float]
    raw_quantity: Optional[float]
    refreshed_available_usdt: Optional[float]
