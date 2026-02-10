from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EntryState = Literal["ENTRY_OPEN", "ENTRY_LOCKED"]
GlobalMode = Literal["GLOBAL_IDLE", "GLOBAL_BLOCKED"]
SymbolState = Literal["IDLE", "MONITORING", "ENTRY_ORDER", "PHASE1", "PHASE2"]

SymbolEvent = Literal[
    "START_MONITORING",
    "SUBMIT_ENTRY_ORDER",
    "PARTIAL_FILL",
    "FIRST_ENTRY_FILLED",
    "SUBMIT_SECOND_ENTRY_ORDER",
    "SECOND_ENTRY_PARTIAL_OR_FILLED",
    "CANCEL_ENTRY_NO_POSITION",
    "RESET",
]


@dataclass(frozen=True)
class GlobalState:
    has_any_position: bool = False
    has_any_open_order: bool = False
    safety_locked: bool = False

    @property
    def entry_locked(self) -> bool:
        return self.has_any_position or self.has_any_open_order

    @property
    def entry_state(self) -> EntryState:
        return "ENTRY_LOCKED" if self.entry_locked else "ENTRY_OPEN"

    @property
    def global_blocked(self) -> bool:
        return self.entry_locked or self.safety_locked

    @property
    def global_mode(self) -> GlobalMode:
        return "GLOBAL_BLOCKED" if self.global_blocked else "GLOBAL_IDLE"


@dataclass(frozen=True)
class GlobalTransitionResult:
    previous: GlobalState
    current: GlobalState
    changed: bool
    reason_code: str


@dataclass(frozen=True)
class SymbolTransitionResult:
    previous_state: SymbolState
    current_state: SymbolState
    event: SymbolEvent
    accepted: bool
    changed: bool
    reason_code: str
