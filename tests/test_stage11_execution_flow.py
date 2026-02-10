from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    ExitPartialFillTracker,
    GatewayCallResult,
    evaluate_exit_five_second_rule,
    evaluate_exit_five_second_rule_with_logging,
    evaluate_pnl_branch,
    evaluate_pnl_branch_with_logging,
    execute_oco_mutual_cancel,
    execute_oco_mutual_cancel_with_logging,
    plan_oco_mutual_cancel,
    plan_oco_mutual_cancel_with_logging,
    plan_risk_management_action,
    plan_risk_management_action_with_logging,
    sync_entry_fill_state,
    sync_entry_fill_state_with_logging,
    update_exit_partial_fill_tracker,
    update_exit_partial_fill_tracker_with_logging,
)


class PnlBranchTests(unittest.TestCase):
    def test_pnl_negative(self) -> None:
        result = evaluate_pnl_branch(avg_entry_price=100.0, mark_price=110.0)
        self.assertTrue(result.ok)
        self.assertEqual(result.branch, "PNL_NEGATIVE")
        self.assertAlmostEqual(result.roi_pct or 0.0, -10.0, places=10)

    def test_pnl_zero_requires_exact_zero(self) -> None:
        result = evaluate_pnl_branch(avg_entry_price=100.0, mark_price=100.0)
        self.assertTrue(result.ok)
        self.assertEqual(result.branch, "PNL_ZERO")
        self.assertEqual(result.roi_pct, 0.0)

    def test_pnl_positive(self) -> None:
        result = evaluate_pnl_branch(avg_entry_price=100.0, mark_price=90.0)
        self.assertTrue(result.ok)
        self.assertEqual(result.branch, "PNL_POSITIVE")
        self.assertAlmostEqual(result.roi_pct or 0.0, 10.0, places=10)

    def test_pnl_unavailable_when_input_invalid(self) -> None:
        result = evaluate_pnl_branch(avg_entry_price=0.0, mark_price=90.0)
        self.assertFalse(result.ok)
        self.assertEqual(result.branch, "PNL_UNAVAILABLE")


class EntryFillSyncTests(unittest.TestCase):
    def test_first_entry_partial_keeps_entry_order_and_activates_tp(self) -> None:
        result = sync_entry_fill_state(
            "ENTRY_ORDER",
            phase="FIRST_ENTRY",
            order_status="PARTIALLY_FILLED",
        )
        self.assertEqual(result.current_state, "ENTRY_ORDER")
        self.assertFalse(result.changed)
        self.assertTrue(result.keep_entry_order)
        self.assertTrue(result.activate_tp_monitor)

    def test_first_entry_filled_transitions_to_phase1(self) -> None:
        result = sync_entry_fill_state(
            "ENTRY_ORDER",
            phase="FIRST_ENTRY",
            order_status="FILLED",
        )
        self.assertEqual(result.current_state, "PHASE1")
        self.assertTrue(result.changed)
        self.assertTrue(result.start_second_entry_monitor)

    def test_second_entry_partial_transitions_to_phase2(self) -> None:
        result = sync_entry_fill_state(
            "PHASE1",
            phase="SECOND_ENTRY",
            order_status="PARTIALLY_FILLED",
        )
        self.assertEqual(result.current_state, "PHASE2")
        self.assertTrue(result.switch_to_phase2_breakeven_only)
        self.assertFalse(result.submit_mdd_stop)

    def test_second_entry_filled_submits_mdd_stop(self) -> None:
        result = sync_entry_fill_state(
            "PHASE1",
            phase="SECOND_ENTRY",
            order_status="FILLED",
        )
        self.assertEqual(result.current_state, "PHASE2")
        self.assertTrue(result.submit_mdd_stop)

    def test_second_entry_filled_on_phase2_keeps_state_and_submits_mdd_stop(self) -> None:
        result = sync_entry_fill_state(
            "PHASE2",
            phase="SECOND_ENTRY",
            order_status="FILLED",
        )
        self.assertEqual(result.current_state, "PHASE2")
        self.assertFalse(result.changed)
        self.assertTrue(result.submit_mdd_stop)


