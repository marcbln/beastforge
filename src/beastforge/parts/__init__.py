"""Reusable, anatomy-neutral part presets and pure recipe resolution.

The preset registry is the filesystem adapter; override application and recipe
resolution are pure functions so builds stay deterministic and testable.
"""

from __future__ import annotations
