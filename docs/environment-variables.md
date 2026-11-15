# Environment variables

beastforge reads only its own variables plus the standard `NO_COLOR` and XDG
variables. Configuration resolves in the documented order: explicit flag →
environment → project `.beastforge.toml` → user
`$XDG_CONFIG_HOME/beastforge/config.toml` → built-in default. Values are
validated at startup; a bad path is an actionable error, not a traceback.

| Name | Purpose | Type / default | Required | Secret | Example | Used by |
|------|---------|----------------|----------|--------|---------|---------|
| `BEASTFORGE_LIBRARY` | Creature recipe library root | path / walk up for `library/` | optional | no | `/repo/library` | `library.py`, all catalog commands |
| `BEASTFORGE_TEXFORGE_LIBRARY` | texforge recipe library root | path / `../texforge/library` | optional | no | `/repo/texforge/library` | `config.py`, texforge adapter |
| `BEASTFORGE_OUT` | Base output directory | path / `dist` | optional | no | `/tmp/creatures` | `render` |
| `NO_COLOR` | Disable ANSI color | presence / unset | optional | no | `1` | CLI presentation |
| `XDG_CONFIG_HOME` | User config base directory | path / `~/.config` | optional | no | `/home/me/.config` | settings resolution |

## Project and user config

Project config is `.beastforge.toml` in the working directory or an ancestor:

```toml
library = "/repo/library"
texforge_library = "/repo/texforge/library"
output_dir = "dist"
color = "auto"       # auto | always | never
```

User config lives at `$XDG_CONFIG_HOME/beastforge/config.toml` with the same
keys. Pass `--config PATH` to read an explicit file.

## Precedence examples

```bash
# Environment overrides project/user config
BEASTFORGE_LIBRARY=/tmp/library beastforge list

# A flag overrides the environment
beastforge list --library /repo/library

# Disable color explicitly
NO_COLOR=1 beastforge list
```

## Failure behaviour

- A missing explicit library or texforge library is a `library-not-found` /
  `texforge-not-found` error with a corrective hint, never a traceback.
- Malformed TOML or an unknown config key exits `1` with `config-error`.
- Secrets are never read or written by beastforge.
