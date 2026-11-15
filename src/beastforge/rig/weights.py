"""Skin-weight blending for construction-bound surfaces (ADR 261114-3).

The bands are centred on the joint, not the bone end: the last half-band of a
bone hands 0..50% influence to the next bone, and the first half-band of that
bone hands 50..0% back to the previous bone. The result is continuous at the
joint with at most two influences per vertex.
"""

from __future__ import annotations

from dataclasses import dataclass

FLOAT_TOLERANCE = 1e-5


def smoothstep(value: float) -> float:
    """Hermite smoothstep on ``[0, 1]``."""
    t = min(1.0, max(0.0, value))
    return t * t * (3.0 - 2.0 * t)


@dataclass
class Influence:
    """Two joints and their normalized weights, in deterministic order."""

    joints: tuple[int, int]
    weights: tuple[float, float]


def band_for(length: float, blend: float) -> float:
    """Clamp the joint band so it can never cover more than a third of the bone."""
    return max(0.0, min(blend * length, 0.35 * length))


def joint_weights(
    current_index: int,
    previous_index: int | None,
    next_index: int | None,
    *,
    s: float,
    length: float,
    blend: float,
) -> Influence:
    """Blend the current bone with its predecessor or successor at a joint."""
    band = band_for(length, blend)
    half = band * 0.5
    if half <= 0.0:
        return Influence((current_index, current_index), (1.0, 0.0))
    if previous_index is not None and s < half:
        t = smoothstep(s / half)
        weight_previous = 0.5 * (1.0 - t)
        weight_current = 1.0 - weight_previous
        return Influence((current_index, previous_index), (weight_current, weight_previous))
    if next_index is not None and s > length - half:
        t = smoothstep((s - (length - half)) / half)
        weight_next = 0.5 * t
        weight_current = 1.0 - weight_next
        return Influence((current_index, next_index), (weight_current, weight_next))
    return Influence((current_index, current_index), (1.0, 0.0))
