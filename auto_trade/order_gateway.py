from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Callable, Mapping, Optional

from .event_logging import StructuredLogEvent, log_structured_event
from .order_gateway_models import (
    GatewayCallResult,
    GatewayRetryResult,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderOperation,
    OrderPreparationResult,
    OrderQueryRequest,
    OrderRefPreparationResult,
    PositionMode,
    RetryPolicy,
    SymbolFilterRules,
)

STOP_FAMILY_WORKING_TYPE = "CONTRACT_PRICE"


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _to_decimal(value: Any) -> Optional[Decimal]:
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not converted.is_finite():
        return None
    return converted


def _to_positive_decimal(value: Any) -> Optional[Decimal]:
    converted = _to_decimal(value)
    if converted is None or converted <= 0:
        return None
    return converted


def _round_price_with_reason(price: float, tick_size: float) -> tuple[Optional[float], str, str]:
    price_decimal = _to_positive_decimal(price)
    if price_decimal is None:
        return None, "INVALID_PRICE_INPUT", "price must be positive finite number"

    tick_decimal = _to_positive_decimal(tick_size)
    if tick_decimal is None:
        return None, "INVALID_TICK_SIZE", "tick_size must be positive finite number"

    units = (price_decimal / tick_decimal).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    adjusted = units * tick_decimal
    if adjusted <= 0:
        return None, "PRICE_NON_POSITIVE_AFTER_ROUND", "adjusted price is not positive"
    return float(adjusted), "PRICE_ROUNDED", "-"


def _floor_quantity_with_reason(quantity: float, step_size: float) -> tuple[Optional[float], str, str]:
    qty_decimal = _to_positive_decimal(quantity)
    if qty_decimal is None:
        return None, "INVALID_QUANTITY_INPUT", "quantity must be positive finite number"

    step_decimal = _to_positive_decimal(step_size)
    if step_decimal is None:
        return None, "INVALID_STEP_SIZE", "step_size must be positive finite number"

    units = (qty_decimal / step_decimal).quantize(Decimal("1"), rounding=ROUND_DOWN)
    adjusted = units * step_decimal
    if adjusted <= 0:
        return None, "QUANTITY_NON_POSITIVE_AFTER_FLOOR", "adjusted quantity is not positive"
    return float(adjusted), "QUANTITY_FLOORED", "-"


def round_price_by_tick_size(price: float, tick_size: float) -> Optional[float]:
    adjusted, _, _ = _round_price_with_reason(price, tick_size)
    return adjusted


def floor_quantity_by_step_size(quantity: float, step_size: float) -> Optional[float]:
    adjusted, _, _ = _floor_quantity_with_reason(quantity, step_size)
    return adjusted


def _validate_filter_rules(filter_rules: SymbolFilterRules) -> tuple[bool, str, str]:
    if _to_positive_decimal(filter_rules.tick_size) is None:
        return False, "INVALID_FILTER_TICK_SIZE", "tick_size must be positive"
    if _to_positive_decimal(filter_rules.step_size) is None:
        return False, "INVALID_FILTER_STEP_SIZE", "step_size must be positive"
    if _to_positive_decimal(filter_rules.min_qty) is None:
        return False, "INVALID_FILTER_MIN_QTY", "min_qty must be positive"
    if filter_rules.min_notional is not None:
        min_notional = _to_decimal(filter_rules.min_notional)
        if min_notional is None or min_notional < 0:
            return False, "INVALID_FILTER_MIN_NOTIONAL", "min_notional must be finite and >= 0"
    return True, "FILTERS_VALID", "-"


def _apply_position_mode_rules(
    params: dict[str, Any],
    *,
    request: OrderCreateRequest,
    position_mode: PositionMode,
) -> tuple[bool, str, str]:
    if position_mode not in ("ONE_WAY", "HEDGE"):
        return False, "INVALID_POSITION_MODE", "position_mode must be ONE_WAY or HEDGE"

    is_stop_market_family = request.order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET")
    close_position_requested = bool(request.close_position)
    if close_position_requested and not is_stop_market_family:
        return (
            False,
            "CLOSE_POSITION_UNSUPPORTED_ORDER_TYPE",
            "closePosition is only allowed for STOP_MARKET/TAKE_PROFIT_MARKET",
        )

    if request.purpose == "ENTRY" and close_position_requested:
        return False, "ENTRY_CLOSE_POSITION_FORBIDDEN", "entry orders cannot use closePosition"

    if position_mode == "HEDGE":
        params["positionSide"] = "SHORT"
        params.pop("reduceOnly", None)
        if request.purpose == "EXIT" and is_stop_market_family:
            params["closePosition"] = True
            params.pop("quantity", None)
        else:
            params.pop("closePosition", None)
        return True, "MODE_RULE_APPLIED_HEDGE", "-"

    params.pop("positionSide", None)
    if request.purpose == "ENTRY":
        params["reduceOnly"] = False
        params.pop("closePosition", None)
        return True, "MODE_RULE_APPLIED_ONE_WAY_ENTRY", "-"

    if is_stop_market_family:
        params["closePosition"] = True
        params.pop("reduceOnly", None)
        params.pop("quantity", None)
        return True, "MODE_RULE_APPLIED_ONE_WAY_EXIT_STOP", "-"

    params["reduceOnly"] = True
    params.pop("closePosition", None)
    return True, "MODE_RULE_APPLIED_ONE_WAY_EXIT_LIMIT_OR_MARKET", "-"


