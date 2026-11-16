---

description: "Task list for the Closed Part Library feature"
---

# Tasks: Closed Part Library

**Input**: Design documents from `/specs/003-closed-part-library/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED for this feature. The plan's test strategy (research.md D18 and plan.md "Testing") explicitly names unit, contract, integration, defect-corpus, determinism, and golden/showroom layers, and quickstart.md depends on them. Test tasks are therefore included and precede the implementation task they cover.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified independently. `[P]` marks tasks that touch different files and have no incomplete-task dependency.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single Python package: `src/beastforge/`, tests under `tests/`, data under `library/`, docs under `docs/`.
- Viewer is buildless ES modules under `src/beastforge/viewer/static/`.
- Contract schemas live under `specs/001-procedural-creature-generator/contracts/schema/` and `specs/003-closed-part-library/contracts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing project is green and create the new package/test scaffolding.

- [X] T001 Verify the baseline toolchain and green default suite (`uv sync --all-groups`, `uv run beastforge validate`, `uv run pytest`) before changing code, using `pyproject.toml` as the dependency and pytest-marker source of truth.
- [X] T002 [P] Create the `parts` subpackage shell at `src/beastforge/parts/__init__.py` with a module docstring and no logic yet.
- [X] T003 [P] Create reusable hand-built mesh fixtures (closed box, open box, non-manifold edge, inward-wound box, repeated-vertex triangle) in `tests/fixtures/meshes.py` plus `tests/fixtures/__init__.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared vocabulary and models used by all part/closure stories. Complete before US2/US3/US4; US1 may start once T004 is done.

**⚠️ CRITICAL**: Phase 2 must be complete before any user-story phase other than the closure-only portion of US1 can begin.

- [X] T004 Extend `src/beastforge/model/findings.py` with the `parts` and `closure` groups and every code listed in research.md D14 (`recipe-empty-geometry` … `surface-degenerate`), keeping `surface-self-intersection` reserved and no longer emitted.
- [X] T005 [P] Create `src/beastforge/model/parts.py` with the shared Pydantic models from data-model.md §1–§2: `PresetSurface`, `PresetParam`, `PresetControl`, the `AutoBehaviour` discriminated union, `PartInstance`, `ResolvedPart`, `ControlChannel`, `ResolvedAuto`, and the canonical override-key vocabulary constant.
- [X] T006 [P] In `src/beastforge/model/recipe.py`, make `Recipe.surfaces` and `Recipe.clips` optional (`min_length=0`) and add `parts: list[PartInstance] = []`; keep `skeleton` and a hit `volumes[]` required.
- [X] T007 [P] Accept the neutral surface kinds `swept-solid` and `shell` in `src/beastforge/validation/surfaces.py::_KINDS` and map them to the same builders as `limb-tube`/`torso-shell` in `src/beastforge/pipeline.py`.
- [X] T008 Add the `recipe-empty-geometry` check (neither `surfaces` nor `parts`) to `src/beastforge/validation/gate.py` and confirm a root-only skeleton remains valid in `src/beastforge/validation/skeleton.py`.

**Checkpoint**: Shared model/vocabulary layer ready — US1 may proceed, and US2/US3/US4 can start as their phase tasks are reached.

---

## Phase 3: User Story 1 - Closed Creature Parts (Priority: P1) 🎯 MVP

**Goal**: Every generated part is a watertight, manifold, outward-wound solid with no degenerate faces; swept limbs and torso shells are capped; no two-sided rendering is used.

**Independent Test**: Generate all five shipped creatures, run the closure gate, and orbit each in the viewer with backface culling enabled. Every part must be closed and no interior may be visible.

### Tests for User Story 1 (required) ⚠️

- [X] T009 [P] [US1] Write closure-analyzer unit tests in `tests/unit/test_closure.py` using `tests/fixtures/meshes.py`: closed box at large and tiny scale, open box → `surface-open`, non-manifold edge → `surface-non-manifold`, inward winding → `surface-winding-invalid`, repeated-vertex/zero-area triangle → `surface-degenerate`.
- [X] T010 [P] [US1] Write a contract test in `tests/contract/test_no_double_sided.py` that parses emitted GLB materials for `doubleSided` and scans authored viewer JS under `src/beastforge/viewer/static/` for `DoubleSide`.
- [X] T011 [P] [US1] Write `tests/contract/test_gameplay_facts.py` and the pinned snapshot `tests/golden/gameplay_facts.json` proving the five creatures' joints, clips, events, sockets, volumes, phases, materials, units, and axes are unchanged (SC-003).
- [X] T012 [P] [US1] Write defect-corpus closure cases in `tests/defect_corpus/test_closure_defects.py` covering an open end, a non-manifold edge, a degenerate cap, and inward winding through the public validation gate.

### Implementation for User Story 1

- [X] T013 [US1] Implement the pure analyzer in `src/beastforge/geometry/closure.py`: per-`SurfaceRange` local index rebasing, boundary/non-manifold/inconsistent edge counts, degenerate-face detection, signed volume, first-issue payload, and the scale-relative epsilon from `contracts/closure.md` §1.1.
- [X] T014 [US1] Enable caps for all swept parts: set `caps=True` in `src/beastforge/pipeline.py::build_mesh` for swept/limb kinds and in `src/beastforge/geometry/shell.py::build_torso_shell` (depends on T007, T013).
- [X] T015 [P] [US1] Implement `src/beastforge/validation/closure.py` to run the analyzer over every `SurfaceRange` in `mesh.surfaces` and emit `surface-open`, `surface-non-manifold`, `surface-winding-invalid`, and `surface-degenerate` with part paths, expected/actual, and remedies.
- [X] T016 [US1] Wire the closure gate into `src/beastforge/validation/gate.py` after mesh construction and before clips/materials/budgets, passing the built `mesh` and its ranges (depends on T015).
- [X] T017 [US1] Remove any duplicated self-intersection/closure concerns from `src/beastforge/validation/skin.py` and stop emitting `surface-self-intersection` from `src/beastforge/validation/surfaces.py`; closure is now owned by `validation/closure.py`.
- [X] T018 [US1] Guard backface culling: verify `src/beastforge/export/gltf.py` never writes `doubleSided` and `src/beastforge/viewer/static/lib/stage.js`/`app.js` never select `DoubleSide`; add a small internal assertion or comment documenting the invariant.
- [X] T019 [US1] Regenerate `tests/golden/library.sha256` for the five creatures after caps are enabled, and update the regeneration snippet in `docs/development.md` so maintainers can repeat it.
- [X] T020 [US1] Run `uv run beastforge validate` over `library/**/*.yaml`, confirm all five creatures pass the closure gate, and correct any failing surface `rings`/`segments`/`radius`/`modifiers` values in-place.

**Checkpoint**: US1 is independently complete — the reported hollow-asset defect is fixed and proving tests exist.

---

## Phase 4: User Story 2 - Reusable, Anatomy-Neutral Part Library (Priority: P2)

**Goal**: Ship immutable versioned preset files, a deterministic registry, partial overrides, a pure resolver, a preset-discovery CLI, and two example assemblies (a mech and a limbless craft) built entirely from presets.

**Independent Test**: Author/load `iron-warden` and `hover-skiff`, run `validate` and `render` with no new geometry code, and confirm preset discovery lists 12 presets across three families.

### Tests for User Story 2 (required) ⚠️

- [X] T021 [P] [US2] Write registry unit tests in `tests/unit/test_part_registry.py` for sorted scans, exact-version lookup, duplicate `(name, version)`, and name/directory or version/filename mismatches.
- [X] T022 [P] [US2] Write override unit tests in `tests/unit/test_part_overrides.py` for partial merge, nested `radius`/`modifiers` targets, type/range errors, unknown keys, and nearest-name suggestions.
- [X] T023 [P] [US2] Write `tests/contract/test_preset_schema.py` validating every shipped `library/parts/*/*.yaml` against `specs/003-closed-part-library/contracts/preset.schema.json`.
- [X] T024 [P] [US2] Write `tests/contract/test_preset_replacement.py` proving a hand-authored surface and an equivalent preset resolve to the same closed part and control addresses (SC-010).
- [X] T025 [P] [US2] Write `tests/contract/test_parts_cli.py` validating `beastforge parts --json` against `specs/003-closed-part-library/contracts/parts.list.schema.json`.
- [X] T026 [P] [US2] Write `tests/integration/test_parts_render.py` covering `validate` and `render` of `iron-warden` and `hover-skiff`, manifest part facts, and both names appearing in the viewer catalog.
- [X] T027 [P] [US2] Write `tests/integration/test_parts_cli.py` covering human/JSON output, `--family`, `--version`, unknown name exit 4, invalid version/family exit 2, and missing `library/parts` exit 4.
- [X] T028 [P] [US2] Write defect-corpus part-resolution cases in `tests/defect_corpus/test_part_defects.py` for missing preset/version, bad binding, duplicate name, unknown override, and `recipe-empty-geometry`.

### Implementation for User Story 2

- [X] T029 [US2] Implement `src/beastforge/parts/registry.py`: sorted `root/*/*.yaml` scan, name/directory and version/filename agreement, duplicate `(name, version)` rejection, `load_yaml_document` + strict `PartPreset` parsing, canonical `sha256`, version lists, and non-fatal `warnings`.
- [X] T030 [P] [US2] Implement `src/beastforge/parts/overrides.py`: apply the closed canonical override vocabulary to a deep-copied preset surface, leaving omitted keys untouched and never replacing a nested object wholesale.
- [X] T031 [US2] Implement `src/beastforge/parts/resolve.py` (pure): exact pin lookup, `@slot` binding completeness/duplicate detection, override application, surface name/material substitution, control/auto slot substitution and name-based merge, and `ResolvedPart` construction (depends on T005, T029, T030).
- [X] T032 [US2] Implement preset/binding/override/name findings in `src/beastforge/validation/parts.py` (`part-preset-missing`, `part-preset-version-missing`, `part-binding-missing`, `part-binding-unknown`, `part-binding-duplicate`, `part-override-unknown`, `part-override-type`, `part-override-range`, `part-duplicate-name`, `preset-file-invalid`).
- [X] T033 [US2] Update `src/beastforge/pipeline.py` so `build_mesh`/`prepare` accept resolved parts and append their concrete `Surface` objects after recipe `surfaces` in deterministic order (depends on T031).
- [X] T034 [US2] Thread resolved part surfaces through `src/beastforge/validation/gate.py`, `src/beastforge/validation/surfaces.py`, `src/beastforge/validation/skin.py`, and `src/beastforge/validation/budgets.py`, using `parts[<name>]` paths for findings.
- [X] T035 [US2] Construct `PresetRegistry` and call `resolve_parts` from `src/beastforge/render.py` and `src/beastforge/validation/runner.py`, passing the resolved parts through `prepare` and `run_gate` (depends on T029, T031, T033, T034).
- [X] T036 [US2] Include resolved-part material references in `src/beastforge/texture/texforge_adapter.py::check_materials` and `src/beastforge/validation/determinism.py::check_manifest`.
- [X] T037 [US2] Update the canonical build digest in `src/beastforge/library.py` and `src/beastforge/pipeline.py` to `sha256(canonical_json({"recipe": document, "presets": [pinned preset documents]}))` when parts exist, preserving the existing recipe-only digest for recipes without parts (D13).
- [X] T038 [P] [US2] Ship the 12 minimal presets as `library/parts/<name>/1.0.0.yaml` exactly per research.md D15 (organic-leg, organic-torso, organic-head, organic-tail, mech-leg, mech-armor-plate, mech-turret, mech-piston, vehicle-hull-panel, vehicle-wing, vehicle-engine-bell, vehicle-rotor), including declared params, controls, and auto behaviours as data.
- [X] T039 [P] [US2] Author `library/other/iron-warden.yaml` from mechanical presets only (`category: other`), with one authored `patrol` clip, turret yaw, leg swing/lift, and piston translation controls; no instance-level auto yet.
- [X] T040 [P] [US2] Author `library/other/hover-skiff.yaml` from vehicle presets only (`category: other`), with hull, wings, engine bell, and rotor, and no authored clips (the rotor's preset auto is baked in US4); this must validate and render as a static asset under US2.
- [X] T041 [US2] Apply the core-clip rule `requires_core_clips = category != "other" and len(clips) > 0` in `src/beastforge/validation/clips.py` and `src/beastforge/validation/determinism.py::check_manifest` (data-model.md §4.1), so `other` and no-authored-clip assets do not fail `clip-missing-core`/`manifest-core-clip-missing`.
- [X] T042 [US2] Implement `src/beastforge/cli/parts.py` (noun command `parts [NAME]`, `--family`, `--version`, `--json`, quiet/verbose/no-color/no-interaction/dry-run, stdout results/stderr diagnostics, exit codes 0/2/3/4/1/130, sorted `(name, semver)` output) and register it in `src/beastforge/cli/app.py` (depends on T029).

**Checkpoint**: US2 is independently complete — a creator can assemble organic, mechanical, and vehicle assets from presets with no geometry-code changes.

---

## Phase 5: User Story 3 - Control Contracts for Articulated Parts (Priority: P3)

**Goal**: Resolve, validate, and publish named control channels (joint, axis, mode, range/unbounded, default, units) with unique addresses in manifest 1.1, and display them in a read-only viewer Controls tab.

**Independent Test**: Publish `iron-warden`, read `parts[].controls` without the recipe, and confirm every control maps to a real joint with a valid axis/range/units; invalid controls fail validation before generation.

### Tests for User Story 3 (required) ⚠️

- [X] T043 [P] [US3] Write control-rule unit tests in `tests/unit/test_controls.py` for unbounded normalization, unit-vector axis tolerance, mode/units matching, range/default consistency, slot substitution, duplicate names, and address uniqueness.
- [X] T044 [P] [US3] Write `tests/contract/test_manifest_v11.py` proving manifest 1.1 validates against the updated schema, `parts`/`source` are optional, and a 1.0 payload still parses via `read_manifest_compatible`.
- [X] T045 [P] [US3] Write `tests/integration/test_parts_controls.py` rendering `iron-warden` and asserting bounded rotation, bounded translation (`units: "m"`), and turret yaw controls reference real skeleton joints and unique addresses.
- [X] T046 [P] [US3] Write defect-corpus control cases in `tests/defect_corpus/test_control_defects.py` for duplicate control/address, missing joint, non-unit axis, unsupported mode, unit mismatch, and invalid range/default.

### Implementation for User Story 3

- [X] T047 [US3] Extend `src/beastforge/validation/parts.py` with control validation and findings (`part-control-duplicate`, `part-control-joint-missing`, `part-control-axis-invalid`, `part-control-mode-invalid`, `part-control-units-mismatch`, `part-control-range-invalid`, `part-control-default-out-of-range`, `part-control-address-duplicate`).
- [X] T048 [US3] Finish control resolution in `src/beastforge/parts/resolve.py`: substitute `@slot` joints, merge instance controls over preset controls by name, compute `"<part>/<control>"` addresses, and reject flattened duplicates (depends on T031, T047).
- [X] T049 [P] [US3] Extend `src/beastforge/model/manifest.py`: add `ManifestPart`, `ManifestControl`, optional `ManifestClip.source` defaulting to `"authored"`, add `"baseline"` to `GeneratorName`, default `Manifest.parts` to `[]`, and produce `schemaVersion: "1.1"`.
- [X] T050 [US3] Extend `src/beastforge/export/manifest.py` to publish resolved `parts` and their `controls`, set `source` on clips, and emit `schemaVersion: "1.1"`; leave `parts` absent only for 1.0-era fixtures (depends on T048, T049).
- [X] T051 [US3] Extend `src/beastforge/validation/determinism.py::check_manifest` to re-check control `joint`s against `skeleton.joints`, duplicate addresses, units/mode, and range/unbounded invariants, and to honor the `category: other`/empty-clip core rule.
- [X] T052 [P] [US3] Update `specs/001-procedural-creature-generator/contracts/schema/manifest.schema.json` additively: `clips.minItems` 5 → 0, add `"baseline"` to the generator enum, optional `clips[].source`, optional `parts[]` with `$defs.part` and `$defs.control`, with no required-field removals or renames.
- [X] T053 [P] [US3] Add a read-only Controls tab in `src/beastforge/viewer/static/lib/inspector.js` that renders `manifest.parts[].controls` (address, joint, axis, mode, range/unbounded, default, units) and shows "not declared" when `parts` is absent; first re-read the uncommitted event-play edits in `src/beastforge/viewer/static/app.js` and `inspector.js` and preserve them.

**Checkpoint**: US3 is independently complete — control contracts are discoverable from published metadata and the viewer, with no interactive controls added.

---

## Phase 6: User Story 4 - Automatic Part Motion (Priority: P4)

**Goal**: Declarative `breathe`/`bob`/`sway`/`rotate` behaviours bake deterministically into every authored clip, explicit clips win per joint, and an auto-only asset receives one synthesized `baseline` clip.

**Independent Test**: Build `hover-skiff` twice; the rotor rotates, the manifest contains a deterministic `baseline` clip with `source: "automatic"`, and GLB + manifest bytes are identical across runs.

### Tests for User Story 4 (required) ⚠️

- [X] T054 [P] [US4] Write `tests/unit/test_auto.py` for each behaviour's evaluated delta, declaration-order composition (translations sum, rotations multiply, scales multiply), explicit-clip precedence, and baseline duration (`max(2s, longest period)`, capped by `budgets.max_clip_ticks`, 2 s for rotate-only).
- [X] T055 [P] [US4] Write defect-corpus auto cases in `tests/defect_corpus/test_auto_defects.py` for duplicate auto name, missing joint, non-unit axis, non-positive amplitude/period, and zero rate.
- [X] T056 [P] [US4] Write `tests/determinism/test_parts_determinism.py` asserting two consecutive builds of `iron-warden` and `hover-skiff` produce byte-identical GLB and manifest files and a stable synthesized `baseline` clip.

### Implementation for User Story 4

- [X] T057 [US4] Implement `src/beastforge/anim/auto.py`: deterministic evaluation for `breathe`, `bob`, `sway`, and `rotate`, declaration-order composition, and the baseline-duration rule from data-model.md §6.
- [X] T058 [US4] Extend `src/beastforge/anim/bake.py` to build generator functions first, add composed auto functions only for joints the generator did not animate, synthesize `Clip(name="baseline", generator="baseline", loop=True, source="automatic")` when clips are empty and auto exists, and add `source` to `BakedClip`.
- [X] T059 [US4] Thread resolved auto into baking via `src/beastforge/pipeline.py::prepare`, publish `clips[].source` in `src/beastforge/export/manifest.py`, and keep deterministic clip ordering (including `baseline`) in `src/beastforge/export/gltf.py` (depends on T057, T058).
- [X] T060 [US4] Extend `src/beastforge/validation/parts.py` with auto validation and findings (`part-auto-duplicate`, `part-auto-joint-missing`, `part-auto-axis-invalid`, `part-auto-amplitude-invalid`, `part-auto-period-invalid`, `part-auto-rate-invalid`).
- [X] T061 [US4] Update `src/beastforge/render.py::_inventory` to build its clip/event inventory from `built.clips` so a synthesized `baseline` appears in `render --json`.
- [X] T062 [US4] Add one instance-level auto behaviour to `library/other/iron-warden.yaml` (for example a turret `sway`) to prove baked baseline into an authored-clip asset, and confirm `library/other/hover-skiff.yaml` synthesizes `baseline` from the rotor preset's `rotate`.

**Checkpoint**: US4 is independently complete — an asset whose only motion is automatic animates without a hand-authored clip, deterministically.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, ADRs, regenerated visual references, and full-suite verification across stories.

- [X] T063 [P] Regenerate showroom reference frames and the gallery (`uv run beastforge showroom --accept`) into `showroom/reference/` and update `docs/showroom-gallery.md`; then verify `uv run beastforge showroom` passes for all five creatures.
- [X] T064 [P] Update `docs/architecture.md` with the closed-geometry pipeline, per-part closure gate, preset resolution, and automatic baseline.
- [X] T065 [P] Update `docs/api.md` with manifest 1.1 `parts`, `controls`, `clips[].source`, and the closure finding codes.
- [X] T066 [P] Update `docs/recipes.md` with `parts[]`, `@slot` binding, canonical overrides, neutral surface kinds, controls, and auto behaviours.
- [X] T067 [P] Update `docs/development.md` with the preset-version, golden-hash, and showroom regeneration workflow.
- [X] T068 [P] Update `docs/cheatsheet-cli.md` with a `## parts` section and "Most useful" rows mirroring the command tree.
- [X] T069 [P] Update `README.md` and `SKILL.md` with the closed-part contract and preset library.
- [X] T070 [P] Update `CHANGELOG.md` with Unreleased Added/Changed/Fixed entries for closure, presets, controls, auto motion, and regenerated goldens.
- [X] T071 [P] Add ADRs 261116-7 (closed-solid part contract), 261116-8 (versioned anatomy-neutral presets), and 261116-9 (control contracts + baked automatic motion) under `_ai/technical_decisions/`.
- [X] T072 [P] Add the `003-closed-part-library` row to the index in `specs/README.md`.
- [X] T073 Run `uv run pytest`, `uv run pytest -m slow`, `uv run beastforge validate`, `uv run beastforge showroom`, `uv run ruff check`, and `uv run mypy`; fix any regression across `src/beastforge/`, `tests/`, `library/`, and `docs/`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. Blocks US2, US3, and US4. US1 needs only `T004` (finding codes) and the shared fixtures, so the closure story may begin while T005–T008 are still in progress if the team is split.
- **User Stories (Phases 3–6)**: Each depends on Foundational; otherwise US1 is independent, US3 builds on US2's models/resolver, and US4 builds on US2's models/resolver. Recommended order is US1 → US2 → US3 → US4.
- **Polish (Phase 7)**: Depends on all desired user stories being complete (T063 and T073 require the regenerated assets and final code).

