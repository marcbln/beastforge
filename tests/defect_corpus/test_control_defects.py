"""Control-resolution defects across the preset/instance boundary."""

from __future__ import annotations

from beastforge.model.parts import PresetControl
from beastforge.parts.resolve import _resolve_control


def _resolve(control: PresetControl):
    return _resolve_control(
        control,
        part_name="leg",
        bind={"upper": "upper-fl"},
        bone_names={"upper-fl"},
        recipe_label="x",
    )


def _base(**overrides) -> PresetControl:
    values = {
        "name": "swing",
        "joint": "@upper",
        "axis": [1.0, 0.0, 0.0],
        "mode": "rotation",
        "range": {"min": -30.0, "max": 30.0},
        "default": 0.0,
        "units": "deg",
    }
    values.update(overrides)
    return PresetControl(**values)


def test_duplicate_control_name() -> None:
    from beastforge.parts.resolve import _duplicate_names

    assert _duplicate_names([_base(), _base()]) == ["swing"]


def test_missing_joint() -> None:
    channel, findings = _resolve(_base(joint="@missing"))
    assert channel is None
    assert "part-control-joint-missing" in [item.code for item in findings]


def test_non_unit_axis() -> None:
    channel, findings = _resolve(_base(axis=[0.0, 0.0, 0.0]))
    assert channel is None
    assert "part-control-axis-invalid" in [item.code for item in findings]


def test_mode_invalid() -> None:
    control = _base().model_copy(update={"mode": "scale"})
    channel, findings = _resolve(control)
    assert channel is None
    assert "part-control-mode-invalid" in [item.code for item in findings]


def test_unit_mismatch() -> None:
    control = _base(mode="translation", units="deg", axis=[0, 1, 0])
    channel, findings = _resolve(control)
    assert channel is None
    assert "part-control-units-mismatch" in [item.code for item in findings]


def test_range_and_default_invalid() -> None:
    channel, findings = _resolve(_base(range={"min": 5, "max": -5}))
    assert channel is None
    assert "part-control-range-invalid" in [item.code for item in findings]

    channel, findings = _resolve(_base(default=99))
    assert channel is None
    assert "part-control-default-out-of-range" in [item.code for item in findings]


def test_address_duplicate_across_parts(tmp_path) -> None:
    from beastforge.model.parts import PartInstance
    from beastforge.model.recipe import Bone, Meta, Recipe, Skeleton, Transform, Volume
    from beastforge.parts.registry import PresetRegistry
    from beastforge.parts.resolve import resolve_parts

    preset_root = tmp_path / "library/parts/unit"
    preset_root.mkdir(parents=True)
    (preset_root / "1.0.0.yaml").write_text(
        """\
name: unit
family: mechanical
version: "1.0.0"
description: "unit"
surface:
  mode: sweep
  kind: swept-solid
  bones: ["@upper"]
  rings: 4
  segments: 4
  radius: {start: 0.1, end: 0.1}
controls:
  - {name: swing, joint: "@upper", axis: [1, 0, 0], mode: rotation,
     range: {min: -10, max: 10}, default: 0, units: deg}
""",
        encoding="utf-8",
    )
    transform = Transform(translation=[0, 1, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1])
    recipe = Recipe(
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
                Bone(name="root", parent=None, rest=transform),
                Bone(
                    name="upper",
                    parent="root",
                    rest=Transform(translation=[0, 0.2, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1]),
                ),
            ],
        ),
        parts=[
            PartInstance(
                name="leg",
                preset="unit",
                preset_version="1.0.0",
                bind={"upper": "upper"},
            ),
            PartInstance(
                name="leg",
                preset="unit",
                preset_version="1.0.0",
                bind={"upper": "upper"},
            ),
        ],
        volumes=[Volume(name="hull", role="hit", center=[0, 1, 0], extents=[1, 1, 1])],
    )
    registry = PresetRegistry(tmp_path / "library/parts", cwd=tmp_path)
    resolution = resolve_parts(recipe, registry, recipe_label="fixture")
    codes = [finding.code for finding in resolution.findings]
    assert "part-duplicate-name" in codes
    assert "part-control-address-duplicate" in codes


def test_duplicate_control_in_one_preset(tmp_path) -> None:
    from beastforge.model.parts import PartInstance
    from beastforge.model.recipe import Bone, Meta, Recipe, Skeleton, Transform, Volume
    from beastforge.parts.registry import PresetRegistry
    from beastforge.parts.resolve import resolve_parts

    preset_root = tmp_path / "library/parts/unit"
    preset_root.mkdir(parents=True)
    (preset_root / "1.0.0.yaml").write_text(
        """\
name: unit
family: mechanical
version: "1.0.0"
description: "unit"
surface:
  mode: sweep
  kind: swept-solid
  bones: ["@upper"]
  rings: 4
  segments: 4
  radius: {start: 0.1, end: 0.1}
controls:
  - {name: swing, joint: "@upper", axis: [1, 0, 0], mode: rotation,
     range: {min: -10, max: 10}, default: 0, units: deg}
  - {name: swing, joint: "@upper", axis: [0, 1, 0], mode: rotation,
     range: {min: -10, max: 10}, default: 0, units: deg}
""",
        encoding="utf-8",
    )
    transform = Transform(translation=[0, 1, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1])
    recipe = Recipe(
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
                Bone(name="root", parent=None, rest=transform),
                Bone(
                    name="upper",
                    parent="root",
                    rest=Transform(translation=[0, 0.2, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1]),
                ),
            ],
        ),
        parts=[
            PartInstance(
                name="leg",
                preset="unit",
                preset_version="1.0.0",
                bind={"upper": "upper"},
            )
        ],
        volumes=[Volume(name="hull", role="hit", center=[0, 1, 0], extents=[1, 1, 1])],
    )
    registry = PresetRegistry(tmp_path / "library/parts", cwd=tmp_path)
    resolution = resolve_parts(recipe, registry, recipe_label="fixture")
    assert "part-control-duplicate" in [finding.code for finding in resolution.findings]
