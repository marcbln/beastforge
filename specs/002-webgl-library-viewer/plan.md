# Implementation Plan: WebGL Library Viewer

**Branch**: `002-webgl-library-viewer` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-webgl-library-viewer/spec.md`;
design handoff `_ai/backlog/active/261115_0338__DESIGN_HANDOFF__webgl-library-viewer.md`;
ADRs 261115-5 and 261115-6.

## Summary

Add a browser-based **library browser** to beastforge: a searchable, category-
filtered gallery of live 3D thumbnails, a full orbit stage with clip playback
and manifest-derived event marks, and an inspector for manifest facts. The same
frontend is served by two delivery modes — `beastforge view` (loopback stdlib
HTTP server, lazy generation into a disposable cache) and `beastforge view
--export DIR` (byte-stable static bundle published to GitHub Pages by CI).

The frontend is hand-written HTML/CSS/ES modules with **no build step**. `three`,
`GLTFLoader`, `BufferGeometryUtils`, and `OrbitControls` are pinned and vendored
as package data, so the viewer makes zero external requests at runtime. Both
modes consume one canonical `catalog.json` v1 with relative, content-addressed
URLs. The viewer is read-only: it never re-derives gameplay facts, regenerates
geometry, or applies `--set` overrides; the existing sidecar manifest stays the
single source of creature facts.

The engineering choices the spec and ADRs leave open — catalog shape and
versioning, asset addressing, cache/export determinism, thumbnail concurrency,
server security, CI topology, and test layering — are resolved in
[research.md](./research.md), modelled in [data-model.md](./data-model.md),
fixed by the contracts in [contracts/](./contracts/), and proven by the
scenarios in [quickstart.md](./quickstart.md).

## Technical Context

All unknowns are resolved against the spec, the two accepted viewer ADRs, the
existing generator ADRs, and `_ai/conventions.md`. **No NEEDS CLARIFICATION
remains.**

**Language/Version**: Python 3.12+ (repo target; `uv` managed) for the server,
catalog, cache, and export. Frontend is ES2022 modules executed directly by the
browser; no transpiler, bundler, Node runtime, or npm install at build or
runtime.

**Primary Dependencies**: Existing runtime deps (`numpy`, `pydantic`, `PyYAML`,
`typer`, `rich`, `Pillow`, `texforge`) plus Python stdlib `http.server`,
`threading`, `webbrowser`, `importlib.resources`, and `hashlib`. Frontend:
vendored `three` (module build), `GLTFLoader`, `BufferGeometryUtils`, and
`OrbitControls`, pinned under `src/beastforge/viewer/third_party/three/` with a
`VERSION` and `LICENSE` note. Dev-only optional group: `playwright` for the
opt-in browser smoke check.

**Storage**: Filesystem only. Recipes at `library/<category>/<name>.yaml`;
generated packages at `dist/` or a caller path; local viewer cache at
`$XDG_CACHE_HOME/beastforge/viewer` (override `BEASTFORGE_CACHE_DIR`,
`--cache-dir`, or config `cache_dir`) — never a source of truth and never inside
tracked content by default; static export at a caller-supplied directory. No
database, no index file, no committed binaries.

**Testing**: `pytest` layers — unit (catalog, cache key/lifecycle), contract
(catalog schema, coverage/manifest agreement, offline scan), integration
(`view --export`, HTTP routes, traversal/stale rejection, on-demand generation),
determinism (two exports byte-identical, `slow` marker), and an opt-in
Playwright browser smoke check (`viewer` marker plus
`BEASTFORGE_VIEWER_SMOKE=1`). Default `pytest` stays offline, browser-free, and
fast; the browser check never runs unless explicitly enabled.

**Target Platform**: Desktop browsers with WebGL on Linux/macOS/Windows served
from `127.0.0.1` or a static host (GitHub Pages). No GPU/display dependency for
the Python test suite. Mobile-first layout is out of scope.

**Project Type**: Single Python package (`src/beastforge/`) augmented with a
buildless static frontend shipped as package data, plus an in-repo creature
library and a CI Pages workflow.

**Performance Goals**: Warm-cache `beastforge view` to interactive gallery under
10 s (SC-006), first thumbnail frame under 1 s after its asset is ready, filter
and search feedback under 100 ms for 100 creatures (SC-001), stage clip switch
under 200 ms, and generation only for creatures whose cards are previewed or
opened (edge case "very large library"). Export of the current 5-creature
library completes in the same order of magnitude as a full `render` sweep.

**Constraints**: Zero runtime requests to external hosts (FR-022, SC-007).
No generated binaries committed (FR-019, SC-008). Byte-identical catalog and
export for identical recipes, vendored assets, and tool version (FR-016,
SC-004). Local server bound to loopback only (FR-014). No tracked-file
modification from local mode (FR-013). Catalog and inspector never contradict
the manifest and tolerate additive manifest fields (FR-009, FR-018). Default
test suite remains offline, browser-free, and within 10% of its current runtime
(FR-021, SC-009).

**Scale/Scope**: Current library of 5 recipes; designed for roughly 100
creatures. One local user, no auth. 1 new CLI command (`view`) with two modes,
1 catalog contract, 1 static bundle format, 1 HTTP contract, 1 opt-in browser
test. Live parameter editing, in-browser regeneration, recipe mutation, skeleton
overlays, A/B comparison, showroom replacement, WebGPU, and mobile-first layout
remain out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> **Finding (surfaced, not silently passed):** `.specify/memory/constitution.md`
> is still the unfilled `[PRINCIPLE_*]` template — no project constitution has
> been ratified. As with feature 001, this gate is evaluated against the
> repository's authoritative resolved conventions (`_ai/conventions.md`,
> generated by `ruleman export`) and the accepted ADRs, which are the effective
> law for this repo today. Filling `constitution.md` remains a repo-hygiene
> follow-up and does not block this feature; no design choice conflicts with the
> example principles (Library-First, CLI Interface, Test-First, Integration
> Testing, Observability, Versioning, Simplicity).

| Gate (source) | Requirement | Status | How the design satisfies it |
|---------------|-------------|--------|-----------------------------|
| `cli:command-grammar` | One consistent grammar, kebab-case flags | ✅ PASS | New verb `beastforge view`; flags `--export`, `--port`, `--cache-dir`, `--no-browser`, `--force`; canonical tree in `contracts/cli.md` |
| `cli:flag-vocabulary` | Canonical `--json/--quiet/--verbose/--no-color/--no-interaction/--dry-run`, `-h/-V` | ✅ PASS | Reuses the existing global flags; `view` adds only mode-specific flags; global flags accepted before and after the verb |
| `cli:streams` | Results→stdout, diagnostics→stderr; `--json` undecorated | ✅ PASS | Serve URL and export report→stdout; generation progress/warnings/errors→stderr; `--json` emits one canonical document |
| `cli:exit-codes` | 0 success, 2 usage, 1 general; documented extras | ✅ PASS | Reuses `0/1/2/3/4/128+n`; export gate failure exits 3, unknown library/creature 4, Ctrl-C 130 |
| `cli:errors` | What failed, why, next step; stable code; traces only behind debug | ✅ PASS | Reuses the published error schema/codes (`stale-asset`, `export-exists`, `viewer-unavailable`, `webgl-unavailable` surfaced client-side); HTTP errors carry the same shape |
| `cli:help` / `cli:version` / `cli:about` | Help from parser; version/about stay non-interactive | ✅ PASS | Typer definitions generate help; `view` does not alter `version`/`about`; one version source |
| `cli:configuration` | Flag > env > project > user > default; XDG | ✅ PASS | Cache resolution `--cache-dir` > `BEASTFORGE_CACHE_DIR` > `cache_dir` config > `$XDG_CACHE_HOME/beastforge/viewer`; documented in `docs/environment-variables.md` |
| `cli:interactivity` / `feedback` | No blocking prompts; acknowledge long work; idempotent | ✅ PASS | No prompts; non-empty export refuses with an actionable error unless `--force`; generation progress on stderr; cache reuse idempotent |
| `cli:cheatsheet` | Task-oriented cheat sheet kept in sync | ✅ PASS | New `## view` section and "Most useful" rows in `docs/cheatsheet-cli.md`, verified against `view --help` |
| `cli:presentation` / `accessibility` | Shared visual language; color not sole signal | ✅ PASS | CLI reuses Rich/typer output; frontend uses text + symbols + position for active clip/event markers and honors reduced motion |
| `docs:minimum-set` / `readme` / `architecture` / `development` / `api` / `adr` / `changelog` / `style` | README + `/docs` set + CHANGELOG + ADRs, linked and current | ✅ PASS | README quick start, `docs/architecture.md`, `docs/api.md`, `docs/development.md`, `docs/environment-variables.md`, `docs/cheatsheet-cli.md`, `CHANGELOG.md` updated in the same change |
| `docs:code-docstrings` / `code-comments` / `code-examples` | Public contracts documented; comments explain why | ✅ PASS | Python modules and public classes get docstrings; frontend modules get header comments stating their contract; quickstart examples are runnable |
| `architecture:separation` / `solid` | Core logic separate from UI/infrastructure; modular | ✅ PASS | `viewer/catalog.py` pure derivation; `viewer/cache.py`, `viewer/export.py`, `viewer/server.py` are adapters; `cli/view.py` is a thin boundary; frontend modules split by responsibility |
| `testing:unit` + `code:robustness` | Features tested; edge cases/errors explicit | ✅ PASS | Unit + contract + integration + determinism layers; explicit empty, stale, traversal, WebGL-unavailable, and generation-failure paths |
| `maintenance:compatibility` | Backwards compatibility or migration path | ✅ PASS | Catalog `MAJOR.MINOR` with major-strict/minor-tolerant consumption; additive fields only within `1.x`; existing `list`/`render`/manifest contracts untouched |
| `release:semver` / `git-tags` | SemVer, one version source, annotated tags | ✅ PASS | `beastforge.__version__` feeds catalog `toolVersion`, bundle metadata, CLI, and manifest; feature is a minor release |
| ADR 261115-5 | Buildless, vendored three.js behind one catalog contract | ✅ PASS | No Node/npm/build step; pinned vendored files under package data; same `catalog.json` for both modes; read-only viewer |
| ADR 261115-6 | Localhost-first with deterministic static export as publish path | ✅ PASS | Loopback stdlib server + lazy cache; `--export` writes a self-contained bundle; CI publishes Pages artifacts, never commits GLBs |
| ADR 261114-1 / 261114-2 | Manifest authoritative; offline deterministic generator | ✅ PASS | Viewer reads manifest directly; catalog may surface only facts it can prove; content-addressed files; canonical JSON and sorted paths |

