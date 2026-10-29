# Arrangement ellipse round 2: height-stack wrap prototype

Measured October 29, 2026. Baseline master: 4105553362870da91f15f768e75b813f7d43598e.

## 1. Counts

Tall panels, same round-1 meshes, topology, dimensions, chest/front point and inert
armature. All three round-1 candidates were recomputed on each exact same avatar
and panel topology used by the fix, both without and with its inert rig. Their
counts and full vertex/triangle geometry hashes exactly match round 1.
Counts are intersecting body/panel triangle pairs; inside counts use
signed nearest-surface distance with the same 1 micrometre tolerance as round 1.

| Body | Circle | Fixed ellipse: arc length | Fixed ellipse: existing angle | Row-height ellipse stack |
| --- | ---: | ---: | ---: | ---: |
| Refit body | 0 | 0 | 16 | 0 |
| Different refit body | 0 | 282 | 528 | 0 |

| Body / piece | Vertices | Circle pairs / faces / inside | Fixed arc ellipse pairs / faces / inside | Fixed angle ellipse pairs / faces / inside | Height stack pairs / faces / inside |
| --- | ---: | ---: | ---: | ---: | ---: |
| Refit body / bodice_front | 576 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Refit body / tall_front | 1470 | 0 / 0 / 0 | 0 / 0 / 0 | 16 / 4 / 0 | 0 / 0 / 0 |
| Different refit body / bodice_front | 576 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Different refit body / tall_front | 3450 | 0 / 0 / 0 | 282 / 224 / 344 | 528 / 408 / 314 | 0 / 0 / 0 |

Fixtures remain the two synthetic 16-segment, 12-ring refit bodies from

tests/blender_advanced.py, not production VRChat avatars. Full dimensions:
A = 0.50 x 0.30 x 1.00 m; B = 0.80 x 0.40 x 1.50 m. Tall panels are
0.60 x 0.80 m and 0.96 x 1.20 m respectively. Ordinary bodices are 0.40 x 0.45 m.

## 2. Root cause and evidence

Yes: each old wrap uses only the section at the selected anchor height.

- In devil_designer/live_panels.py, position_panel obtains radius once at line 40,
  before its vertex loop. Line 50 computes angle from horizontal / radius.
  Line 52 passes vertical through as the output Y coordinate without using it
  to select a center or radius. The panel frame subsequently maps that Y into
  world height. This is where height stops affecting the cross-section shape.
- arrangement._volume_resolve interpolates only point['height'] between two
  samples of the selected volume. It does not inspect panel rows or neighboring
  volumes. This is appropriate for resolving an anchor, not sufficient for a
  height-varying tall panel.
- Both round-1 prototype functions also receive one center and one radii pair.
  Their loops add vertical to center Z; neither uses vertical to remeasure or
  interpolate the radii. This is not an ellipse-fit failure.

Two diagnostic vertices use the same horizontal coordinate but different heights,
within each measured tall panel. Their fixed-ellipse XY difference is exactly zero.

| Body | Anchor Z (m) | Neighbor Z (m) | Probe source X (m) | Fixed XY change (mm) | Height-stack XY change (mm) | Fixed neighbor signed surface gap (mm) | Corrected signed gap (mm) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Refit body | 1.430 | 1.200 | 0.300 | 0.000 | 37.377 | 5.499 | 30.736 |
| Different refit body | 2.145 | 1.800 | 0.470 | 0.000 | 63.515 | -15.728 | 35.176 |

Negative signed gap means inside the actual evaluated mesh. On body B the
unchanged anchor cross-section enters the equator by 15.728 mm; using the
neighboring stack leaves 35.176 mm of nearest-surface clearance at that probe.
The configured clearance is radial 30 mm; nearest Euclidean clearance need not
be exactly 30 mm on the faceted body or at another panel angle.

| Body | Anchor side / depth radii (m) | Neighbor side / depth radii (m) |
| --- | --- | --- |
| Refit body | 0.221 / 0.132 | 0.250 / 0.150 |
| Different refit body | 0.353 / 0.177 | 0.399 / 0.200 |

## 3. The one scratch-only fix

The fitted ellipse result is retained. The prototype does not change any band
or any fitted sample. It builds one cached stack from the existing hip, waist,
chest and neck samples: 28 sections per body. For each panel vertex/row:

