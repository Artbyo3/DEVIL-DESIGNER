# Arrangement-point display performance

Measured October 28, 2026. Baseline: master 128098270cce94d4130c071ac93f170101753a49,
which includes the merged fit-map / Seam Shrink PR #21. The artist accepted the
exact handoff package and authorized the Prompt 11-only shipping workflow in this thread.

## Same-machine scene and method

- Windows 11 Pro 10.0.26200; Intel Core i5-13600KF, 20 logical processors.
- NVIDIA GeForce RTX 3060 Ti, driver 617.42; Blender 5.2.3 LTS, Solid shading.
- Separate factory-startup Blender process; no edits to the artist's open scene.
- Synthetic six-part avatar, 36,300 vertices; six live panels; 12 generated bounding
  volumes, 96 arrangement points; viewport region 1229 x 880 pixels.
- Three alternating Off/On pairs, 12 warmup frames and 120 measured orbit frames
  per condition. Full 360-degree orbit at the same camera distance and tilt.
- Each frame updates view rotation and swaps the complete Blender window through
  wm.redraw_timer(DRAW_WIN_SWAP). Whole-window measurements reach approximately
  144 FPS; they are not an uncapped GPU-throughput measurement.
- Frame and display-handler durations use perf_counter. CPU uses process_time
  over the same window, covering Blender process threads, divided by wall time
  and 20 logical processors for machine-normalized utilization. One fully busy
  core is 5% on this scale. Process utilization is not total system CPU load.
- GPU values are device-wide nvidia-smi utilization snapshots immediately after
  each timed window, not per-process utilization or GPU execution timings.
- cProfile runs separately after FPS/CPU timing, so its overhead is excluded
  from the reported FPS and unprofiled handler durations.

## Median of three runs

| Source | Display | FPS | Mean frame ms | Display handler ms | Blender CPU, machine normalized |
| --- | --- | ---: | ---: | ---: | ---: |
| Baseline | Off | 143.81 | 6.952 | 0.008 | 4.33% |
| Baseline | On | 38.79 | 25.779 | 21.536 | 5.21% |
| Fixed | Off | 143.83 | 6.951 | 0.009 | 4.03% |
| Fixed | On | 143.89 | 6.949 | 0.423 | 4.40% |

CPU at the one-core scale: baseline Off/On 86.63% / 104.20%; fixed Off/On
80.53% / 88.06%. Process CPU sampling includes renderer/driver threads and varies
across runs; the isolated handler duration is the more specific display measure.
Device-wide GPU snapshots: baseline Off 32-39%, On 25-29%; fixed Off 33-40%,
On 33-41%.

The display handler is approximately 51 times faster, with about 0.42 ms CPU
cost per orbit redraw rather than 21.54 ms. Whole-window On/Off frame times
are indistinguishable at the observed ceiling; do not infer zero absolute cost.
The handler still checks the evaluated avatar signature, projects point centers
for shared picking/visibility, selects the first visible point for each volume,
and submits two GPU batches. A genuine source-data change performs a cold rebuild.

## Root cause and evidence

The draw callback called world_points on every redraw, validating/parsing the stored
setup and resolving every unchanged point and its complete volume geometry each
time. The separate 40-frame profile recorded 3,840 _volume_resolve calls and
34,560 sample_radius calls. world_points consumed 1.713 of 2.041 seconds of
profiled callback time (84%); radius calculations alone consumed 1.236 seconds.
The callback also constructed and submitted 97 GPU batches per frame: one for
rings and one for each of 96 markers. These are display-path costs, not layering
collision or cloth costs. The fixed 40-frame profile contains no world_points,
_volume_resolve, sample_radius, trigonometry, or batch_for_shader calls and only
80 GPU draw calls total. The unprofiled handler falls from 21.536 ms to 0.423 ms.

## Display-only change

World geometry is cached by scene, view layer, avatar identity, stored volume
setup, evaluated world matrix and evaluated bounds. Projection/picking is cached
by world signature, region, viewport dimensions, camera matrix and canvas bounds.
A native GPU shader projects cached world vertices, preserves the 5-pixel,
16-segment filled markers, and applies the existing point-center and ring-endpoint
canvas/behind-camera rejection. Rings retain 32 segments and their original
first-visible-point orientation. The fragment shader retains Blender’s framebuffer-aware sRGB conversion, checked
in the actual native viewport as well as offscreen. One marker batch and one ring batch replace
per-point submissions. A change of the first visible point rebuilds only the
ring batch. Ordinary orbit changes projection uniforms, not GPU geometry.

