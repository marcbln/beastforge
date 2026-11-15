"""Skeleton construction: rest/world transforms and inverse bind matrices."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from beastforge.model.errors import BeastforgeError
from beastforge.model.recipe import Skeleton, Transform


def quat_normalize(quat: np.ndarray) -> np.ndarray:
    """Return a unit quaternion ``[x, y, z, w]``."""
    norm = float(np.linalg.norm(quat))
    if norm == 0.0:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return np.asarray(quat, dtype=np.float64) / norm


def quat_to_matrix(quat: np.ndarray) -> np.ndarray:
    """Convert ``[x, y, z, w]`` to a 3x3 rotation matrix."""
    x, y, z, w = quat_normalize(quat)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product of two ``[x, y, z, w]`` quaternions."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array(
        [
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        ],
        dtype=np.float64,
    )


def quat_from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    """Build a unit quaternion for a rotation of ``angle`` radians about ``axis``."""
    axis = np.asarray(axis, dtype=np.float64)
    norm = float(np.linalg.norm(axis))
    if norm == 0.0:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    axis = axis / norm
    half = angle * 0.5
    sin_half = float(np.sin(half))
    return np.array(
        [axis[0] * sin_half, axis[1] * sin_half, axis[2] * sin_half, float(np.cos(half))],
        dtype=np.float64,
    )


def trs_matrix(translation: list[float], rotation: list[float], scale: list[float]) -> np.ndarray:
    """Compose ``T * R * S`` as a 4x4 matrix."""
    matrix = np.eye(4, dtype=np.float64)
    rotation_matrix = quat_to_matrix(np.asarray(rotation, dtype=np.float64))
    matrix[:3, :3] = rotation_matrix @ np.diag(np.asarray(scale, dtype=np.float64))
    matrix[:3, 3] = np.asarray(translation, dtype=np.float64)
    return matrix


def rotation_determinant(rotation: list[float], scale: list[float]) -> float:
    """Determinant of the local transform's linear part."""
    return float(np.linalg.det(trs_matrix([0.0, 0.0, 0.0], rotation, scale)[:3, :3]))


@dataclass
class BuiltSkeleton:
    """A skeleton resolved to world-space rest matrices."""

    names: list[str]
    parents: dict[str, str | None]
    children: dict[str, list[str]]
    local_matrices: dict[str, np.ndarray]
    world_matrices: dict[str, np.ndarray]
    inverse_bind: dict[str, np.ndarray]
    world_positions: dict[str, np.ndarray]
    world_rotations: dict[str, np.ndarray]
    lengths: dict[str, float]
    local_transforms: dict[str, Transform]
    node_order: list[str]

    def index(self, name: str) -> int:
        """Return the skin/joint index for a bone (root first)."""
        return self.node_order.index(name)

    def parent_of(self, name: str) -> str | None:
        """Return the parent bone name, if any."""
        return self.parents.get(name)

    def bone_length(self, name: str) -> float:
        """Return the bone's derived rest length in metres."""
        return self.lengths.get(name, 0.0)


def structural_error(code: str, message: str, *, path: str, remedy: str) -> BeastforgeError:
    """Build a skeleton error with a stable code."""
    return BeastforgeError(
        code,
        message,
        location={"path": path},
        expected="a valid skeleton",
        actual=message,
        remedy=remedy,
    )


