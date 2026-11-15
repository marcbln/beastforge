# Phase 0 Research: WebGL Library Viewer

**Feature**: `002-webgl-library-viewer` | **Date**: 2026-11-15
**Inputs**: [spec.md](./spec.md), ADRs
[261115-5](../../_ai/technical_decisions/ADR__261115-5__buildless-webgl-library-viewer.md)
and [261115-6](../../_ai/technical_decisions/ADR__261115-6__dual-mode-viewer-delivery.md),
ADRs 261114-1/2, and [_ai/conventions.md](../../_ai/conventions.md).

The two accepted viewer ADRs fix the frontend posture (buildless, vendored
three.js), the single catalog contract, the read-only boundary, localhost-first
delivery, and the deterministic static export. This file treats those as
**constraints, not unknowns** and resolves the engineering choices the spec and
design handoff leave open: package layout, catalog shape and versioning, asset
addressing and cache lifecycle, export determinism, thumbnail concurrency,
server security, CI topology, test layering, and configuration. **No NEEDS
CLARIFICATION remains at the end of this file.**

---

## D1 — Package layout and delivery architecture

**Decision**: Ship the viewer as `src/beastforge/viewer/` inside the existing
Python package. Split it into:

- `catalog.py` — pure derivation from the scanned library to a `CatalogDocument`;
- `cache.py` — local asset cache keyed by recipe SHA-256, with generation and
  per-key locking;
- `export.py` — pure bundle plan plus a filesystem writer for the static bundle;
- `server.py` — a loopback `ThreadingHTTPServer` adapter;
- `assets.py` — `importlib.resources` locator for the static files;
- `static/` — the buildless frontend;
- `third_party/three/` — pinned vendored runtime.

`cli/view.py` is a thin Typer boundary that selects serve or export mode and
renders the report. No viewer logic lives in the CLI module.

**Rationale**: This preserves the repository's existing pure-core/adapters split
(`architecture:separation`, `architecture:solid`). Catalog derivation and bundle
planning are testable without a socket, a browser, or a cache. The static files
must travel with the installed wheel, so they belong inside the package; a
top-level `viewer/` directory would require custom Hatch packaging and could
drift from the installed layout.

**Alternatives considered**:
- *Top-level `viewer/` source directory + Hatch `force-include`.* Works, but
  duplicates the source-of-truth layout, complicates editable installs, and
  makes `importlib.resources` resolution less direct for no benefit.
- *Separate `beastforge-viewer` package.* Rejected: one product, one version
  source, one install step (`uv sync`).
- *Server logic inside `cli/view.py`.* Rejected: untestable without a process
  boundary and violates the adapter/core split.

---

## D2 — Buildless frontend and vendored three.js

**Decision**: Hand-write `index.html`, `styles.css`, and ES modules; use a
browser-native import map:

```html
<script type="importmap">
{"imports": {
  "three": "./assets/three/three.module.js",
  "three/addons/": "./assets/three/addons/"
}}
</script>
```

Vendor `three.module.js`, `addons/loaders/GLTFLoader.js`,
`addons/utils/BufferGeometryUtils.js`, and `addons/controls/OrbitControls.js`
under `src/beastforge/viewer/third_party/three/`, together with `VERSION`
(exact upstream version and retrieval date/URL) and `LICENSE` (three.js MIT
text). The files are copied into the static bundle as `assets/three/...`.
No CDN, no npm, no bundler, no minifier, no post-processing.

**Rationale**: ADR 261115-5 requires a buildless, offline, pinned runtime. An
import map is the standard browser mechanism for bare-specifier resolution and
lets unmodified three.js example modules import `three` without a bundler.
Vendoring the unminified module build keeps the code reviewable and makes the
upgrade a deliberate file replacement. `OrbitControls` is added to the vendor
set because FR-004 requires orbit and zoom; writing a custom orbit controller
would duplicate a well-tested standard component for no determinism benefit.

**Alternatives considered**:
- *`<model-viewer>`.* Rejected by the ADR: weak clip/skeleton/manifest access.
- *Vite/esbuild/rollup.* Rejected: second toolchain and build artifact.
- *CDN with SRI.* Rejected: violates offline and zero-external-request.
- *Custom pointer orbit/zoom.* Rejected: more code, worse accessibility and
  inertia behaviour, no requirement it solves.

