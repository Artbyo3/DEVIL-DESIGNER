# Keep Mesh Crash Investigation (v0.11.0 Release)

## Executive Summary

- **Reproduction status**: Not reproduced across all specified primary scenarios or extended piece-state variations in real Blender 5.2.3 LTS.
- **Root cause analysis**: The released v0.11.0 Keep flow is structurally sound across standard workflows. In all tested scenarios, invalid states (e.g., Keep before drape) are cleanly intercepted by `workflow_blocker` returning user-facing guidance (`"Start a drape before keeping or resetting it."`), and valid states create the final mesh cleanly. Because `run()` in `devil_designer/operators.py` and `workflow_action()` in `devil_designer/editor.py` catch only `(ValueError, RuntimeError)`, any unhandled exception of another type (`TypeError`, `KeyError`, `AttributeError`, `IndexError`) would escape and trigger Blender's Python traceback header while leaving the minimal editor status line (`"1 piece · Drag to move"`) visible.
- **Coverage gap**: No automated gate or test suite in the repository exercises the Keep operator (`bpy.ops.devil_designer.keep_drape`) end-to-end through the minimal UI (`minimal_ui=True`) across representative garment types; background tests invoke only the internal backend function `garment.keep_drape(context)`, and GUI tests either disable minimal UI or mock scene state.
- **Proposed gate**: Add a mandatory **Core workflow end-to-end gate** to `AGENTS.md` requiring real-Blender verification of the full `DRAFT` -> `SEW` -> `ARRANGE` -> `SIMULATE` -> `KEEP` pipeline across single pieces, multi-piece garments, and starters through the real minimal UI before any release.

---

## 1. Real-Blender Reproduction Matrix

All reproduction tests were executed using the project's established real-Blender test route with Blender 5.2.3 LTS (`C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe` with `--enable-event-simulate --factory-startup`) against the v0.11.0 code.

### Required Scenarios

| Scenario | Reproduction Result | Observed Behavior | Traceback |
| :--- | :--- | :--- | :--- |
| **(a) Single pattern piece, no seams (pre-simulation)** | **Not reproduced** | Intercepted cleanly by `action_blocker('KEEP')`. Status message: `"Start a drape before keeping or resetting it."`. No operator executed; editor remained in interactive modal loop. | None |
| **(a) Single pattern piece, no seams (post-simulation)** | **Not reproduced** | Gravity simulation completed; Keep button clicked. Operator `DD_OT_keep_drape` executed successfully, created `DD Garment` mesh with pattern UVs, hid simulation source, selected final mesh. | None |
| **(b) Two sewn pieces (pre-simulation)** | **Not reproduced** | Intercepted cleanly by `action_blocker('KEEP')`. Status message: `"Start a drape before keeping or resetting it."`. | None |
| **(b) Two sewn pieces (post-simulation)** | **Not reproduced** | Arranged around avatar and simulated. Keep button clicked. Operator successfully extracted draped mesh, welded seams within tolerance, reported open seam status warning, and finalized object. | None |
| **(c) Keep pressed before arranging on a body** | **Not reproduced** | Tested on empty document, single piece, two sewn pieces, and starter garment. All cleanly intercepted by `workflow_blocker` with `"Start a drape before keeping or resetting it."`. | None |
| **(d) Keep after arranging + simulating** | **Not reproduced** | Completed full arrange -> simulate -> stop -> Keep cycle. Operator generated `DD Garment` with proper thickness modifier and vertex groups. | None |
| **(e) Starter garment (Fitted Tee) through arrange -> simulate -> Keep** | **Not reproduced** | Loaded `STARTER_TEE` (pre-configured chest arrangement) -> simulated -> stopped -> Keep. Final mesh generated without error. | None |

### Extended Variable Matrix

