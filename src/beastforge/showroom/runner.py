"""Showroom orchestration: render frames, compare, and accept references."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from beastforge import __version__
from beastforge.config import Settings, find_library_root, find_texforge_library
from beastforge.library import (
    project_relative,
    resolve_recipe_path,
    scan_with_warnings,
)
from beastforge.model.loader import load_recipe
from beastforge.model.manifest import (
    ShowroomComparison,
    ShowroomCreatureResult,
    ShowroomFrame,
    ShowroomMetrics,
    ShowroomReport,
    ShowroomTolerance,
)
from beastforge.parts.registry import PresetRegistry
from beastforge.parts.resolve import resolve_parts
from beastforge.pipeline import prepare
from beastforge.showroom.compare import (
    DEFAULT_CHANGED_PIXEL_RATIO,
    DEFAULT_PER_PIXEL_THRESHOLD,
    compare_png,
)
from beastforge.showroom.raster import (
    FRAME_SIZE,
    VIEWS,
    RenderScene,
    encode_png,
    pose_extreme_bend,
    render_frame,
)
from beastforge.showroom.reference import (
    frame_filename,
    load_reference,
    reference_base,
    save_reference,
)
from beastforge.showroom.structural import build_structural
from beastforge.texture.texforge_adapter import TexforgeLibrary
from beastforge.validation.gate import ValidationFailed, error_findings, run_gate


@dataclass
class ShowroomOutcome:
    """The showroom report plus its process-level success flag."""

    report: ShowroomReport
    ok: bool


def _current_directory(name: str) -> Path:
    base = Path(tempfile.gettempdir()) / "beastforge-showroom" / name
    base.mkdir(parents=True, exist_ok=True)
    return base


def _render_creature(
    source: str,
    *,
    settings: Settings,
    texforge_root: Path | None,
    cwd: Path | None,
    current_dir: Path,
) -> tuple[str, dict[str, tuple[str, str, bytes]], Any, Any]:
    path = resolve_recipe_path(source, settings, cwd=cwd)
    label = project_relative(path, cwd=cwd)
    recipe, document = load_recipe(path, recipe_label=label)
    registry = PresetRegistry.from_library_root(
        find_library_root(settings, cwd=cwd), cwd=cwd
    )
    resolution = resolve_parts(recipe, registry, recipe_label=label)
    built = prepare(
        recipe,
        document=document,
        recipe_path=label,
        overrides={},
        tool_version=__version__,
        resolved_parts=resolution.parts,
    )
    findings = list(resolution.findings)
    findings.extend(
        run_gate(
            built.recipe,
            recipe_label=label,
            file_stem=path.stem,
            document=document,
            settings=settings,
            skeleton=built.skeleton,
            mesh=built.mesh,
            texforge_root=texforge_root,
            resolved_parts=resolution.parts,
        )
    )
    errors = error_findings(findings)
    if errors:
        raise ValidationFailed(errors)

    library = TexforgeLibrary(texforge_root)
    textures = []
    if texforge_root is not None:
        scratch = Path(tempfile.mkdtemp(prefix=".beastforge-showroom-tex-", dir=current_dir))
        try:
            textures = [
                library.render_material(material, staging_dir=scratch)
                for material in recipe.materials
            ]
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)

    scene = RenderScene.build(mesh=built.mesh, recipe=recipe, textures=textures)
    frames: dict[str, tuple[str, str, bytes]] = {}
    frame_dir = current_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for view in VIEWS:
        rgba = render_frame(scene, __import__("numpy").asarray(view.direction, dtype=float))
        payload = encode_png(rgba)
        name = frame_filename(view.name, "rest")
        (frame_dir / name).write_bytes(payload)
        frames[name] = (view.name, "rest", payload)
    extreme_positions = pose_extreme_bend(recipe, built.skeleton, built.mesh)
    front = VIEWS[0]
    rgba = render_frame(
        scene,
        __import__("numpy").asarray(front.direction, dtype=float),
        positions=extreme_positions,
    )
    payload = encode_png(rgba)
    name = frame_filename(front.name, "extreme-bend")
    (frame_dir / name).write_bytes(payload)
    frames[name] = (front.name, "extreme-bend", payload)
    structural = build_structural(recipe, built.skeleton, built.mesh, built.clips)
    return recipe.meta.name, frames, structural, recipe


def run_showroom(
    sources: list[str] | None,
    *,
    settings: Settings,
    accept: bool = False,
    cwd: Path | None = None,
    tool_version: str = __version__,
) -> ShowroomOutcome:
    """Render and compare (or accept) every requested creature."""
    library_root = find_library_root(settings, cwd=cwd)
    texforge_root = find_texforge_library(settings, library_root=library_root)
    if sources:
        names = list(sources)
    else:
        entries, _warnings = scan_with_warnings(settings, cwd=cwd)
        names = [entry.name for entry in entries]
    base = reference_base(settings, cwd=cwd)
    tolerance = ShowroomTolerance(
        per_pixel_threshold=DEFAULT_PER_PIXEL_THRESHOLD,
        changed_pixel_ratio=DEFAULT_CHANGED_PIXEL_RATIO,
    )
    results: list[ShowroomCreatureResult] = []
    all_ok = True
    for source in names:
        current_dir = _current_directory(Path(source).stem)
        name, frames, structural, _recipe = _render_creature(
            source,
            settings=settings,
            texforge_root=texforge_root,
            cwd=cwd,
            current_dir=current_dir,
        )
        reference = load_reference(base / name)
        frame_reports: list[ShowroomFrame] = []
        differing: list[str] = []
        metrics_max_delta = 0
        metrics_max_ratio = 0.0
        if accept:
            save_reference(
                base / name,
                frames={key: value[2] for key, value in frames.items()},
                structural=structural,
                metadata={
                    "tool_version": tool_version,
                    "frame_size": FRAME_SIZE,
                    "tolerance": tolerance.model_dump(mode="json"),
                    "cameras": [view.name for view in VIEWS],
                },
            )
            for key, (view, pose, payload) in frames.items():
                frame_reports.append(
                    ShowroomFrame(
                        view=view,
                        pose=pose,
                        path=str(base / name / "frames" / key),
                        sha256=hashlib.sha256(payload).hexdigest(),
                    )
                )
            comparison = ShowroomComparison(status="pass", differing_frames=[])
        else:
            current_structural = structural.model_dump(mode="json")
            for key, (view, pose, payload) in frames.items():
                frame_reports.append(
                    ShowroomFrame(
                        view=view,
                        pose=pose,
                        path=str(current_dir / "frames" / key),
                        sha256=hashlib.sha256(payload).hexdigest(),
                    )
                )
                baseline = reference.frames.get(key) if reference is not None else None
                if baseline is None:
                    differing.append(key)
                    continue
                frame_compare = compare_png(
                    baseline,
                    payload,
                    per_pixel_threshold=tolerance.per_pixel_threshold,
                    changed_pixel_ratio=tolerance.changed_pixel_ratio,
                )
                metrics_max_delta = max(metrics_max_delta, frame_compare.max_pixel_delta)
                metrics_max_ratio = max(metrics_max_ratio, frame_compare.changed_pixel_ratio)
                if not frame_compare.passed:
                    differing.append(key)
            if reference is None:
                comparison = ShowroomComparison(status="no-baseline", differing_frames=differing)
            else:
                if reference.structural != current_structural:
                    differing.append("structural")
                comparison = ShowroomComparison(
                    status="fail" if differing else "pass",
                    differing_frames=differing,
                    metrics=ShowroomMetrics(
                        max_pixel_delta=int(metrics_max_delta),
                        changed_pixel_ratio=float(metrics_max_ratio),
                    ),
                )
        if comparison.status != "pass":
            all_ok = False
        results.append(
            ShowroomCreatureResult(
                name=name,
                frames=frame_reports,
                structural=structural,
                comparison=comparison,
            )
        )
    report = ShowroomReport(
        tool_version=tool_version,
        status="ok" if all_ok else "failed",
        mode="accept" if accept else "compare",
        tolerance=tolerance,
        creatures=results,
    )
    return ShowroomOutcome(report=report, ok=all_ok)
