from __future__ import annotations

import time
from typing import Any

from log_rotation import append_rotating_log_line
from runtime_paths import get_log_path

AUTO_TRADE_LOG_PATH = get_log_path("LTS-AutoTrade.log")


def _normalize_value(value: Any) -> str:
    text = str(value)
    return " ".join(text.split())


def write_auto_trade_log_line(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    try:
        append_rotating_log_line(AUTO_TRADE_LOG_PATH, line)
    except Exception:
        # Logging must never break runtime flow.
        pass


def log_auto_trade(component: str, event: str, **fields: Any) -> None:
    normalized_fields = " ".join(
        f"{key}={_normalize_value(val)}" for key, val in fields.items()
    )
    line = f"component={component} event={event}"
    if normalized_fields:
        line = f"{line} {normalized_fields}"
    write_auto_trade_log_line(line)
