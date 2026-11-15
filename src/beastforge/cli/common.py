"""Shared CLI state, settings resolution, and output helpers."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from beastforge import __version__
from beastforge.config import Settings, resolve_settings
from beastforge.model.errors import BeastforgeError
from beastforge.utils.canonical import canonical_json


@dataclass
class GlobalState:
    """Global flags merged from before and after the subcommand."""

    json_output: bool = False
    quiet: bool = False
    verbose: bool = False
    no_color: bool = False
    no_interaction: bool = False
    dry_run: bool = False
    debug: bool = False
    trace: bool = False
    library: str | None = None
    texforge_library: str | None = None
    config: str | None = None


def merge_state(
    ctx: typer.Context,
    *,
    json_output: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
    no_interaction: bool = False,
    dry_run: bool = False,
    debug: bool = False,
    trace: bool = False,
    library: str | None = None,
    texforge_library: str | None = None,
    config: str | None = None,
) -> GlobalState:
    """Merge local flags into the root state without losing pre-subcommand flags."""
    base = ctx.obj if isinstance(ctx.obj, GlobalState) else GlobalState()
    base.json_output = base.json_output or json_output
    base.quiet = base.quiet or quiet
    base.verbose = base.verbose or verbose
    base.no_color = base.no_color or no_color
    base.no_interaction = base.no_interaction or no_interaction
    base.dry_run = base.dry_run or dry_run
    base.debug = base.debug or debug
    base.trace = base.trace or trace
    if library is not None:
        base.library = library
    if texforge_library is not None:
        base.texforge_library = texforge_library
    if config is not None:
        base.config = config
    return base


def settings_for(state: GlobalState, *, cwd: Path | None = None) -> Settings:
    """Resolve settings and apply the highest-precedence flags."""
    settings = resolve_settings(state.config, cwd=cwd)
    if state.library is not None:
        settings.library = state.library
    if state.texforge_library is not None:
        settings.texforge_library = state.texforge_library
    if state.no_color:
        settings.color = "never"
    return settings


def emit_json(payload: Any) -> None:
    """Write a canonical JSON document to stdout with no decoration."""
    sys.stdout.write(canonical_json(payload))
    sys.stdout.flush()


def emit_text(text: str) -> None:
    """Write human result text to stdout."""
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    sys.stdout.flush()


def emit_diagnostic(text: str, *, quiet: bool = False) -> None:
    """Write a non-error diagnostic to stderr."""
    if quiet:
        return
    sys.stderr.write(text if text.endswith("\n") else text + "\n")
    sys.stderr.flush()


def error_payload(exc: BeastforgeError) -> dict[str, Any]:
    """Map a beastforge error to the published error schema."""
    error: dict[str, Any] = {
        "code": exc.code,
        "message": exc.message,
        "location": dict(exc.location),
        "expected": exc.expected,
        "actual": exc.actual,
        "remedy": exc.remedy,
    }
    if exc.suggestion is not None:
        error["suggestion"] = exc.suggestion
    return {
        "schema_version": "1",
        "tool_version": __version__,
        "status": "error",
        "error": error,
    }


def emit_error(exc: BeastforgeError, *, json_mode: bool) -> None:
    """Print one error in JSON or human form."""
    if json_mode:
        emit_json(error_payload(exc))
        return
    sys.stderr.write(f"error: {exc.message}\n")
    if exc.suggestion:
        sys.stderr.write(f"hint: {exc.suggestion}\n")
    if exc.remedy:
        sys.stderr.write(f"try: {exc.remedy}\n")
    sys.stderr.flush()
