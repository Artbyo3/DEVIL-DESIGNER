# Frequently Asked Questions & Troubleshooting

This page addresses common questions and troubleshooting scenarios when authoring clothing with Devil Designer v0.10.0.

---

## Sewing & Seam Questions

### Why does my seam show an amber "Gather warning"?
An amber **Gather warning** appears whenever the arc lengths of two paired seam edges differ by more than **1%**. 

**This is never a hard block.** In professional garment construction, easing and gathers (such as a sleeve cap sewn into a smaller armscye or a gathered skirt attached to a waistband) intentionally use mismatched edge lengths. Devil Designer displays the percentage mismatch and length delta in centimetres for your reference, but allows the simulation to proceed normally.

### Why won't the 3D viewport register my sewing click?
When sewing directly onto live 3D panels in the viewport, Devil Designer strictly validates edge clicks to prevent accidental mispairing:
* **Ambiguous Clicks:** If a click falls on a shared corner vertex or overlapping visible edges, the click is refused. Orbit the camera or zoom in to isolate the intended edge.
* **Occluded Edges:** Edges on the back of the body or behind another panel cannot be clicked through foreground geometry.
* **Active Simulation:** You cannot sew while cloth simulation is actively running. Click **Pause** before picking edges in 3D.
* **Kept Meshes:** Finalized kept meshes cannot be sewn to live pattern panels.

### Why didn't my linked twin receive my new sewing seam?
**Linked Editing intentionally never creates, copies, or removes sewing.** Linking synchronizes pattern geometry: anchor points, Bezier handles, corner/curve point toggles, internal paths, and darts. Sewing topology, however, is often asymmetric (e.g. asymmetrical closures, wrap garments, or distinct left-to-right connections). You must pair seams explicitly on linked pieces.

### Why does Seam Shrink change folds elsewhere on my garment?
Setting a non-zero **Shrink** percentage (10%, 20%, or 30%) on any seam automatically switches the garment's self-collision distance from the default **3 mm down to 1 mm**. This tighter collision tolerance is required to allow dense gathering folds without mesh explosion, but it may cause subtle changes in folding behavior across neighboring panels. Garments with 0% Shrink on all seams retain the standard 3 mm distance.

---

## 3D Placement & Avatar Questions

### Why does my cloth penetrate the avatar or layered clothing?
* **Avatar Collision:** Devil Designer automatically adds a native Blender Collision modifier to the chosen avatar if missing. Ensure your avatar mesh has clean geometry without inverted normals or extreme self-intersections.
* **Layering & Clearance:** When using **Wear over** to simulate a jacket over a shirt, ensure the outer jacket panels are positioned radially outward from the inner garment before starting simulation.
* **Simulation Quality:** For multi-layer garments, set **Simulation quality** to **High** on the canvas menu. High quality uses smaller simulation timesteps to resolve tight contact without penetration.

### Does Devil Designer support avatars with armatures and shape keys?
Yes. When an avatar mesh is selected via **Garment > Body**, Devil Designer evaluates the mesh with active armature deform modifiers, shape keys, and scene scale applied. The pose-stable tack tool (<kbd>T</kbd>) binds directly to avatar skin triangles and follows bone animations and shape keys.

---

## Simulation & Drafting Questions

### Can I freeze a piece and sew live pieces to it?
Yes. Right-click any piece and choose **Simulation > Freeze**. The frozen piece remains rigidly held in its current evaluated shape while live neighboring pieces drape against it. Both endpoints of connecting seams are held, and same-mesh self-collision ensures draping fabric collides cleanly with the frozen piece.

### What does the Fit Map display? Is it pressure or stress?
The Fit Map (<kbd>F</kbd>) is an **edge-deformation guide**, not a calibrated physical pressure or tensile stress analysis:
* **White:** Neutral rest length (within &plusmn;3%).
* **Blue:** Compression (up to 15% / 0.85 ratio).
* **Red:** Stretch (up to 15% / 1.15 ratio).
Loose fabric can fold or drape without compressing individual edges and will remain white. Use the map as a quick visual sanity check for excessive tightness or unwanted sagging.

### What happens if a cut crosses an internal line?
When using the Cut knife (<kbd>N</kbd>), if a straight cut crosses existing straight open internal lines, Devil Designer displays a **Split and retry** prompt. This automatically stages the internal split and outer boundary cut as a single undoable transaction. If the cut intersects curved lines, closed shapes, or anchors, the operation is safely refused with an explanatory card so you can adjust the internal path manually.

### How do I undo an accidental garment load from the library?
When you load a garment from the library over an existing design, Devil Designer automatically captures a backup snapshot (`scene['dd_backup_document']`). Press <kbd>Ctrl</kbd> + <kbd>Z</kbd> immediately to revert the load and restore your previous work.

### How many undo steps are saved, and do they survive closing Blender?
Inside the Devil Designer editor, you have up to **100 transactional undo/redo steps** (<kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>). This pattern and sewing history is stored in the `.blend` file (`dd_history`), meaning it survives saving and reopening Blender.

### Are separate Blender curve objects created in the Outliner?
No. Devil Designer stores its 2D Bezier pattern data directly in its custom internal document structure. It does not clutter your Blender scene Outliner with separate curve objects. Only finalized output meshes created with **Keep mesh** appear as objects in your scene.

### How are UVs prepared for texturing in Substance 3D Painter?
UV coordinates are generated 1:1 from the flat 2D pattern drafting layout:
* Pattern islands retain their exact relative scale, rotation, and placement.
* Devil Designer does not normalize islands independently or automatically repack UVs.
* Piece face identifiers and vertex groups are preserved for easy ID masking in Substance 3D Painter.

### How are the fabric presets calibrated, and what are their solver limits?
Presets (Silk, Knit, Cotton, Linen, Leather, Denim) are calibrated against physical textile benchmarks (KES-F / FAST derived data and Peirce cantilever bending lengths). Known physics and solver limits include:
* **0.02 m spacing:** Calibration is exact near 0.02 m spacing because Blender assigns mass per vertex and bending per edge without area/length normalization.
* **3/8 shear lock:** Triangle-mesh shear is locked to 3/8 of structural stiffness because Blender creates zero shear springs on triangular CDT meshes.
* **Shared density:** Multi-fabric garments share one area-weighted density because native Blender cloth simulation uses a single mass setting across the compiled object.

### Why is quad-grid conversion deferred on Keep mesh?
Keep mesh outputs clean, welded triangle topology with optional Solidify thickness. Quad-grid conversion was prototyped but deferred because it did not reliably preserve welded boundary seams. No quad conversion, decimation, rigging, or weight transfer is performed.

### Where are the add-on interface icons sourced?
Public interface icons are sourced CC0 artwork from Kenney, Maki, and Temaki. Provenance and original licenses are preserved in `devil_designer/assets/icons`.

### Where are disposable developer files and test reports stored?
All temporary test outputs, screenshots, benchmark reports, and generated scripts are placed in the git-ignored `scratch/` folder. The installable extension ZIP is kept in `dist/` and is never automatically deleted. Running `.\dev.cmd --clean` purges the scratch directory safely without touching source files or user projects.
