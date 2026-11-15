# Feature Specification: Procedural 3D Creature Generator

**Feature Branch**: `n/a — created on main (no git hook configured)`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: `_ai/backlog/active/261114_1931__DESIGN_HANDOFF__beastforge-procedural-3d-creatures.md`

## Clarifications

### Session 2026-11-14

- Q: Must the generated package contain the rendered texture images, or only reference the texture recipe? → A: Embed the rendered texture set in the package; no reference-only mode in v1.
- Q: Must every creature provide a fixed core set of clips with reserved names, or may clip names vary freely per recipe? → A: Required core clip names, with extra clips allowed beyond the core.
- Q: Must showroom comparisons require pixel-identical frames, or allow a documented perceptual tolerance? → A: Perceptual tolerance, with fixed cameras and lighting.
- Q: When a recipe omits sockets, hit volumes, or phases, should the generator invent safe defaults, or must the gameplay-critical ones be declared? → A: Require critical hooks; no silent gameplay defaults.
- Q: How should a consumer treat a manifest whose schema version differs from the one it was built against? → A: Major-strict, minor-tolerant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a reproducible creature from the library (Priority: P1)

An agent or developer names a creature from an in-repo library and runs one
non-interactive command. They receive an importable, animated 3D creature asset
plus a companion gameplay manifest, and a machine-readable report of exactly
what was produced. Running the same command again produces identical bytes.

**Why this priority**: This is the product. Every other story either feeds this
loop (authoring, catalog) or guards it (validation, regression).

**Independent Test**: Generate any library creature twice in a clean
environment and compare the reported checksums; import the result into a
standard-format 3D viewer and confirm the creature renders and animates.

**Acceptance Scenarios**:

1. **Given** the in-repo creature library, **When** the user lists available
   creatures, **Then** each catalog entry reports its name, category,
   description, and declared parameters without generating anything.
2. **Given** a valid library recipe with no overrides, **When** the user
   generates it, **Then** one 3D asset file and one sidecar manifest are
   written, and the report lists their paths, content checksums, and the
   clip/event/socket/volume/phase inventory.
3. **Given** the same recipe, the same resolved parameters, and the same tool
   version, **When** generation is repeated — including in a different working
   directory or on another machine — **Then** the asset and manifest are
   byte-identical.
4. **Given** parameter overrides, **When** the user generates, **Then** the
   overrides are applied, echoed in the report, and only seeded variation may
   differ; an unknown parameter is rejected with an actionable message and no
   output is written.
5. **Given** an invalid recipe, **When** the user generates, **Then** the
   command exits non-zero, identifies the offending recipe location and the
   constraint violated, and leaves no partial output behind.

---

### User Story 2 - Drive creature behaviour from the manifest (Priority: P2)

A game developer imports the generated asset and uses the sidecar manifest — not
the generator source — to know which clip is the attack, when the hit lands,
where the muzzle is, which volume is the weak point, and when boss phases
change.

**Why this priority**: The manifest is the reason to prefer this generator over
an opaque asset pack; it makes the creature gameplay-ready in any engine.

**Independent Test**: Hand only the manifest to a developer and ask them to
name the attack clip, the impact time, and the muzzle socket; they can answer
without reading any generator code.

**Acceptance Scenarios**:

1. **Given** a downloaded creature package, **When** the manifest is read,
   **Then** it identifies its own schema version and lists every clip with
   name, duration, loop flag, and originating generator.
2. **Given** a clip with gameplay events, **When** the manifest is read,
   **Then** every event names an existing clip and carries a name and a time in
   seconds.
3. **Given** a creature with attachment points, **When** the manifest is read,
   **Then** each socket names an existing bone or node plus an offset.
4. **Given** a creature with combat hooks, **When** the manifest is read,
   **Then** hit/weak-point/collision volumes, boss phase thresholds, bounds,
   and a suggested scale are present.
5. **Given** a manifest produced by a newer tool version, **When** an existing
   consumer reads it, **Then** unrecognized fields are ignored and required
   fields remain readable.
