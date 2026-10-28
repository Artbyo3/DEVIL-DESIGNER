# Devil Designer

A movable 2D clothing-pattern editor with Bezier drafting, internal construction,
sewing, avatar placement, native Blender cloth, and a reusable local garment library.

By **Artbyo3**. **0.8.0**, tested in **Blender 5.2.3 LTS**.
Requires Blender 5.2+.

## Install and open

Run `python tools/build.py` to create the installable archive, then install
`dist/devil_designer-0.8.0.zip` through **Edit > Preferences > Add-ons >
menu > Install from Disk**. Disable the previous version and restart Blender to
unload its old Python modules. Enable Devil Designer if necessary.

In a 3D Viewport use **Ctrl+Alt+D**, **F3 > Devil Designer**, or **View > Devil Designer**.
There is no full-height sidebar, searchable all-settings inspector, docked sidebar, or universal
cursor menu. The workspace opens with a pure 100% full-screen canvas, a compact 8-tool left dock,
persistent micro-indicators for Snapping `[S]`, Body Guide `[H]`, and Lengths `[L]`, and focused
right-click contextual menus anchored directly at the cursor. When the 3D viewport is revealed for
placement or drape inspection, click Full canvas to return. Other Blender controls remain available
outside the editor when the 3D view is revealed.

Pure contextual interaction:
- Selecting pieces, seams, points, or edges highlights them cleanly with zero auto-opened overlays.
- Right-clicking any item (piece, seam, point, edge, internal path, pin/tack, or empty canvas) opens
  a small, focused contextual menu directly at your cursor.
- Choosing an action immediately executes it and dismisses the menu back to pure canvas.
- Right-clicking empty canvas opens the Garment & View menu: Body avatar selection, Garment default
  fabric chips, Mesh density, Simulation quality, Guide opacity, and Fit design.
- Individual pieces can override their fabric preset or mesh density via their right-click menu.

Escape cancels active drafting or gestures first, dismisses open contextual menus next, and exits
the editor when idle without blocking or trapping the artist. Use Close or Ctrl+Alt+D to leave the
editor explicitly.

The default workspace has three primary actions: **Panel > Sew > Simulate**.
Panel drawing is ready on open: drag the canvas to create pieces, click Sew and
pair edges, then click Simulate. There are no separate Build or Arrange clicks for
a new garment: every closed piece already has its flat 3D panel, and arrangement is optional. The selected body is used automatically;
if the body is ambiguous, one inline choice starts the requested simulation.

An empty garment also offers **Create panel**, a one-click editable 40 x 45 cm
starter, alongside custom panel drawing and the garment library. Starter creation
is undoable. See `ARTIST_UX_AUDIT.md` for the workflow fixes and artist test checklist.

The arrow on **Keep mesh** opens Auto weld and Thickness (None / Thin / Standard). A manual weld
tolerance appears only after Keep actually reports unwelded seam pairs. Self-collision, body clearance,
body-height refit, and automatic defaults are program decisions, not settings the artist must configure.

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
| Cut / Cut & Sew knife | N, or Internal tool choices beside Dart |
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
| Undo / redo | Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y |
| Grid snapping / temporary inversion | S / hold Ctrl |
| Constrain next polygon edge to an axis | Hold Shift |
| Pan / zoom / fit | Middle mouse / wheel / F or Home |
| Show body reference | Body H / H |
| Cancel current gesture/draft/placement | Escape |

The Internal tool choices include **Cut** without adding a ninth dock tool.
Its default mode is **Cut & Sew**; choose **Cut only** there to separate pieces
without sewing. Click two or more straight-line points, then press Enter or
double-click to finish; Escape cancels. Shift locks the next segment horizontally
or vertically, and the usual snapping and Ctrl inversion apply. Live dots mark
outline intersections. The line can begin and end outside the piece: only the
interior section is cut. Each target must cross the outline exactly twice;
tangencies, overlapping outline edges, self-crossings and crossings through holes
are refused without changing the design. Selected pieces are the targets; with
no selection, every fully crossed piece is targeted. A cut that crosses an
existing internal path is refused just like the existing boundary cut; split that
path first. Internal curve cuts, slits and holes still use **Cut along path**.

