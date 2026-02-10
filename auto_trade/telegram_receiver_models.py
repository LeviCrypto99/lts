from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class TelegramSignalEvent:
    update_id: int
    channel_id: int
    message_id: int
    message_text: str
    received_at_local: int


@dataclass(frozen=True)
class TelegramUpdateParseResult:
    accepted: bool
    reason_code: str
    failure_reason: str = ""
    event: Optional[TelegramSignalEvent] = None
    update_id: Optional[int] = None


@dataclass(frozen=True)
class TelegramPollResult:
    ok: bool
    reason_code: str
    next_update_id: int
    events: Sequence[TelegramSignalEvent] = field(default_factory=tuple)
    failure_reason: str = ""
