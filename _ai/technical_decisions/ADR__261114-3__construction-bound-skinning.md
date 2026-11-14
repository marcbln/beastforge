---
title: "Skinned meshes with weights bound at construction; metaball deferred"
status: accepted
date: 2026-11-14
documentType: ADR
tags: [mesh, skinning, rig, geometry, determinism]
---

# ADR 261114-3: Skinned meshes with weights bound at construction; metaball deferred

## Context

Creatures are skinned bodies (skeleton + weighted vertices), not rigid part
hierarchies — chosen so organic endbosses deform smoothly. The hard part of
procedural skinning is not the skeleton or the keyframes; it is producing **skin
weights** that are correct, stable, and debuggable.

The standard approach — generate a mesh, then solve for weights (bone heat,
voxel distance fields) — is iterative, sensitive to tessellation order and
floating-point paths, and fails silently with shoulder/hip shearing. That
directly undermines the determinism contract (ADR 261114-2) and the
agent-self-correction loop: the failure cannot be traced to a recipe line.

## Decision

- **Generate the mesh from the rig, so weights fall out of construction.**
  Limbs are swept tubes emitted along bone chains; the torso is a shell of rings
  bound to spine bones; shells/spikes/plates are rigid parts.
- Every vertex records its source bone at birth. Across a joint, weights blend
  by parametric position:

  ```
  t = clamp((s - (L - band/2)) / band, 0, 1)
  w_next = smoothstep(0, 1, t);  w_bone = 1 - w_next
  band = min(band_fraction * L, 0.35 * L)
  ```

  where `s` is distance along the bone and `L` its length. This yields **1–2
  influences per vertex**, comfortably inside glTF/Three.js's 4-influence limit,
  with weights normalized by construction.
- Rigid parts (carapace plates, spikes, weapons) get weight `1.0` on one bone.
- **UVs are emitted by the sweep** (U along the limb, V around), so a texforge
  material tiles naturally. This is also why tubular bodies are preferred.
- Bind pose equals rest pose; the exported inverse bind matrices are computed
  from the rest skeleton, never from a posed frame.
- Silhouette variety comes from **sweep-time deformation** — taper, twist,
  radial noise, squash, per-part scale — not from a surface solver.
- The recipe carries `mesh.surface: sweep` in v1. **`metaball` is reserved** as a
  v1.5 value: an SDF surface that inherits weights from the nearest source limb
  segment. The manifest and `.glb` contract do not change when it lands.
- `validate` must fail on: weights not summing to 1 (±1e-5), >4 influences, any
  zero-weight vertex, degenerate/inverted joint matrices, bone cycles, or a bind
  pose differing from rest pose.

## Consequences

- Silhouettes are constrained to swept/organic-tubular forms (worms, quadrupeds,
  insectoid mechs, tentacled floating bosses). Free-form lumpy bodies wait for
  the metaball mode.
- Recipes are authored around bone chains first, surfaces second. The recipe
  grammar must make skeleton definition the entry point, not an afterthought.
- Joint bands become a tuning surface (`blend`), and the showroom must exercise
  extreme bends to expose shearing.
- A future metaball mode must satisfy the same validation gates and inherit
  weights deterministically, or it does not ship.

## Alternatives Considered

- **Rigid articulated hierarchy (TRS nodes, no skin).** Simpler and sufficient
  for mechs/insects, but rejected by the user: smooth organic deformation is
  wanted, and adding skinning later would break the recipe grammar.
- **Auto-skinning a generated mesh (bone heat / voxel distance).** Rejected:
  non-deterministic, slow, opaque failure modes, and exactly the class of bug
  agents cannot self-correct from.
- **Authored glTF body with procedural variation on top.** Rejected for v1: it
  reintroduces binary assets and a Blender dependency; nothing prevents adding
  it later as a recipe reference, but it is not the default path.
- **Metaball surface with distance weights now.** Rejected as v1 scope: adds a
  voxel grid, marching-cubes ordering, and weight smoothing — a second
  determinism story for silhouettes not yet required.

## Related

- ADR 261114-2 (determinism contract)
- ADR 261114-4 (baked clips)
