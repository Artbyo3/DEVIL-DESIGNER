# Dead-code reachability audit

Goal: remove code the shipped add-on can never execute, so future work stops testing dead UI.

## Method

Entry points are `__init__.register`, `ui.register`, every registered operator, the modal
`handle_event`, the draw handler, load handlers, and saved `.blend` state.

`reachability.py` traces definitions from those entry points. It over-approximates, because any
name, attribute, or whole-string mention in live code counts as an edge. A definition it reports
is therefore unreachable by any named route.

A name graph cannot see string dispatch, so `state_audit.py` lists action tokens, write-only
attributes, and read-only settings. Each candidate was then checked by hand against its emitters:
`layout.buttons`, `minimal_card` rows, `show_card`, and every `perform_action`, `design_action`,
`workflow_action`, and `minimal_action` call.

`removed_symbols.py` confirms that no package code still references a removed symbol.

Saved files count as an entry point. A scene property with a UI writer in a shipped release can
hold a non-default value in an artist's `.blend`, so its reads stay.

## Removals and evidence

Live emitters for `perform_action` after the audit: CANCEL_ACTION, CONFIRM_ACTION, CANCEL_DRAFT,
FINISH_DRAFT, CHAIN_CLEAR, CURVE, DELETE, DELETE_PIECE, DEMO_PANEL, DUPLICATE, FLIP_H, FLIP_V, KEEP,
LIBRARY_LOAD, LIBRARY_SAVE, MERGE, MIRROR_SEW, POINT_APPLY, REDO, SET_LENGTH, SIMULATE, SPLIT,
STARTER_*, TRACE, UNDO, UNFOLD.

### editor.py

- `set_stage`, `advance_stage`. Trace: `handle_event` > `minimal_action` or `perform_action` >
  `GUIDED_NEXT`. No button, row, or key emits `GUIDED_NEXT`.
- `self.stage`. Its only reads were `advance_stage` and `make_layout`, which passed it to
  `Layout.stage`. Nothing reads `Layout.stage`.
- `workflow_action` BUILD, ARRANGE, DEMO branches and the `ARRANGEMENT` card call. BUILD came only
  from `advance_stage`. ARRANGE and DEMO came only from `perform_action`, with no emitter.
  `minimal_card` had no `ARRANGEMENT` kind.
- `shape_committed_frame`. Written three times, never read.

### interaction.py

- `perform_action` branches: tool names, VIEW_3D, FIT, SNAP, REFERENCE, LENGTHS, HELP, GUIDED_NEXT,
  RESET confirm prompt. None has an emitter. Dock buttons use `TOGGLE_*`, and the RESET row calls
  `workflow_action` directly.
- `action_blocker` entries for STOP, START_PANEL, OFFSET, WRAP, PRESET, SET_PRESET_, CHAIN_SEW,
  LIBRARY_PREV, LIBRARY_NEXT, REMOVE_ANCHOR. Each has no `perform_action` emitter.
- `window_gesture`. Written once, never read.

### design_tools.py

- `design_action` branches ADD_PANEL, START_PANEL, NUM_RECT, NUM_ELLIPSE, POINT_TYPE_, OFFSET,
  SELECT_TARGET_, SET_PRESET_, WRAP, PRESET, CHAIN_A, CHAIN_B, CHAIN_SEW, LIBRARY_PREV, LIBRARY_NEXT.
  None has an emitter. `minimal_action` handles POINT_TYPE_ and SET_SELECT_TARGET_ itself.
- Chain sewing state `chain_stage`, `chain_a`, `chain_b`, also in editor, interaction, minimal,
  draw, and viewport_sewing. `chain_stage` was set only by CHAIN_A and CHAIN_B, so it was always
  None and both lists stayed empty. CHAIN_CLEAR stays because `viewport_sewing` emits it.
- Three-element `handle_preview` arms. The only assignment builds a seven-element tuple.

### minimal.py

- `minimal_action` keys TOGGLE_MEASURE, BODY_CHANGE, EDIT_ACTIONS, WORKSPACE_FIT, BODY_PICK_, CURVE.
  No row or button emits them.
