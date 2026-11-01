# Simulate and Keep the Garment

## Run the Simulation

- Click **Simulate** to start the drape.
- Click **Pause** to inspect it.
- Click **Reset drape** on the garment card to restore the starting arrangement. Reset does not delete finished meshes.

## Choose Fabric and Mesh Detail

Right-click a piece to choose its fabric or mesh detail. A fabric preset is a ready-made choice that helps the drape behave like that material.

- **Coarse:** Use for large, simple pieces and faster previews.
- **Standard:** Use for most garments.
- **Fine:** Use for small or detailed pieces such as collars and cuffs.

### Fabric Presets

Choose Silk, Knit, Cotton, Linen, Leather, or Denim to set how a piece drapes.

## Choose Simulation Quality

Choose **Draft** for a quick first look, **Standard** for everyday draping, or **High** when you need a more detailed result, especially for layers. Higher quality can take longer to simulate.

## Adjust Individual Pieces

Right-click a piece and choose **Simulation**:

- **Freeze** holds the piece in its current shape while other pieces move.
- **Deactivate** leaves the piece out of the simulation.
- **Strengthen** makes the piece stiffer, useful for collars, lapels, waistbands, or cuffs.

## Read the Fit Map

Press <kbd>F</kbd> to show or hide the **Fit Map**, a color guide that shows where the fabric is stretched or compressed. White is close to its original length, blue shows compression, and red shows stretch. It is a visual guide, not a pressure measurement.

<figure class="dd-shot" id="shot-simulate-fit-map" data-shot='{"action":"Inspect garment stretch and compression with the Fit Map","ui_state":"Paused drape with white neutral, blue compressed, and red stretched fabric and bottom controls visible","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-simulate-fit-map-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-simulate-fit-map-caption">Full-editor view of the paused drape with the Fit Map enabled, showing white neutral, blue compressed, and red stretched fabric alongside the bottom controls.</figcaption>
</figure>

## Simulate Clothing in Layers

1. Keep the inner garment as a mesh.
2. Open **Simulate**'s arrow; turn the inner garment **On** in **Wear over**.
3. Position the outer garment around the inner garment.
4. Choose **High** quality for layered clothing.

<figure class="dd-shot" id="shot-simulate-layer-settings" data-shot='{"action":"Enable a kept inner garment for layered draping","ui_state":"Simulate arrow menu open with a named kept inner garment listed under Wear over and set to On","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-simulate-layer-settings-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-simulate-layer-settings-caption">Close-up view of the open Simulate arrow menu, showing the kept inner garment by name under Wear over with its toggle set to On.</figcaption>
</figure>

## If the Drape Fails or Looks Wrong

- Check that the correct avatar is selected and that the pieces are placed around it as expected.
- Make sure at least one piece is active in **Simulation** settings.
- If the fabric starts in the wrong place, use **Reset**, adjust the pieces, and simulate again.
- If the result looks rough, try **Standard** or **High** quality, or use **Fine** mesh detail on small pieces.

## Keep the Finished Mesh

1. Pause on the frame you want.
2. Use the **Keep mesh** arrow for **Weld: Auto/Manual** and **Thickness**.
3. Click **Keep mesh**.

The finished mesh is editable in Blender. Its UVs are the flat map used to place textures on the garment and follow the pattern pieces.

<figure class="dd-shot" id="shot-simulate-keep-mesh" data-shot='{"action":"Configure mesh baking options and execute Keep mesh","ui_state":"Paused drape with Keep mesh arrow expanded showing Weld Auto/Manual and Thickness options","framing":"close-up","aspect_ratio":"4:3"}' data-shot-framing="close-up" aria-labelledby="shot-simulate-keep-mesh-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-simulate-keep-mesh-caption">Close-up view of the Keep mesh popup controls showing Weld Auto/Manual selection and Thickness input fields.</figcaption>
</figure>
