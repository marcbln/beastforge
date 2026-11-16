# Phase 0 Research: Closed Part Library

**Feature**: `003-closed-part-library` · **Date**: 2026-11-16
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

This file resolves every decision the spec and existing contracts leave open. No
`NEEDS CLARIFICATION` remains. Each decision records what was chosen, why, and
what else was considered.

---

## D1 — What "closed" means for a part

**Decision**: A generated part passes closure when **all** of the following hold
for that part's triangles:

1. Every undirected edge has exactly two incident triangles (no boundary edges,
   no non-manifold edges shared by three or more).
2. The two triangles incident to an edge traverse that edge in opposite
   directions (consistent winding).
3. The part's signed volume is positive (outward orientation).
4. No triangle has repeated vertex indices or area at or below a scale-relative
   epsilon.

Self-intersection and duplicate-face detection are **not** performed. Overlap
between different parts is allowed; the assembled asset is not required to be one
manifold.

**Rationale**: This is exactly the clarification in the spec and matches what a
viewer with backface culling needs: no hole to see through and no inward-facing
face that disappears. It is also cheap and deterministic (`numpy` arithmetic
only) and does not require a mesh library.

**Alternatives considered**:
- Full `trimesh.is_watertight` + self-intersection: `trimesh` is a dev-only
  dependency; self-intersection is explicitly out of scope.
- Whole-body manifold: rejected by FR-002 (parts may overlap at joints).
- Visual-only check (render and inspect): non-deterministic and cannot produce a
  stable validation finding.

---

## D2 — How to cap swept parts

**Decision**: Enable `caps=True` for every `sweep_surface` call used by
`limb-tube`/`swept-solid` and `torso-shell`/`shell`. `rigid_surface` already caps
and keeps its implementation. The existing cap code adds one centre vertex at
each path endpoint and a triangle fan to the first/last ring. The ring is planar
and star-shaped about its centre, so the fan is a valid closed end.

**Rationale**: The cap code already exists and is deterministic. Reusing it keeps
one construction path, preserves joint weights and UVs, and adds only
`2 * segments` triangles per swept part. No new geometry algorithm is needed.

**Alternatives considered**:
- Per-surface boolean union with the torso: out of scope (no CSG) and would
  destroy construction-bound weights.
- Triangulated quad caps without a centre vertex: still valid, but the existing
  fan code is simpler and already tested by rigid parts.
- Leaving torso ends open and hiding them inside limbs: fails the closure check
  for assets where the torso end is exposed (e.g. a limbless craft hull).

---

## D3 — Neutral surface kinds and anatomy neutrality

**Decision**: Extend the `surface.kind` vocabulary with `swept-solid` and `shell`
as neutral public names. `limb-tube` and `torso-shell` remain accepted aliases and
map to the same builders. Presets use the neutral names. No validation rule may
require a torso, a limb, a chain, or a family structure.

**Rationale**: The spec requires the core library to be anatomy-neutral. The
existing internal names are creature-biased even though the construction is
generic. Aliases keep every existing recipe valid while giving mechanical and
vehicle authors neutral vocabulary.

**Alternatives considered**:
- Rename `limb-tube`/`torso-shell` outright: breaks existing recipes and the
  001 grammar contract.
- Introduce new geometry code for "hull" or "plate": unnecessary; `swept-solid`
  and `rigid-part` already cover them.
- Encode family in the recipe: rejected; the family is descriptive only.

---

## D4 — Preset storage, versioning, and immutability

**Decision**: Store one immutable preset version per file:

```
library/parts/<preset-name>/<MAJOR.MINOR.PATCH>.yaml
```

The file's `name` must equal the directory name; its `version` must equal the
filename stem. The registry scans all versions in sorted order and resolves an
instance by exact `(name, version)`. Changing a preset requires adding a new
version file; existing version files are never edited. A missing version is a
validation error that lists available versions.

