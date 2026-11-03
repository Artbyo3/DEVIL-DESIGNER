# Issue 76: professional arrangement within the existing ellipse system

Date: November 2, 2026. Phase 1 only. Baseline: `1aeeb795c249c6ef638ea5a0ee20b4e4bcda6b9a` plus pre-existing working-tree changes, not a clean checkout of that commit.

Status: PROPOSAL READY. Implementation has not started and awaits formal artist approval of section 6.

## Recommendation and approval gate

Raise the existing system so artists can place fitted clothing without repairing an uncontrolled wrap. Keep elliptical volumes, named points, click-to-place and saved arrangement records. Add readable interactive points, placement preview, body-checked elliptical wrapping and a deliberate Wrap / Flat choice. Remove repeated synchronous full-mesh section scans from body selection.

This proposal does not authorize implementation. No production source, protected file, README or SPEC was changed. Only measurement tools and reports were added. Existing unrelated changes, including `garment.py`, were preserved. The build requires formal artist approval of section 6. No protected-file exception is requested. If implementation needs a locked file, stop and request approval for that precise additional area.

## 1. Evidence and measurement limits

- `reports/issue76-arrangement-evidence.json` contains samples, profiles, source hashes and collision measurements.
- `tools/research_arrangement76.py` runs the real-Blender selection benchmark and deterministic wrap reproduction.
- `tools/research_arrangement76_gui.py` invokes the real minimal editor, calls its actual body-selection method and performs an actual viewport redraw. No mocked scene, editor or geometry.
- `scratch/issue76-wrap-repro.blend` contains the synthetic body and concave panel for inspection. Logs and temporary scenes remain diagnostics, not extension assets.

Run the background tool with Blender `--background --factory-startup --python-exit-code 1 --python tools/research_arrangement76.py`. Repeat only wrapping with `-- --wrap-only` after the complete evidence file exists. Run the GUI tool in another factory-startup Blender with `--python tools/research_arrangement76_gui.py`. Neither tool attaches to the artist's existing Blender.

Real Blender 5.2.3 LTS ran on an Intel i5-13600KF with 20 logical processors. Five fresh selections alternate with five stored-setup selections. Fresh means deleting only the fixture's volume JSON. Every sample verifies that 12 volumes were generated. Profiling is a separate run, excluded from latency samples. The GUI measurement includes `choose_body`, silhouette refresh and canvas fitting with an empty garment document, then measures redraw separately. It is not an automated mouse-to-photon measurement. Existing-garment rebuilding and expensive avatar modifiers can add costs.

Another Blender session was left running. A sampled machine CPU reading was 11 percent, not continuous load telemetry. GUI and background runs occurred at different times. Their differences are not an optimization comparison. These synthetic fixtures prove a source defect and a bottleneck, not the exact geometry or timing of the artist's private avatar. Vendor documentation establishes controls and workflows, not unpublished algorithms.

## 2. Diagnosis

### Points

`arrangement_controls.py:86` draws a 16-triangle disk with a 5-pixel radius. `hit_point` at line 148 accepts a 10-pixel radius. All markers receive the same cyan color at lines 172-173. These are source measurements, not perceptual contrast results.

`point_event` at line 177 handles press events for clicking and right-click menus, plus H. There is no point drag lifecycle, hover-state rendering, selected-state rendering or placement preview. Clicking immediately places the selected panel. Picking ranks approximate screen distance then eye distance without establishing body occlusion. Enlarging markers alone would increase ambiguous overlap.

Right-click offers Arrange flat, Move point, Add point, Delete point and Edit bounding volume. Move opens a 260-pixel native dialog with angle and fractional height. Volume editing exposes normalized lower/upper height and one radius multiplier. Sources: `arrangement_controls.py:193`, `:239`, `:248`, `:260`.

### Selection and placement flow

