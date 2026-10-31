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
* **Regenerate Body Volumes:** If you scale, edit, or replace the avatar mesh, choose **Regenerate body volumes** in the body picker to remeasure volume dimensions.

---

## Wrapping Panels onto Arrangement Points

To wrap a 2D pattern piece around a body volume:

1. Reveal the 3D viewport.
2. Select the pattern piece in 2D or 3D.
3. Ensure arrangement points are visible (<kbd>H</kbd>).
4. Click a blue **Arrangement Point** (e.g., Chest Front, Chest Back, Upper Arm, Waist, Thigh).
5. The panel wraps around that volume:
    * Wrapping interpolates elliptical radii at each mesh row's height.
    * A radial clearance buffer prevents immediate surface intersection.
    * Pieces wider than the volume circumference wrap into an outward spiral with distinct turns.

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
* **Topology Validation:** Tacks monitor avatar topology. If the underlying mesh changes unexpectedly, Devil Designer flags the tack for reattachment rather than allowing it to drift erratically.

### Removing Pins & Tacks
* Right-click any pin or tack and select **Remove pin / tack**.
* Alternatively, select the anchor with <kbd>K</kbd> or <kbd>T</kbd> and press <kbd>Delete</kbd>.
* Deleting an anchor deletes only the constraint, never the underlying garment piece.
