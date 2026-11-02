# Settled-drape shaping iteration base

## Shipping scope

Merge the verified settled-drape shaping tool as an iteration base. This is not a release. The extension version remains 0.11.0. Issue #45 remains OPEN.

The tool is in the dock, with Pull, Push, radius and Reset controls attached to it. It preserves the 2D canvas and uses open-hand and closed-grip cursors. Keep validates both the evaluated source and the provisional final mesh before hiding the source.

Shaping during a running simulation does not yet hold. The matched live experiment accepted a +2.500 mm Pull stroke but retained -0.478270 mm after 120 released frames. The live limitation is proven, not an untested promise. Tangential pinch, fine-wrinkle dragging and shaping with active tacks remain unsupported.

## Settled retention evidence

Blender 5.2.3 LTS, native cloth, production garment, matched zero-stroke control, 240 released frames:

| Metric | Pull | Push | Zero control |
| --- | ---: | ---: | ---: |
| Accepted input | +6 mm | -12 mm | 0 mm |
| Signed retained center displacement | +2.174776 mm | -15.700252 mm | Reference |
| Maximum draped-edge ratio | 1.014356649 | 1.031107397 | 1.014556598 |
| Maximum original-fabric edge ratio | 1.050821918 | 1.049888708 | 1.051153983 |
| Maximum late-window motion | 0.437958 mm/frame | 0.394783 mm/frame | 0.434532 mm/frame |

The draped-edge limit is 1.053 and the late-motion limit is 0.63 mm/frame. These are settled-path results, not live-retention results.

## Containment diagnosis and correction

The original stage-15 refusal was a false positive. The tested torso vertex was 9.328351 mm outside the collider, with no penetration or triangle overlap. A shallow ray re-hit the same triangle after advancing its origin.

Increasing that advance and taking a majority was rejected. It stepped over a narrow concave slot and let Keep bake an enclosed patch 0.100016594 mm inside a watertight collider.

The replacement counts all triangle crossings from a fixed origin using double-precision scalar arithmetic. It retries a direction when an intersection is ambiguous at a triangle edge. It never advances the origin and never uses a majority vote. If all directions are ambiguous, clearance is refused.

Permanent regressions cover the original exterior torso point, an interior torso point, concave slots of 10 and 1 micrometres, and the registered Keep refusal. The refused Keep creates no final mesh and leaves the simulation visible. Existing stage-15 GUI assertions are unchanged.

Independent native verification passed all 96 adversarial cases plus 32 tiny/reflected cases. The enclosed patch's three vertices are classified inside even though triangle overlaps are empty. The original torso exterior point is classified outside.

## Verification contract

The merge requires the full developer runner, including all existing suites and the added settled shaping suites: 12 native background suites, 11 native GUI suites, static and mocked tests, extension validation and the real-Blender package/ZIP load gate. GUI coverage includes every editor draw state and the complete minimal-UI garment workflow. The settled shaping GUI suite passes 197 checks through registered Keep at stage 15.

Reopened Keep coverage retains all four refusals: closed collider containment, transformed collider containment, open-surface intersection and final-thickness intersection. Safe Keep succeeds after removing the obstacle. The final-thickness obstacle was corrected to intersect the actual solidified shell while leaving the unthickened source clear; the guard itself is not bypassed.

Rule Zero uses both comment-token and AST standalone-string checks. Dead-code checking includes import and draw integrity across 44 package modules. Privacy checks cover current source, ZIP members, reachable historical blobs and commit identities. No artist-profile installation is performed.

## Exclusions

- The experimental live cold-user suite `tests/gui_cloth_shaping_cold.py` and its matched-control helper `tests/blender_cloth_shaping_gui_control.py` are excluded from this settled merge. They were not existing master suites. Their failed live-retention evidence is preserved locally, not presented as a passing production gate.
- Live release-handoff, rest-blending and bounded-grab prototypes are excluded. No experimental live physics change is included.
- Earlier working reports, captured scenes, raw diagnostic outputs and local absolute paths are not committed. This report records the public results.
- No meshing, sewing-force, placement or tack-binding algorithm changes are included. No docs-site edits, version bump, release, tag or artist-profile installation is included.

## Checkpoint privacy scope

Only private checkpoint copies were sanitized: `reports/dual-engine-xpbd-evidence.json`, `reports/dual-engine-xpbd-spike.md`, and the separately authorized `tools/patch_diag.py`. Other checkpoint content and commit metadata were preserved. No public Git history or master content was rewritten. Unreachable original objects were not erased, so this is not a claim of a complete privacy purge.

## Acceptance

The user explicitly approved merging this settled iteration base with the live-retention limitation disclosed and issue #45 left open. The containment correction is within the approved shaping/Keep safety scope. The tested package checksum and exact source commit are recorded in the PR and final shipping report.
