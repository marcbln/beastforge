---
filename: "_ai/backlog/active/261115_0338__DESIGN_HANDOFF__webgl-library-viewer.md"
title: "Design Handoff: WebGL library viewer (beastforge)"
createdAt: 2026-11-15 03:38
updatedAt: 2026-11-15 03:38
project: "beastforge"
status: validated
tags: [design, viewer, webgl, threejs, github-pages, catalog]
documentType: DESIGN_HANDOFF
adrs:
  - "_ai/technical_decisions/ADR__261115-5__buildless-webgl-library-viewer.md"
  - "_ai/technical_decisions/ADR__261115-6__dual-mode-viewer-delivery.md"
---

# Design Handoff: WebGL library viewer (beastforge)

## Context

beastforge's library is only discoverable through `beastforge list` and the
CPU-rendered showroom stills. We want a browser-based **library browser** that
shows every creature, orbits it, plays its baked clips, and surfaces the manifest
facts. Delivery must stay offline, Python-only, and deterministic, and a public
copy should be free to host.

## Decisions

- **Purpose:** library browser (not a QA preview, not a showroom GPU replacement,
  not a shippable per-asset bundle).
- **Stack:** hand-written HTML/CSS/ES modules, **no build step**; `three` +
  `GLTFLoader` (and `BufferGeometryUtils`) pinned and vendored as package data.
  No CDN at runtime, no Node toolchain.
- **Contract:** both delivery modes serve the same canonical `catalog.json` v1
  with relative URLs; the frontend cannot tell which mode produced it. The viewer
  is read-only and reads manifest facts directly rather than re-deriving them.
- **Delivery:** `beastforge view` (stdlib HTTP server on `127.0.0.1`, ephemeral
  port, lazy per-creature generation into a cache dir, opens browser) is the
  default; `beastforge view --export DIR` produces a byte-stable static bundle.
- **Publishing:** GitHub Pages hosts the **full library**, rebuilt in CI on pushes
  touching `library/**` or `viewer/**`. Generated `.glb` files are never
  committed.
- **Interaction:** category + search catalog, live WebGL thumbnails from one
  shared renderer, orbit stage auto-framed from manifest bounds, clip switcher
  with event tick marks, inspector tabs (Manifest / Clips / Events), deep links
  `#/<creature>/<clip>`.
- **Verification:** `catalog.json` schema/coverage contract test, export
  determinism test (two exports, identical hashes), and an opt-in Playwright
  smoke test (`-m viewer`) covering WebGL init, card count, mesh load, clip list,
  and deep links.

## Rejected Alternatives

- **Showroom GPU upgrade** — the showroom's CPU rasterizer exists specifically to
  avoid GPU/display/driver variance in CI; replacing it would undo that guarantee.
- **Shippable per-creature HTML bundle** — a different audience and lifecycle;
  the library browser does not need per-asset distribution yet.
- **Static export only** — would require manual export for every local change and
  would publish private/in-progress recipes.
- **Hosted frontend or Node service** — unnecessary server, violates offline and
  Python-only posture.
- **Committing generated GLBs to a Pages branch** — binaries in git, manual
  regeneration, drift against recipes.
- **Google `<model-viewer>`** — weak access to clips/skeleton/manifest, awkward
  shadow-DOM styling.
- **three.js with Vite/esbuild** — second toolchain and build artifact.
- **Raw WebGL2** — reimplements glTF, skinning, animation playback.
- **Live param editing / `--set` in the browser** — a static site cannot run the
  generator; out of scope for this design.
- **Full rig inspector** (skeleton/bone overlay, wireframe, A/B compare) — deferred
  as scope creep beyond "catalog + inspect".

## Constraints Discovered

- The runtime is offline and deterministic: no wall clock, locale, hostname, or
  unseeded randomness may reach outputs. `catalog.json` and `--export` must respect
  this (canonical JSON, sorted paths, no timestamps).
- The manifest (ADR 261114-1) is authoritative; `catalog.json` may surface it but
  must never contradict it and must tolerate schema growth.
- GLBs are produced only by the existing pipeline — the viewer must not
  re-implement geometry, export, or texture embedding.
- The library currently has 3 recipes (`boss`, `quadruped`, `swarm`); the design
  must still handle lazy loading and a shared thumbnail renderer for growth.
- Pages is static-only, free for public repos, HTTPS same-origin (so `fetch` of
  `.glb` works; `file://` does not), and imposes soft size/bandwidth limits that
  small embedded-texture GLBs are comfortably within.
- Repo has no existing web assets or Node project; Playwright would be a new dev
  dependency and should be opt-in so default `pytest` stays fast and offline.

## Open Questions

- **Thumbnail concurrency and cache policy** — exact cap and whether data URLs or
  blobs are kept; owner: implementer.
- **Pages workflow trigger detail** — push-to-main filters vs tag/release builds;
  owner: maintainer.
- **`catalog.json` schema governance** — version bump rules once fields are added;
  owner: maintainer (likely follows manifest precedent).
- **Vendored three.js upgrade policy** — cadence and where the version/license
  note lives; owner: maintainer.

## Scope Boundary

- **In:** catalog + inspect, local server, static export, Pages CI workflow, live
  thumbnails, deep links, contract/ determinism/Playwright tests.
- **Out:** param editing or `--set` in the browser, recipe mutation, live
  regeneration, replacing the showroom, skeleton/bone overlay, A/B compare, auth
  or private hosting, mobile-first layout, WebGPU.
