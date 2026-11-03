# Save and Reuse Garments

The Library saves editable garment designs so you can use them again or fit them to another avatar.

## Save a Garment

1. Open **Library** from the left dock and click **Save As...**. The same action is available in **Garment**.
2. Enter the name you want and optional comma-separated tags.
3. Click **Save As...**; confirm if replacing an existing saved name.

The visual grid updates as soon as you save, including when you overwrite a design. Each tile shows its captured flat-pattern thumbnail, name, piece count, saved date, body name/height and tags. Thumbnails are automatically captured from the editable pattern layout, not a rendered simulation pose. Existing designs receive a fallback pattern preview without conversion or resaving; missing historical body names are shown as unspecified.

Use **Search** to find a name, tag or body. Use **Tags** to filter the grid; choose **All tags** to clear the filter. Large libraries have pages and support mouse-wheel browsing. Files added, changed or removed while the library is open are detected automatically; no restart or reload action is needed.

<figure class="dd-shot" id="shot-library-save-garment" data-shot='{"action":"Save current garment design to the local library","ui_state":"Library view open with saved garment entries and its save control visible in the minimal interface","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-library-save-garment-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-library-save-garment-caption">Full-editor view showing the open Library with saved garment entries and its save control visible in the minimal interface.</figcaption>
</figure>

Saved designs live in the Devil Designer folder in Blender's user settings on this computer. To back them up, copy that folder to a safe place. Saving a Blender project does not include a separate copy of the local Library folder.

## Load a Garment on Another Avatar

1. Select the new character in the 3D Viewport.
2. Click **Garment**, switch to **Body**, and choose the new avatar.
3. Open **Library** and click a tile to preview it. This does not change your open garment.
4. Review its pattern layout, piece/seam counts, saved date, body and tags, then click **Load garment**.
5. Confirm if replacing the open design, or choose **Cancel** to keep working. Body-height refitting is automatic.

Invalid or deleted designs cannot be loaded from their preview. If a saved design changes after you request a load, preview it again rather than loading unseen changes. Version 1 and version 2 garment files remain supported, and editable pattern data and the existing height-scale refit are unchanged.

The design is placed using matching points on the new avatar when available. If a matching point is not available, the piece returns to its flat layout and a message appears. Tacks are moved to the new avatar.

<figure class="dd-shot" id="shot-library-load-avatar" data-shot='{"action":"Load saved garment onto a new avatar with automatic refitting","ui_state":"Garment pieces loaded and automatically positioned around the new character model","framing":"full-editor","aspect_ratio":"16:9"}' data-shot-framing="full-editor" aria-labelledby="shot-library-load-avatar-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-library-load-avatar-caption">Full-editor view showing a saved garment loaded and refitted around the newly selected avatar in the 3D workspace.</figcaption>
</figure>

## Undo a Load

Loading a design over an open one saves a temporary recovery point. Press <kbd>Ctrl</kbd> + <kbd>Z</kbd> right after loading to restore the previous design.

## Save and Reopen Your Blender Project

Save your Blender project normally to keep your editable pattern, seams, fabric choices, placements, and finished meshes. Reopen the project in Blender to continue working. The temporary simulation drape is not saved, so simulate again if you need to continue from a draped state.
