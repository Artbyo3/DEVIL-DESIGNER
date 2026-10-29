# Arrangement ellipse prototype — stopped at the evidence gate

Measured October 29, 2026, against current master `4105553362870da91f15f768e75b813f7d43598e`.

## Decision

Do not ship this candidate. Ellipse fitting reduces both mean and maximum section
gaps at every one of 42 measured samples. However, fixed-height ellipse wrapping
introduces intersections in the wider body's tall front panel. Keeping the existing
angle rule also introduces intersections. Prompt 10 v2 explicitly requires stopping
if the prototype does not beat the circular baseline honestly on these numbers.
No production code, format version, band placement, or saved design was changed.
This is a failed placement-safety gate, not evidence that ellipse fitting itself is worse.

## Fixtures and measurement

These are the two synthetic mesh-only refit fixtures already specified in
`tests/blender_advanced.py`, recreated with its exact 16-segment, 12-ring UV-sphere
topology. They are not production VRChat avatars and have no anatomical chest,
waist, or hip landmarks: those names refer to the unchanged generator bands.

| Fixture | Full width / depth / height (m) | Center (m) |
| --- | --- | --- |
| A: Refit body | 0.50 / 0.30 / 1.00 | 0 / 0 / 1.20 |
| B: Different refit body | 0.80 / 0.40 / 1.50 | 2 / 0 / 1.80 |

- Baseline samples, centers, band locations and point heights come from the existing generator.
- The candidate measures separate lateral/depth extrema on the same sliced mesh loops,
  then scales both axes by the maximum normalized radius so that the sampled loop
  is enclosed. This avoids knowingly fitting an inscribed ellipse to a box-like loop.
- Each loop is sampled at 256 equal arc-length intervals. Mean and maximum are
  absolute nearest Euclidean distances from those loop samples to the circle or
  ellipse, in millimetres. They are one-direction loop-to-volume distances, not a
  symmetric Hausdorff distance. Section gaps exclude clearance for both candidates.
- Placement uses the same generated panel vertices, faces, selected chest/front
  point, measured center and 30 mm radial clearance. The production baseline calls
  the existing live-panel placement function, without modifying it.
- Candidate 1 maps horizontal panel distance to ellipse arc length using a
  16,384-segment lookup, at the selected point's fixed height. Candidate 2 retains
  the existing angle rule: horizontal distance divided by the selected front
  point's radius, then evaluates the ellipse directional radius at that angle.
  Neither candidate projects onto the avatar, changes bands, follows per-height
  neighboring sections, or exercises spiral turns. All panel widths are below
  both the baseline spiral threshold and candidate circumference.
- Triangle-pair overlaps are measured with Blender BVH against the evaluated
  avatar mesh. Unique intersecting panel triangles and inside vertices are also
  reported; inside tests use signed nearest-surface distance with a 1 micrometre
  tolerance on these closed convex fixtures. Pair counts depend on tessellation;
  all comparisons use the same body and panel topology.
- Adding an inert armature modifier with no weights produces exactly equal
  generated setups, resolved world points, panel geometry hashes, and measured
  results on both bodies. This only tests identical evaluated meshes; a rig that
  deforms the mesh should naturally change mesh-derived measurements.
- Analytic circle-distance and enclosing-box-ellipse checks pass before measurement.

## Per-sample section gaps

All values below are millimetres. Sample t is local to each unchanged band.
Seven samples are reported for each chest, waist and hip band on each body.

### Refit body