class RiskManagementPlanTests(unittest.TestCase):
    def test_symbol_mismatch_is_ignored(self) -> None:
        result = plan_risk_management_action(
            current_state="PHASE1",
            symbol_matches_active=False,
            has_position=True,
            has_open_entry_order=False,
            pnl_branch="PNL_POSITIVE",
            has_tp_order=True,
            second_entry_fully_filled=False,
        )
        self.assertFalse(result.actionable)
        self.assertEqual(result.action_code, "IGNORE_DIFFERENT_SYMBOL")

    def test_monitoring_state_resets(self) -> None:
        result = plan_risk_management_action(
            current_state="MONITORING",
            symbol_matches_active=True,
            has_position=False,
            has_open_entry_order=False,
            pnl_branch="PNL_UNAVAILABLE",
            has_tp_order=False,
            second_entry_fully_filled=False,
        )
        self.assertTrue(result.actionable)
        self.assertTrue(result.reset_state)
        self.assertEqual(result.action_code, "RESET_MONITORING")

    def test_entry_order_without_position_cancels_and_resets(self) -> None:
        result = plan_risk_management_action(
            current_state="ENTRY_ORDER",
            symbol_matches_active=True,
            has_position=False,
            has_open_entry_order=True,
            pnl_branch="PNL_UNAVAILABLE",
            has_tp_order=False,
            second_entry_fully_filled=False,
        )
        self.assertTrue(result.actionable)
        self.assertTrue(result.cancel_entry_orders)
        self.assertTrue(result.reset_state)

    def test_partial_fill_with_negative_pnl_prioritizes_market_exit(self) -> None:
        result = plan_risk_management_action(
            current_state="ENTRY_ORDER",
            symbol_matches_active=True,
            has_position=True,
            has_open_entry_order=True,
            pnl_branch="PNL_NEGATIVE",
            has_tp_order=False,
            second_entry_fully_filled=False,
        )
        self.assertTrue(result.actionable)
        self.assertTrue(result.submit_market_exit)
        self.assertTrue(result.cancel_entry_orders)

    def test_phase1_positive_pnl_stop_and_keep_existing_tp(self) -> None:
        result = plan_risk_management_action(
            current_state="PHASE1",
            symbol_matches_active=True,
            has_position=True,
            has_open_entry_order=False,
            pnl_branch="PNL_POSITIVE",
            has_tp_order=True,
            second_entry_fully_filled=False,
        )
        self.assertTrue(result.actionable)
        self.assertTrue(result.submit_breakeven_stop_market)
        self.assertTrue(result.keep_tp_order)
        self.assertFalse(result.create_tp_limit_once)

    def test_phase1_positive_pnl_arms_tp_trigger_when_missing(self) -> None:
        result = plan_risk_management_action(
            current_state="PHASE1",
            symbol_matches_active=True,
            has_position=True,
            has_open_entry_order=False,
            pnl_branch="PNL_POSITIVE",
            has_tp_order=False,
            second_entry_fully_filled=False,
        )
        self.assertTrue(result.actionable)
        self.assertTrue(result.submit_breakeven_stop_market)
        self.assertFalse(result.create_tp_limit_once)

    def test_phase2_positive_pnl_keeps_breakeven_mode(self) -> None:
        result = plan_risk_management_action(
            current_state="PHASE2",
            symbol_matches_active=True,
            has_position=True,
            has_open_entry_order=False,
            pnl_branch="PNL_POSITIVE",
            has_tp_order=False,
            second_entry_fully_filled=True,
        )
        self.assertTrue(result.actionable)
        self.assertTrue(result.keep_phase2_breakeven_limit)
        self.assertTrue(result.keep_existing_mdd_stop)
        self.assertFalse(result.submit_breakeven_stop_market)