The body menu calls `editor.py:297 choose_body`, which assigns `scene.dd_avatar`. Its RNA callback, `live_panels.py:225 avatar_changed`, synchronously calls `arrangement.py:278 ensure_volumes`. On first selection, evaluated mesh extraction feeds `generate_volumes`, then setup JSON is stored on the avatar. Silhouette refresh and canvas fitting follow. Existing non-legacy patterns can additionally cause a panel rebuild. Sources: `ui.py:81`, `minimal.py:1132`, `editor.py:297`, `silhouette.py:62`, `live_panels.py:225`.

`arrangement.py:78 generate_volumes` defines 12 volumes, each with seven section samples. Arms receive an additional pass after estimating their axes. The fixture executes 112 `_volume_sections` calls. Every call traverses every body triangle in Python and computes corner-plane distances through `_volume_dot`. This repeated whole-mesh work, rather than GPU marker generation, is the measured bottleneck.

Ellipse fitting encloses each sampled contour, not all body surfaces between planes. `ellipse_volumes.py:32 volume_stack` combines sections in the same torso, arm or leg family. `section_at_height` at line 53 interpolates sections, clamping outside their sampled extent while moving the center. Point resolution at line 87 establishes frame and phase.

`live_panels.py:33 position_panel` receives the unchanged generated mesh. Version-2 wrapping calls cached `ellipse_volumes.py:133 wrap_positions`. For each distinct vertex height, it constructs a 4,097-point circumference table, maps horizontal distance by arc length and wraps modulo the perimeter. Whole-piece width triggers an outward spiral when wider than the perimeter. It does not check the body triangles. Folded panels deliberately use flat placement to preserve creases, with a warning.

Source-supported risks, not all independently reproduced:

- An unsampled protrusion can escape the interpolated ellipse. Long panels can exceed a volume family's useful extent.
- Section components are chosen independently at each plane: torso nearest the center, limbs by the relevant side/height heuristic. Nearby disconnected surfaces can therefore produce inconsistent choices between planes. This candidate is source-identified at `arrangement.py:114`, not a second reproduced failure.
- Concave pieces have different occupied widths per row, but spiral handling uses whole-piece width.
- Triangle interiors can cross the body even when vertices are outside. Manual pose deltas can also introduce intersections after wrapping.
- Tables per exact vertex height can make distinct-panel wrapping expensive. The whole-result LRU does not share section tables across different panels. This is not the measured cause of body-selection latency.

### Reproduced complex-panel failure

The closed synthetic torso is 1.8 m tall with baseline radii 230 mm sideways and 140 mm front/back. A narrow protrusion reaches 225 mm front/back at height 1.180 m, fading over 12 mm on either side. This is an adversarial envelope fixture, not a claim about ordinary anatomy.

The concave six-corner panel is 480 by 560 mm with a 320 by 200 mm corner notch. Exact coordinates are in the evidence and tool. It uses native CDT-generated topology, 15 mm spacing, waist/front, version 2, default 30 mm clearance and no pose delta. Production `garment.build_panels` and placement run unchanged.

| Case | Vertices | Triangles | Inside vertices | Deepest signed penetration | Intersecting panel triangles |
| --- | ---: | ---: | ---: | ---: | ---: |
| Concave long tab | 1,143 | 2,141 | 3 | 4.178 mm | 53 |
| Rectangle on the same body | 1,465 | 2,786 | 4 | 6.459 mm | 53 |
| Same wrapped concave mesh against body without protrusion | unchanged | unchanged | not measured | not measured | 0 |

Penetration uses nearest outward triangle-plane signed distance, not radial deficit or a continuous maximum over the panel. Triangle overlap uses real `mathutils.bvhtree`. The fixture is closed and outward-wound; inside means below negative 1 micrometre.

At height 1.180 m the resolved front ellipse radius is 162.116 mm. With the requested 30 mm radial clearance it reaches 192.116 mm, still 32.884 mm short of the body's 225 mm front extent. Neighboring torso samples straddle the waist/chest sampling gap. Interpolation cannot reconstruct the missed maximum. Wrapping returns no arrangement warning. Removing only the protrusion eliminates all 53 intersections in the same mesh.

