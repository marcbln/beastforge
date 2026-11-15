"""Swept-surface construction invariants."""

from __future__ import annotations

import numpy as np

from beastforge.model.loader import load_recipe
from beastforge.pipeline import prepare


def _built(repo_root):
    recipe, document = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    return prepare(recipe, document=document, recipe_path="ridge-stalker", tool_version="0.1.0")


def test_mesh_is_non_empty_and_normalized(repo_root) -> None:
    built = _built(repo_root)
    mesh = built.mesh
    assert mesh.vertex_count > 0
    assert mesh.triangle_count > 0
    assert np.allclose(mesh.weights.sum(axis=1), 1.0, atol=1e-5)
    influences = (mesh.weights > 0.0).sum(axis=1)
    assert int(influences.min()) >= 1
    assert int(influences.max()) <= 2


def test_uvs_are_in_the_unit_square(repo_root) -> None:
    mesh = _built(repo_root).mesh
    assert float(mesh.uv.min()) >= 0.0
    assert float(mesh.uv.max()) <= 1.0


def test_normals_are_unit_length(repo_root) -> None:
    mesh = _built(repo_root).mesh
    lengths = np.linalg.norm(mesh.normals, axis=1)
    assert np.allclose(lengths, 1.0, atol=1e-9)


def test_bounds_are_finite(repo_root) -> None:
    mesh = _built(repo_root).mesh
    assert np.all(np.isfinite(mesh.bounds_min))
    assert np.all(np.isfinite(mesh.bounds_max))
    assert np.all(mesh.bounds_min <= mesh.bounds_max)
