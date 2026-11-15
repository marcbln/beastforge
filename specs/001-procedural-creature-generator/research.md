# Phase 0 Research: Procedural 3D Creature Generator (beastforge v1)

**Feature**: `001-procedural-creature-generator` | **Date**: 2026-11-14
**Inputs**: [spec.md](./spec.md), ADRs 261114-1/2/3/4, [_ai/conventions.md](../../_ai/conventions.md)

The four accepted ADRs fix the asset format, the offline-deterministic CLI
shape, the construction-bound skinning model, and the baked-clip model. Those are
treated as **constraints, not unknowns**. This file resolves the engineering
choices the ADRs and the spec leave open: geometry stack, GLB writer, texture
integration, recipe and manifest schemas, bake rate, showroom renderer, output
safety, test strategy, and performance budgets. **No NEEDS CLARIFICATION
remains at the end of this file.**

---

## D1 — Language, runtime, packaging, and dependency policy

**Decision**: Python 3.12+ (target 3.12, run anywhere ≥3.12), managed with
`uv`; a single installable package `beastforge` under `src/beastforge/` with a
`beastforge` console script and `python -m beastforge` twin. Runtime
dependencies: `numpy` (float64 geometry math), `pydantic` v2 (recipe/manifest
schemas), `PyYAML` (`safe_load` only), `typer` + `rich` (CLI, theme, help),
`Pillow` (PNG encode for showroom frames). `texforge` is a runtime dependency
declared as a uv path source (see D5). Dev dependencies: `pytest`, `ruff`,
`mypy`, `jsonschema` (contract tests), `trimesh` (independent GLB import test).

**Rationale**: ADR 261114-2 fixes Python 3.12+/`uv` and a texforge-shaped
surface; matching texforge means the same packaging, CLI grammar, exit-code
model, and agent ergonomics, and lets the texture pipeline be shared rather than
duplicated. Pydantic keeps the recipe schema, error locations, and JSON Schemas
from drifting (`cli:help`, `docs:api`). numpy float64 is the same numeric base
texforge uses, so geometry and texture math share one determinism story.

**Alternatives considered**:
- *Rust or Go single binary.* Stronger startup and distribution story, but ADR
  261114-2 fixes Python/uv and the texforge analogue; a rewrite would invalidate
  the accepted decision and lose in-process texforge composition.
- *TypeScript/Node generator.* Same objection, plus the reference consumer is
  the only place JS is wanted; a Node runtime adds a second toolchain for
  nothing.
- *No pydantic; hand-written validators.* Fewer deps, but error paths and
  published JSON Schemas would be hand-maintained and drift from the parser.

---

## D2 — Geometry stack: numpy-first, no mesh-library dependency in the engine

**Decision**: Build meshes with our own numpy float64 code: swept tubes along
bone chains, ring shells for torsos, and rigid part emitters. Do **not** depend
on `trimesh`, `pygltflib`, `pyrender`, or a mesh kernel at runtime. `trimesh`
is a dev/test dependency only, used as one independent consumer that loads the
emitted `.glb` (SC-009).

**Rationale**: ADR 261114-3 makes weights fall out of construction, which means
we already own the vertex order, the triangle order, and the UV parameterization.
A general mesh library would either be unused or would reorder/merge geometry in
ways we cannot prove stable. Byte identity (FR-008, SC-002) is cheapest to
guarantee when every buffer is emitted by code whose iteration order is fixed.
The procedural math (Catmull-Rom-ish frames along a chain, quaternion
transport, radial noise) is small and testable, and macOS/Windows wheels for
heavy geometry libraries are a distribution risk.

**Alternatives considered**:
- *`trimesh` + custom exporter.* Convenient primitives, but its merge/sort
  behaviour and float paths vary by version, and the exporter must still be
  ours for byte identity; the convenience does not pay for the risk.
- *`pygltflib` for writing.* Handy model, but serializes dicts in insertion order
  and offers no byte-stability contract; we would wrap and canonicalize it into
  a de-facto custom writer anyway.
- *`pyrender`/OpenGL for showroom only.* Rejected as the default path (D12);
  optional later, not a runtime dependency.

---

## D3 — Deterministic glTF 2.0 binary (`.glb`) writer

