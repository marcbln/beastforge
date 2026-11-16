# Contract: manifest 1.1 additive fields

**Feature**: `003-closed-part-library` · **Enforces**: FR-010, FR-011, FR-015,
FR-016
**Sources**: [data-model.md](../data-model.md) §7, [research.md](../research.md)
D9–D10, [controls.md](./controls.md)
**Canonical schema**: `specs/001-procedural-creature-generator/contracts/schema/manifest.schema.json`
(updated in place; all changes below are additive within major 1)

The manifest remains the shipped sidecar gameplay contract. Version 1.1 adds
part/control metadata and a clip source marker. It does not remove or rename any
1.0 field, and a 1.0 document remains valid and readable.

---

## 1. Versioning

- `schemaVersion` becomes `"1.1"`.
- Consumers remain **major-strict / minor-tolerant**:
  `read_manifest_compatible` accepts any `1.x` and rejects a different major.
- `REQUIRED_MANIFEST_FIELDS` is unchanged. `parts` and `clips[].source` are
  optional for a reader.
- The producer `Manifest` model defaults `parts` to `[]` and `ManifestClip.source`
  to `"authored"`, so existing 1.0 payloads still validate.

---

## 2. `clips[]` additions

### 2.1 `source`

| Value | Meaning |
|-------|---------|
| `authored` | the clip comes from a recipe `clips[]` entry |
| `automatic` | the clip was synthesized from part automatic behaviours |

`source` is optional; absence means `authored`. The synthesized clip is named
`baseline`, uses `generator: "baseline"`, has `loop: true`, and is deterministic.

### 2.2 `generator`

The enum gains `"baseline"`. No other generator names change. The schema's
`clips.minItems` changes from `5` to `0`, because an anatomy-neutral or static
asset may have no authored clips (and an auto-only asset has exactly one
synthesized clip). The five existing creatures still ship all five core clips.

### 2.3 Example

```json
"clips": [
  {
    "name": "idle",
    "duration": 2.0,
    "loop": true,
    "generator": "breathe",
    "source": "authored"
  },
  {
    "name": "baseline",
    "duration": 2.0,
    "loop": true,
    "generator": "baseline",
    "source": "automatic"
  }
]
```

For a static asset with no authored clips and no automatic behaviours, `clips`
is `[]`. For a craft whose only motion is a rotor's automatic rotation, `clips`
contains only the `baseline` entry.

---

## 3. `parts[]`

`parts` is an optional array. Each entry describes one resolved part instance and
its published controls.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `name` | string | yes | unique part name; identifier |
| `preset` | string | yes | preset name |
| `presetVersion` | string | yes | exact `MAJOR.MINOR.PATCH` |
| `presetSha256` | string | yes | 64 lowercase hex; canonical preset content hash |
| `family` | `organic \| mechanical \| vehicle` | yes | preset family |
| `controls` | array | yes | may be empty |

```json
"parts": [
  {
    "name": "front-left-leg",
    "preset": "organic-leg",
    "presetVersion": "1.0.0",
    "presetSha256": "3f0c…",
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
```

A 1.0 manifest has no `parts`; the viewer displays "not declared".

---

## 4. `parts[].controls[]`

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `address` | string | yes | `"<part>/<control>"`; unique across all parts |
| `name` | string | yes | control name |
| `joint` | string | yes | must exist in `skeleton.joints` |
| `axis` | `[number, number, number]` | yes | unit vector within `1e-6` |
| `mode` | `rotation \| translation` | yes | — |
| `unbounded` | boolean | yes | — |
| `range` | `{min, max}` | no | omitted when `unbounded` is true |
| `default` | number | yes | finite; inside the range when bounded |
| `units` | `deg \| m` | yes | matches mode |

Validation on the manifest (`check_manifest`):

- every control `joint` is in the skeleton joint set, otherwise
  `manifest-dangling-reference`;
- duplicate `address` values are `manifest-schema-invalid` (or a dedicated
  duplicate code);
- `units`/`mode` and `range`/`unbounded` invariants are re-checked because a
  consumer may hand-edit a manifest;
- a manifest that omits a part whose surface is in the recipe is a producer bug;
  the gate reports it rather than silently accepting it.

---

## 5. Compatibility matrix

| Document | `parts` | `clips[].source` | `baseline` generator | Read by this release |
|----------|---------|------------------|----------------------|----------------------|
| 1.0 | absent | absent | no | yes (defaults applied) |
| 1.1 | present or `[]` | present or absent | yes | yes |
| 2.x | any | any | any | rejected with `manifest-schema-unsupported` |

The viewer, `check_manifest`, and `read_manifest_compatible` all tolerate unknown
future minor fields. They never perform a partial read of a different major.

---

## 6. What is deliberately not published

- Automatic-behaviour descriptors (kind, period, rate, phase). They remain
  authoring-side and are baked into tracks. The synthesized `baseline` clip and
  its `source: "automatic"` marker are the discoverable evidence.
- Preset parameter defaults and override values. The resolved geometry and the
  `presetSha256` pin are published; the preset file is the authoring source.
- Closure reports. Closure is a generation gate, not a runtime fact. The absence
  of a gate failure is the contract that the part is closed.
- Interactive rig controls. The viewer is read-only in this release.

---

## 7. Schema edits in `specs/001-.../contracts/schema/manifest.schema.json`

- `schemaVersion` pattern unchanged (`^\d+\.\d+$`); producers emit `"1.1"`.
- `clips.minItems`: `5` → `0`.
- `clips.items.generator.enum`: add `"baseline"`.
- `clips.items.properties.source`: add optional `enum: ["authored", "automatic"]`.
- `properties.parts`: add optional array of `#/$defs/part` (not required).
- `$defs.part`: `{name, preset, presetVersion, presetSha256, family, controls}`,
  with `additionalProperties: false`.
- `$defs.control`: `{address, name, joint, axis, mode, unbounded, range?,
  default, units}`, with `additionalProperties: false`.
- No existing required field is removed or renamed. A 1.0 document without
  `parts` or `source` remains valid.
