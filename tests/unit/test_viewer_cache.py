"""Asset cache keying, reuse, invalidation, locking, and cleanup."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from beastforge.config import Settings
from beastforge.model.errors import IOFailure
from beastforge.viewer.cache import TEMP_PREFIX, AssetCache, AssetGenerationError

SHA_A = "a" * 64
SHA_B = "b" * 64


class Producer:
    def __init__(self, *, fail: bool = False, delay: float = 0.0) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail
        self.delay = delay
        self.lock = threading.Lock()

    def __call__(self, name: str, sha: str, out_dir: Path) -> None:
        with self.lock:
            self.calls.append((name, sha))
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise IOFailure(
                "viewer-asset-failed",
                "synthetic failure",
                location={"path": str(out_dir)},
                remedy="retry",
            )
        (out_dir / f"{name}.glb").write_bytes(b"glb")
        (out_dir / f"{name}.manifest.json").write_text(
            json.dumps({"provenance": {"recipeSha256": sha}}), encoding="utf-8"
        )


def cache(tmp_path: Path, producer: Producer) -> AssetCache:
    return AssetCache(tmp_path / "cache", Settings(), producer=producer)


def test_hit_requires_both_files_and_matching_digest(tmp_path: Path) -> None:
    producer = Producer()
    active = cache(tmp_path, producer)
    active.ensure("ridge-stalker", SHA_A)
    assert producer.calls == [("ridge-stalker", SHA_A)]

    # Reuse: no producer call.
    active.ensure("ridge-stalker", SHA_A)
    assert len(producer.calls) == 1

    # Missing manifest: regenerate.
    active.manifest_path("ridge-stalker", SHA_A).unlink()
    active.ensure("ridge-stalker", SHA_A)
    assert len(producer.calls) == 2

    # Wrong digest: regenerate.
    active.manifest_path("ridge-stalker", SHA_A).write_text(
        json.dumps({"provenance": {"recipeSha256": SHA_B}}), encoding="utf-8"
    )
    active.ensure("ridge-stalker", SHA_A)
    assert len(producer.calls) == 3


def test_recipe_change_uses_a_new_key(tmp_path: Path) -> None:
    producer = Producer()
    active = cache(tmp_path, producer)
    active.ensure("ridge-stalker", SHA_A)
    active.ensure("ridge-stalker", SHA_B)
    assert producer.calls == [("ridge-stalker", SHA_A), ("ridge-stalker", SHA_B)]
    assert active.glb_path("ridge-stalker", SHA_A).is_file()
    assert active.glb_path("ridge-stalker", SHA_B).is_file()


def test_concurrent_ensure_generates_once(tmp_path: Path) -> None:
    producer = Producer(delay=0.1)
    active = cache(tmp_path, producer)
    results: list[Path] = []
    errors: list[Exception] = []

    def run() -> None:
        try:
            results.append(active.ensure("ridge-stalker", SHA_A))
        except Exception as exc:  # noqa: BLE001 - collected for the assertion
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert len(results) == 6
    assert len(producer.calls) == 1


def test_failed_generation_leaves_no_entry_and_retries(tmp_path: Path) -> None:
    producer = Producer(fail=True)
    active = cache(tmp_path, producer)
    with pytest.raises(AssetGenerationError):
        active.ensure("ridge-stalker", SHA_A)
    assert not active.directory("ridge-stalker", SHA_A).exists()
    assert active.state("ridge-stalker", SHA_A) == "failed"
    with pytest.raises(AssetGenerationError):
        active.ensure("ridge-stalker", SHA_A)
    assert len(producer.calls) == 2


def test_cleanup_removes_only_old_temp_directories(tmp_path: Path) -> None:
    active = cache(tmp_path, Producer())
    root = tmp_path / "cache"
    root.mkdir(parents=True)
    old = root / f"{TEMP_PREFIX}old"
    fresh = root / f"{TEMP_PREFIX}fresh"
    unrelated = root / "keep"
    for directory in (old, fresh, unrelated):
        directory.mkdir()
    past = time.time() - 7200
    os.utime(old, (past, past))

    removed = active.cleanup_stale_temp(older_than_seconds=3600)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists()
    assert unrelated.exists()
