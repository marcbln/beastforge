"""Construction-bound weight bands."""

from __future__ import annotations

from beastforge.rig.weights import band_for, joint_weights, smoothstep


def test_smoothstep_endpoints() -> None:
    assert smoothstep(-1.0) == 0.0
    assert smoothstep(0.0) == 0.0
    assert smoothstep(0.5) == 0.5
    assert smoothstep(1.0) == 1.0
    assert smoothstep(2.0) == 1.0


def test_band_is_clamped_to_a_third_of_the_bone() -> None:
    assert band_for(1.0, 0.25) == 0.25
    assert band_for(1.0, 0.9) == 0.35


def test_weights_are_normalized_and_at_most_two_influences() -> None:
    for s in [0.0, 0.2, 0.5, 0.9, 1.0]:
        influence = joint_weights(1, 0, 2, s=s, length=1.0, blend=0.25)
        assert len(influence.joints) == 2
        assert abs(sum(influence.weights) - 1.0) < 1e-12
        assert all(weight >= 0.0 for weight in influence.weights)


def test_joint_blend_is_continuous() -> None:
    end = joint_weights(1, 0, 2, s=1.0, length=1.0, blend=0.25)
    start = joint_weights(2, 1, 3, s=0.0, length=1.0, blend=0.25)
    assert abs(end.weights[1] - start.weights[1]) < 1e-12
    assert abs(end.weights[1] - 0.5) < 1e-12
