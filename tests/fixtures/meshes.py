"""Hand-built triangle meshes for closure-analyzer tests.

Coordinates are in metres and deliberately simple: a unit box is enough to
exercise every edge/winding/degeneracy rule without relying on the sweep code.
"""

from __future__ import annotations

import numpy as np


def _quad(vertices: list[list[float]], faces: list[list[int]], corners: list[int]) -> None:
    faces.append([corners[0], corners[1], corners[2]])
    faces.append([corners[0], corners[2], corners[3]])


def _box_vertices(scale: float = 1.0) -> np.ndarray:
    values = [
        [-1.0, -1.0, -1.0],
        [1.0, -1.0, -1.0],
        [1.0, 1.0, -1.0],
        [-1.0, 1.0, -1.0],
        [-1.0, -1.0, 1.0],
        [1.0, -1.0, 1.0],
        [1.0, 1.0, 1.0],
        [-1.0, 1.0, 1.0],
    ]
    return np.asarray(values, dtype=np.float64) * scale


def _outward_box_faces() -> np.ndarray:
    faces: list[list[int]] = []
    _quad([], faces, [0, 3, 2, 1])  # -Z
    _quad([], faces, [4, 5, 6, 7])  # +Z
    _quad([], faces, [0, 1, 5, 4])  # -Y
    _quad([], faces, [2, 3, 7, 6])  # +Y
    _quad([], faces, [0, 4, 7, 3])  # -X
    _quad([], faces, [1, 2, 6, 5])  # +X
    return np.asarray(faces, dtype=np.uint32)


def closed_box(scale: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Return an outward-wound, watertight box at ``scale``."""
    return _box_vertices(scale), _outward_box_faces()


def open_box() -> tuple[np.ndarray, np.ndarray]:
    """Return a box with the +Z face removed (a boundary edge loop)."""
    vertices, faces = closed_box()
    return vertices, faces[2:]


def inward_box() -> tuple[np.ndarray, np.ndarray]:
    """Return a watertight box whose winding points inward."""
    vertices, faces = closed_box()
    return vertices, faces[:, [0, 2, 1]].copy()


def non_manifold_mesh() -> tuple[np.ndarray, np.ndarray]:
    """A closed box plus a duplicated face (three incident faces per edge)."""
    vertices, faces = closed_box()
    return vertices, np.vstack([faces, faces[0:1]])


def repeated_vertex_triangle() -> tuple[np.ndarray, np.ndarray]:
    """Two clean triangles plus one with a repeated vertex index."""
    vertices = np.asarray(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    faces = np.asarray([[0, 1, 2], [1, 3, 2], [0, 0, 1]], dtype=np.uint32)
    return vertices, faces


def zero_area_triangle() -> tuple[np.ndarray, np.ndarray]:
    """A triangle whose three vertices are collinear (area zero)."""
    vertices = np.asarray(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 1.0, 1.0]],
        dtype=np.float64,
    )
    faces = np.asarray([[0, 1, 2], [0, 1, 3], [1, 2, 3], [0, 2, 3]], dtype=np.uint32)
    return vertices, faces


__all__ = [
    "closed_box",
    "inward_box",
    "non_manifold_mesh",
    "open_box",
    "repeated_vertex_triangle",
    "zero_area_triangle",
]
