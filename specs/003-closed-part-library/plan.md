# Implementation Plan: Closed Part Library

**Branch**: `003-closed-part-library` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-closed-part-library/spec.md`;
clarifications recorded in the spec (2026-11-15); existing contracts in
`specs/001-procedural-creature-generator/` and `specs/002-webgl-library-viewer/`;
accepted ADRs 261114-1 through 261115-6; resolved conventions in
`_ai/conventions.md`.

## Summary

Fix the reported hollow-asset defect at its source and turn beastforge's
surface construction into a reusable, anatomy-neutral **part library**.

1. **Closed geometry first.** Limb tubes and torso shells are currently emitted
   open-ended (`caps=False` in `pipeline.build_mesh` and
   `geometry.shell.build_torso_shell`). Every swept surface will be capped into a
   closed solid, and a new per-part closure gate will prove the FR-001 contract:
   every edge shared by exactly two faces, consistent outward winding, and no
   degenerate faces. Overlap between parts is allowed; the assembled asset need
   not be one manifold. Backface culling stays on everywhere; no two-sided
   material is emitted.
2. **Versioned, anatomy-neutral part presets.** Presets live under
   `library/parts/<preset>/<version>.yaml`. Recipes gain a `parts:` section whose
   instances pin a preset name **and exact version**, bind abstract `@slot` bone
   roles to real joints, override preset parameters partially, and may add or
   replace controls and automatic behaviours. Preset versions are immutable:
   changing a preset means adding a new version file, so existing assemblies keep
   resolving their pinned version.
3. **Control contracts in published metadata.** A part declares named rotation or
   translation channels with joint, axis, mode, bounded range or unbounded mode,
   default, and explicit units (`deg` / `m`). The manifest exposes these under
   `parts[].controls` with a unique `part/control` address. The viewer gains a
   read-only Controls tab.
4. **Deterministic automatic motion.** Presets and instances may declare
   breathing, bobbing, swaying, or constant rotation. These are baked as a
   baseline into every authored clip; an explicit clip wins for the same joint.
   When an asset has automatic behaviours and no authored clips, one deterministic
   `baseline` clip is synthesized and published with `source: "automatic"`.

The existing five creatures keep their gameplay facts (joints, clips, events,
sockets, volumes, phases, materials, units, axes). Their bytes change because
closed caps are added and the manifest becomes 1.1; goldens and showroom
reference frames are regenerated and approved as part of the work.

## Technical Context

**Language/Version**: Python 3.12+ (`uv` managed; repository target). No new
runtime language or toolchain. The viewer remains buildless ES2022 modules.

**Primary Dependencies**: Existing runtime dependencies only — `numpy`,
`pydantic` v2, `PyYAML`, `typer`, `rich`, `Pillow`, `texforge`. `trimesh` stays a
dev-only independent checker; closure validation is implemented in-tree with
numpy so it ships in the runtime gate. No new package dependency is planned.

**Storage**: Filesystem only.
- Presets: `library/parts/<preset>/<version>.yaml` (one immutable version per
  file; the directory name and file stem carry the preset name and version).
- Assemblies: existing `library/<category>/<name>.yaml`.
- Outputs: existing `<name>.glb` + `<name>.manifest.json` pair.
- Viewer cache: existing content-addressed cache keyed by the canonical
  build-input digest.
No database, no committed binaries, no network access at runtime.

**Testing**: `pytest` layers — unit (closure analyzer, preset registry, override
application, auto composition, control validation), contract (preset schema,
manifest 1.1 additive compatibility, parts list schema, no `DoubleSide` material,
gameplay-facts snapshot), integration (`validate` over the whole library,
`render` of the mech and craft examples, `parts` CLI, viewer catalog), defect
corpus (open/mis-wound/degenerate parts, duplicate controls/addresses, missing
presets), determinism (two builds of a preset assembly byte-identical; automatic
baseline reproducible), golden (regenerated hashes), and the existing opt-in
viewer smoke check. Default `pytest` stays offline and browser-free.

**Target Platform**: Same as 001/002: Linux/macOS/Windows, Python 3.12, offline;
desktop browsers with WebGL for the viewer.

**Project Type**: Single Python package (`src/beastforge/`) with an in-repo
creature/part library, a buildless static viewer, and a Spec Kit artifact set.

**Performance Goals**: Closure checking is O(triangles) per part and runs once per
build; caps add `2 * segments` triangles per swept part (tens of triangles, not
thousands). Preset registry loading is a small one-time file scan. No measurable
change to the current render budget (20k vertices / 60k triangles per creature).
Default test suite stays within the existing runtime envelope (SC-009 of 002).

**Constraints**:
- Determinism: identical recipe, pinned preset documents, resolved parameters,
  and tool version must produce byte-identical GLB and manifest.
- Offline: no network, wall clock, locale, hostname, or unordered iteration may
  reach geometry, animation, or JSON.
- Closure is unconditional: no `open`/`two-sided`/`disable-culling` escape hatch.
- Backward compatibility: recipes without `parts` remain valid; `limb-tube` and
  `torso-shell` remain accepted; manifest 1.0 documents stay readable; all new
  manifest fields are additive within major 1.
- Anatomy neutrality: no validation rule may require a torso, a limb, a chain, or
  a specific family structure. Core clips are not required for `category: other`
  or for an asset with no authored clips.
- Viewer: backface culling stays enabled; no `DoubleSide` material is emitted or
  selected as a workaround.

**Scale/Scope**: 5 existing creatures + 2 new example assemblies (mechanical mech
and limbless vehicle) + about 12 minimal presets across organic, mechanical, and
vehicle families. Designed for roughly 100 recipes and a growing preset library.
In scope: closure, preset/instance model, controls, auto-motion baseline,
manifest 1.1 additions, viewer Controls tab, `parts` discovery command, tests,
goldens/showroom regeneration, docs/ADRs. Out of scope: boolean union/CSG,
self-intersection detection, duplicate-face detection, interactive rig controls
in the viewer, metaball surfaces, runtime procedural animation, and preset
marketplaces/remote registries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> **Finding (surfaced, not silently passed):** `.specify/memory/constitution.md`
> is still the unfilled `[PRINCIPLE_*]` template. As with features 001 and 002,
> this gate is evaluated against the repository's authoritative resolved
> conventions (`_ai/conventions.md`, generated by `ruleman export`) and the
> accepted ADRs. Filling `constitution.md` remains a repo-hygiene follow-up and
> does not block this feature. No design choice conflicts with the example
> principles (Library-First, CLI Interface, Test-First, Integration Testing,
> Observability, Versioning, Simplicity).

| Gate (source) | Requirement | Status | How the design satisfies it |
|---------------|-------------|--------|-----------------------------|
| `architecture:separation` / `architecture:solid` | Core logic separated from IO/UI; modular | ✅ PASS | Preset models are inert; registry loading is an adapter; `parts/resolve.py` and `geometry/closure.py` are pure; CLI/viewer are thin boundaries |
| `code:robustness` | Edge cases, errors, assertions | ✅ PASS | Explicit findings for open/non-manifold/degenerate parts, missing preset versions, bad bindings/overrides, invalid axes/ranges/units, duplicate addresses |
| `testing:unit` | New features have tests | ✅ PASS | Unit + contract + integration + defect + determinism layers named in Project Structure |
| `docs:minimum-set` / `readme` / `architecture` / `development` / `api` / `adr` / `changelog` / `style` | Documentation set linked and current | ✅ PASS | README/SKILL, `docs/architecture.md`, `docs/api.md`, `docs/recipes.md`, `docs/development.md`, `docs/cheatsheet-cli.md`, `CHANGELOG.md`, and new ADRs updated in the same change |
| `docs:code-docstrings` / `code-comments` / `code-examples` | Public contracts documented; comments explain why | ✅ PASS | New Python modules/classes get docstrings; JS module header states its read-only contract; quickstart examples are runnable |
| `maintenance:compatibility` | Backwards compatibility or migration path | ✅ PASS | Additive recipe fields, neutral kind aliases, immutable preset versions, manifest 1.1 additive fields, 1.0 consumer tolerance, regenerated goldens |
| `cli:command-grammar` / `flag-vocabulary` | One grammar; canonical flags | ✅ PASS | `beastforge parts [NAME]` follows the existing `params [NAME]` noun pattern; uses `--json`, `--quiet`, `--no-color`, `--dry-run` semantics where meaningful; `--family`, `--version` are mode-specific |
| `cli:streams` / `exit-codes` / `errors` | Results stdout, diagnostics stderr; stable exits/errors | ✅ PASS | Preset table/JSON to stdout; parse/generation warnings to stderr; reuses `0/1/2/3/4`; unknown preset exits 4; invalid preset exits 3 |
| `cli:cheatsheet` | Curated cheat sheet kept in sync | ✅ PASS | New `## parts` section and "Most useful" rows that mirror the command tree |
| `release:semver` / `git-tags` | SemVer, one version source | ✅ PASS | Feature is a minor release; `beastforge.__version__` remains the single source |
| ADR 261114-1 (manifest contract) | glTF + sidecar; major-strict/minor-tolerant | ✅ PASS | Manifest becomes 1.1 with additive `parts`, `controls`, `clips[].source`; 1.0 payloads still parse |
| ADR 261114-2 (offline determinism) | Deterministic, offline, no hidden inputs | ✅ PASS | Closure uses numpy arithmetic only; preset versions are pinned and immutable; canonical JSON; built-in presets scanned in sorted order |
| ADR 261114-3 (construction-bound skinning) | Weights at construction; 1–2 influences | ✅ PASS | Presets expand to the same `Surface` builders; caps reuse existing joint/weight rows; no new skinning solver |
| ADR 261114-4 (baked clips/events) | Animation baked at generation; manifest timing authoritative | ✅ PASS | Auto motion is baked at 60 Hz into tracks; explicit clips win per joint; synthesized `baseline` clip is published with `source: "automatic"` |
| ADR 261115-5 / 261115-6 (viewer) | Buildless, vendored, loopback-first, read-only | ✅ PASS | Only `inspector.js` changes to add a read-only Controls tab; no new frontend dependency; culling unchanged |
| FR-003 / SC-008 (no two-sided workaround) | Backface culling enabled everywhere | ✅ PASS | GLB writer never emits `doubleSided`; viewer never sets `DoubleSide`; contract test enforces it |

