from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any

AUTO_TRADE_LOG_PATH = Path(tempfile.gettempdir()) / "LTS-AutoTrade.log"
_LOG_LOCK = threading.Lock()


def _normalize_value(value: Any) -> str:
    text = str(value)
    return " ".join(text.split())


def write_auto_trade_log_line(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    try:
        with _LOG_LOCK:
            with open(AUTO_TRADE_LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(line)
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
