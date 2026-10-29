# Arrangement ellipses: production artist-test build

Prepared October 29, 2026, from master 4105553362870da91f15f768e75b813f7d43598e.

## Status

Implementation, automated verification, package validation and source/archive comparison are complete. Artist hands-on acceptance is pending. No commit, push, PR or merge was made. The round-1 and round-2 reports describe historical experiments, not the current production state.

## Implemented scope

- Evaluated mesh slices at the existing bands now store independent fitted side/depth radii and section bases. No bone, rig or vertex-group lookup is used. Unsamplable sections retain the body-extents fallback, now elliptical.
- Every wrapped row selects neighboring sections in its torso, same-side arm or same-side leg stack; centers and ellipse axis vectors interpolate at that row height. Clearance remains radial. Terminal sections clamp their cross-section while retaining each row height. No body-surface projection is performed.
- Arc-length wrapping uses a 4,096-segment lookup cached per source row. Tangent-flat placement, relative G/R composition, spiral spacing, source paths, UVs, sewing and simulation remain separate.
- Setup format 2 and arrangement-record version 2 are supported. Document format stays 4. Loading a format-1 setup does not rewrite it or move its panels. Explicit per-piece re-arrangement generates format 2, retains the original format-1 snapshot, and opts in only the selected record. Other legacy records still use that snapshot. Regeneration explicitly replaces the setup for all records. Stable/custom point IDs and volume edits survive per-piece conversion; regeneration still resets edits.
- New starters opt into version 2. Back clones retain their source record version. Library refits still use stable volume/point IDs.
- Cached guide rings display ellipses. Cache signatures include every stored setup byte without re-encoding that JSON on each redraw. No per-redraw slicing or panel wrapping is introduced.

Only the two approved core.py edits were made: arrangement_record gains keyword-only version=1; validate_arrangement accepts integer versions 1 and 2. AST comparison excludes just those two functions and matches all other core code. garment.py, meshing.py, placement.py and tack_binding.py are byte-identical to baseline.

## Production evidence

Fixtures are the same two synthetic 16-segment, 12-ring refit meshes with applied scales, not real VRChat avatars. A measures 0.50 x 0.30 x 1.00 m; B measures 0.80 x 0.40 x 1.50 m. Clearance is 30 mm and panel spacing is 20 mm. Tall panels are 0.60 x 0.80 m and 0.96 x 1.20 m; ordinary bodices are 0.40 x 0.45 m.

Counts are body/panel triangle pairs / unique intersecting panel faces / signed-nearest inside vertices (1 micrometre inside tolerance).

| Body / piece | Vertices | Circle | Production row-height ellipse |
| --- | ---: | ---: | ---: |
| A / bodice front | 576 | 0 / 0 / 0 | 0 / 0 / 0 |
| A / tall | 1470 | 0 / 0 / 0 | 0 / 0 / 0 |
| B / bodice front | 576 | 0 / 0 / 0 | 0 / 0 / 0 |
| B / tall | 3450 | 0 / 0 / 0 | 0 / 0 / 0 |

The actual chest/front arrangement point is closer to the evaluated mesh on both bodies. These are nearest point-to-mesh gaps, not minimum clearance over the entire panel:

| Body | Circle point gap (mm) | Ellipse point gap (mm) |
| --- | ---: | ---: |
| A | 117.356747389 | 29.771050438 |
| B | 205.270275474 | 29.818676412 |

All 42 mean and maximum loop gaps improve over the circle. The maximum change from round-1 ellipse measurements is 8.526512829121202e-14 mm, within the stated 0.000001 mm tolerance. Each loop uses 256 equal-arc samples and absolute nearest Euclidean circle/ellipse distance; section-gap measurements exclude clearance.

