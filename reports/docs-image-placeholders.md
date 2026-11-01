# Documentation Screenshot Placeholders Specification

This report defines the screenshot placeholder architecture and catalogs all 19 selective placeholder locations across the Devil Designer v0.11.0 documentation guides.

## Pattern Selector and Data Shape

Each placeholder card follows a standardized HTML figure structure. Automated pipelines and capture agents locate placeholder elements using the CSS selector:

```css
figure.dd-shot[data-shot]
```

### Card Markup Template

```html
<figure class="dd-shot" id="shot-UNIQUE" data-shot='{"action":"...","ui_state":"...","framing":"full-editor|close-up","aspect_ratio":"16:9|4:3"}' data-shot-framing="full-editor|close-up" aria-labelledby="shot-UNIQUE-caption">
  <div class="dd-shot__frame"><span class="dd-shot__icon" aria-hidden="true"></span><span class="dd-shot__label">Screenshot coming soon</span></div>
  <figcaption id="shot-UNIQUE-caption">literal caption specifying action, actual UI state/area, full-editor vs close-up framing.</figcaption>
</figure>
```

Captions remain outside the aspect ratio frame, are left-aligned, and adapt responsively without overflow. The inner frame preserves a fixed aspect ratio of either 16:9 or 4:3 based on the `data-shot-framing` attribute.

## Exact Grep Command

To locate all placeholder figures across markdown documentation files in the repository, execute:

```bash
git grep --no-index -n 'class="dd-shot"' docs-site/docs/
```

In PowerShell environments, execute:

```powershell
git grep --no-index -n 'class=\"dd-shot\"' docs-site/docs/
```

## JSON Schema Fields

The `data-shot` attribute contains a JSON object encoded with standard straight double quotes inside single quotes. The JSON object requires the following fields:

- `action`: String. The user operation or task demonstrated by the screenshot.
- `ui_state`: String. The concrete visual state of the Devil Designer interface, Blender panels, canvas objects, and indicators.
- `framing`: String enum (`full-editor` | `close-up`). Identifies whether the screenshot captures the entire editor layout or an isolated component.
- `aspect_ratio`: String enum (`16:9` | `4:3`). Defines the geometric ratio applied to the viewport frame.

## Per-Page Counts and FAQ Rationale

The 19 selective placeholder locations are distributed across 8 documentation guides as follows:

| Guide File | Page Title | Placeholder Count |
| :--- | :--- | :--- |
| `docs-site/docs/install.md` | Install Devil Designer | 2 |
| `docs-site/docs/quickstart.md` | Quickstart: Panel > Sew > Simulate | 3 |
| `docs-site/docs/draft.md` | Drafting & Pattern Editing | 4 |
| `docs-site/docs/sew.md` | Sewing Edges | 3 |
| `docs-site/docs/arrange.md` | Place Panels Around the Avatar | 2 |
| `docs-site/docs/simulate.md` | Simulate and Keep the Garment | 3 |
| `docs-site/docs/library.md` | Save and Reuse Garments | 2 |
| `docs-site/docs/faq.md` | Frequently Asked Questions & Troubleshooting | 0 |
| **Total** | | **19** |

### FAQ Rationale

The FAQ page (`docs-site/docs/faq.md`) contains no placeholders. Its short troubleshooting answers do not need additional visuals beyond those in the detailed guides.

## All 19 Placeholder Entries

### 1. Install Guide (`docs-site/docs/install.md`)

#### Entry 1
- Stable ID: `shot-install-enable-addon`
- Insertion Position: After Enable section, before Open Editor section.
- Action: Enable the Devil Designer add-on in Blender Preferences.
- UI State: Add-ons Preferences tab filtered to Devil Designer with enabled checkbox.
- Framing: `close-up`
- Aspect Ratio: `4:3`

#### Entry 2
- Stable ID: `shot-install-editor-view`
- Insertion Position: After Open Editor options list, before Upgrade or Reinstall section.
- Action: Open the Devil Designer workspace in Blender.
- UI State: Empty minimal editor with left tool dock, canvas, and bottom workflow controls; no sidebars or docked inspectors.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

