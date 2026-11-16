"""Pure recipe-part resolution: bind, overrides, controls, and automatic motion.

No filesystem access happens here; the caller supplies a :class:`PresetRegistry`.
Given the same recipe, pinned preset documents, and skeleton, resolution returns
the same ``ResolvedPart`` list and findings in the same order.
"""

from __future__ import annotations

import difflib
import math
from dataclasses import dataclass, field

import numpy as np

from beastforge.model.findings import ValidationFinding
from beastforge.model.parts import (
    AutoBehaviour,
    BreatheAuto,
    ControlChannel,
    PartInstance,
    PartPreset,
    PresetControl,
    ResolvedAuto,
    ResolvedPart,
    RotateAuto,
)
from beastforge.model.recipe import Recipe, Surface
from beastforge.parts.overrides import apply_overrides
from beastforge.parts.registry import PresetRegistry
from beastforge.validation.common import finding

AXIS_TOLERANCE = 1e-6


@dataclass
class PartsResolution:
    """Resolved parts plus every finding produced while resolving them."""

    parts: list[ResolvedPart] = field(default_factory=list)
    findings: list[ValidationFinding] = field(default_factory=list)


def _slots_in(value: str | None) -> set[str]:
    if value and value.startswith("@"):
        return {value[1:]}
    return set()


def required_slots(preset: PartPreset, instance: PartInstance) -> set[str]:
    """Every ``@slot`` used by the preset surface, controls, or auto behaviours."""
    slots: set[str] = set()
    slots |= {bone[1:] for bone in preset.surface.bones if bone.startswith("@")}
    slots |= _slots_in(preset.surface.rigid_bone)
    for control in [*preset.controls, *instance.controls]:
        slots |= _slots_in(control.joint)
    for behaviour in [*preset.auto, *instance.auto]:
        slots |= _slots_in(behaviour.joint)
    return slots


def _substitute_joint(joint: str, bind: dict[str, str]) -> str:
    if joint.startswith("@"):
        return bind.get(joint[1:], joint)
    return joint


