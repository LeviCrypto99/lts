from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    AutoTradeRuntime,
    AutoTradeSettings,
    ExchangeSnapshot,
    GatewayCallResult,
    GlobalState,
    PersistentRecoveryState,
    RetryPolicy,
    SymbolFilterRules,
    TriggerCandidate,
    apply_price_source_and_guard,
    execute_oco_cancel_flow,
    handle_leading_market_signal,
    handle_risk_management_signal,
    process_telegram_message,
    run_recovery_startup_flow,
    run_trigger_entry_cycle,
    sync_entry_fill_flow,
    update_exit_partial_and_check_five_second,
)


def _default_settings() -> AutoTradeSettings:
    return AutoTradeSettings(
        entry_signal_channel_id=-1003782821900,
        risk_signal_channel_id=-1003761851285,
        cooldown_minutes=10,
        second_entry_percent=15.0,
        margin_buffer_pct=0.01,
        ws_stale_fallback_seconds=5,
        stale_mark_price_seconds=15,
        rate_limit_fail_threshold=5,
        rate_limit_recovery_threshold=3,
    )


def _leading_message_text() -> str:
    return "\n".join(
        [
            "🔥 주도 마켓 (BTC)",
            "⏱ 펀딩비: +0.01% / 00:10:00",
            "🥇 등락률: -2.00% (하락) 상위 20위",
            "🏷 카테고리: AI",
        ]
    )


def _exchange_info() -> dict:
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "quoteAsset": "USDT",
                "contractType": "PERPETUAL",
            }
        ]
    }


def _candles() -> list[dict]:
    return [
        {"datetime": "2026-02-07T00:00:00", "high": 100.0, "low": 90.0, "close": 95.0},
        {"datetime": "2026-02-07T00:03:00", "high": 110.0, "low": 92.0, "close": 100.0},
    ]


