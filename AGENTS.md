# DEVIL DESIGNER — AGENT GUIDELINES

## RULE ZERO: ZERO COMMENTS OR DOCSTRINGS IN CODE
- **Zero means zero: comments, docstrings, and comment-like standalone strings are strictly forbidden in code. There is no docstring exception.**
- Do not add or retain line, inline, or block comments in any language, including `# ...`, `// ...`, `/* ... */`, HTML comments, PowerShell block comments, or batch `REM`/`::` comments.
- Python module, class, function, and method docstrings are forbidden, whether written with `"""..."""`, `'''...'''`, ordinary single/double quotes, raw strings, or another string-literal spelling.
- Standalone string expressions used as notes, headings, explanations, disabled code, or pseudo-comments are also forbidden, regardless of quoting style. Do not replace a removed comment with a string literal.
- This applies to application source, tests, developer tools, launch scripts, and generated code. Existing comments and docstrings must be removed when encountered; never preserve them merely because they predate this rule.
- Keep explanations, usage instructions, and design rationale in Markdown documentation such as `README.md`, `SPEC.md`, or `AGENTS.md`, not inside code. Use descriptive names and straightforward structure to make code self-documenting.
- Actual program data is not a comment: preserve strings that are assigned, returned, passed to functions, or otherwise used by the program, including UI labels, error messages, templates, and generated-script contents. Inspect their purpose instead of blindly deleting every triple-quoted string. Generated-script contents must themselves obey this rule.
- When removing a docstring or comment would leave an empty required code block, retain valid syntax with `pass`; do not change behavior or protected garment/simulation algorithms.
- Verify Python with both tokenization and AST inspection: reject every `COMMENT` token and every standalone string-expression node, including all docstrings. Tokenization alone is insufficient because Python treats docstrings as strings, not comment tokens. Apply equivalent comment checks to other code languages and generated code, then verify syntax and run the required tests. Do not claim zero comments based only on a `#` search or tokenizer scan.

## RULE ZERO-B: ZERO DEAD CODE AND ZERO UNUSED IMPORTS
- **Dead code and unused imports are strictly forbidden across the codebase.**
- Every import statement must be actively used in the importing file. Never leave unused symbols in `import` or `from ... import ...` statements.
- Every module-level definition (constant, variable, function, class, or dataclass) must be actively referenced in the project or explicitly exported for Blender extension lifecycle registration (`bl_info`, registered scene operators/properties).
- No speculative, abandoned, or placeholder UI component classes, layouts, or renderers. When an architecture or workflow is consolidated (such as consolidating on the minimal workspace), all superseded code, layouts, and helpers must be removed immediately rather than left behind.
- **Import integrity**: every name imported from a project module must exist in that module. A token or constant is defined in its home module before anything references it.
- **Load gate**: no build is verified, ready, or done unless the packaged extension imports cleanly in a real Blender — every module, no mocks. Mocked headless tests never count as evidence for import or GUI-path correctness. Reports list real-Blender checks separately from mocked checks.
- **Draw-path integrity**: code in any draw handler may only access attributes and dict keys that verifiably exist on the target object/dict as defined in this codebase. Referencing an attribute or key that is not defined on its target type is a build-blocking defect, on the same level as a bad import. Extend the static checks to cover attribute accesses on the add-on's own classes and known dict shapes wherever statically determinable; where a case cannot be determined statically, the GUI draw coverage rule below is the enforcement.
- **Draw coverage gate**: no build is verified, ready, or done unless the real-Blender GUI suite exercises the draw path of EVERY editor mode and state (Select, Draw, Internal, Sew including a pending sew selection, Pin, Library, arranged 3D, active gestures such as box-select) against representative session content and asserts that no render error occurs. A mode or state without draw coverage blocks the build from being reported ready — the same standing as the load gate.
- **Core workflow end-to-end gate**: no build is verified, ready, or done unless the real-Blender GUI test suite exercises the complete user journey (`DRAFT` -> `SEW` -> `ARRANGE` -> `SIMULATE` -> `KEEP`) end-to-end through the active minimal UI (`DEVIL_DESIGNER_OT_pattern_editor` with `minimal_ui=True`) and the `devil_designer.keep_drape` operator on real 3D geometry without mocked scene properties. Verification must explicitly cover Keep mesh across fundamental scenario classes: (a) single pattern piece with zero seams, (b) multi-piece sewn garments, (c) pre-arrangement/pre-simulation Keep invocation blocker assertions, (d) post-drape simulation mesh extraction, and (e) starter garments (Fitted Tee, Tank, Skirt) taken through drape and final mesh finalization. Calling internal backend functions like `garment.keep_drape()` directly does not satisfy this gate.
- Automated enforcement: `python -m tools.check_dead_code` checks all package modules for unused imports, missing cross-module imports, unreferenced module-level definitions, and statically determinable draw-path attribute/key integrity (`check_draw_integrity`), while `tests/blender_smoke.py` imports every module of the package in real Blender with zero mocks, `tests/gui_fast_flow.py` exercises the draw path in real Blender across every editor mode and state, and `tests/gui_core_workflow.py` exercises the core workflow end-to-end through the minimal UI. All are enforced during extension packaging and verification (`tools/build.py`, `tools/dev.py`, and `tests/test_dead_code.py`).

