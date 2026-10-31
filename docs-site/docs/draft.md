# Drafting & Pattern Editing

Devil Designer provides a dedicated 2D vector CAD drafting environment for garment patterns. The source patterns are stored as editable cubic Bezier paths, completely independent of the 3D simulation mesh.

---

## Drafting Tools & Shortcuts

| Tool / Action | Shortcut | Description |
| :--- | :--- | :--- |
| **Select** | <kbd>V</kbd> | Select pieces, points, handles, seam badges, and internal lines. Drag within a piece to move it. |
| **Polygon** | <kbd>P</kbd> | Click sequential vertices to draft freeform outlines. Press <kbd>Enter</kbd> or click the starting point to close. |
| **Rectangle** | <kbd>R</kbd> | Click and drag to create rectangular panels. |
| **Ellipse** | <kbd>E</kbd> | Click and drag to draft elliptical panels (constructed with four Bezier anchors). |
| **Internal Line** | <kbd>I</kbd> | Draw internal lines, holes, slits, or construction guides inside the selected piece. |
| **Cut Knife** | <kbd>N</kbd> | Slice across pieces with **Cut & Sew** (default) or **Cut only**. |
| **Dart** | <kbd>D</kbd> | Create self-closing V-darts on outer boundaries. |
| **Sew** | <kbd>J</kbd> | Segment sewing in 2D or 3D. |
| **Free Sewing** | <kbd>Shift</kbd> + <kbd>J</kbd> | 4-click partial range sewing. |
| **Pin / Tack** | <kbd>K</kbd> / <kbd>T</kbd> | Add 3D static pins (<kbd>K</kbd>) or surface-following avatar tacks (<kbd>T</kbd>). |
| **Corner / Curve** | <kbd>C</kbd> | Toggle selected anchor point between sharp corner and smooth Bezier curve. |
| **Split Segment** | <kbd>Q</kbd> | Insert a new anchor point by dividing the selected edge segment. |
| **Merge Points** | <kbd>M</kbd> | Merge two adjacent selected points into one. |
| **Unfold** | <kbd>U</kbd> | Mirror and merge the piece along a selected straight edge without a seam. |
| **Mirror with Seam**| <kbd>Shift</kbd> + <kbd>U</kbd>| Create a separate mirrored piece and generate a sewing connection. |
| **Lengths Toggle** | <kbd>L</kbd> | Show/hide live numerical segment lengths (in cm). |
| **Duplicate** | <kbd>Shift</kbd> + <kbd>D</kbd>| Duplicate selected points, paths, or pieces. |
| **Delete** | <kbd>X</kbd> or <kbd>Del</kbd>| Delete selected points, edges, seams, or pieces. |
| **Grid Snapping** | <kbd>S</kbd> | Toggle grid snapping. Hold <kbd>Ctrl</kbd> for temporary inversion. |
| **Axis Constraint**| Hold <kbd>Shift</kbd> | Lock drafting movement to horizontal or vertical axes. |
| **Pan / Zoom** | <kbd>MMB</kbd> / Wheel | Pan and zoom canvas. |
| **Fit Design** | <kbd>Home</kbd> | Frame all patterns within view (or press <kbd>F</kbd> when Fit Map is off). |
| **Avatar Guide** | <kbd>H</kbd> | Toggle the 2D background avatar silhouette guide. |
| **Cancel / Exit** | <kbd>Escape</kbd> | Cancels active drawing/gesture &rarr; dismisses menu &rarr; exits editor. |

---

## Bezier Curve Editing & Numeric Accuracy

Devil Designer uses true cubic Bezier curves rather than faceted polylines:

* **Anchor Points & Handles:** Click an anchor point to select it. When converted to a curve point (<kbd>C</kbd>), smooth gold Bezier handles appear. Drag either handle to adjust curvature.
* **Exact Dimensions in Centimetres:** Dimensions and segment lengths are displayed in centimetres (while internal coordinates use metres).
* **Live Arc-Length Integration:** Curve lengths are calculated using numerical Bezier arc-length integration, updating in real time as handles move.
* **Exact Numeric Edits:** Right-click an anchor point or segment to enter exact numerical coordinates (**Point X/Y**) or define an **Exact length**. When setting an exact length, you choose which endpoint remains anchored and which side adjusts.

---

## Outline Transformations

