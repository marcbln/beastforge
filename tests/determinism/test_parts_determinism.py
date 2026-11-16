"""Two consecutive builds of a preset assembly are byte-identical (SC-002)."""

from __future__ import annotations

import hashlib

import pytest

from beastforge.render import render


@pytest.mark.slow
@pytest.mark.parametrize("name", ["iron-warden", "hover-skiff"])
def test_preset_assemblies_are_byte_identical(settings, tmp_path, name) -> None:
    first = render(name, settings=settings, out_dir=str(tmp_path / f"{name}-a"), force=True)
    second = render(name, settings=settings, out_dir=str(tmp_path / f"{name}-b"), force=True)
    assert first.glb is not None and second.glb is not None
    assert hashlib.sha256(first.glb).hexdigest() == hashlib.sha256(second.glb).hexdigest()
    assert first.manifest_text == second.manifest_text
    assert first.manifest is not None
    sources = {clip.name: clip.source for clip in first.manifest.clips}
    if name == "hover-skiff":
        assert sources == {"baseline": "automatic"}