**Decision**: Emit glTF 2.0 directly: a 12-byte header, one UTF-8 JSON chunk
(padded with `0x20`), and one BIN chunk (padded with `0x00`), with all
bufferViews 4-byte aligned. Fix the ordering rules: accessors and bufferViews in
emission order, nodes in recipe declaration order (root first, then bones in
declaration order, then mesh nodes), primitives per surface in recipe order,
animations in the reserved-clip order (`idle`, `locomotion`, `attack`, `hurt`,
`death`) followed by extra clips sorted by name. JSON is serialized with sorted
keys, ASCII-only, fixed decimal formatting (round-trip-shortest for floats, no
`-0.0`, reject NaN/Inf), and no timestamps or tool-generated UUIDs.

**Rationale**: ADR 261114-2 requires the GLB writer to be under our control;
glTF has no stable byte-order guarantee across libraries. Emission order is part
of the contract, so it is stated once here and enforced by golden tests. Fixed
4-byte alignment and chunk padding are mandatory for valid GLB parsing.

**Alternatives considered**:
- *`gltf-transform`/`gltfpack` post-processing.* Reorders and deduplicates by
  its own rules; would make byte identity depend on a Node toolchain.
- *JSON `.gltf` + external buffers.* More readable, but the spec requires one
  self-contained scene asset and the consumer (`r-type`) needs a single payload.

---

## D4 — Determinism contract: seeds, ordering, serialization, and atomic output

**Decision**: Only seeded pseudo-randomness. A run seed is derived from
`sha256("beastforge/v1" + recipe_sha256 + canonical(resolved_params))`, and
consumers draw independent streams as
`sha256(run_seed + ":" + purpose + ":" + index)` (same construction texforge
uses). All dict iteration is over sorted keys or over explicitly ordered lists
from the recipe. No wall clock, no `random` module, no locale, no environment
ordering, no process ID, no `set` iteration in output paths. Manifests are
canonical JSON (`sort_keys=True`, fixed separators, trailing newline). Outputs
are written to a temp directory inside the destination and committed with
`os.replace` only after generation **and** validation succeed.

**Rationale**: FR-008/FR-009 and ADR 261114-2. The seed must be a pure function
of the recipe and the resolved parameters, otherwise `--set` overrides would
silently change unrelated variation. Hashing derived streams rather than reusing
one global PRNG makes each subsystem independently reproducible in unit tests.

**Alternatives considered**:
- *One `random.Random(seed)` threaded everywhere.* Simpler, but draw order
  becomes a hidden global coupling; adding a noise call anywhere changes every
  downstream value.
- *Seed only from the recipe, ignoring parameters.* Overrides could not vary
  silhouette detail, contradicting FR-019 and US1 scenario 4.

---

## D5 — Texture and material integration with texforge

**Decision**: Consume texforge **in-process as a library** through a narrow
adapter (`texture/texforge_adapter.py`) that calls
`texforge.render.render_recipe(source, settings=..., overrides=..., size_override=...)`
and captures the PNG bytes plus the reported `sha256`. Resolve the texforge
recipe library root from, in order: `--texforge-library`, the
`BEASTFORGE_TEXFORGE_LIBRARY` environment variable, a `texforge.library`
setting in the project config, then the sibling default `../texforge/library`.
Declare texforge as a uv path source (`[tool.uv.sources] texforge = { path =
"../texforge", editable = true }`); when texforge is published, the source
becomes a version pin without touching call sites. Material references are
`{recipe: <texforge-name>, params: {...}, size: "WxH"}`; beastforge never
implements texture synthesis (FR-021). Rendered PNGs are embedded in the GLB as
`image/png` bufferViews and the manifest records recipe name, resolved params,
dimensions, and the rendered image `sha256`.

**Rationale**: The design handoff says "one pipeline yields skin and body"; an
in-process call reuses texforge's determinism, error model, and golden tests
instead of shelling out per texture. It also keeps SC-006 (under ten seconds per
creature) realistic: a subprocess would pay interpreter startup per texture.
The adapter is the only place that knows texforge exists, so swapping to a
subprocess or a published wheel is a single-file change.

**Alternatives considered**:
- *Subprocess `texforge render --json`.* Clean decoupling and version
  independence, but slower, harder to map texforge errors into our finding
  locations, and requires texforge on `PATH` at runtime.
- *Reimplement texture synthesis in beastforge.* Explicitly rejected by the
  design handoff and FR-021 — two texture engines to keep deterministic.