### Offset Outline Copy
Creates a concentric, editable outline offset at a specified distance from the original piece.
* The original piece is preserved.
* Concave corners and curved offsets are sampled and validated.
* Self-intersecting or collapsed results are cleanly rejected without altering the pattern.

### Unfold (<kbd>U</kbd>)
Select a straight boundary edge and press <kbd>U</kbd>. The piece is reflected across that edge and fused into a single seamless pattern island.

### Mirror with Seam (<kbd>Shift</kbd> + <kbd>U</kbd>)
Select a straight boundary edge and press <kbd>Shift</kbd> + <kbd>U</kbd>. A separate mirrored piece is generated, and a matching sewing seam is automatically created between the mirroring edge and its counterpart. Any existing self-sewing darts are duplicated and preserved.

---

## Linked Editing

For symmetrical pattern drafting (e.g. left and right sleeves, front panels), Devil Designer provides bidirectional **Linked Editing**:

* **Clone as Linked Twin:** Right-click a piece and choose **Clone as linked twin**. A linked mirrored copy appears to the right of the pattern layout without overlapping existing islands.
* **Clone as Back:** For pieces already placed at a front avatar arrangement point, choosing **Clone as Back** creates a linked copy and automatically assigns it to the corresponding back arrangement point on that same volume.
* **Bidirectional Synchronization:** Edits made to either member immediately reflect on the other:
    * Moving anchor points and Bezier handles
    * Toggling corner vs curve (<kbd>C</kbd>)
    * Adding (<kbd>Q</kbd>), merging (<kbd>M</kbd>), or deleting points
    * Modifying internal paths and darts
* **Independent Transforms:** 2D canvas placement and 3D avatar arrangement remain completely independent between twins.
* **Managing Links:**
    * **Linked twin Off:** Temporarily pause synchronization without altering either outline.
    * **Linked twin On:** Re-apply synchronization from the active piece onto the twin.
    * **Link Two Existing Pieces:** Select two unpaired pieces, right-click, and choose **Linked twin**. The active piece provides the master outline. Relinking is safely refused if it would invalidate existing sewing seams.
    * **Linking never alters sewing:** Linking or unlinking twins never automatically creates, copies, or removes sewing seams.

---

## Internal Lines, Cuts, Slits, & Darts

Press <kbd>I</kbd> to activate the **Internal** tool on a selected piece.

### Internal Shapes & Holes
* Draw closed shapes inside a pattern piece.
* Right-click the closed internal path and choose **Cut selected internal path** to convert it into a through-hole.
* Choose **Trace** to extract a closed internal shape into an independent pattern piece.

### Cut Knife (<kbd>N</kbd>)
The Cut tool allows splitting pieces directly across their surface:
* **Modes:** **Cut & Sew** (default; creates matching seam across the cut) or **Cut only** (separates pieces without sewing).
* **Usage:** Click two or more points across a pattern piece, crossing its outer boundary exactly twice. Press <kbd>Enter</kbd> or double-click to finish.
* **Result:** Splits the piece into `Piece 1` and `Piece 2`. Both halves retain original fabric settings, mesh density, and their exact source-space UV layout.
* **Conflict Resolution:** If a straight cut crosses existing straight open internal lines, Devil Designer offers **Split and retry** to stage the split and cut cleanly in one undoable transaction.

### Princess Seams & Slits
* An open internal line that runs from boundary to boundary acts as a seam line for splitting (e.g. princess seams).
* An internal line terminating inside the fabric forms a **slit**, generating separated mesh lips during cloth simulation.

### Darts (<kbd>D</kbd>)
The dedicated Dart tool creates tailored tapering:
1. Click two positions along an outer boundary segment to establish the dart mouth.
2. Click an interior position to establish the dart apex.
3. Devil Designer notches out the V-shape and automatically configures a same-piece self-closing seam pair along the legs. The common apex is mathematically handled to prevent degenerate zero-length simulation springs.

---

## Tracing Reference Images

To draft from reference photographs or fashion flats:

1. Right-click the canvas and choose **Garment > Reference image > Load image**.
2. Position the image and adjust its opacity using its contextual card.
3. Under **Set measured scale**, choose **Pick length endpoints**, then click two known points on the image (e.g., center-front length or ruler mark) and enter the physical distance in centimetres.
4. The reference image scales precisely to real-world dimensions. Existing pattern geometry is never altered by scale calibration.