def _resolve_reference_price(
    *,
    adjusted_price: Optional[float],
    adjusted_stop_price: Optional[float],
    reference_price: Optional[float],
) -> Optional[float]:
    if adjusted_price is not None:
        return adjusted_price
    if adjusted_stop_price is not None:
        return adjusted_stop_price
    if reference_price is not None and reference_price > 0:
        return float(reference_price)
    return None


def prepare_create_order(
    request: OrderCreateRequest,
    *,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
) -> OrderPreparationResult:
    symbol = _normalize_symbol(request.symbol)
    if not symbol:
        return OrderPreparationResult(
            ok=False,
            reason_code="INVALID_SYMBOL",
            failure_reason="symbol is empty",
            prepared_params={},
            adjusted_price=None,
            adjusted_stop_price=None,
            adjusted_quantity=None,
            notional=None,
        )

    filters_ok, filters_reason, filters_failure = _validate_filter_rules(filter_rules)
    if not filters_ok:
        return OrderPreparationResult(
            ok=False,
            reason_code=filters_reason,
            failure_reason=filters_failure,
            prepared_params={},
            adjusted_price=None,
            adjusted_stop_price=None,
            adjusted_quantity=None,
            notional=None,
        )

    params: dict[str, Any] = {
        "symbol": symbol,
        "side": request.side,
        "type": request.order_type,
    }

    adjusted_price: Optional[float] = None
    adjusted_stop_price: Optional[float] = None
    adjusted_quantity: Optional[float] = None

    is_limit_style_order = request.order_type in ("LIMIT", "STOP", "TAKE_PROFIT")
    if is_limit_style_order:
        if request.price is None:
            return OrderPreparationResult(
                ok=False,
                reason_code="LIMIT_PRICE_REQUIRED",
                failure_reason=f"price is required for {request.order_type} order",
                prepared_params={},
                adjusted_price=None,
                adjusted_stop_price=None,
                adjusted_quantity=None,
                notional=None,
            )
        adjusted_price, reason_code, failure_reason = _round_price_with_reason(
            request.price,
            filter_rules.tick_size,
        )
        if adjusted_price is None:
            return OrderPreparationResult(
                ok=False,
                reason_code=reason_code,
                failure_reason=failure_reason,
                prepared_params={},
                adjusted_price=None,
                adjusted_stop_price=None,
                adjusted_quantity=None,
                notional=None,
            )
        params["price"] = adjusted_price
        if request.order_type == "LIMIT":
            params["timeInForce"] = "GTC" if request.purpose == "ENTRY" else (request.time_in_force or "GTC")
        else:
            params["timeInForce"] = request.time_in_force or "GTC"
    elif request.time_in_force:
        params["timeInForce"] = request.time_in_force

    if request.order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"):
        if request.stop_price is None:
            return OrderPreparationResult(
                ok=False,
                reason_code="STOP_PRICE_REQUIRED",
                failure_reason="stop_price is required for stop-family orders",
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=None,
                adjusted_quantity=None,
                notional=None,
            )
        adjusted_stop_price, reason_code, failure_reason = _round_price_with_reason(
            request.stop_price,
            filter_rules.tick_size,
        )
        if adjusted_stop_price is None:
            return OrderPreparationResult(
                ok=False,
                reason_code=reason_code,
                failure_reason=failure_reason,
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=None,
                adjusted_quantity=None,
                notional=None,
            )
        params["stopPrice"] = adjusted_stop_price
        params["workingType"] = STOP_FAMILY_WORKING_TYPE

    quantity_required = not bool(request.close_position)
    if request.purpose == "EXIT" and request.order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
        quantity_required = False

    if quantity_required:
        if request.quantity is None:
            return OrderPreparationResult(
                ok=False,
                reason_code="QUANTITY_REQUIRED",
                failure_reason="quantity is required for this order type",
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=adjusted_stop_price,
                adjusted_quantity=None,
                notional=None,
            )
        adjusted_quantity, reason_code, failure_reason = _floor_quantity_with_reason(
            request.quantity,
            filter_rules.step_size,
        )
        if adjusted_quantity is None:
            return OrderPreparationResult(
                ok=False,
                reason_code=reason_code,
                failure_reason=failure_reason,
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=adjusted_stop_price,
                adjusted_quantity=None,
                notional=None,
            )
        if adjusted_quantity < float(filter_rules.min_qty):
            return OrderPreparationResult(
                ok=False,
                reason_code="LOT_SIZE_MIN_QTY_NOT_MET",
                failure_reason=f"adjusted_quantity={adjusted_quantity} < min_qty={filter_rules.min_qty}",
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=adjusted_stop_price,
                adjusted_quantity=adjusted_quantity,
                notional=None,
            )
        params["quantity"] = adjusted_quantity

    notional: Optional[float] = None
    if quantity_required and filter_rules.min_notional is not None and float(filter_rules.min_notional) > 0:
        reference_price = _resolve_reference_price(
            adjusted_price=adjusted_price,
            adjusted_stop_price=adjusted_stop_price,
            reference_price=request.reference_price,
        )
        if reference_price is None:
            return OrderPreparationResult(
                ok=False,
                reason_code="MIN_NOTIONAL_REFERENCE_PRICE_REQUIRED",
                failure_reason="reference price is required for MIN_NOTIONAL check",
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=adjusted_stop_price,
                adjusted_quantity=adjusted_quantity,
                notional=None,
            )
        notional = float(adjusted_quantity or 0.0) * float(reference_price)
        if notional < float(filter_rules.min_notional):
            return OrderPreparationResult(
                ok=False,
                reason_code="MIN_NOTIONAL_NOT_MET",
                failure_reason=f"notional={notional} < min_notional={filter_rules.min_notional}",
                prepared_params={},
                adjusted_price=adjusted_price,
                adjusted_stop_price=adjusted_stop_price,
                adjusted_quantity=adjusted_quantity,
                notional=notional,
            )

    if request.new_client_order_id:
        params["newClientOrderId"] = request.new_client_order_id

    mode_ok, mode_reason, mode_failure = _apply_position_mode_rules(
        params,
        request=request,
        position_mode=position_mode,
    )
    if not mode_ok:
        return OrderPreparationResult(
            ok=False,
            reason_code=mode_reason,
            failure_reason=mode_failure,
            prepared_params={},
            adjusted_price=adjusted_price,
            adjusted_stop_price=adjusted_stop_price,
            adjusted_quantity=adjusted_quantity,
            notional=notional,
        )

    return OrderPreparationResult(
        ok=True,
        reason_code=mode_reason,
        failure_reason="-",
        prepared_params=params,
        adjusted_price=adjusted_price,
        adjusted_stop_price=adjusted_stop_price,
        adjusted_quantity=adjusted_quantity,
        notional=notional,
    )


