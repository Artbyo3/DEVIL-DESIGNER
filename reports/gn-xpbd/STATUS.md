# GN XPBD simulation: status

Date: 2026-11-04. Branch `feature/gn-xpbd-system`. Blender 5.2.3 LTS, RTX 3060 Ti, i5-13600KF.

The Geometry Nodes XPBD system is the only simulation engine. The built-in Cloth modifier is gone.

## How it works

A garment compiles to one mesh with a Geometry Nodes modifier, `DD XPBD`, built by `xpbd_nodes.py`.

- **Solver.** Blender's native XPBD Solver node in a modified copy of the stock XPBD Simulation framework, in realtime mode at a fixed 30 fps clock. The artist's frame rate and timeline return on Keep and Reset.
- **Live and final quality.** Live handling runs 10 to 12 substeps. Keep then runs 40 frames at the Quality setting (12, 24 or 36 substeps), because stretch is a solver-convergence limit that substeps reduce.
- **Sewing.** Seam rest lengths close over 0.8 s, gravity ramps in afterward, and a weld step pulls partners together.
- **Body contact.** A 5 mm voxel shell of the solidified body feeds the native collider every substep. A true-surface pass corrects on even frames, and self-contact runs on odd frames.
- **Pins and tacks.** Enforced exactly after each solver pass.
- **Grab.** Pull follows the hand in the view plane. Push presses along the surface normal. Radius is set by Ctrl+wheel or strip and shown as a ring at the cursor. The camera is never moved.
- **Keep.** Refines, then checks every collision body. Contacts up to 12 mm are nudged clear and deeper ones refuse.

## Live handling

Through the real editor with its overlay, on a test avatar of about 90k triangles. Raw numbers: `final-fps-raw.txt`.

| Garment | Vertices | Grab FPS | Median ms | Worst ms |
| --- | ---: | ---: | ---: | ---: |
| Sleeved cotton, 3 runs | 1,765 | 29.8 to 30.1 | 32.9 to 33.3 | 66.0 |
| Tee cotton, 3 runs | 1,149 | 30.0 | 34.3 to 34.8 | 57.9 |
| Skirt cotton, 1 run | 1,156 | 30.0 | 34.3 | 56.0 |
| Sleeved denim, 1 run | 1,765 | 28.1 | 35.2 | 65.1 |
| Sleeved from a 24 fps scene, 1 run | 1,765 | 29.8 | 33.2 | 60.6 |

The clock is capped at 30, so these do not show headroom. Stiff fabrics cost about 2 FPS on the heaviest garment.

## Starter coverage

Tee, Tank and Skirt were run through Simulate and Keep on five avatars with different proportions, from about 1.07 m to 1.51 m tall. All 15 runs reach a kept mesh. One keeps with 1 open seam pair.

## Open items

- **Hollow bodies.** Simulate now stops on an avatar with a deleted torso and asks for a full body or a Collision modifier on its outfit (#114). Mask modifiers and Shrink shape keys are ignored, so those bodies drape as if fully shown. On the outfit route, Keep may still refuse a few points near the cut rims.
- **Hem corners.** Skirts crumple at one side of the hem, and Linen and Denim curl there.
- **Small avatars.** The tee on the smallest avatar keeps with 1 open pair and one sleeve flipped up.
- **Skirt stretch.** p99 about 1.14 at Keep, from the waist gripping the hips. Tee and Tank reach about 1.07.
- **Live stretch.** p99 about 1.11 while handling, and up to about 2 at the top row of a sheet hanging from pins. Keep corrects this.
- **Fabrics.** Stiff fabrics now look stiffer, but Denim and Leather look alike and Silk, Knit and Cotton look alike. Not calibrated against real cloth.
- **Self-contact.** A vertex test, off within one ring of seams, and cloth can be pulled through itself while held.
- **Posed bodies.** The collision body is baked at Simulate.
- **Hardware.** One NVIDIA machine. Blender's XPBD assets are marked experimental.
- **Dense meshes.** A tee of about 4,300 vertices ran 26.2 FPS on an earlier build. Not rerun.

Avatar screenshots are kept outside the repository and must not be published.