- *Reference-only material descriptors.* Rejected by the clarified spec: the
  package must embed the rendered texture set.

---

## D6 — Recipe grammar and inert-data enforcement

**Decision**: One YAML file per creature in
`library/<category>/<name>.yaml`, loaded with `yaml.safe_load` only, with these
top-level sections in this documented order: `meta`, `params`, `budgets`,
`skeleton`, `surfaces`, `materials`, `clips`, `sockets`, `volumes`, `phases`.
The pydantic model forbids unknown keys and requires `skeleton` before
`surfaces` semantically (every surface binds to declared bones; validation runs
skeleton checks first). A loader-level scan rejects explicit YAML tags other
than the standard scalars/collections and any key named `eval`, `exec`,
`import`, or `__reduce__`; `safe_load` already rejects Python object tags. The
recipe never names a Python module or function; clip generators are selected
from a closed registry of names.

**Rationale**: FR-004, FR-014, FR-026, and the spec's "recipes are inert data".
A closed generator registry plus a strict pydantic model means "executable
content" is impossible by construction, and unknown keys produce a nearest-key
suggestion rather than a silently ignored typo.

**Alternatives considered**:
- *Free-form YAML with a JSON Schema only.* Cheaper to start, but error
  locations and suggestions are worse, and unknown keys would slip through.
- *Order-enforcing custom loader.* Textual section-order enforcement is brittle
  (YAML mappings are unordered); referential validation expresses the real
  requirement and is testable.
- *Allow `python:module:function` hooks.* Rejected: executes recipe content.

---

## D7 — Clip baking, sampling rate, and `ticks@60` conversion

**Decision**: Bake every clip into glTF animation samplers at **60 Hz**
(one key per tick), using LINEAR interpolation and quantization of sample times
to exact `i/60` seconds serialized with a fixed decimal form. Authored durations
are in seconds with at most six decimals, or in integer `ticks` at 60 Hz;
`duration = ticks / 60` exactly (no intermediate rounding), and the manifest
reports seconds to six decimals plus the original `ticks` value. Loop clips
contain the closing key (time == duration) so engines loop without a pop. Event
times must satisfy `0 <= time < duration`.

**Rationale**: The reference consumer is a deterministic 60 Hz tick simulation,
and FR-023 demands exact conversion without drift. Baking at the simulation rate
keeps windup/impact/recovery aligned to ticks and makes the golden test compare
key counts, not interpolated curves. LINEAR interpolation keeps the file small
and the math reproducible; the generators are parameterized so 60 samples per
second is smooth for these motions.

**Alternatives considered**:
- *30 Hz bake.* Half the file size, but introduces up-to-16 ms timing error
  against the 60 Hz sim and complicates event alignment.
- *CUBICSPLINE.* Smoother in-engine tangents, but larger and more float math to
  pin; generators can express easing directly.
- *Store parametric clips for runtime evaluation.* Rejected by ADR 261114-4.

---

## D8 — Manifest schema and versioning

**Decision**: The manifest is a canonical JSON document with
`schemaVersion: "<major>.<minor>"`, starting at `"1.0"`. Consumers compare the
major component; same-major manifests are read with unknown fields ignored,
different-major manifests are rejected with an explicit
`manifest-schema-unsupported` error (FR-029, SC-010). The manifest is the sole
authority for gameplay timing (FR-031) and includes an explicit
`playback.eventTimeScaling` warning string (FR-033). Reserved core clips are
`idle`, `locomotion`, `attack`, `hurt`, `death`; renaming or removing one, or
changing the shape of a required field, requires a major bump (FR-032). The
full schema is [contracts/schema/manifest.schema.json](./contracts/schema/manifest.schema.json).

**Rationale**: Major-strict/minor-tolerant is the clarification the spec
settled on and mirrors the additive-fields promise in US2 scenario 5. Publishing
the schema as JSON Schema makes the "required fields remain readable" claim
testable with consumer fixtures.

**Alternatives considered**:
- *Single integer schema version.* Cannot distinguish additive (safe) from
  breaking (unsafe) changes without reading a changelog.
- *SemVer `MAJOR.MINOR.PATCH`.* Patch noise invites consumers to compare more
  than they should; `MAJOR.MINOR` is the smallest contract that works.
