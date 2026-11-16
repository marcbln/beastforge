"""Torso ring shells bound along the spine.

A shell is the same construction as a swept solid with a wider, possibly
elliptical cross-section. Both are capped, because a closed part is the library
contract (there is no open-surface escape hatch).
"""

from __future__ import annotations

from beastforge.geometry.sweep import SurfaceGeometry, sweep_surface
from beastforge.model.recipe import Surface
from beastforge.rig.skeleton import BuiltSkeleton


def build_torso_shell(surface: Surface, skeleton: BuiltSkeleton, seed: str) -> SurfaceGeometry:
    """Build a closed shell by sweeping a capped ring along the declared bones."""
    return sweep_surface(surface, skeleton, seed, caps=True)
