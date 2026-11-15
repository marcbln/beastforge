"""Swept-tube surface construction with construction-bound skin weights.

Limbs and torsos both sweep a ring cross-section along a bone chain. The frame
uses parallel transport, so the surface cannot flip or twist unpredictably.
Every vertex is born with one or two joint influences (ADR 261114-3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from beastforge.model.recipe import Modifiers, RadiusProfile, Surface
from beastforge.rig.skeleton import BuiltSkeleton
from beastforge.rig.weights import joint_weights
from beastforge.rng import derive_phases


@dataclass
class SurfaceGeometry:
    """Raw per-surface buffers before they are merged into the mesh."""

    positions: np.ndarray
    uv: np.ndarray
    joints: np.ndarray
    weights: np.ndarray
    indices: np.ndarray


def _radius_at(radius: RadiusProfile | list[float], u: float) -> float:
    if isinstance(radius, RadiusProfile):
        return float(radius.start + (radius.end - radius.start) * u)
    values = [float(value) for value in radius]
    if not values:
        return 1.0
    if len(values) == 1:
        return values[0]
    position = u * (len(values) - 1)
    index = min(int(position), len(values) - 2)
    fraction = position - index
    return float(values[index] + (values[index + 1] - values[index]) * fraction)


def _path_and_bones(surface: Surface, skeleton: BuiltSkeleton) -> tuple[np.ndarray, list[str]]:
    bones = list(surface.bones)
    first_parent = skeleton.parent_of(bones[0])
    if first_parent is not None:
        points = [skeleton.world_positions[first_parent]] + [
            skeleton.world_positions[bone] for bone in bones
        ]
        return np.asarray(points, dtype=np.float64), bones
    points = [skeleton.world_positions[bone] for bone in bones]
    if len(bones) == 1:
        bone = bones[0]
        direction = _bone_direction(skeleton, bone)
        radius = _radius_at(surface.radius, 0.5)
        half = max(radius, 1e-3)
        center = skeleton.world_positions[bone]
        points = [center - direction * half, center + direction * half]
        return np.asarray(points, dtype=np.float64), bones
    return np.asarray(points, dtype=np.float64), bones[:-1]


def _bone_direction(skeleton: BuiltSkeleton, bone: str) -> np.ndarray:
    from beastforge.rig.skeleton import quat_to_matrix

    local_y = quat_to_matrix(skeleton.world_rotations[bone]) @ np.array([0.0, 1.0, 0.0])
    norm = float(np.linalg.norm(local_y))
    if norm == 0.0:
        return np.array([0.0, 1.0, 0.0])
    return local_y / norm


def _rotate_normal(
    previous_tangent: np.ndarray, tangent: np.ndarray, normal: np.ndarray
) -> np.ndarray:
    axis = np.cross(previous_tangent, tangent)
    sin_angle = float(np.linalg.norm(axis))
    cos_angle = float(np.dot(previous_tangent, tangent))
    if sin_angle > 1e-12:
        axis = axis / sin_angle
        # Rodrigues rotation of the normal about the minimal-rotation axis.
        normal = (
            normal * cos_angle
            + np.cross(axis, normal) * sin_angle
            + axis * np.dot(axis, normal) * (1.0 - cos_angle)
        )
    # Re-orthogonalize against the new tangent.
    normal = normal - tangent * float(np.dot(normal, tangent))
    norm = float(np.linalg.norm(normal))
    if norm < 1e-12:
        reference = np.array([0.0, 1.0, 0.0])
        if abs(float(np.dot(reference, tangent))) > 0.9:
            reference = np.array([1.0, 0.0, 0.0])
        normal = np.cross(tangent, reference)
        norm = float(np.linalg.norm(normal))
    return normal / norm


def _first_normal(tangent: np.ndarray) -> np.ndarray:
    reference = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    if abs(float(np.dot(reference, tangent))) > 0.9:
        reference = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    normal = np.cross(tangent, reference)
    norm = float(np.linalg.norm(normal))
    if norm < 1e-12:
        normal = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        norm = 1.0
    return normal / norm


def _sample_path(
    points: np.ndarray, rings: int
) -> list[tuple[np.ndarray, np.ndarray, int, float, float]]:
    """Sample the path; returns (position, tangent, segment, local_s, segment_length)."""
    segment_vectors = points[1:] - points[:-1]
    lengths = np.linalg.norm(segment_vectors, axis=1)
    lengths = np.maximum(lengths, 1e-9)
    cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
    total = float(cumulative[-1])
    samples: list[tuple[np.ndarray, np.ndarray, int, float, float]] = []
    for ring in range(rings):
        u = 0.0 if rings == 1 else ring / (rings - 1)
        target = u * total
        segment = int(np.searchsorted(cumulative, target, side="right") - 1)
        segment = min(max(segment, 0), len(lengths) - 1)
        local_s = float(target - cumulative[segment])
        local_s = min(max(local_s, 0.0), float(lengths[segment]))
        fraction = local_s / float(lengths[segment])
        position = points[segment] + segment_vectors[segment] * fraction
        tangent = segment_vectors[segment] / float(lengths[segment])
        samples.append((position, tangent, segment, local_s, float(lengths[segment])))
    return samples


def _noise_multiplier(
    modifiers: Modifiers, surface_name: str, seed: str, u: float, theta: float
) -> float:
    noise = modifiers.radial_noise
    if noise is None or noise.amplitude <= 0.0:
        return 1.0
    phases = derive_phases(seed, f"radial:{surface_name}", 3)
    frequency = max(float(noise.frequency), 1e-6)
    value = (
        0.5 * np.sin(frequency * theta + phases[0])
        + 0.3 * np.sin(2.0 * frequency * theta + phases[1])
        + 0.2 * np.sin(frequency * math.tau * u + phases[2])
    )
    return 1.0 + float(noise.amplitude) * float(value)


def sweep_surface(
    surface: Surface,
    skeleton: BuiltSkeleton,
    seed: str,
    *,
    caps: bool = False,
) -> SurfaceGeometry:
    """Build one swept surface along ``surface.bones``."""
    rings = max(int(surface.rings), 2)
    segments = max(int(surface.segments), 3)
    points, segment_bones = _path_and_bones(surface, skeleton)
    samples = _sample_path(points, rings)
    modifiers = surface.modifiers

    positions: list[np.ndarray] = []
    uvs: list[np.ndarray] = []
    joint_rows: list[np.ndarray] = []
    weight_rows: list[np.ndarray] = []

    tangent = samples[0][1]
    normal = _first_normal(tangent)
    previous_tangent = tangent

    for ring, (position, tangent, segment, local_s, length) in enumerate(samples):
        u = 0.0 if rings == 1 else ring / (rings - 1)
        normal = _rotate_normal(previous_tangent, tangent, normal)
        previous_tangent = tangent
        binormal = np.cross(tangent, normal)

        base_radius = _radius_at(surface.radius, u)
        taper = 1.0
        if modifiers.taper is not None:
            taper = float(modifiers.taper.start + (modifiers.taper.end - modifiers.taper.start) * u)
        current_index = skeleton.index(segment_bones[segment])
        previous_index = skeleton.index(segment_bones[segment - 1]) if segment - 1 >= 0 else None
        next_index = (
            skeleton.index(segment_bones[segment + 1]) if segment + 1 < len(segment_bones) else None
        )
        influence = joint_weights(
            current_index,
            previous_index,
            next_index,
            s=local_s,
            length=length,
            blend=float(surface.blend),
        )
        joints = np.array([influence.joints[0], influence.joints[1], 0, 0], dtype=np.uint16)
        weights = np.array([influence.weights[0], influence.weights[1], 0.0, 0.0], dtype=np.float64)
        total_weight = float(weights.sum())
        weights = weights / total_weight if total_weight > 0.0 else np.array([1.0, 0.0, 0.0, 0.0])

        for segment_radial in range(segments):
            theta = math.tau * segment_radial / segments + float(modifiers.twist) * u
            radial = np.cos(theta) * normal + np.sin(theta) * binormal
            radius = (
                base_radius * taper * _noise_multiplier(modifiers, surface.name, seed, u, theta)
            )
            offset = radial * max(radius, 1e-6)
            offset = offset * np.asarray(modifiers.squash, dtype=np.float64)
            offset = offset * np.asarray(modifiers.scale, dtype=np.float64)
            positions.append(position + offset)
            uvs.append(np.array([u, segment_radial / segments], dtype=np.float64))
            joint_rows.append(joints)
            weight_rows.append(weights)

    indices: list[np.ndarray] = []
    for ring in range(rings - 1):
        for segment_radial in range(segments):
            a = ring * segments + segment_radial
            b = ring * segments + (segment_radial + 1) % segments
            c = (ring + 1) * segments + segment_radial
            d = (ring + 1) * segments + (segment_radial + 1) % segments
            indices.append(np.array([a, d, c], dtype=np.uint32))
            indices.append(np.array([a, b, d], dtype=np.uint32))

    if caps:
        start_center = len(positions)
        positions.append(samples[0][0].copy())
        uvs.append(np.array([0.0, 0.0]))
        joint_rows.append(joint_rows[0])
        weight_rows.append(weight_rows[0])
        end_center = len(positions)
        positions.append(samples[-1][0].copy())
        uvs.append(np.array([1.0, 0.0]))
        joint_rows.append(joint_rows[-1])
        weight_rows.append(weight_rows[-1])
        for segment_radial in range(segments):
            a = segment_radial
            b = (segment_radial + 1) % segments
            indices.append(np.array([start_center, b, a], dtype=np.uint32))
            last_ring = (rings - 1) * segments
            c = last_ring + segment_radial
            d = last_ring + (segment_radial + 1) % segments
            indices.append(np.array([end_center, c, d], dtype=np.uint32))

    return SurfaceGeometry(
        positions=np.asarray(positions, dtype=np.float64),
        uv=np.asarray(uvs, dtype=np.float64),
        joints=np.asarray(joint_rows, dtype=np.uint16),
        weights=np.asarray(weight_rows, dtype=np.float64),
        indices=np.asarray(indices, dtype=np.uint32),
    )


def rigid_surface(
    surface: Surface,
    skeleton: BuiltSkeleton,
    seed: str,
) -> SurfaceGeometry:
    """Build a capped rigid part with weight 1.0 on exactly one bone."""
    bone = surface.rigid_bone or surface.bones[0]
    center = skeleton.world_positions[bone]
    direction = _bone_direction(skeleton, bone)
    radius = _radius_at(surface.radius, 0.5)
    half_height = max(radius, 1e-3)
    points = np.asarray(
        [center - direction * half_height, center + direction * half_height],
        dtype=np.float64,
    )
    rings = max(int(surface.rings), 2)
    segments = max(int(surface.segments), 3)
    samples = _sample_path(points, rings)
    modifiers = surface.modifiers
    bone_index = skeleton.index(bone)
    joints = np.array([bone_index, bone_index, 0, 0], dtype=np.uint16)
    weights = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

    positions: list[np.ndarray] = []
    uvs: list[np.ndarray] = []
    joint_rows: list[np.ndarray] = []
    weight_rows: list[np.ndarray] = []
    tangent = samples[0][1]
    normal = _first_normal(tangent)
    previous_tangent = tangent
    for ring, (position, tangent, _segment, _s, _length) in enumerate(samples):
        u = 0.0 if rings == 1 else ring / (rings - 1)
        normal = _rotate_normal(previous_tangent, tangent, normal)
        previous_tangent = tangent
        binormal = np.cross(tangent, normal)
        for segment_radial in range(segments):
            theta = math.tau * segment_radial / segments + float(modifiers.twist) * u
            radial = np.cos(theta) * normal + np.sin(theta) * binormal
            offset = radial * radius
            offset = offset * np.asarray(modifiers.squash, dtype=np.float64)
            offset = offset * np.asarray(modifiers.scale, dtype=np.float64)
            positions.append(position + offset)
            uvs.append(np.array([u, segment_radial / segments], dtype=np.float64))
            joint_rows.append(joints)
            weight_rows.append(weights)

    indices: list[np.ndarray] = []
    for ring in range(rings - 1):
        for segment_radial in range(segments):
            a = ring * segments + segment_radial
            b = ring * segments + (segment_radial + 1) % segments
            c = (ring + 1) * segments + segment_radial
            d = (ring + 1) * segments + (segment_radial + 1) % segments
            indices.append(np.array([a, d, c], dtype=np.uint32))
            indices.append(np.array([a, b, d], dtype=np.uint32))
    start_center = len(positions)
    positions.append(samples[0][0].copy())
    uvs.append(np.array([0.0, 0.0]))
    joint_rows.append(joints)
    weight_rows.append(weights)
    end_center = len(positions)
    positions.append(samples[-1][0].copy())
    uvs.append(np.array([1.0, 0.0]))
    joint_rows.append(joints)
    weight_rows.append(weights)
    for segment_radial in range(segments):
        a = segment_radial
        b = (segment_radial + 1) % segments
        indices.append(np.array([start_center, b, a], dtype=np.uint32))
        last_ring = (rings - 1) * segments
        c = last_ring + segment_radial
        d = last_ring + (segment_radial + 1) % segments
        indices.append(np.array([end_center, c, d], dtype=np.uint32))

    return SurfaceGeometry(
        positions=np.asarray(positions, dtype=np.float64),
        uv=np.asarray(uvs, dtype=np.float64),
        joints=np.asarray(joint_rows, dtype=np.uint16),
        weights=np.asarray(weight_rows, dtype=np.float64),
        indices=np.asarray(indices, dtype=np.uint32),
    )