def _axis_is_unit(axis: list[float]) -> bool:
    if len(axis) != 3:
        return False
    values = np.asarray(axis, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        return False
    length = float(np.linalg.norm(values))
    return length > 0.0 and abs(length - 1.0) <= AXIS_TOLERANCE


def _merge_by_name(preset_items, instance_items):
    """Merge preset and instance declarations by name; the instance wins."""
    instance_by_name = {item.name: item for item in instance_items}
    merged = []
    seen: set[str] = set()
    for item in preset_items:
        if item.name in seen:
            continue
        seen.add(item.name)
        merged.append(instance_by_name.get(item.name, item))
    for item in instance_items:
        if item.name in seen:
            continue
        seen.add(item.name)
        merged.append(item)
    return merged


def _duplicate_names(items) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item.name in seen and item.name not in duplicates:
            duplicates.append(item.name)
        seen.add(item.name)
    return duplicates


def _resolve_control(
    control: PresetControl,
    *,
    part_name: str,
    bind: dict[str, str],
    bone_names: set[str],
    recipe_label: str,
) -> tuple[ControlChannel | None, list[ValidationFinding]]:
    findings: list[ValidationFinding] = []
    path = f"parts[{part_name}].controls[{control.name}]"
    joint = _substitute_joint(control.joint, bind)
    if joint not in bone_names:
        findings.append(
            finding(
                "part-control-joint-missing",
                f"Control {control.name!r} on part {part_name!r} targets missing bone {joint!r}.",
                recipe=recipe_label,
                path=f"{path}.joint",
                expected="an existing bone after @slot binding",
                actual=joint,
                remedy="Bind the slot to an existing bone or correct the joint name.",
            )
        )
    if not _axis_is_unit(control.axis):
        findings.append(
            finding(
                "part-control-axis-invalid",
                f"Control {control.name!r} on part {part_name!r} has a non-unit axis.",
                recipe=recipe_label,
                path=f"{path}.axis",
                expected="three finite numbers forming a unit vector",
                actual=control.axis,
                remedy="Normalize the axis; it is rejected rather than silently fixed.",
            )
        )
    expected_units = "deg" if control.mode == "rotation" else "m"
    if control.units != expected_units:
        findings.append(
            finding(
                "part-control-units-mismatch",
                f"Control {control.name!r} uses units {control.units!r} for a "
                f"{control.mode} channel.",
                recipe=recipe_label,
                path=f"{path}.units",
                expected=expected_units,
                actual=control.units,
                remedy="Use deg for rotation and m for translation.",
            )
        )
    unbounded = control.unbounded
    if unbounded is None:
        unbounded = control.range is None
    if unbounded and control.range is not None:
        findings.append(
            finding(
                "part-control-range-invalid",
                f"Unbounded control {control.name!r} on part {part_name!r} declares a range.",
                recipe=recipe_label,
                path=f"{path}.range",
                expected="no range when unbounded",
                actual=control.range.model_dump(),
                remedy="Remove the range or set unbounded: false.",
            )
        )
    if not unbounded and control.range is None:
        findings.append(
            finding(
                "part-control-range-invalid",
                f"Bounded control {control.name!r} on part {part_name!r} has no range.",
                recipe=recipe_label,
                path=f"{path}.range",
                expected="a {min, max} range",
                actual=None,
                remedy="Add a finite range or set unbounded: true.",
            )
        )
    if control.range is not None:
        if not (math.isfinite(control.range.min) and math.isfinite(control.range.max)):
            findings.append(
                finding(
                    "part-control-range-invalid",
                    f"Control {control.name!r} on part {part_name!r} has a non-finite range.",
                    recipe=recipe_label,
                    path=f"{path}.range",
                    expected="finite min and max",
                    actual=control.range.model_dump(),
                    remedy="Use finite limits.",
                )
            )
        elif control.range.min > control.range.max:
            findings.append(
                finding(
                    "part-control-range-invalid",
                    f"Control {control.name!r} on part {part_name!r} has min above max.",
                    recipe=recipe_label,
                    path=f"{path}.range",
                    expected="min <= max",
                    actual=control.range.model_dump(),
                    remedy="Swap or correct the limits.",
                )
            )
        elif not (control.range.min <= control.default <= control.range.max):
            findings.append(
                finding(
                    "part-control-default-out-of-range",
                    f"Control {control.name!r} on part {part_name!r} defaults outside its range.",
                    recipe=recipe_label,
                    path=f"{path}.default",
                    expected=f"{control.range.min} <= default <= {control.range.max}",
                    actual=control.default,
                    remedy="Move the default inside the range.",
                )
            )
    if isinstance(control.mode, str) and control.mode not in {"rotation", "translation"}:
        findings.append(
            finding(
                "part-control-mode-invalid",
                f"Control {control.name!r} on part {part_name!r} has unknown mode.",
                recipe=recipe_label,
                path=f"{path}.mode",
                expected="rotation or translation",
                actual=control.mode,
                remedy="Use a supported mode.",
            )
        )
    if not math.isfinite(float(control.default)):
        findings.append(
            finding(
                "part-control-default-out-of-range",
                f"Control {control.name!r} on part {part_name!r} has a non-finite default.",
                recipe=recipe_label,
                path=f"{path}.default",
                expected="a finite number",
                actual=control.default,
                remedy="Use a finite default.",
            )
        )
    if findings:
        return None, findings
    return (
        ControlChannel(
            address=f"{part_name}/{control.name}",
            name=control.name,
            joint=joint,
            axis=[float(value) for value in control.axis],
            mode=control.mode,
            unbounded=bool(unbounded),
            range=control.range,
            default=float(control.default),
            units=control.units,
        ),
        findings,
    )


def _resolve_auto(
    behaviour: AutoBehaviour,
    *,
    part_name: str,
    bind: dict[str, str],
    bone_names: set[str],
    recipe_label: str,
) -> tuple[ResolvedAuto | None, list[ValidationFinding]]:
    findings: list[ValidationFinding] = []
    path = f"parts[{part_name}].auto[{behaviour.name}]"
    joint = _substitute_joint(behaviour.joint, bind)
    if joint not in bone_names:
        findings.append(
            finding(
                "part-auto-joint-missing",
                f"Automatic behaviour {behaviour.name!r} on part {part_name!r} targets "
                f"missing bone {joint!r}.",
                recipe=recipe_label,
                path=f"{path}.joint",
                expected="an existing bone after @slot binding",
                actual=joint,
                remedy="Bind the slot to an existing bone or correct the joint name.",
            )
        )
    if not isinstance(behaviour, BreatheAuto) and not _axis_is_unit(behaviour.axis):
        findings.append(
            finding(
                "part-auto-axis-invalid",
                f"Automatic behaviour {behaviour.name!r} on part {part_name!r} has a "
                "non-unit axis.",
                recipe=recipe_label,
                path=f"{path}.axis",
                expected="three finite numbers forming a unit vector",
                actual=behaviour.axis,
                remedy="Normalize the axis; it is rejected rather than silently fixed.",
            )
        )
    if isinstance(behaviour, RotateAuto):
        if not math.isfinite(behaviour.rate) or behaviour.rate == 0.0:
            findings.append(
                finding(
                    "part-auto-rate-invalid",
                    f"Automatic rotation {behaviour.name!r} on part {part_name!r} has a "
                    "zero or non-finite rate.",
                    recipe=recipe_label,
                    path=f"{path}.rate",
                    expected="a finite non-zero degrees/second rate",
                    actual=behaviour.rate,
                    remedy="Use a non-zero rate.",
                )
            )
    else:
        if not math.isfinite(behaviour.amplitude) or behaviour.amplitude <= 0.0:
            findings.append(
                finding(
                    "part-auto-amplitude-invalid",
                    f"Automatic behaviour {behaviour.name!r} on part {part_name!r} has a "
                    "non-positive amplitude.",
                    recipe=recipe_label,
                    path=f"{path}.amplitude",
                    expected="a finite amplitude > 0",
                    actual=behaviour.amplitude,
                    remedy="Use a positive amplitude.",
                )
            )
        if not math.isfinite(behaviour.period) or behaviour.period <= 0.0:
            findings.append(
                finding(
                    "part-auto-period-invalid",
                    f"Automatic behaviour {behaviour.name!r} on part {part_name!r} has a "
                    "non-positive period.",
                    recipe=recipe_label,
                    path=f"{path}.period",
                    expected="a finite period > 0 seconds",
                    actual=behaviour.period,
                    remedy="Use a positive period.",
                )
            )
        if not math.isfinite(float(behaviour.phase)):
            findings.append(
                finding(
                    "part-auto-period-invalid",
                    f"Automatic behaviour {behaviour.name!r} on part {part_name!r} has a "
                    "non-finite phase.",
                    recipe=recipe_label,
                    path=f"{path}.phase",
                    expected="finite degrees",
                    actual=behaviour.phase,
                    remedy="Use a finite phase.",
                )
            )
    if findings:
        return None, findings
    resolved = behaviour.model_copy(update={"joint": joint})
    return resolved, findings


def _preset_surface(
    preset: PartPreset,
    instance: PartInstance,
    bind: dict[str, str],
    *,
    recipe_label: str,
) -> tuple[Surface | None, list[ValidationFinding]]:
    template, findings = apply_overrides(
        preset.surface,
        instance.overrides,
        preset.params,
        part_name=instance.name,
        recipe_label=recipe_label,
    )
    try:
        surface = Surface(
            name=instance.name,
            mode=template.mode,
            kind=template.kind,
            bones=[_substitute_joint(bone, bind) for bone in template.bones],
            rigid_bone=_substitute_joint(template.rigid_bone, bind)
            if template.rigid_bone
            else None,
            rings=template.rings,
            segments=template.segments,
            radius=template.radius,
            blend=template.blend,
            modifiers=template.modifiers,
            material=instance.material if instance.material is not None else template.material,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a stable finding
        findings.append(
            finding(
                "preset-file-invalid",
                f"Preset {preset.name!r} cannot produce surface {instance.name!r}: {exc}",
                recipe=recipe_label,
                path=f"parts[{instance.name}]",
                expected="a valid Surface template",
                actual=str(exc),
                remedy="Fix the preset surface or the overrides.",
            )
        )
        return None, findings
    return surface, findings


def resolve_parts(
    recipe: Recipe,
    registry: PresetRegistry,
    *,
    recipe_label: str = "",
) -> PartsResolution:
    """Resolve every ``recipe.parts`` entry against the registry."""
    resolution = PartsResolution()
    bone_names = {bone.name for bone in recipe.skeleton.bones}
    surface_names = {surface.name for surface in recipe.surfaces}
    all_names = list(surface_names)
    addresses: set[str] = set()

    for instance in recipe.parts:
        if instance.name in all_names:
            resolution.findings.append(
                finding(
                    "part-duplicate-name",
                    f"Part name {instance.name!r} collides with another geometry entry.",
                    recipe=recipe_label,
                    path=f"parts[{instance.name}]",
                    expected="unique names across surfaces and parts",
                    actual=instance.name,
                    remedy="Rename the part or the surface.",
                )
            )
        all_names.append(instance.name)

    for instance in recipe.parts:
        preset = registry.get(instance.preset, instance.preset_version)
        if preset is None:
            if instance.preset in registry.names():
                available = registry.versions(instance.preset)
                resolution.findings.append(
                    finding(
                        "part-preset-version-missing",
                        f"Preset {instance.preset!r} has no version "
                        f"{instance.preset_version!r}.",
                        recipe=recipe_label,
                        path=f"parts[{instance.name}].preset_version",
                        expected=available,
                        actual=instance.preset_version,
                        remedy="Pin an available version or add the version file.",
                    )
                )
            elif (instance.preset, instance.preset_version) in registry.errors:
                resolution.findings.append(
                    finding(
                        "preset-file-invalid",
                        f"Preset file for {instance.preset!r} {instance.preset_version!r} "
                        "is malformed.",
                        recipe=recipe_label,
                        path=f"parts[{instance.name}].preset",
                        expected="a valid preset document",
                        actual=registry.errors[(instance.preset, instance.preset_version)],
                        remedy="Fix the preset file; see `beastforge parts` for warnings.",
                    )
                )
            else:
                suggestion = next(
                    iter(difflib.get_close_matches(instance.preset, registry.names(), n=1)),
                    None,
                )
                resolution.findings.append(
                    finding(
                        "part-preset-missing",
                        f"Preset {instance.preset!r} does not exist in the library.",
                        recipe=recipe_label,
                        path=f"parts[{instance.name}].preset",
                        expected="a preset present in library/parts",
                        actual=instance.preset,
                        remedy="Run `beastforge parts` to list available presets.",
                        suggestion=suggestion,
                    )
                )
            continue

        slots = required_slots(preset, instance)
        bound = set(instance.bind)
        for slot in sorted(slots - bound):
            resolution.findings.append(
                finding(
                    "part-binding-missing",
                    f"Part {instance.name!r} does not bind @{slot}.",
                    recipe=recipe_label,
                    path=f"parts[{instance.name}].bind",
                    expected=sorted(slots),
                    actual=sorted(bound),
                    remedy=f"Add `{slot}: <bone>` to the bind map.",
                )
            )
        for extra in sorted(bound - slots):
            resolution.findings.append(
                finding(
                    "part-binding-unknown",
                    f"Part {instance.name!r} binds unused slot {extra!r}.",
                    recipe=recipe_label,
                    path=f"parts[{instance.name}].bind.{extra}",
                    expected=sorted(slots),
                    actual=extra,
                    remedy="Remove the extra binding or declare the slot in the preset.",
                )
            )
        for slot, target in sorted(instance.bind.items()):
            if target not in bone_names:
                resolution.findings.append(
                    finding(
                        "part-binding-missing",
                        f"Part {instance.name!r} binds {slot!r} to missing bone {target!r}.",
                        recipe=recipe_label,
                        path=f"parts[{instance.name}].bind.{slot}",
                        expected="an existing bone",
                        actual=target,
                        remedy="Correct the bone name or add it to the skeleton.",
                    )
                )
        targets = list(instance.bind.values())
        for duplicated in sorted({target for target in targets if targets.count(target) > 1}):
            resolution.findings.append(
                finding(
                    "part-binding-duplicate",
                    f"Part {instance.name!r} binds more than one slot to bone "
                    f"{duplicated!r}.",
                    recipe=recipe_label,
                    path=f"parts[{instance.name}].bind",
                    expected="distinct bones per slot",
                    actual=duplicated,
                    remedy="Bind each slot to its own bone; a collapsed path is invalid.",
                )
            )

        surface, surface_findings = _preset_surface(
            preset, instance, instance.bind, recipe_label=recipe_label
        )
        resolution.findings.extend(surface_findings)

        merged_controls = _merge_by_name(preset.controls, instance.controls)
        for duplicated in _duplicate_names(preset.controls) + _duplicate_names(
            instance.controls
        ):
            resolution.findings.append(
                finding(
                    "part-control-duplicate",
                    f"Part {instance.name!r} declares control {duplicated!r} more than once.",
                    recipe=recipe_label,
                    path=f"parts[{instance.name}].controls",
                    expected="unique control names within a part",
                    actual=duplicated,
                    remedy="Rename one of the duplicate controls.",
                )
            )
        controls: list[ControlChannel] = []
        for control in merged_controls:
            channel, control_findings = _resolve_control(
                control,
                part_name=instance.name,
                bind=instance.bind,
                bone_names=bone_names,
                recipe_label=recipe_label,
            )
            resolution.findings.extend(control_findings)
            if channel is None:
                continue
            if channel.address in addresses:
                resolution.findings.append(
                    finding(
                        "part-control-address-duplicate",
                        f"Control address {channel.address!r} is already used.",
                        recipe=recipe_label,
                        path=f"parts[{instance.name}].controls[{control.name}]",
                        expected="unique <part>/<control> addresses",
                        actual=channel.address,
                        remedy="Rename the part or the control.",
                    )
                )
                continue
            addresses.add(channel.address)
            controls.append(channel)

        merged_auto = _merge_by_name(preset.auto, instance.auto)
        for duplicated in _duplicate_names(preset.auto) + _duplicate_names(instance.auto):
            resolution.findings.append(
                finding(
                    "part-auto-duplicate",
                    f"Part {instance.name!r} declares automatic behaviour "
                    f"{duplicated!r} more than once.",
                    recipe=recipe_label,
                    path=f"parts[{instance.name}].auto",
                    expected="unique automatic-behaviour names within a part",
                    actual=duplicated,
                    remedy="Rename one of the duplicate behaviours.",
                )
            )
        autos: list[ResolvedAuto] = []
        for behaviour in merged_auto:
            resolved_auto, auto_findings = _resolve_auto(
                behaviour,
                part_name=instance.name,
                bind=instance.bind,
                bone_names=bone_names,
                recipe_label=recipe_label,
            )
            resolution.findings.extend(auto_findings)
            if resolved_auto is not None:
                autos.append(resolved_auto)

        if surface is None:
            continue
        resolution.parts.append(
            ResolvedPart(
                name=instance.name,
                preset=preset.name,
                preset_version=preset.version,
                preset_sha256=preset.sha256,
                family=preset.family,
                surface=surface,
                controls=controls,
                auto=autos,
                preset_document=preset.model_dump(
                    mode="json", exclude={"path", "sha256"}
                ),
            )
        )
    return resolution


def resolved_autos(parts: list[ResolvedPart]) -> list[ResolvedAuto]:
    """Flatten resolved automatic behaviours in part declaration order."""
    return [behaviour for part in parts for behaviour in part.auto]


__all__ = [
    "AXIS_TOLERANCE",
    "PartsResolution",
    "required_slots",
    "resolve_parts",
    "resolved_autos",
]
