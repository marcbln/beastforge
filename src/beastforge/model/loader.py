"""YAML recipe loading and pydantic error mapping.

Recipes are inert data: ``yaml.safe_load`` only, a scan for executable keys, and
a strict pydantic model. Parse failures become stable findings so ``validate``
can report them like any other gate failure.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from beastforge.model.errors import BeastforgeError
from beastforge.model.findings import ValidationFinding
from beastforge.model.parts import PartInstance  # noqa: F401 - registers Recipe.parts
from beastforge.model.recipe import Recipe

_EXECUTABLE_KEYS = frozenset({"eval", "exec", "import", "__reduce__"})


class RecipeParseError(BeastforgeError):
    """A recipe could not be parsed; carries the findings that explain why."""

    def __init__(self, findings: list[ValidationFinding]) -> None:
        first = findings[0]
        super().__init__(
            first.code,
            first.message,
            location=first.location.model_dump(),
            expected=first.expected,
            actual=first.actual,
            remedy=first.remedy,
            suggestion=first.suggestion,
        )
        self.findings = findings


def _finding(
    code: str,
    message: str,
    *,
    recipe: str,
    path: str,
    expected: Any = None,
    actual: Any = None,
    remedy: str,
    suggestion: str | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity="error",
        location={"recipe": recipe, "path": path},
        message=message,
        expected=expected,
        actual=actual,
        remedy=remedy,
        suggestion=suggestion,
    )


def _scan_executable(document: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(key, str) and key in _EXECUTABLE_KEYS:
                hits.append(path)
            hits.extend(_scan_executable(value, path))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            hits.extend(_scan_executable(value, f"{prefix}[{index}]"))
    return hits


def load_yaml_document(path: Path, *, recipe_label: str | None = None) -> dict[str, Any]:
    """Load one YAML recipe as a mapping, rejecting executable content."""
    label = recipe_label or str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BeastforgeError(
            "recipe-not-found",
            f"Cannot read recipe {label}: {exc}",
            location={"recipe": label, "path": ""},
            remedy="Check the path and file permissions.",
            exit_code=4,
        ) from exc
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        code = "recipe-executable-content" if "python" in str(exc).lower() else "recipe-syntax"
        raise RecipeParseError(
            [
                _finding(
                    code,
                    f"Recipe {label} is not valid inert YAML: {exc}",
                    recipe=label,
                    path="",
                    expected="standard YAML scalars and collections",
                    actual=str(exc),
                    remedy="Remove custom tags and fix the YAML syntax.",
                )
            ]
        ) from exc
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise RecipeParseError(
            [
                _finding(
                    "recipe-syntax",
                    f"Recipe {label} must be a YAML mapping at the top level.",
                    recipe=label,
                    path="",
                    expected="mapping",
                    actual=type(document).__name__,
                    remedy="Start the recipe with `meta:` and the documented sections.",
                )
            ]
        )
    hits = _scan_executable(document)
    if hits:
        raise RecipeParseError(
            [
                _finding(
                    "recipe-executable-content",
                    f"Recipe {label} contains executable content at {hits[0]}.",
                    recipe=label,
                    path=hits[0],
                    expected="inert data only",
                    actual="executable key",
                    remedy="Remove eval/exec/import/__reduce__ keys; recipes never execute code.",
                )
            ]
        )
    return document


def _format_path(loc: tuple[Any, ...]) -> str:
    path = ""
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
        elif path:
            path += f".{part}"
        else:
            path = str(part)
    return path


def _collect_field_names(model: type, depth: int = 0, seen: set[type] | None = None) -> set[str]:
    """Best-effort set of field names across the nested model tree."""
    seen = seen or set()
    if model in seen or depth > 5:
        return set()
    seen.add(model)
    names: set[str] = set()
    for name, field in getattr(model, "model_fields", {}).items():
        names.add(name)
        annotation = field.annotation
        for candidate in _annotations(annotation):
            if isinstance(candidate, type) and hasattr(candidate, "model_fields"):
                names |= _collect_field_names(candidate, depth + 1, seen)
    return names


def _annotations(annotation: Any) -> list[Any]:
    import typing

    candidates = [annotation]
    origin = typing.get_origin(annotation)
    if origin is not None:
        candidates.extend(typing.get_args(annotation))
    if hasattr(annotation, "__args__"):
        candidates.extend(annotation.__args__)
    return candidates


def pydantic_findings(exc: ValidationError, *, recipe_label: str) -> list[ValidationFinding]:
    """Convert pydantic validation errors into stable findings."""
    findings: list[ValidationFinding] = []
    known = sorted(_collect_field_names(Recipe))
    for error in exc.errors():
        loc = tuple(error.get("loc", ()))
        path = _format_path(loc)
        error_type = str(error.get("type", ""))
        message = str(error.get("msg", "invalid value"))
        bad_key = str(loc[-1]) if loc else ""
        if error_type == "extra_forbidden":
            code = "recipe-unknown-field"
            suggestion = next(iter(difflib.get_close_matches(bad_key, known, n=1)), None)
            remedy = f"Remove `{bad_key}` or use a documented field."
            expected: Any = "a documented field"
        elif error_type == "missing":
            code = "recipe-syntax"
            suggestion = None
            remedy = f"Add the required field `{bad_key}`."
            expected = "required"
        elif error_type == "int_from_float" or (
            loc and str(loc[-1]) == "ticks" and "int" in error_type
        ):
            code = "clip-fractional-ticks"
            suggestion = None
            remedy = "Use an integer tick count at 60 Hz."
            expected = "integer"
        elif error_type.startswith(("int_", "float_", "bool_", "string_", "literal_")):
            code = "recipe-param-type"
            suggestion = None
            remedy = f"Use a value of the declared type for `{bad_key}`."
            expected = error_type
        else:
            code = "recipe-syntax"
            suggestion = None
            remedy = f"Fix `{path or 'the recipe'}` to match the documented grammar."
            expected = "valid recipe data"
        findings.append(
            _finding(
                code,
                f"{path or recipe_label}: {message}",
                recipe=recipe_label,
                path=path,
                expected=expected,
                actual=error.get("input"),
                remedy=remedy,
                suggestion=suggestion,
            )
        )
    return findings


def parse_recipe(document: dict[str, Any], *, recipe_label: str) -> Recipe:
    """Validate a loaded document against the strict recipe model."""
    try:
        return Recipe.model_validate(document)
    except ValidationError as exc:
        raise RecipeParseError(pydantic_findings(exc, recipe_label=recipe_label)) from exc


def load_recipe(path: Path, *, recipe_label: str | None = None) -> tuple[Recipe, dict[str, Any]]:
    """Load and parse one recipe file, returning the model and the raw document."""
    label = recipe_label or str(path)
    document = load_yaml_document(path, recipe_label=label)
    return parse_recipe(document, recipe_label=label), document
