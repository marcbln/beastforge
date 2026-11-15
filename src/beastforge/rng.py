"""Deterministic seeded streams (ADR 261114-2, research D4).

No module-level RNG state exists. Every draw is a pure function of the run seed
and an explicit ``(purpose, index)`` pair, so adding a draw in one subsystem can
never shift another subsystem's values.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from beastforge.utils.canonical import canonical_json


def recipe_digest(document: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical recipe document (formatting is not content)."""
    return hashlib.sha256(
        canonical_json(document, trailing_newline=False).encode("utf-8")
    ).hexdigest()


def run_seed(recipe_sha256: str, resolved_params: Mapping[str, Any]) -> str:
    """Derive the run seed from the recipe hash and the fully resolved params."""
    payload = (
        "beastforge/v1:"
        + recipe_sha256
        + ":"
        + canonical_json(resolved_params, trailing_newline=False)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_unit(seed: str, purpose: str, index: int = 0) -> float:
    """Return a deterministic float in ``[0, 1)`` for ``(seed, purpose, index)``."""
    digest = hashlib.sha256(f"{seed}:{purpose}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def derive_phases(seed: str, purpose: str, count: int) -> list[float]:
    """Return ``count`` deterministic angles in ``[0, 2*pi)``."""
    import math

    return [derive_unit(seed, purpose, index) * math.tau for index in range(count)]
