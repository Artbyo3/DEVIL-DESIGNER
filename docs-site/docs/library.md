# Garment Library & Avatar Refitting

Devil Designer includes a built-in local garment library system for archiving portable, reusable clothing designs and refitting them onto different character avatars.

---

## Local Garment Library

Unlike static 3D mesh exports, Devil Designer's library saves the **living, editable 2D/3D design specification**:

* **What Is Saved:**
    * Cubic Bezier boundary curves and control points.
    * Internal lines, cuts, slits, and auto-closing darts.
    * Complete sewing connections (segments, free ranges, M:N chains, and shrink settings).
    * Pins and pose-stable avatar tacks.
    * Fabric material presets and per-piece mesh density settings.
    * 2D UV layout coordinates.
    * Avatar volume and arrangement point IDs with relative G/R offset deltas.
* **What Is NOT Saved:**
    * Avatar meshes or private scene objects (ensuring clean portability).
    * Heavy volatile simulation mesh caches.
* **Storage Location:** Saved garments are stored in Blender's user configuration directory:
  ```
  [Blender User Data]/devil_designer/garments/
  ```

---

## Saving a Garment

1. Open the **Library** panel from the contextual workspace.
2. Click **Save garment**.
3. Enter a unique name for your design.
4. Click confirm to write the garment definition to disk.

---

## Loading & Cross-Avatar Refitting

To load an existing garment onto a new or different character avatar:

1. Select your target character mesh in the 3D Viewport.
2. In Devil Designer, ensure the body is active via **Garment > Body** (or click **Use selected body**).
3. Open the **Library** view:
    * The browser displays up to 8 garments per page with smooth scrolling and instant page buttons.
4. Locate your desired garment.
5. (Optional) Check **Scale by body height**:
    * When enabled, pattern dimensions are scaled proportionally based on the height ratio between the original and new avatars.
    * Pattern shapes, relative proportions, and UV coordinates are preserved without distortion.
6. Click **Load**.

### Resolving 3D Arrangement on the New Avatar
* Matching arrangement points on the new avatar's bounding volumes resolve automatically.
* If the new avatar lacks a specific volume or arrangement point, that piece gracefully falls back to its flat 2D layout position with an on-screen status message.
* Tacks automatically remap to the new avatar's surface bounds.

### Safety Snapshot & Undo
Loading a library garment over an existing open design automatically captures an immediate safety snapshot (`scene['dd_backup_document']`). You can press <kbd>Ctrl</kbd> + <kbd>Z</kbd> immediately to revert the load and restore your previous work.

---

## Document Versioning & Backward Compatibility

* **Document Version 4:** Current format storing Bezier curves, stable segment IDs, arrangement point IDs, relative transforms (G/R deltas), pattern-space source bounds for cut parent tracking, and per-piece simulation flags.
* **Legacy Formats (Versions 1–3):** Older garments created with circular volumes, ray placement, manual wrap radius, or named Bodice/Sleeves/Skirt layouts automatically migrate on load, preserving pattern outlines, legacy placements, and sewing connections.

---

## Saving and `.blend` File Compatibility

Devil Designer integrates non-destructively with Blender's standard save system:

* **What Is Serialized:** Saving your `.blend` file normally saves all versioned Bezier source paths, sewing ranges, constraints, fabric presets, UV layouts, avatar selection, editor placement, kept meshes, and drafting undo/redo history (`scene.dd_document` and `scene.dd_history`).
* **Dual Undo Architecture:**
    * **Inside the Editor:** Pressing <kbd>Ctrl</kbd> + <kbd>Z</kbd> and <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Z</kbd> steps through internal 2D pattern geometry and seam history (up to 100 transactional edits in `dd_history`), completely isolated from scene object operations.
    * **In the 3D Viewport:** Blender's native undo operates on 3D scene objects and mesh evaluations.
* **Non-Destructive Reloading:** Reopening the `.blend` file restores your complete editable vector patterns and arrangement states. If external mesh edits alter topology, sewing that requires repair is reported without corrupting the file.
