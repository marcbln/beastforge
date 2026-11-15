"""Clip timing, baking, and loop-closing keys."""

from __future__ import annotations

import numpy as np

from beastforge.anim.bake import bake_clip, resolve_duration, sample_times
from beastforge.model.loader import load_recipe
from beastforge.rig.skeleton import build_skeleton


def test_ticks_convert_exactly() -> None:
    from beastforge.model.recipe import Clip

    clip = Clip(name="attack", generator="telegraph-attack", ticks=50, loop=False)
    assert resolve_duration(clip) == 50 / 60.0


def test_sample_times_are_60hz_and_include_endpoint() -> None:
    times = sample_times(1.0)
    assert times[0] == 0.0
    assert times[-1] == 1.0
    assert len(times) == 61
    assert np.allclose(np.diff(times), 1 / 60.0)


def test_loop_closing_key_matches_first_key(repo_root) -> None:
    recipe, _ = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    skeleton = build_skeleton(recipe.skeleton)
    idle = next(clip for clip in recipe.clips if clip.name == "idle")
    baked = bake_clip(idle, recipe, skeleton, "seed")
    assert baked.loop
    assert baked.tracks
    for track in baked.tracks:
        assert np.allclose(track.translations[0], track.translations[-1])
        assert np.allclose(track.rotations[0], track.rotations[-1])
        assert np.allclose(track.scales[0], track.scales[-1])


def test_baked_clips_cover_reserved_names(repo_root) -> None:
    recipe, _ = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    skeleton = build_skeleton(recipe.skeleton)
    baked = [bake_clip(clip, recipe, skeleton, "seed") for clip in recipe.clips]
    assert {clip.name for clip in baked} >= {"idle", "locomotion", "attack", "hurt", "death"}
