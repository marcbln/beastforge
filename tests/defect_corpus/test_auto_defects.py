"""Automatic-behaviour resolution defects (FR-013/014)."""

from __future__ import annotations

from beastforge.model.parts import BobAuto, BreatheAuto, RotateAuto
from beastforge.parts.resolve import _resolve_auto


def _resolve(behaviour, bind=None):
    return _resolve_auto(
        behaviour,
        part_name="tail",
        bind=bind or {"mount": "mount"},
        bone_names={"mount"},
        recipe_label="x",
    )


def test_missing_joint() -> None:
    behaviour = BreatheAuto(kind="breathe", name="b", joint="@missing", amplitude=0.1, period=2)
    resolved, findings = _resolve(behaviour)
    assert resolved is None
    assert "part-auto-joint-missing" in [item.code for item in findings]


def test_non_unit_axis() -> None:
    behaviour = BobAuto(
        kind="bob", name="b", joint="@mount", axis=[0, 2, 0], amplitude=0.1, period=2
    )
    resolved, findings = _resolve(behaviour)
    assert resolved is None
    assert "part-auto-axis-invalid" in [item.code for item in findings]


def test_non_positive_amplitude_and_period() -> None:
    behaviour = BreatheAuto(kind="breathe", name="b", joint="@mount", amplitude=0.0, period=2)
    _resolved, findings = _resolve(behaviour)
    assert "part-auto-amplitude-invalid" in [item.code for item in findings]

    behaviour = BreatheAuto(kind="breathe", name="b", joint="@mount", amplitude=0.1, period=0)
    _resolved, findings = _resolve(behaviour)
    assert "part-auto-period-invalid" in [item.code for item in findings]


def test_zero_rotate_rate() -> None:
    behaviour = RotateAuto(kind="rotate", name="r", joint="@mount", axis=[0, 1, 0], rate=0)
    resolved, findings = _resolve(behaviour)
    assert resolved is None
    assert "part-auto-rate-invalid" in [item.code for item in findings]


def test_duplicate_auto_name() -> None:
    from beastforge.parts.resolve import _duplicate_names

    behaviours = [
        BreatheAuto(kind="breathe", name="breathe", joint="@mount", amplitude=0.1, period=2),
        BreatheAuto(kind="breathe", name="breathe", joint="@mount", amplitude=0.2, period=3),
    ]
    assert _duplicate_names(behaviours) == ["breathe"]


def test_slot_substitution_resolves_joint() -> None:
    behaviour = BreatheAuto(kind="breathe", name="b", joint="@mount", amplitude=0.1, period=2)
    resolved, findings = _resolve(behaviour)
    assert findings == []
    assert resolved is not None and resolved.joint == "mount"