Both halves retain fabric, mesh density and their original UV positions, with no
repack or overlapping interiors, and receive the original name plus ** 1** and
** 2**. Outer-edge sewing uses the existing remapping and repair messages.
Cut & Sew creates a removable seam along the matching new edge chains. The entire
operation, including multiple pieces and new sewing, is one Undo step.

Select a point or segment to edit it. Live lengths use numerical Bezier arc-length
integration and update as handles move. Contextual cards expose exact coordinates
(**Point X/Y**), dimensions, and segment lengths (**Exact length**) to precisely
adjust points, outlines, or handles.

**Offset outline copy** keeps the original piece and creates an editable outline
at the entered distance. Curved offsets use a sampled approximation and can have
more points. Self-intersecting or collapsed results are rejected. **Unfold** joins
the mirrored halves along the selected straight edge. **Mirror with seam** creates
a separate reflected piece and a sewing pair; self-sewing darts are copied as well.

## Linked editing

Right-click a piece and choose **Clone as linked twin** to create a mirrored,
linked copy named after it. The twin sits to the right of the existing pattern
islands without overlapping them. Creating the entire twin is one Undo step.
Nothing creates twins automatically, and cloning or linking never adds, copies,
or removes sewing.

A piece arranged at a front point also offers **Clone as Back**. This places the
linked copy at the back point of that same body volume, with fresh arrangement
deltas. Ordinary linked clones start unarranged; an unarranged Back clone also
starts in the flat layout. Arrangement and moving whole pieces remain independent.

Point moves, handles, corner/curve changes, added/split/merged/deleted points,
exact coordinates and exact edge lengths mirror in either direction. Internal
paths mirror too. Drag previews show both outlines; each completed edit is one
undoable change. Topology edits still use the existing sewing repair rules.

Use **Linked twin Off** in the piece menu to stop sharing edits without changing
either outline. **Linked twin On** reapplies the selected piece onto its existing
twin. To link two existing pieces, select both and right-click the selection,
then choose **Linked twin**; the active piece supplies the replacement outline.
Relinking refuses a replacement that would invalidate existing sewing rather
than silently removing it. Unsew the affected edges explicitly before retrying.
Each piece has at most one linked twin. Switching a pair off remembers it for
single-piece relinking; explicitly linking to a different selected piece or
creating a new linked clone instead replaces that inactive pairing.

Deleting either member removes the pairing; Undo restores it. Duplicating one
member creates an independent copy while leaving the original pair intact.
Duplicating both members creates a separate pair. **Mirror with seam** retains
its existing explicit sewing behavior and does not add a member to the pair.
Links and their On/Off state survive library save/load, body-height refits,
save/reopen, and undo/redo. Older designs have no links and retain their behavior.

## Internal shapes, cuts, trace, and darts

Select the target piece before using I, or click inside it to select an owner.
Use **Internal** (shortcut **I**) or the **Internal shapes** card to draw internal
paths, constraints, darts, and cut lines inside the selected pattern.

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
straight open internal lines offers **Split and retry**. This stages the split and
cut as one undoable edit, preserving supported sewing and anchors. Curved or closed
crossing shapes, overlaps, and anchors on the cut still need manual repair; the
recovery card explains the refusal without changing the design. Slit sewing
uses the path's generated boundary mapping; choose a boundary-to-boundary cut into
separate pieces when both independently selectable cut sides are needed.

## Sewing

In Sew/J, click an edge and its partner for segment sewing. Select a seam badge or
sewn edge to inspect it; B reverses direction, Delete removes the seam, or use the
**Selected seam** card to reverse or remove it.

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

For photo tracing, open **Garment > Reference image > Load image**, including on an
empty canvas. Adjust image placement and opacity in its contextual cards. Enter a
known physical length under **Set measured scale**, choose **Pick length endpoints**,
then click both ends on the image. Calibration changes only the image scale, never
existing patterns. One length cannot correct perspective or lens distortion; use
a flat, undistorted reference when fit matters. Image settings persist in the blend
file; the external image must remain available at its saved path.

Choose the body in **Garment > Body**, or select its mesh in 3D and click
**Use selected body**. The actual evaluated mesh appears behind the pattern grid
at physical scale. It includes armature/shape-key deformation and object/scene
scale; limb gaps are preserved. Toggle guide visibility with **H** or the **Workspace**
card, which also controls opacity. It cannot be selected as a pattern.

