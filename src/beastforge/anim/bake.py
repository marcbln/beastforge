"""Clip baking at 60 Hz with exact tick conversion (research D7, ADR 261114-4)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from beastforge.anim.registry import build_animation, normalize_clip_params
from beastforge.model.errors import BeastforgeError
from beastforge.model.recipe import Clip, Recipe
from beastforge.rig.skeleton import BuiltSkeleton, quat_multiply, quat_normalize


@dataclass
class JointTrack:
    """One joint's baked local TRS samples."""

    name: str
    times: np.ndarray
    translations: np.ndarray
    rotations: np.ndarray
    scales: np.ndarray


@dataclass
class BakedClip:
    """A clip sampled into deterministic joint tracks."""

    name: str
    duration: float
    loop: bool
    generator: str
    ticks: int
    tracks: list[JointTrack]


def resolve_duration(clip: Clip) -> float:
    """Return a clip's duration in seconds, converting ticks exactly."""
    if clip.ticks is not None and clip.duration is not None:
        raise BeastforgeError(
            "clip-param-invalid",
            f"Clip {clip.name!r} declares both duration and ticks.",
            location={"path": f"clips[{clip.name}]"},
            expected="exactly one of duration or ticks",
            actual="both",
            remedy="Remove either duration or ticks.",
        )
    if clip.ticks is not None:
        return clip.ticks / 60.0
    if clip.duration is not None:
        return float(clip.duration)
    raise BeastforgeError(
        "clip-param-invalid",
        f"Clip {clip.name!r} declares neither duration nor ticks.",
        location={"path": f"clips[{clip.name}]"},
        expected="duration or ticks",
        actual=None,
        remedy="Add a positive duration in seconds or an integer tick count.",
    )


def sample_times(duration: float) -> np.ndarray:
    """Return deterministic key times: every 60 Hz tick plus the exact endpoint."""
    if duration <= 0.0:
        raise BeastforgeError(
            "clip-nonpositive-duration",
            f"Clip duration must be positive, got {duration}.",
            remedy="Use a positive duration or a positive tick count.",
        )
    tick_count = max(1, int(round(duration * 60.0)))
    times = np.arange(tick_count + 1, dtype=np.float64) / 60.0
    if abs(times[-1] - duration) > 1e-9:
        if times[-1] < duration:
            times = np.append(times, duration)
        else:
            times[-1] = duration
    return times


def bake_clip(
    clip: Clip,
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    seed: str,
) -> BakedClip:
    """Bake one clip into local joint TRS arrays sampled at ~60 Hz."""
    duration = resolve_duration(clip)
    params = normalize_clip_params(clip)
    functions = build_animation(recipe, skeleton, clip, params, duration, clip.loop)
    times = sample_times(duration)
    tracks: list[JointTrack] = []

    for name in skeleton.names:
        function = functions.get(name)
        if function is None:
            continue
        rest = skeleton.local_transforms[name]
        rest_translation = np.asarray(rest.translation, dtype=np.float64)
        rest_rotation = quat_normalize(np.asarray(rest.rotation, dtype=np.float64))
        rest_scale = np.asarray(rest.scale, dtype=np.float64)
        translations: list[np.ndarray] = []
        rotations: list[np.ndarray] = []
        scales: list[np.ndarray] = []
        for index, time in enumerate(times):
            evaluate_at = time
            if clip.loop and index == len(times) - 1:
                evaluate_at = 0.0
            delta = function(float(evaluate_at))
            translations.append(rest_translation + np.asarray(delta.translation, dtype=np.float64))
            rotations.append(
                quat_normalize(
                    quat_multiply(rest_rotation, np.asarray(delta.rotation, dtype=np.float64))
                )
            )
            scales.append(rest_scale * np.asarray(delta.scale, dtype=np.float64))
        translation_array = np.asarray(translations, dtype=np.float64)
        rotation_array = np.asarray(rotations, dtype=np.float64)
        scale_array = np.asarray(scales, dtype=np.float64)
        changed = (
            not np.allclose(translation_array, rest_translation, atol=1e-9, rtol=0.0)
            or not np.allclose(rotation_array, rest_rotation, atol=1e-9, rtol=0.0)
            or not np.allclose(scale_array, rest_scale, atol=1e-9, rtol=0.0)
        )
        if changed:
            tracks.append(
                JointTrack(
                    name=name,
                    times=times.copy(),
                    translations=translation_array,
                    rotations=rotation_array,
                    scales=scale_array,
                )
            )

    return BakedClip(
        name=clip.name,
        duration=duration,
        loop=clip.loop,
        generator=clip.generator,
        ticks=int(round(duration * 60.0)),
        tracks=tracks,
    )


def bake_clips(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    seed: str,
) -> list[BakedClip]:
    """Bake every declared clip in recipe order."""
    return [bake_clip(clip, recipe, skeleton, seed) for clip in recipe.clips]
