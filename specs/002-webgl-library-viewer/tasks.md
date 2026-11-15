---
description: "Task list for feature 002 — WebGL Library Viewer"
---

# Tasks: WebGL Library Viewer

**Input**: Design documents from `specs/002-webgl-library-viewer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — FR-020 requires automated catalog/schema coverage and export
determinism checks; FR-021 requires an opt-in browser smoke check. The default
`pytest` run must stay offline, browser-free, and within 10% of its current runtime
(FR-021, SC-009).

**Organization**: Tasks are grouped by user story. The delivery spine (catalog,
cache, server, thin CLI) is foundational because US1, US2, US3, and US4 all need it;
each story then adds its own independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Every task includes an exact file path

## Path Conventions

- Single Python package at `src/beastforge/`; buildless frontend at
  `src/beastforge/viewer/static/`; vendored runtime at
  `src/beastforge/viewer/third_party/three/`.
- Tests live under `tests/{unit,contract,integration,determinism,viewer}/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the viewer package, vendor the pinned 3D runtime, and register
the buildless frontend as package data.

- [x] T001 Create the viewer package skeleton in `src/beastforge/viewer/__init__.py`, `src/beastforge/viewer/static/lib/`, and `src/beastforge/viewer/third_party/three/addons/`; the module docstring must state that the viewer is read-only and never re-derives gameplay facts.
- [x] T002 [P] Vendor the pinned three.js runtime under `src/beastforge/viewer/third_party/three/`: `three.module.js`, `addons/GLTFLoader.js`, `addons/BufferGeometryUtils.js`, `addons/OrbitControls.js`, `VERSION` (exact upstream version plus retrieval date/URL), and `LICENSE` (three.js MIT text). Never mix versions between the core module and addons.
- [x] T003 [P] Configure `pyproject.toml`: add the optional dependency group `viewer = ["playwright>=1.44"]`, add the pytest marker `viewer: opt-in browser smoke check`, and verify `uv build` includes `viewer/static/**` and `viewer/third_party/**` as wheel package data.
- [x] T004 [P] Implement `src/beastforge/viewer/assets.py` using `importlib.resources`: expose the static root, an iterator of static files, a byte reader, and the mapping `assets/three/<path>` → `third_party/three/<path>` so both delivery modes use the same `assets/three/...` URLs.
- [x] T005 [P] Add `site/` to `.gitignore` (CI export target) and confirm the default viewer cache path is never inside tracked content.

