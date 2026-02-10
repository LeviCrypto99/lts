from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

AUTO_TRADE_SIGNAL_INBOX_PATH = Path(tempfile.gettempdir()) / "LTS-auto-trade-signal-inbox.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a test signal event for TradePage signal loop.")
    parser.add_argument("--channel-id", type=int, required=True, help="Telegram channel id")
    parser.add_argument("--message-id", type=int, required=True, help="Message id")
    parser.add_argument("--message-text", type=str, required=True, help="Raw message text")
    parser.add_argument(
        "--received-at-local",
        type=int,
        default=None,
        help="Unix timestamp (seconds). Defaults to now.",
    )
    args = parser.parse_args()

    event = {
        "channel_id": int(args.channel_id),
        "message_id": int(args.message_id),
        "message_text": str(args.message_text),
        "received_at_local": int(args.received_at_local) if args.received_at_local is not None else int(time.time()),
    }
    AUTO_TRADE_SIGNAL_INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTO_TRADE_SIGNAL_INBOX_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True))
        handle.write("\n")
    print(f"queued {event['channel_id']}:{event['message_id']} -> {AUTO_TRADE_SIGNAL_INBOX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
