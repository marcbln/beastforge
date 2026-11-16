# Quickstart: validate the closed part library

**Feature**: `003-closed-part-library` · **Date**: 2026-11-16
**Plan**: [plan.md](./plan.md) · **Contracts**: [contracts/](./contracts/)

This is a runnable validation guide, not an implementation guide. It proves the
closed-geometry contract, preset resolution, control publication, automatic motion,
determinism, and the viewer path end to end.

---

## 1. Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).
- The sibling `texforge` checkout for texture recipes. The repository defaults to
  `../texforge/library`; override with `BEASTFORGE_TEXFORGE_LIBRARY` or
  `--texforge-library`.
- No network access is required at runtime.

```bash
# Install the existing dependency groups (no new runtime dependency)
uv sync --all-groups
uv run beastforge --version
```

Expected: the version prints and exits 0.

---

## 2. Validate the whole library

```bash
uv run beastforge validate
```

Expected:

- exit 0;
- all five existing creatures plus `iron-warden` and `hover-skiff` are checked;
- every preset file is structurally valid;
- zero errors. Warnings are allowed and never change the exit code.

Machine-readable form:

```bash
uv run beastforge validate --json | jq '.valid, .summary'
```

Expected: `true` and an error count of `0`.

The closure gate is part of this command. An open, non-manifold, mis-wound, or
degenerate part fails here with one of `surface-open`, `surface-non-manifold`,
`surface-winding-invalid`, or `surface-degenerate`, and the finding names the
part. See [contracts/closure.md](./contracts/closure.md).

---

## 3. Discover presets

```bash
# All preset versions
uv run beastforge parts

# One family
uv run beastforge parts --family vehicle

# One preset, all versions
uv run beastforge parts organic-leg

# Pin a version and inspect parameters, controls, and auto behaviours
uv run beastforge parts organic-leg --version 1.0.0 --json | jq '.presets[0]'
```

Expected:

- 12 shipped presets across `organic`, `mechanical`, and `vehicle`;
- every preset has a path, a `sha256`, parameters, and zero or more controls;
- `vehicle-rotor` has an unbounded `spin` rotation control and a `rotate` auto
  behaviour;
- `mech-piston` has a translation `extend` control with units `m`;
- unknown names exit 4 and list available versions;
- the JSON validates against
  [contracts/parts.list.schema.json](./contracts/parts.list.schema.json).

---

## 4. Render the mechanical mech

```bash
rm -rf /tmp/beastforge-parts
uv run beastforge render iron-warden -o /tmp/beastforge-parts
```

Expected pair:

```text
/tmp/beastforge-parts/iron-warden.glb
/tmp/beastforge-parts/iron-warden.manifest.json
```

The asset is assembled only from `library/parts/mechanical/*` presets. It has no
organic torso or limb surfaces. Assert the published facts:

```bash
jq '{
  schemaVersion,
  clipSources: [.clips[] | {name, generator, source}],
  parts: [.parts[] | {name, preset, presetVersion, family}],
  controls: [.parts[].controls[] | {address, joint, mode, units, unbounded, range}]
}' /tmp/beastforge-parts/iron-warden.manifest.json
```

Expected:

- `schemaVersion` is `"1.1"`;
- every part has a `presetVersion` and `presetSha256`;
- controls include a bounded rotation, a bounded translation (`units: "m"`), and
  a turret yaw;
- `parts[].controls[].joint` names real joints from `skeleton.joints`;
- clips include the authored set and any auto baseline, each with `source`.

---

## 5. Render the limbless craft

```bash
uv run beastforge render hover-skiff -o /tmp/beastforge-parts --force
```

The craft uses only `library/parts/vehicle/*` presets (hull, wing, engine, rotor),
declares no authored clips, and relies on the rotor's automatic rotation.

```bash
jq '{
  schemaVersion,
  clips: [.clips[] | {name, generator, source, duration, loop}],
  parts: [.parts[] | {name, preset, family, controlCount: (.controls | length)}],
  rotor: [.parts[] | select(.preset == "vehicle-rotor") | .controls[]]
}' /tmp/beastforge-parts/hover-skiff.manifest.json
```