**Checkpoint**: Package skeleton, vendored runtime, and static-file locator exist.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Catalog derivation, cache, loopback server, and serve-mode CLI. These
block every user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Extend `src/beastforge/library.py` with `load_entry_with_document(path, *, cwd) -> tuple[LibraryEntry, dict[str, Any], str]` that returns the existing entry, the parsed YAML document, and `beastforge.rng.recipe_digest(document)`; leave `LibraryEntry.to_json()` and the `list --json` shape unchanged.
- [x] T007 Implement the catalog models and `build_catalog(settings, *, cwd)` in `src/beastforge/viewer/catalog.py` with these exact rules: `schemaVersion` is `"1.0"`; `toolVersion` is `beastforge.__version__`; `generatedBy` is `"beastforge"`; `categories` uses canonical order `["boss","quadruped","swarm","other"]` filtered to categories present; `creatures` has exactly one entry per loadable recipe, sorted by `name`, names unique; `warnings` has `{path, message}`, project-relative `path`, sorted by `path`; entry `name`, `category`, `description`, `tags`, `recipeVersion`, `testedWith` come from the parsed recipe; `recipeSha256` is 64 lowercase hex; `asset` is `creatures/<name>/<recipeSha256>/<name>.glb`; `manifest` is `creatures/<name>/<recipeSha256>/<name>.manifest.json`.
- [x] T008 Implement `catalog_json(document)` and `parse_catalog(payload)` in `src/beastforge/viewer/catalog.py`: serialize with `beastforge.utils.canonical.canonical_json` (sorted keys, compact, ASCII, trailing newline), keep relative POSIX URLs with no leading `/`, query string, or fragment, and make the consumer reject a different major `schemaVersion` while ignoring unknown fields in the same major.
- [x] T009 Add `cache_dir: str | None = None` to `Settings` in `src/beastforge/config.py`, accept `cache_dir` as a known project/user config key, read `BEASTFORGE_CACHE_DIR`, and add `resolve_cache_dir(settings, override=None)` with precedence `--cache-dir` > `BEASTFORGE_CACHE_DIR` > `cache_dir` config > `$XDG_CACHE_HOME/beastforge/viewer` (fallback `~/.cache/beastforge/viewer`).
- [x] T010 Implement `AssetCache` in `src/beastforge/viewer/cache.py`: resolve `<cache_root>/<name>/<sha>/`; a hit requires both `<name>.glb` and `<name>.manifest.json` and manifest `provenance.recipeSha256 == sha`; use a per-`(name, sha)` `threading.Lock` with a double-check after acquisition; serialize generation globally with one lock; call `beastforge.render.render(name, settings=..., out_dir=<temp>, force=True, cwd=<library_root>.parent)`; verify the manifest digest; install the completed temp directory with one `os.replace`; always remove the temp directory in `finally`; track in-memory states `absent | generating | ready | failed`.
- [x] T011 Extend `src/beastforge/viewer/cache.py` with `cleanup_stale_temp(older_than_seconds=3600)` for `.beastforge-view-tmp-*` directories, failure isolation (no final entry, next `ensure` retries, other keys unaffected), and an `on_event(kind, name)` progress hook emitting `generating` / `ready`.
- [x] T012 Implement `src/beastforge/viewer/server.py`: a `ThreadingHTTPServer` factory bound to `127.0.0.1` only (ephemeral port by default), with routes `GET /` and `/index.html`, `/assets/**`, `/catalog.json` (regenerated from the current library per request, `Cache-Control: no-store`), `/healthz` (`{"status":"ok"}`), and JSON 404/405 errors; include `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self' blob:; object-src 'none'; base-uri 'none'` on every response.
- [x] T013 Implement path safety in `src/beastforge/viewer/server.py` for `/assets/**` and `/creatures/**`: decode percent-encoding once; reject NUL, `..`, absolute paths, backslashes, and empty segments; resolve inside the allowlisted `viewer/static` (including `third_party`) or cache roots; never follow symlinks outside those roots; never list directories or reveal filesystem contents.
- [x] T014 Implement the creature route in `src/beastforge/viewer/server.py`: `<name>` must match a current catalog entry; `<sha>` must equal that entry's `recipeSha256` else `409` `stale-asset` with `error.actual` (requested) and `error.expected` (current); `<file>` must be exactly `<name>.glb` (`application/octet-stream`) or `<name>.manifest.json` (`application/json`); cache hit serves, cache miss calls `AssetCache.ensure` then serves; send `Cache-Control: public, max-age=31536000, immutable`; generation failure returns `500` `viewer-asset-failed` isolated to that creature; all errors use the existing `schema_version`/`tool_version`/`status`/`error` document shape.
- [x] T015 Implement serve mode in `src/beastforge/cli/view.py` with flags `--export`, `--port`, `--cache-dir`, `--no-browser`, `--force`, `--dry-run` plus the global flags; print `viewer: <url>`, `cache: <path>`, and `serving the current library; press Ctrl-C to stop` to stdout; emit `--json` ServeReport `{schema_version:"1", tool_version, status:"ok", mode:"serve", url, cache_dir, dry_run}` once after binding; make `--json` imply `--no-browser`; make serve `--dry-run` bind nothing and report `"url": null`; handle SIGINT/SIGTERM with `server.shutdown()`/socket close and exit `0` on clean stop, `130` on Ctrl-C.
- [x] T016 Register `view` in `src/beastforge/cli/app.py` and enforce contract usage errors (exit `2`) for `--export` with `--port` or `--cache-dir`, `--force` without `--export`, and `--port` outside `1..65535`; route generation progress and warnings to stderr (`generating <name> (<sha7>)…`, `ready <name>`, `warning: …`), honouring `--quiet`.

**Checkpoint**: `beastforge view --dry-run` works and the loopback server can serve a
catalog plus static files. User stories can now proceed.

---

## Phase 3: User Story 1 - Browse the library visually (Priority: P1) 🎯 MVP

**Goal**: Every loadable creature appears once as a searchable, category-filtered
card with a live 3D thumbnail.