**Upgrade policy**: Replace the four files and `VERSION` in one reviewable
commit, run the browser smoke check, and note the version in `CHANGELOG.md`.
Never mix versions between `three.module.js` and its addons.

---

## D3 — Catalog contract, shape, and versioning

**Decision**: `catalog.json` is a versioned document with
`schemaVersion: "1.0"` (MAJOR.MINOR), `toolVersion`, `generatedBy`, an ordered
`categories` list, an ordered `creatures` array, and an ordered `warnings`
array. Fields use camelCase to match the manifest contract. Each entry carries
only discovery facts and references:

```json
{
  "name": "ridge-stalker",
  "category": "quadruped",
  "description": "…",
  "tags": ["quadruped", "predator", "ridge"],
  "recipeVersion": "1.0.0",
  "testedWith": "0.1.0",
  "recipeSha256": "…64 hex…",
  "asset": "creatures/ridge-stalker/<sha>/ridge-stalker.glb",
  "manifest": "creatures/ridge-stalker/<sha>/ridge-stalker.manifest.json"
}
```

`categories` uses the canonical order `boss, quadruped, swarm, other`, filtered
to present categories. `creatures` is sorted by `name`. `warnings` is sorted by
`path` and has `{path, message}` with a project-relative path. Serialization is
`beastforge.utils.canonical.canonical_json` (sorted keys, compact, ASCII, no
timestamps/NaN). URLs are **relative to the catalog document**, never
host-absolute.

**Rationale**: The catalog is a web-facing contract like the manifest, so
camelCase and a `MAJOR.MINOR` version follow the established manifest
precedent (ADR 261114-1). Limiting entries to discovery facts plus URLs means
the catalog can be produced from recipes without generating assets, while every
fact it surfaces (`name`, `category`, `description`) is also in the manifest and
is asserted equal by a contract test (FR-018). Bounds, clips, events, sockets,
volumes, phases, and provenance stay in the manifest and are fetched by the
viewer; this avoids duplicating the gameplay contract in two places.

**Versioning rules**: Additive fields keep the major version and bump MINOR;
removing/renaming a required field, changing a URL shape, or changing a value's
meaning bumps MAJOR. The viewer compares the major component only, reads known
fields, ignores unknown fields, and rejects a different major with an explicit
banner (mirroring the manifest consumer rule). `recipeSha256` is computed from
the canonical parsed recipe document (`recipe_digest`), the same value the
manifest records in `provenance.recipeSha256`.

**Alternatives considered**:
- *snake_case like CLI reports.* Rejected: the catalog is consumed by the web
  client next to the manifest, and two casing conventions in one browser session
  invites bugs.
- *Embed the whole manifest per entry.* Rejected: duplicates the authoritative
  contract, inflates the catalog, and invites drift.
- *No version field.* Rejected: the catalog is a published surface and must be
  evolvable.
- *Absolute URLs.* Rejected: breaks relative static hosting and determinism.

---

## D4 — Asset addressing: content-addressed paths

**Decision**: Every generated package lives at:

```text
creatures/<name>/<recipeSha256>/<name>.glb
creatures/<name>/<recipeSha256>/<name>.manifest.json
```

Both delivery modes use the same shape. The catalog points at the current
`recipeSha256` directory. A request for an older hash is rejected as stale; the
client reloads the catalog. This makes asset URLs immutable and cacheable
forever while recipe changes produce new URLs.

**Rationale**: FR-012 requires reusing cached assets and detecting when a recipe
has changed so stale assets are not served. Content addressing solves both
without mtime checks, sidecar indexes, or cache invalidation heuristics: change
the recipe → change the hash → new path → cache miss → regenerate. It also makes
the static export safely cacheable on a CDN/Pages because a URL's content never
changes. `recipeSha256` is already computed by the generator and recorded in the
manifest provenance, so the viewer does not invent a new identity.

**Alternatives considered**:
- *`<name>.glb?v=<sha>` query strings.* Rejected: some static servers ignore
  query strings for caching, and a stale URL could still resolve to new bytes.
- *mtime/size comparisons.* Rejected: not deterministic across checkouts and
  unreliable for generated outputs.
- *A separate cache index file.* Rejected: another source of truth to corrupt.

---

## D5 — On-demand generation, serialization, and cache lifecycle