Expected:

- `clips` contains one synthesized entry with `name: "baseline"`,
  `generator: "baseline"`, `source: "automatic"`, and `loop: true`;
- the rotor publishes an unbounded `spin` rotation control with `units: "deg"`;
- no torso or limb part names appear.

---

## 6. Prove the closure contract

```bash
uv run pytest tests/unit/test_closure.py tests/contract/test_no_double_sided.py
```

Expected: pass. The unit tests cover:

- a closed box at large and tiny scale;
- an open box → `surface-open`;
- a non-manifold edge → `surface-non-manifold`;
- inward winding → `surface-winding-invalid`;
- a repeated-vertex/zero-area triangle → `surface-degenerate`.

The no-double-sided test parses emitted GLB materials and scans the authored
viewer JS for `DoubleSide`.

Prove every shipped part is closed:

```bash
uv run pytest tests/contract/test_gameplay_facts.py tests/integration/test_parts_render.py
```

Expected: the five creatures' gameplay facts match the pinned snapshot, and both
example assemblies validate, render, and appear in the viewer catalog.

---

## 7. Prove automatic motion and determinism

```bash
uv run pytest tests/unit/test_auto.py tests/determinism/test_parts_determinism.py
```

Expected:

- `breathe`, `bob`, `sway`, and `rotate` evaluate to the documented deltas;
- multiple behaviours compose in declaration order;
- an explicit clip wins on a joint it animates;
- two consecutive builds of `hover-skiff` and `iron-warden` produce byte-identical
  GLB and manifest files;
- the synthesized `baseline` clip is stable across builds.

Full determinism sweep (slow):

```bash
uv run pytest -m slow
```

Expected: the library golden hashes match and the 100-run/two-directory checks
pass.

---

## 8. Inspect the viewer

```bash
uv run beastforge view
```

Open the printed loopback URL and:

1. Select `iron-warden` or `hover-skiff`.
2. Orbit fully around the asset with normal backface culling. No part interior is
   visible; no polygon disappears to reveal the inside.
3. Open the **Controls** tab. It lists every control with address, joint, axis,
   mode, range/unbounded, default, and units.
4. Confirm the existing **Manifest**, **Clips**, and **Events** tabs still work.
5. For `hover-skiff`, the **Clips** tab shows the synthesized `baseline` clip and
   its automatic source.

The viewer is read-only: no slider drives a joint in this release.

---

## 9. Maintainer regeneration (after the implementation change)

The closed caps change asset bytes. Regenerate and approve the committed
references once:

```bash
# 1. Regenerate the five creatures' golden hashes using the documented snippet
#    in docs/development.md.

# 2. Regenerate the showroom reference frames and the gallery
uv run beastforge showroom --accept
```

Then re-run:

```bash
uv run pytest -m slow
uv run beastforge validate
uv run beastforge showroom
```

Expected: goldens match, the showroom comparison passes for all five creatures,
and the gallery links resolve.

---

## 10. What good looks like

| Check | Command | Pass condition |
|-------|---------|----------------|
| Library validity | `uv run beastforge validate` | exit 0, 0 errors |
| Preset discovery | `uv run beastforge parts` | 12 presets, 3 families |
| Mech assembly | `uv run beastforge render iron-warden …` | pair written, controls published |
| Craft assembly | `uv run beastforge render hover-skiff …` | pair written, `baseline` clip present |
| Closure | `uv run pytest tests/unit/test_closure.py` | all geometry cases pass |
| No culling workaround | `uv run pytest tests/contract/test_no_double_sided.py` | no `doubleSided`/`DoubleSide` |
| Gameplay facts | `uv run pytest tests/contract/test_gameplay_facts.py` | five snapshots match |
| Determinism | `uv run pytest tests/determinism/test_parts_determinism.py` | byte-identical builds |
| Viewer | `uv run beastforge view` | closed parts, Controls tab populated |