- `EDIT` card. Its only `show_card` call was the EDIT_ACTIONS branch.
- Dead button aliases SNAP, REFERENCE, LENGTHS. `minimal_layout` creates only `TOGGLE_*` keys.
- `tool_hint` SELECT entry. SELECT always returns earlier in the function.
- `layout.minimal`, `toast_message`. Written, never read. `toast_until` stays, because draw uses it.

### draw.py

- Vector icon fallback for every icon except SHAPE, about 110 lines. `draw_icon` receives a fixed
  name set, and every name except SHAPE has spans in `geometry.json`, so the method returns first.
- `INSPECTOR` constant, `INSPECTOR_TOGGLE` and `INSPECTOR_COLLAPSE` branches, `HELP` shortcut. No
  such layout button exists.
- `mode_rects` non-dict arm. `card_mode_rects` always returns a dict.

### Other package files

- controls.py: 16 `Setting` entries and `dd_library_dir`. `CONTROL_SETTINGS` is read only by key
  from SLIDER rows and from the `NAME` row, which never use these keys. Scene properties that
  stay registered remain untouched. `Setting.integer` and `TextSetting.allow_empty` became dead
  because no remaining entry sets them.
- ui.py: `dd_width`, `dd_height`, `dd_offset`, `dd_wrap_radius`. Their only readers were the removed
  NUM_RECT, NUM_ELLIPSE, OFFSET, and WRAP branches.
- icons.py: `ICON_ALIASES`. No reachable name is an alias key.
- ui_system.py: `BG_PANEL`, `RADIUS_DOCK`, `RADIUS_DOCK_ITEM`, `RADIUS_CARD`. `BG_PANEL` fed only
  `INSPECTOR`. The radii were read only by a test.
- canvas.py: `Layout.stage` parameter.
- arrangement.py: `generate_volumes`. Only tests called it. Live fitting calls `_fit_steps`, so the
  tests now hold that driver as a local helper and still cover `_fit_steps`.

## Developer tools

- `dev.py --stage` and the screenshot `stage` argument. Both needed `set_stage`.
- `screenshot.py` and `open_preview.py` now create the demo through the registered operator.

## Suspected, kept

- core.py (protected): `Session.select_path` and `Session.rotate`, with no package caller. Only
  tests call `select_path`. `Session.offset` lost its last caller in this change.
- `dd_internal_mode`, `dd_sew_a0`, `dd_sew_a1`, `dd_sew_b0`, `dd_sew_b1`, `dd_measure_visible`: no
  current writer, but shipped releases wrote them, so saved files can hold real values.
- Registered operators `build_panels`, `demo`, `seam`: no UI caller, but registration keeps them
  callable from Blender.
- `TRACE_CALIBRATION`, `TRACE_POSITION` cards, `TRACE_PICK`, `TRACE_FIT`, `trace_points`,
  `tracing.calibrate`, and the `dd_trace_*` slider settings: unreachable today, but the rows are
  visible and clicking them does nothing. This looks like a wiring bug, not an abandoned feature.
- `minimal_ui`: write-only in the add-on, but `AGENTS.md` names it in the core workflow gate.
- `session.history_message`: never read by the add-on, but `test_history.py` asserts it on live
  restore paths.
- Unused `geometry.json` entries such as SAVE, FIT, SETTINGS: data, not code.
- A repeated `if self.gesture` guard in `minimal_event`: dead but harmless, and not worth the risk.

## Defects found, not changed

- Multi-selection `Delete` rows emit `DELETE`, which `minimal_action` does not handle, so the click
  does nothing.
- The image calibration and placement rows described above do nothing when clicked.
- `tools/screenshot.py` calls `op.refresh_controls()`, which does not exist on master, so `--shots`
  hangs.
- `blender_folding`, `blender_fold_garments`, `blender_seam_shrink`, and `blender_ellipse` are not in
  the runner. The first three cannot import the package without an added path.
