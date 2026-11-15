# Architecture

beastforge is a single Python CLI package with a hard boundary between a **pure
build core** and **adapters** that touch the filesystem, environment, or
texforge. The four accepted ADRs are the design law:

- [ADR 261114-1](../../_ai/technical_decisions/ADR__261114-1__gltf-manifest-contract.md):
  glTF 2.0 plus a sidecar manifest.
- [ADR 261114-2](../../_ai/technical_decisions/ADR__261114-2__offline-deterministic-generator.md):
  offline, deterministic, texforge-shaped CLI.
- [ADR 261114-3](../../_ai/technical_decisions/ADR__261114-3__construction-bound-skinning.md):
  skin weights fall out of surface construction.
- [ADR 261114-4](../../_ai/technical_decisions/ADR__261114-4__baked-joint-clips-and-event-frames.md):
  clips are baked at 60 Hz; manifest events are authoritative.

## Goals and boundaries

- One generation produces one `.glb` and one `.manifest.json`, committed as an
  atomic pair.
- Output bytes depend only on the recipe, the resolved parameters, and the tool
  version. No wall clock, locale, hostname, environment ordering, or unseeded
  randomness may reach geometry, clips, textures, or JSON.
- Recipes are inert data. They name clip generators from a closed registry and
  texforge recipes by name; they never execute code.
- Validation is a gate, not advice. A package cannot be committed if the gate
  would reject it.

## Components

```mermaid
flowchart LR
  subgraph Authoring
    R[Recipe YAML] --> L[Loader + pydantic model]
  end
  subgraph Core["Pure build core"]
    L --> P[Params resolver]
    P --> SK[Rig: rest/world + inverse binds]
    SK --> G[Geometry: sweep / shell / rigid]
    L --> C[Clip registry + 60Hz bake]
    G --> M[Mesh]
    C --> A[Baked clips]
    M --> X[GLB writer]
    A --> X
    SK --> X
    M --> MAN[Manifest assembler]
    A --> MAN
    L --> V[Validation gate]
    M --> V
    MAN --> V
  end
  subgraph Adapters
    L -.-> FS[(filesystem)]
    T[texforge adapter] --> X
    X --> ST[Staging dir + os.replace]
    MAN --> ST
    ST --> OUT[dist/name/*.glb + *.manifest.json]
  end
  OUT --> SR[Showroom rasterizer + compare]
  SR --> REF[(showroom/reference)]
```

| Module | Responsibility | IO? |
|--------|----------------|-----|
| `model/` | pydantic recipe, manifest, report, finding, and error models | no |
| `params.py` | declared knobs, coercion, ranges, suggestions | no |
| `rng.py` | SHA-256-derived seed streams | no |
| `rig/` | world rest transforms, inverse binds, joint-band weights | no |
| `geometry/` | swept tubes, torso shells, rigid parts, normals | no |
| `anim/` | closed generator registry, 60 Hz sampling, baked tracks | no |
| `export/` | deterministic GLB writer and manifest assembly | no |
| `validation/` | one ordered gate over skeleton, surfaces, skin, clips, hooks, materials, budgets, determinism | reads texforge recipe metadata only |
| `showroom/raster+compare+structural` | software rendering, perceptual comparison, structural summary | no |
| `pipeline.py` | pure orchestration of recipe → skeleton → mesh → clips | no |
| `render.py` | staging dir, texture rendering, atomic commit, report | yes |
| `texture/texforge_adapter.py` | the only texforge-aware module | yes |
| `library.py`, `config.py` | catalog scanning, name resolution, settings | yes |
| `cli/` | Typer grammar, streams, exit codes, error rendering | yes |
| `viewer/catalog.py` | pure library scan -> `catalog.json` v1.0 | no |
| `viewer/cache.py` | content-addressed `(name, recipeSha256)` cache, serialized generation | yes |
| `viewer/server.py` | loopback `ThreadingHTTPServer`, routes, CSP, path safety | yes |
| `viewer/export.py` | pure export plan plus staged static-bundle writer | yes |
| `viewer/assets.py` | `importlib.resources` locator for packaged frontend | no |
| `viewer/static/` | buildless ES-module frontend; no Node or bundler | browser |

## Viewer component

The viewer is a read-only consumer of the same packages `render` produces. It
never re-derives gameplay facts or regenerates geometry; the sidecar manifest
remains authoritative.

```mermaid
flowchart LR
  LIB[(library/*.yaml)] --> CAT[catalog.py]
  CAT --> CJSON[catalog.json v1.0]
  CJSON --> BROWSER[buildless frontend]
  BROWSER -->|GET asset| SRV[server.py]
  SRV --> CACHE[cache.py]
  CACHE -->|miss| REN[render.py]
  REN --> CACHE
  CACHE -->|creatures/name/sha/*| BROWSER
  CJSON --> EXP[export.py]
  REN --> EXP
  STATIC[static/ + third_party/three] --> EXP
  EXP --> SITE[(static bundle + bundle.json)]
```

- **Catalog**: pure projection of every loadable recipe; relative,
  content-addressed URLs; canonical JSON; warnings for unreadable recipes.
- **Cache**: hit requires both files and a matching manifest digest; generation
  is global-serialized and installed with one `os.replace`.
- **Server**: loopback only, regenerates the catalog per request, rejects
  traversal, and isolates generation failures to one creature.
- **Export**: builds in a sibling staging directory and installs only owned
  paths, so a re-export preserves unrelated files and never commits binaries.
- **Frontend**: browser-native import map plus relative vendor imports, one
  shared offscreen renderer for thumbnails, and manifest-driven stage framing.
  `third_party/three/` is pinned and vendored; there is no npm/build step and no
  runtime request to an external host.

## Data flow and determinism

1. Load YAML with `yaml.safe_load`, reject executable keys/tags, validate the
   strict pydantic model.
2. Resolve declared parameters plus `--set` overrides.
3. Compute `recipe_sha256` from canonical JSON, then
   `run_seed = sha256("beastforge/v1:" + recipe_sha256 + ":" + canonical(params))`.
4. Build the skeleton, every surface, and every clip from the seed.
5. Render texforge textures in-process and embed the PNGs.
6. Assemble the canonical manifest.
7. Run the gate; only then write staged files and `os.replace` both into place.

Byte identity is enforced by golden tests, a 100-run determinism test, and a
two-working-directory comparison.

## Key trade-offs

- **Own numpy geometry and GLB writer** instead of a mesh library: full control
  of vertex/triangle/accessor order is the cheapest way to guarantee byte
  identity. `trimesh` is a dev-only independent consumer.
- **CPU software rasterizer** instead of OpenGL/EGL: no GPU, display server, or
  driver variation; the showroom stays offline and CI-friendly.
- **Construction-bound weights** instead of auto-skinning: weights are traceable
  to a recipe line and always inside the 4-influence glTF limit.
- **Baked clips** instead of runtime procedural animation: engines only need a
  standard glTF animation player; gameplay timing lives in the manifest.

## Further reading

- [API and JSON surfaces](api.md)
- [Recipe authoring](recipes.md)
- [Showroom and tolerance](showroom.md)
- [Development and release](development.md)
- Feature spec, plan, data model, and contracts under
  [specs/001-procedural-creature-generator/](../../specs/001-procedural-creature-generator/)