1. Add its source vertical coordinate to the anchor center height.
2. Find the neighboring stack entries bracketing that world height.
3. Linearly interpolate center XY and both ellipse radii at that height.
4. Wrap its horizontal coordinate by arc length around that ellipse with the
   existing 30 mm radial clearance, then retain its own world Z.
5. Retain a tangent-flat branch and apply the original local-frame G/R delta
   composition after wrapping. For widths exceeding the row circumference,
   keep outward spiral turns separated by the configured clearance per turn.

Ring arc lengths use a 4,096-segment lookup, cached per unique source row.
Outside the terminal samples, XY and radii clamp to the nearest terminal sample;
world Z continues to follow the row. No extra slices, projections, armature reads,
band changes or per-redraw mesh access are introduced by wrapping. Guards raise
if the actual garment-build hook attempts _volume_sections or _volume_mesh.

The monkeypatch exists only inside the separate background Blender process.
The prototype is scratch/arrangement_stack_prototype.py. It invokes existing
protected functions but neither edits them nor substitutes their implementations.
No production source or setup serializer changed.

## 4. Gate results

All three requested gates pass on these two fixtures:

- (a) Both tall panels and both ordinary bodices have 0 intersecting pairs,
  0 intersecting faces and 0 inside vertices, matching the circular baseline.
- (b) All 42 round-1 chest/waist/hip gap improvements are retained. Absolute
  tolerance is 0.000001 mm for both mean and maximum; largest observed change
  is 2.318145675417e-13 mm.
- (c) Actual garment-build hooks pass Arrange flat, native capture and rebuild
  of G/R deltas, unchanged source outlines/UV coordinates and document roundtrip.
  A 2.5-turn wide-panel build stays finite; same-phase probes on three successive
  turns gain 30 mm radial clearance per turn. Bare-mesh versus inert-armature
  setups, resolved points, fitted stacks and all candidate panel geometry hashes
  and measurements are exactly equal on both bodies.

Geometry comparisons allow 0.000002 m (2 micrometres). Flat local-Z warp is exactly
zero on both bodies. G/R record component errors are bounded in metres for
translation and radians for rotation, separately by the same numeric tolerance.

| Body | Max G/R component error | Rebuild world error (m) | Spiral turn-clearance error (m) | Bare / rigged exact equality |
| --- | ---: | ---: | ---: | --- |
| Refit body | 5.692243576e-8 | 1.210576058e-7 | 2.775557562e-17 | true |
| Different refit body | 4.768371581e-8 | 3.371747881e-7 | 2.775557562e-17 | true |

### All 42 retained samples

All gap values are millimetres, excluding clearance, using the same 256 equal-arc
loop samples and nearest Euclidean distances as round 1.

