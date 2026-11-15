"""Torso ring shells bound along the spine (FR-015).

A torso is the same construction as a limb tube with a wider, possibly
elliptical cross-section; keeping one code path keeps skin weights and UVs
identical in behaviour and determinism.
"""

from __future__ import annotations

from beastforge.geometry.sweep import SurfaceGeometry, sweep_surface
from beastforge.model.recipe import Surface
from beastforge.rig.skeleton import BuiltSkeleton


def build_torso_shell(surface: Surface, skeleton: BuiltSkeleton, seed: str) -> SurfaceGeometry:
    """Build a torso shell as an open-ended sweep along the declared spine bones."""
    return sweep_surface(surface, skeleton, seed, caps=False)
