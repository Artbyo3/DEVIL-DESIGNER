# DEVIL DESIGNER — AGENT GUIDELINES

## STRICT CODEBASE RULE: NO CODE COMMENTS
- **Comments in the code are strictly forbidden.**
- Do not write any inline (`# ...`) or block comments in any code files (`.py`, `.js`, `.sh`, `.cmd`, `.ps1`).
- Write clean, self-documenting code with descriptive function, variable, and class names.
- If existing comments are encountered anywhere in the codebase, remove them.

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
- `.\dev.cmd --quick`: Fast headless unit tests (56 tests in ~0.15s)
- `.\dev.cmd --test`: Complete verification across all 8 test suites (~21s)
- `.\dev.cmd --build`: Packages extension zip, validates package with Blender, and syncs to user addons (~0.7s)
- `.\dev.cmd --shots`: Clean, unobstructed in-engine stage screenshots (~14s)
- `.\dev.cmd --inspect`: Slices and validates UI contrast and layout bounds
- `.\dev.cmd --all`: Full end-to-end test, build, screenshot, and inspect pass

All test suites must pass 100% with no regressions on every change.

## REQUIRED RELEASE CHECKLIST
Follow this sequence whenever the user requests a release:
1. Inspect Git status, remotes, branch ancestry, manifest version, tags, and existing GitHub releases. Preserve current work and never release an older commit in its place.
2. Audit unused prototypes, screenshots, old Blender scenes/backups, logs, downloaded archives, caches, and temporary files. Remove confirmed leftovers only inside the repository; preserve runtime assets, provenance, licenses, tests, and required fixtures. Never touch user projects outside the repository or bypass blocked operations.
3. Check current source, publication archives, and reachable Git history for personal paths, identities, and credentials with `python tools/check_public.py`. Keep generated files and machine settings ignored. Never print secrets or claim a complete privacy purge from a targeted scan; report its scope and any remaining findings. Do not rewrite history without explicit authorization.
4. Run `python tools/dev.py --test --build`, `python tools/check_public.py`, and `git diff --check`. Require every suite and Blender package validation to pass. Confirm there are no code comments and that archive contents match the exact source being released, with no private or generated artifacts.
5. With user authorization, commit and push the verified current source. Ensure the intended release branch contains that commit without force-pushing or overwriting unrelated work. Tag the exact source commit matching the package; never publish uncommitted changes against a stale source tag.
6. Publish the manifest version as a GitHub release with accurate release notes, the installable extension ZIP, and its SHA-256 checksum. Upload only deliberate public release assets, not the build directory, local scenes, screenshots, or test reports.
7. Verify the remote commit, tag, release status, downloadable assets, checksums, and final working-tree status. Report the release URL, validation results, cleanup performed, privacy scan scope, and any remaining blockers. Never mark incomplete cleanup or publication complete.
