from __future__ import annotations

import importlib
import sys
import threading
import types
import unittest
from unittest.mock import patch

from auto_trade import (
    AutoTradeRuntime,
    AutoTradeSettings,
    ExitReconcilePlan,
    GatewayCallResult,
    GatewayRetryResult,
    GlobalState,
    SymbolFilterRules,
    TriggerCandidate,
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


def _install_trade_page_import_stubs() -> None:
    if "tkinter" not in sys.modules:
        tk = types.ModuleType("tkinter")

        class _Frame:
            pass

        class _Toplevel:
            pass

        class _Event:
            pass

        tk.Frame = _Frame
        tk.Toplevel = _Toplevel
        tk.Event = _Event
        tk.TclError = Exception
        tk.Canvas = object
        tk.StringVar = object

        tkfont = types.ModuleType("tkinter.font")
        ttk = types.ModuleType("tkinter.ttk")
        messagebox = types.ModuleType("tkinter.messagebox")

        class _Style:
            def configure(self, *_args, **_kwargs) -> None:
                return None

            def map(self, *_args, **_kwargs) -> None:
                return None

        ttk.Style = _Style
        ttk.Combobox = object
        messagebox.showerror = lambda *_args, **_kwargs: None

        tk.font = tkfont
        tk.ttk = ttk
        tk.messagebox = messagebox
        sys.modules["tkinter"] = tk
        sys.modules["tkinter.font"] = tkfont
        sys.modules["tkinter.ttk"] = ttk
        sys.modules["tkinter.messagebox"] = messagebox

    if "PIL" not in sys.modules:
        pil = types.ModuleType("PIL")
        image = types.ModuleType("PIL.Image")
        image_draw = types.ModuleType("PIL.ImageDraw")
        image_tk = types.ModuleType("PIL.ImageTk")
        pil.Image = image
        pil.ImageDraw = image_draw
        pil.ImageTk = image_tk
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image
        sys.modules["PIL.ImageDraw"] = image_draw
        sys.modules["PIL.ImageTk"] = image_tk


_install_trade_page_import_stubs()
if "trade_page" in sys.modules:
    del sys.modules["trade_page"]
trade_page = importlib.import_module("trade_page")
TradePage = trade_page.TradePage


def _make_trade_page_stub(runtime: AutoTradeRuntime | None = None) -> TradePage:
    page = TradePage.__new__(TradePage)
    page._auto_trade_runtime_lock = threading.Lock()
    page._signal_queue_lock = threading.Lock()
    page._signal_event_queue = []
    page._single_asset_mode_ready = False
    page._signal_source_mode = trade_page.SIGNAL_SOURCE_MODE_TELEGRAM
    page._entry_order_ref_by_symbol = {}
    page._second_entry_skip_latch = set()
    page._second_entry_fully_filled_symbols = set()
    page._last_open_exit_order_ids_by_symbol = {}
    page._oco_last_filled_exit_order_by_symbol = {}
    page._pending_oco_retry_symbols = set()
    page._position_zero_confirm_streak_by_symbol = {}
    page._tp_trigger_submit_guard_by_symbol = {}
    page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "5%"}
    page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "5%"}
    if runtime is None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
        )
    page._orchestrator_runtime = runtime
    return page