| Variable Tested | Reproduction Result | Observed Behavior |
| :--- | :--- | :--- |
| **Keep during active simulation** | **Not reproduced** | Invoking Keep while transport was playing called `garment.stop(context)`, pausing animation cleanly and extracting the current frame mesh. |
| **Consecutive Keep presses** | **Not reproduced** | Second click detected that panels/signatures matched the existing kept mesh and returned `"The patterns or arrangement changed. Reset and simulate the current version first."` via handled `ValueError`. |
| **Frozen pieces** | **Not reproduced** | Garment with frozen piece simulated and kept cleanly. |
| **Deactivated pieces** | **Not reproduced** | Garment with deactivated piece simulated active pieces only and kept cleanly. |
| **Pins** | **Not reproduced** | Garment with pattern pins simulated and kept cleanly. |
| **Tacks** | **Not reproduced** | Garment with avatar body tacks simulated and kept cleanly. |
| **Wrap arrangement** | **Not reproduced** | Cylindrical wrap piece simulated and kept cleanly. |
| **Library-loaded garments** | **Not reproduced** | Garment saved to library and reloaded simulated and kept cleanly. |

---

## 2. Root Cause and Code Path Analysis

### The v0.11.0 Keep Flow Map

1. **User Action**: Artist clicks `Keep mesh` button (`layout.buttons['KEEP']`) in the minimal canvas interface (`devil_designer/minimal.py`).
2. **Automatic Defaults**:
   `devil_designer/minimal.py:1047`:
   ```python
   self.automatic_defaults(finalize=button == 'KEEP')
   ```
   Ensures `dd_self_collision`, `dd_library_refit`, `dd_spacing`, `dd_quality`, `dd_weld_distance`, and `dd_thickness` are normalized.
3. **Action Dispatch**:
   `devil_designer/interaction.py:209` (`perform_action`):
   Calls `blocker = self.action_blocker(action)`.
   In `devil_designer/editor.py:429` (`workflow_blocker`):
   ```python
   if button in {'KEEP', 'RESET'} and not any(
           obj.get('dd_owner') == 'Artbyo3/DEVIL-DESIGNER' and obj.get('dd_kind') == 'simulation'
           for obj in self._scene.objects):
       return 'Start a drape before keeping or resetting it.'
   ```
4. **Operator Execution**:
   `devil_designer/editor.py:481`:
   ```python
   op = getattr(bpy.ops.devil_designer, names[button])
   result = op('EXEC_DEFAULT')
   ```
5. **Operator Lifecycle & Error Handling**:
   `devil_designer/operators.py:82` (`DD_OT_keep_drape`):
   Calls `run(self, action)`:
   ```python
   def run(operator, action):
       try:
           return action()
       except (ValueError, RuntimeError) as exc:
           operator.report({'ERROR'}, str(exc))
           return {'CANCELLED'}
   ```
6. **Geometry Extraction & Welding**:
   `devil_designer/garment.py:447` (`keep_drape`):
   Stops animation, verifies simulation signature, creates BMesh from evaluated depsgraph, welds vertices within `dd_weld_distance` across `dd_sewing_pairs`, transfers vertex groups, applies optional solidify modifier, tags final object, and returns `(obj, unclosed)`.

### Why Blender Displays a Python Traceback Header

In Blender, an operator reporting an error (`operator.report({'ERROR'}, ...)` and returning `{'CANCELLED'}`) displays an info banner, never a traceback.

Blender displays the error header `Python: Traceback (most recent call last): File ...` exclusively when an unhandled Python exception escapes execution. In the Keep flow:
- `run()` in `devil_designer/operators.py:7` catches strictly `(ValueError, RuntimeError)`.
- `workflow_action()` in `devil_designer/editor.py:509` catches strictly `(RuntimeError, ValueError)`.

Therefore, if an exception of type `TypeError`, `KeyError`, `AttributeError`, `IndexError`, or `ZeroDivisionError` occurs anywhere within `keep_drape`, `DD_OT_keep_drape.execute`, or `automatic_defaults`, it escapes all handlers, crashes the modal operator `DEVIL_DESIGNER_OT_pattern_editor`, pops up Blender's traceback header, and leaves the editor UI frozen on its last drawn status line (`"1 piece · Drag to move"`).