| Body | Band | Sample | Circle mean | Circle max | Round-1 ellipse mean | Round-1 ellipse max | Height-stack ellipse mean | Height-stack ellipse max | Max absolute change |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Refit body | chest | 0 | 51.982 | 95.052 | 2.220 | 4.364 | 2.220 | 4.364 | 0.000e+0 |
| Refit body | chest | 1 | 50.910 | 93.091 | 2.171 | 4.283 | 2.171 | 4.283 | 0.000e+0 |
| Refit body | chest | 2 | 49.845 | 91.145 | 2.129 | 4.188 | 2.129 | 4.188 | 0.000e+0 |
| Refit body | chest | 3 | 48.775 | 89.189 | 2.082 | 4.101 | 2.082 | 4.101 | 0.000e+0 |
| Refit body | chest | 4 | 47.576 | 86.995 | 2.029 | 4.002 | 2.029 | 4.002 | 0.000e+0 |
| Refit body | chest | 5 | 45.600 | 83.382 | 1.948 | 3.819 | 1.948 | 3.819 | 0.000e+0 |
| Refit body | chest | 6 | 43.618 | 79.756 | 1.860 | 3.669 | 1.860 | 3.669 | 0.000e+0 |
| Refit body | waist | 0 | 54.829 | 100.259 | 2.342 | 4.595 | 2.342 | 4.595 | 0.000e+0 |
| Refit body | waist | 1 | 54.538 | 99.727 | 2.330 | 4.575 | 2.330 | 4.575 | 0.000e+0 |
| Refit body | waist | 2 | 54.246 | 99.193 | 2.316 | 4.558 | 2.316 | 4.558 | 0.000e+0 |
| Refit body | waist | 3 | 53.954 | 98.658 | 2.302 | 4.537 | 2.302 | 4.537 | 0.000e+0 |
| Refit body | waist | 4 | 53.662 | 98.123 | 2.289 | 4.514 | 2.289 | 4.514 | 0.000e+0 |
| Refit body | waist | 5 | 53.353 | 97.559 | 2.276 | 4.488 | 2.276 | 4.488 | 0.000e+0 |
| Refit body | waist | 6 | 52.439 | 95.889 | 2.239 | 4.405 | 2.239 | 4.405 | 0.000e+0 |
| Refit body | hip | 0 | 54.247 | 99.194 | 2.317 | 4.542 | 2.317 | 4.542 | 0.000e+0 |
| Refit body | hip | 1 | 54.512 | 99.679 | 2.327 | 4.583 | 2.327 | 4.583 | 0.000e+0 |
| Refit body | hip | 2 | 54.777 | 100.160 | 2.336 | 4.608 | 2.336 | 4.608 | 0.000e+0 |
| Refit body | hip | 3 | 55.047 | 100.658 | 2.351 | 4.620 | 2.351 | 4.620 | 0.000e+0 |
| Refit body | hip | 4 | 55.213 | 100.960 | 2.355 | 4.645 | 2.355 | 4.645 | 0.000e+0 |
| Refit body | hip | 5 | 54.948 | 100.478 | 2.345 | 4.620 | 2.345 | 4.620 | 0.000e+0 |
| Refit body | hip | 6 | 54.684 | 99.992 | 2.336 | 4.581 | 2.336 | 4.581 | 0.000e+0 |
| Different refit body | chest | 0 | 104.042 | 189.040 | 3.119 | 6.840 | 3.119 | 6.840 | 0.000e+0 |
| Different refit body | chest | 1 | 101.904 | 185.155 | 3.054 | 6.703 | 3.054 | 6.703 | 7.727e-14 |
| Different refit body | chest | 2 | 99.764 | 181.267 | 2.989 | 6.567 | 2.989 | 6.567 | 7.727e-14 |
| Different refit body | chest | 3 | 97.620 | 177.369 | 2.919 | 6.419 | 2.919 | 6.419 | 7.816e-14 |
| Different refit body | chest | 4 | 95.229 | 173.027 | 2.854 | 6.264 | 2.854 | 6.264 | 0.000e+0 |
| Different refit body | chest | 5 | 91.268 | 165.829 | 2.736 | 5.993 | 2.736 | 5.993 | 0.000e+0 |
| Different refit body | chest | 6 | 87.306 | 158.631 | 2.616 | 5.747 | 2.616 | 5.747 | 1.377e-14 |
| Different refit body | waist | 0 | 109.741 | 199.393 | 3.290 | 7.204 | 3.290 | 7.204 | 1.537e-13 |
| Different refit body | waist | 1 | 109.156 | 198.331 | 3.270 | 7.186 | 3.270 | 7.186 | 7.816e-14 |
| Different refit body | waist | 2 | 108.571 | 197.269 | 3.250 | 7.146 | 3.250 | 7.146 | 7.816e-14 |
| Different refit body | waist | 3 | 107.993 | 196.219 | 3.237 | 7.097 | 3.237 | 7.097 | 7.727e-14 |
| Different refit body | waist | 4 | 107.410 | 195.160 | 3.219 | 7.068 | 3.219 | 7.068 | 6.750e-14 |
| Different refit body | waist | 5 | 106.786 | 194.025 | 3.196 | 7.027 | 3.196 | 7.027 | 7.816e-14 |
| Different refit body | waist | 6 | 104.957 | 190.703 | 3.145 | 6.909 | 3.145 | 6.909 | 7.638e-14 |
| Different refit body | hip | 0 | 108.573 | 197.272 | 3.252 | 7.147 | 3.252 | 7.147 | 7.816e-14 |
| Different refit body | hip | 1 | 109.109 | 198.247 | 3.270 | 7.181 | 3.270 | 7.181 | 1.537e-13 |
| Different refit body | hip | 2 | 109.643 | 199.216 | 3.286 | 7.217 | 3.286 | 7.217 | 7.816e-14 |
| Different refit body | hip | 3 | 110.176 | 200.185 | 3.301 | 7.252 | 3.301 | 7.252 | 8.082e-14 |
| Different refit body | hip | 4 | 110.517 | 200.805 | 3.312 | 7.271 | 3.312 | 7.271 | 2.318e-13 |
| Different refit body | hip | 5 | 109.981 | 199.830 | 3.294 | 7.240 | 3.294 | 7.240 | 1.545e-13 |
| Different refit body | hip | 6 | 109.449 | 198.865 | 3.280 | 7.199 | 3.280 | 7.199 | 0.000e+0 |