class OcoAndFiveSecondRuleTests(unittest.TestCase):
    def test_oco_plan_excludes_filled_order(self) -> None:
        plan = plan_oco_mutual_cancel(
            filled_order_id=100,
            open_exit_order_ids=[100, 101, 102],
        )
        self.assertTrue(plan.has_targets)
        self.assertEqual(list(plan.cancel_target_order_ids), [101, 102])

    def test_oco_execute_failure_locks_new_orders(self) -> None:
        def fake_cancel(params: dict) -> GatewayCallResult:
            if int(params["orderId"]) == 102:
                return GatewayCallResult(ok=False, reason_code="INVALID_SIGNATURE")
            return GatewayCallResult(ok=True, reason_code="OK")

        result = execute_oco_mutual_cancel(
            symbol="BTCUSDT",
            cancel_order_ids=[101, 102],
            cancel_call=fake_cancel,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.lock_new_orders)
        self.assertEqual(list(result.failed_order_ids), [102])

    def test_exit_partial_fill_5s_rule_and_reset_by_additional_fill(self) -> None:
        tracker = ExitPartialFillTracker()
        tracker = update_exit_partial_fill_tracker(
            tracker,
            is_exit_order=True,
            order_id=9001,
            order_status="PARTIALLY_FILLED",
            executed_qty=1.0,
            updated_at=100,
        ).current
        early = evaluate_exit_five_second_rule(
            tracker,
            is_exit_order=True,
            now=103,
            stall_seconds=5,
        )
        self.assertFalse(early.should_force_market_exit)
        self.assertEqual(early.reason_code, "EXIT_PARTIAL_WAITING")

        tracker = update_exit_partial_fill_tracker(
            tracker,
            is_exit_order=True,
            order_id=9001,
            order_status="PARTIALLY_FILLED",
            executed_qty=1.2,
            updated_at=104,
        ).current
        after_reset = evaluate_exit_five_second_rule(
            tracker,
            is_exit_order=True,
            now=108,
            stall_seconds=5,
        )
        self.assertFalse(after_reset.should_force_market_exit)

        trigger = evaluate_exit_five_second_rule(
            tracker,
            is_exit_order=True,
            now=109,
            stall_seconds=5,
        )
        self.assertTrue(trigger.should_force_market_exit)
        self.assertEqual(trigger.reason_code, "EXIT_PARTIAL_STALLED_5S")

    def test_exit_partial_fill_rule_is_skipped_when_risk_market_exit_in_same_loop(self) -> None:
        tracker = ExitPartialFillTracker(
            active=True,
            order_id=1,
            partial_started_at=100,
            last_update_at=100,
            last_executed_qty=1.0,
        )
        decision = evaluate_exit_five_second_rule(
            tracker,
            is_exit_order=True,
            now=110,
            stall_seconds=5,
            risk_market_exit_in_same_loop=True,
        )
        self.assertFalse(decision.should_force_market_exit)
        self.assertEqual(decision.reason_code, "RISK_MARKET_EXIT_PRIORITY")


class Stage11LoggingTests(unittest.TestCase):
    def test_execution_flow_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = evaluate_pnl_branch_with_logging(avg_entry_price=100.0, mark_price=90.0)
            _ = sync_entry_fill_state_with_logging(
                "ENTRY_ORDER",
                phase="FIRST_ENTRY",
                order_status="PARTIALLY_FILLED",
            )
            _ = plan_risk_management_action_with_logging(
                current_state="PHASE1",
                symbol_matches_active=True,
                has_position=True,
                has_open_entry_order=False,
                pnl_branch="PNL_POSITIVE",
                has_tp_order=True,
                second_entry_fully_filled=False,
            )
            _ = plan_oco_mutual_cancel_with_logging(
                filled_order_id=1,
                open_exit_order_ids=[1, 2],
            )
            _ = execute_oco_mutual_cancel_with_logging(
                symbol="BTCUSDT",
                cancel_order_ids=[2],
                cancel_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
            )
            tracker = update_exit_partial_fill_tracker_with_logging(
                ExitPartialFillTracker(),
                is_exit_order=True,
                order_id=2,
                order_status="PARTIALLY_FILLED",
                executed_qty=1.0,
                updated_at=100,
            ).current
            _ = evaluate_exit_five_second_rule_with_logging(
                tracker,
                is_exit_order=True,
                now=101,
                stall_seconds=5,
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
