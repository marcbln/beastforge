"""Pure build orchestration: recipe + params -> skeleton, mesh, baked clips.

No filesystem, environment, or texforge access happens here, so golden tests can
exercise the build core directly (``architecture:separation``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from beastforge.anim.bake import BakedClip, bake_clips
from beastforge.geometry.mesh import Mesh, append_surface
from beastforge.geometry.rigid import build_rigid_part
from beastforge.geometry.shell import build_torso_shell
from beastforge.geometry.sweep import sweep_surface
from beastforge.model.parts import ResolvedPart
from beastforge.model.recipe import Recipe
from beastforge.params import resolve_params
from beastforge.parts.resolve import resolved_autos
from beastforge.rig.skeleton import BuiltSkeleton, build_skeleton
from beastforge.rng import build_digest, run_seed


@dataclass
class BuiltCreature:
    """Everything the export layer needs, before textures are rendered."""

    recipe: Recipe
    document: dict[str, Any]
    recipe_path: str
    recipe_sha256: str
    resolved_params: dict[str, Any]
    seed: str
    skeleton: BuiltSkeleton
    mesh: Mesh
    clips: list[BakedClip]
    parts: list[ResolvedPart] | None = None


def _append(mesh: Mesh, surface, skeleton: BuiltSkeleton, seed: str) -> None:
    if surface.kind == "rigid-part":
        geometry = build_rigid_part(surface, skeleton, seed)
    elif surface.kind in {"torso-shell", "shell"}:
        geometry = build_torso_shell(surface, skeleton, seed)
    else:
        geometry = sweep_surface(surface, skeleton, seed, caps=True)
    append_surface(
        mesh,
        name=surface.name,
        positions=geometry.positions,
        uv=geometry.uv,
        joints=geometry.joints,
        weights=geometry.weights,
        indices=geometry.indices,
        material=surface.material,
    )


def build_mesh(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    seed: str,
    *,
    resolved_parts: list[ResolvedPart] | None = None,
) -> Mesh:
    """Construct and merge hand-authored surfaces then resolved part surfaces."""
    mesh = Mesh(
        positions=__import__("numpy").zeros((0, 3), dtype=float),
        normals=__import__("numpy").zeros((0, 3), dtype=float),
        uv=__import__("numpy").zeros((0, 2), dtype=float),
        joints=__import__("numpy").zeros((0, 4), dtype=__import__("numpy").uint16),
        weights=__import__("numpy").zeros((0, 4), dtype=float),
        indices=__import__("numpy").zeros((0, 3), dtype=__import__("numpy").uint32),
    )
    for surface in recipe.surfaces:
        _append(mesh, surface, skeleton, seed)
    for part in resolved_parts or []:
        _append(mesh, part.surface, skeleton, seed)
    return mesh


def preset_documents(resolved_parts: list[ResolvedPart] | None) -> list[dict[str, Any]]:
    """Return the unique pinned preset documents in canonical order."""
    if not resolved_parts:
        return []
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for part in resolved_parts:
        unique[(part.preset, part.preset_version)] = part.preset_document
    return [unique[key] for key in sorted(unique)]


def prepare(
    recipe: Recipe,
    *,
    document: dict[str, Any],
    recipe_path: str,
    overrides: dict[str, Any] | None = None,
    tool_version: str,
    resolved_parts: list[ResolvedPart] | None = None,
) -> BuiltCreature:
    """Resolve parameters, derive the seed, and build rig/mesh/clips."""
    resolution = resolve_params(
        recipe,
        overrides,
        recipe_label=recipe_path,
        strict=True,
    )
    digest = build_digest(document, preset_documents(resolved_parts))
    seed = run_seed(digest, resolution.values)
    skeleton = build_skeleton(recipe.skeleton)
    mesh = build_mesh(recipe, skeleton, seed, resolved_parts=resolved_parts)
    clips = bake_clips(
        recipe,
        skeleton,
        seed,
        autos=resolved_autos(resolved_parts or []),
    )
    return BuiltCreature(
        recipe=recipe,
        document=document,
        recipe_path=recipe_path,
        recipe_sha256=digest,
        resolved_params=resolution.values,
        seed=seed,
        skeleton=skeleton,
        mesh=mesh,
        clips=clips,
        parts=resolved_parts,
    )
