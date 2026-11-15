# Feature Specification: WebGL Library Viewer

**Feature Branch**: `n/a — created on main (no git hook configured)`

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: `_ai/backlog/active/261115_0338__DESIGN_HANDOFF__webgl-library-viewer.md`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse the library visually (Priority: P1)

A developer or artist opens the viewer and sees every creature in the library as
a searchable, category-filtered gallery of live 3D thumbnails. Selecting a card
opens that creature on a full stage.

**Why this priority**: Discovery is the reason the viewer exists. Without a
browsable catalog, the remaining inspection features have nothing to inspect.

**Independent Test**: Open the viewer against the shipped library, confirm every
loadable recipe appears exactly once with its name, category, and description,
apply a category filter and a text search, and confirm the visible cards narrow
to matching creatures without regenerating anything.

**Acceptance Scenarios**:

1. **Given** the shipped library, **When** the viewer loads, **Then** each
   loadable recipe appears as one card showing its name, category, and
   description.
2. **Given** the gallery is loaded, **When** the user selects a category,
   **Then** only creatures in that category remain visible and the selection
   survives a page reload via a deep link where applicable.
3. **Given** the gallery is loaded, **When** the user types part of a creature
   name or description, **Then** the gallery narrows to matching creatures and
   shows an explicit empty state when nothing matches.
4. **Given** a recipe that cannot be loaded, **When** the viewer scans the
   library, **Then** that recipe is reported as a non-fatal warning and the rest
   of the gallery still renders.

---

### User Story 2 - Inspect a creature's animation and manifest facts (Priority: P2)

A developer opens one creature, orbits and zooms around it, plays any of its
baked clips, sees where that clip's events land in time, and reads the manifest
facts (clips, events, sockets, volumes, phases, bounds, provenance) in an
inspector without re-deriving any of them.

**Why this priority**: This is the value beyond `beastforge list` and still
images; it lets a consumer verify the gameplay-facing contract before building
against it.

**Independent Test**: Open a known creature, switch between every declared clip,
confirm each clip plays and its event markers match the manifest, orbit the
model, and compare every inspector value against the sidecar manifest for that
creature.

**Acceptance Scenarios**:

1. **Given** a creature is open, **When** the stage initializes, **Then** the
   camera frames the creature using its manifest bounds so the whole creature is
   visible without manual adjustment.
2. **Given** a creature has multiple clips, **When** the user switches clips,
   **Then** playback restarts on the chosen clip and the active clip is clearly
   indicated.
3. **Given** a clip declares events, **When** that clip is active, **Then** the
   timeline shows one mark per event at its declared time and the mark's label
   matches the event name.
4. **Given** a creature is open, **When** the user opens the inspector,
   **Then** they can view manifest facts, the clip inventory, and the event
   inventory in separate tabs, and every displayed value equals the
   corresponding manifest value.
5. **Given** a creature is open, **When** the user drags, scrolls, or pinches on
   the stage, **Then** the model orbits and zooms while the creature stays
   centered.

---

### User Story 3 - Start a local viewer in one command (Priority: P3)

A developer runs one non-interactive command from the repository and their
default browser opens the viewer for the current library. Assets that do not yet
exist are produced on demand, and subsequent visits reuse them without user
action.

**Why this priority**: Local viewing is the default workflow and must not
require a separate build, export, or server setup.

**Independent Test**: From a clean cache, run the local view command, confirm a
browser opens on a working gallery, open a creature that was never generated,
confirm it renders, stop the command, and confirm no tracked files changed.

**Acceptance Scenarios**:

1. **Given** a library and an empty cache, **When** the user starts the local
   viewer, **Then** the browser opens a gallery that reflects the current
   library and the process tells the user how to stop it.
2. **Given** a creature has no cached asset, **When** the user opens it,
   **Then** the viewer reports progress, produces the asset, and displays the
   creature without requiring a second command.
3. **Given** a creature was already produced, **When** the user reopens it,
   **Then** the existing cached asset is served and no regeneration occurs.
4. **Given** a recipe changes after an asset was cached, **When** the user
   reopens that creature, **Then** the viewer serves an asset that reflects the
   current recipe rather than stale output.
5. **Given** the local viewer is running, **When** the user stops it, **Then**
   the port is released and no repository files were modified.

---

### User Story 4 - Publish the full library as a static site (Priority: P4)

A maintainer produces a self-contained static bundle of the whole library and
publishes it automatically from continuous integration; any visitor can browse,
orbit, and play every published creature with no server-side component.

