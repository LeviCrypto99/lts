from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import config

_LOCK_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.Lock] = {}


def _resolve_max_bytes(max_bytes: int | None) -> int:
    value = int(max_bytes if max_bytes is not None else config.LOG_ROTATE_MAX_BYTES)
    return max(1024, value)


def _resolve_backup_count(backup_count: int | None) -> int:
    value = int(backup_count if backup_count is not None else config.LOG_ROTATE_BACKUP_COUNT)
    return max(0, value)


def _lock_for_path(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCK_GUARD:
        existing = _PATH_LOCKS.get(key)
        if existing is not None:
            return existing
        created = threading.Lock()
        _PATH_LOCKS[key] = created
        return created


def _backup_path(path: Path, index: int) -> Path:
    return path.with_name(f"{path.name}.{index}")


def _try_remove(path: Path) -> None:
    try:
        path.unlink()
    except Exception:
        pass


def _truncate_in_place(path: Path, max_bytes: int) -> tuple[bool, int, int]:
    if not path.exists():
        return False, 0, 0
    try:
        previous_size = path.stat().st_size
        keep_bytes = max(1024, max_bytes // 2)
        read_size = min(previous_size, keep_bytes)
        start_offset = max(0, previous_size - read_size)

        with open(path, "rb") as read_handle:
            read_handle.seek(start_offset)
            tail = read_handle.read(read_size)

        first_newline = tail.find(b"\n")
        if first_newline != -1 and first_newline + 1 < len(tail):
            tail = tail[first_newline + 1 :]

        with open(path, "wb") as write_handle:
            write_handle.write(tail)
        return True, previous_size, len(tail)
    except Exception:
        return False, 0, 0


def _rotate(path: Path, backup_count: int) -> Path | None:
    if not path.exists():
        return None
    if backup_count <= 0:
        _try_remove(path)
        return None

    _try_remove(_backup_path(path, backup_count))
    for idx in range(backup_count - 1, 0, -1):
        src = _backup_path(path, idx)
        if not src.exists():
            continue
        dst = _backup_path(path, idx + 1)
        try:
            os.replace(src, dst)
        except Exception:
            pass

    rotated = _backup_path(path, 1)
    try:
        os.replace(path, rotated)
        return rotated
    except Exception:
        return None


def append_rotating_log_line(
    path: Path,
    line: str,
    *,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> None:
    max_size = _resolve_max_bytes(max_bytes)
    max_backups = _resolve_backup_count(backup_count)
    lock = _lock_for_path(path)
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotated_to: Path | None = None
        truncated_sizes: tuple[int, int] | None = None
        try:
            line_bytes = len(line.encode("utf-8", errors="replace"))
            current_size = path.stat().st_size if path.exists() else 0
            if current_size + line_bytes > max_size:
                if max_backups <= 0:
                    truncated, previous_size, kept_size = _truncate_in_place(path, max_size)
                    if truncated:
                        truncated_sizes = (previous_size, kept_size)
                    else:
                        rotated_to = _rotate(path, 0)
                else:
                    rotated_to = _rotate(path, max_backups)
        except Exception:
            rotated_to = None
            truncated_sizes = None

        with open(path, "a", encoding="utf-8") as handle:
            if truncated_sizes is not None:
                previous_size, kept_size = truncated_sizes
                truncate_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                handle.write(
                    f"[{truncate_ts}] [LOG_TRUNCATE] previous_bytes={previous_size} "
                    f"kept_bytes={kept_size} max_bytes={max_size}\n"
                )
            elif rotated_to is not None:
                rotate_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                handle.write(
                    f"[{rotate_ts}] [LOG_ROTATE] rotated_file={rotated_to.name} "
                    f"max_bytes={max_size} backups={max_backups}\n"
                )
            handle.write(line)