**Verdict**: **PASS** — no unjustified violations; no entries required in
Complexity Tracking. The constitution-template gap is a documented repo-hygiene
follow-up, not a design violation.

### Post-design re-check (after Phase 0 research + Phase 1 design)

Re-ran the gate against the concrete artifacts now written —
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/catalog.md](./contracts/catalog.md),
[contracts/catalog.schema.json](./contracts/catalog.schema.json),
[contracts/bundle.schema.json](./contracts/bundle.schema.json),
[contracts/viewer-http.md](./contracts/viewer-http.md),
[contracts/cli.md](./contracts/cli.md), and [quickstart.md](./quickstart.md):

- **CLI gates** — the `view` grammar, flag precedence, streams, JSON shapes, and
  exit codes are now normative in `contracts/cli.md`; `--export`/`--dry-run`/
  `--force` interactions are stated. ✅ still passes.
- **Docs gates** — every new surface (catalog, bundle, HTTP routes, cache env
  var, cheat-sheet section, quickstart) has a named owner document in Project
  Structure. ✅
- **Architecture gates** — the pure/adaptive split is explicit: catalog
  derivation and bundle planning are pure functions; cache, render, server, and
  filesystem writes are isolated adapters. ✅
- **Determinism gates** — content-addressed asset paths, canonical JSON, sorted
  catalog entries and bundle file lists, fixed manifest `recipePath` labels, and
  no timestamps/hostnames are all specified. ✅
