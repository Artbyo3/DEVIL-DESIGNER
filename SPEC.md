# Devil Designer: product specification

This records the requested target for future development. It is not a claim that
all features below are complete or production-ready. Author identity: Artbyo3.

## Product direction

Create clothing for VRChat and other game characters through a dedicated flat
pattern editor, avatar placement, sewing, live XPBD simulation, and editable mesh
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
- Snapping, on by default and reversed by Ctrl: drawing points, the rectangle and
  ellipse corners, knife points, moves and the transform pivot snap to the points,
  midpoints, edges and crossings of every piece within 10 pixels, with a marker that
  names the target. A move snaps the moving point nearest the cursor, and geometry
  that is itself moving is never a target. Otherwise positions snap to the 1 cm grid.
  Pin, Tack and dart apex clicks use the same snapping, and a snap that would land
  outside the fabric (for example on a hole outline) falls back to the grid point or
  the exact click. Dart base clicks and the double-click edge split take a snap only
  when it lies on the clicked edge away from its ends.
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
can be linked explicitly. Linking refuses invalidation of existing sewing, and
turning a link on or off never creates, copies, or removes seams. Sewing on a
linked twin is linked as well: a seam created on enabled twins gets the mirrored
seam on the partners, and reversing, removing, switching on or off, changing
shrink or shrink side, or moving a seam end applies to that mirrored seam in the
same undo step. Seams on unlinked pieces are unchanged. Point topology edits retain the existing
sewing remapping and repair contract. Deletion, paired/independent duplication,
explicit Mirror with seam, document/library persistence, refits and history must
preserve valid pair membership. Designs without pair records remain unchanged.

### Internal lines, cuts, and darts

- Internal lines and closed internal shapes, distinct from the outer boundary.
- Sew to internal geometry or cut along it, including princess seams and slits.
- Trace existing geometry into a new pattern.
- Edit internal lines in place with the Internal tool: drag a line point to move it,
  double-click a line to add a point, Delete removes the selected point, and a plain
  click on a line point still starts a new line there. Right-click anywhere along a line
  opens its cut, fold, offset and split actions.
- A dart tool that defines its legs and automatically creates its closing sewing.
- Support self-sewing within a piece where needed for darts; the current ban on
  all same-pattern sewing cannot remain a universal rule.
- Cuts must create the correct pieces/openings while retaining design intent,
  pattern identities, UV relationships, and sewing references where possible.

### Sewing

- Segment sewing and free sewing.
- The same segment and four-click free sewing work on visible arranged live
  panels in the revealed 3D viewport, including same-piece pairs and M:N chains.
  Picking uses derived boundary samples with cached visibility, never a second
  sewing model or stored design format. Multiple visible edges within tolerance
  refuse the click with an explanation; shared corners never guess a neighbor.
- Shared seam preview, hover and selection identities connect the 2D canvas and
  3D viewport. Reverse and delete use the existing document transactions and
  persistent history. In a 3D sewing session, seam-only panel resampling retains the exact existing
  transform channels for wrapped, flat-arranged and click-placed pieces.
  Kept meshes and sewing during playback are excluded. Cached display batches
  resolve only after source/geometry changes, not on orbit redraws.
- Partial ranges along segments/curves, plus M:N pairing across edge chains.
- Reverse, remove, and edit existing pairings.
- Seams draw by attention so patterns read first. An idle seam is a thin edge tint
  and a quiet numbered badge, with nothing crossing the canvas. Seams of a selected
  piece show one link line. A selected seam, a hovered badge, or a hovered sewn edge
  shows full detail. A mismatched seam keeps its warning color on its edges at all
  times. These levels are display only.
- Proportional resampling by arc length, independent of how many control points
  or mesh vertices are present on either side.
- Live lengths for both sides, difference in cm, and mismatch percentage.
- Length mismatch is a warning, NEVER a hard block: intentional gathers and ease
  must remain sewable. Invalid or missing geometry may still require repair.
- Direction and correspondence must be visible before simulation.
- The pre-simulation preview consumes the compiler's shared exact fraction-to-vertex
  resolver and native-verified zero JOIN targets, drawing every resolved pair
  on the 2D canvas and arranged 3D pieces. Preserve existing strokes and picking.
  Show mismatch/pass/warn, paired direction arrows and in-place coverage, reversal,
  local uneven-ease-risk and observed-edit/drift flags. Stale panels must show an
  explicit unavailable state rather than approximate links. Inspect active piece
  states without modifying the live scene, solver settings or sewing format.

