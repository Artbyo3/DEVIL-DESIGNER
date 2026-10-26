# Devil Designer

A movable 2D clothing-pattern editor with Bezier drafting, internal construction,
sewing, avatar placement, native Blender cloth, and a reusable local garment library.

By **Artbyo3**. **0.5.0**, tested in **Blender 5.2.3 LTS**.
Requires Blender 5.2+.

## Install and open

Run `python tools/build.py` to create the installable archive, then install
`dist/devil_designer-0.5.0.zip` through **Edit > Preferences > Add-ons >
menu > Install from Disk**. Disable the previous version and restart Blender to
unload its old Python modules. Enable Devil Designer if necessary.

In a 3D Viewport use **Ctrl+Alt+D**, **F3 > Devil Designer**, or **View > Devil Designer**.
There is no full-height sidebar or all-settings popup. The workspace opens as a full canvas with
a compact tool dock and an optional Workspace side card. Use Expand / Restore or Tab to switch layouts. Other Blender
controls remain available outside the editor when the 3D view is revealed.

The compact **Workspace** card controls snapping, measured edge labels, body-guide
visibility, and Fit design. Guide opacity offers Light / Medium / Strong only while
the guide is shown. Pin keeps the card open while working; unpin dismisses it on
canvas input. Close hides it, and Workspace at the top right reopens it without
changing the canvas layout or the active piece/task card. Other controls stay in
their existing contextual locations.
The pinned card remains visible while drawing. Escape cancels the current edit or
closes a contextual popover; it does not exit the minimal workspace. Use Close or
Ctrl+Alt+D to leave the editor explicitly.

The default workspace has three primary actions: **Panel > Sew > Simulate**.
Panel drawing is ready on open: drag the canvas to create pieces, click Sew and
pair edges, then click Simulate. There are no separate Build or Arrange clicks for
a new standard two-panel front/back garment. The selected body is used automatically;
if the body is ambiguous, one inline choice starts the requested simulation.

Selecting a piece shows its small card. **Fabric** opens Cotton, Linen, Denim, Silk,
Leather, and Knit beneath the card. Presets own physical parameters; there are no
cloth-parameter fields. With nothing selected the card describes the garment, its
name, body, and piece count. The dock grid opens the local garment library.

The arrow on **Simulate** opens Mesh density (Coarse / Standard / Fine) and Quality
(Draft / Standard / High). The arrow on **Keep mesh** opens Auto weld and Thickness
(None / Thin / Standard). A manual weld tolerance appears only after Keep actually
reports unwelded seam pairs. Self-collision, body clearance, body-height refit, and
automatic defaults are program decisions, not settings the artist must configure.

Select a seam badge to reverse or remove that seam in place. Right-click a point,
edge, or piece for a small task-specific card, not a list of unrelated options.
Popovers stay within approximately five controls; the fabric list has six materials.
Exact design dimensions can still be dragged or typed when needed. Numeric point
and edge edits apply on completion as one undoable edit. Escape cancels a value drag.

The selected piece card also exposes **Edit piece**. Internal-edge cards keep Cut
and closed-path Trace attached to the selected path. Right-click a pin or tack for
its removal card; Delete removes the selected anchor, not its owner piece. Shift+D
duplicates through the same undoable action as the piece menu. Context cards have
close buttons, and save/undo shortcuts continue working while hovering over them.
Fit design frames patterns clear of the dock and pinned Workspace card when space
permits, without shrinking the actual canvas.

Public interface icons are sourced CC0 artwork from Kenney, Maki and Temaki.
Provenance and original licenses ship in `devil_designer/assets/icons`; the Blender
renderer caches native GPU geometry and needs no extra runtime dependencies.

**Simulate** also pauses playback and automatically reveals the 3D result. Existing
panel placement is preserved when resuming. Keep mesh stays beside Simulate; Reset
is available on the garment card after simulation exists. Finish or cancel an
unfinished drawing before switching tools or closing. The reference sections below
describe the underlying authoring operations; old sidebar paths are superseded by
the contextual cards described here.

## Draft and edit

The source patterns are cubic Bezier paths, stored independently of generated mesh
topology. Polygon and rectangle segments begin straight; ellipse outlines use four
Bezier anchors. The custom editor owns the editable path data; these are not
separate Blender Curve objects.

| Tool/action | Control |
| --- | --- |
| Select / polygon / rectangle / ellipse | V / P / R / E |
| Internal line / sewing / pin / tack / dart | I / J / K / T / D |
| Place selected panel in 3D | G inside the editor; Blender transforms outside it |
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
inspect it; B reverses direction and X removes the pair. The Sewing section's pair list
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
framing, and refresh are all in Body & placement, under More controls or search.
It cannot be selected as a pattern.

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

Use **Simulate > Pause**, then Tools > Keep mesh when needed. Keep mesh copies the evaluated drape, removes
loose sewing springs, welds only paired vertices within tolerance, and retains UVs,
piece face identifiers, and group memberships. Optional thickness is an editable
Solidify modifier. If pairs remain open, the result reports them; simulate longer
or correct placement/direction before keeping another copy.

Reset asks for confirmation before removing the simulation/cache and restoring arranged panels, preserving kept
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
Saving an existing name asks before replacing that named library entry. A custom
Library folder can be entered through More garment library controls or search.

Choose another body, select an entry with Previous/Next, and **Load onto selected
avatar**. With **Scale by body height** enabled, the source dimensions scale
uniformly by height while preserving UV coordinates. Placement and tacks remap to
the new body bounds. This is a starting refit, not automatic tailoring to every
body proportion; adjust the 2D design, place pieces, and simulate again. Loading
without a body still restores an editable design for later arrangement. Loading
over an existing garment requires confirmation; Go back or Escape preserves it.

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
    blender --background --factory-startup --command extension validate dist/devil_designer-0.5.0.zip

[The product specification](SPEC.md) records the intended scope and implementation
coverage. Temporary scenes, test libraries/reports, Python caches, machine settings,
and installable ZIPs are excluded from Git. No upload occurs unless explicitly requested.

## Disposable development workspace

`dist/` holds the installable extension ZIP and is never auto-deleted. Everything
disposable belongs in the ignored `scratch/` directory: test scenes and backups,
reports, screenshots and crops, generated scripts, preview logs, icon downloads,
temporary dependencies, and test garment libraries. Do not put source, required
artwork, licenses, user projects, or the installable ZIP in scratch.

Use the developer runner so child processes do not create Python bytecode caches:

    .\dev.cmd --test --build

Successful runner commands automatically delete scratch, including its directory,
after all requested work finishes. Failed runs retain diagnostics for inspection.
The ZIP remains available in `dist/` for installation either way.

For a visual audit, explicitly retain screenshots until review is finished:

    .\dev.cmd --shots --keep-scratch
    .\dev.cmd --inspect --keep-scratch
    .\dev.cmd --clean

`--clean` only deletes scratch; it never deletes dist, source, or user projects.
It refuses linked directories and reports locked files rather than force-closing
Blender or discarding work. Close disposable previews before cleaning. Standalone
test/screenshot/icon utilities also write to scratch; run `--clean` when finished.
For icon regeneration, download vendor archives into scratch first as described in
the icon asset README.

License: [GPL-3.0-or-later](LICENSE).