---

## ARTIST-FACING ANSWERS AND FEATURE REVIEWS
- Lead with the recommendation and the artist benefit, not implementation details. Use plain, concise language by default.
- For feature reviews, use "Add [feature] because [practical artist benefit]", "Do not add [feature] because [reason]", or "Prototype [feature] first because [uncertainty]". Explain whether the feature removes a real obstacle when making fitted VRChat clothing in Blender.
- Include technical details only when they are necessary to understand the recommendation, a meaningful limitation, or a decision the artist needs to make. Do not default to source paths, function names, plumbing, or implementation walkthroughs.
- Keep build priorities distinct from deferred conveniences and rejected features. Do not turn a review request into authorization to implement features.
- Still verify claims against the source and report uncertainty honestly; concise answers must not hide important risks or imply an untested feature works.
- Keep shipping reports brief while retaining the required verification, package, merge, and cleanup facts. Documentation-only changes do not require an artificial artist test.

## ARCHITECTURE & IMPLEMENTATION PRINCIPLES
1. **Garment & Simulation Math Integrity**:
   - Initial built-panel position and orientation in garment.build_panels and arrangement.arrange are editable, and arrangement.py may implement bounding volumes and arrangement points; placement.py, tack_binding.py, cloth setup/loop/modifiers, meshing output, and sewing springs remain locked.
   - Strictly locked and protected: simulation algorithms and cloth loop/modifiers in `garment.py`, meshing output and Delaunay CDT math in `meshing.py`, sewing spring force formulations in `garment.py`, and 3D placement math in `placement.py` and `tack_binding.py`.
   - Now editable: the pattern-editing code in `core.py` and `construction.py` (specifically pattern selection state, multi-piece and point selection, point and handle movement and editing, segment splitting, and internal/boundary path cutting). Downstream simulation, meshing output, sewing springs, and placement math must remain untouched and verified by automated meshing regression tests.
2. **UI & Rendering Architecture**:
   - Blender native GPU rendering (`gpu.shader.from_builtin('UNIFORM_COLOR')`, `POLYLINE_UNIFORM_COLOR`).
   - Shared computed bounds for rendering and hit detection.
   - Minimalist Apple-inspired design language with cohesive tokens (`ui_system.py`).
3. **UX & Workflow Priority**:
   - Prioritize user flow and time-to-first-garment.
   - Maintain guided stage flow (`DRAFT` -> `SEW` -> `ARRANGE` -> `SIMULATE` -> `KEEP`).
   - Keep empty states actionable with one-click creation templates.
   - Provide real-time feedback during sewing and authoring to prevent user errors before they happen.

