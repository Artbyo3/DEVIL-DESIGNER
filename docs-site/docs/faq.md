# Frequently Asked Questions & Troubleshooting

This page answers common questions about using Devil Designer v0.11.0.

## Sewing & Seam Questions

### Why does my seam show an amber "Gather warning"?

It means the joined edges have different lengths. This can be intentional for gathers or eased seams, and it does not stop simulation.

### Why won't the 3D Viewport register my sewing click?

Zoom in or orbit so the edge is clear. Edges hidden behind the body or another piece cannot be selected. Pause simulation before sewing in 3D.

### Why didn't my linked twin receive my new sewing seam?

Linked twins copy pattern edits, not seams. Sew the matching edges on each piece yourself.

### Why does Seam Shrink change folds elsewhere on my garment?

Shrink can change nearby folds. Set it to 0% if you do not want the gathering effect.

## Avatar & Placement Questions

### Why does my cloth go through the avatar or another garment?

Check that the avatar is selected and move the garment pieces so they begin outside the body or inner garment. For layers, try **High** simulation quality.

### Will my avatar work with armatures and shape keys?

Yes. Devil Designer follows the visible avatar shape, including active poses and shape keys. A tack attached to the avatar follows its movement.

## Simulation & Drafting Questions

### Can I freeze a piece and sew other pieces to it?

Yes. Choose **Simulation > Freeze** from the piece's right-click menu, then sew and simulate the other active pieces.

### What does the Fit Map show?

The Fit Map is a color guide to stretch and compression, not a pressure reading. White is close to the original edge length, blue shows compression, and red shows stretch.

### What happens if a cut crosses an internal line?

For a straight open line, choose **Split and retry** if it appears. If the cut is refused, adjust the line or cut path and try again.

### How do I undo an accidental garment load from the Library?

Press <kbd>Ctrl</kbd> + <kbd>Z</kbd> immediately after loading to restore the previous design.

### How many undo steps are saved, and do they survive closing Blender?

Pattern and seam edits can be undone in Devil Designer. Save the Blender project to keep the design when you close Blender.

### How are UVs prepared for texturing?

UVs are the flat map used to place a texture on the garment. Their layout follows the pattern pieces.

### What do the fabric presets do?

The fabric presets are calibrated against real fabric so each choice gives the garment a different drape.

## Installation and Startup Problems

### Devil Designer is missing from the add-on list. What should I do?

Install the v0.11.0 download from **Preferences > Add-ons > Install from Disk...**, then enable it in the add-on list.

### The editor will not open. What should I try?

Activate a 3D Viewport and use <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>D</kbd>, search for **Devil Designer** with <kbd>F3</kbd>, or choose **View > Devil Designer**.

### The simulation will not start. What should I check?

Make sure at least one piece is active in **Simulation** settings. If needed, reset the garment, check its placement, and click **Simulate** again.
