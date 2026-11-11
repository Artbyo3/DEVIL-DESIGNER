# Live drape performance: benchmark, cost map, and the first two fixes

Branch `next/fable-wave` from master `5affc6a`. Blender 5.3.0, Windows, 20 threads. Target: 30 stable FPS on a ~70k-triangle avatar with 30 panels.

## How to reproduce

```
python tools/live_benchmark.py              # 3 runs, headless + viewport, 3/10/20/30 panels
python tools/live_benchmark.py --headless-only --runs 1 --panels 3,30
```

The scene is synthetic and identical every run:

- **Body.** A torso ellipsoid (0.16 × 0.13 × 0.6 m). It comes as a dense build (70,144 triangles) and a light build (720 triangles) of the same shape.
- **Cloth.** Panels sewn into six-panel tubes, layered outward like an outfit (shirt, jacket, coat), with the top rows pinned. It uses the default 2 cm spacing and 12 live substeps.
- **Vertex counts.** 30 panels is 16,692 cloth vertices here. That is more than the 11,790 in the inspection's layout, because the outer layers are wider.
- **Headless frame time** is the wall time of `frame_set`.
- **Viewport frame time** runs real playback, with the minimal editor open on a 3D view. It is the time from frame start to that frame's viewport draw. "Delivered" is the frame-to-frame interval at the product's 30 fps cap.

The cost map comes from ablation inside one process, using the same compiled garment each time:

| Ablation | What it removes |
|---|---|
| shell off | The Body Shell input is empty |
| true surface off | The body is a single far-away triangle |
| collision off | Both of the above |
| self-contact off | The self-contact pass is skipped |

**Python** time is every frame and depsgraph handler, plus the editor's `draw_overlay` and `modal`, wrapped with timers.

## Results (median of 3 runs, ms per frame)

| Panels | Cloth verts | Master headless | Branch headless | Master viewport (delivered) | Branch viewport (delivered) |
|---:|---:|---:|---:|---:|---:|
| 3 | 1,320 | 37.9 | 23.2 | 39.8 (41.1) | 23.9 (33.3, capped at 30 fps) |
| 10 | 4,628 | 63.3 | 37.9 | 65.1 (66.7) | 40.5 (41.7) |
| 20 | 10,192 | 125.2 | 66.6 | 126.0 (127.8) | 68.7 (72.5) |
| 30 | 16,692 | 210.5 | 101.7 | 207.3 (213.0) | 104.0 (105.4) |

Seam gap max (0.34 / 0.56 / 0.59 / 0.68 mm) and stretch p99 (1.285 / 1.281 / 1.292 / 1.297) are identical between master and the branch at every panel count.

### Cost map, master (mean ms per frame)

| Panels | Solver + self-contact | Shell contact | True-surface pass | Python |
|---:|---:|---:|---:|---:|
| 3 | 9.7 | 23.4 | 4.7 | 0.0 |
| 10 | 18.0 | 38.7 | 6.5 | 0.0 |
| 20 | 27.2 | 85.5 | 14.0 | 0.0 |
| 30 | 35.8 | 154.4 | 25.0 | 0.0 |

### Cost map, branch (mean ms per frame)

| Panels | Solver | Self-contact | Shell contact | True-surface pass | Python |
|---:|---:|---:|---:|---:|---:|
| 3 | 8.5 | 2.8 | 11.7 | 0.4 | 0.0 |
| 10 | 12.3 | 7.2 | 19.0 | 2.8 | 0.0 |
| 20 | 21.4 | 8.6 | 34.8 | ~0 | 0.0 |
| 30 | 30.2 | 9.6 | 59.5 | 0.5 | 0.0 |

- **Python per frame.** Handlers cost 0.0 ms, because the add-on's only handler is `depsgraph_update_post`, which frame changes do not fire. With the editor open in viewport playback, Python costs 0.5 to 0.7 ms median, with a p95 of 3 to 6 ms.
- **Self-contact.** It runs every second frame. At 30 panels it costs about 19 ms on its own frames, which averages to 9.6 ms.
- **Fixed overhead.** About 15 to 16 ms per frame does not scale with cloth size. It comes from the stock XPBD pipeline: bundle handling, per-geometry loops and effector evaluation.

