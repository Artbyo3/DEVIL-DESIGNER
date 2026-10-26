# DEVIL DESIGNER — Native Blender UI Redesign

**Repository:** `Artbyo3/DEVIL-DESIGNER`  
**Design reference:** `devil_designer_ui_concept.png`  
**Interactive layout/reference:** `devil_designer_ui_concept.html` (browser-only prototype)  
**Target:** existing custom GPU/BLF editor inside Blender 5.2+, not a webview, Qt application, or standard Blender N-panel.

## Objective

Make the interface behave like an uncluttered professional pattern-drafting tool. Apple-inspired here means clarity, restraint, predictable hierarchy, generous space for work, concise actions, and progressive disclosure—not copying macOS window chrome. The user should be able to start drafting, connect seams, position pieces, and simulate without hunting through unrelated buttons.

**Existing functionality must be retained.** Do not rewrite geometry, Bezier evaluation, source documents, UV mapping, sewing algorithms, or Blender cloth features in order to redesign the UI.

## What is wrong with the current interface

- ~3 horizontal rows of undifferentiated action buttons consume canvas height.
- Five inspector tabs put overlapping, unrelated controls beside one another.
- Width/Height *creation* inputs, Point X/Y edits, sewing, and simulation are visually presented as equal priority.
- Tool states, task progression, selected object details, and secondary commands are not clearly separated.
- Raw precision like `30.000001 cm` distracts from drafting.
- Expanded mode wastes available room and the small floating window crushes buttons.

## Reference layout: expanded mode

Design at an illustrative **1600 × 950** viewport; actual measurements must scale with the current Blender `ui_scale` and available `WINDOW` region.

1. **Header (approx. 66 logical px):** brand; central four-step navigation `Draft / Sew / Arrange / Simulate`; separate `Library`, overflow/preferences, and close affordances. Preserve drag-to-move and double-click-to-expand/restore.
2. **Left tool rail (approx. 78 px):** only the active workspace's tools. Use monochrome geometric icons and short labels; active tool is the single highlighted selection. Always display keyboard shortcuts in tooltips. Select V; Polygon P; Rectangle R; Ellipse E; Internal I; Dart D. In Sew show select/sew; in Arrange show place/pin/tack. There must also be room for mode-specific secondary tools if required.
3. **Center canvas:** as large as practical. Keep the real measured grid, pattern colors, outline points, Bezier handles, body reference, seam overlay, world pan/zoom, rulers, and exact source coordinates. The screenshot is *illustrative*: do not copy its dummy geometry or dimensions.
4. **Canvas utility strip (approx. 62 px):** context title on left; Body, Lengths, Snap and Fit controls on right. Undo and Redo must stay discoverable through shortcuts and/or compact toolbar actions.
5. **Right inspector (approx. 327 px):** contextual object or operation details only. Example: selected pattern → name, actual computed dimensions, location, fabric preset, relevant actions. Selected point → X/Y and curve controls; selected edge → actual length, exact-length edit, split/unfold options; selected seam → A/B lengths, mismatch, reverse/remove; no selection → task-specific creation instructions and numeric new-shape controls.
6. **Inspector bottom:** a single primary next-task action *when applicable*. Draft → `Continue to sewing`; Sew → `Continue to arranging`; Arrange → `Continue to simulation`; Simulate → `Start / Stop`, followed by Keep/Finalize when the workflow reaches a valid state. Keep ordinary navigation possible in either direction; avoid imposing mandatory stages.
7. **Status footer (approx. 32 px):** meaningful current message, selection/tool/unit/coordinates where useful. Use it for errors and nonblocking warnings, not destructive modal dialogs.

## Stage definitions and control mapping — NO FEATURE LOSS

| Surface | Existing capabilities that must remain accessible |
|---|---|
| **Draft** | Select, polygon, rectangle, ellipse, internal path, dart, new-shape numeric X/Y/Width/Height, add/move point, Bezier handle edit, corner/curve C, split Q, merge M, exact segment length, offset outline, Unfold U, mirror with seam Shift+U, cut internal shape, trace internal shape, show lengths, delete/duplicate |
| **Sew** | Segment sewing J, free four-click sewing, M:N chain A/B picking, chain clear, chain sew, ranges A/B start/end %, selected seam details, reverse B, remove X, explicit length mismatch warnings, sewing preview |
| **Arrange** | Avatar body picker/Use selected body, Body reference front/back/left/right, opacity, reference X/Y, align/frame/refresh, Build 3D, two-piece Arrange, click-place, wrap radius/unwrap, pins K and tacks T, remove selected anchor |
| **Simulate** | Fabric preset, mesh spacing, body clearance, quality, frame limit, self-collision, pin highest points, Simulate/Stop/Reset, Keep mesh, weld distance, thickness, existing demo where appropriate |
| **Library** | Local garment name, save editable garment, previous/next selection, refit toggle, load on avatar; never bundle avatar mesh/name by default |
| **Global** | Move, resize, maximize/restore, close, grid snap S, fit F/Home, body H, lengths L, undo/redo, pan/zoom, typing/committing numeric values, tool cancel Esc, Blender scene interaction outside overlay |