- **ADR gates** — no Node toolchain, no CDN, no committed binaries, loopback-only
  local mode, same catalog in both modes. ✅

**Post-design verdict**: **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/002-webgl-library-viewer/
├── plan.md                         # This file
├── spec.md                         # Feature specification
├── research.md                     # Phase 0 decisions (D1–D14)
├── data-model.md                   # Phase 1 entities, invariants, state
├── quickstart.md                   # Phase 1 runnable validation guide
├── checklists/
│   └── requirements.md             # Spec quality gate (already present)
└── contracts/
    ├── cli.md                      # `beastforge view` grammar, flags, JSON, exits
    ├── catalog.md                  # Catalog semantics, coverage, versioning
    ├── catalog.schema.json         # Catalog document JSON Schema
    ├── bundle.schema.json          # Static export file manifest schema
    └── viewer-http.md              # Local server routes, headers, errors
```

### Source Code (repository root)

```text
src/beastforge/
├── viewer/
│   ├── __init__.py
│   ├── catalog.py                  # Pure: library scan -> CatalogDocument
│   ├── cache.py                    # Local asset cache keyed by recipe SHA-256
│   ├── export.py                   # Pure plan + filesystem writer for static bundle
│   ├── server.py                   # Loopback ThreadingHTTPServer + routes
│   ├── assets.py                   # importlib.resources locator for static files
│   ├── static/                     # Buildless frontend (package data)
│   │   ├── index.html              # Import map, CSP, app shell
│   │   ├── styles.css
│   │   ├── app.js                  # Bootstrap, routing, filters, wiring
│   │   └── lib/
│   │       ├── catalog.js          # Tolerant catalog fetch/parse
│   │       ├── router.js           # Hash + query deep-link state
│   │       ├── thumbnails.js       # IntersectionObserver queue + shared blit
│   │       ├── stage.js            # Shared three renderer, orbit, framing
│   │       ├── clips.js            # Mixer, clip switching, event timeline
│   │       └── inspector.js        # Manifest / Clips / Events tabs
│   └── third_party/
│       └── three/                  # Pinned vendored runtime (NOT `vendor/`)
│           ├── VERSION             # Exact upstream version + retrieval note
│           ├── LICENSE             # three.js MIT license text
│           ├── three.module.js
│           └── addons/
│               ├── GLTFLoader.js
│               ├── BufferGeometryUtils.js
│               └── OrbitControls.js
├── cli/
│   └── view.py                     # Thin Typer boundary for `beastforge view`
├── library.py                      # + non-serialized document/digest helper
├── config.py                       # + `cache_dir` setting resolution

