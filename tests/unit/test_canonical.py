"""Canonical JSON and hashing invariants."""

from __future__ import annotations

import math

import pytest

from beastforge.utils.canonical import canonical_json, sha256_hex, sha256_text


def test_canonical_json_sorts_keys_and_is_compact() -> None:
    assert canonical_json({"b": 1, "a": 2}, trailing_newline=False) == '{"a":2,"b":1}'


def test_canonical_json_trailing_newline_by_default() -> None:
    assert canonical_json({"a": 1}).endswith("\n")


def test_canonical_json_normalizes_negative_zero() -> None:
    assert canonical_json({"v": -0.0}, trailing_newline=False) == '{"v":0.0}'


def test_canonical_json_rejects_nan_and_inf() -> None:
    with pytest.raises(ValueError):
        canonical_json({"v": math.nan})
    with pytest.raises(ValueError):
        canonical_json({"v": math.inf})


def test_hash_helpers() -> None:
    assert sha256_hex(b"beastforge") == sha256_text("beastforge")
    assert len(sha256_text("beastforge")) == 64
