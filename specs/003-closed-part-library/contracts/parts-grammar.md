# Contract: recipe `parts` grammar (v1)

**Feature**: `003-closed-part-library` · **Enforces**: FR-004 through FR-009,
FR-013, FR-018, FR-020
**Sources**: [data-model.md](../data-model.md) §1–§4,
[research.md](../research.md) D3–D6, D11, D17
**Normative preset schema**: [preset.schema.json](./preset.schema.json)
**Control/auto semantics**: [controls.md](./controls.md)

A recipe may declare reusable part instances instead of, or alongside,
hand-authored `surfaces`. The recipe remains inert YAML parsed with
`yaml.safe_load`; presets are data, never code.

```yaml
meta:        # catalog identity (required)
params:      # declared knobs (required, may be [])
budgets:     # measured-value ceilings (required)
skeleton:    # bones + chains — declared first (required)
surfaces:    # hand-authored skinned regions (optional, may be [])
parts:       # reusable preset instances (optional, may be [])
materials:   # texforge texture references (required, may be [])
clips:       # clip generators + events (optional, may be [])
sockets:     # attachment points (optional)
volumes:     # gameplay proxies (required; >=1 hit)
phases:      # boss phase thresholds (required for category boss)
```

At least one of `surfaces` / `parts` must produce a surface. A recipe with
neither fails with `recipe-empty-geometry`. A root-only skeleton is valid.

## 1. Neutral surface kinds

The existing `limb-tube` and `torso-shell` kinds remain accepted. Presets use the
anatomy-neutral names:

| Public kind | Alias | Builder |
|-------------|-------|---------|
| `swept-solid` | `limb-tube` | `sweep_surface(..., caps=True)` |
| `shell` | `torso-shell` | `sweep_surface(..., caps=True)` |
| `rigid-part` | — | `rigid_surface(...)` (already capped) |

No validation rule requires a torso, a limb, a chain, or a part family. A hull, a
wing, a turret, and a leg are all just closed parts.

## 2. `parts` entries

```yaml
parts:
  - name: front-left-leg
    preset: organic-leg
    preset_version: "1.0.0"
    bind: {upper: upper-fl, lower: lower-fl, foot: foot-fl}
    overrides: {radius-end: 0.045}
    material: hide
```

| Field | Required | Contract |
|-------|----------|----------|
| `name` | yes | identifier; unique across all surfaces and parts in the asset |
| `preset` | yes | preset name present in `library/parts/<preset>/` |
| `preset_version` | yes | exact `MAJOR.MINOR.PATCH`; the pinned version, not a range |
| `bind` | yes | slot name → existing bone; every `@slot` used by the preset must be bound; extra keys are rejected |
| `overrides` | no | partial per-parameter overrides; keys must be declared by the preset |
| `material` | no | overrides the preset surface material; must exist in `materials[]` |
| `controls` | no | full control definitions; a same-name entry replaces the preset control |
| `auto` | no | full auto definitions; a same-name entry replaces the preset behaviour |

### 2.1 Preset file layout and pinning

```
library/parts/<preset-name>/<MAJOR.MINOR.PATCH>.yaml
```

- The file's `name` must equal the directory name.
- The file's `version` must equal the filename stem.
- Versions are immutable. To change a preset, add a new version file. Old
  assemblies keep resolving their pinned version.
- A missing `(name, version)` is a validation error listing the available
  versions.
- Scanning is deterministic (sorted paths). Duplicate `(name, version)` files are
  an error.

### 2.2 Preset surface and `@slot` binding

A preset surface uses `@slot` names for every bone position:

```yaml
# library/parts/organic-leg/1.0.0.yaml (excerpt)
surface:
  mode: sweep
  kind: swept-solid
  bones: ["@upper", "@lower", "@foot"]
  rings: 10
  segments: 8
  radius: {start: 0.12, end: 0.05}
  blend: 0.25
  material: hide
```

The instance's `bind` replaces each `@slot` with the named bone. A rigid preset
uses one `@mount` slot; a panel, turret, piston, and rotor all bind one bone.

### 2.3 Partial overrides

Overrides use the closed canonical vocabulary from
[data-model.md](../data-model.md) §1.3. Omitted keys keep the preset value; a
nested object is not replaced wholesale.

```yaml
overrides:
  radius-start: 0.14
  radius-end: 0.05
  rings: 12
```

