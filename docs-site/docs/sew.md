# Sewing Edges

Use the Sew tool to connect pattern edges before you simulate the garment.

## Sewing Modes

### Segment Sewing (<kbd>J</kbd>)

1. Press <kbd>J</kbd>.
2. Click the first edge.
3. Click the matching edge.

<figure class="dd-shot" id="shot-sew-segment-selection" data-shot='{"action":"Select first edge segment using the Sew tool","ui_state":"First boundary edge highlighted awaiting selection of matching edge across two pieces","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-sew-segment-selection-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-sew-segment-selection-caption">Close-up view of the first selected pattern edge highlighted in the Sew tool state while awaiting the matching target edge.</figcaption>
</figure>

### Free Sewing (3D Viewport)

In the revealed 3D Viewport, press <kbd>Shift</kbd> + <kbd>J</kbd> to join part of an edge:

1. Click the start and end of the first edge range.
2. Click the start and end of the matching range.

## Direct 3D Viewport Sewing

1. Reveal the 3D Viewport.
2. Press <kbd>J</kbd> or <kbd>Shift</kbd> + <kbd>J</kbd>.
3. Click the visible edges on the placed pieces.

## Direction, Reversal, & Removal

- Follow the arrows to check which way the two edges are joined.
- To reverse a seam, select it and press <kbd>B</kbd>, or right-click its canvas badge and choose **Reverse**.
- To remove a seam, select it and press <kbd>X</kbd> or <kbd>Delete</kbd>, or right-click its canvas badge and choose **Remove**.
- Press <kbd>Ctrl</kbd> + <kbd>Z</kbd> to undo a removal.

<figure class="dd-shot" id="shot-sew-direction-reversal" data-shot='{"action":"Inspect seam orientation arrows and trigger Reverse or Remove from context menu","ui_state":"Seam directional arrows and numbered badge context menu with Reverse and Remove options","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-sew-direction-reversal-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-sew-direction-reversal-caption">Close-up view of seam directional arrows and canvas badge context menu with Reverse and Remove options active.</figcaption>
</figure>

## Pre-Simulation Preview & Mismatch Warning

Before draping, right-click a numbered seam badge to see the mismatch in centimetres and percent. **Pass** means the lengths are close; **Gather warning** means they differ by more than 1%. A mismatch can be intentional, and it does not stop simulation.

<figure class="dd-shot" id="shot-sew-mismatch-warning" data-shot='{"action":"Review seam length mismatch warning and tolerance report","ui_state":"Numbered seam badge showing length difference in centimetres and percent with Gather warning","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-sew-mismatch-warning-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-sew-mismatch-warning-caption">Close-up view of a numbered seam badge detailing centimetre and percentage length differences alongside the Gather warning status.</figcaption>
</figure>

## Seam Shrink (Elastic Cuffs & Waistbands)

1. Right-click a seam badge.
2. Choose **Shrink: 0%, 10%, 20%, or 30%**.
3. Save the design to keep the choice.

### What Shrink Changes

When Shrink is above 0%, tighter collision helps create gathers but can change nearby folds.