**Independent Test**: Start the viewer against the shipped library, confirm every
loadable recipe appears exactly once with name, category, and description, apply a
category filter and a text search, and confirm cards narrow with an explicit empty
state and no regeneration.

### Tests for User Story 1

- [x] T017 [P] [US1] Add unit tests in `tests/unit/test_viewer_catalog.py` for canonical category order, ascending creature names, one entry per loadable recipe, 64-lowercase-hex `recipeSha256`, relative `creatures/...` URLs, warnings sorted by project-relative `path`, and byte-identical `catalog_json` across runs.
- [x] T018 [P] [US1] Add contract tests in `tests/contract/test_viewer_catalog.py` that validate the catalog against `specs/002-webgl-library-viewer/contracts/catalog.schema.json`, assert coverage equals the `library.scan_with_warnings` loadable set exactly once, and assert each entry's `name`, `category`, `description`, and `recipeSha256` equal the generated manifest (`tests/conftest.py::rendered` for `ridge-stalker`); also assert additive unknown fields are tolerated by the consumer.
- [x] T019 [US1] Add unit tests in `tests/unit/test_viewer_catalog.py` for an empty library (zero creatures, no crash) and an unreadable recipe (appears only in `warnings`, rest of catalog intact).

### Implementation for User Story 1

- [x] T020 [US1] Create `src/beastforge/viewer/static/index.html`: import map mapping `three` → `./assets/three/three.module.js` and `three/addons/` → `./assets/three/addons/`, CSP meta matching the server policy, a header with category filter and search input, a gallery region, an empty-state region, a warning banner region, a toast region, and the module entry `./app.js`.
- [x] T021 [US1] Create `src/beastforge/viewer/static/styles.css`: responsive card grid, card name/category/description, thumbnail canvas sizing, loading skeleton, explicit empty state, warning banner, filter bar, visible focus, and `prefers-reduced-motion` handling; never use color alone to signal state.
- [x] T022 [P] [US1] Create `src/beastforge/viewer/static/lib/catalog.js`: tolerant catalog fetch/parse (ignore unknown top-level and entry fields), reject a different major `schemaVersion` with an explicit banner message, and expose entry lookup by name.
- [x] T023 [P] [US1] Create `src/beastforge/viewer/static/lib/router.js`: parse `?category=<category>&q=<text>` and `#/<creature>/<clip>`, write filter state with `replaceState`, push the gallery→stage hash entry, return filters when going back, and fall back to gallery/all with a toast for unknown values.
- [x] T024 [US1] Create `src/beastforge/viewer/static/app.js` gallery bootstrap: load `catalog.json`, render one card per entry in catalog order with name, category, and description, apply the category filter and free-text search over name + description + tags, show match counts and the explicit empty state with a clear-filters action, surface scan warnings non-fatally, and wire card selection to the router without loading a stage asset yet.
- [x] T025 [US1] Create `src/beastforge/viewer/static/lib/thumbnails.js`: one shared offscreen `WebGLRenderer` at 256×256, `IntersectionObserver` visibility gating, at most 3 asset requests in flight, an LRU of 24 loaded scenes with explicit geometry/material/texture disposal on eviction, blit each rendered frame into the card canvas, show a rest-pose 3/4 frame, and play the `idle` clip at ~15 fps on hover/focus unless `prefers-reduced-motion` is set.
- [x] T026 [US1] Wire `src/beastforge/viewer/static/app.js` and `src/beastforge/viewer/static/lib/thumbnails.js` to the catalog's `asset`/`manifest` URLs: request thumbnails only for visible cards, show a per-card loading state, and show an actionable per-card error without blocking the rest of the gallery when generation fails.
- [x] T027 [US1] Add integration tests in `tests/integration/test_view_server.py` for `GET /`, `/index.html`, `/assets/<path>` (including `assets/three/...`), `/catalog.json` (`no-store`, correct content type, relative URLs), `/healthz`, `HEAD`, `405` for other methods, and `404` JSON for unknown paths.

**Checkpoint**: User Story 1 is independently demonstrable: gallery, filters,
search, empty state, warnings, and live thumbnails.

---

## Phase 4: User Story 2 - Inspect a creature's animation and manifest facts (Priority: P2)

