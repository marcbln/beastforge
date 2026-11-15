"""Showroom reference storage and explicit acceptance (FR-040)."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from beastforge.config import Settings, find_library_root
from beastforge.model.manifest import ShowroomStructural
from beastforge.utils.canonical import canonical_json


def frame_filename(view: str, pose: str) -> str:
    """Return the committed frame filename for one view/pose pair."""
    return f"{view}__{pose}.png"


def reference_base(settings: Settings, *, cwd: Path | None = None) -> Path:
    """Locate ``showroom/reference`` next to the library, or under the cwd."""
    try:
        root = find_library_root(settings, cwd=cwd)
        return root.parent / "showroom" / "reference"
    except Exception:  # noqa: BLE001 - showroom can run on an explicit recipe
        return (cwd or Path.cwd()) / "showroom" / "reference"


@dataclass
class ReferenceSet:
    """Approved frames plus their structural summary."""

    frames: dict[str, bytes]
    structural: dict[str, object] | None
    metadata: dict[str, object] | None


def load_reference(directory: Path) -> ReferenceSet | None:
    """Load an approved reference set, or ``None`` when no baseline exists."""
    frames_dir = directory / "frames"
    if not frames_dir.is_dir():
        return None
    frames: dict[str, bytes] = {}
    for path in sorted(frames_dir.glob("*.png")):
        frames[path.name] = path.read_bytes()
    if not frames:
        return None
    structural = None
    structural_path = directory / "structural.json"
    if structural_path.is_file():
        structural = json.loads(structural_path.read_text(encoding="utf-8"))
    metadata = None
    metadata_path = directory / "manifest.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return ReferenceSet(frames=frames, structural=structural, metadata=metadata)


def save_reference(
    directory: Path,
    *,
    frames: dict[str, bytes],
    structural: ShowroomStructural,
    metadata: dict[str, object],
) -> None:
    """Atomically replace one creature's reference set."""
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{directory.name}-", dir=directory.parent))
    try:
        frames_dir = staging / "frames"
        frames_dir.mkdir()
        for name, payload in sorted(frames.items()):
            (frames_dir / name).write_bytes(payload)
        (staging / "structural.json").write_text(
            canonical_json(structural.model_dump(mode="json")), encoding="utf-8"
        )
        (staging / "manifest.json").write_text(canonical_json(metadata), encoding="utf-8")
        if directory.exists():
            shutil.rmtree(directory)
        shutil.move(str(staging), str(directory))
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