| Band | Sample | t | Circle mean | Circle max | Ellipse mean | Ellipse max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chest | 0 | 0.000 | 51.982 | 95.052 | 2.220 | 4.364 |
| chest | 1 | 0.167 | 50.910 | 93.091 | 2.171 | 4.283 |
| chest | 2 | 0.333 | 49.845 | 91.145 | 2.129 | 4.188 |
| chest | 3 | 0.500 | 48.775 | 89.189 | 2.082 | 4.101 |
| chest | 4 | 0.667 | 47.576 | 86.995 | 2.029 | 4.002 |
| chest | 5 | 0.833 | 45.600 | 83.382 | 1.948 | 3.819 |
| chest | 6 | 1.000 | 43.618 | 79.756 | 1.860 | 3.669 |
| waist | 0 | 0.000 | 54.829 | 100.259 | 2.342 | 4.595 |
| waist | 1 | 0.167 | 54.538 | 99.727 | 2.330 | 4.575 |
| waist | 2 | 0.333 | 54.246 | 99.193 | 2.316 | 4.558 |
| waist | 3 | 0.500 | 53.954 | 98.658 | 2.302 | 4.537 |
| waist | 4 | 0.667 | 53.662 | 98.123 | 2.289 | 4.514 |
| waist | 5 | 0.833 | 53.353 | 97.559 | 2.276 | 4.488 |
| waist | 6 | 1.000 | 52.439 | 95.889 | 2.239 | 4.405 |
| hip | 0 | 0.000 | 54.247 | 99.194 | 2.317 | 4.542 |
| hip | 1 | 0.167 | 54.512 | 99.679 | 2.327 | 4.583 |
| hip | 2 | 0.333 | 54.777 | 100.160 | 2.336 | 4.608 |
| hip | 3 | 0.500 | 55.047 | 100.658 | 2.351 | 4.620 |
| hip | 4 | 0.667 | 55.213 | 100.960 | 2.355 | 4.645 |
| hip | 5 | 0.833 | 54.948 | 100.478 | 2.345 | 4.620 |
| hip | 6 | 1.000 | 54.684 | 99.992 | 2.336 | 4.581 |

### Different refit body

| Band | Sample | t | Circle mean | Circle max | Ellipse mean | Ellipse max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chest | 0 | 0.000 | 104.042 | 189.040 | 3.119 | 6.840 |
| chest | 1 | 0.167 | 101.904 | 185.155 | 3.054 | 6.703 |
| chest | 2 | 0.333 | 99.764 | 181.267 | 2.989 | 6.567 |
| chest | 3 | 0.500 | 97.620 | 177.369 | 2.919 | 6.419 |
| chest | 4 | 0.667 | 95.229 | 173.027 | 2.854 | 6.264 |
| chest | 5 | 0.833 | 91.268 | 165.829 | 2.736 | 5.993 |
| chest | 6 | 1.000 | 87.306 | 158.631 | 2.616 | 5.747 |
| waist | 0 | 0.000 | 109.741 | 199.393 | 3.290 | 7.204 |
| waist | 1 | 0.167 | 109.156 | 198.331 | 3.270 | 7.186 |
| waist | 2 | 0.333 | 108.571 | 197.269 | 3.250 | 7.146 |
| waist | 3 | 0.500 | 107.993 | 196.219 | 3.237 | 7.097 |
| waist | 4 | 0.667 | 107.410 | 195.160 | 3.219 | 7.068 |
| waist | 5 | 0.833 | 106.786 | 194.025 | 3.196 | 7.027 |
| waist | 6 | 1.000 | 104.957 | 190.703 | 3.145 | 6.909 |
| hip | 0 | 0.000 | 108.573 | 197.272 | 3.252 | 7.147 |
| hip | 1 | 0.167 | 109.109 | 198.247 | 3.270 | 7.181 |
| hip | 2 | 0.333 | 109.643 | 199.216 | 3.286 | 7.217 |
| hip | 3 | 0.500 | 110.176 | 200.185 | 3.301 | 7.252 |
| hip | 4 | 0.667 | 110.517 | 200.805 | 3.312 | 7.271 |
| hip | 5 | 0.833 | 109.981 | 199.830 | 3.294 | 7.240 |
| hip | 6 | 1.000 | 109.449 | 198.865 | 3.280 | 7.199 |

## Arranged panel intersection counts

The ordinary front panel is 0.40 x 0.45 m on both bodies. The tall panel is
1.2 times body width by 0.8 times body height: 0.60 x 0.80 m for A and
0.96 x 1.20 m for B. All panels are centered at the chest/front point.

