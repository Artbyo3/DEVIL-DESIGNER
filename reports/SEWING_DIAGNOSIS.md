# Sewing diagnosis and compiler-truth preview

Round 3 correction: the artist found the existing reversal control and confirms manually reversing default-created seams fixes their garments. See SEWING_DIRECTION_VERIFICATION.md for the complete control map, creation decision points, and twelve controlled reproductions. Earlier middle-only and wrong-cuff fixtures below distinguish possible mechanisms; they are not attribution of the artist incidents. Artist-file attribution remains out of scope. Round 3 changes diagnostic tooling only, so the round 2 diagnostic source fingerprint below identifies that historical run, not the revised reusable runner. The artist subsequently approved the exact round 2 package for shipping; the historical acceptance status at the end describes the original handoff only.

Date: 2026-10-29. Round 2: initialized native rest-length gate passed; production preview implemented and verified; ready for artist testing. No simulation or sewing fixes applied.

## Recommendation

Add compiler-resolved correspondence links and direction arrows because a correctly positioned sleeve can still contain a destructive sewing instruction. Do not change the solver, force cap or zero-length sewing target based on these measurements. Artist files are waived this round; the sleeve results demonstrate a mechanism, not attribution of the actual incident.

## Source and experiment scope

- Read AGENTS.md, README.md and SPEC.md before inspecting the sewing path.
- Local master and refreshed origin/master both point to 22b8355cd0e573094476b1898adf5c65fb5223d6.
- The checkout already contains uncommitted Prompt 14 viewport sewing changes. Their interactions and placement behavior were preserved; the draw paths are extended by this preview. Each fixture was also run against a clean git archive of that exact master inside scratch/master-source.
- All 13 compiled geometry/topology/pair fingerprints match master exactly; all frame-31 per-seam mean-gap measurements match master exactly (maximum difference 0 mm). Existing Prompt 14 work is not the cause of differences observed here.
- Blender 5.2.3 LTS, build e13b728c6880; quality 8; sewing force cap 50; spacing 25 mm, except the remesh case changes to 18 mm after building. Cotton, no shrink, no pins, no freeze/deactivate/strengthen, gravity enabled, self collision enabled. Sequential evaluation from frame 1 through 31 gives 30 simulation steps. No playback/timer approximation.
- Ordinary pieces are 20 by 30 cm, facing each other with 130 mm plane separation. Their collider is moved away to isolate sewing. Sleeve panels are 16 by 60 cm; cuffs are 16 by 5 cm. The arm is a closed 48-sided cylinder of radius 50 mm and length 800 mm. Sleeve panels face opposite sides of the arm, with long axes parallel to it. Wrist height is z=0.8 m, shoulder height z=1.4 m. Cuffs occupy z=0.75 through 0.8 m.
- These are controlled synthetic tests, not an artist-file reproduction, not a broad fabric study, and not a solver calibration. Late unpinned motion is not by itself proof of a sewing bug.

## End-to-end trace

