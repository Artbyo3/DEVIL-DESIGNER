# Action-time micro-stutter diagnosis

Measured October 29, 2026 against master `422ddee` (v0.10.0).

## Approved panel reuse: final candidate

The artist approved only garment.build_panels on October 29, 2026. That function now reuses unaffected meshes with explicit exact-input invalidation and a force_rebuild full-build fallback. All other protected functions and files remain unchanged. Round 1’s bounded exact-input wrap cache is retained.

The same fixture and 28 conditions were rerun before and after this change. The pre-change source includes round 1 wrap caching. Each condition retains two raw trials and a separate cProfile trial. No other Blender tests or builds ran during the final candidate profile. The fixture reports 38 undo entries; persistence validates 39 snapshots including the current state.

| Action | Round 1 cache median ms | Final median ms | Final maximum ms | Panels rebuilt |
| --- | ---: | ---: | ---: | --- |
| add pin | 65.59 | 37.54 | 170.02 | 1 |
| remove pin | 64.83 | 37.64 | 180.05 | 1 |
| add point | 46.05 | 12.62 | 13.35 | 0 |
| remove point | 47.16 | 12.83 | 13.51 | 0 |
| duplicate | 70.83 | 38.04 | 167.74 | 1 |
| drag release | 70.42 | 39.23 | 166.87 | 1 |
| move | 68.18 | 37.39 | 167.48 | 1 |

All pin, duplicate and move trials rebuild only the affected/new panel, never an unrelated panel. Unused arrangement-point add/delete rebuild zero panels. Drag rebuilds zero during motion and one on release. The original-master figures in the historical section below provide the original uncached comparison.

### Full condition matrix

Each cell is raw median before / after, milliseconds; drag uses release only, not its intentionally paced gesture.

| Action | Layout, H off | Layout, H on | Arranged, H off | Arranged, H on |
| --- | ---: | ---: | ---: | ---: |
| add pin | 64.92 / 37.80 | 65.57 / 37.17 | 138.21 / 103.84 | 64.91 / 37.62 |
| remove pin | 63.89 / 36.73 | 66.08 / 35.49 | 133.88 / 108.62 | 64.49 / 38.39 |
| add point | 45.38 / 13.21 | 46.05 / 12.55 | 47.64 / 12.62 | 46.23 / 12.56 |
| remove point | 47.30 / 12.96 | 47.25 / 12.63 | 47.97 / 13.02 | 46.87 / 12.98 |
| duplicate | 70.29 / 37.41 | 71.25 / 35.07 | 138.33 / 102.94 | 71.06 / 39.55 |
| drag release | 67.68 / 37.71 | 70.40 / 44.79 | 134.41 / 103.76 | 73.89 / 39.06 |
| move | 67.36 / 36.33 | 66.29 / 36.95 | 144.91 / 102.55 | 68.46 / 38.41 |

### Final main-thread attribution

Separate cProfile trials; nested totals overlap and must not be added. Snapshot/commit includes document validation; JSON means document dumps/loads totals, including validation and history serialization, not exclusive codec CPU. Update/evaluation getters are API timings, not an internal Blender profiler. Display is the actual arrangement draw callback, including invalidation when applicable.

