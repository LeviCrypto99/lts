from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional

from .state_machine_models import GlobalTransitionResult

PriceSourceMode = Literal["WS_PRIMARY", "REST_FALLBACK"]
PriceValueSource = Literal["WS", "REST", "UNAVAILABLE"]
SafetyAction = Literal[
    "NONE",
    "FORCE_MARKET_EXIT",
    "CANCEL_OPEN_ORDERS_AND_RESET",
    "RESET_ONLY",
]


@dataclass(frozen=True)
class MarkPriceRecord:
    mark_price: float
    received_at: int


@dataclass(frozen=True)
class PriceSourceState:
    mode: PriceSourceMode = "WS_PRIMARY"
    ws_last_received_at: int = 0
    rest_last_received_at: int = 0
    ws_mark_prices: Mapping[str, MarkPriceRecord] = field(default_factory=dict)
    rest_mark_prices: Mapping[str, MarkPriceRecord] = field(default_factory=dict)


@dataclass(frozen=True)
class PriceSourceUpdateResult:
    previous: PriceSourceState
    current: PriceSourceState
    changed: bool
    reason_code: str
    source: PriceValueSource
    symbol: Optional[str]


@dataclass(frozen=True)
class PriceSourceModeResult:
    previous_mode: PriceSourceMode
    current_mode: PriceSourceMode
    changed: bool
    ws_age_seconds: int
    reason_code: str
    state: PriceSourceState


@dataclass(frozen=True)
class MarkPriceReadResult:
    symbol: str
    mark_price: Optional[float]
    source: PriceValueSource
    used_mode: PriceSourceMode
    reason_code: str
    price_received_at: int
    price_age_seconds: int
    state: PriceSourceState


@dataclass(frozen=True)
class SafetyLockDecision:
    target_safety_locked: bool
    stale_detected: bool
    action: SafetyAction
    reason_code: str
    ws_age_seconds: int
    rest_age_seconds: int


@dataclass(frozen=True)
class PriceSourceGuardResult:
    decision: SafetyLockDecision
    global_transition: GlobalTransitionResult
