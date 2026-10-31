# Sewing System

Devil Designer features a unified sewing architecture that operates identically across the **2D pattern canvas** and directly onto **live 3D panels** in the viewport.

---

## Sewing Modes

### 1. Segment Sewing (<kbd>J</kbd>)
Pair two complete boundary or internal segments:
1. Press <kbd>J</kbd> to activate the Sew tool.
2. Click Edge A.
3. Click Edge B.
4. The two edges are linked with sewing springs. Same-piece segment pairs (e.g., closing darts or wrap seams) are fully supported.

### 2. Free Sewing (<kbd>Shift</kbd> + <kbd>J</kbd>)
Pair partial distances or arbitrary continuous spans across multiple edges using a 4-click workflow:
1. Click **Start point A** on the first edge.
2. Click **End point A** (can span across multiple connected segments).
3. Click **Start point B** on the target edge.
4. Click **End point B**.

The clicked positions are resolved into proportional arc-length ranges, not volatile mesh indices.

### 3. M:N Multi-Segment Chains
Explicitly connect a chain of multiple segments on side A to a chain of multiple segments on side B:
1. Choose **Pick chain A** in the sewing options.
2. Click each edge belonging to chain A in traversal order, then press <kbd>Enter</kbd>.
3. Click each edge belonging to chain B in traversal order, then press <kbd>Enter</kbd> (or click **Sew selected chains**).
4. Use the start and end percentage fields on the seam card to trim chains proportionally if needed.

---

## Direct 3D Viewport Sewing

You can sew panels directly in 3D while viewing the avatar:

1. Reveal the 3D viewport split.
2. Press <kbd>J</kbd> (Segment) or <kbd>Shift</kbd> + <kbd>J</kbd> (Free sewing).
3. Click visible live-panel edges on wrapped, flat-arranged, or click-placed panels.
4. Edge locations follow the actual sampled geometry, including wrapped curves.

### 3D Click Validation Rules
To prevent accidental sewing mistakes:
* **Ambiguous Clicks Refused:** Shared corner vertices, overlapping visible edges, and overlapping seam selections refuse ambiguous clicks rather than guessing a neighbor. Zoom in or orbit the camera to separate edges.
* **Occlusion Culling:** Edges hidden behind the body or obscured behind another panel cannot be accidentally clicked.
* **Active Drape / Kept Meshes:** Kept meshes and active simulation drapes cannot be sewn. **Pause simulation** before sewing in 3D.

---

## Direction, Reversal, & Removal

* **Direction Arrows:** Start markers and paired direction arrows show seam correspondence in both 2D and 3D.
* **Reversing a Seam:**
    * Hover over a seam badge or span and press <kbd>B</kbd>.
    * Right-click the seam badge or sewn edge and select **Reverse seam**.
* **Removing a Seam:**
    * Select a seam badge or edge with Select (<kbd>V</kbd>) or Sew (<kbd>J</kbd>) and press <kbd>X</kbd> or <kbd>Delete</kbd>.
    * Right-click and choose **Remove seam**.
    * <kbd>Ctrl</kbd> + <kbd>Z</kbd> immediately restores removed seams.

---

## Pre-Simulation Preview & Mismatch Warning

Before starting simulation, Devil Designer inspects every compiler-resolved point-to-point link, displaying:
* Live edge lengths for both sides in centimetres.
* Length difference in cm and percentage mismatch.
* Real-time status badges:
    * **Pass:** Edge lengths match within 1%.
    * **Gather Warning (>1% mismatch):** Displayed in amber.

!!! note "Gather Warnings Are Never Hard Blocks"
    A length mismatch is purely informational. In real garment construction, sleeves, ruffles, skirts, and waistbands intentionally have easing and gathers. Devil Designer **never blocks simulation** for length mismatches.

Other contextual indicators displayed on seams:
* **Reversed B direction:** Seam arrows point in opposing directions.
* **Partial / middle-only coverage:** Seam covers a sub-segment.
* **Uneven-ease risk:** Disproportionate distribution across multi-edge chains.
* **Observed edits:** Flagged when underlying geometry changed after seam creation.
* **Unavailable state:** Displayed if panel geometry is stale, pending rebuild.

---

## Seam Shrink (Elastic Cuffs & Waistbands)

Apply localized fabric contraction to cuffs, necklines, or waistbands without altering the flat pattern or UV layout:

1. Right-click any seam badge.
2. Choose **Shrink: 0%, 10%, 20%, or 30%**.
3. The choice is undoable and persists with the blend file and garment library.
4. If multiple seams share a vertex, the highest Shrink setting takes precedence.

### Opt-In Simulation Cost
When any seam in a garment has a non-zero Shrink setting:
* The simulation engine automatically reduces self-collision distance from **3 mm to 1 mm**.
* This tighter collision allows realistic gathering folds without seam explosion, but may subtly affect drape behavior across neighboring fabric.
* Garments with 0% Shrink across all seams retain the standard 3 mm collision distance and bypass the shrink calculation hook entirely.
