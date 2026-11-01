# Drafting & Pattern Editing

Use these tools to create and edit garment pattern pieces. A Bezier curve is a smooth line shaped by moving its points and handles.

## Make Your First Pattern Piece

1. Open an empty design and press <kbd>R</kbd> for the Rectangle tool.
2. Click and drag to draw one simple piece.
3. Press <kbd>V</kbd> to select it and move it into place.
4. Save your Blender file when you are happy with the shape.

## Drafting Tools & Shortcuts

| Tool / Action | Shortcut | Description |
| :--- | :--- | :--- |
| **Select** | <kbd>V</kbd> | Select seams; select and move pieces, points, handles, and internal lines. |
| **Polygon** | <kbd>P</kbd> | Click outline points; press <kbd>Enter</kbd> or click the first point to close. |
| **Rectangle** | <kbd>R</kbd> | Click and drag to create a rectangular piece. |
| **Ellipse** | <kbd>E</kbd> | Click and drag to create an oval piece. |
| **Internal Line** | <kbd>I</kbd> | Draw lines, openings, or guides inside a piece. |
| **Cut Knife** | <kbd>N</kbd> | Cut a piece, with or without a seam along the cut. |
| **Dart** | <kbd>D</kbd> | Add a tapered dart to a piece. |
| **Sew** | <kbd>J</kbd> | Connect complete edges. |
| **Free Sewing** | <kbd>Shift</kbd> + <kbd>J</kbd> in 3D | Connect part of an edge in the revealed 3D Viewport. |
| **Pin / Tack** | <kbd>K</kbd> / <kbd>T</kbd> | Hold a piece in place or attach it to the avatar. |
| **Corner / Curve** | <kbd>C</kbd> | Cycle Corner, Smooth, and Auto. |
| **Split Segment** | <kbd>Q</kbd> | Add a point on an edge. |
| **Merge Points** | <kbd>M</kbd> | Join two neighboring selected points. |
| **Unfold** | <kbd>U</kbd> | Mirror a piece across a straight edge. |
| **Mirror with Seam** | <kbd>Shift</kbd> + <kbd>U</kbd> | Make a separate mirrored piece and connect the edges. |
| **Lengths Toggle** | <kbd>L</kbd> | Show or hide edge lengths in centimetres. |
| **Duplicate** | <kbd>Shift</kbd> + <kbd>D</kbd> | Copy selected pieces or the active piece. |
| **Delete** | <kbd>X</kbd> or <kbd>Del</kbd> | Remove the selected item. |
| **Grid Snapping** | <kbd>S</kbd> | Turn grid snapping on or off. Hold <kbd>Ctrl</kbd> to reverse it temporarily. |
| **Axis Constraint** | Hold <kbd>Shift</kbd> | Keep movement horizontal or vertical. |
| **Pan / Zoom** | <kbd>MMB</kbd> / Wheel | Move around or zoom the canvas. |
| **Fit Design** | <kbd>Home</kbd> | Show all pattern pieces in the canvas. |
| **Avatar Guide** | <kbd>H</kbd> | Show or hide the avatar guide. |
| **Cancel / Exit** | <kbd>Escape</kbd> | Cancel the current action, close a menu, or exit the editor. |

## Bezier Curve Editing & Numeric Accuracy

Select a point and press <kbd>C</kbd> to make it a smooth curve. Drag its handles to change the shape. Right-click a point or edge to enter an exact position or length in centimetres.

<figure class="dd-shot" id="shot-draft-bezier-editing" data-shot='{"action":"Edit Bezier curve handles and enter numeric coordinates","ui_state":"Smooth curve point with two control handles and open right-click coordinate menu","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-draft-bezier-editing-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-draft-bezier-editing-caption">Close-up view of a smooth curve control point with dual handles and the right-click numeric coordinate popup menu.</figcaption>
</figure>

## Outline Transformations

### Unfold (<kbd>U</kbd>)

Select a straight edge and press <kbd>U</kbd> to mirror the piece across that edge.

### Mirror with Seam (<kbd>Shift</kbd> + <kbd>U</kbd>)

Select a straight edge and press <kbd>Shift</kbd> + <kbd>U</kbd> to make a separate mirrored piece with the matching edges already sewn.

<figure class="dd-shot" id="shot-draft-mirror-with-seam" data-shot='{"action":"Generate a mirrored piece connected with a sewn seam","ui_state":"Mirrored separate pattern pieces with matching boundary edges joined by an active seam","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-draft-mirror-with-seam-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-draft-mirror-with-seam-caption">Full-editor view showing separate mirrored pattern pieces created across an axis with matching seam connections already established.</figcaption>
</figure>