- *Embed the manifest inside the GLB `extras`.* Kills the sidecar contract and
  forces a GLB parser to read gameplay data.

---

## D9 — CLI surface, streams, `--json`, and exit codes

**Decision**: Verb-first grammar, one tree: `list`, `params`, `render`,
`validate`, `showroom`, `version`, `about`. Canonical global flags:
`-h/--help`, `-V/--version`, `-q/--quiet`, `-v/--verbose`, `--json`,
`--no-color`, `-n/--no-interaction`, `--dry-run`, `--config`. Results and
`--json` payloads go to stdout; progress, warnings, and errors go to stderr.
Exit codes: `0` success, `1` runtime/IO failure, `2` usage error, `3`
invalid recipe / validation failure, `4` not found (unknown creature, unknown
parameter, missing texture recipe), `128+n` signal. `render` writes a package
directory (default `dist/<name>/`) containing `<name>.glb` and
`<name>.manifest.json`; `-o/--out DIR` changes the directory; `--force` opts
into overwriting existing outputs; `--dry-run` prints the plan and writes
nothing. Flags are accepted before and after the subcommand. The full contract is
[contracts/cli.md](./contracts/cli.md).

**Rationale**: `cli:flag-vocabulary`, `cli:streams`, `cli:exit-codes`,
`cli:command-grammar`, and `cli:errors` from the resolved conventions, and
texforge parity (ADR 261114-2). The exit set lets an agent branch on
"invocation wrong" (`2`) versus "recipe wrong" (`3`) versus "name wrong" (`4`)
without parsing prose, which is what SC-003 depends on.

**Alternatives considered**:
- *`beastforge library list` style.* Mixes noun-first with the verb-first
  commands; `cli:command-grammar` forbids mixing.
- *One exit code (`1`) for all failures.* Loses the agent's cheapest signal.
- *Write textures as loose files next to the GLB.* Contradicts the clarified
  "embedded texture set" requirement and breaks the single-pair package promise.

---

## D10 — Output safety, overwrite policy, and interruption

**Decision**: Generate into a fresh temporary directory (`.beastforge-tmp-*`)
inside the chosen output directory, run the full validation gate against the
staged pair, then `os.replace` both files into place. Refuse to write when
either target exists unless `--force` is given (FR-012). Concurrent generations
to the same directory cannot interleave because each run stages in its own temp
directory and only the final two renames touch the target names; a lock file is
not used in v1. On error or SIGINT, the temp directory is removed in a `finally`
block, so no partial asset or manifest survives. `--dry-run` never creates the
temp directory.

**Rationale**: FR-012, FR-038, and the edge cases for pre-existing and
interrupted output. Staging also lets the gate inspect the exact bytes that will
be committed, satisfying "an artefact cannot be produced that the gate would
reject".

**Alternatives considered**:
- *Write in place and delete on error.* Crash windows leave partial files.
- *A directory-level lock.* Adds platform-specific locking for a problem two
  `os.replace` calls already avoid; revisit if cross-run deduplication is added.

---

## D11 — Validation gate and stable finding codes

**Decision**: One `validate()` entry point returns an ordered
`list[ValidationFinding]`; the CLI maps a non-empty error-severity list to exit
`3`. Every finding has `code`, `severity` (`error`|`warning`), `location`
(recipe path plus a JSON-pointer-ish field path such as
`surfaces[1].bones[2]`), `expected`, `actual`, `message`, and `remedy`. The code
vocabulary is closed and versioned alongside the schema; new codes are additive,
renaming a code is a major change. The gate covers: recipe syntax/unknown
fields/unknown params, skeleton structure (root, cycles, duplicates, degenerate
and inverted transforms, missing bone refs), skin invariants (sum within 1e-5,
≤4 influences, no zero-weight vertex, bind pose == rest pose), name-identifier
rules, surface mode support, clip inventory (reserved clips, duplicates,
non-positive duration, fractional ticks, unknown generator), event/socket/phase
referential integrity and ranges, material resolution, budgets, determinism
hazards, and manifest core-clip/reference checks. `render` runs the same gate
before committing. `validate` with no argument validates every library creature.

**Rationale**: FR-034–FR-038 and SC-004 require a distinct, stable finding per
defect class. A closed vocabulary is what lets the seeded defect corpus assert
"exactly one new code appeared" and lets an agent map a finding to a fix.

