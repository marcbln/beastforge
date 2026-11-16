"""Manifest 1.1 additive fields and 1.0 compatibility."""

from __future__ import annotations

import json

import jsonschema

from beastforge.export.manifest import build_manifest, manifest_json
from beastforge.model.loader import load_recipe
from beastforge.model.manifest import read_manifest_compatible
from beastforge.parts.registry import PresetRegistry
from beastforge.parts.resolve import resolve_parts
from beastforge.pipeline import prepare
from tests.conftest import ROOT

SCHEMA = (
    ROOT
    / "specs/001-procedural-creature-generator/contracts/schema/manifest.schema.json"
)


def _hover_manifest() -> dict:
    path = ROOT / "library/other/hover-skiff.yaml"
    recipe, document = load_recipe(path)
    registry = PresetRegistry(ROOT / "library/parts", cwd=ROOT)
    resolution = resolve_parts(recipe, registry, recipe_label="hover-skiff")
    assert resolution.findings == []
    built = prepare(
        recipe,
        document=document,
        recipe_path="hover-skiff",
        tool_version="0.1.0",
        resolved_parts=resolution.parts,
    )
    manifest = build_manifest(
        recipe=recipe,
        recipe_path="hover-skiff",
        recipe_sha256=built.recipe_sha256,
        resolved_params=built.resolved_params,
        skeleton=built.skeleton,
        mesh=built.mesh,
        baked_clips=built.clips,
        textures=[],
        tool_version="0.1.0",
        texforge_version="0.0.0",
        parts=resolution.parts,
    )
    return manifest_json(manifest)


def test_manifest_1_1_validates_and_publishes_parts() -> None:
    payload = _hover_manifest()
    jsonschema.validate(payload, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert payload["schemaVersion"] == "1.1"
    assert payload["parts"] and payload["parts"][0]["presetSha256"]
    baseline = [clip for clip in payload["clips"] if clip["name"] == "baseline"]
    assert baseline and baseline[0]["generator"] == "baseline"
    assert baseline[0]["source"] == "automatic"


def test_a_1_0_payload_remains_valid(rendered) -> None:
    assert rendered.manifest is not None
    payload = manifest_json(rendered.manifest)
    payload["schemaVersion"] = "1.0"
    payload.pop("parts", None)
    for clip in payload["clips"]:
        clip.pop("source", None)
    jsonschema.validate(payload, json.loads(SCHEMA.read_text(encoding="utf-8")))
    compatible = read_manifest_compatible(payload)
    assert compatible["schemaVersion"] == "1.0"


def test_unbounded_range_is_omitted(tmp_path) -> None:
    payload = _hover_manifest()
    controls = {
        control["name"]: control
        for part in payload["parts"]
        for control in part["controls"]
    }
    assert controls["spin"]["unbounded"] is True
    assert "range" not in controls["spin"]
    assert controls["pitch"]["unbounded"] is False
    assert "range" in controls["pitch"]
