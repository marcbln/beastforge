# Development

## Setup

```bash
uv sync --all-groups
uv run beastforge --version
uv run beastforge validate --json
```

Prerequisites: Python 3.12+ and `uv`. The sibling texforge checkout is expected
at `../texforge`; override with `BEASTFORGE_TEXFORGE_LIBRARY` or
`--texforge-library`.

## Common commands

| Task | Command |
|------|---------|
| Run fast tests | `uv run pytest -m "not slow"` |
| Run all tests | `uv run pytest` |
| Determinism loop | `uv run pytest -m slow` |
| Lint | `uv run ruff check src tests` |
| Format check | `uv run ruff format --check src tests` |
| Type-check | `uv run mypy src` |
| Validate the library | `uv run beastforge validate` |
| Render one creature | `uv run beastforge render ridge-stalker -o /tmp/out` |
| Compare showroom | `uv run beastforge showroom` |
| Accept references | `uv run beastforge showroom --accept` |
| Browse the library | `uv run beastforge view --no-browser` |
| Export the static site | `uv run beastforge view --export /tmp/site --no-browser` |
| Browser smoke (opt-in) | `BEASTFORGE_VIEWER_SMOKE=1 uv run pytest -m viewer tests/viewer -q` |

Tests are layered:

- `tests/unit/` — canonical JSON, seeds, weights, skeleton, sweep, bake, GLB.
- `tests/contract/` — every `--json` payload against the published schemas.
- `tests/integration/` — CLI grammar, overwrite safety, dry-run, showroom.
- `tests/determinism/` — 100 pure builds and a two-directory render comparison.
- `tests/defect_corpus/` — one curated mutation per stable finding code.
- `tests/golden/` — committed `.glb`/manifest SHA-256 values.
- `tests/consumers/` — `trimesh` loads the skinned GLB.
- `tests/viewer/` — opt-in Playwright smoke check; skipped unless
  `BEASTFORGE_VIEWER_SMOKE=1` and the `viewer` dependency group is installed.

The browser smoke check is the only GPU/browser dependency:

```bash
uv sync --group viewer
uv run playwright install chromium
BEASTFORGE_VIEWER_SMOKE=1 uv run pytest -m viewer tests/viewer -q
```

The default suite stays offline and browser-free. The vendored three.js runtime
lives under `src/beastforge/viewer/third_party/three/`; upgrade all files and
`VERSION` together, then rerun the smoke check.

## Golden hashes

After an intended change, regenerate the committed hashes:

```bash
uv run python - <<'PY'
import hashlib, json, tempfile
from pathlib import Path
from beastforge.config import resolve_settings
from beastforge.render import render

root = Path.cwd()
settings = resolve_settings(cwd=root)
rows = {}
with tempfile.TemporaryDirectory() as tmp:
    for name in (
        "ash-crowned-tyrant",
        "ridge-stalker",
        "chitter-mite",
        "giraffe",
        "elephant",
    ):
        out = render(name, settings=settings, out_dir=f"{tmp}/{name}", force=True)
        rows[name] = {
            "glb": hashlib.sha256(out.glb).hexdigest(),
            "manifest": hashlib.sha256(out.manifest_text.encode()).hexdigest(),
        }
(root / "tests/golden/library.sha256").write_text(
    "\n".join(f"{name} {row['glb']} {row['manifest']}" for name, row in rows.items()) + "\n"
)
PY
uv run pytest tests/golden
```

Golden changes are reviewed like code: if the bytes changed, say why.

## Showroom references

References are committed under `showroom/reference/<creature>/`. Update them only
explicitly:

```bash
uv run beastforge showroom --accept
uv run beastforge showroom          # must pass immediately afterwards
```

## Preset versions

Preset files at `library/parts/<name>/<MAJOR.MINOR.PATCH>.yaml` are immutable
once published. To change a preset, add a new version file; never edit an
existing one, because assemblies pin an exact version.

```bash
uv run beastforge parts                       # every preset version
uv run beastforge parts organic-leg --json    # one preset's declared facts
uv run beastforge validate                    # resolves every pinned version
```

The canonical build digest includes the pinned preset documents, so editing a
version (which you must not do) changes the output bytes. Adding a new version
only changes assemblies that pin it. Regenerate goldens when an example
assembly's pinned preset or recipe changes.

## Adding a creature

1. Add `library/<category>/<name>.yaml` following [recipes.md](recipes.md).
2. Run `uv run beastforge validate <name>` and fix every finding.
3. Run `uv run beastforge render <name> -o /tmp/out` and inspect the package.
4. Avoid a showroom baseline until the creature looks right, then run
   `uv run beastforge showroom <name> --accept`.
5. Update the catalog index in [specs/README.md](../specs/README.md) if the
   feature list changes.

## Release

- The single version source is `src/beastforge/__init__.py::__version__`.
- Version numbers follow SemVer. The package metadata, `--version`, the
  manifest `toolVersion`, and the report `tool_version` all read that constant.
- Tag releases as annotated `vX.Y.Z` on the commit that produced the artifacts.
- Update [CHANGELOG.md](../CHANGELOG.md) in the same change.

## Conventions

Project conventions are generated by `ruleman export` into
[`_ai/conventions.md`](../_ai/conventions.md). Do not edit it by hand.
