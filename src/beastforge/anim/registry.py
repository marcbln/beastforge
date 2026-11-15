"""Closed clip-generator registry (ADR 261114-4, FR-022).

Generators return a small set of local joint deltas as functions of time. The
baker samples those functions at 60 Hz; nothing here is evaluated at runtime.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Clip, Recipe
from beastforge.rig.skeleton import BuiltSkeleton, quat_from_axis_angle

IDENTITY_ROTATION = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)


@dataclass
class Delta:
    """A local-space offset from a joint's rest transform."""

    translation: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    rotation: np.ndarray = field(default_factory=lambda: IDENTITY_ROTATION.copy())
    scale: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=np.float64))


@dataclass
class GeneratorSpec:
    """One generator's defaults, accepted parameter types, and animation builder."""

    name: str
    defaults: dict[str, Any]
    types: dict[str, type | tuple[type, ...]]
    factory: Callable[
        [Recipe, BuiltSkeleton, dict[str, Any], float, bool],
        dict[str, Callable[[float], Delta]],
    ]


def identity() -> Delta:
    """Return an identity delta."""
    return Delta()


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _smoothstep(value: float) -> float:
    t = _clamp01(value)
    return t * t * (3.0 - 2.0 * t)


def _bones_matching(skeleton: BuiltSkeleton, keywords: tuple[str, ...]) -> list[str]:
    return [name for name in skeleton.names if any(keyword in name.lower() for keyword in keywords)]


def _chains_matching(recipe: Recipe, keywords: tuple[str, ...]) -> list[list[str]]:
    return [
        list(chain.bones)
        for chain in recipe.skeleton.chains
        if any(keyword in chain.name.lower() for keyword in keywords)
    ]


def _all_chains(recipe: Recipe) -> list[list[str]]:
    return [list(chain.bones) for chain in recipe.skeleton.chains]


def _locomotion_chains(recipe: Recipe) -> list[list[str]]:
    chains = _chains_matching(recipe, ("leg", "limb", "foot", "arm", "hand", "claw"))
    return chains or [
        chain
        for chain in _all_chains(recipe)
        if not any(token in " ".join(chain) for token in ("tail", "head", "jaw", "neck"))
    ]


def _attack_chain(recipe: Recipe, skeleton: BuiltSkeleton) -> list[str]:
    chains = _chains_matching(recipe, ("claw", "arm", "weapon", "jaw", "head", "maw"))
    if chains:
        return max(chains, key=len)
    heads = _bones_matching(skeleton, ("head", "jaw", "maw", "claw"))
    if heads:
        return [heads[-1]]
    chains = _all_chains(recipe)
    if chains:
        return max(chains, key=len)
    return [skeleton.node_order[-1]]


def _spine_bones(skeleton: BuiltSkeleton) -> list[str]:
    spine = _bones_matching(skeleton, ("spine", "chest", "torso", "body"))
    if spine:
        return spine
    return [name for name in skeleton.names if skeleton.parent_of(name) == skeleton.node_order[0]]


