"""Skin invariants proven on the built mesh (FR-035, ADR 261114-3)."""

from __future__ import annotations

import numpy as np

from beastforge.geometry.mesh import Mesh
from beastforge.model.findings import ValidationFinding
from beastforge.model.parts import ResolvedPart
from beastforge.model.recipe import Recipe
from beastforge.rig.skeleton import BuiltSkeleton
from beastforge.validation.common import finding

WEIGHT_TOLERANCE = 1e-5


def _first_vertex_with(mesh: Mesh, predicate) -> int | None:
    for index in range(mesh.vertex_count):
        if predicate(index):
            return index
    return None


def check_skin(
    recipe: Recipe,
    mesh: Mesh,
    skeleton: BuiltSkeleton,
    *,
    recipe_label: str,
    parts: list[ResolvedPart] | None = None,
) -> list[ValidationFinding]:
    """Check weight sums, influence counts, rigid bindings, and bind pose."""
    findings: list[ValidationFinding] = []
    if mesh.vertex_count == 0 or mesh.triangle_count == 0:
        findings.append(
            finding(
                "surface-empty",
                "The built mesh has no vertices or triangles.",
                recipe=recipe_label,
                path="surfaces",
                expected="at least 3 vertices and 1 triangle",
                actual={"vertices": mesh.vertex_count, "triangles": mesh.triangle_count},
                remedy="Increase rings/segments or add a surface.",
            )
        )
        return findings

    sums = mesh.weights.sum(axis=1)
    positive_counts = (mesh.weights > 0.0).sum(axis=1)
    bad_sum = np.where(np.abs(sums - 1.0) > WEIGHT_TOLERANCE)[0]
    if bad_sum.size:
        index = int(bad_sum[0])
        findings.append(
            finding(
                "skin-weight-sum",
                f"{bad_sum.size} vertices have weights that do not sum to 1 ± {WEIGHT_TOLERANCE}.",
                recipe=recipe_label,
                path=f"mesh.vertices[{index}]",
                expected="sum = 1.0",
                actual=float(sums[index]),
                remedy="Fix construction-bound weights so every vertex normalizes to one.",
            )
        )
    too_many = np.where(positive_counts > 4)[0]
    if too_many.size:
        index = int(too_many[0])
        findings.append(
            finding(
                "skin-too-many-influences",
                f"{too_many.size} vertices have more than four influences.",
                recipe=recipe_label,
                path=f"mesh.vertices[{index}]",
                expected="<= 4 influences (v1 construction uses 1-2)",
                actual=int(positive_counts[index]),
                remedy="Limit weights to two construction-bound bones.",
            )
        )
    zero = np.where(positive_counts == 0)[0]
    if zero.size:
        index = int(zero[0])
        findings.append(
            finding(
                "skin-zero-weight",
                f"{zero.size} vertices have zero total weight.",
                recipe=recipe_label,
                path=f"mesh.vertices[{index}]",
                expected="at least one non-zero weight",
                actual=0.0,
                remedy="Bind every vertex to at least one bone.",
            )
        )

    # Rigid parts bind to exactly one bone with weight 1.0.
    surfaces = [*recipe.surfaces, *(part.surface for part in parts or [])]
    for surface_range, surface in zip(mesh.surfaces, surfaces, strict=False):
        if surface.kind != "rigid-part":
            continue
        start = surface_range.vertex_offset
        end = start + surface_range.vertex_count
        block_weights = mesh.weights[start:end]
        block_joints = mesh.joints[start:end]
        expected_joint = skeleton.index(surface.rigid_bone or surface.bones[0])
        counts = (block_weights > 0.0).sum(axis=1)
        if (
            not np.all(counts == 1)
            or not np.allclose(block_weights[:, 0], 1.0, atol=WEIGHT_TOLERANCE)
            or not np.all(block_joints[:, 0] == expected_joint)
        ):
            findings.append(
                finding(
                    "skin-rigid-multi-influence",
                    f"Rigid surface {surface.name!r} is not bound with weight 1.0 to one bone.",
                    recipe=recipe_label,
                    path=f"surfaces[{surface.name}]",
                    expected=f"joint {expected_joint} with weight 1.0",
                    actual="multiple influences",
                    remedy="Bind rigid parts to exactly one bone.",
                )
            )

    # Bind pose equals rest pose: inverse-bind * rest-world is the identity.
    identity = np.eye(4, dtype=np.float64)
    for name in skeleton.names:
        product = skeleton.inverse_bind[name] @ skeleton.world_matrices[name]
        if not np.allclose(product, identity, atol=1e-5):
            findings.append(
                finding(
                    "skin-bind-pose-mismatch",
                    f"Bone {name!r} bind pose differs from its rest pose.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{name}]",
                    expected="inverse(world_rest) * world_rest = I",
                    actual=float(np.max(np.abs(product - identity))),
                    remedy="Compute inverse bind matrices from the rest skeleton only.",
                )
            )
            break
    return findings
