from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    TriggerCandidate,
    compute_trigger_threshold,
    evaluate_symbol_trigger,
    evaluate_trigger_loop,
    evaluate_trigger_loop_with_logging,
    is_trigger_satisfied,
    run_trigger_simulation,
    run_trigger_simulation_with_logging,
    SimulatedPriceSource,
)


class TriggerThresholdTests(unittest.TestCase):
    def test_threshold_first_entry(self) -> None:
        self.assertAlmostEqual(compute_trigger_threshold("FIRST_ENTRY", 100.0), 99.5, places=10)

    def test_threshold_second_entry(self) -> None:
        self.assertAlmostEqual(compute_trigger_threshold("SECOND_ENTRY", 120.0), 119.4, places=10)

    def test_threshold_tp(self) -> None:
        self.assertAlmostEqual(compute_trigger_threshold("TP", 95.0), 95.475, places=10)

    def test_threshold_breakeven(self) -> None:
        self.assertAlmostEqual(compute_trigger_threshold("BREAKEVEN", 120.0), 120.6, places=10)

    def test_threshold_first_entry_with_tick_size(self) -> None:
        self.assertAlmostEqual(
            compute_trigger_threshold("FIRST_ENTRY", 100.0, trigger_tick_size=0.1),
            99.9,
            places=10,
        )

    def test_is_trigger_satisfied_rules(self) -> None:
        tp_threshold = compute_trigger_threshold("TP", 95.0)
        self.assertTrue(
            is_trigger_satisfied("FIRST_ENTRY", current_mark_price=99.5, target_price=100.0)
        )
        self.assertFalse(
            is_trigger_satisfied("FIRST_ENTRY", current_mark_price=99.49, target_price=100.0)
        )
        self.assertTrue(
            is_trigger_satisfied("TP", current_mark_price=tp_threshold, target_price=95.0)
        )
        self.assertTrue(
            is_trigger_satisfied("BREAKEVEN", current_mark_price=120.6, target_price=120.0)
        )
        self.assertTrue(
            is_trigger_satisfied(
                "FIRST_ENTRY",
                current_mark_price=99.9,
                target_price=100.0,
                trigger_tick_size=0.1,
            )
        )
        self.assertFalse(
            is_trigger_satisfied(
                "FIRST_ENTRY",
                current_mark_price=99.89,
                target_price=100.0,
                trigger_tick_size=0.1,
            )
        )


class TriggerEvaluationTests(unittest.TestCase):
    def test_evaluate_symbol_trigger_immediate_satisfied(self) -> None:
        candidate = TriggerCandidate(
            symbol="BTCUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=100,
            message_id=10,
        )
        result = evaluate_symbol_trigger(candidate, current_mark_price=99.95)
        self.assertTrue(result.satisfied)
        self.assertEqual(result.reason_code, "TRIGGER_SATISFIED")

    def test_evaluate_symbol_trigger_missing_price(self) -> None:
        candidate = TriggerCandidate(
            symbol="BTCUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=100,
            message_id=10,
        )
        result = evaluate_symbol_trigger(candidate, current_mark_price=None)
        self.assertFalse(result.satisfied)
        self.assertEqual(result.reason_code, "MARK_PRICE_MISSING")

    def test_tiebreak_prefers_latest_received_at_local(self) -> None:
        c1 = TriggerCandidate(
            symbol="BTCUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=100,
            message_id=10,
        )
        c2 = TriggerCandidate(
            symbol="ETHUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=101,
            message_id=1,
        )
        result = evaluate_trigger_loop(
            [c1, c2],
            {"BTCUSDT": 100.0, "ETHUSDT": 100.0},
        )
        self.assertIsNotNone(result.selected_candidate)
        assert result.selected_candidate is not None
        self.assertEqual(result.selected_candidate.symbol, "ETHUSDT")
        self.assertEqual(result.reason_code, "MULTI_TRIGGER_TIEBREAK_RECEIVED_AT")
        self.assertEqual(result.dropped_symbols, ["BTCUSDT"])

    def test_tiebreak_prefers_larger_message_id_when_received_same(self) -> None:
        c1 = TriggerCandidate(
            symbol="BTCUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=100,
            message_id=10,
        )
        c2 = TriggerCandidate(
            symbol="ETHUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=100,
            message_id=11,
        )
        result = evaluate_trigger_loop(
            [c1, c2],
            {"BTCUSDT": 100.0, "ETHUSDT": 100.0},
        )
        self.assertIsNotNone(result.selected_candidate)
        assert result.selected_candidate is not None
        self.assertEqual(result.selected_candidate.symbol, "ETHUSDT")
        self.assertEqual(result.reason_code, "MULTI_TRIGGER_TIEBREAK_MESSAGE_ID")
        self.assertEqual(result.dropped_symbols, ["BTCUSDT"])

    def test_evaluate_trigger_loop_uses_symbol_tick_size_override(self) -> None:
        candidate = TriggerCandidate(
            symbol="BTCUSDT",
            trigger_kind="FIRST_ENTRY",
            target_price=100.0,
            received_at_local=100,
            message_id=10,
        )
        no_trigger = evaluate_trigger_loop(
            [candidate],
            {"BTCUSDT": 99.89},
            trigger_tick_size_by_symbol={"BTCUSDT": 0.1},
        )
        self.assertIsNone(no_trigger.selected_candidate)
        self.assertEqual(no_trigger.reason_code, "NO_TRIGGER_IN_LOOP")
        yes_trigger = evaluate_trigger_loop(
            [candidate],
            {"BTCUSDT": 99.9},
            trigger_tick_size_by_symbol={"BTCUSDT": 0.1},
        )
        self.assertIsNotNone(yes_trigger.selected_candidate)
        assert yes_trigger.selected_candidate is not None
        self.assertEqual(yes_trigger.selected_candidate.symbol, "BTCUSDT")


