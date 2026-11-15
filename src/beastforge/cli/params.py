"""``beastforge params`` — inspect declared knobs (FR-003)."""

from __future__ import annotations

import typer

from beastforge.cli.common import emit_json, merge_state, settings_for
from beastforge.library import project_relative, resolve_recipe_path
from beastforge.model.loader import load_recipe


def _param_payload(param) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": param.name,
        "type": param.type,
        "default": param.default,
        "description": param.description,
    }
    for key in ("min", "max", "values", "unit"):
        value = getattr(param, key)
        if value is not None:
            payload[key] = value
    return payload


def params_command(
    ctx: typer.Context,
    recipe: str = typer.Argument(..., help="Library name or explicit recipe path."),
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
    """Show one recipe's declared parameters without generating."""
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
    path = resolve_recipe_path(recipe, settings)
    label = project_relative(path)
    loaded, _document = load_recipe(path, recipe_label=label)
    payload = [_param_payload(param) for param in loaded.params]
    if state.json_output:
        emit_json(
            {
                "schema_version": "1",
                "tool_version": __version__,
                "status": "ok",
                "recipe": label,
                "name": loaded.meta.name,
                "params": payload,
            }
        )
        return
    typer.echo(f"{loaded.meta.name} ({label})")
    if not payload:
        typer.echo("No declared parameters.")
    for item in payload:
        limits = ""
        if "min" in item or "max" in item:
            limits = f" [{item.get('min', '-inf')}, {item.get('max', 'inf')}]"
        unit = f" {item['unit']}" if "unit" in item else ""
        typer.echo(
            f"  {item['name']}: {item['type']}{unit} = {item['default']!r}{limits}"
            f" — {item['description']}"
        )
