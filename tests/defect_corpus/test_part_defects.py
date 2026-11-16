"""Part-resolution defects through the public validation gate (FR-022)."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from beastforge.model.loader import parse_recipe
from beastforge.validation.gate import run_gate

ROOT = Path(__file__).resolve().parents[2]
TEXFORGE = ROOT.parent / "texforge" / "library"
BASE = yaml.safe_load((ROOT / "library/other/iron-warden.yaml").read_text())


def _codes(document: dict) -> list[str]:
    recipe = parse_recipe(document, recipe_label="broken.yaml")
    findings = run_gate(
        recipe,
        recipe_label="broken.yaml",
        document=document,
        texforge_root=TEXFORGE,
    )
    return [finding.code for finding in findings]


def _mutate(change) -> dict:
    document = copy.deepcopy(BASE)
    change(document)
    return document


def _part(document: dict, name: str) -> dict:
    return next(part for part in document["parts"] if part["name"] == name)


def test_missing_preset() -> None:
    document = _mutate(lambda d: _part(d, "left-leg").__setitem__("preset", "mech-lge"))
    codes = _codes(document)
    assert "part-preset-missing" in codes


def test_missing_preset_version() -> None:
    document = _mutate(
        lambda d: _part(d, "left-leg").__setitem__("preset_version", "9.9.9")
    )
    assert "part-preset-version-missing" in _codes(document)


def test_missing_binding() -> None:
    document = _mutate(lambda d: _part(d, "left-leg")["bind"].pop("knee"))
    assert "part-binding-missing" in _codes(document)


def test_unknown_binding() -> None:
    document = _mutate(lambda d: _part(d, "left-leg")["bind"].__setitem__("tail", "spine"))
    assert "part-binding-unknown" in _codes(document)


def test_duplicate_binding_target() -> None:
    document = _mutate(lambda d: _part(d, "left-leg")["bind"].__setitem__("knee", "left-hip"))
    assert "part-binding-duplicate" in _codes(document)


def test_duplicate_part_name() -> None:
    document = _mutate(lambda d: _part(d, "right-leg").__setitem__("name", "left-leg"))
    assert "part-duplicate-name" in _codes(document)


def test_unknown_override() -> None:
    document = _mutate(
        lambda d: _part(d, "left-leg").__setitem__("overrides", {"radius-endd": 0.1})
    )
    assert "part-override-unknown" in _codes(document)


def test_recipe_empty_geometry() -> None:
    document = _mutate(
        lambda d: (d.__setitem__("surfaces", []), d.__setitem__("parts", []))
    )
    assert "recipe-empty-geometry" in _codes(document)
