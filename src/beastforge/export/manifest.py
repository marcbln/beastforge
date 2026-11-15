"""Manifest assembly (ADR 261114-1, data-model §14)."""

from __future__ import annotations

from typing import Any

from beastforge.anim.bake import BakedClip, resolve_duration
from beastforge.export.gltf import TextureImage
from beastforge.geometry.mesh import Mesh
from beastforge.model.findings import CORE_CLIPS
from beastforge.model.manifest import (
    Bounds,
    Manifest,
    ManifestBudgets,
    ManifestClip,
    ManifestCreature,
    ManifestEvent,
    ManifestJoint,
    ManifestMaterial,
    ManifestPhase,
    ManifestProvenance,
    ManifestSkeleton,
    ManifestSocket,
    ManifestTexture,
    ManifestVolume,
    Playback,
)
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
) -> Manifest:
    """Assemble the canonical manifest model for one built creature."""
    clip_durations = {clip.name: clip.duration for clip in baked_clips}
    clips: list[ManifestClip] = []
    events: list[ManifestEvent] = []
    for clip in ordered_clips(recipe.clips):
        duration = clip_durations.get(clip.name, resolve_duration(clip))
        clips.append(
            ManifestClip(
                name=clip.name,
                duration=duration,
                loop=clip.loop,
                generator=clip.generator,
            )
        )
        for event in clip.events:
            time = event_time(event)
            if time is None:
                continue
            events.append(ManifestEvent(clip=clip.name, time=time, name=event.name))

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
    return Manifest(
        schemaVersion="1.0",
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