## 5. Protected-file approval required before production

Production implementation stops here despite the passed prototype gate. Preserving
old placements while allowing only a re-arranged piece to opt into the new wrap
requires a durable per-piece model selector. The arrangement record already has a
version field, but core.validate_arrangement currently accepts only version 1.
The prototype tested an otherwise-valid version-2 record against the existing
validator and received: Unsupported arrangement record.

Exact proposed protected changes, not applied:

1. File devil_designer/core.py, function arrangement_record (line 252): add
   a keyword-only version=1 argument and return that value in the existing
   version field. Keep the existing six keys and legacy default unchanged.
   New arrange/re-arrange callers explicitly request version=2.
2. Same file, function validate_arrangement (line 256): accept integer versions
   1 and 2 instead of only 1. Retain the exact key set, bool rejection, stable
   volume/point IDs, flat flag and all existing finite G/R delta checks.

Version 1 retains legacy placement against an old setup or its preserved legacy
snapshot; version 2 opts the individual piece into height-stack ellipses. The
editable arrangement code would own version-2 avatar setup storage and preserve
the old snapshot when conversion is triggered by just one piece's re-arrangement.
Explicit avatar regeneration may replace the setup for all pieces as authorized
by the original prompt. Loading alone must never perform that conversion.
Document.loads and the top-level document version need no change: they already
retain records and call this validator without automatically rewriting them.

No other protected change is proposed. Garment build, meshing, simulation, sewing,
placement and tack math remain untouched. No production build, artist-test handoff,
PR or merge is performed in round 2. The existing dist package is preserved.

## Verification

- The final scratch prototype passes all three explicit gates, including exact
  baseline reproduction on each shared avatar/rig, and exact bare/rigged equality.
- The unchanged application's headless unit tests, all nine Blender background
  suites and all seven GUI suites pass, including arrangement display.
- All 97 repository Python files pass token and AST checks; all 36 package
  modules pass dead-code/unused-import checks. The scratch prototype separately
  passes syntax, token and AST checks, including its final measurement run.
- Publication checks pass across 148 source paths, 655 historical blobs,
  archives and public commit identities. The existing notice for 23 commits
  retaining an explicitly accepted historical identity remains; no history purge
  is claimed.
- Production source matches HEAD. The preserved dist/devil_designer-0.9.0.zip
  SHA-256 remains 8f428dea8b94490c87a4603e7955e1c529a23197f6ab4bf5b77a1bc065e06d8b.
  No new package was built or installed in round 2.

## Scope and reproducibility

The passing result is limited to the two existing synthetic torso fixtures and
explicitly tested workflows. It does not establish limb/oblique-frame coverage or
full arbitrary-avatar production readiness. Format migration and modified ellipse
display/cache behavior still need implementation and dedicated regression tests
after protected-file approval. Unchanged production GUI tests are not a benchmark
of a production implementation that has not been written.

Run the round-1 experiment first using its report's instructions, preserving its
scratch JSON. Then run the scratch prototype with tools.dev.run_cmd and the same
configured Blender, background/factory-startup and python-exit-code 1.
Its output is scratch/arrangement-ellipse-round2.json. Both scripts complete with
explicit gate fields; successful process exit means completed measurements, not
automatic permission to proceed.

Scratch script SHA-256: 122013aa1e376f2f0065dd40feedf0acdefe3f9968b542851a9371b986f66f37.

Scratch is retained for the protected-change review. No experimental code is
installed or packaged. Production hashes are checked unchanged before/after
the prototype, and all raw geometry hashes are preserved in the scratch JSON.
