# Issue 76 release blocker: editor closes on release, Simulate fails

Date: November 2, 2026. Blender 5.2.3 LTS. Source is `1aeeb79` plus the uncommitted #76 working tree.

## Verdict

No reproduction with only this build installed. All four symptoms reproduce every time when two copies of Devil Designer are loaded at once. That is what the artist's Blender had.

## What the artist's Blender had loaded

A read-only inspection of the artist's running Blender, with nothing changed, found two enabled copies of 0.11.0:

- `bl_ext.blender_org.devil_designer`, installed at 20:04.
- `bl_ext.user_default.devil_designer`, the copy the dev runner syncs. The build was at 19:51.

The two copies are byte-identical. The pattern editor class that was running came from the `blender_org` copy. Both copies had a `capture_updates` scene handler registered. The scene held 10 panel objects for 5 patterns, a `.001` duplicate for every piece. After the artist's latest change, only `user_default` is enabled. The `blender_org` folder is still installed on disk.

## Reproduction

Script: `reports/issue76-release-fix/repro.py`. It drives the real modal editor through `window.event_simulate`, which is a real click, drag and release, not a direct `handle_event` call. It runs (b) attach by click, (a) drag a point, (c) move a panel in 2D, and (d) Simulate.

| Setup | (b) attach | (a) point drag | (c) panel move | (d) Simulate |
| --- | --- | --- | --- | --- |
| One copy, #76 build (`result-single.json`) | stays open | stays open | stays open | runs |
| Two copies, #76 build (`result-double.json`) | **editor closes** | **editor closes** | **editor closes** | **Unexpected error: ReferenceError: StructRNA … has been removed** |
| Two copies, pre-#76 `master` (`result-double-head.json`) | **closes** (on press) | **closes** | **closes** | **same ReferenceError** |
| Two copies, fixed build (`result-double-fixed.json`) | stays open | stays open | stays open | runs |

Exception behind all three closes and the Simulate error:

```
garment.py, build_panels: group.add(list(range(len(mesh.vertices))),1,'REPLACE')
ReferenceError: StructRNA of type Mesh has been removed
```

## Root cause

Each copy has its own module state, its own `_busy` rebuild guard and its own scene-update handler. Each release commits an edit, and the commit rebuilds the live panels. Mid-build, `build_panels` calls `view_layer.update()`. That fires the *other* copy's `capture_updates`. Its `_busy` flag is false, so it starts its own rebuild and replaces the mesh the first build still holds. The first build then touches a freed Mesh, and Python raises `ReferenceError`.

The editor's `modal()` treats `ReferenceError` as "my scene is gone" and calls `cleanup()`, so the editor closes with no message. Simulate goes through the operator error boundary instead, which is why the artist saw the text. It said Object rather than Mesh because a different RNA struct was freed on that path. The cause is the same. The fight between the two copies also left the duplicate `.001` panels.

This is not a #76 regression. Pre-#76 `master` fails the same way under a double install. #76 only moved the attach commit from press to release, which is why every symptom now lands on a release.

Does the multi-version install explain each symptom? Yes for all four. Every one goes through a commit that rebuilds panels, which is the step the two copies fight over. The StructRNA text is the same freed-struct `ReferenceError`, raised on the Simulate path.

## Fix

Kept small. No protected file was touched.

- `devil_designer/__init__.py`. When another copy has already registered the editor, `register()` refuses with "Devil Designer is already enabled from <path>. Two installed copies break the editor and simulation. Disable or remove one copy in Preferences > Get Extensions, then restart Blender." `unregister()` leaves the other copy alone.
- `devil_designer/live_panels.py`, in `sync`. Duplicate panel objects for the same pattern are removed before a rebuild. This repairs scenes the double install already corrupted, like the artist's 10 panels for 5 patterns. It does nothing when there are no duplicates.

## Why the suites missed it

- Every suite runs with `--factory-startup` and imports only the source tree, so two copies were never loaded together.
- The editor suites (`gui_fast_flow`, `gui_core_workflow` and the others) call `workspace.handle_event()` directly from a timer. That skips `modal()`, where a `ReferenceError` silently closes the editor. So a closed editor could never show up as a failure.

## Regression check added

`tests/gui_editor_release.py` is now in the `tools/dev.py` GUI list. In a real Blender it does the following:

- Registers the package, then tries to register a second copy. It asserts the refusal and that only one scene-update handler is installed.
- Seeds a duplicate panel.
- Opens the real modal editor and drives everything through `window.event_simulate`: V for Select, click-release attach, point drag and release, 2D panel drag and release, and the Simulate button.
- After each release, asserts the editor is still open, no exception went through the real modal handler, and no "Unexpected error" is shown. It also asserts each commit landed, one panel per pattern, and that Simulate built the drape.

Against the build without the fix, the suite fails on its first assertion. With the fix it passes 21 checks.

## Fresh gates on the fixed code

`python tools/dev.py --test --build` passes (`reports/issue76-release-fix-gates.txt`). That covers the static and dead-code checks, the mocked unit tests and the 12 Blender background suites. It also covers all 12 GUI suites, including `gui_fast_flow` draw coverage, `gui_core_workflow` and the new `gui_editor_release`. Extension validation and the real-Blender full-package and zip load gate pass too. Also passing are `python -m tools.check_dead_code` (44 modules clean), `python tools/check_public.py`, `git diff --check`, and Rule Zero token and AST checks on 31 changed or new Python files (zero comments, zero standalone strings).

Package: `dist/devil_designer-0.11.0.zip`, SHA-256 `a7c279442043fe11b60043f78078e57a05c1551a0734beaa67a0cdba8f193a87`. The runner synced it to `user_default`.

Protected files: `meshing.py`, `placement.py` and `tack_binding.py` have no diff. `garment.py` keeps only its pre-existing 5-line change. `core.py` keeps only the #76 record change and was not touched in this fix.

## Artist action needed

Remove the `blender_org` copy of Devil Designer (Preferences > Get Extensions > Devil Designer under the Blender Extensions repository > Uninstall), then restart Blender. The fix stops a second copy from running, but it cannot uninstall one.
