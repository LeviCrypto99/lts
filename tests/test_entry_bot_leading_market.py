from __future__ import annotations

import textwrap
import unittest

from entry_bot import evaluate_common_filters, parse_leading_market_message


class LeadingMarketCheckmarkTests(unittest.TestCase):
    def test_parse_leading_market_message_reads_required_checkmarks(self) -> None:
        message = textwrap.dedent(
            """
            🔥 실시간 주도 마켓 분석 (NOM)

            📈 주도 마켓: 바이낸스 현물

            🌐글로벌 거래소 통합 펀딩비 : -0.7214% ❌

            🥇지난 24H 등락률 및 순위 : +24.38% / (상승) 상위 13위 ✅

            🏷️카테고리 : (Decentralized Finance (DeFi)) ✅

            🐜개미 롱/숏 비율 : 🟢롱 51.16명 / 🔴숏 48.84명 ✅

            🦈고래 동향 (계정 수) : 🟢롱 50.22명 / 🔴숏 49.78명 ✅

            ⚖️스마트머니 포지션 (고래 자금비율) : 🟢롱 53.18% / 🔴숏 46.82% ✅

            🔗Liq HeatMap : 히트맵 링크
            """
        ).strip()

        signal, reason = parse_leading_market_message(message)

        self.assertEqual(reason, "ok")
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.ticker, "NOM")
        self.assertEqual(signal.symbol, "NOMUSDT")
        self.assertFalse(signal.funding_check_passed)
        self.assertTrue(signal.ranking_check_passed)
        self.assertTrue(signal.category_check_passed)
        self.assertTrue(signal.retail_ratio_check_passed)
        self.assertTrue(signal.whale_accounts_check_passed)
        self.assertTrue(signal.smart_money_check_passed)

    def test_evaluate_common_filters_rejects_when_any_required_check_is_fail(self) -> None:
        passed, reason = evaluate_common_filters(
            funding_check_passed=False,
            ranking_check_passed=True,
            category_check_passed=True,
            retail_ratio_check_passed=True,
            whale_accounts_check_passed=True,
            smart_money_check_passed=True,
        )

        self.assertFalse(passed)
        self.assertEqual(reason, "required_check_failed:funding")

    def test_evaluate_common_filters_passes_when_all_required_checks_are_pass(self) -> None:
        passed, reason = evaluate_common_filters(
            funding_check_passed=True,
            ranking_check_passed=True,
            category_check_passed=True,
            retail_ratio_check_passed=True,
            whale_accounts_check_passed=True,
            smart_money_check_passed=True,
        )

        self.assertTrue(passed)
        self.assertEqual(reason, "filter_pass")


if __name__ == "__main__":
    unittest.main()
