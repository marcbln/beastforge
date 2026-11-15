# Contract: beastforge CLI surface

**Feature**: `001-procedural-creature-generator` · **Enforces**: FR-002, FR-005,
FR-007, FR-010, FR-011, FR-012, FR-034
**Sources**: [research.md](../research.md) D9/D10, [data-model.md](../data-model.md),
ADR 261114-2
**Conventions**: `_ai/conventions.md` → `cli:command-grammar`,
`cli:flag-vocabulary`, `cli:streams`, `cli:exit-codes`, `cli:version`,
`cli:about`, `cli:errors`, `cli:output`, `cli:interactivity`,
`cli:configuration`, `cli:feedback`

## Grammar (verb-first)

Single grammar: `beastforge <verb> [<subject>] [<flags>]`. Every top-level token
is a verb; the subject (a creature name or recipe path) is positional. This
document is the canonical command tree; `--help` is generated from the same
parser definition, so it cannot drift.

```text
beastforge list      [--category NAME] [--tag TAG]... [--json]
beastforge params    RECIPE [--json]
beastforge render    RECIPE [-o DIR] [--set KEY=VALUE]... [--force] [--dry-run] [--json]
beastforge validate  [RECIPE] [--json]
beastforge showroom  [RECIPE]... [--accept] [--json]
beastforge version
beastforge about
```

`RECIPE` is a library name (resolved across categories) or an explicit path.
An explicit path always wins; a bare name must resolve uniquely, otherwise
`ambiguous-name` (exit `4`).

## Global flags (every command)

Per `cli:flag-vocabulary`, defined once and never renamed:

| Flag | Meaning |
|------|---------|
| `-h`, `--help` | Print usage to **stdout**, exit 0 |
| `-V`, `--version` | Print `beastforge <semver>` to stdout, exit 0, before reading config |
| `-q`, `--quiet` | Suppress non-essential output; **never** suppresses errors |
| `-v`, `--verbose` | Add diagnostics on stderr |
| `--json` | Machine-readable output on stdout; no ANSI, no locale formatting, no human text |
| `--no-color` | Disable ANSI; also honors `NO_COLOR` |
| `-n`, `--no-interaction` | Never prompt; confirmations are treated as answered |
| `--dry-run` | Print the planned actions, apply nothing, exit 0 |
| `--config PATH` | Explicit config file |
| `--debug` / `--trace` | Show stack traces (hidden otherwise) |

Global flags are accepted before and after the subcommand. When `--dry-run` and
`--no-interaction` are combined, `--dry-run` wins and nothing is written.

## Streams (`cli:streams`)

- **stdout**: result data only — catalog, params, written paths, validation
  status, showroom results, `--json` payloads.
- **stderr**: progress, warnings, prompts, human diagnostics, errors.
- No color, spinner, or prompt is emitted into a pipe; TTYs are detected per
  stream. `--json` output is never decorated.

## Commands

### `beastforge list [flags]`

List library creatures by scanning `library/*/*.yaml` `meta` blocks on demand (no
index file). Filters: `--category NAME`; repeatable `--tag TAG` (AND semantics).
Human output is one aligned row per creature. `--json` → `library.list`
([schema/library.list.schema.json](./schema/library.list.schema.json)).
Generating nothing; agrees with FR-002 and US1 scenario 1.

### `beastforge params RECIPE [flags]`

Show the declared parameters of one recipe — name, type, default, unit, limits,
description — without generating anything (FR-003). `--json` → `params`
([schema/params.schema.json](./schema/params.schema.json)).

### `beastforge render RECIPE [flags]`

Generate the creature package non-interactively (FR-005).

| Flag | Default | Notes |
|------|---------|-------|
| `-o`, `--out DIR` | `dist/<name>/` | Output directory; created if missing |
| `--set KEY=VALUE` | — | Repeatable parameter override (FR-005, US1 scenario 4) |
| `--force` | off | Allow overwriting existing outputs (FR-012) |
| `--dry-run` | off | Print the plan; write nothing |
| `--json` | off | Emit the generation report |

Outputs, written as a single versioned pair:

```text
<out>/<name>.glb            # glTF 2.0 binary, textures embedded
<out>/<name>.manifest.json  # canonical JSON gameplay contract
```

On success, human mode prints both paths, their SHA-256 values, and a one-line
inventory summary; `--json` emits
[render.result.schema.json](./schema/render.result.schema.json). The command
runs the full validation gate on the staged bytes and only then commits.
Existing outputs without `--force` → exit `1` with `output-exists` and no write.
Unknown `--set` key → exit `3` with `recipe-unknown-param` and a nearest-name
suggestion; nothing is written.