**Rationale**: Exact version pinning plus immutable files gives deterministic
regeneration without a lockfile or database. Old assemblies continue to resolve
after a preset evolves. A single file overwritten in place would silently change
old assemblies, violating the spec's determinism requirement.

**Alternatives considered**:
- One file per preset with a `versions:` list: works, but grows unwieldy and makes
  diffs noisy.
- One current file plus git history: requires checking out old commits at build
  time, which breaks offline/deterministic operation.
- Floating major/minor ranges: non-deterministic and contradicts the spec.

---

## D5 — Preset geometry template and `@slot` bindings

**Decision**: A preset's `surface` is a normalized `Surface`-shaped template whose
`bones` list contains `@slot` names rather than concrete joints. An instance
supplies a `bind` mapping from slot name (without `@`) to an existing bone. Every
slot referenced by the surface, controls, or auto behaviours must be bound; extra
bindings are errors. A rigid part binds one `@mount` slot.

**Rationale**: Presets must be reusable across different skeletons. Slot names
make the indirection explicit, and the `@` prefix cannot collide with the recipe
identifier grammar (which forbids `@`). Binding is the only skeleton-specific
input an instance needs.

**Alternatives considered**:
- Preset uses positional bone order: brittle and unreadable.
- Preset references concrete joints: not reusable.
- Instance lists bones in order with no names: cannot validate controls or auto
  joints or support multi-surface presets.

---

## D6 — Canonical override vocabulary and partial merge

**Decision**: Preset parameters use a closed, flat vocabulary of override keys:

```
radius-start, radius-end, rings, segments, blend,
taper-start, taper-end, twist,
noise-amplitude, noise-frequency, noise-seed,
squash-x, squash-y, squash-z, scale-x, scale-y, scale-z
```

A preset's `params` list declares the allowed keys, types (`float`/`int`), ranges,
optional units, and descriptions. Defaults are read from the preset's surface
template (the surface is the source of truth). An instance's `overrides` mapping
is deep-merged key-by-key into the preset surface; omitted keys keep the preset
value. Unknown keys are errors with a nearest-name suggestion; type/range errors
are findings.

**Rationale**: Flat keys make partial overrides unambiguous, JSON-serializable,
and easy to validate. A preset can expose only the knobs its shape actually uses
(e.g. a rigid plate exposes `rings`, `segments`, `scale-*`, but not `taper-*`).
Keeping defaults in the surface avoids duplicating numbers and guarantees the
preset is buildable before any override.

**Alternatives considered**:
- Nested override objects (`{radius: {end: 0.05}}`): Pydantic would require a
  second partial model for every nested field; more code for no user benefit.
- String placeholders (`"${radius-end}"`): untyped, easy to misuse, and hard to
  validate before substitution.
- Free-form field paths: turns presets into a second YAML patch language.

---

## D7 — Control-channel contract

**Decision**: A control declares:

- `name` — unique within the part;
- `joint` — `@slot` in a preset, or a concrete bone in an instance;
- `axis` — exactly three finite numbers forming a unit vector;
- `mode` — `rotation` or `translation`;
- `range` — `{min, max}` with `min <= max`, or omitted when `unbounded: true`;
- `unbounded` — boolean, required in the normalized model (defaults `false` if a
  range is present, `true` if no range is given);
- `default` — finite number, inside the range when bounded;
- `units` — explicit string `"deg"` for rotation or `"m"` for translation.

The published address is `"<part-name>/<control-name>"`. Addresses are unique
across the asset because part names and control names are unique.

**Rationale**: This is the minimum complete description a downstream consumer
needs to drive a joint without inspecting the recipe. Explicit units and a
mode/units match rule prevent the common degrees-versus-metres ambiguity. A unit
vector axis is more expressive than `x|y|z` and still easy to validate.

**Alternatives considered**:
- Named axis (`x`, `y`, `z`): simpler but cannot express a diagonal hinge.
- Separate `min`/`max` fields plus an `unbounded` flag: redundant and easier to
  make inconsistent.