## Linked Editing

Right-click a piece and choose **Clone as linked twin** to make a mirrored copy. Changes to either linked piece are reflected in the other. Turn **Linked twin** off when you want to edit the pieces separately.

## Internal Lines, Cuts, Slits, & Darts

Press <kbd>I</kbd> to draw inside a selected piece. Closed shapes can be cut out or traced as a separate piece. Use **Cut along path** on a line to split the piece or make a slit.

### Internal Shapes & Holes

Draw a closed shape inside a piece. Right-click it and choose **Cut along path** to make a hole, or **Trace as piece** to make a separate piece.

### Cut Knife (<kbd>N</kbd>)

In the Internal tool menu, choose **Cut & Sew** or **Cut only** first. Click points across a piece, crossing its outline twice, then press <kbd>Enter</kbd> to cut. Press <kbd>Escape</kbd> to cancel.

### Princess Seams & Slits

Draw a line, then right-click it and choose **Cut along path**. An edge-to-edge line splits the piece; a line ending inside makes a slit.

### Darts (<kbd>D</kbd>)

Click two points on the same outer segment for the dart opening, then click inside the piece for the dart point.

### Fold Lines & Pleats

1. Select a pattern piece and press <kbd>I</kbd> for **Internal path**.
2. Click the start and end of a straight line, from one boundary of the piece to the other, then press <kbd>Enter</kbd> to finish the path.
3. Right-click the internal edge and choose **Fold or pleat**.
4. Choose **Mountain** or **Valley** for a single fold. For a pleat, choose **Knife 1 cm**, **Knife 2 cm**, or **Knife 4 cm**, or **Box 1 cm**, **Box 2 cm**, or **Box 4 cm**. The spacing is the distance between paired fold lines, not the width of the finished pleat. Leave enough fabric beside the path for the added lines.
5. Check the arrows and Mountain or Valley labels on the canvas before simulation. They show the fold direction and angle.

To adjust a fold, right-click one of its internal edges and open **Fold or pleat** again:

- **Reverse direction** reverses the entire fold or pleat, not just the selected line.
- **60 degrees** or **120 degrees** changes the fold angle; **Sharp fold** sets it to 150 degrees. These choices apply to the entire pleat and preserve each line's Mountain or Valley direction.
- **Remove fold or pleat** removes the settings for the entire fold or pleat but keeps its internal paths.

Continue with sewing, arrangement, simulation, and keeping the mesh. Fold settings are saved with the pattern in the garment library and Blender file, and are included in undo and redo.

<figure class="dd-shot" id="shot-draft-fold-pleats" data-shot='{"action":"Configure internal fold lines and pleat directions","ui_state":"Parallel pleat lines with Mountain and Valley arrows and labels across valid boundary path","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-draft-fold-pleats-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-draft-fold-pleats-caption">Close-up view of parallel pleat paths displaying Mountain and Valley directional indicators, angle settings, and valid boundary-to-boundary lines.</figcaption>
</figure>

#### Current Limits

Only straight, open, boundary-to-boundary fold paths are supported. All folds on a piece must be parallel. Curved, partial, crossing, and hole-crossing folds are not supported; a fold also cannot cross a gap in a concave piece. Folded pieces use flat placement at arrangement points rather than automatic wrapping around the body.

When self-collision is enabled, a garment containing any folds uses **1 mm clearance for every piece in that simulation**, including pieces without folds. Garments without folds use **3 mm**, unless a nonzero seam shrink setting already requires 1 mm. The smaller clearance allows closer layers, so inspect the whole garment, not just its pleats.

Folds can relax under load during cloth simulation. Fabric, mesh density, pins or tacks, and simulation duration still affect the result; folds use the same cloth simulation as the rest of the garment.

#### Darts & Fold Lines

Fold settings do not change how darts are made or add a dart-depth cap. A deep dart can approach the opposite edge, but its point must stay inside the fabric. Do not pin both ends of the dart opening apart if you want it to close during simulation.

## Tracing Reference Images

1. Right-click the canvas, open **Garment settings > Trace image**, then choose **Load image**.
2. Place the image and adjust its opacity.
3. Open **Set measured scale** and set **Known length** in centimetres.
4. Choose **Pick length endpoints**, then click two known points to set the image scale.

<figure class="dd-shot" id="shot-draft-trace-reference" data-shot='{"action":"Calibrate reference image scale with known-length endpoints","ui_state":"Loaded trace image with calibration endpoints and scale numeric input controls","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-draft-trace-reference-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-draft-trace-reference-caption">Close-up view of the loaded reference image overlay showing picked calibration endpoints and measured scale dimension inputs.</figcaption>
</figure>