---

## MINIMAL CONTEXTUAL UX CONTRACT
- Zero sidebars and zero docked inspectors: 100% full-screen canvas from the left dock to the right window edge.
- Eliminates split-attention friction: the artist interacts directly where their cursor is positioned.
- Pure canvas interaction: left-clicking or selecting any piece, seam badge, point, edge, or internal path highlights it cleanly without auto-opening popovers or card overlays.
- Focused Right-Click Contextual Menus: right-clicking any entity opens a compact, contextual menu directly anchored at the cursor:
  1. Piece right-click: piece dimensions, Fabric override submenu (Cotton, Linen, Denim, Silk, Leather, Knit), Mesh density override submenu (Coarse, Standard, Fine), Duplicate, Mirror, Unfold, Delete piece.
  2. Seam badge right-click: length mismatch stats (cm & %), Reverse seam, Remove seam.
  3. Point right-click: corner/curve toggle, exact numeric X/Y coordinate sliders, Merge selected points (when multiple points selected).
  4. Edge right-click: exact length slider, Split edge, Unfold, Mirror.
  5. Internal edge right-click: exact length slider, Split edge, Cut along path, Trace as piece (for closed paths).
  6. Pin/Tack right-click: attached pattern name, Remove tack / Remove pin.
  7. Empty canvas right-click: Body selector submenu, Garment default fabric chips, Garment mesh density chips, Simulation quality chips, Guide opacity chips, Fit design.
- Quick auto-dismissal: executing any action in a contextual menu immediately completes the action and dismisses the menu back to pure canvas. Pressing Escape or clicking outside also instantly dismisses the menu.
- Reduced left dock: 8 tools (Select, Draw, Internal, Sew, Pin, Undo, Redo, Library) with micro-toggles for Snapping [S], Body guide [H], and Lengths [L]. Shortcuts P, R, E, I, D, K, T, V, J, S, H, L remain fully functional.
- Keep mesh retains its options menu (Auto weld and Thickness). Simulate directly starts drape.

