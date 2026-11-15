"""``beastforge showroom`` — visual regression compare/accept (FR-039..FR-041)."""

from __future__ import annotations

import typer

from beastforge.cli.common import emit_json, merge_state, settings_for
from beastforge.model.manifest import showroom_json
from beastforge.showroom.runner import run_showroom


def showroom_command(
    ctx: typer.Context,
    sources: list[str] = typer.Argument(
        None, help="Creature names or recipe paths (default: whole library)."
    ),
    accept: bool = typer.Option(False, "--accept", help="Accept new references explicitly."),
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
    """Render turntable and extreme-bend frames and compare them to references."""
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
    outcome = run_showroom(sources or None, settings=settings, accept=accept)
    if state.json_output:
        emit_json(showroom_json(outcome.report))
    else:
        for creature in outcome.report.creatures:
            status = creature.comparison.status
            typer.echo(f"{creature.name}: {status}")
            for frame in creature.comparison.differing_frames:
                typer.echo(f"  differs: {frame}")
        typer.echo(f"showroom: {'ok' if outcome.ok else 'failed'}")
    raise typer.Exit(0 if outcome.ok else 3)
