"""Surface declaration checks (FR-015/016/019/020)."""

from __future__ import annotations

from beastforge.model.findings import ValidationFinding
from beastforge.model.parts import ResolvedPart
from beastforge.model.recipe import RadiusProfile, Recipe, Surface
from beastforge.validation.common import check_identifier, duplicates, finding

_KINDS = {"limb-tube", "torso-shell", "rigid-part", "swept-solid", "shell"}


def check_surfaces(
    recipe: Recipe,
    *,
    recipe_label: str,
    parts: list[ResolvedPart] | None = None,
) -> list[ValidationFinding]:
    """Check modes, bone references, rigid bindings, and construction limits."""
    findings: list[ValidationFinding] = []
    bone_names = {bone.name for bone in recipe.skeleton.bones}
    by_name = {bone.name: bone for bone in recipe.skeleton.bones}
    seen: set[str] = set()
    entries: list[tuple[str, Surface]] = [
        (f"surfaces[{surface.name}]", surface) for surface in recipe.surfaces
    ]
    entries.extend((f"parts[{part.name}]", part.surface) for part in parts or [])
    for path, surface in entries:
        if surface.name in seen:
            findings.append(
                finding(
                    "duplicate-name",
                    f"Surface name {surface.name!r} is declared more than once.",
                    recipe=recipe_label,
                    path=path,
                    expected="unique surface names",
                    actual=surface.name,
                    remedy="Rename one of the duplicate surfaces.",
                )
            )
        seen.add(surface.name)
        identifier = check_identifier(surface.name, recipe=recipe_label, path=path)
        if identifier is not None:
            findings.append(identifier)

        if surface.mode != "sweep":
            findings.append(
                finding(
                    "surface-unsupported-mode",
                    f"Surface {surface.name!r} requests unsupported mode {surface.mode!r}.",
                    recipe=recipe_label,
                    path=f"{path}.mode",
                    expected="sweep (the only supported mode in v1)",
                    actual=surface.mode,
                    remedy="Change mode to sweep; metaball is reserved for a later version.",
                )
            )
        if surface.kind not in _KINDS:
            findings.append(
                finding(
                    "surface-unsupported-mode",
                    f"Surface {surface.name!r} has unknown kind {surface.kind!r}.",
                    recipe=recipe_label,
                    path=f"{path}.kind",
                    expected="one of: " + ", ".join(sorted(_KINDS)),
                    actual=surface.kind,
                    remedy=(
                        "Use swept-solid, shell, rigid-part, or an accepted alias "
                        "(limb-tube, torso-shell)."
                    ),
                )
            )
        if not surface.bones:
            findings.append(
                finding(
                    "surface-empty",
                    f"Surface {surface.name!r} binds to no bones.",
                    recipe=recipe_label,
                    path=f"{path}.bones",
                    expected="at least one bone",
                    actual=[],
                    remedy="List the ordered bones the surface is built from.",
                )
            )
        for index, bone in enumerate(surface.bones):
            if bone not in bone_names:
                findings.append(
                    finding(
                        "surface-bone-missing",
                        f"Surface {surface.name!r} references missing bone {bone!r}.",
                        recipe=recipe_label,
                        path=f"{path}.bones[{index}]",
                        expected="an existing bone name",
                        actual=bone,
                        remedy="Add the bone to the skeleton or correct the name.",
                    )
                )
        for index in range(1, len(surface.bones)):
            previous = surface.bones[index - 1]
            current = surface.bones[index]
            if previous in by_name and current in by_name and by_name[current].parent != previous:
                findings.append(
                    finding(
                        "chain-invalid",
                        f"Surface {surface.name!r} bone list is not contiguous at {current!r}.",
                        recipe=recipe_label,
                        path=f"{path}.bones[{index}]",
                        expected=f"parent {previous!r}",
                        actual=by_name[current].parent,
                        remedy="Order surface bones parent-to-child without gaps.",
                    )
                )
        if surface.kind == "rigid-part":
            rigid = surface.rigid_bone
            if rigid is None or rigid not in bone_names:
                findings.append(
                    finding(
                        "surface-bone-missing",
                        f"Rigid surface {surface.name!r} has no valid rigid_bone.",
                        recipe=recipe_label,
                        path=f"{path}.rigid_bone",
                        expected="exactly one existing bone",
                        actual=rigid,
                        remedy="Set rigid_bone to the single bone the part follows.",
                    )
                )
            elif len(surface.bones) != 1 or surface.bones[0] != rigid:
                findings.append(
                    finding(
                        "skin-rigid-multi-influence",
                        f"Rigid surface {surface.name!r} must bind to exactly one bone.",
                        recipe=recipe_label,
                        path=path,
                        expected=f"bones: [{rigid}]",
                        actual=surface.bones,
                        remedy="List only the rigid_bone in bones[].",
                    )
                )
        if isinstance(surface.radius, RadiusProfile):
            if surface.radius.start <= 0.0 or surface.radius.end <= 0.0:
                findings.append(
                    finding(
                        "surface-empty",
                        f"Surface {surface.name!r} has a non-positive radius.",
                        recipe=recipe_label,
                        path=f"{path}.radius",
                        expected="start and end > 0",
                        actual={"start": surface.radius.start, "end": surface.radius.end},
                        remedy="Use positive radii.",
                    )
                )
        elif any(float(value) <= 0.0 for value in surface.radius):
            findings.append(
                finding(
                    "surface-empty",
                    f"Surface {surface.name!r} has a non-positive radius entry.",
                    recipe=recipe_label,
                    path=f"{path}.radius",
                    expected="all radii > 0",
                    actual=list(surface.radius),
                    remedy="Use positive radii.",
                )
            )
        if surface.rings < 2:
            findings.append(
                finding(
                    "surface-empty",
                    f"Surface {surface.name!r} needs at least 2 rings.",
                    recipe=recipe_label,
                    path=f"{path}.rings",
                    expected=">= 2",
                    actual=surface.rings,
                    remedy="Raise rings to at least 2.",
                )
            )
        if surface.segments < 3:
            findings.append(
                finding(
                    "surface-empty",
                    f"Surface {surface.name!r} needs at least 3 radial segments.",
                    recipe=recipe_label,
                    path=f"{path}.segments",
                    expected=">= 3",
                    actual=surface.segments,
                    remedy="Raise segments to at least 3.",
                )
            )
        if not (0.0 < surface.blend <= 0.35):
            findings.append(
                finding(
                    "recipe-param-range",
                    f"Surface {surface.name!r} blend must be in (0, 0.35].",
                    recipe=recipe_label,
                    path=f"{path}.blend",
                    expected="0 < blend <= 0.35",
                    actual=surface.blend,
                    remedy="Use a blend fraction such as 0.25.",
                )
            )
    for duplicate in duplicates([surface.name for _path, surface in entries]):
        if duplicate:  # already reported per-surface; this keeps ordering stable
            continue
    return findings
