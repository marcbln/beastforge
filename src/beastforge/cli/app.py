"""Typer application and the process-level error/exit-code handling."""

from __future__ import annotations

import sys

import click
import typer

from beastforge import __version__
from beastforge.cli.common import GlobalState, emit_error
from beastforge.cli.library import list_command
from beastforge.cli.meta_cmds import about_command, version_command
from beastforge.cli.params import params_command
from beastforge.cli.render import render_command
from beastforge.cli.showroom import showroom_command
from beastforge.cli.validate import validate_command
from beastforge.model.errors import BeastforgeError

HELP_CONTEXT = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="beastforge",
    help="Offline, deterministic procedural 3D creature generator.",
    add_completion=False,
    no_args_is_help=False,
    context_settings=HELP_CONTEXT,
)


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "-V", "--version", is_eager=True, help="Print version and exit."
    ),
    json_output: bool = typer.Option(False, "--json"),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    no_color: bool = typer.Option(False, "--no-color"),
    no_interaction: bool = typer.Option(False, "-n", "--no-interaction"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    debug: bool = typer.Option(False, "--debug"),
    trace: bool = typer.Option(False, "--trace"),
    library: str | None = typer.Option(None, "--library"),
    texforge_library: str | None = typer.Option(None, "--texforge-library"),
    config: str | None = typer.Option(None, "--config"),
) -> None:
    """Run a beastforge command; global flags work before or after the verb."""
    if version:
        typer.echo(f"beastforge {__version__}")
        raise typer.Exit()
    ctx.obj = GlobalState(
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
    if ctx.invoked_subcommand is None:
        typer.echo(click.get_current_context().get_help())
        raise typer.Exit()


app.command("list", context_settings=HELP_CONTEXT)(list_command)
app.command("params", context_settings=HELP_CONTEXT)(params_command)
app.command("render", context_settings=HELP_CONTEXT)(render_command)
app.command("validate", context_settings=HELP_CONTEXT)(validate_command)
app.command("showroom", context_settings=HELP_CONTEXT)(showroom_command)
app.command("version", context_settings=HELP_CONTEXT)(version_command)
app.command("about", context_settings=HELP_CONTEXT)(about_command)


def main() -> None:
    """Console-script entry point with stable error JSON and exit codes."""
    argv = sys.argv[1:]
    json_mode = "--json" in argv
    debug = "--debug" in argv or "--trace" in argv
    try:
        app(standalone_mode=False)
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.exit_code) from None
    except click.exceptions.UsageError as exc:
        error = BeastforgeError(
            "usage-error",
            str(exc),
            location={"path": ""},
            remedy="Run `beastforge --help` to see the command grammar.",
            exit_code=2,
        )
        emit_error(error, json_mode=json_mode)
        raise SystemExit(2) from None
    except click.ClickException as exc:
        error = BeastforgeError(
            "usage-error",
            exc.format_message(),
            location={"path": ""},
            remedy="Run `beastforge --help` to see the command grammar.",
            exit_code=2,
        )
        emit_error(error, json_mode=json_mode)
        raise SystemExit(2) from None
    except BeastforgeError as exc:
        emit_error(exc, json_mode=json_mode)
        raise SystemExit(exc.exit_code) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:  # noqa: BLE001 - last-resort CLI boundary
        if debug:
            import traceback

            traceback.print_exc()
        error = BeastforgeError(
            "internal-error",
            f"Unexpected failure: {exc}",
            location={"path": ""},
            remedy="Re-run with --debug for a traceback, then report the bug.",
            exit_code=1,
        )
        emit_error(error, json_mode=json_mode)
        raise SystemExit(1) from None


__all__ = ["app", "main"]
