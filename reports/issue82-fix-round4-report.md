# Issue 82 selection and transforms: accepted and shipped

The artist accepted the build with "Ship it" on November 3, 2026. Tested package: `devil_designer-0.11.0.zip`, SHA-256 `fa22ab070800235039400d90953f4632485a3c1c9c0d97064d0fdb8cec7741d3`. Shipped package: SHA-256 `dfa40f76ed6cb5949106118fd70f8764eb5c1229fc22f659055dd17b1fc750da`. The only source difference is the removal of the unreachable rotate action, which the artist cannot see.

## Changes after round 4

- Mouse selection frame replaced menu and shortcut transforms: corners scale, the knob rotates, Shift snaps to 15 degrees or 10 percent, Alt+drag moves the pivot, and a live ghost and readout show the result. Seam and curve warnings still stop a drag before anything changes.
- The old docked inspector layout and every branch that served it were deleted, leaving the minimal workspace as the only layout.
- Removal exposed and fixed dead Finish and Cancel draft buttons and an arrow-nudge guard watching the wrong text field.
- Box and lasso selection use one colour and no on-canvas label. Drag direction still chooses fully inside or touching, and the status line names the rule.

The round 4 record follows. Its package hash and test counts describe the earlier build.

Candidate worktree: `t3/issue82-selection-transforms` (uncommitted, base 448f1b8). Package: `dist/devil_designer-0.11.0.zip`, SHA-256 `b8fada4e9ed542fb033590dad683450bdf1b43ad0e2187097315568158872766`, 55 entries matching source byte-for-byte.

## Audit of the dead round (ordinal 4)

The round-3 baseline was recovered from the round-3 ZIP, whose `core.py`/`editor.py` match the round-3 evidence hashes.

| Dead-round change | Verdict |
| --- | --- |
| CSS comments removed from `docs-site/docs/stylesheets/extra.css` | Kept. Verified comment-only: 15 → 0 comments; master with comments stripped equals the current file ignoring whitespace. No other docs-site file differs. |
| AUTO fix: stash/restore handles in preflight and commit, remove MOVE AUTO recompute | Discarded. `sample_path` recomputes AUTO handles on every `outline()`, so the stash was cosmetic: the rendered curve still distorted by 2.071184 mm. It also let seam preflight measure handles that never render. |
| Seam chain checks: per-span near-zero block, reorder/reference/span-change block, same-total breakpoint WARN | Kept. Verified with the dead round's own repro (now WARN, source unchanged) and the model tests. |
| `editor.py` nudge gate `not panel` → `not canvas` | Reverted. Its purpose (blocking the dock) never worked, because the dock floats over the full-screen canvas. |
| Model tests in test_seams / test_linked_editing / test_selection | Kept, except `test_exact_auto_move_rotate_scale_101_samples...`, which asserted `OK` on the defect. Replaced. |
| 9 new native groups in gui_design | 6 of 9 failed in real Blender. The delegate never launched Blender. All repaired; see below. |

## Fixes this round

- **Check 7.** Candidates keep AUTO handles canonical, so what you preview is what renders. Preflight measures 101 samples on every selected edge against the exact affine image. Any deviation over 1e-6 m stops at a Curve warning showing the exact mm, with three choices: Convert to smooth (exact; only the affected AUTO endpoints become Smooth), Apply with change (keeps AUTO), or Cancel. Repro: MOVE 2.071184 mm, ROTATE 16.04 mm, SCALE 1.75 mm all warn; converted results are exact to 1e-14 mm; whole pieces stay OK.
- **Warning bypasses closed.**
  - Rotate 90° (`]`, `[`, Shift+R and the menu buttons) committed WARN candidates silently. It now goes through the warning card.
  - Session `move_selection`/`rotate`/`scale` now default to returning the WARN report instead of committing.
  - Include sewn pieces re-preflights before committing.
  - Card clicks no longer drop a warning raised by the clicked action.
- **Product bugs exposed by the fixtures.**
  - Lasso ignored Shift/Alt, so add/subtract was impossible.
  - Ctrl+L (connected path) was swallowed by the Lengths toggle.
  - Numeric Move left a placed pivot behind.
  - Redo restored the selection from Undo time, not the committed one.
- **Fixture repairs.**
  - Missing `persist()` calls.
  - Shift held on press, which toggled the selection off.
  - Probes that missed the dock or 3D viewport; they now reveal the 3D viewport and assert the probe lands there.
  - Region-less `projected_points`.
  - An over-strict invert comparison.
  - Off-grid snap grab pixels.
  - The click helper hitting the middle of two-button rows.
  - The conditional 3D placement assertion, now unconditional.
- **Cleanup.** Removed the now-unused `Session.rotate_90` and `include_sewn_and_transform`.

## Section 9 (19 checks)

All PASS. Native groups ran through `window.event_simulate` in the active minimal editor (21/21 groups, 1019 native assertions). Model tests are listed separately.

1 Mixed rotation; 2 Pivot placement; 3 Numeric scale (snapped third-piece pivot, mixed targets, 1.1 = 110%, invalid text); 4 Panel marquee (12 cases plus curved/concave partial pieces); 5 Region/lasso (replace/add/subtract/overlap/empty, Escape, target switching, even-odd); 6 Click/toggle (an empty-selection drag is tested on empty canvas; dragging an unselected piece still selects and moves it); 7 Edge/internal (bare edge, internal path, visible confirmed AUTO conversion); 8 Snap/axis (panel/point/mixed, ±X/±Y, negative coordinates, snap off, Ctrl both ways, numeric exact); 9 Connected/invert (native plus model coincident cases); 10 Seam follow (model); 11 Warning before seam damage; 12 Chain/invalid (model, including same-total breakpoint); 13 Sewn-component follow; 14 Linked editing (model); 15 #42 nudge (text fields, revealed 3D viewport); 16 Transaction safety (Enter, click, Escape, right-click, outside-card click, focus loss, invalid geometry, redo selection and pivot); 17 3D boundary (bridge, orbit reaches viewport without 2D leak, placement on the active piece only, marquee no leak); 18 Draw/core workflow; 19 Protected regression.

## Gates (fresh, final code)

`python -B tools/dev.py --test --build --keep-scratch` exit 0:
- dead-code PASS;
- 437 unit tests (23 Blender-only skips);
- 12/12 background suites;
- 12/12 GUI suites: gui_design 1051 checks, gui_fast_flow 298 draw checks with no render error, gui_core_workflow 170;
- package validate PASS;
- real-Blender full ZIP load PASS.

Rule Zero: 131 Python files clean (token + AST), 17 non-Python files clean. `check_public.py` PASS. `git diff --check` PASS. Locked files, curve math and the manifest are unchanged from master; the mirror methods are verbatim.