**Verdict**: **PASS** — no unjustified violations; no entries required in
Complexity Tracking. The constitution-template gap is a documented repo-hygiene
follow-up, not a design violation.

### Post-design re-check (after Phase 0 research + Phase 1 design)

Re-ran the gate against the concrete artifacts now written —
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/preset.schema.json](./contracts/preset.schema.json),
[contracts/parts-grammar.md](./contracts/parts-grammar.md),
[contracts/controls.md](./contracts/controls.md),
[contracts/closure.md](./contracts/closure.md),
[contracts/manifest-additions.md](./contracts/manifest-additions.md),
[contracts/cli.md](./contracts/cli.md),
[contracts/parts.list.schema.json](./contracts/parts.list.schema.json), and
[quickstart.md](./quickstart.md):

- **Closure** — capping policy, per-part edge/winding/degenerate checks, epsilon,
  and finding codes are normative in `contracts/closure.md`; no escape hatch
  exists. ✅
- **Presets** — storage/versioning, `@slot` binding, canonical override
  vocabulary, type/range rules, and the immutability policy are normative in
  `contracts/preset.schema.json` and `contracts/parts-grammar.md`. ✅
- **Controls/auto** — both discriminated schemas, units/mode matching, address
  uniqueness, composition order, baseline duration, and explicit-clip precedence
  are normative in `contracts/controls.md`. ✅