| H | Piece | Action | Build ms | Mesh ms/calls | Resolve ms/calls | Wrap ms/calls | Commit ms | History ms | JSON ms | Display ms | Update/get ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| off | layout | add_pin | 32.82 | 10.08/1 | 10.03/3 | 0.00/0 | 1.93 | 35.42 | 49.89 | 0.01 | 1.16/0.94 |
| off | layout | remove_pin | 31.90 | 9.68/1 | 10.03/3 | 0.00/0 | 1.72 | 36.14 | 50.07 | 0.01 | 1.00/0.85 |
| off | layout | add_point | 20.37 | 0.00/0 | 10.09/3 | 0.00/0 | 0.00 | 0.00 | 14.02 | 0.01 | 1.14/1.01 |
| off | layout | remove_point | 22.09 | 0.00/0 | 10.84/3 | 0.00/0 | 0.00 | 0.00 | 15.85 | 0.01 | 1.42/1.17 |
| off | layout | duplicate | 33.59 | 9.91/1 | 10.37/3 | 0.00/0 | 1.78 | 35.05 | 49.76 | 0.01 | 1.33/0.87 |
| off | layout | drag | 31.94 | 9.60/1 | 10.05/3 | 0.00/0 | 1.75 | 34.87 | 70.23 | 0.52 | 1.07/0.99 |
| off | layout | move | 30.86 | 9.25/1 | 9.50/3 | 0.00/0 | 1.80 | 33.57 | 47.08 | 0.01 | 1.15/0.89 |
| off | arranged | add_pin | 35.95 | 9.58/1 | 13.42/4 | 0.00/0 | 1.75 | 34.30 | 49.17 | 0.01 | 1.20/1.44 |
| off | arranged | remove_pin | 35.43 | 9.39/1 | 13.71/4 | 0.00/0 | 1.97 | 34.47 | 47.18 | 0.01 | 1.01/1.35 |
| off | arranged | add_point | 19.97 | 0.00/0 | 10.03/3 | 0.00/0 | 0.00 | 0.00 | 14.02 | 0.01 | 1.01/0.88 |
| off | arranged | remove_point | 19.75 | 0.00/0 | 9.65/3 | 0.00/0 | 0.00 | 0.00 | 14.13 | 0.01 | 1.11/1.00 |
| off | arranged | duplicate | 39.39 | 9.58/1 | 16.14/5 | 0.00/0 | 1.91 | 35.05 | 49.61 | 0.01 | 1.17/1.52 |
| off | arranged | drag | 35.79 | 9.60/1 | 13.48/4 | 0.00/0 | 2.06 | 36.32 | 71.23 | 0.50 | 1.11/1.61 |
| off | arranged | move | 35.88 | 9.50/1 | 13.55/4 | 0.00/0 | 1.74 | 35.06 | 48.80 | 0.01 | 0.99/1.34 |
| on | layout | add_pin | 32.53 | 10.14/1 | 10.02/3 | 0.00/0 | 1.75 | 35.93 | 50.28 | 0.19 | 1.03/0.91 |
| on | layout | remove_pin | 32.36 | 9.50/1 | 10.40/3 | 0.00/0 | 1.86 | 34.44 | 47.65 | 0.17 | 1.07/1.13 |
| on | layout | add_point | 19.14 | 0.00/0 | 9.59/3 | 0.00/0 | 0.00 | 0.00 | 14.10 | 193.65 | 0.97/0.86 |
| on | layout | remove_point | 18.99 | 0.00/0 | 9.45/3 | 0.00/0 | 0.00 | 0.00 | 13.74 | 187.90 | 1.01/0.83 |
| on | layout | duplicate | 31.90 | 9.43/1 | 9.59/3 | 0.00/0 | 1.83 | 34.81 | 48.59 | 0.17 | 1.32/0.90 |
| on | layout | drag | 32.16 | 9.79/1 | 10.05/3 | 0.00/0 | 1.79 | 38.93 | 75.95 | 11.42 | 0.99/0.87 |
| on | layout | move | 32.13 | 9.97/1 | 9.76/3 | 0.00/0 | 1.73 | 33.75 | 47.81 | 0.16 | 1.01/0.90 |
| on | arranged | add_pin | 35.48 | 9.55/1 | 13.15/4 | 0.00/0 | 1.81 | 34.85 | 48.51 | 0.18 | 0.98/1.29 |
| on | arranged | remove_pin | 35.42 | 9.57/1 | 13.63/4 | 0.00/0 | 2.08 | 34.51 | 46.67 | 0.23 | 0.99/1.44 |
| on | arranged | add_point | 19.90 | 0.00/0 | 10.12/3 | 0.00/0 | 0.00 | 0.00 | 14.09 | 192.92 | 0.94/1.09 |
| on | arranged | remove_point | 20.54 | 0.00/0 | 10.43/3 | 0.00/0 | 0.00 | 0.00 | 13.62 | 189.75 | 1.16/0.99 |
| on | arranged | duplicate | 39.62 | 9.51/1 | 16.36/5 | 0.00/0 | 2.00 | 35.32 | 49.18 | 0.17 | 1.19/1.49 |
| on | arranged | drag | 35.31 | 9.60/1 | 13.00/4 | 0.00/0 | 1.96 | 36.68 | 72.66 | 11.38 | 0.99/1.23 |
| on | arranged | move | 34.65 | 9.25/1 | 12.95/4 | 0.00/0 | 7.83 | 57.33 | 64.51 | 0.18 | 1.01/1.27 |

### Numerical, display and residual-cost gates

- All 84 final outcomes match forced full rebuilds with wrapping also bypassed, and all 84 match the independent pre-change baseline outcomes exactly. The same comparison set hashes local vertex coordinates, polygon indices and world matrices without rounding, preserving wraps, placements and gaps. Added Blender regressions also compare UVs, rest/piece attributes, boundary and anchor metadata, vertex groups, materials and document stamps against forced full rebuilds.
- Invalidation regressions cover pins, unused arrangement points, seam-connected density, source geometry, UV layout, spacing, units, avatar transforms, active arrangement-point edits, clearance, piece order, externally edited/shared meshes and missing/corrupt cache metadata. Existing tests and profiling cover duplication/deletion, sewing and arranged/legacy transforms. Reset still removes drape/anchors, unhides panels and returns to frame start.
- Cache keys include full pattern/anchor records, actual seam-coupled boundary sampling, density/spacing/units, UV layout and exact resolved placement inputs. Existing mesh/UV/metadata buffers are verified before reuse. Missing, stale, edited, shared, parented or constrained panel state falls back to rebuilding; force_rebuild=True explicitly bypasses all panel reuse. Manually changed nonlegacy matrices fall back rather than introducing matrix-decomposition roundoff.

| H | Before FPS | Final FPS | Before cached draw ms | Final cached draw ms |
| --- | ---: | ---: | ---: | ---: |
| off | 95.51 | 101.18 | 0.00702 | 0.00589 |
| on | 99.79 | 107.70 | 0.13062 | 0.11913 |

