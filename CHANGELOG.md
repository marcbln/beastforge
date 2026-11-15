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
- Starter library: `boss/ash-crowned-tyrant`, `quadruped/ridge-stalker`, and
  `swarm/chitter-mite`.
- Layered test suite: unit, contract, integration, determinism, defect corpus,
  golden, and consumer imports.

### Changed
- Initial project README and changelog replaced with the feature documentation
  set (architecture, development, API, recipes, showroom, CLI cheat sheet,
  environment variables).

### Fixed
- None.

## [0.1.0] - 2026-11-14

### Added
- Initial project structure with README and CHANGELOG.
