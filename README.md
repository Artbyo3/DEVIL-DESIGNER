# Devil Designer

A movable 2D clothing-pattern editor with Bezier drafting, internal construction,
sewing, avatar placement, native Blender cloth, and a reusable local garment library.

By **Artbyo3**. **0.5.0 development build**, tested in **Blender 5.2.3 LTS**.
Requires Blender 5.2+.

## Install and open

Run `python tools/build.py` to create the installable archive, then install
`build/devil_designer-0.5.0.zip` through **Edit > Preferences > Add-ons >
menu > Install from Disk**. Disable the previous version and restart Blender to
unload its old Python modules. Enable Devil Designer if necessary.

In a 3D Viewport use **Ctrl+Alt+D**, **F3 > Devil Designer**, or **View > Devil Designer**.
There is no N-panel. Drag the editor header to move it, its bottom-right corner to
resize it, and use **Expand / Restore** or Tab for the expanded layout. Bounds and
Settings visibility save per scene. Other Blender controls work outside the editor.

The custom Settings inspector has **Design, Avatar, Sew, Cloth, and Library** tabs.
Scroll inside it for additional controls. Click values to type, Enter to apply,
Escape to cancel, or use +/- buttons. Drafting dimensions are displayed in cm;
reference/output fields show their own units. The internal geometry unit is metres.

## Draft and edit

The source patterns are cubic Bezier paths, stored independently of generated mesh
topology. Polygon and rectangle segments begin straight; ellipse outlines use four
Bezier anchors. The custom editor owns the editable path data; these are not
separate Blender Curve objects.

| Tool/action | Control |
| --- | --- |
| Select / polygon / rectangle / ellipse | V / P / R / E |
| Internal line / sewing / pin / tack / dart | I / J / K / T / D |
| Finish polygon | Enter or click its first corner |
| Finish open internal line / closed internal shape | Enter / click its first point |
| Edit point or Bezier handle | Select, then drag the anchor or gold handle |
| Corner / curve point | C or Design > Corner / curve |
| Add a point by splitting the selected segment | Q or Design > Split segment |
| Select two adjacent points / merge | Shift-click points / M |
| Unfold across selected straight edge | U |
| Mirror across selected straight edge with sewing | Shift+U |
| Show live segment lengths | Lengths L / L |
| Move a whole pattern | Select and drag inside its fabric area |
| Duplicate / delete selected point, path or piece | Shift+D / X or Delete |
| Undo / redo | < / >, Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y |
| Grid snapping / temporary inversion | S / hold Ctrl |
| Constrain next polygon edge to an axis | Hold Shift |
| Pan / zoom / fit | Middle mouse / wheel / F or Home |
| Show body reference | Body H / H |
| Cancel current gesture/draft/placement | Escape |

Select a point or segment to edit it. Live lengths use numerical Bezier arc-length
integration and update as handles move. **Design > Point X/Y > Apply / add point**
sets a selected point or adds a numeric point to the active polygon/internal draft.
**Width/Height > Create rectangle/ellipse** creates precisely sized shapes at X/Y.
**Segment length > Apply exact length** fixes the start and adjusts the end/handles
of that segment; neighbouring geometry may change accordingly.

**Offset outline copy** keeps the original piece and creates an editable outline
at the entered distance. Curved offsets use a sampled approximation and can have
more points. Self-intersecting or collapsed results are rejected. **Unfold** joins
the mirrored halves along the selected straight edge. **Mirror with seam** creates
a separate reflected piece and a sewing pair; self-sewing darts are copied as well.

## Internal shapes, cuts, trace, and darts

Select the target piece before using I, or click inside it to select an owner.
Enable **Design > Draw internal shapes** to make polygon/rectangle/ellipse tools
create internal shapes in the selected pattern.