Closing a piece immediately builds its flat panel in front of the body, with the
same relative positions and physical scale as the 2D drawing. Committed outline
edits and 2D moves rebuild the panels; deleting a piece removes its panel. The 2D
body silhouette is only a drawing reference: moving it never places new panels.

Select a piece, reveal the 3D view, and click a blue **arrangement point** to wrap
it around that point's bounding volume. **H** shows or hides the guide, volume
rings, and points. Avatar volumes cover neck, chest, waist, hip, upper arms,
forearms, thighs, and calves. Right-click a point for **Arrange flat**, **Move
point**, **Add point**, **Delete point**, or **Edit bounding volume**. Point angles
and heights stay on their volume; volume bounds are fractions of body height.
The body picker offers **Regenerate body volumes** to remeasure a changed mesh
or recover invalid setup; this explicitly resets point and volume edits.

Volume and point edits belong to the avatar in this scene, never to a garment.
Moving or scaling the avatar updates its live panels and points. After arranging,
Blender **G/R** adjustments are saved as relative translation/rotation deltas.
Clicking a point again resets those deltas. **Reset to 2D layout** on the piece
card clears its arrangement and restores its flat layout position. Ordinary
**Reset drape** removes simulation/cache but keeps arrangements.

Wrapping uses the cylinder radius at the selected point's height. Wider-than-one-
circumference pieces form an outward spiral with separate successive turns.
These are editable starting placements, not automatic fitting: anatomical section
detection is heuristic, missing sections use fallback cylinders, and a tall piece
can intersect a wider neighboring section on a tapered body. Inspect before draping.
The Tee uses integrated sleeve outlines rather than separate sleeve panels;
Tee/Tank fronts and backs use explicit chest points, and Skirt uses waist points.

Design document versions 1–3 keep their legacy guide/name/order placement and
named Bodice/Sleeves/Skirt layouts. Legacy ray placement and manual wrap radius
remain available only for those pieces. Version 4 records point IDs and relative
deltas, plus pattern-space source bounds when a cut must retain its parent's
3D frame. Cutting an arranged or legacy piece preserves both halves' placement.
Neither arranging nor cutting repacks UVs or rewrites the source outline's layout.

K adds a static pin on fabric. T picks a fabric point, then a target on the avatar
in 3D. Tacks use native Hook/pin groups and avatar-parented surface-following targets.
Select a pin/tack with K/T and use **Remove selected pin / tack** to remove it.
Pins/tacks are source-space anchors and are remapped when the mesh is rebuilt.
Tacks bind to a skin triangle and follow its vertex deformation through poses,
shape keys, and object transforms. A topology mismatch asks for reattachment instead
of drifting to a nearby surface. Disable topology-changing modifiers before binding.
Older tacks bind once at their current resolved position; reattach an already
misplaced legacy tack. A replacement avatar uses the retained portable target.

## Generate, simulate, and finalize

Mesh spacing controls a staggered interior grid and constrained Delaunay
triangulation. Curved boundaries, holes, internal constraints, and slit edges are
included. Start around 2-3 cm and increase density only when needed. Each source
piece and compiled garment has piece face identifiers, sculpt face sets, and
per-piece vertex groups.

Select a piece and open **Mesh density** to choose **Garment default**, **Coarse**,
**Standard**, or **Fine**. Fine halves the default spacing; Coarse doubles it.
Interiors remain per piece, so a fine strap need not refine a large panel interior.
Sewn components share conservative boundary sampling to keep paired seams compatible;
unrelated pieces keep their own boundary density. Density changes are undoable.

Drafting undo and redo retain up to 100 document edits per stack after closing and
reopening the editor. Save the blend file to retain them across Blender restarts.
Replacing the design invalidates history from a different document rather than
applying unrelated edits.

Choose a selected piece's preset in the **Fabric** card: Silk, Knit, Cotton,
Linen, Leather, or Denim. Native structural, shear, and bending groups provide per-piece
stiffness. **Mass density is a shared, area-weighted native cloth value**; these
presets are practical starting values, not measured textile calibration.

**Simulate** starts from current live panels, arranged or not, with no auto-placement
gate. An unarranged panel intersecting the body produces a named status warning
without blocking simulation. The locked cloth setup and sewing force math remain
unchanged. Legacy **Build 3D** preserves manually placed legacy panels.
Simulation quality and mesh density are adjusted on the empty-canvas right-click menu.
Fabric presets live on the piece **Fabric** card. Body clearance, self collision, and automatic defaults
are program decisions, not settings the artist must configure. The chosen body gets Collision if needed; an existing collision
modifier is left unchanged.

