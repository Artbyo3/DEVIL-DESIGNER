# Quickstart: Panel > Sew > Simulate

This guide takes a simple garment from pattern pieces to a finished mesh.

## Step 1: Open Devil Designer

1. In Blender, activate a 3D Viewport.
2. Press <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>D</kbd>, or choose **View > Devil Designer**.

## Step 2: Select the Avatar Reference

1. Click **Garment** and switch to the **Body** tab.
2. Choose your avatar from the list.
3. Press <kbd>H</kbd> to show or hide the avatar guide.

## Step 3: Create Pattern Panels

On an empty canvas, choose **Create panel** for a starter rectangle. To draw your own pieces, press <kbd>R</kbd> and drag a rectangle, press <kbd>P</kbd> and click the outline points, or press <kbd>E</kbd> and drag an ellipse. Close a polygon by pressing <kbd>Enter</kbd> or clicking its first point.

### Creating a Mirrored Twin

For a matching left and right piece, right-click a piece and choose **Clone as linked twin**. Changes to its outline and internal lines are copied to the twin.

<figure class="dd-shot" id="shot-quickstart-mirrored-twin" data-shot='{"action":"Create a mirrored linked twin of a pattern piece","ui_state":"Two pattern pieces with linked twin on minimal canvas","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-quickstart-mirrored-twin-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-quickstart-mirrored-twin-caption">Full-editor view showing two pattern pieces on the minimal canvas with an active linked twin reflecting outline edits.</figcaption>
</figure>

## Step 4: Arrange Panels Around the Body (Optional)

Panels can drape without being arranged first. To place them around the avatar:

1. Reveal the 3D Viewport.
2. Select a piece and click a blue placement point, such as **Chest Front**.
3. Place the back piece at **Chest Back**.
4. Use Blender's <kbd>G</kbd> and <kbd>R</kbd> controls to adjust a piece if needed.

## Step 5: Sew the Seams

1. Press <kbd>J</kbd> to choose the Sew tool.
2. Click one edge, then the matching edge on the other piece.
3. Repeat for the remaining edges.
4. Follow the arrows to check seam direction. If needed, reverse a seam from its right-click menu.

**Pass** means the edge lengths match closely. **Gather warning** means they differ, but you can still simulate the garment.

<figure class="dd-shot" id="shot-quickstart-seam-mismatch" data-shot='{"action":"Inspect seam connection and mismatch status between pattern panels","ui_state":"Paired seam directional arrows and status badges joining two pieces","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-quickstart-seam-mismatch-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-quickstart-seam-mismatch-caption">Full-editor view showing paired seam directional arrows and alignment badges connecting two pattern pieces across the canvas.</figcaption>
</figure>

## Step 6: Simulate the Drape

1. Click **Simulate** in the bottom bar.
2. Click **Pause** when you want to inspect the drape.
3. Press <kbd>F</kbd> to show or hide the **Fit Map**, a color guide that shows where fabric is stretched or compressed.

## Step 7: Keep the Final Mesh

1. Pause on the frame you want to keep.
2. Open the **Keep mesh** arrow to choose **Weld: Auto/Manual** and **Thickness**.
3. Click **Keep mesh**.

The finished mesh is editable in Blender. Its UVs are the flat map used to place textures on the garment and follow the pattern pieces.

<figure class="dd-shot" id="shot-quickstart-mesh-keep" data-shot='{"action":"Keep final simulated garment mesh in Blender","ui_state":"Kept garment mesh selected in Blender 3D Viewport after Keep mesh","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-quickstart-mesh-keep-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-quickstart-mesh-keep-caption">Full-editor view showing the finished cloth mesh selected around the avatar in the Blender 3D Viewport after clicking Keep mesh.</figcaption>
</figure>

## Step 8: Save Your Work

Save the Blender file to keep your pattern pieces, seams, fabric choices, and panel placement.

If the drape or finished mesh does not look right, adjust the pieces or seams, simulate again, and keep a new result.