1. core.py:213 (Seam) and core.py:344 (edge_vertices): records reference persistent pattern/path/endpoint IDs and fractional arc-length spans. Chain aliases and direction are validated. No new sewing format was introduced.
2. core.py:353 through chain_position: each side is traversed by normalized total arc length. meshing.py:11 edge_counts unions regular ratios and source boundary fractions from both sides; reversed side B uses 1-ratio. Partial and M:N chain boundaries become explicit correspondence samples. density.py:15 boundary_plan applies the finest spacing in a seam-connected component.
3. meshing.py:62 fabric_mesh and native_features.py:8 decorate_mesh map those fractions through CDT output vertices (and slit splitting) to stored dd_edge_samples. Flat source coordinates are retained in panel dd_rest for diagnostics.
4. garment.py:299 compile_garment rebuilds stale panels if document, spacing or units changed. garment.py:347-360 resolves each plan fraction against samples on the SAME referenced edge, requires fraction error <= 1e-6, discards self-links, sorts endpoints and deduplicates undirected pairs. This is NOT nearest spatial-edge reattachment. The smallest fraction difference is used only inside the existing edge's sample table. Missing references fail validation or are pruned with repair feedback during an editor transaction.
5. garment.py:361-379 creates loose mesh edges and records their indices in dd_sewing_pairs. Native cloth has use_sewing_springs enabled and sewing_force_max=50. The baseline compiler did not emit per-seam resolved IDs or per-spring native rest lengths; the round-2 inspection extraction adds resolved IDs and the native-verified JOIN contract only.
6. Exact Blender build source, source/blender/blenkernel/intern/cloth.cc:1605-1610, gives loose sewing springs restlen=0 and lin_stiffness=1. This is the JOIN target, not the desired length of a sleeve edge. Structural springs use adjacent vertex distances, with any configured shrink factor; cloth.cc:772-781 uses initial arranged geometry unless a rest shape key is supplied. A panel's custom dd_rest attribute is not automatically a native rest shape key.
7. Exact Blender build source, source/blender/simulation/intern/SIM_mass_spring.cc:389-412: effective sewing tension uses the cloth tension range, normalized by average spring length; the linear sewing force is capped by max_sewing. The force cap is not a stiffness value. Cotton tension range is 25/25 in these fixtures.
8. Native evaluation moves the vertices. Frame metrics below read evaluated coordinates, not the original mesh. Final welding in garment.py:436 uses the same stored undirected pairs, but welding was not used in these tests.

The exact-build Blender source files downloaded for inspection are scratch/blender-cloth-exact.txt and scratch/blender-solver.txt. Their source commit is e13b728c6880; these text copies are diagnostic artifacts, not added application code.

## Ranked demonstrated failure mechanisms

### 1. A long sleeve edge can validly be sewn to a short cuff edge

Evidence: changing only the seam topology while keeping the same four panels and arrangement connects the front panel's 600 mm long edge to a 160 mm cuff edge: 73.333% mismatch by the existing max-length denominator. There are 31 DISTINCT targets, not one welded point. Every target lies at wrist z=0.8 m. Both panels rapidly shorten because one side is coupled through the remaining correct long seam. By frame 5 the front/back axial spans are 244.612/270.629 mm, versus 591.309/591.321 mm in the correctly sewn control.

Locations: core.py:371 computes mismatch; core.py:375 validate_seams permits intentional gathers; design_tools.py:297 warns nonblockingly above 1%; garment.py:349 and sewing_preview.py:9 compile the allowed pairing. This is a faithfully compiled destructive instruction, NOT evidence that the compiler secretly redirected a correct long seam into the cuff. Do not ban all mismatch: legitimate gathers use the same model.

### 2. Wrong direction can faithfully compile into a crossed, shortening join

Evidence: on otherwise identical 300 mm edges, flipping the direction makes opposite physical ends connect. The correct fixture is 298.3/298.0 mm tall at frame 5; the wrong-direction fixture is 243.3/226.7 mm. At frame 31 its seam mean/max gap is 8.753/18.003 mm versus 0.0017/0.0065 mm for the correct control. Pairing diff remains exactly zero. Direction is a physical relationship between chains: reverse=True is not intrinsically wrong, and reverse=False is not intrinsically safe.

Locations: core.py:360 chain_position; meshing.py:40-41 selects B at 1-ratio; core.py:1059 reverse_seam; draw.py:1064 marks only a start dot. A renderer must show paired order, not label every reverse=True seam as erroneous.

### 3. The baseline preview hid the instruction that causes those failures

Evidence: the wrong cuff fixture contains 31 actual cross-piece vertex constraints on the dangerous seam. The current 2D renderer and the uncommitted 3D renderer show a single dashed midpoint-to-midpoint connector, not 31 actual correspondences. The 3D renderer samples each drawn side at 49 display positions, independent of the compiler's sample count. Number badges do not encode mismatch or pass/warn text. Existing color/mismatch feedback is useful and must be preserved, not described as nonexistent.

