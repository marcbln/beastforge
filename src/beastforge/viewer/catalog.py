"""Pure derivation of the viewer catalog from the current library.

``build_catalog`` reads recipes only; it never generates assets. The resulting
document is the single discovery contract consumed by both the local server and
the static export (``specs/002-webgl-library-viewer/contracts/catalog.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from beastforge import __version__
from beastforge.config import Settings, find_library_root
from beastforge.library import (
    library_paths,
    load_entry_with_document,
    project_relative,
)
from beastforge.model.loader import RecipeParseError
from beastforge.utils.canonical import canonical_json

SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = "1"
GENERATOR = "beastforge"
CATEGORY_ORDER: tuple[str, ...] = ("boss", "quadruped", "swarm", "other")


class CatalogVersionError(ValueError):
    """Raised when a catalog cannot be read by this consumer."""


@dataclass(frozen=True)
class CatalogWarning:
    """A non-fatal scan problem, reported with a project-relative path."""

    path: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


@dataclass(frozen=True)
class CatalogEntry:
    """One loadable creature as the gallery sees it."""

    name: str
    category: str
    description: str
    tags: list[str]
    recipe_version: str
    tested_with: str
    recipe_sha256: str
    asset: str
    manifest: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "tags": list(self.tags),
            "recipeVersion": self.recipe_version,
            "testedWith": self.tested_with,
            "recipeSha256": self.recipe_sha256,
            "asset": self.asset,
            "manifest": self.manifest,
        }


@dataclass(frozen=True)
class CatalogDocument:
    """The versioned catalog consumed by the viewer."""

    schema_version: str
    tool_version: str
    generated_by: str
    categories: list[str]
    creatures: list[CatalogEntry]
    warnings: list[CatalogWarning] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "toolVersion": self.tool_version,
            "generatedBy": self.generated_by,
            "categories": list(self.categories),
            "creatures": [entry.to_json() for entry in self.creatures],
            "warnings": [warning.to_json() for warning in self.warnings],
        }

    def entry(self, name: str) -> CatalogEntry | None:
        for entry in self.creatures:
            if entry.name == name:
                return entry
        return None


def asset_path(name: str, sha: str) -> str:
    """Return the catalog-relative GLB path for a content-addressed package."""
    return f"creatures/{name}/{sha}/{name}.glb"


def manifest_path(name: str, sha: str) -> str:
    """Return the catalog-relative manifest path for a package."""
    return f"creatures/{name}/{sha}/{name}.manifest.json"


def build_catalog(settings: Settings, *, cwd: Path | None = None) -> CatalogDocument:
    """Scan the library and project every loadable recipe into a catalog."""
    root = find_library_root(settings, cwd=cwd)
    entries: list[CatalogEntry] = []
    warnings: list[CatalogWarning] = []
    seen: set[str] = set()

    for path in library_paths(root):
        relative = project_relative(path, cwd=cwd)
        try:
            loaded, _document, digest = load_entry_with_document(path, cwd=cwd)
        except RecipeParseError as exc:
            warnings.append(CatalogWarning(path=relative, message=exc.message))
            continue
        if loaded.name in seen:
            warnings.append(
                CatalogWarning(
                    path=relative,
                    message=f"duplicate creature name {loaded.name!r}; entry skipped",
                )
            )
            continue
        seen.add(loaded.name)
        entries.append(
            CatalogEntry(
                name=loaded.name,
                category=loaded.category,
                description=loaded.description,
                tags=list(loaded.tags),
                recipe_version=loaded.version,
                tested_with=loaded.tested_with,
                recipe_sha256=digest,
                asset=asset_path(loaded.name, digest),
                manifest=manifest_path(loaded.name, digest),
            )
        )

    entries.sort(key=lambda item: item.name)
    warnings.sort(key=lambda item: item.path)
    present = {entry.category for entry in entries}
    categories = [category for category in CATEGORY_ORDER if category in present]

    return CatalogDocument(
        schema_version=SCHEMA_VERSION,
        tool_version=__version__,
        generated_by=GENERATOR,
        categories=categories,
        creatures=entries,
        warnings=warnings,
    )


def catalog_json(document: CatalogDocument) -> str:
    """Serialize a catalog in canonical JSON with a trailing newline."""
    return canonical_json(document.to_json())


def parse_catalog(payload: Any) -> dict[str, Any]:
    """Read a catalog major-strict/minor-tolerant, ignoring unknown fields."""
    if not isinstance(payload, dict):
        raise CatalogVersionError("catalog-schema-invalid: expected a JSON object")
    version = payload.get("schemaVersion")
    if not isinstance(version, str) or not re.match(r"^\d+\.\d+$", version):
        raise CatalogVersionError("catalog-schema-invalid: schemaVersion must be MAJOR.MINOR")
    if version.split(".", 1)[0] != SCHEMA_MAJOR:
        raise CatalogVersionError(
            f"catalog-schema-unsupported: major version {version.split('.', 1)[0]} "
            f"is not supported (expected {SCHEMA_MAJOR}.x)"
        )
    missing = [
        key
        for key in ("toolVersion", "generatedBy", "categories", "creatures", "warnings")
        if key not in payload
    ]
    if missing:
        raise CatalogVersionError(
            "catalog-schema-invalid: missing required fields: " + ", ".join(missing)
        )
    creatures = payload.get("creatures")
    if not isinstance(creatures, list):
        raise CatalogVersionError("catalog-schema-invalid: creatures must be an array")
    for entry in creatures:
        if not isinstance(entry, dict):
            raise CatalogVersionError("catalog-schema-invalid: creature entry must be an object")
        for key in ("name", "category", "description", "recipeSha256", "asset", "manifest"):
            if key not in entry:
                raise CatalogVersionError(f"catalog-schema-invalid: creature entry missing {key}")
    return payload


__all__ = [
    "CATEGORY_ORDER",
    "SCHEMA_VERSION",
    "CatalogDocument",
    "CatalogEntry",
    "CatalogVersionError",
    "CatalogWarning",
    "asset_path",
    "build_catalog",
    "catalog_json",
    "manifest_path",
    "parse_catalog",
]
