# Contract: `beastforge parts`

**Feature**: `003-closed-part-library` · **Enforces**: FR-004, FR-006
**Sources**: [research.md](../research.md) D16, [parts-grammar.md](./parts-grammar.md)
**JSON schema**: [parts.list.schema.json](./parts.list.schema.json)

`beastforge parts` is the read-only discovery surface for the part-preset library.
It follows the existing noun-command pattern (`beastforge params NAME`) and the
repository's global flag vocabulary.

---

## 1. Grammar

```text
beastforge parts [NAME] [OPTIONS]
```

| Form | Behavior |
|------|----------|
| `beastforge parts` | list every preset version in the library |
| `beastforge parts organic-leg` | list every version of `organic-leg` |
| `beastforge parts organic-leg --version 1.0.0` | show exactly one version |
| `beastforge parts --family vehicle` | list only the vehicle family |
| `beastforge parts --json` | emit the stable JSON document |

`NAME` must be a preset name. A path is not accepted; presets are library data,
not arbitrary files.

### 1.1 Options

| Option | Meaning |
|--------|---------|
| `--family organic\|mechanical\|vehicle` | filter by family; invalid value is a usage error (exit 2) |
| `--version MAJOR.MINOR.PATCH` | exact version; requires `NAME`; invalid semver is exit 2 |
| `--json` | machine-readable document on stdout; no ANSI, no decorations |
| `-q` / `--quiet` | suppress the human table; still prints errors |
| `-v` / `--verbose` | add preset paths and file scan diagnostics on stderr |
| `--no-color` | disable ANSI; also honors `NO_COLOR` |
| `-n` / `--no-interaction` | no prompts (the command never prompts) |
| `--dry-run` | accepted as a no-op; the command never writes |

Global flags are accepted before and after the verb, exactly as the root callback
already implements.

---

## 2. Streams and exit codes

- Preset table or JSON → stdout.
- Scan warnings, malformed-file diagnostics, and verbose paths → stderr.
- Exit `0` on success.
- Exit `2` for a usage error (unknown flag, invalid family, invalid version, or
  `--version` without `NAME`).
- Exit `3` for a malformed preset file that prevents listing.
- Exit `4` for an unknown preset name.
- Exit `1` for an unexpected IO failure.
- Exit `130` on Ctrl-C.

No result data is encoded in the exit code.

---

## 3. Human output

A compact table, one row per preset version, sorted by `(name, semver)`:

```text
NAME                  FAMILY       VERSION  CONTROLS  AUTO  DESCRIPTION
mech-armor-plate      mechanical   1.0.0    0         0     Closed rigid armor plate.
mech-leg              mechanical   1.0.0    2         0     Closed articulated mech leg.
organic-leg           organic      1.0.0    2         0     Closed tapered organic leg.
vehicle-rotor         vehicle      1.0.0    1         1     Closed rotor with spin control.
```

For a single `NAME`, print a heading and fact grid:

```text
organic-leg 1.0.0 (organic)
Closed tapered organic leg.
Path: library/parts/organic-leg/1.0.0.yaml
Preset sha256: 3f0c…

Parameters
NAME          TYPE   DEFAULT  RANGE        UNIT
radius-start  float  0.12     0.02..0.5    m
radius-end    float  0.05     0.01..0.5    m
rings         int    10       4..32        count

Controls
NAME   JOINT   MODE      AXIS          RANGE       DEFAULT  UNITS
swing  @upper  rotation  [1, 0, 0]     -35..35     0        deg
lift   @lower  rotation  [1, 0, 0]     -60..10     0        deg

Automatic behaviours
(none)
```

The table obeys `cli:presentation` (shared Rich theme, no raw ANSI) and
`cli:accessibility` (text carries meaning; color is not the only signal).

---

## 4. JSON document

```json
{
  "schema_version": "1",
  "tool_version": "0.2.0",
  "status": "ok",
  "presets": [
    {
      "name": "organic-leg",
      "family": "organic",
      "version": "1.0.0",
      "description": "Closed tapered organic leg.",
      "path": "library/parts/organic-leg/1.0.0.yaml",
      "sha256": "3f0c…",
      "params": [
        {
          "name": "radius-start",
          "type": "float",
          "default": 0.12,
          "min": 0.02,
          "max": 0.5,
          "unit": "m",
          "description": "Radius at the root."
        }
      ],
      "controls": [
        {
          "name": "swing",
          "joint": "@upper",
          "axis": [1.0, 0.0, 0.0],
          "mode": "rotation",
          "unbounded": false,
          "range": {"min": -35.0, "max": 35.0},
          "default": 0.0,
          "units": "deg"
        }
      ],
      "auto": [
        {
          "name": "breathe",
          "kind": "breathe",
          "joint": "@spine-2",
          "amplitude": 0.03,
          "period": 2.0,
          "phase": 0.0
        }
      ]
    }
  ],
  "warnings": [
    {"path": "library/parts/broken/9.9.9.yaml", "message": "preset-file-invalid: …"}
  ]
}
```

Rules:

- `presets` is sorted by `(name, semver)`; semantic version comparison is numeric
  per component, never a lexical string sort.
- `params` is sorted by name; `controls` and `auto` preserve declaration order.
- `range` is omitted for an unbounded control; `unbounded` is always present.
- All numbers are finite JSON numbers; no NaN/Infinity.
- `path` is project-relative where possible.
- `sha256` is the canonical preset document hash.
- `warnings` is sorted by path then message.
- The document is canonical JSON with a trailing newline, matching the other CLI
  surfaces.
- `--quiet --json` still prints the document (quiet affects human output only).

The JSON document validates against [parts.list.schema.json](./parts.list.schema.json).

---

## 5. Errors

| Situation | Code | Exit | Message shape |
|-----------|------|------|---------------|
| Unknown preset name | `part-preset-missing` | 4 | names the value, lists nearest names or `beastforge parts` |
| Unknown version | `part-preset-version-missing` | 4 | lists available versions |
| Invalid `--family` | `usage-error` | 2 | names the value and the allowed enum |
| Invalid `--version` | `usage-error` | 2 | names the value and the `MAJOR.MINOR.PATCH` shape |
| Malformed preset file | `preset-file-invalid` | 3 | path, parser/model error, remedy |
| Missing `library/parts` | `parts-library-missing` | 4 | run from the repo root or pass `--library` |

Errors go to stderr in human mode and to the existing error JSON shape when
`--json` is present.

---

## 6. Determinism

`parts` reads files only and writes nothing. Two invocations over the same files
produce identical JSON. It never generates geometry, renders textures, or touches
the viewer cache.
