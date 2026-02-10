from __future__ import annotations

import hashlib
import re
import urllib.parse
from pathlib import Path
from typing import Any, Mapping, Sequence

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_HASH_CONTAINER_KEYS = ("sha256", "hashes")


def normalize_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not _SHA256_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _build_candidate_keys(keys: Sequence[str], *, file_url: str | None = None) -> list[str]:
    candidates = [str(key).strip() for key in keys if str(key).strip()]
    if file_url:
        parsed = urllib.parse.urlparse(str(file_url))
        filename = urllib.parse.unquote(Path(parsed.path).name).strip()
        if filename:
            stem = Path(filename).stem
            candidates.extend([filename, filename.lower(), stem, stem.lower()])
    return _dedupe_preserve_order(candidates)


def _extract_from_mapping(mapping: Mapping[str, Any], candidate_keys: Sequence[str]) -> str | None:
    lowered = {str(key).lower(): value for key, value in mapping.items()}
    for candidate in candidate_keys:
        normalized = normalize_sha256(mapping.get(candidate))
        if normalized:
            return normalized
        normalized = normalize_sha256(lowered.get(candidate.lower()))
        if normalized:
            return normalized
    return None


def extract_sha256_from_metadata(
    metadata: Mapping[str, Any],
    *,
    keys: Sequence[str],
    file_url: str | None = None,
) -> str | None:
    candidate_keys = _build_candidate_keys(keys, file_url=file_url)
    direct = _extract_from_mapping(metadata, candidate_keys)
    if direct:
        return direct

    lowered = {str(key).lower(): value for key, value in metadata.items()}
    for container_key in _HASH_CONTAINER_KEYS:
        nested = lowered.get(container_key)
        if isinstance(nested, Mapping):
            resolved = _extract_from_mapping(nested, candidate_keys)
            if resolved:
                return resolved
    return None


def calculate_file_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(max(1024, int(chunk_size)))
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_sha256(path: Path, expected_sha256: str) -> tuple[bool, str]:
    normalized_expected = normalize_sha256(expected_sha256)
    if normalized_expected is None:
        raise ValueError("expected_sha256 must be a 64-char hex string.")
    actual_sha256 = calculate_file_sha256(path)
    return actual_sha256 == normalized_expected, actual_sha256
