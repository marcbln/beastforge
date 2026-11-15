"""Skeleton structure checks (FR-035, data-model §5)."""

from __future__ import annotations

import math

import numpy as np

from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Recipe
from beastforge.rig.skeleton import rotation_determinant
from beastforge.validation.common import check_identifier, duplicates, finding


def check_skeleton(recipe: Recipe, *, recipe_label: str) -> list[ValidationFinding]:
    """Return every structural skeleton finding in declaration order."""
    findings: list[ValidationFinding] = []
    skeleton = recipe.skeleton
    bones = skeleton.bones
    names = [bone.name for bone in bones]
    by_name = {bone.name: bone for bone in bones}
    chain_bones = {name for chain in skeleton.chains for name in chain.bones}

    for duplicate in duplicates(names):
        findings.append(
            finding(
                "skeleton-duplicate-bone",
                f"Bone name {duplicate!r} is declared more than once.",
                recipe=recipe_label,
                path=f"skeleton.bones[{duplicate}]",
                expected="unique bone names",
                actual=duplicate,
                remedy="Rename one of the duplicate bones.",
            )
        )
    for bone in bones:
        result = check_identifier(
            bone.name, recipe=recipe_label, path=f"skeleton.bones[{bone.name}]"
        )
        if result is not None:
            findings.append(result)

    roots = [bone.name for bone in bones if bone.parent is None]
    if not roots:
        findings.append(
            finding(
                "skeleton-root-missing",
                "The skeleton has no parentless root bone.",
                recipe=recipe_label,
                path="skeleton.root",
                expected="exactly one bone with parent: null",
                actual="none",
                remedy="Set exactly one bone's parent to null and name it in skeleton.root.",
            )
        )
    elif len(roots) > 1:
        findings.append(
            finding(
                "skeleton-root-multiple",
                f"The skeleton has {len(roots)} parentless bones: {', '.join(sorted(roots))}.",
                recipe=recipe_label,
                path="skeleton.root",
                expected="exactly one bone with parent: null",
                actual=sorted(roots),
                remedy="Give every non-root bone a parent.",
            )
        )
    if skeleton.root not in by_name:
        findings.append(
            finding(
                "skeleton-root-missing",
                f"skeleton.root names missing bone {skeleton.root!r}.",
                recipe=recipe_label,
                path="skeleton.root",
                expected="an existing bone name",
                actual=skeleton.root,
                remedy="Set skeleton.root to the name of the parentless bone.",
            )
        )
    elif len(roots) == 1 and roots[0] != skeleton.root:
        findings.append(
            finding(
                "skeleton-root-missing",
                f"skeleton.root is {skeleton.root!r} but the parentless bone is {roots[0]!r}.",
                recipe=recipe_label,
                path="skeleton.root",
                expected="the parentless bone",
                actual=skeleton.root,
                remedy="Make skeleton.root match the parentless bone name.",
            )
        )

    for bone in bones:
        if bone.parent is not None and bone.parent not in by_name:
            findings.append(
                finding(
                    "skeleton-parent-missing",
                    f"Bone {bone.name!r} names missing parent {bone.parent!r}.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{bone.name}].parent",
                    expected="an existing bone name",
                    actual=bone.parent,
                    remedy="Add the parent bone or correct the parent name.",
                )
            )

    # Cycle detection: follow each parent chain and record the first repeat.
    cycle_reported = False
    for bone in bones:
        seen: list[str] = []
        current: str | None = bone.name
        while current is not None and current in by_name:
            if current in seen:
                if not cycle_reported:
                    cycle_reported = True
                    cycle = seen[seen.index(current) :] + [current]
                    findings.append(
                        finding(
                            "skeleton-cycle",
                            f"Bone hierarchy contains a cycle: {' -> '.join(cycle)}.",
                            recipe=recipe_label,
                            path=f"skeleton.bones[{current}].parent",
                            expected="a tree rooted at skeleton.root",
                            actual=cycle,
                            remedy="Break the parent loop so every bone reaches the root.",
                        )
                    )
                break
            seen.append(current)
            current = by_name[current].parent

    # Reachability from the root.
    children: dict[str, list[str]] = {name: [] for name in names}
    for bone in bones:
        if bone.parent in children:
            children[bone.parent].append(bone.name)
    reachable: set[str] = set()
    if skeleton.root in by_name:
        stack = [skeleton.root]
        while stack:
            name = stack.pop()
            if name in reachable or name not in by_name:
                continue
            reachable.add(name)
            stack.extend(children.get(name, []))
    for name in names:
        if skeleton.root in by_name and name not in reachable:
            findings.append(
                finding(
                    "skeleton-unreachable-bone",
                    f"Bone {name!r} is not reachable from root {skeleton.root!r}.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{name}]",
                    expected="every bone reachable from the root",
                    actual="unreachable",
                    remedy="Connect it to the root through parent links.",
                )
            )

    for bone in bones:
        rest = bone.rest
        values = [*rest.translation, *rest.rotation, *rest.scale]
        if any(not math.isfinite(float(value)) for value in values):
            findings.append(
                finding(
                    "skeleton-degenerate-transform",
                    f"Bone {bone.name!r} has a non-finite rest transform.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{bone.name}].rest",
                    expected="finite numbers",
                    actual=values,
                    remedy="Replace NaN/Inf with finite values.",
                )
            )
            continue
        quaternion_norm = float(np.linalg.norm(np.asarray(rest.rotation, dtype=np.float64)))
        if abs(quaternion_norm - 1.0) > 1e-6:
            findings.append(
                finding(
                    "skeleton-degenerate-transform",
                    f"Bone {bone.name!r} rotation is not unit length.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{bone.name}].rest.rotation",
                    expected="|q| = 1 within 1e-6",
                    actual=quaternion_norm,
                    remedy="Normalize the quaternion [x, y, z, w].",
                )
            )
        if any(float(value) == 0.0 for value in rest.scale):
            findings.append(
                finding(
                    "skeleton-degenerate-transform",
                    f"Bone {bone.name!r} has a zero scale component.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{bone.name}].rest.scale",
                    expected="non-zero scale",
                    actual=rest.scale,
                    remedy="Use positive scale values (typically [1, 1, 1]).",
                )
            )
        elif (
            any(float(value) < 0.0 for value in rest.scale)
            or rotation_determinant(rest.rotation, rest.scale) <= 0.0
        ):
            findings.append(
                finding(
                    "skeleton-inverted-transform",
                    f"Bone {bone.name!r} transform has a non-positive determinant.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{bone.name}].rest",
                    expected="a positive determinant",
                    actual=rotation_determinant(rest.rotation, rest.scale),
                    remedy="Remove mirrored/negative scale.",
                )
            )
        length = float(np.linalg.norm(np.asarray(rest.translation, dtype=np.float64)))
        if bone.name in chain_bones and length <= 1e-9:
            findings.append(
                finding(
                    "skeleton-zero-length-bone",
                    f"Chain bone {bone.name!r} has zero rest length.",
                    recipe=recipe_label,
                    path=f"skeleton.bones[{bone.name}].rest.translation",
                    expected="a non-zero translation for a limb bone",
                    actual=rest.translation,
                    remedy="Give the bone a non-zero rest translation.",
                )
            )

    for duplicate in duplicates([chain.name for chain in skeleton.chains]):
        findings.append(
            finding(
                "chain-duplicate",
                f"Chain name {duplicate!r} is declared more than once.",
                recipe=recipe_label,
                path=f"skeleton.chains[{duplicate}]",
                expected="unique chain names",
                actual=duplicate,
                remedy="Rename one of the duplicate chains.",
            )
        )
    for chain in skeleton.chains:
        if not chain.bones:
            findings.append(
                finding(
                    "chain-invalid",
                    f"Chain {chain.name!r} has no bones.",
                    recipe=recipe_label,
                    path=f"skeleton.chains[{chain.name}]",
                    expected="an ordered, non-empty bone list",
                    actual=[],
                    remedy="List at least one bone.",
                )
            )
            continue
        for index, bone_name in enumerate(chain.bones):
            if bone_name not in by_name:
                findings.append(
                    finding(
                        "chain-invalid",
                        f"Chain {chain.name!r} references missing bone {bone_name!r}.",
                        recipe=recipe_label,
                        path=f"skeleton.chains[{chain.name}].bones[{index}]",
                        expected="an existing bone name",
                        actual=bone_name,
                        remedy="Add the bone or correct the name.",
                    )
                )
                continue
            if index > 0 and by_name[bone_name].parent != chain.bones[index - 1]:
                findings.append(
                    finding(
                        "chain-invalid",
                        f"Chain {chain.name!r} is not contiguous at {bone_name!r}.",
                        recipe=recipe_label,
                        path=f"skeleton.chains[{chain.name}].bones[{index}]",
                        expected=f"parent {chain.bones[index - 1]!r}",
                        actual=by_name[bone_name].parent,
                        remedy="Order chain bones parent-to-child without gaps.",
                    )
                )
    return findings
