# Contract: control channels and automatic behaviours

**Feature**: `003-closed-part-library` · **Enforces**: FR-008, FR-009, FR-012,
FR-013, FR-014, FR-015, FR-016
**Sources**: [data-model.md](../data-model.md) §1.4–§1.5, §2.2–§2.3, §6–§7,
[research.md](../research.md) D7–D9

This contract defines the two authoring-side declarations that turn a closed part
into something a clip, a game, or a viewer can drive:

- a **control channel** — a named, addressable articulation input;
- an **automatic behaviour** — a declarative ambient motion baked at generation
  time.

Both are declared on a preset and may be added or replaced on a part instance.
They use the same `@slot` bone-role mechanism as the preset surface.

---

## 1. Control channel

```yaml
controls:
  - name: swing
    joint: "@upper"
    axis: [1, 0, 0]
    mode: rotation
    range: {min: -35, max: 35}
    default: 0
    units: deg

  - name: extend
    joint: "@mount"
    axis: [0, 1, 0]
    mode: translation
    range: {min: 0.0, max: 0.25}
    default: 0.0
    units: m

  - name: spin
    joint: "@mount"
    axis: [0, 1, 0]
    mode: rotation
    unbounded: true
    default: 0
    units: deg
```

### 1.1 Fields

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `name` | identifier | yes | unique within the part |
| `joint` | `@slot` or bone | yes | must resolve to an existing bone |
| `axis` | 3 finite numbers | yes | non-zero and unit length within `1e-6`; rejected, not silently normalized |
| `mode` | `rotation` or `translation` | yes | closed enum |
| `range` | `{min, max}` | conditional | finite, `min <= max`; required for a bounded control |
| `unbounded` | boolean | no | normalization in §1.2 |
| `default` | number | yes | finite; inside `range` when bounded |
| `units` | `"deg"` or `"m"` | yes | `rotation` → `deg`; `translation` → `m` |

### 1.2 `unbounded` normalization

1. `unbounded` omitted and `range` present → bounded (`unbounded: false`).
2. `unbounded` omitted and `range` absent → unbounded (`unbounded: true`).
3. `unbounded: false` requires `range`; otherwise
   `part-control-range-invalid`.
4. `unbounded: true` forbids `range`; otherwise
   `part-control-range-invalid`.

An unbounded channel means the consumer may drive the joint arbitrarily (for
example a rotor or a continuous track). A bounded channel is clamped to its
range (for example a servo).

### 1.3 Address and uniqueness

The published address is:

```
<part-name>/<control-name>
```

`/` is not part of the identifier grammar, so the address splits unambiguously.
Control names are unique within a part; part names are unique across the asset;
therefore addresses are unique across the asset. The gate also checks the
flattened list and reports `part-control-address-duplicate` if a collision is
ever introduced.

### 1.4 Validation findings

| Condition | Finding |
|-----------|---------|
| duplicate control name in one part | `part-control-duplicate` |
| `joint` does not exist after binding | `part-control-joint-missing` |
| axis is zero, non-finite, or not unit | `part-control-axis-invalid` |
| `mode` is not rotation/translation | `part-control-mode-invalid` |
| `units` does not match mode | `part-control-units-mismatch` |
| range missing when bounded, present when unbounded, or `min > max` | `part-control-range-invalid` |
| default outside a bounded range or non-finite | `part-control-default-out-of-range` |
| duplicate address across parts | `part-control-address-duplicate` |

### 1.5 Published projection

Every resolved control is published in the manifest under its part:

```json
{
  "parts": [
    {
      "name": "front-left-leg",
      "preset": "organic-leg",
      "presetVersion": "1.0.0",
      "presetSha256": "…",
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

`range` is omitted (or `null` in the model) when `unbounded` is true. The viewer
renders exactly these values; it never re-derives them.

---

## 2. Automatic behaviour

Automatic behaviours are authoring-side only. They are baked into animation tracks
and are **not** published as a runtime composition API. The synthesized baseline
clip is the only manifest evidence.

```yaml
auto:
  - name: breathe
    kind: breathe
    joint: "@spine-2"
    amplitude: 0.03
    period: 2.0
    phase: 0

  - name: spin
    kind: rotate
    joint: "@mount"
    axis: [0, 1, 0]
    rate: 90
    phase: 0