def _breathe(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    amplitude = float(params["amplitude"])
    cycles = float(params["cycles"])
    bones = _spine_bones(skeleton)
    functions: dict[str, Callable[[float], Delta]] = {}
    for index, name in enumerate(bones):
        phase = index * 0.45

        def make(bone_phase: float) -> Callable[[float], Delta]:
            def evaluate(t: float) -> Delta:
                pulse = math.sin(math.tau * cycles * t / max(duration, 1e-9) + bone_phase)
                return Delta(
                    scale=np.array(
                        [1.0 + amplitude * pulse, 1.0 + amplitude * pulse, 1.0 + amplitude * pulse]
                    )
                )

            return evaluate

        functions[name] = make(phase)
    return functions


def _gait(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    stride = float(params["stride"])
    bob = float(params["bob"])
    chains = _locomotion_chains(recipe)
    functions: dict[str, Callable[[float], Delta]] = {}
    for chain_index, chain in enumerate(chains):
        phase = math.tau * chain_index / max(len(chains), 1)
        for bone_index, bone in enumerate(chain):
            if bone not in skeleton.parents:
                continue

            def make(bone_phase: float, depth: int) -> Callable[[float], Delta]:
                def evaluate(t: float) -> Delta:
                    wave = math.sin(math.tau * t / max(duration, 1e-9) + bone_phase)
                    angle = stride * wave * (0.55 if depth == 0 else 1.0)
                    rotation = quat_from_axis_angle(np.array([1.0, 0.0, 0.0]), angle)
                    return Delta(rotation=rotation)

                return evaluate

            functions[bone] = make(phase + 0.35 * bone_index, bone_index)
    root = skeleton.node_order[0]

    def root_bob(t: float) -> Delta:
        offset = bob * math.sin(2.0 * math.tau * t / max(duration, 1e-9))
        return Delta(translation=np.array([0.0, offset, 0.0]))

    functions[root] = root_bob
    return functions


def _hover_bob(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    amplitude = float(params["amplitude"])
    cycles = float(params["cycles"])
    root = skeleton.node_order[0]

    def evaluate(t: float) -> Delta:
        offset = amplitude * math.sin(math.tau * cycles * t / max(duration, 1e-9))
        tilt = 0.12 * amplitude * math.sin(math.tau * cycles * t / max(duration, 1e-9) + 0.7)
        return Delta(
            translation=np.array([0.0, offset, 0.0]),
            rotation=quat_from_axis_angle(np.array([0.0, 0.0, 1.0]), tilt),
        )

    return {root: evaluate}


def _recoil(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    amplitude = float(params["amplitude"])
    decay = float(params["decay"])
    root = skeleton.node_order[0]
    spine = _spine_bones(skeleton)[:2] or [root]

    def impulse(t: float) -> float:
        envelope = math.exp(-decay * t / max(duration, 1e-9))
        return amplitude * envelope * math.sin(math.pi * _clamp01(t / max(duration, 1e-9)))

    def root_eval(t: float) -> Delta:
        value = impulse(t)
        return Delta(
            translation=np.array([0.0, 0.0, value]),
            rotation=quat_from_axis_angle(np.array([1.0, 0.0, 0.0]), -value * 1.5),
        )

    functions: dict[str, Callable[[float], Delta]] = {root: root_eval}
    for index, bone in enumerate(spine):
        if bone == root:
            continue

        def make(scale: float) -> Callable[[float], Delta]:
            def evaluate(t: float) -> Delta:
                return Delta(
                    rotation=quat_from_axis_angle(
                        np.array([1.0, 0.0, 0.0]), -impulse(t) * 1.2 * scale
                    )
                )

            return evaluate

        functions[bone] = make(1.0 + 0.2 * index)
    return functions


def _telegraph_attack(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    windup = float(params["windup"])
    strike = float(params["strike"])
    recovery = float(params["recovery"])
    reach = float(params["reach"])
    chain = _attack_chain(recipe, skeleton)
    root = skeleton.node_order[0]
    impact_start = windup
    impact_end = windup + strike

    def attack_curve(t: float) -> float:
        if t < impact_start:
            return -1.0 * _smoothstep(t / max(windup, 1e-9))
        if t < impact_end:
            return -1.0 + 2.0 * _smoothstep((t - impact_start) / max(strike, 1e-9))
        return 1.0 - _smoothstep((t - impact_end) / max(recovery, 1e-9))

    functions: dict[str, Callable[[float], Delta]] = {}
    for index, bone in enumerate(chain):
        if bone not in skeleton.parents:
            continue

        def make(depth: int) -> Callable[[float], Delta]:
            def evaluate(t: float) -> Delta:
                angle = attack_curve(t) * (0.65 if depth == 0 else 0.9)
                return Delta(rotation=quat_from_axis_angle(np.array([1.0, 0.0, 0.0]), angle))

            return evaluate

        functions[bone] = make(index)

    def root_eval(t: float) -> Delta:
        forward = -reach * 0.15 * max(0.0, attack_curve(t))
        return Delta(translation=np.array([0.0, 0.0, forward]))

    functions[root] = root_eval
    return functions


def _death_collapse(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    collapse = float(params["collapse"])
    root = skeleton.node_order[0]
    spine = _spine_bones(skeleton)

    def progress(t: float) -> float:
        return _smoothstep(t / max(duration, 1e-9)) * collapse

    def root_eval(t: float) -> Delta:
        amount = progress(t)
        return Delta(
            translation=np.array([0.0, -0.45 * amount, 0.0]),
            rotation=quat_from_axis_angle(np.array([1.0, 0.0, 0.0]), -1.35 * amount),
        )

    functions: dict[str, Callable[[float], Delta]] = {root: root_eval}
    for index, bone in enumerate(spine):
        if bone == root:
            continue

        def make(depth: int) -> Callable[[float], Delta]:
            def evaluate(t: float) -> Delta:
                amount = progress(t)
                return Delta(
                    rotation=quat_from_axis_angle(
                        np.array([1.0, 0.0, 0.0]), -0.45 * amount * (1.0 + 0.15 * depth)
                    )
                )

            return evaluate

        functions[bone] = make(index)
    return functions


REGISTRY: dict[str, GeneratorSpec] = {
    "breathe": GeneratorSpec(
        name="breathe",
        defaults={"amplitude": 0.04, "cycles": 1.0},
        types={"amplitude": (int, float), "cycles": (int, float)},
        factory=_breathe,
    ),
    "gait": GeneratorSpec(
        name="gait",
        defaults={"stride": 0.35, "duty": 0.6, "bob": 0.02},
        types={"stride": (int, float), "duty": (int, float), "bob": (int, float), "legs": list},
        factory=_gait,
    ),
    "hover-bob": GeneratorSpec(
        name="hover-bob",
        defaults={"amplitude": 0.08, "cycles": 1.0},
        types={"amplitude": (int, float), "cycles": (int, float)},
        factory=_hover_bob,
    ),
    "recoil": GeneratorSpec(
        name="recoil",
        defaults={"amplitude": 0.18, "decay": 8.0},
        types={"amplitude": (int, float), "decay": (int, float)},
        factory=_recoil,
    ),
    "telegraph-attack": GeneratorSpec(
        name="telegraph-attack",
        defaults={"windup": 0.4, "strike": 0.15, "recovery": 0.35, "reach": 1.2},
        types={
            "windup": (int, float),
            "strike": (int, float),
            "recovery": (int, float),
            "reach": (int, float),
        },
        factory=_telegraph_attack,
    ),
    "death-collapse": GeneratorSpec(
        name="death-collapse",
        defaults={"collapse": 0.9},
        types={"collapse": (int, float)},
        factory=_death_collapse,
    ),
}

GENERATOR_NAMES: tuple[str, ...] = tuple(REGISTRY)


def normalize_clip_params(clip: Clip) -> dict[str, Any]:
    """Merge generator defaults with declared parameters; reject unknown keys."""
    spec = REGISTRY.get(clip.generator)
    if spec is None:
        from beastforge.model.errors import BeastforgeError

        raise BeastforgeError(
            "clip-unknown-generator",
            f"Clip {clip.name!r} selects unknown generator {clip.generator!r}.",
            location={"path": f"clips[{clip.name}].generator"},
            expected="one of: " + ", ".join(GENERATOR_NAMES),
            actual=clip.generator,
            remedy="Choose a generator from the closed registry.",
        )
    params = dict(spec.defaults)
    for key, value in clip.params.items():
        if key not in spec.types:
            from beastforge.model.errors import BeastforgeError

            raise BeastforgeError(
                "clip-param-invalid",
                f"Clip {clip.name!r} generator {clip.generator!r} "
                f"does not accept parameter {key!r}.",
                location={"path": f"clips[{clip.name}].params.{key}"},
                expected="one of: " + ", ".join(sorted(spec.types)),
                actual=key,
                remedy="Remove the parameter or use a documented generator parameter.",
            )
        expected = spec.types[key]
        if expected is list:
            if not isinstance(value, list):
                raise _bad_param(clip, key, value, "list")
        elif (
            not isinstance(value, expected)
            or isinstance(value, bool)
            and isinstance(expected, tuple)
            and float not in [t for t in expected if t is not bool]
        ):
            raise _bad_param(clip, key, value, str(expected))
        params[key] = value
    return params


def _bad_param(clip: Clip, key: str, value: Any, expected: str):
    from beastforge.model.errors import BeastforgeError

    return BeastforgeError(
        "clip-param-invalid",
        f"Clip {clip.name!r} parameter {key!r} has invalid value {value!r}.",
        location={"path": f"clips[{clip.name}].params.{key}"},
        expected=expected,
        actual=value,
        remedy="Use a value of the documented type.",
    )


def check_clip_params(clip: Clip, *, recipe_label: str = "") -> list[ValidationFinding]:
    """Return findings for an unknown generator or invalid generator parameter."""
    findings: list[ValidationFinding] = []
    spec = REGISTRY.get(clip.generator)
    if spec is None:
        findings.append(
            ValidationFinding(
                code="clip-unknown-generator",
                location={"recipe": recipe_label, "path": f"clips[{clip.name}].generator"},
                message=f"Clip {clip.name!r} selects unknown generator {clip.generator!r}.",
                expected="one of: " + ", ".join(GENERATOR_NAMES),
                actual=clip.generator,
                remedy="Choose a generator from the closed registry.",
            )
        )
        return findings
    for key, value in clip.params.items():
        if key not in spec.types:
            findings.append(
                ValidationFinding(
                    code="clip-param-invalid",
                    location={"recipe": recipe_label, "path": f"clips[{clip.name}].params.{key}"},
                    message=f"Generator {clip.generator!r} does not accept parameter {key!r}.",
                    expected="one of: " + ", ".join(sorted(spec.types)),
                    actual=key,
                    remedy="Remove the parameter or use a documented generator parameter.",
                )
            )
            continue
        expected = spec.types[key]
        valid = isinstance(value, expected)
        if expected is list:
            valid = isinstance(value, list)
        elif isinstance(expected, tuple) and bool in expected:
            valid = (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                or isinstance(value, bool)
            )
        if not valid:
            findings.append(
                ValidationFinding(
                    code="clip-param-invalid",
                    location={"recipe": recipe_label, "path": f"clips[{clip.name}].params.{key}"},
                    message=f"Clip {clip.name!r} parameter {key!r} has invalid value {value!r}.",
                    expected=str(expected),
                    actual=value,
                    remedy="Use a value of the documented type.",
                )
            )
    return findings


def build_animation(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    clip: Clip,
    params: dict[str, Any],
    duration: float,
    loop: bool,
) -> dict[str, Callable[[float], Delta]]:
    """Build the per-joint time functions for one clip."""
    spec = REGISTRY[clip.generator]
    return spec.factory(recipe, skeleton, params, duration, loop)
