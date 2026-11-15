"""Validation finding model and the closed v1 finding-code vocabulary."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FindingLocation(BaseModel):
    """Where a finding applies: a recipe path and a JSON-pointer-ish field path."""

    model_config = ConfigDict(extra="forbid")

    recipe: str = ""
    path: str = ""


class ValidationFinding(BaseModel):
    """One gate result (FR-034, data-model §16)."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["error", "warning"] = "error"
    location: FindingLocation = Field(default_factory=FindingLocation)
    message: Annotated[str, Field(min_length=1)]
    expected: Any = None
    actual: Any = None
    remedy: Annotated[str, Field(min_length=1)]
    suggestion: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Return the schema-shaped mapping, dropping an absent suggestion."""
        payload = self.model_dump(mode="json")
        if payload.get("suggestion") is None:
            payload.pop("suggestion", None)
        return payload


FINDING_CODES: dict[str, tuple[str, ...]] = {
    "recipe": (
        "recipe-syntax",
        "recipe-executable-content",
        "recipe-unknown-field",
        "recipe-unknown-param",
        "recipe-param-type",
        "recipe-param-range",
        "recipe-name-invalid",
        "recipe-unknown-param-suggestion",
    ),
    "skeleton": (
        "skeleton-root-missing",
        "skeleton-root-multiple",
        "skeleton-parent-missing",
        "skeleton-cycle",
        "skeleton-duplicate-bone",
        "skeleton-unreachable-bone",
        "skeleton-degenerate-transform",
        "skeleton-inverted-transform",
        "skeleton-zero-length-bone",
        "chain-invalid",
        "chain-duplicate",
    ),
    "surfaces": (
        "surface-unsupported-mode",
        "surface-bone-missing",
        "surface-empty",
        "surface-self-intersection",
        "surface-winding-invalid",
    ),
    "skin": (
        "skin-weight-sum",
        "skin-too-many-influences",
        "skin-zero-weight",
        "skin-bind-pose-mismatch",
        "skin-rigid-multi-influence",
    ),
    "clips": (
        "clip-missing-core",
        "clip-duplicate",
        "clip-unknown-generator",
        "clip-nonpositive-duration",
        "clip-fractional-ticks",
        "clip-duration-over-budget",
        "clip-event-duplicate",
        "clip-event-negative-time",
        "clip-event-out-of-range",
        "clip-param-invalid",
    ),
    "hooks": (
        "volume-missing-hit",
        "volume-duplicate",
        "volume-role-invalid",
        "phase-duplicate",
        "phase-missing-for-boss",
        "phase-threshold-range",
        "socket-duplicate",
        "socket-target-missing",
    ),
    "materials": (
        "material-duplicate",
        "material-unresolved",
        "material-param-invalid",
        "material-size-invalid",
        "material-not-referenced",
        "material-render-failed",
    ),
    "budgets": ("budget-exceeded", "duplicate-name", "identifier-invalid"),
    "determinism": (
        "determinism-hazard",
        "manifest-dangling-reference",
        "manifest-core-clip-missing",
        "manifest-schema-invalid",
        "manifest-schema-unsupported",
    ),
}

ALL_FINDING_CODES: frozenset[str] = frozenset(
    code for group in FINDING_CODES.values() for code in group
)

CORE_CLIPS: tuple[str, ...] = ("idle", "locomotion", "attack", "hurt", "death")
