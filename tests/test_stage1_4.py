from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    MAPPING_ACTION_IGNORE_KEEP_STATE,
    MAPPING_ACTION_RESET_AND_EXCLUDE,
    check_message_id_dedup,
    check_message_id_dedup_with_logging,
    check_symbol_cooldown,
    decide_cooldown_recording,
    load_auto_trade_settings,
    map_ticker_to_candidate_symbol,
    map_ticker_to_candidate_symbol_with_logging,
    parse_leading_market_message,
    parse_leading_market_message_with_logging,
    parse_risk_management_message,
    record_symbol_cooldown,
    resolve_mapping_failure_action,
    validate_candidate_symbol_usdt_m,
)


LEADING_MARKET_TEXT = """🔥 실시간 주도 마켓 분석 (btc)

📈 주도 마켓: 바이낸스
⏱️Binance 펀딩비 및 카운트다운 : -0.0250% / 01:23:45 (4h)
🥇지난 24H 등락률 및 순위 : +12.34% / (상승) 상위 11위
🏷️카테고리 : AI
"""

RISK_MANAGEMENT_TEXT = "🥈 Binance : btcusdt.p 에서 숏 리스크관리 권장"


class ConfigTests(unittest.TestCase):
    def test_load_defaults(self) -> None:
        settings = load_auto_trade_settings({})
        self.assertEqual(settings.entry_signal_channel_id, -1003782821900)
        self.assertEqual(settings.risk_signal_channel_id, -1003761851285)
        self.assertEqual(settings.cooldown_minutes, 10)
        self.assertEqual(settings.second_entry_percent, 15.0)
        self.assertEqual(settings.margin_buffer_pct, 0.01)
        self.assertEqual(settings.ws_stale_fallback_seconds, 5)
        self.assertEqual(settings.stale_mark_price_seconds, 15)
        self.assertEqual(settings.rate_limit_fail_threshold, 5)
        self.assertEqual(settings.rate_limit_recovery_threshold, 3)

    def test_invalid_values_fallback_to_defaults(self) -> None:
        settings = load_auto_trade_settings(
            {
                "LTS_COOLDOWN_MINUTES": "abc",
                "LTS_MARGIN_BUFFER_PCT": "0.8",
                "LTS_RATE_LIMIT_FAIL_THRESHOLD": "0",
            }
        )
        self.assertEqual(settings.cooldown_minutes, 10)
        self.assertEqual(settings.margin_buffer_pct, 0.01)
        self.assertEqual(settings.rate_limit_fail_threshold, 5)


class MessageParserTests(unittest.TestCase):
    def test_parse_leading_market_success(self) -> None:
        result = parse_leading_market_message(LEADING_MARKET_TEXT)
        self.assertTrue(result.ok)
        self.assertEqual(result.failure_code, "OK")
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(result.data.ticker, "BTC")
        self.assertEqual(result.data.symbol, "BTCUSDT")
        self.assertEqual(result.data.funding_rate_pct, -0.025)
        self.assertEqual(result.data.funding_countdown, "01:23:45")
        self.assertEqual(result.data.ranking_change_pct, 12.34)
        self.assertEqual(result.data.ranking_direction, "상승")
        self.assertEqual(result.data.ranking_position, 11)
        self.assertEqual(result.data.category, "AI")

    def test_parse_leading_market_reject_invalid_ticker(self) -> None:
        bad_text = LEADING_MARKET_TEXT.replace("(btc)", "(bt c)")
        result = parse_leading_market_message(bad_text)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "TICKER_NORMALIZE_FAILED")

    def test_parse_leading_market_reject_missing_funding(self) -> None:
        bad_text = """🔥 실시간 주도 마켓 분석 (btc)
🥇지난 24H 등락률 및 순위 : +12.34% / (상승) 상위 11위
🏷️카테고리 : AI
"""
        result = parse_leading_market_message(bad_text)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "FUNDING_LINE_NOT_FOUND")

    def test_parse_risk_management_success(self) -> None:
        result = parse_risk_management_message(RISK_MANAGEMENT_TEXT)
        self.assertTrue(result.ok)
        self.assertEqual(result.failure_code, "OK")
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(result.data.symbol, "BTCUSDT")

    def test_parse_risk_management_reject_invalid_characters(self) -> None:
        bad = "🥈 Binance : BTC-USDT.P 에서 숏 리스크관리 권장"
        result = parse_risk_management_message(bad)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "RISK_SYMBOL_NORMALIZE_FAILED")


class MessageDedupTests(unittest.TestCase):
    def test_dedup_reject_old_or_duplicate(self) -> None:
        result = check_message_id_dedup(
            {-1003782821900: 100},
            channel_id=-1003782821900,
            message_id=100,
        )
        self.assertFalse(result.accepted)
        self.assertTrue(result.is_duplicate_or_old)
        self.assertEqual(result.reason_code, "OLD_OR_DUPLICATE_MESSAGE")
        self.assertEqual(result.updated_last_message_ids[-1003782821900], 100)

    def test_dedup_accept_new_message(self) -> None:
        result = check_message_id_dedup(
            {-1003782821900: 100},
            channel_id=-1003782821900,
            message_id=101,
        )
        self.assertTrue(result.accepted)
        self.assertFalse(result.is_duplicate_or_old)
        self.assertEqual(result.reason_code, "NEW_MESSAGE_ACCEPTED")
        self.assertEqual(result.updated_last_message_ids[-1003782821900], 101)

    def test_dedup_reject_invalid_message_id(self) -> None:
        result = check_message_id_dedup(
            {},
            channel_id=-1003782821900,
            message_id=0,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_code, "INVALID_MESSAGE_ID")


class SymbolMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange_info = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "quoteAsset": "USDT",
                    "contractType": "PERPETUAL",
                },
                {
                    "symbol": "ETHUSDT",
                    "status": "PENDING_TRADING",
                    "quoteAsset": "USDT",
                    "contractType": "PERPETUAL",
                },
            ]
        }

    def test_map_ticker_success(self) -> None:
        result = map_ticker_to_candidate_symbol(" btc ")
        self.assertTrue(result.ok)
        self.assertEqual(result.normalized_ticker, "BTC")
        self.assertEqual(result.candidate_symbol, "BTCUSDT")

    def test_map_ticker_reject_invalid_characters(self) -> None:
        result = map_ticker_to_candidate_symbol("bt c")
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "TICKER_INVALID_CHARACTERS")

    def test_validate_symbol_success(self) -> None:
        result = validate_candidate_symbol_usdt_m("BTCUSDT", self.exchange_info)
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "TRADING")

    def test_validate_symbol_fail_not_trading(self) -> None:
        result = validate_candidate_symbol_usdt_m("ETHUSDT", self.exchange_info)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "SYMBOL_NOT_TRADING")

    def test_validate_symbol_fail_not_found(self) -> None:
        result = validate_candidate_symbol_usdt_m("XRPUSDT", self.exchange_info)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "SYMBOL_NOT_FOUND")

    def test_validate_symbol_fail_exchange_info_error(self) -> None:
        result = validate_candidate_symbol_usdt_m(
            "BTCUSDT",
            None,
            exchange_info_error="timeout",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "EXCHANGE_INFO_UNAVAILABLE")

    def test_mapping_failure_action_keep_state(self) -> None:
        result = resolve_mapping_failure_action(
            is_monitoring=True,
            has_open_order=False,
            has_position=False,
        )
        self.assertEqual(result.action, MAPPING_ACTION_IGNORE_KEEP_STATE)

    def test_mapping_failure_action_reset(self) -> None:
        result = resolve_mapping_failure_action(
            is_monitoring=False,
            has_open_order=False,
            has_position=False,
        )
        self.assertEqual(result.action, MAPPING_ACTION_RESET_AND_EXCLUDE)


class CooldownTests(unittest.TestCase):
    def test_cooldown_record_decision_rules(self) -> None:
        by_entry_lock = decide_cooldown_recording(
            blocked_by_entry_lock=True,
            blocked_by_safety_lock=False,
            candidate_symbol="BTCUSDT",
        )
        self.assertFalse(by_entry_lock.should_record)
        self.assertEqual(by_entry_lock.reason_code, "BLOCKED_BY_ENTRY_LOCK")

        by_safety_lock = decide_cooldown_recording(
            blocked_by_entry_lock=False,
            blocked_by_safety_lock=True,
            candidate_symbol="BTCUSDT",
        )
        self.assertFalse(by_safety_lock.should_record)
        self.assertEqual(by_safety_lock.reason_code, "BLOCKED_BY_SAFETY_LOCK")

        no_symbol = decide_cooldown_recording(
            blocked_by_entry_lock=False,
            blocked_by_safety_lock=False,
            candidate_symbol=None,
        )
        self.assertFalse(no_symbol.should_record)
        self.assertEqual(no_symbol.reason_code, "CANDIDATE_SYMBOL_UNAVAILABLE")

        record = decide_cooldown_recording(
            blocked_by_entry_lock=False,
            blocked_by_safety_lock=False,
            candidate_symbol="BTCUSDT",
        )
        self.assertTrue(record.should_record)
        self.assertEqual(record.reason_code, "RECORD_BY_SYMBOL")

    def test_check_and_record_cooldown(self) -> None:
        cooldown_store = {}
        cooldown_store = record_symbol_cooldown(
            cooldown_store,
            symbol="btcusdt",
            received_at=100,
        )
        self.assertEqual(cooldown_store["BTCUSDT"], 100)

        blocked = check_symbol_cooldown(
            cooldown_store,
            symbol="BTCUSDT",
            received_at=200,
            cooldown_minutes=10,
        )
        self.assertTrue(blocked.should_ignore)
        self.assertEqual(blocked.reason_code, "IN_COOLDOWN_WINDOW")
        self.assertEqual(blocked.remaining_seconds, 500)

        allowed = check_symbol_cooldown(
            cooldown_store,
            symbol="BTCUSDT",
            received_at=701,
            cooldown_minutes=10,
        )
        self.assertFalse(allowed.should_ignore)
        self.assertEqual(allowed.reason_code, "COOLDOWN_EXPIRED")


class StructuredLoggingTests(unittest.TestCase):
    def test_parser_wrapper_logs_required_fields(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            parse_leading_market_message_with_logging(
                LEADING_MARKET_TEXT,
                channel_id=-1003782821900,
                message_id=123,
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_mapping_wrapper_logs_required_fields(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            map_ticker_to_candidate_symbol_with_logging(
                "btc",
                channel_id=-1003782821900,
                message_id=123,
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_dedup_wrapper_logs_required_fields(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            check_message_id_dedup_with_logging(
                {-1003782821900: 100},
                channel_id=-1003782821900,
                message_id=100,
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
