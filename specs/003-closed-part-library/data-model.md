# Phase 1 Data Model: Closed Part Library

**Feature**: `003-closed-part-library` · **Date**: 2026-11-16
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) ·
**Research**: [research.md](./research.md)

All models are Pydantic v2 `StrictModel` variants (`extra="forbid"`) unless stated
otherwise. YAML is inert data (`yaml.safe_load` only). Names use the existing
recipe identifier grammar unless a field explicitly says otherwise.

---

## 1. Part Preset (new, authoring-side)

One immutable preset version per file at
`library/parts/<preset-name>/<version>.yaml`.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `name` | `str` | yes | identifier; equals the parent directory name |
| `family` | `organic \| mechanical \| vehicle` | yes | descriptive only; never constrains structure |
| `version` | `str` | yes | `^\d+\.\d+\.\d+$`; equals the filename stem |
| `description` | `str` | yes | non-empty |
| `surface` | `PresetSurface` | yes | normalized surface template with `@slot` bones |
| `params` | `list[PresetParam]` | no (`[]`) | allowed override keys; defaults derive from `surface` |
| `controls` | `list[PresetControl]` | no (`[]`) | reusable control channels |
| `auto` | `list[AutoBehaviour]` | no (`[]`) | reusable automatic behaviours |
| `path` | `str` | derived | project-relative file path (not in the YAML) |
| `sha256` | `str` | derived | SHA-256 of the canonical parsed preset document |

### 1.1 `PresetSurface`

Same shape as the existing `Surface` model, with these differences:

- `kind` is one of `swept-solid`, `shell`, `rigid-part` (neutral names).
- `bones` entries are `@slot` names (e.g. `@upper`), not concrete bones.
- `rigid_bone` may also be `@slot` for `rigid-part`.
- `name` is omitted; the instance's part name becomes the concrete surface name.
- `material` is an optional material name resolved in the consuming recipe.

```yaml
surface:
  mode: sweep
  kind: swept-solid
  bones: ["@upper", "@lower", "@foot"]
  rings: 10
  segments: 8
  radius: {start: 0.12, end: 0.05}
  blend: 0.25
  modifiers:
    taper: {start: 1.0, end: 0.9}
    squash: [1.0, 1.0, 1.0]
  material: hide
```

### 1.2 `PresetParam`

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `name` | canonical override key | yes | one of the closed vocabulary in §1.3 |
| `type` | `float \| int` | yes | `int` only for `rings`, `segments`, `noise-seed` |
| `min` | `float` | no | finite; `min <= max` |
| `max` | `float` | no | finite; `min <= max` |
| `unit` | `m \| deg \| ratio \| count` | no | descriptive; does not change the value |
| `description` | `str` | yes | non-empty |

The param's **default** is read from the preset surface at that key. A preset must
only declare params its surface can apply (for example, `taper-start` requires a
`modifiers.taper` object).

### 1.3 Canonical override vocabulary

| Key | Surface field | Type |
|-----|---------------|------|
| `radius-start` | `radius.start` (or first list entry) | float |
| `radius-end` | `radius.end` (or last list entry) | float |
| `rings` | `rings` | int |
| `segments` | `segments` | int |
| `blend` | `blend` | float |
| `taper-start` | `modifiers.taper.start` | float |
| `taper-end` | `modifiers.taper.end` | float |
| `twist` | `modifiers.twist` | float |
| `noise-amplitude` | `modifiers.radial_noise.amplitude` | float |
| `noise-frequency` | `modifiers.radial_noise.frequency` | float |
| `noise-seed` | `modifiers.radial_noise.seed` | int |
| `squash-x` / `squash-y` / `squash-z` | `modifiers.squash[i]` | float |
| `scale-x` / `scale-y` / `scale-z` | `modifiers.scale[i]` | float |

