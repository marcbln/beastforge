---
title: "Every generated part is a closed solid; culling is proof, not a toggle"
status: accepted
date: 2026-11-16
documentType: ADR
tags: [geometry, closure, validation, viewer, determinism]
---

# ADR 261116-7: Closed-solid part contract

## Context

Limb tubes and torso shells were emitted open-ended. With backface culling on,
an orbit revealed the hollow interior of shipped assets. The acceptable fixes
were to hide the opening with two-sided rendering, to union parts into one
manifold, or to construct closed parts. Two-sided rendering hides the defect and
removes the visual proof; boolean union is out of scope and would destroy
construction-bound skin weights.

## Decision

- Every swept part (`swept-solid`/`shell`, with `limb-tube`/`torso-shell` as
  aliases) calls `sweep_surface(..., caps=True)`; `rigid-part` was already capped.
- A part passes closure when every undirected edge has exactly two incident
  triangles, the two traverse it in opposite directions, the signed volume is
  positive, and no triangle is degenerate under a scale-relative epsilon.
- The check is per `SurfaceRange`, never on the merged mesh. Parts may overlap at
  a joint; the assembly need not be one manifold.
- Self-intersection and duplicate-face detection are explicitly out of scope.
- There is no open-surface, two-sided, or culling-disable escape hatch. The GLB
  writer never emits `doubleSided`; the viewer never selects `DoubleSide`.
- Findings are `surface-open`, `surface-non-manifold`, `surface-winding-invalid`,
  and `surface-degenerate`.

## Consequences

- Every shipped asset changed bytes when caps were enabled; goldens, showroom
  references, and gameplay-facts snapshots were regenerated and reviewed.
- Hole-like forms (mouth cavity, exhaust bell) must be modelled as closed solids
  with an inner wall and rim.
- Closure is O(triangles) per part and adds `2 * segments` triangles per swept
  part, well inside the render budget.
- Backface culling remains enabled everywhere and becomes the visual proof that
  geometry is complete.

## Alternatives Considered

- **Two-sided materials.** Rejected: hides the defect and violates the product
  constraint.
- **Boolean union / CSG.** Rejected: out of scope and destructive to weights.
- **Whole-assembly manifold check.** Rejected: parts legitimately overlap.
- **`trimesh` watertightness in the runtime gate.** Rejected: dev-only dependency
  and still does not express winding or per-part paths.

## Related

- ADR 261114-2 (offline deterministic generator)
- ADR 261114-3 (construction-bound skinning)
- `specs/003-closed-part-library/contracts/closure.md`
