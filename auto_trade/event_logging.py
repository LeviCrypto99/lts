from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .logging_utils import write_auto_trade_log_line

LOG_FIELD_EMPTY = "-"


def _normalize(value: Any) -> str:
    if value is None:
        return LOG_FIELD_EMPTY
    text = " ".join(str(value).split())
    return text if text else LOG_FIELD_EMPTY


@dataclass(frozen=True)
class StructuredLogEvent:
    component: str
    event: str
    input_data: str = LOG_FIELD_EMPTY
    decision: str = LOG_FIELD_EMPTY
    result: str = LOG_FIELD_EMPTY
    state_before: str = LOG_FIELD_EMPTY
    state_after: str = LOG_FIELD_EMPTY
    failure_reason: str = LOG_FIELD_EMPTY


def log_structured_event(event: StructuredLogEvent, **context: Any) -> None:
    state_before = _normalize(event.state_before)
    state_after = _normalize(event.state_after)
    state_transition = (
        LOG_FIELD_EMPTY
        if state_before == LOG_FIELD_EMPTY and state_after == LOG_FIELD_EMPTY
        else f"{state_before}->{state_after}"
    )

    core = [
        f"component={_normalize(event.component)}",
        f"event={_normalize(event.event)}",
        f"input={_normalize(event.input_data)}",
        f"decision={_normalize(event.decision)}",
        f"result={_normalize(event.result)}",
        f"state_transition={state_transition}",
        f"failure_reason={_normalize(event.failure_reason)}",
    ]

    if context:
        extra = [f"{key}={_normalize(value)}" for key, value in sorted(context.items())]
        core.extend(extra)

    write_auto_trade_log_line(" ".join(core))