6. **Given** playback rate is changed by the engine, **When** the consumer reads
   the manifest, **Then** it is warned that event times scale proportionally.

---

### User Story 3 - Author a new creature, skeleton first (Priority: P3)

A recipe author describes a new creature as declarative data: bone chains first,
then surfaces bound to those bones, materials referenced by texture recipe name,
clips chosen from generators, and gameplay hooks declared alongside. No code is
written and no code is executed from the recipe.

**Why this priority**: The library is only as useful as the recipes it can
express; the skeleton-first grammar is the core authoring contract.

**Independent Test**: Author one new quadruped recipe from the documented
grammar, then generate and validate it successfully without editing generator
code.

**Acceptance Scenarios**:

1. **Given** the recipe grammar, **When** a creature is defined, **Then** the
   skeleton is declared first as named bones with parent, rest transform, and
   ordered chains, and surfaces reference those bones by name.
2. **Given** a limb defined as a bone chain, **When** the creature is
   generated, **Then** the limb is a continuous skinned surface with texture
   coordinates running along the limb and around it.
3. **Given** a rigid part such as a plate, spike, or weapon, **When** the
   creature is generated, **Then** the part follows exactly one bone without
   deformation.
4. **Given** a silhouette variation such as taper, twist, radial noise, squash,
   or per-part scale, **When** the user sets it, **Then** the change is visible
   and deterministic.
5. **Given** a clip declaration, **When** the author selects a generator and
   its parameters with a duration and loop flag, **Then** the clip is produced
   and documented in the manifest.
6. **Given** timing authored in ticks at 60 Hz, **When** the recipe is
   generated, **Then** the duration is converted exactly and the manifest reports
   seconds.
7. **Given** a material declaration, **When** the recipe references a texture
   recipe by name, **Then** the reference and its resolved parameters appear in
   the manifest and the generator produces no texture content of its own.
8. **Given** a recipe containing executable content, **When** it is loaded,
   **Then** the content is rejected because recipes are inert data.

---

### User Story 4 - Treat validation as a gate (Priority: P3)

A maintainer or agent runs validation locally and in continuous integration. It
exits non-zero on any skeleton, skin, manifest, or determinism defect and emits
a stable machine-readable finding list that names the exact location, the
constraint violated, and the expected value.

**Why this priority**: Deterministic self-correction by agents is the central
design constraint; a validation that only advises breaks that loop.

**Independent Test**: Introduce one known defect class at a time into a copy of
a library recipe and confirm each is rejected with its own stable finding code.

**Acceptance Scenarios**:

1. **Given** the shipped library, **When** validation runs, **Then** it exits
   zero and reports every creature as valid.
2. **Given** vertices whose weights do not sum to one within tolerance, **When**
   validation runs, **Then** it fails and identifies the affected vertices.
3. **Given** any vertex influenced by more than four bones, having zero total
   weight, or bound with a bind pose differing from the rest pose, **When**
   validation runs, **Then** each case fails with a distinct finding.
4. **Given** a bone hierarchy containing a cycle or duplicate bone name, or a
   degenerate or inverted joint transform, **When** validation runs, **Then**
   validation fails and names the bones involved.
5. **Given** an event, socket, phase, volume, or material reference pointing at
   something that does not exist, **When** validation runs, **Then** validation
   fails and names the dangling reference.
6. **Given** an event scheduled at or beyond a clip's duration, or a clip with
   non-positive duration, **When** validation runs, **Then** validation fails.
7. **Given** a recipe or generator path that could introduce environment- or
   time-dependent output, **When** validation runs, **Then** it fails as a
   determinism hazard.
8. **Given** any validation run, **When** machine-readable output is requested,
   **Then** findings use a stable schema with a code, severity, location,
   expected value, and suggested remedy per record.

---

### User Story 5 - Guard visual output with a showroom (Priority: P4)

A maintainer inspects all library creatures as turntable frames and extreme
joint-bend poses, then compares new output against approved reference images and
a structural summary. Unchanged creatures pass; intended changes are approved by
regenerating the references explicitly.

