# beastforge agent guide

beastforge turns a declarative YAML recipe into an animated, skinned glTF 2.0
package plus a sidecar gameplay manifest. It is offline, deterministic, and
agent-first: every command has a stable `--json` surface and a documented exit
code.

**Use this skill when** you need to discover, render, remix, validate, or
regression-check a procedural 3D creature.

## Discover

```bash
beastforge list
beastforge list --json
beastforge list --category boss --json
beastforge params ridge-stalker --json
```

`--json` writes only the machine document to stdout. Progress, warnings, and
errors go to stderr. Exit codes: `0` success, `1` IO, `2` usage, `3` invalid
input/gate failure, `4` not found.

## Render

```bash
beastforge render ridge-stalker -o /tmp/creatures
beastforge render ridge-stalker --set body-length=3.1 --json
beastforge render ridge-stalker --dry-run --json
```

The output pair is `<out>/<name>.glb` and `<out>/<name>.manifest.json`. The GLB
embeds texforge-rendered textures. Re-running without `--force` exits `1` with
`output-exists`; nothing is overwritten. Generation stages in a temp directory
and commits both files atomically, so an interruption leaves no partial pair.

Reproducibility: the same recipe, resolved parameters, and tool version produce
byte-identical files on any machine, directory, locale, or clock.

## Browse and export

```bash
beastforge view                                   # loopback gallery, browsers open
beastforge view --no-browser --port 8765          # headless / fixed port
beastforge view --cache-dir /tmp/beastforge-view  # disposable asset cache
beastforge view --export site --force --no-browser # static bundle for Pages
```

The viewer is read-only: it never re-derives gameplay facts, regenerates
geometry, or applies `--set`. `catalog.json` v1.0 lists every loadable recipe
with relative `creatures/<name>/<recipeSha256>/...` URLs; the sidecar manifest
remains authoritative. Generation is lazy and content-addressed, so a recipe
change produces a new URL and stale requests return HTTP `409 stale-asset`.
`--json` emits one `ServeReport`/`ExportReport`; progress and warnings go to
stderr.

## Read the manifest

The manifest is the gameplay contract. Never read generator source to answer
gameplay questions.

```bash
jq -r '.clips[] | select(.name=="attack") | "\(.name) \(.duration)s"' package.manifest.json
jq -r '.events[] | select(.clip=="attack") | "\(.name) at \(.time)s"' package.manifest.json
jq -r '.sockets[] | select(.name=="maw") | "\(.target) + \(.offset)"' package.manifest.json
```

- `schemaVersion` is `MAJOR.MINOR`: same major = read and ignore unknown fields;
  different major = fail with `manifest-schema-unsupported`.
- `events[]` is the authoritative timing source.
- `playback.eventTimeScaling` is `"proportional"`: changing playback rate scales
  event times by the same factor.
- Units are metres, Y-up, forward −Z. `suggestedScale` is a uniform hint.

## Validate and self-correct

```bash
beastforge validate --json
beastforge validate ridge-stalker --json
```

Each finding has `code`, `severity`, `location {recipe, path}`, `message`,
`expected`, `actual`, `remedy`, and often a `suggestion`. Branch on the code and
fix the exact path. Common fixes:

| Code | Fix |
|------|-----|
| `recipe-unknown-param` | Use the `suggestion`, or declare the param |
| `recipe-unknown-field` | Remove the unknown key |
| `skeleton-*` | Fix the bone hierarchy/transform named in `location.path` |
| `clip-missing-core` | Add `idle`, `locomotion`, `attack`, `hurt`, `death` |
| `clip-event-out-of-range` | Move the event inside the clip duration |
| `volume-missing-hit` | Add a `role: hit` volume |
| `material-unresolved` | Reference a texforge recipe by name |
| `surface-unsupported-mode` | Use `mode: sweep` |
| `budget-exceeded` | Reduce geometry or raise a budget deliberately |

Validation is a gate: `render` runs the same gate before it commits. A package
cannot be produced that the gate would reject.

## Remix

1. Copy `library/<category>/<name>.yaml` to a new file.
2. Rename `meta.name` to the new file stem.
3. Bump `meta.version`.
4. Adjust params, skeleton, surfaces, clips, and hooks.
5. `beastforge validate <new-name>`, then render.

Recipes are inert data: no Python, no shell, no imports. Materials reference
texforge recipes by name. The skeleton is declared before surfaces; surfaces
bind to bone names.

## Regression-check

```bash
beastforge showroom
beastforge showroom ridge-stalker
beastforge showroom --accept      # explicit reference update only
```

The showroom renders fixed-camera turntable frames plus an extreme-bend pose,
compares them under a documented perceptual tolerance, and emits a structural
summary. A visual change is accepted only by an explicit `--accept`.

## Contribute

- Add a recipe under `library/<category>/<name>.yaml`.
- Run `beastforge validate <name>`, `pytest`, `ruff check src tests`,
  `mypy src`.
- Update `docs/`, `CHANGELOG.md`, and the spec index in `specs/README.md` when
  behavior changes.
- Golden hashes and showroom references change only for intended output changes;
  explain why in the change.

Read more: [README.md](README.md), [docs/recipes.md](docs/recipes.md),
[docs/api.md](docs/api.md), [docs/showroom.md](docs/showroom.md).
