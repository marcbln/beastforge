# Feature Specification: Closed Part Library

**Feature Branch**: `003-closed-part-library`

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: "Build a reusable library of beast parts (legs, arms, torsos, heads, tails, and hard-surface parts) whose geometry is always closed, never hollow or visibly open. Do not solve this by disabling backface culling; fix the incomplete geometry itself. Parts must support control contracts for articulated movement and parameters for automatic movement such as breathing or constant rotation. The library must remain anatomy-neutral so it can later support robot mechwarriors and flying spaceships that have no limbs or torso."

## Clarifications

### Session 2026-11-15

- Q: When a part is checked for being closed, which set of geometry checks decides pass or fail? → A: Watertight plus manifold: every edge shared by exactly two faces, consistent outward normals, and no degenerate or zero-area faces; self-intersection and duplicate faces are not checked.
- Q: Must this release ship mechanical and vehicle part presets, or only organic presets with closure and control contracts? → A: All three families ship now, each with a minimal preset set sufficient to build the mech and the limbless craft.
- Q: When automatic part motion is baked into the asset, where should it appear? → A: Baked into every existing clip, plus one synthesized baseline clip when the asset has no authored clips.
- Q: Which movement modes and units must a control channel support? → A: Rotation and translation only; rotation in degrees, translation in metres, with units stored as explicit strings.
- Q: How should an assembly reference a preset so regeneration stays deterministic when that preset later changes? → A: By preset name plus pinned preset version, with partial per-parameter overrides; changing a preset requires an explicit version bump.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Closed Creature Parts (Priority: P1)

A creator opens any creature in the library viewer and orbits around it. Every body part reads as a solid volume: no missing polygons, no visible interior, and no surfaces that disappear depending on the viewing angle.

**Why this priority**: This is the reported defect. It blocks trust in every generated asset and must be fixed before adding more authoring capability. The viewer must keep normal backface culling; the geometry itself must be complete.

**Independent Test**: Generate every creature currently in the library, inspect each part for open boundaries, and orbit each creature in the viewer from standard angles. Every part must be closed and no interior may be visible.

**Acceptance Scenarios**:

1. **Given** a generated creature with swept body and limb surfaces, **When** the asset is inspected for open edges, **Then** every part has zero boundary edges, consistent outward normals, and no degenerate faces, forming a closed manifold volume.
2. **Given** the same creature in the viewer with backface culling enabled, **When** the user orbits fully around it, **Then** no polygon disappears to reveal the inside of a part.
3. **Given** two adjacent parts that meet at a joint, **When** they overlap, **Then** the overlap is accepted and each part remains individually closed.

---

### User Story 2 - Reusable, Anatomy-Neutral Part Library (Priority: P2)

A creator builds a new asset from reusable part presets instead of hand-authoring every surface. The same library supports an organic quadruped, an articulated mech with armor and actuators, and a flying spaceship with no torso or limbs at all.

**Why this priority**: Reuse prevents the hollow defect from returning part by part and opens the system to non-creature assets. It is independently valuable even before control contracts or ambient motion exist.

**Independent Test**: Author one organic creature, one articulated mech, and one limbless flying craft using only library parts and presets. All three must validate, generate, and render without adding new geometry code or open surfaces.

**Acceptance Scenarios**:

1. **Given** the part library, **When** a creator assembles a creature from leg, torso, head, and tail presets, **Then** the asset uses only closed parts and validates successfully.
2. **Given** the same library, **When** a creator assembles a spaceship from hull, wing, panel, and engine presets with no torso or limb, **Then** the asset validates and renders correctly.
3. **Given** an articulated mech assembled from rigid and jointed presets, **When** the asset is generated, **Then** each part follows its assigned joint and remains closed.
4. **Given** a part preset used in multiple assemblies, **When** one assembly overrides its size or material, **Then** other assemblies are unaffected and determinism is preserved.

---

### User Story 3 - Control Contracts for Articulated Parts (Priority: P3)

A creator or downstream consumer can discover how each part is meant to move. A leg exposes named controls such as swing and lift; a turret exposes yaw; an engine gimbal exposes pitch. Each control names its joint, axis, movement mode, allowed range, default, and units.

**Why this priority**: Stable controls let clips, gameplay, and future mechanical assemblies drive parts without guessing joint names. Contracts become part of the published asset API.

**Independent Test**: Publish metadata for an asset with articulated parts, read the control contracts without inspecting the recipe, and verify every control maps to a real joint with a valid axis and range.

**Acceptance Scenarios**:

1. **Given** a part with articulated joints, **When** the asset is published, **Then** its metadata exposes named controls with joint, axis, mode, range, default, and units.
2. **Given** four symmetric legs that each declare a swing control, **When** controls are addressed, **Then** each is uniquely addressable through its part name without collisions.
3. **Given** a control that names a missing joint or an invalid axis, **When** the asset is validated, **Then** validation fails with a clear finding.
4. **Given** a limbless craft, **When** it publishes controls for a rotor or gimbal, **Then** those controls are valid even though the asset has no limbs or torso.

---

### User Story 4 - Automatic Part Motion (Priority: P4)

A creator declares automatic movement once on a part: breathing for a torso, constant rotation for a rotor, bobbing for a hovering craft. The generated asset moves without the creator hand-authoring a clip for that part, and the motion is deterministic.

**Why this priority**: It makes mechanical and ambient motion reusable and consistent. It builds on the part library and control contracts but is not required to fix the hollow geometry.

**Independent Test**: Build an asset whose only motion source is a part's automatic behaviour. Generate it twice and confirm the asset animates on its own and is byte-identical across runs.

**Acceptance Scenarios**:

1. **Given** a torso part with a breathing behaviour, **When** the asset is generated without any authored clip, **Then** a deterministic baseline clip is synthesized and the torso breathes in it.
2. **Given** a rotor part with an unbounded constant rotation, **When** the asset plays, **Then** the rotor keeps rotating for the full clip duration.
3. **Given** a part with an automatic behaviour and an explicit clip that animates the same joint, **When** the asset is generated, **Then** the explicit clip takes precedence for that joint.
4. **Given** identical recipes, **When** the asset is generated twice, **Then** the animation output is byte-identical.

---

### Edge Cases

- A part intentionally needs an opening (mouth cavity, exhaust bell, wound). It must be modelled as a closed solid with an inner wall and rim; no general open-surface escape hatch is provided in this release.
- A part has only one joint or no articulated chain, such as a hull panel or engine bell. It must still bind to a valid anchor and remain closed.
- Caps or closed ends collapse to zero area because of extreme taper, noise, or scaling. Validation must reject degenerate closed geometry rather than emitting invisible or non-manifold faces.
- Two parts share a joint, overlap deeply, or occupy the same space. Overlap is allowed, but duplicate part names and duplicate control names are rejected.
- A control declares an unbounded rotation (rotor) versus a clamped range (servo). Both must be represented and validated.
- A control declares translation instead of rotation (piston, sliding panel).
- Symmetric mirrored parts expose the same control names on different part instances. Addresses must remain unique.
- An asset has no torso, no limbs, no declared clips, or no articulated hierarchy.
- An explicit clip animates a joint that also has automatic motion.
- Existing recipes and published assets are regenerated. Gameplay facts must remain stable even though closed geometry changes asset bytes.
- A consumer reads metadata produced by a newer minor version that includes control contracts.
- Backface culling must remain enabled in every viewer and preview path; two-sided rendering is not an acceptable workaround.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every generated part MUST be a closed volume that is watertight and manifold: every edge is shared by exactly two faces, face normals are consistently outward, and no degenerate or zero-area faces are present. Self-intersection and duplicate-face detection are NOT required.
- **FR-002**: Adjacent parts MAY overlap at joints; the system MUST NOT require the assembled asset to be one watertight manifold.
- **FR-003**: All viewer and preview paths MUST keep backface culling enabled and MUST NOT rely on two-sided rendering to hide incomplete geometry.
- **FR-004**: The system MUST provide a reusable library of parametric part presets covering organic, mechanical, and vehicle assemblies, shipping a minimal preset set for each of the three families in this release.
- **FR-005**: The core part library MUST be anatomy-neutral; it MUST NOT require a torso, limb, or any specific creature structure.
- **FR-006**: Creators MUST be able to assemble an asset from presets and override preset parameters without changing the preset itself. An assembly MUST reference each preset by name and pinned preset version, and overrides MUST merge partially per parameter.
- **FR-007**: Every part instance MUST have a creature-wide unique name.
- **FR-008**: A part MAY declare one or more named control channels. Each channel MUST identify its joint, axis, movement mode (rotation or translation), allowed range or unbounded mode, default, and units (degrees for rotation, metres for translation, stored as explicit strings).
- **FR-009**: Control names MUST be unique within a part, and control addresses MUST be unique across the asset by combining part and control names.
- **FR-010**: Published asset metadata MUST expose every part's control contracts as a public, discoverable interface.
- **FR-011**: Control contracts MUST be additive and version-compatible so consumers that do not understand them can still read the rest of the asset metadata.
- **FR-012**: Validation MUST reject controls that reference missing joints, invalid axes, invalid ranges, unsupported movement modes, unit/mode mismatches, or duplicate addresses.
- **FR-013**: A part MAY declare automatic movement behaviours such as breathing, bobbing, swaying, or constant rotation, including the joint, axis, amplitude, period or rate, and phase.
- **FR-014**: Automatic movement MUST be deterministic and reproducible from the recipe.
- **FR-015**: Automatic movement MUST be baked into every existing clip as a baseline, and when an asset declares automatic behaviours but has no authored clips, the system MUST synthesize one baseline clip so the asset still animates; the synthesized clip MUST be deterministic and discoverable in the published metadata.
- **FR-016**: When an explicit clip animates the same joint as an automatic behaviour, the explicit clip MUST take precedence for that joint.
- **FR-017**: The viewer MUST display each part's control contracts alongside the existing manifest and animation views.
- **FR-018**: The system MUST validate, generate, render, and animate assets that have no torso and no limbs.
- **FR-019**: Regenerating the existing library MUST preserve gameplay facts: joint hierarchy, clips, events, sockets, volumes, phases, materials, units, and axes.
- **FR-020**: Existing recipes MUST remain authorable while presets are introduced incrementally; migrating a recipe to presets MUST NOT require changing its gameplay facts.
- **FR-021**: Deterministic generation MUST be preserved: identical recipes and tool versions MUST produce byte-identical assets.
- **FR-022**: The system MUST report clear validation findings for open parts, degenerate caps, missing anchors, duplicate names, and invalid controls.