- **Manifest compatibility** — every addition is additive within major 1; old
  1.0 manifests remain readable; `source` and `baseline` are specified in
  `contracts/manifest-additions.md`. ✅
- **CLI/docs** — `parts` grammar, streams, JSON shape, and exit codes are
  normative in `contracts/cli.md`; every new surface has an owner document in
  Project Structure. ✅
- **Determinism** — preset content is included in the canonical build digest,
  preset versions are immutable, and two-build tests are planned. ✅
- **ADR gates** — no Node toolchain, no CDN, no committed binaries, no boolean
  union, no self-intersection check, no two-sided rendering. ✅

**Post-design verdict**: **PASS**.

## Design Overview

### Closed-geometry pipeline

```
recipe surface / part instance
        │
        ▼
  Surface (same model) ──► sweep_surface(caps=True) / rigid_surface(caps=True)
        │                              │
        │                              ▼
        │                       SurfaceGeometry
        │                              │
        ▼                              ▼
  append_surface (per-surface range, winding normalized)
        │
        ▼
  Mesh ──► check_closure (per SurfaceRange)
        │      • every undirected edge has exactly 2 incident faces
        │      • the two directed occurrences are opposite (consistent winding)
        │      • signed volume > 0 (outward)
        │      • no repeated-vertex or near-zero-area triangle
        ▼
  gate findings (surface-open / surface-non-manifold / surface-winding-invalid /
                 surface-degenerate) or commit
```

