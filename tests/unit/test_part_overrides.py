"""Canonical partial override application."""

from __future__ import annotations

from beastforge.model.parts import PresetParam, PresetSurface
from beastforge.parts.overrides import apply_overrides

SURFACE = PresetSurface(
    mode="sweep",
    kind="swept-solid",
    bones=["@root", "@tip"],
    rings=8,
    segments=8,
    radius={"start": 0.2, "end": 0.1},
    blend=0.25,
    modifiers={"taper": {"start": 1.0, "end": 0.8}, "twist": 0.0, "squash": [1.0, 1.0, 1.0]},
)


def _params() -> list[PresetParam]:
    return [
        PresetParam(name="radius-start", type="float", min=0.01, max=0.5, description="root"),
        PresetParam(name="radius-end", type="float", min=0.01, max=0.5, description="tip"),
        PresetParam(name="rings", type="int", min=4, max=32, description="rings"),
        PresetParam(name="taper-end", type="float", min=0.1, max=2.0, description="taper"),
        PresetParam(name="squash-y", type="float", min=0.1, max=3.0, description="squash"),
    ]


def test_partial_merge_keeps_untouched_values() -> None:
    result, findings = apply_overrides(
        SURFACE, {"radius-end": 0.04}, _params(), part_name="leg", recipe_label="x"
    )
    assert findings == []
    assert result.radius.start == 0.2
    assert result.radius.end == 0.04
    assert result.rings == 8


def test_nested_targets_do_not_replace_objects_wholesale() -> None:
    result, findings = apply_overrides(
        SURFACE,
        {"taper-end": 0.5, "squash-y": 1.5},
        _params(),
        part_name="leg",
        recipe_label="x",
    )
    assert findings == []
    assert result.modifiers.taper is not None
    assert result.modifiers.taper.start == 1.0
    assert result.modifiers.taper.end == 0.5
    assert result.modifiers.squash[0] == 1.0
    assert result.modifiers.squash[1] == 1.5
    assert result.modifiers.squash[2] == 1.0


def test_type_and_range_errors() -> None:
    _result, findings = apply_overrides(
        SURFACE, {"rings": 8.5}, _params(), part_name="leg", recipe_label="x"
    )
    assert [finding.code for finding in findings] == ["part-override-type"]

    _result, findings = apply_overrides(
        SURFACE, {"radius-start": 99.0}, _params(), part_name="leg", recipe_label="x"
    )
    assert [finding.code for finding in findings] == ["part-override-range"]


def test_unknown_key_has_nearest_suggestion() -> None:
    result, findings = apply_overrides(
        SURFACE, {"radius-en": 0.1}, _params(), part_name="leg", recipe_label="x"
    )
    assert result.radius.end == 0.1  # untouched
    assert findings[0].code == "part-override-unknown"
    assert findings[0].suggestion == "radius-end"


def test_deep_copy_does_not_mutate_input() -> None:
    apply_overrides(SURFACE, {"rings": 16}, _params(), part_name="leg", recipe_label="x")
    assert SURFACE.rings == 8
