"""Pure closed-solid analysis for one part's local triangle list.

The check is deliberately per part, never on the merged mesh: adjacent parts may
share space at a joint, and the seam between them is not a shared edge. Only
watertightness, manifoldness, winding, and degeneracy are inspected; self
intersection and duplicate faces are out of scope.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ClosureReport:
    """The closure facts for one part."""

    name: str
    closed: bool
    boundary_edges: int
    non_manifold_edges: int
    inconsistent_edges: int
    degenerate_faces: int
    signed_volume: float
    epsilon: float
    first_issue: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)


def scale_epsilon(positions: np.ndarray) -> float:
    """Return ``max(1e-12, diagonal² * 1e-10)`` for the part's local AABB."""
    if positions.size == 0:
        return 1e-12
    minimum = positions.min(axis=0)
    maximum = positions.max(axis=0)
    diagonal = float(np.linalg.norm(maximum - minimum))
    return max(1e-12, diagonal * diagonal * 1e-10)


def analyze_part(positions: np.ndarray, indices: np.ndarray, name: str) -> ClosureReport:
    """Analyze one part's local positions and (already re-based) indices."""
    positions = np.asarray(positions, dtype=np.float64)
    indices = np.asarray(indices, dtype=np.int64)
    epsilon = scale_epsilon(positions)

    edge_counts: Counter[tuple[int, int]] = Counter()
    edge_direction: dict[tuple[int, int], list[int]] = {}
    degenerate = 0
    first_degenerate: dict[str, Any] | None = None

    if indices.size:
        triangles = positions[indices]
        faces = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        areas = np.linalg.norm(faces, axis=1) * 0.5
        repeated = (
            (indices[:, 0] == indices[:, 1])
            | (indices[:, 1] == indices[:, 2])
            | (indices[:, 0] == indices[:, 2])
        )
        bad = repeated | (areas <= epsilon)
        degenerate = int(np.count_nonzero(bad))
        if degenerate:
            first = int(np.argmax(bad))
            first_degenerate = {
                "face": first,
                "indices": [int(value) for value in indices[first]],
                "area": float(areas[first]),
                "repeated_index": bool(repeated[first]),
            }
        signed_volume = float(np.sum(np.einsum("ij,ij->i", triangles[:, 0], faces)) / 6.0)
    else:
        signed_volume = 0.0

    for triangle in indices:
        edges = (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        )
        for start, end in edges:
            key = (int(min(start, end)), int(max(start, end)))
            edge_counts[key] += 1
            direction = 1 if start < end else -1
            edge_direction.setdefault(key, []).append(direction)

    boundary = 0
    non_manifold = 0
    inconsistent = 0
    first_boundary: tuple[int, int] | None = None
    first_non_manifold: tuple[int, int] | None = None
    first_inconsistent: tuple[int, int] | None = None
    for key in sorted(edge_counts):
        count = edge_counts[key]
        if count == 1:
            boundary += 1
            if first_boundary is None:
                first_boundary = key
        elif count > 2:
            non_manifold += 1
            if first_non_manifold is None:
                first_non_manifold = key
        else:
            directions = edge_direction.get(key, [])
            if len(directions) == 2 and directions[0] == directions[1]:
                inconsistent += 1
                if first_inconsistent is None:
                    first_inconsistent = key

    closed = (
        boundary == 0
        and non_manifold == 0
        and inconsistent == 0
        and degenerate == 0
        and signed_volume > 0.0
    )

    first_issue: dict[str, Any] | None = None
    if boundary:
        first_issue = {"kind": "boundary", "edge": list(first_boundary or ())}
    elif non_manifold:
        first_issue = {"kind": "non-manifold", "edge": list(first_non_manifold or ())}
    elif inconsistent:
        first_issue = {"kind": "inconsistent", "edge": list(first_inconsistent or ())}
    elif degenerate:
        first_issue = {"kind": "degenerate", **(first_degenerate or {})}
    elif signed_volume <= 0.0:
        first_issue = {"kind": "inward", "signed_volume": signed_volume}

    return ClosureReport(
        name=name,
        closed=closed,
        boundary_edges=boundary,
        non_manifold_edges=non_manifold,
        inconsistent_edges=inconsistent,
        degenerate_faces=degenerate,
        signed_volume=signed_volume,
        epsilon=epsilon,
        first_issue=first_issue,
        details={
            "triangles": int(indices.shape[0]),
            "vertices": int(positions.shape[0]),
        },
    )


__all__ = ["ClosureReport", "analyze_part", "scale_epsilon"]