Use the bottom bar **Pause**, then click **Keep mesh** when needed. Keep mesh copies the evaluated drape, removes
loose sewing springs, welds only paired vertices within tolerance, and retains UVs,
piece face identifiers, and group memberships. Optional thickness is an editable
Solidify modifier. If pairs remain open, the result reports them; simulate longer
or correct placement/direction before keeping another copy.

Reset asks for confirmation before removing the simulation/cache and restoring arranged panels, preserving kept
garments. Reset after body geometry/collision changes before simulating again.
Simulation caches are not automatically baked to disk. A single piece can drape
without sewing; a selected body is still required for this workflow.

### Wear over kept garments

When kept garments exist, the **Simulate** arrow opens **Wear over**. Every kept
garment starts On. Up to five garments are shown; scroll or use Next to reach the
rest. Clicking a garment toggles it and immediately dismisses the list. The choice
is saved with that object in the blend file and is applied when Simulate next
starts or resumes; a changed selection rebuilds the simulation rather than reusing
its old cache. Linked garments need an editable override to change their choice.

Enabled kept meshes get a Collision modifier only if one is missing. Existing
Collision modifiers and their settings are never changed. Each new simulation gets
its own collision filter containing the body and every other scene collider; only
unchecked kept garments are excluded. Turning a garment Off does not disable or
remove its Collision modifier. Other simulations keep their own filters. With no
kept garments, the existing simulation path and collision settings stay unchanged.
Reset still preserves all kept garments.

Place the outer garment outside the kept layer before simulating, and use the
existing **High** simulation-quality preset for layered work. The automated
shirt/jacket fixture uses prearranged panels and shoulder pins on a headless torso,
checks 121 frames at High quality against a 2 mm penetration tolerance, and samples
vertices, edge midpoints and face centers away from open boundaries. This controlled
test is not a penetration guarantee for arbitrary clothing or initial intersections;
the Standard-quality fixture exceeded that tolerance. Cloth settings, sewing
forces and placement algorithms are not changed to implement layering.

Keep mesh remains the existing triangle output with Auto weld and Thickness.
Quad-grid conversion is deferred: its prototype did not preserve welded seams.
No quad conversion, reduction, decimation, rigging or weight transfer ships here.

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

In Library, choose **Save garment** to store the Bezier source, internal features,
sewing, anchors, presets, UV layout, and volume/point IDs with relative G/R deltas.
It never bundles the avatar mesh or its name. Files live in Blender's user datafiles
folder under `devil_designer/garments`.

Choose another body in the body picker card, open **Library**, and click **Load** on
the desired garment. The body and library pickers display up to 8 items per view with
mouse-wheel scrolling and instant page navigation. With **Scale by body height**
enabled, source dimensions scale uniformly by height while preserving UV coordinates.
The new avatar generates its own volumes and matching point IDs resolve there.
A missing volume or point falls back to the flat 2D-layout position with a status
message. Legacy files retain bounds-relative placements. Tacks remap to the new
body bounds. Loading over an existing garment
automatically saves a backup snapshot (`scene['dd_backup_document']`) and can be
undone immediately with Ctrl+Z; Go back or Escape cancels before loading.

## Saving and compatibility

Save the `.blend` normally. Versioned source paths, sewing ranges, constraints,
cloth choices, UV layout, body selection, editor placement, kept meshes, and
drafting undo/redo history (`dd_history`) save with it. Inside the editor,
Ctrl+Z and Ctrl+Shift+Z step through private 2D pattern geometry and seam history
(up to 100 edits) across editor sessions. In the 3D viewport outside the editor,
Blender's native undo operates on scene objects and meshes. Topology edits report sewing that requires repair.

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
    blender --background --factory-startup --command extension validate dist/devil_designer-0.8.0.zip

The publication audit checks source, archives, and reachable Git history. GitHub's
public noreply identity is permitted as a merge committer only. The already-published
author identity accepted for PR #1 is recognized by an exact SHA-256 fingerprint
in commit metadata only, without copying its email into source. The audit reports
each affected commit; this does not redact or remove its original history metadata.
Other unapproved identities and private emails in source or archives still fail.

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
