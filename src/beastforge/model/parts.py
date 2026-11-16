"""Part preset, instance, control, and automatic-behaviour models.

Presets are inert YAML data with ``@slot`` bone roles. A recipe part instance
binds those roles to real bones and may override parameters. The resolved models
carry concrete bone names and published control addresses.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from beastforge.model.recipe import Modifiers, RadiusProfile, Surface


class StrictModel(BaseModel):
    """Base model: reject unknown keys everywhere."""

    model_config = ConfigDict(extra="forbid")


Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]

CANONICAL_OVERRIDE_KEYS: tuple[str, ...] = (
    "radius-start",
    "radius-end",
    "rings",
    "segments",
    "blend",
    "taper-start",
    "taper-end",
    "twist",
    "noise-amplitude",
    "noise-frequency",
    "noise-seed",
    "squash-x",
    "squash-y",
    "squash-z",
    "scale-x",
    "scale-y",
    "scale-z",
)

INT_OVERRIDE_KEYS: frozenset[str] = frozenset({"rings", "segments", "noise-seed"})


class PresetSurface(StrictModel):
    """A surface template whose bone entries are ``@slot`` roles."""

    mode: str = "sweep"
    kind: str
    bones: Annotated[list[str], Field(min_length=1)]
    rigid_bone: str | None = None
    rings: int = 1
    segments: int = 1
    radius: RadiusProfile | Annotated[list[float], Field(min_length=1)]
    blend: float = 0.25
    modifiers: Modifiers = Field(default_factory=Modifiers)
    material: str | None = None


class PresetParam(StrictModel):
    """One declared, overridable preset parameter."""

    name: str
    type: Literal["float", "int"]
    min: float | None = None
    max: float | None = None
    unit: Literal["m", "deg", "ratio", "count"] | None = None
    description: str


class ControlRange(StrictModel):
    """A bounded control's inclusive limits."""

    min: float
    max: float


class PresetControl(StrictModel):
    """A named articulation channel declared on a preset or instance."""

    name: str
    joint: str
    axis: Vec3
    mode: Literal["rotation", "translation"]
    range: ControlRange | None = None
    unbounded: bool | None = None
    default: float
    units: Literal["deg", "m"]


class BreatheAuto(StrictModel):
    """A uniform scale pulse on one joint."""

    kind: Literal["breathe"]
    name: str
    joint: str
    amplitude: float
    period: float
    phase: float = 0.0


class BobAuto(StrictModel):
    """A translation oscillation along an axis."""

    kind: Literal["bob"]
    name: str
    joint: str
    axis: Vec3
    amplitude: float
    period: float
    phase: float = 0.0


class SwayAuto(StrictModel):
    """A rotation oscillation about an axis."""

    kind: Literal["sway"]
    name: str
    joint: str
    axis: Vec3
    amplitude: float
    period: float
    phase: float = 0.0


class RotateAuto(StrictModel):
    """An unbounded constant rotation about an axis."""

    kind: Literal["rotate"]
    name: str
    joint: str
    axis: Vec3
    rate: float
    phase: float = 0.0


AutoBehaviour = Annotated[
    BreatheAuto | BobAuto | SwayAuto | RotateAuto,
    Field(discriminator="kind"),
]
ResolvedAuto = AutoBehaviour


class PartInstance(StrictModel):
    """A recipe-side binding of one immutable preset version to real bones."""

    name: str
    preset: str
    preset_version: str
    bind: dict[str, str] = Field(default_factory=dict)
    overrides: dict[str, float | int] = Field(default_factory=dict)
    material: str | None = None
    controls: list[PresetControl] = Field(default_factory=list)
    auto: list[AutoBehaviour] = Field(default_factory=list)


class PartPreset(StrictModel):
    """One immutable preset version loaded from ``library/parts``."""

    name: str
    family: Literal["organic", "mechanical", "vehicle"]
    version: str
    description: str
    surface: PresetSurface
    params: list[PresetParam] = Field(default_factory=list)
    controls: list[PresetControl] = Field(default_factory=list)
    auto: list[AutoBehaviour] = Field(default_factory=list)
    path: str = ""
    sha256: str = ""


class ControlChannel(StrictModel):
    """A resolved control channel with a concrete joint and published address."""

    address: str
    name: str
    joint: str
    axis: Vec3
    mode: Literal["rotation", "translation"]
    unbounded: bool
    range: ControlRange | None = None
    default: float
    units: Literal["deg", "m"]


class ResolvedPart(StrictModel):
    """A preset instance resolved to concrete geometry, controls, and motion."""

    name: str
    preset: str
    preset_version: str
    preset_sha256: str
    family: Literal["organic", "mechanical", "vehicle"]
    surface: Surface
    controls: list[ControlChannel] = Field(default_factory=list)
    auto: list[ResolvedAuto] = Field(default_factory=list)
    preset_document: dict[str, Any] = Field(default_factory=dict, exclude=True)


__all__ = [
    "AutoBehaviour",
    "BobAuto",
    "BreatheAuto",
    "CANONICAL_OVERRIDE_KEYS",
    "ControlChannel",
    "ControlRange",
    "INT_OVERRIDE_KEYS",
    "PartInstance",
    "PartPreset",
    "PresetControl",
    "PresetParam",
    "PresetSurface",
    "ResolvedAuto",
    "ResolvedPart",
    "RotateAuto",
    "SwayAuto",
]


def _register_recipe_part_model() -> None:
    """Resolve ``Recipe.parts`` without a module-level circular import."""
    from beastforge.model import recipe as recipe_module

    recipe_module.Recipe.model_rebuild(
        _types_namespace={**vars(recipe_module), "PartInstance": PartInstance}
    )


_register_recipe_part_model()

