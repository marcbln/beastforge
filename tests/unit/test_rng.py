"""Seeded stream derivation."""

from __future__ import annotations

from beastforge.rng import derive_phases, derive_unit, recipe_digest, run_seed


def test_recipe_digest_ignores_key_order() -> None:
    assert recipe_digest({"a": 1, "b": 2}) == recipe_digest({"b": 2, "a": 1})


def test_run_seed_depends_on_recipe_and_params() -> None:
    base = run_seed("a" * 64, {"seed": 1})
    assert base == run_seed("a" * 64, {"seed": 1})
    assert base != run_seed("a" * 64, {"seed": 2})
    assert base != run_seed("b" * 64, {"seed": 1})


def test_derived_units_are_stable_and_bounded() -> None:
    first = derive_unit("seed", "purpose", 3)
    assert first == derive_unit("seed", "purpose", 3)
    assert 0.0 <= first < 1.0
    phases = derive_phases("seed", "phases", 4)
    assert len(phases) == 4
    assert all(0.0 <= value <= 6.283185307179587 for value in phases)
