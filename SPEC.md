# Devil Designer: product specification

This records the requested target for future development. It is not a claim that
all features below are complete or production-ready. Author identity: Artbyo3.

## Product direction

Create clothing for VRChat and other game characters through a dedicated flat
pattern editor, avatar placement, sewing, Blender-native cloth, and editable mesh
output. Every garment control belongs in the custom UI. Keep the floating editor
movable/resizable, retain its body silhouette reference, and do not add an N-panel.

The editable 2D design is the source of truth. Generated simulation meshes and
finished mesh copies are downstream products. Changing density or rebuilding must
not replace the source patterns with their triangulated approximation.

## Required capabilities

### 2D drafting with Bezier curves

- Dedicated flat pattern view with polygon, rectangle, and ellipse tools.
- Patterns represented by editable Bezier paths, including straight segments.
- Convert points between corners and curve points, with editable handles.
- Numeric drafting and editing in centimetres; retain metre-based internal units.
- Display live segment lengths while drawing and editing, including curve arc
  lengths, so edges can be compared before sewing.
- Keep measurement, displayed curves, sewing, and meshing consistent by sharing
  the same geometric evaluation and length calculation.

### Pattern operations

- Add, delete, split, and merge points.
- Set a segment length exactly, with clear control over the fixed endpoint and
  affected geometry instead of silently moving unrelated parts of the pattern.
- Offset an outline, including validation of concave corners and self-intersections.
- Symmetry and Unfold: mirror across a selected edge, either joined without a
  seam or as mirrored pieces with a sewing connection.
- Preserve valid sewing/internal-line references through operations. If an edit
  changes their topology, remap references where possible and explain any repairs
  required. Undo restores both geometry and its relationships.

### Linked editing

Linked editing uses explicit pair records in the design document, with an On/Off
state, a mirrored pattern-space transform, and stable point/path correspondence.
Clone as linked twin is one transaction and places a nonoverlapping mirrored
island. Clone as Back uses the same volume's back point only when explicitly
requested from a front-arranged piece. No drawing, placement, or simulation step
automatically clones or sews a piece.

Outline and internal-path edits mirror bidirectionally within the same undo
transaction. Whole-piece layout movement and 3D arrangement remain independent.
Remove Linked Editing changes only the enabled state; Apply Linked Editing
replaces the other outline from the active member. Two selected unpaired pieces
can be linked explicitly. Linking refuses invalidation of existing sewing; it
never creates, copies, or removes seams. Point topology edits retain the existing
sewing remapping and repair contract. Deletion, paired/independent duplication,
explicit Mirror with seam, document/library persistence, refits and history must
preserve valid pair membership. Designs without pair records remain unchanged.

### Internal lines, cuts, and darts

- Internal lines and closed internal shapes, distinct from the outer boundary.
- Sew to internal geometry or cut along it, including princess seams and slits.
- Trace existing geometry into a new pattern.
- A dart tool that defines its legs and automatically creates its closing sewing.
- Support self-sewing within a piece where needed for darts; the current ban on
  all same-pattern sewing cannot remain a universal rule.
- Cuts must create the correct pieces/openings while retaining design intent,
  pattern identities, UV relationships, and sewing references where possible.

### Sewing

- Segment sewing and free sewing.
- Partial ranges along segments/curves, plus M:N pairing across edge chains.
- Reverse, remove, and edit existing pairings.
- Proportional resampling by arc length, independent of how many control points
  or mesh vertices are present on either side.
- Live lengths for both sides, difference in cm, and mismatch percentage.
- Length mismatch is a warning, NEVER a hard block: intentional gathers and ease
  must remain sewable. Invalid or missing geometry may still require repair.
- Direction and correspondence must be visible before simulation.

### Placement and constraints

- Every committed closed piece has a live flat 3D panel mirroring its 2D layout;
  outline edits and moves update it, and deletion removes it. The body silhouette
  is a drawing reference only, not a placement projection.
- Avatar-owned body-relative bounding volumes and editable arrangement points
  provide optional click-to-wrap or tangent-flat placement. Points toggle with H.
- Store stable volume/point IDs and relative G/R deltas in document version 4;
  avatar setup is scene data, never bundled with a garment. Cuts retain their
  parent's pattern-space origin so both halves preserve their current placement.
- Simulate from current panels in any state. Unarranged intersections warn but
  do not gate simulation. Reset to layout clears a record; Reset drape retains it.
- Library loads resolve the same IDs on the new body's own volumes. Missing IDs
  fall back visibly to layout. Versions 1–3 retain legacy placement and named layouts.
- Pins and tacks, with clear attachment targets and release/edit controls.
- Keep placement and bend state separate from the flat source pattern. Arranging
  a piece must not rewrite its 2D outline or its UV layout.

### Mesh generation and Substance workflow

- Even triangulation at a user-selected density, with holes and internal cuts.
- Generate UVs from the actual 2D pattern layout. This is a core requirement for
  Substance, not an optional final export step.
- Preserve relative scale, orientation, and layout of pattern islands. Do not
  silently normalize pieces independently or automatically repack their UVs.
- Keep the UV correspondence intact through simulation, seam welding, and finalize.
  Changing density changes sampling, not the source UV mapping.
- Face sets/piece face identifiers and vertex groups for every pattern piece.
- Per-pattern cloth presets. Determine which settings can be represented using
  native cloth groups/attributes and clearly handle settings that remain global
  on one sewn cloth object; do not silently claim full per-piece material control.

