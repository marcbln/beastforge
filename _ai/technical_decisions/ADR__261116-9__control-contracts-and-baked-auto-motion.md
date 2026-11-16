---
title: "Controls are published contracts; automatic motion is baked, never a runtime API"
status: accepted
date: 2026-11-16
documentType: ADR
tags: [controls, animation, manifest, determinism, baking]
---

# ADR 261116-9: Control contracts and baked automatic motion

## Context

A downstream consumer needs to know which joints a part exposes, how to drive
them, and in what units without parsing the authoring recipe. Ambient motion
(breathing, bobbing, swaying, spinning) should also work for assets with no
hand-authored clips. Both must remain deterministic and offline; the viewer is
read-only in this release.

## Decision

- A control declares a name, joint, unit-vector axis, mode (`rotation` or
  `translation`), bounded range or `unbounded`, default, and explicit units
  (`deg`/`m`). Units must match the mode; axes are rejected rather than silently
  normalized.
- Resolved controls publish a unique `<part>/<control>` address in manifest 1.1
  under `parts[].controls[]`. Preset and instance declarations merge by name
  (the instance wins).
- Four automatic behaviours form a discriminated union: `breathe` (scale),
  `bob` (translation), `sway` (rotation), and `rotate` (constant rotation).
- For every authored clip, generator functions are built first; automatic
  behaviours are added only for joints the generator did not animate. Explicit
  clip motion always wins on a joint.
- Multiple behaviours on one joint compose in declaration order: translations
  sum, rotations multiply as quaternions, scales multiply component-wise.
- If a recipe has automatic behaviours and no authored clips, one `baseline`
  clip is synthesized with `generator: "baseline"`, `source: "automatic"`, and a
  deterministic duration of `max(2 s, longest period)` capped by
  `budgets.max_clip_ticks`.
- Manifest changes are additive within major 1: optional `parts`,
  `parts[].controls`, `clips[].source`, and the `baseline` generator name.

## Consequences

- Consumers can discover controls from published metadata alone.
- Ambient motion works for a static craft with no authored clip, and the GLB and
  manifest remain byte-identical across runs.
- The viewer shows a read-only Controls tab and never drives joints.
- Automatic descriptors are authoring-side and are not published; the
  synthesized clip is the discoverable evidence.

## Alternatives Considered

- **Runtime control API in the viewer.** Rejected for this release: read-only.
- **Blend automatic and explicit motion on the same joint.** Rejected: hides
  author intent and complicates determinism.
- **Require an authored clip for every auto asset.** Rejected: contradicts the
  limbless-craft scenario.
- **Publish auto descriptors.** Rejected: the manifest remains a gameplay
  contract, not a composition language.

## Related

- ADR 261114-1 (glTF + sidecar manifest contract)
- ADR 261114-4 (baked clips and event frames)
- ADR 261116-8 (versioned part presets)
- `specs/003-closed-part-library/contracts/controls.md`