- Closed internal shapes can be traced into independent editable patterns.
- **Cut selected internal path** converts a closed shape into a hole.
- A boundary-to-boundary internal line/curve cuts a pattern into two pieces,
  including princess-seam-style construction. Existing valid boundary sewing is
  remapped; affected references that cannot be repaired are reported.
- A line with interior endpoints becomes a slit, with separate mesh lips.
- Internal paths and hole boundaries are selectable for sewing.
- The dart tool takes two positions on the same outer segment for its mouth,
  followed by an interior apex. It creates a V notch and its own same-piece closing
  seam. The common apex does not produce a zero-length sewing spring.

Holes must remain strictly inside the outline and cannot overlap. A cut crossing
another internal shape currently asks you to split that shape first. Slit sewing
uses the path's generated boundary mapping; choose a boundary-to-boundary cut into
separate pieces when both independently selectable cut sides are needed.

## Sewing

In Sew/J, click an edge and its partner for segment sewing. Select a sewn edge to
inspect it; B reverses direction and X removes the pair. The Sew tab's pair list
also has Flip/remove controls and lengths for both sides.

**Free sewing** uses four clicks: start A, end A, start B, end B. Each side can span
several segments of one connected path. The clicked positions become partial
arc-length ranges, not temporary mesh indices.

For explicit **M:N chains**, choose **Pick chain A**, click its edges in order, then
Enter to switch to B. Select B's edges and press Enter (or Sew selected chains).
Selected edges can be toggled off by clicking again. Pick connected edges in the
intended traversal order; endpoint direction is adjusted to the preceding edge.
The A/B start and end percentage fields trim the chosen chains proportionally.

Sampling uses arc length across each complete side, includes segment boundaries,
and inserts matching samples on the other side. Range correspondence survives
curve splitting and mesh-density changes. Disjoint ranges may share a source edge;
overlapping sewing ranges are rejected.

**Length mismatch is a warning, never a hard block.** Differences show in cm and
percent, with amber pairing feedback. Gathers and ease remain sewable. Invalid
geometry, missing references, or zero-length ranges still require correction.

## Avatar reference, placement, wrap, pins, and tacks

Choose the body in **Avatar > Avatar body**, or select its mesh in 3D and click
**Use selected body**. The actual evaluated mesh appears behind the pattern grid
at physical scale. It includes armature/shape-key deformation and object/scene
scale; limb gaps are preserved. Reference view, opacity, position, alignment,
framing, and refresh are all in the Avatar tab. It cannot be selected as a pattern.

Build 3D panels, then either move them with Blender G/R, use the two-piece
front/back Arrange helper, or choose **Click-place selected piece** and click the
body in the uncovered 3D viewport. Ray picking targets the chosen body only.

Set **Wrap radius** and click **Wrap / unwrap selected piece** to bend a piece
around its vertical local axis. Use zero to restore flat geometry. This is useful
for sleeves and waistbands; it does not scale the 2D outline or change its UVs.
Use a radius appropriate to the piece width to avoid wrapping over itself.

K adds a static pin on fabric. T picks a fabric point, then a target on the avatar
in 3D. Tacks use native Hook/pin groups and avatar-parented surface-following targets.
Select a pin/tack with K/T and use **Remove selected pin / tack** to remove it.
Pins/tacks are source-space anchors and are remapped when the mesh is rebuilt.
Tacks follow the body object and nearest deformed surface; they are not a rigid
barycentric attachment to one exact skin triangle. Check them after major pose changes.

## Generate, simulate, and finalize

Mesh spacing controls a staggered interior grid and constrained Delaunay
triangulation. Curved boundaries, holes, internal constraints, and slit edges are
included. Start around 2-3 cm and increase density only when needed. Each source
piece and compiled garment has piece face identifiers, sculpt face sets, and
per-piece vertex groups.

Choose a selected piece's preset in **Cloth > Selected fabric**: Silk, Knit, Cotton,
Linen, or Denim. Native structural, shear, and bending groups provide per-piece
stiffness. **Mass density is a shared, area-weighted native cloth value**; these
presets are practical starting values, not measured textile calibration.

