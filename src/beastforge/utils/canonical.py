"""Canonical serialization and hashing helpers (research D4/D8).

Canonical JSON is sorted, ASCII-only, uses compact separators, carries no
timestamps, normalizes ``-0.0`` to ``0.0``, and rejects NaN/Inf. It is the only
serializer used for the manifest, the generation report, and run-seed inputs.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON cannot encode NaN or Infinity")
        return 0.0 if value == 0.0 else value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any, *, trailing_newline: bool = True) -> str:
    """Serialize ``value`` to the canonical JSON form used across the tool."""
    text = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return text + "\n" if trailing_newline else text


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 of ``text`` encoded as UTF-8."""
    return sha256_hex(text.encode("utf-8"))


def sha256_bytes_file(path: str) -> str:
    """Hash a file without loading it all into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