---

### 2. Quickstart Guide (`docs-site/docs/quickstart.md`)

#### Entry 3
- Stable ID: `shot-quickstart-mirrored-twin`
- Insertion Position: After Step 3 Creating Mirrored Twin paragraph, before Step 4 section.
- Action: Create a mirrored linked twin of a pattern piece.
- UI State: Two pattern pieces with linked twin on minimal canvas.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

#### Entry 4
- Stable ID: `shot-quickstart-seam-mismatch`
- Insertion Position: After Step 5 mismatch explanation paragraph, before Step 6 section.
- Action: Inspect seam connection and mismatch status between pattern panels.
- UI State: Paired seam directional arrows and status badges joining two pieces.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

#### Entry 5
- Stable ID: `shot-quickstart-mesh-keep`
- Insertion Position: After Step 7 final mesh paragraph, before Step 8 section.
- Action: Keep final simulated garment mesh in Blender.
- UI State: Kept garment mesh selected in Blender 3D Viewport after Keep mesh.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

---

### 3. Drafting Guide (`docs-site/docs/draft.md`)

#### Entry 6
- Stable ID: `shot-draft-bezier-editing`
- Insertion Position: After Bezier Curve Editing paragraph, before Outline Transformations section.
- Action: Edit Bezier curve handles and enter numeric coordinates.
- UI State: Smooth curve point with two control handles and open right-click coordinate menu.
- Framing: `close-up`
- Aspect Ratio: `4:3`

#### Entry 7
- Stable ID: `shot-draft-mirror-with-seam`
- Insertion Position: After Mirror with Seam instructions, before Linked Editing section.
- Action: Generate a mirrored piece connected with a sewn seam.
- UI State: Mirrored separate pattern pieces with matching boundary edges joined by an active seam.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

#### Entry 8
- Stable ID: `shot-draft-fold-pleats`
- Insertion Position: After fold instructions, adjustment bullets, and concluding paragraph, before Current Limits subsection.
- Action: Configure internal fold lines and pleat directions.
- UI State: Parallel pleat lines with Mountain and Valley arrows and labels across valid boundary path.
- Framing: `close-up`
- Aspect Ratio: `4:3`

#### Entry 9
- Stable ID: `shot-draft-trace-reference`
- Insertion Position: After Tracing Reference Images numbered steps at end of guide.
- Action: Calibrate reference image scale with known-length endpoints.
- UI State: Loaded trace image with calibration endpoints and scale numeric input controls.
- Framing: `close-up`
- Aspect Ratio: `4:3`

---

### 4. Sewing Guide (`docs-site/docs/sew.md`)

#### Entry 10
- Stable ID: `shot-sew-segment-selection`
- Insertion Position: After Segment Sewing numbered steps, before Free Sewing subsection.
- Action: Select first edge segment using the Sew tool.
- UI State: First boundary edge highlighted awaiting selection of matching edge across two pieces.
- Framing: `close-up`
- Aspect Ratio: `4:3`

#### Entry 11
- Stable ID: `shot-sew-direction-reversal`
- Insertion Position: After Direction, Reversal, & Removal bullet list, before Pre-Simulation Preview & Mismatch Warning section.
- Action: Inspect seam orientation arrows and trigger Reverse or Remove from context menu.
- UI State: Seam directional arrows and numbered badge context menu with Reverse and Remove options.
- Framing: `close-up`
- Aspect Ratio: `4:3`

#### Entry 12
- Stable ID: `shot-sew-mismatch-warning`
- Insertion Position: After Pre-Simulation Preview paragraph, before Seam Shrink section.
- Action: Review seam length mismatch warning and tolerance report.
- UI State: Numbered seam badge showing length difference in centimetres and percent with Gather warning.
- Framing: `close-up`
- Aspect Ratio: `4:3`

---

### 5. Arrangement Guide (`docs-site/docs/arrange.md`)

