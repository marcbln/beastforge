# Implementation Plan: Procedural 3D Creature Generator (beastforge v1)

**Branch**: `001-procedural-creature-generator` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-procedural-creature-generator/spec.md`

## Summary

beastforge is an offline, deterministic CLI that turns declarative YAML recipes
into an animated, skinned 3D creature package: one glTF 2.0 binary (`.glb`) with
embedded texforge-rendered textures, plus one sidecar `*.manifest.json` carrying
the gameplay contract (clips, event timing, sockets, volumes, phases, bounds,
provenance). A recipe declares its **skeleton first**, then surfaces bound to
those bones at construction time, then materials, clips, and combat hooks. The
primary users are AI coding agents: they discover creatures from an in-repo
library, render with `--set` overrides, validate and self-correct through a
stable `--json` finding list, and accept visual regressions only explicitly.

Technical approach is fixed by the accepted ADRs
([261114-1](../../_ai/technical_decisions/ADR__261114-1__gltf-manifest-contract.md),
[261114-2](../../_ai/technical_decisions/ADR__261114-2__offline-deterministic-generator.md),
[261114-3](../../_ai/technical_decisions/ADR__261114-3__construction-bound-skinning.md),
[261114-4](../../_ai/technical_decisions/ADR__261114-4__baked-joint-clips-and-event-frames.md)):
Python 3.12+/`uv`, pydantic recipe schema, numpy float64 geometry, a custom
byte-stable GLB writer, construction-bound skin weights, 60 Hz baked joint
clips, and a single validation gate. This plan resolves the remaining engineering
choices — geometry stack, texture integration, manifest/report schemas, bake
rate, showroom renderer, output safety, test layers, budgets — in
[research.md](./research.md), and defines the entities, contracts, and
validation scenarios in [data-model.md](./data-model.md),
[contracts/](./contracts/), and [quickstart.md](./quickstart.md).

## Technical Context

All unknowns are resolved against the ADRs, the spec clarifications, and
`_ai/conventions.md`; each is settled in [research.md](./research.md). **No
NEEDS CLARIFICATION remains.**

**Language/Version**: Python 3.12+ (ADR 261114-2). Managed with `uv`; single
installable package with a `beastforge` console script.

**Primary Dependencies**: `numpy` (float64 mesh/clip math), `pydantic` v2
(recipe, manifest, finding models), `PyYAML` (`safe_load` only), `typer` +
`rich` (CLI, help, theme), `Pillow` (showroom PNG encode), `texforge` (texture
rendering, uv path source). Dev: `pytest`, `ruff`, `mypy`, `jsonschema`,
`trimesh` (independent consumer).

**Storage**: Filesystem only. Recipes at `library/<category>/<name>.yaml`;
generated packages at `dist/<name>/<name>.glb` + `.manifest.json` (caller
overridable with `-o`); showroom references at
`showroom/reference/<creature>/`. No database, no cache index (the library is
scanned on demand).

**Testing**: `pytest` in layers — unit, contract (JSON Schema), integration,
determinism (incl. a `slow` 100-run marker), defect corpus (one fixture per
finding code), byte-exact GLB/manifest goldens, showroom structural summaries,
and consumer imports (`trimesh`; optional `@gltf-transform/cli` via Node).
See [research.md](./research.md) D14.

**Target Platform**: Developer machines (Linux/macOS/Windows), fully local and
offline. No GPU, no display server, no network at runtime (SC-001).

**Project Type**: Single shippable CLI package plus an in-repo creature library
and an agent `SKILL.md` deliverable (texforge-shaped).

**Performance Goals**: Catalog and `params` under 2 s; one full generation
(geometry + clips + textures + gate + atomic write) under 10 s on a developer
laptop; showroom 5 frames × 512² per creature under 5 s; peak memory under
512 MB (SC-006, research D15).

**Constraints**: Byte-identical `.glb` + manifest for the same recipe, resolved
parameters, and tool version across machines, directories, locales, clocks, and
processes; only seeded randomness; recipes are inert data; no runtime
procedural animation in the asset; weights 1–2 influences inside the glTF
4-influence limit; metres, Y-up, −Z forward; no GPU/EGL dependency.

**Scale/Scope**: v1 = 3+ starter creatures (boss, quadruped, swarm), 3 surface
kinds in one surface mode (`sweep`), 6 clip generators, 5 reserved core clips,
5 work commands + `version`/`about`, budgets of 20k vertices / 64 bones / 60k
triangles / ≤600 ticks per clip. Metaball, auto-skinning, IK, runtime
generation, Blender, and consumer packaging (inline single-file build) are out
of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> **Finding (surfaced, not silently passed):** `.specify/memory/constitution.md`
> is still the unfilled `[PRINCIPLE_*]` template — no project constitution has
> been ratified. The gate below is therefore evaluated against the repository's
> **authoritative resolved conventions** (`_ai/conventions.md`, generated by
> `ruleman export`) and the four accepted ADRs, which is the effective law for
> this repo today. Filling in `constitution.md` is recommended but does not
> block this feature; no decision conflicts with any principle in the example
> template (Library-First, CLI Interface, Test-First, Integration Testing,
> Observability, Versioning, Simplicity).

| Gate (source) | Requirement | Status | How the design satisfies it |
|---------------|-------------|--------|-----------------------------|
| `cli:command-grammar` | One consistent grammar, kebab-case flags | ✅ PASS | Verb-first `beastforge list/params/render/validate/showroom` + `version/about`; canonical tree in `contracts/cli.md` |
| `cli:flag-vocabulary` | Canonical `--json/--quiet/--verbose/--no-color/--no-interaction/--dry-run`, `-h/-V` | ✅ PASS | Defined once in `contracts/cli.md`; global flags accepted before and after subcommands |
| `cli:streams` | Results→stdout, diagnostics→stderr; `--json` undecorated | ✅ PASS | Paths/catalog/params/findings → stdout; progress/warnings/errors → stderr (D9) |
| `cli:exit-codes` | 0 success, 2 usage, 1 general; documented extras | ✅ PASS | Documented set `0/1/2/3/4/128+n`; agents branch on 2 vs 3 vs 4 (D9) |
| `cli:version` + `cli:about` | Non-interactive `version` and `about`, one version source | ✅ PASS | `version`/`about` commands; `beastforge.__version__` feeds `--version`, manifest, report |
| `cli:errors` | What failed, why, next step; stable code; traces only behind debug | ✅ PASS | Closed error codes, field-path location, expected/actual/remedy (`error.schema.json`); FR-011 |
| `cli:help` | Help from the same parser definitions | ✅ PASS | Typer definitions generate `--help`; no hand-written usage strings |
| `cli:output` / `presentation` / `accessibility` | Stable `--json`, plain fallback, color not sole signal | ✅ PASS | JSON Schemas published; `NO_COLOR`/non-TTY plain path; text + symbol + position in findings |
| `cli:interactivity` / `feedback` | Prompt only on a TTY; idempotent; no partial writes | ✅ PASS | FR-012 atomic staging; `--force` is the only overwrite path; no prompts in v1 |
| `cli:configuration` | Flag > env > project > user > default; XDG | ✅ PASS | Documented in `contracts/cli.md`; `BEASTFORGE_*` env + XDG config (D9) |
| `cli:cheatsheet` | `docs/cheatsheet-cli.md` task table, kept in sync | ✅ PASS | Deliverable in Project Structure; CLI tree in `contracts/cli.md` |
| `docs:minimum-set` / `readme` / `architecture` / `development` / `api` / `adr` / `changelog` / `style` | README + `/docs` set + CHANGELOG + ADRs, linked and current | ✅ PASS | All listed in Project Structure; `/docs/api.md` hosts the `--json` contract |
| `docs:code-docstrings` / `code-comments` | Public contracts documented; comments explain why | ✅ PASS | Module/function docstrings required by the plan; finding/error contracts documented |
| `architecture:separation` / `solid` | Core logic separate from CLI/IO; modular | ✅ PASS | Pure build core (`rig/geometry/anim/export/validation/showroom`) vs adapters (`cli/`, `render.py`, `texture/`, `library.py`, `config.py`) |
| `testing:unit` + ADRs 261114-2/3 | Features have tests; determinism and skin invariants proven | ✅ PASS | Layered suite in D14 incl. defect corpus, 100-run determinism, byte goldens, consumer imports |
| `code:robustness` | Edge cases, error handling, assertions | ✅ PASS | Gate-first pipeline, atomic writes, explicit unsupported-mode/version errors, budget ceilings |
| `maintenance:compatibility` | Backwards compatibility or migration path | ✅ PASS | Manifest major-strict/minor-tolerant; finding codes additive; recipe `tested_with` bump rule |
| `release:semver` / `git-tags` | SemVer + annotated `vX.Y.Z` tags, one version source | ✅ PASS | `__version__` single source; release process documented in `docs/development.md` |
| ADR 261114-1 | glTF 2.0 + sidecar manifest, no bespoke format | ✅ PASS | `.glb` + manifest pair only; `contracts/schema/manifest.schema.json` |
| ADR 261114-2 | Offline deterministic CLI, texforge-shaped, validation gate | ✅ PASS | D1/D3/D4/D9/D10; `sha256` in the report; exits 0/1/2/3/4 |
| ADR 261114-3 | Construction-bound skinning, 1–2 influences, sweep UVs, rigid parts | ✅ PASS | D2, §6 of the recipe grammar, skin findings in §16 of data-model |
| ADR 261114-4 | Baked 60 Hz clips, manifest events authoritative, `ticks@60` | ✅ PASS | D7, clip grammar, manifest `events[]` + playback warning |

**Verdict**: **PASS** — no unjustified violations; no entries required in
Complexity Tracking. The constitution-template gap is a repo-hygiene follow-up,
not a design violation.

### Post-design re-check (after Phase 0 research + Phase 1 design)

Re-ran the gate table against the concrete artifacts now written —
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/cli.md](./contracts/cli.md),
[contracts/recipe-grammar.md](./contracts/recipe-grammar.md),
[contracts/json-schemas.md](./contracts/json-schemas.md),
[contracts/schema/](./contracts/schema/), and [quickstart.md](./quickstart.md):

- `cli:command-grammar` / `cli:flag-vocabulary` — the tree is now normative in
  `contracts/cli.md`; every flag appears once and `--dry-run`/`--force`
  interactions are stated. ✅ still passes.
- `cli:exit-codes` / `cli:errors` — the `0/1/2/3/4` set and the error schema are
  now normative, and the finding vocabulary is closed in data-model §16. ✅
- `docs:api` / contract tests — eight JSON Schemas are published and
  meta-validated; `tests/contract/` is obliged to validate live payloads. ✅
- `architecture:separation` — the structure tree keeps the pure build core free
  of IO imports; texforge is isolated in one adapter. ✅
- FR-008/FR-009 determinism — seed derivation, canonical JSON, fixed GLB
  emission order, and staged atomic writes are specified (D4/D10) and exercised
  in quickstart §4. ✅
- FR-014 skeleton-first / FR-020 sweep-only / FR-025 required hooks — encoded in
  the recipe grammar and the gate, with a rejection summary table. ✅
- FR-029/FR-032 manifest versioning — `MAJOR.MINOR`, major-strict rules, and the
  compatibility fixtures are specified (D8, json-schemas.md). ✅

No new violations introduced by the design; **Constitution gate remains PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/001-procedural-creature-generator/
├── plan.md                  # This file
├── spec.md                  # Feature specification
├── research.md              # Phase 0: resolved engineering decisions (D1–D16)
├── data-model.md            # Phase 1: entities, invariants, state machine
├── quickstart.md            # Phase 1: runnable validation scenarios
├── contracts/
│   ├── cli.md               # Command tree, flags, streams, exit codes
│   ├── recipe-grammar.md    # Skeleton-first authoring contract
│   ├── json-schemas.md      # Machine-surface index + versioning rules
│   └── schema/
│       ├── manifest.schema.json
│       ├── render.result.schema.json
│       ├── validate.result.schema.json
│       ├── library.list.schema.json
│       ├── params.schema.json
│       ├── showroom.result.schema.json
│       ├── error.schema.json
│       └── recipe.schema.json
├── checklists/
│   └── requirements.md      # Spec-quality gate (already passing)
└── tasks.md                 # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/beastforge/
├── __init__.py              # __version__ (single source of truth)
├── __main__.py              # `python -m beastforge`
├── cli/
│   ├── app.py               # typer app + global flags + theme
│   ├── library.py           # list (scan, filters)
│   ├── params.py            # params (declared knobs)
│   ├── render.py            # render (generate, --set, --force, --dry-run)
│   ├── validate.py          # validate (gate, single or whole library)
│   ├── showroom.py          # showroom (compare / --accept)
│   └── meta_cmds.py         # version / about
├── model/                   # pydantic v2 domain models (no IO)
│   ├── recipe.py            # Meta, Param, Skeleton, Surface, Clip, ...
│   ├── manifest.py          # Manifest + schemaVersion rules
│   ├── report.py            # GenerationReport, ShowroomReport
│   ├── findings.py          # ValidationFinding + closed code vocabulary
│   └── errors.py            # BeastforgeError hierarchy, stable codes
├── rig/
│   ├── skeleton.py          # rest/world transforms, chains, inverse bind matrices
│   └── weights.py           # joint-band smoothstep blend, normalization
├── geometry/
│   ├── mesh.py              # Mesh buffers, AABB, winding helpers
│   ├── sweep.py             # swept tube + UVs + silhouette modifiers
│   ├── shell.py             # torso ring shell bound along spine
│   └── rigid.py             # rigid part emitter (weight 1.0)
├── anim/
│   ├── registry.py          # closed generator registry (single source)
│   ├── bake.py              # 60 Hz sampling, ticks@60 conversion, loop closing key
│   └── generators/          # breathe, gait, hover_bob, recoil,
│                            # telegraph_attack, death_collapse
├── texture/
│   └── texforge_adapter.py  # in-process texforge call, PNG bytes + sha256
├── export/
│   ├── gltf.py              # deterministic glTF 2.0 binary writer
│   └── manifest.py          # manifest assembly + canonical JSON
├── validation/
│   ├── gate.py              # single entry point, ordered findings
│   ├── skeleton.py          # root/cycle/duplicate/degenerate/inverted
│   ├── skin.py              # weight sum, influences, bind==rest, winding
│   ├── clips.py             # core clips, durations, ticks, events
│   ├── hooks.py             # volumes, sockets, phases
│   ├── materials.py         # texforge resolution + rendered PNG checks
│   ├── budgets.py           # measured vs declared ceilings
│   └── determinism.py       # hazard scan, manifest referential integrity
├── showroom/
│   ├── raster.py            # numpy z-buffer software renderer
│   ├── compare.py           # per-pixel threshold + changed-pixel ratio
│   ├── structural.py        # joint/clip/skin/bounds summary
│   └── reference.py         # reference load/store, explicit accept
├── pipeline.py              # pure orchestration of the generation state machine
├── render.py                # IO adapter: staging dir, atomic commit, report
├── library.py               # scan library/, name resolution (path wins)
├── params.py                # declared params + --set overrides + suggestions
├── rng.py                   # sha256-derived deterministic streams (ADR-2)
└── config.py                # flag > env > project > user(XDG) > default

library/                     # the catalog IS this directory
├── boss/ash-crowned-tyrant.yaml        # 3 phases, large rig
├── quadruped/ridge-stalker.yaml        # gait, 4 limb chains
├── swarm/chitter-mite.yaml             # hover-bob, small rig
└── other/                              # optional extras as the grammar matures

showroom/
└── reference/<creature>/               # approved frames + structural.json
    ├── frames/<view>__<pose>.png
    └── structural.json

tests/
├── unit/                    # sweep math, weights, ticks, seed, GLB layout
├── contract/                # every --json payload vs contracts/schema/
├── integration/             # list→params→render, overwrite, interrupt, concurrency
├── determinism/             # two-cwd hash equality + slow 100-run loop
├── defect_corpus/           # one fixture per finding code
├── golden/                  # committed .glb/manifest sha256 + structural summaries
├── consumers/               # trimesh import, optional @gltf-transform/cli validate
└── fixtures/                # recipes, consumer manifest fixtures, expected JSON

docs/
├── architecture.md          # pure core vs adapters, Mermaid diagram
├── development.md           # setup, test/lint/typecheck/release commands
├── api.md                   # the --json surfaces + manifest consumer guide
├── recipes.md               # authoring guide (skeleton-first, modifiers, clips)
├── showroom.md              # cameras, lighting, tolerance, accept workflow
├── cheatsheet-cli.md        # task-oriented command table
└── environment-variables.md # BEASTFORGE_* + NO_COLOR

SKILL.md                     # agent guide: discover/render/remix/validate/contribute
pyproject.toml               # package, entry point, ruff/mypy/pytest config, uv sources
uv.lock
README.md
CHANGELOG.md
```

**Structure Decision**: A single Python CLI package with a hard boundary between
the **pure build core** (`model`, `rig`, `geometry`, `anim`, `export`,
`validation`, `showroom/raster+compare+structural`, `pipeline`, `rng`) and the
**adapters** (`cli/`, `render.py` staging/commit, `texture/texforge_adapter.py`,
`library.py`, `config.py`). This satisfies `architecture:separation`, lets the
core be golden-tested without a subprocess, and keeps every non-deterministic
input (filesystem, environment, texforge call) on the adapter side of the line.
The in-repo `library/` and `showroom/reference/` are first-class artifacts
co-equal with the binary, mirroring texforge's thesis; the manifest is the
consumer contract, and the CLI stays an agent-first generator, not a runtime
library.

The design-handoff open questions are closed as follows: geometry stack →
custom numpy (D2); texture binding → embedded PNGs + manifest hashes (D5); units
and orientation → metres / Y-up / −Z with a scale hint (D8); hit volumes →
recipe-authored, never derived (D11); showroom strategy → perceptual frames +
structural summaries (D12); first-consumer packaging → deferred to a follow-up
feature (D16).

## Complexity Tracking

> No Constitution Check violations — nothing to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
