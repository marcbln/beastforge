"""Preset, binding, control, and automatic-motion validation findings."""

from __future__ import annotations

from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Recipe
from beastforge.parts.registry import PresetRegistry
from beastforge.parts.resolve import PartsResolution, resolve_parts
from beastforge.validation.common import finding


def check_parts(
    recipe: Recipe,
    registry: PresetRegistry,
    *,
    recipe_label: str,
) -> PartsResolution:
    """Resolve every part and surface all resolution findings."""
    return resolve_parts(recipe, registry, recipe_label=recipe_label)


def check_geometry_present(recipe: Recipe, *, recipe_label: str) -> list[ValidationFinding]:
    """Require at least one hand-authored surface or one resolved part instance."""
    if recipe.surfaces or recipe.parts:
        return []
    return [
        finding(
            "recipe-empty-geometry",
            "Recipe declares neither surfaces nor parts.",
            recipe=recipe_label,
            path="surfaces",
            expected="at least one surface or part instance",
            actual={"surfaces": len(recipe.surfaces), "parts": len(recipe.parts)},
            remedy="Add a surfaces[] entry or a parts[] entry with a pinned preset.",
        )
    ]


__all__ = ["check_geometry_present", "check_parts"]
