"""Declared-parameter resolution and ``--set`` overrides (FR-005, FR-026)."""

from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass
from typing import Any

from beastforge.model.errors import BeastforgeError, UsageError
from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Param, Recipe

_FLOAT_TOLERANCE = 1e-9


@dataclass
class ParamResolution:
    """Resolved values plus any non-fatal findings from declared defaults."""

    values: dict[str, Any]
    findings: list[ValidationFinding]


def parse_set_tokens(tokens: list[str]) -> dict[str, str]:
    """Split repeated ``KEY=VALUE`` overrides, rejecting malformed tokens."""
    overrides: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            raise UsageError(
                "set-syntax",
                f"Malformed --set value {token!r}; expected KEY=VALUE.",
                remedy="Pass --set key=value, for example --set body-length=3.1.",
            )
        key, raw = token.split("=", 1)
        key = key.strip()
        if not key:
            raise UsageError(
                "set-syntax",
                f"Malformed --set value {token!r}; the key is empty.",
                remedy="Pass --set key=value, for example --set body-length=3.1.",
            )
        overrides[key] = raw
    return overrides


def _coerce_scalar(raw: str) -> Any:
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        value = raw
    return value


def _type_ok(param: Param, value: Any) -> bool:
    if param.type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if param.type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if param.type == "bool":
        return isinstance(value, bool)
    if param.type == "string":
        return isinstance(value, str)
    if param.type == "enum":
        return value in (param.values or [])
    return False


def _coerce(param: Param, raw: Any) -> Any:
    if param.type == "int":
        if isinstance(raw, bool):
            raise ValueError("boolean is not an integer")
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            if not raw.is_integer():
                raise ValueError("fractional value for an int parameter")
            return int(raw)
        if isinstance(raw, str):
            return int(raw.strip(), 10)
        raise ValueError("expected an integer")
    if param.type == "float":
        if isinstance(raw, bool):
            raise ValueError("boolean is not a float")
        return float(raw)
    if param.type == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, int) and raw in (0, 1):
            return bool(raw)
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "yes", "1", "on"}:
                return True
            if lowered in {"false", "no", "0", "off"}:
                return False
        raise ValueError("expected a boolean")
    if param.type == "string":
        return str(raw)
    if param.type == "enum":
        if raw in (param.values or []):
            return raw
        if isinstance(raw, str):
            for candidate in param.values or []:
                if str(candidate) == raw:
                    return candidate
        raise ValueError(f"expected one of {param.values}")
    raise ValueError(f"unsupported parameter type {param.type!r}")


def _range_ok(param: Param, value: float) -> bool:
    below = param.min is not None and value < param.min - _FLOAT_TOLERANCE
    above = param.max is not None and value > param.max + _FLOAT_TOLERANCE
    return not (below or above)


def _finding(
    code: str,
    message: str,
    *,
    recipe: str,
    path: str,
    expected: Any,
    actual: Any,
    remedy: str,
    suggestion: str | None = None,
    severity: str = "error",
) -> ValidationFinding:
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


def resolve_params(
    recipe: Recipe,
    overrides: dict[str, Any] | None = None,
    *,
    recipe_label: str = "",
    strict: bool = False,
) -> ParamResolution:
    """Merge declared defaults with overrides, enforcing type and range.

    ``strict`` makes the first finding an exception (used by ``render``); the
    non-strict form returns findings so ``validate`` can report all of them.
    """
    overrides = overrides or {}
    declared = {param.name: param for param in recipe.params}
    findings: list[ValidationFinding] = []
    resolved: dict[str, Any] = {}

    for param in recipe.params:
        try:
            value = _coerce(param, param.default)
        except (TypeError, ValueError) as exc:
            findings.append(
                _finding(
                    "recipe-param-type",
                    f"Default for parameter {param.name!r} does not match "
                    f"its declared type: {exc}.",
                    recipe=recipe_label,
                    path=f"params[{param.name}]",
                    expected=param.type,
                    actual=param.default,
                    remedy="Change the parameter default or its declared type.",
                )
            )
            continue
        if not _range_ok(param, float(value)) if isinstance(value, (int, float)) else False:
            findings.append(
                _finding(
                    "recipe-param-range",
                    f"Default for parameter {param.name!r} is outside [{param.min}, {param.max}].",
                    recipe=recipe_label,
                    path=f"params[{param.name}]",
                    expected={"min": param.min, "max": param.max},
                    actual=value,
                    remedy="Adjust the default or the declared limits.",
                )
            )
        resolved[param.name] = value

    for key, raw in overrides.items():
        if key not in declared:
            suggestion = next(iter(difflib.get_close_matches(key, sorted(declared), n=1)), None)
            message = f"Parameter {key!r} is not declared by recipe {recipe.meta.name!r}."
            if suggestion:
                message += f" Did you mean {suggestion!r}?"
            finding = _finding(
                "recipe-unknown-param",
                message,
                recipe=recipe_label,
                path="params",
                expected=f"one of: {', '.join(sorted(declared)) or '(none)'}",
                actual=key,
                remedy=f"Use --set {suggestion}=... or add the parameter to params[]."
                if suggestion
                else "Use a declared parameter name or add it to params[].",
                suggestion=suggestion,
            )
            findings.append(finding)
            continue
        param = declared[key]
        try:
            value = _coerce(param, raw)
        except (TypeError, ValueError) as exc:
            findings.append(
                _finding(
                    "recipe-param-type",
                    f"Value {raw!r} for parameter {key!r} is not a valid {param.type}: {exc}.",
                    recipe=recipe_label,
                    path=f"params[{key}]",
                    expected=param.type,
                    actual=raw,
                    remedy=f"Pass a valid {param.type} value.",
                )
            )
            continue
        if isinstance(value, (int, float)) and not _range_ok(param, float(value)):
            findings.append(
                _finding(
                    "recipe-param-range",
                    f"Value {value!r} for parameter {key!r} is outside [{param.min}, {param.max}].",
                    recipe=recipe_label,
                    path=f"params[{key}]",
                    expected={"min": param.min, "max": param.max},
                    actual=value,
                    remedy="Choose a value inside the declared limits.",
                )
            )
            continue
        resolved[key] = value

    if strict and findings:
        first = findings[0]
        raise BeastforgeError(
            first.code,
            first.message,
            location=first.location.model_dump(),
            expected=first.expected,
            actual=first.actual,
            remedy=first.remedy,
            suggestion=first.suggestion,
        )
    return ParamResolution(values=resolved, findings=findings)
