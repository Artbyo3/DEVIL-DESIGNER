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
   - Zero modifications to garment algorithms, physics equations, or simulation math in `core.py`, `garment.py`, `meshing.py`, `placement.py`.
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
- Only the approved compact, optional Workspace side card is allowed; do not restore a full-height sidebar, searchable all-settings inspector, or universal cursor menu.
- Workspace exposes existing artist-facing preferences only: snapping, measurements, body-guide visibility/opacity, and Fit design. Keep the rest of the UI unchanged when extending this card.
- Show only controls relevant to the current piece, seam, garment, or task button.
- Keep popovers at approximately five controls; prefer named choices. The fabric preset list contains six named materials.
- Fabric presets own physical parameters. Do not expose raw cloth parameters, self-collision, body-clearance, body-height refit, or auto-quality toggles.
- Simulation choices live on Simulate. Finalization choices live on Keep mesh. Seam reverse/removal lives on the seam badge.
- Weld is Auto; expose manual tolerance only after an actual unwelded-seam report.

## REQUIRED ARTIST ACCEPTANCE AND SHIPPING WORKFLOW
- The required sequence is: implement -> automated verification -> ready for artist testing -> artist approval -> PR and merge -> verified session closure. Do not replace artist acceptance with automated tests or agent reviews.
- Before handing off for artist testing, finish the requested work, run all nine suites and Blender package validation, verify Rule Zero, and prepare the exact installable build. State what changed, give a short focused test checklist and the build location, and explicitly ask the user to test it. Stop and wait at this acceptance gate; do not open or merge a PR while the build is still awaiting artist acceptance.
- Use this handoff wording or its clear equivalent: "Ready for your test. Please test this build. If it passes, reply PR or ship it; I will run the final checks, create or update the PR, merge it into master, and close the session."
- After that test handoff, the user's standalone "PR", "ship it", "go ahead", "looks good, ship", or equivalent instruction is both artist acceptance of the handed-off build and authorization to complete the entire commit/push/PR/merge workflow. Do not require a separate "approved", a second merge command, or a second manual test. If the user reports a problem or says testing is incomplete, acceptance has not been granted.
- Honor narrower instructions such as "draft PR only", "do not merge", "wait", or "do not push". A mention or quotation of these commands while discussing the rules is not a shipping instruction. If no ready-for-test handoff or prior confirmed artist test exists, ask for that one acceptance step instead of assuming an untested build is approved.
- Record the accepted source commit or source-tree fingerprint, the tested package checksum, and the acceptance message in the thread or PR. Preserve this acceptance across resumed sessions. Deterministic rebuilds, automated checks, PR creation, merges that do not change behavior, and documentation-only or test-only changes do not require the artist to repeat the same manual test.
- If a later fix or conflict resolution changes artist-visible behavior from the accepted build, explain exactly what changed and request only the affected manual checks. Do not request a complete repeat of unaffected testing. Never silently apply acceptance to materially different behavior.
- Once shipping is authorized, execute without another permission round: inspect current status and branch ancestry; preserve unrelated work; run `python tools/dev.py --test --build`, `python tools/check_public.py`, `git diff --check`, Rule Zero token/AST checks, and equivalent checks for other code and generated scripts; verify the package matches the source; commit and push the verified task changes; create or update the PR targeting `master`; and register the PR with the session when supported.
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
- `.\dev.cmd --quick`: Fast headless unit tests
- `.\dev.cmd --test`: Complete verification across all 9 test suites
- `.\dev.cmd --build`: Packages extension ZIP in `dist/`, validates it with Blender, and syncs to user addons
- `.\dev.cmd --shots`: Clean, unobstructed in-engine stage screenshots (~14s)
- `.\dev.cmd --inspect`: Slices and validates UI contrast and layout bounds
- `.\dev.cmd --all`: Full end-to-end test, build, screenshot, and inspect pass
- `.\dev.cmd --keep-scratch`: Combine with a task to retain artifacts for manual review
- `.\dev.cmd --clean`: Delete only the disposable scratch workspace after review

All test suites must pass 100% with no regressions on every change.

## DISPOSABLE ARTIFACT CONTRACT
- Keep installable deliverables in `dist/`; never auto-delete that directory.
- Put every disposable development artifact in ignored `scratch/`: screenshots, crops, test scenes/backups, reports, generated scripts, preview logs, downloads, temporary dependencies, and test libraries. Never use the repository root, source folders, or `dist/` as a dumping ground.
- Use the developer runner and disable bytecode generation for development subprocesses; do not recreate scattered `__pycache__` directories.
- Successful runner tasks delete scratch automatically after all requested steps finish. Failed runs preserve diagnostic artifacts. Use `--keep-scratch` for visual audits and `--clean` immediately after review is complete.
- Cleanup must validate its repository-local target and refuse links/junctions. Never delete source, required assets/licenses, installable ZIPs, or user projects, and never silently discard an unsaved scene to unlock a file.
- Before handing off finished work, verify the installable ZIP still exists and scratch has been removed unless diagnostics or an explicitly requested review are still pending.

## REQUIRED RELEASE CHECKLIST
Follow this sequence whenever the user requests a release:
1. Inspect Git status, remotes, branch ancestry, manifest version, tags, and existing GitHub releases. Preserve current work and never release an older commit in its place.
2. Audit unused prototypes, screenshots, old Blender scenes/backups, logs, downloaded archives, caches, and temporary files. Remove confirmed leftovers only inside the repository; preserve runtime assets, provenance, licenses, tests, and required fixtures. Never touch user projects outside the repository or bypass blocked operations.
3. Check current source, publication archives, and reachable Git history for personal paths, identities, and credentials with `python tools/check_public.py`. Keep generated files and machine settings ignored. Never print secrets or claim a complete privacy purge from a targeted scan; report its scope and any remaining findings. Do not rewrite history without explicit authorization.
4. Run `python tools/dev.py --test --build`, `python tools/check_public.py`, and `git diff --check`. Require every suite and Blender package validation to pass. Verify Rule Zero with comment-token and AST standalone-string/docstring checks, not tokenization alone. Confirm archive contents match the exact source being released, with no private or generated artifacts.
5. With user authorization, commit and push the verified current source. Ensure the intended release branch contains that commit without force-pushing or overwriting unrelated work. Tag the exact source commit matching the package; never publish uncommitted changes against a stale source tag.
6. Publish the manifest version as a GitHub release with accurate release notes, the installable extension ZIP from `dist/`, and its SHA-256 checksum. Upload only deliberate public release assets, never scratch, local scenes, screenshots, or test reports. Delete scratch after verification is complete.
7. Verify the remote commit, tag, release status, downloadable assets, checksums, and final working-tree status. Report the release URL, validation results, cleanup performed, privacy scan scope, and any remaining blockers. Never mark incomplete cleanup or publication complete.