### User Story Dependencies

- **US1 (P1)**: Depends on `T004` and Setup only. Deliverable MVP.
- **US2 (P2)**: Depends on Foundational. No dependency on US1 beyond the closure gate accepting newly appended part surfaces.
- **US3 (P3)**: Depends on US2's `model/parts.py`, registry, resolver, and shipped presets. Publishes data already present in preset files.
- **US4 (P4)**: Depends on US2 (resolved parts/auto) and shares `validation/parts.py` with US3; the auto-specific validation and baking do not require control publication to be finished.

### Within Each User Story

- Tests are written first and must fail before implementation.
- Models/shared helpers → resolver/assembler → pipeline/gate wiring → CLI/viewer surfaces.
- Story checkpoint must pass before moving to the next priority.

### Parallel Opportunities

- Setup: `T002` and `T003` in parallel after `T001`.
- Foundational: `T005`, `T006`, `T007` in parallel; `T008` after `T006`.
- US1: `T009`–`T012` in parallel (four distinct test files); `T015`, `T018`, `T019` can proceed alongside `T013`/`T014` where files differ.
- US2: all eight test files (`T021`–`T028`) in parallel; `T030`, `T038`, `T039`, `T040`, `T042`, `T052` can run alongside the resolver/gate work once their prerequisites exist.
- US3: `T043`–`T046` in parallel; `T049`, `T052`, `T053` are independent of the control validation/resolution tasks.
- US4: `T054`–`T056` in parallel; `T057`, `T060`, `T061` touch distinct files.
- Polish: nearly all documentation tasks (`T063`–`T072`) are parallel; `T073` runs last.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 test tasks together (distinct files):
Task: "Write closure-analyzer unit tests in tests/unit/test_closure.py"
Task: "Write the no-double-sided contract test in tests/contract/test_no_double_sided.py"
Task: "Write the gameplay-facts snapshot test in tests/contract/test_gameplay_facts.py"
Task: "Write closure defect-corpus cases in tests/defect_corpus/test_closure_defects.py"
```

## Parallel Example: User Story 2

```bash
# Launch the preset data and CLI work in parallel after the models exist:
Task: "Ship the 12 minimal presets under library/parts/<name>/1.0.0.yaml"
Task: "Author library/other/iron-warden.yaml"
Task: "Author library/other/hover-skiff.yaml"
Task: "Implement src/beastforge/cli/parts.py and register it"
Task: "Implement src/beastforge/parts/overrides.py"
```

## Parallel Example: User Story 3

```bash
# Launch the independent contract/viewer work together:
Task: "Extend src/beastforge/model/manifest.py with parts/controls/source"
Task: "Update specs/001-.../contracts/schema/manifest.schema.json additively"
Task: "Add the read-only Controls tab in src/beastforge/viewer/static/lib/inspector.js"
```

## Parallel Example: User Story 4

```bash
# Launch the auto tests and independent implementation files together:
Task: "Write tests/unit/test_auto.py"
Task: "Write tests/defect_corpus/test_auto_defects.py"
Task: "Write tests/determinism/test_parts_determinism.py"
Task: "Implement src/beastforge/anim/auto.py"
Task: "Extend src/beastforge/validation/parts.py with auto validation"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete the parts of Phase 2 required by US1 (`T004`) and the shared models needed later (`T005`–`T008`).
3. Complete Phase 3: US1 closure.
4. **STOP and VALIDATE**: run `tests/unit/test_closure.py`, `tests/contract/test_no_double_sided.py`, `tests/contract/test_gameplay_facts.py`, `uv run beastforge validate`, and orbit the five creatures in the viewer.
5. Deploy/demo the fixed, closed library.