class TriggerSimulationTests(unittest.TestCase):
    def test_simulation_stops_at_first_selected_step(self) -> None:
        candidates = [
            TriggerCandidate(
                symbol="BTCUSDT",
                trigger_kind="FIRST_ENTRY",
                target_price=100.0,
                received_at_local=100,
                message_id=10,
            ),
            TriggerCandidate(
                symbol="ETHUSDT",
                trigger_kind="FIRST_ENTRY",
                target_price=100.0,
                received_at_local=101,
                message_id=5,
            ),
        ]
        source = SimulatedPriceSource(
            [
                {"BTCUSDT": 99.0, "ETHUSDT": 99.0},
                {"BTCUSDT": 100.0, "ETHUSDT": 100.0},
                {"BTCUSDT": 101.0, "ETHUSDT": 101.0},
            ]
        )
        report = run_trigger_simulation(
            candidates=candidates,
            price_source=source,
            stop_on_first_trigger=True,
        )
        self.assertEqual(report.total_steps, 2)
        self.assertTrue(report.stopped_early)
        self.assertEqual(report.first_selected_step, 1)
        selected = report.steps[1].loop_result.selected_candidate
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.symbol, "ETHUSDT")

    def test_simulation_keeps_running_if_stop_false(self) -> None:
        candidates = [
            TriggerCandidate(
                symbol="BTCUSDT",
                trigger_kind="FIRST_ENTRY",
                target_price=100.0,
                received_at_local=100,
                message_id=10,
            )
        ]
        source = SimulatedPriceSource(
            [
                {"BTCUSDT": 99.0},
                {"BTCUSDT": 100.0},
                {"BTCUSDT": 101.0},
            ]
        )
        report = run_trigger_simulation(
            candidates=candidates,
            price_source=source,
            stop_on_first_trigger=False,
        )
        self.assertEqual(report.total_steps, 3)
        self.assertFalse(report.stopped_early)
        self.assertEqual(report.first_selected_step, 1)


class Stage7LoggingTests(unittest.TestCase):
    def test_loop_logging_fields_exist(self) -> None:
        candidates = [
            TriggerCandidate(
                symbol="BTCUSDT",
                trigger_kind="FIRST_ENTRY",
                target_price=100.0,
                received_at_local=100,
                message_id=10,
            )
        ]
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = evaluate_trigger_loop_with_logging(candidates, {"BTCUSDT": 100.0})
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_simulation_logging_fields_exist(self) -> None:
        candidates = [
            TriggerCandidate(
                symbol="BTCUSDT",
                trigger_kind="FIRST_ENTRY",
                target_price=100.0,
                received_at_local=100,
                message_id=10,
            )
        ]
        source = SimulatedPriceSource([{"BTCUSDT": 100.0}])
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = run_trigger_simulation_with_logging(
                candidates=candidates,
                price_source=source,
                simulation_label="stage7-test",
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