## REQUIRED ARTIST ACCEPTANCE AND SHIPPING WORKFLOW
- The required sequence is: implement -> automated verification -> ready for artist testing -> artist approval -> PR and merge -> verified session closure. Do not replace artist acceptance with automated tests or agent reviews.
- Before handing off for artist testing, finish the requested work, run all nine suites and Blender package validation, verify Rule Zero, and prepare the exact installable build. State what changed, give a short focused test checklist and the build location, and explicitly ask the user to test it. Stop and wait at this acceptance gate; do not open or merge a PR while the build is still awaiting artist acceptance.
- Use this handoff wording or its clear equivalent: "Ready for your test. Please test this build. If it passes, reply PR or ship it; I will run the final checks, create or update the PR, merge it into master, and close the session."
- After that test handoff, the user's standalone "PR", "ship it", "go ahead", "looks good, ship", or equivalent instruction is both artist acceptance of the handed-off build and authorization to complete the entire commit/push/PR/merge workflow. Do not require a separate "approved", a second merge command, or a second manual test. If the user reports a problem or says testing is incomplete, acceptance has not been granted.
- Honor narrower instructions such as "draft PR only", "do not merge", "wait", or "do not push". A mention or quotation of these commands while discussing the rules is not a shipping instruction. If no ready-for-test handoff or prior confirmed artist test exists, ask for that one acceptance step instead of assuming an untested build is approved.
- Record the accepted source commit or source-tree fingerprint, the tested package checksum, and the acceptance message in the thread or PR. Preserve this acceptance across resumed sessions. Deterministic rebuilds, automated checks, PR creation, merges that do not change behavior, and documentation-only or test-only changes do not require the artist to repeat the same manual test.
- If a later fix or conflict resolution changes artist-visible behavior from the accepted build, explain exactly what changed and request only the affected manual checks. Do not request a complete repeat of unaffected testing. Never silently apply acceptance to materially different behavior.
- Once shipping is authorized, execute without another permission round: inspect current status and branch ancestry; preserve unrelated work; run `python tools/dev.py --test --build`, `python tools/check_public.py`, `python -m tools.check_dead_code`, `git diff --check`, Rule Zero token/AST checks, and equivalent checks for other code and generated scripts; verify the package matches the source; commit and push the verified task changes; create or update the PR targeting `master`; and register the PR with the session when supported.
- Require all nine suites, Blender package validation, required remote checks, and required reviews to pass on the exact source being merged. Resolve actionable review findings and conflicts without bypassing protections. Reverify after changes and apply the acceptance rule above if behavior changes. Never force-push or overwrite unrelated work merely to finish shipping.
- Merge the verified PR into `master` as part of the authorized workflow; do not stop at "PR ready" and ask the user to merge it manually. Verify the remote merge, safely synchronize local `master`, and rerun the required tests, build, privacy, and Rule Zero checks against the resulting `master`. Confirm remote checks are green and the final package matches that source.
- Clean disposable scratch through the validated developer runner after diagnostics and reviews are resolved; preserve `dist/`, required fixtures, and user projects.
- After the merge and post-merge checks pass, audit all local branches, branches on the repository's owned remotes, and registered repository-owned worktrees, not just this session's task branch. Refresh remote references and inspect current tips, ancestry, PR state, worktree status, active sessions, and branch/PR dependents before deciding which candidates are unused. Do not treat a branch as disposable merely because it is old or has a familiar name.
- Delete confirmed unused, integrated task branches locally and remotely, and clean unused repository-owned worktrees, as part of the authorized shipping workflow without another cleanup permission round. Verify that every candidate's current commits are integrated into remote `master`; for squash/rebase merges, verify equivalent integrated changes and the corresponding PR history instead of assuming ancestry. Recheck the remote tip before deleting a remote branch; preserve it if it moved or cannot be verified safely.
- Never remove `master`, the default branch, protected/release/long-lived branches, active sessions' branches or worktrees, branches supporting an open PR or dependent stack, unmerged work, dirty worktrees, user projects, or uncertain candidates. A branch containing unmerged work requires separate explicit discard authorization, even if it appears abandoned. Preserve unrelated work and any candidate whose ownership, integration, cleanliness, or lack of dependents cannot be established.
- Verify each worktree removal target against Git's registered absolute paths and repository ownership before removal. Use normal Git branch/worktree removal, never forced deletion or recursive shell deletion to bypass safeguards. If normal removal refuses, preserve the candidate and report why. Audit and prune obsolete remote-tracking references separately; pruning a tracking reference is not deletion of an actual remote branch.
- Complete and report this cleanup audit before closing the session. List the local branches, remote branches, and worktrees removed, plus every retained cleanup candidate and its reason; report "none eligible" when appropriate rather than skipping the audit or claiming everything was deleted.
- Close the session only after the merge and post-merge verification succeed: report the merge commit, local/remote `master` synchronization, checks, package, cleanup, and any preserved branches. When the session platform supports settlement, mark the session settled after that report. If blocked by failing checks, permissions, required reviews, or changed behavior needing acceptance, keep the session open and report the precise blocker; do not claim shipment is complete.
- The final shipping report is a completion report, not a new testing assignment. Do not append "restart and test again", "manual testing pending", "please merge", or another approval request for the unchanged build the artist already accepted.
- "PR" or "ship it" means complete the tested changes through merge and session closure. It does not by itself request a version bump, tag, or public GitHub release; the separate release checklist applies only when a release is explicitly requested.
- Changes that only correct workflow rules or documentation do not need an artificial Blender/manual artist acceptance test. Validate those changes appropriately, preserve the existing accepted application build, and do not claim that editing a rule has itself authorized publication or merging.