### 1.4 `PresetControl`

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `name` | `str` | yes | identifier; unique within the preset |
| `joint` | `str` | yes | `@slot` in a preset; concrete bone in an instance |
| `axis` | `[float, float, float]` | yes | finite, non-zero, unit length (tolerance `1e-6`) |
| `mode` | `rotation \| translation` | yes | closed enum |
| `range` | `{min: float, max: float}` | conditional | required when `unbounded` is false; `min <= max` |
| `unbounded` | `bool` | no (`false` with range, `true` without) | cannot be true with a range |
| `default` | `float` | yes | finite; inside the range when bounded |
| `units` | `deg \| m` | yes | `rotation` requires `deg`; `translation` requires `m` |

### 1.5 `AutoBehaviour` (discriminated union on `kind`)

| Kind | Fields | Semantics |
|------|--------|-----------|
| `breathe` | `joint`, `amplitude` (ratio > 0), `period` (s > 0), `phase` (deg, default 0) | uniform scale pulse on the joint |
| `bob` | `joint`, `axis`, `amplitude` (m > 0), `period` (s > 0), `phase` | translation along `axis` |
| `sway` | `joint`, `axis`, `amplitude` (deg > 0), `period` (s > 0), `phase` | rotation about `axis` |
| `rotate` | `joint`, `axis`, `rate` (deg/s, non-zero), `phase` (deg initial) | unbounded constant rotation |

Every variant requires a valid `joint` and, except `breathe`, a valid unit `axis`.
`name` is an identifier, unique within the part, and is used only for
preset/instance merging; it is not published in the manifest.

---

## 2. Part Instance (new, recipe-side)

A `Recipe.parts[]` entry binds a preset version to concrete joints.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `name` | `str` | yes | identifier; unique across the asset (surfaces + parts) |
| `preset` | `str` | yes | identifier; must exist in the registry |
| `preset_version` | `str` | yes | exact `MAJOR.MINOR.PATCH`; must exist |
| `bind` | `dict[str, str]` | yes | slot name → existing bone; every `@slot` covered; no extras |
| `overrides` | `dict[str, float \| int]` | no (`{}`) | keys must be declared by the preset `params`; type/range checked |
| `material` | `str \| null` | no (`null`) | overrides the preset surface material; must be declared in `materials[]` |
| `controls` | `list[PresetControl]` | no (`[]`) | full definitions; same-name entries replace the preset control |
| `auto` | `list[AutoBehaviour]` | no (`[]`) | full definitions; same-name entries replace the preset behaviour |

```yaml
parts:
  - name: front-left-leg
    preset: organic-leg
    preset_version: "1.0.0"
    bind: {upper: upper-fl, lower: lower-fl, foot: foot-fl}
    overrides: {radius-end: 0.045}
    material: hide
    controls:
      - name: swing
        joint: "@upper"
        axis: [1, 0, 0]
        mode: rotation
        range: {min: -45, max: 45}
        default: 0
        units: deg
```

### 2.1 `ResolvedPart` (pure build output)

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | instance name |
| `preset` | `str` | preset name |
| `preset_version` | `str` | pinned version |
| `preset_sha256` | `str` | canonical preset document hash |
| `family` | `str` | preset family |
| `surface` | `Surface` | concrete surface with resolved bone names, part name, material |
| `controls` | `list[ControlChannel]` | resolved controls with concrete joints and addresses |
| `auto` | `list[ResolvedAuto]` | resolved behaviours with concrete joints |

### 2.2 `ControlChannel` (resolved)

| Field | Type | Description |
|-------|------|-------------|
| `address` | `str` | `"<part>/<control>"`; unique across the asset |
| `name` | `str` | control name |
| `joint` | `str` | concrete bone name |
| `axis` | `[float, float, float]` | unit vector |
| `mode` | `rotation \| translation` | — |
| `unbounded` | `bool` | true when no range |
| `range` | `{min, max} \| null` | omitted/null when unbounded |
| `default` | `float` | initial value |
| `units` | `deg \| m` | explicit |

### 2.3 `ResolvedAuto` (resolved)

