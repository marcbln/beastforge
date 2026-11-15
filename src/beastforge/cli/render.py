"""``beastforge render`` — generate a creature package (FR-005..FR-013)."""

from __future__ import annotations

import typer

from beastforge.cli.common import emit_json, merge_state, settings_for
from beastforge.model.manifest import report_json
from beastforge.render import render


def render_command(
    ctx: typer.Context,
    recipe: str = typer.Argument(..., help="Library name or explicit recipe path."),
    out: str | None = typer.Option(None, "-o", "--out", help="Output directory."),
    set_values: list[str] = typer.Option(
        [], "--set", help="KEY=VALUE parameter override (repeatable)."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing outputs."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan; write nothing."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress diagnostics."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Extra diagnostics."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI color."),
    no_interaction: bool = typer.Option(False, "-n", "--no-interaction", help="Never prompt."),
    debug: bool = typer.Option(False, "--debug", help="Show stack traces."),
    trace: bool = typer.Option(False, "--trace", help="Show stack traces."),
    library: str | None = typer.Option(None, "--library", help="Library root."),
    texforge_library: str | None = typer.Option(
        None, "--texforge-library", help="texforge library root."
    ),
    config: str | None = typer.Option(None, "--config", help="Explicit config file."),
) -> None:
    """Generate one creature and its sidecar manifest."""
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
    outcome = render(
        recipe,
        settings=settings,
        out_dir=out,
        set_values=set_values,
        force=force,
        dry_run=state.dry_run,
    )
    report = outcome.report
    if state.json_output:
        emit_json(report_json(report))
        return
    if report.dry_run:
        typer.echo("dry run: nothing written")
    typer.echo(f"glb:      {report.outputs.glb.path}")
    if report.outputs.glb.sha256:
        typer.echo(f"sha256:   {report.outputs.glb.sha256}")
    typer.echo(f"manifest: {report.outputs.manifest.path}")
    if report.outputs.manifest.sha256:
        typer.echo(f"sha256:   {report.outputs.manifest.sha256}")
    typer.echo(
        "inventory: "
        f"{len(report.inventory.clips)} clips, "
        f"{len(report.inventory.events)} events, "
        f"{len(report.inventory.sockets)} sockets, "
        f"{len(report.inventory.volumes)} volumes, "
        f"{len(report.inventory.phases)} phases"
    )
    for warning in report.warnings:
        typer.echo(f"warning: {warning}", err=True)