| Body | Volume | Sample | Circle mean (mm) | Circle max (mm) | Ellipse mean (mm) | Ellipse max (mm) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | chest | 0 | 51.981843670 | 95.052316835 | 2.220378649 | 4.363924710 |
| A | chest | 1 | 50.910081568 | 93.090586478 | 2.171104241 | 4.282886474 |
| A | chest | 2 | 49.844793864 | 91.144814810 | 2.128600269 | 4.187647424 |
| A | chest | 3 | 48.775158362 | 89.189489332 | 2.081541563 | 4.101287523 |
| A | chest | 4 | 47.575834725 | 86.994716258 | 2.029365717 | 4.002273575 |
| A | chest | 5 | 45.599875542 | 83.381873197 | 1.947997481 | 3.818805527 |
| A | chest | 6 | 43.617661540 | 79.756087092 | 1.860093976 | 3.669393763 |
| A | waist | 0 | 54.829122967 | 100.258586468 | 2.342144209 | 4.595074278 |
| A | waist | 1 | 54.538129644 | 99.726548746 | 2.329762364 | 4.574522240 |
| A | waist | 2 | 54.246203226 | 99.193179257 | 2.316401019 | 4.558057068 |
| A | waist | 3 | 53.953539899 | 98.658309743 | 2.302259746 | 4.537435107 |
| A | waist | 4 | 53.661665011 | 98.122938539 | 2.288953549 | 4.514245065 |
| A | waist | 5 | 53.352724160 | 97.558827872 | 2.276296723 | 4.487753752 |
| A | waist | 6 | 52.439203162 | 95.888851541 | 2.239437998 | 4.405435115 |
| A | hip | 0 | 54.247177327 | 99.193756729 | 2.317415993 | 4.541754605 |
| A | hip | 1 | 54.511862229 | 99.679438704 | 2.326613349 | 4.583241811 |
| A | hip | 2 | 54.776609359 | 100.160172529 | 2.335897968 | 4.608112160 |
| A | hip | 3 | 55.047336281 | 100.657732080 | 2.351407211 | 4.620130715 |
| A | hip | 4 | 55.213460351 | 100.960116521 | 2.354833743 | 4.644894891 |
| A | hip | 5 | 54.948292187 | 100.477525643 | 2.345129036 | 4.620123045 |
| A | hip | 6 | 54.683699147 | 99.992304341 | 2.336028235 | 4.580611167 |
| B | chest | 0 | 104.042055962 | 189.040089132 | 3.118609559 | 6.839634701 |
| B | chest | 1 | 101.903533639 | 185.155161750 | 3.054150420 | 6.702798463 |
| B | chest | 2 | 99.764232845 | 181.267238788 | 2.989099092 | 6.567289679 |
| B | chest | 3 | 97.620281509 | 177.369377256 | 2.919087828 | 6.418677670 |
| B | chest | 4 | 95.228651611 | 173.027060629 | 2.854111500 | 6.264462813 |
| B | chest | 5 | 91.268134841 | 165.829222075 | 2.735786969 | 5.993072441 |
| B | chest | 6 | 87.305796160 | 158.630792698 | 2.615808531 | 5.747171329 |
| B | waist | 0 | 109.740860833 | 199.392505906 | 3.289590335 | 7.203842506 |
| B | waist | 1 | 109.155947962 | 198.331406960 | 3.269911869 | 7.185568587 |
| B | waist | 2 | 108.571444456 | 197.269054271 | 3.250429708 | 7.145817098 |
| B | waist | 3 | 107.993177778 | 196.218719132 | 3.237103083 | 7.097100231 |
| B | waist | 4 | 107.410131602 | 195.160140413 | 3.219206918 | 7.067616253 |
| B | waist | 5 | 106.786029845 | 194.024958096 | 3.196015546 | 7.027228915 |
| B | waist | 6 | 104.957384591 | 190.703155562 | 3.145199691 | 6.908646208 |
| B | hip | 0 | 108.572931729 | 197.271989874 | 3.251951773 | 7.147132938 |
| B | hip | 1 | 109.108970710 | 198.246638049 | 3.269959532 | 7.180620061 |
| B | hip | 2 | 109.642575956 | 199.215959911 | 3.285635163 | 7.216955304 |
| B | hip | 3 | 110.176233579 | 200.185449003 | 3.301342745 | 7.252446321 |
| B | hip | 4 | 110.516964533 | 200.805191562 | 3.312340900 | 7.271403833 |
| B | hip | 5 | 109.980699586 | 199.829823806 | 3.294167753 | 7.239755496 |
| B | hip | 6 | 109.449018766 | 198.865054411 | 3.280253172 | 7.198799321 |

## Workflow and compatibility checks

- Both fixtures: exact equality of generated setups, world points and all bodice/tall world vertices without and with an inert armature. Evaluated geometry, not armature presence, is the input.
- Two legacy pieces: opening/building leaves stored setup bytes unchanged; re-arranging one changes only its version and geometry; the other retains exact world vertices; explicit regeneration then updates that legacy piece.
- Flat panels stay planar; wrapped panels retain source paths and UVs; native G/R capture, document roundtrip and rebuild agree within 0.000002 m.
- A 2.5-turn spiral stays finite and consecutive same-phase turns retain 30 mm radial spacing.
- Existing oblique-arm and transform tests pass. Added unit checks cover independent radii, nonorthogonal transformed ellipse vectors, exact row center/radius interpolation, terminal clamping, fallback extents, malformed v2 fields and invalid legacy snapshots.
- Existing garment, sewing, simulation, meshing-baseline, UV, library, Keep mesh, arrangement and display suites pass.

