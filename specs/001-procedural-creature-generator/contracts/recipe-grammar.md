# Contract: beastforge recipe grammar (v1)

**Feature**: `001-procedural-creature-generator` · **Enforces**: FR-001,
FR-004, FR-014–FR-028
**Sources**: [data-model.md](../data-model.md) §1–§11, [research.md](../research.md)
D6/D7, ADRs 261114-2/3/4
**Normative schema**: [schema/recipe.schema.json](./schema/recipe.schema.json)

A recipe is **inert data**: YAML parsed with `yaml.safe_load` only. It names no
modules or functions, and it is never executed. The top-level sections appear in
the documented order; the loader rejects unknown keys at every level.

```yaml
meta:        # catalog identity (required)
params:      # declared knobs (required, may be [])
budgets:     # measured-value ceilings (required)
skeleton:    # bones + chains — declared first (required)
surfaces:    # skinned body regions bound to bones (required)
materials:   # texforge texture references (required, may be [])
clips:       # clip generators + events (required)
sockets:     # attachment points (optional)
volumes:     # hit / weak-point / collision proxies (required; >=1 hit)
phases:      # boss phase thresholds (required for category boss)
```

## 1. Identifiers and naming

- `meta.name`, bone, chain, surface, material, clip, socket, volume, and phase
  names match `^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$` and are at most 64 chars.
- `meta.name` equals the file stem.
- Names are a public contract once shipped: renaming or removing a clip, socket,
  event, or phase requires a manifest schema **major** bump (FR-032).
- Reserved clip names: `idle`, `locomotion`, `attack`, `hurt`, `death`. All five
  are required; extra clip names are allowed.

## 2. `meta`

```yaml
meta:
  name: ridge-stalker
  description: "A low, ridge-backed quadruped predator with a chitin skull plate."
  category: quadruped          # boss | quadruped | swarm | other
  tags: [quadruped, predator]  # optional, lowercase, unique
  author: beastforge           # optional
  tested_with: "0.1.0"         # required; generator version verified against
  version: "1.0.0"             # required; recipe SemVer, bump on behaviour edits
  units: m                     # optional; only metres in v1
  orientation: {up: Y, forward: "-Z"}  # optional; this is the only accepted value
```

## 3. `params`

```yaml
params:
  - name: body-length
    type: float                # int | float | bool | enum | string
    default: 2.4
    min: 1.2
    max: 4.0
    unit: m                    # optional: m, rad, deg, s, count, ratio
    description: "Tip-to-tail body length."
  - name: seed
    type: int
    default: 1717
    min: 0
    max: 1000000
    description: "Deterministic noise seed."
```

Rules: names match `^[a-z][a-z0-9-]*$`; `default` must satisfy the declared
type and limits; `enum` requires `values`; unknown override keys are errors with
a nearest-name suggestion (FR-026). A declared `seed` param participates in the
run seed, so changing it changes seeded variation; per-modifier `seed` values
are salts that keep independent streams independent.

## 4. `budgets`

```yaml
budgets:
  vertices: 20000     # default
  bones: 64           # default
  triangles: 60000    # default
  max_clip_ticks: 600 # default, at 60 Hz
```

Exceeding any budget is a validation **failure**, never a warning (FR-028).

## 5. `skeleton` (declared first)

```yaml
skeleton:
  root: root
  bones:
    - name: root
      parent: null
      rest: {translation: [0, 0.9, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
    - name: spine-01
      parent: root
      rest: {translation: [0, 0, 0.55], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
    - name: head
      parent: spine-01
      rest: {translation: [0, 0.1, -0.7], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
    - name: shoulder-fl
      parent: spine-01
      rest: {translation: [0.22, -0.05, -0.2], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
    - name: upper-fl
      parent: shoulder-fl
      rest: {translation: [0, -0.35, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
    - name: lower-fl
      parent: upper-fl
      rest: {translation: [0, -0.4, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
    - name: foot-fl
      parent: lower-fl
      rest: {translation: [0, -0.35, 0.05], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}
  chains:
    - name: front-left-leg
      bones: [upper-fl, lower-fl, foot-fl]
```

- Exactly one bone has `parent: null` and it equals `skeleton.root`.
- `rest` is relative to the parent: translation in metres, rotation a unit
  quaternion `[x, y, z, w]`, scale positive and non-zero.
- A chain lists an ordered, contiguous parent→child run of bones; the first
  bone's `parent` is the chain's attachment.
- Bone length is derived from the rest translation; limb bones must be > 0.
- Cycles, duplicate names, unreachable bones, and degenerate or inverted
  transforms fail validation with the bones named (FR-035).

## 6. `surfaces`

