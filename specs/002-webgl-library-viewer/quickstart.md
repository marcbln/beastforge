# Quickstart & Validation: WebGL Library Viewer

**Feature**: `002-webgl-library-viewer` | **Date**: 2026-11-15

Runnable scenarios that prove the feature end-to-end. Implementation details live
in [plan.md](./plan.md), [research.md](./research.md), and
[data-model.md](./data-model.md); contracts are under [contracts/](./contracts/).

## Prerequisites

- Python 3.12+ and `uv`
- The sibling texforge checkout at `../texforge` (or `--texforge-library` /
  `BEASTFORGE_TEXFORGE_LIBRARY`)
- A desktop browser with WebGL for the manual viewer checks; no browser is
  needed for the default test suite
- Run every command from the repository root unless stated otherwise

```bash
uv sync --all-groups
uv run beastforge --version
uv run beastforge validate
```

Expected: version prints `beastforge 0.1.0` (or the current version), validation
exits 0, and no tracked file changes.

---

## 1. Browse the library (US1)

```bash
uv run beastforge view
```

Expected:

- A browser opens on a gallery of every loadable creature; each card shows
  name, category, and description.
- Visible cards gain live WebGL thumbnails; off-screen cards do not generate
  anything until scrolled into view.
- The category filter narrows the cards; the search box narrows by name and
  description and shows an explicit empty state for a non-match.
- Selecting a card changes the URL to `#/<creature>/<first-clip>`.
- Reloading a filtered URL preserves `?category=...&q=...`.
- The terminal prints the URL and "press Ctrl-C to stop"; Ctrl-C releases the
  port.

Stop with Ctrl-C and confirm the port is free (the process exits 0 on a clean
stop; 130 on Ctrl-C).

---

## 2. Inspect a creature (US2)

Open a known creature, for example `#/ridge-stalker/idle`:

- The camera frames the whole creature from manifest bounds with no manual
  adjustment.
- Orbit (drag), zoom (wheel/pinch), and pan stay centered on the creature.
- The clip list matches the manifest `clips[]`; switching clips restarts
  playback and marks the active clip with text/shape, not color alone.
- Timeline marks appear at each `events[]` time for the active clip and are
  labeled with the event name.
- Inspector tabs **Manifest**, **Clips**, and **Events** display values that
  equal the sidecar manifest.
- A clip with no matching glTF animation is disabled with an inline warning; the
  other clips still play.

Contract cross-check (no browser):

```bash
uv run pytest tests/contract/test_viewer_catalog.py -q
```

Expected: catalog schema validates, coverage equals the loadable recipe set, and
each entry's `name`/`category`/`description`/`recipeSha256` equals the generated
manifest.

---

## 3. On-demand generation and cache reuse (US3)

Use a scratch cache so the default cache is untouched:

```bash
rm -rf /tmp/bf-view-cache
uv run beastforge view --no-browser --port 8765 --cache-dir /tmp/bf-view-cache
```

In a second terminal:

```bash
curl -fsS http://127.0.0.1:8765/healthz
curl -fsS http://127.0.0.1:8765/catalog.json | head -c 400
```

Expected: `{"status":"ok"}`, then a catalog with relative `creatures/...` URLs.

Open a creature URL in the browser (or `curl` its asset URL from the catalog).
The first request prints `generating <name>…` / `ready <name>` on stderr and
serves the asset. Reopening it serves from cache with no new generation and no
new files in the cache directory. The terminal still reports the URL and stop
instruction.

**Recipe change invalidation** (does not modify tracked files):

```bash
cp -r library /tmp/bf-lib
# Change a parameter default in /tmp/bf-lib/quadruped/ridge-stalker.yaml
uv run beastforge view --no-browser --port 8766 --cache-dir /tmp/bf-view-cache \
  --library /tmp/bf-lib
```

Expected: the catalog now points at a new `recipeSha256` path; the new asset is
generated; the old cache directory is no longer referenced. Requesting the old
hash returns `409 stale-asset`; reloading the catalog and using the new URL
works.

**No tracked writes**:

```bash
git status --short
```

Expected: no changes from running the viewer (only the temporary cache and any
untracked scratch paths you created yourself).

---

## 4. Static export (US4)

```bash
rm -rf /tmp/bf-site
uv run beastforge view --export /tmp/bf-site --no-browser
```

Expected layout:

```text
/tmp/bf-site/
├── index.html
├── assets/
├── catalog.json
├── bundle.json
└── creatures/<name>/<sha>/<name>.glb
    creatures/<name>/<sha>/<name>.manifest.json
```

Serve it with a plain static server (no Python viewer, no network beyond the
bundle):

```bash
python3 -m http.server 9000 --bind 127.0.0.1 --directory /tmp/bf-site
```

Open `http://127.0.0.1:9000/` and verify `#/ridge-stalker/idle` loads directly,
orbits, and plays every clip. Open DevTools → Network and confirm no request goes
to an external host.

**Non-empty target safety**:

```bash
touch /tmp/bf-site/keep-me.txt
uv run beastforge view --export /tmp/bf-site            # exit 1, export-exists
uv run beastforge view --export /tmp/bf-site --force    # replaces only owned paths
test -f /tmp/bf-site/keep-me.txt && echo "unrelated file preserved"
```

**Dry run**:

```bash
uv run beastforge view --export /tmp/bf-site-dry --dry-run
test ! -e /tmp/bf-site-dry && echo "nothing written"
```

**Machine report**:

```bash
uv run beastforge view --export /tmp/bf-site-json --json | python3 -m json.tool
```

Expected: `mode: "export"`, sorted `creatures`, a `files` count, and
`dry_run: false`.

---

## 5. Determinism (FR-016, SC-004)