**Decision**: `AssetCache.ensure(name, sha)`:

1. Resolves `<cache_root>/<name>/<sha>/` and returns immediately if both the
   `.glb` and `.manifest.json` exist and the manifest's
   `provenance.recipeSha256` equals `sha`.
2. Otherwise takes a per-`(name, sha)` `threading.Lock` (double-checked after
   acquisition) and renders into a temporary directory under the cache root
   using the existing `beastforge.render.render` with `force=True` and
   `cwd=library_root.parent`.
3. Verifies the manifest digest, then renames the completed temporary directory
   into the final `<name>/<sha>/` location in one `os.replace` so a reader never
   sees a half-written package. The temporary directory is removed in `finally`.

Generation is **serialized globally** through one worker lock/executor: cached
assets are served concurrently by the threaded server, but only one render runs
at a time. A failed generation leaves no final entry; the next request retries.
Old hash directories are not deleted automatically (disposable cache);
`--cache-dir` may be deleted by the user at any time. Startup removes only stale
`.beastforge-view-tmp-*` directories older than one hour.

**Rationale**: FR-012/FR-013 and the edge case "asset generation failure" require
reuse, correct invalidation, and a per-creature failure that does not poison the
rest of the gallery. Generation is serialized because the render pipeline and
texforge were written for sequential CLI use and texforge publishes no
thread-safety contract; corrupt textures are a far worse outcome than a short
queue. The frontend's visibility gating means only a handful of cards are ever
requested at once, so serialization does not delay the gallery's first paint.
Reusing `render()` (rather than duplicating the pipeline) preserves the
validation gate, atomic write, and determinism guarantees.

**Alternatives considered**:
- *Pre-generate the whole library on startup.* Rejected: violates "generate only
  for creatures the user actually opens or previews", makes startup unbounded,
  and wastes work.
- *Parallel generation (2–4 workers).* Rejected for v1: unverified texforge
  thread safety; can be revisited with a process pool and a measured need.
- *Background subprocess per asset.* Rejected: process management, duplicated
  config resolution, and harder error propagation for no benefit.

---

## D6 — Static export layout and determinism

**Decision**: `beastforge view --export DIR` writes:

```text
DIR/
├── index.html
├── assets/                  # copied static frontend incl. assets/three/
├── catalog.json
├── bundle.json              # ordered file list + SHA-256 + byte sizes
└── creatures/
    └── <name>/<sha>/<name>.glb
        <name>/<sha>/<name>.manifest.json
```

Rules:

- Render each recipe into a temporary directory, then place files in the
  content-addressed layout. Use `cwd=library_root.parent` so manifest
  `provenance.recipePath` labels are stable (`library/...`).
- Catalog entries and warnings sorted; bundle file list sorted by path; all JSON
  via `canonical_json`.
- No timestamps, hostnames, locale-dependent formatting, or unseeded values.
- Copy static files byte-for-byte in sorted path order; do not rewrite their
  contents.
- `bundle.json` records `{schemaVersion:"1", toolVersion, files:[{path, sha256,
  bytes}]}` in sorted path order for every emitted file **except itself**. It is
  build provenance for determinism tests and CI, not a viewer input.
- Refuse a non-empty target unless `--force`. With `--force`, remove and replace
  only the owned paths (`index.html`, `assets/`, `catalog.json`, `bundle.json`,
  `creatures/`); unrelated files are preserved.
- Build into a temporary sibling directory, then install only the owned paths
  into the target (rename wholesale only when the target is new/empty). On
  failure leave no partial bundle. A generation/gate failure aborts the export
  with exit 3 (a published bundle must be complete); unreadable-recipe scan
  warnings are non-fatal and recorded in `catalog.json`.
- `--dry-run` prints the planned file list and counts without writing.

**Rationale**: FR-015/FR-016 and SC-004. Canonical JSON plus sorted traversal
removes the usual determinism leaks. Fixed `cwd` removes the one path-dependent
value the manifest embeds. `bundle.json` makes "identical file lists and
contents" mechanically checkable instead of relying on `find | sort` in a test.
Owned-path replacement satisfies "never unrelated files" while allowing
idempotent re-exports.

**Alternatives considered**:
- *Write in place with no staging.* Rejected: a failed export leaves a broken
  site.