**Goal**: Open one creature on an orbit stage, play every manifest clip, see event
marks at declared times, and read manifest facts without re-deriving anything.

**Independent Test**: Open a known creature, switch through every declared clip,
confirm playback and event marks match the manifest, orbit/zoom the model, and
compare every inspector value against the sidecar manifest.

### Implementation for User Story 2

- [x] T028 [P] [US2] Create `src/beastforge/viewer/static/lib/stage.js`: dedicated `WebGLRenderer` + `OrbitControls` (damping, constrained zoom/pan), read `bounds.min`/`bounds.max` and `suggestedScale` from the manifest, frame the bounding sphere with camera FOV plus a small margin, apply `suggestedScale` as a uniform hint, light with a hemisphere plus one directional light (no shadows or external environment map), and dispose renderer/controls on route change.
- [x] T029 [P] [US2] Create `src/beastforge/viewer/static/lib/clips.js`: build the clip list from `manifest.clips` (`name`, `duration`, `loop`, `generator`), match clips to `gltf.animations` by name, reset and restart the mixer on clip switch, play/pause, stop non-loop clips at the end and wrap loop clips, disable a declared clip with no matching animation plus an inline warning while leaving other clips usable, and place one timeline mark per `manifest.events[]` at `event.time / clip.duration` labeled with `event.name`.
- [x] T030 [P] [US2] Create `src/beastforge/viewer/static/lib/inspector.js`: three tabs **Manifest**, **Clips**, **Events**; render creature/provenance/units/axes/bounds/suggested scale/skeleton/sockets/volumes/phases/materials/playback/budgets; show a missing optional field as "not declared"; ignore unknown fields for behaviour and show them in a collapsible raw-manifest view; list one clip row and one event row per manifest declaration; call out a different major manifest `schemaVersion` with the standard compatibility message.
- [x] T031 [US2] Extend `src/beastforge/viewer/static/lib/catalog.js` with a tolerant manifest fetch (`fetchManifest(entry)`) that reads known fields, ignores unknown fields, rejects a different major `schemaVersion`, and returns the raw payload for the inspector's raw view.
- [x] T032 [US2] Wire the stage in `src/beastforge/viewer/static/app.js`: on card selection load the manifest and GLB, open `#/<creature>/<first-clip>`, switch clips with `replaceState`, keep filter query state, return to the gallery on back/clear-hash, show an explanatory toast for an unknown creature or clip, keep the model rendered with playback disabled for a creature with no clips, and keep gallery + inspector usable with a clear "3D unavailable" banner when WebGL initialization fails.
- [x] T033 [US2] Add the accessible timeline interaction in `src/beastforge/viewer/static/lib/clips.js` and `styles.css`: an `<input type="range">` scrubber, click/seek on a mark, keyboard operation, active mark indicated by shape/text in addition to color, and reduced-motion-safe playback chrome.

**Checkpoint**: User Story 2 is independently demonstrable against `#/ridge-stalker/idle`
and the sidecar manifest.

---

## Phase 5: User Story 3 - Start a local viewer in one command (Priority: P3)

**Goal**: One non-interactive command opens the viewer, generates missing assets on
demand, reuses cached assets, invalidates stale recipes, and never touches tracked
files.

**Independent Test**: From a clean cache, run `beastforge view`, confirm a browser
opens on a working gallery, open a never-generated creature, confirm it renders,
stop the command, and confirm no tracked files changed.

### Tests for User Story 3