- Implicit units from mode: the spec requires units stored as explicit strings.
- Runtime control API: the viewer is read-only in this release.

---

## D8 — Automatic-behaviour schema and composition

**Decision**: Automatic behaviours are a discriminated union:

- `breathe` — `joint`, `amplitude` (scale ratio), `period` (seconds), `phase`
  (degrees);
- `bob` — `joint`, `axis`, `amplitude` (metres), `period`, `phase`;
- `sway` — `joint`, `axis`, `amplitude` (degrees), `period`, `phase`;
- `rotate` — `joint`, `axis`, `rate` (degrees/second), `phase` (degrees initial
  angle).

`period` must be `> 0`; `rate` must be non-zero; `amplitude` must be `> 0` for
periodic kinds; axes and joints are validated like controls. Multiple behaviours
on one joint compose in declaration order: translations sum, rotations multiply as
quaternions, scales multiply component-wise.

**Rationale**: The four kinds cover the spec's examples (breathing, bobbing,
swaying, constant rotation) with a small closed registry. A discriminated union
keeps the YAML readable and the Pydantic model strict. Fixed composition order
makes the bake deterministic and reviewable.

**Alternatives considered**:
- A generic `{mode, frequency, amplitude, phase}` model: cannot express the
  difference between a scale pulse and a rotation cleanly.
- One behaviour per joint: unnecessarily restrictive; the spec says "one or more".
- Runtime descriptors: ADR 261114-4 bakes animation at generation time.

---

## D9 — Baseline baking, precedence, and synthesized clip

**Decision**: For each authored clip, the baker builds the generator's per-joint
functions first, then adds auto functions **only for joints absent from that
map**. If `recipe.clips` is empty and auto behaviours exist, the baker synthesizes
one clip named `baseline`, with `generator: "baseline"`, `source: "automatic"`,
`loop: true`, and a deterministic duration equal to the longest periodic
behaviour's period (minimum 2 s, capped by `budgets.max_clip_ticks`). If there are
only constant rotations, the duration is 2 s.

**Rationale**: The spec requires auto motion baked into every clip, explicit clips
to win on the same joint, and a synthesized clip when no clips exist. Per-joint
precedence is the narrowest interpretation of "explicit clip takes precedence".
A deterministic duration derived from the behaviour keeps the clip discoverable
and reproducible without a per-asset authoring knob.

**Alternatives considered**:
- Blend auto and explicit motion additively on the same joint: violates FR-016.
- Require an authored clip for auto assets: contradicts FR-015 and the craft
  scenario.
- Fixed 10 s baseline/CMS of all period ticks: more complex and not required;
  `max(period)` is deterministic and sufficient.
- Expose auto descriptors in the manifest: the spec keeps them authoring-side;
  only the synthesized clip is published.

---

## D10 — Manifest 1.1 additive fields

**Decision**: Bump the manifest to `schemaVersion: "1.1"` and add:

- `clips[].source`: `"authored"` or `"automatic"` (defaults to `"authored"` when
  absent);
- `clips[].generator` may be `"baseline"`;
- `parts[]`: `{name, preset, presetVersion, presetSha256, family, controls[]}`;
- `controls[]`: `{address, name, joint, axis, mode, unbounded, range?, default,
  units}`.

`parts` is optional in the schema and defaults to `[]` in the producer model.
`read_manifest_compatible` remains major-strict/minor-tolerant. The 1.0 schema
document is updated in place with these additive properties because there is one
canonical manifest schema in the repository; a 1.0 document without them remains
valid.

**Rationale**: The manifest is the published consumer contract. Controls must be
discoverable without the recipe. A minor bump preserves existing consumers;
optional fields preserve 1.0 read compatibility. `source` makes the synthesized
clip self-describing rather than relying on a reserved name alone.

**Alternatives considered**:
- Manifest 2.0: unnecessarily breaks every consumer; all changes are additive.
- Separate controls sidecar file: adds a third artifact and a new delivery
  contract; the manifest is already the gameplay contract.