The first failure is an insufficient envelope between sections. Concavity exposes it but is not the cause, since the rectangle also fails. Point angle/height edits cannot restore missing envelope geometry. Increasing an entire volume's radius can hide this collision while overinflating unrelated rows. Flat should not be required to conceal it.

### Selection cost

The background benchmark times actual RNA body assignment and its callbacks:

| Body triangles | Fresh median | Fresh range | Stored-setup median |
| ---: | ---: | ---: | ---: |
| 4,320 | 1.633 s | 1.102-1.744 s | 0.783 ms |
| 17,856 | 7.243 s | 7.063-7.285 s | 0.923 ms |
| 72,576 | 28.292 s | 28.063-29.121 s | 0.941 ms |

The separate largest profile attributes 66.559 of 67.939 seconds to 112 `_volume_sections` calls, 97.97 percent inclusive. It executes 24,547,493 `_volume_dot` calls. Mesh extraction takes 0.517 seconds; ellipse fitting takes 0.279 seconds. Profiled seconds include instrumentation overhead and must not replace the unprofiled medians.

The real minimal-editor callback on a 17,856-triangle body takes a median 4.381 s, range 4.368-4.414 s over five fresh selections. The stored-setup callback median is 31.057 ms, and the separate actual-redraw median is 6.902 ms. This reproduces the reported 3-6 second magnitude on a representative body, without claiming to time the private avatar. In its separate profile, `_volume_sections` consumes 10.094 of 10.434 s, 96.74 percent of the entire `choose_body` call. Its `avatar_changed` callback consumes 10.383 s. Silhouette refresh/canvas fitting therefore cannot explain the bulk of this fixture's freeze. The empty garment isolates body setup and excludes existing-panel rebuilding. Full samples and profiles are in the companion evidence.

### Settings and ownership

| Existing input | Current behavior | Proposed treatment |
| --- | --- | --- |
| Point angle, height, ID | Avatar JSON; radians, 0-1 height, stable named/custom IDs | Keep IDs/representation; show degrees and physical height; drag edits these coordinates |
| Volume lower/upper | Normalized body bounds | Keep; show physical units in temporary advanced editing |
| Radius multiplier | Both ellipse dimensions together; UI range 0.1-5 | Preserve imported values; advanced fit adjustment, not the main wrap repair |
| Stored clearance | Normalized at generation | Preserve legacy interpretation; make new effective-clearance ownership explicit |
| `dd_clearance` | Scene setting, 5-300 mm, default 30 mm; shared by placement paths | Keep property unchanged; inherit it unless a new piece placement override is explicit |
| Record `flat` | Boolean, currently available from point right-click | Preserve; direct contextual Wrap / Flat before and after placement |
| Translation/rotation | Per-pattern post-wrap deltas | Preserve; validate the final transformed result |
| Record version | Circular v1, elliptical v2 | Explicitly version improved behavior; no unsolicited old-record migration |
| `panel_origin`, legacy `wrap_radius` | Existing origin/legacy builder behavior | Preserve; no builder-math edits |
| `placement_mode`, pattern names/order and BODICE/SLEEVES/SKIRT presets | LAYOUT/LEGACY dispatch; legacy front/back inference and preset targets | Preserve existing paths; no changes to protected `placement.place` |
| Scene units and mesh density | `unit_settings.scale_length`, scene `dd_spacing` and piece `mesh_density` affect coordinate conversion and face sampling | Preserve units/density semantics; certify existing faces, not hidden remeshing |
| Reference placement X/Y and placed flag | `dd_reference_x`, `dd_reference_y`, `dd_reference_placed` feed legacy initial positioning | Preserve legacy behavior; do not repurpose guide offsets as wrap controls |
| Body geometry/transform, evaluated modifiers and manual object pose | Influence extracted shape/frame; object movement is captured into arrangement deltas | Revision-aware fit/validation; preserve manual pose capture |
| Guide visibility, opacity | H and scene display settings | Preserve; display toggles never alter arrangement |
| Regenerate | Recomputes setup and resets point edits | Split nondestructive Refresh fit from destructive Reset points |
| Folded panels | Deliberately flat to retain creases | Retain and label this constraint |

