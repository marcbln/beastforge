"""Configuration resolution (``cli:configuration``, research D9).

Order: explicit flag -> environment -> project config -> user config (XDG) ->
built-in default. Only beastforge's own config file is read.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from beastforge.model.errors import IOFailure

ENV_LIBRARY = "BEASTFORGE_LIBRARY"
ENV_TEXFORGE_LIBRARY = "BEASTFORGE_TEXFORGE_LIBRARY"
ENV_OUT = "BEASTFORGE_OUT"
PROJECT_CONFIG = ".beastforge.toml"


@dataclass
class Settings:
    """Effective beastforge settings."""

    library: str | None = None
    texforge_library: str | None = None
    output_dir: str = "dist"
    color: str = "auto"
    config_path: str | None = None


def _user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "beastforge" / "config.toml"


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise IOFailure(
            "config-error",
            f"Cannot read config {path}: {exc}",
            location={"path": str(path)},
            remedy="Fix the TOML file or pass --config with a valid file.",
            exit_code=1,
        ) from exc
    if not isinstance(data, dict):
        raise IOFailure(
            "config-error",
            f"Config {path} must be a TOML table.",
            location={"path": str(path)},
            remedy="Use keys such as library, texforge_library, output_dir, and color.",
            exit_code=1,
        )
    if isinstance(data.get("beastforge"), dict):
        data = data["beastforge"]
    return data


def _apply(settings: Settings, data: dict[str, Any], source: str) -> None:
    known = {"library", "texforge_library", "output_dir", "color", "config_path"}
    for key, value in data.items():
        if key not in known:
            raise IOFailure(
                "config-error",
                f"Unknown setting {key!r} in {source}.",
                location={"path": source},
                remedy=f"Use one of: {', '.join(sorted(known - {'config_path'}))}.",
                exit_code=1,
            )
        setattr(settings, key, value)


def resolve_settings(
    config_path: str | None = None,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> Settings:
    """Build the effective settings for one invocation."""
    env_map = os.environ if env is None else env
    settings = Settings()

    _apply(settings, _read_toml(_user_config_path()), str(_user_config_path()))

    start = cwd or Path.cwd()
    project_file: Path | None = None
    for directory in [start, *start.parents]:
        candidate = directory / PROJECT_CONFIG
        if candidate.is_file():
            project_file = candidate
            break
    if project_file is not None:
        _apply(settings, _read_toml(project_file), str(project_file))

    if (value := env_map.get(ENV_LIBRARY)) is not None:
        settings.library = value
    if (value := env_map.get(ENV_TEXFORGE_LIBRARY)) is not None:
        settings.texforge_library = value
    if (value := env_map.get(ENV_OUT)) is not None:
        settings.output_dir = value
    if env_map.get("NO_COLOR") is not None:
        settings.color = "never"

    if config_path is not None:
        _apply(settings, _read_toml(Path(config_path)), config_path)
        settings.config_path = config_path

    if settings.color not in {"auto", "always", "never"}:
        raise IOFailure(
            "config-error",
            f"color must be auto|always|never, got {settings.color!r}.",
            location={"path": settings.config_path or PROJECT_CONFIG},
            remedy="Set color = 'auto', 'always', or 'never'.",
            exit_code=1,
        )
    return settings


def find_library_root(settings: Settings, *, cwd: Path | None = None) -> Path:
    """Locate ``library/``: explicit setting wins, else walk up from ``cwd``."""
    if settings.library:
        root = Path(settings.library)
        if not root.is_dir():
            raise IOFailure(
                "library-not-found",
                f"Library root {root} does not exist or is not a directory.",
                location={"path": str(root)},
                remedy=(
                    "Pass --library or set BEASTFORGE_LIBRARY to the "
                    "repository's library/ directory."
                ),
                exit_code=4,
            )
        return root
    start = cwd or Path.cwd()
    for directory in [start, *start.parents]:
        candidate = directory / "library"
        if candidate.is_dir():
            return candidate
    raise IOFailure(
        "library-not-found",
        f"No library/ directory found from {start} upward.",
        location={"path": str(start)},
        remedy="Run from the repository root, or pass --library /path/to/library.",
        exit_code=4,
    )


def find_texforge_library(settings: Settings, *, library_root: Path | None = None) -> Path | None:
    """Resolve the texforge recipe library rooted next to the beastforge repo."""
    if settings.texforge_library:
        candidate = Path(settings.texforge_library)
        return candidate if candidate.is_dir() else None
    candidates: list[Path] = []
    if library_root is not None:
        repo_root = library_root.parent
        candidates.append(repo_root.parent / "texforge" / "library")
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "texforge" / "library")
    candidates.append(Path.cwd().parent / "texforge" / "library")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None
