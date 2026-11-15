"""Committed .glb/manifest SHA-256 goldens (SC-002)."""

from __future__ import annotations

import hashlib

import pytest
from tests.conftest import ROOT

from beastforge.render import render

GOLDEN = ROOT / "tests/golden/library.sha256"


def _expected() -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for line in GOLDEN.read_text().splitlines():
        name, glb, manifest = line.split()
        rows[name] = (glb, manifest)
    return rows


@pytest.mark.slow
def test_library_hashes_match_goldens(settings, tmp_path) -> None:
    expected = _expected()
    assert set(expected) == {
        "ash-crowned-tyrant",
        "ridge-stalker",
        "chitter-mite",
        "giraffe",
        "elephant",
    }
    for name, (glb_hash, manifest_hash) in expected.items():
        outcome = render(name, settings=settings, out_dir=str(tmp_path / name), force=True)
        assert outcome.glb is not None
        assert outcome.manifest_text is not None
        assert hashlib.sha256(outcome.glb).hexdigest() == glb_hash, name
        assert hashlib.sha256(outcome.manifest_text.encode()).hexdigest() == manifest_hash, name