Sources: `core.py:255`; `arrangement.py:177`, `:278`, `:385`, `:418`, `:449`; `arrangement_controls.py:239`; `ui.py:83`; `live_panels.py:33`, `:165`; `garment.py:156`; `minimal.py:259`, `:930`.

Version-2 resolution reads stored setup clearance, while scene clearance also invalidates caches. Changing the scene slider does not rewrite that stored value. Resolve this ownership rather than add another multiplier.

`live_panels.py:111 avatar_signature` uses evaluated transform, bounds, clearance and stored setup. Same-bounds geometry changes are absent from that signature. This is a source-verified invalidation gap, not proof that arbitrary skeletal pose-following already works. Preserve tested rigid/scale behavior and add explicit same-bounds deformation coverage.

## 3. Professional-tool evidence

Every vendor fact below has a public primary source. CLO and MD are related products, not independent confirmations of an algorithm.

| Documented behavior | Source | Fit for this project |
| --- | --- | --- |
| MD previews a selected pattern on point hover, places its center on click and permits later precise adjustment | [S1] | Adopt preview, preserve click-to-place, avoid a permanent inspector |
| MD arrangement properties include flat/curved shape, horizontal/vertical position, offset and orientation | [S2] | Adopt compact shape/offset/orientation controls |
| MD and CLO document default point size and curved/flat arrangement preference | [S3], [S4] | Adopt comfortable DPI-aware defaults; preferences are secondary |
| CLO points expose volume association, X/Y, offset and direction; symmetric points have an outer outline | [S5] | Retain volume association; use non-color-only states, not symmetry naming conventions |
| CLO volumes expose joint endpoints, cylinder/cuboid shapes, height and independent X/Y dimensions | [S6] | Independent ellipse width/depth fits; cuboids and joint-based replacement volumes do not |
| MD documents spiral placement of long pieces and Flip Wrap Direction | [S1] | Make direction/overwrap explicit; avoid whole-piece-width surprises |
| Browzwear has a preparation step with precise gizmos and piece grids before dressing | [S7] | Adopt inspectable preview within our existing ARRANGE stage, not a new stage |
| Browzwear warns that leg-cluster direction can cause body/panel collision, recommends Flat for a multi-panel hood and special preparation for an underarm gusset | [S8] | Make Flat/direction deliberate; do not promise one ellipse family represents every anatomical branch |

These sources do not disclose exact MD/CLO contour sampling or collision guarantees. They support interaction and control choices, not a claim that the proposed geometry reproduces proprietary algorithms. Difficult-shape guidance argues against promising universal automatic wrapping.

## 4. Proposed design

### Data shape

Keep avatar-owned volumes and garment-owned arrangement records. Extend versioned records with shape, clearance override-or-inherit, direction and explicit overwrap choice, alongside current point reference and pose delta. Keep stable volume/point IDs and edited coordinates. Runtime interaction has one state: idle, hover, pressed, dragging or numeric edit. A fitting job is pending, ready, cancelled or failed, tagged with body identity and geometry revision.

Do not persist hover, progress, preview meshes, BVHs or lookup tables in garment data. Temporary drag edits commit once with one undo step. Invalid fit results never become ready.

### Points and editing

- Use native uniform-color/polyline GPU primitives. Proposed 100 percent UI-scale sizes: 14 px normal disk, 18 px hover/active outline, invisible 32 px hit diameter. Scale with Blender UI scale.
- Differentiate idle, hover, bound-to-selected-piece and editing by outlines/fill/glyphs, not hue alone. Show labels only on hover/edit and emphasize only relevant volume rings.
- A short click still places. Under 4 logical pixels movement remains a click; beyond it begins point drag. Freeze point identity while dragging. Release commits once; Escape restores the exact setup and pose. Do not intercept navigation or unrelated editor input.
- Drag in the existing volume's angular/height coordinates, with continuous angle across the seam and Shift fine movement. Do not use unconstrained world-plane dragging or arbitrary shrinkwrap. Keep exact numeric degree/height entry.
- Hover previews the selected panel's actual proposed shape/orientation. Drag previews are temporary and throttled; they do not rewrite meshes or documents on each event. Preview and commit use the same geometric rule and show pending/error states explicitly.
- Keep cursor-anchored menus and temporary native numeric dialogs. Actions dismiss immediately. No sidebar, docked inspector or automatic selection popup. Preserve H/S/L and existing tool shortcuts.