```yaml
surfaces:
  - name: body
    mode: sweep                # v1: only sweep; metaball is rejected explicitly
    kind: torso-shell          # limb-tube | torso-shell | rigid-part
    bones: [spine-01, head]    # ordered binding bones (must exist; contiguous)
    rings: 12
    segments: 16
    radius: {start: 0.42, end: 0.30}
    blend: 0.25                # joint band fraction, clamped to <= 0.35*L
    modifiers:
      taper: {start: 1.0, end: 0.85}
      twist: 0.0
      radial_noise: {amplitude: 0.03, frequency: 4.0, seed: 7}
      squash: [1.0, 1.0, 1.0]
      scale: [1.0, 1.0, 1.0]
    material: hide

  - name: front-left-leg
    mode: sweep
    kind: limb-tube
    bones: [upper-fl, lower-fl, foot-fl]
    rings: 16
    segments: 10
    radius: {start: 0.24, end: 0.08}
    material: hide

  - name: head-plate
    mode: sweep
    kind: rigid-part
    bones: [head]
    rigid_bone: head           # exactly one bone; weight 1.0, no deformation
    rings: 4
    segments: 6
    radius: {start: 0.22, end: 0.22}
    material: chitin
```

- Limbs are continuous swept tubes; torsos are ring shells bound along the spine
  (FR-015). Rigid parts bind to exactly one bone and do not deform (FR-016).
- Skin weights are assigned at vertex birth: 1–2 influences, blended across
  joints by a clamped smoothstep, normalized to 1.0 (FR-017). Bind pose equals
  rest pose; inverse bind matrices come from the rest skeleton.
- UVs are emitted by the sweep — `U` along the sweep, `V` around it — so
  texforge textures tile without manual mapping (FR-018).
- Silhouette modifiers (`taper`, `twist`, `radial_noise`, `squash`, `scale`) are
  seeded and deterministic (FR-019).
- Any `mode` other than `sweep` is rejected with `surface-unsupported-mode`
  (FR-020) — no silent substitution.

## 7. `materials`

```yaml
materials:
  - name: hide
    texture: granite           # a texforge recipe NAME, never a path
    params: {scale: 9, seed: 12}
    size: 512x512
    slot: baseColor            # v1 supports baseColor only
    metallic: 0.0
    roughness: 0.85
  - name: chitin
    texture: brushed-steel
    params: {seed: 3}
```

Material references are resolved and rendered at generation time by the texforge
adapter; the PNGs are embedded in the `.glb`. beastforge implements no texture
synthesis of its own (FR-021). An unresolved recipe or invalid params fails
generation before any asset is staged.

## 8. `clips` and `events`

```yaml
clips:
  - name: idle
    generator: breathe          # closed registry (see below)
    duration: 2.0               # seconds, positive, <=6 decimals
    loop: true
    params: {amplitude: 0.04, cycles: 1}

  - name: locomotion
    generator: gait
    duration: 1.0
    loop: true
    params: {stride: 0.35, duty: 0.6, legs: [front-left-leg, front-right-leg,
                                            rear-left-leg, rear-right-leg]}

  - name: attack
    generator: telegraph-attack
    ticks: 50                   # alternative to duration: exact ticks/60 seconds
    loop: false
    params: {windup: 0.4, strike: 0.15, recovery: 0.35, reach: 1.2}
    events:
      - {name: impact, ticks: 38}   # required on the attack clip

  - name: hurt
    generator: recoil
    duration: 0.5
    loop: false
    params: {amplitude: 0.18}

  - name: death
    generator: death-collapse
    duration: 1.5
    loop: false
    params: {collapse: 0.9}
```

**Closed generator registry**: `breathe`, `gait`, `hover-bob`, `recoil`,
`telegraph-attack`, `death-collapse`. Generator parameters are validated against
the registry; changing a generator's math is a breaking change for recipes that
use it and requires a `meta.tested_with` bump (ADR 261114-4).

**Timing**: declare exactly one of `duration` (seconds) or `ticks` (integer at
60 Hz). `duration = ticks / 60` exactly. Event times use the same rule and must
satisfy `0 <= time < duration`; the `attack` clip must contain an `impact` event
(FR-023, FR-025). Clips are baked at 60 Hz at generation time; no runtime
procedural behaviour ships in the asset (FR-024). Loop clips include a closing
key at `t == duration`.

## 9. `sockets` (optional)

```yaml
sockets:
  - name: maw
    bone: head
    offset: [0, -0.05, -0.6]   # metres, bone-local space
```

Every socket target must exist. `node` is reserved and rejected in v1. Sockets
may be omitted entirely (FR-025).

## 10. `volumes`