- *Delete the whole target with `--force`.* Rejected: could destroy unrelated
  files.
- *Zip/tar the bundle.* Rejected: Pages deploys directories; an archive adds a
  second format and loses static-host simplicity.
- *`file://` support.* Rejected: `fetch` of GLBs fails under `file://`; static
  hosting is the documented path.

---

## D7 — Local HTTP server and security posture

**Decision**: A `ThreadingHTTPServer` bound to **`127.0.0.1` only**, port `0`
(ephemeral) by default, `--port` to pin. Routes:

| Method | Path | Behaviour |
|--------|------|-----------|
| GET | `/` or `/index.html` | frontend entry point |
| GET | `/assets/<path>` | static package files; normalized; allowlisted roots/extensions |
| GET | `/catalog.json` | regenerate from the current library per request; `Cache-Control: no-store` |
| GET | `/creatures/<name>/<sha>/<file>` | validate name+sha against current catalog; ensure cached asset; immutable cache header |
| GET | `/healthz` | `{"status":"ok"}` for tests and operators |
| * | anything else | 404 JSON |

Headers on every response: `X-Content-Type-Options: nosniff`, a restrictive CSP
(`default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:
blob:; connect-src 'self'; object-src 'none'; base-uri 'none'`), and
`Referrer-Policy: no-referrer`. No CORS, no directory listing, no symlink
following outside the allowlisted root. Path validation rejects `..`, absolute
paths, backslashes, NULs, and unknown extensions before touching the filesystem.
Creature `name` must match a catalog entry; `sha` must equal that entry's current
`recipeSha256`; otherwise return a JSON error (`404` unknown name, `409`
`stale-asset` with the current sha). Generation failures return `500` with the
standard error body and do not affect `/catalog.json` or other creatures.

Shutdown: handle SIGINT/SIGTERM, call `server.shutdown()`, close the socket, and
exit 0 on a clean stop (130 on Ctrl-C per CLI convention). `--no-browser`
suppresses `webbrowser.open`; the server prints the URL and the stop
instruction to stdout/stderr regardless.

**Rationale**: FR-014 (local only), FR-010 (per-recipe failure isolation),
FR-013 (no tracked writes), and `cli:errors`. Binding to loopback is the
simplest enforceable guarantee; no `--host` flag is offered. Regenerating the
catalog per request makes the local mode always reflect the current library
(`beastforge list`). Content-addressed paths make immutable caching safe and
stale detection explicit.

**Alternatives considered**:
- *Flask/FastAPI/uvicorn.* Rejected: new runtime dependency for a handful of
  routes; ADR 261115-6 names stdlib `http.server`.
- *`--host 0.0.0.0` for LAN access.* Rejected: FR-014 forbids non-local reach.
- *Serving the repository root.* Rejected: leaks unrelated files; only the
  allowlisted static roots and generated cache are exposed.
- *Long-lived generate queue with WebSocket progress.* Rejected for v1: the
  first screen has few visible cards, and blocking HTTP + stderr progress is
  sufficient and simpler.

---

## D8 — Live thumbnails without 100 simultaneous generations

**Decision**: One shared offscreen `WebGLRenderer` renders 256×256 card frames
into a single offscreen canvas; each resulting frame is blitted into the card's
2D `<canvas>` immediately after render. Card assets are requested only when the
card intersects the viewport (`IntersectionObserver`) and at most **3** requests
are in flight (the server still serializes generation; see D5). Loaded GLTF
scenes for thumbnails are kept in an LRU (24 entries)
with explicit disposal of geometries, materials, and textures on eviction. A
visible card shows a rest-pose 3/4 frame; a hovered/focused card plays its
`idle` clip at ~15 fps unless `prefers-reduced-motion` is set.

**Rationale**: FR-003 asks for a live 3D thumbnail without opening the creature;
the "very large library" edge case asks that assets be generated only for
creatures the user actually previews. Visibility-gated requests reconcile both.
One renderer avoids exhausting browser WebGL contexts (typically 8–16 per page)
and keeps 100 cards affordable. LRU disposal bounds memory. Hover animation
makes the thumbnail feel live without animating every card.

**Alternatives considered**:
- *One renderer/context per card.* Rejected: context limit, memory, and
  browser instability.
- *Pre-render thumbnails to PNG during export.* Rejected: adds a CPU/GPU bake
  step, bloats the bundle, and still needs live 3D in local mode.
