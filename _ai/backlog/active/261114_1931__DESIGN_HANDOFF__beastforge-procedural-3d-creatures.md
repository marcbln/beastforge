---
filename: "_ai/backlog/active/261114_1931__DESIGN_HANDOFF__beastforge-procedural-3d-creatures.md"
title: "Design Handoff: procedural 3D creatures (beastforge)"
createdAt: 2026-11-14 19:31
updatedAt: 2026-11-14 19:31
project: "beastforge"
status: validated
tags: [design, 3d, skinning, gltf, procedural, texforge-family, agents]
documentType: DESIGN_HANDOFF
workingName: beastforge
adrs:
  - "_ai/technical_decisions/ADR__261114-1__gltf-manifest-contract.md"
  - "_ai/technical_decisions/ADR__261114-2__offline-deterministic-generator.md"
  - "_ai/technical_decisions/ADR__261114-3__construction-bound-skinning.md"
  - "_ai/technical_decisions/ADR__261114-4__baked-joint-clips-and-event-frames.md"
---

# Design Handoff: procedural 3D creatures (beastforge)

## Context

Starting point: "a library I can reuse with monsters or general objects for 3D
games … with animation … maybe some meshes + classes (js/ts or also rust) that
present the monster (e.g. an endboss) … animated and controlled by the game
engine". The user refined this to: **an analogue of `texforge`, but for 3D
objects** — i.e. an offline, deterministic, declarative generator rather than a
runtime library.

Existing workspace context:

- `texforge` — offline deterministic YAML→PNG texture generator, agent-first CLI,
  in-repo recipe library, `sha256`-proven byte identity. The template being
  copied.
- `r-type` — single-file Three.js vertical slice (`index.html`, no build step),
  deterministic 60 Hz tick simulation decoupled from the 3D presentation layer,
  procedural textures generated at boot. The first consumer.

The conceptual shift that resolved the design: a "monster library" is **an asset
generator plus a gameplay manifest**, not a runtime animation engine. Engines
already play glTF clips; what they lack is our semantic contract (which clip is
the attack, when it lands, where the muzzle is).

## Decisions

1. **Output = `.glb` + `*.manifest.json`; no bespoke creature format and no
   runtime monster library in v1.** The manifest carries clips, event frames,
   sockets, hit volumes, phase thresholds, bounds, and provenance. Semantic names
   are a public contract. → ADR 261114-1
2. **Offline deterministic CLI, texforge-shaped.** Python 3.12+/`uv`;
   `list`/`params`/`render`/`validate`/`showroom`; stable `--json` surfaces;
   in-repo `library/`; recipes are `yaml.safe_load` data; seeded PRNG only;
   byte-identical `.glb` and manifest with `sha256`; validation is a gate with
   exit code 0/1. → ADR 261114-2
3. **Skinned meshes, weights assigned at vertex birth from the rig.** Limbs are
   swept tubes emitted along bone chains; torso is a ring shell on spine bones;
   rigid parts get weight 1.0. Joint blending is a clamped smoothstep, 1–2
   influences per vertex (well under the 4-influence glTF limit). UVs come from
   the sweep so texforge materials tile. `surface: sweep` now; `metaball`
   reserved for v1.5 with inherited weights. → ADR 261114-3
4. **Clips are synthesized at generation time and baked to joint TRS.** Generators
   (`breathe`, `gait`, `hover-bob`, `recoil`, `telegraph-attack`,
   `death-collapse`) are recipe-level; timings in seconds with a `ticks@60`
   convenience; event frames live in the manifest and are authoritative. No
   runtime procedural locomotion in v1. → ADR 261114-4
5. **texforge composition, not duplication.** Materials reference texforge recipes
   by name; beastforge does not grow its own texture engine. One pipeline
   yields skin and body.

## Rejected Alternatives

- **Runtime `Monster` class in TS/Three.js (or a Rust/Bevy crate).** Rejected:
  locks into one engine, duplicates clip playback the engine already provides,
  and forces reimplementation per target.
- **Bespoke creature format + per-engine adapters.** Rejected: two APIs to
  version and maintain; glTF 2.0 plus a manifest already covers geometry,
  skinning, and clips.
- **Engine-agnostic format *and* a required runtime adapter in v1.** Rejected:
  the adapter earns its place only after a real consumer exists; a ~100-line
  loader per engine is a later, optional deliverable.