Baseline locations: draw.py:1045 midpoint connector; minimal.py:105 seam_badges; original Prompt 14 viewport_sewing.py:122 midpoint connector. Current remedies: draw.py:1046 and viewport_sewing.py:205 draw all shared resolved links; sewing_preview.py:63 reads exact panel coordinates. This is a demonstrated diagnostic blind spot, not proof that drawing causes a solver failure.

## Cleared suspects and unresolved observations

- Compiler drift/hidden reversal: all 424 resolved per-seam pairs across 13 fixtures agree exactly with compiled dd_sewing_pairs after the compiler's same self-link and duplicate filtering. Maximum flat position discrepancy is below 0.000052 mm (float storage); no materially displaced endpoint was found.
- Nearest-edge reattachment: no such sewing operation exists on the traced path. The same-edge fraction lookup measured clean. Tacks use nearest-body binding, but that is a different subsystem.
- Concentration at one target vertex: absent, including the deliberately bad sleeve. It targets 31 distinct cuff vertices spread across 160 mm, all at the same wrist height.
- Equal and partial M:N distribution: the compiler uses normalized arc length. The 10% mismatch fixture has adjacent B/A length ratios 0.8999994 through 0.9000002: uniform input ease, not an end-biased compiler distribution. The 2:1 partial M:N fixture also matches exactly.
- Native join rest length: exact-build source specifies 0, which is the intended closure target. Do not mistake that for a 0-length structural sleeve. Planar adjacent structural distances differ from flat source distances by at most 0.000387 mm across these fixtures, consistent with float storage, not a missing 600 mm structural length.
- Actual ease is not uniform after draping: in the 10% fixture, front side signed strain over successive thirds at frame 31 is -2.057%, -4.965%, +2.476%; back is +6.696%, +4.514%, +8.468%. Local absolute stretch reaches 238.539%. This proves nonuniform OUTCOME, not nonuniform compiler input, nor which native collision/material/triangulation effect caused it. No force/stiffness fix is justified by this test alone.
- Split and partial seams can have substantial local strain even though their correspondence is correct. Their small gaps do not certify good cloth quality. Mesh/solver sensitivity is a follow-up, not a proved root cause. No protected meshing or solver changes were made.
- Initial body penetration: absent in both sleeve fixtures; minimum radial clearances are 15.192 mm (control) and 15.000 mm (wrong cuff). All initial panel vertices are outside the analytic cylinder, and flat panel faces lie on planes outside its radius. This clears initial panel penetration for these synthetic cases only. It says nothing about the artist's actual arm, clothing or contact margins.

## Editing fallout

The edited, split and remesh cases first build their old live panels, THEN change the source or spacing, and call compile without manually rebuilding. All three automatically rebuild, preserve their existing panel transforms, and produce exact correspondences. The edited endpoint moves 60 mm, making one seam 360 vs 300 mm: mismatch becomes 16.667%. Split at fraction 0.37 remaps one side into two chain spans; its geometric length remains 300 mm. Remeshing from 25 to 18 mm changes sample count to 18 pairs without changing the referenced sewing spans.

Existing semantics: valid references follow edited geometry; invalid references can be pruned by core.py:466 during Session.commit at core.py:686, with last_repairs feedback shown by editor.py. No persistent sewn-at geometry snapshot exists, so a later reopened file cannot distinguish an intentional edit from historical drift by comparing current records alone. Actual invalid-edge deletion was source-traced, not separately simulated in this run.

## Fixed 30-step simulation measurements

Gap means actual paired-vertex separation in millimetres. Stretch is absolute relative change of consecutive unique mapped sample intervals along either seam side, versus that SAME interval on the initial arranged panels, expressed as percent. Both extension and compression count. Mean stretch is unweighted over intervals; it can be dominated by short intervals. It is not a fabric-wide stress estimate or native spring-force readback. The signed length-weighted thirds above supplement that statistic. These are per-seam metrics, not whole-garment averages.

