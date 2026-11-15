# Quickstart & Validation Guide: Procedural 3D Creature Generator

**Feature**: `001-procedural-creature-generator` | **Date**: 2026-11-14
**Inputs**: [spec.md](./spec.md), [plan.md](./plan.md),
[contracts/cli.md](./contracts/cli.md), [data-model.md](./data-model.md)

Runnable scenarios that prove the feature works end to end. This is a validation
guide, not a replacement for `tasks.md`; it names commands and expected
outcomes, not implementation code.

## Prerequisites

- Python 3.12+ available (3.12 is the target; 3.13/3.14 should pass the same
  suite).
- `uv` installed (`uv --version`).
- The sibling `texforge` checkout at `../texforge` (or set
  `BEASTFORGE_TEXFORGE_LIBRARY` / `--texforge-library`).
- Optional: Node 20+ for the independent `@gltf-transform/cli` import check.
- No network access needed at runtime (SC-001).

## 1. Setup

```bash
# -- install deps and the console script from the lockfile
uv sync --all-groups

# -- sanity: version surfaces (cli:version)
uv run beastforge --version
uv run beastforge version
uv run beastforge about
```

Expected: `beastforge <semver>` on stdout, exit 0, no config read.

## 2. Discover the library (FR-002, FR-003, SC-006)

```bash
# -- catalog scan, human + machine
uv run beastforge list
uv run beastforge list --json | jq '.creatures[] | {name, category, path}'

# -- filter by category and tag
uv run beastforge list --category boss

# -- inspect declared parameters without generating
uv run beastforge params ash-crowned-tyrant
uv run beastforge params ash-crowned-tyrant --json | jq '.params'
```

Expected: every shipped creature appears with name, category, description, and
parameters; each command finishes under 2 s; no output files are created.

## 3. Generate one creature (FR-005–FR-013, SC-001)

```bash
# -- clean output directory
rm -rf /tmp/beastforge-out

# -- generate the boss package
uv run beastforge render ash-crowned-tyrant -o /tmp/beastforge-out

# -- inspect the pair
ls -la /tmp/beastforge-out
sha256sum /tmp/beastforge-out/*.glb /tmp/beastforge-out/*.manifest.json

# -- machine-readable report
uv run beastforge render ash-crowned-tyrant -o /tmp/beastforge-out-2 --json \
  | jq '{glb: .outputs.glb, manifest: .outputs.manifest, clips: .inventory.clips}'
```

Expected: exactly `<name>.glb` and `<name>.manifest.json`; the report lists both
paths, their SHA-256, the clip/event/socket/volume/phase inventory, and
provenance. The GLB embeds the rendered textures; no loose texture files are
written. Re-running without `--force` exits `1` with `output-exists` and changes
nothing; `--force` overwrites.

## 4. Prove byte identity (FR-008/FR-009, SC-002)

```bash
# -- same recipe in two working directories with different locale/timezone
mkdir -p /tmp/run-a /tmp/run-b
(cd /tmp/run-a && TZ=UTC LC_ALL=C uv --project /path/to/beastforge run beastforge render ridge-stalker)
(cd /tmp/run-b && TZ=Pacific/Auckland LC_ALL=de_DE.UTF-8 uv --project /path/to/beastforge run beastforge render ridge-stalker)

# -- compare the assets and manifests
sha256sum /tmp/run-a/dist/ridge-stalker/* /tmp/run-b/dist/ridge-stalker/*
diff <(jq -S . /tmp/run-a/dist/ridge-stalker/ridge-stalker.manifest.json) \
     <(jq -S . /tmp/run-b/dist/ridge-stalker/ridge-stalker.manifest.json)
```

Expected: identical SHA-256 values for both files and an empty diff. The `slow`
determinism test extends this to 100 repetitions (SC-002).

Override behaviour (US1 scenario 4):

```bash
# -- a declared override changes seeded variation and is echoed
uv run beastforge render ridge-stalker --set body-length=3.1 --json \
  | jq '.effective_params["body-length"]'

# -- an unknown override is rejected with a suggestion and no output
uv run beastforge render ridge-stalker --set body-lenght=3.1 --json
# → exit 3, error.code = recipe-unknown-param, suggestion = body-length
```

## 5. Validate the gate (FR-034–FR-038, SC-004)

```bash
# -- whole shipped library must pass
uv run beastforge validate --json | jq '.valid, .summary'

# -- one recipe
uv run beastforge validate ridge-stalker
```

Expected: exit 0, `valid: true`, zero error findings, every creature reported
valid.

Defect injection (one class per fixture; each must fail with its own code):

```bash
# -- copy a recipe, then break exactly one invariant
cp library/quadruped/ridge-stalker.yaml /tmp/broken.yaml
# ... edit /tmp/broken.yaml: e.g. remove the 'attack' clip ...
uv run beastforge validate /tmp/broken.yaml --json | jq '.findings[].code'
# → exit 3, one finding with code "clip-missing-core"
```