### Placement and constraints

- Every committed closed piece has a live flat 3D panel mirroring its 2D layout;
  outline edits and moves update it, and deletion removes it. The body silhouette
  is a drawing reference only, not a placement projection.
- Avatar-owned body-relative bounding volumes and editable arrangement points
  provide optional click-to-wrap or tangent-flat placement. Points toggle with H.
- Points are flat discs lying on the body, so they read round facing the camera and
  narrow to slivers at the body's edge. They scale with zoom between fixed limits.
  The avatar and other meshes hide them; pieces, simulation and final meshes made
  by the add-on do not. Hidden points cannot be hovered or clicked.
- A point with a left/right mirror partner uses the mirrored color. A dragged point
  loses it, as does its partner, until the two mirror each other again. A point
  holding a piece uses the attached color.
- Placing a linked piece on a mirrored point also places its enabled twin on the
  mirror point, in one undo step. Centerline points leave the twin where it is.
- Setup format 2 stores independent fitted ellipse radii and section bases, derived
  only from evaluated mesh slices at the existing height-fraction bands. Wrapped
  rows interpolate centers and radii across neighboring volumes in the same body
  region; radial clearance and arc-length spiral spacing remain intact. No rig or
  surface projection is used. Format-1 setups remain circular until regeneration
  or explicit per-piece re-arrangement; mixed setups retain a format-1 snapshot.
  Arrangement records accept versions 1 and 2; the document format remains 4.
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
- Per-pattern fabric presets. Stretch, bending and mass density are per-vertex and
  per-edge attributes on the one sewn simulation mesh, so each piece keeps its own.

### Simulation, finalize, and garment library

- Simulate with the Geometry Nodes XPBD system in `xpbd.py` and `xpbd_nodes.py`.
  It is the only simulation engine. The zone runs in realtime mode at a fixed
  30 fps clock, so playback runs until stopped and accepts live input. The
  artist's frame rate and timeline are restored on Keep and Reset, and when the
  editor is closed. Simulate and Keep set the clock again after reopening.
- Fabrics differ through bending stiffness. Linen, Denim and Leather add links across
  two cloth edges, because the solver's own bending saturates.
- A piece with a partner on the opposite side of the same volume stops wrapping at
  the body side, and extra width stands out as a flap so the panels cannot cross.
- Grab cloth while it simulates. Pull follows the hand in the view plane, Push
  presses along the surface normal, and radius is set by Ctrl+wheel or the strip. The wheel alone zooms the view.
  Releasing softens the hold over about half a second instead of dropping the cloth: the held cloth
  stays tied to its own last position by a link that weakens every frame, so it returns in small even steps.
- Cloth pins hold the cloth where the artist put it while the simulation keeps running. W while holding
  pins the cloth inside the ring, and Pin mode pins on release. Dragging a pinned spot moves it, Ctrl+click
  frees the pins under the ring, and Remove pins in the Grab flyout frees all of them. Cloth pins are written
  straight into the running solver, so no new drape starts. They are kept through Re-drape and Keep, and
  Reset drape clears them. They never override pattern pins, tacks or frozen pieces. Pinned cloth shows as
  dots over the 3D view in every tool, and Ctrl+Z in Grab undoes the last pin change.
- Fold and Sweep in the Grab flyout are live brushes for deliberate folds. Dragging along the playing drape
  moves the cloth inside the ring with a smooth falloff: Fold draws it toward the stroke line so it gathers
  into a fold, and Sweep carries it along with the stroke. The stroke is a short trailing segment behind the
  cursor, two radii long for Fold and one for Sweep. The brush is three modifier inputs that feed the running
  solver's pin constraint, the same path as Grab, so no drape restarts and nothing is rebuilt, and the cursor is kept on the cloth by walking mesh
  neighbours from the last point instead of searching the whole mesh. Strength is set in the strip or with
  Ctrl+Shift+wheel, radius as in Grab. W pins the cloth under the brush and the stroke continues around the
  pin. Pattern pins, tacks, frozen pieces and cloth pins are never moved by the brush. Releasing switches the
  brush off, and cloth that is free to relax settles back, so a fold that should stay is pinned with W during the stroke. Pinch and Steam remain the
  pattern strokes that need a re-drape.
- Pressing the cloth holds the grabbed cloth point itself, so a still hand does not move it. The solver
  substeps change once when the Grab tool opens, not at each press and release.
- Keep runs a short high-substep refine, then checks the result against every
  collision body. Contacts within 12 mm are nudged clear and deeper ones refuse.
