from __future__ import annotations

import importlib
import sys
import threading
import types
import unittest

from auto_trade import AutoTradeRuntime, AutoTradeSettings, ExitReconcilePlan, GlobalState, SymbolFilterRules


def _default_settings() -> AutoTradeSettings:
    return AutoTradeSettings(
        entry_signal_channel_id=-1002171239233,
        risk_signal_channel_id=-1003096527269,
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
    page._second_entry_fully_filled_symbols = set()
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
    def test_tp_ratio_options_exclude_half_percent(self) -> None:
        self.assertNotIn("0.5%", trade_page.TP_RATIO_OPTIONS)
        self.assertEqual(trade_page.TP_RATIO_OPTIONS, ["3%", "5%"])

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
        page._fetch_loop_account_snapshot = lambda: ([], [])
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

        self.assertEqual(submitted_order_types, ["BREAKEVEN_LIMIT"])
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