**Build 3D** preserves existing panel transforms. **Arrange** places exactly two
pieces around a Z-up, -Y-facing body; adjust this starting layout before simulation.
Body clearance, quality, self collision, frame limit, and optional top-point pinning
are in Cloth. The chosen body gets Collision if needed; an existing collision
modifier is left unchanged.

Use **Simulate > Stop > Keep mesh**. Keep mesh copies the evaluated drape, removes
loose sewing springs, welds only paired vertices within tolerance, and retains UVs,
piece face identifiers, and group memberships. Optional thickness is an editable
Solidify modifier. If pairs remain open, the result reports them; simulate longer
or correct placement/direction before keeping another copy.

Reset removes the simulation/cache and restores arranged panels, preserving kept
garments. Reset after body geometry/collision changes before simulating again.
Simulation caches are not automatically baked to disk. A single piece can drape
without sewing; a selected body is still required for this workflow.

## UVs for Substance

UVs come directly from the flat 2D layout. The first build records one shared UV
origin and scale in the design document. Rebuilding at another density preserves
that source-space mapping; pieces are not normalized independently or silently
repacked. Holes, internal features, simulation, and welding retain the layout and
island coordinates. Face/piece identifiers make material assignment easier.

Keep source pieces separated to avoid overlapping UV islands. Newly added pieces
can extend outside the original 0-1 tile; move the source layout or explicitly
repack in Blender when that is intended. Retopology, rigging/weight transfer, and
VRChat/Unity setup remain separate finishing tasks.

## Local garment library and refitting

In Library, type a garment name and choose **Save editable garment**. It saves the
Bezier source, internal features, sewing, anchors, presets, wrap state, UV layout,
and body-relative panel placements. It never bundles the avatar mesh or its name.
Files live in Blender's user datafiles folder under `devil_designer/garments`.
Saving an existing name replaces that named library entry.

Choose another body, select an entry with Previous/Next, and **Load onto selected
avatar**. With **Scale by body height** enabled, the source dimensions scale
uniformly by height while preserving UV coordinates. Placement and tacks remap to
the new body bounds. This is a starting refit, not automatic tailoring to every
body proportion; adjust the 2D design, place pieces, and simulate again. Loading
without a body still restores an editable design for later arrangement.

## Saving and compatibility

Save the `.blend` normally. Versioned source paths, sewing ranges, constraints,
cloth choices, UV layout, body selection, editor placement, and kept meshes save
with it. Earlier straight-edge documents migrate to the new schema. The current
overlay's drafting history resets when the editor is reopened; unfinished drafts
and drag previews are not saved. Topology edits report sewing that requires repair.

## Validation

No external runtime packages or network services are required.

    python -m unittest discover -s tests -p "test_*.py" -v
    blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
    blender --background --factory-startup --python-exit-code 1 --python tests/blender_garment.py
    blender --background --factory-startup --python-exit-code 1 --python tests/blender_advanced.py
    blender --background --factory-startup --python-exit-code 1 --python tests/blender_silhouette.py
    blender --factory-startup --python tests/gui_preview.py
    blender --factory-startup --python tests/gui_design.py
    blender --factory-startup --python tests/gui_silhouette.py

The native tests cover real draping, weld/UV/group preservation, holed/slit meshes,
M:N springs, pin/tack targets, presets, garment-library loading on a different body,
reference geometry, and save/reopen. GUI tests exercise all tool families through
the actual modal editor and leave isolated factory previews.

    python tools/build.py
    python tools/check_public.py
    blender --background --factory-startup --command extension validate build/devil_designer-0.5.0.zip

[The product specification](SPEC.md) records the intended scope and implementation
coverage. Temporary scenes, test libraries/reports, Python caches, machine settings,
and build ZIPs are excluded from Git. No upload occurs unless explicitly requested.

License: [GPL-3.0-or-later](LICENSE).