- *Animate every visible card.* Rejected: wasteful and distracting; hover/focus
  animation plus a static rest frame satisfies "live".
- *Load all models on gallery open.* Rejected: unbounded generation and memory.

---

## D9 — Stage, auto-framing, clips, and event timeline

**Decision**: The stage uses a dedicated `WebGLRenderer` + `OrbitControls`
(damping enabled, zoom/pan constrained). On model load:

1. Read `bounds.min`/`bounds.max` and `suggestedScale` from the manifest.
2. Compute the bounding sphere, set `controls.target` to its center, and place
   the camera so the sphere fits the vertical and horizontal FOV with a small
   margin.
3. Scale the model by `suggestedScale` (consumers treat it as a uniform hint).
4. Light with a hemisphere light plus one directional light; no shadows, no
   external environment map; background from the theme.

Clips come from the manifest (`name`, `duration`, `loop`, `generator`) and are
matched by name to `gltf.animations`. Switching a clip resets the mixer and
starts the chosen action; non-loop clips stop at the end, loop clips wrap. A
play/pause control exists. The timeline is an accessible `<input type="range">`
scrubber with absolutely-positioned event marks at `event.time / clip.duration`;
clicking a mark seeks to that time. The active mark is indicated by shape/text,
not color alone. If the manifest declares a clip with no matching animation,
the entry is shown disabled with an inline warning and the rest of the clips
remain usable.

**Rationale**: FR-004/FR-005/FR-006 and US2. Framing from manifest bounds avoids
per-model heuristics and is the consumer-facing contract. Matching by name is
the only stable link between the sidecar and glTF animations. Using the mixer's
native playback keeps the browser from reimplementing animation.

**Alternatives considered**:
- *Frame from `Box3.setFromObject` after animation.* Rejected: animated bounds
  can exceed the manifest rest bounds and cause clipping.
- *Drive event marks from baked keyframes.* Rejected by ADR 261114-4: manifest
  events are authoritative.
- *Custom WebGL skinning/player.* Rejected: reimplements glTF playback.

---

## D10 — Deep links, filters, and invalid states

**Decision**: Viewer state lives in the URL:

- Hash route `#/<creature>/<clip>` selects the stage and active clip.
- Query string `?category=<category>&q=<text>` holds gallery filters, preserved
  across reloads and shareable.
- On load, parse query first, apply filters, then parse the hash. Unknown
  creature → gallery with an explanatory toast and the hash cleared. Unknown
  clip on a known creature → its first manifest clip with a toast. Unknown
  category → "all" with a toast.
- Navigating from gallery to stage pushes a hash entry; switching clips and
  filters uses `history.replaceState` so the back button returns to the gallery
  rather than walking every clip.
- Empty search/filter result shows an explicit empty state with a clear-filters
  action.
- If WebGL initialization fails, the gallery and inspector remain usable; the
  stage shows a clear "3D unavailable" banner instead of a broken canvas.

**Rationale**: FR-002/FR-008 and the edge cases. URL state needs no server
support, works identically in both delivery modes, and gives the static export
deep links for free (FR-017/FR-004 in US4). The fallback behaviour is specified
so invalid links never produce a blank page.

**Alternatives considered**:
- *Path-based routes (`/creature/clip`).* Rejected: static hosts would 404 on
  refresh without rewrite rules; hash routes are host-agnostic.
- *`localStorage` for filters.* Rejected: not shareable and not part of the
  spec's deep-link requirement.
- *A client-side router library.* Rejected: overkill for two state dimensions.

---

## D11 — Manifest tolerance and inspector

**Decision**: Parse the manifest as a JSON object with optional typed accessors.
Known fields are rendered with their declared meaning; unknown fields are ignored
for behaviour and shown in a collapsible "Raw manifest" view. The inspector has
three tabs:

- **Manifest** — creature, provenance (recipe path/hash/version, resolved params,
  tool/texforge versions), units/axes, bounds, suggested scale, skeleton root and
  joint count, sockets, volumes, phases, materials, playback, budgets.
- **Clips** — one row per manifest clip: name, duration, loop, generator; the
  active clip is marked.
- **Events** — one row per manifest event: clip, name, time; rows for the active
  clip are highlighted and scroll-linked with the timeline.