| Body / piece | Vertices | Circle pairs / faces / inside | Arc-length ellipse pairs / faces / inside | Existing-angle ellipse pairs / faces / inside |
| --- | ---: | ---: | ---: | ---: |
| Refit body / bodice_front | 576 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Refit body / tall_front | 1470 | 0 / 0 / 0 | 0 / 0 / 0 | 16 / 4 / 0 |
| Different refit body / bodice_front | 576 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Different refit body / tall_front | 3450 | 0 / 0 / 0 | 282 / 224 / 344 | 528 / 408 / 314 |

### Ordinary bodice front surface gap

Nearest body-surface distance at the panel vertex nearest its source center,
including placement clearance. This is a center measurement, not a whole-panel
fit guarantee; both ordinary bodices have zero intersections in both candidates.

| Body | Circle (mm) | Arc-length ellipse (mm) |
| --- | ---: | ---: |
| Refit body | 117.605 | 30.616 |
| Different refit body | 205.402 | 30.590 |

## Why the gate fails

The fitted chest ellipse is narrower than the conservative circle. It fits its
measured section well, but carrying that same section down a tall panel can enter
a wider neighboring section. On fixture B, the arc-length candidate changes
0 intersection pairs to 282, involving 224 panel triangles and 344 inside vertices.
The unchanged-angle candidate also regresses (528 pairs, 408 faces, 314 vertices).
The smaller body additionally has 16 pairs under the unchanged-angle rule despite
zero inside vertices: checking only vertex containment would miss those crossings.

A possible separate prototype would evaluate the already mesh-derived volume
samples along panel height rather than using one fixed-height section. That would
change the current wrapping contract and is only a proposal, not implemented here.
It would still be volume wrapping, not surface projection or rig anchoring.
No band-placement improvement or MD parity claim is established by this experiment.

## Verification

- The prototype completed repeatedly with the same failed gate and exact
  bare-mesh versus inert-armature geometry hashes on both bodies.
- The full developer runner passed: headless unit tests, all nine Blender
  background suites, all seven GUI suites (including arrangement display),
  extension packaging and Blender package validation.
- Python tokenization and AST checks passed for all 97 Python files;
  the dead-code/unused-import check passed for all 36 package modules.
- The publication check passed across 147 source paths, 653 historical blobs,
  archives and public commit identities. It retains the existing acknowledged
  historical identity notice; this is not a history purge.
- The unchanged 0.9.0 package matches all 76 source/archive entries byte for byte.
  ZIP SHA-256: 8f428dea8b94490c87a4603e7955e1c529a23197f6ab4bf5b77a1bc065e06d8b.
  It contains the existing circular implementation, not this test-only candidate.
- No protected or other application source changed. No PR, commit or merge
  was requested or performed. There is no artist-acceptance handoff.

## Reproduce

Run from the repository root with the same configured Blender as the developer runner:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -c "from tools.dev import run_cmd, BLENDER_PATH; raise SystemExit(not run_cmd([BLENDER_PATH, '--background', '--factory-startup', '--python-exit-code', '1', '--python', 'tests/blender_arrangement_ellipse_prototype.py'], desc='Mesh-only ellipse prototype'))"
Get-Content scratch/arrangement-ellipse-prototype.json
python tools/dev.py --clean
```

The script exits successfully when the experiment completes, even when its explicit
gate_passed result is false. The JSON is disposable; this report preserves all
requested per-sample measurements. No feature build is offered for artist acceptance.

Prototype script SHA-256: `88f0a301a2030966cbd53ed680d8b34b924597343ed301a2f404d9fa0e1018ff`.

Protected source SHA-256 values were checked unchanged during the experiment:

| File | SHA-256 |
| --- | --- |
| core.py | 6b2bbface0801439f2e60f36c2971af5ca60b4d2fad35bb1b48ed33fffdd6fe3 |
| garment.py | 2a5be73eff25c7f97006402d776f2c01648ca77c76e0fc77e61fd4e67d3732d7 |
| meshing.py | af33189cdffff84a6c7c2b6908c3967d9e22901f824098b377ca09e44affcfb9 |
| placement.py | 77b0c5b1d792a8e32dda6f2908899d1803ee4f9f87bfb94daaa3fda3c4db7377 |
| tack_binding.py | 109cd28374997754c90b4b95cf969a4cb4972a3cfb5448cb941523444bbb1141 |
