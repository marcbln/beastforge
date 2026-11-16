"""Manifest, generation-report, and showroom-report models.

These models mirror ``specs/001-procedural-creature-generator/contracts/schema``
exactly (``additionalProperties: false`` -> ``extra="forbid"``). The manifest is
the consumer contract; the reports are the CLI's own machine surface.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GeneratorName = Literal[
    "breathe",
    "gait",
    "hover-bob",
    "recoil",
    "telegraph-attack",
    "death-collapse",
    "baseline",
]
Scalar = str | int | float | bool | None


class Strict(BaseModel):
    """Base model matching a closed JSON object."""

    model_config = ConfigDict(extra="forbid")


class Vec3(Strict):
    """A three-component vector serialized as a JSON array."""

    pass


class ManifestCreature(Strict):
    name: str
    category: Literal["boss", "quadruped", "swarm", "other"]
    description: str


class ManifestProvenance(Strict):
    recipePath: str
    recipeSha256: str
    recipeVersion: str
    resolvedParams: dict[str, Scalar]
    toolVersion: str
    texforgeVersion: str


class Bounds(Strict):
    min: list[float]
    max: list[float]


class ManifestJoint(Strict):
    name: str
    parent: str | None


class ManifestSkeleton(Strict):
    root: str
    joints: list[ManifestJoint]


class ManifestClip(Strict):
    name: str
    duration: float
    loop: bool
    generator: GeneratorName
    source: Literal["authored", "automatic"] = "authored"


class ManifestControlRange(Strict):
    min: float
    max: float


class ManifestControl(Strict):
    address: str
    name: str
    joint: str
    axis: list[float]
    mode: Literal["rotation", "translation"]
    unbounded: bool
    range: ManifestControlRange | None = None
    default: float
    units: Literal["deg", "m"]


class ManifestPart(Strict):
    name: str
    preset: str
    presetVersion: str
    presetSha256: str
    family: Literal["organic", "mechanical", "vehicle"]
    controls: list[ManifestControl] = Field(default_factory=list)


class ManifestEvent(Strict):
    clip: str
    time: float
    name: str


class ManifestSocket(Strict):
    name: str
    target: str
    offset: list[float]


class ManifestVolume(Strict):
    name: str
    role: Literal["hit", "weak-point", "collision"]
    center: list[float]
    extents: list[float]
    bone: str | None = None


class ManifestPhase(Strict):
    name: str
    threshold: float


class ManifestTexture(Strict):
    recipe: str
    params: dict[str, Scalar]
    size: str
    sha256: str


class ManifestMaterial(Strict):
    name: str
    slot: Literal["baseColor"]
    texture: ManifestTexture
    metallic: float
    roughness: float


class Playback(Strict):
    eventTimeScaling: Literal["proportional"]
    warning: str


class ManifestBudgets(Strict):
    vertices: int
    bones: int
    triangles: int


class Manifest(Strict):
    """The shipped sidecar gameplay contract (ADR 261114-1)."""

    schemaVersion: str
    toolVersion: str
    generator: Literal["beastforge"] = "beastforge"
    creature: ManifestCreature
    provenance: ManifestProvenance
    units: Literal["m"] = "m"
    upAxis: Literal["Y"] = "Y"
    forwardAxis: Literal["-Z"] = "-Z"
    bounds: Bounds
    suggestedScale: float
    skeleton: ManifestSkeleton
    clips: list[ManifestClip]
    parts: list[ManifestPart] = Field(default_factory=list)
    events: list[ManifestEvent]
    sockets: list[ManifestSocket]
    volumes: list[ManifestVolume]
    phases: list[ManifestPhase]
    materials: list[ManifestMaterial]
    playback: Playback
    budgets: ManifestBudgets


class ReportFile(Strict):
    path: str
    sha256: str | None = None
    bytes: int | None = None


class ReportTexture(Strict):
    name: str
    sha256: str
    width: int
    height: int
    recipe: str | None = None


class ReportOutputs(Strict):
    glb: ReportFile
    manifest: ReportFile
    textures: list[ReportTexture]


class ReportInventoryEvent(Strict):
    clip: str
    time: float
    name: str


class ReportInventory(Strict):
    clips: list[str]
    events: list[ReportInventoryEvent]
    sockets: list[str]
    volumes: list[str]
    phases: list[str]


class ReportProvenance(Strict):
    recipe: str
    recipe_sha256: str
    tool_version: str


class GenerationReport(Strict):
    """``render --json`` (data-model §15)."""

    schema_version: Literal["1"] = "1"
    tool_version: str
    status: Literal["ok"] = "ok"
    dry_run: bool
    outputs: ReportOutputs
    inventory: ReportInventory
    effective_params: dict[str, Scalar]
    provenance: ReportProvenance
    warnings: list[str] = Field(default_factory=list)
    timing_ms: float | None = None


class ShowroomFrame(Strict):
    view: Literal["front", "three-quarter", "side", "rear"]
    pose: Literal["rest", "extreme-bend"]
    path: str
    sha256: str


class ShowroomSkin(Strict):
    influences_one: int
    influences_two: int
    min_weight_sum: float
    max_weight_sum: float


class ShowroomJoints(Strict):
    count: int
    names: list[str]


class ShowroomCounts(Strict):
    vertices: int
    triangles: int
    surfaces: int


class ShowroomStructuralClip(Strict):
    name: str
    duration: float
    loop: bool
    generator: str


class ShowroomStructuralEvent(Strict):
    clip: str
    name: str
    time: float


class ShowroomStructural(Strict):
    joints: ShowroomJoints
    clips: list[ShowroomStructuralClip]
    events: list[ShowroomStructuralEvent]
    skin: ShowroomSkin
    bounds: Bounds
    counts: ShowroomCounts


class ShowroomMetrics(Strict):
    max_pixel_delta: int
    changed_pixel_ratio: float


class ShowroomComparison(Strict):
    status: Literal["pass", "fail", "no-baseline"]
    differing_frames: list[str]
    metrics: ShowroomMetrics | None = None


class ShowroomCreatureResult(Strict):
    name: str
    frames: list[ShowroomFrame]
    structural: ShowroomStructural
    comparison: ShowroomComparison


class ShowroomTolerance(Strict):
    per_pixel_threshold: int
    changed_pixel_ratio: float


class ShowroomReport(Strict):
    """``showroom --json`` (data-model §17)."""

    schema_version: Literal["1"] = "1"
    tool_version: str
    status: Literal["ok", "failed"]
    mode: Literal["compare", "accept"]
    tolerance: ShowroomTolerance
    creatures: list[ShowroomCreatureResult]


class ManifestVersionError(ValueError):
    """Raised when a manifest cannot be read by this consumer."""


REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "schemaVersion",
    "toolVersion",
    "generator",
    "creature",
    "provenance",
    "units",
    "upAxis",
    "forwardAxis",
    "bounds",
    "suggestedScale",
    "skeleton",
    "clips",
    "events",
    "sockets",
    "volumes",
    "phases",
    "materials",
    "playback",
    "budgets",
)


def read_manifest_compatible(payload: dict[str, object]) -> dict[str, object]:
    """Read a manifest major-strict/minor-tolerant, ignoring unknown fields.

    This is the consumer contract (FR-029, SC-010), deliberately separate from
    the strict producer-side :class:`Manifest` model.
    """
    import re

    version = payload.get("schemaVersion")
    if not isinstance(version, str) or not re.match(r"^\d+\.\d+$", version):
        raise ManifestVersionError("manifest-schema-unsupported: schemaVersion must be MAJOR.MINOR")
    major = version.split(".", 1)[0]
    if major != "1":
        raise ManifestVersionError(
            f"manifest-schema-unsupported: major version {major} is not supported"
        )
    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in payload]
    if missing:
        raise ManifestVersionError(
            "manifest-schema-invalid: missing required fields: " + ", ".join(missing)
        )
    return payload


def report_json(report: GenerationReport) -> dict[str, object]:
    """Serialize a generation report for the published schema.

    Optional file hashes and byte counts are omitted in ``--dry-run`` (the
    schema allows absence, not ``null``).
    """
    payload = report.model_dump(mode="json")
    outputs = payload.get("outputs", {})
    for key in ("glb", "manifest"):
        file_payload = outputs.get(key, {})
        for field in ("sha256", "bytes"):
            if file_payload.get(field) is None:
                file_payload.pop(field, None)
    return payload


def showroom_json(report: ShowroomReport) -> dict[str, object]:
    """Serialize a showroom report, omitting an absent comparison metrics block."""
    payload = report.model_dump(mode="json")
    for creature in payload.get("creatures", []):
        comparison = creature.get("comparison", {})
        if comparison.get("metrics") is None:
            comparison.pop("metrics", None)
    return payload