### Wrap: improve the envelope, retain mapping

1. Extract evaluated geometry once per revision. Index triangle candidates for section planes instead of rescanning every triangle. Preserve connected-component/body-family selection to avoid merging adjacent limbs into torso fits.
2. Adapt the existing ellipse stack where the body escapes its interpolated envelope. Include triangle/vertex extrema and inter-volume gaps, not just a larger fixed plane count. The demonstrated protrusion must introduce a fitted constraint near 1.180 m.
3. Keep arc-length wrapping, consistent phase and outward frames. Share circumference tables by envelope/section revision with bounded interpolation error, not exact per-vertex height. Check geometric separation; equal radial inflation on an ellipse is not proof of equal surface clearance.
4. Validate final existing panel triangles against the actual body after pose deltas. Include containment, face intersections and clearance. Refine or conservatively expand affected envelope sections and revalidate the whole panel. Never call vertex-only success collision-free.
5. Detect overwrap using occupied row intervals and local circumference. Preview overlap, expose direction and require deliberate spiral/overwrap selection. Preserve legacy results. Check panel self-intersections too.
6. Keep topology, rest coordinates, sewing, pin/tack binding and cloth unchanged. If coarse faces cannot satisfy clearance without excessive distortion, report the density/shape limitation and retain the prior arrangement. Do not silently remesh, clip the pattern, flatten it or run cloth as a repair.

Default to body-checked Wrap. This is not cloth simulation or isometric conformance to arbitrary curvature. A single ellipse family cannot represent every armpit or hood branch. Unsupported geometry must be identified before commit. Flat is an explicit valid option, not automatic recovery.

### Flat and configuration

Expose Wrap / Flat in selected-piece and point-placement context menus; retain Arrange flat as a direct action. Switching shape preserves point reference, pose delta and selection. Hover preview reflects the choice before placement. No point reselection or angle guessing is required.

Primary controls are shape, distance from body and direction. Scene clearance remains inherited by default. Advanced fit editing offers start/end height, independent ellipse width/depth and Reset fit. Map legacy uniform multipliers equally to both dimensions on explicit upgrade. Keep placement offset separate from cloth collision settings.

Version old arrangements explicitly. Version-1/2 files retain their saved behavior until explicit upgrade, which preserves IDs/edits, retains legacy interpretation where needed and rolls back failed changes transactionally. Refresh fit preserves points; Reset points is separate. Garment library data still excludes avatar setup.

### Responsive selection

Return promptly with Preparing arrangement status. Coalesce duplicate jobs, cancel stale bodies and install only a matching body/revision result. Drawing must not trigger synchronous fitting through `ensure_volumes` while pending.

Use indexed geometry and bounded cooperative main-thread timer slices. Blender warns against Python-thread API use [S9] and provides modal/timer APIs [S10]. Scheduling one long loop on a timer is not nonblocking. A separate process on plain snapshot data is a fallback only if indexed cooperative fitting misses the budget.

Share fitted data across display, preview and placement. Invalidate for evaluated geometry changes even with identical bounds. Transform existing setup for rigid movement; refit deforming geometry. Preserve mesh identity and artist edits where valid.

## 5. Alternatives considered

