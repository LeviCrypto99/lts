from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    GatewayCallResult,
    RetryPolicy,
    SymbolFilterRules,
    compute_first_entry_budget,
    compute_first_entry_budget_with_logging,
    compute_second_entry_budget,
    compute_second_entry_budget_with_logging,
    run_first_entry_pipeline,
    run_first_entry_pipeline_with_logging,
    run_second_entry_pipeline,
    run_second_entry_pipeline_with_logging,
)


class EntryBudgetTests(unittest.TestCase):
    def test_first_entry_budget_is_wallet_50_percent(self) -> None:
        result = compute_first_entry_budget(100.0)
        self.assertTrue(result.ok)
        self.assertEqual(result.budget_usdt, 50.0)
        self.assertEqual(result.reason_code, "FIRST_ENTRY_BUDGET_READY")

    def test_first_entry_budget_aggressive_mode_applies_double_multiplier(self) -> None:
        result = compute_first_entry_budget(100.0, entry_mode="AGGRESSIVE")
        self.assertTrue(result.ok)
        self.assertEqual(result.budget_usdt, 100.0)
        self.assertEqual(result.reason_code, "FIRST_ENTRY_BUDGET_READY")

    def test_second_entry_budget_is_available_with_margin_buffer(self) -> None:
        result = compute_second_entry_budget(200.0, margin_buffer_pct=0.01)
        self.assertTrue(result.ok)
        self.assertEqual(result.budget_usdt, 198.0)
        self.assertEqual(result.reason_code, "SECOND_ENTRY_BUDGET_READY")

    def test_second_entry_budget_aggressive_mode_applies_double_multiplier(self) -> None:
        result = compute_second_entry_budget(
            200.0,
            margin_buffer_pct=0.01,
            entry_mode="AGGRESSIVE",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.budget_usdt, 396.0)
        self.assertEqual(result.reason_code, "SECOND_ENTRY_BUDGET_READY")


class FirstEntryPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filters = SymbolFilterRules(
            tick_size=0.1,
            step_size=0.01,
            min_qty=0.1,
            min_notional=5.0,
        )

    def test_first_entry_success_moves_to_entry_order(self) -> None:
        captured = {}

        def fake_create(params: dict) -> GatewayCallResult:
            captured.update(params)
            return GatewayCallResult(ok=True, reason_code="OK", payload={"orderId": 1})

        result = run_first_entry_pipeline(
            current_state="MONITORING",
            symbol="BTCUSDT",
            target_price=100.0,
            wallet_balance_usdt=100.0,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
            new_client_order_id="first-1",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.action, "ENTRY_SUBMITTED")
        self.assertEqual(result.current_state, "ENTRY_ORDER")
        self.assertEqual(captured.get("newClientOrderId"), "first-1")
        self.assertEqual(captured.get("quantity"), 0.5)
        self.assertEqual(captured.get("type"), "TAKE_PROFIT")
        self.assertEqual(captured.get("price"), 100.0)
        self.assertEqual(captured.get("stopPrice"), 99.9)

    def test_first_entry_aggressive_mode_doubles_order_quantity(self) -> None:
        captured = {}

        def fake_create(params: dict) -> GatewayCallResult:
            captured.update(params)
            return GatewayCallResult(ok=True, reason_code="OK", payload={"orderId": 11})

        result = run_first_entry_pipeline(
            current_state="MONITORING",
            symbol="BTCUSDT",
            target_price=100.0,
            wallet_balance_usdt=100.0,
            entry_mode="AGGRESSIVE",
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
            new_client_order_id="first-agg-1",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.action, "ENTRY_SUBMITTED")
        self.assertEqual(result.current_state, "ENTRY_ORDER")
        self.assertEqual(captured.get("newClientOrderId"), "first-agg-1")
        self.assertEqual(captured.get("quantity"), 1.0)
        self.assertEqual(captured.get("price"), 100.0)

    def test_first_entry_insufficient_margin_resets(self) -> None:
        def fake_create(_params: dict) -> GatewayCallResult:
            return GatewayCallResult(ok=False, reason_code="INSUFFICIENT_MARGIN")

        result = run_first_entry_pipeline(
            current_state="MONITORING",
            symbol="BTCUSDT",
            target_price=100.0,
            wallet_balance_usdt=100.0,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.action, "RESET_AND_EXCLUDE")
        self.assertEqual(result.current_state, "IDLE")
        self.assertEqual(result.reason_code, "FIRST_ENTRY_INSUFFICIENT_MARGIN_RESET")


class SecondEntryPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filters = SymbolFilterRules(
            tick_size=0.1,
            step_size=0.01,
            min_qty=0.1,
            min_notional=5.0,
        )

    def test_second_entry_success_keeps_phase1_state(self) -> None:
        captured = {}

        def fake_create(params: dict) -> GatewayCallResult:
            captured.update(params)
            return GatewayCallResult(ok=True, reason_code="OK", payload={"orderId": 2})

        result = run_second_entry_pipeline(
            current_state="PHASE1",
            symbol="BTCUSDT",
            second_target_price=110.0,
            available_usdt=200.0,
            margin_buffer_pct=0.01,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
            new_client_order_id="second-1",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.action, "ENTRY_SUBMITTED")
        self.assertEqual(result.current_state, "PHASE1")
        self.assertEqual(result.state_transition_reason, "NO_STATE_CHANGE")
        self.assertEqual(captured.get("newClientOrderId"), "second-1")
        self.assertEqual(captured.get("type"), "TAKE_PROFIT")
        self.assertEqual(captured.get("price"), 110.0)
        self.assertEqual(captured.get("stopPrice"), 109.9)

    def test_second_entry_aggressive_mode_doubles_order_quantity(self) -> None:
        captured = {}

        def fake_create(params: dict) -> GatewayCallResult:
            captured.update(params)
            return GatewayCallResult(ok=True, reason_code="OK", payload={"orderId": 12})

        result = run_second_entry_pipeline(
            current_state="PHASE1",
            symbol="BTCUSDT",
            second_target_price=110.0,
            available_usdt=200.0,
            margin_buffer_pct=0.01,
            entry_mode="AGGRESSIVE",
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
            new_client_order_id="second-agg-1",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.action, "ENTRY_SUBMITTED")
        self.assertEqual(result.current_state, "PHASE1")
        self.assertEqual(result.budget_usdt, 396.0)
        self.assertEqual(captured.get("newClientOrderId"), "second-agg-1")
        self.assertEqual(captured.get("quantity"), 3.6)
        self.assertEqual(captured.get("price"), 110.0)

    def test_second_entry_non_margin_failure_skips_and_keeps_state(self) -> None:
        def fake_create(_params: dict) -> GatewayCallResult:
            return GatewayCallResult(ok=False, reason_code="INVALID_SIGNATURE")

        result = run_second_entry_pipeline(
            current_state="PHASE1",
            symbol="BTCUSDT",
            second_target_price=110.0,
            available_usdt=200.0,
            margin_buffer_pct=0.01,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.action, "SECOND_ENTRY_SKIPPED_KEEP_STATE")
        self.assertEqual(result.current_state, "PHASE1")
        self.assertEqual(result.reason_code, "SECOND_ENTRY_CREATE_FAILED_KEEP_STATE")

    def test_second_entry_insufficient_margin_refresh_success(self) -> None:
        call_count = {"value": 0}

        def fake_create(_params: dict) -> GatewayCallResult:
            call_count["value"] += 1
            if call_count["value"] == 1:
                return GatewayCallResult(ok=False, reason_code="INSUFFICIENT_MARGIN")
            return GatewayCallResult(ok=True, reason_code="OK", payload={"orderId": 3})

        result = run_second_entry_pipeline(
            current_state="PHASE1",
            symbol="BTCUSDT",
            second_target_price=110.0,
            available_usdt=100.0,
            margin_buffer_pct=0.01,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
            refresh_available_usdt=lambda: 200.0,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.reason_code, "SECOND_ENTRY_SUBMITTED_AFTER_MARGIN_REFRESH")
        self.assertEqual(result.current_state, "PHASE1")
        self.assertEqual(result.refreshed_available_usdt, 200.0)
        self.assertEqual(result.gateway_attempts, 2)

    def test_second_entry_insufficient_margin_refresh_fail_keeps_state(self) -> None:
        call_count = {"value": 0}

        def fake_create(_params: dict) -> GatewayCallResult:
            call_count["value"] += 1
            return GatewayCallResult(ok=False, reason_code="INSUFFICIENT_MARGIN")

        result = run_second_entry_pipeline(
            current_state="PHASE1",
            symbol="BTCUSDT",
            second_target_price=110.0,
            available_usdt=100.0,
            margin_buffer_pct=0.01,
            filter_rules=self.filters,
            position_mode="ONE_WAY",
            create_call=fake_create,
            retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
            refresh_available_usdt=lambda: 200.0,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.action, "SECOND_ENTRY_SKIPPED_KEEP_STATE")
        self.assertEqual(result.current_state, "PHASE1")
        self.assertEqual(result.reason_code, "SECOND_ENTRY_MARGIN_REFRESH_RETRY_FAILED_KEEP_STATE")


class Stage10LoggingTests(unittest.TestCase):
    def test_budget_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = compute_first_entry_budget_with_logging(100.0)
            _ = compute_second_entry_budget_with_logging(200.0, margin_buffer_pct=0.01)
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)
            self.assertIn("entry_mode=", line)
            self.assertIn("mode_multiplier=", line)

    def test_pipeline_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = run_first_entry_pipeline_with_logging(
                current_state="MONITORING",
                symbol="BTCUSDT",
                target_price=100.0,
                wallet_balance_usdt=100.0,
                filter_rules=SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.01,
                    min_qty=0.1,
                    min_notional=5.0,
                ),
                position_mode="ONE_WAY",
                create_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
                retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
                loop_label="stage10-first",
            )
            _ = run_second_entry_pipeline_with_logging(
                current_state="PHASE1",
                symbol="BTCUSDT",
                second_target_price=110.0,
                available_usdt=200.0,
                margin_buffer_pct=0.01,
                filter_rules=SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.01,
                    min_qty=0.1,
                    min_notional=5.0,
                ),
                position_mode="ONE_WAY",
                create_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
                retry_policy=RetryPolicy(max_attempts=1, retryable_reason_codes=()),
                loop_label="stage10-second",
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)
            self.assertIn("entry_mode=", line)
            self.assertIn("mode_multiplier=", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