## DEVELOPER WORKFLOW SHORTCUTS
Run the unified developer runner from the repository root:
- `.\\dev.cmd --quick`: Fast headless unit tests (includes dead code, unused import, and rule checks)
- `.\\dev.cmd --test`: Complete verification across all 9 test suites
- `.\\dev.cmd --build`: Packages extension ZIP in `dist/`, validates it with Blender, and syncs to user addons
- `.\\dev.cmd --shots`: Clean, unobstructed in-engine stage screenshots (~14s)
- `.\\dev.cmd --inspect`: Slices and validates UI contrast and layout bounds
- `.\\dev.cmd --all`: Full end-to-end test, build, screenshot, and inspect pass
- `.\\dev.cmd --keep-scratch`: Combine with a task to retain artifacts for manual review
- `.\\dev.cmd --clean`: Delete only the disposable scratch workspace after review

All test suites must pass 100% with no regressions on every change.

## DISPOSABLE ARTIFACT CONTRACT
- Keep installable deliverables in `dist/`; never auto-delete that directory.
- Put every disposable development artifact in ignored `scratch/`: screenshots, crops, test scenes/backups, reports, generated scripts, preview logs, downloads, temporary dependencies, and test libraries. Never use the repository root, source folders, or `dist/` as a dumping ground.
- Use the developer runner and disable bytecode generation for development subprocesses; do not recreate scattered `__pycache__` directories.
- Successful runner tasks delete scratch automatically after all requested steps finish. Failed runs preserve diagnostic artifacts. Use `--keep-scratch` for visual audits and `--clean` immediately after review is complete.
- Cleanup must validate its repository-local target and refuse links/junctions. Never delete source, required assets/licenses, installable ZIPs, or user projects, and never silently discard an unsaved scene to unlock a file.
- Before handing off finished work, verify the installable ZIP still exists and scratch has been removed unless diagnostics or an explicitly requested review are still pending.

## WORKING REPORTS AND REPOSITORY ROOT
- Working reports (session reports, benchmarks, diagnoses, verification logs, audits) never live in the repository root — they go in a new top-level folder named `reports/`.
- The repository root is reserved strictly for product and project configuration files (`README.md`, `SPEC.md`, `LICENSE`, `AGENTS.md`, and top-level runner scripts). Never place working reports or diagnostic writeups in the root directory.

## REQUIRED RELEASE CHECKLIST
Follow this sequence whenever the user requests a release:
1. Inspect Git status, remotes, branch ancestry, manifest version, tags, and existing GitHub releases. Preserve current work and never release an older commit in its place.
2. Audit unused prototypes, screenshots, old Blender scenes/backups, logs, downloaded archives, caches, and temporary files. Remove confirmed leftovers only inside the repository; preserve runtime assets, provenance, licenses, tests, and required fixtures. Never touch user projects outside the repository or bypass blocked operations.
3. Check current source, publication archives, and reachable Git history for personal paths, identities, and credentials with `python tools/check_public.py`. Keep generated files and machine settings ignored. Never print secrets or claim a complete privacy purge from a targeted scan; report its scope and any remaining findings. Do not rewrite history without explicit authorization.
4. Run `python tools/dev.py --test --build`, `python tools/check_public.py`, `python -m tools.check_dead_code`, and `git diff --check`. Require every suite and Blender package validation to pass. Verify Rule Zero with comment-token and AST standalone-string/docstring checks, not tokenization alone. Confirm archive contents match the exact source being released, with no private or generated artifacts.
5. With user authorization, commit and push the verified current source. Ensure the intended release branch contains that commit without force-pushing or overwriting unrelated work. Tag the exact source commit matching the package; never publish uncommitted changes against a stale source tag.
6. Publish the manifest version as a GitHub release with accurate release notes, the installable extension ZIP from `dist/`, and its SHA-256 checksum. Upload only deliberate public release assets, never scratch, local scenes, screenshots, or test reports. Delete scratch after verification is complete.
7. Verify the remote commit, tag, release status, downloadable assets, checksums, and final working-tree status. Report the release URL, validation results, cleanup performed, privacy scan scope, and any remaining blockers. Never mark incomplete cleanup or publication complete.