**Alternatives considered**:
- *Free-text messages only.* Agents cannot branch or prove coverage.
- *Let generation validate separately from `validate`.* Two gates drift; FR-038
  explicitly requires one gate.

---

## D12 — Showroom renderer and perceptual comparison

**Decision**: Render turntable and extreme-pose frames with a **numpy software
rasterizer** (`showroom/raster.py`): float64 vertex transforms, a z-buffer, a
flat background, one fixed key light plus ambient, and nearest-neighbour texture
sampling, encoded to 512×512 PNG via Pillow with pinned metadata. Fixed cameras
per view (front, three-quarter, side, rear) at a fixed distance and FOV, and one
extreme-bend pose per creature that applies a ±90° rotation at a declared test
joint. Comparison uses two documented numbers: per-pixel per-channel absolute
threshold (default `8/255`) and changed-pixel ratio (default `0.10%` of opaque
pixels); frames pass when both are within tolerance. Structural summaries
(joint count, clip/event inventory, influence histogram, bounds) are compared
exactly as a separate signal. `showroom --accept` rewrites references; plain
`showroom` compares and exits `3` on any regression. The comparison reports the
differing frame paths.

**Rationale**: SC-008 allows a documented perceptual tolerance, not byte
identity, because renderer and float variation are real. A CPU rasterizer
removes the GPU/EGL/display dependency that would make CI flaky and keeps the
renderer offline and deterministic enough for tight tolerances. Structural
summaries catch contract changes that pixels might hide.

**Alternatives considered**:
- *`pyrender`/OpenGL with EGL.* Faster and nicer shading, but needs a GPU or
  software GL stack, varies across drivers, and adds a heavyweight dependency
  to a tool whose core promise is offline reproducibility.
- *Blender headless.* Rejected by the design handoff (heavy, weak determinism).
- *Byte-exact golden PNGs.* Rejected by the clarified spec: renderer and
  floating-point variation would produce false positives.

---

## D13 — Library catalog and starter creatures

**Decision**: The library lives at `library/<category>/<name>.yaml` and is
scanned on demand; there is no index file. Categories are `boss`, `quadruped`,
`swarm`, `other`. v1 ships at least one creature per required category:
`boss/ash-crowned-tyrant.yaml` (boss, three phases), a quadruped, and a swarm
unit, with additional optional creatures as the grammar matures. `list` filters
by `--category` and repeatable `--tag`; `params` resolves a name or path with
explicit path precedence (same rule as texforge). Catalog metadata is the
recipe's `meta` block, so it cannot go stale.

**Rationale**: FR-001–FR-003 and texforge parity. A scanned library keeps the
catalog and the recipes one artifact; the required boss/quadruped/swarm spread
is stated in the spec assumptions and exercises the phase, gait, and small-rig
paths respectively.

**Alternatives considered**:
- *Generated `library/index.json`.* Two sources of truth that drift on every
  edit; scanning three YAML front-matter blocks is microseconds.
- *Flat `library/*.yaml`.* Category browsing is a stated user flow; direct
  subdirectories make it free.

---

## D14 — Testing strategy

**Decision**: `pytest` with these layers:
- `tests/unit/` — sweep math, frame transport, weight blending, tick
  conversion, seed derivation, canonical JSON, GLB header/chunk layout,
  parameter coercion and suggestions.
- `tests/contract/` — every `--json` payload validates against the published
  JSON Schemas; the manifest schema validates a generated manifest; error
  payloads validate on each exit code.
- `tests/integration/` — list→params→render, render twice and compare
  `sha256`, validate a library recipe, showroom compare/accept, overwrite
  refusal, interrupted-write cleanup, concurrent renders to one directory.
- `tests/determinism/` — same recipe in two different working directories with
  cleared locale/timezone/env differences yields identical hashes; a `slow`
  marker holds the 100-run SC-002 loop.
- `tests/defect_corpus/` — one fixture per finding code; each asserts the exit
  status and that the expected code appears.
- `tests/golden/` — committed `sha256` values for the library `.glb` and
  manifest pairs (bytes, not images) plus showroom structural summaries.
- `tests/consumers/` — `trimesh` loads each emitted GLB with skinning intact;
  a Node-based `@gltf-transform/cli validate` run is available as an optional
  CI job (Node 26 is present locally) and is not required for the Python suite.