class OrchestratorIntegrationTests(unittest.TestCase):
    def test_leading_signal_registers_trigger_candidate(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        updated, result = handle_leading_market_signal(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=101,
            message_text=_leading_message_text(),
            received_at_local=1_700_000_000,
            exchange_info=_exchange_info(),
            candles=_candles(),
            entry_mode="AGGRESSIVE",
            loop_label="stage13-leading",
        )
        self.assertTrue(result.accepted)
        self.assertTrue(result.trigger_registered)
        self.assertEqual(updated.symbol_state, "MONITORING")
        self.assertIn("BTCUSDT", updated.pending_trigger_candidates)
        self.assertEqual(updated.last_message_ids[runtime.settings.entry_signal_channel_id], 101)
        self.assertEqual(updated.cooldown_by_symbol["BTCUSDT"], 1_700_000_000)
        self.assertEqual(updated.message_id_by_symbol["BTCUSDT"], 101)

    @patch("auto_trade.orchestrator.time.time", return_value=1_700_000_001.0)
    def test_leading_signal_target_uses_processing_time_when_received_time_is_stale(
        self,
        _mocked_time,
    ) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        candles = [
            {"timestamp": 100, "close_time": 500, "high": 100.0, "low": 90.0, "close": 95.0},
            {"timestamp": 600, "close_time": 1000, "high": 110.0, "low": 92.0, "close": 101.0},
            {"timestamp": 1100, "close_time": 1500, "high": 120.0, "low": 93.0, "close": 111.0},
        ]
        updated, result = handle_leading_market_signal(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=102,
            message_text=_leading_message_text(),
            received_at_local=1_700_000_000,
            exchange_info=_exchange_info(),
            candles=candles,
            entry_mode="AGGRESSIVE",
            loop_label="stage13-leading-stale-received-at",
        )
        self.assertTrue(result.accepted)
        self.assertIn("BTCUSDT", updated.pending_trigger_candidates)
        self.assertEqual(updated.pending_trigger_candidates["BTCUSDT"].target_price, 120.0)

    def test_trigger_cycle_submits_first_entry_and_locks_entry(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=101,
                )
            },
        )
        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
            loop_label="stage13-trigger",
        )
        self.assertTrue(result.attempted)
        self.assertTrue(result.success)
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")
        self.assertEqual(updated.pending_trigger_candidates, {})
        self.assertTrue(updated.global_state.entry_locked)

    def test_trigger_cycle_allows_second_entry_when_only_exit_orders_are_open(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            global_state=GlobalState(has_any_position=True, has_any_open_order=True),
            symbol_state="PHASE1",
            active_symbol="BTCUSDT",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="SECOND_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=401,
                )
            },
        )
        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
            has_open_entry_order_for_symbol=lambda _symbol: False,
            loop_label="stage13-trigger-second-entry-exit-only-open",
        )
        self.assertTrue(result.attempted)
        self.assertTrue(result.success)
        self.assertEqual(result.selected_trigger_kind, "SECOND_ENTRY")
        self.assertTrue(updated.second_entry_order_pending)

    def test_trigger_cycle_blocks_second_entry_when_open_entry_order_exists(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            global_state=GlobalState(has_any_position=True, has_any_open_order=True),
            symbol_state="PHASE1",
            active_symbol="BTCUSDT",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="SECOND_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=402,
                )
            },
        )
        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
            has_open_entry_order_for_symbol=lambda _symbol: True,
            loop_label="stage13-trigger-second-entry-entry-open",
        )
        self.assertFalse(result.attempted)
        self.assertFalse(result.success)
        self.assertEqual(result.reason_code, "GLOBAL_BLOCKED_OR_NEW_ORDER_LOCKED")
        self.assertEqual(updated, runtime)

    def test_trigger_cycle_first_entry_uses_aggressive_budget_multiplier(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=102,
                    entry_mode="AGGRESSIVE",
                )
            },
        )
        captured: dict[str, object] = {}

        def _create_call(params: dict) -> GatewayCallResult:
            captured.update(params)
            return GatewayCallResult(ok=True, reason_code="OK")

        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=_create_call,
            loop_label="stage13-trigger-aggressive-budget",
        )
        self.assertTrue(result.success)
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")
        self.assertEqual(captured.get("quantity"), 10.0)

    def test_trigger_cycle_uses_stable_client_order_id_on_retries(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=321,
                )
            },
        )
        observed_client_order_ids: list[str] = []

        def _create_call(params: dict) -> GatewayCallResult:
            observed_client_order_ids.append(str(params.get("newClientOrderId", "")))
            if len(observed_client_order_ids) < 3:
                return GatewayCallResult(ok=False, reason_code="TIMEOUT")
            return GatewayCallResult(ok=True, reason_code="OK")

        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=_create_call,
            retry_policy=RetryPolicy(max_attempts=3, retryable_reason_codes=("TIMEOUT",)),
            loop_label="stage13-trigger-client-id-retry",
        )
        self.assertTrue(result.success)
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")
        self.assertEqual(len(observed_client_order_ids), 3)
        self.assertTrue(all(value == observed_client_order_ids[0] for value in observed_client_order_ids))
        self.assertTrue(observed_client_order_ids[0].startswith("LTS-F1-"))

    def test_trigger_cycle_uses_tick_normalized_target_for_trigger_threshold(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.03,
                    received_at_local=1_000,
                    message_id=401,
                )
            },
        )
        captured: dict[str, object] = {}

        def _create_call(params: dict) -> GatewayCallResult:
            captured.update(params)
            return GatewayCallResult(ok=True, reason_code="OK")

        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 99.91},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=_create_call,
            loop_label="stage13-trigger-normalized-target",
        )
        self.assertTrue(result.success)
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")
        self.assertEqual(captured.get("price"), 100.0)

    def test_trigger_cycle_pre_order_setup_failure_resets_state(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            active_symbol="BTCUSDT",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=101,
                )
            },
        )
        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=lambda _params: GatewayCallResult(ok=True, reason_code="OK"),
            pre_order_setup=lambda _symbol, _trigger_kind, _loop_label: (
                False,
                "POSITION_MODE_FETCH_FAILED",
                "position mode unknown",
                True,
            ),
            loop_label="stage13-trigger-pre-order-setup-fail",
        )
        self.assertTrue(result.attempted)
        self.assertFalse(result.success)
        self.assertTrue(result.reason_code.startswith("PRE_ORDER_SETUP_FAILED_"))
        self.assertEqual(updated.symbol_state, "IDLE")
        self.assertIsNone(updated.active_symbol)
        self.assertEqual(updated.pending_trigger_candidates, {})

    def test_trigger_cycle_pre_order_setup_failure_non_reset_reassigns_active_symbol(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            active_symbol="ETHUSDT",
            second_entry_order_pending=True,
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=100,
                ),
                "ETHUSDT": TriggerCandidate(
                    symbol="ETHUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=2_000,
                    message_id=200,
                ),
            },
        )

        def _create_call(_params: dict) -> GatewayCallResult:
            raise AssertionError("create_call must not run when pre-order setup fails")

        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0, "ETHUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                ),
                "ETHUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                ),
            },
            position_mode="ONE_WAY",
            create_call=_create_call,
            pre_order_setup=lambda _symbol, _trigger_kind, _loop_label: (
                False,
                "POSITION_MODE_UNKNOWN",
                "position mode unresolved",
                False,
            ),
            loop_label="stage13-trigger-pre-order-non-reset-reassign",
        )
        self.assertTrue(result.attempted)
        self.assertFalse(result.success)
        self.assertEqual(result.selected_symbol, "ETHUSDT")
        self.assertEqual(updated.symbol_state, "MONITORING")
        self.assertEqual(updated.active_symbol, "BTCUSDT")
        self.assertEqual(set(updated.pending_trigger_candidates.keys()), {"BTCUSDT"})
        self.assertTrue(updated.second_entry_order_pending)

    def test_trigger_cycle_pre_order_setup_failure_non_reset_sets_idle_when_pending_empty(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            active_symbol="BTCUSDT",
            second_entry_order_pending=True,
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=101,
                )
            },
        )

        def _create_call(_params: dict) -> GatewayCallResult:
            raise AssertionError("create_call must not run when pre-order setup fails")

        updated, result = run_trigger_entry_cycle(
            runtime,
            mark_prices={"BTCUSDT": 100.0},
            wallet_balance_usdt=1000.0,
            available_usdt=500.0,
            filter_rules_by_symbol={
                "BTCUSDT": SymbolFilterRules(
                    tick_size=0.1,
                    step_size=0.001,
                    min_qty=0.001,
                    min_notional=5.0,
                )
            },
            position_mode="ONE_WAY",
            create_call=_create_call,
            pre_order_setup=lambda _symbol, _trigger_kind, _loop_label: (
                False,
                "POSITION_MODE_UNKNOWN",
                "position mode unresolved",
                False,
            ),
            loop_label="stage13-trigger-pre-order-non-reset-idle",
        )
        self.assertTrue(result.attempted)
        self.assertFalse(result.success)
        self.assertEqual(updated.symbol_state, "IDLE")
        self.assertIsNone(updated.active_symbol)
        self.assertEqual(updated.pending_trigger_candidates, {})
        self.assertFalse(updated.second_entry_order_pending)

    def test_recovery_lock_blocks_leading_signal_handling(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            recovery_locked=True,
            signal_loop_paused=True,
            signal_loop_running=False,
        )
        updated, result = handle_leading_market_signal(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=101,
            message_text=_leading_message_text(),
            received_at_local=1_000,
            exchange_info=_exchange_info(),
            candles=_candles(),
            entry_mode="AGGRESSIVE",
            loop_label="stage13-recovery-gate",
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_code, "RECOVERY_LOCKED_SIGNAL_PAUSED")
        self.assertEqual(updated.last_message_ids, {})

    def test_leading_signal_same_symbol_monitoring_is_ignored(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            active_symbol="BTCUSDT",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=900,
                    message_id=100,
                )
            },
            cooldown_by_symbol={"BTCUSDT": 900},
        )
        updated, result = handle_leading_market_signal(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=101,
            message_text=_leading_message_text(),
            received_at_local=1_000,
            exchange_info=_exchange_info(),
            candles=_candles(),
            entry_mode="AGGRESSIVE",
            loop_label="stage13-leading-duplicate-monitoring",
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_code, "SYMBOL_ALREADY_MONITORING")
        self.assertEqual(updated.pending_trigger_candidates["BTCUSDT"].message_id, 100)
        self.assertEqual(updated.cooldown_by_symbol["BTCUSDT"], 900)

    def test_leading_parse_failure_after_symbol_validation_records_cooldown(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        invalid_text = "\n".join(
            [
                "🔥 주도 마켓 (BTC)",
                "⏱ 펀딩비: +0.01% / 00:10:00",
                "🏷 카테고리: AI",
            ]
        )
        updated, result = handle_leading_market_signal(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=500,
            message_text=invalid_text,
            received_at_local=1_500,
            exchange_info=_exchange_info(),
            candles=_candles(),
            entry_mode="AGGRESSIVE",
            loop_label="stage13-leading-field-parse-fail",
        )
        self.assertFalse(result.accepted)
        self.assertTrue(result.reason_code.startswith("LEADING_PARSE_FAILED_"))
        self.assertEqual(result.symbol, "BTCUSDT")
        self.assertEqual(updated.cooldown_by_symbol.get("BTCUSDT"), 1_500)

    def test_leading_symbol_validation_failure_still_records_cooldown(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        updated, result = handle_leading_market_signal(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=501,
            message_text=_leading_message_text(),
            received_at_local=1_600,
            exchange_info={"symbols": []},
            candles=_candles(),
            entry_mode="AGGRESSIVE",
            loop_label="stage13-leading-validate-fail-cooldown",
        )
        self.assertFalse(result.accepted)
        self.assertTrue(result.reason_code.startswith("SYMBOL_VALIDATE_FAILED_"))
        self.assertEqual(result.symbol, "BTCUSDT")
        self.assertEqual(updated.cooldown_by_symbol.get("BTCUSDT"), 1_600)

    def test_risk_signal_negative_pnl_prioritizes_market_exit(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="ENTRY_ORDER",
            active_symbol="BTCUSDT",
        )
        updated, result = handle_risk_management_signal(
            runtime,
            channel_id=runtime.settings.risk_signal_channel_id,
            message_id=301,
            message_text="리스크 알림\nBinance: BTCUSDT.P",
            avg_entry_price=100.0,
            mark_price=110.0,
            has_position=True,
            has_open_entry_order=True,
            has_tp_order=False,
            second_entry_fully_filled=False,
            exchange_info=_exchange_info(),
            loop_label="stage13-risk",
        )
        self.assertTrue(result.accepted)
        self.assertTrue(result.actionable)
        self.assertEqual(result.action_code, "MARKET_EXIT_PRIORITY")
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")

    def test_risk_signal_phase2_negative_pnl_prioritizes_market_exit(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE2",
            active_symbol="BTCUSDT",
        )
        updated, result = handle_risk_management_signal(
            runtime,
            channel_id=runtime.settings.risk_signal_channel_id,
            message_id=302,
            message_text="리스크 알림\nBinance: BTCUSDT.P",
            avg_entry_price=100.0,
            mark_price=110.0,
            has_position=True,
            has_open_entry_order=False,
            has_tp_order=False,
            second_entry_fully_filled=True,
            exchange_info=_exchange_info(),
            loop_label="stage13-risk-phase2-negative-market-exit",
        )
        self.assertTrue(result.accepted)
        self.assertTrue(result.actionable)
        self.assertEqual(result.action_code, "MARKET_EXIT_PRIORITY")
        self.assertEqual(result.reason_code, "RISK_PNL_LE_ZERO_MARKET_EXIT")
        self.assertTrue(result.submit_market_exit)
        self.assertEqual(updated.symbol_state, "PHASE2")

    def test_risk_signal_symbol_validation_failure_is_ignored(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="ENTRY_ORDER",
            active_symbol="BTCUSDT",
        )
        updated, result = handle_risk_management_signal(
            runtime,
            channel_id=runtime.settings.risk_signal_channel_id,
            message_id=302,
            message_text="리스크 알림\nBinance: ETHUSDT.P",
            avg_entry_price=100.0,
            mark_price=110.0,
            has_position=True,
            has_open_entry_order=True,
            has_tp_order=False,
            second_entry_fully_filled=False,
            exchange_info={
                "symbols": [
                    {
                        "symbol": "ETHUSDT",
                        "status": "PENDING_TRADING",
                        "quoteAsset": "USDT",
                        "contractType": "PERPETUAL",
                    }
                ]
            },
            loop_label="stage13-risk-symbol-validate-fail",
        )
        self.assertFalse(result.accepted)
        self.assertTrue(result.reason_code.startswith("RISK_SYMBOL_VALIDATE_FAILED_"))
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")

    def test_risk_signal_on_monitored_non_active_symbol_removes_only_that_symbol(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            active_symbol="BTCUSDT",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=100,
                ),
                "ETHUSDT": TriggerCandidate(
                    symbol="ETHUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=200.0,
                    received_at_local=2_000,
                    message_id=200,
                ),
            },
        )
        exchange_info = {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
            ]
        }
        updated, result = handle_risk_management_signal(
            runtime,
            channel_id=runtime.settings.risk_signal_channel_id,
            message_id=350,
            message_text="리스크 알림\nBinance: ETHUSDT.P",
            avg_entry_price=100.0,
            mark_price=100.0,
            has_position=False,
            has_open_entry_order=False,
            has_tp_order=False,
            second_entry_fully_filled=False,
            exchange_info=exchange_info,
            loop_label="stage13-risk-monitoring-remove-one",
        )
        self.assertTrue(result.accepted)
        self.assertTrue(result.actionable)
        self.assertEqual(result.reason_code, "RISK_MONITORING_RESET")
        self.assertEqual(updated.symbol_state, "MONITORING")
        self.assertEqual(updated.active_symbol, "BTCUSDT")
        self.assertEqual(set(updated.pending_trigger_candidates.keys()), {"BTCUSDT"})

    def test_risk_signal_unmonitored_symbol_is_ignored_in_monitoring_state(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="MONITORING",
            active_symbol="BTCUSDT",
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1_000,
                    message_id=100,
                )
            },
        )
        exchange_info = {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
            ]
        }
        updated, result = handle_risk_management_signal(
            runtime,
            channel_id=runtime.settings.risk_signal_channel_id,
            message_id=351,
            message_text="리스크 알림\nBinance: ETHUSDT.P",
            avg_entry_price=100.0,
            mark_price=100.0,
            has_position=False,
            has_open_entry_order=False,
            has_tp_order=False,
            second_entry_fully_filled=False,
            exchange_info=exchange_info,
            loop_label="stage13-risk-monitoring-ignore-unrelated",
        )
        self.assertFalse(result.actionable)
        self.assertEqual(result.reason_code, "RISK_SYMBOL_MISMATCH")
        self.assertEqual(updated.symbol_state, "MONITORING")
        self.assertEqual(updated.active_symbol, "BTCUSDT")
        self.assertEqual(set(updated.pending_trigger_candidates.keys()), {"BTCUSDT"})

    def test_process_telegram_message_routes_leading_channel(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        updated, result = process_telegram_message(
            runtime,
            channel_id=runtime.settings.entry_signal_channel_id,
            message_id=707,
            message_text=_leading_message_text(),
            received_at_local=1_700_000_200,
            exchange_info=_exchange_info(),
            candles=_candles(),
            entry_mode="AGGRESSIVE",
            loop_label="stage13-route-leading",
        )
        self.assertTrue(result.handled)
        self.assertEqual(result.message_type, "LEADING")
        self.assertIn("BTCUSDT", updated.pending_trigger_candidates)

    def test_process_telegram_message_routes_risk_channel(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="ENTRY_ORDER",
            active_symbol="BTCUSDT",
        )
        updated, result = process_telegram_message(
            runtime,
            channel_id=runtime.settings.risk_signal_channel_id,
            message_id=808,
            message_text="리스크 알림\nBinance: BTCUSDT.P",
            received_at_local=2_100,
            risk_context={
                "avg_entry_price": 100.0,
                "mark_price": 110.0,
                "has_position": True,
                "has_open_entry_order": True,
                "has_tp_order": False,
                "second_entry_fully_filled": False,
                "exchange_info": _exchange_info(),
            },
            loop_label="stage13-route-risk",
        )
        self.assertTrue(result.handled)
        self.assertEqual(result.message_type, "RISK")
        self.assertEqual(result.reason_code, "RISK_PNL_LE_ZERO_MARKET_EXIT")
        self.assertEqual(updated.symbol_state, "ENTRY_ORDER")

    def test_sync_fill_flow_transitions_entry_order_to_phase1(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            symbol_state="ENTRY_ORDER",
        )
        updated, result = sync_entry_fill_flow(
            runtime,
            phase="FIRST_ENTRY",
            order_status="FILLED",
            has_position=True,
            has_any_open_order=False,
            loop_label="stage13-fill",
        )
        self.assertTrue(result.accepted)
        self.assertEqual(updated.symbol_state, "PHASE1")
        self.assertTrue(updated.global_state.has_any_position)
        self.assertTrue(updated.global_state.entry_locked)

    def test_price_guard_sets_safety_lock_when_dual_source_stale(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
        updated, result = apply_price_source_and_guard(
            runtime,
            ws_prices={},
            rest_prices={},
            received_at=100,
            now=200,
            loop_label="stage13-price-guard",
        )
        self.assertTrue(result.success)
        self.assertTrue(updated.global_state.safety_locked)
        self.assertTrue(result.global_blocked)

    def test_oco_failure_locks_new_orders(self) -> None:
        runtime = AutoTradeRuntime(settings=_default_settings())

        def cancel_call(params: dict) -> GatewayCallResult:
            if int(params.get("orderId", 0)) == 2:
                return GatewayCallResult(ok=False, reason_code="INVALID_SIGNATURE")
            return GatewayCallResult(ok=True, reason_code="OK")

        updated, result = execute_oco_cancel_flow(
            runtime,
            symbol="BTCUSDT",
            filled_order_id=1,
            open_exit_order_ids=[1, 2],
            cancel_call=cancel_call,
            loop_label="stage13-oco",
        )
        self.assertFalse(result.success)
        self.assertTrue(result.lock_new_orders)
        self.assertTrue(updated.new_orders_locked)

    def test_exit_partial_flow_applies_5_second_rule(self) -> None:
        runtime = AutoTradeRuntime(settings=_default_settings())
        runtime, _ = update_exit_partial_and_check_five_second(
            runtime,
            is_exit_order=True,
            order_id=9001,
            order_status="PARTIALLY_FILLED",
            executed_qty=1.0,
            updated_at=100,
            now=103,
            risk_market_exit_in_same_loop=False,
            loop_label="stage13-exit-early",
        )
        updated, result = update_exit_partial_and_check_five_second(
            runtime,
            is_exit_order=True,
            order_id=9001,
            order_status="PARTIALLY_FILLED",
            executed_qty=1.0,
            updated_at=100,
            now=105,
            risk_market_exit_in_same_loop=False,
            loop_label="stage13-exit-trigger",
        )
        self.assertTrue(result.decision.should_force_market_exit)
        self.assertEqual(result.reason_code, "EXIT_PARTIAL_STALLED_5S")
        self.assertTrue(updated.exit_partial_tracker.active)

    def test_recovery_startup_flow_unpauses_runtime_on_success(self) -> None:
        runtime = AutoTradeRuntime(settings=_default_settings())
        updated, result = run_recovery_startup_flow(
            runtime,
            load_persisted_state=lambda: PersistentRecoveryState(
                last_message_ids={runtime.settings.entry_signal_channel_id: 999},
                cooldown_by_symbol={"BTCUSDT": 500},
                received_at_by_symbol={"BTCUSDT": 500},
                message_id_by_symbol={"BTCUSDT": 999},
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
            cleared_monitoring_queue_count=0,
            loop_label="stage13-recovery",
        )
        self.assertTrue(result.success)
        self.assertFalse(updated.recovery_locked)
        self.assertFalse(updated.signal_loop_paused)
        self.assertTrue(updated.signal_loop_running)
        self.assertEqual(updated.symbol_state, "IDLE")
        self.assertEqual(updated.message_id_by_symbol.get("BTCUSDT"), 999)


class Stage13LoggingTests(unittest.TestCase):
    def test_orchestrator_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            runtime = AutoTradeRuntime(
                settings=_default_settings(),
                signal_loop_paused=False,
                signal_loop_running=True,
            )
            _updated, _ = handle_leading_market_signal(
                runtime,
                channel_id=runtime.settings.entry_signal_channel_id,
                message_id=101,
                message_text=_leading_message_text(),
                received_at_local=1_700_000_300,
                exchange_info=_exchange_info(),
                candles=_candles(),
                entry_mode="AGGRESSIVE",
                loop_label="stage13-log",
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
