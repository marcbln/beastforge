"""Loopback-only HTTP server for the local viewer.

The server is deliberately small and dependency-free: it serves the buildless
frontend, regenerates ``catalog.json`` from the current library on every request,
and materializes creature packages on demand through :class:`AssetCache`. Every
response carries a restrictive CSP and the same error document shape as the CLI.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from beastforge import __version__
from beastforge.config import Settings, resolve_cache_dir
from beastforge.model.errors import BeastforgeError
from beastforge.viewer.assets import read_static
from beastforge.viewer.cache import AssetCache, Producer
from beastforge.viewer.catalog import CatalogDocument, build_catalog, catalog_json

HOST = "127.0.0.1"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": CSP,
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".glb": "application/octet-stream",
}


class ViewerHTTPServer(ThreadingHTTPServer):
    """Threaded server carrying the settings, cache, and catalog builder."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        settings: Settings,
        cache: AssetCache,
        cwd: Path | None = None,
        verbose: bool = False,
        catalog_builder: Callable[[], CatalogDocument] | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.cwd = cwd
        self.verbose = verbose
        self.catalog_builder = catalog_builder or (lambda: build_catalog(settings, cwd=cwd))
        super().__init__(address, ViewerRequestHandler)

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        if isinstance(host, bytes):
            host = host.decode("ascii")
        return f"http://{host}:{port}/"


