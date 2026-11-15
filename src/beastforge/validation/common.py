"""Shared validation helpers and identifier rules."""

from __future__ import annotations

import re
from typing import Any

from beastforge.model.findings import ValidationFinding

IDENTIFIER_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
PARAM_RE = re.compile(r"^[a-z][a-z0-9-]*$")
MAX_IDENTIFIER = 64


def finding(
    code: str,
    message: str,
    *,
    recipe: str,
    path: str,
    expected: Any = None,
    actual: Any = None,
    remedy: str,
    suggestion: str | None = None,
    severity: str = "error",
) -> ValidationFinding:
    """Build a finding with a stable code."""
    return ValidationFinding(
        code=code,
        severity=severity,
        location={"recipe": recipe, "path": path},
        message=message,
        expected=expected,
        actual=actual,
        remedy=remedy,
        suggestion=suggestion,
    )


def check_identifier(name: str, *, recipe: str, path: str) -> ValidationFinding | None:
    """Reject names that are not stable lowercase identifiers."""
    if len(name) <= MAX_IDENTIFIER and IDENTIFIER_RE.match(name):
        return None
    return finding(
        "identifier-invalid",
        f"Name {name!r} is not a stable identifier.",
        recipe=recipe,
        path=path,
        expected="lowercase [a-z0-9._-], starting and ending with a letter or digit, <=64 chars",
        actual=name,
        remedy="Rename it to a lowercase slug such as ash-crowned-tyrant or spine-01.",
    )


def duplicates(names: list[str]) -> list[str]:
    """Return duplicate names in first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        if name in seen and name not in result:
            result.append(name)
        seen.add(name)
    return result
