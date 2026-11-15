"""Gameplay hook checks: volumes, phases, sockets (FR-025/030/036)."""

from __future__ import annotations

import math

from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Recipe
from beastforge.validation.common import check_identifier, duplicates, finding

_ROLES = {"hit", "weak-point", "collision"}


def check_hooks(recipe: Recipe, *, recipe_label: str) -> list[ValidationFinding]:
    """Check required hit volume, boss phases, sockets, and referential integrity."""
    findings: list[ValidationFinding] = []
    bone_names = {bone.name for bone in recipe.skeleton.bones}

    if not any(volume.role == "hit" for volume in recipe.volumes):
        findings.append(
            finding(
                "volume-missing-hit",
                "Every creature must declare at least one hit volume.",
                recipe=recipe_label,
                path="volumes",
                expected=">= 1 volume with role: hit",
                actual=[volume.role for volume in recipe.volumes],
                remedy="Add a volume named body-hull with role: hit and box extents.",
            )
        )
    for duplicate in duplicates([volume.name for volume in recipe.volumes]):
        findings.append(
            finding(
                "volume-duplicate",
                f"Volume name {duplicate!r} is declared more than once.",
                recipe=recipe_label,
                path=f"volumes[{duplicate}]",
                expected="unique volume names",
                actual=duplicate,
                remedy="Rename one of the duplicate volumes.",
            )
        )
    for volume in recipe.volumes:
        path = f"volumes[{volume.name}]"
        identifier = check_identifier(volume.name, recipe=recipe_label, path=path)
        if identifier is not None:
            findings.append(identifier)
        if volume.role not in _ROLES:
            findings.append(
                finding(
                    "volume-role-invalid",
                    f"Volume {volume.name!r} has unknown role {volume.role!r}.",
                    recipe=recipe_label,
                    path=f"{path}.role",
                    expected="one of: " + ", ".join(sorted(_ROLES)),
                    actual=volume.role,
                    remedy="Use hit, weak-point, or collision.",
                )
            )
        if len(volume.extents) != 3 or any(float(value) <= 0.0 for value in volume.extents):
            findings.append(
                finding(
                    "recipe-param-range",
                    f"Volume {volume.name!r} extents must be three positive half-extents.",
                    recipe=recipe_label,
                    path=f"{path}.extents",
                    expected="three values > 0",
                    actual=volume.extents,
                    remedy="Use half-extents such as [0.5, 0.45, 1.2].",
                )
            )
        if any(not math.isfinite(float(value)) for value in [*volume.center, *volume.extents]):
            findings.append(
                finding(
                    "recipe-param-range",
                    f"Volume {volume.name!r} has a non-finite value.",
                    recipe=recipe_label,
                    path=path,
                    expected="finite numbers",
                    actual=[*volume.center, *volume.extents],
                    remedy="Replace NaN/Inf with finite numbers.",
                )
            )
        if volume.bone is not None and volume.bone not in bone_names:
            findings.append(
                finding(
                    "manifest-dangling-reference",
                    f"Volume {volume.name!r} follows missing bone {volume.bone!r}.",
                    recipe=recipe_label,
                    path=f"{path}.bone",
                    expected="an existing bone",
                    actual=volume.bone,
                    remedy="Remove the follow bone or correct the name.",
                )
            )

    if recipe.meta.category == "boss" and not recipe.phases:
        findings.append(
            finding(
                "phase-missing-for-boss",
                "Boss creatures must declare at least one phase threshold.",
                recipe=recipe_label,
                path="phases",
                expected=">= 1 phase",
                actual=[],
                remedy="Add phases such as enraged at 0.66 and desperate at 0.33.",
            )
        )
    for duplicate in duplicates([phase.name for phase in recipe.phases]):
        findings.append(
            finding(
                "phase-duplicate",
                f"Phase name {duplicate!r} is declared more than once.",
                recipe=recipe_label,
                path=f"phases[{duplicate}]",
                expected="unique phase names",
                actual=duplicate,
                remedy="Rename one of the duplicate phases.",
            )
        )
    for phase in recipe.phases:
        path = f"phases[{phase.name}]"
        identifier = check_identifier(phase.name, recipe=recipe_label, path=path)
        if identifier is not None:
            findings.append(identifier)
        if not (0.0 < phase.threshold < 1.0) or not math.isfinite(float(phase.threshold)):
            findings.append(
                finding(
                    "phase-threshold-range",
                    f"Phase {phase.name!r} threshold must be strictly inside (0, 1).",
                    recipe=recipe_label,
                    path=f"{path}.threshold",
                    expected="0 < threshold < 1",
                    actual=phase.threshold,
                    remedy="Use a fraction such as 0.66.",
                )
            )

    for duplicate in duplicates([socket.name for socket in recipe.sockets]):
        findings.append(
            finding(
                "socket-duplicate",
                f"Socket name {duplicate!r} is declared more than once.",
                recipe=recipe_label,
                path=f"sockets[{duplicate}]",
                expected="unique socket names",
                actual=duplicate,
                remedy="Rename one of the duplicate sockets.",
            )
        )
    for socket in recipe.sockets:
        path = f"sockets[{socket.name}]"
        identifier = check_identifier(socket.name, recipe=recipe_label, path=path)
        if identifier is not None:
            findings.append(identifier)
        if socket.bone not in bone_names:
            findings.append(
                finding(
                    "socket-target-missing",
                    f"Socket {socket.name!r} targets missing bone {socket.bone!r}.",
                    recipe=recipe_label,
                    path=f"{path}.bone",
                    expected="an existing bone",
                    actual=socket.bone,
                    remedy="Correct the target or add the bone.",
                )
            )
        if len(socket.offset) != 3 or any(
            not math.isfinite(float(value)) for value in socket.offset
        ):
            findings.append(
                finding(
                    "recipe-param-range",
                    f"Socket {socket.name!r} offset must be three finite metres.",
                    recipe=recipe_label,
                    path=f"{path}.offset",
                    expected="[x, y, z] finite",
                    actual=socket.offset,
                    remedy="Use a finite bone-local offset.",
                )
            )
    return findings
