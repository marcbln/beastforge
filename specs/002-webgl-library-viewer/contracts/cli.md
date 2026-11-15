# Contract: `beastforge view`

**Status**: normative for feature 002
**Related**: [viewer HTTP contract](./viewer-http.md),
[catalog contract](./catalog.md), [catalog schema](./catalog.schema.json)

## Grammar

```text
beastforge view [--export DIR] [--port N] [--cache-dir DIR] [--no-browser]
                [--force] [--dry-run] [--json] [-q|--quiet] [-v|--verbose]
                [--no-color] [-n|--no-interaction]
```

`view` is a single verb; there are no subcommands. It reuses the existing global
flags (`--library`, `--texforge-library`, `--config`, `--debug`, `--trace`,
`-V/--version`) before or after the verb, exactly like the other commands.

### Mode selection

| Invocation | Mode | Behaviour |
|------------|------|-----------|
| `beastforge view` | serve | Starts the loopback server, opens the browser, prints the URL and stop instruction. |
| `beastforge view --export DIR` | export | Writes a self-contained static bundle and exits. |
| `beastforge view --dry-run` | dry run | Prints the URL/cache that would be used, binds nothing, exits 0. |
| `beastforge view --export DIR --dry-run` | dry run | Prints the planned bundle paths/counts, writes nothing, exits 0. |

### Flags

| Flag | Mode | Default | Meaning |
|------|------|---------|---------|
| `--export DIR` | export | — | Write the static bundle to `DIR`. |
| `--port N` | serve | `0` (ephemeral) | Bind `127.0.0.1:N`. `0` chooses a free port. |
| `--cache-dir DIR` | serve | XDG cache | Local generation cache. See precedence below. |
| `--no-browser` | both | off | Do not call `webbrowser.open`. The URL is still printed. A no-op in export mode. |
| `--force` | export | off | Replace the exporter's own outputs in a non-empty target; never touches unrelated files. |
| `--dry-run` | both | off | Print the plan; write/bind nothing. |
| `--json` | both | off | Emit one machine document (below). In serve mode it implies `--no-browser`. |
| `-q/--quiet` | both | off | Suppress progress diagnostics; never errors. |
| `-v/--verbose` | both | off | Extra diagnostics on stderr. |
| `--no-color` | both | off | Disable ANSI; honors `NO_COLOR`. |
| `-n/--no-interaction` | both | off | Never prompt. A non-empty export target without `--force` fails with an actionable error. |

Invalid combinations are usage errors (exit `2`) with a remedy:

- `--export` with `--port` or `--cache-dir`.
- `--force` without `--export`.
- `--port` outside `1..65535` when non-zero.

`--library`, `--texforge-library`, and `--config` follow the existing
configuration precedence (`cli:configuration`).

`--dry-run` always wins over `--force`: it prints the plan and exits 0 without
binding or writing. If a real export would refuse a non-empty target, the dry run
says so but still exits 0.

### Cache resolution

1. `--cache-dir DIR`
2. `BEASTFORGE_CACHE_DIR`
3. `cache_dir` in project `.beastforge.toml` or user
   `$XDG_CONFIG_HOME/beastforge/config.toml`
4. `$XDG_CACHE_HOME/beastforge/viewer`, else `~/.cache/beastforge/viewer`

The resolved path is printed in serve mode and is never inside tracked
repository content by default.

## Output

### Human

Serve, on stdout (one line each):

```text
viewer: http://127.0.0.1:54321/
cache:  /home/me/.cache/beastforge/viewer
serving the current library; press Ctrl-C to stop
```

Generation progress and warnings go to stderr, prefixed:

```text
generating ridge-stalker (a1b2c3d)…
ready ridge-stalker
warning: library/other/broken.yaml: …
```

Export, on stdout:

```text
exported 5 creatures / 47 files to site
```

Warnings go to stderr. `--quiet` suppresses progress and the informational
warning lines but never errors.

### `--json`

Serve mode emits exactly one document once the socket is bound, then keeps
serving; subsequent diagnostics stay on stderr:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "ok",
  "mode": "serve",
  "url": "http://127.0.0.1:54321/",
  "cache_dir": "/home/me/.cache/beastforge/viewer",
  "dry_run": false
}
```

Export mode emits:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "status": "ok",
  "mode": "export",
  "output": "site",
  "creatures": ["ash-crowned-tyrant", "chitter-mite", "elephant", "giraffe", "ridge-stalker"],
  "files": 47,
  "warnings": [],
  "dry_run": false
}
```

`--dry-run` sets `"dry_run": true`; serve dry-run reports the resolved cache and
`"url": null` (no port is bound). Failures use the standard error document.

## Export semantics

- Output layout, determinism, and ordering are specified in
  [catalog.md](./catalog.md#static-bundle-bundlejson).
- A non-empty target is refused without `--force`:
  code `export-exists`, exit `1`, remedy "pass `--force` or choose an empty
  directory".
- With `--force`, only `index.html`, `assets/`, `catalog.json`, `bundle.json`,
  and `creatures/` are replaced; any other file in the target is preserved.
- A recipe that cannot be parsed is a non-fatal warning recorded in
  `catalog.json`. A recipe that loads but fails validation/generation aborts the
  export (exit `3`) and leaves no partial bundle, because the published catalog
  must never reference a missing asset.
- No file under the repository source tree is created or modified by an export
  outside the target directory.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Serve stopped cleanly, export succeeded, or dry-run printed its plan. |
| `1` | IO/cache/bind failure (`io-failure`, `export-exists`). |
| `2` | Usage error (invalid flag combination, bad port, missing argument). |
| `3` | Gate/generation failure during export. |
| `4` | Library not found (`library-not-found`). |
| `130` | Interrupted by Ctrl-C. |

An on-demand generation failure in serve mode does **not** stop the process; it
returns an HTTP `500` for that creature and the process still exits `0` on a
clean stop.

## Examples

```bash
# Default: open the current library in the browser
beastforge view

# CI or headless: bind a known port, no browser
beastforge view --no-browser --port 8765

# Pin a cache for a reproducible demo
beastforge view --cache-dir /tmp/beastforge-view

# Machine-readable URL, then keep serving
beastforge view --json

# Build the publishable bundle
beastforge view --export site --force --no-browser

# Show what an export would write
beastforge view --export site --dry-run
```

## Cheat-sheet entries (must stay in sync with `--help`)

| Task | Command |
|------|---------|
| Browse the library | `beastforge view` |
| Serve without opening a browser | `beastforge view --no-browser` |
| Serve on a fixed port | `beastforge view --port {{port}}` |
| Use a custom cache | `beastforge view --cache-dir {{dir}}` |
| Export the static site | `beastforge view --export {{dir}}` |
| Replace an earlier export | `beastforge view --export {{dir}} --force` |
| Preview an export | `beastforge view --export {{dir}} --dry-run` |
