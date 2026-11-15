"""Rigid part emitter: one bone, weight 1.0, no deformation (FR-016)."""

from __future__ import annotations

from beastforge.geometry.sweep import SurfaceGeometry, rigid_surface
from beastforge.model.recipe import Surface
from beastforge.rig.skeleton import BuiltSkeleton


def build_rigid_part(surface: Surface, skeleton: BuiltSkeleton, seed: str) -> SurfaceGeometry:
    """Build a capped rigid part bound to exactly one bone."""
    return rigid_surface(surface, skeleton, seed)
