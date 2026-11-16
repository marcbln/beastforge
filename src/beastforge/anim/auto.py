"""Deterministic automatic-behaviour evaluation and composition.

Behaviours are declarative data. They are evaluated at fixed sample times and
baked into clips; nothing here is a runtime animation API. Multiple behaviours on
one joint compose in declaration order (translations sum, rotations multiply,
scales multiply).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from beastforge.anim.registry import Delta
from beastforge.model.parts import (
    BobAuto,
    BreatheAuto,
    ResolvedAuto,
    RotateAuto,
    SwayAuto,
)
from beastforge.rig.skeleton import quat_from_axis_angle, quat_multiply, quat_normalize

IDENTITY_ROTATION = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
UNIT_SCALE = np.ones(3, dtype=np.float64)


def evaluate_behaviour(behaviour: ResolvedAuto, time: float) -> Delta:
    """Evaluate one behaviour's local delta at ``time`` seconds."""
    phase = math.radians(float(getattr(behaviour, "phase", 0.0)))
    if isinstance(behaviour, BreatheAuto):
        pulse = math.sin(math.tau * time / behaviour.period + phase)
        scale = 1.0 + behaviour.amplitude * pulse
        return Delta(scale=np.array([scale, scale, scale], dtype=np.float64))
    if isinstance(behaviour, BobAuto):
        offset = behaviour.amplitude * math.sin(math.tau * time / behaviour.period + phase)
        axis = np.asarray(behaviour.axis, dtype=np.float64)
        return Delta(translation=axis * offset)
    if isinstance(behaviour, SwayAuto):
        angle = math.radians(behaviour.amplitude) * math.sin(
            math.tau * time / behaviour.period + phase
        )
        return Delta(
            rotation=quat_from_axis_angle(np.asarray(behaviour.axis, dtype=np.float64), angle)
        )
    if isinstance(behaviour, RotateAuto):
        angle = math.radians(behaviour.rate * time + behaviour.phase)
        return Delta(
            rotation=quat_from_axis_angle(np.asarray(behaviour.axis, dtype=np.float64), angle)
        )
    raise TypeError(f"unknown automatic behaviour {type(behaviour).__name__}")


def compose_behaviours(behaviours: list[ResolvedAuto]) -> Callable[[float], Delta]:
    """Compose behaviours for one joint in declaration order."""

    def evaluate(time: float) -> Delta:
        translation = np.zeros(3, dtype=np.float64)
        rotation = IDENTITY_ROTATION.copy()
        scale = UNIT_SCALE.copy()
        for behaviour in behaviours:
            delta = evaluate_behaviour(behaviour, time)
            translation = translation + np.asarray(delta.translation, dtype=np.float64)
            rotation = quat_multiply(
                rotation, np.asarray(delta.rotation, dtype=np.float64)
            )
            rotation = quat_normalize(rotation)
            scale = scale * np.asarray(delta.scale, dtype=np.float64)
        return Delta(translation=translation, rotation=rotation, scale=scale)

    return evaluate


def auto_functions(autos: list[ResolvedAuto]) -> dict[str, Callable[[float], Delta]]:
    """Group behaviours by joint, preserving declaration order per joint."""
    grouped: dict[str, list[ResolvedAuto]] = {}
    order: list[str] = []
    for behaviour in autos:
        if behaviour.joint not in grouped:
            grouped[behaviour.joint] = []
            order.append(behaviour.joint)
        grouped[behaviour.joint].append(behaviour)
    return {joint: compose_behaviours(grouped[joint]) for joint in order}


def baseline_duration(autos: list[ResolvedAuto], *, max_ticks: int = 600) -> float:
    """Deterministic synthesized-baseline duration in seconds."""
    periods = [
        float(behaviour.period)
        for behaviour in autos
        if isinstance(behaviour, (BreatheAuto, BobAuto, SwayAuto))
    ]
    duration = max(2.0, max(periods)) if periods else 2.0
    return min(duration, max_ticks / 60.0)


__all__ = [
    "auto_functions",
    "baseline_duration",
    "compose_behaviours",
    "evaluate_behaviour",
]