tests/
├── unit/
│   ├── test_viewer_catalog.py      # Ordering, digests, warnings, relative URLs
│   └── test_viewer_cache.py        # Keying, reuse, invalidation, locks, cleanup
├── contract/
│   ├── test_viewer_catalog.py      # Schema + coverage + manifest agreement
│   └── test_viewer_offline.py     # No external URLs in runtime assets
├── integration/
│   ├── test_view_cli.py            # `view --export`, force/dry-run/json/exits
│   └── test_view_server.py         # Routes, traversal, stale, on-demand, shutdown
├── determinism/
│   └── test_viewer_export.py       # Two exports byte-identical (`slow`)
└── viewer/
    └── test_browser_smoke.py       # Opt-in Playwright smoke (`viewer`)

.github/
└── workflows/
    └── pages.yml                   # Build + validate + export + deploy Pages

docs/
├── api.md                          # + viewer HTTP/catalog/export surfaces
├── architecture.md                 # + viewer component and data flow
├── cheatsheet-cli.md               # + `## view`
├── development.md                  # + viewer/export/smoke commands
└── environment-variables.md        # + `BEASTFORGE_CACHE_DIR`

README.md                           # + `beastforge view` quick start
SKILL.md                            # + view/export discovery for agents
CHANGELOG.md                        # + Unreleased/Added entry
specs/README.md                     # + 002 index row
.gitignore                          # + `site/` (CI export target)
```

**Structure Decision**: Feature 002 extends the existing single-package layout.
The viewer is a subpackage (`src/beastforge/viewer/`) so its static assets ship
as package data with the wheel and can be located through `importlib.resources`
in both editable and installed installs. The vendored three.js directory is
named `third_party/`, not `vendor/`, because the repository `.gitignore`
ignores every `vendor/` directory and vendored runtime files must be committed.
The CLI stays a thin adapter in `src/beastforge/cli/view.py`, matching the
existing command pattern. Tests follow the existing `unit/contract/integration/
determinism` layering plus a new `viewer/` folder that is never collected into
the default run.

## Complexity Tracking

No constitution or convention violations require justification. The one
structural addition — a browser frontend inside the Python package — is required
by ADR 261115-5 (buildless, vendored as package data) and is not a second
toolchain: there is no Node project, no lockfile, and no build artifact.