**Why this priority**: Determinism proves bytes are stable; only the showroom
proves the bytes are still the intended creature and that deformation has not
sheared.

**Independent Test**: Change one blend or sweep parameter on a creature,
regenerate, and confirm the showroom comparison flags only that creature while
the untouched library still passes.

**Acceptance Scenarios**:

1. **Given** the creature library, **When** the showroom is produced, **Then**
   each creature has turntable frames from multiple angles plus at least one
   extreme-bend pose.
2. **Given** approved reference output, **When** an unchanged creature is
   regenerated, **Then** the comparison reports a pass with no differences.
3. **Given** an intentionally changed creature, **When** the comparison runs,
   **Then** it reports a per-creature failure with the differing frames, and
   updating references is a separate, explicit action.
4. **Given** any creature, **When** the showroom runs, **Then** a structural
   summary is produced (joint count, clip inventory, skin-influence statistics,
   bounds) that can be diffed independently of pixels.

---

### Edge Cases

- A recipe names a parameter that does not exist: rejected with the nearest
  valid parameter suggested, and no output written.
- A recipe contains a bone cycle, duplicate bone or clip names, a zero-length
  bone, or omits a reserved core clip: validation fails naming the offending
  bones, names, or missing clip.
- A recipe omits its required hit volume or the attack impact event, or a boss
  recipe omits phase thresholds: validation fails naming the missing hook.
- A socket, event, phase, or volume refers to a bone or clip that was renamed or
  removed: validation fails rather than silently dropping the reference.
- An event time is negative, or falls at or beyond the clip duration: rejected.
- A clip has zero or negative duration, or a tick count is fractional: rejected.
- A requested surface mode is not supported in this version: rejected with an
  explicit unsupported-mode message rather than silently substituted.
- A referenced texture recipe is missing or its parameters are invalid: the
  generation is rejected before any asset is written.
- An output path already exists: generation refuses to overwrite unless the user
  explicitly opts in.
- Generation is interrupted: no partially written asset or manifest is left
  behind.
- A creature exceeds the declared mesh or bone budget: validation fails with the
  measured value and the limit.
- Creature, bone, clip, socket, and event names contain characters that are not
  stable identifiers: rejected rather than silently normalized, so the public
  contract cannot drift.
- A consumer presents a manifest with a newer minor schema version: unrecognized
  fields are ignored and every required field still reads. A different major
  schema version produces an explicit unsupported-version error, never a partial
  or undefined read.
- Two creatures are generated concurrently to the same output directory:
  outputs do not interleave or overwrite each other.
- Minor frame differences caused by renderer or floating-point variation occur:
  the showroom passes within the documented tolerance, while a real silhouette
  or deformation change still fails the comparison.

## Requirements *(mandatory)*

### Functional Requirements

**Catalog and discovery**

- **FR-001**: The project MUST ship an in-repo creature library organized by
  category, where each recipe carries catalog metadata: name, description,
  category, tags, declared parameters with types/units/defaults/limits, and the
  generator version it was tested with.
- **FR-002**: Users MUST be able to list creatures and categories, as
  human-readable output and as a stable machine-readable document.
- **FR-003**: Users MUST be able to inspect a recipe's parameters, types,
  defaults, units, and constraints without generating the creature.
- **FR-004**: Recipes MUST be loaded as inert data only; any executable content
  in a recipe MUST be rejected.

**Generation and reproducibility**

- **FR-005**: Users MUST be able to generate a creature by library name or by
  recipe path, with zero or more explicit parameter overrides, without any
  interactive prompt.
- **FR-006**: Generation MUST produce one standard 3D scene asset importable by
  common engines plus one sidecar gameplay manifest, treated as a single
  versioned pair. The package MUST be self-contained: the rendered texture set
  produced from the referenced texture recipes MUST be embedded, so a consumer
  can render the creature without the texture generator.
- **FR-007**: Generation MUST produce a machine-readable report containing output
  paths, content checksums, the emitted inventory (clips, events, sockets,
  volumes, phases), warnings, and provenance.
