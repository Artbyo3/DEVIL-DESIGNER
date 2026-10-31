# Simulation & Finalizing

Devil Designer leverages Blender's native cloth physics solver while providing custom tooling for per-piece simulation states, real-time deformation inspection, layered clothing collision, and clean mesh extraction.

---

## Running the Simulation

* **Start Simulation:** Click **Simulate** in the bottom bar. The 3D viewport reveals automatically and cloth draping begins.
* **Pause Drape:** Click **Pause** to freeze simulation on any frame for inspection.
* **Reset Simulation:** On the garment card, click **Reset** to clear the cloth cache and restore panels to their arranged starting positions. A confirmation prompt prevents accidental resets. Kept finalized garments are never deleted by a reset.

---

## Mesh Density & Fabric Presets

### Mesh Spacing & Triangulation
Devil Designer triangulates 2D Bezier patterns using a staggered interior grid and constrained Delaunay triangulation:
* Curved boundaries, internal cut paths, holes, and slits are cleanly integrated into the generated topology.
* Default spacing begins at 2&ndash;3 cm for rapid drafting.
* **Per-Piece Overrides:** Right-click any piece and select **Mesh density**:
    * **Garment default:** Inherits global garment spacing.
    * **Coarse:** Doubles interior mesh spacing (ideal for large, simple back panels).
    * **Standard:** Standard interior density.
    * **Fine:** Halves interior spacing (ideal for small collars, cuffs, or detailed trims).
    * Paired seams automatically share compatible boundary sampling so differing interior densities do not disrupt sewing.

### Fabric Presets
Select a piece and open the **Fabric** card to choose one of six material presets:
* **Silk**
* **Knit**
* **Cotton**
* **Linen**
* **Leather**
* **Denim**

Presets apply native structural, shear, and bending vertex groups. Presets are calibrated against physical textile benchmarks (KES-F / FAST derived data and Peirce cantilever bending lengths).

**Known physics and solver limits:**
* **Spacing Normalization:** Calibration is exact near 0.02 m spacing because Blender assigns mass per vertex and bending per edge without area/length normalization.
* **CDT Shear Lock:** Triangle-mesh shear is locked to 3/8 of structural stiffness because Blender creates zero shear springs on triangular CDT meshes.
* **Shared Density:** Multi-fabric garments share one area-weighted density because native Blender cloth simulation uses a single mass setting across the compiled object.

---

## Per-Piece Simulation States

Right-click any pattern piece and open **Simulation** to assign one of three dedicated states:

### 1. Freeze
* **Behavior:** Holds the piece's exact current simulated shape (or its arranged 3D panel if unsimulated) in place.
* **Shared Mesh:** Frozen and active live pieces remain part of a single unified cloth mesh.
* **Seam Anchoring:** Both endpoints of seams connecting to a frozen piece are pinned, while the neighboring live piece drapes naturally against it.
* **No Pin Drift:** An in-mesh exact-position clamp neutralizes native Blender pin roundoff to guarantee 0 mm drift. Temporary attributes are removed before Keep mesh.
* **Self-Collision:** Same-mesh self-collision is automatically enabled so draping live fabric collides against held frozen fabric without needing separate collider objects.
* **Tacks:** Frozen tacks do not drag the held boundary with the body.

### 2. Deactivate
* **Behavior:** Completely omits the piece from the active simulation run.
* **Inert Seams:** Seams and anchors connected to deactivated pieces become inert for that run, but remain in the editable design.
* **Sampling:** Other pieces are sampled as if the deactivated piece were absent. Activate at least one piece before simulating.
* **Wire Guide:** Deactivated pieces remain visible in the viewport as wire guides for reference.

### 3. Strengthen
* **Behavior:** Multiplies the piece's tension, compression, shear, and bending stiffness by **4x** using independent native vertex groups. Shared presets, other pieces' stiffness, mass, and sewing forces are unchanged.
* **Priority:** Deactivate takes precedence; stored Freeze and Strengthen choices return on activation.
* **Use Cases:** Ideal for stiff collars, lapels, waistbands, or cuffs that must hold shape without affecting softer main body panels.

### Persistence & Linking Rules
Flags survive Blender save/reopen, the 100-edit undo history, ordinary duplication, and garment-library save/load. Explicitly enabled linked twins share subsequent state toggles; switch Linked twin Off for independent states. Linking never edits sewing.

Frozen outlines remain editable and arrangement remains available. Editing an outline rebuilds its sampling; its next frozen run starts from the rebuilt arrangement if the old drape is no longer compatible. The library stores the flags and editable design, not a portable simulation cache.

Kept frozen garments work as ordinary Wear over bases. Current shape is transferred directly into the shared simulation mesh, without a panel-coordinate round trip.

### Prototype Measurements (2026-10-29)

Scratch-only gates ran against master `689d785e92ee0ee829d68a353977d58ff87ffb5b` before production edits, using Blender 5.2.3 LTS and 121 frames per trial:

| Measurement | Result |
| :--- | :--- |
| **Frozen piece maximum movement** | 0 mm; required at most 0.001 mm |
| **Unheld live sewn partner maximum movement** | 25.510 mm |
| **Maximum seam gap, both-live / one frozen** | 1.301 / 1.087 mm |
| **Maximum paired seam-side length difference** | 0.461 mm |
| **Seam-side length tolerance** | 2 mm + 2% of initial side length, every frame |
| **Maximum permitted seam-gap excess over baseline** | 2 mm |
| **Cotton strip mean positive edge strain, normal / 4x** | 0.06730% / 0.01684% |
| **Stretch reduction, frames 101-121** | 74.98% |
| **Other Cotton strip maximum trajectory difference** | 0.002315 mm; below diagnostic 0.01 mm tolerance |
| **Absent-inner control final outer penetration into excluded shirt surface** | 15.707 mm, body retained, zero errors |
| **Frozen kept-base penetration, Standard / High** | 0 / 0 mm; matched both shipped-path references |