def _prepare_order_ref(symbol: str, order_id: Optional[int], orig_client_order_id: Optional[str]) -> OrderRefPreparationResult:
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return OrderRefPreparationResult(
            ok=False,
            reason_code="INVALID_SYMBOL",
            failure_reason="symbol is empty",
            prepared_params={},
        )
    if order_id is None and not (orig_client_order_id or "").strip():
        return OrderRefPreparationResult(
            ok=False,
            reason_code="ORDER_IDENTIFIER_REQUIRED",
            failure_reason="order_id or orig_client_order_id is required",
            prepared_params={},
        )

    params: dict[str, Any] = {"symbol": normalized_symbol}
    if order_id is not None:
        params["orderId"] = int(order_id)
    if (orig_client_order_id or "").strip():
        params["origClientOrderId"] = str(orig_client_order_id).strip()
    return OrderRefPreparationResult(
        ok=True,
        reason_code="ORDER_REFERENCE_READY",
        failure_reason="-",
        prepared_params=params,
    )


def prepare_cancel_order(request: OrderCancelRequest) -> OrderRefPreparationResult:
    return _prepare_order_ref(request.symbol, request.order_id, request.orig_client_order_id)


def prepare_query_order(request: OrderQueryRequest) -> OrderRefPreparationResult:
    return _prepare_order_ref(request.symbol, request.order_id, request.orig_client_order_id)