Caps are triangle fans from the path endpoint to the first/last ring. Because the
ring is planar and star-shaped about its centre, the fan is a valid closed end.
Torso shells and limb tubes both use the existing `sweep_surface`; the only
change is `caps=True`. Rigid parts already cap. No boolean union is performed:
caps at joints may sit inside neighbouring parts, which is explicitly allowed.

### Preset resolution

```
library/parts/<preset>/<version>.yaml
        │  PresetRegistry (sorted scan, exact version lookup)
        ▼
recipe.parts[] (name, preset, preset_version, bind, overrides, material, controls, auto)
        │  resolve_parts (pure; no IO)
        ├── validate every @slot has a bind and every bind names a real bone
        ├── apply canonical overrides to a deep copy of the preset surface
        ├── expand controls: @slot -> joint, address = "<part>/<control>"
        ├── merge instance controls/auto over preset ones by name
        └── produce ResolvedPart {surface, controls, auto, presetSha256}
        ▼
recipe.surfaces + resolved part surfaces  (one ordered list)
        ▼
skeleton → mesh → closure → bake → manifest → gate → commit
```

`limb-tube` / `torso-shell` keep working; `swept-solid` / `shell` are the neutral
public names and map to the same builders. A part with no slots (a rigid panel,
turret, or rotor) still binds one `@mount` slot.

### Automatic motion

Auto behaviours are a discriminated union (`breathe`, `bob`, `sway`, `rotate`)
resolved against real joints. For each authored clip, the baker first builds the
generator functions, then adds auto functions **only for joints the generator did
not animate**. Multiple auto behaviours on one joint compose in declaration order
(translation sums, rotations multiply, scales multiply). When `clips` is empty and
auto behaviours exist, one `baseline` clip is synthesized with a deterministic
duration (the longest periodic behaviour, at least 2 s, capped by
`budgets.max_clip_ticks`) and `loop: true`.

### Anatomy neutrality and core clips

- `Recipe.surfaces` and `Recipe.clips` become optional (`min_length=0`); at least
  one of `surfaces` / `parts` is required, enforced by the gate.
- The skeleton still requires one root bone; a root-only skeleton is valid.
- Core clips (`idle`, `locomotion`, `attack`, `hurt`, `death`) are required only
  when `meta.category != "other"` **and** at least one clip is authored. This
  preserves the existing five creatures, allows an auto-only creature, and lets a
  mechanical `other` asset author any clip set (or none).
- No rule references a torso, limb, chain, or family structure. A hit volume is
  still required because it is a gameplay fact, not an anatomy fact.

### Manifest 1.1

Additive fields only:

```json
{
  "schemaVersion": "1.1",
  "clips": [
    {"name": "idle", "duration": 2.0, "loop": true, "generator": "breathe", "source": "authored"},
    {"name": "baseline", "duration": 2.0, "loop": true, "generator": "baseline", "source": "automatic"}
  ],
  "parts": [
    {
      "name": "front-left-leg",
      "preset": "organic-leg",
      "presetVersion": "1.0.0",
      "presetSha256": "…64 hex…",
      "family": "organic",
      "controls": [
        {
          "address": "front-left-leg/swing",
          "name": "swing",
          "joint": "upper-fl",
          "axis": [1.0, 0.0, 0.0],
          "mode": "rotation",
          "unbounded": false,
          "range": {"min": -35.0, "max": 35.0},
          "default": 0.0,
          "units": "deg"
        }
      ]
    }
  ]
}
```

