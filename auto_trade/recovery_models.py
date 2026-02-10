from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from .order_gateway_models import PositionMode
from .state_machine_models import GlobalState, GlobalTransitionResult, SymbolState

RecoveryPositionMode = PositionMode | Literal["UNKNOWN"]
ReconcileActionCode = Literal[
    "NONE",
    "CANCEL_UNNEEDED_ORDERS",
    "REQUIRE_EXIT_REGISTRATION",
    "CANCEL_AND_REQUIRE_EXIT_REGISTRATION",
]


@dataclass(frozen=True)
class PersistentRecoveryState:
    last_message_ids: Mapping[int, int] = field(default_factory=dict)
    cooldown_by_symbol: Mapping[str, int] = field(default_factory=dict)
    received_at_by_symbol: Mapping[str, int] = field(default_factory=dict)
    message_id_by_symbol: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ExchangeSnapshot:
    ok: bool
    reason_code: str
    failure_reason: str
    open_orders: Sequence[Mapping[str, Any]]
    positions: Sequence[Mapping[str, Any]]
    open_order_count: int
    has_any_position: bool
    position_mode: RecoveryPositionMode


@dataclass(frozen=True)
class ExitReconcilePlan:
    action_code: ReconcileActionCode
    reason_code: str
    cancel_symbols: Sequence[str]
    register_symbols: Sequence[str]
    require_exit_registration: bool

    @property
    def has_action(self) -> bool:
        return self.action_code != "NONE"


@dataclass(frozen=True)
class ExitReconcileExecutionResult:
    success: bool
    reason_code: str
    failure_reason: str
    canceled_symbols: Sequence[str]


@dataclass(frozen=True)
class RecoveryRuntimeState:
    recovery_locked: bool = False
    signal_loop_paused: bool = True
    signal_loop_running: bool = False
    persisted_loaded: bool = False
    snapshot_loaded: bool = False
    monitoring_queue_cleared: bool = False
    global_state: GlobalState = field(default_factory=GlobalState)
    position_mode: RecoveryPositionMode = "UNKNOWN"
    active_symbol_state: SymbolState = "IDLE"
    last_message_ids: Mapping[int, int] = field(default_factory=dict)
    cooldown_by_symbol: Mapping[str, int] = field(default_factory=dict)
    received_at_by_symbol: Mapping[str, int] = field(default_factory=dict)
    message_id_by_symbol: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryTransitionResult:
    previous: RecoveryRuntimeState
    current: RecoveryRuntimeState
    changed: bool
    reason_code: str
    failure_reason: str


@dataclass(frozen=True)
class RecoverySnapshotResult:
    previous: RecoveryRuntimeState
    current: RecoveryRuntimeState
    changed: bool
    reason_code: str
    failure_reason: str
    global_transition: GlobalTransitionResult


@dataclass(frozen=True)
class RecoveryRunResult:
    success: bool
    reason_code: str
    failure_reason: str
    state: RecoveryRuntimeState
    snapshot_reason_code: str
    reconcile_plan_reason_code: str
    reconcile_execution_reason_code: str
