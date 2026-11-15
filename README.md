# beastforge

**Offline, deterministic procedural 3D creature generator.** beastforge turns a
declarative YAML recipe into an animated, skinned glTF 2.0 package (`.glb`) plus
a sidecar gameplay manifest (`*.manifest.json`). It is built for AI coding agents
and developers: discover creatures from an in-repo library, render with `--set`
overrides, validate and self-correct through a stable `--json` finding list, and
accept visual changes only explicitly.

The primary contract is in [specs/001-procedural-creature-generator/](specs/001-procedural-creature-generator/):
one standard asset, one manifest, byte-identical output for the same recipe,
parameters, and tool version.

## Prerequisites

- Python 3.12+ (3.12 is the target)
- [`uv`](https://docs.astral.sh/uv/)
- The sibling [`texforge`](../texforge) checkout for texture recipes
  (`BEASTFORGE_TEXFORGE_LIBRARY` defaults to `../texforge/library`)

No network access is needed at runtime.

## Install

```bash
uv sync --all-groups
uv run beastforge --version
```

## Quick start

```bash
# Discover the library
uv run beastforge list
uv run beastforge list --category boss --json

# Inspect declared parameters without generating
uv run beastforge params ridge-stalker

# Generate one creature package
uv run beastforge render ridge-stalker -o /tmp/creatures

# Validate the whole shipped library
uv run beastforge validate

# Compare rendered frames with the approved showroom references
uv run beastforge showroom
```

Generated outputs are a pair:

```text
/tmp/creatures/ridge-stalker.glb
/tmp/creatures/ridge-stalker.manifest.json
```

The `.glb` embeds the rendered texforge texture set; no loose texture files are
written. `render` runs the full validation gate before it commits the pair and
refuses to overwrite existing outputs unless `--force` is passed.

## Configuration

Resolution order: explicit flag → environment → project `.beastforge.toml` in
the working directory (or an ancestor) → user
`$XDG_CONFIG_HOME/beastforge/config.toml` → built-in default.

See [docs/environment-variables.md](docs/environment-variables.md) for the full
table.

## Development

```bash
uv run pytest                 # unit, contract, integration, defect, consumer tests
uv run pytest -m slow         # determinism loop and full render comparisons
uv run ruff check src tests
uv run mypy src
```

See [docs/development.md](docs/development.md) for setup, golden and showroom
workflows, and release steps. Architecture is in
[docs/architecture.md](docs/architecture.md); the machine surface is documented
in [docs/api.md](docs/api.md); recipe authoring is in
[docs/recipes.md](docs/recipes.md).

## License

MIT.