- **FR-008**: Generation MUST be byte-reproducible: the same recipe, resolved
  parameters, and tool version MUST yield identical asset and manifest bytes on
  any machine, independent of working directory, locale, clock, environment, or
  process state.
- **FR-009**: Only a seeded pseudo-random source MAY introduce variation;
  unseeded randomness, wall-clock input, and environment-dependent ordering MUST
  be impossible in a successful generation.
- **FR-010**: Every command MUST offer a stable machine-readable output mode that
  contains no human-only text, with success and failure signalled by exit code.
- **FR-011**: Errors MUST name the offending value and the next corrective step,
  and MUST NOT require reading generator source to understand.
- **FR-012**: Generation MUST NOT overwrite existing outputs unless the user
  explicitly allows it, and MUST leave no partial asset or manifest on failure or
  interruption.
- **FR-013**: The manifest MUST record provenance: recipe content hash, resolved
  parameters, tool version, and manifest schema version.

**Recipe grammar (skeleton first)**

- **FR-014**: A recipe MUST declare its skeleton before its surfaces: named bones
  with parent, rest transform, and ordered chains, plus a single declared root.
- **FR-015**: Limbs MUST be expressible as bone chains that generate continuous
  skinned tube surfaces, and torsos as ring shells bound along the spine.
- **FR-016**: Rigid parts — plates, spikes, weapons — MUST bind to exactly one
  bone and MUST NOT deform.
- **FR-017**: Skin weights MUST be determined during construction: one or two
  influences per vertex, blended across joints, normalized to one.
- **FR-018**: Texture coordinates MUST be generated by the surface construction so
  that referenced texture recipes tile without manual mapping.
- **FR-019**: Silhouette variation MUST be expressible at surface-construction
  time via taper, twist, radial noise, squash, and per-part scale, all seeded and
  deterministic.
- **FR-020**: The supported surface mode for this version MUST be limited to the
  construction-bound tubular mode; any other requested mode MUST be rejected with
  an explicit unsupported message.
- **FR-021**: Materials MUST reference texture recipes by name, MAY override their
  parameters, and MUST NOT cause the generator to implement its own texture
  synthesis. Referenced materials MUST be rendered at generation time and their
  images embedded in the package.
- **FR-022**: Clips MUST be declared by selecting a clip generator plus its
  parameters, duration, and loop flag; the available generators MUST cover at
  least idle breathing, locomotion gait, hover bobbing, hit recoil, telegraphed
  attack, and death collapse. Every creature MUST provide the reserved core clips
  `idle`, `locomotion`, `attack`, `hurt`, and `death`, and MAY provide additional
  clips with other names.
- **FR-023**: Clip timing MUST be authored in seconds, with a 60-tick-per-second
  field accepted as a convenience and converted exactly with no rounding drift.
- **FR-024**: Clips MUST be baked into the asset at generation time; the asset
  MUST contain no runtime procedural animation behaviour.
- **FR-025**: Every creature MUST explicitly declare at least one hit volume and
  the `attack` clip's impact event. Sockets MAY be omitted, and phases MAY be
  omitted except for creatures in the boss category, which MUST declare phase
  thresholds. The generator MUST NOT invent silent gameplay defaults, and
  validation MUST reject a missing required hook.
- **FR-026**: Parameters MUST be validated against their declared types, units,
  and limits; unknown keys MUST be errors that suggest the closest valid key.
- **FR-027**: Every creature MUST be generated in one consistent unit and
  orientation convention (metres, Y-up, forward −Z) with the manifest carrying a
  suggested scale for the consumer.
- **FR-028**: Recipes and generated assets MUST declare a mesh and bone budget;
  exceeding it MUST be a validation failure, not a warning.

**Manifest contract**

- **FR-029**: The manifest schema version MUST use major and minor components.
  A consumer on the same major version MUST be able to read the manifest while
  ignoring unknown fields, and MUST reject a different major version with an
  explicit unsupported-version error rather than a partial read.
