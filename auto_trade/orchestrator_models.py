from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional

from .config import AutoTradeSettings
from .execution_models import ExitFiveSecondRuleDecision, ExitPartialFillTracker, PnlBranch
from .order_gateway_models import PositionMode
from .price_source_models import PriceSourceState
from .recovery_models import RecoveryPositionMode
from .state_machine_models import GlobalState, SymbolState
from .trigger_models import TriggerCandidate, TriggerKind


@dataclass(frozen=True)
class AutoTradeRuntime:
    settings: AutoTradeSettings
    recovery_locked: bool = False
    signal_loop_paused: bool = True
    signal_loop_running: bool = False
    global_state: GlobalState = field(default_factory=GlobalState)
    symbol_state: SymbolState = "IDLE"
    position_mode: RecoveryPositionMode = "UNKNOWN"
    active_symbol: Optional[str] = None
    last_message_ids: Mapping[int, int] = field(default_factory=dict)
    cooldown_by_symbol: Mapping[str, int] = field(default_factory=dict)
    received_at_by_symbol: Mapping[str, int] = field(default_factory=dict)
    message_id_by_symbol: Mapping[str, int] = field(default_factory=dict)
    pending_trigger_candidates: Mapping[str, TriggerCandidate] = field(default_factory=dict)
    price_state: PriceSourceState = field(default_factory=PriceSourceState)
    exit_partial_tracker: ExitPartialFillTracker = field(default_factory=ExitPartialFillTracker)
    new_orders_locked: bool = False
    rate_limit_locked: bool = False
    auth_error_locked: bool = False
    second_entry_order_pending: bool = False


@dataclass(frozen=True)
class LeadingSignalProcessResult:
    accepted: bool
    reason_code: str
    failure_reason: str
    symbol: Optional[str]
    trigger_registered: bool
    symbol_state_before: SymbolState
    symbol_state_after: SymbolState


@dataclass(frozen=True)
class TriggerCycleProcessResult:
    attempted: bool
    success: bool
    reason_code: str
    failure_reason: str
    selected_symbol: Optional[str]
    selected_trigger_kind: Optional[TriggerKind]
    pipeline_reason_code: str
    symbol_state_before: SymbolState
    symbol_state_after: SymbolState


@dataclass(frozen=True)
class RiskSignalProcessResult:
    accepted: bool
    actionable: bool
    reason_code: str
    failure_reason: str
    symbol: Optional[str]
    pnl_branch: PnlBranch
    action_code: str
    reset_state: bool
    cancel_entry_orders: bool = False
    submit_market_exit: bool = False
    submit_breakeven_stop_market: bool = False
    create_tp_limit_once: bool = False
    keep_tp_order: bool = False
    keep_phase2_breakeven_limit: bool = False
    keep_existing_mdd_stop: bool = False


@dataclass(frozen=True)
class FillSyncProcessResult:
    accepted: bool
    reason_code: str
    failure_reason: str
    symbol_state_before: SymbolState
    symbol_state_after: SymbolState


@dataclass(frozen=True)
class PriceGuardProcessResult:
    success: bool
    reason_code: str
    failure_reason: str
    safety_action: str
    safety_locked: bool
    global_blocked: bool


@dataclass(frozen=True)
class RecoveryStartupProcessResult:
    success: bool
    reason_code: str
    failure_reason: str


@dataclass(frozen=True)
class OcoCancelProcessResult:
    success: bool
    reason_code: str
    failure_reason: str
    lock_new_orders: bool


@dataclass(frozen=True)
class ExitFiveSecondProcessResult:
    decision: ExitFiveSecondRuleDecision
    reason_code: str


@dataclass(frozen=True)
class TelegramMessageProcessResult:
    handled: bool
    message_type: Literal["LEADING", "RISK", "UNSUPPORTED"]
    reason_code: str
    failure_reason: str
    symbol: Optional[str] = None
    action_code: str = "-"
    pnl_branch: PnlBranch = "PNL_UNAVAILABLE"
    reset_state: bool = False
    cancel_entry_orders: bool = False
    submit_market_exit: bool = False
    submit_breakeven_stop_market: bool = False
    create_tp_limit_once: bool = False