**Why this priority**: A public, free-to-host demo broadens access, but it is
secondary to the local workflow and must not become the only way to view.

**Independent Test**: Produce two bundles from the same recipes and tool
version, confirm their file lists and contents are identical, serve one from a
plain static file server, and confirm every creature loads, orbits, and plays.

**Acceptance Scenarios**:

1. **Given** a library, **When** the maintainer exports a static bundle,
   **Then** the output contains a viewer entry point, the catalog, and every
   creature asset needed to browse and play the library with no network access
   beyond that bundle.
2. **Given** the same recipes, assets, and tool version, **When** the export is
   run twice, **Then** both bundles are byte-identical, including file ordering
   and the catalog.
3. **Given** a push that changes a recipe or the viewer, **When** continuous
   integration runs, **Then** the published site is rebuilt from the current
   library and no generated binary is committed to the repository.
4. **Given** the published site, **When** a visitor opens a deep link to a
   creature and clip, **Then** that creature and clip are shown directly.

---

### Edge Cases

- **Empty or unreadable library**: the viewer shows an explicit empty state and
  any per-recipe warnings instead of a blank page or silent failure.
- **Unknown creature or clip in a deep link**: the viewer falls back to the
  gallery or the creature's default clip and explains what was not found.
- **Creature with no clips**: the stage still renders the model and playback
  controls are disabled with an explanation.
- **Asset production failure**: the affected card and stage show an actionable
  error while the rest of the library remains usable.
- **WebGL unavailable**: the viewer reports the limitation clearly instead of
  showing a broken stage.
- **Slow or partial asset load**: the viewer shows loading state and does not
  block the rest of the gallery.
- **Very large library**: the gallery remains responsive and generates assets
  only for creatures the user actually opens or previews.
- **Export into a non-empty directory**: the export either refuses safely or
  replaces only its own outputs, never unrelated files.
- **Recipe changed between export and publish**: the bundle is regenerated from
  the current library so the published catalog never references missing assets.
- **Offline / no third-party access**: the viewer functions with zero requests
  to external hosts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The viewer MUST present every loadable library recipe as a card
  showing its name, category, and description.
- **FR-002**: The viewer MUST support filtering the gallery by category and
  narrowing it with free-text search over name and description.
- **FR-003**: The viewer MUST show a live 3D thumbnail for each visible card
  without requiring the user to open the creature first.
- **FR-004**: The viewer MUST let users open a creature into a full stage that
  supports orbit, zoom, and automatic framing from the creature's bounds.
- **FR-005**: The viewer MUST list every clip declared in the creature's
  manifest and allow the user to play any one of them.
- **FR-006**: The viewer MUST display event markers at the times declared in the
  manifest for the active clip, labeled with the event names.
- **FR-007**: The viewer MUST display manifest facts, clips, and events in
  separate inspector views and MUST NOT display values that contradict the
  manifest.
- **FR-008**: The viewer MUST resolve deep links of the form
  creature-plus-clip and restore that exact stage state on load.
- **FR-009**: The viewer MUST tolerate unknown manifest fields and MUST NOT fail
  when the manifest gains fields.
- **FR-010**: The viewer MUST report per-recipe problems as non-fatal warnings
  while continuing to serve the rest of the library.
- **FR-011**: A single command MUST start a local viewer that reflects the
  current library, opens a browser, and reports how to stop it.
- **FR-012**: The local viewer MUST produce a missing creature asset on demand,
  reuse cached assets, and detect when a recipe has changed so stale assets are
  not served.
- **FR-013**: The local viewer MUST keep its cache outside the tracked
  repository content and MUST NOT modify tracked files.
- **FR-014**: The local viewer MUST be reachable only from the local machine.
- **FR-015**: A single export command MUST produce a self-contained static
  bundle containing the viewer, the catalog, and all assets needed for the
  library.
- **FR-016**: The static export MUST be byte-identical for identical recipes,
  assets, and tool version; it MUST NOT embed timestamps, hostnames, or
  unseeded values.
- **FR-017**: Both delivery modes MUST serve the same catalog structure with
  relative references, so the viewer behaves identically regardless of mode.
- **FR-018**: The catalog MUST cover every loadable recipe and MUST agree with
  each creature's manifest for every fact it surfaces.
- **FR-019**: Continuous integration MUST rebuild and publish the static site
  when a recipe or the viewer changes, and MUST NOT commit generated binary
  assets.