- **FR-030**: The manifest MUST describe, per creature, every clip (name,
  duration, loop flag, source generator), every event (clip, time in seconds,
  name), every socket (name, target bone or node, offset), every hit, weak-point,
  and collision volume, every phase threshold, bounds, suggested scale, and
  provenance.
- **FR-031**: Manifest events MUST be the authoritative gameplay timing; baked
  keyframes MUST NOT be the source of event timing.
- **FR-032**: Clip, socket, event, and phase names MUST be treated as a public
  contract; renaming or removing one MUST require a major manifest schema version
  bump.
- **FR-033**: The manifest MUST warn consumers that changing playback rate scales
  event times proportionally.

**Validation gate**

- **FR-034**: Validation MUST be a gate with a zero/non-zero exit status and a
  stable machine-readable finding list.
- **FR-035**: Validation MUST reject skin and skeleton defects: weights not
  summing to one within a documented tolerance, more than four influences, any
  zero-weight vertex, a bind pose that differs from the rest pose, bone cycles,
  duplicate bone names, and degenerate or inverted joint transforms.
- **FR-036**: Validation MUST reject dangling references, missing core clips,
  and timing defects: events or sockets pointing at missing clips, bones, or
  nodes; any absent reserved core clip; events outside their clip's duration;
  non-positive clip durations; duplicate clip, socket, event, or phase names.
- **FR-037**: Validation MUST reject determinism hazards and missing or invalid
  texture recipe references.
- **FR-038**: Every generation MUST run the same validation before committing
  outputs, so an artefact cannot be produced that the gate would reject.

**Showroom and regression**

- **FR-039**: The showroom MUST produce, for every library creature, turntable
  frames from multiple angles and at least one extreme joint-bend pose.
- **FR-040**: The showroom MUST compare generated output against approved
  references under fixed cameras and lighting, using a documented perceptual
  tolerance (per-pixel threshold and changed-pixel ratio), report per-creature
  pass or failure with the differing frames, and require an explicit action to
  accept new references.
- **FR-041**: The showroom MUST also emit a structural summary per creature —
  joint count, clip and event inventory, skin-influence statistics, and bounds —
  that can be compared independently of rendered images.

### Key Entities *(include if data involved)*

- **Creature Recipe**: The complete declarative description of one creature:
  catalog metadata, parameters, skeleton, surfaces, materials, clips, sockets,
  volumes, and phases.
- **Library Entry**: The catalog view of a recipe — name, category, description,
  tags, parameter list, tested-with version.
- **Skeleton / Bone**: The articulation hierarchy; each bone has a name, parent,
  rest transform, and a position in an ordered chain. The skeleton is the
  authoring entry point.
- **Surface**: A generated skinned body region bound to bones at birth (limb tube,
  torso shell, rigid part), carrying texture coordinates and a source bone per
  vertex.
- **Skin Binding**: Per-vertex influence set with normalized weights, recorded
  during construction and fixed thereafter.
- **Clip**: One named animation with duration, loop flag, source generator, and
  baked joint motion. The names `idle`, `locomotion`, `attack`, `hurt`, and
  `death` are reserved and required on every creature.
- **Clip Generator**: A named, parameterized recipe-level function that
  synthesizes a clip (breathing, gait, hover, recoil, telegraphed attack, death
  collapse).
- **Event**: A gameplay cue within a clip, identified by name and time in
  seconds; authoritative for impact, fire, footstep, and death timing.
- **Socket**: A named attachment point on a bone or node with an offset, used for
  muzzles, eyes, cores, and hands.
- **Volume**: A named hit, weak-point, or collision proxy with a role and bounds.
- **Phase**: A named boss-phase threshold.
- **Material Reference**: A pointer to a texture recipe by name with optional
  parameter overrides, plus its resolved provenance and the rendered texture
  images embedded in the package.
- **Manifest**: The sidecar gameplay contract describing clips, events, sockets,
  volumes, phases, bounds, scale, and provenance. Its schema version is
  major.minor, with minor steps additive and major steps breaking.
- **Generation Report**: The machine-readable outcome of one generation: paths,
  checksums, inventory, warnings, provenance.
