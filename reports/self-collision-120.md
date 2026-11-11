# Self-collision side memory (issue #120)

Date: 2026-11-11. Branch `next/self-collision-120` from master `67564d7`. Blender 5.3.0, same PC as the GN XPBD status report.

## Problem

Self-contact was a vertex proximity test. Each vertex probed along its own normal in both directions and pushed away from any foreign layer closer than 6 mm. The test had no memory of which side a vertex started on. Once Grab forced a vertex through a layer, the probe found the layer on the other side and pushed the vertex further onto the wrong side. The tangle then held until Reset.

## Change

Each vertex now remembers the layer it last faced and which side of it it was on.

- The layer is stored as a point in flat pattern space (`dd_side_rest`) with a side sign (`dd_side_sign`). A flat-pattern copy of the cloth maps that point back to its current world position and normal on every pass, however far the cloth has moved.
- When a vertex ends up on the wrong side of its remembered layer within 4.8 cm, it is pushed back by at most one cloth thickness per pass and loses its velocity into the layer. It keeps the old side until it is back.
- Only layers more than 4.8 cm away in the flat pattern count, so a curved or wrinkled sheet never triggers on itself. Seam rings stay excluded as before.
- Both attributes are passed to the stock XPBD updater as extra simulation attributes, so the memory survives between frames.
- Self-contact keeps its alternate-frame schedule. Running it every frame cost 5.8 ms per frame and measured worse.

All of this stays in the one Geometry Nodes XPBD engine. No new solver, no external program.

## Measurement

`tools/self_collision_bench.py` runs headless in Blender. A 70 cm cotton sheet (1,524 vertices) drapes on a flattened dome of 71,168 triangles. Grab lifts one corner, carries it over the centre and presses it onto the lower layer (depth 0) or 5 cm into it. It holds for 30 frames, releases, and settles for 60 frames. The metric counts intersecting triangle pairs that share no vertex (BVH self-overlap). The live substeps are 12. The sweep covers 4 corners at 2 press depths on each tree. Each run is deterministic.

| Mean of 8 runs | master | branch | change |
| --- | ---: | ---: | ---: |
| Crossing pairs at end of hold | 999 | 501 | -50% |
| Crossing pairs 60 frames after release | 913 | 374 | -59% |
| Mean crossing pairs during Grab | 204 | 138 | -32% |
| Mean crossing pairs after release | 988 | 565 | -43% |
| Headless solver frame, ms | 19.0 | 21.2 | +2.2 |

Grab FPS was measured through real viewport playback with the same 71k-triangle scene at the 10-substep live floor, 3 runs each. Playback is capped at the 30 fps clock.

| Run | master FPS / median / p95 ms | branch FPS / median / p95 ms |
| --- | --- | --- |
| 1 | 30.02 / 33.0 / 50.2 | 29.79 / 33.6 / 43.0 |
| 2 | 30.02 / 33.2 / 50.1 | 30.01 / 33.3 / 42.6 |
| 3 | 29.94 / 33.7 / 49.3 | 30.01 / 33.4 / 39.1 |

The first branch run had one 103 ms frame. An earlier first run also had one, near 102 ms. Master's worst frame was 53 ms.

## What remains

- Crossings that the cloth is pinned through while held cannot be removed until release, because a held patch is pinned exactly.
- About 40% of the tangle still survives release in the two worst corners (535 to 843 pairs). Edge-through-face crossings with every vertex on its correct side are not detected, and neither are vertices that crossed before they ever recorded a side.
- Seam rings are still excluded from self-contact.
- One synthetic scene. Not yet measured on a real avatar garment.