### Repeatability

- **Baseline.** The worst full-variant spread across 3 runs is 4.0%, inside 5%.
- **After work order 2 and the shell bound.** 2.3%, inside 5%.
- **Final.** 18.5%, outside 5%. One disturbed run caused it: the 10-panel median was 44.5 ms against 37.9 and 37.5 ms in the other two runs.
- **Disturbance.** The artist's Blender (pid 63080) was open for every run. It used 78 CPU-seconds during the session, so it was not fully idle. The "no other Blender open" condition was not met.

## What changed and why

1. **True-surface pass, proxy gate.** The true-surface pass ran two nearest-surface queries per cloth point against the full avatar. BVH nearest search costs much more on a dense mesh when the cloth sits centimetres away, which hanging cloth usually does.
   - **The bake** now makes a decimated proxy of at most 3,000 triangles. It records the worst distance from the real body's vertices to the proxy.
   - **The gate.** A point that is outside the proxy by more than that deviation, plus the contact reach (margin / 0.6), plus a 2 mm pad, cannot touch the body.
   - **For those points**, the real-body query starts from the proxy's nearest point, which makes it cheap, and contact is forced off. Every other point is queried exactly as before.
   - **Equivalence.** The drape is bit-identical to the ungated query: 0.0 mm apart after 60 frames.
   - **Effect.** The density penalty at 3 panels went from 4.4 ms to 0.1 ms.
2. **Shell, bounded to 8,000 triangles.** The native XPBD collider cost scales with the shell's triangle count. A far-away 1-triangle shell costs nothing, and a 2,000-triangle shell already costs 35 ms at 30 panels.
   - **Raw size.** The 5 mm voxel shell is 97k triangles on the torso, 182k on the limbed `blender_torso` body and 45k on the demo avatar. Those counts follow avatar surface area.
   - **The fix.** It is now decimated to 8,000 triangles.
   - **Accuracy.** The decimated shell stays within 0.25 mm of the voxel shell on the torso and the demo avatar, and within 0.86 mm on the limbed body (p99 0.43 mm). All of that is below the 5 mm voxel size the shell already has.
   - **Effect.** At 30 panels the shell went from 154 ms to 60 ms.
3. **Self collision off now skips self-contact.** With the toggle off, the self-contact graph still ran at zero thickness and moved nothing. A lazy geometry switch now skips it. The drape is bit-identical, and turning self collision off saves about 3 ms per frame at 3 panels and about 10 ms at 30. The default, self collision on, is unchanged.

## The 30-panel vertex budget (decision for the artist)

Fitting the branch's viewport numbers gives frame time ≈ 16.5 ms plus 5.25 µs per cloth vertex. A stable 30 FPS (33.3 ms) then needs:

- **By p95:** about **2,650 cloth vertices in total**.
- **By median:** about **3,200 cloth vertices**.

On master the same fit gives 19.0 ms plus 11.0 µs per vertex, a budget of about 1,000 to 1,300 vertices.

At 30 panels that is about 90 to 105 vertices per panel. Because vertex count goes as 1/spacing², that means:

| Layout | Default verts | Spacing for the budget |
|---|---:|---:|
| Inspection's 30-panel layout | 11.8k | ~3.8 cm |
| This benchmark's 30-panel layout | 16.7k | ~4.6 cm |

At the default 2 cm spacing, 30 panels runs at about 9.5 FPS on the branch, up from about 4.7 FPS on master. Getting 30 FPS at default density would need roughly another 3× cut in per-vertex cost on top of this branch.

## Left open

- **Shell contact** is still the largest single cost: 59.5 ms at 30 panels. `SHELL_TRIANGLES` is a tunable: about 4,000 triangles would save an estimated 15 ms at 30 panels, at about 1.4 mm worst shell deviation on the limbed body.
- **The fixed ~16 ms** of stock pipeline overhead per frame has not been examined.
- **Self-contact** alternates with body contact frame by frame, which shows up as a two-level frame-time pattern.
- **Solver per-vertex cost** (12 substeps) was not touched, because fewer substeps would change stretch and seam closure.
