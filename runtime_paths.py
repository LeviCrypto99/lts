from __future__ import annotations

import sys
from pathlib import Path


def get_runtime_dir() -> Path:
    """Return the directory of the running executable (or project dir in dev)."""
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
    except Exception:
        pass
    return Path(__file__).resolve().parent


def get_log_path(
    filename: str,
    *,
    target_executable: str | Path | None = None,
) -> Path:
    """Build a log path next to the runtime executable (or given target executable)."""
    if target_executable is not None:
        try:
            return Path(target_executable).expanduser().resolve().parent / filename
        except Exception:
            pass
    return get_runtime_dir() / filename
