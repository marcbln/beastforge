"""Budget ceilings: measured values are a failure, never a warning (FR-028)."""

from __future__ import annotations

from beastforge.geometry.mesh import Mesh
from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Recipe
from beastforge.rig.skeleton import BuiltSkeleton
from beastforge.validation.common import finding


def check_budgets(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    mesh: Mesh,
    *,
    recipe_label: str,
) -> list[ValidationFinding]:
    """Compare measured bones/vertices/triangles against the declared ceilings."""
    findings: list[ValidationFinding] = []
    budgets = recipe.budgets
    measured = {
        "vertices": mesh.vertex_count,
        "bones": len(skeleton.names),
        "triangles": mesh.triangle_count,
    }
    declared = {
        "vertices": budgets.vertices,
        "bones": budgets.bones,
        "triangles": budgets.triangles,
    }
    for key in ("vertices", "bones", "triangles"):
        if measured[key] > declared[key]:
            findings.append(
                finding(
                    "budget-exceeded",
                    f"Measured {key} ({measured[key]}) exceed the declared "
                    f"budget ({declared[key]}).",
                    recipe=recipe_label,
                    path=f"budgets.{key}",
                    expected=f"<= {declared[key]}",
                    actual=measured[key],
                    remedy=f"Reduce {key} or raise budgets.{key} deliberately.",
                )
            )
    return findings