```bash
rm -rf /tmp/bf-a /tmp/bf-b
uv run beastforge view --export /tmp/bf-a --no-browser
ROOT=$(pwd)
(cd /tmp && uv run --project "$ROOT" beastforge view --export /tmp/bf-b --no-browser)
diff -r /tmp/bf-a /tmp/bf-b
```

Expected: no differences. Also:

```bash
uv run pytest -m slow tests/determinism/test_viewer_export.py -q
```

This compares two full exports from different working directories: every file
hash, the catalog bytes, the manifest bytes, and `bundle.json` ordering.

---

## 6. Automated contract, offline, and integration checks

```bash
uv run pytest tests/unit/test_viewer_catalog.py tests/unit/test_viewer_cache.py -q
uv run pytest tests/contract/test_viewer_catalog.py tests/contract/test_viewer_offline.py -q
uv run pytest tests/integration/test_view_cli.py tests/integration/test_view_server.py -q
```

Expected: all pass offline with no browser. The server integration tests cover
`/`, `/assets`, `/catalog.json`, `/healthz`, traversal rejection, `409` stale
hash, per-creature `500` isolation, on-demand generation then cache reuse, and
port release on shutdown.

The default suite must remain within 10% of its previous runtime (SC-009):

```bash
uv run pytest -q
```

---

## 7. Opt-in browser smoke check (FR-021, SC-010)

```bash
uv sync --group viewer
uv run playwright install chromium
BEASTFORGE_VIEWER_SMOKE=1 uv run pytest -m viewer tests/viewer -q
```

Expected: the test starts the viewer with `--no-browser --port 0`, opens the
gallery, asserts the card count, opens a card, waits for the canvas/model and
clip list, switches a clip, asserts event-mark count against the manifest,
reloads a deep link, and confirms the same creature/clip is active.

Without `BEASTFORGE_VIEWER_SMOKE=1` (or without Playwright installed) the test is
skipped; the default `pytest` run never launches a browser.

---

## 8. Continuous integration / Pages (FR-019, SC-008)

On a push to `main` touching `library/**`, the viewer/CLI sources,
`pyproject.toml`, `uv.lock`, or the workflow:

1. CI checks out `beastforge` and its sibling `texforge`.
2. Runs `uv sync --all-groups`, `uv run pytest -m "not slow and not viewer"`,
   and `uv run beastforge validate`.
3. Runs `uv run beastforge view --export site --force --no-browser`.
4. Deploys `site/` as a Pages artifact.

Expected: the published site reflects the current recipes; no `.glb` or manifest
binary is committed (`git status` clean after the workflow). A recipe change
rebuilds and republishes automatically.

---

## 9. Edge cases

| Scenario | Check | Expected |
|----------|-------|----------|
| Empty/unreadable library | `--library` pointing at an empty dir | Explicit empty gallery + warnings; no blank page |
| Unknown creature deep link | `#/does-not-exist/idle` | Gallery + explanatory toast; no crash |
| Unknown clip deep link | `#/ridge-stalker/nope` | First manifest clip + toast |
| Creature with no clips | A fixture recipe with none | Model renders; playback disabled with an explanation |
| Asset generation failure | Break a texforge reference in a scratch library | Card/stage shows an actionable error; the rest of the gallery works |
| WebGL unavailable | Disable WebGL in the browser | Clear "3D unavailable" banner; catalog and inspector remain usable |
| Slow/partial asset load | Throttle the network | Loading state per card; the gallery is not blocked |
| Export into non-empty dir | `touch` an unrelated file, export with `--force` | Unrelated file preserved; only owned paths replaced |
| Offline | DevTools offline after load / static scan | Zero external requests |

---

## 9a. Validation notes (implementation, 2026-11-15)

- Exported the full shipped library with
  `beastforge view --export /tmp/bf-site-verify --no-browser --json`: 5
  creatures / 28 files, `bundle.json` sorted from `assets/app.js` through
  `index.html`, no warnings.
- Served the bundle with
  `python3 -m http.server 9411 --bind 127.0.0.1 --directory /tmp/bf-site-verify`:
  `/` returned 200, `/catalog.json` returned 5 entries with relative
  `creatures/...` URLs, the first GLB returned 200 (382 436 bytes), and the
  deep-link URL `/?category=quadruped&q=ridge#/ridge-stalker/idle` returned the
  same entry point (routing is client-side, so no rewrite rule is needed).
- The offline contract test scans `index.html` and every non-vendored runtime
  module for external `import`/`fetch`/`src`/`href` URLs and finds none.
- No generated `.glb`, manifest, or `site/` content is committed; `site/` is
  ignored and CI publishes the artifact.
- Security/perf spot check (2026-11-15): `ss` showed the server listening only on
  `127.0.0.1:<ephemeral>`; a raw `assets/../library/...` request returned `404`;
  `catalog.json` carried the exact CSP, `nosniff`, `no-referrer`, and `no-store`
  headers. Warm responses measured `/healthz` 0.001 s, `/` 0.002 s, and the
  first `catalog.json` build 0.40 s for 5 recipes (well under the 10 s goal).
  The gallery filter over 100 synthetic entries averaged 0.06 ms in a Node
  microbenchmark (goal <100 ms), and `thumbnails.js` caps in-flight asset
  requests at 3 with a 24-scene LRU.

## 10. Documentation and release checks

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

Confirm in the same change:

- `docs/cheatsheet-cli.md` has a `## view` section whose commands exit 0 with
  `--help`.
- `docs/api.md`, `docs/architecture.md`, `docs/development.md`,
  `docs/environment-variables.md`, `README.md`, `SKILL.md`, and `CHANGELOG.md`
  describe the new surfaces.
- The version bump is minor (new backward-compatible capability) and still has
  one source in `src/beastforge/__init__.py`.
