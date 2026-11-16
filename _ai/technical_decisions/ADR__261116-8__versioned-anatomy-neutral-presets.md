---
title: "Parts are immutable, versioned, anatomy-neutral presets bound by @slots"
status: accepted
date: 2026-11-16
documentType: ADR
tags: [presets, library, versioning, anatomy-neutral, determinism]
---

# ADR 261116-8: Versioned, anatomy-neutral part presets

## Context

The surface builders are generic, but the vocabulary and recipe layout assume a
creature with a torso and limbs. Reuse across organic, mechanical, and vehicle
assets needs a stable unit that can evolve without silently changing assemblies
that already ship. A floating version range or an in-place edit would break
deterministic regeneration.

## Decision

- One immutable preset version per file at
  `library/parts/<name>/<MAJOR.MINOR.PATCH>.yaml`. The directory name, filename
  stem, `name`, and `version` must agree.
- A preset surface uses `@slot` bone roles instead of concrete joints. An
  instance pins an exact version and supplies a complete `bind` map; extras,
  missing slots, and two slots on one bone are errors.
- Surface kinds gain the neutral names `swept-solid` and `shell`; the old
  `limb-tube`/`torso-shell` names remain accepted aliases. No validation rule
  requires a torso, limb, chain, or family structure.
- Overrides use a closed canonical vocabulary. Omitted keys keep the preset value
  and nested objects are never replaced wholesale.
- A sorted filesystem scan (`parts/registry.py`) is the only IO; resolution
  (`parts/resolve.py`) and override application are pure.
- The canonical build digest includes the pinned preset documents. Preset
  versions are immutable; a change adds a new version file.

## Consequences

- Old assemblies keep resolving their pinned version while presets evolve.
- A preset edit is a review-visible addition of a file, not a silent mutation.
- `beastforge parts` provides read-only discovery with stable JSON.
- Recipes may migrate one surface at a time; `surfaces[]` and `parts[]` coexist.
- The library is anatomy-neutral at the model and validation layers, even though
  shipped presets happen to be named after organic/mechanical/vehicle parts.

## Alternatives Considered

- **One file per preset with a `versions:` list.** Rejected: noisy diffs and a
  single mutable source for old pins.
- **Floating version ranges.** Rejected: non-deterministic.
- **Preset uses concrete joints.** Rejected: not reusable across skeletons.
- **Nested override objects or free-form field paths.** Rejected: a second patch
  language with weaker validation.

## Related

- ADR 261114-2 (offline deterministic generator)
- ADR 261116-7 (closed-solid part contract)
- ADR 261116-9 (control contracts and baked automatic motion)
- `specs/003-closed-part-library/contracts/parts-grammar.md`