The strengthened and normal strips shared a Cotton preset; only the selected strip's weights changed. The absent-inner control tested actual absence and the collision filter, not persistence of flags. Production regression tests separately verify inactive faces/seams are absent and sampling matches an absent-piece design.

Production validation also exposed native pin roundoff of 0.000119 mm after compiling the run separately; that caused 4.059 mm Standard penetration and failed the strict layering gate. The in-mesh exact-position clamp removed this drift. The final production path measured 0 mm frozen movement, 0 mm kept-coordinate difference, and 0 mm penetration at both Standard and High, matching references over 327,423 and 470,666 sampled points respectively. No sewing force, collider modifier setting, placement function, or Keep mesh processing was changed.

---

## Fit Map Deformation Guide

Press <kbd>F</kbd> (or click the dock's **[F]** chip) while viewing a simulation to toggle the **Fit Map**.

```
[Full Blue] ------------ [White] ------------ [Full Red]
  -15% (0.85)         Neutral (±3%)         +15% (1.15)
 (Compression)                              (Stretch)
```

* **Color Spectrum:**
    * **White:** Neutral rest length (edge ratios between 0.97 and 1.03).
    * **Blue:** Compression (fabric bunching or under compression; saturates at 15% compression / 0.85 ratio).
    * **Red:** Stretch (fabric under tension; saturates at 15% stretch / 1.15 ratio).
* **Rest-Length Ratio Calculation:** Compares evaluated world-space edge lengths in metres against original 2D flat-panel rest lengths (excluding sewing springs). Each vertex computes a rest-length-weighted average of incident edges.
* **Non-Destructive GPU Display:** The Fit Map is rendered via native GPU draw handlers on a temporary unlinked mesh. It creates no material overrides, vertex color layers, or persistent attributes on your garment.

!!! tip "Fit Map Interpretation"
    The Fit Map is an edge deformation guide, not a calibrated textile stress/pressure sensor. Loose fabric can fold or drape without edge compression and remain white. Use it as a visual aid to identify tight pulling areas or excessive sagging.

**Prototype Verification:** The included two-panel demo at 2.5 cm spacing and quality 8, evaluated through frame 40, had 820 vertices: 806 neutral, 14 stretched, none compressed, with ratios 0.9755–1.0814. Mean neighboring variation was 0.22 percentage points; no neighboring jump exceeded 10 percentage points. Visual inspection confirmed a calm, mostly neutral surface with subtle localized shoulder stretch rather than speckling, validating usable low-noise data.

---

## Layering: Wear Over Kept Garments

To dress an avatar in multiple layers (e.g. jacket over a shirt):

1. Finalize the inner garment using **Keep mesh**.
2. Click the arrow next to **Simulate** and choose **Wear over**.
3. All existing kept garments in the scene are listed (up to 5 per page with scroll). Enabled garments act as active colliders for the new garment.
4. If a kept garment lacks a Collision modifier, Devil Designer automatically adds one without altering existing settings.
5. Place the outer garment panels radially outside the inner garment.
6. Set simulation quality to **High** for layered cloth simulation.

**Fixture Validation:** The automated shirt/jacket fixture uses prearranged panels and shoulder pins on a headless torso, checks 121 frames at High quality against a 2 mm penetration tolerance, and samples vertices, edge midpoints and face centers away from open boundaries. This controlled test is not a penetration guarantee for arbitrary clothing or initial intersections; the Standard-quality fixture exceeded that tolerance. Cloth settings, sewing forces, and placement algorithms are not changed to implement layering.

---

## Finalizing with Keep Mesh

When satisfied with the simulated drape:

1. Click **Pause** on the desired frame.
2. Click **Keep mesh** in the bottom bar.
3. Click the arrow on **Keep mesh** to adjust options:
    * **Auto weld:** Automatically welds paired seam vertices within distance tolerance. If pairs remain open, a notification reports the count.
    * **Thickness:** Adds an editable Solidify modifier (**None**, **Thin**, or **Standard**).
4. The finalized mesh is an independent Blender object containing:
    * Triangle topology suitable for character clothing.
    * Dedicated vertex groups and sculpt face sets per pattern piece.
    * Clean, unnormalized 1:1 UV coordinates.

**Quad-Grid Conversion Deferred:** Keep mesh remains the existing triangle output with Auto weld and Thickness. Quad-grid conversion is deferred: its prototype did not preserve welded seams. No quad conversion, reduction, decimation, rigging, or weight transfer ships here.

---

## Substance 3D Painter Ready UVs

Devil Designer derives UVs directly from the 2D pattern drafting canvas:
* **True 1:1 Scaling:** Relative scale and orientation between pattern islands are preserved exactly as drafted.
* **No Silent Repacking:** Pattern pieces are not automatically normalized to fit a 0&ndash;1 tile or scrambled during rebuilds.
* **Seamless Continuity:** Welded seams match the corresponding boundary edges for predictable texture painting in Substance 3D Painter or Blender's texture paint mode.
