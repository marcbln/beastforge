"""Parameter coercion, ranges, and suggestions."""

from __future__ import annotations

import pytest

from beastforge.model.errors import BeastforgeError, UsageError
from beastforge.model.loader import load_recipe
from beastforge.params import parse_set_tokens, resolve_params


def _recipe(repo_root):
    recipe, _document = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    return recipe


def test_parse_set_tokens_rejects_malformed() -> None:
    with pytest.raises(UsageError) as exc:
        parse_set_tokens(["body-length"])
    assert exc.value.exit_code == 2
    assert exc.value.code == "set-syntax"


def test_unknown_parameter_suggests_nearest(repo_root) -> None:
    resolution = resolve_params(
        _recipe(repo_root), {"body-lenght": "3.1"}, recipe_label="ridge-stalker"
    )
    assert resolution.findings[0].code == "recipe-unknown-param"
    assert resolution.findings[0].suggestion == "body-length"


def test_override_coerces_and_resolves(repo_root) -> None:
    resolution = resolve_params(
        _recipe(repo_root), {"body-length": "3.1", "seed": "9"}, recipe_label="ridge-stalker"
    )
    assert resolution.values["body-length"] == 3.1
    assert resolution.values["seed"] == 9


def test_out_of_range_is_rejected(repo_root) -> None:
    resolution = resolve_params(
        _recipe(repo_root), {"body-length": "99"}, recipe_label="ridge-stalker"
    )
    assert resolution.findings[0].code == "recipe-param-range"


def test_strict_raises(repo_root) -> None:
    with pytest.raises(BeastforgeError):
        resolve_params(
            _recipe(repo_root), {"body-lenght": "3.1"}, recipe_label="ridge-stalker", strict=True
        )