| Fixture / seam | Pairs | Gap mean / max (mm) | Absolute stretch mean / max (%) |
| --- | ---: | ---: | ---: |
| equal / 1: Front to Back | 13 | 0.0017 / 0.0065 | 0.009 / 0.023 |
| mismatch_10 / 1: Front to Back | 23 | 0.9614 / 3.6001 | 23.626 / 238.539 |
| partial / 1: Front to Back | 15 | 0.3681 / 0.8118 | 24.654 / 149.856 |
| partial_mn / 1: Front to Back | 25 | 0.0194 / 0.1881 | 0.112 / 1.159 |
| edited / 1: Front to Back | 25 | 0.9766 / 1.6668 | 7.166 / 30.723 |
| split / 1: Front to Back | 25 | 0.6093 / 2.9383 | 20.589 / 288.237 |
| remeshed / 1: Front to Back | 18 | 0.0000 / 0.0000 | 0.000 / 0.001 |
| reversed / 1: Front to Back | 13 | 8.7532 / 18.0028 | 16.160 / 32.789 |
| sleeve_correct / 1: Front to Back | 25 | 7.7714 / 15.4473 | 1.773 / 6.957 |
| sleeve_correct / 2: Front to Back | 25 | 7.5081 / 10.4517 | 1.905 / 8.097 |
| sleeve_correct / 3: Front to Cuff front | 8 | 2.6995 / 7.5461 | 14.082 / 33.572 |
| sleeve_correct / 4: Back to Cuff back | 8 | 3.5877 / 7.7904 | 17.923 / 47.029 |
| sleeve_correct / 5: Cuff front to Cuff back | 3 | 7.4912 / 12.7512 | 2.168 / 4.664 |
| sleeve_correct / 6: Cuff front to Cuff back | 3 | 7.9093 / 13.5015 | 3.737 / 8.481 |
| sleeve_long_to_cuff / 1: Front to Back | 25 | 1.7642 / 13.2023 | 3.820 / 45.121 |
| sleeve_long_to_cuff / 2: Front to Cuff front | 31 | 7.3648 / 15.5815 | 68.740 / 767.084 |
| sleeve_long_to_cuff / 3: Back to Cuff back | 8 | 4.7796 / 9.4093 | 15.896 / 43.511 |
| sleeve_long_to_cuff / 4: Cuff front to Cuff back | 3 | 3.4295 / 6.4070 | 9.058 / 13.354 |
| sleeve_long_to_cuff / 5: Cuff front to Cuff back | 3 | 11.4599 / 14.6727 | 25.564 / 33.184 |

| trousers_full / 1: Front to Back | 37 | 0.0064 / 0.0196 | 0.013 / 0.040 |
| trousers_middle_record / 1: Front to Back | 15 | 0.5401 / 1.7061 | 27.432 / 205.847 |
| trousers_nonuniform_nodes / 1: Front to Back | 73 | 0.4164 / 3.4457 | 10.897 / 298.629 |

## Trousers: pairing distribution, record versus compile

The artist describes lines converging near the crotch/inseam. No actual screenshots or source trousers file were attached for inspection here. The additional controls use 22 by 90 cm panels and isolate a long trouser-leg seam; they are not a fitted four-panel anatomical trouser reproduction around an actual avatar's thigh/calf volumes. Their distribution test does not depend on a particular body pose. They use the same compile and sequential simulation as the other isolated-panel fixtures.

For EACH unique compiled pair, scratch/sewing-diagnosis-pairs.csv exports the A and B arc fractions on the stored chains, B's oriented sewing progress, full-source-edge fractions, and actual compiled vertex indices. The JSON preserves the same full per-pair table. With reverse enabled the intrinsic relation is B=1-A; oriented sewing progress is B_oriented=A. These are arc fractions, NOT point indices.

