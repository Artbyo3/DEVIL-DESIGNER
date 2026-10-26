# Devil Designer

**2D pattern drafting, edge sewing, and cloth draping inside Blender.**

By **Artbyo3**. Intended for creating clothing shapes for VRChat and other game
characters. Version **0.3.0**, tested in **Blender 5.2.3 LTS**; requires Blender 5.2+.

This version connects the editable 2D patterns to real 3D fabric meshes. It includes
an actual two-piece bodice sewing demo, body collisions, and a way to keep the
draped result as a normal Blender mesh. It is an early garment authoring tool;
final topology cleanup and rigging are still separate Blender tasks.

## Install

Download the ZIP from [Releases](https://github.com/Artbyo3/DEVIL-DESIGNER/releases).
Disable an older Devil Designer installation before installing this version.
In Blender, open **Edit > Preferences > Add-ons > menu > Install from Disk**,
select `devil_designer-0.3.0.zip`, and enable the extension.

In a 3D Viewport, press **Ctrl+Alt+D**, use **F3 > Devil Designer**, or choose
**View > Devil Designer**. There is no Devil Designer N-panel. Avatar selection,
sewing controls, fabric settings, simulation, and output options all live inside
the custom editor.

Drag the header to move the window anywhere within the viewport. Drag its bottom
right corner to resize it. **Expand / Restore** or **Tab** toggles the expanded
layout; restoring preserves the floating position. Position, size, and settings
visibility are saved per scene with the `.blend` file. Bounds are clamped when a
file opens on a smaller viewport so the controls remain reachable.

The header's **Settings** button shows or hides the in-window inspector. Scroll
inside it to reach every option and the seam list; scroll over the pattern canvas
to zoom. Click a numeric value to type it, then Enter to apply or Escape to cancel.
The **- / +** buttons adjust values; Shift makes smaller decimal steps and Ctrl
makes larger steps. Choose the avatar from the custom body list, or select its
mesh in 3D and click **Use selected body**. Numeric fields use the displayed cm/mm
units and validate values before applying them.

## Try the complete workflow

Start with a new scene and an empty pattern document. Open Devil Designer and
click **Settings > Create sewing demo** (scroll to TRY IT if needed). This creates two bodice patterns,
four sewing pairs, a procedural torso collider, and positioned 3D panels.

1. Open the pattern editor to inspect the front and back pieces. **Sew / J** shows
   the numbered seam connections; large matching dots indicate paired endpoints.
2. Press **Simulate** in the editor. Blender pulls the seams together
   and drapes the fabric around the torso. Playback stops at the simulation limit.
3. Press **Stop** when the shape looks right. **Keep mesh / Keep Draped Mesh**
   creates an editable garment with its UVs, removes loose sewing springs, and
   welds only matched seam vertices within the selected tolerance.
4. To revise the fit, use **Reset**, edit a 2D pattern, and **Build 3D**. Existing
   panel positions and valid seam connections are preserved. Simulate again.

If some seam pairs have not closed, Blender reports how many remain unwelded.
Simulate longer or correct their direction and arrangement before keeping a new
result. Increasing weld tolerance can bridge small gaps, but it does not fix a
wrong seam pairing. Kept garments are independent copies; reset never removes them.

## Make clothing for your avatar

1. Draw the required 2D pieces. Use **Polygon / P** to click corners, then click
   the first corner or press Enter to close. Use **Rect / R** to drag rectangles.
2. Choose **Sew / J** and click an edge on one piece, then its partner on another.
   Each edge can belong to one seam. Select a sewn edge and press **B** to reverse
   its direction or **X** to remove the seam. The editor's Settings seam list also has Flip/remove
   buttons. Different-length sewn edges get matching sample counts; excessive
   length differences can stretch or gather the cloth.
3. Choose your body mesh in the custom editor's **Settings > Avatar body** field. Click **Build 3D**
   to generate the fabric meshes. **Arrange** supplies a front/back starting layout
   for exactly two pieces; it estimates torso height and assumes a Z-up avatar
   facing Blender's -Y direction. Adjust the pieces using Blender's **G / R** tools.
   Additional pieces can be built and positioned manually.
4. Avoid starting panels inside the body. **Body clearance** controls the initial
   front/back offset. The add-on adds collision to the chosen body if needed and
   leaves an existing collision modifier unchanged.
5. Use **Simulate**, **Stop**, and **Keep mesh** as in the demo. A suitable body
   pose, correctly sized patterns, and sensible placement are necessary for a good fit.

**Build 3D**, **Arrange**, and **Reset** discard the previous simulation and restore
its positioned source panels. They preserve completed garment copies. Merely
resuming an unchanged simulation keeps its cache. If the avatar geometry or its
collision settings have changed, use Reset before simulating again.

## Editing controls

Move the pointer over the overlay to use its shortcuts.

| Action | Control |
| --- | --- |
| Open / close editor | Ctrl+Alt+D |
| Move / resize editor | Drag header / bottom right corner |
| Show garment settings | Settings button in header |
| Polygon / rectangle / select / sew | P / R / V / J |
| Move a corner / whole pattern | Select, then drag a corner / piece interior |
| Duplicate pattern | Shift+D |
| Delete selected corner or piece | X / Delete in Select mode |
| Remove last draft corner | Backspace |
| Finish polygon | Enter or click its first corner |
| Constrain next polygon edge horizontally/vertically | Hold Shift |
| Toggle 1 cm snapping | Snap / S; hold Ctrl to temporarily invert |
| Undo / redo drafting and sewing | < / >, Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y |
| Pan / zoom | Middle mouse / mouse wheel |
| Fit all patterns | Fit / F / Home |
| Expand / restore overlay | Header button / Tab |
| Cancel draft, drag, or pending sewing edge | Escape |
| Close overlay when no edit is pending | Escape / header X |

Pattern coordinates are stored in metres and displayed in centimetres. The visible
grid adapts to zoom; snap spacing remains 1 cm. Generated meshes account for scene
unit scale. The complete draping test uses the default scale of 1 metre per Blender
unit. Nonstandard unit scales may require cloth/collision tuning.

## Fabric and output settings

- **Mesh spacing:** smaller values make denser, slower cloth meshes. The interior
  uses a staggered point grid and constrained Delaunay triangulation. Pattern
  boundaries and concavities are preserved. Start around 2-3 cm for a torso.
- **Quality steps:** cloth solver steps per frame. Higher values cost more time.
- **Self collision:** helps prevent fabric passing through itself.
- **Pin highest panel points:** optional arrangement aids; pinned points stay fixed
  in their initial positions and can prevent a seam from closing. Off by default.
- **Seam weld distance:** applies only to paired seam vertices in the kept result.
- **Final thickness:** an editable Solidify modifier on the kept garment; zero disables it.

Pattern-based UVs are normalized together, preserving relative scale. Keep the 2D
pieces separated if you want separate UV islands without overlap. Repacking the UVs,
retopology, weight transfer, and VRChat/Unity setup remain part of finishing the garment.

Curved pattern edges, darts, internal cuts, interactive cloth sculpting, and automatic
rigging are not implemented yet. Cloth uses Blender's native solver, so response and
performance differ from dedicated garment applications.

## Saving

Save the `.blend` normally. Patterns, seam IDs/directions, avatar selection, settings,
source panel transforms, floating window placement, and kept meshes are saved with it. Version 0.1 pattern
files are migrated when read. Unfinished 2D drafts and drag previews are not saved.
Drafting undo history resets when the overlay is reopened. The simulation cache is
not baked to disk by this tool; reset and simulate after reopening to regenerate it.

## Development and validation

No runtime packages or network services are required. Python-only tests cover
geometry, documents, undo history, seam references, migration, and layout:

    python -m unittest discover -s tests -p "test_*.py" -v

Blender integration tests exercise registration/storage and the actual garment loop:

    blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
    blender --background --factory-startup --python-exit-code 1 --python tests/blender_garment.py

The garment test generates a bodice, changes a pattern, preserves its panel position,
simulates 60 frames without pins, checks seam closure/body support, keeps the drape,
and verifies save/reopen. The graphical test checks the overlay input and opens a
sewn, draped demonstration in a separate factory scene:

    blender --factory-startup --python tests/gui_preview.py

Build, check publication files, and validate the extension:

    python tools/build.py
    python tools/check_public.py
    blender --background --factory-startup --command extension validate build/devil_designer-0.3.0.zip

Builds, temporary `.blend` files, test reports, caches, and machine-specific settings
are excluded from source control. Only the extension ZIP is uploaded as a release
asset. The public author identity is **Artbyo3**.

License: [GPL-3.0-or-later](LICENSE).
