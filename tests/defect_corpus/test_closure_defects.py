"""Closure defects observed through the public validation gate (FR-001)."""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from beastforge.model.loader import load_recipe
from beastforge.pipeline import prepare
from beastforge.validation.gate import run_gate

ROOT = Path(__file__).resolve().parents[2]
TEXFORGE = ROOT.parent / "texforge" / "library"


@pytest.fixture(scope="module")
def built():
    recipe, document = load_recipe(ROOT / "library/quadruped/ridge-stalker.yaml")
    return prepare(recipe, document=document, recipe_path="ridge-stalker", tool_version="0.1.0")


def _codes(built, mutate) -> list[str]:
    mesh = copy.deepcopy(built.mesh)
    mutate(mesh)
    findings = run_gate(
        built.recipe,
        recipe_label="broken.yaml",
        document=built.document,
        skeleton=built.skeleton,
        mesh=mesh,
        texforge_root=TEXFORGE,
    )
    return [finding.code for finding in findings]


def _open_end(mesh) -> None:
    surface_range = mesh.surfaces[0]
    start = surface_range.index_offset
    end = start + surface_range.index_count
    mesh.indices = np.concatenate(
        [mesh.indices[:start], mesh.indices[start + 1 : end], mesh.indices[end:]]
    )
    surface_range.index_count -= 1
    for later in mesh.surfaces[1:]:
        later.index_offset -= 1


def _non_manifold(mesh) -> None:
    surface_range = mesh.surfaces[0]
    end = surface_range.index_offset + surface_range.index_count
    duplicate = mesh.indices[surface_range.index_offset : surface_range.index_offset + 1]
    mesh.indices = np.concatenate([mesh.indices[:end], duplicate, mesh.indices[end:]])
    surface_range.index_count += 1
    for later in mesh.surfaces[1:]:
        later.index_offset += 1


def _degenerate_cap(mesh) -> None:
    mesh.positions[1] = mesh.positions[0]


def _inward_winding(mesh) -> None:
    surface_range = mesh.surfaces[0]
    start = surface_range.index_offset
    end = start + surface_range.index_count
    indices = mesh.indices.copy()
    indices[start:end] = indices[start:end][:, [0, 2, 1]]
    mesh.indices = indices


def test_open_end_fails_with_surface_open(built) -> None:
    assert "surface-open" in _codes(built, _open_end)


def test_non_manifold_edge_fails(built) -> None:
    assert "surface-non-manifold" in _codes(built, _non_manifold)


def test_degenerate_cap_fails(built) -> None:
    assert "surface-degenerate" in _codes(built, _degenerate_cap)


def test_inward_winding_fails(built) -> None:
    assert "surface-winding-invalid" in _codes(built, _inward_winding)