Display uses the same 12 warmups, 120 measured redraws and 38 projected points. Prompt 11 cache code is unchanged and idle performance does not regress. Mean drag event plus window-swap wall time ranges 14.34-15.03 ms; maximum individual event is 31.28 ms. The deliberately paced approximately two-second gesture is not counted as release latency.

The fix does not make every cold action immediate: cold affected-piece wrapping still reaches the maxima above, and H-visible point add/delete still requires approximately 96–98 ms for its first guide redraw, outside synchronous action time. Persistent history validation remains in the tens of profiled milliseconds. These are addon costs, not an established Blender-native bottleneck; no behavior-changing workaround or protected math edit was made. This synthetic rig still does not reproduce the artist’s exact 2–3-second idle recovery, so hands-on acceptance remains necessary.

Reproduce with python tools/dev.py --action-performance current --keep-scratch. Raw trial and per-function data are disposable scratch outputs; this report preserves the matrix and gates.

## Final verified build awaiting artist acceptance

- Final-source verification passed: headless discovery, all 11 Blender background scripts, all 8 in-engine GUI scripts, and Blender extension package validation. The approved-function scope was verified by AST comparison; core.py, meshing.py, placement.py, tack_binding.py and ellipse_volumes.py remain byte-identical to master.
- All 42 final package-module hashes match the final profile source. All 82 archive members and their bytes match source plus README, LICENSE and SPEC exactly.
- Tokenization and AST inspection passed for 114 Python files; no comments, docstrings or standalone note strings. Dead-code/unused-import checks passed for 42 package modules. Chart HTML/JavaScript comment-delimiter checks and git diff --check passed. No repository __pycache__ directories remain.
- Publication scan passed for 169 source paths, 731 historical blobs, archives and public commit identities. Its existing notice retains explicitly accepted published-author identity in 27 historical commits; history was not rewritten.
- Installable package: `dist/devil_designer-0.10.0.zip`.
- Package SHA-256: `9df920ff2ca1374c7b774a1fabcc7b338394e994f6678359251a38d8ad9ee9a9`.
- Package-source fingerprint: `23136ca4049e866ee9028f6b00d8bba390d5fcab6ff00a92376cda7475545f6d` (sorted member names plus SHA-256 of each member's exact bytes).
- Artist acceptance of this package is still pending. Changes remain uncommitted on master. No commit, push, PR, merge, version bump or release was performed.

## Historical round 1 diagnosis and wrap-only candidate

The remaining sections record the earlier diagnosis, proposal and partial candidate as historical evidence; their approval-pending wording does not describe the final candidate above.


## Pre-fix diagnosis gate

The following complete 28-condition action table was written before any application fix. Two unprofiled trials per condition; median synchronous main-thread wall time in milliseconds. Drag reports release cost separately from its paced 60-event, approximately two-second gesture. A separate cProfile trial supplies attribution, not the primary latency figure.

| Action | Layout, H off | Layout, H on | Arranged, H off | Arranged, H on |
| --- | ---: | ---: | ---: | ---: |
| add pin | 461.29 | 478.53 | 450.80 | 463.99 |
| remove pin | 460.54 | 456.59 | 453.58 | 458.79 |
| add point | 443.90 | 435.08 | 438.30 | 438.94 |
| remove point | 440.41 | 438.38 | 438.06 | 449.41 |
| duplicate | 472.42 | 459.83 | 592.00 | 586.71 |
| drag release | 457.84 | 466.26 | 463.34 | 469.46 |
| move | 451.88 | 453.05 | 460.24 | 457.35 |

## Fixture and attribution

Separate factory-startup Blender 5.2.3 process, synthetic six-part 36,300-vertex avatar with a one-bone Armature modifier, six panels (three v2-wrapped and three layout), two seams, six pins, 39 undo entries, 35 mm mesh spacing. It is not the artist's exact avatar or modifier stack. Add/delete arrangement-point trials add or delete an unused custom chest point, so they do not intentionally invalidate the attached front-point placements.

All seven actions rebuild every existing panel: six panels for pin, point and move edits; seven for duplication. Editing one piece rebuilds the other five. Unrelated wrapped pieces rerun the per-row v2 wrap calculation even when their arrangement is unchanged. This is not a continuous redraw problem.

Nested cProfile totals below overlap and must not be summed. JSON includes all document dumps/loads, including history validation. Commit includes undo snapshot plus editing/validation. History is persistent history serialization. Resolve is resolve_point only; the expensive per-row section/curve work is inside wrap. Display is its draw callback, not the whole window swap. Update API timings use unprofiled context proxies around synchronous view-layer updates inside build_panels; these are API-boundary timings, not a Blender-internal thread breakdown.

| H | Piece | Action | Build ms | Wrap ms / calls | Mesh ms / calls | Resolve ms / calls | Commit ms | History ms | JSON ms | Display ms | Update API ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| off | layout | add_pin | 1292.03 | 1195.49 / 3 | 57.22 / 6 | 10.73 / 3 | 1.89 | 36.53 | 51.03 | 0.01 | 1.91 |
| off | layout | remove_pin | 1292.19 | 1194.48 / 3 | 57.88 / 6 | 10.67 / 3 | 1.72 | 36.10 | 50.39 | 0.01 | 1.93 |
| off | layout | add_point | 1284.79 | 1186.04 / 3 | 58.78 / 6 | 10.61 / 3 | 0.00 | 0.00 | 14.31 | 0.05 | 2.01 |
| off | layout | remove_point | 1287.80 | 1188.98 / 3 | 58.53 / 6 | 10.88 / 3 | 0.00 | 0.00 | 15.45 | 0.01 | 1.79 |
| off | layout | duplicate | 1322.05 | 1210.09 / 3 | 69.66 / 7 | 10.66 / 3 | 1.80 | 36.33 | 51.28 | 0.01 | 2.21 |
| off | layout | drag | 1280.50 | 1178.73 / 3 | 61.52 / 6 | 11.17 / 3 | 1.88 | 36.40 | 74.31 | 0.58 | 1.95 |
| off | layout | move | 1271.19 | 1174.72 / 3 | 57.23 / 6 | 10.26 / 3 | 2.10 | 35.59 | 49.82 | 0.01 | 1.80 |
| off | arranged | add_pin | 1278.00 | 1178.14 / 3 | 57.86 / 6 | 12.17 / 3 | 1.96 | 34.85 | 50.64 | 0.01 | 1.82 |
| off | arranged | remove_pin | 1278.24 | 1180.03 / 3 | 58.78 / 6 | 10.51 / 3 | 1.75 | 35.49 | 50.23 | 0.01 | 1.84 |
| off | arranged | add_point | 1302.93 | 1202.90 / 3 | 59.79 / 6 | 10.55 / 3 | 0.00 | 0.00 | 15.54 | 0.01 | 1.74 |
| off | arranged | remove_point | 1294.50 | 1194.91 / 3 | 58.63 / 6 | 11.64 / 3 | 0.00 | 0.00 | 14.61 | 0.01 | 2.00 |
| off | arranged | duplicate | 1719.66 | 1600.45 / 4 | 69.87 / 7 | 14.15 / 4 | 1.83 | 36.21 | 52.75 | 0.01 | 2.42 |
| off | arranged | drag | 1273.04 | 1175.27 / 3 | 58.04 / 6 | 10.72 / 3 | 1.78 | 34.13 | 70.97 | 0.64 | 1.89 |
| off | arranged | move | 1301.41 | 1201.69 / 3 | 58.43 / 6 | 11.69 / 3 | 1.95 | 36.03 | 51.45 | 0.01 | 1.74 |
| on | layout | add_pin | 1297.12 | 1195.50 / 3 | 61.16 / 6 | 10.73 / 3 | 1.84 | 38.51 | 53.99 | 0.22 | 1.89 |
| on | layout | remove_pin | 1284.20 | 1183.94 / 3 | 59.44 / 6 | 10.78 / 3 | 1.81 | 37.31 | 51.55 | 0.17 | 1.94 |
| on | layout | add_point | 1299.89 | 1202.64 / 3 | 58.12 / 6 | 10.82 / 3 | 0.00 | 0.00 | 14.73 | 192.64 | 2.11 |
| on | layout | remove_point | 1280.16 | 1184.50 / 3 | 56.55 / 6 | 10.29 / 3 | 0.00 | 0.00 | 14.42 | 186.44 | 1.94 |
| on | layout | duplicate | 1264.71 | 1153.61 / 3 | 67.65 / 7 | 11.20 / 3 | 1.88 | 35.69 | 51.33 | 0.18 | 2.11 |
| on | layout | drag | 1279.78 | 1177.29 / 3 | 59.69 / 6 | 11.51 / 3 | 2.39 | 36.74 | 74.77 | 12.51 | 1.73 |
| on | layout | move | 1279.35 | 1183.02 / 3 | 56.97 / 6 | 10.44 / 3 | 2.03 | 35.72 | 50.05 | 0.19 | 1.75 |
| on | arranged | add_pin | 1273.87 | 1175.52 / 3 | 58.90 / 6 | 10.62 / 3 | 1.89 | 34.56 | 49.65 | 0.36 | 1.76 |
| on | arranged | remove_pin | 1313.41 | 1214.06 / 3 | 60.37 / 6 | 10.65 / 3 | 1.90 | 37.22 | 50.32 | 0.17 | 1.99 |
| on | arranged | add_point | 1283.11 | 1181.14 / 3 | 58.82 / 6 | 11.60 / 3 | 0.00 | 0.00 | 15.22 | 193.95 | 2.24 |
| on | arranged | remove_point | 1247.34 | 1149.67 / 3 | 56.96 / 6 | 10.82 / 3 | 0.00 | 0.00 | 14.81 | 187.54 | 2.28 |
| on | arranged | duplicate | 1697.22 | 1572.50 / 4 | 69.82 / 7 | 15.16 / 4 | 1.82 | 36.83 | 53.60 | 0.17 | 3.02 |
| on | arranged | drag | 1275.79 | 1177.66 / 3 | 59.08 / 6 | 10.51 / 3 | 2.60 | 36.98 | 75.38 | 12.44 | 2.14 |
| on | arranged | move | 1283.99 | 1186.53 / 3 | 56.57 / 6 | 10.94 / 3 | 1.82 | 36.87 | 52.84 | 0.18 | 1.86 |

## Measured fix scope

The dominant measured cost is repeated pure wrapping in live_panels.position_panel, reached from garment.build_panels. First candidate: cache exact wrap inputs and immutable resulting coordinates outside the protected files. Do not alter v2 wrap math, panel triangulation, placement or simulation. Keep rebuilding semantics unchanged. Selective panel rebuilding would require separately approved changes to garment.build_panels; it is not authorized here.

The initial post-matrix idle assertion inspected projection outside the draw context and failed. That diagnostic-only bug was corrected, and the complete baseline was repeated successfully before the final comparisons below. Baseline source hashes were verified against master.

## Same-rig before/after

The corrected baseline completed all 28 conditions and its idle check. Every baseline application-file SHA-256 matches master 422ddee. The separate fixed process loads only the wrap-result memoization change. Each condition has two raw trials and a separate profiled trial. Timings below are medians of the two raw trials; a median of two can conceal a cold/warm difference, so the cold caveat below is important.

Arrangement-point edits are avatar-global. For those rows, Target identifies the currently selected arranged/layout piece, not ownership of the edited point.

| H | Target | Action | Before action ms | Cached action ms | Before first paint ms | Cached first paint ms | Panels rebuilt |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| off | layout | add_pin | 474.51 | 66.92 | 28.64 | 28.33 | 6 |
| off | layout | remove_pin | 467.93 | 65.77 | 27.91 | 28.32 | 6 |
| off | layout | add_point | 443.95 | 48.17 | 27.68 | 27.17 | 6 |
| off | layout | remove_point | 447.69 | 49.69 | 28.33 | 28.74 | 6 |
| off | layout | duplicate | 481.73 | 72.92 | 31.27 | 30.94 | 7 |
| off | layout | drag | 463.22 | 66.35 | 28.68 | 27.60 | 6 |
| off | layout | move | 464.29 | 65.25 | 28.22 | 27.78 | 6 |
| off | arranged | add_pin | 459.86 | 136.83 | 28.65 | 28.99 | 6 |
| off | arranged | remove_pin | 456.50 | 131.21 | 27.86 | 26.69 | 6 |
| off | arranged | add_point | 437.05 | 46.84 | 27.95 | 27.99 | 6 |
| off | arranged | remove_point | 437.73 | 47.31 | 27.91 | 27.97 | 6 |
| off | arranged | duplicate | 599.81 | 137.93 | 30.02 | 29.97 | 7 |
| off | arranged | drag | 462.76 | 132.16 | 29.58 | 27.31 | 6 |
| off | arranged | move | 474.12 | 137.33 | 27.59 | 27.31 | 6 |
| on | layout | add_pin | 459.34 | 63.78 | 27.88 | 27.41 | 6 |
| on | layout | remove_pin | 464.95 | 64.52 | 28.68 | 26.64 | 6 |
| on | layout | add_point | 454.02 | 45.94 | 99.38 | 98.70 | 6 |
| on | layout | remove_point | 435.81 | 46.02 | 97.83 | 93.59 | 6 |
| on | layout | duplicate | 466.71 | 70.57 | 30.17 | 29.73 | 7 |
| on | layout | drag | 486.30 | 64.90 | 30.82 | 28.52 | 6 |
| on | layout | move | 480.24 | 65.19 | 27.56 | 27.64 | 6 |
| on | arranged | add_pin | 473.93 | 65.68 | 27.82 | 28.03 | 6 |
| on | arranged | remove_pin | 470.87 | 65.20 | 28.69 | 28.00 | 6 |
| on | arranged | add_point | 456.34 | 46.21 | 100.90 | 97.41 | 6 |
| on | arranged | remove_point | 458.02 | 48.94 | 97.83 | 97.11 | 6 |
| on | arranged | duplicate | 612.11 | 72.67 | 31.66 | 30.93 | 7 |
| on | arranged | drag | 468.75 | 65.12 | 30.27 | 28.18 | 6 |
| on | arranged | move | 463.34 | 65.52 | 29.77 | 26.86 | 6 |

First paint is the full Blender window redraw/swap after the action, not an addon-only CPU timing. It excludes the action, and includes frame/driver/window-system waiting. Build-internal view-layer update calls are already inside action time. A final explicit update is measured separately in raw reports; it is not evidence that all internal depsgraph work is zero.

## What improved, and what did not

- Only identical wrap inputs are memoized, with a 16-entry LRU. The complete serialized argument payload includes every mesh vertex, all resolved frame/ellipse/stack inputs, width, minimum and minimum clearance. JSON float round trips preserve signed zero. Results are immutable coordinate tuples. Disable/unregister clears the cache. No timers, deferred edits, approximation, reduction in density, or changed v2 math were introduced.
- Unchanged wraps avoid rebuilding their per-row 4,097-sample arc-length tables. Meshing, undo, document persistence, panel recreation and existing reset semantics deliberately still run. The cache is bounded; a new input or eviction must run the original computation.
- For example, arranged H-off add-pin raw trials were 207.82 ms then 65.85 ms after caching. The first was a cold miss, not an immediate action. Reporting only the warm trial would overstate the result. Arranged duplication also retains a cold-input risk.
- Adding/removing an unused arrangement point still invalidates the whole display-world cache. With H on, its first repaint remains about 94-99 ms, versus about 27-31 ms for an ordinary repaint. This is real addon work in a legitimately cold display rebuild; the Prompt 11 unchanged-redraw cache is still effective. No claim is made that this remaining cost is structural or impossible to optimize.
- This is a partial fix, not proof that every named action now feels immediate. The next rebuild optimization crosses the protected-file boundary described below; no such change was made.

## Remaining action attribution after caching

Profile totals include first paint and ten manually dispatched TIMER events after the action. They overlap, and must not be added. These are instrumented diagnostics, not raw action latency. Rows cover every visibility/target condition.

| H | Target | Action | Build ms | Actual wrap calls | Mesh ms | Commit ms | History ms | JSON ms | Display ms | Raw update API ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| off | layout | add_pin | 92.03 | 0 | 58.85 | 1.85 | 36.98 | 51.64 | 0.04 | 1.26 |
| off | layout | remove_pin | 92.05 | 0 | 59.36 | 2.01 | 35.62 | 49.76 | 0.01 | 1.44 |
| off | layout | add_point | 97.01 | 0 | 61.06 | 0.00 | 0.00 | 15.56 | 0.01 | 1.65 |
| off | layout | remove_point | 93.53 | 0 | 60.73 | 0.00 | 0.00 | 15.40 | 0.01 | 1.53 |
| off | layout | duplicate | 106.60 | 0 | 69.72 | 2.00 | 36.58 | 51.40 | 0.01 | 1.77 |
| off | layout | drag | 90.46 | 0 | 57.20 | 1.99 | 34.51 | 72.47 | 0.66 | 1.67 |
| off | layout | move | 91.89 | 0 | 57.37 | 1.91 | 35.10 | 50.64 | 0.01 | 1.98 |
| off | arranged | add_pin | 88.16 | 0 | 56.46 | 1.95 | 36.44 | 52.21 | 0.01 | 1.86 |
| off | arranged | remove_pin | 91.72 | 0 | 58.51 | 1.71 | 34.55 | 48.12 | 0.01 | 1.99 |
| off | arranged | add_point | 90.32 | 0 | 57.54 | 0.00 | 0.00 | 15.82 | 0.01 | 1.67 |
| off | arranged | remove_point | 89.39 | 0 | 57.08 | 0.00 | 0.00 | 14.20 | 0.01 | 2.02 |
| off | arranged | duplicate | 106.97 | 0 | 67.20 | 1.99 | 35.92 | 51.27 | 0.01 | 1.76 |
| off | arranged | drag | 89.52 | 0 | 56.76 | 2.14 | 35.32 | 71.66 | 0.59 | 2.20 |
| off | arranged | move | 89.87 | 0 | 57.02 | 1.74 | 35.55 | 50.22 | 0.01 | 2.69 |
| on | layout | add_pin | 89.62 | 0 | 57.40 | 1.85 | 35.79 | 50.03 | 0.36 | 1.85 |
| on | layout | remove_pin | 90.86 | 0 | 57.33 | 1.76 | 33.52 | 47.16 | 0.19 | 1.74 |
| on | layout | add_point | 90.51 | 0 | 56.97 | 0.00 | 0.00 | 14.37 | 192.15 | 1.69 |
| on | layout | remove_point | 90.98 | 0 | 58.25 | 0.00 | 0.00 | 14.67 | 186.89 | 1.73 |
| on | layout | duplicate | 103.94 | 0 | 68.00 | 1.81 | 34.41 | 48.85 | 0.25 | 2.11 |
| on | layout | drag | 94.98 | 0 | 59.86 | 1.89 | 37.61 | 74.98 | 11.76 | 1.72 |
| on | layout | move | 92.48 | 0 | 58.46 | 1.94 | 35.45 | 50.77 | 0.19 | 1.72 |
| on | arranged | add_pin | 92.72 | 0 | 58.59 | 1.76 | 34.75 | 51.36 | 0.21 | 1.74 |
| on | arranged | remove_pin | 94.00 | 0 | 59.78 | 2.03 | 36.83 | 51.72 | 0.18 | 1.63 |
| on | arranged | add_point | 90.71 | 0 | 57.96 | 0.00 | 0.00 | 15.03 | 194.99 | 1.99 |
| on | arranged | remove_point | 92.67 | 0 | 58.76 | 0.00 | 0.00 | 16.07 | 187.87 | 1.89 |
| on | arranged | duplicate | 106.80 | 0 | 66.66 | 2.12 | 34.45 | 50.12 | 0.19 | 1.86 |
| on | arranged | drag | 91.19 | 0 | 58.02 | 2.00 | 36.06 | 73.54 | 11.83 | 1.81 |
| on | arranged | move | 92.14 | 0 | 58.64 | 1.88 | 36.19 | 50.37 | 0.19 | 1.80 |

## Drag and delayed recovery

| H | Target | Before motion mean ms | Cached motion mean ms | Before release ms | Cached release ms | Before TIMER burst ms | Cached TIMER burst ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| off | layout | 15.15 | 15.99 | 463.22 | 66.35 | 1.63 | 1.20 |
| off | arranged | 15.12 | 15.48 | 462.76 | 132.16 | 1.17 | 1.14 |
| on | layout | 15.23 | 15.58 | 486.30 | 64.90 | 1.25 | 1.14 |
| on | arranged | 15.69 | 15.81 | 468.75 | 65.12 | 1.14 | 1.21 |

The sixty paced movement events use the real editor MOVE gesture and window redraw; the release uses the real handle_event path. Movement builds no panels; the release builds them all. This fixture reproduces the release hitch, not a 2-3-second post-idle recovery. The TIMER burst checks one periodic body-reference refresh but is not a recording of Blender's naturally scheduled event queue. The artist's during-motion/delayed recovery observation therefore remains unconfirmed on their actual avatar. The point and pin actions call the production operator/edit/persist paths, excluding pointer hit-testing and selection UI.

## Idle display regression guard

| Source | H | FPS, same static view | Cached display CPU ms/redraw | Visible projected points |
| --- | --- | ---: | ---: | ---: |
| baseline | off | 95.51 | 0.0069 | 0 |
| baseline | on | 98.03 | 0.1333 | 38 |
| fixed | off | 100.24 | 0.0063 | 0 |
| fixed | on | 106.83 | 0.1268 | 38 |

Both sources use 12 warmup redraws and 120 measured redraws per H condition on this same rig. The shader callback is timed inside the real draw context. These are same-machine samples, not a statistical FPS guarantee. The unchanged cache remains at roughly 0.13 ms/redraw; this run shows no idle regression. Original Prompt 11 orbit tests use a different view and scene configuration and are not numerically interchangeable with this static-view/editor-open measurement.

## Numerical preservation

All 84 cached action outcomes match an immediate rebuild with the cache bypassed, hashing exact local vertex coordinates, face indices and world matrices. All 84 also match the corresponding baseline outcome hashes across independent runs. These compare exact IEEE float values serialized without rounding, including resulting wraps, world positions and clearances/gaps. Six cache unit tests additionally check packed-double equality against the original function, normal and spiral widths, complete-key invalidation, signed-zero distinction, bounded eviction and uncached failures. Simulation, meshing, core editing and placement source files are unchanged.

## Approval required for the next root-level fix

Proposed protected edit: `devil_designer/garment.py`, function `build_panels`.

Introduce an explicit per-piece invalidation/reuse path so unchanged pieces do not rerun fabric_mesh, mesh decoration and positioning on another piece's edit. Derive affected pieces from geometry, spacing/units, avatar frame, arrangement inputs, UV layout and sewing boundary-plan dependencies; retain the current full rebuild as the fallback. Pin-only and unused-point edits would update their needed metadata rather than regenerate six unchanged meshes. Preserve the current drape-reset, anchor, UV, sewing and legacy-transform semantics and use the existing numerical algorithms without alteration. Validate full output equivalence against the existing full build before accepting reuse.

This is a proposal only. No protected file has been modified. Approval is required before implementing it. The display cold-rebuild cost above is a separate possible follow-up, not authorization to change Prompt 10 v2 math or add features.

## Reproduce

`python tools/dev.py --action-performance baseline --keep-scratch` on unchanged master, then `--action-performance fixed --keep-scratch` on the candidate. Raw profiles and source hashes are written to ignored scratch. Run without concurrent CPU/GPU benchmarks. `python tools/dev.py --test --build` runs the repository's complete configured verification and packages the candidate. `python tools/dev.py --clean` removes diagnostic scratch after review. Do not replace an artist's open scene; the rig always runs in a separate factory-startup process.

## Verification status

The checks below passed for the partial-fix candidate. The application goal remains approval-blocked; this report is not a shipping or artist-acceptance claim.

## Depsgraph API boundaries by action

Medians of two raw trials, in milliseconds. Update/getter calls wait synchronously on Blender and may include addon handlers. These are API boundaries, not an internal Blender/Armature thread breakdown; they do not establish a Blender-internal bottleneck. The rebuilt fixture panels are 1-6, with wrapped panels 1/3/5 and layout panels 2/4/6. Duplication adds panel 7.

| H | Target | Action | Update calls before / cached | Update ms before / cached | Eval-get ms before / cached | Final update ms before / cached |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| off | layout | add_pin | 6 / 6 | 2.062 / 1.346 | 1.464 / 1.522 | 0.007 / 0.006 |
| off | layout | remove_pin | 6 / 6 | 2.120 / 1.449 | 1.488 / 1.366 | 0.006 / 0.006 |
| off | layout | add_point | 6 / 6 | 2.130 / 1.803 | 1.546 / 1.835 | 0.004 / 0.004 |
| off | layout | remove_point | 6 / 6 | 2.188 / 1.645 | 1.572 / 1.581 | 0.004 / 0.004 |
| off | layout | duplicate | 7 / 7 | 2.445 / 1.970 | 1.507 / 1.706 | 0.006 / 0.007 |
| off | layout | drag | 6 / 6 | 1.905 / 1.671 | 1.631 / 1.585 | 0.007 / 0.006 |
| off | layout | move | 6 / 6 | 1.958 / 1.889 | 1.584 / 1.765 | 0.007 / 0.006 |
| off | arranged | add_pin | 6 / 6 | 1.921 / 1.750 | 1.445 / 1.611 | 0.006 / 0.006 |
| off | arranged | remove_pin | 6 / 6 | 1.955 / 2.075 | 1.553 / 1.783 | 0.006 / 0.008 |
| off | arranged | add_point | 6 / 6 | 1.842 / 1.712 | 1.374 / 1.706 | 0.003 / 0.003 |
| off | arranged | remove_point | 6 / 6 | 1.952 / 1.890 | 1.769 / 1.711 | 0.004 / 0.003 |
| off | arranged | duplicate | 7 / 7 | 2.015 / 1.852 | 1.959 / 2.274 | 0.007 / 0.007 |
| off | arranged | drag | 6 / 6 | 1.821 / 1.977 | 1.437 / 1.728 | 0.006 / 0.006 |
| off | arranged | move | 6 / 6 | 2.205 / 2.096 | 1.545 / 2.031 | 0.007 / 0.007 |
| on | layout | add_pin | 6 / 6 | 1.933 / 1.827 | 1.571 / 1.653 | 0.006 / 0.006 |
| on | layout | remove_pin | 6 / 6 | 1.826 / 1.771 | 1.540 / 1.609 | 0.008 / 0.006 |
| on | layout | add_point | 6 / 6 | 2.459 / 1.696 | 2.026 / 1.607 | 0.004 / 0.003 |
| on | layout | remove_point | 6 / 6 | 1.925 / 1.687 | 1.438 / 1.719 | 0.004 / 0.004 |
| on | layout | duplicate | 7 / 7 | 2.530 / 2.021 | 1.578 / 1.568 | 0.007 / 0.006 |
| on | layout | drag | 6 / 6 | 2.026 / 1.737 | 1.414 / 1.699 | 0.007 / 0.006 |
| on | layout | move | 6 / 6 | 2.287 / 1.783 | 1.666 / 1.778 | 0.006 / 0.006 |
| on | arranged | add_pin | 6 / 6 | 1.978 / 1.761 | 1.501 / 1.666 | 0.006 / 0.006 |
| on | arranged | remove_pin | 6 / 6 | 2.169 / 1.671 | 1.904 / 1.588 | 0.008 / 0.006 |
| on | arranged | add_point | 6 / 6 | 2.203 / 1.827 | 1.461 / 1.622 | 0.003 / 0.003 |
| on | arranged | remove_point | 6 / 6 | 2.332 / 1.873 | 1.581 / 1.756 | 0.004 / 0.004 |
| on | arranged | duplicate | 7 / 7 | 1.949 / 1.823 | 1.879 / 1.984 | 0.007 / 0.007 |
| on | arranged | drag | 6 / 6 | 1.911 / 1.821 | 1.500 / 1.598 | 0.009 / 0.006 |
| on | arranged | move | 6 / 6 | 1.911 / 1.765 | 1.528 / 1.838 | 0.007 / 0.007 |

## Verified candidate, not artist-accepted

- Complete configured verification passed: headless discovery, all 11 Blender background scripts, all 8 in-engine GUI scripts, and Blender extension validation.
- Privacy check passed for 169 source paths, 723 historical blobs, archives and public commit identities. It reports the existing accepted published-author identity in 27 commits. History was not rewritten; this is the scanner's stated scope, not an unrestricted privacy-purge claim.
- Dead-code/unused-import checks passed for 42 package modules. Tokenization plus AST checks passed for 114 Python files. The full suite also checks embedded shader comment delimiters. Changed production code is Python only. git diff --check passed.
- All 82 ZIP members and their bytes match package source plus README, LICENSE and SPEC exactly. The candidate is dist/devil_designer-0.10.0.zip; no version bump or release was requested.
- Candidate SHA-256: `fc2edebcbfcd715d0011edf976ba63410763b0d7cbc78774c021f0704efc1419`.
- core.py, garment.py, meshing.py, placement.py, tack_binding.py and ellipse_volumes.py are byte-identical to master. No PR, commit, push, merge or release was performed. This is a partial improvement awaiting the protected-file decision, not a completed performance fix.
- The validated developer runner removed 42 disposable scratch files after review. scratch no longer exists; the verified ZIP remains in dist. Changes remain uncommitted on master, with no unrelated working-tree edits present at the start.
