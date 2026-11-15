---
title: "The library viewer is buildless, vendored three.js behind one catalog contract"
status: accepted
date: 2026-11-15
documentType: ADR
tags: [viewer, webgl, threejs, tooling, offline, determinism]
---

# ADR 261115-5: The library viewer is buildless, vendored three.js behind one catalog contract

## Context

The library (`library/**` recipes) is only discoverable through `beastforge list`
and stills. We want a browser-based library browser that shows every creature,
orbits it, plays its baked clips, and exposes the manifest facts that make the
format useful. The project is a single Python package with an offline,
deterministic, no-network runtime; adding a Node toolchain, a CDN dependency, or
a second build system would violate that posture.

There is also a temptation to give the viewer its own private data shape. That
would drift from the manifest, which ADR 261114-1 makes the authoritative
gameplay contract.

## Decision

- The frontend is **hand-written HTML/CSS/ES modules, no build step**. `three`
  and `GLTFLoader` (and its `BufferGeometryUtils` import) are **pinned and
  vendored as package data**, never loaded from a CDN at runtime.
- Both delivery modes serve the **same `catalog.json` v1 contract** with relative
  URLs. The frontend cannot tell which mode produced it.
- The viewer is **read-only**: it displays the manifest; it does not derive
  gameplay semantics, re-generate creatures, or apply `--set` overrides.
- The showroom stays a CPU software rasterizer; this viewer does not replace it
  or introduce a GPU dependency into the validation path.

## Consequences

- No Node/esbuild/Vite in the repo; `uv sync` is still the only install step.
- Upgrading three.js is a deliberate, reviewable file replacement plus a license
  and version note — not a lockfile bump.
- `catalog.json` is a new versioned surface: consumer-facing, canonical, and
  schema-tested. It may expose manifest data but must never contradict it.
- Any future richness (overlays, comparison) must fit the read-only boundary or
  justify a new decision.

## Alternatives Considered

- **Google `<model-viewer>`.** Rejected: weak access to clips, skeleton, and
  manifest inspection; awkward shadow-DOM styling.
- **three.js with a bundler (Vite/esbuild).** Rejected: second toolchain and
  build artifact in a Python-only repo, against the offline posture.
- **Raw WebGL2.** Rejected: reimplementing glTF + skinning + animation playback.
- **CDN-hosted three.js.** Rejected: breaks offline and pinning guarantees.

## Related

- ADR 261114-1 (glTF + sidecar manifest contract)
- ADR 261114-2 (offline deterministic generator)
- ADR 261115-6 (dual-mode delivery and Pages export)