### Key Entities

- **Part Preset**: A reusable parametric definition of a closed part, with defaults, allowed parameters, optional controls, and optional automatic behaviours.
- **Part Instance**: A preset bound to concrete joints and overrides inside one assembly, pinned to a specific preset version, with a unique name.
- **Control Channel**: A named, addressable articulation input with joint, axis, movement mode (rotation or translation), range or unbounded mode, default, and units (degrees or metres).
- **Automatic Behaviour**: A declarative ambient motion assigned to a part, such as breathing, bob, sway, or constant rotation.
- **Part Family**: A classification such as organic, mechanical, or vehicle. It guides preset discovery but MUST NOT constrain assembly structure.
- **Assembly**: The complete set of parts and joints that forms a creature, mech, or craft. It may contain no torso or limbs.
- **Asset Contract**: The published metadata that describes joints, clips, events, parts, and control channels for consumers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of generated parts in the shipped library pass the watertight-and-manifold closure check (two faces per edge, outward normals, no degenerate faces).
- **SC-002**: Across all shipped creatures, orbiting the viewer through a full rotation reveals zero visible part interiors with backface culling enabled.
- **SC-003**: 100% of existing gameplay facts remain unchanged for the five shipped creatures after regeneration.
- **SC-004**: An articulated mech and a limbless flying craft can each be authored entirely from the minimal preset set shipped in this release and pass validation, generation, and viewer rendering.
- **SC-005**: 100% of articulated parts expose discoverable control contracts, and every invalid control reference is rejected before asset generation.
- **SC-006**: An asset whose only motion source is automatic part behaviour animates without a hand-authored clip.
- **SC-007**: Two consecutive generations of the same recipe produce byte-identical assets and animation data.
- **SC-008**: No viewer or preview path enables two-sided rendering as a workaround for open geometry.
- **SC-009**: Adding a new creature, mech, or craft from existing presets requires zero changes to geometry-generation code.
- **SC-010**: Replacing a hand-authored part with an equivalent preset preserves the part's closedness and control addresses.

## Assumptions

- Closed parts may overlap at joints; no boolean union, CSG, or whole-body stitching is in scope.
- Closure is unconditional. There is no general `open surface` or `disable culling` option in this release; intentional openings are modelled as closed solids.
- The first release adds closed geometry, the part/control metadata contract, and a minimal preset set for each of the three part families (organic, mechanical, vehicle); preset depth is expanded incrementally in later releases.
- Control contracts are published in the asset metadata under a compatible minor version. Automatic-movement descriptors remain authoring-side and are baked into animation output rather than exposed as a runtime composition API.
- Automatic movement acts as a baseline baked into every clip; explicit clip motion wins for the same joint. A single synthesized baseline clip is added only when the asset has no authored clips.
- The viewer remains read-only. It displays control contracts but does not provide interactive rig controls in this release.
- Existing recipes remain valid during migration. Presets expand to the same closed geometry contract and are adopted gradually; each assembly pins the preset versions it was authored against, so a preset change only reaches an assembly after an explicit version bump.
- Regeneration will change asset bytes and content hashes because closed caps are added; golden assets are regenerated and approved as part of the work.
- Determinism, offline operation, and the existing asset delivery model remain unchanged.
- Part families are descriptive only. No validation rule may require a specific family structure, torso, limb, or biped/quadruped layout.