The `AutoBehaviour` variant after replacing `@slot` with a concrete joint. It is
consumed by `anim/auto.py` and is **not** published in the manifest.

---

## 3. Preset Registry (new, adapter)

| Field | Type | Description |
|-------|------|-------------|
| `root` | `Path` | `<library-root>/parts` |
| `presets` | `dict[(name, version), PartPreset]` | exact-version lookup |
| `names` | `dict[name, list[version]]` | versions sorted ascending |
| `warnings` | `list[PresetWarning]` | unreadable/duplicate files (non-fatal at scan time) |

Loading rules:

- Scan `root/*/*.yaml` in sorted path order.
- Reject a file whose `name` ≠ directory name or `version` ≠ filename stem.
- Reject duplicate `(name, version)` pairs.
- Parse with `load_yaml_document` (rejects executable content) and the strict
  `PartPreset` model.
- Compute `sha256` from `canonical_json(preset_document)`.
- A malformed preset becomes a `preset-file-invalid` finding when it is needed by
  an assembly; `validate` reports it for the library scope.

Resolution rules (`parts/resolve.py`, pure):

1. Look up `(preset, preset_version)`; missing name/version produces
   `part-preset-missing` / `part-preset-version-missing` with available versions.
2. Check every `@slot` in `surface.bones`, `surface.rigid_bone`, control joints,
   and auto joints has a binding; reject extras.
3. Deep-copy the preset surface, substitute bound joints, apply overrides via the
   canonical vocabulary, set `name`/`material`, and validate the result as a
   `Surface`.
4. Resolve preset controls, then merge instance controls by name (instance wins).
   Compute addresses and validate uniqueness.
5. Resolve preset auto, then merge instance auto by name (instance wins).
6. Return `ResolvedPart` entries in recipe order plus all findings.

---

## 4. Recipe changes

| Field | Before | After | Notes |
|-------|--------|-------|-------|
| `surfaces` | required, min 1 | optional, min 0 | at least one of `surfaces` / `parts` required (gate: `recipe-empty-geometry`) |
| `parts` | absent | `list[PartInstance] = []` | new |
| `clips` | required, min 1 | optional, min 0 | core-clip rule in §4.1 |
| `skeleton` | required, min 1 bone | unchanged | a root-only skeleton is valid |
| `volumes` | required, min 1 with a hit | unchanged | a gameplay fact, not an anatomy fact |
| `materials` | optional | unchanged | part materials must resolve against it |

### 4.1 Core-clip rule

```
requires_core_clips(recipe) :=
    recipe.meta.category != "other" and len(recipe.clips) > 0
```

When false, `idle/locomotion/attack/hurt/death` are not required. When true, all
five are required exactly as today. If `clips == []` and auto behaviours exist, a
`baseline` clip is synthesized (§6).

### 4.2 Name uniqueness

Part names are unique among themselves and against `surfaces[].name` (FR-007).
Control addresses are unique by construction from unique part names and unique
control names; validation also checks the flattened list.

---

## 5. Closure Report (new, pure geometry)

`geometry/closure.py` produces one report per `SurfaceRange`:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | surface/part name |
| `closed` | `bool` | all checks pass |
| `boundary_edges` | `int` | undirected edges with exactly one triangle |
| `non_manifold_edges` | `int` | undirected edges with more than two triangles |
| `inconsistent_edges` | `int` | edges whose two incident triangles traverse in the same direction |
| `degenerate_faces` | `int` | repeated indices or area ≤ epsilon |
| `signed_volume` | `float` | sum of `dot(p0, cross(p1, p2)) / 6` |
| `first_issue` | `dict \| null` | smallest offending edge/face for the finding's `actual` |

Rules:

- `epsilon = max(1e-12, diagonal² × 1e-10)`, where `diagonal` is the length of the
  surface's local AABB diagonal.
