from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    GlobalState,
    apply_symbol_event,
    apply_symbol_event_with_logging,
    set_safety_lock,
    set_safety_lock_with_logging,
    update_account_activity,
    update_account_activity_with_logging,
)


class GlobalStateMachineTests(unittest.TestCase):
    def test_entry_lock_opens_when_no_position_and_no_open_order(self) -> None:
        state = GlobalState(has_any_position=False, has_any_open_order=False, safety_locked=False)
        self.assertFalse(state.entry_locked)
        self.assertEqual(state.entry_state, "ENTRY_OPEN")
        self.assertEqual(state.global_mode, "GLOBAL_IDLE")
        self.assertFalse(state.global_blocked)

    def test_entry_lock_blocks_when_position_exists(self) -> None:
        state = GlobalState(has_any_position=True, has_any_open_order=False, safety_locked=False)
        self.assertTrue(state.entry_locked)
        self.assertEqual(state.entry_state, "ENTRY_LOCKED")
        self.assertEqual(state.global_mode, "GLOBAL_BLOCKED")
        self.assertTrue(state.global_blocked)

    def test_entry_lock_blocks_when_open_order_exists(self) -> None:
        state = GlobalState(has_any_position=False, has_any_open_order=True, safety_locked=False)
        self.assertTrue(state.entry_locked)
        self.assertEqual(state.entry_state, "ENTRY_LOCKED")
        self.assertEqual(state.global_mode, "GLOBAL_BLOCKED")
        self.assertTrue(state.global_blocked)

    def test_safety_lock_blocks_even_when_entry_open(self) -> None:
        state = GlobalState(has_any_position=False, has_any_open_order=False, safety_locked=True)
        self.assertFalse(state.entry_locked)
        self.assertEqual(state.entry_state, "ENTRY_OPEN")
        self.assertEqual(state.global_mode, "GLOBAL_BLOCKED")
        self.assertTrue(state.global_blocked)

    def test_update_account_activity_transition(self) -> None:
        prev = GlobalState(has_any_position=False, has_any_open_order=False, safety_locked=False)
        result = update_account_activity(prev, has_any_position=False, has_any_open_order=True)
        self.assertTrue(result.changed)
        self.assertEqual(result.current.entry_state, "ENTRY_LOCKED")
        self.assertEqual(result.current.global_mode, "GLOBAL_BLOCKED")
        self.assertEqual(result.reason_code, "ENTRY_LOCK_CHANGED")

    def test_set_and_release_safety_lock(self) -> None:
        prev = GlobalState(has_any_position=False, has_any_open_order=False, safety_locked=False)
        locked = set_safety_lock(prev, enabled=True)
        self.assertTrue(locked.changed)
        self.assertTrue(locked.current.safety_locked)
        self.assertEqual(locked.current.global_mode, "GLOBAL_BLOCKED")

        released = set_safety_lock(locked.current, enabled=False)
        self.assertTrue(released.changed)
        self.assertFalse(released.current.safety_locked)
        self.assertEqual(released.current.global_mode, "GLOBAL_IDLE")


class SymbolStateMachineTests(unittest.TestCase):
    def test_happy_path_idle_to_phase2(self) -> None:
        state = "IDLE"

        step1 = apply_symbol_event(state, "START_MONITORING")
        self.assertTrue(step1.accepted)
        self.assertEqual(step1.current_state, "MONITORING")

        step2 = apply_symbol_event(step1.current_state, "SUBMIT_ENTRY_ORDER")
        self.assertTrue(step2.accepted)
        self.assertEqual(step2.current_state, "ENTRY_ORDER")

        step3 = apply_symbol_event(step2.current_state, "FIRST_ENTRY_FILLED")
        self.assertTrue(step3.accepted)
        self.assertEqual(step3.current_state, "PHASE1")

        step4 = apply_symbol_event(step3.current_state, "SECOND_ENTRY_PARTIAL_OR_FILLED")
        self.assertTrue(step4.accepted)
        self.assertEqual(step4.current_state, "PHASE2")

    def test_partial_fill_keeps_entry_order(self) -> None:
        step = apply_symbol_event("ENTRY_ORDER", "PARTIAL_FILL")
        self.assertTrue(step.accepted)
        self.assertFalse(step.changed)
        self.assertEqual(step.current_state, "ENTRY_ORDER")
        self.assertEqual(step.reason_code, "NO_STATE_CHANGE")

    def test_invalid_transition_rejected(self) -> None:
        step = apply_symbol_event("IDLE", "FIRST_ENTRY_FILLED")
        self.assertFalse(step.accepted)
        self.assertFalse(step.changed)
        self.assertEqual(step.reason_code, "INVALID_TRANSITION")
        self.assertEqual(step.current_state, "IDLE")

    def test_reset_from_any_state_to_idle(self) -> None:
        for current in ["IDLE", "MONITORING", "ENTRY_ORDER", "PHASE1", "PHASE2"]:
            step = apply_symbol_event(current, "RESET")
            self.assertTrue(step.accepted)
            self.assertEqual(step.current_state, "IDLE")


class StateMachineLoggingTests(unittest.TestCase):
    def test_global_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            prev = GlobalState(has_any_position=False, has_any_open_order=False, safety_locked=False)
            _ = update_account_activity_with_logging(
                prev,
                has_any_position=True,
                has_any_open_order=False,
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_safety_lock_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            prev = GlobalState(has_any_position=False, has_any_open_order=False, safety_locked=False)
            _ = set_safety_lock_with_logging(prev, enabled=True)
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_symbol_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = apply_symbol_event_with_logging("IDLE", "START_MONITORING")
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
