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