- [x] T034 [P] [US3] Add unit tests in `tests/unit/test_viewer_cache.py` for keying by `(name, recipeSha256)`, a hit requiring both files and a matching manifest digest, reuse without invoking the producer, invalidation when the recipe hash changes, concurrent `ensure` calls performing at most one generation, failed generation leaving no final entry, and `cleanup_stale_temp` removing only `.beastforge-view-tmp-*` older than one hour.
- [x] T035 [US3] Add integration tests in `tests/integration/test_view_server.py` for `GET /creatures/<name>/<sha>/<file>` covering cache miss → on-demand generation → serve, cache hit → no generation, `409 stale-asset` with `expected`/`actual`, `500 viewer-asset-failed` isolation while `/catalog.json` and other creatures keep working, and port release after server shutdown; inject a fast fake producer so the default run stays offline.
- [x] T036 [US3] Add integration tests in `tests/integration/test_view_cli.py` for serve mode: startup prints URL/cache/stop lines, `/healthz` responds, `--json` emits exactly one serve document, serve `--dry-run` binds nothing and reports `"url": null`, invalid flag combinations exit `2`, `--port` is released after stop, and Ctrl-C semantics map to `130`.
- [x] T037 [US3] Add an integration test in `tests/integration/test_view_cli.py` asserting the resolved cache lives outside tracked content by default, `--cache-dir`/`BEASTFORGE_CACHE_DIR`/config precedence is honoured, and running the viewer leaves `git status --short` unchanged apart from the caller's scratch paths.
- [x] T038 [US3] Implement the remaining serve UX in `src/beastforge/cli/view.py` and `src/beastforge/viewer/server.py`: call `webbrowser.open` unless `--no-browser` or `--json`, stream `generating`/`ready` progress through the cache `on_event` hook to stderr, suppress progress under `--quiet`, and enable a no-timestamp per-request access log only under `--verbose`.

**Checkpoint**: User Story 3 is independently demonstrable from a clean cache and
leaves the repository untouched.

---

## Phase 6: User Story 4 - Publish the full library as a static site (Priority: P4)

**Goal**: One export command writes a self-contained, byte-identical static bundle
that CI publishes to GitHub Pages with no committed binaries.

**Independent Test**: Export twice from the same recipes and tool version, confirm
the file lists and bytes are identical, serve one bundle from a plain static server,
and confirm every creature loads, orbits, plays, and honours deep links.

### Tests for User Story 4

- [x] T039 [P] [US4] Add contract tests in `tests/contract/test_viewer_catalog.py` that validate `bundle.json` against `specs/002-webgl-library-viewer/contracts/bundle.schema.json`, assert `files` lists every emitted file except `bundle.json` exactly once, is sorted by POSIX path, and records 64-lowercase-hex `sha256` plus `bytes >= 0`.
- [x] T040 [P] [US4] Add integration tests in `tests/integration/test_view_cli.py` for export: bundle layout (`index.html`, `assets/`, `catalog.json`, `bundle.json`, `creatures/<name>/<sha>/...`), `--json` ExportReport (`mode:"export"`, sorted `creatures`, `files` count, `warnings`), `--dry-run` writing nothing, non-empty target refusal (`export-exists`, exit `1`), `--force` replacing only owned paths while preserving unrelated files, and idempotent re-export.
- [x] T041 [US4] Add the determinism test in `tests/determinism/test_viewer_export.py` using the `slow` marker: export the full library twice from different working directories and temp roots, then compare every `bundle.json` entry, every file hash and size, the catalog bytes, the manifest bytes, and bundle ordering.
- [x] T042 [P] [US4] Add the offline contract test in `tests/contract/test_viewer_offline.py`: scan `index.html` and every runtime JS module for external `import`/`fetch`/`src`/`href` URLs and assert none; assert an exported HTML file references no host and that runtime assets include only relative paths.

### Implementation for User Story 4

