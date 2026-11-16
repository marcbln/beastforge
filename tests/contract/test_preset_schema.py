"""Every shipped preset validates against the published preset schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "specs/003-closed-part-library/contracts/preset.schema.json"


def test_twelve_presets_across_three_families() -> None:
    documents = [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "library/parts").glob("*/*.yaml"))
    ]
    assert len(documents) == 12
    assert {document["family"] for document in documents} == {
        "organic",
        "mechanical",
        "vehicle",
    }
    names = {document["name"] for document in documents}
    assert "vehicle-rotor" in names
    assert "organic-leg" in names


def test_every_shipped_preset_matches_the_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    paths = sorted((ROOT / "library/parts").glob("*/*.yaml"))
    assert paths
    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        jsonschema.validate(document, schema)


def test_name_and_version_agree_with_path() -> None:
    for path in sorted((ROOT / "library/parts").glob("*/*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert document["name"] == path.parent.name
        assert document["version"] == path.stem
