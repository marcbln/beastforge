"""Every published JSON surface validates against its schema."""

from __future__ import annotations

import json

import jsonschema
import pytest

from beastforge.model.manifest import ManifestVersionError, read_manifest_compatible
from tests.conftest import ROOT, run_cli


def _schema(name: str) -> dict:
    return json.loads(
        (ROOT / "specs/001-procedural-creature-generator/contracts/schema" / name).read_text()
    )


def test_library_list_schema(env) -> None:
    result = run_cli(["list", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema("library.list.schema.json"))
    assert len(payload["creatures"]) >= 3


def test_params_schema(env) -> None:
    result = run_cli(["params", "ridge-stalker", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema("params.schema.json"))


def test_validate_schema(env) -> None:
    result = run_cli(["validate", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema("validate.result.schema.json"))


def test_render_report_schema(rendered) -> None:
    jsonschema.validate(
        rendered.report.model_dump(mode="json"), _schema("render.result.schema.json")
    )


def test_manifest_schema(rendered) -> None:
    assert rendered.manifest is not None
    from beastforge.export.manifest import manifest_json

    jsonschema.validate(manifest_json(rendered.manifest), _schema("manifest.schema.json"))


def test_error_schema(env) -> None:
    result = run_cli(["render", "ridge-stalker", "--set", "body-lenght=3.1", "--json"], env)
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, _schema("error.schema.json"))
    assert payload["error"]["suggestion"] == "body-length"


def test_additional_properties_are_closed(rendered) -> None:
    payload = rendered.report.model_dump(mode="json")
    payload["unexpected"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, _schema("render.result.schema.json"))


def test_consumer_reads_same_major_and_rejects_new_major(rendered) -> None:
    from beastforge.export.manifest import manifest_json

    assert rendered.manifest is not None
    payload = manifest_json(rendered.manifest)
    payload["schemaVersion"] = "1.1"
    payload["futureField"] = {"added": "in a minor release"}
    compat = read_manifest_compatible(payload)
    assert compat["schemaVersion"] == "1.1"
    assert any(clip["name"] == "attack" for clip in compat["clips"])

    payload["schemaVersion"] = "2.0"
    with pytest.raises(ManifestVersionError):
        read_manifest_compatible(payload)
