# Contract: `catalog.json` v1.0

**Status**: normative for feature 002
**Schema**: [catalog.schema.json](./catalog.schema.json)
**Bundle manifest**: [bundle.schema.json](./bundle.schema.json)

## Purpose

`catalog.json` is the only discovery contract the viewer consumes. It is
produced by `beastforge view` in both modes and served at the bundle root. It
lists every **loadable** library recipe exactly once with the facts needed for
the gallery, plus relative URLs for the asset and the authoritative sidecar
manifest.

The catalog is a **projection**, never a second source of truth. It may surface
`name`, `category`, `description`, `tags`, `recipeVersion`, `testedWith`, and
`recipeSha256`; every one of those is also present in the manifest (or derived
from the same canonical recipe document). Bounds, clips, events, sockets,
volumes, phases, materials, playback, and budgets stay in the manifest and are
fetched by the viewer.

## Shape

```json
{
  "schemaVersion": "1.0",
  "toolVersion": "0.1.0",
  "generatedBy": "beastforge",
  "categories": ["boss", "quadruped", "swarm"],
  "creatures": [
    {
      "name": "ridge-stalker",
      "category": "quadruped",
      "description": "A low, ridge-backed quadruped predator with a chitin skull plate.",
      "tags": ["quadruped", "predator", "ridge"],
      "recipeVersion": "1.0.0",
      "testedWith": "0.1.0",
      "recipeSha256": "<64 lowercase hex characters>",
      "asset": "creatures/ridge-stalker/<sha>/ridge-stalker.glb",
      "manifest": "creatures/ridge-stalker/<sha>/ridge-stalker.manifest.json"
    }
  ],
  "warnings": [
    { "path": "library/other/unreadable.yaml", "message": "…" }
  ]
}
```

All fields are required. Unknown fields are **not** allowed in the produced
document (the schema is closed), but consumers must ignore unknown fields so a
newer minor catalog remains usable.

## Ordering and determinism

| Part | Rule |
|------|------|
| `categories` | Canonical order `boss, quadruped, swarm, other`, filtered to present categories. |
| `creatures` | Ascending `name`. Names are unique. |
| `tags` | Recipe declaration order. |
| `warnings` | Ascending `path`. |
| Serialization | `beastforge.utils.canonical.canonical_json`: sorted keys, compact separators, ASCII-only, trailing newline, no NaN/Infinity. |
| Forbidden | Wall clock, locale-dependent formatting, hostnames, absolute paths, unseeded randomness, build timestamps. |

Two catalogs produced from the same recipes and `toolVersion` are byte-identical.

## Coverage and agreement

- The catalog contains **exactly one** entry for every recipe that loads via the
  normal library scan. "Loads" means the YAML parses into a valid recipe model,
  matching `beastforge list`. Recipes that fail to parse are omitted and reported
  in `warnings`.
- A recipe that parses but fails the generation/validation gate still appears in
  local mode; its card and stage show an actionable per-creature error. Static
  export is stricter: a gate failure aborts the export (exit 3) so the published
  catalog never references a missing asset.
- For each entry, a contract test generates the package and asserts:
  - `name == manifest.creature.name`
  - `category == manifest.creature.category`
  - `description == manifest.creature.description`
  - `recipeSha256 == manifest.provenance.recipeSha256`
- The number of entries equals the number of loadable recipes; no duplicates.
- Every `asset` and `manifest` path resolves in the same mode: it exists in the
  exported bundle, and in local mode it is generated on demand if absent and
  then served.

## URL rules

- Paths are relative to the catalog document, POSIX separators, no leading `/`,
  no query string, no fragment.
- The asset path shape is fixed:
  `creatures/<name>/<recipeSha256>/<name>.glb`.
- The manifest path shape is fixed:
  `creatures/<name>/<recipeSha256>/<name>.manifest.json`.
- Because `recipeSha256` is part of the path, a recipe change produces a new URL.
  A URL's bytes never change, so both modes may serve it as immutable.

## Versioning

`schemaVersion` is `MAJOR.MINOR`:

- **MINOR** — additive optional fields or new warning metadata; existing fields
  keep their meaning. Consumers read normally and ignore unknown fields.
- **MAJOR** — removed/renamed required fields, changed URL shape, changed value
  meaning, or changed ordering guarantees. Consumers must reject a different
  major with an explicit message rather than partially reading.

`toolVersion` is informational and may change without a catalog version bump.

## Static bundle (`bundle.json`)

The export also writes `bundle.json` (schema: `bundle.schema.json`):

```json
{
  "schemaVersion": "1",
  "toolVersion": "0.1.0",
  "files": [
    { "path": "assets/app.js", "sha256": "…", "bytes": 1234 },
    { "path": "catalog.json", "sha256": "…", "bytes": 5678 }
  ]
}
```

- Lists every emitted file **except `bundle.json` itself**, sorted by path.
- No timestamps or hostnames.
- Used by the export determinism check and CI; the viewer does not fetch it.

## Bundle layout

```text
<target>/
├── index.html
├── assets/                       # frontend + assets/three/...
├── catalog.json
├── bundle.json
└── creatures/
    └── <name>/<recipeSha256>/
        ├── <name>.glb
        └── <name>.manifest.json
```

`<target>` may contain unrelated files; the exporter only writes/replaces the
paths above. Without `--force`, a non-empty target is refused.
