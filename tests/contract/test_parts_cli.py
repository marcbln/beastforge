"""`beastforge parts --json` validates against the published list schema."""

from __future__ import annotations

import json

import jsonschema

from tests.conftest import ROOT, run_cli

SCHEMA = ROOT / "specs/003-closed-part-library/contracts/parts.list.schema.json"


def test_parts_json_matches_schema(env) -> None:
    result = run_cli(["parts", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert len(payload["presets"]) == 12
    assert payload["warnings"] == []


def test_single_preset_json_is_self_consistent(env) -> None:
    result = run_cli(["parts", "organic-leg", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["presets"]) == 1
    preset = payload["presets"][0]
    assert preset["name"] == "organic-leg"
    assert [control["name"] for control in preset["controls"]] == ["swing", "lift"]
    assert [param["name"] for param in preset["params"]] == sorted(
        param["name"] for param in preset["params"]
    )
    assert preset["params"][0]["default"] is not None
