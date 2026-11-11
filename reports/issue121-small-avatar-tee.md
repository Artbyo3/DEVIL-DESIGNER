# Issues #121 and #49: small-avatar Tee and hip reading

## Root causes

1. **Tee height ignored the body.** The Tee top was placed at the waist plus at least 25 cm, from a fixed 40 cm torso floor. On a 1.08 m avatar, the neck is only 16 cm above the waist. The collar landed about 9 cm above the neck and bunched against the face, so Keep refused the cloth as inside the body.
2. **The sleeve band was placed by adult offsets, not by the arm.** On the 1.08 m avatar, the sleeve top seam lay on the top of the T-pose arm, and the underarm point sat inside the arm's height. The arm split the front and back sleeve panels apart. Seven seam pairs stayed open before Keep, and the front sleeves faced inward (inside-out).
3. **Torso length used a fixed 81 % neck height.** This misreads bodies whose head is not one-seventh of their height.
4. **#49 hip reading.** When the widest silhouette bin fell at thigh height, the hip search took the first closed outline around the centre. On an avatar whose outfit is part of the body mesh, that outline was a small crotch piece, which read 45.5 cm.

## Changes

- Measuring now finds the T-pose arm band (top and bottom of the arm just outside the shoulders) and the neck (narrowest section above the arms). Torso length comes from that neck. Lowered arms, as in an A-pose, are not read as a band, and the old estimate is kept.
- The hip is now the widest closed torso girth between the hip slice and the waist.
- The Tee top stops at the measured neck. The sleeve band keeps at least 1 cm of clearance above and below the measured arm, and the underarm point stays below the sleeve. When the default shape already clears the arm, nothing changes. Long sleeve, Jacket and Hoodie inherit this.

## Evidence

Real Blender 5.2, headless: starter, Simulate, 120 frames, Keep. Nine bodies: five real avatar bodies from 1.08 m to 1.51 m, one 1.55 m avatar with its outfit merged into the body, one 1.10 m body without a head, and the 1.51 m body scaled to 1.40 m and 1.80 m. The bodies stay outside the repository.

| Body | Starter | master | branch |
| --- | --- | --- | --- |
| 1.08 m | Tee | Keep refused, 7 open pairs before Keep, front sleeves 10–31 % outward-facing | Kept, 0 open, sleeves 100 % outward, symmetric |
| 1.08 m | Jacket | Fell off | Kept, 0 open |
| 1.08 m | Hoodie | Keep refused | Kept, 0 open |
| 1.26–1.30 m (3 bodies) | Tee, Tank | Kept, 0 open | Kept, 0 open |
| 1.26 m | Long sleeve, Jacket | Kept, 0 open | Kept, 0 open |
| 1.40, 1.51, 1.80 m | Tee, Tank, Skirt | Kept, 0 open | Kept, 0 open |
| 1.51, 1.80 m | Long sleeve, Jacket | Kept, 0 open | Kept, 0 open |

The 1.08 m Tee result is the same at 60, 120 and 240 frames.

Measurement changes on the adult bodies: chest, waist, shoulders, arm length, inseam and height are unchanged. Hip moves by 0.5–1 cm. Torso length rises by 6.5–7.5 cm because it now reaches the real neck. On the merged-outfit avatar, the hip reads 83.5 cm instead of 45.5 cm. Measuring is up to about 0.9 s slower on a 79k-triangle body.

## Open items

- **Hoodie.** On master, the Hoodie already fails Keep on 5 of 7 bodies, at the hood-to-V-neck junction. The branch fixes the 1.08 m body and turns the 1.40 m refusal into a kept mesh with 8 open pairs. On the 1.26 m and 1.30 m bodies, it goes from 0 to 3 and 2 open pairs, because the neckline now sits at the real neck.
- **Skirt.** The Skirt falls off the 1.08 m and 1.26 m bodies on master and on the branch. This change does not touch the Skirt.
- **Merged-outfit avatar.** It still reads 79.5 cm shoulders and 114.5 cm chest from the jacket, and every starter keeps with open pairs, on master and on the branch.
- **Headless body.** Its shoulders are mismeasured, so no arm band is found, and the Tee behaves as on master (Keep refused).
