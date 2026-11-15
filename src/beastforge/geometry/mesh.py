"""Mesh buffers and deterministic normal/winding helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class SurfaceRange:
    """The vertex/index range owned by one recipe surface."""

    name: str
    vertex_offset: int
    vertex_count: int
    index_offset: int
    index_count: int
    material: str | None


@dataclass
class Mesh:
    """A single skinned mesh ready for export (data-model §13)."""

    positions: np.ndarray
    normals: np.ndarray
    uv: np.ndarray
    joints: np.ndarray
    weights: np.ndarray
    indices: np.ndarray
    surfaces: list[SurfaceRange] = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        """Number of vertices in the merged mesh."""
        return int(self.positions.shape[0])

    @property
    def triangle_count(self) -> int:
        """Number of triangles in the merged mesh."""
        return int(self.indices.shape[0])

    @property
    def bounds_min(self) -> np.ndarray:
        """Per-axis minimum of the mesh AABB."""
        return self.positions.min(axis=0)

    @property
    def bounds_max(self) -> np.ndarray:
        """Per-axis maximum of the mesh AABB."""
        return self.positions.max(axis=0)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(min, max)`` as float64 vectors."""
        return self.bounds_min, self.bounds_max


def compute_vertex_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Area-weighted vertex normals; degenerate normals fall back to +Y."""
    normals = np.zeros_like(positions, dtype=np.float64)
    if indices.size == 0:
        return normals
    triangles = positions[indices]
    face = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    for corner in range(3):
        np.add.at(normals, indices[:, corner], face)
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths == 0.0] = 1.0
    normals = normals / lengths[:, None]
    return normals


def outward_indices(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Flip triangle winding if the mesh's signed volume points inward."""
    if indices.size == 0:
        return indices
    center = positions.mean(axis=0)
    triangles = positions[indices]
    a = triangles[:, 0] - center
    b = triangles[:, 1] - center
    c = triangles[:, 2] - center
    signed_volume = float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))))
    if signed_volume < 0.0:
        return indices[:, [0, 2, 1]].copy()
    return indices


def empty_mesh() -> Mesh:
    """An empty mesh, useful as an accumulator seed."""
    return Mesh(
        positions=np.zeros((0, 3), dtype=np.float64),
        normals=np.zeros((0, 3), dtype=np.float64),
        uv=np.zeros((0, 2), dtype=np.float64),
        joints=np.zeros((0, 4), dtype=np.uint16),
        weights=np.zeros((0, 4), dtype=np.float64),
        indices=np.zeros((0, 3), dtype=np.uint32),
    )


def append_surface(
    mesh: Mesh,
    *,
    name: str,
    positions: np.ndarray,
    uv: np.ndarray,
    joints: np.ndarray,
    weights: np.ndarray,
    indices: np.ndarray,
    material: str | None,
) -> None:
    """Append one constructed surface to the merged mesh in recipe order."""
    vertex_offset = mesh.vertex_count
    index_offset = mesh.triangle_count
    normals = compute_vertex_normals(positions, outward_indices(positions, indices))
    oriented = outward_indices(positions, indices)
    mesh.positions = np.concatenate([mesh.positions, positions], axis=0)
    mesh.normals = np.concatenate([mesh.normals, normals], axis=0)
    mesh.uv = np.concatenate([mesh.uv, uv], axis=0)
    mesh.joints = np.concatenate([mesh.joints, joints.astype(np.uint16)], axis=0)
    mesh.weights = np.concatenate([mesh.weights, weights], axis=0)
    mesh.indices = np.concatenate(
        [mesh.indices, (oriented + vertex_offset).astype(np.uint32)], axis=0
    )
    mesh.surfaces.append(
        SurfaceRange(
            name=name,
            vertex_offset=vertex_offset,
            vertex_count=int(positions.shape[0]),
            index_offset=index_offset,
            index_count=int(oriented.shape[0]),
            material=material,
        )
    )
