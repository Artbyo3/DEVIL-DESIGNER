# Sewing direction verification — round 3

## Scope and verdict

Verification and controlled reproduction only. No new Reverse action, UI change, default-direction fix, solver change, package change, or artist-file investigation was authorized in round 3. The artist confirmed an existing reversal works and explicitly deferred a fix. Their exact discovered control was not relayed; the candidates below are verified from source. Artist-file attribution is out of scope this round; the sleeve and trousers are controlled fixtures, not reconstructions of unavailable files or screenshots.

Existing seams can already be reversed in both views. The actionable deferred finding is the unconditional saved creation flag, together with a 2D pending-preview orientation calculation that is not used when committing. Correct orientation is not universally reverse=False: opposite-traversal control edges require True, whereas sides traversed in the same physical direction require False. A global flip would break the clean controls.

## Existing direction-control map

| Surface / time | Control and exact path | Coverage / limitation |
| --- | --- | --- |
| 2D, existing | Left-click seam badge selects; B calls Session.reverse_seam through run_edit: minimal.py:834, editor.py:1056 | Segment, free, partial and M:N share the existing record operation. Normal event flow only; draft/modal input may intercept keys. |
| 2D, existing | Right-click seam badge, Reverse: minimal.py:852, minimal.py:316, minimal.py:325, minimal.py:646 | Card dismisses after action. Right-clicking an ordinary sewn edge rather than its badge can open edge/point/piece controls instead: minimal.py:848. |
| Arranged 3D, existing | Select a visible sewn span in Select or Sew; B: viewport_sewing.py:393, viewport_sewing.py:411 | Uses the same record reversal and retains the arranged pose. Free Sew left-click is endpoint input, so select with Select or use right-click. |
| Arranged 3D, existing | Right-click unique visible sewn span, Reverse seam: viewport_sewing.py:430, viewport_sewing.py:438, viewport_sewing.py:454 | Native popup action calls run_edit at line 469. Ambiguous or occluded spans are not guessed. Playback/context checks can refuse the action. |
| 2D, creation | B with pending_edge, no selected seam: editor.py:1059 | Toggles saved scene flag. Selected seam reversal takes precedence. Free four-click / chain state alone does not satisfy pending_edge. |
| Arranged 3D, creation | B in Sew with no selected seam: viewport_sewing.py:393 | Toggles saved scene flag before or during input. FREE_SEW normalizes to SEW: editor.py:351. Selected seam still takes precedence. |
| Legacy nonminimal controls | Reverse side B creation toggle: controls.py:210; seam-list flip zone: controls.py:417, interaction.py:646 | Current minimal workspace does not expose the old inspector; gated by editor.py:662 and minimal.py:72. Not a current visible sidebar remedy. |
| Registered operator / scripting | bpy.ops.devil_designer.seam(seam_id=..., remove=False): operators.py:98, operators.py:111; Session.reverse_seam: core.py:1059 | API candidate, not the normal artist-facing popup. Raw operator does not use editor persist/history routing; operator UNDO is separate. |

The shared existing operation toggles seam.reverse in Session.commit (core.py:1059, core.py:686); it does not replace the record. Editor run_edit / persist (editor.py:314, editor.py:295) updates document/history and live panels. History is stored at core.py:1182. Compiler-truth preview requests invalidate on document changes (viewport_sewing.py:134, viewport_sewing.py:157); direction/status presentation is in sewing_preview.py:44. These paths cover the artist's case; there is no evidence that a duplicate operation is needed.

Other automatic direction mutations are not artist reversal controls: whole-piece horizontal/vertical mirror compensates when exactly one complete seam side is mirrored (core.py:851, core.py:894). Knife, mirror-with-seam and dart constructors explicitly choose True, False and True respectively (construction.py:106, construction.py:273, construction.py:400). Clone/load preserve stored direction.

Discoverability is inconsistent, not absent: 2D uses badges versus 3D spans, labels are Reverse versus Reverse seam, and B changes either an existing seam or a creation default depending on selection and pending state. design_tools.py:325 gives the existing-edge hint B flips; X removes. In free mode endpoint creation is processed before that selection branch. Source evidence supports this friction, not a claim that a specific control was invisible in the artist's session.

## Why the default can be wrong — filed for later, not fixed

