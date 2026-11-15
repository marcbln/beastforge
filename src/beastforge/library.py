"""Filesystem library scanning and creature-name resolution (research D13)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from beastforge.config import Settings, find_library_root
from beastforge.model.errors import NotFoundError
from beastforge.model.loader import RecipeParseError, load_yaml_document, parse_recipe
from beastforge.model.recipe import Meta


@dataclass
class LibraryEntry:
    """The catalog view of one recipe; never a stored duplicate."""

    name: str
    category: str
    description: str
    tags: list[str]
    tested_with: str
    version: str
    path: str
    params: list[dict[str, object]]

    def to_json(self) -> dict[str, object]:
        """Return the ``library.list`` entry shape."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "tags": list(self.tags),
            "params": list(self.params),
            "tested_with": self.tested_with,
            "version": self.version,
            "path": self.path,
        }


def library_paths(root: Path) -> list[Path]:
    """Return every recipe file under ``root`` in deterministic order."""
    paths = sorted(set(root.glob("*/*.yaml")) | set(root.glob("*/*.yml")))
    return [path for path in paths if path.is_file()]


def project_relative(path: Path, *, cwd: Path | None = None) -> str:
    """Render ``path`` relative to ``cwd`` when possible, else absolute."""
    base = cwd or Path.cwd()
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def load_entry(path: Path, *, cwd: Path | None = None) -> LibraryEntry:
    """Load one catalog entry from a recipe file's ``meta`` and ``params``."""
    label = project_relative(path, cwd=cwd)
    document = load_yaml_document(path, recipe_label=label)
    recipe = parse_recipe(document, recipe_label=label)
    meta: Meta = recipe.meta
    params = [
        {
            key: value
            for key, value in {
                "name": param.name,
                "type": param.type,
                "default": param.default,
                "min": param.min,
                "max": param.max,
                "values": param.values,
                "unit": param.unit,
                "description": param.description,
            }.items()
            if value is not None
        }
        for param in recipe.params
    ]
    return LibraryEntry(
        name=meta.name,
        category=meta.category,
        description=meta.description,
        tags=list(meta.tags),
        tested_with=meta.tested_with,
        version=meta.version,
        path=label,
        params=params,
    )


def scan(settings: Settings, *, cwd: Path | None = None) -> list[LibraryEntry]:
    """Scan the library on demand, sorted by path; broken recipes are skipped."""
    root = find_library_root(settings, cwd=cwd)
    entries: list[LibraryEntry] = []
    for path in library_paths(root):
        try:
            entries.append(load_entry(path, cwd=cwd))
        except RecipeParseError:
            continue
    return entries


def scan_with_warnings(
    settings: Settings, *, cwd: Path | None = None
) -> tuple[list[LibraryEntry], list[str]]:
    """Scan the library and return both entries and per-file parse warnings."""
    root = find_library_root(settings, cwd=cwd)
    entries: list[LibraryEntry] = []
    warnings: list[str] = []
    for path in library_paths(root):
        try:
            entries.append(load_entry(path, cwd=cwd))
        except RecipeParseError as exc:
            warnings.append(f"{project_relative(path, cwd=cwd)}: {exc.message}")
    return entries, warnings


def _looks_like_path(source: str) -> bool:
    return source.endswith((".yaml", ".yml")) or os.sep in source or "/" in source


def resolve_recipe_path(source: str, settings: Settings, *, cwd: Path | None = None) -> Path:
    """Resolve a name or explicit path, with explicit-path precedence."""
    base = cwd or Path.cwd()
    if _looks_like_path(source):
        candidate = Path(source)
        if not candidate.is_absolute():
            candidate = base / candidate
        if candidate.is_file():
            return candidate.resolve()
        raise NotFoundError(
            "recipe-not-found",
            f"Recipe file {source!r} does not exist.",
            location={"recipe": source, "path": ""},
            remedy="Check the path or pass a library creature name instead.",
        )

    root = find_library_root(settings, cwd=cwd)
    matches: list[Path] = []
    for path in library_paths(root):
        if path.stem == source:
            matches.append(path)
    if not matches:
        raise NotFoundError(
            "recipe-not-found",
            f"No creature named {source!r} exists in the library.",
            location={"recipe": source, "path": ""},
            remedy="Run `beastforge list` to see available creatures.",
        )
    if len(matches) > 1:
        locations = ", ".join(project_relative(path, cwd=cwd) for path in matches)
        raise NotFoundError(
            "ambiguous-name",
            f"Creature name {source!r} matches more than one recipe: {locations}.",
            location={"recipe": source, "path": ""},
            remedy="Pass the explicit recipe path instead of the bare name.",
        )
    return matches[0].resolve()