- **FR-020**: The project MUST ship an automated contract check for catalog
  coverage and schema, and a determinism check comparing two exports.
- **FR-021**: The project MUST ship an opt-in browser smoke check covering
  viewer initialization, card count, model load, clip list, and deep links;
  the default automated test run MUST remain offline and fast.
- **FR-022**: The viewer MUST make no runtime requests to external hosts and
  MUST NOT require an additional toolchain or build step to run.

### Key Entities

- **Catalog entry**: One library creature as the viewer sees it — name,
  category, description, tags, and references to its asset and manifest. There
  is exactly one per loadable recipe.
- **Catalog document**: The versioned, canonical index of all catalog entries
  plus the viewer metadata needed to consume them. It is derived from the
  library and may surface manifest facts but never contradicts them.
- **Creature package**: The generated asset plus its authoritative sidecar
  manifest; the only source of creature facts shown by the inspector.
- **Clip**: A named animation with duration and loop flag; the unit the viewer
  plays.
- **Event**: A named moment within a clip at a declared time; shown as a
  timeline mark.
- **Manifest fact**: Any inspector-visible value from the manifest, including
  sockets, volumes, phases, bounds, and provenance.
- **Viewer session**: The selected creature, active clip, camera state, and
  filters, recoverable from a deep link.
- **Export bundle**: A self-contained static copy of the viewer, catalog, and
  creature assets.
- **Cache entry**: A locally produced creature asset keyed to a recipe state,
  disposable and never a source of truth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a library of at least 100 creatures, users can locate a known
  creature by category and search in under 10 seconds without generating
  anything.
- **SC-002**: 100% of loadable recipes appear exactly once in the catalog, and
  100% of inspector values match their manifests in the contract check.
- **SC-003**: 100% of manifest clips are playable and 100% of events for the
  active clip appear as timeline marks at their declared times.
- **SC-004**: Two exports of the same library and tool version are byte-identical
  in every file, including the catalog.
- **SC-005**: A deep link to any valid creature and clip opens that exact state
  with zero additional user actions.
- **SC-006**: A user goes from starting the local viewer to seeing the gallery
  in under 10 seconds on a warm cache, with no second command.
- **SC-007**: The published site loads and plays 100% of the published library
  with no requests to external hosts.
- **SC-008**: Zero generated binary assets are committed across a full publish
  cycle.
- **SC-009**: The default automated test run remains offline, requires no
  browser, and does not regress the existing suite's runtime by more than 10%.
- **SC-010**: The opt-in browser smoke check passes on every supported
  desktop browser configuration used by the project.

## Assumptions

- **Audience**: Developers and artists already working with the repository;
  they have a desktop browser with WebGL support. Mobile-first layout is out of
  scope.
- **Usage**: One local user at a time; no authentication, accounts, or private
  hosted views.
- **Library size**: Starts at the current handful of recipes and is designed to
  stay responsive as it grows to roughly 100 creatures.
- **Authoritative source**: The existing sidecar manifest is the only source of
  creature facts; the viewer is read-only and never re-derives gameplay meaning.
- **Generation**: Assets are produced only by the existing pipeline; the viewer
  does not re-implement geometry, export, texture embedding, or parameter
  overrides.
- **Delivery posture**: Everything runs offline and requires no additional
  language toolchain, build step, or runtime CDN dependency; the local mode is
  the default and the static export is the publish path.
- **Hosting**: The public copy is the full library on GitHub Pages for a public
  repository, rebuilt in continuous integration; in-progress or private recipes
  are not published through a separate selective mechanism.
- **Repository hygiene**: Generated asset binaries are never committed; the
  local cache is disposable and ignored by version control.
- **Determinism**: Wall clock, locale, hostname, and unseeded randomness remain
  excluded from catalog and export outputs, consistent with the existing
  generator contract.
- **Test tooling**: Browser-based checking is an opt-in development dependency
  so the default test run stays offline and fast.
- **Deferred scope**: Live parameter editing, in-browser regeneration, recipe
  mutation, skeleton or bone overlays, side-by-side comparison, replacing the
  existing showroom, authentication, and WebGPU are out of scope for this
  feature.
- **Open implementation details**: Thumbnail concurrency limits and cache
  retention, the exact continuous-integration trigger filters, catalog schema
  versioning rules, and the cadence for updating the vendored 3D runtime are
  maintainer decisions that do not change this specification's behavior.
