"""A hand-authored surface and an equivalent preset produce the same closed part."""

from __future__ import annotations

import numpy as np

from beastforge.geometry.closure import analyze_part
from beastforge.model.parts import PartInstance
from beastforge.model.recipe import Bone, Meta, Recipe, Skeleton, Surface, Transform, Volume
from beastforge.parts.registry import PresetRegistry
from beastforge.parts.resolve import resolve_parts
from beastforge.pipeline import build_mesh
from beastforge.rig.skeleton import build_skeleton
from tests.conftest import ROOT


def _transform(translation: list[float]) -> Transform:
    return Transform(translation=translation, rotation=[0, 0, 0, 1], scale=[1, 1, 1])


def _skeleton() -> Skeleton:
    return Skeleton(
        root="root",
        bones=[
            Bone(name="root", parent=None, rest=_transform([0, 1, 0])),
            Bone(name="upper", parent="root", rest=_transform([0, -0.3, 0])),
            Bone(name="lower", parent="upper", rest=_transform([0, -0.3, 0])),
            Bone(name="foot", parent="lower", rest=_transform([0, -0.3, 0])),
        ],
    )


def _recipe(instance: PartInstance) -> Recipe:
    return Recipe(
        meta=Meta(
            name="fixture",
            description="fixture",
            category="other",
            tested_with="0.1.0",
            version="1.0.0",
        ),
        skeleton=_skeleton(),
        parts=[instance],
        volumes=[Volume(name="hull", role="hit", center=[0, 1, 0], extents=[1, 1, 1])],
    )


def test_preset_replaces_hand_authored_surface_without_losing_closure() -> None:
    hand = Surface(
        name="front-leg",
        mode="sweep",
        kind="swept-solid",
        bones=["upper", "lower", "foot"],
        rings=10,
        segments=8,
        radius={"start": 0.12, "end": 0.05},
        blend=0.25,
        material="hide",
    )
    instance = PartInstance(
        name="front-leg",
        preset="organic-leg",
        preset_version="1.0.0",
        bind={"upper": "upper", "lower": "lower", "foot": "foot"},
        material="hide",
    )
    registry = PresetRegistry(ROOT / "library/parts", cwd=ROOT)
    resolution = resolve_parts(_recipe(instance), registry, recipe_label="fixture")
    assert resolution.findings == []
    resolved = resolution.parts[0]

    skeleton = build_skeleton(_skeleton())
    hand_mesh = build_mesh(Recipe.model_construct(surfaces=[hand], parts=[]), skeleton, "seed")
    preset_mesh = build_mesh(
        Recipe.model_construct(surfaces=[], parts=[]), skeleton, "seed", resolved_parts=[resolved]
    )
    np.testing.assert_allclose(hand_mesh.positions, preset_mesh.positions)
    np.testing.assert_array_equal(hand_mesh.indices, preset_mesh.indices)

    assert [control.address for control in resolved.controls] == [
        "front-leg/swing",
        "front-leg/lift",
    ]
    report = analyze_part(preset_mesh.positions, preset_mesh.indices, "front-leg")
    assert report.closed is True