The exact default is Scene.dd_sew_reverse=True (ui.py:56), also Seam.reverse=True (core.py:215) and Session.sew_chains(..., reverse=True) (core.py:1049). The saved scene flag persists; choosing a tool does not reset it.

All creation commits pass this flag without physical endpoint inference:

- Segment: design_tools.py:333, decision at line 336.
- Free four-click: design_tools.py:313, decision at line 319.
- M:N chain: design_tools.py:259, decision at line 263.
- 3D: viewport_sewing.py:448 forwards a surface hit into that SAME design_sew_click implementation. No separate 3D direction algorithm exists.

Segment side traversal follows canonical pattern/path vertex order and stored ranges (normally 0 to 1). First and second click choose A and B; clicking near one endpoint does not choose traversal. Camera/view and arranged piece pose do not participate. Swapping A/B does not automatically solve a reversed physical mapping.

Free sewing uses click order for start/end on each side via construction.path_range (construction.py:489): same-edge descending ranges are preserved; closed cross-edge ranges walk forward and may wrap; open backward ranges reverse edge order/ranges. If both sides were clicked wrist-to-shoulder, the default True then reverses B again, joining wrist to shoulder. Manual reversal correctly removes that additional inversion. Chain entry orients appended edges to the nearest preceding endpoint within each side (design_tools.py:303, construction.py:473), not between sides.

The compiler does exactly what the record says: meshing.py:40 maps A(u) to B(1-u) for True, B(u) otherwise. The 2D pending hover/HUD instead computes same_dir from the dot product of the two flat edge vectors, then uses not dd_sew_reverse when same_dir is true (draw.py:482, draw.py:483, draw.py:1120, draw.py:1121). Commit at design_tools.py:336 does not use that derived rev. Thus same-directed edges with default True can preview direct correspondence while committing reversed correspondence. The post-creation round 2 truth preview reads the committed mapping correctly. The 3D pending display (viewport_sewing.py:284) shows strokes/endpoints, not that pair prediction.

Deferred fix target: reconcile creation direction with endpoint traversal and pending preview at those decision points, consistently across segment/free/chains and both views. Preserve intentional reversal and opposite-oriented controls. This report does not authorize choosing an inference policy or changing code.

## Controlled reproduction

Command, with bytecode disabled and native-memory inspection disabled for this additional experiment:

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:DD_NATIVE_PROBE='0'
& 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/sewing_direction_diagnosis.py
~~~

The executable diagnostic reuses tools/sewing_diagnosis.py actual compile and simulation. Twelve fixtures completed successfully. Settings match round 2: Blender 5.2.3 LTS, cloth quality 8, 25 mm spacing, frames 1 through 31. Sleeve front/back are 600 mm long with cuff bands and an arm cylinder (wrist z=0.8 m, shoulder z=1.4 m); trousers are 900 mm two-panel off-body controls without leg colliders. This isolates direction, not exact artist anatomy or placement. The sleeve starts with zero penetrating vertices and minimum arm clearance 15.192 mm, unchanged by reversing records.

### Rapid shortening, with unchanged placement

Axial span, front/back in mm; frame 1 is initialized, frame 2 the first simulated sample.

| Fixture | Frame 2 | Frame 3 | Frame 5 | Frame 31 |
| --- | --- | --- | --- | --- |
| Sleeve correct | 587.048 / 588.259 | 590.135 / 590.914 | 591.309 / 591.321 | 590.189 / 589.538 |
| Sleeve one long seam reversed | 393.703 / 399.679 | 256.902 / 253.795 | 245.796 / 244.591 | 260.356 / 235.588 |
| Sleeve both long seams reversed | 287.865 / 281.809 | 114.829 / 124.636 | 121.041 / 123.221 | 156.136 / 152.831 |
| Sleeve cuff seam only reversed | 586.161 / 588.482 | 584.175 / 588.725 | 578.836 / 583.307 | 562.941 / 564.130 |
| Trousers correct | 899.239 / 898.933 | 901.250 / 900.820 | 899.415 / 899.420 | 895.286 / 893.944 |
| Trousers long seam reversed | 752.947 / 746.615 | 411.340 / 399.528 | 210.555 / 215.010 | 227.891 / 300.523 |

