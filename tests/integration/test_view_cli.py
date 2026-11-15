"""``beastforge view`` serve/export CLI behaviour and cache precedence."""

from __future__ import annotations

import json
import shutil
import signal
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from beastforge.config import Settings, resolve_cache_dir
from tests.conftest import ROOT, run_cli


def _tiny_library(tmp_path: Path, env: dict[str, str]) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "library"
    (root / "quadruped").mkdir(parents=True)
    shutil.copyfile(
        ROOT / "library/quadruped/ridge-stalker.yaml",
        root / "quadruped/ridge-stalker.yaml",
    )
    return root, {**env, "BEASTFORGE_LIBRARY": str(root)}


def _start_viewer(env: dict[str, str], cache: Path, *extra: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "beastforge",
            "view",
            "--no-browser",
            "--port",
            "0",
            "--cache-dir",
            str(cache),
            *extra,
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _read_url(process: subprocess.Popen[str]) -> tuple[str, dict]:
    assert process.stdout is not None
    line = process.stdout.readline()
    assert line, "viewer did not print a startup line"
    payload = json.loads(line)
    return payload["url"], payload


def _stop(process: subprocess.Popen[str], sig: int = signal.SIGINT) -> int:
    process.send_signal(sig)
    return process.wait(timeout=15)


def test_serve_json_and_health(env, tmp_path) -> None:
    process = _start_viewer(env, tmp_path / "cache", "--json")
    try:
        url, payload = _read_url(process)
        assert payload["mode"] == "serve"
        assert payload["dry_run"] is False
        assert payload["cache_dir"] == str((tmp_path / "cache").resolve())
        with urllib.request.urlopen(f"{url}healthz", timeout=10) as response:
            assert json.loads(response.read()) == {"status": "ok"}
        assert _stop(process) == 130
    finally:
        if process.poll() is None:
            process.kill()


def test_serve_human_output_and_sigterm(env, tmp_path) -> None:
    process = _start_viewer(env, tmp_path / "cache")
    try:
        assert process.stdout is not None
        first = process.stdout.readline()
        second = process.stdout.readline()
        third = process.stdout.readline()
        assert first.startswith("viewer: http://127.0.0.1:")
        assert second.startswith("cache:")
        assert "press Ctrl-C" in third
        assert _stop(process, signal.SIGTERM) == 0
    finally:
        if process.poll() is None:
            process.kill()


def test_serve_dry_run_binds_nothing(env, tmp_path) -> None:
    result = run_cli(["view", "--dry-run", "--json", "--cache-dir", str(tmp_path / "c")], env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "serve"
    assert payload["url"] is None
    assert payload["dry_run"] is True


def test_invalid_flag_combinations_exit_2(env, tmp_path) -> None:
    for args in (
        ["view", "--export", str(tmp_path / "site"), "--port", "8080"],
        ["view", "--export", str(tmp_path / "site"), "--cache-dir", str(tmp_path / "c")],
        ["view", "--force"],
        ["view", "--port", "70000", "--dry-run"],
    ):
        result = run_cli(args, env)
        assert result.returncode == 2, (args, result.stderr)


def test_port_is_released_after_stop(env, tmp_path) -> None:
    process = _start_viewer(env, tmp_path / "cache", "--json")
    try:
        url, _payload = _read_url(process)
        port = int(url.rsplit(":", 1)[1].strip("/"))
        assert _stop(process, signal.SIGTERM) == 0
    finally:
        if process.poll() is None:
            process.kill()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))


def test_cache_precedence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BEASTFORGE_CACHE_DIR", str(tmp_path / "env"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    settings = Settings(cache_dir=str(tmp_path / "config"))
    assert resolve_cache_dir(settings, str(tmp_path / "flag")) == (tmp_path / "flag").resolve()
    assert resolve_cache_dir(settings) == (tmp_path / "env").resolve()
    monkeypatch.delenv("BEASTFORGE_CACHE_DIR")
    assert resolve_cache_dir(settings) == (tmp_path / "config").resolve()
    assert resolve_cache_dir(Settings()) == (tmp_path / "xdg/beastforge/viewer").resolve()


def test_serve_does_not_modify_tracked_files(env, tmp_path) -> None:
    before = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    process = _start_viewer(
        {**env, "BEASTFORGE_CACHE_DIR": str(tmp_path / "cache")}, tmp_path / "cache", "--json"
    )
    try:
        url, _payload = _read_url(process)
        with urllib.request.urlopen(f"{url}catalog.json", timeout=10) as response:
            assert response.status == 200
    finally:
        if process.poll() is None:
            _stop(process, signal.SIGTERM)
    after = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    assert before == after


# -- export --------------------------------------------------------------
@pytest.fixture
def tiny_env(tmp_path, env) -> tuple[Path, dict[str, str]]:
    return _tiny_library(tmp_path, env)


@pytest.fixture
def exported(tmp_path, tiny_env) -> Iterator[tuple[Path, dict, dict[str, str]]]:
    _library, environment = tiny_env
    target = tmp_path / "site"
    result = run_cli(["view", "--export", str(target), "--no-browser", "--json"], environment)
    assert result.returncode == 0, result.stderr
    yield target, json.loads(result.stdout), environment


def test_export_layout_and_report(exported) -> None:
    target, payload, _env = exported
    assert payload["mode"] == "export"
    assert payload["creatures"] == ["ridge-stalker"]
    assert payload["dry_run"] is False
    assert payload["files"] > 0
    for path in ("index.html", "assets", "catalog.json", "bundle.json", "creatures"):
        assert (target / path).exists(), path
    catalog = json.loads((target / "catalog.json").read_text())
    entry = catalog["creatures"][0]
    assert (target / entry["asset"]).is_file()
    assert (target / entry["manifest"]).is_file()

    bundle = json.loads((target / "bundle.json").read_text())
    assert bundle["schemaVersion"] == "1"
    paths = [item["path"] for item in bundle["files"]]
    assert paths == sorted(paths)
    assert "bundle.json" not in paths
    assert len(paths) == payload["files"]
    for item in bundle["files"]:
        assert (target / item["path"]).is_file()


def test_export_dry_run_writes_nothing(tmp_path, tiny_env) -> None:
    _library, environment = tiny_env
    target = tmp_path / "dry-site"
    result = run_cli(["view", "--export", str(target), "--dry-run", "--json"], environment)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["files"] > 0
    assert not target.exists()


def test_export_refuses_non_empty_target(tmp_path, tiny_env) -> None:
    _library, environment = tiny_env
    target = tmp_path / "site"
    target.mkdir()
    (target / "keep-me.txt").write_text("keep", encoding="utf-8")
    result = run_cli(["view", "--export", str(target), "--json"], environment)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "export-exists"
    assert (target / "keep-me.txt").is_file()


def test_export_force_preserves_unrelated_and_is_idempotent(exported, tiny_env) -> None:
    target, _payload, environment = exported
    (target / "keep-me.txt").write_text("keep", encoding="utf-8")
    first_bundle = (target / "bundle.json").read_bytes()
    first_catalog = (target / "catalog.json").read_bytes()
    result = run_cli(
        ["view", "--export", str(target), "--force", "--no-browser", "--json"], environment
    )
    assert result.returncode == 0, result.stderr
    assert (target / "keep-me.txt").is_file()
    assert (target / "bundle.json").read_bytes() == first_bundle
    assert (target / "catalog.json").read_bytes() == first_catalog