- Put controls in the GLB extras: harder to consume and not part of the existing
  manifest contract.

---

## D11 — Core clips for anatomy-neutral assets

**Decision**: Core clips (`idle`, `locomotion`, `attack`, `hurt`, `death`) are
required only when `meta.category != "other"` **and** at least one clip is
authored. `category: "other"` assets may author any clip set or none. An asset
with no authored clips is valid when auto behaviours synthesize a baseline; an
asset with neither clips nor auto behaviours is still valid (it is a static
prop) but the manifest will have an empty clips array.

**Rationale**: This preserves the existing five creatures' contract exactly, lets
mechanical/vehicle assets omit creature-specific clips, and allows an auto-only
creature. It uses the existing category taxonomy instead of adding a new
anatomy/asset-type field, and it never requires a torso or limb.

**Alternatives considered**:
- Require core clips for every asset: impossible for a limbless craft and
  contradicts the "no authored clips" edge case.
- Never require core clips: silently weakens the 001 contract for existing
  creature recipes.
- Add `meta.assetType`: workable, but a new field is unnecessary when `other`
  already exists and is semantically correct for non-creature assets.

---

## D12 — Viewer Controls tab and culling

**Decision**: Add a read-only `Controls` tab to `inspector.js` that reads
`manifest.parts[].controls` and renders a table of address, joint, axis, mode,
range/unbounded, default, and units. Missing `parts` reads "not declared". The
viewer never adds `THREE.DoubleSide`; the GLB writer never emits `doubleSided`.
No interactive rig controls are added.

**Rationale**: FR-017 asks the viewer to display control contracts alongside the
manifest and animation views. A tab matches the existing UI. Keeping the viewer
read-only and culling on satisfies FR-003 and SC-008.

**Alternatives considered**:
- Interactive sliders driving joints: out of scope for this release.
- Show controls only in the raw manifest dump: does not satisfy "display".
- Two-sided materials to hide new caps: explicitly forbidden.

---

## D13 — Determinism, build digest, and cache

**Decision**: The canonical build digest for a recipe becomes

```
sha256(canonical_json({"recipe": <document>, "presets": [<pinned preset documents>]}))
```

when the recipe has `parts`; for recipes without `parts` it stays exactly
`recipe_digest(document)`. This digest remains `provenance.recipeSha256`, so the
viewer cache key and `_verify_manifest` continue to work. `parts[].presetSha256`
exposes each preset's content hash, and the digest changes when a pinned preset
document changes.

**Rationale**: Determinism must include the actual preset content, not only the
recipe's textual reference. Reusing the existing digest field avoids a second
cache key and a catalog schema change. Recipes without presets are byte-for-byte
unaffected.

**Alternatives considered**:
- Keep the recipe-only digest and rely on version discipline: simpler, but a
  silently edited preset version would produce different bytes under the same
  cache key.
- Add a separate `buildSha256` and change the cache schema: more correct naming,
  but a larger ripple through the catalog/cache/manifest contract.
- Lockfile of preset hashes: extra artifact and process; the immutable-version
  policy plus content digest is sufficient.

---

## D14 — Validation ordering and findings

**Decision**: The gate order becomes:

1. recipe metadata and declared params;
2. preset registry resolution and part expansion (bindings, overrides, controls,
   auto);
3. skeleton;
4. surfaces (raw + resolved part surfaces, with per-surface paths);
5. mesh construction;
6. skin weights/rigid bindings;
7. **closure** (per surface range);
8. clips and hooks;
9. materials;
10. budgets;
11. determinism and manifest referential integrity.

New finding codes:

```
recipe-empty-geometry
preset-file-invalid
part-preset-missing
part-preset-version-missing
part-duplicate-name
part-binding-missing
part-binding-unknown
part-binding-duplicate
part-override-unknown
part-override-type
part-override-range
part-control-duplicate
part-control-joint-missing
part-control-axis-invalid
part-control-mode-invalid
part-control-units-mismatch
part-control-range-invalid
part-control-default-out-of-range
part-control-address-duplicate
part-auto-duplicate
part-auto-joint-missing
part-auto-axis-invalid
part-auto-amplitude-invalid
part-auto-period-invalid
part-auto-rate-invalid
surface-open
surface-non-manifold
surface-degenerate
```

`surface-winding-invalid` is reused for inconsistent winding or non-positive
signed volume. `surface-self-intersection` remains in the vocabulary as reserved
but is no longer emitted.

**Rationale**: Parts must resolve before surfaces/skin/mesh so downstream checks
see one ordered surface list. Closure runs after mesh construction and before
materials/budgets so a structurally invalid asset fails early with a precise
location. Stable codes keep the CLI self-correction loop working.

**Alternatives considered**:
- Reuse `surface-empty` for all closure failures: loses the actionable distinction
  between an open boundary, a non-manifold edge, and a degenerate cap.
- Run closure inside `check_skin`: mixes mesh-topology and skin-weight concerns
  and makes the defect corpus harder to target.
- Check closure on the merged whole mesh: violates FR-002 (parts may overlap).

---

## D15 — Minimal preset set and example assemblies

**Decision**: Ship these presets (all with `version: "1.0.0"`):

| Preset | Family | Kind | Slots | Controls | Auto |
|--------|--------|------|-------|----------|------|
| `organic-leg` | organic | swept-solid | upper, lower, foot | swing, lift (rotation) | — |
| `organic-torso` | organic | shell | spine-1, spine-2, spine-3 | — | breathe |
| `organic-head` | organic | swept-solid | skull, jaw | jaw (rotation) | — |
| `organic-tail` | organic | swept-solid | base, mid, tip | sway (rotation) | sway |
| `mech-leg` | mechanical | swept-solid | hip, knee, ankle | swing, lift (rotation) | — |
| `mech-armor-plate` | mechanical | rigid-part | mount | — | — |
| `mech-turret` | mechanical | rigid-part | mount | yaw (rotation) | — |
| `mech-piston` | mechanical | rigid-part | mount | extend (translation) | — |
| `vehicle-hull-panel` | vehicle | rigid-part | mount | — | — |
| `vehicle-wing` | vehicle | swept-solid | root, tip | sweep (rotation) | — |
| `vehicle-engine-bell` | vehicle | swept-solid | mount | pitch (rotation) | — |
| `vehicle-rotor` | vehicle | rigid-part | mount | spin (unbounded rotation) | rotate |

Ship two examples:

- `library/other/iron-warden.yaml` — mech assembled only from mechanical presets;
  turret yaw, leg swing/lift, piston translation; at least one auto behaviour.
- `library/other/hover-skiff.yaml` — limbless craft assembled only from vehicle
  presets; hull, wings, engine, rotor; no authored clips; rotor auto-rotation
  synthesizes a `baseline` clip.

**Rationale**: The set covers organic, mechanical, and vehicle families; rotation
and translation controls; bounded and unbounded ranges; all four auto kinds; and
assets with no torso, no limbs, and no clips. It is the smallest set that proves
SC-004, SC-005, SC-006, and SC-009.

**Alternatives considered**:
- Presets only, no example assemblies: cannot demonstrate end-to-end validation,
  rendering, and viewer controls.
- A larger library: violates "minimal preset set" and increases golden/showroom
  surface area.
- One generic preset per family: cannot represent a leg, a panel, and a rotor.

---

## D16 — Preset discovery CLI

**Decision**: Add `beastforge parts [NAME]` with `--family`, `--version`, and the
global `--json` flag. Without a name it lists all preset versions; with a name it
lists that preset's versions (or one version when `--version` is given). Output
includes name, family, version, description, path, params, controls, auto summary,
and `presetSha256`. Unknown names exit 4; malformed presets exit 3.

