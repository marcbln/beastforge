"""Pixel-independent structural summaries for the showroom (FR-041)."""

from __future__ import annotations

from beastforge.anim.bake import BakedClip
from beastforge.export.manifest import ordered_clips
from beastforge.geometry.mesh import Mesh
from beastforge.model.manifest import (
    Bounds,
    ShowroomCounts,
    ShowroomJoints,
    ShowroomSkin,
    ShowroomStructural,
    ShowroomStructuralClip,
    ShowroomStructuralEvent,
)
from beastforge.model.recipe import Recipe
from beastforge.rig.skeleton import BuiltSkeleton


def build_structural(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    mesh: Mesh,
    clips: list[BakedClip] | None = None,
) -> ShowroomStructural:
    """Build the exact structural summary committed with the reference set."""
    influence_counts = (mesh.weights > 0.0).sum(axis=1)
    weight_sums = mesh.weights.sum(axis=1)
    clip_durations = {clip.name: clip.duration for clip in (clips or [])}
    clip_json: list[ShowroomStructuralClip] = []
    event_json: list[ShowroomStructuralEvent] = []
    for clip in ordered_clips(recipe.clips):
        duration = clip_durations.get(
            clip.name,
            clip.ticks / 60.0 if clip.ticks is not None else float(clip.duration or 0.0),
        )
        clip_json.append(
            ShowroomStructuralClip(
                name=clip.name,
                duration=duration,
                loop=clip.loop,
                generator=clip.generator,
            )
        )
        for event in clip.events:
            time = event.ticks / 60.0 if event.ticks is not None else float(event.time or 0.0)
            event_json.append(ShowroomStructuralEvent(clip=clip.name, name=event.name, time=time))
    bounds_min, bounds_max = mesh.bounds()
    return ShowroomStructural(
        joints=ShowroomJoints(count=len(skeleton.node_order), names=list(skeleton.node_order)),
        clips=clip_json,
        events=event_json,
        skin=ShowroomSkin(
            influences_one=int((influence_counts == 1).sum()),
            influences_two=int((influence_counts == 2).sum()),
            min_weight_sum=float(weight_sums.min()) if weight_sums.size else 0.0,
            max_weight_sum=float(weight_sums.max()) if weight_sums.size else 0.0,
        ),
        bounds=Bounds(
            min=[float(value) for value in bounds_min],
            max=[float(value) for value in bounds_max],
        ),
        counts=ShowroomCounts(
            vertices=mesh.vertex_count,
            triangles=mesh.triangle_count,
            surfaces=len(mesh.surfaces),
        ),
    )
