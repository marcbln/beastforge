"""``beastforge parts`` — read-only discovery of the part-preset library."""

from __future__ import annotations

import re

import typer

from beastforge import __version__
from beastforge.cli.common import emit_json, merge_state, settings_for
from beastforge.config import find_library_root
from beastforge.model.errors import BeastforgeError, NotFoundError, UsageError
from beastforge.model.parts import PartPreset
from beastforge.parts.registry import PresetRegistry, version_key
from beastforge.utils.canonical import canonical_json

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _surface_default(preset: PartPreset, key: str) -> float | int:
    surface = preset.surface
    if key == "radius-start":
        return (
            surface.radius.start
            if hasattr(surface.radius, "start")
            else float(surface.radius[0])
        )
    if key == "radius-end":
        return surface.radius.end if hasattr(surface.radius, "end") else float(surface.radius[-1])
    if key == "rings":
        return surface.rings
    if key == "segments":
        return surface.segments
    if key == "blend":
        return surface.blend
    if key in {"taper-start", "taper-end"}:
        taper = surface.modifiers.taper
        if taper is None:
            return 0.0
        return taper.start if key == "taper-start" else taper.end
    if key == "twist":
        return surface.modifiers.twist
    if key.startswith("noise-"):
        noise = surface.modifiers.radial_noise
        if noise is None:
            return 0
        return {
            "noise-amplitude": noise.amplitude,
            "noise-frequency": noise.frequency,
            "noise-seed": noise.seed,
        }[key]
    if key.startswith("squash-"):
        return float(surface.modifiers.squash[{"x": 0, "y": 1, "z": 2}[key[-1]]])
    if key.startswith("scale-"):
        return float(surface.modifiers.scale[{"x": 0, "y": 1, "z": 2}[key[-1]]])
    return 0.0


def _param_json(preset: PartPreset) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for param in sorted(preset.params, key=lambda item: item.name):
        row: dict[str, object] = {
            "name": param.name,
            "type": param.type,
            "default": _surface_default(preset, param.name),
            "description": param.description,
        }
        if param.min is not None:
            row["min"] = param.min
        if param.max is not None:
            row["max"] = param.max
        if param.unit is not None:
            row["unit"] = param.unit
        rows.append(row)
    return rows


def _control_json(preset: PartPreset) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for control in preset.controls:
        unbounded = control.unbounded if control.unbounded is not None else control.range is None
        row: dict[str, object] = {
            "name": control.name,
            "joint": control.joint,
            "axis": [float(value) for value in control.axis],
            "mode": control.mode,
            "unbounded": bool(unbounded),
            "default": float(control.default),
            "units": control.units,
        }
        if control.range is not None and not unbounded:
            row["range"] = {"min": control.range.min, "max": control.range.max}
        rows.append(row)
    return rows


def _auto_json(preset: PartPreset) -> list[dict[str, object]]:
    return [behaviour.model_dump(mode="json") for behaviour in preset.auto]


def _preset_json(preset: PartPreset) -> dict[str, object]:
    return {
        "name": preset.name,
        "family": preset.family,
        "version": preset.version,
        "description": preset.description,
        "path": preset.path,
        "sha256": preset.sha256,
        "params": _param_json(preset),
        "controls": _control_json(preset),
        "auto": _auto_json(preset),
    }


