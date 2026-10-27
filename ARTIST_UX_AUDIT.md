# Artist workflow audit

## Scope

This pass eliminates the docked inspector in favor of 100% full-screen canvas
and focused right-click contextual menus anchored at the cursor. Selecting anything
never opens an overlay on the canvas. Right-clicking a piece, seam, point, edge, internal
path, pin/tack, or empty canvas opens a small focused contextual menu that dismisses
immediately upon selecting an action or pressing Escape/clicking outside. The protected
garment, meshing, placement, and physics algorithms are unchanged.

## Findings addressed

| Issue | Artist impact | Implemented behavior |
| --- | --- | --- |
| Point selections leaked across pieces and paths on right-click | Merge could modify corners the artist never selected on the new piece | Selection is scoped to the clicked piece and path; intentional same-group selections remain intact |
| Delete on a seam badge depended on the current tool | Delete could remove the selected garment piece instead of its seam | The selected seam takes precedence; B reverses it and Delete removes it without deleting pieces |
| Delete piece reused selection-sensitive deletion | A corner or internal path could disappear while the piece remained | The piece card has an explicit whole-piece action, with one-step undo |
| Shortcuts could mutate selection during an active drag | Shift+D could redirect a pending move or handle edit onto a duplicate | Conflicting actions wait until the current drag finishes or is cancelled |
| Numeric geometry failures looked successful | Invalid edits dismissed input and could leave displayed values inconsistent with source | Failed typed edits retain input and the actual error; rejected drags restore source values without adding undo entries |
| Escape left chain picks or Bezier previews behind | Cancelled work could influence a later operation or remain visible | Cancellation clears pending chains, ranges, darts, edges, and handle previews as appropriate |
| External document replacement retained old interaction state | Pending edits, picks, cards, or destructive confirmations could reference the wrong garment | Source reload clears document-specific interaction state before continuing |
| Library metadata was incompletely validated before building | Corrupt settings or placements could fail after scene mutation | Root, name, body height, placement references, supported setting types/ranges, and UTF-8 are validated before building; assignment/build errors restore imported scene values |
| Library replacement applied defaults before confirmation | Choosing Go back could still change the current garment settings | Opening and cancelling replacement leaves existing settings unchanged |
| Empty-state help was obscured by contextual cards and lacked one-click creation | New artists had to infer how to start | A three-choice Start garment card creates a 40 x 45 cm editable panel, offers custom drawing, or opens the library; obscured duplicate canvas instructions are hidden |

Regression checks cover these cases in `tests/gui_fast_flow.py` and
`tests/blender_advanced.py`, alongside the existing nine verification suites.

## Artist acceptance pass

1. Restart Blender to unload the previous extension modules, then open Devil
   Designer with Ctrl+Alt+D. Verify the pure full-width canvas with zero sidebars,
   the reduced left tool dock (8 tools + S/H/L toggles), and that selecting pieces
   never creates an overlay on the canvas. Right-click empty canvas to inspect Garment & View options,
   and right-click pieces/seams/points to access contextual actions directly at your cursor.
2. Shift-select two corners on one panel, then right-click a corner on the other.
   Merge must not reuse the first panel's selection. Repeat between the outer
   boundary and an internal path.
3. Sew a pair, switch to Select, and click its seam badge. B should reverse the
   seam; Delete should remove only the seam. Undo should restore it.
4. Select a corner or internal path, open Edit piece, and choose Delete piece.
   The whole piece should disappear; one Undo should restore its complete design.
5. Start moving a piece or a Bezier handle and press Shift+D before releasing.
   It must not create a duplicate or redirect the drag. Finish the drag and undo.
6. Type an exact point position that makes the outline cross itself. The input
   and error should remain available for correction. Correct the value, apply,
   and verify that one Undo restores the original point. Try the same failure
   using a value drag.
7. Start chain sewing, free sewing, a dart, or a handle drag and press Escape.
   Start again and confirm that no previous picks or previews remain.
8. Save a garment, modify it, load the saved version, and undo the source change.
   Try an invalid library design: it must show an error without replacing the
   current garment. Keep a saved copy of important Blender projects.
9. Complete the usual Sew > Simulate > Pause > Keep mesh flow, checking fabric,
   UVs, final mesh, and the existing unwelded-seam recovery controls.

## Verification

- All nine developer-runner suites and Blender extension-package validation pass.
  The fast-flow GUI suite includes 155 checks.
- Two independent review rounds were completed; the final review found no
  unresolved high- or medium-priority correctness findings in the scoped changes.
- Eleven in-engine scenarios were captured, and compact/empty onboarding was
  recaptured after its changes. Compact starter and Workspace cards remain
  separate, without the former obscured empty-state text.
- The installable archive is byte-for-byte matched against all 62 packaged source
  and documentation files. No protected algorithm file is modified.
- Python source and generated screenshot scripts pass syntax, comment-token,
  and AST standalone-string/docstring checks. PowerShell parsing and equivalent
  CMD, SVG, JSON, TOML, and YAML checks pass.
- The public-source/archive/reachable-history scan passes. Its existing notice
  acknowledges two accepted published author identities retained in Git history;
  no history rewrite or claim of a complete privacy purge is made.
- Installable output remains in `dist/`; disposable screenshot and test artifacts
  are removed through the validated developer runner after review.

## Remaining boundary

Library rollback restores imported settings and source values, not generated
geometry already removed or replaced by an unexpected failure inside the
protected panel builder. Malformed library metadata is rejected before that
builder runs. Save important Blender projects before loading or rebuilding.
This audit is not a guarantee that every possible artist workflow is defect-free.

The testing and shipping handoff follows AGENTS.md: after the artist test handoff,
PR or ship it confirms acceptance and authorizes final checks, PR creation or
update, merging into master, post-merge verification, and session closure. Do not
request another manual test of unchanged accepted behavior. A public release
remains a separate explicit request.
