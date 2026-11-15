# Contract: machine-readable JSON surfaces

**Feature**: `001-procedural-creature-generator` · **Enforces**: FR-002,
FR-007, FR-010, FR-029, FR-030, FR-034, FR-040
**Sources**: [data-model.md](../data-model.md), [cli.md](./cli.md),
[research.md](../research.md) D8/D9/D11

Every command has one stable `--json` document on stdout, containing no
human-only text. Success and failure are signalled by exit code (see
[cli.md](./cli.md)); the document shape is validated in
`tests/contract/` against the schemas below.

## Schema index

| File | Emitted by | Purpose |
|------|------------|---------|
| [schema/manifest.schema.json](./schema/manifest.schema.json) | written as `<name>.manifest.json` | The shipped gameplay contract (clips, events, sockets, volumes, phases, materials, provenance) |
| [schema/render.result.schema.json](./schema/render.result.schema.json) | `render --json` | Generation report: paths, hashes, inventory, effective params, provenance |
| [schema/validate.result.schema.json](./schema/validate.result.schema.json) | `validate --json` | Gate result: findings, counts, scope |
| [schema/library.list.schema.json](./schema/library.list.schema.json) | `list --json` | Catalog entries with parameters |
| [schema/params.schema.json](./schema/params.schema.json) | `params --json` | One recipe's declared knobs |
| [schema/showroom.result.schema.json](./schema/showroom.result.schema.json) | `showroom --json` | Frames, structural summary, per-creature comparison |
| [schema/error.schema.json](./schema/error.schema.json) | any failing command under `--json` | Exactly one actionable error object |
| [schema/recipe.schema.json](./schema/recipe.schema.json) | — (authoring contract) | Structural schema for `library/**/*.yaml` |

## Versioning

Two independent versions exist and must not be confused:

- **Report schema** (`schema_version`, string `"1"` in every `--json` output):
  describes the CLI's own machine surface. Additive fields keep `"1"`; a
  breaking reshape bumps it.
- **Manifest schema** (`schemaVersion`, `"MAJOR.MINOR"` inside the shipped
  manifest): describes the consumer contract. Minor additions are safe; a major
  bump is required for removing/renaming reserved names or required fields
  (FR-029, FR-032).

The manifest's `toolVersion` and the report's `tool_version` come from one source
(`beastforge.__version__`) and match the released package.

## Manifest consumer rules (normative)

1. Compare `schemaVersion` major only. Same major → read; ignore unknown fields.
   Different major → fail with `manifest-schema-unsupported`, never a partial
   read (FR-029, SC-010).
2. Treat manifest `events[]` as the only gameplay timing source; never derive
   timing from baked keyframes (FR-031).
3. Names of clips, sockets, events, and phases are a public contract. A package
   that renames one of the reserved clips is a major-version change (FR-032).
4. `playback.eventTimeScaling` is `"proportional"` and `playback.warning` is
   non-empty: changing playback rate scales every event time by the same factor
   (FR-033).
5. `suggestedScale` is a hint applied uniformly to the imported scene; geometry
   is metres, Y-up, −Z forward (FR-027).

## Validation finding codes

`validate.result.findings[].code` is a closed vocabulary. The canonical list and
grouping is in [data-model.md](../data-model.md) §16. Rules:

- Codes are stable once released; renaming/removing one is a major change.
- Adding a code is additive and keeps `schema_version: "1"`.
- Every error-severity finding maps to exit `3`; warnings never change the exit
  code.
- Every defect class in the seeded corpus asserts exactly its expected code
  (SC-004).

## Error mapping

| Exit | `error.code` examples | JSON schema |
|------|----------------------|-------------|
| `2` | `usage-error`, `flag-unknown`, `set-syntax` | `error.schema.json` |
| `3` | `recipe-syntax`, `recipe-unknown-param`, `skin-weight-sum`, `material-unresolved` | `error.schema.json` (single error) or `validate.result.schema.json` (list) |
| `4` | `recipe-not-found`, `ambiguous-name`, `texture-not-found` | `error.schema.json` |
| `1` | `output-exists`, `io-failure`, `internal-error` | `error.schema.json` |

`validate` always reports through `validate.result.schema.json` (a list), even
when the list is empty; other commands report a single `error` object.

## Contract test obligations

- Feed one live payload per schema through `jsonschema.validate` in
  `tests/contract/`.
- Validate each generated manifest against `manifest.schema.json` and each
  library recipe against `recipe.schema.json`.
- Assert `additionalProperties: false` catches an accidentally added CLI field
  before release (deliberate negative fixtures).
- Assert a manifest with a bumped major is rejected by the consumer fixture
  helper (SC-010).