- **Validation Finding**: One gate result with code, severity, location,
  expected value, observed value, and suggested remedy.
- **Showroom Reference Set**: The approved turntable frames and structural
  summaries used as the visual regression baseline, compared under fixed camera
  and lighting settings with a documented perceptual tolerance.

### Out of Scope (v1)

- Any runtime monster or animation library for any engine, and any engine
  adapter beyond a documented manifest-reader example.
- Metaball or signed-distance surfaces, automatic skinning, cloth, and soft-body
  simulation.
- Runtime procedural locomotion, inverse kinematics, foot planting, and physics
  ragdolls.
- Blender pipelines and authored or binary source assets.
- World, level, behaviour-tree, and combat simulation logic.
- Packaging the generated asset into a specific consumer build (for example
  inlining it into a single-file game page).
- A curated library of prebuilt binary creature assets.
- Reference-only packages that defer texture rendering to the consumer; this is
  a possible later mode, not a v1 output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of shipped library creatures generate successfully on a clean
  machine with no network access and no manual setup steps.
- **SC-002**: Repeating generation of any library creature 100 times, including
  in at least two distinct clean environments and working directories, produces
  byte-identical asset and manifest pairs on 100% of runs.
- **SC-003**: An agent given only command help and machine-readable output
  corrects any recipe from a seeded defect corpus within three attempts, on 100%
  of defects, without reading generator source.
- **SC-004**: The validation gate detects 100% of the curated defect corpus, with
  a distinct, actionable finding per defect class, and reports zero findings on
  the unchanged library.
- **SC-005**: A developer who receives only the manifest determines which clip is
  the attack, when it lands, and where the muzzle is within five minutes.
- **SC-006**: Generating one library creature, including validation, completes in
  under ten seconds on a developer laptop; catalog and parameter inspection
  complete in under two seconds.
- **SC-007**: A new author produces a validated, importable creature from a blank
  recipe in under 30 minutes using only the shipped documentation.
- **SC-008**: The visual regression check, under its documented perceptual
  tolerance, detects 100% of injected silhouette or deformation changes in a
  curated set while reporting zero false positives on the unchanged library.
- **SC-009**: Every shipped creature imports with zero errors into at least two
  independent standard-format 3D consumers, renders with skinning intact, and
  plays at least one clip.
- **SC-010**: Consumers built against an earlier minor manifest schema continue
  to read every required field after a newer tool adds fields, on 100% of tested
  consumer fixtures; consumers presented a different major schema version reject
  it with an explicit error on 100% of fixtures.

## Assumptions

- The working name `beastforge` is retained for now; a later rename changes no
  requirement in this specification.
- Concrete language, runtime, and geometry-library choices are planning
  decisions, not product requirements; the accepted architecture decision that
  the asset is a standard 3D format plus a sidecar manifest is treated as fixed
  input.
- One generation invocation produces one creature; batch work is repeated
  invocations.
- The manifest embeds texture recipe names with their resolved parameters and a
  checksum of the rendered texture set, and the rendered images themselves are
  embedded in the package, so a consumer can verify provenance and render
  offline without the texture generator.
- Units are metres with Y-up and −Z forward; the manifest carries a suggested
  scale hint rather than leaving orientation to be guessed.
- Hit volumes and the attack impact event are authored in the recipe and emitted
  by the generator; there is no auto-derived fallback, so a consumer never has to
  guess and a recipe cannot silently ship without its combat hooks.
- The regression baseline combines turntable images and structural summaries.
  Image comparison uses fixed camera and lighting settings plus a documented
  perceptual tolerance; the exact comparison tooling is a planning decision.
- Packaging for the first single-file consumer is a separate follow-up feature,
  not part of this scope.
- Texture recipes are consumed by declared name; whether that is a library call
  or a generation-time subprocess is a planning decision.
- Consumers are assumed to support a standard 3D scene format with skinning and
  at least four bone influences per vertex, which the construction-bound skinning
  rule stays comfortably inside.
- The reference library contains at least one boss, one quadruped, and one swarm
  unit; recipes for them are part of this feature.