### Contextual inspector specification

- **Nothing selected:** show one-sentence guidance for the active tool and creation inputs when applicable. Do not show an invented `Pattern 01` inspector.
- **Selected whole pattern:** computed bounding size (display-only initially), selected fabric, object name, move/offset/mirror/unfold. **Do not mistake `dd_width/dd_height` (new-shape creation parameters) for an editable selected-pattern size.** If changing a selected pattern's size is desired later, implement and test a separate explicit operation.
- **Selected vertex:** editable actual point X/Y; Corner/Curve; Split; Delete; precise coordinates.
- **Selected edge:** actual measured Bezier arc length and existing exact-length operation; make endpoint locking/affected geometry understandable.
- **Selected internal path:** Trace, Cut, Slit where valid; explain invalid actions.
- **Selected sewing pair:** show both arc lengths, delta in cm and %, direction, Flip, Remove. **Mismatch never hard-blocks valid intentional gathers.**
- **Simulation:** show status (ready, running, stopped, finalized), controls and detailed settings in an expandable section.
- **Destructive operations:** present undo availability and confirmation only where actually necessary; don't introduce modal dialogs for regular tool changes.

### Compact/responsive rules (essential; current editor is a movable floating window)

- **Wide / expanded >= 1100 logical px:** fixed tool rail ~72–78, inspector ~300–327, canvas receives remainder.
- **Medium 850–1099 px:** compact rail ~58–64, inspector ~240–275, remove text from low-priority utility chips; preserve canvas min ~440 where possible.
- **Narrow 620–849 px:** keep tool rail ~52; make inspector a toggleable *overlay drawer* instead of permanently squeezing the canvas. Collapse the four-stage navigator to a single stage selector if needed. Secondary controls stay reachable via popovers or drawer scrolling.
- **Minimum 420–619 px when the Blender `WINDOW` region forces it:** prioritize canvas/tool selection; compact header and place inspector in a modal/overlay sheet; do not overlap hit regions, chop numeric fields, or trap the close control. Existing `clamp_window()` already accounts for constrained regions—preserve that behavior.
- Inspector scrolling is separate from canvas pan/zoom; scene mouse events outside the editor continue to pass through.
- Minimum practical pointer target about 32 × 32 logical px and readable labels >= 10–11 px at scale 1. Hover/active/disabled/focus must be distinguishable without relying only on color.

## Design tokens

| Token | Hex | Purpose |
|---|---|---|
| Window background | `#14191E` | Base shell |
| Top chrome | `#1A2026` | Header |
| Canvas background | `#12171C` | Drafting surface |
| Inspector | `#1C232A` | Context properties |
| Field background | `#141B21` | Inputs |
| Elevated control | `#253039` | Secondary buttons |
| Subtle border | `#34404A` | Structural boundaries |
| Primary text | `#EDF0F2` | Headings, numbers |
| Secondary text | `#A4AFB9` | Descriptions |
| Muted text | `#778592` | Metadata |
| Accent | `#79DAC7` | Selected tool and single primary action |
| Accent soft | `#223E3C` | Selected tool background |
| Pattern 01 | `#BDA6E9` | Per-pattern identifiable line |
| Pattern 02 | `#D7B17B` | Per-pattern identifiable line |
| Pattern 03 | `#79BBD0` | Per-pattern identifiable line |

Style: mostly flat fills; small rounded corners (8–11 px) where geometry is affordable; 1 px quiet borders; no gratuitous dividers, gradients, drop shadows, or multiple neon colors. Pattern identity hues should be stable across drafting/sewing/arrangement. Only the primary action uses a solid accent fill. Group controls through proximity and whitespace before adding lines.

Precise unit rendering: keep full internal float precision and existing metre storage. **Presentation only** rounds common cm measurements to 1 decimal by default and optionally 2 decimals for fine drafting; live edit buffer must preserve typed precision; never change geometry by rounding its displayed string.

## Implementation approach specific to this repository

**Repo files inspected:** `devil_designer/canvas.py`, `draw.py`, `controls.py`, `interaction.py`, `editor.py`, `ui.py`, plus README/SPEC. The current UI is a native custom `gpu` + `blf` overlay, and hit regions originate from `canvas.Layout` and `controls.Inspector`.

