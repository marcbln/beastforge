"""Preset registry scanning, versioning, and duplicate/mismatch rejection."""

from __future__ import annotations

from pathlib import Path

from beastforge.parts.registry import PresetRegistry, version_key

PRESET = """\
name: {name}
family: organic
version: "{version}"
description: "A test preset."
surface:
  mode: sweep
  kind: swept-solid
  bones: ["@root", "@tip"]
  rings: 4
  segments: 4
  radius: {{start: 0.1, end: 0.05}}
"""


def _write(root: Path, directory: str, filename: str, *, name: str, version: str) -> Path:
    folder = root / directory
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_text(PRESET.format(name=name, version=version), encoding="utf-8")
    return path


def test_sorted_scan_and_exact_version_lookup(tmp_path) -> None:
    _write(tmp_path, "zeta", "1.0.0.yaml", name="zeta", version="1.0.0")
    _write(tmp_path, "alpha", "2.0.0.yaml", name="alpha", version="2.0.0")
    _write(tmp_path, "alpha", "1.0.0.yaml", name="alpha", version="1.0.0")
    registry = PresetRegistry(tmp_path)
    assert registry.names() == ["alpha", "zeta"]
    assert registry.versions("alpha") == ["1.0.0", "2.0.0"]
    assert registry.get("alpha", "1.0.0") is not None
    assert registry.get("alpha", "3.0.0") is None
    assert [preset.name for preset in registry.all_presets()] == ["alpha", "alpha", "zeta"]


def test_semver_sorting_is_numeric_not_lexical() -> None:
    assert sorted(["1.10.0", "1.2.0", "1.0.1"], key=version_key) == [
        "1.0.1",
        "1.2.0",
        "1.10.0",
    ]


def test_duplicate_name_version_is_rejected(tmp_path) -> None:
    _write(tmp_path, "alpha", "1.0.0.yaml", name="alpha", version="1.0.0")
    _write(tmp_path, "alpha", "1.0.0.yml", name="alpha", version="1.0.0")
    registry = PresetRegistry(tmp_path)
    assert len(registry.presets) == 1
    assert any("duplicate preset version" in warning.message for warning in registry.warnings)


def test_name_directory_mismatch_is_rejected(tmp_path) -> None:
    _write(tmp_path, "wrong", "1.0.0.yaml", name="alpha", version="1.0.0")
    registry = PresetRegistry(tmp_path)
    assert registry.presets == {}
    assert any("does not match directory" in warning.message for warning in registry.warnings)


def test_version_filename_mismatch_is_rejected(tmp_path) -> None:
    _write(tmp_path, "alpha", "9.9.9.yaml", name="alpha", version="1.0.0")
    registry = PresetRegistry(tmp_path)
    assert registry.presets == {}
    assert any("does not match filename" in warning.message for warning in registry.warnings)


def test_preset_sha_is_canonical_and_stable(tmp_path) -> None:
    _write(tmp_path, "alpha", "1.0.0.yaml", name="alpha", version="1.0.0")
    first = PresetRegistry(tmp_path).get("alpha", "1.0.0")
    second = PresetRegistry(tmp_path).get("alpha", "1.0.0")
    assert first is not None and second is not None
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64
