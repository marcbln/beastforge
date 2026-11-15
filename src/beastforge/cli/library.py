"""``beastforge list`` — scan the catalog without generating (FR-002)."""

from __future__ import annotations

import typer

from beastforge.cli.common import emit_diagnostic, emit_json, merge_state, settings_for
from beastforge.library import scan_with_warnings


def list_command(
    ctx: typer.Context,
    category: str | None = typer.Option(None, "--category", help="Filter by category."),
    tag: list[str] = typer.Option([], "--tag", help="Filter by tag (repeatable, AND)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress diagnostics."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Extra diagnostics."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI color."),
    no_interaction: bool = typer.Option(False, "-n", "--no-interaction", help="Never prompt."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Apply nothing."),
    debug: bool = typer.Option(False, "--debug", help="Show stack traces."),
    trace: bool = typer.Option(False, "--trace", help="Show stack traces."),
    library: str | None = typer.Option(None, "--library", help="Library root."),
    texforge_library: str | None = typer.Option(
        None, "--texforge-library", help="texforge library root."
    ),
    config: str | None = typer.Option(None, "--config", help="Explicit config file."),
) -> None:
    """List library creatures by scanning recipes on demand."""
    from beastforge import __version__

    state = merge_state(
        ctx,
        json_output=json_output,
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        no_interaction=no_interaction,
        dry_run=dry_run,
        debug=debug,
        trace=trace,
        library=library,
        texforge_library=texforge_library,
        config=config,
    )
    settings = settings_for(state)
    entries, warnings = scan_with_warnings(settings)
    if category is not None:
        entries = [entry for entry in entries if entry.category == category]
    if tag:
        entries = [entry for entry in entries if all(item in entry.tags for item in tag)]
    if state.json_output:
        emit_json(
            {
                "schema_version": "1",
                "tool_version": __version__,
                "status": "ok",
                "creatures": [entry.to_json() for entry in entries],
            }
        )
    else:
        if not entries:
            typer.echo("No creatures found.")
        else:
            width = max((len(entry.name) for entry in entries), default=7)
            for entry in entries:
                typer.echo(f"{entry.name.ljust(width)}  {entry.category:<10}  {entry.description}")
    for warning in warnings:
        emit_diagnostic(f"warning: {warning}", quiet=state.quiet)
