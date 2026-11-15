"""Perceptual image comparison for the showroom (FR-040)."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

DEFAULT_PER_PIXEL_THRESHOLD = 8
DEFAULT_CHANGED_PIXEL_RATIO = 0.001


@dataclass
class FrameComparison:
    """One frame's comparison metrics."""

    max_pixel_delta: int
    changed_pixel_ratio: float
    passed: bool


def decode_png(data: bytes) -> np.ndarray:
    """Decode a PNG to an RGBA uint8 array."""
    return np.asarray(Image.open(BytesIO(data)).convert("RGBA"), dtype=np.uint8)


def compare_images(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    per_pixel_threshold: int = DEFAULT_PER_PIXEL_THRESHOLD,
    changed_pixel_ratio: float = DEFAULT_CHANGED_PIXEL_RATIO,
) -> FrameComparison:
    """Compare two RGBA frames using the documented two-number tolerance."""
    if reference.shape != candidate.shape:
        return FrameComparison(max_pixel_delta=255, changed_pixel_ratio=1.0, passed=False)
    difference = np.abs(reference.astype(np.int16) - candidate.astype(np.int16))
    max_delta = int(difference.max())
    opaque = (reference[:, :, 3] > 0) | (candidate[:, :, 3] > 0)
    opaque_count = int(opaque.sum())
    if opaque_count == 0:
        return FrameComparison(
            max_pixel_delta=max_delta,
            changed_pixel_ratio=0.0,
            passed=max_delta <= per_pixel_threshold,
        )
    changed_pixel = (difference > per_pixel_threshold).any(axis=2)
    changed = int((changed_pixel & opaque).sum())
    ratio = changed / opaque_count
    passed = ratio <= changed_pixel_ratio
    return FrameComparison(max_pixel_delta=max_delta, changed_pixel_ratio=ratio, passed=passed)


def compare_png(
    reference: bytes,
    candidate: bytes,
    *,
    per_pixel_threshold: int = DEFAULT_PER_PIXEL_THRESHOLD,
    changed_pixel_ratio: float = DEFAULT_CHANGED_PIXEL_RATIO,
) -> FrameComparison:
    """Decode and compare two PNG payloads."""
    return compare_images(
        decode_png(reference),
        decode_png(candidate),
        per_pixel_threshold=per_pixel_threshold,
        changed_pixel_ratio=changed_pixel_ratio,
    )