| Alternative | Decision |
| --- | --- |
| Larger markers only | Reject as the whole solution; leaves drag, preview, wrap defects and stalls |
| More numeric sliders | Reject as the primary workflow; adds diagnosis burden and cannot restore missing envelope data |
| Fixed dense section count | Reject as correctness rule; features can still fall between planes and repeated scans cost more |
| Independent vertex shrinkwrap | Reject; replaces ellipse mapping, risks stretching/collapse and misses face interiors |
| New skeleton clusters/cuboids/placement engine | Reject for scope; replaces the structure the artist wants raised |
| Automatic Flat on failure | Reject; repeats the reported escape hatch and conceals invalid wrapping |
| Cloth-based placement repair | Reject; crosses protected simulation boundaries and makes placement nondeterministic |
| Permanent vendor-style inspectors | Reject; conflicts with canvas-first contextual UI |
| Thread the existing loop | Reject; Blender API safety and unbounded work remain [S9] |
| Adaptive ellipse envelope plus final body checks | Recommend; fixes demonstrated missing-envelope geometry while retaining the current system |

Independent fit, direction and preview have documented precedents [S1], [S2], [S5], [S6]. Collision certification and acceleration are this proposal's design, not attributed vendor algorithms.

## 6. Exact scope requiring formal artist approval

### Protected files: no edits requested

| Protected file | Areas remaining untouched |
| --- | --- |
| `devil_designer/garment.py` | Entire file, including `build_panels`, simulation loops/modifiers and sewing-spring formulations. Use its existing builder interface |
| `devil_designer/meshing.py` | Entire file, all CDT, topology and rest/UV output |
| `devil_designer/placement.py` | Entire file, `ray_body`, `place`, `normalized_target` and placement-frame math |
| `devil_designer/tack_binding.py` | Entire file and all binding/placement math |

Requested protected-file scope is the empty set. This is not permission to relocate locked algorithms into an editable module. The changes below raise the existing ellipse arrangement subsystem. If the established builder boundary is insufficient, return an amended scope rather than change it.

### Proposed arrangement-owned production scope

| File | Exact areas and purpose |
| --- | --- |
| `devil_designer/arrangement_controls.py` | `display_world_points`, `display_batches`, `projected_points`, `hit_point`, `draw_points`, `point_event`, arrangement pick/edit operators and registration. Marker states, picking, previews, drag and temporary menus |
| `devil_designer/ui_system.py` | Arrangement-only size, hit, outline and label tokens with DPI scaling. No unrelated redesign |
| `devil_designer/arrangement.py` | `_volume_sections`, `generate_volumes`, `_volume_validate`, `_volume_mesh`, `_volume_frame`, `ensure_volumes`, `_volume_resolve`, `resolve_point`, `upgrade_volumes`, `world_points`, `edit_point`, `edit_volume`. Indexed/adaptive fitting, revisioned jobs, edited-point retention and versioned setup |
| `devil_designer/ellipse_volumes.py` | `fit_section`, `volume_stack`, `section_at_height`, `directional_radius`, `resolve_ellipse`, `ellipse_ring`, `wrap_positions`. Improved existing envelope/mapping and local fit. Explicit placement-behavior approval is required for these areas |
| `devil_designer/live_panels.py` | `point_frame`, `position_panel`, `avatar_signature`, `sync`, `arrange_piece`, `avatar_changed`, `capture_updates`, registration/unregistration. Final validation, fit readiness and pose/cache lifecycle. No cloth, seam or binding changes |
| `devil_designer/panel_cache.py` | `panel_pose`, `wrapped_positions` and arrangement-only fit/table cache ownership. Complete geometry keys and bounded reuse. Keep `panel_output` mesh-hash semantics unchanged |
| `devil_designer/core.py` | `arrangement_record`, `validate_arrangement` and arrangement serialization/upgrade callers only. Explicit new record fields and compatibility |
| `devil_designer/editor.py` | `choose_body` and existing arrangement-event forwarding block. Responsive fit completion and drag routing only |
| `devil_designer/minimal.py` | Body-card rows, `REGENERATE_VOLUMES`, body-selection status and existing piece-context-menu construction. Refresh/Reset separation and contextual Wrap / Flat |
| `devil_designer/ui.py` | Arrangement-only RNA properties and registration/unregistration if needed for effective clearance/job state. No cloth-property changes |

New helpers stay in these arrangement-owned areas unless an amended file list is approved. No production edit occurs in Phase 1.