- Build a coherent theme (shared palette + logical spacing, typography, radii, borders) in or alongside `draw.py`.
- In `canvas.py`, replace the three dense horizontal button rows with separate header, stage navigator, vertical tool rail, top utilities, canvas, contextual inspector and status footer. **All clickable bounds must come from this same layout**, and resize/full-screen positioning stays viewport-local.
- In `controls.py`, derive inspector rows from current workspace mode **and current selection kind**, not from a fixed five-tab scroll of every setting. Keep the existing Setting conversion/validation rules and bindings where applicable. Reuse the same `Control` rectangles for painting and input hit tests.
- In `interaction.py`, route stage changes, rail tool selection, contextual commands, inspector collapse and popovers to existing actions. Do not accidentally consume wheel/pan events outside the intended panel. Prevent changing stages midway through an uncommitted draft without deliberate Finish/Cancel behavior.
- In `editor.py`, keep `workflow_action()` and the existing modal behavior as the source of truth. A stage is a UI workspace, **not** a forced finite-state wizard. The core `Session` and source pattern data must not change merely because a stage is switched.
- In `draw.py`, use existing `gpu` triangle/line drawing and `blf` labels. Rounded rectangles may be approximated with cached triangle fans. Icons must be simple native GPU lines/triangles, not external PNG/icon-font dependencies. Do not assume HTML, CSS, Qt, DOM or JavaScript are available inside Blender.
- Preserve existing behavior of other add-on modules unless explicitly necessary; no new network dependencies.

### Performance and correctness

- Avoid reconstructing GPU batches/icons every frame if they can be cached; respect `gpu.state` restoration, scissor viewport offsets, text clipping, and DPI scale. Preserve actual canvas world projection and measured geometry.
- One and only one logical definition of each interactive rectangle. Avoid visuals that render where input is not accepted, especially when the inspector is collapsed or the window is small.
- A disabled control must not fire, and its disabled state must clearly explain missing prerequisites.
- Preserve keyboard-first workflows, tool shortcuts and undo. Never silently discard an unfinished polygon, draft, or user edit on stage switch.

## Agent task — deliver in small reviewable stages

Start by reading repository instructions including `AGENTS.md` if present. Fetch the latest `main`, create a **dedicated branch** such as `ui/custom-editor-redesign-v1`, and avoid out-of-scope changes. This request is primarily a **UI redesign**.

**Phase 1 (first PR only):** Implement new layout primitives/theme, top stage navigation, tool rail, utility strip, canvas sizing, footer, and **Draft-only** contextual inspector states (none selected, whole pattern, point, segment). Keep all other commands reachable temporarily by a legacy fallback until their native context panels exist. Do **not** remove existing functionality or tests. Take real Blender UI screenshots of expanded and floating states.

**Phase 2:** Implement Sew and Arrange contextual inspector surfaces, including M:N sewing, numeric range fields, body picker, wrap/anchor actions and warnings. Only remove legacy fallbacks once their commands have parity.

**Phase 3:** Implement Simulate, Library, advanced settings, polish, responsive fallback and final parity test. Confirm keep mesh/reset/simulate actions remain correct.

### Acceptance and report

1. Open editor with `Ctrl+Alt+D`; move, resize, expand, restore, and close without broken hit targets.
2. Create rectangle and polygon; see real measured points and lengths; select/edit a point and segment through the contextual inspector, without losing Bezier fidelity.
3. Switch Draft → Sew → Arrange → Simulate and back; no loss of selected source pattern, seam references or original UVs; no unintended simulation.
4. At 620×440 and at expanded display sizes, all essential actions are reachable; canvas and 3D viewport remain interactive in correct regions.
5. Existing sewing length-mismatch warning remains nonblocking; precise numeric edits remain accurately parsed despite prettier display formatting.
6. Old layout is replaced by native Blender GPU rendering, not HTML. Screenshot should visibly follow the supplied reference (hierarchy, spacing, color, typography) but prioritize actual Blender interaction over exact browser pixels.
7. Run existing tests, including `python -m unittest discover -s tests -p "test_*.py" -v`, Blender background tests (`blender_smoke.py`, `blender_garment.py`, `blender_advanced.py`, `blender_silhouette.py`), and GUI tests (`gui_preview.py`, `gui_design.py`, `gui_silhouette.py`) where Blender is available. State which were run, passed, skipped, or failed.
8. Report **branch, commit, files changed, screenshots, exact commands, test results, UI regressions, known gaps, and a privacy scan**. Do not merge until reviewed.

## Boundaries

The HTML file is an **interactive visual reference**, not a replacement for Blender and not a functional pattern editor. Its pattern data, dimensions and seam example are fake for visual demonstration. The UI code must read real Blender data through the existing backend. No repo files have been changed by this design proposal.