- [x] T043 [P] [US4] Implement the pure export plan in `src/beastforge/viewer/export.py`: enumerate static frontend files in sorted path order (mapping `third_party/three/**` to `assets/three/**`), the catalog, and each creature's `<name>.glb` + `<name>.manifest.json`; return the planned file map, the owned top-level paths (`index.html`, `assets/`, `catalog.json`, `bundle.json`, `creatures/`), and the `bundle.json` payload (`{schemaVersion:"1", toolVersion, files:[{path, sha256, bytes}]}` sorted by path, excluding `bundle.json` itself).
- [x] T044 [US4] Implement the export writer in `src/beastforge/viewer/export.py`: build into a temporary sibling directory; render every recipe with `cwd=<library_root>.parent` so manifest `provenance.recipePath` labels stay `library/...`; place outputs in `creatures/<name>/<recipeSha256>/`; copy static files byte-for-byte without rewriting; write catalog and bundle with `canonical_json`; install only owned paths atomically; refuse a non-empty target without `--force`; under `--force` preserve unrelated files; leave no partial bundle on failure; abort with exit `3` on a generation/gate failure while recording unreadable-recipe scan warnings as non-fatal.
- [x] T045 [US4] Implement export dispatch in `src/beastforge/cli/view.py`: `--export DIR` selects export mode, `--dry-run` prints the planned paths/counts and writes nothing, `--json` emits the ExportReport, human output prints `exported <n> creatures / <m> files to <dir>`, warnings go to stderr, and exit codes match `contracts/cli.md` (`0` success, `1` `export-exists`/IO, `3` gate/generation).
- [x] T046 [US4] Add `.github/workflows/pages.yml`: trigger on pushes to `main` filtered to `library/**`, `src/beastforge/viewer/**`, `src/beastforge/cli/view.py`, `src/beastforge/config.py`, `src/beastforge/library.py`, `pyproject.toml`, `uv.lock`, and the workflow file; check out sibling `beastforge` and `texforge`; run `uv sync --all-groups`, `uv run pytest -m "not slow and not viewer"`, `uv run beastforge validate`, and `uv run beastforge view --export site --force --no-browser`; upload and deploy `site/` as a Pages artifact with `contents: read`, `pages: write`, `id-token: write`, concurrency group `pages`, and environment `github-pages`.
- [x] T047 [US4] Verify the exported bundle from `python3 -m http.server --bind 127.0.0.1 --directory <export>`: deep links `#/<creature>/<clip>` and `?category=&q=` load directly, every creature orbits and plays, and DevTools shows zero requests to external hosts; record the result in the quickstart validation notes (no generated binaries committed).

**Checkpoint**: User Story 4 is independently demonstrable from a plain static host
and produces a deterministic bundle suitable for Pages.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, release hygiene, opt-in browser coverage, and the final
quality gate.

- [x] T048 [P] Update `README.md` (quick-start `beastforge view`) and `SKILL.md` (view/export discovery for agents) so the new workflow is discoverable without reading the spec.
- [x] T049 [P] Update `docs/cheatsheet-cli.md` with a `## view` section and "Most useful" rows exactly matching `contracts/cli.md`, verified against `beastforge view --help`.
- [x] T050 [P] Update `docs/environment-variables.md` with `BEASTFORGE_CACHE_DIR`, the `cache_dir` config key, and the full precedence `--cache-dir` > env > config > XDG default.
- [x] T051 [P] Update `docs/api.md` with the catalog, bundle, viewer HTTP, ServeReport, and ExportReport contracts, linking the schemas under `specs/002-webgl-library-viewer/contracts/`.
- [x] T052 [P] Update `docs/architecture.md` with the viewer component and data flow and `docs/development.md` with viewer/export/browser-smoke commands (`uv sync --group viewer`, `playwright install chromium`, `BEASTFORGE_VIEWER_SMOKE=1 ...`).
- [x] T053 [P] Update `CHANGELOG.md` with an `Unreleased`/Added entry for the viewer and change the 002 row in `specs/README.md` to its delivered status.
- [x] T054 Bump `__version__` in `src/beastforge/__init__.py` as a minor release (new backward-compatible capability); keep it the single version source feeding the catalog, bundle metadata, CLI, and manifest.
- [x] T055 Add `tests/viewer/test_browser_smoke.py` using `pytest.importorskip("playwright")`, the `viewer` marker, and `BEASTFORGE_VIEWER_SMOKE=1` as the only run gate: start `beastforge view --no-browser --port 0`, assert the card count, open a card, wait for the canvas/model and clip list, assert the clip list matches the manifest, switch a clip, assert the event-mark count, reload a deep link, and assert the same creature/clip is active; without the flag or Playwright the module is skipped.
- [x] T056 Run the full quality gate: `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy src`, `uv run pytest -q`, `uv run pytest -m slow tests/determinism/test_viewer_export.py -q`, and the quickstart scenarios in `specs/002-webgl-library-viewer/quickstart.md`; confirm the default suite stays offline, browser-free, and within 10% of its previous runtime.
- [x] T057 Security and performance verification: confirm loopback-only binding, traversal/NUL/backslash rejection, no directory listings, CSP on every response, and no external runtime URLs; measure warm-cache gallery readiness (<10 s), filter/search feedback (<100 ms for 100 creatures), and thumbnail concurrency (3 in flight) and record the results.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**.
- **User Story 1 (Phase 3, P1)**: Depends on Foundational — MVP.
- **User Story 2 (Phase 4, P2)**: Depends on Foundational; integrates with US1's
  `index.html`, `styles.css`, `app.js`, and `router.js` (US1 must ship those files
  first).