- A closed report requires `boundary_edges == 0`, `non_manifold_edges == 0`,
  `inconsistent_edges == 0`, `degenerate_faces == 0`, and `signed_volume > 0`.
- Findings: `surface-open`, `surface-non-manifold`, `surface-winding-invalid`,
  `surface-degenerate`.
- The check is per surface range, never on the merged mesh (FR-002).

---

## 6. Automatic Motion Model (build-time)

### 6.1 Evaluation

For a resolved behaviour at time `t` (seconds):

| Kind | Delta |
|------|-------|
| `breathe` | `scale = [1 + a·sin(2πt/P + φ), …]` (all three axes) |
| `bob` | `translation = axis · a · sin(2πt/P + φ)` |
| `sway` | `rotation = quat(axis, radians(a) · sin(2πt/P + φ))` |
| `rotate` | `rotation = quat(axis, radians(rate·t + phase))` |

`φ = radians(phase)` for periodic kinds; for `rotate`, `phase` is the initial
angle in degrees.

### 6.2 Composition

For multiple behaviours on one joint, in declaration order:

- translations sum;
- rotations multiply as Hamilton quaternions (then normalize);
- scales multiply component-wise.

### 6.3 Clip baking

For each authored clip:

1. Build the generator's `dict[joint, function]`.
2. For each resolved auto behaviour whose joint is **not** in that dict, add the
   composed auto function.
3. Bake at 60 Hz exactly as today.

If `recipe.clips == []` and auto behaviours exist:

- synthesize `Clip(name="baseline", generator="baseline", loop=True)` with
  `duration = max(2.0, max(period of periodic behaviours))`, capped at
  `budgets.max_clip_ticks / 60`;
- evaluate the auto functions directly (no generator registry entry);
- publish the clip in the manifest with `source: "automatic"`.

### 6.4 Precedence

Explicit generator motion always wins for a joint it animates. Auto motion is a
baseline only for otherwise-unanimated joints.

---

## 7. Manifest additions (published contract, 1.1)

### 7.1 `ManifestClip`

| Field | Type | Rules |
|-------|------|-------|
| `name` | `str` | unique |
| `duration` | `float` | > 0 |
| `loop` | `bool` | — |
| `generator` | enum + `baseline` | existing names plus `baseline` |
| `source` | `authored \| automatic` | optional; defaults to `authored` when absent |

### 7.2 `ManifestPart`

| Field | Type | Rules |
|-------|------|-------|
| `name` | `str` | unique part name |
| `preset` | `str` | preset name |
| `presetVersion` | `str` | pinned version |
| `presetSha256` | `str` | 64 lowercase hex |
| `family` | `organic \| mechanical \| vehicle` | — |
| `controls` | `list[ManifestControl]` | may be empty |

### 7.3 `ManifestControl`

| Field | Type | Rules |
|-------|------|-------|
| `address` | `str` | `"<part>/<control>"`; unique across `parts[]` |
| `name` | `str` | control name |
| `joint` | `str` | must exist in `skeleton.joints` |
| `axis` | `[float, float, float]` | unit vector |
| `mode` | `rotation \| translation` | — |
| `unbounded` | `bool` | — |
| `range` | `{min, max}` | omitted when unbounded |
| `default` | `float` | — |
| `units` | `deg \| m` | matches mode |

### 7.4 Versioning

- `schemaVersion` becomes `"1.1"`.
- `parts` is optional in the JSON Schema and defaults to `[]` in the producer
  model.
- `clips[].source` is optional and defaults to `"authored"`.
- `read_manifest_compatible` remains major-strict (`1.x`) and minor-tolerant.
- `REQUIRED_MANIFEST_FIELDS` does not add `parts` or `source`.

---

## 8. Invariants

1. **Closure**: every generated part is a closed manifold by D1; overlap between
   parts is allowed.
2. **Culling**: no generated material sets `doubleSided`; no authored viewer code
   selects `DoubleSide`.
3. **Uniqueness**: part names, surface names, control names within a part, and
   control addresses across the asset are unique.
