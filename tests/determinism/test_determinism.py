"""Byte identity across working directories and repeated builds (SC-002)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from beastforge.export.gltf import build_glb
from beastforge.model.loader import load_recipe
from beastforge.pipeline import prepare
from beastforge.render import render

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_hundred_builds_are_byte_identical(settings) -> None:
    path = ROOT / "library/swarm/chitter-mite.yaml"
    recipe, document = load_recipe(path)
    hashes: set[str] = set()
    for _ in range(100):
        built = prepare(recipe, document=document, recipe_path=str(path), tool_version="0.1.0")
        glb = build_glb(
            recipe=built.recipe,
            skeleton=built.skeleton,
            mesh=built.mesh,
            clips=built.clips,
            textures=[],
            tool_version="0.1.0",
        )
        hashes.add(hashlib.sha256(glb).hexdigest())
    assert len(hashes) == 1


@pytest.mark.slow
def test_render_is_identical_across_working_directories(settings, tmp_path, env) -> None:
    import os

    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    os.environ["TZ"] = "UTC"
    os.environ["LC_ALL"] = "C"
    first = render("chitter-mite", settings=settings, out_dir=str(out_a), force=True)
    os.environ["TZ"] = "Pacific/Auckland"
    os.environ["LC_ALL"] = "C.UTF-8"
    second = render("chitter-mite", settings=settings, out_dir=str(out_b), force=True)
    assert first.glb is not None and second.glb is not None
    assert hashlib.sha256(first.glb).hexdigest() == hashlib.sha256(second.glb).hexdigest()
    assert first.manifest_text == second.manifest_text
