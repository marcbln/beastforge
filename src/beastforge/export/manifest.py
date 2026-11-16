"""Manifest assembly (ADR 261114-1, data-model §14)."""

from __future__ import annotations

from typing import Any

from beastforge.anim.bake import BakedClip
from beastforge.export.gltf import TextureImage
from beastforge.geometry.mesh import Mesh
from beastforge.model.findings import CORE_CLIPS
from beastforge.model.manifest import (
    Bounds,
    Manifest,
    ManifestBudgets,
    ManifestClip,
    ManifestControl,
    ManifestControlRange,
    ManifestCreature,
    ManifestEvent,
    ManifestJoint,
    ManifestMaterial,
    ManifestPart,
    ManifestPhase,
    ManifestProvenance,
    ManifestSkeleton,
    ManifestSocket,
    ManifestTexture,
    ManifestVolume,
    Playback,
)
from beastforge.model.parts import ResolvedPart
from beastforge.model.recipe import Clip, Event, Recipe
from beastforge.rig.skeleton import BuiltSkeleton


def event_time(event: Event) -> float | None:
    """Resolve an event time in seconds from ``time`` or integer ``ticks``."""
    if event.ticks is not None:
        return event.ticks / 60.0
    if event.time is not None:
        return float(event.time)
    return None


def ordered_clips(clips: list[Clip]) -> list[Clip]:
    """Reserved core clips first, then extras sorted by name."""
    by_name = {clip.name: clip for clip in clips}
    ordered = [by_name[name] for name in CORE_CLIPS if name in by_name]
    ordered.extend(
        sorted((clip for clip in clips if clip.name not in CORE_CLIPS), key=lambda c: c.name)
    )
    return ordered


def _scalar(value: Any) -> str | int | float | bool | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def manifest_json(manifest: Manifest) -> dict[str, Any]:
    """Return the schema-shaped manifest mapping.

    ``parent`` is required-but-nullable, while ``volumes[].bone`` is optional:
    emit the former as ``null`` and omit the latter when absent.
    """
    payload = manifest.model_dump(mode="json")
    for volume in payload.get("volumes", []):
        if volume.get("bone") is None:
            volume.pop("bone", None)
    for part in payload.get("parts", []):
        for control in part.get("controls", []):
            if control.get("range") is None:
                control.pop("range", None)
    return payload


def build_manifest(
    *,
    recipe: Recipe,
    recipe_path: str,
    recipe_sha256: str,
    resolved_params: dict[str, Any],
    skeleton: BuiltSkeleton,
    mesh: Mesh,
    baked_clips: list[BakedClip],
    textures: list[TextureImage],
    tool_version: str,
    texforge_version: str,
    parts: list[ResolvedPart] | None = None,
) -> Manifest:
    """Assemble the canonical manifest model for one built creature."""
    recipe_by_clip = {clip.name: clip for clip in recipe.clips}
    ordered = [clip for clip in baked_clips if clip.name in recipe_by_clip]
    ordered += sorted(
        (clip for clip in baked_clips if clip.name not in recipe_by_clip),
        key=lambda clip: clip.name,
    )
    by_core = {clip.name: clip for clip in ordered}
    clips_model: list[BakedClip] = []
    for core in CORE_CLIPS:
        if core in by_core:
            clips_model.append(by_core.pop(core))
    clips_model.extend(sorted(by_core.values(), key=lambda clip: clip.name))

    clips: list[ManifestClip] = []
    events: list[ManifestEvent] = []
    for baked in clips_model:
        clips.append(
            ManifestClip(
                name=baked.name,
                duration=baked.duration,
                loop=baked.loop,
                generator=baked.generator,
                source=baked.source,
            )
        )
        declared = recipe_by_clip.get(baked.name)
        if declared is None:
            continue
        for event in declared.events:
            time = event_time(event)
            if time is None:
                continue
            events.append(ManifestEvent(clip=baked.name, time=time, name=event.name))

    texture_by_material = {texture.material: texture for texture in textures}
    materials: list[ManifestMaterial] = []
    for material in recipe.materials:
        texture = texture_by_material.get(material.name)
        if texture is None:
            continue
        materials.append(
            ManifestMaterial(
                name=material.name,
                slot="baseColor",
                texture=ManifestTexture(
                    recipe=texture.recipe,
                    params=dict(texture.params),
                    size=texture.size,
                    sha256=texture.sha256,
                ),
                metallic=float(material.metallic),
                roughness=float(material.roughness),
            )
        )

    bounds_min, bounds_max = mesh.bounds()
    manifest_parts = [
        ManifestPart(
            name=part.name,
            preset=part.preset,
            presetVersion=part.preset_version,
            presetSha256=part.preset_sha256,
            family=part.family,
            controls=[
                ManifestControl(
                    address=control.address,
                    name=control.name,
                    joint=control.joint,
                    axis=[float(value) for value in control.axis],
                    mode=control.mode,
                    unbounded=control.unbounded,
                    range=ManifestControlRange(min=control.range.min, max=control.range.max)
                    if control.range is not None
                    else None,
                    default=control.default,
                    units=control.units,
                )
                for control in part.controls
            ],
        )
        for part in parts or []
    ]
    return Manifest(
        schemaVersion="1.1",
        toolVersion=tool_version,
        creature=ManifestCreature(
            name=recipe.meta.name,
            category=recipe.meta.category,
            description=recipe.meta.description,
        ),
        provenance=ManifestProvenance(
            recipePath=recipe_path,
            recipeSha256=recipe_sha256,
            recipeVersion=recipe.meta.version,
            resolvedParams={key: _scalar(value) for key, value in resolved_params.items()},
            toolVersion=tool_version,
            texforgeVersion=texforge_version,
        ),
        bounds=Bounds(
            min=[float(value) for value in bounds_min],
            max=[float(value) for value in bounds_max],
        ),
        suggestedScale=1.0,
        skeleton=ManifestSkeleton(
            root=skeleton.node_order[0],
            joints=[
                ManifestJoint(name=name, parent=skeleton.parent_of(name))
                for name in skeleton.node_order
            ],
        ),
        clips=clips,
        parts=manifest_parts,
        events=events,
        sockets=[
            ManifestSocket(
                name=socket.name, target=socket.bone, offset=[float(v) for v in socket.offset]
            )
            for socket in recipe.sockets
        ],
        volumes=[
            ManifestVolume(
                name=volume.name,
                role=volume.role,
                center=[float(value) for value in volume.center],
                extents=[float(value) for value in volume.extents],
                bone=volume.bone,
            )
            for volume in recipe.volumes
        ],
        phases=[
            ManifestPhase(name=phase.name, threshold=float(phase.threshold))
            for phase in recipe.phases
        ],
        materials=materials,
        playback=Playback(
            eventTimeScaling="proportional",
            warning=(
                "Changing playback rate scales every event time by the same factor; "
                "read gameplay timing from this manifest, never from baked keyframes."
            ),
        ),
        budgets=ManifestBudgets(
            vertices=mesh.vertex_count,
            bones=len(skeleton.names),
            triangles=mesh.triangle_count,
        ),
    )