There is no deliberate color, size, label, ring-detail, toggle, point, wrap or
arrangement-result change. Placement, arrangement, meshing, sewing, tack and cloth
math files are untouched. The existing arrangement/placement tests are unchanged.
Layered collision performance remains out of scope.

## Reproduce and verify

Run python tools/dev.py --arrangement-performance current --keep-scratch on the
source to measure. Baseline and fixed are output labels, not switches that load
old code: to remeasure baseline, run the same benchmark harness against the source
at the baseline commit, then against the fixed application source. Reports and
profiles go only to scratch. Use python tools/dev.py --clean after reviewing them.

The new GUI regression compares the former drawing algorithm with the optimized
shader in a real GPU offscreen buffer; it exercises perspective, orthographic,
canvas clipping and a camera close to/inside the volumes. It compares projected
hit targets exactly, checks cache invalidation, verifies no GPU-batch rebuilds on
ordinary orbit, and confirms H-off bypasses geometry. Small raster-edge differences
from CPU/GPU floating-point projection are measured rather than called bit-identical.
Embedded GLSL is checked for comments, Python is checked by tokenization plus AST,
and the real Blender GPU driver compiles and exercises both shader stages.

## Artist-test artifact

Installable archive: dist/devil_designer-0.8.0.zip. SHA-256:
d388ef42ec7b0626360c6e4a27048448bb797054d8d23a7ca8e623c3959b2d9c.
Packaged source-tree fingerprint (sorted archive path + NUL + source bytes + NUL):
70b45c24fe840f3e44a71085965a6636772ab31122947d228d240efc705495ce.
Artist acceptance and shipping authorization: "Ship it. The artist hands-on test
passed." The user explicitly authorized final checks, a PR, merge when green,
master verification and session closure, restricted to Prompt 11 display performance.
The accepted source-tree fingerprint and package SHA-256 above remain unchanged.
No version bump, tag, public release or unrelated feature is included.

## Automated verification and focused artist check

- The final python tools/dev.py --test --build --keep-scratch completed successfully:
  346 headless unit tests (14 existing environment-dependent skips), all nine
  Blender background suites, all seven GUI suites, and Blender extension validation.
- Display regression: 21 checks, including native viewport color/raster comparison.
  Offscreen mean channel error was at most 0.0000018; native mean channel error
  was 0.0000902, with matching maximum RGBA values and 354 coverage-edge pixels
  differing. This is not bit-identical rasterization; no style change is intended.
- The archive contains exactly 76 expected files with bytes equal to current
  source. No protected math source or existing arrangement/placement test changed.
- Python tokenization and AST checks, embedded-GLSL comment checks, GPU compilation,
  dead-code checks, PowerShell parsing/comment checks, batch comment checks and
  git diff --check passed.
- Publication scan checked source, archive payloads, 641 historical blobs and
  public Git identities. It preserves the pre-existing explicitly accepted author
  identity in 21 commits; this is a scoped scan, not a claim of a history purge.

The accepted artist checklist was: orbit the real avatar with H Off/On; click and right-click
points and check the unchanged flat/wrap result; edit a point/volume and move/scale
the body to confirm immediate updates; verify guide appearance and H behavior.
The artist reported this hands-on test passed before authorizing shipping.

## Timing records

| Source | Repeat | Display | FPS | Mean frame ms | Handler ms | Blender CPU | GPU snapshot |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 1 | Off | 143.81 | 6.952 | 0.008 | 3.46% | 39 % |
| Baseline | 1 | On | 38.79 | 25.779 | 21.536 | 5.15% | 28 % |
| Baseline | 2 | Off | 143.81 | 6.952 | 0.008 | 4.40% | 32 % |
| Baseline | 2 | On | 38.47 | 25.991 | 21.675 | 5.21% | 29 % |
| Baseline | 3 | Off | 141.56 | 7.063 | 0.010 | 4.33% | 33 % |
| Baseline | 3 | On | 39.87 | 25.080 | 20.936 | 5.50% | 25 % |
| Fixed | 1 | Off | 143.86 | 6.950 | 0.008 | 4.12% | 33 % |
| Fixed | 1 | On | 143.89 | 6.949 | 0.417 | 4.40% | 33 % |
| Fixed | 2 | Off | 143.81 | 6.953 | 0.010 | 3.93% | 40 % |
| Fixed | 2 | On | 143.89 | 6.949 | 0.423 | 4.12% | 41 % |
| Fixed | 3 | Off | 143.83 | 6.951 | 0.009 | 4.03% | 39 % |
| Fixed | 3 | On | 143.99 | 6.944 | 0.428 | 4.78% | 36 % |
