"""Static export: a pure plan plus a staged filesystem writer.

The export is the publish path. It renders every recipe with
``cwd=<library_root>.parent`` so manifest provenance labels stay ``library/...``,
places packages in the same content-addressed layout the local server uses, and
records ``bundle.json`` for determinism checks. No timestamps or hostnames are
emitted, so identical recipes and tool versions produce identical bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from beastforge import __version__
from beastforge.config import Settings, find_library_root
from beastforge.model.errors import IOFailure
from beastforge.render import render
from beastforge.utils.canonical import canonical_json
from beastforge.viewer.assets import iter_static_files
from beastforge.viewer.catalog import CatalogDocument, build_catalog, catalog_json

OWNED_PATHS: tuple[str, ...] = (
    "index.html",
    "assets",
    "catalog.json",
    "bundle.json",
    "creatures",
)


@dataclass(frozen=True)
class PlannedCreature:
    """One creature package the export will render and place."""

    name: str
    recipe_sha256: str
    asset: str
    manifest: str


@dataclass
class ExportPlan:
    """Everything the export will emit, resolved before writing anything."""

    settings: Settings
    catalog: CatalogDocument
    catalog_text: str
    static_files: dict[str, bytes]
    creatures: list[PlannedCreature]
    warnings: list[str] = field(default_factory=list)
    owned_paths: tuple[str, ...] = OWNED_PATHS

    @property
    def planned_file_count(self) -> int:
        """Files emitted excluding ``bundle.json`` itself."""
        return len(self.static_files) + 1 + 2 * len(self.creatures)


@dataclass
class ExportOutcome:
    """The result of a dry run or a completed export."""

    output: str
    creatures: list[str]
    files: int
    warnings: list[str]
    dry_run: bool


def plan_export(settings: Settings, *, cwd: Path | None = None) -> ExportPlan:
    """Derive the catalog and enumerate the static bundle without writing."""
    catalog = build_catalog(settings, cwd=cwd)
    static_files: dict[str, bytes] = {}
    for path, resource in iter_static_files():
        # The bundle entry point lives at the root; its references stay relative.
        static_files["index.html" if path == "assets/index.html" else path] = resource.read_bytes()
    if "index.html" not in static_files:
        raise IOFailure(
            "io-failure",
            "The packaged frontend is missing index.html.",
            location={"path": "index.html"},
            remedy="Reinstall beastforge; the viewer package data is incomplete.",
        )
    creatures = [
        PlannedCreature(
            name=entry.name,
            recipe_sha256=entry.recipe_sha256,
            asset=entry.asset,
            manifest=entry.manifest,
        )
        for entry in catalog.creatures
    ]
    warnings = [f"{warning.path}: {warning.message}" for warning in catalog.warnings]
    return ExportPlan(
        settings=settings,
        catalog=catalog,
        catalog_text=catalog_json(catalog),
        static_files=static_files,
        creatures=creatures,
        warnings=warnings,
    )


def write_export(
    plan: ExportPlan,
    output: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> ExportOutcome:
    """Build the bundle into a sibling staging directory, then install it."""
    target = Path(output)
    if dry_run:
        return ExportOutcome(
            output=output,
            creatures=[creature.name for creature in plan.creatures],
            files=plan.planned_file_count,
            warnings=list(plan.warnings),
            dry_run=True,
        )

    if target.exists() and (target.is_file() or any(target.iterdir())) and not force:
        raise IOFailure(
            "export-exists",
            f"Export target {target} is not empty.",
            location={"path": str(target)},
            expected="an empty or missing directory",
            actual="non-empty target",
            remedy="Pass --force or choose an empty directory.",
            exit_code=1,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".beastforge-export-", dir=target.parent))
    rendered_root = Path(tempfile.mkdtemp(prefix=".beastforge-export-render-"))
    try:
        _stage_static(plan, staging)
        _stage_creatures(plan, staging, rendered_root)
        files = _compute_bundle_files(staging)
        bundle = {
            "schemaVersion": "1",
            "toolVersion": __version__,
            "files": files,
        }
        (staging / "bundle.json").write_text(canonical_json(bundle), encoding="utf-8")
        _install(staging, target, plan.owned_paths)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(rendered_root, ignore_errors=True)

    return ExportOutcome(
        output=output,
        creatures=[creature.name for creature in plan.creatures],
        files=len(files),
        warnings=list(plan.warnings),
        dry_run=False,
    )


def _stage_static(plan: ExportPlan, staging: Path) -> None:
    for path, data in plan.static_files.items():
        destination = staging / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (staging / "catalog.json").write_text(plan.catalog_text, encoding="utf-8")


def _stage_creatures(plan: ExportPlan, staging: Path, rendered_root: Path) -> None:
    library_root = find_library_root(plan.settings)
    generator_cwd = library_root.parent
    for creature in plan.creatures:
        out_dir = rendered_root / creature.name
        render(
            creature.name,
            settings=plan.settings,
            out_dir=str(out_dir),
            force=True,
            cwd=generator_cwd,
        )
        glb = out_dir / f"{creature.name}.glb"
        manifest = out_dir / f"{creature.name}.manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        actual = (payload.get("provenance") or {}).get("recipeSha256")
        if actual != creature.recipe_sha256:
            raise IOFailure(
                "viewer-asset-failed",
                f"Recipe for {creature.name!r} changed during export; "
                "the bundle would reference a stale asset.",
                location={"path": creature.manifest},
                expected=creature.recipe_sha256,
                actual=actual,
                remedy="Re-run the export against a stable library.",
                exit_code=3,
            )
        destination = staging / "creatures" / creature.name / creature.recipe_sha256
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(glb, destination / glb.name)
        shutil.copyfile(manifest, destination / manifest.name)


def _compute_bundle_files(staging: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(staging.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(staging).as_posix()
        if relative == "bundle.json":
            continue
        data = path.read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    files.sort(key=lambda item: item["path"])
    return files


def _install(staging: Path, target: Path, owned_paths: tuple[str, ...]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for owned in owned_paths:
        source = staging / owned
        if not source.exists():
            continue
        destination = target / owned
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        os.replace(source, destination)


__all__ = [
    "OWNED_PATHS",
    "ExportOutcome",
    "ExportPlan",
    "PlannedCreature",
    "plan_export",
    "write_export",
]