#### Entry 13
- Stable ID: `shot-arrange-wrap-points`
- Insertion Position: After Wrap a Panel Around the Body list and fallback paragraph, before Fine-Tune Placement subsection.
- Action: Wrap selected panel around body placement points.
- UI State: Selected chest panel aligned to blue placement landmarks with avatar visible in 3D Viewport.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

#### Entry 14
- Stable ID: `shot-arrange-avatar-tacks`
- Insertion Position: After Avatar Tacks instructions, before Remove Pins & Tacks subsection.
- Action: Attach fabric tack point to target avatar geometry.
- UI State: Fabric tack line linking pattern point directly to avatar surface mesh.
- Framing: `close-up`
- Aspect Ratio: `4:3`

---

### 6. Simulation Guide (`docs-site/docs/simulate.md`)

#### Entry 15
- Stable ID: `shot-simulate-fit-map`
- Insertion Position: After Read the Fit Map paragraph, before Simulate Clothing in Layers section.
- Action: Inspect garment stretch and compression with the Fit Map.
- UI State: Paused drape with white neutral, blue compressed, and red stretched fabric and bottom controls visible.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

#### Entry 16
- Stable ID: `shot-simulate-layer-settings`
- Insertion Position: After Simulate Clothing in Layers steps, before If the Drape Fails or Looks Wrong section.
- Action: Enable a kept inner garment for layered draping.
- UI State: Simulate arrow menu open with a named kept inner garment listed under Wear over and set to On.
- Setup: Keep an inner garment mesh, place active outer panels around it, and choose High quality from the canvas context menu before opening Simulate. Quality and Wear over belong to separate menus; show only Wear over in this shot.
- Framing: `close-up`
- Aspect Ratio: `4:3`

#### Entry 17
- Stable ID: `shot-simulate-keep-mesh`
- Insertion Position: After Keep the Finished Mesh paragraph at end of guide.
- Action: Configure mesh baking options and execute Keep mesh.
- UI State: Paused drape with Keep mesh arrow expanded showing Weld Auto/Manual and Thickness options.
- Framing: `close-up`
- Aspect Ratio: `4:3`

---

### 7. Library Guide (`docs-site/docs/library.md`)

#### Entry 18
- Stable ID: `shot-library-save-garment`
- Insertion Position: In Save a Garment, immediately before the paragraph beginning Saved designs live.
- Action: Save current garment design to the local library.
- UI State: Library view open with saved garment entries and its save control visible in the minimal interface.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

#### Entry 19
- Stable ID: `shot-library-load-avatar`
- Insertion Position: After Load a Garment on Another Avatar explanation paragraph, before Undo a Load section.
- Action: Load saved garment onto a new avatar with automatic refitting.
- UI State: Garment pieces loaded and automatically positioned around the new character model.
- Framing: `full-editor`
- Aspect Ratio: `16:9`

---

## Later Replacement Steps Without Capturing Now

When the screenshot capture agent executes:

1. Query all figure cards using selector `figure.dd-shot[data-shot]`.
2. Parse the metadata payload from the `data-shot` JSON attribute (`action`, `ui_state`, `framing`, `aspect_ratio`).
3. Set up the corresponding test scene in Blender with Devil Designer v0.11.0 active.
4. Capture the screenshot matching the requested framing and aspect ratio. Use 1600 by 900 pixels for full-editor shots and 1200 by 900 pixels for close-ups. Do not include sidebars or docked inspectors in Devil Designer. Blender Preferences and native 3D Viewport shots retain the UI needed for their action.
5. Save the image file under `docs-site/docs/assets/images/screenshots/`.
6. Replace only the interior contents of `<div class="dd-shot__frame">...</div>` with the `<img>` element:
   ```html
   <img src="../assets/images/screenshots/shot-install-editor-view.png" alt="Empty Devil Designer editor with the left tool dock and bottom controls" width="1600" height="900">
   ```
7. Use the stable shot ID as the filename and write alt text for the actual captured state. Use width="1200" height="900" for close-ups. The relative image path starts with `../` because built guide pages live in their own URL directories. Retain the parent `<figure>` tag, stable `id`, JSON metadata, framing attribute, and existing caption.
8. Re-run `zensical build --strict` to verify site generation.
