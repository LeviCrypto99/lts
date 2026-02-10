from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    GlobalState,
    PriceSourceState,
    apply_price_source_guard,
    apply_price_source_guard_with_logging,
    get_mark_price,
    record_rest_mark_price,
    record_ws_mark_price,
    update_price_source_mode,
    update_price_source_mode_with_logging,
)


class PriceSourceModeTests(unittest.TestCase):
    def test_ws_primary_stays_active_when_ws_is_fresh(self) -> None:
        state = PriceSourceState()
        state = record_ws_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=100.0,
            received_at=100,
        ).current
        result = update_price_source_mode(
            state,
            now=104,
            ws_stale_fallback_seconds=5,
        )
        self.assertEqual(result.current_mode, "WS_PRIMARY")
        self.assertFalse(result.changed)
        self.assertEqual(result.reason_code, "WS_PRIMARY_CONTINUE")

    def test_switch_to_rest_fallback_after_5_seconds_ws_gap(self) -> None:
        state = PriceSourceState()
        state = record_ws_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=100.0,
            received_at=100,
        ).current
        result = update_price_source_mode(
            state,
            now=105,
            ws_stale_fallback_seconds=5,
        )
        self.assertEqual(result.current_mode, "REST_FALLBACK")
        self.assertTrue(result.changed)
        self.assertEqual(result.reason_code, "WS_STALE_SWITCH_TO_REST")

    def test_ws_recovery_immediately_restores_ws_primary(self) -> None:
        state = PriceSourceState()
        state = record_ws_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=100.0,
            received_at=100,
        ).current
        state = update_price_source_mode(
            state,
            now=106,
            ws_stale_fallback_seconds=5,
        ).state
        self.assertEqual(state.mode, "REST_FALLBACK")

        ws_update = record_ws_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=101.0,
            received_at=107,
        )
        self.assertEqual(ws_update.current.mode, "WS_PRIMARY")
        self.assertEqual(ws_update.reason_code, "WS_PRICE_RECORDED_AND_MODE_RECOVERED")


class MarkPriceSelectionTests(unittest.TestCase):
    def test_get_mark_price_prefers_ws_in_ws_primary_mode(self) -> None:
        state = PriceSourceState()
        state = record_ws_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=100.0,
            received_at=100,
        ).current
        state = record_rest_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=99.5,
            received_at=103,
        ).current
        read = get_mark_price(
            state,
            symbol="BTCUSDT",
            now=104,
            ws_stale_fallback_seconds=5,
        )
        self.assertEqual(read.used_mode, "WS_PRIMARY")
        self.assertEqual(read.source, "WS")
        self.assertEqual(read.mark_price, 100.0)
        self.assertEqual(read.reason_code, "PRIMARY_SOURCE_PRICE")

    def test_get_mark_price_uses_rest_in_fallback_mode(self) -> None:
        state = PriceSourceState()
        state = record_ws_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=100.0,
            received_at=100,
        ).current
        state = record_rest_mark_price(
            state,
            symbol="BTCUSDT",
            mark_price=99.4,
            received_at=104,
        ).current
        read = get_mark_price(
            state,
            symbol="BTCUSDT",
            now=106,
            ws_stale_fallback_seconds=5,
        )
        self.assertEqual(read.used_mode, "REST_FALLBACK")
        self.assertEqual(read.source, "REST")
        self.assertEqual(read.mark_price, 99.4)
        self.assertEqual(read.reason_code, "PRIMARY_SOURCE_PRICE")


class SafetyGuardTests(unittest.TestCase):
    def test_dual_stale_with_position_forces_market_exit_action(self) -> None:
        global_state = GlobalState(
            has_any_position=True,
            has_any_open_order=False,
            safety_locked=False,
        )
        result = apply_price_source_guard(
            global_state,
            PriceSourceState(),
            now=200,
            stale_mark_price_seconds=15,
            has_monitoring=False,
        )
        self.assertTrue(result.decision.target_safety_locked)
        self.assertTrue(result.decision.stale_detected)
        self.assertEqual(result.decision.action, "FORCE_MARKET_EXIT")
        self.assertTrue(result.global_transition.current.safety_locked)
        self.assertEqual(result.global_transition.reason_code, "SAFETY_LOCK_CHANGED")

    def test_dual_stale_without_position_cancels_and_resets(self) -> None:
        global_state = GlobalState(
            has_any_position=False,
            has_any_open_order=True,
            safety_locked=False,
        )
        result = apply_price_source_guard(
            global_state,
            PriceSourceState(),
            now=200,
            stale_mark_price_seconds=15,
            has_monitoring=True,
        )
        self.assertTrue(result.decision.target_safety_locked)
        self.assertEqual(result.decision.action, "CANCEL_OPEN_ORDERS_AND_RESET")
        self.assertTrue(result.global_transition.current.safety_locked)

    def test_safety_lock_release_keeps_entry_lock_when_open_order_exists(self) -> None:
        price_state = record_ws_mark_price(
            PriceSourceState(),
            symbol="BTCUSDT",
            mark_price=100.0,
            received_at=300,
        ).current
        global_state = GlobalState(
            has_any_position=False,
            has_any_open_order=True,
            safety_locked=True,
        )
        result = apply_price_source_guard(
            global_state,
            price_state,
            now=302,
            stale_mark_price_seconds=15,
            has_monitoring=False,
        )
        self.assertFalse(result.decision.target_safety_locked)
        self.assertEqual(result.decision.action, "NONE")
        self.assertFalse(result.global_transition.current.safety_locked)
        self.assertTrue(result.global_transition.current.entry_locked)
        self.assertTrue(result.global_transition.current.global_blocked)


class Stage8LoggingTests(unittest.TestCase):
    def test_mode_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = update_price_source_mode_with_logging(
                PriceSourceState(),
                now=100,
                ws_stale_fallback_seconds=5,
                loop_label="stage8-mode",
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_guard_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = apply_price_source_guard_with_logging(
                GlobalState(has_any_position=True, has_any_open_order=False, safety_locked=False),
                PriceSourceState(),
                now=200,
                stale_mark_price_seconds=15,
                has_monitoring=False,
                loop_label="stage8-guard",
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
