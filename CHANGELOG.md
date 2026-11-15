# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `beastforge` CLI with `list`, `params`, `render`, `validate`, `showroom`,
  `version`, and `about`, including global flags and stable `--json` surfaces.
- Deterministic procedural build core: skeleton-first recipes, swept limb tubes,
  torso shells, rigid parts, construction-bound 1–2 influence skin weights, and
  seeded silhouette modifiers.
- glTF 2.0 binary writer with embedded texforge textures, fixed emission order,
  and canonical JSON.
- Sidecar manifest with clips, events, sockets, volumes, phases, materials,
  bounds, scale, playback warning, and provenance; `MAJOR.MINOR` versioning with
  major-strict/minor-tolerant reads.
- 60 Hz baked clips for `breathe`, `gait`, `hover-bob`, `recoil`,
  `telegraph-attack`, and `death-collapse`; reserved core clips are required.
- Single validation gate with a closed finding vocabulary, ordered findings, and
  atomic staged output.
- Showroom with a numpy software rasterizer, fixed cameras/lighting, perceptual
  image comparison, structural summaries, and explicit `--accept`.
- Browsable [showroom gallery](docs/showroom-gallery.md) of the approved
  turntable and extreme-bend frames.
- Starter library: `boss/ash-crowned-tyrant`, `quadruped/ridge-stalker`,
  `quadruped/giraffe`, `quadruped/elephant`, and `swarm/chitter-mite`.
- `beastforge view`: buildless WebGL library viewer with a searchable,
  category-filtered gallery of live thumbnails, an orbit stage with manifest
  clip playback and event marks, and a manifest/clips/events inspector.
- Loopback-only local server with lazy content-addressed asset generation,
  cache reuse, stale-recipe `409` detection, and per-creature failure isolation.
- `beastforge view --export DIR`: deterministic static bundle (viewer,
  `catalog.json` v1.0, `bundle.json`, and creature packages) plus a GitHub Pages
  workflow that publishes without committing generated binaries.
- Vendored three.js 0.187.0 under `viewer/third_party/`; no Node, npm, CDN, or
  external runtime request.
- Opt-in Playwright browser smoke check (`-m viewer`,
  `BEASTFORGE_VIEWER_SMOKE=1`).
- Layered test suite: unit, contract, integration, determinism, defect corpus,
  golden, and consumer imports.

### Changed
- Initial project README and changelog replaced with the feature documentation
  set (architecture, development, API, recipes, showroom, CLI cheat sheet,
  environment variables).

### Fixed
- The published viewer rendered an empty gallery because `three.module.js`
  imported a `three.core.js` file that was never vendored; the full 0.187.0
  module split is now shipped.
- Removed the leftover inline import map, which strict CSP blocked and logged
  as an error on every load, and added a packaged favicon to avoid a 404.
- Allowed `blob:` in `connect-src` so `GLTFLoader` can fetch embedded textures
  from GLB files without CSP violations.

## [0.1.0] - 2026-11-14

### Added
- Initial project structure with README and CHANGELOG.
