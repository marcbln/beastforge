"""Validation command helpers used by the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from beastforge import __version__
from beastforge.config import Settings, find_library_root, find_texforge_library
from beastforge.library import library_paths, project_relative, resolve_recipe_path
from beastforge.model.findings import ValidationFinding
from beastforge.model.loader import RecipeParseError, load_recipe
from beastforge.parts.registry import PresetRegistry
from beastforge.parts.resolve import resolve_parts
from beastforge.validation.gate import error_findings, run_gate


@dataclass
class ValidateOutcome:
    """The ``validate --json`` result."""

    valid: bool
    scope: dict[str, object]
    findings: list[ValidationFinding] = field(default_factory=list)
    creatures: list[str] = field(default_factory=list)
    tool_version: str = __version__

    @property
    def errors(self) -> int:
        return sum(1 for item in self.findings if item.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.findings if item.severity == "warning")

    def to_json(self) -> dict[str, object]:
        """Return the schema-shaped ``validate.result`` payload."""
        return {
            "schema_version": "1",
            "tool_version": self.tool_version,
            "status": "ok" if self.valid else "invalid",
            "valid": self.valid,
            "scope": self.scope,
            "findings": [item.to_json() for item in self.findings],
            "summary": {
                "errors": self.errors,
                "warnings": self.warnings,
                "creatures_checked": len(self.creatures),
            },
        }


def _check_one(
    path: Path,
    *,
    settings: Settings,
    texforge_root: Path | None,
    cwd: Path | None,
    library_root: Path | None = None,
) -> tuple[list[ValidationFinding], str]:
    label = project_relative(path, cwd=cwd)
    try:
        recipe, document = load_recipe(path, recipe_label=label)
    except RecipeParseError as exc:
        return exc.findings, recipe_name_from_path(path)
    registry = PresetRegistry.from_library_root(library_root, cwd=cwd)
    resolution = resolve_parts(recipe, registry, recipe_label=label)
    findings = list(resolution.findings)
    findings.extend(
        run_gate(
            recipe,
            recipe_label=label,
            file_stem=path.stem,
            document=document,
            settings=settings,
            texforge_root=texforge_root,
            resolved_parts=resolution.parts,
        )
    )
    return findings, recipe.meta.name


def recipe_name_from_path(path: Path) -> str:
    """Use the filename stem when the recipe cannot be parsed."""
    return path.stem


def validate_library(settings: Settings, *, cwd: Path | None = None) -> ValidateOutcome:
    """Validate every recipe in the library."""
    root = find_library_root(settings, cwd=cwd)
    texforge_root = find_texforge_library(settings, library_root=root)
    findings: list[ValidationFinding] = []
    creatures: list[str] = []
    for path in library_paths(root):
        path_findings, name = _check_one(
            path,
            settings=settings,
            texforge_root=texforge_root,
            cwd=cwd,
            library_root=root,
        )
        findings.extend(path_findings)
        creatures.append(name)
    valid = not error_findings(findings)
    return ValidateOutcome(
        valid=valid,
        scope={"kind": "library", "creatures": creatures},
        findings=findings,
        creatures=creatures,
    )


def validate_recipe(source: str, settings: Settings, *, cwd: Path | None = None) -> ValidateOutcome:
    """Validate one recipe by name or path."""
    path = resolve_recipe_path(source, settings, cwd=cwd)
    root = find_library_root(settings, cwd=cwd)
    texforge_root = find_texforge_library(settings, library_root=root)
    findings, name = _check_one(
        path,
        settings=settings,
        texforge_root=texforge_root,
        cwd=cwd,
        library_root=root,
    )
    valid = not error_findings(findings)
    return ValidateOutcome(
        valid=valid,
        scope={"kind": "recipe", "recipe": project_relative(path, cwd=cwd)},
        findings=findings,
        creatures=[name],
    )
