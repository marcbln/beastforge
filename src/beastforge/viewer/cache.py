"""Disposable content-addressed cache for generated creature packages.

An asset is keyed by ``(name, recipeSha256)``. A hit requires both files and a
manifest whose ``provenance.recipeSha256`` equals the key. Generation runs
through the existing :func:`beastforge.render.render` pipeline one render at a
time, then the completed temporary directory is installed with one
``os.replace`` so readers never observe a partial package.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from beastforge.config import Settings, find_library_root
from beastforge.model.errors import IOFailure
from beastforge.render import render

CacheState = Literal["absent", "generating", "ready", "failed"]
Producer = Callable[[str, str, Path], None]
EventHook = Callable[[str, str], None]

TEMP_PREFIX = ".beastforge-view-tmp-"


class AssetGenerationError(IOFailure):
    """One creature's package could not be produced."""

    def __init__(self, name: str, sha: str, message: str, *, remedy: str) -> None:
        super().__init__(
            "viewer-asset-failed",
            message,
            location={"path": f"creatures/{name}/{sha}/{name}.glb"},
            remedy=remedy,
            exit_code=1,
        )


class AssetCache:
    """Materialize creature packages under ``<cache_root>/<name>/<sha>/``."""

    def __init__(
        self,
        root: Path,
        settings: Settings,
        *,
        producer: Producer | None = None,
        on_event: EventHook | None = None,
        cwd: Path | None = None,
    ) -> None:
        self.root = Path(root)
        self.settings = settings
        self.cwd = cwd
        self._producer = producer
        self.on_event = on_event
        self._key_locks: dict[tuple[str, str], threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._generation_lock = threading.Lock()
        self._states: dict[tuple[str, str], CacheState] = {}

    # -- paths -----------------------------------------------------------
    def directory(self, name: str, sha: str) -> Path:
        return self.root / name / sha

    def glb_path(self, name: str, sha: str) -> Path:
        return self.directory(name, sha) / f"{name}.glb"

    def manifest_path(self, name: str, sha: str) -> Path:
        return self.directory(name, sha) / f"{name}.manifest.json"

    def state(self, name: str, sha: str) -> CacheState:
        return self._states.get((name, sha), "absent")

    # -- inspection ------------------------------------------------------
    def is_ready(self, name: str, sha: str) -> bool:
        glb = self.glb_path(name, sha)
        manifest = self.manifest_path(name, sha)
        if not glb.is_file() or not manifest.is_file():
            return False
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        provenance = payload.get("provenance") if isinstance(payload, dict) else None
        return isinstance(provenance, dict) and provenance.get("recipeSha256") == sha

    # -- generation ------------------------------------------------------
    def _lock_for(self, name: str, sha: str) -> threading.Lock:
        key = (name, sha)
        with self._locks_guard:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key] = lock
            return lock

    def _emit(self, kind: str, name: str) -> None:
        if self.on_event is not None:
            self.on_event(kind, name)

    def _default_producer(self, name: str, sha: str, out_dir: Path) -> None:
        library_root = find_library_root(self.settings, cwd=self.cwd)
        render(
            name,
            settings=self.settings,
            out_dir=str(out_dir),
            force=True,
            cwd=library_root.parent,
        )

    def ensure(self, name: str, sha: str) -> Path:
        """Return the directory for ``(name, sha)``, generating it if needed."""
        key = (name, sha)
        if self.is_ready(name, sha):
            self._states[key] = "ready"
            return self.directory(name, sha)

        lock = self._lock_for(name, sha)
        with lock:
            if self.is_ready(name, sha):
                self._states[key] = "ready"
                return self.directory(name, sha)

            self._states[key] = "generating"
            self._emit("generating", name)
            with self._generation_lock:
                try:
                    final = self._generate(name, sha)
                except Exception as exc:
                    self._states[key] = "failed"
                    raise self._wrap_failure(name, sha, exc) from exc
            self._states[key] = "ready"
            self._emit("ready", name)
            return final

    def _generate(self, name: str, sha: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX, dir=self.root))
        try:
            producer = self._producer or self._default_producer
            producer(name, sha, staging)
            self._verify_manifest(name, sha, staging)
            target = self.directory(name, sha)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            os.replace(staging, target)
            return target
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def _verify_manifest(self, name: str, sha: str, directory: Path) -> None:
        manifest = directory / f"{name}.manifest.json"
        glb = directory / f"{name}.glb"
        if not glb.is_file() or not manifest.is_file():
            raise IOFailure(
                "viewer-asset-failed",
                f"Generated package for {name!r} is missing a file.",
                location={"path": str(directory)},
                remedy="Retry; if it persists, run `beastforge validate`.",
            )
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise IOFailure(
                "viewer-asset-failed",
                f"Cannot read the generated manifest for {name!r}: {exc}",
                location={"path": str(manifest)},
                remedy="Retry; if it persists, regenerate the creature.",
            ) from exc
        provenance = payload.get("provenance") if isinstance(payload, dict) else None
        actual = provenance.get("recipeSha256") if isinstance(provenance, dict) else None
        if actual != sha:
            raise IOFailure(
                "viewer-asset-failed",
                f"Generated manifest for {name!r} is for a different recipe.",
                location={"path": str(manifest)},
                expected=sha,
                actual=actual,
                remedy="Retry; the recipe may have changed while generating.",
            )

    def _wrap_failure(self, name: str, sha: str, exc: Exception) -> Exception:
        if isinstance(exc, AssetGenerationError):
            return exc
        detail = getattr(exc, "message", str(exc))
        return AssetGenerationError(
            name,
            sha,
            f"Could not generate {name!r}: {detail}",
            remedy="Check the recipe with `beastforge validate`, then retry the card.",
        )

    # -- housekeeping ----------------------------------------------------
    def cleanup_stale_temp(self, older_than_seconds: float = 3600) -> int:
        """Remove abandoned ``.beastforge-view-tmp-*`` directories."""
        if not self.root.is_dir():
            return 0
        cutoff = time.time() - older_than_seconds
        removed = 0
        for child in self.root.iterdir():
            if not child.is_dir() or not child.name.startswith(TEMP_PREFIX):
                continue
            try:
                if child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
        return removed


def cache_summary(cache: AssetCache) -> dict[str, Any]:
    """Small debug helper used by tests and diagnostics."""
    return {"root": str(cache.root), "states": dict(cache._states)}


__all__ = ["AssetCache", "AssetGenerationError", "EventHook", "Producer", "TEMP_PREFIX"]
