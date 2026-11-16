"""Canonical partial override application on a deep-copied preset surface.

Overrides are a closed, flat vocabulary. Omitted keys keep the preset value; a
nested object (radius, modifiers, taper, noise) is never replaced wholesale.
"""

from __future__ import annotations

import difflib
import math

from beastforge.model.findings import ValidationFinding
from beastforge.model.parts import (
    CANONICAL_OVERRIDE_KEYS,
    INT_OVERRIDE_KEYS,
    PresetParam,
    PresetSurface,
)
from beastforge.model.recipe import RadiusProfile
from beastforge.validation.common import finding


def _number(value: float | int, *, key: str, param: PresetParam) -> tuple[float | int, str | None]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value, "part-override-type"
    if not math.isfinite(float(value)):
        return value, "part-override-type"
    if param.type == "int" and not isinstance(value, int):
        return value, "part-override-type"
    if param.min is not None and float(value) < float(param.min):
        return value, "part-override-range"
    if param.max is not None and float(value) > float(param.max):
        return value, "part-override-range"
    return value, None


def _apply_key(surface: PresetSurface, key: str, value: float | int) -> bool:
    if key == "radius-start":
        if isinstance(surface.radius, RadiusProfile):
            surface.radius.start = float(value)
        else:
            surface.radius[0] = float(value)
        return True
    if key == "radius-end":
        if isinstance(surface.radius, RadiusProfile):
            surface.radius.end = float(value)
        else:
            surface.radius[-1] = float(value)
        return True
    if key == "rings":
        surface.rings = int(value)
        return True
    if key == "segments":
        surface.segments = int(value)
        return True
    if key == "blend":
        surface.blend = float(value)
        return True
    if key == "taper-start":
        if surface.modifiers.taper is None:
            return False
        surface.modifiers.taper.start = float(value)
        return True
    if key == "taper-end":
        if surface.modifiers.taper is None:
            return False
        surface.modifiers.taper.end = float(value)
        return True
    if key == "twist":
        surface.modifiers.twist = float(value)
        return True
    if key in {"noise-amplitude", "noise-frequency", "noise-seed"}:
        if surface.modifiers.radial_noise is None:
            return False
        if key == "noise-amplitude":
            surface.modifiers.radial_noise.amplitude = float(value)
        elif key == "noise-frequency":
            surface.modifiers.radial_noise.frequency = float(value)
        else:
            surface.modifiers.radial_noise.seed = int(value)
        return True
    if key.startswith("squash-"):
        index = {"x": 0, "y": 1, "z": 2}[key[-1]]
        surface.modifiers.squash[index] = float(value)
        return True
    if key.startswith("scale-"):
        index = {"x": 0, "y": 1, "z": 2}[key[-1]]
        surface.modifiers.scale[index] = float(value)
        return True
    return False


def apply_overrides(
    surface: PresetSurface,
    overrides: dict[str, float | int],
    params: list[PresetParam],
    *,
    part_name: str,
    recipe_label: str,
) -> tuple[PresetSurface, list[ValidationFinding]]:
    """Return a deep copy with every declared override applied plus findings."""
    result = surface.model_copy(deep=True)
    findings: list[ValidationFinding] = []
    declared = {param.name: param for param in params}
    for key in sorted(overrides):
        value = overrides[key]
        path = f"parts[{part_name}].overrides.{key}"
        param = declared.get(key)
        if param is None:
            suggestion = next(
                iter(difflib.get_close_matches(key, list(declared), n=1)), None
            )
            findings.append(
                finding(
                    "part-override-unknown",
                    f"Part {part_name!r} overrides undeclared key {key!r}.",
                    recipe=recipe_label,
                    path=path,
                    expected="one of the preset's declared params: "
                    + ", ".join(sorted(declared)),
                    actual=key,
                    remedy="Declare the parameter in the preset or remove the override.",
                    suggestion=suggestion,
                )
            )
            continue
        checked, code = _number(value, key=key, param=param)
        if code is not None:
            findings.append(
                finding(
                    code,
                    f"Override {key!r} on part {part_name!r} is not a valid {param.type}.",
                    recipe=recipe_label,
                    path=path,
                    expected={"type": param.type, "min": param.min, "max": param.max},
                    actual=value,
                    remedy="Use a finite value of the declared type inside its range.",
                )
            )
            continue
        if not _apply_key(result, key, checked):
            findings.append(
                finding(
                    "part-override-unknown",
                    f"Preset surface cannot apply override {key!r}.",
                    recipe=recipe_label,
                    path=path,
                    expected="a preset surface with the matching field",
                    actual=key,
                    remedy="Only expose parameters the preset surface actually supports.",
                )
            )
    return result, findings


__all__ = ["CANONICAL_OVERRIDE_KEYS", "INT_OVERRIDE_KEYS", "apply_overrides"]
