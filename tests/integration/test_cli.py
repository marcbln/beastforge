"""End-to-end CLI behaviour: discovery, generation, safety, and streams."""

from __future__ import annotations

import json

from tests.conftest import run_cli


def test_version_and_about(env) -> None:
    for args in (["version"], ["about"], ["--version"], ["-V"]):
        result = run_cli(args, env)
        assert result.returncode == 0, result.stderr
        assert "beastforge 0.1.0" in result.stdout


def test_help_exits_zero(env) -> None:
    for args in (["--help"], ["render", "--help"], ["list", "-h"]):
        result = run_cli(args, env)
        assert result.returncode == 0, result.stderr
        assert "Usage" in result.stdout


def test_list_json_is_clean_stdout(env) -> None:
    result = run_cli(["list", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert {entry["name"] for entry in payload["creatures"]} >= {
        "ash-crowned-tyrant",
        "ridge-stalker",
        "chitter-mite",
    }


def test_list_filters(env) -> None:
    result = run_cli(["list", "--category", "boss", "--json"], env)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["creatures"]] == ["ash-crowned-tyrant"]
    result = run_cli(["list", "--tag", "quadruped", "--json"], env)
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["creatures"]] == ["ridge-stalker"]


def test_params_json(env) -> None:
    result = run_cli(["params", "ridge-stalker", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    names = [param["name"] for param in payload["params"]]
    assert names == ["body-length", "seed"]


def test_validate_library_and_one_recipe(env) -> None:
    result = run_cli(["validate", "--json"], env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True
    result = run_cli(["validate", "ridge-stalker", "--json"], env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["scope"]["kind"] == "recipe"


def test_render_writes_pair_and_report(env, tmp_path) -> None:
    out = tmp_path / "creature"
    result = run_cli(["render", "ridge-stalker", "-o", str(out), "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert (out / "ridge-stalker.glb").is_file()
    assert (out / "ridge-stalker.manifest.json").is_file()
    assert payload["outputs"]["glb"]["sha256"] == _sha(out / "ridge-stalker.glb")
    assert payload["outputs"]["manifest"]["sha256"] == _sha(out / "ridge-stalker.manifest.json")


def test_render_refuses_overwrite(env, tmp_path) -> None:
    out = tmp_path / "creature"
    assert run_cli(["render", "ridge-stalker", "-o", str(out), "--json"], env).returncode == 0
    result = run_cli(["render", "ridge-stalker", "-o", str(out), "--json"], env)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "output-exists"


def test_render_dry_run_writes_nothing(env, tmp_path) -> None:
    out = tmp_path / "dry"
    result = run_cli(["render", "ridge-stalker", "-o", str(out), "--dry-run", "--json"], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert "sha256" not in payload["outputs"]["glb"]
    assert not out.exists()


def test_unknown_set_is_exit_3_with_suggestion(env) -> None:
    result = run_cli(["render", "ridge-stalker", "--set", "body-lenght=3.1", "--json"], env)
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "recipe-unknown-param"
    assert payload["error"]["suggestion"] == "body-length"


def test_global_flags_work_before_the_verb(env) -> None:
    result = run_cli(["--json", "list"], env)
    assert result.returncode == 0
    assert "creatures" in json.loads(result.stdout)
    result = run_cli(["--no-color", "validate", "ridge-stalker"], env)
    assert result.returncode == 0


def test_unknown_creature_is_exit_4(env) -> None:
    result = run_cli(["params", "does-not-exist", "--json"], env)
    assert result.returncode == 4
    assert json.loads(result.stdout)["error"]["code"] == "recipe-not-found"


def _sha(path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
