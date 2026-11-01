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
| **Select** | <kbd>V</kbd> | Select and move pieces, points, handles, seams, and internal lines. |
| **Polygon** | <kbd>P</kbd> | Click outline points; press <kbd>Enter</kbd> or click the first point to close. |
| **Rectangle** | <kbd>R</kbd> | Click and drag to create a rectangular piece. |
| **Ellipse** | <kbd>E</kbd> | Click and drag to create an oval piece. |
| **Internal Line** | <kbd>I</kbd> | Draw lines, openings, or guides inside a piece. |
| **Cut Knife** | <kbd>N</kbd> | Cut a piece, with or without a seam along the cut. |
| **Dart** | <kbd>D</kbd> | Add a tapered dart to a piece. |
| **Sew** | <kbd>J</kbd> | Connect complete edges. |
| **Free Sewing** | <kbd>Shift</kbd> + <kbd>J</kbd> | Connect part of an edge. |
| **Pin / Tack** | <kbd>K</kbd> / <kbd>T</kbd> | Hold a piece in place or attach it to the avatar. |
| **Corner / Curve** | <kbd>C</kbd> | Change a point between a sharp corner and a smooth curve. |
| **Split Segment** | <kbd>Q</kbd> | Add a point on an edge. |
| **Merge Points** | <kbd>M</kbd> | Join two neighboring selected points. |
| **Unfold** | <kbd>U</kbd> | Mirror a piece across a straight edge. |
| **Mirror with Seam** | <kbd>Shift</kbd> + <kbd>U</kbd> | Make a separate mirrored piece and connect the edges. |
| **Lengths Toggle** | <kbd>L</kbd> | Show or hide edge lengths in centimetres. |
| **Duplicate** | <kbd>Shift</kbd> + <kbd>D</kbd> | Copy selected points, lines, or pieces. |
| **Delete** | <kbd>X</kbd> or <kbd>Del</kbd> | Remove the selected item. |
| **Grid Snapping** | <kbd>S</kbd> | Turn grid snapping on or off. Hold <kbd>Ctrl</kbd> to reverse it temporarily. |
| **Axis Constraint** | Hold <kbd>Shift</kbd> | Keep movement horizontal or vertical. |
| **Pan / Zoom** | <kbd>MMB</kbd> / Wheel | Move around or zoom the canvas. |
| **Fit Design** | <kbd>Home</kbd> | Show all pattern pieces in the canvas. |
| **Avatar Guide** | <kbd>H</kbd> | Show or hide the avatar guide. |
| **Cancel / Exit** | <kbd>Escape</kbd> | Cancel the current action, close a menu, or exit the editor. |

## Bezier Curve Editing & Numeric Accuracy

Select a point and press <kbd>C</kbd> to make it a smooth curve. Drag its handles to change the shape. Right-click a point or edge to enter an exact position or length in centimetres.

## Outline Transformations

### Offset Outline Copy

Right-click a piece and choose the outline-copy action to make a second outline at a chosen distance. The original piece stays in place.

### Unfold (<kbd>U</kbd>)

Select a straight edge and press <kbd>U</kbd> to mirror the piece across that edge.

### Mirror with Seam (<kbd>Shift</kbd> + <kbd>U</kbd>)

Select a straight edge and press <kbd>Shift</kbd> + <kbd>U</kbd> to make a separate mirrored piece with matching edges ready to sew.

## Linked Editing

Right-click a piece and choose **Clone as linked twin** to make a mirrored copy. Changes to either linked piece are reflected in the other. Turn **Linked twin** off when you want to edit the pieces separately.

## Internal Lines, Cuts, Slits, & Darts

Press <kbd>I</kbd> to draw inside a selected piece. Closed shapes can be cut out or traced as a separate piece. Lines that reach the outer edge can split a piece; lines that stop inside make a slit.

### Internal Shapes & Holes

Draw a closed shape inside a piece. Right-click it and choose **Cut selected internal path** to make a hole, or choose **Trace** to make it a separate piece.

### Cut Knife (<kbd>N</kbd>)

Click points across a piece, crossing its outline twice, then press <kbd>Enter</kbd> to finish. Choose **Cut & Sew** to connect the new edges, or **Cut only** to leave them separate. Press <kbd>Escape</kbd> to cancel.

### Princess Seams & Slits

Draw a line from one edge of a piece to another to create a split. A line that ends inside the piece creates a slit.

### Darts (<kbd>D</kbd>)

Click two points on the outer edge for the dart opening, then click inside the piece for the dart point.

## Tracing Reference Images

1. Right-click the canvas and choose **Garment > Reference image > Load image**.
2. Place the image and adjust its opacity.
3. Choose **Set measured scale > Pick length endpoints**.
4. Click two known points, enter their real distance in centimetres, and use the image as a scale reference.