### Simulation, finalize, and garment library

- Prepare and simulate with Blender's native cloth.
- Reset/rebuild without losing valid source relationships or arranged placements.
- Finalize to editable garment meshes with the pattern UVs and piece identifiers.
- A garment library that saves the editable design, not only a frozen final mesh.
- Load a design onto another avatar and refit it: preserve outlines, internal
  features, sewing, material choices, UV layout, and garment-relative arrangement.
- Separate portable design data from avatar bindings, absolute scene placement,
  and simulation caches. Remap or flag pins/tacks when the body changes.
- Do not bundle an avatar or other private scene assets in a library design by default.

## Architecture requirements

1. Extend the versioned design document for Bezier anchors/handles, stable segment
   IDs, multiple boundary loops, internal paths, symmetry, and feature identities.
   Migrate existing straight-edge documents without losing patterns or sewing.
2. Represent future sewing as references to ordered curve ranges and edge chains,
   not temporary simulation vertex indices. Use arc-length correspondence for
   partial and M:N pairs. Splitting a source segment must remap these ranges.
3. Share curve evaluation between rendering, hit testing, lengths, seam sampling,
   outline operations, and meshing. Approximation tolerances must be explicit and
   independent of viewport zoom.
4. Keep source-to-generated mappings for vertices and faces, piece IDs, seam
   samples, UVs, and anchors. Generated topology may be replaced during rebuild.
5. Store UV layout transforms and portable garment definitions independently of
   the current avatar and live simulation object.
6. Retain transactional edits, undo/redo, save/reopen support, and the complete
   in-editor workflow as the data model expands.

## Implementation coverage (0.5 development)

The requested feature families now have initial working implementations.
The README documents the UI and practical limits.

| Requirement | Implementation |
| --- | --- |
| Bezier paths, polygon/rectangle/ellipse, corner conversion | Version 4 source document, versions 1–3 migration, dedicated editor tools |
| Numeric cm editing and live lengths | Custom fields, exact segment scaling, integrated Bezier arc lengths |
| Point split/delete/merge, offsets, symmetry and Unfold | Transactional operations with undo, IDs and sewing repair feedback |
| Internal paths, holes, slits, princess cuts, trace and darts | Selectable paths, constrained meshing, separate slit lips and auto-closing dart sewing |
| Segment/free/partial/M:N sewing | Arc-length ranges/chains, four-click free sewing, reverse/remove and nonblocking mismatch warnings |
| Click placement, wrapping, pins/tacks | Avatar arrangement points and cylinders, live layout panels, native constraints; legacy ray/bend fallback |
| Density, UV layout, face sets and groups | Constrained triangulation with shared persistent UV transform and piece metadata |
| Per-pattern presets | Native stiffness groups; mass density remains an explicit shared weighted value |
| Simulation/finalize | Native cloth, reset, evaluated output, matched seam welds, UV/group retention |
| Garment library/refits | Portable editable designs, body-relative placement, optional height-based refit |
| Per-piece mesh density | Named overrides, independent interiors, seam-compatible component boundaries |
| Reference-image tracing | Persistent image placement/opacity and two-point measured scale calibration |
| Multi-piece arrangement | Stable avatar-owned volumes/points, relative G/R deltas, optional arrangement, legacy named layouts |
| Persistent undo | Validated document-matched undo/redo stacks saved with the blend file |
| Pose-stable tacks | Triangle weights and native evaluated-vertex parenting, with topology checks |
| Crossing-cut recovery | Transactional preview, split-and-retry, and actionable unsupported-case refusal |

Offsets approximate Bezier offsets with sampled paths. Straight open crossing
lines support split-and-retry; complex curves and closed crossing shapes still
require manual repair. Slits expose their
path mapping; use a cut into separate pieces for independently selectable lips.
Tacks follow their bound skin triangle through deformation; topology changes
require reattachment. Measured image scale cannot correct distorted photographs.
Bounding-volume generation is heuristic and wrapping uses the radius at the point's
height, not a fitted surface along the entire panel. Tall pieces may intersect wider
neighboring body sections; inspect the starting fit. Regeneration resets avatar edits.
Legacy named layouts are non-anatomical placements, not automatic fitting. Cross-avatar
loading provides an editable starting fit,
not automatic tailoring to all body proportions. These limits are visible in the
usage documentation and do not imply Marvelous Designer feature/performance parity.

## Acceptance examples

- Draft a curved sleeve cap, read its arc length in cm, split it, and retain the
  original overall curve and meaningful sewing references.
- Sew a longer sleeve edge to a shorter opening; show the mismatch and allow the
  intentional gather through simulation.
- Pair one edge chain against several segments using partial ranges; reverse or
  delete the pair without rebuilding the entire design manually.
- Unfold a half-bodice into either one joined pattern or two mirrored sewn pieces.
- Create a dart with automatic closing sewing and a cut/slit with correct topology.
- Mesh a pattern with a hole at two different densities; preserve its silhouette,
  opening, piece identity, and the same source-space UV mapping.
- Finalize and texture in Substance using islands that correspond to the flat
  pattern layout, including the expected continuity after sewing/welding.
- Save the garment, load it onto a different avatar, adjust its fit, and simulate
  again while retaining source patterns, sewing, and UV layout.