- Reset/rebuild without losing valid source relationships or arranged placements.
- Finalize to editable garment meshes with the pattern UVs and piece identifiers.
- Kept garments are collision layers for later simulations. A five-row scrollable
  Wear over list in the Simulate arrow defaults kept garments on, except a kept mesh
  that shares pieces with the current design, which defaults off so a garment never
  collides with its own re-drape. A manual choice always wins. Add missing
  Collision modifiers without changing existing ones. Filter only the current
  simulation: always retain the body and every pre-existing scene collider except
  unchecked kept garments. Preserve kept meshes on Reset and the original path
  when no kept garments exist.
- The Keep arrow and the Keep message show the garment's triangle count and, with the avatar
  counted, its VRChat PC and Quest rank on triangles alone. Thickness doubles the count as an
  estimate. Other VRChat rank stats are not checked.
- Number fields accept simple math with + - * / and brackets, as Blender's own fields do.
- Keep output defaults to triangles. The Keep arrow's opt-in Faces: Quads joins triangle
  pairs with Blender's Tris to Quads after seams are welded, matching UVs and materials, so
  welded seams and UVs survive. The result is mostly quads, not a clean quad grid. A
  seam-locked quad grid stays deferred (#54).
- Garment and View has a body Friction choice (Slippery, Normal, Grippy). It feeds the
  solver's body grip and the drape signature.
- A seam can be switched off from its right-click menu. It stays in the pattern and keeps
  its sampled points, but its sewing joins are dropped before the solver and its Shrink is
  ignored. Only the off state is serialized.
- Fabrics carry four optional values that default to no change: weft stretch and bias
  stiffness as ratios of the main (warp) stretch, and lengthwise and widthwise shrinkage of
  up to 30 percent. Pattern Y is the warp. Stretch edges are weighted by their direction in
  the flat pattern, so the defaults reproduce the previous rest lengths and compliances.
- Edge and internal edge menus split a segment into 3 or 4 equal parts, or into parts of
  about 2 or 5 cm, measured along the curve, in one undo step.
- Pinch and Steam paint along a drag, laying dabs spaced at 0.6 of the dab radius.
- A garment library that saves the editable design, not only a frozen final mesh.
- Load a design onto another avatar and refit it: preserve outlines, internal
  features, sewing, material choices, UV layout, and garment-relative arrangement.
- Separate portable design data from avatar bindings, absolute scene placement,
  and simulation caches. Remap or flag pins/tacks when the body changes.
- Do not bundle an avatar or other private scene assets in a library design by default.

### Per-piece simulation states

Document version 4 accepts optional per-pattern boolean simulation flags: frozen,
deactivated, strengthened. Default flags are omitted for unchanged normal documents.
State controls live in the piece right-click Simulation submenu; existing piece
labels name active states in 2D and revealed 3D, without additional panels.

Freeze holds the exact current evaluated pose inside the shared sewn cloth mesh.
Both endpoints of incident sewing pairs are pinned; live neighboring interiors
remain simulated. Frozen anchors do not animate held vertices. No separate frozen
collider is created. Pins are enforced exactly after each solver pass.
Deactivate filters patterns, incident seams, and anchors out of a run-only design
before invoking existing meshing functions; active sampling equals physical absence.
Strengthen divides only selected pieces' stretch and bending compliance by four,
without changing shared presets or mass density.

The normal compiler, protected mesh/placement functions, sewing formulas and Keep
mesh processing remain unchanged behind a scoped state-run dispatch. All-normal
simulation is regression-checked against the pre-dispatch compiler. Flag persistence
covers save/reopen, 100-edit history, duplication and actual library load. Explicit
linked editing propagates subsequent state toggles only while enabled. Outlines
and arrangement remain editable; library data does not include simulation caches.
README records scratch gate tolerances, measured values, and the diagnosed failed
panel-round-trip transfer that was replaced by exact in-mesh pose transfer.

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
7. Every string the editor draws passes through one lookup keyed by its English
   text. Each language is one JSON file in `devil_designer/locales`, named by
   Blender locale (`ja_JP.json`) or language (`ja.json`). The active language
   follows Blender's interface language when interface translation is on.
   English is the source and the per-string fallback, so a partial file works
   and a language without a file shows English. Japanese and Spanish ship first.

## Implementation coverage (0.5 development)

### Fit-map display contract

The dock adds F beside S, H and L. F toggles a display-only fit map on the visible
simulated garment, with a compact legend in the exposed 3D view. Home fits the
2D design. Each fabric-surface edge compares its evaluated length in metres with
the corresponding original flat-panel rest length; sewing bridges are excluded.
Per-vertex values are rest-length-weighted incident edge ratios, stored as colors
on a temporary, unlinked evaluated-mesh copy. White spans ratios 0.97–1.03;
blue saturates at 0.85 and red at 1.15. The overlay does not change source geometry,
simulation, kept meshes, UVs, materials or viewport shading settings. Turning it
off or closing the editor removes the display handler. It is an approximate
deformation guide, not pressure or stress, and folded loose cloth may remain
neutral. Mismatched source topology or changed patterns must not display stale data.

No seam rest lengths, solver settings or design fields are changed
by the fit-map feature.

### Opt-in seam Shrink contract

A seam right-click menu offers 0, 10, 20 and 30 percent Shrink. Zero is omitted
from serialized seams for legacy document and cache-signature equivalence.
Nonzero choices persist with the seam and participate in transactional undo/redo.
Both sampled sewn boundaries receive shortened rest lengths that fade over eight
rings of cloth; at shared vertices maximum Shrink wins. Sampling, flat mesh output,
UVs and sewing connections remain unchanged. One gain is calibrated so a free seam
shortens by the chosen percentage to within 3 points. A seam around a body can
shorten less, because the body limits it.

The requested feature families now have initial working implementations.
The README documents the UI and practical limits.

| Requirement | Implementation |
| --- | --- |
| Bezier paths, polygon/rectangle/ellipse, corner conversion | Version 4 source document, versions 1–3 migration, dedicated editor tools |
| Numeric cm editing and live lengths | Custom fields, exact segment scaling, integrated Bezier arc lengths |
| Point split/delete/merge, offsets, symmetry and Unfold | Transactional operations with undo, IDs and sewing repair feedback |
| Internal paths, holes, slits, princess cuts, trace and darts | Selectable paths, constrained meshing, separate slit lips and auto-closing dart sewing |
| Segment/free/partial/M:N sewing | Arc-length ranges/chains, four-click free sewing, reverse/remove and nonblocking mismatch warnings |
| Click placement, wrapping, pins/tacks | Mesh-fitted ellipse stacks and arrangement points, live layout panels, native constraints; legacy circle/ray/bend fallback |
| Density, UV layout, face sets and groups | Constrained triangulation with shared persistent UV transform and piece metadata |
| Per-pattern presets | Per-edge stretch and per-vertex bending and mass attributes |
| Simulation/finalize | GN XPBD, live grab, refine on Keep, true-body check, matched seam welds, UV/group retention |
| Garment library/refits | Portable editable designs, body-relative placement, optional height-based refit |
| Per-piece mesh density | Named overrides, independent interiors, seam-compatible component boundaries |
| Reference-image tracing | Persistent image placement/opacity and two-point measured scale calibration |
| Multi-piece arrangement | Stable avatar-owned volumes/points, relative G/R deltas, optional arrangement, legacy named layouts |
| Persistent undo | Validated document-matched undo/redo stacks saved with the blend file |
| Pose-stable tacks | Triangle weights on the body baked at Simulate, with topology checks |
| Crossing-cut recovery | Transactional preview, split-and-retry, and actionable unsupported-case refusal |

Offsets approximate Bezier offsets with sampled paths. Straight open crossing
lines support split-and-retry; complex curves and closed crossing shapes still
require manual repair. Slits expose their
path mapping; use a cut into separate pieces for independently selectable lips.
Tacks follow their bound skin triangle through deformation; topology changes
require reattachment. Measured image scale cannot correct distorted photographs.
Bounding-volume generation remains heuristic. Per-row ellipse interpolation follows
neighboring sampled sections, not the body surface; terminal rows retain the nearest
sample's cross-section. Unsamplable sections use body-extents ellipses. Intersections
remain possible on unusual bodies; inspect the starting fit. Regeneration resets avatar edits.
Legacy named layouts are non-anatomical placements, not automatic fitting. Cross-avatar
loading provides an editable starting fit,
not automatic tailoring to all body proportions. Built-in fabric presets (SILK, KNIT,
COTTON, LINEN, DENIM, LEATHER) are calibrated against KES-F / FAST data and cantilever
bending lengths; known simulation limits apply: calibration is exact near 0.02 m spacing
(Blender assigns mass per vertex and bending per edge without area/length normalization),
triangle-mesh shear is locked to 3/8 of structural (no shear springs on CDT triangles),
and multi-fabric garments share one area-weighted density. These limits are visible in the
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
