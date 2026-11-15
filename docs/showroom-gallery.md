# Showroom gallery

Every creature in the shipped library has an approved reference set under
[`showroom/reference/`](../showroom/reference). The showroom renders the current
build with fixed cameras and lighting and compares it against those references,
so this gallery is exactly what visual regression is protecting.

For the comparison rules and the accept workflow, see
[Showroom and visual regression](showroom.md).

## How the frames are made

Each creature is built through the normal pipeline and rasterized on the CPU by
`src/beastforge/showroom/raster.py`:

- Five RGBA frames per creature at `512 × 512`.
- Four fixed orthographic cameras: front, three-quarter, side, rear.
- One front frame is rerendered in an **extreme-bend** pose: a declared test
  joint is rotated 90° and the mesh is skinned, exposing shoulder/hip shearing.
- A z-buffer, one fixed key light plus ambient, two-sided Lambert shading, and
  nearest-neighbour texforge texture sampling.
- Transparent background (`alpha = 0`) on uncovered pixels.

No GPU, EGL, display server, or driver is involved, so the same frames render in
CI and offline.

## Regenerating this gallery

References only change through an explicit accept:

```bash
uv run beastforge showroom --accept
```

That rewrites `showroom/reference/<creature>/` with the newly rendered frames.
Commit the updated references and refresh the image links below in the same
change.

## ash-crowned-tyrant

Recipe: [`library/boss/ash-crowned-tyrant.yaml`](../library/boss/ash-crowned-tyrant.yaml)

**Turntable, rest pose**

| Front | Three-quarter | Side | Rear |
|:---:|:---:|:---:|:---:|
| ![Front view, rest pose](../showroom/reference/ash-crowned-tyrant/frames/front__rest.png) | ![Three-quarter view, rest pose](../showroom/reference/ash-crowned-tyrant/frames/three-quarter__rest.png) | ![Side view, rest pose](../showroom/reference/ash-crowned-tyrant/frames/side__rest.png) | ![Rear view, rest pose](../showroom/reference/ash-crowned-tyrant/frames/rear__rest.png) |

**Deformation check**

| Front, extreme bend (90°) |
|:---:|
| ![Front view with the test joint bent 90 degrees](../showroom/reference/ash-crowned-tyrant/frames/front__extreme-bend.png) |

## ridge-stalker

Recipe: [`library/quadruped/ridge-stalker.yaml`](../library/quadruped/ridge-stalker.yaml)

**Turntable, rest pose**

| Front | Three-quarter | Side | Rear |
|:---:|:---:|:---:|:---:|
| ![Front view, rest pose](../showroom/reference/ridge-stalker/frames/front__rest.png) | ![Three-quarter view, rest pose](../showroom/reference/ridge-stalker/frames/three-quarter__rest.png) | ![Side view, rest pose](../showroom/reference/ridge-stalker/frames/side__rest.png) | ![Rear view, rest pose](../showroom/reference/ridge-stalker/frames/rear__rest.png) |

**Deformation check**

| Front, extreme bend (90°) |
|:---:|
| ![Front view with the test joint bent 90 degrees](../showroom/reference/ridge-stalker/frames/front__extreme-bend.png) |

## elephant

Recipe: [`library/quadruped/elephant.yaml`](../library/quadruped/elephant.yaml)

**Turntable, rest pose**

| Front | Three-quarter | Side | Rear |
|:---:|:---:|:---:|:---:|
| ![Front view, rest pose](../showroom/reference/elephant/frames/front__rest.png) | ![Three-quarter view, rest pose](../showroom/reference/elephant/frames/three-quarter__rest.png) | ![Side view, rest pose](../showroom/reference/elephant/frames/side__rest.png) | ![Rear view, rest pose](../showroom/reference/elephant/frames/rear__rest.png) |

**Deformation check**

| Front, extreme bend (90°) |
|:---:|
| ![Front view with the test joint bent 90 degrees](../showroom/reference/elephant/frames/front__extreme-bend.png) |

## giraffe

Recipe: [`library/quadruped/giraffe.yaml`](../library/quadruped/giraffe.yaml)

**Turntable, rest pose**

| Front | Three-quarter | Side | Rear |
|:---:|:---:|:---:|:---:|
| ![Front view, rest pose](../showroom/reference/giraffe/frames/front__rest.png) | ![Three-quarter view, rest pose](../showroom/reference/giraffe/frames/three-quarter__rest.png) | ![Side view, rest pose](../showroom/reference/giraffe/frames/side__rest.png) | ![Rear view, rest pose](../showroom/reference/giraffe/frames/rear__rest.png) |

**Deformation check**

| Front, extreme bend (90°) |
|:---:|
| ![Front view with the test joint bent 90 degrees](../showroom/reference/giraffe/frames/front__extreme-bend.png) |

## chitter-mite

Recipe: [`library/swarm/chitter-mite.yaml`](../library/swarm/chitter-mite.yaml)

**Turntable, rest pose**

| Front | Three-quarter | Side | Rear |
|:---:|:---:|:---:|:---:|
| ![Front view, rest pose](../showroom/reference/chitter-mite/frames/front__rest.png) | ![Three-quarter view, rest pose](../showroom/reference/chitter-mite/frames/three-quarter__rest.png) | ![Side view, rest pose](../showroom/reference/chitter-mite/frames/side__rest.png) | ![Rear view, rest pose](../showroom/reference/chitter-mite/frames/rear__rest.png) |

**Deformation check**

| Front, extreme bend (90°) |
|:---:|
| ![Front view with the test joint bent 90 degrees](../showroom/reference/chitter-mite/frames/front__extreme-bend.png) |
