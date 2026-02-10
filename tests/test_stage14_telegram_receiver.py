from __future__ import annotations

import unittest

import requests

from auto_trade import (
    parse_telegram_update,
    parse_telegram_update_with_logging,
    poll_telegram_updates,
    poll_telegram_updates_with_logging,
)


ENTRY_CHANNEL_ID = -1002171239233
RISK_CHANNEL_ID = -1003096527269


class _FakeResponse:
    def __init__(self, status_code: int, payload: object, *, raise_json: bool = False) -> None:
        self.status_code = status_code
        self._payload = payload
        self._raise_json = raise_json

    def json(self) -> object:
        if self._raise_json:
            raise ValueError("invalid-json")
        return self._payload


class TelegramReceiverParseTests(unittest.TestCase):
    def test_parse_channel_post_success(self) -> None:
        update = {
            "update_id": 10,
            "channel_post": {
                "message_id": 777,
                "chat": {"id": ENTRY_CHANNEL_ID, "type": "channel"},
                "text": "🔥 실시간 주도 마켓 분석 (BTC)",
            },
        }
        result = parse_telegram_update(
            update,
            allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID),
            received_at_local=1700000000,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_code, "OK")
        self.assertIsNotNone(result.event)
        assert result.event is not None
        self.assertEqual(result.event.update_id, 10)
        self.assertEqual(result.event.channel_id, ENTRY_CHANNEL_ID)
        self.assertEqual(result.event.message_id, 777)
        self.assertEqual(result.event.received_at_local, 1700000000)

    def test_parse_reject_non_target_channel(self) -> None:
        update = {
            "update_id": 11,
            "channel_post": {
                "message_id": 5,
                "chat": {"id": -1000000000001, "type": "channel"},
                "text": "ignored",
            },
        }
        result = parse_telegram_update(update, allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID))
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_code, "CHANNEL_NOT_TARGET")

    def test_parse_with_logging_supports_caption(self) -> None:
        update = {
            "update_id": 12,
            "channel_post": {
                "message_id": 6,
                "chat": {"id": RISK_CHANNEL_ID, "type": "channel"},
                "caption": "🥈 Binance : BTCUSDT.P 에서 숏 리스크관리 권장",
            },
        }
        result = parse_telegram_update_with_logging(
            update,
            allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID),
            received_at_local=1700000010,
            loop_label="unittest",
        )
        self.assertTrue(result.accepted)
        self.assertIsNotNone(result.event)
        assert result.event is not None
        self.assertEqual(result.event.channel_id, RISK_CHANNEL_ID)


class TelegramReceiverPollTests(unittest.TestCase):
    def test_poll_success_filters_events_and_updates_offset(self) -> None:
        payload = {
            "ok": True,
            "result": [
                {
                    "update_id": 100,
                    "channel_post": {
                        "message_id": 1,
                        "chat": {"id": ENTRY_CHANNEL_ID, "type": "channel"},
                        "text": "🔥 실시간 주도 마켓 분석 (BTC)",
                    },
                },
                {
                    "update_id": 101,
                    "channel_post": {
                        "message_id": 2,
                        "chat": {"id": -1001234567890, "type": "channel"},
                        "text": "not target",
                    },
                },
                {
                    "update_id": 102,
                    "channel_post": {
                        "message_id": 3,
                        "chat": {"id": RISK_CHANNEL_ID, "type": "channel"},
                        "caption": "🥈 Binance : ETHUSDT.P 에서 숏 리스크관리 권장",
                    },
                },
                {
                    "update_id": 103,
                    "edited_channel_post": {
                        "message_id": 99,
                        "chat": {"id": ENTRY_CHANNEL_ID, "type": "channel"},
                        "text": "ignored",
                    },
                },
            ],
        }
        result = poll_telegram_updates(
            bot_token="test-token",
            allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID),
            last_update_id=100,
            request_get=lambda *_args, **_kwargs: _FakeResponse(200, payload),
            now_provider=lambda: 1700000100,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.reason_code, "OK")
        self.assertEqual(result.next_update_id, 104)
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.events[0].channel_id, ENTRY_CHANNEL_ID)
        self.assertEqual(result.events[1].channel_id, RISK_CHANNEL_ID)
        self.assertEqual(result.events[0].received_at_local, 1700000100)
        self.assertEqual(result.events[1].received_at_local, 1700000100)

    def test_poll_no_updates(self) -> None:
        payload = {"ok": True, "result": []}
        result = poll_telegram_updates(
            bot_token="test-token",
            allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID),
            last_update_id=500,
            request_get=lambda *_args, **_kwargs: _FakeResponse(200, payload),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.reason_code, "NO_UPDATES")
        self.assertEqual(result.next_update_id, 500)
        self.assertEqual(len(result.events), 0)

    def test_poll_request_failure(self) -> None:
        def _raise(*_args, **_kwargs):
            raise requests.RequestException("network-fail")

        result = poll_telegram_updates(
            bot_token="test-token",
            allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID),
            last_update_id=10,
            request_get=_raise,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "REQUEST_FAILED")
        self.assertEqual(result.next_update_id, 10)

    def test_poll_with_logging_invalid_json(self) -> None:
        result = poll_telegram_updates_with_logging(
            bot_token="test-token",
            allowed_channel_ids=(ENTRY_CHANNEL_ID, RISK_CHANNEL_ID),
            last_update_id=42,
            request_get=lambda *_args, **_kwargs: _FakeResponse(200, {}, raise_json=True),
            loop_label="unittest",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "INVALID_JSON")
        self.assertEqual(result.next_update_id, 42)


if __name__ == "__main__":
    unittest.main()