Repeat for: duplicate bone name (`skeleton-duplicate-bone`), bone cycle
(`skeleton-cycle`), weight sum (`skin-weight-sum`), >4 influences
(`skin-too-many-influences`), zero-weight vertex (`skin-zero-weight`), bind pose
mismatch (`skin-bind-pose-mismatch`), event past duration
(`clip-event-out-of-range`), missing hit volume (`volume-missing-hit`), boss
without phases (`phase-missing-for-boss`), dangling socket
(`socket-target-missing`), missing texture recipe (`material-unresolved`),
oversized mesh (`budget-exceeded`), and an unrecognized surface mode
(`surface-unsupported-mode`).

The seeded corpus lives in `tests/defect_corpus/`; each case asserts exit `3`
and exactly the expected code.

## 6. Use the manifest as the gameplay contract (US2, SC-005)

```bash
# -- answer the three consumer questions from the manifest alone
jq -r '.clips[] | select(.name=="attack") | "\(.name) \(.duration)s"' \
  /tmp/beastforge-out/ash-crowned-tyrant.manifest.json
jq -r '.events[] | select(.clip=="attack") | "\(.name) at \(.time)s"' \
  /tmp/beastforge-out/ash-crowned-tyrant.manifest.json
jq -r '.sockets[] | select(.name=="maw") | "\(.target) + \(.offset)"' \
  /tmp/beastforge-out/ash-crowned-tyrant.manifest.json
```

Expected: the attack clip, its `impact` event time, and the muzzle socket are
readable without generator source. `jq '.schemaVersion'` prints a `MAJOR.MINOR`
string such as `"1.0"`.

Version behaviour (SC-010): a fixture consumer reads a `1.1` manifest with
unknown fields and every required field intact; a `2.0` manifest is rejected with
`manifest-schema-unsupported`.

## 7. Check a real consumer (SC-009)

```bash
# -- independent consumer 1: trimesh loads the GLB with skinning
uv run python - <<'PY'
import trimesh
scene = trimesh.load("/tmp/beastforge-out/ash-crowned-tyrant.glb")
print(type(scene).__name__, len(scene.geometry))
for name, geom in scene.geometry.items():
    print(name, len(geom.vertices), geom.visual.kind)
PY

# -- independent consumer 2: Khronos-style structural validation (Node optional)
npx --yes @gltf-transform/cli validate /tmp/beastforge-out/ash-crowned-tyrant.glb
```

Expected: zero import errors, skinned geometry present, at least one clip
defined in the GLB animations, and the validator reports no errors.

## 8. Showroom regression (FR-039–FR-041, SC-008)

```bash
# -- compare the current build against approved references
uv run beastforge showroom --json | jq '.status, .creatures[] | {name, status: .comparison.status}'

# -- explicitly accept a reference update after an intended change
uv run beastforge showroom --accept
```

Expected: unchanged creatures report `pass` with no differing frames; changing a
blend or sweep parameter flags only that creature, names its differing frames,
and exits `3`; `--accept` is the only way references change. `structural` in the
report is diffable independently of pixels.

## 9. Performance checks (SC-006)

```bash
# -- catalog and params under 2 s each
time uv run beastforge list >/dev/null
time uv run beastforge params ash-crowned-tyrant >/dev/null

# -- one full generation (geometry + clips + textures + gate + write) under 10 s
time uv run beastforge render ash-crowned-tyrant -o /tmp/perf-out --force
```

Expected: catalog/params < 2 s; render < 10 s on a developer laptop.

## 10. Expected outcomes summary

| Scenario | Command | Expected |
|----------|---------|----------|
| Catalog | `list --json` | exit 0, every creature, no generation |
| Params | `params NAME --json` | exit 0, declared knobs only |
| Generate | `render NAME` | exit 0, one `.glb` + one manifest, report hashes |
| Determinism | two runs, `sha256sum` | identical hashes |
| Unknown override | `render --set typo=...` | exit 3, suggestion, no output |
| Invalid recipe | `validate bad.yaml` | exit 3, distinct finding code |
| Shipped library | `validate` | exit 0, zero error findings |
| Manifest consumer | `jq` queries | attack clip, impact time, muzzle socket |
| Schema forward compat | fixture consumer | 1.x read, 2.x rejected |
| Standard import | `trimesh` + `gltf-transform` | zero errors, skinning intact |
| Showroom unchanged | `showroom` | pass, no differing frames |
| Showroom changed | `showroom` after edit | exit 3, only that creature flagged |
| Performance | `time` | <2 s catalog, <10 s render |

## Troubleshooting

- **`texforge-not-found`**: point `--texforge-library` or
  `BEASTFORGE_TEXFORGE_LIBRARY` at the texforge `library/` directory; a material
  reference never takes an absolute path.
- **`output-exists`**: re-run with `--force` or choose a new `-o` directory.
- **`ambiguous-name`**: two categories define the same creature name; pass the
  explicit recipe path.
- **`determinism-hazard`**: a recipe or build path introduced clock, environment,
  or unordered iteration; the finding names the offending location.
