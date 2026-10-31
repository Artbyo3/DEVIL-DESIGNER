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

Presets apply native structural, shear, and bending vertex groups. Mass density is calculated as an area-weighted native cloth value across the garment.

---

## Per-Piece Simulation States

Right-click any pattern piece and open **Simulation** to assign one of three dedicated states:

### 1. Freeze
* **Behavior:** Holds the piece's exact current simulated shape (or its arranged 3D panel if unsimulated) in place.
* **Shared Mesh:** Frozen and active live pieces remain part of a single unified cloth mesh.
* **Seam Anchoring:** Both endpoints of seams connecting to a frozen piece are pinned, while the neighboring live piece drapes naturally against it.
* **No Pin Drift:** An in-mesh exact-position clamp neutralizes native Blender pin roundoff to guarantee 0 mm drift.
* **Self-Collision:** Same-mesh self-collision is automatically enabled so draping live fabric collides against held frozen fabric without needing separate collider objects.

### 2. Deactivate
* **Behavior:** Completely omits the piece from the active simulation run.
* **Inert Seams:** Seams and anchors connected to deactivated pieces become inert for that run.
* **Wire Guide:** Deactivated pieces remain visible in the viewport as wire guides for reference.

### 3. Strengthen
* **Behavior:** Multiplies the piece's tension, compression, shear, and bending stiffness by **4x** using independent native vertex groups.
* **Use Cases:** Ideal for stiff collars, lapels, waistbands, or cuffs that must hold shape without affecting softer main body panels.

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

---

## Layering: Wear Over Kept Garments

To dress an avatar in multiple layers (e.g. jacket over a shirt):

1. Finalize the inner garment using **Keep mesh**.
2. Click the arrow next to **Simulate** and choose **Wear over**.
3. All existing kept garments in the scene are listed (up to 5 per page with scroll). Enabled garments act as active colliders for the new garment.
4. If a kept garment lacks a Collision modifier, Devil Designer automatically adds one without altering existing settings.
5. Place the outer garment panels radially outside the inner garment.
6. Set simulation quality to **High** for layered cloth simulation.

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

---

## Substance 3D Painter Ready UVs

Devil Designer derives UVs directly from the 2D pattern drafting canvas:
* **True 1:1 Scaling:** Relative scale and orientation between pattern islands are preserved exactly as drafted.
* **No Silent Repacking:** Pattern pieces are not automatically normalized to fit a 0&ndash;1 tile or scrambled during rebuilds.
* **Seamless Continuity:** Welded seams match the corresponding boundary edges for predictable texture painting in Substance 3D Painter or Blender's texture paint mode.
