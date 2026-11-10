# AUDIT2 fixes and verification

Worktree: `devil_designer-fixes`. Branch: `next/audit2-fixes`. Base: explicitly requested `81ce681`, rather than the later local `master` tip. Audit source: `next/audit-round2`, commit `dc9b578`, findings 1–5 in `reports/audit-round2-2026-11-09.md`.

## Per-finding changes

| Finding | Root cause | Fix | Commit | Regression evidence |
| --- | --- | --- | --- | --- |
| 1. Merge followed by Delete removes a neighbour | The corner setter retains a two-point selection whose second index has changed meaning | Replace selection with the surviving point after merge | `64faaad` | `test_merge_then_delete_removes_only_merged_point`: ordinary adjacency and loop closure both fail on base with stale keys; both pass after, including deletion of only the merged vertex and preservation of every neighbour ID |
| 2. M:N sewing follows click order | Raw clicked edges reach range construction without adjacency ordering or validation | Order each side along its path, including closed-loop wraparound, and refuse disconnected or mixed-path selections | `2d4bb54` | `test_mn_sewing_orders_reverse_clicks_and_wraparound` and `test_mn_sewing_refuses_disconnected_edges_on_either_side`: five failing base subcases; all pass after |
| 3. Normal seams show a direction warning | Normal opposite-direction correspondence is emitted as a warning flag, with inconsistent label/line filtering | Remove the normal-direction flag and use the remaining warning flags consistently in 2D and 3D | `2055a9f` | `test_normal_opposite_direction_seam_has_no_warning_flags`: fails on base, passes after; existing mismatch and partial-span warnings remain tested |
| 4. Splits and piece merges lose Elastic | Splits remap seams alone; merging an absorbed piece does not remap its elastic references; repair accounting excludes elastics | Copy shrink settings onto both split spans, remap absorbed-piece elastic references, and report elastic records dropped by topology pruning | `ce078ef` | Straight/curved three-way split, absorbed-piece merge, and dropped-elastic reporting: four failing base subcases; all pass after, including shrink, total length, persistence, undo and redo checks |
| 5. Starter/library loading keeps stale selections | Document replacement uses compatibility setters that preserve multi-selection sets | Share document replacement that clears all selection kinds and pivot, selects the new piece, and pairs document/selection undo snapshots | `8f17179` | Starter and library action paths, each with piece/point/edge/path selection: eight failing base subcases; all pass after, including bounds, Delete and undo/redo |

The document replacement fix also removes the adjacent selection-history stack mismatch described by audit finding 7. Other lower-priority audit findings are outside this mission.

## Verification

All test executions occurred after implementing the five fixes. Processes ran sequentially in the foreground, with no detached test runs.

- Before evidence: extracted the original product package from `81ce681` into ignored scratch, then ran the eight new test methods against that package. Result: 20 assertion failures across the subcases, zero test errors. Every requested finding has a failing regression on the original code.
- After evidence: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -m unittest test_selection test_seams test_sewing_preview test_matrix_features`: 84 tests passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 tools/dev.py --quick --keep-scratch`: static import/dead-code/draw integrity and the complete headless unit suite passed. The headless suite contains 479 tests, including meshing regression and token/AST Rule Zero checks. Blender-dependent headless fixtures use mocks and do not establish real GUI correctness.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.check_comments`: 140 Python files passed comment-token and AST standalone-string/docstring inspection.
- `git diff --check`: passed.

Real Blender 5.2.4 checks, separate from mocked headless tests:

- `blender --background --factory-startup --python-exit-code 1 --python tests/blender_advanced.py`: passed, including real garment geometry, M:N sewing springs, finalization and garment-library round trips.
- The same background invocation for `tests/blender_sewing_preview.py`: passed.
- `xvfb-run -a blender --enable-event-simulate --factory-startup --python tools/run_blender_gui.py -- gui_viewport_sewing`: passed, 118 GUI checks.
- The same GUI invocation for `gui_design`: failed at `ellipse tool creates four Bezier anchors`, after the merge/undo, curve editing, length and split assertions passed.
- The same GUI invocation for `gui_library`: failed at `Menu card enforces native minimum 180px width`.
- Both failed GUI suites were rerun against the untouched `81ce681` product, tests and tools under identical Xvfb conditions. Each failed at the identical assertion. These are baseline failures; no unrelated product or test changes were made to suppress them.

## Limits and repository state

All five requested product fixes are implemented and have failing-before/passing-after regression evidence. The two baseline GUI failures remain unresolved and limit broader GUI verification. This is not a ready-for-artist-test build or a shipping report: no full battery, package validation, or complete core-workflow gate was run, as requested. No package was produced, no protected meshing/placement/tack-binding code changed, and no merges, pushes, or GitHub writes occurred. The original audit worktree and its unrelated untracked report were preserved. Disposable scratch is cleaned through the validated developer runner after recording these results.