```

### 2.1 Variants

| Kind | Required fields | Units and meaning |
|------|-----------------|-------------------|
| `breathe` | `name`, `joint`, `amplitude`, `period` | `amplitude` is a scale ratio (> 0); `period` seconds (> 0); `phase` degrees (default 0) |
| `bob` | `name`, `joint`, `axis`, `amplitude`, `period` | `amplitude` metres (> 0); translation along `axis`; `phase` degrees |
| `sway` | `name`, `joint`, `axis`, `amplitude`, `period` | `amplitude` degrees (> 0); rotation about `axis`; `phase` degrees |
| `rotate` | `name`, `joint`, `axis`, `rate` | `rate` degrees/second (non-zero); `phase` is the initial angle in degrees |

`axis` follows the control-axis rule (finite, unit vector within `1e-6`).
`breathe` is an isotropic scale pulse and therefore has no meaningful axis; it is
the one variant that omits `axis`. Every directional behaviour (`bob`, `sway`,
`rotate`) requires it. `name` is an identifier, unique within the part, and is
used only for merging a preset behaviour with an instance override.

### 2.2 Evaluation

For time `t` in seconds, with `φ = radians(phase)`:

```
breathe:  s = 1 + amplitude * sin(2π t / period + φ)
          delta.scale = [s, s, s]

bob:      delta.translation = axis * amplitude * sin(2π t / period + φ)

sway:     angle = radians(amplitude) * sin(2π t / period + φ)
          delta.rotation = quat(axis, angle)

rotate:   delta.rotation = quat(axis, radians(rate * t + phase))
```

### 2.3 Composition

When more than one behaviour targets the same joint, they compose in declaration
order:

- translations sum;
- rotations multiply as Hamilton quaternions and are normalized;
- scales multiply component-wise.

The composition order is part of the determinism contract.

### 2.4 Validation findings

| Condition | Finding |
|-----------|---------|
| duplicate auto name in one part | `part-auto-duplicate` |
| `joint` does not exist after binding | `part-auto-joint-missing` |
| axis is zero, non-finite, or not unit | `part-auto-axis-invalid` |
| amplitude is missing, non-finite, or `<= 0` | `part-auto-amplitude-invalid` |
| period is missing, non-finite, or `<= 0` | `part-auto-period-invalid` |
| rate is missing, non-finite, or zero | `part-auto-rate-invalid` |

### 2.5 Baking and precedence

For every authored clip:

1. Build the generator's `dict[joint, function]`.
2. For each resolved automatic behaviour whose `joint` is **not** in that dict,
   add the composed automatic function.
3. Bake at 60 Hz.

Therefore an explicit clip always wins for a joint it animates. Automatic motion
fills only the joints the clip leaves alone. This is FR-016.

### 2.6 Synthesized baseline clip

When `recipe.clips` is empty and the asset has automatic behaviours:

- one clip named `baseline` is synthesized;
- `generator` is `baseline`, `source` is `automatic`, `loop` is `true`;
- `duration = max(2.0, max(period of periodic behaviours))`, capped at
  `budgets.max_clip_ticks / 60`;
- only `rotate` behaviours → duration `2.0`;
- the clip is baked with the same 60 Hz sampler and is byte-deterministic;
- it is published in the manifest so consumers can discover it.

A recipe may not author a clip named `baseline`; the name is reserved for the
synthesized clip (`clip-duplicate` or a dedicated finding).

When `recipe.clips` is empty and there are no automatic behaviours, the asset is
valid and the manifest's `clips` array is empty. No clip is invented.

---

## 3. Determinism

- Behaviour evaluation uses `math.sin`, `math.cos`, and fixed-order quaternion
  multiplication only.
- No RNG, wall clock, or host state is read.
- Automatic motion is baked into the 60 Hz samples, so two builds of the same
  recipe and pinned presets are byte-identical.
- The synthesized baseline's duration and name do not depend on dictionary
  iteration order.