### `beastforge validate [RECIPE] [flags]`

Run the gate without generating. With `RECIPE`, validate that recipe (schema,
skeleton, skin, clips, hooks, materials, budgets, determinism); with no argument,
validate every library creature (FR-034, US4 scenario 1). Success → exit `0`,
`valid: true`, zero error findings. Failure → exit `3` and a finding list; each
finding carries `code`, `severity`, `location`, `expected`, `actual`, `message`,
`remedy`. `--json` → `validate.result`
([schema/validate.result.schema.json](./schema/validate.result.schema.json)).

### `beastforge showroom [RECIPE]... [flags]`

Render turntable and extreme-bend frames for the named creatures (or the whole
library when none are named), compare them against the approved reference set
under fixed cameras and lighting, and emit a structural summary per creature
(FR-039–FR-041).

| Flag | Default | Notes |
|------|---------|-------|
| `--accept` | off | Rewrite references from the current output (explicit action only) |
| `--json` | off | Emit `showroom.result` |

Compare mode: per-creature `pass`/`fail`/`no-baseline`; any failure or missing
baseline exits `3` and names the differing frames. Acceptance never happens
implicitly. `--json` →
[schema/showroom.result.schema.json](./schema/showroom.result.schema.json).

### `beastforge version` / `beastforge about`

`cli:version` + `cli:about`: `version` prints `beastforge <semver>` to stdout,
exit 0, before reading config or touching the network. `about` prints name and
semver, a one-line purpose, maintainer, license, repository URL, documentation
path, and cheat-sheet path; exit 0, non-interactive. Root `--version`/`-V` is the
same surface as `version`.

## Exit codes (`cli:exit-codes`, research D9)

| Code | Meaning | Typical cause |
|------|---------|---------------|
| `0` | Success | Command did its job; `validate` found no errors |
| `1` | Runtime / IO failure | Unwritable output, `output-exists` without `--force`, interrupted write, unexpected internal error |
| `2` | Usage error | Unknown flag, missing required argument, malformed `--set` |
| `3` | Invalid input / gate failure | Recipe invalid, unknown parameter, missing texture recipe, showroom regression |
| `4` | Not found | Unknown creature name, ambiguous library name, unknown texforge recipe name |
| `128+n` | Terminated by signal n | e.g. `130` on Ctrl-C; no partial output |

Result data is never encoded in the exit code; severity and detail live in the
`--json` payload. An agent can branch on `2` (invocation wrong) vs `3` (input
wrong) vs `4` (name wrong) without parsing prose (SC-003).

## Error contract (agent-facing)

Any non-zero exit under `--json` emits exactly one error object and nothing else
on stdout:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "error",
  "error": {
    "code": "recipe-unknown-param",
    "message": "Parameter 'widht' is not declared by recipe 'ridge-stalker'.",
    "location": {"recipe": "library/quadruped/ridge-stalker.yaml", "path": "params"},
    "expected": "one of: width, height, girth",
    "actual": "widht",
    "remedy": "Use --set width=... or add the parameter to params[].",
    "suggestion": "width"
  }
}
```

Schema: [schema/error.schema.json](./schema/error.schema.json). Stack traces are
only shown behind `--debug`/`--trace`. Human mode prints the same facts as
`error: <message>` plus `hint: <remedy>` on stderr.

## Configuration (`cli:configuration`)

Resolution order: explicit flag → environment variable → project config
(`.beastforge.toml` in the working directory or an ancestor) → user config
(`$XDG_CONFIG_HOME/beastforge/config.toml`) → built-in default.

| Setting | Flag | Environment | Default |
|---------|------|-------------|---------|
| Library root | `--library` | `BEASTFORGE_LIBRARY` | `./library` (repo root) |
| texforge library root | `--texforge-library` | `BEASTFORGE_TEXFORGE_LIBRARY` | `../texforge/library` |
| Output directory | `-o/--out` | `BEASTFORGE_OUT` | `dist` |
| Color | `--no-color` | `NO_COLOR` | color on a TTY |

Values are validated at startup; a bad path is an actionable error, not a
traceback. No other tool's config file is read or written.

## Determinism-relevant guarantees (FR-008/FR-009)

- `--json` output is locale-independent and contains no timestamps.
- `timing_ms` is diagnostic only and never affects the hashes.
- The same recipe, resolved parameters, and tool version produce identical
  `.glb` and manifest bytes regardless of working directory, hostname, locale,
  timezone, clock, or process state.
- `--dry-run` reports the projected paths and does not create the staging
  directory.
