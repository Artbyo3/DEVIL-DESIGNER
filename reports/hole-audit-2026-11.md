# Hole audit, November 2026

Branch `next/live-shaping`. Written with AI assistance (Claude). No test suite was run.
Evidence is either code that was read, or the one real-Blender probe below. Nothing was verified by hand in the editor.

## Probe: do cloth pins take effect while the simulation plays

One background run in Blender 5.2.3 on a sheet draped over a sphere. Result: the assumption holds.

| Measurement | Value |
| --- | --- |
| Cloth points pinned by a 50 mm ring | 10 |
| Jump on the frame the pin was written | 0 mm |
| Pin moved 120 mm, distance to its new target one frame later | 0 mm |
| Same, 31 frames later | 0 mm |
| Far corner: distance from its start pose, which would be 0 after a reset | 346 mm |
| Far corner: movement across the 31 pinned frames | 12 mm |
| After Remove pins, pinned corner movement in 25 frames | 76 mm |
| Movement on the first frame after a 78 mm pull is released | 0.09 mm |
| Same, 13 frames after release | 75 mm |

Not measured: how the 75 mm return is spread over those 13 frames, so the release may still end in a short snap.

## Hole matrix

| Area | Hole | Severity | Evidence | State |
| --- | --- | --- | --- | --- |
| Simulate | A kept garment collides with the next drape of the same garment. Keep, adjust, Simulate again is the loop the quickstart teaches. | High | `layering.collision_bodies` takes every kept mesh with Wear over on by default | Open |
| After Keep | No rigging, weight copy or export help. The workflow ends at a loose mesh. | High | No export or rig code in the package | Open by decision. One paragraph added to the quickstart, the commit after `b0fb542`. |
| Editor | An operator error closed the editor with no message | High | `editor.modal` caught `RuntimeError` and called `cleanup` | Fixed `b0fb542` |
| Editor | Blender undo over the 3D view may invalidate the editor's scene reference and close it | Medium, unverified | The editor keeps `self._scene` across events. It now reports why it closed, `b0fb542`. | Open |
| Keep | Avatar deleted after Simulate gave "Unexpected error: AttributeError" | Medium | `keep_drape` never called `require_body` | Fixed `b0fb542` |
| Grab | Dragging cloth held by a pattern pin, tack or freeze did nothing, silently | Medium | Solver re-places pinned points after each pass | Fixed `b0fb542` |
| Grab | Release ease is one untuned value, and its shape is unmeasured | Medium | Probe above | Open, #116 |
| Grab | Cloth pins can be undone only inside Grab, 32 steps | Low | `ClothGrab.undo_steps` | Open |
| Grab | Pins behind the body still draw | Low | `editor.cloth_pin_pixels` has no depth test | Open |
| Grab | Pin dots raised an error when the drape was outside the view layer | Low | `hide_get` raises there | Fixed `b0fb542` |
| Close | Closing the editor left the drape playing with no Pause in sight | Medium | Close handler only called `cleanup` | Fixed `b0fb542` |
| Close | Closing mid-drape leaves the scene at 30 fps with a very long end frame until Keep or Reset | Medium | `lock_timeline` is undone only in `reset` and `keep_drape` | Open |
| Simulate | The Simulate button reads Pause and only pauses whenever anything is playing, including the artist's own animation | Low | `workflow_action` tests `is_animation_playing` | Open |
| Simulate | A very large mesh chosen as the body can stall the collision shell bake | Low, inferred | `bake_shell` remeshes at a fixed 5 mm voxel | Open |
| First run | Starter without an avatar said "placed on avatar" | Low | `design_action` | Fixed the commit after `b0fb542` |
| First run | A failed starter left an empty undo step | Low | Undo entry was pushed before the generator ran | Fixed the commit after `b0fb542` |
| First run | The only ways in are View > Devil Designer and Ctrl+Alt+D | Low | `ui.register`. The spec forbids an N-panel. | Open by decision |
| Operators | Demo and Build panels operators are reachable only by search. The demo message named a panel that does not exist. | Low | `operators.py` | Message fixed `b0fb542`. Operators left in place. |
| Docs | "Reveal the 3D Viewport" never said how | Low | `arrange.md`, `quickstart.md`, `sew.md` | Fixed `b0fb542` |
| Docs | Most screenshots are placeholders | Medium | `docs-site/docs/*.md` | Open, known |
| Docs | The FAQ does not answer how many undo steps are kept or whether they survive closing Blender | Low | `faq.md` | Open |
| Code | Duplicate unreachable `return False` | Low | `editor.prepare_simulation` | Fixed `b0fb542` |
| Code | Cloth pin records assumed the saved rest matched the mesh | Low | `xpbd_live.pin_records` | Fixed `b0fb542` |

## Not covered

The audit read the operators, the editor event and error paths, the simulate, shape and keep path, layering, history, library loading and the docs. It did not read the 2D drafting core, sewing, arrangement or the renderer line by line. Holes in those areas would not be in this matrix.

## For the test phase

- The earlier list in `reports/live-cloth-pins.md` still applies. Item 1 there is now settled by the probe.
- The editor no longer closes on `RuntimeError`. Any suite that relied on that close will fail and should be updated.
- `tests/blender_layering.py` and `tests/test_layering.py` encode the Wear over default. A fix for the first row changes them.

## Build round after the audit

Three holes were built on the same branch. No suite was run. Only `tests/test_snapping.py` was executed on its own, and it passes.

| Hole | What changed | Test phase must verify |
| --- | --- | --- |
| Kept garment collides with its own re-drape | `layering.worn` defaults Wear over off when a kept mesh shares pieces with the current design. A manual choice wins. | `tests/blender_layering.py`, `tests/test_layering.py` and the Wear over block of `tests/gui_fast_flow.py` were edited to the new default and are unrun. Keep's body check now also skips such a mesh. |
| Timeline left changed after closing | `editor.cleanup` restores the timeline when playback is paused. Keep locks the clock again before refining. | No test covers it. Simulate, pause, close: frame rate, end frame and sync mode return. Reopen and Keep still works. A Keep refused after reopening leaves the clock locked until Reset. |
| No snapping to geometry | `snapping.py`, wired into drawing points, rectangle and ellipse corners, knife points, moves and the pivot, with a marker. | GUI drag tests that end within 10 pixels of other geometry now land on it instead of the grid. Marker draws in every draw state. Hover marker before the first click of a drawing tool. |

Snapping left out on purpose: Pin, Tack and Dart clicks and the double-click edge split still use the grid only, because a point snapped onto the outline fails their inside-the-fabric check. A linked twin that moves with its partner is still a target at its old place during the drag.
