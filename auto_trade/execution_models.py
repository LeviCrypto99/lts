from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from .state_machine_models import SymbolState

ExecutionEntryPhase = Literal["FIRST_ENTRY", "SECOND_ENTRY"]
ExecutionOrderStatus = Literal[
    "NEW",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED",
]
PnlBranch = Literal["PNL_NEGATIVE", "PNL_ZERO", "PNL_POSITIVE", "PNL_UNAVAILABLE"]


@dataclass(frozen=True)
class PnlEvaluationResult:
    ok: bool
    roi_pct: Optional[float]
    branch: PnlBranch
    reason_code: str
    failure_reason: str


@dataclass(frozen=True)
class EntryFillSyncResult:
    phase: ExecutionEntryPhase
    order_status: ExecutionOrderStatus
    previous_state: SymbolState
    current_state: SymbolState
    changed: bool
    reason_code: str
    keep_entry_order: bool
    activate_tp_monitor: bool
    start_second_entry_monitor: bool
    switch_to_phase2_breakeven_only: bool
    submit_mdd_stop: bool


@dataclass(frozen=True)
class RiskManagementPlanResult:
    actionable: bool
    action_code: str
    reason_code: str
    cancel_entry_orders: bool
    submit_market_exit: bool
    submit_breakeven_stop_market: bool
    keep_tp_order: bool
    create_tp_limit_once: bool
    keep_phase2_breakeven_limit: bool
    keep_existing_mdd_stop: bool
    reset_state: bool


@dataclass(frozen=True)
class OcoCancelPlanResult:
    has_targets: bool
    reason_code: str
    cancel_target_order_ids: Sequence[int]


@dataclass(frozen=True)
class OcoCancelExecutionResult:
    success: bool
    reason_code: str
    attempted_count: int
    failed_order_ids: Sequence[int]
    lock_new_orders: bool


@dataclass(frozen=True)
class ExitPartialFillTracker:
    active: bool = False
    order_id: Optional[int] = None
    partial_started_at: int = 0
    last_update_at: int = 0
    last_executed_qty: float = 0.0


@dataclass(frozen=True)
class ExitPartialFillUpdateResult:
    previous: ExitPartialFillTracker
    current: ExitPartialFillTracker
    changed: bool
    reason_code: str


@dataclass(frozen=True)
class ExitFiveSecondRuleDecision:
    should_force_market_exit: bool
    reason_code: str
    remaining_seconds: int
