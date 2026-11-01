# Minimal native-Blender presentation verification

## Goal and current status

Make the minimal workspace feel at home in Blender while preserving its brand palette, saved garments, and existing garment behavior. Stop before PR, merge, or release.

The six presentation findings and the compact preview/menu defects are implemented. Full Blender, GUI, package validation, and independent fix reviews pass on the unchanged candidate build. The authorized checkpoint-only sanitization is complete, and the unmodified all-history privacy gate now passes. **Verdict: READY FOR ARTIST TEST.** Artist acceptance remains pending. No PR, merge, or release is authorized by this report.

## Six findings

All dimensions below are logical pixels at UI scale 1. Native references are pinned to Blender 5.2.3, revision `e13b728c6880d3084d9d57c30031ed5df8b39dee`. These are native-proportioned GPU controls, not replacements with Blender UILayout widgets or a claim of pixel-identical rendering.

1. Widths: property cards start at 280px and expand to measured displayed labels, values, icons, and disclosure space. Fabric cards retain a 304px nominal width. Library/save/preview nominal widths are 480/360/420px. These card widths are application layout decisions, not universal Blender constants. MENU rows measure their displayed label and value; sliders measure their formatted visible setting value. The default Fold or pleat row fits its complete value.
2. Library: normal tiles are 168px tall with an 8px column gap, a large undistorted pattern-outline preview, an 11pt garment name, and a 9pt piece/body metadata line. Full saved date and tags remain in the non-destructive preview. Save uses Garment name and Save. Search, tags, pagination, filename sanitization, overwrite confirmation, legacy loading, and body-height refit remain intact. These are flat-pattern thumbnails, not rendered 3D garment photographs.
3. Tool dock: 56px envelope, 40px tool column, 8px centering inset, nominal 35px pitch and 33px target height, and up to 32px artwork. Short layouts adapt the pitch. Idle, hover, active, and open-menu states use the existing brand tokens.
4. Menus: ordinary items are 20px high with 2px gaps, 4px side padding, and a 180px minimum width. Composite labeled choices retain 48px so labels and chips cannot collide. Disclosure appears only for navigation. Layout and drawing share the header/content boundary, so the separator no longer crosses the first item. Contextual actions retain their existing dismissal and dispatch.
5. Icons: generic actions now use the original pinned Blender SVG or toolbar DAT artwork, compiled offline into the existing GPU span format. Original artwork framing is preserved. DAT downloads resolve Blender's Git LFS object, verify size and SHA-256, and reject malformed or pointer-only input. No DAT parsing or network access is added to the running interface.
6. Corners: seven theme roles resolve `0.5 * RNA roundness * 20`, with display scale applied once by the renderer. Factory roundness 0.4 gives 4px; roundness zero gives square corners. Toolbar items, regular buttons, menu backgrounds/items, fields, boxes, and tooltips use their corresponding roles. Minimal shell, labels, dimension callouts, and pending-sew HUD no longer bypass those roles. Canvas and selection rectangles stay square. User preferences are not changed.

## Compact-card root fix

Cards share one size-aware placement rule. Preferred bottom/top clearance is 58/34px when the complete card fits. Otherwise placement uses an 8px viewport inset rather than keeping exclusions that push the card outside its editor. Preview artwork shrinks first, with a 32px minimum; metadata and Load/Back controls are retained. The final rectangle is built from the actual content height, not clamped independently of its children.

Actual Layout heights of 320px and 400px now exercise preview and empty-canvas menu containment, GPU drawing, Load confirmation, Back navigation, retained Fit design, and full-height choice rows. Library browsing uses the same placement helper with its existing compact grid budget. This does not introduce scrolling or promise support for arbitrarily tiny viewports.

## Icon inventory

| Minimal action | Genuine stock artwork |
| --- | --- |
| Select | `ops.generic.select.dat` |
| Rectangle, ellipse, polygon | `ops.gpencil.primitive_box.dat`, `ops.gpencil.primitive_circle.dat`, `ops.gpencil.primitive_polyline.dat` |
| Internal path, knife, lengths | `ops.curve.draw.dat`, `ops.mesh.knife_tool.dat`, `ops.view3d.ruler.dat` |
| Library | `ASSET_MANAGER` |
| Undo, redo | `LOOP_BACK`, `LOOP_FORWARDS` |
| Simulate, pause, Keep/check | `PLAY`, `PAUSE`, `CHECKMARK` |
| Save, close, settings | `FILE_TICK`, `X`, `SETTINGS` |
| Fit design, expand, pin | `ZOOM_SELECTED`, `FULLSCREEN_ENTER`, `PINNED` |
| Disclosure and direction indicators | `DISCLOSURE_TRI_RIGHT`, `TRIA_UP`, `TRIA_DOWN` |
| Snapping and body visibility | `SNAP_ON`, `SNAP_OFF`, `HIDE_OFF`, `HIDE_ON` |

Custom exceptions are SEW needle/thread, DART, GARMENT, and the fit-map F toggle. Blender has no demonstrated equivalent for these garment-domain actions; UV seam, cone, and physics-modifier icons would imply different operations. Tack has no separate asset entry and retains the existing pin/tack presentation. The Kenney MORE asset remains legacy-only, outside the minimal action inventory. The editing caret, shortcut letters, units, and punctuation are text rather than substitute action icons.

## Fresh verification on November 1, 2026

