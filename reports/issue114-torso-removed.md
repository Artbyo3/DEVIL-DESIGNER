# Issue #114: torso-removed avatars

The owner chose options 3 and 4. They are implemented on `next/issue-114`; see "Fix" at the end.

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

## Fix

### What the artist sees now

- **Torso deleted, fully or partly:** Simulate stops before any cloth moves: "This avatar has no torso surface for the cloth to rest on, so it would fall through. Choose a full body, or add a Collision modifier to its outfit, then Simulate again."
- **Outfit with a Collision modifier:** the torso fit comes from the outfit wherever the avatar has no torso. Adding the modifier later refits automatically.
- **Mask modifier or Shrink shape key:** fitting, measuring, the body guide, the collision body and the Keep check all use the body as if the Mask were off and the Shrink key at 0. The artist's Mask and key are left untouched.
- **Keep:** if a drape falls or sinks because the torso is missing, Keep names the missing torso instead of blaming fit and placement.

### Rules

- A cross-section counts as torso only if its edges, seen from the body centre line, cover the full circle with no gap of a quarter turn or more. This works on low-poly loops, still accepts small holes, and rejects arms, legs and open rims. A height with no such section has no torso sample; it never borrows an arm or a leg.
- The Simulate check slices 60–78 % of body height, limited to the heights the garment covers. It passes when any collision body (avatar, worn kept garments, Collision objects) surrounds the centre at every slice.
- A Shrink shape key is any key whose name contains "shrink" (any case) that is active and not muted. Bodies are evaluated through a temporary copy, and only when one of these, or an enabled Mask modifier, is present.

### After the fix (same fixture, Tee, 120 frames)

| Variant | Before | After |
| --- | --- | --- |
| Intact (control) | Stays up; Keep refused (fixture armpit, 8 pts) | Identical numbers |
| Torso deleted | Chest on an arm; falls to −15 m; "fell off" | Simulate stops with the guidance |
| Mask modifier | Same as deleted | Chest fit identical to intact; stays up |
| Shrink shape key | Placed 1.25 m wide; falls to −17 m | Chest fit identical to intact; stays up |
| Edit-Mode hidden faces | Same as intact | Same as intact |
| Belly band deleted | 15 pts sink; Keep refused 30 mm | Simulate stops with the guidance |
| Front torso deleted | 50 pts sink; Keep refused 162 mm | Simulate stops with the guidance |
| Deleted + outfit, no Collision | Falls | Simulate stops with the guidance |
| Deleted + outfit with Collision | Chest on an arm; falls | Centred fit from the outfit; stays up, 0 pts in the hole |

With the sleeveless Tank, the intact, Mask and Shrink avatars all Keep with 0 open seam pairs.

### Remaining limits

- Panel wrapping and intersection previews (`panel_cache.py`, `live_panels.py`) and the locked placement code still read the visible avatar. On a Masked avatar, the starter's start width differs by 7 mm.
- On the Collision-outfit route, Keep can still refuse a few points as "inside" the avatar near the cut rims (Tee: 9 pts, 37 mm; Tank: 4 pts, 35 mm). That inside test is unreliable at open edges.
- The torso test depends on the 60–78 % height band. Unusual proportions can move the torso out of that band.
- Measurements use the avatar only, so a torso-removed avatar on the outfit route gets the standard height-based sizes.
