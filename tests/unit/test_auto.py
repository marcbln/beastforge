"""Automatic motion evaluation, composition, precedence, and baseline length."""

from __future__ import annotations

import math

import numpy as np

from beastforge.anim.auto import baseline_duration, compose_behaviours, evaluate_behaviour
from beastforge.anim.bake import bake_clip
from beastforge.model.parts import BobAuto, BreatheAuto, RotateAuto, SwayAuto
from beastforge.model.recipe import Bone, Clip, Meta, Recipe, Skeleton, Transform, Volume
from beastforge.rig.skeleton import build_skeleton


def _transform(translation: list[float]) -> Transform:
    return Transform(translation=translation, rotation=[0, 0, 0, 1], scale=[1, 1, 1])


def _skeleton():
    return build_skeleton(
        Skeleton(
            root="root",
            bones=[
                Bone(name="root", parent=None, rest=_transform([0, 1, 0])),
                Bone(name="spine-1", parent="root", rest=_transform([0, 0.3, 0])),
                Bone(name="tail-1", parent="spine-1", rest=_transform([0, 0, 0.3])),
            ],
        )
    )


def _recipe() -> Recipe:
    return Recipe(
        meta=Meta(
            name="fixture",
            description="fixture",
            category="other",
            tested_with="0.1.0",
            version="1.0.0",
        ),
        skeleton=Skeleton(
            root="root",
            bones=[
                Bone(name="root", parent=None, rest=_transform([0, 1, 0])),
                Bone(name="spine-1", parent="root", rest=_transform([0, 0.3, 0])),
                Bone(name="tail-1", parent="spine-1", rest=_transform([0, 0, 0.3])),
            ],
        ),
        volumes=[Volume(name="hull", role="hit", center=[0, 1, 0], extents=[1, 1, 1])],
        clips=[Clip(name="idle", generator="breathe", duration=2.0, loop=True)],
    )


def test_breathe_bob_sway_and_rotate_deltas() -> None:
    breathe = BreatheAuto(kind="breathe", name="breathe", joint="j", amplitude=0.1, period=4.0)
    delta = evaluate_behaviour(breathe, 1.0)
    np.testing.assert_allclose(delta.scale, [1.1, 1.1, 1.1])

    bob = BobAuto(kind="bob", name="bob", joint="j", axis=[0, 1, 0], amplitude=0.2, period=4.0)
    delta = evaluate_behaviour(bob, 1.0)
    np.testing.assert_allclose(delta.translation, [0.0, 0.2, 0.0])

    sway = SwayAuto(
        kind="sway", name="sway", joint="j", axis=[0, 0, 1], amplitude=30.0, period=4.0
    )
    delta = evaluate_behaviour(sway, 1.0)
    assert math.isclose(float(delta.rotation[3]), math.cos(math.radians(15)), rel_tol=1e-9)

    rotate = RotateAuto(
        kind="rotate", name="spin", joint="j", axis=[0, 1, 0], rate=90.0, phase=0.0
    )
    delta = evaluate_behaviour(rotate, 1.0)
    assert math.isclose(float(delta.rotation[3]), math.cos(math.radians(45)), rel_tol=1e-9)


def test_declaration_order_composition() -> None:
    bob_x = BobAuto(kind="bob", name="x", joint="j", axis=[1, 0, 0], amplitude=0.1, period=4.0)
    bob_y = BobAuto(kind="bob", name="y", joint="j", axis=[0, 1, 0], amplitude=0.2, period=4.0)
    delta = compose_behaviours([bob_x, bob_y])(1.0)
    np.testing.assert_allclose(delta.translation, [0.1, 0.2, 0.0])

    breathe_a = BreatheAuto(kind="breathe", name="a", joint="j", amplitude=0.1, period=4.0)
    breathe_b = BreatheAuto(kind="breathe", name="b", joint="j", amplitude=0.2, period=4.0)
    delta = compose_behaviours([breathe_a, breathe_b])(1.0)
    np.testing.assert_allclose(delta.scale, [1.32, 1.32, 1.32])

    sway_z = SwayAuto(
        kind="sway", name="s", joint="j", axis=[0, 0, 1], amplitude=30.0, period=4.0
    )
    delta = compose_behaviours([sway_z, sway_z])(1.0)
    assert math.isclose(float(delta.rotation[3]), math.cos(math.radians(30)), rel_tol=1e-9)


def test_baseline_duration_rule() -> None:
    slow = SwayAuto(kind="sway", name="a", joint="j", axis=[0, 1, 0], amplitude=5, period=4.0)
    fast = BobAuto(kind="bob", name="b", joint="j", axis=[0, 1, 0], amplitude=0.1, period=1.0)
    rotate = RotateAuto(kind="rotate", name="r", joint="j", axis=[0, 1, 0], rate=90)
    assert baseline_duration([slow, fast]) == 4.0
    assert baseline_duration([rotate]) == 2.0
    assert baseline_duration([slow], max_ticks=120) == 2.0
    long_period = SwayAuto(
        kind="sway", name="s", joint="j", axis=[0, 1, 0], amplitude=5, period=10
    )
    assert baseline_duration([long_period], max_ticks=300) == 5.0


def test_explicit_clip_wins_on_the_same_joint() -> None:
    recipe = _recipe()
    skeleton = _skeleton()
    clip = recipe.clips[0]
    sway = SwayAuto(
        kind="sway", name="ambient", joint="spine-1", axis=[0, 1, 0], amplitude=20, period=2.0
    )
    bob = BobAuto(
        kind="bob", name="tail-bob", joint="tail-1", axis=[0, 1, 0], amplitude=0.1, period=2.0
    )
    plain = bake_clip(clip, recipe, skeleton, "seed")
    with_auto = bake_clip(clip, recipe, skeleton, "seed", autos=[sway, bob])
    plain_spine = next(track for track in plain.tracks if track.name == "spine-1")
    auto_spine = next(track for track in with_auto.tracks if track.name == "spine-1")
    np.testing.assert_allclose(plain_spine.rotations, auto_spine.rotations)
    assert any(track.name == "tail-1" for track in with_auto.tracks)
    assert not any(track.name == "tail-1" for track in plain.tracks)