4. **Preset immutability**: a preset file is immutable once published; changes
   add a new version file.
5. **Exact pinning**: an instance resolves only its declared `preset_version`.
6. **Binding completeness**: every `@slot` used by the resolved preset is bound;
   no extra bindings; two slots must not bind to the same bone (`part-binding-duplicate`)
   because that would collapse a swept part into a degenerate path.
7. **Override closure**: every override key is declared by the preset's `params`.
8. **Control validity**: joint exists, axis is a unit vector, mode is supported,
   units match mode, range/default are consistent.
9. **Auto validity**: joint exists, axis/amplitude/period/rate are valid, names
   are unique.
10. **Precedence**: explicit clip motion wins on an animated joint; auto fills
    only the rest.
11. **Determinism**: canonical build digest includes pinned preset documents;
    identical inputs produce identical GLB and manifest bytes.
12. **Anatomy neutrality**: no rule requires a torso, limb, chain, or family
    structure; a root-only skeleton and parts-only geometry are valid.
13. **Backward compatibility**: recipes without `parts` behave as before except
    for closed caps; manifest 1.0 documents remain readable.

---

## 9. State transitions

### 9.1 Preset version lifecycle

```
draft version file  ──> validated + shipped (immutable)
                              │
                              ├── assembly pins (name, version)
                              │
                              └── new behaviour/geometry needed
                                        │
                                        ▼
                              add <next-version>.yaml
                                        │
                              old assemblies keep the old pin
                              new assemblies may pin either version
```

A file at an existing version is never edited. A retracted preset is marked in
docs/CHANGELOG but its file remains so pinned assemblies still build.

### 9.2 Build pipeline

```
load YAML
  └─► parse strict Recipe
        └─► resolve declared params
              └─► resolve preset registry (adapter)
                    └─► resolve parts (pure): bind, overrides, controls, auto
                          └─► build skeleton
                                └─► build mesh from surfaces + resolved parts
                                      └─► closure gate (per part)
                                            └─► bake clips (auto baseline + precedence)
                                                  └─► assemble manifest 1.1
                                                        └─► full gate
                                                              └─► stage + os.replace
```

Any gate error stops before the atomic commit. Warnings never change the exit
code.

---

## 10. Requirement mapping

| Spec requirement | Model/gate location |
|------------------|---------------------|
| FR-001 closed volume | `geometry/closure.py`, `validation/closure.py` |
| FR-002 overlap allowed | per-`SurfaceRange` check; no whole-mesh check |
| FR-003 culling stays on | GLB writer + viewer contract test |
| FR-004 preset families | `PartPreset.family`, `library/parts/` |
| FR-005 anatomy neutral | neutral kinds; no structural rule |
| FR-006 pinned preset + partial overrides | `PartInstance.preset_version`, `overrides` |
| FR-007 unique part names | `validation/parts.py` |
| FR-008 control fields | `PresetControl` / `ManifestControl` |
| FR-009 unique addresses | `ControlChannel.address` |
| FR-010 published controls | `ManifestPart.controls` |
| FR-011 additive/version-compatible | manifest 1.1 optional fields |
| FR-012 control validation | `validation/parts.py` |
| FR-013 automatic behaviours | `AutoBehaviour` union |
| FR-014 deterministic auto | `anim/auto.py`, seeded/fixed functions |
| FR-015 baked + synthesized baseline | `anim/bake.py`, `ManifestClip.source` |
| FR-016 explicit clip precedence | baker per-joint merge |
| FR-017 viewer controls | `inspector.js` Controls tab |
| FR-018 no torso/limbs | optional surfaces/clips, root-only skeleton |
| FR-019 preserve gameplay facts | gameplay-facts snapshot test |
| FR-020 incremental preset adoption | `surfaces` and `parts` coexist |
| FR-021 determinism | build digest + determinism tests |
| FR-022 clear findings | new finding codes in §D14 of research |
