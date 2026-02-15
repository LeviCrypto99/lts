from __future__ import annotations

import unittest
from unittest.mock import patch

from auto_trade import (
    calculate_entry_target,
    calculate_entry_target_with_logging,
    evaluate_common_filters,
    evaluate_common_filters_with_logging,
)


class CommonFilteringTests(unittest.TestCase):
    def test_common_filter_pass(self) -> None:
        result = evaluate_common_filters(
            category="AI",
            ranking_direction="상승",
            ranking_position=11,
            funding_rate_pct=-0.09,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.reason_code, "FILTER_PASS")

    def test_common_filter_fail_excluded_category_keyword(self) -> None:
        result = evaluate_common_filters(
            category="Meme / AI",
            ranking_direction="상승",
            ranking_position=11,
            funding_rate_pct=-0.09,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "CATEGORY_EXCLUDED_KEYWORD")

    def test_common_filter_fail_unknown_category(self) -> None:
        result = evaluate_common_filters(
            category="정보없음",
            ranking_direction="상승",
            ranking_position=11,
            funding_rate_pct=-0.09,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "CATEGORY_UNKNOWN")

    def test_common_filter_fail_unknown_category_with_space_variant(self) -> None:
        result = evaluate_common_filters(
            category="정보 없음",
            ranking_direction="상승",
            ranking_position=11,
            funding_rate_pct=-0.09,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "CATEGORY_UNKNOWN")

    def test_common_filter_fail_rising_top5(self) -> None:
        result = evaluate_common_filters(
            category="AI",
            ranking_direction="상승",
            ranking_position=5,
            funding_rate_pct=-0.09,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "RANKING_TOP5_RISE")

    def test_common_filter_downward_rank_is_allowed(self) -> None:
        result = evaluate_common_filters(
            category="AI",
            ranking_direction="하락",
            ranking_position=1,
            funding_rate_pct=-0.09,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.reason_code, "FILTER_PASS")

    def test_common_filter_fail_funding_too_negative(self) -> None:
        result = evaluate_common_filters(
            category="AI",
            ranking_direction="상승",
            ranking_position=11,
            funding_rate_pct=-0.1,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "FUNDING_TOO_NEGATIVE")

    def test_common_filter_fail_invalid_direction(self) -> None:
        result = evaluate_common_filters(
            category="AI",
            ranking_direction="보합",
            ranking_position=11,
            funding_rate_pct=-0.09,
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason_code, "RANKING_DIRECTION_INVALID")

class EntryTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candles = [
            {"timestamp": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
            {"timestamp": 2, "open": 1.5, "high": 3.0, "low": 1.0, "close": 2.0},
            {"timestamp": 3, "open": 2.0, "high": 4.0, "low": 1.5, "close": 3.0},
            {"timestamp": 4, "open": 3.0, "high": 5.0, "low": 2.0, "close": 4.0},
        ]

    def test_aggressive_target_uses_previous_confirmed_high(self) -> None:
        result = calculate_entry_target(mode="AGGRESSIVE", candles=self.candles)
        self.assertTrue(result.ok)
        self.assertEqual(result.reference_index, 2)
        self.assertEqual(result.target_price, 4.0)
        self.assertIn("PREV_CONFIRMED_3M_HIGH", str(result.reference_source))

    def test_conservative_target_uses_aggressive_baseline_high(self) -> None:
        result = calculate_entry_target(
            mode="CONSERVATIVE",
            candles=self.candles,
            atr_length=3,
            atr_multiplier=1.0,
        )
        self.assertTrue(result.ok)
        self.assertAlmostEqual(float(result.target_price or 0.0), 4.0, places=10)
        self.assertIn("PREV_CONFIRMED_3M_HIGH", str(result.reference_source))

    def test_target_fail_on_insufficient_candles(self) -> None:
        one_candle = [{"high": 1.0, "low": 0.9, "close": 0.95}]
        result = calculate_entry_target(mode="AGGRESSIVE", candles=one_candle)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "INSUFFICIENT_CANDLES")

    def test_conservative_target_does_not_require_atr_length(self) -> None:
        two_candles = [
            {"high": 2.0, "low": 1.0, "close": 1.5},
            {"high": 3.0, "low": 1.5, "close": 2.0},
        ]
        result = calculate_entry_target(mode="CONSERVATIVE", candles=two_candles, atr_length=3)
        self.assertTrue(result.ok)
        self.assertEqual(result.reason_code, "TARGET_READY")
        self.assertAlmostEqual(float(result.target_price or 0.0), 2.0, places=10)

    def test_target_fail_on_invalid_candle_columns(self) -> None:
        bad = [{"high": 1.0, "close": 0.9}]
        result = calculate_entry_target(mode="AGGRESSIVE", candles=bad)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "INVALID_CANDLE_INPUT")


class Stage6LoggingTests(unittest.TestCase):
    def test_common_filter_logging_fields_exist(self) -> None:
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = evaluate_common_filters_with_logging(
                category="AI",
                ranking_direction="상승",
                ranking_position=11,
                funding_rate_pct=-0.09,
                symbol="BTCUSDT",
            )
            self.assertTrue(mocked.called)
            line = mocked.call_args.args[0]
            self.assertIn("input=", line)
            self.assertIn("decision=", line)
            self.assertIn("result=", line)
            self.assertIn("state_transition=", line)
            self.assertIn("failure_reason=", line)

    def test_entry_target_logging_fields_exist(self) -> None:
        candles = [
            {"high": 1.0, "low": 0.5, "close": 0.8},
            {"high": 1.5, "low": 0.7, "close": 1.2},
            {"high": 2.0, "low": 1.0, "close": 1.5},
        ]
        with patch("auto_trade.event_logging.write_auto_trade_log_line") as mocked:
            _ = calculate_entry_target_with_logging(
                mode="AGGRESSIVE",
                candles=candles,
                symbol="BTCUSDT",
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