The viewer never invents a value, re-derives timing from keyframes, or mutates
the manifest. A missing optional field renders as "not declared", not as a
fabricated default. A different major `schemaVersion` stops manifest-based
features and shows the consumer-compatibility error; additive minor versions are
read normally.

**Rationale**: FR-007/FR-009 and the assumption that the sidecar manifest is
the only source of creature facts. A tolerant object model means a new manifest
field cannot break the viewer. Splitting tabs matches US2's independent test.

**Alternatives considered**:
- *A generated TypeScript type mirroring the manifest.* Rejected: no build step,
  and generated types drift.
- *Validating the manifest against JSON Schema in the browser.* Rejected: a
  schema validator is a large runtime dependency; the viewer only needs
  tolerance plus explicit major-version handling.
- *Hiding unknown fields.* Rejected: the raw view is useful during schema
  evolution and costs little.

---

## D12 — CI and GitHub Pages

**Decision**: Add `.github/workflows/pages.yml` triggered by pushes to `main`
touching:

```text
library/**
src/beastforge/viewer/**
src/beastforge/cli/view.py
src/beastforge/config.py
src/beastforge/library.py
pyproject.toml
uv.lock
.github/workflows/pages.yml
```

Workflow:

1. Check out `beastforge` into `$GITHUB_WORKSPACE/beastforge` and the sibling
   `texforge` repository into `$GITHUB_WORKSPACE/texforge` so the existing
   `../texforge` uv path source resolves. (If texforge is private, use a token
   with read access; the repository layout is otherwise unchanged.)
2. `uv sync --all-groups` in `beastforge`.
3. `uv run pytest -m "not slow and not viewer"`.
4. `uv run beastforge validate`.
5. `uv run beastforge view --export site --force --no-browser`.
6. `actions/upload-pages-artifact` with `path: beastforge/site`, then
   `actions/deploy-pages`.
7. Permissions `contents: read`, `pages: write`, `id-token: write`; concurrency
   group `pages`; environment `github-pages`.

No generated `.glb`/manifest files are committed; `site/` is ignored. A recipe
or viewer change rebuilds the full library, so the published catalog never
references a missing asset.

**Rationale**: FR-017/FR-019 and ADR 261115-6. Checking out both repositories as
siblings preserves the existing editable `texforge` dependency without changing
the project's install contract. Running tests and validation before export makes
the publish path a gate, not a best-effort script. Pages artifacts avoid a
`gh-pages` branch and committed binaries.

**Alternatives considered**:
- *Commit the bundle to a `gh-pages` branch.* Rejected by the ADR and FR-019.
- *A Node build action.* Rejected: no build step.
- *Publish only on tags.* Rejected: the handoff wants recipe changes to
  republish automatically; trigger filters are a maintainer decision already
  documented.
- *Install texforge from PyPI.* Rejected: the project intentionally uses a
  sibling editable checkout; CI mirrors that.

---

## D13 — Test strategy and opt-in browser check

**Decision**: Add these layers:

- **Unit** — catalog ordering/digests/warnings/URLs; cache keying, reuse,
  invalidation, lock behaviour, failed-generation cleanup; bundle plan ordering.
- **Contract** — catalog validates against
  `specs/002-webgl-library-viewer/contracts/catalog.schema.json`; coverage equals
  the loadable recipe set; each catalog entry's `name`/`category`/`description`
  equals the generated manifest's `creature` fields; additive unknown fields are
  tolerated; `bundle.json` validates against `bundle.schema.json`.
- **Integration** — `view --export` layout, JSON report, dry-run, non-empty
  refusal, `--force` preserving unrelated files, idempotent re-export; server
  `/`, `/assets`, `/catalog.json`, `/healthz`, 404 traversal, 409 stale sha, 500
  isolation, on-demand generation then reuse; `--port` and shutdown release the
  port.
- **Determinism** (`slow`) — export the full library twice from different
  working directories/temp roots and compare every `bundle.json` entry, every
  file hash, the catalog bytes, and the manifest bytes.
- **Offline** — scan `index.html` and runtime JS for external `import`/`fetch`
  URLs and assert none; assert exported HTML does not reference a host.