Sleeve conclusion: reversing long seams reproduces instant severe length loss; reversing only the cuff seam does not reproduce it in this fixture. The exact wrist-centered tight ball is NOT reproduced: paired-line convergence initially sits at z=1.1 m (forearm midpoint), not the wrist at 0.8 m. One-wrong-seam whole-garment center is 1.070498 m initially, 1.061477 m at frame 3 and 1.048207 m at frame 5; both-wrong center at frame 5 is 1.106728 m. Later unpinned fall is not evidence of instant wristward collapse. No stronger artist-specific attribution is justified.

### Central fan is not endpoint bunching

All 12 fixtures have compiler/expected pair symmetric difference zero. All selected full seam spans cover 0–100% on both edges; sleeve long seams have 25 distinct targets per side, trousers 37. Length mismatch is zero (trousers floating residual approximately 1.23e-14%). Normalized progress is linear, not index-bunched. For opposite canonical edges the correct intrinsic arc-fraction relation is B=1-A; deliberately wrong False changes it to B=A. Reversing a stored B traversal while keeping True creates the same wrong physical mapping.

At frame 1 the correct sleeve pair-line midpoints span z=0.800000012 to 1.400000095 m. Reversed long-seam midpoints all lie at 1.099999994 to 1.100000054 m: only 0.0000596 mm spread. Trousers correct midpoints span 0.800000012 to 1.700000048 m; wrong midpoints lie at 1.249999940 to 1.250000060 m: 0.0001192 mm spread. Every endpoint remains distributed over the full edge. The lines cross centrally because of reversed endpoint order, not because destinations occupy a middle-only subrange. This strongly reproduces the described trousers central fan and rapid collapse, without claiming screenshot pixel equivalence.

Both cases therefore share a demonstrated wrong-direction collapse mechanism. The exact wrist location remains unproven. Earlier round 2 middle-only and wrong-cuff controls remain separate diagnostics, NOT attribution of these artist incidents; the artist's corrected explanation supersedes that framing.

### Gaps and existing-reversal parity

Frame 31 seam 0 gap mean / max in mm: sleeve correct 7.771 / 15.447; one-long reversed 8.647 / 16.040; both-long reversed 15.172 / 48.521; cuff-only reversed (seam 0 still correct) 6.999 / 12.807; trousers correct 0.006 / 0.020; trousers reversed 5.973 / 14.967. Small final gap alone does not prove correct sewing: crossed endpoint constraints can close while destroying garment length.

Same-physical-traversal free controls with the saved default True reproduce the wrong one-long sleeve and trousers results. Applying the EXISTING Session.reverse_seam restores the correct results. Created-wrong-then-reversed and directly-created-correct variants have identical compiled geometry/topology/pair fingerprints, zero diff:

- Sleeve: 3c6d19ae81e62301055d1d9c59010d8bd6661a773e5a29370dc0b2f9c8d9a0ea.
- Trousers: 428f33f73e50cb298fa2631c5196ec5202de7d0f1944ed2eeff4f8257081e0b3.

These are compiled-data fingerprints, not Blender file-byte identities. Round 3 did not repeat native spring-memory readback: its portable diagnostic leaves native rest fields unmeasured, not zero. The completed round 2 native gate still establishes JOIN rest length 0 m and stiffness 1 for all 424 measured springs, with zero preview/compiler/native rest and pair differences. Direction changes endpoints, not that rest-length contract. Full raw distributions/frame metrics are reproducible in scratch/sewing-direction-diagnosis.json; scratch is disposable after review.

## Shipping boundary

This report and diagnostic tooling are round 3's complete deliverable. No application behavior was changed for round 3. The artist separately approved shipping the round 2 build with SHA-256 599d222bd58875f3502250420755f5b02e0b357f7198ee1f19b73f6c6ed65a48. No default-direction fix, duplicate Reverse implementation, release, or tag is included.

Shipping verification on 2026-10-29: 362 headless tests (14 expected Blender-only skips), all 11 configured Blender background suites and all 8 configured GUI suites passed, including 118 viewport-sewing checks. Blender extension validation passed. Rule Zero tokenization/AST checks covered 111 Python files; dead-code checks covered 41 package modules. Publication scan and git diff --check passed. A fresh build reproduced the artist-approved ZIP SHA-256 exactly and all 81 archive entries matched current source bytes. Acceptance message: SHIP IT — the artist approves the Prompt 15 pre-sim sewing preview build from round 2. Packaged-source fingerprint: 19d842630ec1104539ff33270e58aafe047f55cffe63ed1b09eba03774e33526.
