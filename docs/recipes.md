# Authoring creatures

A recipe is one YAML file at `library/<category>/<name>.yaml`. It is inert data:
`yaml.safe_load` only, no executable content, and every unknown key is rejected.
The skeleton is declared first; surfaces bind to its bones.

The normative grammar and the shipped examples are
[contracts/recipe-grammar.md](../specs/001-procedural-creature-generator/contracts/recipe-grammar.md)
and `library/`. The structural schema is
[recipe.schema.json](../specs/001-procedural-creature-generator/contracts/schema/recipe.schema.json).

## Sections

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
volumes:     # hit / weak-point / collision proxies (required; >=1 hit)
phases:      # boss phase thresholds (required for category boss)
```

At least one of `surfaces` / `parts` must produce geometry.

## Identifiers

`meta.name`, bones, chains, surfaces, materials, clips, sockets, volumes, and
phases match `^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$` and are at most 64 chars.
`meta.name` must equal the file stem. Names are a public contract once shipped.

## Parameters

Declare every knob used by the build. `--set key=value` overrides a declared
parameter; an unknown key is a `recipe-unknown-param` error with a nearest-name
suggestion. The declared `seed` parameter is part of the run seed, so changing
it changes seeded variation.

```yaml
params:
  - {name: body-length, type: float, default: 2.4, min: 1.2, max: 4.0, unit: m,
     description: "Tip-to-tail body length."}
  - {name: seed, type: int, default: 1717, min: 0, max: 1000000,
     description: "Deterministic noise seed."}