def _failed_retry_result(
    operation: OrderOperation,
    reason_code: str,
    failure_reason: str,
) -> GatewayRetryResult:
    final = GatewayCallResult(
        ok=False,
        reason_code=reason_code,
        payload=None,
        error_code=None,
        error_message=failure_reason,
    )
    return GatewayRetryResult(
        operation=operation,
        success=False,
        attempts=0,
        reason_code=reason_code,
        last_result=final,
        history=[],
    )


def execute_gateway_with_retry(
    operation: OrderOperation,
    *,
    params: Mapping[str, Any],
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
) -> GatewayRetryResult:
    policy = retry_policy if retry_policy is not None else RetryPolicy()
    max_attempts = max(1, int(policy.max_attempts))
    retryable = set(policy.retryable_reason_codes)
    history: list[GatewayCallResult] = []

    for attempt_index in range(max_attempts):
        result = call(dict(params))
        history.append(result)
        if result.ok:
            return GatewayRetryResult(
                operation=operation,
                success=True,
                attempts=attempt_index + 1,
                reason_code="SUCCESS",
                last_result=result,
                history=history,
            )
        if result.reason_code not in retryable:
            return GatewayRetryResult(
                operation=operation,
                success=False,
                attempts=attempt_index + 1,
                reason_code=result.reason_code,
                last_result=result,
                history=history,
            )

    last_result = history[-1]
    return GatewayRetryResult(
        operation=operation,
        success=False,
        attempts=max_attempts,
        reason_code=last_result.reason_code,
        last_result=last_result,
        history=history,
    )


def create_order_with_retry(
    request: OrderCreateRequest,
    *,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
) -> GatewayRetryResult:
    prepared = prepare_create_order(
        request,
        filter_rules=filter_rules,
        position_mode=position_mode,
    )
    if not prepared.ok:
        return _failed_retry_result("CREATE", prepared.reason_code, prepared.failure_reason)
    return execute_gateway_with_retry(
        "CREATE",
        params=prepared.prepared_params,
        call=call,
        retry_policy=retry_policy,
    )


def cancel_order_with_retry(
    request: OrderCancelRequest,
    *,
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
) -> GatewayRetryResult:
    prepared = prepare_cancel_order(request)
    if not prepared.ok:
        return _failed_retry_result("CANCEL", prepared.reason_code, prepared.failure_reason)
    return execute_gateway_with_retry(
        "CANCEL",
        params=prepared.prepared_params,
        call=call,
        retry_policy=retry_policy,
    )


def query_order_with_retry(
    request: OrderQueryRequest,
    *,
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
) -> GatewayRetryResult:
    prepared = prepare_query_order(request)
    if not prepared.ok:
        return _failed_retry_result("QUERY", prepared.reason_code, prepared.failure_reason)
    return execute_gateway_with_retry(
        "QUERY",
        params=prepared.prepared_params,
        call=call,
        retry_policy=retry_policy,
    )


