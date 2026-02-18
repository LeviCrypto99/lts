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
    """Build a log path under logs/<log_name>_log_file next to runtime executable."""
    file_name = Path(str(filename or "").strip()).name
    if not file_name:
        file_name = "application.log"
    log_stem = Path(file_name).stem or "application"
    log_folder_name = f"{log_stem}_log_file"

    base_dir: Path
    if target_executable is not None:
        try:
            base_dir = Path(target_executable).expanduser().resolve().parent
            return base_dir / "logs" / log_folder_name / file_name
        except Exception:
            pass
    base_dir = get_runtime_dir()
    return base_dir / "logs" / log_folder_name / file_name
