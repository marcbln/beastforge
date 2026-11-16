"""`beastforge parts` human/JSON output, filters, and exit codes."""

from __future__ import annotations

import json

from tests.conftest import run_cli


def test_human_and_json_output(env) -> None:
    human = run_cli(["parts"], env)
    assert human.returncode == 0, human.stderr
    assert "organic-leg" in human.stdout
    assert "NAME" in human.stdout

    machine = run_cli(["parts", "--json"], env)
    assert machine.returncode == 0, machine.stderr
    assert json.loads(machine.stdout)["status"] == "ok"


def test_family_filter(env) -> None:
    result = run_cli(["parts", "--family", "vehicle", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["presets"]
    assert {preset["family"] for preset in payload["presets"]} == {"vehicle"}


def test_exact_version(env) -> None:
    result = run_cli(["parts", "organic-leg", "--version", "1.0.0", "--json"], env)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["presets"]) == 1


def test_unknown_name_is_exit_4(env) -> None:
    result = run_cli(["parts", "does-not-exist", "--json"], env)
    assert result.returncode == 4
    assert json.loads(result.stdout)["error"]["code"] == "part-preset-missing"


def test_invalid_version_and_family_are_exit_2(env) -> None:
    version = run_cli(["parts", "organic-leg", "--version", "one", "--json"], env)
    assert version.returncode == 2
    family = run_cli(["parts", "--family", "mineral", "--json"], env)
    assert family.returncode == 2


def test_missing_parts_library_is_exit_4(env, tmp_path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    result = run_cli(["parts", "--library", str(library), "--json"], env, cwd=tmp_path)
    assert result.returncode == 4
    assert json.loads(result.stdout)["error"]["code"] == "parts-library-missing"
