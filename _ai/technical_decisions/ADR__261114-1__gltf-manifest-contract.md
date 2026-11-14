---
title: "glTF 2.0 plus a sidecar manifest is the engine contract"
status: accepted
date: 2026-11-14
documentType: ADR
tags: [format, gltf, manifest, integration, portability]
---

# ADR 261114-1: glTF 2.0 plus a sidecar manifest is the engine contract

## Context

The library must let a game engine drive a procedural creature — meshes,
articulation, animation, and the gameplay hooks around it — and must outlive the
first engine. The first consumer is a Three.js vertical slice (`r-type`), with
Bevy/Rust a plausible follow-up.

Every candidate engine already ships an animation player and a glTF importer
(Three.js `GLTFLoader` + `AnimationMixer`, Bevy `AnimationPlayer`, Godot).
Inventing a creature format plus one adapter per engine means two APIs to
version, and the adapter inevitably re-implements clip playback.

What an engine cannot infer is *our* semantics: which clip is the attack, when
the attack lands, where the muzzle is, which volume is the weak point.

## Decision

- The generated asset is a **`.glb` (glTF 2.0 binary)** plus a **sidecar
  `*.manifest.json`**. No bespoke scene/creature format.
- The manifest is the gameplay contract and carries, per creature:
  - `clips[]`: name, duration, loop flag, source generator;
  - `events[]`: `{clip, time, name}` — impact, fire, footstep, death;
  - `sockets[]`: `{name, bone|node, offset}` — muzzle, eye, core, hand;
  - `volumes[]`: hit / weak-point / collision proxies;
  - `phases[]`: named thresholds for boss phase logic;
  - bounds, suggested scale, and provenance (recipe hash, tool version,
    manifest schema version).
- **The library defines no runtime animation API.** An optional per-engine
  loader may later read `glb` + `manifest` and expose `play(clip)`,
  `socket(name)`, and event callbacks. It must not simulate, seek, or blend
  itself.
- Semantic names in the manifest are a public contract. Renaming a clip, socket,
  or event is a breaking change and requires a manifest schema version bump.
- glTF has no event channel, so clip events are manifest-only and authoritative;
  baked keyframes are not inspected for timing.

## Consequences

- Engines without glTF import are out of scope; supporting them is a separate
  decision, not a format change.
- Manifest and `.glb` are versioned together by `manifest.schemaVersion`; the
  `.glb` itself stays plain glTF so generic tooling and viewers keep working.
- Consumers must tolerate unknown manifest fields (forward compatibility) and
  must not infer gameplay meaning from node names alone.
- A consumer that ignores the manifest still gets a working animated creature —
  degraded, not broken. This is the portability guarantee.

## Alternatives Considered

- **TypeScript `Monster` class / npm package.** Rejected: engine-locked,
  duplicates clip playback, and forces Bevy to reimplement it.
- **Rust crate / Bevy plugin.** Rejected: same lock-in in the other direction;
  premature before a Rust game exists.
- **Bespoke JSON creature format + per-engine adapters.** Rejected: two APIs to
  maintain and version; buys nothing glTF + manifest does not already provide.
- **Runtime procedural animation (clips evaluated in-engine).** Rejected for
  v1 — see ADR 261114-4.

## Related

- ADR 261114-2 (offline deterministic generator)
- ADR 261114-4 (baked clips and event frames)
- Design handoff: `_ai/backlog/active/261114_1931__DESIGN_HANDOFF__beastforge-procedural-3d-creatures.md`
