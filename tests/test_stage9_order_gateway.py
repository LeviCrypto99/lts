from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    GatewayCallResult,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderQueryRequest,
    RetryPolicy,
    SymbolFilterRules,
    cancel_order_with_retry,
    cancel_order_with_retry_with_logging,
    create_order_with_retry,
    create_order_with_retry_with_logging,
    prepare_create_order,
    prepare_create_order_with_logging,
    query_order_with_retry,
)


class OrderPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filters = SymbolFilterRules(
            tick_size=0.1,
            step_size=0.01,
            min_qty=0.1,
            min_notional=5.0,
        )

    def test_one_way_entry_limit_enforces_filters_and_reduce_only_false(self) -> None:
        request = OrderCreateRequest(
            symbol="btcusdt",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=1.234,
            price=100.16,
            new_client_order_id="entry-1",
        )
        result = prepare_create_order(
            request,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.prepared_params["symbol"], "BTCUSDT")
        self.assertEqual(result.prepared_params["price"], 100.2)
        self.assertEqual(result.prepared_params["quantity"], 1.23)
        self.assertEqual(result.prepared_params["timeInForce"], "GTC")
        self.assertEqual(result.prepared_params["reduceOnly"], False)
        self.assertNotIn("positionSide", result.prepared_params)

    def test_one_way_exit_limit_enforces_reduce_only_true(self) -> None:
        request = OrderCreateRequest(
            symbol="ETHUSDT",
            side="BUY",
            order_type="LIMIT",
            purpose="EXIT",
            quantity=2.0,
            price=120.04,
        )
        result = prepare_create_order(
            request,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.prepared_params["reduceOnly"], True)
        self.assertNotIn("closePosition", result.prepared_params)
        self.assertNotIn("positionSide", result.prepared_params)

    def test_one_way_exit_stop_market_enforces_close_position_without_quantity(self) -> None:
        request = OrderCreateRequest(
            symbol="ETHUSDT",
            side="BUY",
            order_type="STOP_MARKET",
            purpose="EXIT",
            stop_price=120.14,
            quantity=2.5,
        )
        result = prepare_create_order(
            request,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.prepared_params["stopPrice"], 120.1)
        self.assertEqual(result.prepared_params["workingType"], "MARK_PRICE")
        self.assertEqual(result.prepared_params["closePosition"], True)
        self.assertNotIn("quantity", result.prepared_params)
        self.assertNotIn("reduceOnly", result.prepared_params)

    def test_hedge_entry_sets_position_side_short(self) -> None:
        request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=1.0,
            price=100.0,
        )
        result = prepare_create_order(
            request,
            filter_rules=self.filters,
            position_mode="HEDGE",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.prepared_params["positionSide"], "SHORT")
        self.assertNotIn("reduceOnly", result.prepared_params)

    def test_hedge_exit_stop_market_sets_position_side_and_close_position(self) -> None:
        request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="BUY",
            order_type="STOP_MARKET",
            purpose="EXIT",
            stop_price=105.06,
        )
        result = prepare_create_order(
            request,
            filter_rules=self.filters,
            position_mode="HEDGE",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.prepared_params["positionSide"], "SHORT")
        self.assertEqual(result.prepared_params["workingType"], "MARK_PRICE")
        self.assertEqual(result.prepared_params["closePosition"], True)
        self.assertNotIn("quantity", result.prepared_params)

    def test_reject_price_filter_non_positive_after_round(self) -> None:
        request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=1.0,
            price=0.1,
        )
        result = prepare_create_order(
            request,
            filter_rules=SymbolFilterRules(tick_size=1.0, step_size=0.01, min_qty=0.01, min_notional=1.0),
            position_mode="ONE_WAY",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "PRICE_NON_POSITIVE_AFTER_ROUND")

    def test_reject_lot_size_min_qty_not_met(self) -> None:
        request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=0.11,
            price=100.0,
        )
        result = prepare_create_order(
            request,
            filter_rules=SymbolFilterRules(tick_size=0.1, step_size=0.1, min_qty=0.2, min_notional=1.0),
            position_mode="ONE_WAY",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "LOT_SIZE_MIN_QTY_NOT_MET")

    def test_reject_min_notional_not_met(self) -> None:
        request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=0.1,
            price=10.0,
        )
        result = prepare_create_order(
            request,
            filter_rules=SymbolFilterRules(tick_size=0.1, step_size=0.01, min_qty=0.01, min_notional=5.0),
            position_mode="ONE_WAY",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "MIN_NOTIONAL_NOT_MET")


class RetryGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filters = SymbolFilterRules(
            tick_size=0.1,
            step_size=0.01,
            min_qty=0.1,
            min_notional=5.0,
        )
        self.entry_request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=1.0,
            price=100.0,
            new_client_order_id="fixed-client-id",
        )

    def test_create_order_retries_and_keeps_same_client_order_id(self) -> None:
        observed_client_order_ids: list[str] = []
        call_count = {"value": 0}

        def fake_create(params: dict) -> GatewayCallResult:
            call_count["value"] += 1
            observed_client_order_ids.append(str(params.get("newClientOrderId")))
            if call_count["value"] < 3:
                return GatewayCallResult(ok=False, reason_code="NETWORK_ERROR")
            return GatewayCallResult(ok=True, reason_code="OK", payload={"orderId": 1234})

        result = create_order_with_retry(
            self.entry_request,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            call=fake_create,
            retry_policy=RetryPolicy(max_attempts=3, retryable_reason_codes=("NETWORK_ERROR",)),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(observed_client_order_ids, ["fixed-client-id", "fixed-client-id", "fixed-client-id"])

    def test_create_order_stops_on_non_retryable_failure(self) -> None:
        def fake_create(_params: dict) -> GatewayCallResult:
            return GatewayCallResult(ok=False, reason_code="INVALID_SIGNATURE")

        result = create_order_with_retry(
            self.entry_request,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            call=fake_create,
            retry_policy=RetryPolicy(max_attempts=3, retryable_reason_codes=("NETWORK_ERROR",)),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.reason_code, "INVALID_SIGNATURE")

    def test_create_order_rejects_before_gateway_when_filter_fails(self) -> None:
        bad_request = OrderCreateRequest(
            symbol="BTCUSDT",
            side="SELL",
            order_type="LIMIT",
            purpose="ENTRY",
            quantity=0.01,
            price=100.0,
        )

        def fake_create(_params: dict) -> GatewayCallResult:
            return GatewayCallResult(ok=True, reason_code="SHOULD_NOT_BE_CALLED")

        result = create_order_with_retry(
            bad_request,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            call=fake_create,
            retry_policy=RetryPolicy(max_attempts=3, retryable_reason_codes=("NETWORK_ERROR",)),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 0)
        self.assertEqual(result.reason_code, "LOT_SIZE_MIN_QTY_NOT_MET")

    def test_cancel_order_retry_and_query_retry(self) -> None:
        cancel_count = {"value": 0}
        query_count = {"value": 0}

        def fake_cancel(_params: dict) -> GatewayCallResult:
            cancel_count["value"] += 1
            if cancel_count["value"] < 2:
                return GatewayCallResult(ok=False, reason_code="TIMEOUT")
            return GatewayCallResult(ok=True, reason_code="OK")

        def fake_query(_params: dict) -> GatewayCallResult:
            query_count["value"] += 1
            if query_count["value"] < 2:
                return GatewayCallResult(ok=False, reason_code="RATE_LIMIT")
            return GatewayCallResult(ok=True, reason_code="OK", payload={"status": "NEW"})

        cancel_result = cancel_order_with_retry(
            OrderCancelRequest(symbol="BTCUSDT", order_id=10),
            call=fake_cancel,
            retry_policy=RetryPolicy(max_attempts=3, retryable_reason_codes=("TIMEOUT",)),
        )
        self.assertTrue(cancel_result.success)
        self.assertEqual(cancel_result.attempts, 2)

        query_result = query_order_with_retry(
            OrderQueryRequest(symbol="BTCUSDT", order_id=10),
            call=fake_query,
            retry_policy=RetryPolicy(max_attempts=3, retryable_reason_codes=("RATE_LIMIT",)),
        )
        self.assertTrue(query_result.success)
        self.assertEqual(query_result.attempts, 2)

    def test_cancel_order_rejects_missing_order_identifier(self) -> None:
        result = cancel_order_with_retry(
            OrderCancelRequest(symbol="BTCUSDT"),
            call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 0)
        self.assertEqual(result.reason_code, "ORDER_IDENTIFIER_REQUIRED")


class Stage9LoggingTests(unittest.TestCase):
    def test_prepare_create_order_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = prepare_create_order_with_logging(
                OrderCreateRequest(
                    symbol="BTCUSDT",
                    side="SELL",
                    order_type="LIMIT",
                    purpose="ENTRY",
                    quantity=1.0,
                    price=100.0,
                ),
                filter_rules=SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.01,
                    min_qty=0.1,
                    min_notional=5.0,
                ),
                position_mode="ONE_WAY",
                loop_label="stage9-prepare",
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_create_and_cancel_retry_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = create_order_with_retry_with_logging(
                OrderCreateRequest(
                    symbol="BTCUSDT",
                    side="SELL",
                    order_type="LIMIT",
                    purpose="ENTRY",
                    quantity=1.0,
                    price=100.0,
                ),
                filter_rules=SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.01,
                    min_qty=0.1,
                    min_notional=5.0,
                ),
                position_mode="ONE_WAY",
                call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
                loop_label="stage9-create",
            )
            _ = cancel_order_with_retry_with_logging(
                OrderCancelRequest(symbol="BTCUSDT", order_id=1),
                call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
                loop_label="stage9-cancel",
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