| Control | Unique pairs | Coverage of full source edge A / B | Max normalized arc mapping error |
| --- | ---: | --- | ---: |
| Full 900 mm trouser seam | 37 | 0-100% / 0-100% | 1.11e-16 |
| Deliberate middle-only free range | 15 | 40-60% / 40-60% | 3.33e-16 |
| Full seam, unequal authoring-node spacing on A | 73 | Whole chain / whole chain | 1.67e-16 |
| Correct 600 mm sleeve long seam | 25 per side seam | 0-100% / 0-100% | 1.11e-16 |
| Wrong 600 mm sleeve-to-160 mm cuff seam | 31 | 0-100% / 0-100% | 1.11e-16 |

The unequal-node case splits A at 13% and 71.29% of its original long edge while B remains one segment. The actual compile pairs include (A=0.13, B=0.87) and (A=0.7129, B=0.2871). Equal authoring-point indexing would instead put the two A breaks at 1/3 and 2/3; that is NOT what compile does. Both endpoints remain present. There is no collapse of full-seam coverage to the middle. The maximum oriented arc mapping error over ALL 13 fixtures is 3.33e-16, and compiled-pair set difference remains exactly zero throughout.

The middle-only control demonstrates a DIFFERENT mechanism: the sewing RECORD deliberately stores t0=0.4 and t1=0.6 on both sides, so it contains 180 mm of each 900 mm edge. Compile correctly connects only that central 20%; 80% of each full edge is outside the stored seam. Normalized progress within the selected span is still perfectly linear. This is record coverage, not compiler bunching. No claim is made that the artist's records actually contain these ranges.

For the sleeve-to-cuff case, normalized progress is ALSO linear, but the physical domains differ: every 150 mm of long-edge travel maps to 40 mm of cuff travel (600:160). The mapping covers the whole cuff, not a single cuff point; its endpoints and all intervening targets are at wrist height z=0.8 m. Geometric convergence toward the wrist therefore does not require arc-fraction bunching. The correct long sleeve seams map 600 mm to 600 mm and span shoulder to wrist on both sides.

Conclusion: there is no measured shared compiler-bunching root cause. These controls distinguish (1) midpoint-only DISPLAY shorthand, (2) central partial-range RECORD coverage, and (3) uniformly distributed but physically short sleeve/cuff destinations. The existing 3D display's one midpoint connector per seam can visually cluster centrally even when all 37 actual long-trouser correspondences span the full edges. Its 49 side-stroke samples are NOT drawn sewing pair constraints. A screenshot of that shorthand cannot prove the outer edge is physically unsewn. Artist-file attribution is out of scope this round; these controls do not choose among explanations for that incident.

## Sleeve-specific conclusion

The control retains about 590 mm of its 600 mm axial span at frame 31. The deliberately wrong cuff map shortens the front to 198 mm and back to 304 mm, while its overall center falls from z=1.059 to 0.913 m toward the wrist at z=0.8 m. Its frame-3 front span is already 281 mm. Thus a valid-looking arrangement plus wrong seam destination CAN produce rapid wristward collapse without initial penetration. This reproduction is rapid contraction, not a claim of an identical tight-ball shape to the artist's file.

| Frame | Correct front / back span (mm) | Wrong cuff front / back span (mm) |
| ---: | ---: | ---: |
| 1 | 600.000 / 600.000 | 600.000 / 600.000 |
| 2 | 587.048 / 588.259 | 499.306 / 522.253 |
| 3 | 590.135 / 590.914 | 281.054 / 351.034 |
| 5 | 591.309 / 591.321 | 244.612 / 270.629 |
| 10 | 591.441 / 591.885 | 215.019 / 264.480 |
| 31 | 590.189 / 589.538 | 198.347 / 304.376 |

Actual artist-file attribution is out of scope for this round. The surrogate does not establish the artist's stored cuff spans, physical endpoint direction, structural rest shape, or contact state.

## Round 2 prototype gate: PASSED