def prepare_create_order_with_logging(
    request: OrderCreateRequest,
    *,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    loop_label: str = "loop",
) -> OrderPreparationResult:
    result = prepare_create_order(
        request,
        filter_rules=filter_rules,
        position_mode=position_mode,
    )
    log_structured_event(
        StructuredLogEvent(
            component="order_gateway",
            event="prepare_create_order",
            input_data=(
                f"symbol={_normalize(request.symbol)} type={request.order_type} "
                f"purpose={request.purpose} position_mode={position_mode}"
            ),
            decision="apply_filters_and_mode_rules",
            result="prepared" if result.ok else "rejected",
            state_before="request_received",
            state_after="request_prepared" if result.ok else "request_rejected",
            failure_reason=result.reason_code if not result.ok else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
        adjusted_price=result.adjusted_price if result.adjusted_price is not None else "-",
        adjusted_stop_price=result.adjusted_stop_price if result.adjusted_stop_price is not None else "-",
        adjusted_quantity=result.adjusted_quantity if result.adjusted_quantity is not None else "-",
        notional=result.notional if result.notional is not None else "-",
    )
    return result


def prepare_cancel_order_with_logging(
    request: OrderCancelRequest,
    *,
    loop_label: str = "loop",
) -> OrderRefPreparationResult:
    result = prepare_cancel_order(request)
    log_structured_event(
        StructuredLogEvent(
            component="order_gateway",
            event="prepare_cancel_order",
            input_data=(
                f"symbol={_normalize(request.symbol)} order_id={request.order_id if request.order_id is not None else '-'} "
                f"orig_client_order_id={_normalize(request.orig_client_order_id)}"
            ),
            decision="validate_cancel_order_reference",
            result="prepared" if result.ok else "rejected",
            state_before="request_received",
            state_after="request_prepared" if result.ok else "request_rejected",
            failure_reason=result.reason_code if not result.ok else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
    )
    return result


def prepare_query_order_with_logging(
    request: OrderQueryRequest,
    *,
    loop_label: str = "loop",
) -> OrderRefPreparationResult:
    result = prepare_query_order(request)
    log_structured_event(
        StructuredLogEvent(
            component="order_gateway",
            event="prepare_query_order",
            input_data=(
                f"symbol={_normalize(request.symbol)} order_id={request.order_id if request.order_id is not None else '-'} "
                f"orig_client_order_id={_normalize(request.orig_client_order_id)}"
            ),
            decision="validate_query_order_reference",
            result="prepared" if result.ok else "rejected",
            state_before="request_received",
            state_after="request_prepared" if result.ok else "request_rejected",
            failure_reason=result.reason_code if not result.ok else "-",
        ),
        loop_label=loop_label,
        reason_code=result.reason_code,
    )
    return result


def create_order_with_retry_with_logging(
    request: OrderCreateRequest,
    *,
    filter_rules: SymbolFilterRules,
    position_mode: PositionMode,
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    loop_label: str = "loop",
) -> GatewayRetryResult:
    result = create_order_with_retry(
        request,
        filter_rules=filter_rules,
        position_mode=position_mode,
        call=call,
        retry_policy=retry_policy,
    )
    log_structured_event(
        StructuredLogEvent(
            component="order_gateway",
            event="create_order_with_retry",
            input_data=(
                f"symbol={_normalize(request.symbol)} type={request.order_type} purpose={request.purpose} "
                f"new_client_order_id={_normalize(request.new_client_order_id)}"
            ),
            decision="prepare_create_request_and_execute_retry_policy",
            result="success" if result.success else "failed",
            state_before="order_create_pending",
            state_after="order_create_done",
            failure_reason=result.reason_code if not result.success else "-",
        ),
        loop_label=loop_label,
        attempts=result.attempts,
        reason_code=result.reason_code,
        exchange_error_code=result.last_result.error_code if result.last_result.error_code is not None else "-",
    )
    return result


def cancel_order_with_retry_with_logging(
    request: OrderCancelRequest,
    *,
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    loop_label: str = "loop",
) -> GatewayRetryResult:
    result = cancel_order_with_retry(
        request,
        call=call,
        retry_policy=retry_policy,
    )
    log_structured_event(
        StructuredLogEvent(
            component="order_gateway",
            event="cancel_order_with_retry",
            input_data=(
                f"symbol={_normalize(request.symbol)} order_id={request.order_id if request.order_id is not None else '-'} "
                f"orig_client_order_id={_normalize(request.orig_client_order_id)}"
            ),
            decision="prepare_cancel_request_and_execute_retry_policy",
            result="success" if result.success else "failed",
            state_before="order_cancel_pending",
            state_after="order_cancel_done",
            failure_reason=result.reason_code if not result.success else "-",
        ),
        loop_label=loop_label,
        attempts=result.attempts,
        reason_code=result.reason_code,
        exchange_error_code=result.last_result.error_code if result.last_result.error_code is not None else "-",
    )
    return result


def query_order_with_retry_with_logging(
    request: OrderQueryRequest,
    *,
    call: Callable[[Mapping[str, Any]], GatewayCallResult],
    retry_policy: Optional[RetryPolicy] = None,
    loop_label: str = "loop",
) -> GatewayRetryResult:
    result = query_order_with_retry(
        request,
        call=call,
        retry_policy=retry_policy,
    )
    log_structured_event(
        StructuredLogEvent(
            component="order_gateway",
            event="query_order_with_retry",
            input_data=(
                f"symbol={_normalize(request.symbol)} order_id={request.order_id if request.order_id is not None else '-'} "
                f"orig_client_order_id={_normalize(request.orig_client_order_id)}"
            ),
            decision="prepare_query_request_and_execute_retry_policy",
            result="success" if result.success else "failed",
            state_before="order_query_pending",
            state_after="order_query_done",
            failure_reason=result.reason_code if not result.success else "-",
        ),
        loop_label=loop_label,
        attempts=result.attempts,
        reason_code=result.reason_code,
        exchange_error_code=result.last_result.error_code if result.last_result.error_code is not None else "-",
    )
    return result