```

Types: `int`, `float`, `bool`, `enum` (requires `values`), `string`.

## Skeleton

```yaml
skeleton:
  root: root
  bones:
    - {name: root, parent: null, rest: {translation: [0, 0.9, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}}
    - {name: spine-01, parent: root, rest: {translation: [0, 0, 0.55], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}}
    # ...
  chains:
    - {name: front-left-leg, bones: [upper-fl, lower-fl, foot-fl]}
```

- Exactly one bone has `parent: null` and it equals `skeleton.root`.
- `rest` is relative to the parent: metres, a unit quaternion `[x, y, z, w]`,
  and positive non-zero scale.
- A chain is an ordered, contiguous parent→child run. Its first bone's parent is
  the attachment (torso, shoulder, hip, ...).
- Limb bones must have positive rest length. Cycles, duplicates, unreachable
  bones, and degenerate/inverted transforms fail validation.

## Surfaces

The only v1 mode is `sweep`. Kinds are `swept-solid`, `shell`, and `rigid-part`;
`limb-tube` and `torso-shell` remain accepted aliases. Every kind is capped and
therefore closed.

```yaml
surfaces:
  - name: body
    mode: sweep
    kind: torso-shell
    bones: [spine-01, spine-02, spine-03]
    rings: 12
    segments: 16
    radius: {start: 0.42, end: 0.30}
    blend: 0.25
    modifiers:
      taper: {start: 1.0, end: 0.85}
      twist: 0.0
      radial_noise: {amplitude: 0.03, frequency: 4.0, seed: 7}
      squash: [1.0, 0.9, 1.0]
      scale: [1.0, 1.0, 1.0]
    material: hide

  - name: head-plate
    mode: sweep
    kind: rigid-part
    bones: [head]
    rigid_bone: head
    rings: 4
    segments: 6
    radius: {start: 0.22, end: 0.22}
    material: chitin
```

- A limb/torso is a continuous sweep along its bone chain. Skin weights are
  assigned at construction: 1–2 influences, blended across joints with a
  clamped smoothstep, normalized to 1.0.
- `blend` is a joint-band fraction; it is clamped to at most `0.35 * bone_length`.
- `radius` is a `{start, end}` linear profile or a per-position list.
- `rings` is the number of cross-sections; `segments` is the number of radial
  samples. Both must be positive (rings ≥ 2, segments ≥ 3).
- UVs are emitted by the sweep: `U` along the sweep and `V` around it.
- Silhouette modifiers are seeded and deterministic: `taper`, `twist`,
  `radial_noise`, `squash`, `scale`.
- A rigid part binds to exactly one bone with weight 1.0 and is capped.
- Any `mode` other than `sweep` is rejected with `surface-unsupported-mode`.
- Every surface must be a closed solid. Caps are unconditional; there is no
  `open` or `two-sided` option.

## Part instances

A recipe may assemble reusable presets instead of, or alongside, hand-authored
surfaces. Presets live at `library/parts/<preset>/<MAJOR.MINOR.PATCH>.yaml` and
are immutable once published.

```yaml
parts:
  - name: front-left-leg
    preset: organic-leg
    preset_version: "1.0.0"
    bind: {upper: upper-fl, lower: lower-fl, foot: foot-fl}
    overrides: {radius-end: 0.045}
    material: hide
```

- `name` is unique across surfaces and parts.
- `preset_version` is an exact pin, never a range. Missing names/versions fail
  with `part-preset-missing` / `part-preset-version-missing`.
- `bind` maps every `@slot` used by the preset (surface, controls, auto) to an
  existing bone. Extras and unbound slots are errors.
- `overrides` use the closed vocabulary `radius-start`, `radius-end`, `rings`,
  `segments`, `blend`, `taper-start`, `taper-end`, `twist`, `noise-amplitude`,
  `noise-frequency`, `noise-seed`, `squash-x/y/z`, and `scale-x/y/z`. Omitted keys
  keep the preset value; nested objects are never replaced wholesale.
- `material` overrides the preset surface material and must be declared in
  `materials[]`.
- A recipe with neither `surfaces` nor `parts` fails with `recipe-empty-geometry`.

## Controls and automatic motion

Controls and automatic behaviours may be declared on a preset or overridden by
name on an instance. Control joints may be `@slots`; they resolve to concrete
bones and publish an address of `<part>/<control>` in manifest 1.1.

```yaml
controls:
  - {name: swing, joint: "@upper", axis: [1, 0, 0], mode: rotation,
     range: {min: -35, max: 35}, default: 0, units: deg}

auto:
  - {name: breathe, kind: breathe, joint: "@spine-2",
     amplitude: 0.03, period: 2.0, phase: 0}
```

- Rotation controls use `units: deg`; translation controls use `units: m`.
- `unbounded: true` forbids a `range`; a range without `unbounded` means bounded.
- Automatic kinds are `breathe`, `bob`, `sway`, and `rotate`. They are baked into
  every authored clip, but an explicit generator wins for any joint it animates.
- If `clips` is empty and automatic behaviours exist, one `baseline` clip is
  synthesized with `source: "automatic"`.
- Core clips are required only when `meta.category != "other"` and at least one
  clip is authored.

## Materials

```yaml
materials:
  - {name: hide, texture: granite, params: {scale: 9, seed: 12}, size: 512x512,
     metallic: 0.0, roughness: 0.85}
  - {name: chitin, texture: brushed-steel, params: {seed: 3}, size: 512x512,
     metallic: 0.3, roughness: 0.4}
```

`texture` is a texforge recipe **name**, never a path. beastforge implements no
texture synthesis; the texforge adapter renders the PNG at generation time and
embeds it in the `.glb`. A missing recipe or invalid parameter fails generation
before anything is staged. v1 supports the `baseColor` slot only.

## Clips and events

```yaml
clips:
  - {name: idle, generator: breathe, duration: 2.0, loop: true,
     params: {amplitude: 0.04, cycles: 1}}
  - {name: locomotion, generator: gait, duration: 1.0, loop: true,
     params: {stride: 0.35, duty: 0.6, bob: 0.02,
              legs: [front-left-leg, front-right-leg, rear-left-leg, rear-right-leg]}}
  - name: attack
    generator: telegraph-attack
    ticks: 50
    loop: false
    params: {windup: 0.4, strike: 0.15, recovery: 0.35, reach: 1.2}
    events:
      - {name: impact, ticks: 38}
  - {name: hurt, generator: recoil, duration: 0.5, loop: false,
     params: {amplitude: 0.18, decay: 8.0}}
  - {name: death, generator: death-collapse, duration: 1.5, loop: false,
     params: {collapse: 0.9}}
```

- Required core clips: `idle`, `locomotion`, `attack`, `hurt`, `death`. Extra
  clip names are allowed.
- Closed generator registry: `breathe`, `gait`, `hover-bob`, `recoil`,
  `telegraph-attack`, `death-collapse`.
- Declare exactly one of `duration` (seconds) or `ticks` (integer at 60 Hz).
  `duration = ticks / 60` exactly.
- Events use the same time/ticks rule and must satisfy `0 <= time < duration`.
  The `attack` clip must declare an event named `impact`.
- Clips are baked at 60 Hz at generation time. Loop clips include a closing key
  at `t == duration`. There is no runtime procedural animation in the asset.
- The manifest's `events[]` is the authoritative gameplay timing.

## Sockets, volumes, phases

```yaml
sockets:
  - {name: maw, bone: head, offset: [0, -0.05, -0.6]}

volumes:
  - {name: body-hull, role: hit, center: [0, 0.9, 0], extents: [0.5, 0.45, 1.2]}
  - {name: skull-weak, role: weak-point, center: [0, 1.15, -0.85],
     extents: [0.2, 0.2, 0.25], bone: head}

phases:
  - {name: enraged, threshold: 0.66}
  - {name: desperate, threshold: 0.33}
```

- Sockets may be omitted. Every target must exist.
- At least one `hit` volume is required. `weak-point` and `collision` are
  optional. `bone` makes the volume follow a joint in-engine.
- Phases are required for `category: boss`; thresholds are strictly inside
  `(0, 1)`. Other categories may declare them.

## Determinism rules

Only declared params, the recipe document, the tool version, and the texforge
version influence output. No wall clock, environment, locale, hostname, or
process state may be read by the build. Noise draws only from seeded streams.
A recipe must not reference files outside itself and the texforge library.

## Rejection summary

| Input | Finding | Exit |
|-------|---------|------|
| Unknown top-level/nested key | `recipe-unknown-field` | 3 |
| Unknown `--set` key | `recipe-unknown-param` + suggestion | 3 |
| Executable YAML tag or key | `recipe-executable-content` | 3 |
| `mode` other than `sweep` | `surface-unsupported-mode` | 3 |
| Missing reserved clip | `clip-missing-core` | 3 |
| Missing `hit` volume or `attack.impact` | `volume-missing-hit` / `clip-missing-core` | 3 |
| Boss without phases | `phase-missing-for-boss` | 3 |
| Fractional ticks / non-positive duration | `clip-fractional-ticks` / `clip-nonpositive-duration` | 3 |
| Dangling socket/event/volume/material | matching `*-missing` / `*-unresolved` | 3 |
| Budget exceeded | `budget-exceeded` | 3 |
