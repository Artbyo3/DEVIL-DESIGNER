# Issue 76 Phase 1 build: ready for artist test

Date: November 2, 2026. Built on `1aeeb79` plus the pre-existing uncommitted work, which was preserved and not touched. Package: `dist/devil_designer-0.11.0.zip`, SHA-256 `28717203d3dfe06e5846a070b8b4c15683a216736208f2fd8899082224a16139`. There was no version bump, no release, and no README, SPEC or docs-site edits.

## Scope kept

No protected file was edited. `meshing.py`, `placement.py` and `tack_binding.py` have no diff. `garment.py` shows only the 5-line change that was already in the working tree at session start. Production edits are limited to `arrangement.py`, `ellipse_volumes.py`, `arrangement_controls.py`, `live_panels.py`, `panel_cache.py`, `core.py`, `editor.py`, `minimal.py` and `ui_system.py`. `ui.py` was not changed. Tests changed are `blender_ellipse.py` (run through `blender_arrangement`), `test_arrangement_volumes`, `test_arrangement_records`, `test_live_panels`, `gui_arrangement`, `gui_arrangement_display` and `gui_fast_flow`.

## What changed for the artist

- **Points.** Markers are 14 px with a dark edge and a cyan fill. The hit target is 32 px. Everything scales with Blender's UI scale. Points on the far side of the body are dimmed. Hovering shows an 18 px halo and a label. Points bound to the selected piece show a center dot. Only the relevant volume rings are shown when a point is hovered or bound.
- **Click and drag.** A click places the selected piece on release. Movement under 4 px still counts as a click. Past 4 px the point drags around and up its volume. Shift gives fine movement. Esc or right-click restores the exact setup. Release commits once, as one undo step.
- **Hover preview.** Hovering a point shows the selected piece's actual wrapped shape as an orange wireframe, computed by the same rule as the commit.
- **Body-checked wrap (version-3 records).** New arrangements fit the elliptical envelope adaptively, inserting extra sections where the body escapes it. Rows follow a clearance offset of the envelope with a limited slope. The final faces are checked against the real body, with a deterministic edge-length relaxation. If clearance can't be kept, the artist gets a warning. The system never switches to Flat on its own.
- **Piece right-click menu.** Placement Wrap / Flat, Distance from body (Body / 1 / 2 / 5 cm), and Overwrap (Off / Right on top / Left on top). Older arrangements get "Use body-checked wrap", an explicit upgrade that keeps the point and offset.
- **Point right-click menu.** Arrange here: Wrap, Arrange here: Flat, numeric Move in degrees and centimetres, and Edit bounding volume with start/end height, separate width and depth, and Reset fit.
- **Body card.** Refresh fit keeps your points. Reset points restores the defaults. A "Preparing…" status shows while fitting.
- **Responsive body selection.** Fitting runs in cooperative timer slices and never blocks drawing. A same-bounds deformation such as a shape key triggers a refit that keeps points. A body switch cancels the stale fit.

## Proposal section 7 acceptance checks

| Check | Result |
| --- | --- |
| Demonstrated failure (concave tab and rectangle, 15 mm spacing) | 0 inside, 0 intersecting triangles, 0 self-intersections, 0 degenerate faces. Topology and rest coordinates unchanged. **Pass** |
| Clearance (30 mm requested) | Minimum 29.21 mm at faces, 30.00 mm at vertices. Excess p95 11.7 / 12.9 mm. **Pass** |
| Shape preservation | Stretch min 0.95, median 1.00, p95 1.03 to 1.04, max 1.13. **Pass** |
| Difficult shapes | Tapered sleeve, notched panel, long bodice, two-panel hood, and overwrap in both directions all have 0 intersections. A wide piece without overwrap gives an explicit warning and stays Wrap. **Pass** |
| Component continuity | Arms at 15 mm and 60 mm gaps: torso centers stay within 1 cm and radii are continuous. **Pass** |
| Point size and readability | 14 / 20 / 28 px at 100 / 150 / 200% UI scale. Hit target 32 px scaled. Contrast 12.2:1 on the light fixture and 9.9:1 on the dark one. All four states differ in grayscale. **Pass** |
| Picking and drag | 24 of 24 crowded front-facing targets picked correctly. 4 px threshold holds. Shift step is 0.55 mm per pixel. 0.1° numeric entry works. Esc restores exactly. One Undo restores the pre-drag point. **Pass** |
| Click-to-place | Native keymap and minimal workspace both place on click and keep the selection. H and the right-click menu still work. **Pass** |
| Preview | Cold p95 36 ms on a 5,284-vertex panel. Preview matches commit within 0.0001 mm. No panel rebuild during drag. **Pass** |
| Flat | One contextual action. Planar within 1 µm. Point, offset, selection, undo and redo all preserved. **Pass** |
| Pose following | Existing translate, rotate and scale tests pass. Same-bounds shape-key refit and stale-job tests pass. **Pass** |
| Selection responsiveness (live GUI) | Callback at most 20.7 ms. Ready at most 0.31 s on both bodies. Longest slice 7.3 ms. Event-gap p95 7.5 ms. **Pass** |
| Cached selection | Callback about 4 ms. **Pass** |
| Persistence | Version-1/2 records keep their behavior. Version-3 round-trips. An invalid setup is never replaced by a failed fit. **Pass** |
| Shipping gates | See below. **Pass** |

## Gate results

`python tools/dev.py --test --build`: all suites passed (`ALL TESTS PASSED`). That covers the unit tests, all 12 Blender background suites and all 11 GUI suites, including draw coverage (`gui_fast_flow`) and `gui_core_workflow`. The real-Blender full-package and zip load gate passed. `check_dead_code` is clean. `check_public.py` passed. Rule Zero token and AST checks are clean on all 19 changed Python files. `git diff --check` is clean.

## Known limits

- Starter garments (`starters.py`) and linked-twin clones (`linked_editing.py`) are outside the approved scope. They still create version-2 records. Use "Use body-checked wrap" to upgrade them.
- Setups saved before this build carry no geometry fingerprint. Run Refresh fit once to get automatic deformation refits.
- Adaptive envelope refinement covers the torso and legs. Arms rely on the final body check.
- When clearance can't be kept, the build warns but does not roll back to the previous arrangement.
- Evidence: `issue76-build-acceptance-evidence.json`, `issue76-build-display-evidence.json` and `issue76-build-selection-gui-evidence.json`.