The artist files are waived for this round. Artist-file attribution is out of scope: the sleeve and trousers conclusions above describe controlled mechanisms only, not the cause of either actual incident. No request for those files remains outstanding.

Initialized native spring readback was measured on Blender 5.2.3 LTS build e13b728c6880, Windows x64, at frame 1 before stepping. A scratch-only, read-only ReadProcessMemory probe traversed the evaluated modifier's actual ClothSpring linked list. The saved file's SDNA supplies ClothModifierData.clothObject offset 128; the exact-build Spring layout supplies restlen offset 40 and type offset 48. Build hash, pointer size, vertex bounds, finite values, list acyclicity and component counts are checked before accepting a result. Combined spring flags count separately in the native component count. This is actual initialized data, not an RNA availability test or an assumption that all loose edges have zero target.

| Fixture | Initialized native sewing springs | Preview/compiler/native pair difference | Max absolute native/preview JOIN rest difference (m) |
| --- | ---: | ---: | ---: |
| equal | 13 | 0 | 0 |
| mismatch_10 | 23 | 0 | 0 |
| partial | 15 | 0 | 0 |
| partial_mn | 25 | 0 | 0 |
| edited | 25 | 0 | 0 |
| split | 25 | 0 | 0 |
| remeshed | 18 | 0 | 0 |
| reversed | 13 | 0 | 0 |
| sleeve_correct | 72 | 0 | 0 |
| sleeve_long_to_cuff | 70 | 0 | 0 |
| trousers_full | 37 | 0 | 0 |
| trousers_middle_record | 15 | 0 | 0 |
| trousers_nonuniform_nodes | 73 | 0 | 0 |
| Total | 424 | 0 | 0 |

Every sewing spring reads restlen=0.0 and lin_stiffness=1.0. As a nonzero-layout control, the same traversal reads 16,988 structural springs with rest lengths 0.0009523630142211914 through 0.03664134070277214 m. Thus the probe does not merely read zeros at a guessed offset. Direct native structural-rest versus flat-pattern comparison has a maximum error of 0.00038743019104003906 mm across all 13 fixtures (largest fixture mean 0.00012960551009186805 mm), confirming float-scale differences rather than a lost sleeve length. The production preview's ordered pairs and per-pair rest contract match the compiler's inspection records exactly on all 13 fixtures; their union matches the actual native sewing set exactly. All 13 compiled geometry/topology/pair fingerprints remain identical to the original exact-master run. The extraction changes no measured simulated result or sewing instruction.

## Production implementation and approved scope

The approved change extracts only the existing fraction-to-index lookup, same-edge 1e-6 guard, self-link removal and undirected deduplication into sewing_preview.resolve_sewing. garment.compile_garment calls that helper and stores its ordered per-seam inspection on the generated simulation object. The garment document format is unchanged. Existing setup, forces, cloth loop, modifiers, placement and meshing output are unchanged; the original protected-code fingerprint test still verifies them after removing only the specifically approved inspection hook.

Both renderers now draw EVERY resolved correspondence, not a representative midpoint line. Existing smooth edge strokes, start markers, selection, picking and in-progress sewing remain. Paired-order arrowheads on both sides make direction visible. Each seam shows current mismatch percent and the existing >1% Gather warning; sewing allowed wording, otherwise Pass. B reversed is a direction flag, not proof of an invalid seam: reversed=True is often the correct physical join. Partial and middle-only source ranges are labelled in place. Local physical-interval imbalance on mismatched edges is flagged as Uneven ease risk, not a predicted simulation outcome. Flat-point disagreement over 1 micrometre is labelled Pairing drift; rebuild panels. Edits observed during the editor session add Edited span; check pairing.

Preview snapshots use the same compiled panel sample maps and actual arranged coordinates. Stale panels are explicitly refused until live-panel rebuilding completes; no approximate correspondence fallback is drawn. Freeze, Deactivate and Strengthen inspect the existing active-document topology in an isolated temporary scene using existing build/pose-transfer functions. Inactive seams are labelled inactive and produce no links. Temporary resources are cleaned on success and failure. No live compiler invocation, playback or native memory inspection is performed by the UI. Ordinary orbit redraws reuse cached data. The native probe is diagnostic-only and is not packaged.