- **Auto-skinning (bone heat / voxel distance weights).** Rejected: iterative,
  tessellation-order sensitive, fragile determinism, and its artifacts (sheared
  joints) are untraceable to a recipe line — fatal for agent self-correction.
- **Rigid articulated hierarchy (no skin).** Rejected by the user: smooth organic
  deformation is wanted; retrofitting skin later would break the recipe grammar.
- **Metaball/SDF bodies with distance-based weights in v1.** Deferred: voxel
  grid, marching-cubes ordering, weight smoothing, a second determinism story —
  for silhouettes not yet required.
- **Runtime parametric clip evaluation / IK.** Deferred: forces a per-engine
  animation layer; no gameplay requirement yet.
- **Prebuilt `.glb` asset library.** Rejected: no remixing, no seeded variation,
  binary assets in the repo.
- **Blender headless pipeline.** Rejected: heavy dependency, weak determinism,
  opaque failures for agents.
- **Runtime generator embedded in the single-file game.** Rejected: blows the
  single-file/no-build budget and destroys the byte-identity proofs.

## Constraints Discovered

- **r-type ships as one self-contained `index.html` with no build step** and loads
  Three.js from a CDN import map. A generated `.glb` therefore has to be inlined
  (base64/data URI) or re-derived at boot for that consumer. This is a packaging
  problem, not a format problem — but it must be designed for, and it argues
  against a runtime asset fetch.
- **glTF/Three.js skinning limit** is 4 influences per vertex; weights normalize
  to 1.0. The construction-bound rule (ADR-3) satisfies this by design.
- **glTF has no event channel** — gameplay timing must live in the manifest.
- **Byte identity is fragile** once third-party mesh/glTF libraries are involved;
  the exporter ordering must be ours.
- **The reference game is tick-based (60 Hz)** while animation is authored in
  seconds; conversion needs to be explicit and tested.
- **Endboss legibility is a design input**, not a polish step: windup/impact/
  recovery timings are part of the recipe and the manifest contract.

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Confirm the working name `beastforge` (vs `meshforge`, `formforge`, `critterforge`) before the repo is created. | Marc |
| 2 | Python geometry stack: custom `numpy`-only mesh/sweep code, or build on `trimesh`/`pygltflib` with a sorting wrapper? Byte-identity favours custom; velocity favours libraries. | Marc (spike) |
| 3 | Texture/material binding: does the manifest embed texforge texture recipe names + params, or a pre-rendered texture set hash? | Marc |
| 4 | Unit and orientation convention: metres with Y-up/−Z-forward (glTF default) and a `scale` hint in the manifest? | Marc |
| 5 | Hit volumes: emitted by the generator, or left to the engine to derive from bones/bounds? | Marc |
| 6 | Showroom/golden strategy: turntable PNG goldens, glTF structural diffs, or both? | Agent proposal, Marc approves |
| 7 | First consumer packaging: inline base64 `.glb` into `r-type/index.html`, or generate a compact runtime-built variant for the single-file budget? | Marc |
| 8 | Is texforge consumed as a library import or only referenced by recipe name (subprocess at generation time)? | Marc |

## Scope Boundary

**In scope (v1)**

- `library/` of creature recipes (at minimum one boss, one quadruped, one swarm
  unit) + recipe schema with skeleton-first grammar.
- Skinned mesh generation with construction-bound weights and sweep UVs.
- Clip generators baked to joint TRS, with manifest event frames.
- `.glb` + manifest export with `sha256` byte identity.
- `list` / `params` / `render` / `validate` / `showroom`, all with `--json`.
- Skin/manifest validation gates and golden visual/structural tests.
- Material references to texforge recipes by name.

**Explicitly out of scope (v1)**

- Any runtime animation/monster library for any engine.
- Metaball/SDF surfaces, auto-skinning, cloth/soft-body.
- Runtime procedural locomotion, IK, foot planting, physics ragdolls.
- A Blender or authored-glTF asset path.
- Level/world generation, AI behaviour trees, combat simulation — gameplay logic
  stays with the engine.
- Engine adapters beyond a documented manifest reader example.

## Recommended Next Artifact

This is a new capability with some open behavioural questions still on the table,
so the next step is a **spec** (`create-spec`), not an implementation plan. The
spec should pin down the recipe schema, manifest schema (versioned), validation
rules, and the exact `--json` surfaces; questions 2 and 7 can be closed with a
small spike during planning.
