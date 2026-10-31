# 3D Placement & Avatar Arrangement

Devil Designer bridges 2D pattern drafting and 3D simulation by maintaining **live 3D panels** that mirror your 2D pattern shapes, paired with an anatomical avatar bounding-volume system for quick wrapping.

---

## Live 3D Panels

* **Automatic Generation:** The moment a 2D pattern shape is closed, a flat 3D panel is generated in front of your avatar reference at real-world physical scale.
* **Continuous Synchronization:** Moving, modifying Bezier handles, cutting, or resizing a piece in 2D immediately updates its 3D panel. Deleting a piece removes its panel.
* **Arrangement is Optional:** You do not have to wrap panels around the avatar to simulate. Flat panels can drape directly if desired.

---

## Avatar Reference & Bounding Volumes

### Selecting the Avatar
1. Right-click empty canvas and choose **Garment & View > Body**, or select your character mesh in the 3D Viewport and click **Use selected body**.
2. Devil Designer measures the evaluated mesh at physical scale, taking armature modifiers, active shape keys, and scene transforms into account.
3. Press <kbd>H</kbd> to toggle visibility of the avatar silhouette in 2D and the bounding volumes/points in 3D.

### Elliptical Bounding Volumes
Devil Designer automatically slices the evaluated avatar mesh into anatomical regions:
* **Regions:** Neck, Chest, Waist, Hip, Upper Arms, Forearms, Thighs, and Calves.
* **Elliptical Sections:** Volumes use fitted elliptical cross-sections with independent width and depth radii measured directly from the mesh slices. No rigging, bones, or vertex groups are required.
* **Format Versioning:** New body setups use format-2 elliptical sections. Existing format-1 circular setups from earlier versions are preserved on opening; re-arranging one piece upgrades only that piece, while regenerating explicitly replaces setup for all pieces. Garment document format remains version 4.
* **Regenerate Body Volumes:** If you scale, edit, or replace the avatar mesh, choose **Regenerate body volumes** in the body picker to remeasure volume dimensions (this explicitly resets manual point and volume edits).

---

## Wrapping Panels onto Arrangement Points

To wrap a 2D pattern piece around a body volume:

1. Reveal the 3D viewport.
2. Select the pattern piece in 2D or 3D.
3. Ensure arrangement points are visible (<kbd>H</kbd>).
4. Click a blue **Arrangement Point** (e.g., Chest Front, Chest Back, Upper Arm, Waist, Thigh).
5. The panel wraps around that volume:
    * Wrapping follows an interpolated ellipse at each mesh row's own height across neighboring torso, arm, or leg volumes, with radial clearance.
    * Pieces wider than the volume circumference wrap into an outward spiral with distinct successive turns.
    * Anatomical section detection is heuristic; missing sections use body-extents fallback ellipses, and rows beyond the sampled stack retain terminal dimensions. There is no body surface projection; inspect starting placement before draping.
    * Template specifics: The Tee uses integrated sleeve outlines rather than separate sleeve panels; Tee/Tank fronts and backs use explicit chest points, and Skirt uses waist points.
    * **Cutting arranged pieces:** Cutting an arranged or legacy piece preserves both halves' 3D placement. Neither arranging nor cutting repacks UVs or rewrites the source outline's layout.

### Fine-Tuning Placement
* **Blender Transforms (<kbd>G</kbd> / <kbd>R</kbd>):** After wrapping, use Blender's standard <kbd>G</kbd> (Grab) and <kbd>R</kbd> (Rotate) shortcuts inside the 3D view to shift or angle the panel. These offsets are saved as relative delta records.
* **Resetting Deltas:** Clicking the arrangement point again resets all manual transform deltas.
* **Arrangement Point Menu:** Right-click an arrangement point to access:
    * **Arrange flat:** Positions the panel tangent to the volume without curved bending.
    * **Move point / Add point / Delete point:** Customize point layout for unique clothing styles.
    * **Edit bounding volume:** Tweak volume radius and height bands.
* **Reset to 2D layout:** On the piece contextual menu, choose **Reset to 2D layout** to clear arrangement deltas and return the piece to its flat reference position.
* **Reset drape:** Clears the simulation cache while keeping all 3D panel arrangements intact.

---

## Anchors: Pins & Tacks

Anchors hold cloth in place during simulation to prevent garments from slipping off shoulders, waists, or moving limbs.

### Static Pins (<kbd>K</kbd>)
* **Usage:** Press <kbd>K</kbd> and click a point on a pattern piece in 2D or 3D.
* **Behavior:** Locks that vertex position in world space. Pins remain fixed in 3D regardless of avatar motion.

### Pose-Stable Avatar Tacks (<kbd>T</kbd>)
* **Usage:** Press <kbd>T</kbd>, click a fabric anchor point on the piece, then click a target point on the 3D avatar surface.
* **Behavior:** Binds the cloth point to the nearest avatar mesh triangle using native Hook and vertex-parenting constraints.
* **Animation-Ready:** As the avatar deforms through bone poses, armatures, and shape keys, the tack moves faithfully with the skin surface.
* **Topology Validation:** Tacks monitor avatar topology. If the underlying mesh changes unexpectedly, Devil Designer flags the tack for reattachment rather than allowing it to drift erratically. Disable topology-changing modifiers before binding.
* **Compatibility:** Older tacks bind once at their current resolved position; reattach an already misplaced legacy tack. A replacement avatar uses the retained portable target.

### Removing Pins & Tacks
* Right-click any pin or tack and select **Remove pin / tack**.
* Alternatively, select the anchor with <kbd>K</kbd> or <kbd>T</kbd> and press <kbd>Delete</kbd>.
* Deleting an anchor deletes only the constraint, never the underlying garment piece.

---

## Arrangement Display & Action-Time Performance

Devil Designer optimizes viewport responsiveness through aggressive geometric and GPU batch caching:

### 3D Guide Display Caching
The 3D avatar guide display (<kbd>H</kbd>) caches unchanged world geometry and GPU batches:
* **Orbiting & Projection:** Orbiting updates projection matrices rather than re-resolving volume radii or rebuilding a batch per point.
* **Cache Invalidation:** Point/volume edits and evaluated avatar frame changes invalidate the display cache; the display never re-slices the mesh during redraw.
* **Benchmarks:** See `reports/ARRANGEMENT_DISPLAY_PERFORMANCE.md` for measured before/after results (reproducible via `python tools/dev.py --arrangement-performance current --keep-scratch`).

### Action-Time Caching
* **Live-Panel Invalidation:** Live-panel edits reuse unaffected panels with explicit geometry, sewing, UV, and placement invalidation, while retaining a full-rebuild fallback.
* **Exact-Input Wrap Cache:** Repeated wrapping uses a bounded exact-input cache.
* **Latency Profile:** On a six-panel test rig, median pin, duplicate, and move actions take ~37–39 ms, and unused arrangement-point edits take ~13 ms. Cold affected-piece wraps and initial guide refreshes may still hitch.
* **Profiling Report:** See `reports/ACTION_TIME_PERFORMANCE.md` for the full 28-condition profile (reproducible via `python tools/dev.py --action-performance current --keep-scratch`).
