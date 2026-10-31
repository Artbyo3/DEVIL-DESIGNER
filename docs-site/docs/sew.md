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

### 3D Click Validation & Redraw Performance
To prevent accidental sewing mistakes:
* **Ambiguous Clicks Refused:** Shared corner vertices, overlapping visible edges, and overlapping seam selections refuse ambiguous clicks rather than guessing a neighbor. Zoom in or orbit the camera to separate edges.
* **Occlusion Culling:** Edges hidden behind the body or obscured behind another panel cannot be accidentally clicked.
* **Active Drape / Kept Meshes:** Kept meshes and active simulation drapes cannot be sewn. **Pause simulation** before sewing in 3D.

During development, the scratch prototype resolved 20/20 representative front/back chest edge clicks and rejected both shared-corner checks. A segment seam and an M:N free seam had zero record and compiled-mesh differences against equivalent 2D records, with independently generated seam IDs normalized.

On a 36,300-vertex synthetic avatar with 12 volumes, cached seam preview plus arrangement display averaged **0.105 ms/redraw display CPU** across three 120-redraw runs, versus the supplied 0.423 ms historical baseline. The same-run arrangement-only mean was 0.082 ms, so preview added about 0.024 ms (display CPU timings, not end-to-end interaction or frame times). The production preview, remeasured with six panels and two seams on the same 36,300-vertex, 12-volume fixture, averaged **0.100 ms/redraw** (0.073 ms without preview). Original-master comparison also checks exact 2D records and compiled geometry for layout, flat, wrapped, click-placed, and manually transformed wrapped panels.

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
* **Reversed B direction:** Seam arrows point in opposing directions (a reversed direction is not necessarily wrong; inspect the endpoint arrows).
* **Partial / middle-only coverage:** Seam covers a sub-segment.
* **Uneven-ease risk:** Disproportionate distribution across multi-edge chains.
* **Observed edits:** Flagged when underlying geometry changed after seam creation.
* **Unavailable state:** Displayed if panel geometry is stale, pending rebuild; no midpoint-only or approximate pairing is substituted. Deactivated seams have no active links.

The preview does not run simulation or alter your sewing records. Historical edit intent cannot be recovered after reopening an existing file. For detailed diagnostic validation and the 424-pair initialized native rest-length parity gate, see `reports/SEWING_DIAGNOSIS.md`.

---

## Seam Shrink (Elastic Cuffs & Waistbands)

Apply localized fabric contraction to cuffs, necklines, or waistbands without altering the flat pattern or UV layout:

1. Right-click any seam badge.
2. Choose **Shrink: 0%, 10%, 20%, or 30%**.
3. The choice is undoable and persists with saved designs, library loads, and blend save/reopen.
4. Both sewn sides receive localized fabric shrink; sewing connections and sewing force are unchanged.
5. If multiple seams share a vertex, the largest Shrink setting takes precedence, independently of seam order.
6. Reverse and partial/chained sewing retain the setting. Shrink does not modify the flat pattern or its UV coordinates.

### Opt-In Simulation Cost & Collision Distance
When any seam in a garment has a non-zero Shrink setting:
* The simulation engine automatically reduces self-collision distance from **3 mm down to 1 mm**.
* This tighter collision allows realistic gathering folds without seam explosion, but may visibly change folds even away from the seam.
* Garments with 0% Shrink across all seams retain the standard 3 mm collision distance and bypass the shrink calculation hook entirely.
* Changing the shrink setting invalidates the simulation cache; reset or resimulate to evaluate the updated drape.

### Calibration Data & Measurements

Native boundary weights are measured calibration data, not literal shrink percentages: `shrink_min` is 0, `shrink_max` is 0.60. Cotton cylinder tests use paired same-frame lengths against a diagnostic zero reference at the same 1 mm collision setting (which is not the normal 3 mm all-zero garment). Frame 481 supplied calibration data; frames 482 through 601 were held out. Each sewn side passed ±1 percentage point; final 61-frame variation stayed below 0.25 pp.

| Rig | Setting | Weight | Frame 481 A / B | Frame 601 A / B |
| :--- | :--- | :--- | :--- | :--- |
| **Waistband** | 10% | 0.18440000 | 9.44860 / 9.46699% | 9.44860 / 9.46698% |
| **Waistband** | 20% | 0.35871667 | 20.90911 / 20.91694% | 20.90910 / 20.91692% |
| **Waistband** | 30% | 0.53130000 | 30.52588 / 30.58664% | 30.51950 / 30.57705% |
| **Cuff** | 10% | 0.18440000 | 10.51972 / 10.52396% | 10.51984 / 10.52403% |
| **Cuff** | 20% | 0.35871667 | 19.50710 / 19.66611% | 19.50767 / 19.66628% |
| **Cuff** | 30% | 0.53130000 | 29.73231 / 30.04095% | 29.73148 / 30.04536% |

At the same 20% Shrink and identical boundary weights, changing collision distance from 3 mm to 1 mm moved unweighted cloth at frame 601 by **14.514 mm RMS / 44.365 mm maximum** on the waistband and **6.768 mm RMS / 18.754 mm maximum** on the cuff (excluding pins and a 20 mm / 12 mm band around the seam respectively). Inspect neighboring folds when opting in.
