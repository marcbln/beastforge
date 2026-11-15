"""Local viewer HTTP surface: routes, safety, stale hashes, and generation."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from beastforge.config import Settings
from beastforge.model.errors import IOFailure
from beastforge.viewer.cache import AssetCache
from beastforge.viewer.server import create_server


class FakeProducer:
    """Fast offline stand-in for the real render pipeline."""

    def __init__(self, failing: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing = failing or set()
        self.lock = threading.Lock()

    def __call__(self, name: str, sha: str, out_dir: Path) -> None:
        with self.lock:
            self.calls.append(name)
        if name in self.failing:
            raise IOFailure(
                "viewer-asset-failed",
                f"synthetic generation failure for {name}",
                location={"path": str(out_dir)},
                remedy="retry",
            )
        (out_dir / f"{name}.glb").write_bytes(f"glb:{name}:{sha}".encode())
        (out_dir / f"{name}.manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "creature": {"name": name},
                    "provenance": {"recipeSha256": sha},
                }
            ),
            encoding="utf-8",
        )


def _request(server, method: str, path: str) -> tuple[int, dict[str, str], bytes]:
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(host, port, timeout=10)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        headers = {key.lower(): value for key, value in response.getheaders()}
        return response.status, headers, body
    finally:
        connection.close()


@pytest.fixture
def viewer(settings: Settings, tmp_path: Path) -> Iterator[tuple[object, FakeProducer, AssetCache]]:
    producer = FakeProducer()
    cache = AssetCache(tmp_path / "cache", settings, producer=producer)
    server = create_server(settings, cache=cache, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, producer, cache
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _catalog(server) -> dict:
    status, _headers, body = _request(server, "GET", "/catalog.json")
    assert status == 200
    return json.loads(body)


def test_static_routes_and_security_headers(viewer) -> None:
    server, _producer, _cache = viewer
    for path, fragment in [("/", b"beastforge library"), ("/index.html", b"beastforge library")]:
        status, headers, body = _request(server, "GET", path)
        assert status == 200
        assert headers["content-type"].startswith("text/html")
        assert fragment in body
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
        assert "default-src 'self'" in headers["content-security-policy"]
        assert headers["cache-control"] == "no-cache"

    status, headers, body = _request(server, "GET", "/assets/app.js")
    assert status == 200
    assert headers["content-type"].startswith("text/javascript")
    assert b"Viewer bootstrap" in body

    status, _headers, body = _request(server, "GET", "/assets/three/three.module.js")
    assert status == 200
    assert b"three.js" in body or b"THREE" in body


def test_catalog_route(viewer) -> None:
    server, _producer, _cache = viewer
    status, headers, body = _request(server, "GET", "/catalog.json")
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert headers["cache-control"] == "no-store"
    payload = json.loads(body)
    assert payload["schemaVersion"] == "1.0"
    assert payload["creatures"]
    for entry in payload["creatures"]:
        assert entry["asset"].startswith("creatures/")
        assert not entry["asset"].startswith("/")


def test_health_head_methods_and_errors(viewer) -> None:
    server, _producer, _cache = viewer
    status, headers, body = _request(server, "GET", "/healthz")
    assert status == 200
    assert json.loads(body) == {"status": "ok"}
    assert headers["cache-control"] == "no-store"

    status, headers, body = _request(server, "HEAD", "/index.html")
    assert status == 200
    assert body == b""
    assert int(headers["content-length"]) > 0

    status, _headers, body = _request(server, "POST", "/healthz")
    assert status == 405
    assert json.loads(body)["error"]["code"] == "usage-error"

    status, _headers, body = _request(server, "GET", "/nope")
    assert status == 404
    assert json.loads(body)["status"] == "error"


def test_path_traversal_is_rejected(viewer) -> None:
    server, _producer, _cache = viewer
    for path in (
        "/assets/../library/quadruped/ridge-stalker.yaml",
        "/assets/%2e%2e/library/quadruped/ridge-stalker.yaml",
        "/assets/..%5clibrary",
        "/assets/%00",
        "/assets//app.js",
    ):
        status, _headers, body = _request(server, "GET", path)
        assert status == 404, path
        assert json.loads(body)["status"] == "error"


def test_creature_generation_then_cache_hit(viewer) -> None:
    server, producer, _cache = viewer
    entry = next(e for e in _catalog(server)["creatures"] if e["name"] == "ridge-stalker")
    path = f"/creatures/ridge-stalker/{entry['recipeSha256']}/ridge-stalker.glb"
    status, headers, body = _request(server, "GET", path)
    assert status == 200
    assert headers["content-type"] == "application/octet-stream"
    assert headers["cache-control"] == "public, max-age=31536000, immutable"
    assert body.startswith(b"glb:")
    assert producer.calls == ["ridge-stalker"]

    status, _headers, body = _request(server, "GET", path)
    assert status == 200
    assert producer.calls == ["ridge-stalker"]


def test_manifest_route(viewer) -> None:
    server, _producer, _cache = viewer
    entry = next(e for e in _catalog(server)["creatures"] if e["name"] == "giraffe")
    status, headers, body = _request(
        server, "GET", f"/creatures/giraffe/{entry['recipeSha256']}/giraffe.manifest.json"
    )
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert json.loads(body)["provenance"]["recipeSha256"] == entry["recipeSha256"]


def test_stale_hash_returns_409(viewer) -> None:
    server, _producer, _cache = viewer
    entry = next(e for e in _catalog(server)["creatures"] if e["name"] == "ridge-stalker")
    old = "0" * 64
    status, _headers, body = _request(
        server, "GET", f"/creatures/ridge-stalker/{old}/ridge-stalker.glb"
    )
    assert status == 409
    error = json.loads(body)["error"]
    assert error["code"] == "stale-asset"
    assert error["actual"] == old
    assert error["expected"] == entry["recipeSha256"]


def test_unknown_name_and_file(viewer) -> None:
    server, _producer, _cache = viewer
    status, _headers, body = _request(server, "GET", f"/creatures/nope/{'a' * 64}/nope.glb")
    assert status == 404
    assert json.loads(body)["error"]["code"] == "recipe-not-found"

    entry = next(e for e in _catalog(server)["creatures"] if e["name"] == "ridge-stalker")
    status, _headers, _body = _request(
        server, "GET", f"/creatures/ridge-stalker/{entry['recipeSha256']}/other.glb"
    )
    assert status == 404


def test_generation_failure_is_isolated(settings: Settings, tmp_path: Path) -> None:
    producer = FakeProducer(failing={"elephant"})
    cache = AssetCache(tmp_path / "cache", settings, producer=producer)
    server = create_server(settings, cache=cache, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        entry = next(e for e in _catalog(server)["creatures"] if e["name"] == "elephant")
        status, _headers, body = _request(
            server, "GET", f"/creatures/elephant/{entry['recipeSha256']}/elephant.glb"
        )
        assert status == 500
        assert json.loads(body)["error"]["code"] == "viewer-asset-failed"

        status, _headers, _body = _request(server, "GET", "/catalog.json")
        assert status == 200

        other = next(e for e in _catalog(server)["creatures"] if e["name"] == "ridge-stalker")
        status, _headers, _body = _request(
            server, "GET", f"/creatures/ridge-stalker/{other['recipeSha256']}/ridge-stalker.glb"
        )
        assert status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_port_released_after_shutdown(settings: Settings, tmp_path: Path) -> None:
    producer = FakeProducer()
    cache = AssetCache(tmp_path / "cache", settings, producer=producer)
    server = create_server(settings, cache=cache, port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

    reborn = create_server(settings, cache=cache, port=port)
    try:
        assert reborn.server_address[1] == port
    finally:
        reborn.server_close()
