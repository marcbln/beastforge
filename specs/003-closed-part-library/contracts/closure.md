# Contract: closed part geometry

**Feature**: `003-closed-part-library` · **Enforces**: FR-001, FR-002, FR-003,
FR-022
**Sources**: [spec.md](../spec.md) clarifications, [research.md](../research.md)
D1–D2, [data-model.md](../data-model.md) §5

Every generated part is a **closed solid**. A part passes when its triangle set is
watertight and manifold, its winding is consistently outward, and it has no
degenerate faces. Overlap between parts is allowed. Backface culling stays on.

Self-intersection and duplicate-face detection are explicitly **not** part of this
contract.

---

## 1. Definitions

Given one part's local triangle list (`indices` re-based to the part's vertex
range), with each triangle contributing three directed edges `(a,b)`, `(b,c)`,
`(c,a)`:

| Term | Definition |
|------|------------|
| **boundary edge** | an undirected edge `{u,v}` with exactly one incident triangle |
| **non-manifold edge** | an undirected edge with three or more incident triangles |
| **inconsistent edge** | an undirected edge with exactly two incident triangles that traverse it in the same direction (both `u→v` or both `v→u`) |
| **degenerate face** | a triangle with a repeated vertex index, zero-length edge, or geometric area at or below `epsilon` |
| **signed volume** | `sum(dot(p0, cross(p1, p2)) / 6)` over all triangles |
| **closed** | zero boundary edges, zero non-manifold edges, zero inconsistent edges, zero degenerate faces, and signed volume `> 0` |

A positive signed volume means the winding is outward. Because the sum is
translation-invariant for a closed surface, no particular origin is required.

### 1.1 Scale-relative epsilon

```
diagonal = length of the part's local AABB diagonal
epsilon  = max(1e-12, diagonal² * 1e-10)
```

The relative term rejects caps that collapse because of extreme taper, radial
noise, or scale, without rejecting a legitimately tiny part. Exact repeated
indices and zero-length edges are always degenerate regardless of epsilon.

---

## 2. Generation rules

- `swept-solid` and `shell` parts call `sweep_surface(..., caps=True)`.
  `limb-tube` and `torso-shell` are aliases for the same closed construction.
- `rigid-part` uses the existing capped `rigid_surface`.
- A cap is a triangle fan from the path endpoint to the first/last ring. The ring
  is planar and star-shaped about its centre, so the fan closes the end without a
  new algorithm.
- Caps join the part's existing vertex/index range. Skin joints and weights are
  copied from the corresponding ring, preserving the construction-bound skinning
  contract.
- Parts may overlap at joints. No boolean union, CSG, stitching, or whole-asset
  manifold check is performed.
- An intentional opening (mouth cavity, exhaust bell, wound) must be modelled as a
  closed solid with an inner wall and rim. There is **no** general open-surface
  escape hatch in this release.
- No material sets `doubleSided`. The viewer never selects `THREE.DoubleSide`.
  Culling is the proof that geometry is complete, not something to disable.

---

## 3. Gate algorithm

`validation/closure.py` runs once after mesh construction and before materials,
budgets, and commit.

```text
for each SurfaceRange in mesh.surfaces (recipe order):
    local_indices = mesh.indices[range] - range.vertex_offset
    edge_undirected_count = Counter()
    edge_direction = {}
    degenerate = 0

    for triangle in local_indices:
        if repeated index: degenerate += 1
        area = 0.5 * |cross(p1-p0, p2-p0)|
        if area <= epsilon: degenerate += 1
        for each directed edge (u, v):
            edge_undirected_count[sorted(u, v)] += 1
            record direction (u -> v)

    boundary = count(edge count == 1)
    non_manifold = count(edge count > 2)
    inconsistent = count(
        edge has two triangles and both traverse the same direction
    )
    signed_volume = sum(dot(p0, cross(p1, p2)) / 6)

    if boundary > 0: finding surface-open
    if non_manifold > 0: finding surface-non-manifold
    if inconsistent > 0 or signed_volume <= 0: finding surface-winding-invalid
    if degenerate > 0: finding surface-degenerate
```

The check is per `SurfaceRange`, never on the merged mesh: two adjacent parts may
share space, and the seam between them is not an edge.

### 3.1 Findings

| Code | Meaning | `expected` / `actual` |
|------|---------|-----------------------|
| `surface-open` | one or more boundary edges | expected "every edge shared by exactly two faces"; actual boundary count and the first edge |
| `surface-non-manifold` | an edge shared by 3+ faces | expected exactly two; actual count and the first edge |
| `surface-winding-invalid` | inconsistent edge directions or non-positive signed volume | expected "consistent outward winding"; actual signed volume / inconsistent count |
| `surface-degenerate` | repeated indices or near-zero area | expected "positive-area triangles"; actual count and the first face |

Each finding carries the part path (`surfaces[<name>]` or `parts[<name>]`), a
remedy (raise rings/segments, remove extreme taper/noise/scale, fix winding), and
a stable code from the closed finding vocabulary.

### 3.2 What is not checked

- Self-intersection between triangles of the same part.
- Duplicate faces.
- Whether the assembled asset is one manifold.
- Whether a cap is visible or hidden inside an adjacent part.
- Whether a part has a particular anatomy (torso, limb, head, hull, etc.).

These are deliberate scope limits, not oversights.

---

## 4. Test obligations

- A hand-built open box fails with `surface-open`.
- A hand-built non-manifold edge fails with `surface-non-manifold`.
- A hand-built inward-wound closed box fails with `surface-winding-invalid`.
- A collapsed/duplicate-vertex triangle fails with `surface-degenerate`.
- A closed box at both large and tiny scale passes.
- Every shipped library part (existing creatures, mech, craft) passes.
- The emitted GLB's materials never set `doubleSided`.
- The viewer's authored JS never selects `DoubleSide`.