- Unknown keys: `part-override-unknown` with a nearest-name suggestion.
- Type mismatch: `part-override-type`.
- Out-of-range: `part-override-range`.
- A preset declares only the keys its shape supports (e.g. a rigid plate does not
  declare `taper-start`).

The preset's `surface` is the source of truth for defaults. A preset's `params`
list declares the allowed override keys, their types, ranges, optional units, and
descriptions; `beastforge parts` prints the effective defaults.

## 3. Controls and automatic behaviours

Both may be declared on a preset and on an instance. The instance form uses the
same shape, except `joint` may be a concrete bone name instead of an `@slot`.
Merging is by `name`; an instance entry fully replaces the preset entry with the
same name. The full schemas and semantic rules are in
[controls.md](./controls.md).

```yaml
controls:
  - name: swing
    joint: "@upper"
    axis: [1, 0, 0]
    mode: rotation
    range: {min: -35, max: 35}
    default: 0
    units: deg

auto:
  - name: breathe
    kind: breathe
    joint: "@spine-2"
    amplitude: 0.03
    period: 2.0
    phase: 0
```

## 4. Core clips and anatomy neutrality

```
requires_core_clips(recipe) :=
    recipe.meta.category != "other" and len(recipe.clips) > 0
```

- The existing five creatures are not `other` and declare clips, so all five core
  clips remain required.
- A mechanical or vehicle asset uses `category: other` and may declare any clip
  set or none.
- An asset with no authored clips is valid. If it has automatic behaviours, the
  builder synthesizes a `baseline` clip; otherwise the manifest's `clips` array is
  empty.
- No rule requires a torso, limb, biped/quadruped layout, or part family.

## 5. Incremental migration

A recipe can move one surface at a time:

```yaml
# Before
surfaces:
  - name: front-left-leg
    mode: sweep
    kind: limb-tube
    bones: [upper-fl, lower-fl, foot-fl]
    rings: 10
    segments: 8
    radius: {start: 0.12, end: 0.05}
    material: hide

# After
parts:
  - name: front-left-leg
    preset: organic-leg
    preset_version: "1.0.0"
    bind: {upper: upper-fl, lower: lower-fl, foot: foot-fl}
    overrides: {radius-start: 0.12, radius-end: 0.05}
    material: hide
```

The resolved surface keeps the same `name`, so mesh ranges, materials, and
gameplay references do not move. Controls are additive published facts.

## 6. Rejection summary

| Input | Finding | Exit |
|-------|---------|------|
| No `surfaces` and no `parts` | `recipe-empty-geometry` | 3 |
| Part name collides with a surface/part | `part-duplicate-name` / `duplicate-name` | 3 |
| Preset name not found | `part-preset-missing` | 3 |
| Preset version not found | `part-preset-version-missing` | 3 |
| Unbound `@slot` | `part-binding-missing` | 3 |
| Extra `bind` key | `part-binding-unknown` | 3 |
| Two slots bound to the same bone | `part-binding-duplicate` | 3 |
| Unknown override key | `part-override-unknown` (+ suggestion) | 3 |
| Override type/range error | `part-override-type` / `part-override-range` | 3 |
| Control/auto joint missing | `part-control-joint-missing` / `part-auto-joint-missing` | 3 |
| Invalid axis | `part-control-axis-invalid` / `part-auto-axis-invalid` | 3 |
| Invalid mode/units/range/default | matching `part-control-*` | 3 |
| Duplicate control/address | `part-control-duplicate` / `part-control-address-duplicate` | 3 |
| Invalid auto amplitude/period/rate | matching `part-auto-*` | 3 |
| Malformed preset file | `preset-file-invalid` | 3 |
| Open/non-manifold/mis-wound/degenerate part | `surface-open` / `surface-non-manifold` / `surface-winding-invalid` / `surface-degenerate` | 3 |

## 7. Determinism rules

- Only declared params, the recipe document, the **pinned preset documents**, and
  the tool version influence output.
- The canonical build digest includes the pinned preset documents (D13).
- Preset versions are immutable; a preset change adds a version file.
- Override merge order is deterministic (declared order, then sorted keys where a
  mapping is emitted).
- Auto composition order is declaration order.
- No wall clock, environment, locale, hostname, or unordered iteration may reach
  geometry, animation, or JSON.