### Incremental Delivery

1. Setup + Foundational → shared models and vocabulary ready.
2. US1 → closed creatures (MVP), regenerate goldens.
3. US2 → presets + mech/craft examples + `parts` CLI.
4. US3 → published controls + viewer Controls tab.
5. US4 → automatic motion + synthesized baseline.
6. Polish → docs, ADRs, showroom, full validation.

### Parallel Team Strategy

With multiple developers, complete Setup + Foundational together, then:

- Developer A: US1 closure and golden regeneration.
- Developer B: US2 preset models/registry/resolution and example assemblies.
- Developer C: US3 manifest publication and viewer Controls tab (after US2's models land).
- Developer D: US4 auto evaluation/baking and determinism proofs (after US2's resolver lands).

---

## Notes

- `[P]` tasks touch different files and have no incomplete-task dependency.
- `[Story]` labels map every story-phase task to its user story for traceability.
- Tests are mandatory here because research.md D18 and plan.md define them as the proof of FR-001, FR-003, FR-010, FR-014–FR-016, SC-003, SC-005, SC-007, and SC-010.
- Commit after each task or logical group; never commit regenerated binaries or secrets.
- Stop at every checkpoint to validate the story independently before moving on.
- The worktree may contain pre-existing uncommitted event-play edits in `src/beastforge/viewer/static/app.js` and `src/beastforge/viewer/static/lib/inspector.js`; preserve them when adding the Controls tab.
