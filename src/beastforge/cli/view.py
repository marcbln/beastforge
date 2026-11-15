"""``beastforge view`` — local gallery server or static export.

Serve mode binds the loopback HTTP server and streams generation progress to
stderr. Export mode dispatches to :mod:`beastforge.viewer.export`. The command is
a thin boundary: catalog derivation, caching, serving, and export live in the
``viewer`` package.
"""

from __future__ import annotations

import signal
import threading
import webbrowser
from pathlib import Path
from typing import Any

import typer

from beastforge import __version__
from beastforge.cli.common import (
    GlobalState,
    emit_diagnostic,
    emit_json,
    emit_text,
    merge_state,
    settings_for,
)
from beastforge.config import resolve_cache_dir
from beastforge.model.errors import IOFailure, UsageError
from beastforge.viewer.cache import AssetCache
from beastforge.viewer.catalog import build_catalog
from beastforge.viewer.server import create_server

USAGE_REMEDY = "Run `beastforge view --help` to see the command grammar."


def _usage(message: str) -> UsageError:
    return UsageError("usage-error", message, remedy=USAGE_REMEDY)


def view_command(
    ctx: typer.Context,
    export: str | None = typer.Option(
        None, "--export", metavar="DIR", help="Write a self-contained static bundle to DIR."
    ),
    port: int | None = typer.Option(
        None, "--port", metavar="N", help="Bind 127.0.0.1:N (0 chooses a free port)."
    ),
    cache_dir: str | None = typer.Option(
        None, "--cache-dir", metavar="DIR", help="Local generation cache."
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open a browser (serve mode)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Replace the exporter's own outputs in a non-empty target."
    ),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan; write/bind nothing."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress progress diagnostics."),
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
    """Browse the library locally or export it as a static site."""
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

    _validate_combinations(export=export, port=port, cache_dir=cache_dir, force=force)

    if export is not None:
        _run_export(state, settings, output=export, force=force)
        return
    _run_serve(state, settings, port=port or 0, cache_dir=cache_dir, no_browser=no_browser)


def _validate_combinations(
    *,
    export: str | None,
    port: int | None,
    cache_dir: str | None,
    force: bool,
) -> None:
    if export is not None and port is not None:
        raise _usage("--export cannot be combined with --port.")
    if export is not None and cache_dir is not None:
        raise _usage("--export cannot be combined with --cache-dir.")
    if force and export is None:
        raise _usage("--force is only valid with --export DIR.")
    if port is not None and port != 0 and not 1 <= port <= 65535:
        raise _usage(f"--port must be 0 or between 1 and 65535, got {port}.")


# -- serve mode -----------------------------------------------------------
def _run_serve(
    state: GlobalState,
    settings: Any,
    *,
    port: int,
    cache_dir: str | None,
    no_browser: bool,
) -> None:
    cache_root = resolve_cache_dir(settings, cache_dir)
    document = build_catalog(settings)
    sha_by_name = {entry.name: entry.recipe_sha256 for entry in document.creatures}

    for warning in document.warnings:
        emit_diagnostic(f"warning: {warning.path}: {warning.message}", quiet=state.quiet)

    if state.dry_run:
        _report_serve(
            url=None,
            cache_root=cache_root,
            json_output=state.json_output,
            dry_run=True,
        )
        return

    def on_event(kind: str, name: str) -> None:
        if state.quiet:
            return
        if kind == "generating":
            sha = sha_by_name.get(name)
            suffix = f" ({sha[:7]})" if sha else ""
            emit_diagnostic(f"generating {name}{suffix}…")
        elif kind == "ready":
            emit_diagnostic(f"ready {name}")

    cache = AssetCache(cache_root, settings, on_event=on_event)
    cache.cleanup_stale_temp()
    try:
        server = create_server(
            settings,
            cache=cache,
            port=port,
            verbose=state.verbose,
        )
    except OSError as exc:
        raise IOFailure(
            "io-failure",
            f"Cannot bind 127.0.0.1:{port}: {exc}",
            location={"path": f"127.0.0.1:{port}"},
            remedy="Pass --port 0 for an ephemeral port or choose another port.",
        ) from exc

    url = server.url

    def on_ready() -> None:
        _report_serve(
            url=url,
            cache_root=cache_root,
            json_output=state.json_output,
            dry_run=False,
        )
        if not state.json_output and not no_browser:
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001 - a missing browser must not stop the server
                emit_diagnostic("warning: could not open a browser; use the printed URL.")

    _serve_until_stopped(server, on_ready)


def _report_serve(*, url: str | None, cache_root: Path, json_output: bool, dry_run: bool) -> None:
    if json_output:
        emit_json(
            {
                "schema_version": "1",
                "tool_version": __version__,
                "status": "ok",
                "mode": "serve",
                "url": url,
                "cache_dir": str(cache_root),
                "dry_run": dry_run,
            }
        )
        return
    if dry_run:
        emit_text("viewer: (not bound; dry run)")
    else:
        emit_text(f"viewer: {url}")
    emit_text(f"cache:  {cache_root}")
    if not dry_run:
        emit_text("serving the current library; press Ctrl-C to stop")


def _serve_until_stopped(server: Any, on_ready: Any) -> None:
    stop = threading.Event()
    received: list[int] = []

    def handler(signum: int, _frame: Any) -> None:
        received.append(signum)
        stop.set()

    previous_int = signal.signal(signal.SIGINT, handler)
    previous_term = signal.signal(signal.SIGTERM, handler)
    thread = threading.Thread(target=server.serve_forever, name="beastforge-view", daemon=True)
    thread.start()
    try:
        on_ready()
        stop.wait()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)
    if signal.SIGINT in received:
        raise SystemExit(130)


# -- export mode ----------------------------------------------------------
def _run_export(state: GlobalState, settings: Any, *, output: str, force: bool) -> None:
    from beastforge.viewer.export import plan_export, write_export

    plan = plan_export(settings)
    outcome = write_export(plan, output, force=force, dry_run=state.dry_run)

    for warning in outcome.warnings:
        emit_diagnostic(f"warning: {warning}", quiet=state.quiet)

    if state.json_output:
        emit_json(
            {
                "schema_version": "1",
                "tool_version": __version__,
                "status": "ok",
                "mode": "export",
                "output": output,
                "creatures": sorted(outcome.creatures),
                "files": outcome.files,
                "warnings": list(outcome.warnings),
                "dry_run": outcome.dry_run,
            }
        )
        return
    if outcome.dry_run:
        emit_text("dry run: nothing written")
        emit_text(
            f"would export {len(outcome.creatures)} creatures / {outcome.files} files to {output}"
        )
        return
    emit_text(f"exported {len(outcome.creatures)} creatures / {outcome.files} files to {output}")
