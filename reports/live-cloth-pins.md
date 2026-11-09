# Live cloth pins and Grab release

Date: 2026-11-09. Branch `next/live-shaping`, from master `1e4e09e`. Not pushed, no PR.
Written with AI assistance (Claude). No test suite has been run on this work.

## What changed for the artist

- **Pin the cloth where you hold it.** While dragging with Grab, W pins the cloth inside the ring. Pin mode pins on release. The simulation keeps running and no new drape starts. Before this, Pin mode added a pattern pin and rebuilt the whole drape.
- **Move a pin.** Drag a pinned spot and it stays where it is dropped.
- **Remove pins.** Ctrl+click frees the pins under the ring. Remove pins in the Grab flyout frees all of them. Ctrl+Z in Grab undoes the last pin change.
- **See pins.** Pinned cloth shows as dots over the 3D view in every tool.
- **Pins last.** They carry through Re-drape and are baked by Keep mesh. Reset drape clears them.
- **Softer release.** Letting go eases the hand out over a quarter second instead of one frame (#116).
- **A still hand keeps the cloth still.** Pressing no longer pulls the nearest cloth point to the cursor, and the solver substeps change once when the Grab tool opens instead of at each press and release (#116).

## How it works

Blender's XPBD framework reads the modifier's input mesh again every frame and only carries position and velocity from the previous step. A cloth pin is therefore three point attributes written on the simulation mesh while it plays: `dd_pinned`, `dd_pin_target`, and a new `dd_hold` flag that separates cloth pins from pattern pins, tacks and frozen pieces. `xpbd_live.py` owns these writes.

The eased release is one new group input, `Grab Release`. The node graph scales the hand's pull from 1 to 0 over `GRAB_EASE` seconds after that time. `GROUP_VERSION` is 4.

Cloth pins are stored per piece as 2D pattern points when a drape is carried, and placed on the nearest cloth point of the new mesh.

## Verification done

- Every package module imports in Blender 5.2.3 background, and the cloth node group builds with the new input.
- `tools.check_dead_code` and `tools.check_comments` pass.
- Changed files parse.

Nothing else. The behaviour below is unverified.

## What the test phase must cover

1. **Writing attributes during playback keeps the simulation state.** This is the main assumption. `tests/blender_xpbd.py` `test_live_grab` asserts a pin holds within 0.1 mm for 30 frames and that the cloth continues from where it was.
2. **Eased release.** The same test asserts less than 30 mm of movement in the first frame after release. The 0.25 s ease is a first value, not tuned. Measure the #116 numbers (34 mm tee, 51 mm sleeved) again.
3. **Press without moving.** Measure the 2 to 6 mm per frame drift from #116 again on a sleeved garment.
4. **GUI path.** `tests/gui_live_grab.py` steps 6 and 7 cover W, the pin dots during live playback, Ctrl+click and Remove pins. `tests/gui_matrix.py` covers Pin mode without a new drape.
5. **Carry through Re-drape**, including a garment with a frozen piece, which takes the `piece_states.compile_run` path.
6. **Keep with pins in place**, and Keep refusal still working when a pin holds cloth inside the body.
7. **Scenes saved by 0.15.0 with a drape in progress.** The group version changed. Simulate now rebuilds a drape made by an older group and carries its pose, and Grab asks for that Simulate first. Confirm both on a real 0.15.0 file.
8. **Frame rate** with a few hundred pinned points drawn. The dots are two batches per frame.
9. **Custom theme and Japanese or Spanish**: the new strings are `Remove pins` (translated) and status messages (English only).

## Known limits

- Pins behind the body still draw.
- Cloth pins are not part of document undo. Ctrl+Z covers them only inside Grab, 32 steps.
- A pin can hold cloth inside the body. Keep's body check is the guard.
- Pins are placed by nearest cloth point after a re-drape, so a large mesh density change moves them slightly.
