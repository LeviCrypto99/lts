from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Optional

TriggerKind = Literal["FIRST_ENTRY", "SECOND_ENTRY", "TP", "BREAKEVEN"]


@dataclass(frozen=True)
class TriggerCandidate:
    symbol: str
    trigger_kind: TriggerKind
    target_price: float
    received_at_local: int
    message_id: int
    entry_mode: Optional[str] = None


@dataclass(frozen=True)
class SymbolTriggerEvaluation:
    symbol: str
    trigger_kind: TriggerKind
    target_price: float
    threshold_price: float
    current_mark_price: Optional[float]
    satisfied: bool
    reason_code: str


@dataclass(frozen=True)
class TriggerLoopResult:
    selected_candidate: Optional[TriggerCandidate]
    reason_code: str
    satisfied_symbols: list[str]
    dropped_symbols: list[str]
    evaluations: Mapping[str, SymbolTriggerEvaluation]


@dataclass(frozen=True)
class SimulationStepResult:
    step_index: int
    snapshot_prices: Mapping[str, float]
    loop_result: TriggerLoopResult


@dataclass(frozen=True)
class TriggerSimulationReport:
    total_steps: int
    stopped_early: bool
    first_selected_step: Optional[int]
    steps: list[SimulationStepResult]