`parts` is optional for a reader (a 1.0 document is valid), `source` defaults to
`authored`, and `generator: "baseline"` is the only new generator name. The
`Manifest` producer model defaults `parts` to `[]`, so existing manifests still
parse.

### Determinism and cache

`library.load_entry_with_document` and `pipeline.prepare` compute the canonical
build digest as:

```
sha256(canonical_json({"recipe": <document>, "presets": [<pinned preset documents>]}))
```

For recipes without `parts`, this is byte-identical to the current
`recipe_digest(document)`. The digest remains the value in
`provenance.recipeSha256`, so the viewer cache and its manifest verification keep
working. Preset files are immutable at a version; adding a version changes the
digest only for assemblies that pin it. `parts[].presetSha256` exposes the
per-preset content hash for auditing.

## Implementation Phases

1. **Closure (P1 blocker).** Add `geometry/closure.py`; cap limb/torso sweeps;
   add closure findings and gate wiring; update defect tests; prove the five
   creatures are closed.
2. **Models and preset library.** Add `model/parts.py`, neutral surface kinds,
   optional `surfaces`/`clips`, `parts` recipe section, `parts/registry.py`,
   `parts/overrides.py`, and the shipped minimal presets.
3. **Resolution and validation.** Add `parts/resolve.py`,
   `validation/parts.py`, `validation/closure.py`; thread resolved surfaces
   through `pipeline`, `gate`, `check_surfaces`, `check_skin`, `check_materials`,
   and `check_clips`.
4. **Automatic motion.** Add `anim/auto.py`; extend `bake.py` with baseline
   injection, explicit-clip precedence, and synthesized `baseline`; add
   `clips[].source`; update the render report inventory to use baked clips so the
   synthesized baseline is visible there too.
5. **Published contract.** Extend manifest 1.1 (`parts`, controls,
   `presetSha256`), viewer Controls tab, and `beastforge parts`.
6. **Proof and regeneration.** Ship the mech and craft examples; regenerate
   goldens, showroom references, and the showroom gallery; add gameplay-facts
   snapshot, no-double-sided contract, and determinism tests.
7. **Documentation.** Update README/SKILL, docs, cheat sheet, CHANGELOG, ADRs, and
   the specs index.

## Project Structure

### Documentation (this feature)

```text
specs/003-closed-part-library/
├── plan.md                         # This file
├── spec.md                         # Feature specification
├── research.md                     # Phase 0 decisions (D1–D18)
├── data-model.md                   # Phase 1 entities, invariants, state
├── quickstart.md                   # Phase 1 runnable validation guide
├── checklists/
│   └── requirements.md             # Spec quality gate (already present)
└── contracts/
    ├── closure.md                  # Closed-solid definition, algorithm, findings
    ├── preset.schema.json          # Part-preset file schema
    ├── parts-grammar.md            # Recipe parts[], @slots, overrides, neutral kinds
    ├── controls.md                 # Control + automatic-behaviour schemas, baking rules
    ├── manifest-additions.md       # Manifest 1.1 additive fields and compatibility
    ├── cli.md                      # `beastforge parts` grammar, flags, JSON, exits
    └── parts.list.schema.json      # `parts --json` document schema
```

### Source Code (repository root)