class TradePageRegressionTests(unittest.TestCase):
    def test_tp_ratio_options_include_half_percent(self) -> None:
        self.assertIn("0.5%", trade_page.TP_RATIO_OPTIONS)
        self.assertEqual(trade_page.TP_RATIO_OPTIONS, ["0.5%", "3%", "5%"])

    def test_parse_multi_assets_margin_mode_handles_bool_and_string(self) -> None:
        self.assertIs(TradePage._parse_multi_assets_margin_mode({"multiAssetsMargin": True}), True)
        self.assertIs(TradePage._parse_multi_assets_margin_mode({"multiAssetsMargin": "false"}), False)
        self.assertIsNone(TradePage._parse_multi_assets_margin_mode({"multiAssetsMargin": "unknown"}))
        self.assertIsNone(TradePage._parse_multi_assets_margin_mode(None))

    def test_login_asset_mode_sync_skips_when_already_single_asset(self) -> None:
        page = _make_trade_page_stub()
        page._api_key = "key"
        page._secret_key = "secret"
        page._fetch_multi_assets_margin_mode = lambda: (False, "-")
        set_calls: list[bool] = []
        page._set_multi_assets_margin_mode = lambda *, enabled: set_calls.append(bool(enabled)) or (True, "OK", "-")

        ok = page._ensure_single_asset_mode_on_login()

        self.assertTrue(ok)
        self.assertTrue(page._single_asset_mode_ready)
        self.assertEqual(set_calls, [])

    def test_login_asset_mode_sync_sets_single_asset_when_multi_asset(self) -> None:
        page = _make_trade_page_stub()
        page._api_key = "key"
        page._secret_key = "secret"
        page._fetch_multi_assets_margin_mode = lambda: (True, "-")
        set_calls: list[bool] = []
        page._set_multi_assets_margin_mode = lambda *, enabled: set_calls.append(bool(enabled)) or (
            True,
            "MULTI_ASSETS_MODE_SET_OK",
            "-",
        )

        ok = page._ensure_single_asset_mode_on_login()

        self.assertTrue(ok)
        self.assertTrue(page._single_asset_mode_ready)
        self.assertEqual(set_calls, [False])

    def test_fetch_wallet_balance_skips_when_single_asset_mode_not_ready(self) -> None:
        page = _make_trade_page_stub()
        page._api_key = "key"
        page._secret_key = "secret"
        calls = {
            "restrictions": 0,
            "wallet_failure": 0,
        }

        page._ensure_single_asset_mode_on_login = lambda: False

        def _fetch_api_restrictions():
            calls["restrictions"] += 1
            return {"enableReading": True, "enableFutures": True}

        page._fetch_api_restrictions = _fetch_api_restrictions
        page._set_wallet_failure_async = lambda: calls.__setitem__("wallet_failure", calls["wallet_failure"] + 1)

        page._fetch_wallet_balance()

        self.assertEqual(calls["restrictions"], 0)
        self.assertEqual(calls["wallet_failure"], 0)

    def test_refresh_status_skips_updates_until_single_asset_mode_ready(self) -> None:
        page = _make_trade_page_stub()
        page._api_key = "key"
        page._secret_key = "secret"
        page._single_asset_mode_ready = False
        page._refresh_in_progress = True
        calls = {
            "fetch_balance": 0,
            "fetch_positions": 0,
            "set_wallet": 0,
            "set_positions": 0,
            "start_refresh": 0,
        }

        page._ensure_single_asset_mode_on_login = lambda: False

        def _fetch_balance():
            calls["fetch_balance"] += 1
            return 100.0

        def _fetch_positions(*, force_refresh=False, loop_label="-"):
            calls["fetch_positions"] += 1
            return []

        page._fetch_futures_balance = _fetch_balance
        page._fetch_open_positions = _fetch_positions
        page._set_wallet_value = lambda _balance: calls.__setitem__("set_wallet", calls["set_wallet"] + 1)
        page._set_positions = lambda _positions: calls.__setitem__("set_positions", calls["set_positions"] + 1)
        page._start_status_refresh = lambda: calls.__setitem__("start_refresh", calls["start_refresh"] + 1)
        page.after = lambda _delay, callback: callback()

        page._refresh_status()

        self.assertEqual(calls["fetch_balance"], 0)
        self.assertEqual(calls["fetch_positions"], 0)
        self.assertEqual(calls["set_wallet"], 0)
        self.assertEqual(calls["set_positions"], 0)
        self.assertEqual(calls["start_refresh"], 1)
        self.assertFalse(page._refresh_in_progress)

    def test_normalize_open_order_row_uses_trigger_price_when_stop_price_zero(self) -> None:
        row = TradePage._normalize_open_order_row(
            {
                "symbol": "RIVERUSDT",
                "orderId": 12345,
                "status": "NEW",
                "type": "STOP_MARKET",
                "side": "BUY",
                "stopPrice": "0",
                "triggerPrice": "19.786",
            },
            is_algo_order=True,
        )

        self.assertIsNotNone(row)
        self.assertAlmostEqual(float(row.get("stopPrice") or 0.0), 19.786, places=9)
        self.assertEqual(row.get("_stop_price_source"), "triggerPrice")

    def test_normalize_open_order_row_maps_algo_order_type_and_status_fields(self) -> None:
        row = TradePage._normalize_open_order_row(
            {
                "symbol": "RIVERUSDT",
                "algoId": 555123,
                "algoStatus": "NEW",
                "orderType": "TAKE_PROFIT",
                "side": "BUY",
                "quantity": "15.8",
                "price": "17.55",
                "triggerPrice": "17.786",
            },
            is_algo_order=True,
        )

        self.assertIsNotNone(row)
        self.assertEqual(row.get("orderId"), 555123)
        self.assertEqual(row.get("status"), "NEW")
        self.assertEqual(row.get("type"), "TAKE_PROFIT")
        self.assertEqual(row.get("_type_source"), "orderType")
        self.assertAlmostEqual(float(row.get("origQty") or 0.0), 15.8, places=9)

    def test_phase1_tp_target_uses_three_percent_ratio_when_selected(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "3%", "risk_filter": "보수적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "3%", "risk_filter": "보수적"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        submitted: dict[str, object] = {}
        page._submit_tp_limit_once = lambda **kwargs: submitted.update(kwargs) or True

        positions = [
            {"symbol": "BTCUSDT", "positionAmt": "1.0", "entryPrice": "100", "markPrice": "103"},
        ]
        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BTCUSDT",
            open_orders=[],
            positions=positions,
            loop_label="stage15-half-percent-tp",
        )

        self.assertEqual(submitted.get("symbol"), "BTCUSDT")
        self.assertAlmostEqual(float(submitted.get("target_price_override") or 0.0), 103.0, places=9)

    def test_phase1_tp_target_and_trigger_use_half_percent_ratio_when_selected(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        submitted: dict[str, object] = {}
        page._submit_tp_limit_once = lambda **kwargs: submitted.update(kwargs) or True

        positions = [
            {"symbol": "BTCUSDT", "positionAmt": "-1.0", "entryPrice": "100", "markPrice": "99.7"},
        ]
        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BTCUSDT",
            open_orders=[],
            positions=positions,
            loop_label="stage15-half-percent-tp",
        )

        self.assertEqual(submitted.get("symbol"), "BTCUSDT")
        self.assertAlmostEqual(float(submitted.get("target_price_override") or 0.0), 99.5, places=9)
        self.assertAlmostEqual(float(submitted.get("trigger_price_override") or 0.0), 100.0, places=9)

    def test_phase1_tp_trigger_guard_blocks_duplicate_submit_with_same_params(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        submit_counter = {"count": 0}

        def _submit(**_kwargs):
            submit_counter["count"] += 1
            return True

        page._submit_tp_limit_once = _submit

        positions = [
            {"symbol": "BTCUSDT", "positionAmt": "-1.0", "entryPrice": "100", "markPrice": "99.7"},
        ]

        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BTCUSDT",
            open_orders=[],
            positions=positions,
            loop_label="stage15-tp-guard-1",
        )
        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BTCUSDT",
            open_orders=[],
            positions=positions,
            loop_label="stage15-tp-guard-2",
        )

        self.assertEqual(submit_counter["count"], 1)

    def test_phase1_skips_tp_submit_when_algo_order_uses_order_type_field(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        submit_counter = {"count": 0}

        def _submit(**_kwargs):
            submit_counter["count"] += 1
            return True

        page._submit_tp_limit_once = _submit
        positions = [
            {"symbol": "BTCUSDT", "positionAmt": "-1.0", "entryPrice": "100", "markPrice": "99.7"},
        ]
        raw_open_order = {
            "symbol": "BTCUSDT",
            "algoId": 2000001,
            "algoStatus": "NEW",
            "orderType": "TAKE_PROFIT",
            "side": "BUY",
            "price": "99.5",
            "triggerPrice": "100.0",
            "quantity": "1.0",
            "reduceOnly": False,
            "closePosition": False,
        }
        normalized = TradePage._normalize_open_order_row(raw_open_order, is_algo_order=True)
        self.assertIsNotNone(normalized)
        open_orders = [normalized]

        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BTCUSDT",
            open_orders=open_orders,
            positions=positions,
            loop_label="stage15-phase1-algo-ordertype-aligned",
        )

        self.assertEqual(submit_counter["count"], 0)

    def test_phase1_keeps_existing_tp_limit_child_order_without_replacing(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "0.5%", "risk_filter": "보수적"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.000001,
            step_size=1.0,
            min_qty=1.0,
            min_notional=5.0,
        )
        cancel_reasons: list[str] = []
        page._cancel_orders_by_ids = lambda **kwargs: cancel_reasons.append(str(kwargs.get("reason") or ""))
        page._submit_tp_limit_once = lambda **_kwargs: self.fail("tp trigger should not be re-submitted")

        positions = [
            {"symbol": "BLESSUSDT", "positionAmt": "-24069", "entryPrice": "0.005925", "markPrice": "0.005896"},
        ]
        open_orders = [
            {
                "symbol": "BLESSUSDT",
                "orderId": 937594872,
                "type": "LIMIT",
                "side": "BUY",
                "price": "0.005895",
                "reduceOnly": "true",
                "status": "NEW",
            }
        ]

        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BLESSUSDT",
            open_orders=open_orders,
            positions=positions,
            loop_label="stage15-phase1-keep-triggered-limit",
        )

        self.assertEqual(cancel_reasons, [])

    def test_submit_tp_trigger_immediate_reject_does_not_force_market_exit(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.0001,
            step_size=1.0,
            min_qty=1.0,
            min_notional=5.0,
        )
        page._current_position_mode = lambda: "ONE_WAY"
        market_exit_called = {"value": False}
        page._submit_market_exit_for_symbol = lambda **_kwargs: market_exit_called.__setitem__("value", True) or True

        last_result = GatewayCallResult(
            ok=False,
            reason_code="EXCHANGE_REJECTED",
            payload={"code": -2021, "msg": "Order would immediately trigger."},
            error_code=-2021,
            error_message="Order would immediately trigger.",
        )
        retry_result = GatewayRetryResult(
            operation="CREATE",
            success=False,
            attempts=1,
            reason_code="EXCHANGE_REJECTED",
            last_result=last_result,
            history=[last_result],
        )
        positions = [
            {"symbol": "BLESSUSDT", "positionAmt": "-1000", "entryPrice": "1.0", "markPrice": "0.99"},
        ]

        with patch.object(trade_page, "create_order_with_retry_with_logging", return_value=retry_result):
            submitted = page._submit_tp_limit_once(
                symbol="BLESSUSDT",
                positions=positions,
                loop_label="stage15-tp-immediate-reject",
            )

        self.assertFalse(submitted)
        self.assertFalse(market_exit_called["value"])

    def test_phase2_mdd_alignment_uses_trigger_price_fallback_without_duplicate_submit(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE2",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "3%", "risk_filter": "공격적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "3%", "risk_filter": "공격적"}
        page._second_entry_fully_filled_symbols = {"RIVERUSDT"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.001,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        submit_counter = {"mdd_stop": 0}
        page._submit_mdd_stop_market = lambda **_kwargs: submit_counter.__setitem__(
            "mdd_stop",
            submit_counter["mdd_stop"] + 1,
        ) or True
        page._submit_tp_limit_once = lambda **_kwargs: True

        positions = [
            {"symbol": "RIVERUSDT", "positionAmt": "-15.8", "entryPrice": "17.205", "markPrice": "17.1"},
        ]
        open_orders = [
            {
                "symbol": "RIVERUSDT",
                "orderId": 98765,
                "type": "STOP_MARKET",
                "side": "BUY",
                "stopPrice": "0",
                "triggerPrice": "19.786",
                "closePosition": "true",
            },
        ]

        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="RIVERUSDT",
            open_orders=open_orders,
            positions=positions,
            loop_label="stage15-mdd-stop-fallback-aligned",
        )

        self.assertEqual(submit_counter["mdd_stop"], 0)

    def test_phase2_ensures_breakeven_tp_trigger_without_mark_threshold_gate(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE2",
        )
        page = _make_trade_page_stub(runtime)
        page._saved_filter_settings = {"mdd": "15%", "tp_ratio": "3%", "risk_filter": "보수적"}
        page._default_filter_settings = lambda: {"mdd": "15%", "tp_ratio": "3%", "risk_filter": "보수적"}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        captured: dict[str, float] = {}
        submit_counter = {"tp_trigger": 0}

        def _submit_tp_limit_once(**kwargs):
            submit_counter["tp_trigger"] += 1
            captured["target_price_override"] = float(kwargs.get("target_price_override", 0.0))
            captured["trigger_price_override"] = float(kwargs.get("trigger_price_override", 0.0))
            return True

        page._submit_tp_limit_once = _submit_tp_limit_once
        page._submit_mdd_stop_market = lambda **_kwargs: self.fail("mdd stop should not be submitted")

        positions = [
            {"symbol": "BTCUSDT", "positionAmt": "1.0", "entryPrice": "100.0", "markPrice": "100.2"},
        ]
        open_orders: list[dict] = []

        _ = page._enforce_phase_exit_policy(
            runtime,
            symbol="BTCUSDT",
            open_orders=open_orders,
            positions=positions,
            loop_label="stage15-phase2-breakeven-trigger",
        )

        self.assertEqual(submit_counter["tp_trigger"], 1)
        self.assertAlmostEqual(captured["target_price_override"], 100.0, places=8)
        self.assertAlmostEqual(captured["trigger_price_override"], 99.5, places=8)

    def test_safety_lock_drops_signal_queue_immediately(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            global_state=GlobalState(safety_locked=True),
        )
        page = _make_trade_page_stub(runtime)
        page._signal_event_queue = [
            {"channel_id": 1, "message_id": 10, "message_text": "A", "received_at_local": 100},
            {"channel_id": 1, "message_id": 11, "message_text": "B", "received_at_local": 101},
        ]
        called = {"run_trigger_cycle_once": False, "refresh_controls": False}
        page._poll_telegram_bot_updates = lambda: None
        page._poll_signal_inbox_file = lambda: None
        page._fetch_loop_account_snapshot = lambda **_kwargs: ([], [])
        page._run_fill_sync_pass = lambda **_kwargs: None
        page._apply_price_guard_for_loop = lambda **_kwargs: None
        page._execute_safety_action_if_needed = lambda **_kwargs: None
        page._run_trigger_cycle_once = lambda: called.__setitem__("run_trigger_cycle_once", True)
        page._refresh_filter_controls_lock_from_runtime = (
            lambda _runtime: called.__setitem__("refresh_controls", True)
        )

        page._signal_loop_tick()

        self.assertEqual(page._signal_event_queue, [])
        self.assertFalse(called["run_trigger_cycle_once"])
        self.assertTrue(called["refresh_controls"])

    def test_position_mode_unknown_pre_order_hook_rejects_candidate_without_reset(self) -> None:
        page = _make_trade_page_stub()
        ok, reason, failure, reset = page._reject_pre_order_when_position_mode_unknown(
            "BTCUSDT",
            "FIRST_ENTRY",
            "stage15-mode-unknown",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "POSITION_MODE_UNKNOWN")
        self.assertEqual(failure, "position_mode_unknown")
        self.assertFalse(reset)

    def test_pre_order_setup_hook_maps_aggressive_mode_to_two_x_leverage(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1,
                    message_id=10,
                    entry_mode="AGGRESSIVE",
                )
            },
        )
        page = _make_trade_page_stub(runtime)
        captured: dict[str, object] = {}

        def _ensure_symbol_setup(
            *,
            symbol: str,
            entry_mode: str,
            target_leverage: int,
            loop_label: str,
        ) -> tuple[bool, str, str]:
            captured["symbol"] = symbol
            captured["entry_mode"] = entry_mode
            captured["target_leverage"] = target_leverage
            captured["loop_label"] = loop_label
            return True, "SYMBOL_SETUP_ALREADY_ALIGNED", "-"

        page._ensure_symbol_trading_setup_for_entry = _ensure_symbol_setup

        ok, reason, failure, reset = page._run_pre_order_setup_hook(
            "BTCUSDT",
            "FIRST_ENTRY",
            "stage15-pre-order-aggressive",
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "SYMBOL_SETUP_ALREADY_ALIGNED")
        self.assertEqual(failure, "-")
        self.assertFalse(reset)
        self.assertEqual(captured["symbol"], "BTCUSDT")
        self.assertEqual(captured["entry_mode"], "AGGRESSIVE")
        self.assertEqual(captured["target_leverage"], 2)

    def test_pre_order_setup_hook_maps_conservative_mode_to_one_x_leverage(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            pending_trigger_candidates={
                "BTCUSDT": TriggerCandidate(
                    symbol="BTCUSDT",
                    trigger_kind="FIRST_ENTRY",
                    target_price=100.0,
                    received_at_local=1,
                    message_id=10,
                    entry_mode="CONSERVATIVE",
                )
            },
        )
        page = _make_trade_page_stub(runtime)
        captured: dict[str, object] = {}

        def _ensure_symbol_setup(
            *,
            symbol: str,
            entry_mode: str,
            target_leverage: int,
            loop_label: str,
        ) -> tuple[bool, str, str]:
            captured["symbol"] = symbol
            captured["entry_mode"] = entry_mode
            captured["target_leverage"] = target_leverage
            captured["loop_label"] = loop_label
            return True, "SYMBOL_SETUP_ALREADY_ALIGNED", "-"

        page._ensure_symbol_trading_setup_for_entry = _ensure_symbol_setup

        ok, reason, failure, reset = page._run_pre_order_setup_hook(
            "BTCUSDT",
            "FIRST_ENTRY",
            "stage15-pre-order-conservative",
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "SYMBOL_SETUP_ALREADY_ALIGNED")
        self.assertEqual(failure, "-")
        self.assertFalse(reset)
        self.assertEqual(captured["symbol"], "BTCUSDT")
        self.assertEqual(captured["entry_mode"], "CONSERVATIVE")
        self.assertEqual(captured["target_leverage"], 1)

    def test_cancel_exit_orders_for_symbol_keeps_entry_orders(self) -> None:
        page = _make_trade_page_stub()
        canceled: list[int] = []
        page._cancel_order_with_gateway = (
            lambda *, symbol, order_id, loop_label: canceled.append(int(order_id)) or True
        )
        open_orders = [
            {
                "symbol": "BTCUSDT",
                "orderId": 101,
                "type": "LIMIT",
                "side": "SELL",
                "reduceOnly": "false",
                "closePosition": "false",
                "price": "100",
            },
            {
                "symbol": "BTCUSDT",
                "orderId": 202,
                "type": "LIMIT",
                "side": "BUY",
                "reduceOnly": "true",
                "closePosition": "false",
                "price": "95",
            },
        ]

        page._cancel_exit_orders_for_symbol(
            symbol="BTCUSDT",
            open_orders=open_orders,
            loop_label="stage15-cancel-exit-only",
        )

        self.assertEqual(canceled, [202])

    def test_position_quantity_rebuild_in_phase2_keeps_only_phase2_active_exit_policy(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE2",
            active_symbol="BTCUSDT",
            global_state=GlobalState(has_any_position=True),
        )
        page = _make_trade_page_stub(runtime)
        page._last_position_qty_by_symbol = {"BTCUSDT": 1.0}
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        page._cancel_open_orders_for_symbols = lambda **_kwargs: None
        page._cancel_order_with_gateway = lambda **_kwargs: True
        refreshed_positions = [
            {"symbol": "BTCUSDT", "positionAmt": "-0.5", "entryPrice": "100", "markPrice": "101"}
        ]
        page._fetch_open_orders = lambda: []
        page._fetch_open_positions = lambda: refreshed_positions
        submitted_order_types: list[str] = []
        page._submit_tp_limit_once = lambda **_kwargs: submitted_order_types.append("TP_LIMIT") or True
        page._submit_breakeven_limit_once = (
            lambda **_kwargs: submitted_order_types.append("BREAKEVEN_LIMIT") or True
        )
        page._submit_breakeven_stop_market = (
            lambda **_kwargs: submitted_order_types.append("BREAKEVEN_STOP") or True
        )
        page._submit_mdd_stop_market = lambda **_kwargs: submitted_order_types.append("MDD_STOP") or True

        open_orders = [
            {"symbol": "BTCUSDT", "orderId": 1, "type": "LIMIT", "side": "BUY", "price": "95", "reduceOnly": "true"},
            {"symbol": "BTCUSDT", "orderId": 2, "type": "LIMIT", "side": "BUY", "price": "100", "reduceOnly": "true"},
            {
                "symbol": "BTCUSDT",
                "orderId": 3,
                "type": "STOP_MARKET",
                "side": "BUY",
                "stopPrice": "115",
                "closePosition": "true",
            },
        ]

        updated_runtime, _updated_open_orders, _updated_positions = page._handle_position_quantity_reconciliation(
            runtime,
            symbol="BTCUSDT",
            open_orders=open_orders,
            positions=refreshed_positions,
            loop_label="stage15-qty-sync",
        )

        self.assertEqual(submitted_order_types, ["TP_LIMIT"])
        self.assertTrue(updated_runtime.global_state.has_any_position)
        self.assertEqual(page._last_position_qty_by_symbol["BTCUSDT"], 0.5)

    def test_recovery_exit_registration_skips_when_no_active_templates(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
        )
        page = _make_trade_page_stub(runtime)
        page._fetch_open_orders = lambda: []
        page._fetch_open_positions = lambda: [
            {"symbol": "BTCUSDT", "positionAmt": "-0.2", "entryPrice": "100", "markPrice": "100"}
        ]
        page._get_symbol_filter_rule = lambda _symbol: SymbolFilterRules(
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
        )
        page._submit_tp_limit_once = lambda **_kwargs: self.fail("tp_limit should not be submitted")
        page._submit_breakeven_limit_once = lambda **_kwargs: self.fail("breakeven_limit should not be submitted")
        page._submit_breakeven_stop_market = lambda **_kwargs: self.fail("breakeven_stop should not be submitted")
        page._submit_mdd_stop_market = lambda **_kwargs: self.fail("mdd_stop should not be submitted")

        result = page._execute_recovery_exit_reconciliation(
            ExitReconcilePlan(
                action_code="REQUIRE_EXIT_REGISTRATION",
                reason_code="RECOVERY_RECONCILE_REQUIRE_EXIT_REGISTRATION",
                cancel_symbols=[],
                register_symbols=["BTCUSDT"],
                require_exit_registration=True,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.reason_code, "RECOVERY_RECONCILE_DONE")
        self.assertEqual(list(result.canceled_symbols), [])

    def test_position_zero_reconciles_immediately_with_cancel_all(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
            active_symbol="DYMUSDT",
        )
        page = _make_trade_page_stub(runtime)
        page._last_position_qty_by_symbol = {"DYMUSDT": 2930.5}
        page._position_zero_confirm_streak_by_symbol = {"DYMUSDT": 1}

        cancel_all_calls: list[dict[str, object]] = []

        def _cancel_all(**kwargs):
            cancel_all_calls.append(kwargs)
            return True, "-"

        page._cancel_all_open_orders_for_symbol = _cancel_all
        page._cancel_open_orders_for_symbols = lambda **_kwargs: self.fail("fallback cancel should not run")
        page._fetch_open_orders = lambda **_kwargs: []
        page._fetch_open_positions = lambda **_kwargs: []

        updated, _, _ = page._handle_position_quantity_reconciliation(
            runtime,
            symbol="DYMUSDT",
            open_orders=[],
            positions=[],
            loop_label="stage15-qty-zero-immediate",
        )

        self.assertEqual(len(cancel_all_calls), 1)
        self.assertEqual(updated.symbol_state, "IDLE")
        self.assertIsNone(updated.active_symbol)
        self.assertNotIn("DYMUSDT", page._last_position_qty_by_symbol)
        self.assertNotIn("DYMUSDT", page._position_zero_confirm_streak_by_symbol)

    def test_position_zero_uses_fallback_cancel_when_cancel_all_fails(self) -> None:
        runtime = AutoTradeRuntime(
            settings=_default_settings(),
            signal_loop_paused=False,
            signal_loop_running=True,
            symbol_state="PHASE1",
            active_symbol="DYMUSDT",
        )
        page = _make_trade_page_stub(runtime)
        page._last_position_qty_by_symbol = {"DYMUSDT": 2930.5}

        page._cancel_all_open_orders_for_symbol = lambda **_kwargs: (False, "network_error")
        fallback_calls: list[dict[str, object]] = []
        page._cancel_open_orders_for_symbols = lambda **kwargs: fallback_calls.append(kwargs)
        page._fetch_open_orders = lambda **_kwargs: []
        page._fetch_open_positions = lambda **_kwargs: []

        _updated, _, _ = page._handle_position_quantity_reconciliation(
            runtime,
            symbol="DYMUSDT",
            open_orders=[],
            positions=[],
            loop_label="stage15-qty-zero-fallback",
        )

        self.assertEqual(len(fallback_calls), 1)
        self.assertEqual(fallback_calls[0].get("symbols"), ["DYMUSDT"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