The later build's test scope is `tests/test_arrangement.py`, `tests/test_arrangement_volumes.py`, `tests/test_arrangement_records.py`, `tests/test_arrangement_display_source.py`, `tests/test_live_panels.py`, `tests/blender_ellipse.py`, `tests/gui_arrangement.py`, `tests/gui_arrangement_display.py`, `tests/gui_arrangement_performance.py`, `tests/gui_fast_flow.py` and `tests/gui_core_workflow.py`. Add the reproduction to an existing owning suite. If a new fixture/module is needed, name it in a scope amendment. Research tools are reproducibility inputs, never production imports.

## 7. Measurable build acceptance

These are proposed gates, not results achieved in Phase 1.

| Area | Required check |
| --- | --- |
| Demonstrated failure | Exact concave fixture, 15 mm spacing: zero body-intersecting triangles, zero inside vertices below negative 1 micrometre, no self-intersections and unchanged topology/index/rest coordinates. Validate faces, not just vertices |
| Clearance | Default 30 mm reaches at least 29 mm geometric separation on certified panel faces in the fixture. Report the distribution. No more than 15 mm unintended excess gap at the 95th percentile of predefined uniform rest-area samples |
| Shape preservation | Compare all mesh edges to rest lengths; report minimum/median/95th percentile/maximum. No zero-area/flipped faces and no fixture edge distortion above 15 percent. If clearance and distortion targets conflict, return to design review rather than relax them silently |
| Difficult shapes | Concave tab, asymmetric long bodice, tapered sleeve/cuff, annular/notched panel and multi-panel hood/gusset. Cover explicit Flat, direction, overwrap and unsupported-family warnings. Never auto-switch Wrap to Flat |
| Component continuity | Add close/disconnected torso/limb-shell fixtures with named expected body components. No unexpected component switch between adjacent sections; report chosen component and center/axis continuity before accepting the fit |
| Point size/readability | At 100 percent UI scale: normal diameter at least 14 px, hit diameter at least 32 px, hover/active outline at least 18 px. Test 100/150/200 percent scale and two working distances; marker-edge contrast at least 3:1 on light/dark body/background fixtures. States distinguishable in grayscale |
| Picking/drag | 100 percent correct identities on a deterministic target grid and crowded-point fixtures. Four-pixel drag threshold, no identity jumps, Shift fine movement supports 1 mm equivalent height changes, numeric entry supports 0.1 degree. Escape restores exact setup/pose; release makes one undo step |
| Click-to-place | Native input in active minimal workspace still places the selected piece with one click and retains selection. Sub-threshold jitter never edits the point. Right-click, H and existing shortcuts still work |
| Preview | Valid preview/committed vertices agree within 1 mm. Input-to-preview 95th percentile below 50 ms for a 5,000-vertex panel. No mesh rebuild on every pointer event. Pending checks visibly pending |
| Flat | One contextual action switches selected piece Wrap / Flat without point reselection. Before pose delta, planar within 1 micrometre. Preserve point, delta, selection, undo/redo and save/reload |
| Pose following | Existing translated/rotated/uniform/nonuniform-scale fixtures retain IDs and offsets. Preserve regression expectations within 0.1 mm and 0.1 degree. Add same-bounds deformation/shape-key invalidation and stale-job/body-switch tests |
| Selection responsiveness | Same hardware/fixtures: callback below 50 ms, target fitting slices no longer than 8 ms, input-event gap below 50 ms at the 95th percentile. Completion below 0.5 s for 17,856 triangles and below 1 s for 72,576. Five runs with work/error counts; measure actual event/redraw intervals too |
| Cached selection | Stored valid setup plus complete GUI callback below 50 ms, point edits unchanged. Display/orbit never regenerate volumes |
| Persistence | Old v1/v2 loads without unsolicited pose changes; explicit upgrade preserves IDs/edits/library separation; invalid JSON or interrupted fitting never replace valid setup |
| Shipping gates | All nine suites; every-mode/state real GUI drawing; complete DRAFT through KEEP scenarios; real packaged imports and Blender validation; Rule Zero token plus AST checks; dead-code/import/draw integrity; exact package/source match. Then artist acceptance, before PR/merge |