def build_skeleton(skeleton: Skeleton) -> BuiltSkeleton:
    """Resolve a validated skeleton into world matrices and inverse binds."""
    names = [bone.name for bone in skeleton.bones]
    if len(set(names)) != len(names):
        duplicate = next(name for name in names if names.count(name) > 1)
        raise structural_error(
            "skeleton-duplicate-bone",
            f"Bone name {duplicate!r} appears more than once.",
            path="skeleton.bones",
            remedy="Give every bone a unique name.",
        )
    by_name = {bone.name: bone for bone in skeleton.bones}
    roots = [bone.name for bone in skeleton.bones if bone.parent is None]
    if len(roots) != 1:
        raise structural_error(
            "skeleton-root-multiple" if roots else "skeleton-root-missing",
            f"Expected exactly one root bone, found {len(roots)}.",
            path="skeleton.root",
            remedy="Set exactly one bone's parent to null and match skeleton.root.",
        )
    if roots[0] != skeleton.root:
        raise structural_error(
            "skeleton-root-missing",
            f"skeleton.root is {skeleton.root!r} but the parentless bone is {roots[0]!r}.",
            path="skeleton.root",
            remedy="Make skeleton.root name the bone whose parent is null.",
        )
    parents: dict[str, str | None] = {}
    children: dict[str, list[str]] = {name: [] for name in names}
    for bone in skeleton.bones:
        if bone.parent is not None and bone.parent not in by_name:
            raise structural_error(
                "skeleton-parent-missing",
                f"Bone {bone.name!r} names missing parent {bone.parent!r}.",
                path=f"skeleton.bones[{bone.name}]",
                remedy="Add the parent bone or fix the parent name.",
            )
        parents[bone.name] = bone.parent
        if bone.parent is not None:
            children[bone.parent].append(bone.name)

    # Walk from the root, rejecting cycles and unreachable bones.
    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise structural_error(
                "skeleton-cycle",
                f"Bone hierarchy contains a cycle through {name!r}.",
                path=f"skeleton.bones[{name}]",
                remedy="Make the parent chain a tree rooted at skeleton.root.",
            )
        if name in visited:
            return
        visiting.add(name)
        order.append(name)
        for child in children[name]:
            visit(child)
        visiting.remove(name)
        visited.add(name)

    visit(skeleton.root)
    if len(visited) != len(names):
        unreachable = next(name for name in names if name not in visited)
        raise structural_error(
            "skeleton-unreachable-bone",
            f"Bone {unreachable!r} is not reachable from the root.",
            path=f"skeleton.bones[{unreachable}]",
            remedy="Connect every bone to the root through parent links.",
        )

    local_matrices: dict[str, np.ndarray] = {}
    world_matrices: dict[str, np.ndarray] = {}
    inverse_bind: dict[str, np.ndarray] = {}
    world_positions: dict[str, np.ndarray] = {}
    world_rotations: dict[str, np.ndarray] = {}
    lengths: dict[str, float] = {}
    local_transforms: dict[str, Transform] = {}

    for name in order:
        bone = by_name[name]
        rest = bone.rest
        if not (
            np.all(np.isfinite(rest.translation))
            and np.all(np.isfinite(rest.rotation))
            and np.all(np.isfinite(rest.scale))
        ):
            raise structural_error(
                "skeleton-degenerate-transform",
                f"Bone {name!r} has a non-finite rest transform.",
                path=f"skeleton.bones[{name}].rest",
                remedy="Use finite numbers for translation, rotation, and scale.",
            )
        quat_norm = float(np.linalg.norm(np.asarray(rest.rotation, dtype=np.float64)))
        if abs(quat_norm - 1.0) > 1e-6:
            raise structural_error(
                "skeleton-degenerate-transform",
                f"Bone {name!r} rotation is not unit length (|q|={quat_norm:.9f}).",
                path=f"skeleton.bones[{name}].rest.rotation",
                remedy="Normalize the quaternion [x, y, z, w].",
            )
        if any(float(value) == 0.0 for value in rest.scale):
            raise structural_error(
                "skeleton-degenerate-transform",
                f"Bone {name!r} has a zero scale component.",
                path=f"skeleton.bones[{name}].rest.scale",
                remedy="Use positive, non-zero scale values.",
            )
        determinant = rotation_determinant(rest.rotation, rest.scale)
        if determinant <= 0.0:
            raise structural_error(
                "skeleton-inverted-transform",
                f"Bone {name!r} transform has a non-positive determinant ({determinant:.9g}).",
                path=f"skeleton.bones[{name}].rest",
                remedy="Use positive, non-zero scale values.",
            )
        local = trs_matrix(rest.translation, rest.rotation, rest.scale)
        local_matrices[name] = local
        local_transforms[name] = rest
        lengths[name] = float(np.linalg.norm(np.asarray(rest.translation, dtype=np.float64)))
        if bone.parent is None:
            world = local
            world_rotation = quat_normalize(np.asarray(rest.rotation, dtype=np.float64))
        else:
            world = world_matrices[bone.parent] @ local
            world_rotation = quat_normalize(
                quat_multiply(
                    world_rotations[bone.parent], np.asarray(rest.rotation, dtype=np.float64)
                )
            )
        world_matrices[name] = world
        world_rotations[name] = world_rotation
        world_positions[name] = world[:3, 3].copy()
        inverse_bind[name] = np.linalg.inv(world)

    node_order = [skeleton.root] + [name for name in names if name != skeleton.root]
    return BuiltSkeleton(
        names=names,
        parents=parents,
        children=children,
        local_matrices=local_matrices,
        world_matrices=world_matrices,
        inverse_bind=inverse_bind,
        world_positions=world_positions,
        world_rotations=world_rotations,
        lengths=lengths,
        local_transforms=local_transforms,
        node_order=node_order,
    )