**Rationale**: A reusable library needs discovery. The command mirrors the
existing `beastforge params NAME` noun pattern and reuses the established global
flags/streams/exit codes. JSON output gives agents a stable surface.

**Alternatives considered**:
- No CLI: authors must read the filesystem; agents lose a discoverable surface.
- Extend `beastforge list --parts`: mixes two record types in one command and
  complicates the existing `library.list` schema.
- A remote registry: out of scope; offline only.

---

## D17 — Backward compatibility and migration

**Decision**:

- Existing recipes remain valid; `surfaces` and `clips` are still accepted, and
  `limb-tube`/`torso-shell` remain aliases.
- Existing five creatures gain only closed caps and additive manifest fields;
  joints, clips, events, sockets, volumes, phases, materials, units, and axes are
  unchanged.
- `Manifest` 1.0 documents remain readable; `parts` defaults to `[]` and `source`
  defaults to `authored`.
- Goldens (`tests/golden/library.sha256`) and showroom references are regenerated
  and committed as part of this change.
- A recipe can migrate one surface at a time: replace a `surfaces[]` entry with a
  `parts[]` entry of the same `name` and equivalent preset overrides; control
  addresses are added without renaming existing gameplay facts.
- New ADRs record the closure, preset, and auto-motion contracts; the 003 spec
  directory is added to `specs/README.md`.

**Rationale**: The spec explicitly allows incremental preset adoption and requires
existing gameplay facts to survive regeneration. Additive schema changes keep
consumers working while the goldens acknowledge the byte change.

**Alternatives considered**:
- Big-bang migration of all five creatures to presets: higher risk and not
  required; the spec says presets are adopted incrementally.
- Manifest 2.0: breaks consumers for additive changes.
- Editing old golden hashes silently: the plan requires explicit regeneration and
  a gameplay-facts snapshot.

---

## D18 — Test strategy

**Decision**:

- **Unit**: closure analyzer on hand-built open/closed/non-manifold/mis-wound/
  degenerate meshes; preset registry versions and duplicate detection; override
  merge/type/range; auto composition and baseline duration; control axis/range/
  units/address rules.
- **Contract**: every shipped preset validates against `preset.schema.json`; the
  manifest 1.1 document validates and a 1.0 payload still parses; `parts --json`
  validates against `parts.list.schema.json`; emitted GLB materials never set
  `doubleSided`; the viewer's authored JS never selects `DoubleSide`; a pinned
  `gameplay_facts.json` proves the five creatures' facts are unchanged; and a
  replacement fixture proves a hand-authored part can become an equivalent preset
  without losing closure or control addresses (SC-010).
- **Integration**: `validate` over the whole library; `render` for `iron-warden`
  and `hover-skiff`; manifests contain controls and the synthesized baseline;
  viewer catalog includes the examples; `parts` human and JSON output; unknown
  preset exit 4.
- **Defect corpus**: open end, non-manifold edge, degenerate cap, inward winding,
  duplicate control, duplicate address, missing preset, missing version, bad
  binding, unknown override, invalid axis/range/units, auto period/rate errors.
- **Determinism**: two consecutive builds of a preset assembly are byte-identical
  (GLB + manifest) and the baseline clip is stable; the existing 100-run and
  two-working-directory tests continue to pass.
- **Golden/showroom**: `uv run pytest -m slow` after regenerating
  `tests/golden/library.sha256`; `uv run beastforge showroom --accept` for the
  five creatures.

**Rationale**: Each layer targets a distinct failure mode: the analyzer's
geometry math, the preset contract, the end-to-end build, stable findings, and
byte identity. Keeping closure unit tests independent of the library recipes lets
bugs be localized; the integration tests prove SC-004/SC-009.

**Alternatives considered**:
- Rely on `trimesh` for closure tests: useful as an independent oracle, but it
  does not test the runtime gate and is dev-only.
- Only golden tests: too coarse to localize an open edge or a bad control.
- Browser tests by default: slower and environment-dependent; the existing opt-in
  smoke test remains unchanged.