Performance budgets are targets requiring implementation measurements, not promised speedups. Phase 1 does not make the extension verified, built or ready for artist testing.

## 8. Verification and boundaries

The final background wrap run and full GUI run exit successfully; GUI errors are empty. Both research tools pass syntax, COMMENT-token and AST standalone-string checks. All package-source SHA-256 values match their pre-measurement values, and `git diff --check` passes. Existing unrelated modifications/untracked work remain untouched; this investigation does not verify them. Initial tool-only setup errors used a nonexistent document helper and an unregistered operator keyword; the tools were corrected to the existing `Session.add` API and normal minimal-editor invocation, then rerun successfully. Neither error required a production change.

No package was built or installed. The nine shipping suites were not run for this research-only phase. The artist's open scene was not selected, cleared, modified or saved. Repro scenes/logs stay in `scratch/` while diagnostic review is pending; afterward use the validated developer runner, not recursive shell deletion of shared scratch.

The original private avatar/panel were not supplied. The collision and full GUI timing use controlled synthetic fixtures. A permitted production-avatar regression set belongs in the build phase; its absence does not erase the reproduced defect.

## Public sources

Accessed November 2, 2026. All are vendor or Blender-project primary sources. Above, documented facts are separated from design judgments.

- [S1] Marvelous Designer, Arrange Pattern with Arrangement Points/Flip Wrap Direction, manual dated August 21, 2026: https://www.marvelousdesigner.com/en-au/manuals/articles/47358262924185
- [S2] Marvelous Designer, Arrangement Property Setting, May 29, 2025: https://support.marvelousdesigner.com/hc/en-us/articles/47358278939417-Arrangement-Property-Setting
- [S3] Marvelous Designer, 3D Above ver4.2.0, May 29, 2025: https://support.marvelousdesigner.com/hc/en-us/articles/47358402111769-3D-Above-ver4-2-0
- [S4] CLO, 3D, updated August 30, 2024: https://support.clo3d.com/hc/en-us/articles/360001547168-3D
- [S5] CLO, Add Arrangement Point, updated September 6, 2023: https://support.clo3d.com/hc/en-us/articles/115000430768-Add-Arrangement-Point
- [S6] CLO, Add/Edit Bounding Volume, updated August 24, 2024: https://support.clo3d.com/hc/en-us/articles/115000431228-Add-Edit-Bounding-Volume
- [S7] Browzwear, Preparing the Garment on the Avatar: https://help.browzwear.com/en/articles/13065742-preparing-the-garment-on-the-avatar
- [S8] Browzwear, Checking Clusters: https://help.browzwear.com/en/articles/13065741-checking-clusters
- [S9] Blender Python API, Python Threads are Not Supported: https://docs.blender.org/api/main/info_gotchas_threading.html
- [S10] Blender Python API, WindowManager modal-handler and event-timer APIs: https://docs.blender.org/api/current/bpy.types.WindowManager.html

## Investigation method

Throughput checkpoint: n/a, read-only production investigation. Measurement tools are allowed by the brief.

Model the Domain shaped the single interaction state and revision-tagged fitting job instead of independent flags. Prove It Works required real body/panel geometry, triangle overlaps and the actual GUI callback rather than treating source suspicion or mocked tests as proof.

Dispatch ledger: UI/settings explorer, `codex/gpt-6-luna`; geometry/lifecycle explorer, `codex/gpt-6-luna`. Runtime measurements, source research and proposal authorship are in-thread on `codex/gpt-6.1-sol`. Explorer analysis is not runtime evidence.

The final read-only architectural synthesis also ran on `codex/gpt-6-luna`. It corroborated the measured diagnosis and requested a distinction between conditional panel rebuilding and `sync`; this report already states the current conditional `garment.build_panels` behavior. It identified no missing Phase 1 deliverable. That synthesis is not an independent runtime rerun or proof of the future design.
