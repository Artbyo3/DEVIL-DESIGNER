# Reliability rows

Behavior the feature matrix cannot show. Each row is one drape scenario, not one feature.

## Method

Run on 2026-11-06 in real Blender 5.2.3 through the editor: starter, Simulate, about six seconds of live playback, pause, Keep. One run per row. The body is the synthetic `build_body` from `tests/blender_matrix.py`, not a real avatar. "Small" scales it to 0.62. "Torso removed" deletes the faces in the central torso volume.

A first attempt on the T-pose mannequin from `tests/gui_core_workflow.py` was discarded. Its arms inflate the measured width, arrangement refuses, and every garment including the adult control falls. That body cannot judge drape.

## Results

| Scenario | Kept | Open seam pairs | Result |
| --- | --- | --- | --- |
| Adult tee (control) | Yes | 6 | Sits low on the torso |
| Adult skirt (control) | No | n/a | Falls off |
| Small tee | Yes | 3 | |
| Small tank | Yes | 0 | |
| Small skirt | No | n/a | Falls off |
| Torso removed tee | Yes | 6 | Same as the adult control |
| Torso removed skirt | No | n/a | Falls off |
| Library tee, saved and reloaded | Yes | 6 | No weld error, same as the fresh tee |

## What this does and does not show

- #78: the `weld_verts` error did not recur on a saved and reloaded two-piece tee. The issue's two follow-up points were not examined.
- #114: not reproduced, but this body is not evidence of a fix. It has no real hollow shell, and the issue was found on a real avatar.
- #121: small avatars do not stand out here. The adult control has more open pairs than the small tee, so open seams after a short drape are not specific to small bodies.
- The skirt falls on every body here, including the adult control. It has no measured waist grip on this body. Real avatars passed in #121, so this may be the body and not the garment.

## Gap

`tests/gui_core_workflow.py` presses Simulate and pauses at once, so no frames run on that path. It cannot catch cloth falling off. Rerun these rows on the real test avatars before calling any of them fixed.
