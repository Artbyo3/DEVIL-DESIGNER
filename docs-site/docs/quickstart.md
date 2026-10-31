# Quickstart: Panel > Sew > Simulate

This quickstart guides you through drafting a simple two-piece top, sewing its edges, draping it around an avatar, and keeping the finalized mesh.

The default workflow centers on three main steps: **Panel > Sew > Simulate**.

---

## Step 1: Open Devil Designer

1. In Blender, switch to a 3D Viewport containing your character avatar.
2. Press <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>D</kbd> (or go to **View > Devil Designer**).
3. The editor opens in full-screen 2D canvas mode.

---

## Step 2: Select the Avatar Reference

1. Right-click anywhere on the empty canvas to open the **Garment & View** contextual menu.
2. In the **Body** picker, select your avatar mesh, or select the mesh in the 3D viewport beforehand and click **Use selected body**.
3. Press <kbd>H</kbd> to toggle the avatar silhouette guide on the 2D canvas. The evaluated mesh is projected at physical scale with limb proportions preserved.

---

## Step 3: Create Pattern Panels

You can start drafting in two ways:

* **One-Click Starter:** On an empty canvas, click **Create panel** to spawn a 40 x 45 cm starter rectangle.
* **Custom Drafting:**
    * Press <kbd>R</kbd> to activate the **Rectangle** tool and drag out a panel.
    * Press <kbd>P</kbd> to activate the **Polygon** tool and click boundary points. Press <kbd>Enter</kbd> or click the starting point to close the shape.
    * Press <kbd>E</kbd> for the **Ellipse** tool.

### Creating a Mirrored Twin

For symmetrical garments (such as front/back or left/right panels):

1. Right-click the newly created panel.
2. Select **Clone as linked twin**.
3. A linked, mirrored twin is generated to the right of your original pattern without overlapping it. Any edits made to the outline, Bezier handles, or internal lines on one piece will automatically mirror to the other.

---

## Step 4: Arrange Panels Around the Body (Optional)

Every closed 2D piece automatically generates a flat 3D panel positioned in front of your avatar. Arrangement is optional, but wrapping gives cleaner starting drape:

1. Click the 3D viewport split or reveal button to view the 3D avatar.
2. Ensure arrangement points are visible (toggle with <kbd>H</kbd>).
3. Select your front piece, then click the blue **Chest Front** arrangement point on the avatar guide. The piece instantly wraps around the chest volume.
4. Select your back piece, right-click, and choose **Clone as Back** (or select an existing back piece and click the **Chest Back** arrangement point).
5. Use Blender's standard <kbd>G</kbd> (grab) and <kbd>R</kbd> (rotate) shortcuts inside the revealed 3D view to adjust panel placement if needed.

---

## Step 5: Sew the Seams

You can sew seams either in the **2D pattern canvas** or directly on **visible 3D live panels**:

1. Press <kbd>J</kbd> to activate **Segment Sewing**.
2. Click the shoulder seam edge on Panel A, then click the corresponding shoulder edge on Panel B.
3. Repeat for the side seams.
4. Observe the seam indicators:
    * Direction arrows show seam correspondence.
    * If seam directions are mismatched, hover over the seam and press <kbd>B</kbd> or right-click the seam badge and choose **Reverse seam**.
    * A green **Pass** indicator means segment lengths match within 1%. If lengths differ, an amber **Gather warning** appears. This is non-blocking: intentional gathers and ruffles simulate normally.

---

## Step 6: Simulate the Drape

1. In the bottom bar, click **Simulate**.
2. The 3D view reveals automatically and Blender's native cloth physics drapes the garment around the avatar.
3. To freeze the simulation on a desired frame, click **Pause**.
4. Press <kbd>F</kbd> (or click the dock's **[F]** chip) to toggle the **Fit Map**:
    * **White:** Neutral rest length (within &plusmn;3%).
    * **Blue:** Compression (fabric under compression).
    * **Red:** Stretch (fabric under tension).

---

## Step 7: Keep the Final Mesh

1. With the simulation paused on the desired frame, click **Keep mesh** in the bottom bar.
2. (Optional) Click the arrow on **Keep mesh** to adjust:
    * **Thickness:** None, Thin, or Standard (adds an editable Solidify modifier).
    * **Auto weld:** Automatically welds paired seam vertices within distance tolerance.
3. A finalized, editable Blender mesh object is created in the scene, containing:
    * Clean 1:1 UV coordinates mapped from the flat 2D layout.
    * Piece face identifiers and vertex groups for material assignment.
    * Welded seams ready for sculpting or texturing in Substance 3D Painter.

---

## Step 8: Save Your Work

Save the `.blend` file normally. Devil Designer stores all Bezier vector data, sewing relationships, arrangement records, fabric presets, and up to 100 transactional undo/redo steps directly inside the Blender file.
