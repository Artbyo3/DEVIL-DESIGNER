# Close-more wave, 2026-11-11

Branch `next/close-more`, from master `28d878c`. Each claim was checked on master before any change. Measurements come from real Blender 5.3. The private test avatars stay outside the repository and are named here only by their role.

## #144 Undo depth in the FAQ

On master the FAQ answer said only that edits can be undone. The code keeps 100 undo and 100 redo steps (`HISTORY_LIMIT` in `history.py`, and the `[-100:]` caps in `core.py`). It saves them in the scene's `dd_history`, which goes into the Blender file. On reopen they are restored when the document fingerprint matches, and reset with a message when it does not. The FAQ now says so. A test ties the FAQ wording to `HISTORY_LIMIT` and to a live session capped at 100. It fails on master's FAQ.

## #139 Cloth pin undo

On master, pin changes lived in `ClothGrab.undo_steps`, capped at 32. Ctrl+Z reached them only while Grab was active, and they were lost when the editor closed. Pin changes now push onto the session's undo stack as `PinStep` records, so they share its 100-step cap, its redo and its save in the Blender file. A step from another drape is skipped. The new GUI check, Ctrl+Z after leaving Grab brings removed pins back, fails on master and passes on the branch.

## #142 Collision shell bake on large bodies

Measured on master by baking the shell of the demo torso at growing scales:

| Body | Shell bake on master | Branch |
| --- | --- | --- |
| Demo torso, 0.56 m | 0.10 s | 0.09 s |
| x4 (2.2 m) | 2.3 s | 1.3 s |
| x8 (4.5 m) | 15.9 s | 1.3 s |
| x16 (9 m) | 78.5 s | 1.4 s |
| x100 (56 m) | not run, extrapolated hours | 1.4 s |
| Torso joined with a 10 m floor | 86.1 s | 1.6 s |
| Torso joined with a 100 m floor | not run | 1.7 s |
| 47k-triangle torso at true size | 0.13 s | unchanged |

Cost follows surface area, not triangle count. A real avatar body has about 0.8 m2 of surface and bakes in 0.4 s. The voxel now stays at 5 mm up to 4 m2 of surface and coarsens beyond that, with the shell thickness scaled to match.

## #49 Merged-outfit shoulders

On the 1.55 m merged-outfit avatar, the waist bin falls at 0.653 of height. The chest search then climbs through bins of 42.6, 47.9 and 54.8 cm, each step under the 15 % armpit limit. Above 0.694 of height the jacket sleeves join the torso loop at every level, so no slice holds the torso alone. Shoulders were 54.8 x 1.45 = 79.5 cm. The arms-out estimate is now bounded at a quarter of body height, and the eight intact avatars read 0.189 to 0.241 of height.

| Avatar | Master | Branch |
| --- | --- | --- |
| 1.55 m merged outfit | shoulders 79.5 | shoulders 38.5, every other value unchanged |
| Eight intact avatars, 1.08 to 1.80 m | | identical |
| 1.51 m headless cut body | | identical |
| Merged outfit, Tee drape then Keep | 36 open pairs | 36 open pairs |
| Merged outfit, Tank drape then Keep | 2 open pairs | 2 open pairs |

A first version also narrowed the neck search. That moved torso length from 32.0 to 24.5 cm and made Keep refuse the Tee, so the neck search keeps its master width.

## #81 Reference images in library files

On master `library.save` wrote no reference data. Library files now carry every reference image, active first, with placement, rotation, mirror, lock, visibility and opacity. Load restores them and rolls them back if the load fails. An image missing from its saved path is found beside the garment file. Files from before this change leave the current images alone.

## #148 Flaky arrangement readiness

Root cause: fit jobs were keyed by `avatar.as_pointer()`. Every live-panel test leaves a pending fit for a cube it then deletes. In background mode no timer finishes that fit. When the next test's identical cube is allocated at the same address, `start_fit` matches the stale job (same key, same fingerprint) and returns it. `_install` then cancels it because its avatar is gone, which raises "The avatar changed before its arrangement setup was ready."

- Forcing that key collision fails the reported test and three others with that exact message.
- CPU load alone never reproduced it. With all 20 cores busy, 12 of 12 traced runs passed before the fix, as expected when no timer runs mid-script.
- Fix: jobs are keyed by `session_uid`, which Blender never reuses within a session.
- The new regression test fails on master with the reported message and passes on the branch.
- After the fix, `blender_density.py` passed 20 of 20 runs: 10 with leftover busy loops still running and 10 with all 20 cores saturated (65 to 72 s per run).

## #131 Refit to another avatar

Inventory on master:
- Pieces were already re-placed by arrangement point on an avatar change and on a library load.
- Resizing existed only on library load, as two global factors (height and chest).
- Nothing re-draped.

Now, picking another body in the editor refits the open garment in one undo step:
- Every piece takes the new body length.
- Across, each pattern point follows the girth ratio at its own height on the old body, interpolated over hip, waist and chest. Seams joined at the same body height stay matched.
- Pieces are re-placed by arrangement point.
- A draped garment re-drapes once the new arrangement points are ready.
- Bodies measured with the height fallback refit evenly by height.
- A body under half or over twice the old height is refused.

`gui_refit` covers it end to end. Its first version found that re-draping before the fit was ready started the cloth 824 mm inside the body, so the re-drape now waits for the fit. Limitation: the GUI fixture bodies use the fallback measurement path, so per-region girth is proven by `test_refit.py` and not yet on a real avatar drape.

## #137 Audit of drafting core, sewing, arrangement and renderer

Method:
- **Drafting core and sewing.** A headless fuzzer ran 300 seeds of 60 random operations each (`add`, split, set length, sew, unfold, merge, delete, transforms, offset, round corner, knife, slash, darts, anchors, seam settings, undo and redo), with non-finite and degenerate arguments mixed in. After each step it checked that the document still validates, that it reloads unchanged, that undo restores it exactly, and that a refused operation changes nothing.
- **Sewing edge cases.** Directed probes covered self-sewing, adjacent and opposite edges, duplicate pairs and an edge in two seams.
- **Arrangement.** A real-Blender probe ran eleven bodies through choose, ensure volumes, arrange, build and Simulate.
- **Renderer.** A real-Blender probe drew seven kinds of content at three zoom levels in three tools, with a profile of the slow case.

| Area | Result | Filed |
| --- | --- | --- |
| Drafting core | Clean on validity, reload, undo and refusals. The crashes it found needed out-of-range indexes or NaN, which only internal callers can pass. | none |
| Sewing | Clean. Overlaps and duplicates are refused, and darts and tubes are allowed. | none |
| Darts | An apex on the mouth edge makes a zero-depth dart that gathers the edge. | #150 |
| Arrangement | Every unusable body is refused before building, and odd valid bodies simulate. Two refusals are written in data terms. | #151 |
| Renderer | No render errors in any case. Frame cost grows with the square of the point count: a 3000-point piece takes 25.9 s for its first frame and 250 to 790 ms after. | #149 |
