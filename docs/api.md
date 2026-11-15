# API and machine surfaces

beastforge has one stable `--json` document per command. Success and failure are
signalled by the exit code; the document shape is validated in `tests/contract/`
against the schemas under
[`specs/001-procedural-creature-generator/contracts/schema/`](../specs/001-procedural-creature-generator/contracts/schema/).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Runtime / IO failure (`output-exists`, `io-failure`) |
| `2` | Usage error (unknown flag, missing argument, malformed `--set`) |
| `3` | Invalid input / gate failure (recipe, skin, clips, material, showroom regression) |
| `4` | Not found (unknown creature, ambiguous name, missing texforge recipe) |
| `128+n` | Terminated by signal `n` (e.g. `130` on Ctrl-C) |

Results never hide in the exit code: the payload carries the detail. Error
payloads are a single object:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "error",
  "error": {
    "code": "recipe-unknown-param",
    "message": "Parameter 'widht' is not declared by recipe 'ridge-stalker'.",
    "location": {"recipe": "library/quadruped/ridge-stalker.yaml", "path": "params"},
    "expected": "one of: body-length, seed",
    "actual": "widht",
    "remedy": "Use --set body-length=... or add the parameter to params[].",
    "suggestion": "body-length"
  }
}
```

## Commands

### `list --json`

Emits `{schema_version, tool_version, status, creatures[]}`. Each creature has
`name`, `category`, `description`, `tags`, `params`, `tested_with`, `version`,
and project-relative `path`. Nothing is generated. Filters: `--category NAME`,
repeatable `--tag TAG`.

### `params RECIPE --json`

Emits `{schema_version, tool_version, status, recipe, name, params[]}`. Each
param has `name`, `type`, `default`, `description`, and optional `min`, `max`,
`values`, `unit`.

### `render RECIPE --json`

Emits the generation report:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "ok",
  "dry_run": false,
  "outputs": {
    "glb": {"path": "...", "sha256": "...", "bytes": 12345},
    "manifest": {"path": "...", "sha256": "...", "bytes": 6789},
    "textures": [{"name": "hide", "sha256": "...", "width": 512, "height": 512, "recipe": "granite"}]
  },
  "inventory": {"clips": [], "events": [], "sockets": [], "volumes": [], "phases": []},
  "effective_params": {},
  "provenance": {"recipe": "...", "recipe_sha256": "...", "tool_version": "0.1.0"},
  "warnings": [],
  "timing_ms": 1234.5
}
```

`--dry-run` reports the projected paths and writes nothing; `sha256`/`bytes` are
absent. `timing_ms` is diagnostic only and never affects byte identity.

### `validate [RECIPE] --json`

Emits `{schema_version, tool_version, status, valid, scope, findings[], summary}`.
Each finding carries `code`, `severity`, `location {recipe, path}`, `message`,
`expected`, `actual`, `remedy`, and an optional `suggestion`. Error-severity
findings map to exit `3`; warnings never change the exit code. The closed code
vocabulary is in
[`data-model.md`](../specs/001-procedural-creature-generator/data-model.md) §16.

### `showroom [RECIPE]... --json`

Emits `{schema_version, tool_version, status, mode, tolerance, creatures[]}`.
Each creature has `frames[]` (`view`, `pose`, `path`, `sha256`), an exact
`structural` summary (joints, clips, events, skin-influence histogram, bounds,
counts), and a `comparison {status, differing_frames[], metrics}`. Status is
`pass`, `fail`, or `no-baseline`; a failure or missing baseline exits `3`.
`--accept` rewrites references explicitly.

## Manifest consumer guide

The sidecar `<name>.manifest.json` is the gameplay contract. Its
`schemaVersion` is `MAJOR.MINOR`.

1. **Major-strict, minor-tolerant.** Compare the major component only. Same
   major: read the manifest and ignore unknown fields. Different major: reject
   with `manifest-schema-unsupported`; never perform a partial read.
2. **Events are authoritative.** Read `events[]` for impact, fire, footstep,
   and death timing. Baked keyframes are never inspected for gameplay timing.
3. **Reserved names are public.** `idle`, `locomotion`, `attack`, `hurt`, and
   `death` are required. Renaming or removing one is a major schema change.
4. **Playback scaling.** `playback.eventTimeScaling` is `"proportional"` and
   `playback.warning` is non-empty: changing playback rate scales every event
   time by the same factor.
5. **Units and orientation.** Geometry is metres, Y-up, forward −Z.
   `suggestedScale` is a uniform consumer hint.
6. **Hooks.** Sockets target a joint plus a bone-local offset. Volumes are box
   proxies with a role (`hit`, `weak-point`, `collision`) and optional follow
   bone. Boss phases are health fractions.

A consumer that ignores the manifest still gets a working animated creature;
it simply loses the semantic gameplay data.

## Versioning

Two independent versions exist:

- **Report schema** (`schema_version: "1"`): the CLI's machine surface.
  Additive fields keep `"1"`; a breaking reshape bumps it.
- **Manifest schema** (`schemaVersion: "MAJOR.MINOR"`): the shipped consumer
  contract. Additive minor changes are safe; removing or renaming required
  names/fields requires a major bump.

Finding codes are additive. Renaming or removing a code is a major change to
the validation contract.
