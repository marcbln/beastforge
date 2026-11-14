---
title: "Offline, deterministic generator CLI with a texforge-shaped surface"
status: accepted
date: 2026-11-14
documentType: ADR
tags: [cli, determinism, agents, library, python]
---

# ADR 261114-2: Offline, deterministic generator CLI with a texforge-shaped surface

## Context

The user's framing: *"an analogue for texforge, but for 3D objects"*. texforge
is an offline CLI that renders byte-reproducible PNGs from declarative YAML
recipes, aimed primarily at AI coding agents: discover from an in-repo library,
render with parameter overrides, validate and self-correct through `--json`,
remix by cloning.

Creature generation is heavier than texture generation (geometry, rigs, skin
weights, animation curves), which makes *determinism* more valuable, not less:
agents and golden tests need to know that a recipe, not a solver run, produced
the output.

## Decision

- Python 3.12+ managed with `uv`; no network at runtime.
- CLI surface mirrors texforge's contract, adapted to 3D:
  `list`, `params`, `render`, `validate`, plus `showroom`. Parameters are
  overridden with `--set key=value`; recipes live in an in-repo
  `library/<category>/<name>.yaml` and carry a `meta:` block that is the catalog.
- **Every command has a stable `--json` surface.** `render --json` reports the
  output path, `sha256` of the `.glb` and manifest, clip/socket/event inventory,
  and warnings.
- **Determinism contract**: same recipe + params + tool version ⇒ byte-identical
  `.glb` and manifest, proven by `sha256`. Only a seeded PRNG may introduce
  variation; no wall-clock, no `random`, no environment-dependent ordering.
  Iteration order over dicts, bones, vertices, and joints is fixed and seeded.
- Recipes are trusted-as-data: `yaml.safe_load` only, no code execution,
  materials may reference texforge recipes by name but never import arbitrary
  Python.
- **Validation is a gate, not advice.** `validate` fails on skeleton/skin
  invariants (see ADR 261114-3), on manifest referential integrity (events and
  sockets point at existing clips/bones), and on non-determinism hazards. Exit
  code 0/1 and a machine-readable error list, same discipline as texforge.

## Consequences

- Geometry libraries are allowed only if their output ordering is stable; any
  library whose tessellation order depends on process state is wrapped and
  sorted before export.
- The `.glb` writer must be under our control for byte-identity (fixed buffer
  order, no timestamps, sorted JSON keys). This likely means emitting glTF
  directly rather than delegating to a general exporter.
- Adding a feature means adding its `--json` fields and its validation rule in
  the same change, or the feature is not done.
- The showroom (turntable frames vs golden images) becomes the visual
  regression gate, mirroring texforge's golden-PNG discipline.

## Alternatives Considered

- **Runtime generator in JS/WASM shipped with the game.** Rejected for v1:
  moves generation into the single-file `index.html` budget, kills
  byte-identity proofs, and forces the same code to run in engines that don't
  embed JS.
- **A curated library of prebuilt `.glb` files.** Rejected: no parameter
  remixing, no seeded variation, binary assets in the repo — the opposite of
  texforge's thesis.
- **Blender headless + Python scripting.** Rejected: heavyweight runtime
  dependency, poor determinism story, opaque failure modes for agents.
- **Non-deterministic authoring mode with a "final bake" step.** Rejected: two
  modes doubles the test surface and invites drift.

## Related

- ADR 261114-1 (glTF + manifest contract)
- ADR 261114-3 (construction-bound skinning)
- texforge ADR 261104-3 (determinism contract) — same principle, 3D output