```text
src/beastforge/
├── model/
│   ├── recipe.py                   # + parts[], optional surfaces/clips, neutral kinds
│   ├── parts.py                    # NEW preset/instance/control/auto models
│   ├── manifest.py                 # + parts/controls, clips[].source, schema 1.1
│   └── findings.py                 # + part/closure finding codes
├── parts/                          # NEW preset subsystem
│   ├── __init__.py
│   ├── registry.py                 # adapter: sorted library/parts scan, exact versions
│   ├── overrides.py                # pure canonical override application
│   └── resolve.py                  # pure recipe parts -> ResolvedPart + findings
├── geometry/
│   ├── sweep.py                    # caps already supported; no algorithm change
│   ├── shell.py                    # caps=True for torso shells
│   └── closure.py                  # NEW pure edge/winding/degenerate analyzer
├── anim/
│   ├── auto.py                     # NEW behaviour functions + baseline duration
│   ├── registry.py                 # unchanged generator registry
│   └── bake.py                     # + auto baseline injection, synthesized clip
├── validation/
│   ├── parts.py                    # NEW preset/binding/override/control findings
│   ├── closure.py                  # NEW per-SurfaceRange gate
│   ├── gate.py                     # + parts resolution, closure, resolved surfaces
│   ├── surfaces.py                 # + neutral kinds, resolved-surface paths
│   ├── skin.py                     # + resolved surfaces; closure checks moved out
│   ├── clips.py                    # + category/no-clip core rule
│   ├── determinism.py              # + manifest parts/control checks, core rule, resolved materials
│   └── budgets.py                  # unchanged
├── export/
│   ├── manifest.py                 # + parts/controls, clips[].source, build digest
│   └── gltf.py                     # + `baseline` clip ordering (no doubleSided)
├── pipeline.py                     # + preset resolution, closed surfaces, baseline clips
├── render.py                       # + load registry, pass parts through prepare/gate, baked-clip inventory
├── library.py                      # + build digest over pinned preset documents
├── cli/
│   ├── app.py                      # + `parts` registration
│   └── parts.py                    # NEW `beastforge parts` command
├── texture/
│   └── texforge_adapter.py         # + resolved surfaces for referenced-material checks
└── viewer/
    ├── catalog.py                  # unchanged shape; build digest reflects presets
    └── static/lib/inspector.js     # + read-only Controls tab

library/
├── parts/                          # NEW minimal preset library
│   ├── organic-leg/1.0.0.yaml
│   ├── organic-torso/1.0.0.yaml
│   ├── organic-head/1.0.0.yaml
│   ├── organic-tail/1.0.0.yaml
│   ├── mech-leg/1.0.0.yaml
│   ├── mech-armor-plate/1.0.0.yaml
│   ├── mech-turret/1.0.0.yaml
│   ├── mech-piston/1.0.0.yaml
│   ├── vehicle-hull-panel/1.0.0.yaml
│   ├── vehicle-wing/1.0.0.yaml
│   ├── vehicle-engine-bell/1.0.0.yaml
│   └── vehicle-rotor/1.0.0.yaml
├── other/
│   ├── iron-warden.yaml            # NEW mechanical example (parts only)
│   └── hover-skiff.yaml            # NEW limbless vehicle example (parts + auto)
└── … existing five creatures …

tests/
├── unit/
│   ├── test_closure.py             # NEW open/closed/non-manifold/winding/degenerate
│   ├── test_part_registry.py       # NEW versions, duplicates, sorted scan
│   ├── test_part_overrides.py      # NEW partial merge, types, ranges
│   ├── test_auto.py                # NEW behaviour composition + baseline duration
│   └── test_controls.py            # NEW axis/range/units/address rules
├── contract/
│   ├── test_preset_schema.py       # NEW shipped presets conform
│   ├── test_manifest_v11.py        # NEW additive fields + 1.0 tolerance
│   ├── test_parts_cli.py           # NEW `parts --json` schema
│   ├── test_no_double_sided.py     # NEW emitted materials and viewer sources
│   ├── test_preset_replacement.py  # NEW hand-authored part -> equivalent preset (SC-010)
│   └── test_gameplay_facts.py      # NEW pinned facts for the five creatures
├── integration/
│   ├── test_parts_render.py        # NEW mech/craft validate, render, manifest, viewer
│   └── test_parts_cli.py           # NEW human/JSON/exit-code behavior
├── determinism/
│   └── test_parts_determinism.py   # NEW two builds byte-identical, baseline stable
├── defect_corpus/
│   └── test_defects.py             # + open/non-manifold/degenerate, bad parts/controls
├── golden/
│   ├── library.sha256              # regenerated
│   └── gameplay_facts.json         # NEW pre-change facts snapshot
└── viewer/
    └── test_browser_smoke.py       # unchanged opt-in check

docs/
├── architecture.md                 # + parts, closure gate, auto baseline
├── api.md                          # + manifest 1.1 parts/controls and closure findings
├── recipes.md                      # + parts[], @slots, overrides, neutral kinds, auto
├── development.md                  # + preset/golden/showroom regeneration workflow
└── cheatsheet-cli.md               # + `## parts`