- **Browser smoke** (`viewer` marker + `BEASTFORGE_VIEWER_SMOKE=1`) — start the
  server with `--no-browser --port 0`, navigate, assert card count, open a card,
  assert a canvas/model loaded, assert the clip list matches the manifest, switch
  clips, assert event mark count, reload a deep link, and assert the same
  creature/clip is active. Uses Playwright from an optional dependency group.

Default `pytest` excludes the browser check structurally: the module calls
`pytest.importorskip("playwright")` and is skipped unless the environment flag is
set. The `slow` tests remain opt-in exactly like the existing determinism suite.

**Rationale**: FR-020/FR-021/SC-009/SC-010. Keeping heavy generation out of the
default path and using an injected fake producer for server integration keeps the
default run fast and offline. The contract tests are the automated proof that
catalog and manifest cannot drift. The Playwright check is the only place a real
browser is required and is deliberately opt-in.

**Alternatives considered**:
- *Run Playwright by default.* Rejected: violates offline/fast default and adds
  a browser download to every contributor's install.
- *Selenium/WebDriver.* Rejected: heavier setup; Playwright is the project's
  chosen optional tool.
- *Screenshot pixel comparison for the viewer.* Rejected: font/GPU variance
  makes it flaky; assert behaviour and DOM/counts instead.
- *No determinism test until later.* Rejected: FR-020 requires it.

---

## D14 — Configuration, versioning, and documentation surface

**Decision**:

- Add `cache_dir: str | None` to `Settings`; accept `cache_dir` in
  `.beastforge.toml` and the user config. Resolution order:
  `--cache-dir` > `BEASTFORGE_CACHE_DIR` > project/user `cache_dir` > default
  `$XDG_CACHE_HOME/beastforge/viewer` (or `~/.cache/beastforge/viewer`).
- Add `cli/view.py` command flags: `--export DIR`, `--port`, `--cache-dir`,
  `--no-browser`, `--force`, plus the standard global flags. `--export` and
  serve mode are mutually exclusive; `--port`/`--cache-dir` are serve-only, while
  `--no-browser` is accepted in both (a no-op in export).
- `--json` behaviour: serve mode emits one startup document
  `{schema_version, tool_version, status, mode:"serve", url, cache_dir,
  dry_run}` and then keeps running (progress on stderr); export mode emits
  `{schema_version, tool_version, status, mode:"export", output, creatures,
  files, warnings, dry_run}`.
- Update `docs/api.md` with the catalog, bundle, HTTP, and `view` report
  contracts; `docs/architecture.md` with the viewer component and data flow;
  `docs/development.md` with viewer/export/smoke commands; `docs/environment-
  variables.md` with `BEASTFORGE_CACHE_DIR`; `docs/cheatsheet-cli.md` with a
  `## view` section and "Most useful" rows; `README.md` and `SKILL.md` with the
  discovery workflow; `CHANGELOG.md` with an Unreleased entry.
- The viewer is a **minor** version bump (new backward-compatible capability).
  `beastforge.__version__` remains the single version source and feeds catalog
  `toolVersion`, bundle metadata, the CLI, and the manifest.

**Rationale**: `cli:configuration`, `cli:flag-vocabulary`, `docs:minimum-set`,
`release:semver`. Keeping the cache outside the repository by default satisfies
FR-013 while still allowing explicit overrides. Documenting every new surface in
the existing docs set avoids a parallel manual.

**Alternatives considered**:
- *A separate viewer config file.* Rejected: one project config convention.
- *Environment variable only, no config key.* Rejected: project config should be
  able to pin a cache location for reproducible local workflows.
- *A new package version major.* Rejected: nothing existing breaks.

---

## Resolved open questions from the design handoff

| Handoff question | Resolution |
|------------------|------------|
| Thumbnail concurrency and cache policy | 3 in-flight asset requests client-side; visibility-gated; server generation serialized; LRU 24 thumbnail models; content-addressed cache; no automatic pruning |
| Pages workflow trigger detail | Push to `main` filtered to `library/**`, viewer/CLI paths, `pyproject.toml`, `uv.lock`, and the workflow file |
| `catalog.json` schema governance | `MAJOR.MINOR`; additive fields bump MINOR; breaking changes bump MAJOR; viewer is major-strict/minor-tolerant |
| Vendored three.js upgrade policy | Explicit four-file replacement plus `VERSION`/`LICENSE` review, browser smoke check, and changelog note |
