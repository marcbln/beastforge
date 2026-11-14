---
title: "Animation baked to joint TRS at generation; manifest carries timing events"
status: accepted
date: 2026-11-14
documentType: ADR
tags: [animation, clips, gltf, gameplay, timing]
---

# ADR 261114-4: Animation baked to joint TRS at generation; manifest carries timing events

## Context

Creatures must be animated by the engine, but the clips themselves can either be
(a) synthesized at generation time and baked into the `.glb`, or (b) exported as
parametric specs the engine evaluates every frame. Option (b) enables responsive
locomotion but requires a runtime animation layer in every engine — the thing
ADR 261114-1 rules out.

Telegraphs must be readable: an endboss attack's windup, impact, and recovery
have to line up with simulation timing (the reference game runs a deterministic
60 Hz tick, e.g. a 50-tick beam telegraph).

## Decision

- Clip generators (`breathe`, `gait`, `hover-bob`, `recoil`,
  `telegraph-attack`, `death-collapse`, …) synthesize joint TRS curves **at
  generation time** and bake them into glTF animations targeting joint nodes.
- Each clip declares `loop: bool`, `duration`, and **event frames** in the
  manifest: `{clip, time, name}`. Events are authoritative; keyframes are not
  inspected for timing.
- Clip timing is authored in **seconds**; a `ticks@60` field is accepted as a
  convenience for tick-based sims and converted exactly (`t = ticks / 60`).
- There is **no runtime procedural locomotion in v1**. Variable locomotion speed
  is achieved by the engine's playback rate; consumers are warned in the
  manifest that rate changes scale event times proportionally.
- Clip generator parameters are part of the recipe and therefore part of the
  determinism hash. Changing a generator's math is a breaking change for every
  recipe that uses it and requires a `meta.tested-with` bump.

## Consequences

- Same-speed variation is free; opposite-direction or strafing locomotion
  needs distinct clips. Recipes should budget for that.
- Telegraph → impact synchronization must be read from manifest events, never
  assumed from clip duration.
- Adding runtime clip evaluation later is an additive manifest feature
  (`clips[].runtime: true`), not a format break — but it reintroduces the
  per-engine adapter cost and is therefore out of scope by default.
- Golden tests must cover event timings, not only vertex/weight output.

## Alternatives Considered

- **Export parametric clip specs; engines evaluate per frame.** Rejected for v1:
  forces a runtime animation layer in every engine and duplicates what
  `AnimationMixer`/`AnimationPlayer` already do.
- **Runtime IK/foot planting.** Rejected: requires skeletal collision queries
  and per-engine tuning; no gameplay requirement yet.
- **Per-engine animation code.** Rejected: the explicit lock-in ADR 261114-1
  exists to prevent.
- **Author clips as raw keyframe tables only.** Kept as a low-level escape
  hatch, but generators are the primary authoring path: raw tables are
  unauthorable at bestiary scale and hide telegraph intent.

## Related

- ADR 261114-1 (manifest contract)
- ADR 261114-3 (rig and bind pose)
