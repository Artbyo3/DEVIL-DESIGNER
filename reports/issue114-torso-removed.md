# Issue #114: torso-removed avatars

Reproduced on 2026-11-10 in real Blender 5.2.4, headless, from master `81ce681`. The issue text could not be read here because `gh` is not installed. The failure matches the "Hollow bodies" item in `reports/gn-xpbd/STATUS.md`.

## Fixture

The fixture is one continuous skin, unlike the joined primitives in `tests/blender_matrix.py`. Torso, hips, legs, A-pose arms, neck and head primitives are joined and voxel-remeshed at 12 mm into a single shell 1.69 m tall with 16,088 vertices. The torso region is `0.80 < z < 1.38 m` and `|x| < 0.19 m`. Each variant uses the same path: estimate measurements, create the Tee starter, fit arrangement volumes, `compile_garment`, run 120 frames at 30 fps, then `keep_drape`.

## Results

| Variant | Chest/waist fit | Start half-width | Cloth after 120 frames | Keep |
| --- | --- | --- | --- | --- |
| Intact (control) | Centered, r ≈ 0.08–0.14 | 0.367 m | Stays up, z 1.09–1.47 | Refused: 8 pts, 20.6 mm (fixture armpit, not torso) |
| Torso deleted | **On the arms**, r ≈ 0.03, off-center | 0.557 m | **Falls to z ≈ −15 m** | "The garment fell off the body" |
| Torso hidden by a Mask modifier | Same as deleted | 0.557 m | Falls to z ≈ −15 m | Fell off |
| Torso Shrink shape key (value 1) | Centered, r ≈ 0.004 | 1.251 m | Falls to z ≈ −17 m | Fell off |
| Faces hidden in Edit Mode | Same as intact | 0.367 m | Same as intact | Same as intact |
| Belly band deleted | Mixed; waist samples on arms | 0.367 m | Stays up; 15 pts sink into the hole | Refused: 5 pts, 30 mm |
| Front torso deleted | Center shifted backward | 0.399 m | Stays up; 50 pts sink into the hole | Refused: 59 pts, 162 mm |
| Deleted + separate outfit (no Collision modifier) | On the arms | 0.557 m | Falls | Fell off |
| Deleted + outfit with a Collision modifier | On the arms | 0.557 m | Starts 37 mm inside the outfit, then falls | Fell off |
| Deleted, rims capped flat | Mostly on the arms | 1.251 m | Falls | Fell off |
| Deleted, volumes fitted on the intact body | Centered | 0.384 m | Hangs on the shoulders; 151 pts inside the torso core | Refused: 4 pts, 37 mm |
| Outfit Collision + intact-body volumes | Centered | 0.384 m | Stays up, 0 pts in the core | Refused: 6 pts, 41 mm (same class as the control) |

Simulate itself never raises an error. The run starts, the cloth drops through the missing torso, and the artist only learns about it at Keep, from a message that blames fit and placement.

Edit-Mode face hiding has no effect, because the evaluated mesh still contains hidden faces. Mask modifiers and Shrink shape keys break it in the same way as deletion.

## Root cause

The code assumes that the chosen avatar object has a closed torso cross-section at the chest, waist and hip heights. It makes this assumption in four places:

1. `arrangement.py:159` `_choose_group`: torso volumes (neck, chest, waist, hip) take the section group whose center is nearest the middle, even when that group does not enclose the middle. With no torso, this is an arm loop or an open rim arc, so the chest and waist volumes collapse onto an arm. The fallback at `arrangement.py:296` runs only when a height has no section at all. This is the first failure: starters are placed wide and off-center.
2. `measurements.py:88` `torso_loop_circumference` and `measurements.py:109` `single_torso_loop` have the same nearest-component rule. They can measure an arm as the chest. On this fixture, measurements already fell back to height ratios, so they did not cause this run's failure.
3. `layering.py:31` `collision_bodies` and `xpbd.py:135` `bake_collider` collide only with `scene.dd_avatar`, kept garments, and objects that have a Collision modifier. A missing torso means there is nothing under the cloth, so even a correctly placed garment sinks into the opening.
4. `body_guard.py:54` `check` then refuses Keep, correctly but late. Its "fell off" message does not mention the missing torso.

Fixing placement alone (rows "volumes fitted on the intact body") stops the fall but still leaves the cloth inside the hole. Fixing it needs both a torso fit and a torso collision surface.

## Decision options

1. **Stand-in fitting body.** Add a "Fit and collide on" choice (default: the avatar). The artist picks an unoptimized body or the original outfit, and measurement, arrangement and collision use it, while Keep and weights still use the avatar. This is the most accurate option and uses existing geometry, but it needs a new control and works only if the artist has a full body.
2. **Generated torso proxy.** When the torso sections are open or missing, build a closed collider from the fitted ellipse stack, interpolated between the neck and hip rims, and add it to the collision bodies and the arrangement fit. This needs no artist action, but the shape is approximate: tight garments fit the proxy, not the real chest. The proxy fit is also new heuristic code with its own failure cases.
3. **Detect and stop with guidance.** At Simulate, detect a torso with no enclosing section and refuse with "This avatar has no torso surface. Choose a full body, or add a Collision modifier to its outfit." The torso fit would also need to reject non-enclosing groups so that the Collision-outfit route places correctly. This is small and safe, but it is not a fix: the artist still needs a full body or an outfit.
4. **Ignore Shrink and Mask on the fitting body.** Evaluate the avatar for fitting and collision with Mask modifiers off and Shrink shape keys at 0. This fixes those two variants cheaply but does nothing for deleted geometry, the usual case. It combines with any of 1–3.

Recommended: 3 now, plus 4 as an inexpensive addition, then 1 if artists without a full body need it. Option 2 should be prototyped before it is promised.

## Residual risk

- The fixture is synthetic. Real avatars have separate head and hand meshes, non-planar rims and skinned poses. The intact control already refuses Keep at 120 frames, which is a fixture armpit contact, so this report cannot judge Keep quality.
- Only the Tee starter was run. The Tank and Skirt depend on the same waist and hip volumes and are expected to fail the same way, but they were not run.
- The issue text was not read, so the exact avatar and steps in the report are unverified.
