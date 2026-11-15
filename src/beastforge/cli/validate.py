"""``beastforge validate`` — run the gate (FR-034..FR-038)."""

from __future__ import annotations

import typer

from beastforge.cli.common import emit_json, merge_state, settings_for
from beastforge.validation.runner import validate_library, validate_recipe


def validate_command(
    ctx: typer.Context,
    recipe: str | None = typer.Argument(None, help="Library name or explicit recipe path."),
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
    """Validate one recipe or the whole library."""
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
    outcome = (
        validate_recipe(recipe, settings) if recipe is not None else validate_library(settings)
    )
    if state.json_output:
        emit_json(outcome.to_json())
    else:
        for finding in outcome.findings:
            location = finding.location.path or finding.location.recipe
            typer.echo(f"{finding.severity}: {finding.code} at {location}")
            typer.echo(f"  {finding.message}")
            typer.echo(f"  try: {finding.remedy}")
        typer.echo(
            f"{'valid' if outcome.valid else 'invalid'}: "
            f"{outcome.errors} errors, {outcome.warnings} warnings, "
            f"{len(outcome.creatures)} creatures checked"
        )
    raise typer.Exit(0 if outcome.valid else 3)