## Display performance

Same benchmark: Blender 5.2.3 LTS, 36,300 avatar vertices, six patterns, 96 points, 12 volumes, 1,229 x 880 viewport, three 120-frame repeats. The display is refresh-limited near 144 FPS; hardware/CPU samples vary. Values below are arithmetic means across the three repeats.

| Metric | Circle baseline | Final ellipse build |
| --- | ---: | ---: |
| Display-on FPS | 143.494158 | 143.832670 |
| Display-on draw time (ms) | 0.428656 | 0.392024 |
| Display-on CPU, one-core % | 81.589872 | 83.029037 |

GUI regressions assert one world resolution for unchanged redraws, zero orbit-time GPU batch rebuilds, correct hit projection and raster equivalence, cache invalidation on edits/transforms, and no hidden geometry work when H is off.

## Verification and package

- python tools/dev.py --test --build --keep-scratch: headless tests, all nine background suites and all seven GUI suites pass; Blender extension validation passes.
- python tools/check_comments.py: 99 Python files pass tokenization plus AST standalone-string/docstring checks. Embedded GLSL comment checks and launcher review pass; no generated application code was introduced.
- python -m tools.check_dead_code: all 37 package modules pass.
- git diff --check passes. Package member names and all 77 file payloads exactly match current runtime source, assets, README, SPEC and LICENSE.
- Publication check covers current source, installable archive, reachable historical blobs and public commit identities. The existing notice that 23 commits retain an explicitly accepted historical author identity remains; no history rewrite or complete privacy purge is claimed.

Installable build: dist/devil_designer-0.9.0.zip. The extension version is unchanged; only the requested arrangement formats advance.

ZIP SHA-256: cf632389e4c4172e3fc87b7998e2abe5c975b08848aaf7943b143de6655926b6.

Packaged-source fingerprint: 77c0627bd4987f0883c58f7a71f201c9bca2791f12d60379293c4600c232637b. This hashes each sorted archive member name, a NUL, and its SHA-256 bytes.

Validation-source fingerprint: a59fb03e91758c7dfa7bf157eff18d4f3097e3d4f69c042857d150e9b8d933c3. This uses the same algorithm over all 142 non-cache files under devil_designer/, tests/ and tools/, plus AGENTS.md, README.md, SPEC.md, LICENSE, dev.cmd and dev.ps1, with repository-relative names. Evidence reports and disposable scratch are excluded.

The package is synced to the existing user extension directory by the developer runner. Save open projects and restart Blender to unload previously loaded Python modules before testing. Disposable scratch is cleaned through the validated runner after retaining this report; dist and user projects are preserved.

## Artist acceptance gate

Ready for your test. Please test this build:

1. On two differently proportioned real bodies, regenerate the setup and arrange a bodice and tall piece at chest/front. Inspect width/depth fit and intersections, including without an armature.
2. Open an older design: verify it stays unchanged, then re-arrange only one piece and confirm other pieces stay put. Separately test explicit regeneration.
3. Check Arrange flat, a wide spiral, native G/R adjustments and reset-to-layout, H/orbit responsiveness, library refit, Simulate and Keep mesh.

The numerical fit/intersection guarantee here is limited to the two synthetic torso fixtures. Arbitrary anatomical bodies and limb intersections still need artist inspection; no automatic tailoring or MD-wide feature parity is claimed.

If it passes, reply PR or ship it; final checks, PR/merge and session closure can then proceed under the artist-acceptance workflow. No PR or merge is authorized by this implementation approval alone.

## Recorded artist acceptance: October 29, 2026

The artist accepted the exact handed-off build and authorized the merge-to-master
shipping workflow, without a release. This supersedes the pending acceptance state
recorded above; the application source and accepted package remain unchanged.

Acceptance message:

> Ship it. The artist's hands-on test passed: arrangements hug the body, old versions still save and load, and the update is more convenient than the old behavior. Proceed with the ship flow for Prompt 10 v2: final checks, open the PR, merge into master once checks pass, verify master, and run the cleanup audit per the repo rules, then close the session. No release in this step — merge to master only.

Accepted ZIP SHA-256:
cf632389e4c4172e3fc87b7998e2abe5c975b08848aaf7943b143de6655926b6.
Accepted validation-source fingerprint:
a59fb03e91758c7dfa7bf157eff18d4f3097e3d4f69c042857d150e9b8d933c3.

Recorded as deferred, non-blocking and outside this shipping run: action-time
micro-stutter during pins, point edits, duplication and 2D panel moves;
auto-measurement line/label alignment; and a wrap-direction cue. None is
investigated or changed by this run.
