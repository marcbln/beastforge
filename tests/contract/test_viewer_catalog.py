"""Catalog and bundle contracts: schema, coverage, and manifest agreement."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from beastforge.config import Settings
from beastforge.export.manifest import manifest_json
from beastforge.library import scan_with_warnings
from beastforge.render import RenderOutcome
from beastforge.viewer.catalog import build_catalog, catalog_json, parse_catalog
from beastforge.viewer.export import _compute_bundle_files
from tests.conftest import ROOT

SPECS = ROOT / "specs/002-webgl-library-viewer/contracts"


def _schema(name: str) -> dict:
    return json.loads((SPECS / name).read_text(encoding="utf-8"))


def test_catalog_matches_schema(settings: Settings) -> None:
    document = build_catalog(settings)
    jsonschema.validate(document.to_json(), _schema("catalog.schema.json"))


def test_catalog_coverage_equals_loadable_set(settings: Settings) -> None:
    catalog = build_catalog(settings)
    loaded, _warnings = scan_with_warnings(settings)
    expected = sorted(entry.name for entry in loaded)
    assert [entry.name for entry in catalog.creatures] == expected
    assert len(expected) == len(set(expected))


def test_catalog_entry_agrees_with_manifest(settings: Settings, rendered: RenderOutcome) -> None:
    assert rendered.manifest is not None
    catalog = build_catalog(settings)
    entry = next(item for item in catalog.creatures if item.name == "ridge-stalker")
    payload = manifest_json(rendered.manifest)
    assert entry.name == payload["creature"]["name"]
    assert entry.category == payload["creature"]["category"]
    assert entry.description == payload["creature"]["description"]
    assert entry.recipe_sha256 == payload["provenance"]["recipeSha256"]


def test_consumer_tolerates_unknown_fields(settings: Settings) -> None:
    payload = json.loads(catalog_json(build_catalog(settings)))
    payload["newTopLevel"] = {"future": True}
    payload["creatures"][0]["newEntryField"] = 1
    parsed = parse_catalog(payload)
    assert parsed["newTopLevel"] == {"future": True}


def test_consumer_rejects_different_major(settings: Settings) -> None:
    payload = json.loads(catalog_json(build_catalog(settings)))
    payload["schemaVersion"] = "2.0"
    with pytest.raises(ValueError):
        parse_catalog(payload)


def test_bundle_file_list_is_sorted_and_complete(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("console.log(1)\n", encoding="utf-8")
    (tmp_path / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (tmp_path / "catalog.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "bundle.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "creatures/ridge/abc").mkdir(parents=True)
    (tmp_path / "creatures/ridge/abc/ridge.glb").write_bytes(b"glb")

    files = _compute_bundle_files(tmp_path)
    paths = [item["path"] for item in files]
    assert paths == sorted(paths)
    assert "bundle.json" not in paths
    assert set(paths) == {
        "assets/app.js",
        "catalog.json",
        "creatures/ridge/abc/ridge.glb",
        "index.html",
    }
    for item in files:
        assert len(item["sha256"]) == 64
        assert item["bytes"] >= 0

    payload = {"schemaVersion": "1", "toolVersion": "0.1.0", "files": files}
    jsonschema.validate(payload, _schema("bundle.schema.json"))


def test_export_plan_enumerates_static_and_creatures(settings: Settings) -> None:
    from beastforge.viewer.export import plan_export

    plan = plan_export(settings)
    assert "index.html" in plan.static_files
    assert "assets/app.js" in plan.static_files
    assert "assets/three/three.module.js" in plan.static_files
    assert {creature.name for creature in plan.creatures} >= {"ridge-stalker", "elephant"}
    assert plan.planned_file_count == len(plan.static_files) + 1 + 2 * len(plan.creatures)