Limits: no historical sewn-at snapshot is added, so a reopened document cannot reconstruct pre-edit intent. A direction flag cannot determine whether a physical join was artistically intended. Uneven resulting drape is not inferred from uniform input ease. Existing source strokes remain authoring outlines while correspondence endpoints are the actual discretized panel vertices. No solver or sewing bug fix is justified by the clean correspondence measurements; no behavior-changing protected fix was applied.

## Reproduction and verification

The scratch-first probes are preserved as tools/sewing_diagnosis.py and tools/sewing_native_probe.py for repeatable measurements; neither is part of the installed add-on. Run Blender with --background --factory-startup --python-exit-code 1 --python tools/sewing_diagnosis.py and bytecode disabled. Set DD_NATIVE_PROBE=1 for initialized readback on the explicitly supported exact build; DD_DIAG_REPORT=sewing-native-final.json selects the final report name. Without DD_NATIVE_PROBE the portable diagnosis still measures compiler/preview pairing. The JSON contains every native spring and every exported seam arc-fraction pair, with a sibling CSV. The earlier exact-master comparison used a git archive in scratch/master-source, not a branch or worktree. Only generated diagnostic artifacts and downloaded exact-build source are disposable; use the developer runner to clean them after review.

Permanent regression tests: tests/test_sewing_preview.py verifies resolution, duplicate attribution, stale-fraction refusal, coverage, direction and warning threshold. tests/blender_sewing_preview.py verifies exact compiler correspondence/rest-contract parity, arranged endpoints, state isolation, unchanged scene/resource counts and failure cleanup across eleven cases, including transfer of a current simulated pose into Freeze. tests/gui_viewport_sewing.py checks that both actual rendering paths include every resolved pair and that 3D strokes/arrows and both readouts remain present, alongside all existing Prompt 14 interactions. tests/test_cloth_integrity.py retains its original protected-code digest outside the approved extraction.

Verification completed: python tools/dev.py --test --build --keep-scratch passed the headless suite, all 11 configured Blender background suites, all 8 configured in-engine GUI suites, packaging and Blender extension validation. Headless rerun: 362 tests, 348 passed and 14 expected Blender-only skips. Viewport sewing GUI: 118 checks. The final native diagnostic rerun also passed all 13 fixtures. Rule Zero tokenization plus AST checks passed 110 Python files; the three generated/scratch Python scripts were checked separately. The dead-code/unused-import checker passed all 41 package modules. git diff --check passed. Publication scanning covers current source, archives and reachable history; it is not a history privacy purge and retains 25 explicitly accepted published author identities.

Installable archive: dist/devil_designer-0.9.0.zip. All 81 archive entries match current source bytes. Package SHA-256: 599d222bd58875f3502250420755f5b02e0b357f7198ee1f19b73f6c6ed65a48. Packaged-source fingerprint, SHA-256 of sorted relative names plus NUL plus file bytes: 19d842630ec1104539ff33270e58aafe047f55cffe63ed1b09eba03774e33526. The archive was validated with Blender and synced through the existing developer runner.

Reproducibility fingerprints: tools/sewing_diagnosis.py 41f7a8b9ac03a67ee782be77199ebddd88c10100e0d560e49750fbb9343e8f5d; tools/sewing_native_probe.py 4936ba2622c40bdbde261056a6ff653f02897cb381346f23869b99927f7fad7d; final raw native report 04091b42daefb238044c452c52b08eb9b2908e80b6c4f600562faeffc0110a9c. Raw outputs are disposable; rerunning produces fresh random seam IDs, while geometry fingerprints and measured comparisons remain reproducible.

Ready for artist testing, not accepted or shipped. No commit, PR, merge or release was made or authorized in this round.