### Untested Variable Vectors

Because no crash reproduced across standard geometric configurations, the failure encountered by the artist must stem from an environmental or mesh condition outside standard test primitives:
1. **Collider Topology Anomalies**: Non-manifold avatar meshes, zero-area polygons, or missing UV layers on custom artist colliders.
2. **Third-Party Dependency / Add-On Interception**: Depsgraph evaluation hooks or object-linking handlers from third-party add-ons raising unhandled exceptions during `bpy.data.meshes.new_from_object` or `collection.objects.link`.
3. **Corrupt Scene Custom Properties**: Pre-existing invalid datatypes stored on `scene['dd_unwelded_seams']` or `scene['dd_sewing_pairs']`.

---

## 3. Verification Coverage Audit

An audit of the repository's test suites and gates reveals a complete absence of end-to-end verification for the Keep operator.

### Files Checked

| File | Type | Verification Mechanism | Keep Coverage Assessment |
| :--- | :--- | :--- | :--- |
| `tools/build.py` | Build Gate | Static AST & Token Checks | **Zero execution coverage.** Only runs comment, import, and dead-code checks. |
| `tests/test_*.py` | Unit Tests | Mocked `bpy` (Headless) | **Zero functional coverage.** `test_controls.py` asserts button key strings only. No geometry or operator execution. |
| `tests/blender_garment.py` | Real Blender | Background script | **Bypasses operator.** Calls internal `garment.keep_drape(context)` directly at line 130. Does not test `DD_OT_keep_drape`, scene properties, or UI handlers. |
| `tests/blender_advanced.py` | Real Blender | Background script | **Bypasses operator.** Calls internal `garment.keep_drape(bpy.context)` at line 78. |
| `tests/blender_layering.py` | Real Blender | Background script | **Bypasses operator.** Calls internal `garment.keep_drape(bpy.context)` at line 162. |
| `tests/blender_piece_states.py` | Real Blender | Background script | **Bypasses operator.** Calls internal `garment.keep_drape(bpy.context)` at lines 49 and 67. |
| `tests/gui_preview.py` | Real Blender | In-Engine GUI | **Disables Minimal UI.** Clicks `'KEEP'` at line 285, but line 30 explicitly sets `op.minimal_ui = False`, executing only legacy UI paths and bypassing `minimal.py`. |
| `tests/gui_fast_flow.py` | Real Blender | In-Engine GUI | **Synthetic and Mocked.** Clicks `'KEEP'` at line 1011, but lines 1014/1017 manually mock `scene['dd_unwelded_seams']` rather than testing real unwelded seam reporting across varied garments. |

### The Precise Shipping Gap

The v0.11.0 release shipped without any test exercising `DD_OT_keep_drape` through the active minimal interface (`minimal_ui=True`) from a user click. Background suites called the internal backend helper directly, while GUI suites either disabled the minimal UI or manually mocked operator state.

---

## 4. Proposed AGENTS.md Release Gate

The following exact text is proposed for addition to `AGENTS.md` under the verification gates section:

```markdown
- **Core workflow end-to-end gate**: no build is verified, ready, or done unless the real-Blender GUI test suite exercises the complete user journey (`DRAFT` -> `SEW` -> `ARRANGE` -> `SIMULATE` -> `KEEP`) end-to-end through the active minimal UI (`DEVIL_DESIGNER_OT_pattern_editor` with `minimal_ui=True`) and the `devil_designer.keep_drape` operator on real 3D geometry without mocked scene properties. Verification must explicitly cover Keep mesh across fundamental scenario classes: (a) single pattern piece with zero seams, (b) multi-piece sewn garments, (c) pre-arrangement/pre-simulation Keep invocation blocker assertions, (d) post-drape simulation mesh extraction, and (e) starter garments (Fitted Tee, Tank, Skirt) taken through drape and final mesh finalization. Calling internal backend functions like `garment.keep_drape()` directly does not satisfy this gate.
```
