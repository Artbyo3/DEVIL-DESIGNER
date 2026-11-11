# Grab release ease, measured on every frame (#116)

Date: 2026-11-10. Branch `next/grab-release-ease`, from master `81ce681`. Written with AI assistance (Claude).
Blender 5.2.3 background, demo two-piece garment, 820 cloth points, Cotton, 30 fps. One machine.

## What was wrong

The 0.15.0 ease scaled the hand's pull from 1 to 0 over a quarter second. The held cloth is tied to its own position at the start of each frame, so scaling the pull changed nothing until the tie was dropped. The cloth stayed frozen for 7 frames and then let go at once.

Movement of the grabbed cloth point per frame after release, in mm, 77 mm pull:

| Frame | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.15.0 | 0.07 | 0.16 | 0.29 | 0.42 | 0.56 | 0.71 | 0.92 | **17.01** | 7.81 | 11.92 | 11.10 | 8.50 | 3.48 | 1.19 |

Largest movement of any cloth point on one frame: 23.56 mm, on frame 16. The old check looked at frame 1 only, so it passed.

## What changed

The pull now stops at release, and the tie to the cloth's own last position is kept but weakened every frame. Its compliance grows from `GRAB_EASE_START` (2e-6) by `GRAB_EASE_RATE` (15 per second) until `GRAB_EASE_END` (1e-2), then the cloth is free. That is 0.57 s, 17 frames. The tie acts as a brake that fades, so the cloth walks back instead of jumping.

## Result, every frame

Grabbed cloth point, mm per frame, same 77 mm pull:

| Frame | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| New | 2.05 | 1.45 | 1.26 | 1.23 | 1.29 | 1.43 | 1.72 | 2.18 | 2.58 | 3.03 | 3.17 | 3.22 | 3.46 | 3.48 | 3.37 |

| Frame | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| New | 3.20 | 2.83 | 2.74 | 1.93 | 1.48 | 1.28 | 1.16 | 1.05 | 0.97 | 0.87 | 0.86 | 0.88 | 0.90 | 0.86 | 0.91 |

- Peak at the hand: 3.48 mm per frame, down from 17.01.
- Largest change between neighbouring frames: 0.81 mm, down from 16.09.
- Largest movement of any cloth point on one frame: 8.48 mm, down from 23.56. The cloth moved 4 to 7 mm per frame while still held, and 1.4 to 1.8 mm when idle, so most of that 8.48 is drape motion away from the hand, not the release.
- The cloth returned 50 mm of the pull in 30 frames. It still returns, it is not frozen.

A pull twice as large (145 mm) peaks at 8.69 mm on frame 1 and then runs 3.5 to 6.4 mm per frame. That first frame is the cloth still travelling to the hand when it was let go, since it moved 12 to 14 mm per frame while held.

Other settings measured and rejected: an exponential fade of the pull (still froze, then jumped 6.9 mm when the fade ended), a softer start of 1e-8 at rate 20 (smooth, but 10 frames of dead time first), and a start of 5e-6 at rate 20 (peak 4.9 mm at the hand, 10 mm cloth-wide).

## The check

`tests/blender_xpbd.py` `test_live_grab` now samples every frame of the ease window plus six frames and asserts:

- no frame moves the grabbed point more than 8 mm,
- no frame differs from its neighbour by more than 3 mm,
- no cloth point moves more than 15 mm on any frame,
- the cloth has returned more than 20 mm by the end.

It prints both per-frame series. The 0.15.0 curve fails the first three.

## Not verified

- Other fabrics, denser meshes, sleeved garments and a real avatar. Compliance is an absolute number, so stiff fabrics may release faster.
- The feel in the real editor at playback speed.
- Any suite other than `tests/blender_xpbd.py`.
