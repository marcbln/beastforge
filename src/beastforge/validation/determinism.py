"""Determinism hazards and manifest referential integrity (FR-037/038)."""

from __future__ import annotations

from typing import Any

from beastforge.model.findings import CORE_CLIPS, ValidationFinding
from beastforge.model.manifest import Manifest
from beastforge.model.recipe import Recipe
from beastforge.validation.common import finding


def check_recipe_determinism(recipe: Recipe, *, recipe_label: str) -> list[ValidationFinding]:
    """Reject units/orientation values that would make the contract ambiguous."""
    findings: list[ValidationFinding] = []
    if recipe.meta.units != "m":
        findings.append(
            finding(
                "determinism-hazard",
                f"Recipe units must be metres, got {recipe.meta.units!r}.",
                recipe=recipe_label,
                path="meta.units",
                expected="m",
                actual=recipe.meta.units,
                remedy="Remove meta.units or set it to m.",
            )
        )
    if recipe.meta.orientation.up != "Y" or recipe.meta.orientation.forward != "-Z":
        findings.append(
            finding(
                "determinism-hazard",
                "Recipe orientation must be Y-up and -Z forward.",
                recipe=recipe_label,
                path="meta.orientation",
                expected={"up": "Y", "forward": "-Z"},
                actual={
                    "up": recipe.meta.orientation.up,
                    "forward": recipe.meta.orientation.forward,
                },
                remedy="Remove meta.orientation or use up: Y and forward: '-Z'.",
            )
        )
    return findings


def check_manifest(
    manifest: Manifest | dict[str, Any],
    *,
    recipe: Recipe | None,
    skeleton_names: set[str] | None,
    recipe_label: str,
) -> list[ValidationFinding]:
    """Check schema version, core clips, and dangling references."""
    findings: list[ValidationFinding] = []
    if isinstance(manifest, dict):
        try:
            manifest = Manifest.model_validate(manifest)
        except Exception as exc:  # noqa: BLE001 - validation surfaces the error
            return [
                finding(
                    "manifest-schema-invalid",
                    f"Manifest does not match the v1 schema: {exc}",
                    recipe=recipe_label,
                    path="manifest",
                    expected="a v1 manifest object",
                    actual=str(exc),
                    remedy="Regenerate the package; do not hand-edit the manifest.",
                )
            ]
    major = manifest.schemaVersion.split(".", 1)[0]
    if major != "1":
        findings.append(
            finding(
                "manifest-schema-unsupported",
                f"Manifest major version {major} is not supported by this consumer.",
                recipe=recipe_label,
                path="manifest.schemaVersion",
                expected="1.x",
                actual=manifest.schemaVersion,
                remedy="Upgrade the consumer or regenerate with a matching major version.",
            )
        )
    clip_names = {clip.name for clip in manifest.clips}
    for core in CORE_CLIPS:
        if core not in clip_names:
            findings.append(
                finding(
                    "manifest-core-clip-missing",
                    f"Manifest is missing required core clip {core!r}.",
                    recipe=recipe_label,
                    path="manifest.clips",
                    expected="all reserved core clips",
                    actual=sorted(clip_names),
                    remedy="Regenerate the manifest from the recipe.",
                )
            )
    for event in manifest.events:
        if event.clip not in clip_names:
            findings.append(
                finding(
                    "manifest-dangling-reference",
                    f"Manifest event {event.name!r} references missing clip {event.clip!r}.",
                    recipe=recipe_label,
                    path="manifest.events",
                    expected="an existing clip name",
                    actual=event.clip,
                    remedy="Regenerate the manifest; do not edit clip names by hand.",
                )
            )
    joint_names = skeleton_names or {joint.name for joint in manifest.skeleton.joints}
    for socket in manifest.sockets:
        if socket.target not in joint_names:
            findings.append(
                finding(
                    "manifest-dangling-reference",
                    f"Manifest socket {socket.name!r} targets missing joint {socket.target!r}.",
                    recipe=recipe_label,
                    path="manifest.sockets",
                    expected="an existing joint name",
                    actual=socket.target,
                    remedy="Regenerate the manifest from the recipe.",
                )
            )
    for volume in manifest.volumes:
        if volume.bone is not None and volume.bone not in joint_names:
            findings.append(
                finding(
                    "manifest-dangling-reference",
                    f"Manifest volume {volume.name!r} follows missing joint {volume.bone!r}.",
                    recipe=recipe_label,
                    path="manifest.volumes",
                    expected="an existing joint name",
                    actual=volume.bone,
                    remedy="Regenerate the manifest from the recipe.",
                )
            )
    if recipe is not None:
        material_names = {material.name for material in manifest.materials}
        referenced = {surface.material for surface in recipe.surfaces if surface.material}
        for name in sorted(referenced - material_names):
            findings.append(
                finding(
                    "manifest-dangling-reference",
                    f"Manifest omits material {name!r} referenced by a surface.",
                    recipe=recipe_label,
                    path="manifest.materials",
                    expected="every referenced material",
                    actual=sorted(material_names),
                    remedy="Regenerate the package so textures are embedded.",
                )
            )
    return findings
