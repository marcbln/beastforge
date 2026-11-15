---
title: "Viewer delivery is localhost-first with a deterministic static export as the publish path"
status: accepted
date: 2026-11-15
documentType: ADR
tags: [viewer, delivery, github-pages, ci, determinism]
---

# ADR 261115-6: Viewer delivery is localhost-first with a deterministic static export as the publish path

## Context

A browser viewer needs an origin. Options were a local server, a static export, or
a hosted frontend. The library is the working set: it changes locally, may grow,
and may include recipes that are not meant to be published. A public demo is still
wanted, and GitHub Pages is free for public repos, static-only, and serves over
same-origin HTTPS (so `fetch` of `.glb` works, unlike `file://`).

## Decision

- **Primary mode:** `beastforge view` runs a stdlib `http.server` on `127.0.0.1`
  (ephemeral port by default), generates missing GLBs lazily into a cache
  directory, and opens the browser. It always reflects `beastforge list`.
- **Publish mode:** `beastforge view --export DIR` writes a self-contained static
  bundle (`index.html`, `assets/`, `catalog.json`, `creatures/<name>/...`). The
  export is **byte-stable** for the same recipes, vendored assets, and tool
  version: canonical JSON, sorted paths, no timestamps or host information.
- **GitHub Pages** hosts the full library, generated in CI on pushes that touch
  `library/**` or the viewer, then published via Pages artifacts. **No generated
  `.glb` files are committed.**
- One frontend serves both modes; the delivery layer differs, the contract does
  not.

## Consequences

- Local and published views cannot drift structurally, only in recipe recency.
- CI owns the published truth; a recipe change republishes automatically and
  determinism makes that safe to trust.
- The cache directory is disposable, ignorable, and never a source of truth.
- Publishing is a build step, not a runtime capability — which is exactly what
  Pages requires.

## Alternatives Considered

- **Static export only.** Rejected: publishing private or in-progress recipes and
  requiring a manual export for every local change.
- **Hosted frontend / Node service.** Rejected: unnecessary server, violates the
  offline, Python-only posture.
- **Committing generated GLBs + a Pages branch.** Rejected: binaries in git,
  manual regeneration, and drift against the recipes.

## Related

- ADR 261115-5 (buildless vendored three.js viewer)
- ADR 261114-2 (offline deterministic generator)
