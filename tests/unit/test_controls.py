"""Control-channel normalization and validation rules (FR-008/012)."""

from __future__ import annotations

from beastforge.model.parts import ControlRange, PresetControl
from beastforge.parts.resolve import _resolve_control


def _control(**overrides) -> PresetControl:
    values = {
        "name": "swing",
        "joint": "@upper",
        "axis": [1.0, 0.0, 0.0],
        "mode": "rotation",
        "range": {"min": -35.0, "max": 35.0},
        "default": 0.0,
        "units": "deg",
    }
    values.update(overrides)
    return PresetControl(**values)


def _resolve(control: PresetControl, bind: dict[str, str] | None = None):
    return _resolve_control(
        control,
        part_name="leg",
        bind=bind or {"upper": "upper-fl"},
        bone_names={"upper-fl"},
        recipe_label="x",
    )


def test_range_implies_bounded_and_missing_range_implies_unbounded() -> None:
    channel, findings = _resolve(_control())
    assert findings == []
    assert channel is not None and channel.unbounded is False

    channel, findings = _resolve(
        _control(range=None, default=0.0)
    )
    assert findings == []
    assert channel is not None and channel.unbounded is True
    assert channel.range is None


def test_axis_must_be_a_unit_vector() -> None:
    channel, findings = _resolve(_control(axis=[2.0, 0.0, 0.0]))
    assert channel is None
    assert [finding.code for finding in findings] == ["part-control-axis-invalid"]


def test_units_must_match_mode() -> None:
    channel, findings = _resolve(_control(mode="translation", units="deg", axis=[0, 1, 0]))
    assert channel is None
    assert "part-control-units-mismatch" in [finding.code for finding in findings]


def test_bounded_default_must_be_inside_range() -> None:
    channel, findings = _resolve(_control(default=90.0))
    assert channel is None
    assert [finding.code for finding in findings] == ["part-control-default-out-of-range"]


def test_unbounded_control_may_not_declare_a_range() -> None:
    channel, findings = _resolve(_control(unbounded=True))
    assert channel is None
    assert [finding.code for finding in findings] == ["part-control-range-invalid"]


def test_slot_substitutes_to_a_concrete_joint_and_address() -> None:
    channel, findings = _resolve(_control(joint="@upper"))
    assert findings == []
    assert channel is not None
    assert channel.joint == "upper-fl"
    assert channel.address == "leg/swing"


def test_missing_joint_is_reported() -> None:
    channel, findings = _resolve(_control(joint="@missing"))
    assert channel is None
    assert "part-control-joint-missing" in [finding.code for finding in findings]


def test_control_range_model_round_trips() -> None:
    channel, _findings = _resolve(_control(range=ControlRange(min=-1, max=1), default=0))
    assert channel is not None and channel.range is not None
    assert channel.range.min == -1.0