showroom/reference/                 # regenerated frames for the five creatures
docs/showroom-gallery.md            # regenerated image links (same paths)
README.md, SKILL.md                 # + closed parts / preset library
CHANGELOG.md                        # + Unreleased Added/Changed/Fixed
specs/README.md                     # + 003 index row
_ai/technical_decisions/            # + ADRs (see below)
```

**Structure Decision**: Feature 003 extends the existing single-package layout.
Presets live in a new `src/beastforge/parts/` subpackage so the registry adapter
(filesystem scan) is separated from the pure resolver and override code. Preset
data stays under `library/parts/` next to recipes, so `--library` and
`BEASTFORGE_LIBRARY` locate presets with no new configuration surface; the
existing `library_paths()` glob (`*/*.yaml`) does not mistake preset files for
creatures. Closure checking is a `geometry/` + `validation/` pair, not a mesh
library dependency, to preserve determinism and the in-tree owner of GPU-free
geometry. The viewer change is confined to `inspector.js`; no new frontend
module or dependency is introduced.

### ADRs to add

- **ADR 261116-7 — Closed-solid part contract.** Cap all swept parts, validate
  watertight/manifold/winding/degeneracy per part, allow joint overlap, forbid
  two-sided rendering, and explicitly exclude self-intersection and duplicate-face
  detection.
- **ADR 261116-8 — Versioned, anatomy-neutral part presets.** One immutable
  preset version per file, exact version pinning, `@slot` bone roles, neutral
  surface kinds, canonical partial overrides, and a preset registry separate from
  creature recipes.
- **ADR 261116-9 — Control contracts and baked automatic motion.** Rotation and
  translation channels with explicit units, bounded/unbounded ranges, a published
  `part/control` address, baked auto-motion baselines with explicit-clip
  precedence, and a synthesized `baseline` clip.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Caps change every GLB and showroom frame | Regenerate `tests/golden/library.sha256` and `showroom/reference` with `--accept` in the same change; add a pinned gameplay-facts snapshot so SC-003 is proven, not assumed |
| Closure epsilon flags legitimate small parts (e.g. the mite) | Use a scale-relative area threshold (`diagonal² × 1e-10`) plus exact repeated-index checks; unit-test tiny and large closed solids |
| Caps at joints create visually odd internal geometry | Caps are flat fans at the path endpoints; they overlap neighbouring parts and are hidden by the joint overlap. Showroom extreme-bend frames prove no visible interior |
| Preset override vocabulary grows into a second recipe language | Closed canonical vocabulary (radius, rings, segments, blend, taper, twist, noise, squash, scale); unknown names are errors with suggestions; the preset's full surface template remains the source of truth |
| Preset change breaks old assemblies | One file per immutable version; exact pin; missing-version findings list available versions; registry scans all versions |
| Manifest 1.1 breaks existing consumers | All additions are optional; `parts` defaults to `[]`, `source` defaults to `authored`, and `read_manifest_compatible` keeps major-strict/minor-tolerant behavior |
| Automatic motion conflicts with authored clips | Explicit generator functions always win on the same joint; composition order for multiple auto behaviours is fixed and documented |
| Anatomy-neutral assets accidentally inherit creature-only rules | Core clips are gated by `category != "other"` **and** at least one authored clip; empty `clips` synthesizes a baseline; root-only skeletons and parts-only geometry are valid |
| Determinism across preset content changes | Canonical build digest includes pinned preset documents; preset versions are immutable; two-build determinism test covers a preset assembly |
| Viewer accidentally hides open geometry with two-sided rendering | `build_glb` never emits `doubleSided`; the viewer never sets `DoubleSide`; a contract test scans both |
| The worktree has uncommitted event-play changes in `viewer/static/app.js` and `viewer/static/lib/inspector.js` | The Controls-tab edit must layer on those changes and not revert them; re-read both files before editing and keep the event-play behaviour intact |

## Complexity Tracking

No constitution or convention violations require justification. The feature adds
a preset subsystem and a closure gate to the existing package; neither introduces
a new toolchain, a new runtime dependency, or a second source of truth for
creature facts.
