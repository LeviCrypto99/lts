from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional, Sequence

PositionMode = Literal["ONE_WAY", "HEDGE"]
OrderPurpose = Literal["ENTRY", "EXIT"]
OrderType = Literal["LIMIT", "MARKET", "STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"]
OrderSide = Literal["BUY", "SELL"]
OrderOperation = Literal["CREATE", "CANCEL", "QUERY"]

DEFAULT_RETRYABLE_REASON_CODES: tuple[str, ...] = (
    "NETWORK_ERROR",
    "TIMEOUT",
    "RATE_LIMIT",
    "SERVER_ERROR",
    "TEMPORARY_UNAVAILABLE",
)


@dataclass(frozen=True)
class SymbolFilterRules:
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: Optional[float] = None


@dataclass(frozen=True)
class OrderCreateRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    purpose: OrderPurpose
    quantity: Optional[float] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    reference_price: Optional[float] = None
    time_in_force: Optional[str] = None
    reduce_only: Optional[bool] = None
    close_position: Optional[bool] = None
    new_client_order_id: Optional[str] = None
    position_side: Optional[str] = None


@dataclass(frozen=True)
class OrderCancelRequest:
    symbol: str
    order_id: Optional[int] = None
    orig_client_order_id: Optional[str] = None


@dataclass(frozen=True)
class OrderQueryRequest:
    symbol: str
    order_id: Optional[int] = None
    orig_client_order_id: Optional[str] = None


@dataclass(frozen=True)
class GatewayCallResult:
    ok: bool
    reason_code: str
    payload: Optional[Mapping[str, Any]] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    retryable_reason_codes: Sequence[str] = field(default_factory=lambda: DEFAULT_RETRYABLE_REASON_CODES)


@dataclass(frozen=True)
class OrderPreparationResult:
    ok: bool
    reason_code: str
    failure_reason: str
    prepared_params: Mapping[str, Any]
    adjusted_price: Optional[float]
    adjusted_stop_price: Optional[float]
    adjusted_quantity: Optional[float]
    notional: Optional[float]


@dataclass(frozen=True)
class OrderRefPreparationResult:
    ok: bool
    reason_code: str
    failure_reason: str
    prepared_params: Mapping[str, Any]


@dataclass(frozen=True)
class GatewayRetryResult:
    operation: OrderOperation
    success: bool
    attempts: int
    reason_code: str
    last_result: GatewayCallResult
    history: Sequence[GatewayCallResult]