def parts_command(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help="Preset name; omit to list every preset."),
    family: str | None = typer.Option(None, "--family", help="organic|mechanical|vehicle"),
    version: str | None = typer.Option(None, "--version", help="Exact MAJOR.MINOR.PATCH."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress the human table."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Extra diagnostics."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI color."),
    no_interaction: bool = typer.Option(False, "-n", "--no-interaction", help="Never prompt."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Accepted no-op; nothing is written."),
    debug: bool = typer.Option(False, "--debug", help="Show stack traces."),
    trace: bool = typer.Option(False, "--trace", help="Show stack traces."),
    library: str | None = typer.Option(None, "--library", help="Library root."),
    texforge_library: str | None = typer.Option(
        None, "--texforge-library", help="texforge library root."
    ),
    config: str | None = typer.Option(None, "--config", help="Explicit config file."),
) -> None:
    """List immutable part presets and their declared parameters and controls."""
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
    if family is not None and family not in {"organic", "mechanical", "vehicle"}:
        raise UsageError(
            "usage-error",
            f"Unknown family {family!r}.",
            remedy="Use --family organic, mechanical, or vehicle.",
        )
    if version is not None:
        if name is None:
            raise UsageError(
                "usage-error",
                "--version requires a preset NAME.",
                remedy="Run `beastforge parts <name> --version 1.0.0`.",
            )
        if not VERSION_RE.match(version):
            raise UsageError(
                "usage-error",
                f"Invalid version {version!r}.",
                remedy="Use a MAJOR.MINOR.PATCH version such as 1.0.0.",
            )

    settings = settings_for(state)
    root = find_library_root(settings)
    parts_root = root / "parts"
    if not parts_root.is_dir():
        raise NotFoundError(
            "parts-library-missing",
            f"No parts library found at {parts_root}.",
            location={"path": str(parts_root)},
            remedy="Run from the repository root or pass --library.",
        )
    registry = PresetRegistry.from_library_root(root)
    if registry.warnings:
        first = registry.warnings[0]
        raise BeastforgeError(
            "preset-file-invalid",
            f"Cannot list presets: {first.message} ({first.path}).",
            location={"path": first.path},
            expected="well-formed preset files",
            actual=first.message,
            remedy="Fix the preset file; see --verbose for scan scope.",
        )

    presets = registry.all_presets()
    if name is not None:
        if name not in registry.names():
            raise NotFoundError(
                "part-preset-missing",
                f"No preset named {name!r} exists in the library.",
                location={"path": f"parts/{name}"},
                expected=sorted(registry.names()),
                actual=name,
                remedy="Run `beastforge parts` to list available presets.",
            )
        if version is not None and registry.get(name, version) is None:
            raise NotFoundError(
                "part-preset-version-missing",
                f"Preset {name!r} has no version {version!r}.",
                location={"path": f"parts/{name}/{version}.yaml"},
                expected=registry.versions(name),
                actual=version,
                remedy="Pin an available version.",
            )
        presets = [preset for preset in presets if preset.name == name]
        if version is not None:
            presets = [preset for preset in presets if preset.version == version]
    if family is not None:
        presets = [preset for preset in presets if preset.family == family]
    presets.sort(key=lambda preset: (preset.name, version_key(preset.version)))

    if state.json_output:
        emit_json(
            {
                "schema_version": "1",
                "tool_version": __version__,
                "status": "ok",
                "presets": [_preset_json(preset) for preset in presets],
                "warnings": [warning.to_json() for warning in registry.warnings],
            }
        )
        return
    if state.quiet:
        return
    if name is not None and len(presets) == 1:
        _echo_detail(presets[0])
        return
    _echo_table(presets)


def _echo_table(presets: list[PartPreset]) -> None:
    typer.echo(f"{'NAME':<22}{'FAMILY':<13}{'VERSION':<9}{'CONTROLS':<10}{'AUTO':<6}DESCRIPTION")
    for preset in presets:
        typer.echo(
            f"{preset.name:<22}{preset.family:<13}{preset.version:<9}"
            f"{len(preset.controls):<10}{len(preset.auto):<6}{preset.description}"
        )


def _echo_detail(preset: PartPreset) -> None:
    typer.echo(f"{preset.name} {preset.version} ({preset.family})")
    typer.echo(preset.description)
    typer.echo(f"Path: {preset.path}")
    typer.echo(f"Preset sha256: {preset.sha256}")
    typer.echo("")
    typer.echo("Parameters")
    for item in _param_json(preset):
        limits = ""
        if "min" in item or "max" in item:
            limits = f"{item.get('min', '-inf')}..{item.get('max', 'inf')}"
        typer.echo(
            f"  {item['name']}: {item['type']} = {item['default']!r} {limits}"
            f" — {item['description']}"
        )
    typer.echo("")
    typer.echo("Controls")
    controls = _control_json(preset)
    if not controls:
        typer.echo("  (none)")
    for control in controls:
        span = "unbounded" if control["unbounded"] else str(control.get("range"))
        typer.echo(
            f"  {control['name']}: {control['joint']} {control['mode']} "
            f"axis={control['axis']} {span} default={control['default']} {control['units']}"
        )
    typer.echo("")
    typer.echo("Automatic behaviours")
    autos = _auto_json(preset)
    if not autos:
        typer.echo("  (none)")
    for behaviour in autos:
        typer.echo(f"  {canonical_json(behaviour, trailing_newline=False)}")
