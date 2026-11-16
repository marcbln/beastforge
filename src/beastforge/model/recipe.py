"""Pydantic v2 recipe models (the inert authoring contract).

The models forbid unknown keys at every level. Structural typing is deliberately
permissive for fields whose *semantic* rejection has a stable finding code
(surface mode, identifiers, ranges); the validation gate owns those checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from beastforge.model.parts import PartInstance

Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
Quat = Annotated[list[float], Field(min_length=4, max_length=4)]


class StrictModel(BaseModel):
    """Base model: reject unknown keys everywhere (research D6)."""

    model_config = ConfigDict(extra="forbid")


class Transform(StrictModel):
    """A bone's rest transform, relative to its parent."""

    translation: Vec3
    rotation: Quat
    scale: Vec3 = Field(default_factory=lambda: [1.0, 1.0, 1.0])


class Bone(StrictModel):
    """One named joint in the skeleton."""

    name: str
    parent: str | None
    rest: Transform


class Chain(StrictModel):
    """An ordered, contiguous parent-to-child run of bones."""

    name: str
    bones: Annotated[list[str], Field(min_length=1)]


class Skeleton(StrictModel):
    """The articulation hierarchy; the skeleton is declared before surfaces."""

    root: str
    bones: Annotated[list[Bone], Field(min_length=1)]
    chains: list[Chain] = Field(default_factory=list)


class Taper(StrictModel):
    """Linear radius multiplier from the start to the end of a sweep."""

    start: float
    end: float


class RadialNoise(StrictModel):
    """Seeded radial displacement applied during sweep construction."""

    amplitude: float = 0.0
    frequency: float = 1.0
    seed: int = 0


class Modifiers(StrictModel):
    """Deterministic silhouette modifiers (FR-019)."""

    taper: Taper | None = None
    twist: float = 0.0
    radial_noise: RadialNoise | None = None
    squash: Vec3 = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    scale: Vec3 = Field(default_factory=lambda: [1.0, 1.0, 1.0])


class RadiusProfile(StrictModel):
    """A linear radius profile along a surface."""

    start: float
    end: float


class Surface(StrictModel):
    """A skinned body region bound to bones at construction time."""

    name: str
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


class Material(StrictModel):
    """A reference to a texforge texture recipe (never a path)."""

    name: str
    texture: str
    params: dict[str, Any] = Field(default_factory=dict)
    size: str = "512x512"
    slot: str = "baseColor"
    metallic: float = 0.0
    roughness: float = 0.8


class Event(StrictModel):
    """A gameplay cue inside a clip; time is in seconds or integer 60 Hz ticks."""

    name: str
    time: float | None = None
    ticks: int | None = None


class Clip(StrictModel):
    """A clip declaration: one closed-registry generator plus timing metadata."""

    name: str
    generator: str
    duration: float | None = None
    ticks: int | None = None
    loop: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    events: list[Event] = Field(default_factory=list)


class Socket(StrictModel):
    """A named attachment point on a bone."""

    name: str
    bone: str
    offset: Vec3


class Volume(StrictModel):
    """A hit, weak-point, or collision proxy."""

    name: str
    role: str
    center: Vec3
    extents: Annotated[list[float], Field(min_length=3, max_length=3)]
    bone: str | None = None


class Phase(StrictModel):
    """A named boss-phase threshold, as a fraction of max health."""

    name: str
    threshold: float


class Orientation(StrictModel):
    """The only accepted orientation in v1."""

    up: str = "Y"
    forward: str = "-Z"


class Meta(StrictModel):
    """Catalog identity for one creature."""

    name: str
    description: str
    category: Literal["boss", "quadruped", "swarm", "other"]
    tags: list[str] = Field(default_factory=list)
    author: str | None = None
    tested_with: str
    version: str
    units: str = "m"
    orientation: Orientation = Field(default_factory=Orientation)


class Param(StrictModel):
    """One declared recipe knob."""

    name: str
    type: Literal["int", "float", "bool", "enum", "string"]
    default: Any
    min: float | None = None
    max: float | None = None
    values: list[Any] | None = None
    unit: Literal["m", "rad", "deg", "s", "count", "ratio"] | None = None
    description: str


class Budgets(StrictModel):
    """Measured-value ceilings; exceeding one is a gate failure (FR-028)."""

    vertices: int = 20000
    bones: int = 64
    triangles: int = 60000
    max_clip_ticks: int = 600


class Recipe(StrictModel):
    """The complete declarative description of one creature or prop.

    ``surfaces`` and ``clips`` may be empty: an asset can be assembled entirely
    from part presets, and an anatomy-neutral asset may have no authored clips.
    At least one of ``surfaces`` / ``parts`` is required, enforced by the gate.
    """

    meta: Meta
    params: list[Param] = Field(default_factory=list)
    budgets: Budgets = Field(default_factory=Budgets)
    skeleton: Skeleton
    surfaces: list[Surface] = Field(default_factory=list)
    parts: list[PartInstance] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)
    clips: list[Clip] = Field(default_factory=list)
    sockets: list[Socket] = Field(default_factory=list)
    volumes: Annotated[list[Volume], Field(min_length=1)]
    phases: list[Phase] = Field(default_factory=list)


class ResolvedRecipe(StrictModel):
    """The pure, hashable build input (data-model §12)."""

    recipe: Recipe
    recipe_path: str
    recipe_sha256: str
    resolved_params: dict[str, Any]
    seed: str
    tool_version: str
