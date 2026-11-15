"""Generation adapter: staging directory, texture rendering, atomic commit, report.

The build core is pure; this module owns every filesystem and texforge side
effect (research D5/D10, FR-007/012).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from beastforge import __version__
from beastforge.config import Settings, find_library_root, find_texforge_library
from beastforge.export.gltf import TextureImage, build_glb
from beastforge.export.manifest import build_manifest, manifest_json, ordered_clips
from beastforge.library import project_relative, resolve_recipe_path
from beastforge.model.errors import BeastforgeError, IOFailure
from beastforge.model.findings import ValidationFinding
from beastforge.model.loader import load_recipe
from beastforge.model.manifest import (
    GenerationReport,
    Manifest,
    ReportFile,
    ReportInventory,
    ReportInventoryEvent,
    ReportOutputs,
    ReportProvenance,
    ReportTexture,
)
from beastforge.model.recipe import Recipe
from beastforge.params import parse_set_tokens
from beastforge.pipeline import BuiltCreature, prepare
from beastforge.texture.texforge_adapter import TexforgeLibrary, texforge_version
from beastforge.utils.canonical import canonical_json, sha256_hex
from beastforge.validation.gate import ValidationFailed, error_findings, run_gate


@dataclass
class RenderOutcome:
    """Everything one render produced, for the CLI and tests."""

    report: GenerationReport
    manifest: Manifest | None
    glb: bytes | None
    manifest_text: str | None
    textures: list[TextureImage]


def output_directory(recipe: Recipe, settings: Settings, out_dir: str | None) -> Path:
    """Resolve the directory that receives ``<name>.glb`` and the manifest."""
    if out_dir is not None:
        return Path(out_dir)
    return Path(settings.output_dir) / recipe.meta.name


def _inventory(recipe: Recipe) -> ReportInventory:
    clips = ordered_clips(recipe.clips)
    events: list[ReportInventoryEvent] = []
    for clip in clips:
        for event in clip.events:
            time = event.ticks / 60.0 if event.ticks is not None else float(event.time or 0.0)
            events.append(ReportInventoryEvent(clip=clip.name, time=time, name=event.name))
    return ReportInventory(
        clips=[clip.name for clip in clips],
        events=events,
        sockets=[socket.name for socket in recipe.sockets],
        volumes=[volume.name for volume in recipe.volumes],
        phases=[phase.name for phase in recipe.phases],
    )


def _validation_check(
    built: BuiltCreature,
    *,
    recipe_label: str,
    file_stem: str,
    settings: Settings,
    texforge_root: Path | None,
    manifest: Manifest | None = None,
) -> list[ValidationFinding]:
    return run_gate(
        built.recipe,
        recipe_label=recipe_label,
        file_stem=file_stem,
        document=built.document,
        settings=settings,
        skeleton=built.skeleton,
        mesh=built.mesh,
        manifest=manifest,
        texforge_root=texforge_root,
    )


def render(
    source: str,
    *,
    settings: Settings,
    out_dir: str | None = None,
    set_values: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    cwd: Path | None = None,
    tool_version: str = __version__,
) -> RenderOutcome:
    """Generate one creature package, gated before commit."""
    started = time.perf_counter()
    path = resolve_recipe_path(source, settings, cwd=cwd)
    label = project_relative(path, cwd=cwd)
    recipe, document = load_recipe(path, recipe_label=label)
    overrides = parse_set_tokens(set_values or [])
    built = prepare(
        recipe,
        document=document,
        recipe_path=label,
        overrides=overrides,
        tool_version=tool_version,
    )
    library_root = find_library_root(settings, cwd=cwd)
    texforge_root = find_texforge_library(settings, library_root=library_root)
    findings = _validation_check(
        built,
        recipe_label=label,
        file_stem=path.stem,
        settings=settings,
        texforge_root=texforge_root,
    )
    errors = error_findings(findings)
    if errors:
        raise ValidationFailed(errors)

    target_dir = output_directory(recipe, settings, out_dir)
    glb_path = target_dir / f"{recipe.meta.name}.glb"
    manifest_path = target_dir / f"{recipe.meta.name}.manifest.json"
    warnings = [item.message for item in findings if item.severity == "warning"]

    if dry_run:
        report = GenerationReport(
            tool_version=tool_version,
            dry_run=True,
            outputs=ReportOutputs(
                glb=ReportFile(path=str(glb_path)),
                manifest=ReportFile(path=str(manifest_path)),
                textures=[],
            ),
            inventory=_inventory(recipe),
            effective_params={key: _scalar(value) for key, value in built.resolved_params.items()},
            provenance=ReportProvenance(
                recipe=label,
                recipe_sha256=built.recipe_sha256,
                tool_version=tool_version,
            ),
            warnings=warnings,
            timing_ms=(time.perf_counter() - started) * 1000.0,
        )
        return RenderOutcome(
            report=report, manifest=None, glb=None, manifest_text=None, textures=[]
        )

    if not force and (glb_path.exists() or manifest_path.exists()):
        raise IOFailure(
            "output-exists",
            f"Output already exists for {recipe.meta.name!r}: {glb_path} or {manifest_path}.",
            location={"path": str(target_dir)},
            expected="a clean output directory",
            actual="existing output pair",
            remedy="Pass --force to overwrite, or choose a different -o directory.",
        )
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".beastforge-tmp-", dir=target_dir))
    except OSError as exc:
        raise IOFailure(
            "io-failure",
            f"Cannot create output directory {target_dir}: {exc}",
            location={"path": str(target_dir)},
            remedy="Check permissions and that the path is writable.",
        ) from exc

    try:
        library = TexforgeLibrary(texforge_root)
        textures = [
            library.render_material(material, staging_dir=staging) for material in recipe.materials
        ]
        manifest = build_manifest(
            recipe=recipe,
            recipe_path=label,
            recipe_sha256=built.recipe_sha256,
            resolved_params=built.resolved_params,
            skeleton=built.skeleton,
            mesh=built.mesh,
            baked_clips=built.clips,
            textures=textures,
            tool_version=tool_version,
            texforge_version=texforge_version(),
        )
        final_findings = _validation_check(
            built,
            recipe_label=label,
            file_stem=path.stem,
            settings=settings,
            texforge_root=texforge_root,
            manifest=manifest,
        )
        final_errors = error_findings(final_findings)
        if final_errors:
            raise ValidationFailed(final_errors)
        warnings.extend(item.message for item in final_findings if item.severity == "warning")

        glb = build_glb(
            recipe=recipe,
            skeleton=built.skeleton,
            mesh=built.mesh,
            clips=built.clips,
            textures=textures,
            tool_version=tool_version,
        )
        manifest_text = canonical_json(manifest_json(manifest))
        staged_glb = staging / glb_path.name
        staged_manifest = staging / manifest_path.name
        staged_glb.write_bytes(glb)
        staged_manifest.write_text(manifest_text, encoding="utf-8")

        _verify_staged_glb(staged_glb)
        os.replace(staged_glb, glb_path)
        os.replace(staged_manifest, manifest_path)

        report = GenerationReport(
            tool_version=tool_version,
            dry_run=False,
            outputs=ReportOutputs(
                glb=ReportFile(path=str(glb_path), sha256=sha256_hex(glb), bytes=len(glb)),
                manifest=ReportFile(
                    path=str(manifest_path),
                    sha256=sha256_hex(manifest_text.encode("utf-8")),
                    bytes=len(manifest_text.encode("utf-8")),
                ),
                textures=[
                    ReportTexture(
                        name=texture.material,
                        sha256=texture.sha256,
                        width=texture.width,
                        height=texture.height,
                        recipe=texture.recipe,
                    )
                    for texture in textures
                ],
            ),
            inventory=_inventory(recipe),
            effective_params={key: _scalar(value) for key, value in built.resolved_params.items()},
            provenance=ReportProvenance(
                recipe=label,
                recipe_sha256=built.recipe_sha256,
                tool_version=tool_version,
            ),
            warnings=warnings,
            timing_ms=(time.perf_counter() - started) * 1000.0,
        )
        return RenderOutcome(
            report=report,
            manifest=manifest,
            glb=glb,
            manifest_text=manifest_text,
            textures=textures,
        )
    except BeastforgeError:
        raise
    except OSError as exc:
        raise IOFailure(
            "io-failure",
            f"Generation failed while writing outputs: {exc}",
            location={"path": str(target_dir)},
            remedy="Check disk space and permissions, then retry.",
        ) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _verify_staged_glb(path: Path) -> None:
    """Re-read the staged GLB and verify its header and declared length."""
    import struct

    data = path.read_bytes()
    if len(data) < 20:
        raise IOFailure(
            "internal-error",
            "Staged GLB is too short to be valid.",
            location={"path": str(path)},
            remedy="Regenerate the package; this indicates an internal writer bug.",
        )
    magic, version, length = struct.unpack("<III", data[:12])
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise IOFailure(
            "internal-error",
            "Staged GLB failed its header/self-length check.",
            location={"path": str(path)},
            expected={"magic": "glTF", "version": 2, "length": len(data)},
            actual={"magic": magic, "version": version, "length": length},
            remedy="Regenerate the package; this indicates an internal writer bug.",
        )