```yaml
volumes:
  - name: body-hull
    role: hit                  # hit | weak-point | collision
    center: [0, 0.9, 0]
    extents: [0.5, 0.45, 1.2]  # half-extents, all > 0
  - name: skull-weak
    role: weak-point
    center: [0, 1.15, -0.85]
    extents: [0.2, 0.2, 0.25]
    bone: head                 # optional: volume follows this bone in-engine
```

At least one `hit` volume is required on every creature. There is no
auto-derived fallback (FR-025).

## 11. `phases`

```yaml
phases:
  - {name: enraged, threshold: 0.66}
  - {name: desperate, threshold: 0.33}
```

`0 < threshold < 1`; names unique. Required for `category: boss`; optional and
validated identically for other categories.

## 12. Complete example

```yaml
meta:
  name: ridge-stalker
  description: "A low, ridge-backed quadruped predator with a chitin skull plate."
  category: quadruped
  tags: [quadruped, predator]
  author: beastforge
  tested_with: "0.1.0"
  version: "1.0.0"

params:
  - {name: body-length, type: float, default: 2.4, min: 1.2, max: 4.0, unit: m,
     description: "Tip-to-tail body length."}
  - {name: seed, type: int, default: 1717, min: 0, max: 1000000,
     description: "Deterministic noise seed."}

budgets: {vertices: 20000, bones: 64, triangles: 60000, max_clip_ticks: 600}

skeleton:
  root: root
  bones:
    - {name: root, parent: null,
       rest: {translation: [0, 0.9, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}}
    - {name: spine-01, parent: root,
       rest: {translation: [0, 0, 0.55], rotation: [0, 0, 0, 1], scale: [1, 1, 1]}}
    # ... remaining bones ...
  chains:
    - {name: front-left-leg, bones: [upper-fl, lower-fl, foot-fl]}
    # ... remaining chains ...

surfaces:
  - name: body
    mode: sweep
    kind: torso-shell
    bones: [spine-01, spine-02, spine-03]
    rings: 12
    segments: 16
    radius: {start: 0.42, end: 0.30}
    material: hide
  # ... limbs and rigid parts ...

materials:
  - {name: hide, texture: granite, params: {scale: 9, seed: 12}, size: 512x512}
  - {name: chitin, texture: brushed-steel, params: {seed: 3}}

clips:
  - {name: idle, generator: breathe, duration: 2.0, loop: true,
     params: {amplitude: 0.04, cycles: 1}}
  - {name: locomotion, generator: gait, duration: 1.0, loop: true,
     params: {stride: 0.35, duty: 0.6}}
  - name: attack
    generator: telegraph-attack
    ticks: 50
    loop: false
    params: {windup: 0.4, strike: 0.15, recovery: 0.35, reach: 1.2}
    events: [{name: impact, ticks: 38}]
  - {name: hurt, generator: recoil, duration: 0.5, loop: false,
     params: {amplitude: 0.18}}
  - {name: death, generator: death-collapse, duration: 1.5, loop: false,
     params: {collapse: 0.9}}

sockets:
  - {name: maw, bone: head, offset: [0, -0.05, -0.6]}

volumes:
  - {name: body-hull, role: hit, center: [0, 0.9, 0], extents: [0.5, 0.45, 1.2]}
  - {name: skull-weak, role: weak-point, center: [0, 1.15, -0.85],
     extents: [0.2, 0.2, 0.25], bone: head}
```

## 13. Determinism rules for recipes

- Only declared params, the recipe document, the tool version, and the texforge
  version influence output.
- No wall clock, environment, locale, hostname, or process state may be read by
  the build.
- Noise and variation draw from seeded streams derived from the run seed;
  shuffling or set iteration is forbidden in output paths.
- A recipe must not reference files outside the recipe and the texforge library
  (no absolute paths, no network URLs).

## 14. Rejection summary

| Input | Result |
|-------|--------|
| Unknown top-level or nested key | `recipe-unknown-field`, exit 3 |
| Unknown `--set` key | `recipe-unknown-param` + suggestion, exit 3 |
| `!!python/...` or other non-standard tag | `recipe-executable-content`, exit 3 |
| `mode` other than `sweep` | `surface-unsupported-mode`, exit 3 |
| Missing reserved clip | `clip-missing-core`, exit 3 |
| Missing `hit` volume or `attack.impact` event | `volume-missing-hit` / `clip-missing-core`, exit 3 |
| Missing boss phases | `phase-missing-for-boss`, exit 3 |
| Fractional `ticks`, non-positive duration | `clip-fractional-ticks` / `clip-nonpositive-duration`, exit 3 |
| Dangling socket/event/volume/material reference | matching `*-missing` / `*-unresolved` code, exit 3 |
