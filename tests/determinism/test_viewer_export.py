"""Two static exports from identical inputs must be byte-identical (SC-004)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from beastforge.config import Settings
from beastforge.viewer.export import plan_export, write_export
from tests.conftest import ROOT


@pytest.mark.slow
def test_export_is_byte_identical(settings: Settings, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    plan_a = plan_export(settings, cwd=ROOT)
    outcome_a = write_export(plan_a, str(first))
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()
    plan_b = plan_export(settings, cwd=workdir)
    outcome_b = write_export(plan_b, str(second))

    assert outcome_a.creatures == outcome_b.creatures
    assert outcome_a.files == outcome_b.files
    assert (first / "catalog.json").read_bytes() == (second / "catalog.json").read_bytes()
    assert (first / "bundle.json").read_bytes() == (second / "bundle.json").read_bytes()

    bundle = json.loads((first / "bundle.json").read_text(encoding="utf-8"))
    for item in bundle["files"]:
        left = first / item["path"]
        right = second / item["path"]
        assert right.is_file(), item["path"]
        assert left.read_bytes() == right.read_bytes(), item["path"]

    for creature in outcome_a.creatures:
        catalog = json.loads((first / "catalog.json").read_text(encoding="utf-8"))
        entry = next(item for item in catalog["creatures"] if item["name"] == creature)
        left_manifest = first / entry["manifest"]
        right_manifest = second / entry["manifest"]
        assert left_manifest.read_bytes() == right_manifest.read_bytes()