class ViewerRequestHandler(BaseHTTPRequestHandler):
    """Route the small viewer surface and reject everything else."""

    server_version = "beastforge-viewer"
    protocol_version = "HTTP/1.1"

    @property
    def viewer(self) -> ViewerHTTPServer:
        return cast(ViewerHTTPServer, self.server)

    # -- methods ---------------------------------------------------------
    def do_GET(self) -> None:
        self._dispatch(head=False)

    def do_HEAD(self) -> None:
        self._dispatch(head=True)

    def do_POST(self) -> None:
        self._method_not_allowed()

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    # -- routing ---------------------------------------------------------
    def _dispatch(self, *, head: bool) -> None:
        path = urlsplit(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._serve_static("assets/index.html", head=head)
            elif path == "/catalog.json":
                self._serve_catalog(head=head)
            elif path == "/healthz":
                self._send(
                    200,
                    b'{"status":"ok"}',
                    "application/json; charset=utf-8",
                    "no-store",
                    head=head,
                )
            elif path.startswith("/assets/"):
                self._serve_asset(path[len("/assets/") :], head=head)
            elif path.startswith("/creatures/"):
                self._serve_creature(path[len("/creatures/") :], head=head)
            else:
                self._error(
                    404,
                    "recipe-not-found",
                    f"No viewer route matches {path!r}.",
                    remedy="Open / or reload the catalog.",
                    head=head,
                )
        except BeastforgeError as exc:
            self._error(
                500,
                exc.code,
                exc.message,
                location=exc.location,
                expected=exc.expected,
                actual=exc.actual,
                remedy=exc.remedy,
                head=head,
            )
        except (BrokenPipeError, ConnectionResetError):
            return
        except OSError as exc:
            self._error(
                500,
                "io-failure",
                f"Filesystem failure while serving {path!r}: {exc}",
                remedy="Check permissions and retry.",
                head=head,
            )

    # -- routes ----------------------------------------------------------
    def _serve_catalog(self, *, head: bool) -> None:
        try:
            document = self.viewer.catalog_builder()
        except BeastforgeError:
            raise
        except Exception as exc:  # noqa: BLE001 - served as a scoped 500
            self._error(
                500,
                "io-failure",
                f"Cannot build the catalog: {exc}",
                remedy="Fix the library or run `beastforge validate`.",
                head=head,
            )
            return
        body = catalog_json(document).encode("utf-8")
        self._send(200, body, "application/json; charset=utf-8", "no-store", head=head)

    def _serve_asset(self, encoded: str, *, head: bool) -> None:
        segments = self._safe_segments(encoded)
        if segments is None:
            self._not_found(head=head)
            return
        try:
            body = read_static("assets/" + "/".join(segments))
        except (FileNotFoundError, IsADirectoryError, OSError):
            self._not_found(head=head)
            return
        content_type = CONTENT_TYPES.get(Path(segments[-1]).suffix, "application/octet-stream")
        self._send(200, body, content_type, "no-cache", head=head)

    def _serve_creature(self, encoded: str, *, head: bool) -> None:
        segments = self._safe_segments(encoded)
        if segments is None or len(segments) != 3:
            self._not_found(head=head)
            return
        name, sha, filename = segments
        document = self.viewer.catalog_builder()
        entry = document.entry(name)
        if entry is None:
            self._error(
                404,
                "recipe-not-found",
                f"No creature named {name!r} is in the current library.",
                remedy="Reload the catalog and choose an available creature.",
                head=head,
            )
            return
        if sha != entry.recipe_sha256:
            self._error(
                409,
                "stale-asset",
                f"Asset {sha[:7]}… was generated from an older recipe.",
                location={"path": f"creatures/{name}/{sha}/{filename}"},
                expected=entry.recipe_sha256,
                actual=sha,
                remedy="Reload the catalog and retry the current asset URL.",
                head=head,
            )
            return
        if filename == f"{name}.glb":
            content_type = "application/octet-stream"
        elif filename == f"{name}.manifest.json":
            content_type = "application/json; charset=utf-8"
        else:
            self._not_found(head=head)
            return
        try:
            self.viewer.cache.ensure(name, sha)
        except BeastforgeError as exc:
            self._error(
                500,
                "viewer-asset-failed",
                exc.message,
                location={"path": f"creatures/{name}/{sha}/{filename}"},
                remedy=exc.remedy,
                head=head,
            )
            return
        path = (
            self.viewer.cache.glb_path(name, sha)
            if filename == f"{name}.glb"
            else self.viewer.cache.manifest_path(name, sha)
        )
        try:
            body = path.read_bytes()
        except OSError as exc:
            self._error(
                500,
                "io-failure",
                f"Cannot read cached asset {path}: {exc}",
                location={"path": f"creatures/{name}/{sha}/{filename}"},
                remedy="Delete the cache entry and retry.",
                head=head,
            )
            return
        self._send(200, body, content_type, "public, max-age=31536000, immutable", head=head)

    # -- helpers ---------------------------------------------------------
    def _safe_segments(self, encoded: str) -> list[str] | None:
        """Decode once and reject traversal, NULs, backslashes, empty segments."""
        decoded = unquote(encoded)
        if "\x00" in decoded or "\\" in decoded:
            return None
        if decoded.startswith("/"):
            return None
        segments = decoded.split("/")
        if any(segment in {"", ".", ".."} for segment in segments):
            return None
        return segments

    def _serve_static(self, asset_path: str, *, head: bool) -> None:
        try:
            body = read_static(asset_path)
        except (FileNotFoundError, OSError):
            self._not_found(head=head)
            return
        self._send(200, body, "text/html; charset=utf-8", "no-cache", head=head)

    def _not_found(self, *, head: bool) -> None:
        self._error(
            404,
            "recipe-not-found",
            "No such viewer file.",
            remedy="Reload the catalog and retry.",
            head=head,
        )

    def _method_not_allowed(self) -> None:
        self._error(
            405,
            "usage-error",
            f"Method {self.command} is not allowed.",
            remedy="Use GET or HEAD.",
            head=False,
        )

    def _error(
        self,
        status: int,
        code: str,
        message: str,
        *,
        location: dict[str, str] | None = None,
        expected: Any = None,
        actual: Any = None,
        remedy: str,
        head: bool,
    ) -> None:
        payload = {
            "schema_version": "1",
            "tool_version": __version__,
            "status": "error",
            "error": {
                "code": code,
                "message": message,
                "location": location or {"path": ""},
                "expected": expected,
                "actual": actual,
                "remedy": remedy,
            },
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self._send(
            status,
            body.encode("utf-8"),
            "application/json; charset=utf-8",
            "no-store",
            head=head,
        )

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        cache_control: str,
        *,
        head: bool,
    ) -> None:
        self.send_response(status)
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        if not self.viewer.verbose:
            return
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")
        sys.stderr.flush()


def create_server(
    settings: Settings,
    *,
    cache: AssetCache | None = None,
    port: int = 0,
    host: str = HOST,
    cwd: Path | None = None,
    verbose: bool = False,
    producer: Producer | None = None,
    catalog_builder: Callable[[], CatalogDocument] | None = None,
) -> ViewerHTTPServer:
    """Create (but do not start) a loopback server with the given cache."""
    if host != HOST:
        raise ValueError("the viewer only binds to 127.0.0.1")
    active_cache = cache or AssetCache(
        resolve_cache_dir(settings), settings, producer=producer, cwd=cwd
    )
    return ViewerHTTPServer(
        (host, port),
        settings=settings,
        cache=active_cache,
        cwd=cwd,
        verbose=verbose,
        catalog_builder=catalog_builder,
    )


__all__ = ["CSP", "HOST", "ViewerHTTPServer", "create_server"]