- `python tools/dev.py --test --build --keep-scratch`: exit 0. Mocked headless tests and static integrity pass. All 11 real-Blender background suites and all 10 real-Blender GUI suites pass. Package validation and the full-package/ZIP real-Blender import gate pass. The runner syncs the build to the installed extension directory.
- The GUI reports contain 912 passed checks total. This includes 246 library checks, 230 fast-flow checks with all editor-mode/state draw coverage, and 170 core-workflow checks. The core suite covers the minimal DRAFT/SEW/ARRANGE/SIMULATE/KEEP journey and its required single-piece, sewn, blocker, post-drape, and starter-garment cases.
- Independent Codex `gpt-6.1-sol` fix review: `blender --background --factory-startup --python-exit-code 1 --python scratch/recheck_card_probe.py` reports `CARD_GEOMETRY_CASES=1080 FAILURES=0`. It covers six resolutions, four anchors, normal/error/missing library previews, empty/populated libraries, menus, Save, tags, choosers, and Keep options. No verified findings.
- Independent Antigravity `gemini-3.8-flash-high` real-artifact verification reruns `gui_library` and `gui_fast_flow`: 246/246 and 230/230 pass. It verifies 54 expected ZIP entries, no missing/extra entries, and zero byte mismatches. No source drift or verified defects.
- `python -m tools.check_comments`: 126 Python files, zero comments/docstrings/standalone string expressions under the token/AST gate. `python -m tools.check_dead_code`: 43 package modules pass unused-import, symbol, import, and statically determinable draw-integrity checks. `git diff --check`: exit 0; existing CRLF normalization warnings only.
- Parent inspected fresh library, preview, compact preview, and empty-canvas-menu captures. Save and label captures were also inspected by the independent verifier. User Blender and its unsaved scene remain untouched.
- Palette values are unchanged. Protected garment/meshing/placement/tack-binding files and root README/SPEC have no diff. Existing unrelated dirty changes, including documentation and icon README work, are preserved rather than attributed to this task.

## Authorized checkpoint sanitization and privacy pass

The initial all-history privacy scan found private home-directory paths in older snapshots of `reports/pstack-issue78-trial.md` and `reports/pstack-issue78-evidence.json`. The user explicitly authorized sanitizing only those local T3 checkpoint snapshots while preserving application changes and leaving branches and remotes untouched.

The two report blobs were sanitized by replacing only their literal or JSON-escaped home-directory prefixes with `$HOME`:

- Trial report: `0f5264d36cb50fcbb520f31da01c1d641fb6cf16` becomes `77697c596b513e8eea524b5d56ae5c9865039aab`.
- Evidence report: `913b29467b35005ed5992a126f558a2361745508` becomes `18b039d45934ce421fe6d8c1939eaf2740a948b3`.

An atomic compare-and-swap transaction updates 41 refs exclusively under `refs/t3/orchestration-v2/checkpoints/`. It rewrites 41 checkpoint commits and 11 distinct root trees. Tree-diff assertions permit changes only to the two authorized report paths. All other snapshot bytes and commit messages/metadata are preserved; descendant parent hashes change only to reference the sanitized ancestry. The two private original blobs are no longer reachable from refs. This is not a claim of secure erasure of unreachable Git objects.

- Before/after assertions confirm unchanged working-tree file bytes, index bytes, HEAD, and all non-checkpoint refs, including local branches, remote-tracking refs, tags, and the existing Codex tree ref. No remote operation was performed.
- Repeating the sanitizer produces zero ref updates, zero changed root trees, and zero rewritten commits.
- `tools/check_public.py` remains byte-for-byte unchanged, SHA-256 `9fed8b669a82844154414d2eb77eede02747e75c578e475b1265a00faa47a3fc`.
- Fresh unmodified `python tools/check_public.py`: exit 0, `Publication check passed: 226 source paths, 1093 historical blobs, archives, and public commit identities checked.`
- The 40 explicitly accepted published author identities remain a notice, not a failure. No author identity was rewritten.
- Source/archive equality and the recorded packaged-source fingerprint were rechecked after sanitization. The installable build and application source did not change, so the existing real-Blender verification applies to the exact same bytes.
- Final Rule Zero, dead-code/import/draw-integrity, and diff checks pass. Disposable diagnostics are cleaned through the validated developer runner after review; the installable ZIP and this report are retained.

## Candidate installable build

- Path: `dist/devil_designer-0.11.0.zip`.
- SHA-256: `2b55be79c0f825d2c5e6030e69a9b6f3b5e037ac4ec1eea986de74a120895d9f`.
- Exact source/archive comparison: 54 files, zero differences.
- Packaged-source fingerprint: `cf7d449c5402679e3b418f7726a0529a638019c3c05f1aed41560e14474890bb`.
- Fingerprint construction: SHA-256 over sorted archive-relative path, NUL, and each file's SHA-256 digest.
- No version bump, application commit, branch, PR, merge, or release was created for this task. Only the explicitly authorized local checkpoint objects and refs were rewritten.

## Artist checklist

- Inspect default and long contextual labels, especially Fold or pleat.
- Browse, search, filter, name, save, preview, cancel, and load an older garment.
- In a short editor, verify preview Load/Back and empty-canvas Fit design remain usable.
- Compare dock spacing, stock glyphs, hover/active feedback, menu density, and corners with nearby Blender UI under the artist's own theme.

## Poteto routing

Prior grounding used Codex `gpt-6-luna`. Competing designs used Codex `gpt-6.1-sol` and Antigravity `gemini-3.8-flash-high`; implementation used Gemini Flash High. The resumed fix was applied by the parent Codex agent, reviewed by Codex Sol, and exercised independently by Gemini Flash High. Model the Domain led to shared card placement geometry rather than separate outer clamps. Prove It Works required real Blender geometry/events, original artwork verification, and exact archive/source comparison instead of relying on summaries or mocked tests.

The authorized checkpoint sanitization was performed in-thread by the parent Codex agent. Make Operations Idempotent led to content-addressed replacements, an atomic leased ref transaction, and a second-run no-op check. Prove It Works required preserved working-tree/index/ref assertions and a fresh pass of the unchanged all-history privacy checker.
