from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from auto_trade import (
    ExchangeSnapshot,
    PersistentRecoveryState,
    RecoveryRuntimeState,
    apply_exchange_snapshot,
    apply_exchange_snapshot_with_logging,
    begin_recovery,
    begin_recovery_with_logging,
    complete_recovery,
    complete_recovery_with_logging,
    plan_exit_reconciliation,
    plan_exit_reconciliation_with_logging,
    run_recovery_startup,
    run_recovery_startup_with_logging,
    stop_signal_loop,
    stop_signal_loop_with_logging,
)


class RecoveryCoreTests(unittest.TestCase):
    def test_begin_recovery_enables_lock_and_pauses_loop(self) -> None:
        state = RecoveryRuntimeState(
            recovery_locked=False,
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        result = begin_recovery(state)
        self.assertTrue(result.current.recovery_locked)
        self.assertTrue(result.current.signal_loop_paused)
        self.assertFalse(result.current.signal_loop_running)
        self.assertEqual(result.reason_code, "RECOVERY_LOCK_ENABLED")

    def test_complete_recovery_requires_snapshot_first(self) -> None:
        state = begin_recovery(RecoveryRuntimeState()).current
        state = replace(
            state,
            persisted_loaded=True,
            monitoring_queue_cleared=True,
        )
        result = complete_recovery(
            state,
            price_source_ready=True,
            reconciliation_ok=True,
        )
        self.assertTrue(result.current.recovery_locked)
        self.assertFalse(result.current.signal_loop_running)
        self.assertEqual(result.reason_code, "RECOVERY_WAIT_EXCHANGE_SNAPSHOT")

    def test_apply_snapshot_recomputes_entry_lock_from_open_orders(self) -> None:
        snapshot = ExchangeSnapshot(
            ok=True,
            reason_code="SNAPSHOT_READY",
            failure_reason="-",
            open_orders=[{"symbol": "BTCUSDT"}],
            positions=[],
            open_order_count=1,
            has_any_position=False,
            position_mode="ONE_WAY",
        )
        result = apply_exchange_snapshot(RecoveryRuntimeState(), snapshot=snapshot)
        self.assertTrue(result.current.snapshot_loaded)
        self.assertTrue(result.current.global_state.entry_locked)
        self.assertEqual(result.current.active_symbol_state, "ENTRY_ORDER")
        self.assertEqual(result.reason_code, "RECOVERY_SNAPSHOT_APPLIED")

    def test_apply_snapshot_prioritizes_position_state_over_open_order_state(self) -> None:
        snapshot = ExchangeSnapshot(
            ok=True,
            reason_code="SNAPSHOT_READY",
            failure_reason="-",
            open_orders=[{"symbol": "BTCUSDT"}],
            positions=[{"symbol": "BTCUSDT", "positionAmt": "-0.1"}],
            open_order_count=1,
            has_any_position=True,
            position_mode="ONE_WAY",
        )
        result = apply_exchange_snapshot(RecoveryRuntimeState(), snapshot=snapshot)
        self.assertTrue(result.current.snapshot_loaded)
        self.assertTrue(result.current.global_state.entry_locked)
        self.assertEqual(result.current.active_symbol_state, "PHASE1")
        self.assertEqual(result.reason_code, "RECOVERY_SNAPSHOT_APPLIED")

    def test_plan_exit_reconciliation_cancels_unneeded_orders_when_no_position(self) -> None:
        snapshot = ExchangeSnapshot(
            ok=True,
            reason_code="SNAPSHOT_READY",
            failure_reason="-",
            open_orders=[{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}],
            positions=[],
            open_order_count=2,
            has_any_position=False,
            position_mode="ONE_WAY",
        )
        plan = plan_exit_reconciliation(snapshot)
        self.assertEqual(plan.action_code, "CANCEL_UNNEEDED_ORDERS")
        self.assertEqual(list(plan.cancel_symbols), ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(list(plan.register_symbols), [])
        self.assertFalse(plan.require_exit_registration)

    def test_plan_exit_reconciliation_skips_register_when_position_symbol_already_has_order(self) -> None:
        snapshot = ExchangeSnapshot(
            ok=True,
            reason_code="SNAPSHOT_READY",
            failure_reason="-",
            open_orders=[{"symbol": "BTCUSDT"}],
            positions=[{"symbol": "BTCUSDT", "positionAmt": "-0.1"}],
            open_order_count=1,
            has_any_position=True,
            position_mode="ONE_WAY",
        )
        plan = plan_exit_reconciliation(snapshot)
        self.assertEqual(plan.action_code, "NONE")
        self.assertEqual(list(plan.cancel_symbols), [])
        self.assertEqual(list(plan.register_symbols), [])
        self.assertFalse(plan.require_exit_registration)

    def test_run_recovery_startup_success_resumes_signal_loop_after_snapshot(self) -> None:
        result = run_recovery_startup(
            RecoveryRuntimeState(),
            load_persisted_state=lambda: PersistentRecoveryState(
                last_message_ids={-1001: 10},
                cooldown_by_symbol={"BTCUSDT": 100},
                received_at_by_symbol={"BTCUSDT": 100},
                message_id_by_symbol={"BTCUSDT": 10},
            ),
            fetch_exchange_snapshot=lambda: ExchangeSnapshot(
                ok=True,
                reason_code="SNAPSHOT_READY",
                failure_reason="-",
                open_orders=[],
                positions=[],
                open_order_count=0,
                has_any_position=False,
                position_mode="ONE_WAY",
            ),
            check_price_source_ready=lambda: True,
            cleared_monitoring_queue_count=3,
        )
        self.assertTrue(result.success)
        self.assertFalse(result.state.recovery_locked)
        self.assertTrue(result.state.signal_loop_running)
        self.assertFalse(result.state.signal_loop_paused)
        self.assertEqual(result.reason_code, "RECOVERY_COMPLETED_SIGNAL_LOOP_RESUMED")
        self.assertEqual(result.state.message_id_by_symbol.get("BTCUSDT"), 10)

    def test_run_recovery_startup_snapshot_failure_keeps_lock(self) -> None:
        result = run_recovery_startup(
            RecoveryRuntimeState(),
            load_persisted_state=lambda: PersistentRecoveryState(),
            fetch_exchange_snapshot=lambda: ExchangeSnapshot(
                ok=False,
                reason_code="SNAPSHOT_HTTP_ERROR",
                failure_reason="timeout",
                open_orders=[],
                positions=[],
                open_order_count=0,
                has_any_position=False,
                position_mode="UNKNOWN",
            ),
            check_price_source_ready=lambda: True,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.state.recovery_locked)
        self.assertEqual(result.reason_code, "RECOVERY_SNAPSHOT_FETCH_FAILED_SNAPSHOT_HTTP_ERROR")

    def test_run_recovery_startup_requires_reconcile_handler_when_action_needed(self) -> None:
        result = run_recovery_startup(
            RecoveryRuntimeState(),
            load_persisted_state=lambda: PersistentRecoveryState(),
            fetch_exchange_snapshot=lambda: ExchangeSnapshot(
                ok=True,
                reason_code="SNAPSHOT_READY",
                failure_reason="-",
                open_orders=[],
                positions=[{"symbol": "BTCUSDT", "positionAmt": "0.1"}],
                open_order_count=0,
                has_any_position=True,
                position_mode="ONE_WAY",
            ),
            check_price_source_ready=lambda: True,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.state.recovery_locked)
        self.assertEqual(result.reason_code, "RECOVERY_RECONCILE_HANDLER_MISSING")

    def test_run_recovery_startup_waits_until_price_source_ready(self) -> None:
        result = run_recovery_startup(
            RecoveryRuntimeState(),
            load_persisted_state=lambda: PersistentRecoveryState(),
            fetch_exchange_snapshot=lambda: ExchangeSnapshot(
                ok=True,
                reason_code="SNAPSHOT_READY",
                failure_reason="-",
                open_orders=[],
                positions=[],
                open_order_count=0,
                has_any_position=False,
                position_mode="ONE_WAY",
            ),
            check_price_source_ready=lambda: False,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.state.recovery_locked)
        self.assertFalse(result.state.signal_loop_running)
        self.assertEqual(result.reason_code, "RECOVERY_WAIT_PRICE_SOURCE_HEALTHY")

    def test_stop_signal_loop_sets_paused_state(self) -> None:
        state = RecoveryRuntimeState(
            recovery_locked=False,
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        result = stop_signal_loop(state)
        self.assertFalse(result.current.recovery_locked)
        self.assertTrue(result.current.signal_loop_paused)
        self.assertFalse(result.current.signal_loop_running)


class Stage12LoggingTests(unittest.TestCase):
    def test_recovery_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            state = begin_recovery_with_logging(
                RecoveryRuntimeState(),
                loop_label="stage12-begin",
            ).current
            snapshot = ExchangeSnapshot(
                ok=True,
                reason_code="SNAPSHOT_READY",
                failure_reason="-",
                open_orders=[],
                positions=[],
                open_order_count=0,
                has_any_position=False,
                position_mode="ONE_WAY",
            )
            _ = apply_exchange_snapshot_with_logging(
                state,
                snapshot=snapshot,
                loop_label="stage12-snapshot",
            )
            _ = plan_exit_reconciliation_with_logging(
                snapshot=snapshot,
                loop_label="stage12-plan",
            )
            _ = complete_recovery_with_logging(
                state,
                price_source_ready=False,
                reconciliation_ok=True,
                loop_label="stage12-complete",
            )
            _ = run_recovery_startup_with_logging(
                RecoveryRuntimeState(),
                load_persisted_state=lambda: PersistentRecoveryState(),
                fetch_exchange_snapshot=lambda: snapshot,
                check_price_source_ready=lambda: True,
                cleared_monitoring_queue_count=0,
                loop_label="stage12-run",
            )
            _ = stop_signal_loop_with_logging(
                state,
                loop_label="stage12-stop",
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
