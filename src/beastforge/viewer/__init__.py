"""Read-only WebGL library viewer.

The viewer discovers creatures and delivers their already-generated packages;
it never re-derives gameplay facts, regenerates geometry, or applies parameter
overrides. Every creature fact shown in the browser comes from the authoritative
sidecar manifest (ADR 261114-1).
"""

from __future__ import annotations

__all__ = ["__version__"]

from beastforge import __version__  # noqa: F401
