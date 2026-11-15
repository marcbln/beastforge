# Contract: local viewer HTTP surface

**Status**: normative for feature 002
**Scope**: `beastforge view` serve mode only. The static export has no server; it
uses the exact same relative URLs from `catalog.json`.

## Binding and lifecycle

- Bind address: **`127.0.0.1` only**. There is no `--host` flag and no LAN or
  public binding.
- Port: ephemeral (`0`) by default; `--port <n>` pins a port. A bind failure is
  an `io-failure` (exit 1) with an actionable message.
- Startup prints the URL and how to stop (Ctrl-C) to stdout. Progress and
  warnings go to stderr.
- `--no-browser` suppresses `webbrowser.open`; the server still starts.
- `SIGINT`/`SIGTERM` shut down the server, close the socket, and release the
  port. A clean stop exits `0`; Ctrl-C exits `130` per CLI convention.
- The server regenerates `/catalog.json` from the current library on every
  request, so a recipe added while the server runs appears on the next reload.
- The default access log is suppressed (it would be noise and is not part of the
  result). `--verbose` may enable one line per request on stderr; timestamps are
  not printed.

## Routes

| Method | Path | Success | Notes |
|--------|------|---------|-------|
| GET | `/` | `200` `text/html; charset=utf-8` | `index.html` |
| GET | `/index.html` | `200` `text/html; charset=utf-8` | same |
| GET | `/assets/<path>` | `200` | Static frontend files from `viewer/static/`; includes `assets/three/**` |
| GET | `/catalog.json` | `200` `application/json; charset=utf-8` | Current [catalog](./catalog.md); `Cache-Control: no-store` |
| GET | `/creatures/<name>/<sha>/<file>` | `200` | `<file>` is `<name>.glb` (`application/octet-stream`) or `<name>.manifest.json` (`application/json`); generates on demand; immutable caching |
| GET | `/healthz` | `200` `application/json` | `{"status":"ok"}` |
| GET | anything else | `404` | error document |

`HEAD` may mirror `GET` headers with no body. Other methods return `405`.

## Creature route contract

1. `<name>` must match a current catalog entry. Otherwise `404` with
   `recipe-not-found`.
2. `<sha>` must equal that entry's current `recipeSha256`. Otherwise `409` with
   `stale-asset`; `error.actual` is the requested sha and `error.expected` is the
   current sha. The client should reload `catalog.json`.
3. `<file>` must be exactly `<name>.glb` or `<name>.manifest.json`. Otherwise
   `404`.
4. Cache hit → serve the file. Cache miss → generate the package through the
   normal render pipeline, then serve it. While generating, the request blocks;
   progress is logged to stderr. Concurrent requests for the same key share one
   generation. Across keys, generation is **serialized** (one render at a time);
   cached files are served concurrently.
5. Generation failure → `500` with the standard error document; the failure is
   scoped to that creature. `/catalog.json` and other creatures keep working.

## Error document

Every non-`2xx` JSON response uses the existing CLI error schema:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "error",
  "error": {
    "code": "stale-asset",
    "message": "Asset 0123… was generated from an older recipe.",
    "location": {"path": "creatures/ridge-stalker/0123…/ridge-stalker.glb"},
    "expected": "4567…",
    "actual": "0123…",
    "remedy": "Reload the catalog and retry the current asset URL."
  }
}
```

Viewer-specific codes:

| Code | HTTP | Meaning |
|------|------|---------|
| `stale-asset` | 409 | Requested recipe hash is no longer current. |
| `recipe-not-found` | 404 | Name/path does not match the current catalog. |
| `viewer-asset-failed` | 500 | Generation failed for this creature; details in `message`/`remedy`. |
| `io-failure` | 500 | Cache/filesystem failure. |
| `usage-error` | 405 | Method not allowed or malformed request path. |

`404` is also used for traversal attempts and unknown static paths; the response
never reveals filesystem contents.

## Headers

All responses include:

```text
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self';
  img-src 'self' data: blob:; connect-src 'self' blob:; object-src 'none'; base-uri 'none'
```

Cache policy:

- `/` and `/assets/**`: `Cache-Control: no-cache` (revalidate; local files can
  change during development).
- `/catalog.json`, `/healthz`: `Cache-Control: no-store`.
- `/creatures/<name>/<sha>/...`: `Cache-Control: public, max-age=31536000,
  immutable` because the URL is content-addressed.

No CORS headers. The frontend is same-origin in both modes.

## Path safety

For `/assets/**` and `/creatures/**`:

- Decode percent-encoding once, reject NUL, `..`, absolute paths, backslashes,
  and empty segments.
- Resolve against an allowlisted root and verify the resolved path is still
  inside that root.
- Static assets are limited to the files shipped under `viewer/static/`
  (including `third_party`); no repository files are served.
- Creature files are limited to the cache's content-addressed directories.
- No directory listings.

## Deep links are client-side

The server never parses viewer routes. `#/<creature>/<clip>` and
`?category=&q=` are handled by the frontend, so the same URLs work on a plain
static host without rewrite rules. Malformed or unknown values fall back per
[data-model.md §8](../data-model.md#8-viewersession-client-state).

## Manual checks

```bash
beastforge view --no-browser --port 8765 &
curl -fsS http://127.0.0.1:8765/healthz
curl -fsS http://127.0.0.1:8765/catalog.json | head
curl -fsS http://127.0.0.1:8765/ >/dev/null
curl --path-as-is -sS -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8765/creatures/../library/echo/echo.yaml   # 404
kill %1
```