**Rationale**: SC-002/SC-004/SC-009/SC-010 each need a different kind of proof.
Contract tests keep the published schemas honest; the defect corpus is the gate
coverage metric; the consumer test is the only way to catch a GLB that parses in
our own reader but not in a standard one.

**Alternatives considered**:
- *Only golden `.glb` hashes.* Proves stability, not validity.
- *Only integration tests.* Slow feedback and poor defect-localization.

---

## D15 — Performance and resource budgets

**Decision**: Targets from SC-006: catalog and `params` under 2 s; one creature
render (geometry + clips + textures + validation + write) under 10 s on a
developer laptop; showroom frame render budget 512×512 × 5 frames per creature
under 5 s. Default mesh/bone budgets declared in the recipe and enforced by
validation: 20,000 vertices and 64 bones per creature (override allowed in the
recipe, still validated). Clip bake at 60 Hz with at most 600 ticks per clip in
v1. Peak memory target under 512 MB.

**Rationale**: These are the spec's measurable outcomes plus an explicit
ceiling so "budget exceeded" is a testable failure rather than a vague warning.
They also bound the showroom's CPU rasterizer cost.

**Alternatives considered**:
- *No budget ceilings.* Violates FR-028 and lets a bad recipe make `render`
  appear hung.
- *Tighter budgets.* Would exclude the three required creatures before the
  grammar is even exercised.

---

## D16 — First-consumer packaging (design-handoff open question 7)

**Decision**: **Deferred, as the spec states.** v1 emits a standard `.glb` plus
manifest and stops there. The `r-type` single-file consumer will need an inline
data-URI or boot-time rebuild step; that is a packaging follow-up with its own
spec. No generator-side option is added now, because a "single-file variant"
would fork the output contract and the determinism hash for one consumer.

**Rationale**: Spec "Out of Scope (v1)" and the handoff's "Recommended Next
Artifact" both call this a separate feature. Keeping it out preserves ADR
261114-1 (one standard format) and SC-009 (two independent standard consumers).

**Alternatives considered**:
- *`--inline` or `--single-file` flag now.* Premature, and it would imply the
  generator owns a specific consumer's build.
- *Emit a compact runtime-built variant.* Reintroduces runtime generation, which
  ADR 261114-2 rejects.

---

## Decision summary

| # | Area | Decision |
|---|------|----------|
| D1 | Stack | Python 3.12+/uv; pydantic v2, numpy, PyYAML, typer, rich, Pillow; texforge path source |
| D2 | Geometry | Own numpy sweep/shell/rigid code; no runtime mesh library; `trimesh` dev-only |
| D3 | GLB writer | Custom glTF 2.0 binary writer, fixed emission order, canonical JSON |
| D4 | Determinism | Hashed seeded streams from recipe+params; canonical JSON; atomic staged output |
| D5 | Textures | In-process texforge library call via one adapter; PNGs embedded in GLB |
| D6 | Recipes | `safe_load`-only YAML, strict pydantic model, closed clip-generator registry |
| D7 | Clips | Baked at 60 Hz, LINEAR, exact `ticks/60`, closing key on loop clips |
| D8 | Manifest | `MAJOR.MINOR` schema, major-strict/minor-tolerant, events authoritative |
| D9 | CLI | Verb-first `list/params/render/validate/showroom` + `version/about`; exits `0/1/2/3/4` |
| D10 | Output safety | Temp-dir staging, `--force` to overwrite, cleanup on error/signal |
| D11 | Validation | Single gate, closed finding-code vocabulary, render runs it before commit |
| D12 | Showroom | numpy software rasterizer, fixed cameras/lights, perceptual tolerance + structural diff |
| D13 | Library | Scanned `library/<category>/<name>.yaml`; boss, quadruped, swarm required |
| D14 | Tests | unit/contract/integration/determinism/defect-corpus/golden/consumers |
| D15 | Budgets | <2 s catalog, <10 s render, 20k verts / 64 bones, ≤600 ticks per clip |
| D16 | Packaging | Deferred to a follow-up feature; no generator-side inline mode in v1 |

**Open questions remaining**: none. Design-handoff open questions 2, 3, 4, 5, 6,
and 8 are resolved by D2, D5, D8, D11, D12, and D5 respectively; question 7 is
explicitly deferred by D16 and the spec's out-of-scope list.