- **User Story 3 (Phase 5, P3)**: Depends on Foundational (cache + server + serve
  CLI); can proceed in parallel with US1/US2 once the checkpoint is reached.
- **User Story 4 (Phase 6, P4)**: Depends on Foundational (catalog + static assets +
  export plan); the full-bundle integration/determinism tests additionally need the
  frontend files from US1/US2.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No story dependencies; first shippable increment.
- **US2 (P2)**: Needs US1's shell and router; independent inspection behaviour after
  that.
- **US3 (P3)**: Independent of US1/US2 beyond the shared server; testable with
  `curl` and the gallery shell.
- **US4 (P4)**: Independent export logic; the end-to-end static-site test needs US1
  and US2 frontend assets.

### Within Each User Story

- Tests (where present) before or alongside implementation; they must fail first.
- `catalog.py`/`cache.py` primitives before server routes.
- Server routes before CLI wiring.
- CLI wiring before integration tests.
- Frontend modules (`catalog.js`, `router.js`, `stage.js`, `clips.js`,
  `inspector.js`) before `app.js` wiring.
- Export plan before export writer before export CLI.

### Parallel Opportunities

- All Setup tasks marked `[P]` can run together.
- Foundational tasks T006–T014 touch different modules; T010/T011 share
  `cache.py`, T012–T014 share `server.py`, so only run those pairs sequentially.
- All US1 tests marked `[P]` can run together; `catalog.js` and `router.js` (T022,
  T023) can be written in parallel, then `app.js` (T024) and `thumbnails.js` (T025)
  in parallel, then their integration (T026).
- US2 `stage.js`, `clips.js`, and `inspector.js` (T028–T030) can be written in
  parallel; `app.js` wiring (T032) follows.
- US3 tests (T034–T037) can be written in parallel once the cache/server/CLI
  interfaces exist; T038 implementation touches CLI + server.
- US4 export plan (T043) and all US4 tests/offline/CI (T039–T042, T046) can proceed
  in parallel; export writer (T044) follows the plan; CLI dispatch (T045) follows the
  writer.
- Polish documentation tasks T048–T053 are independent and parallelizable.

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task: "Unit tests for catalog ordering/digests/warnings in tests/unit/test_viewer_catalog.py"
Task: "Contract tests for catalog schema/coverage/manifest agreement in tests/contract/test_viewer_catalog.py"

# Frontend modules (parallel):
Task: "Create static/lib/catalog.js"
Task: "Create static/lib/router.js"

# Then gallery render + thumbnails (parallel):
Task: "Create static/app.js gallery bootstrap"
Task: "Create static/lib/thumbnails.js"
```

## Parallel Example: User Story 2

```bash
Task: "Create static/lib/stage.js"
Task: "Create static/lib/clips.js"
Task: "Create static/lib/inspector.js"

# After those exist:
Task: "Wire stage, clips, inspector, and deep links in static/app.js"
```

## Parallel Example: User Story 4

```bash
Task: "Add bundle schema contract test in tests/contract/test_viewer_catalog.py"
Task: "Add export CLI integration tests in tests/integration/test_view_cli.py"
Task: "Add offline contract test in tests/contract/test_viewer_offline.py"
Task: "Implement pure export plan in src/beastforge/viewer/export.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (catalog, cache, loopback server, serve CLI).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run `uv run beastforge view` and the US1 quickstart
   checks; the gallery, filters, search, empty state, warnings, and thumbnails must
   all work.
5. Deploy/demo the local viewer if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → gallery MVP → validate independently.
3. US2 → stage, clips, events, inspector → validate against the manifest.
4. US3 → one-command local workflow, cache lifecycle, no tracked writes.
5. US4 → deterministic static export + Pages publish.
6. Polish → docs, changelog, version, browser smoke, full gate.

### Notes

- `[P]` tasks touch different files and have no dependency on incomplete tasks.
- Every story ends at a checkpoint that can be validated on its own.
- Commit after each task or logical group; never commit generated `.glb`/manifest
  binaries or `site/`.
- The viewer is read-only: it must never re-derive gameplay facts, regenerate
  geometry, or apply `--set` overrides.
