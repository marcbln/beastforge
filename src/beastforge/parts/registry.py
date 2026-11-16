"""Filesystem adapter for the immutable part-preset library.

Each preset version is one file at ``<library>/parts/<name>/<version>.yaml``. The
scan is sorted, agreement between directory/filename/name/version is enforced,
and duplicate ``(name, version)`` pairs are rejected. Malformed files are
recorded as warnings so a single bad preset cannot hide the rest of the library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from beastforge.model.errors import BeastforgeError
from beastforge.model.loader import RecipeParseError, load_yaml_document
from beastforge.model.parts import PartPreset
from beastforge.utils.canonical import canonical_json, sha256_text

VERSION_RE = r"^\d+\.\d+\.\d+$"


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a strict ``MAJOR.MINOR.PATCH`` string."""
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid semantic version {version!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def version_key(version: str) -> tuple[int, int, int]:
    """Sort key that compares versions numerically, never lexically."""
    return parse_version(version)


@dataclass(frozen=True)
class PresetWarning:
    """A non-fatal scan problem (unreadable, mismatched, or duplicate file)."""

    path: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


class PresetRegistry:
    """An in-memory view of every preset version in a library."""

    def __init__(self, root: Path | None, *, cwd: Path | None = None) -> None:
        self.root = root
        self.cwd = cwd
        self.presets: dict[tuple[str, str], PartPreset] = {}
        self.files: dict[tuple[str, str], Path] = {}
        self.warnings: list[PresetWarning] = []
        self.errors: dict[tuple[str, str], str] = {}
        self._scan()

    @classmethod
    def from_library_root(cls, library_root: Path | None, *, cwd: Path | None = None):
        """Build a registry rooted at ``<library>/parts``."""
        if library_root is None:
            return cls(None, cwd=cwd)
        return cls(library_root / "parts", cwd=cwd)

    def _label(self, path: Path) -> str:
        base = (self.cwd or Path.cwd()).resolve()
        try:
            return str(path.resolve().relative_to(base))
        except ValueError:
            return str(path.resolve())

    def _scan(self) -> None:
        if self.root is None or not self.root.is_dir():
            return
        paths = sorted(set(self.root.glob("*/*.yaml")) | set(self.root.glob("*/*.yml")))
        for path in paths:
            if not path.is_file():
                continue
            label = self._label(path)
            try:
                document = load_yaml_document(path, recipe_label=label)
                preset = PartPreset.model_validate(document)
            except (RecipeParseError, ValidationError, BeastforgeError) as exc:
                message = getattr(exc, "message", str(exc))
                self.warnings.append(
                    PresetWarning(path=label, message=f"preset-file-invalid: {message}")
                )
                continue
            directory = path.parent.name
            stem = path.stem
            if preset.name != directory:
                self.warnings.append(
                    PresetWarning(
                        path=label,
                        message=(
                            f"preset-file-invalid: name {preset.name!r} does not match "
                            f"directory {directory!r}"
                        ),
                    )
                )
                continue
            if preset.version != stem:
                self.warnings.append(
                    PresetWarning(
                        path=label,
                        message=(
                            f"preset-file-invalid: version {preset.version!r} does not match "
                            f"filename {stem!r}"
                        ),
                    )
                )
                continue
            key = (preset.name, preset.version)
            if key in self.presets:
                message = (
                    f"preset-file-invalid: duplicate preset version "
                    f"{preset.name!r} {preset.version!r}"
                )
                self.warnings.append(PresetWarning(path=label, message=message))
                self.errors[key] = message
                continue
            preset.path = label
            canonical = preset_document(preset)
            preset.sha256 = sha256_text(canonical_json(canonical, trailing_newline=False))
            self.presets[key] = preset
            self.files[key] = path
        self.warnings.sort(key=lambda item: (item.path, item.message))

    def get(self, name: str, version: str) -> PartPreset | None:
        """Return one exact preset version, or ``None``."""
        return self.presets.get((name, version))

    def versions(self, name: str) -> list[str]:
        """Return a preset's versions in ascending numeric order."""
        values = [version for (preset_name, version) in self.presets if preset_name == name]
        return sorted(set(values), key=version_key)

    def names(self) -> list[str]:
        """Return preset names in sorted order."""
        return sorted({name for (name, _version) in self.presets})

    def all_presets(self) -> list[PartPreset]:
        """Return every preset version sorted by ``(name, semver)``."""
        return sorted(
            self.presets.values(),
            key=lambda preset: (preset.name, version_key(preset.version)),
        )

    def documents_for(self, parts) -> list[dict[str, object]]:
        """Return the unique pinned preset documents in canonical order."""
        keys = sorted(
            {(part.preset, part.preset_version) for part in parts},
            key=lambda key: (key[0], version_key(key[1])),
        )
        documents: list[dict[str, object]] = []
        for key in keys:
            preset = self.presets.get(key)
            if preset is not None:
                documents.append(dict(preset_document(preset)))
        return documents


def preset_document(preset: PartPreset) -> dict[str, object]:
    """Return the canonical authoring document for a preset.

    ``path`` and ``sha256`` are derived fields and never part of the hash.
    """
    return preset.model_dump(mode="json", exclude={"path", "sha256"})


__all__ = [
    "PresetRegistry",
    "PresetWarning",
    "parse_version",
    "preset_document",
    "version_key",
]
