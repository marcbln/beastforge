"""Shared pytest fixtures: repo paths, settings, and a once-per-session render."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from beastforge.config import Settings, resolve_settings
from beastforge.render import RenderOutcome, render

ROOT = Path(__file__).resolve().parents[1]
TEXFORGE_LIBRARY = ROOT.parent / "texforge" / "library"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def env() -> dict[str, str]:
    return {
        **os.environ,
        "BEASTFORGE_LIBRARY": str(ROOT / "library"),
        "BEASTFORGE_TEXFORGE_LIBRARY": str(TEXFORGE_LIBRARY),
        "NO_COLOR": "1",
        "PYTHONHASHSEED": "0",
    }


@pytest.fixture(scope="session")
def settings(env: dict[str, str]) -> Settings:
    return resolve_settings(env=env, cwd=ROOT)


@pytest.fixture(scope="session")
def rendered(tmp_path_factory: pytest.TempPathFactory, settings: Settings) -> RenderOutcome:
    out = tmp_path_factory.mktemp("rendered")
    return render("ridge-stalker", settings=settings, out_dir=str(out), force=True)


def run_cli(
    args: list[str], env: dict[str, str], cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    """Invoke the installed module in a subprocess so exit codes and streams are real."""
    return subprocess.run(
        [sys.executable, "-m", "beastforge", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
