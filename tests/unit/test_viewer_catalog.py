"""Catalog derivation: ordering, digests, warnings, and determinism."""

from __future__ import annotations

import re
from pathlib import Path

from beastforge.config import Settings
from beastforge.library import scan_with_warnings
from beastforge.viewer.catalog import (
    CATEGORY_ORDER,
    asset_path,
    build_catalog,
    catalog_json,
    manifest_path,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_catalog_order_and_shape(settings: Settings) -> None:
    catalog = build_catalog(settings)
    names = [entry.name for entry in catalog.creatures]
    assert names == sorted(names)
    assert len(names) == len(set(names))
    assert catalog.categories == [
        category
        for category in CATEGORY_ORDER
        if category in {e.category for e in catalog.creatures}
    ]
    for entry in catalog.creatures:
        assert HEX64.match(entry.recipe_sha256)
        assert entry.asset == asset_path(entry.name, entry.recipe_sha256)
        assert entry.manifest == manifest_path(entry.name, entry.recipe_sha256)
        assert entry.asset.startswith("creatures/")
        assert not entry.asset.startswith("/")
        assert "?" not in entry.asset and "#" not in entry.asset


def test_catalog_covers_every_loadable_recipe(settings: Settings) -> None:
    catalog = build_catalog(settings)
    loaded, _warnings = scan_with_warnings(settings)
    assert [entry.name for entry in catalog.creatures] == sorted(entry.name for entry in loaded)


def test_catalog_is_byte_identical(settings: Settings) -> None:
    assert catalog_json(build_catalog(settings)) == catalog_json(build_catalog(settings))


def test_empty_library(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    catalog = build_catalog(Settings(library=str(library)), cwd=tmp_path)
    assert catalog.creatures == []
    assert catalog.categories == []
    assert catalog.warnings == []


def test_unreadable_recipe_is_a_warning(tmp_path: Path) -> None:
    library = tmp_path / "library" / "other"
    library.mkdir(parents=True)
    (library / "broken.yaml").write_text("meta: [unterminated\n", encoding="utf-8")
    catalog = build_catalog(Settings(library=str(tmp_path / "library")), cwd=tmp_path)
    assert catalog.creatures == []
    assert len(catalog.warnings) == 1
    assert catalog.warnings[0].path == "library/other/broken.yaml"
    assert catalog.warnings[0].message


def test_warnings_sorted_by_project_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "library"
    for name in ("zeta", "alpha"):
        directory = root / "other"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.yaml").write_text("meta: [broken\n", encoding="utf-8")
    catalog = build_catalog(Settings(library=str(root)), cwd=tmp_path)
    paths = [warning.path for warning in catalog.warnings]
    assert paths == sorted(paths)
    assert all(path.startswith("library/") for path in paths)
