# DEVIL-DESIGNER Feature Idea Verdicts

| Idea | Verdict | Evidence (files / functions) | Effort | Protected-Math Risk |
| :--- | :--- | :--- | :---: | :--- |
| **1. Seam preview before commit** | **BUILD** | `devil_designer/design_tools.py` (`design_sew_click`), `devil_designer/draw.py` (`seams`), `devil_designer/editor.py` (`design_hit_edge`) | **S** | **NONE** |
| **2. Freeze a piece** | **BUILD WITH CHANGES** | `devil_designer/garment.py` (`build_simulation`, `keep_drape`, `generated`), `devil_designer/operators.py` (`DD_OT_simulate`) | **M** | **YES** (`garment.py` simulation setup) |
| **3. Layered sim passes** | **BUILD WITH CHANGES** | `devil_designer/garment.py` (`build_simulation`, `start_playback`), `devil_designer/core.py` (`Pattern`), `devil_designer/minimal.py` | **L** | **YES** (`garment.py` simulation pipeline) |
| **4. Mirror refresh** | **BUILD** | `devil_designer/construction.py` (`unfold`), `devil_designer/core.py` (`clone_pattern`, `clone_relationships`, `Pattern.features`) | **M** | **NONE** |
| **5. Collision precheck on Simulate** | **BUILD** | `devil_designer/operators.py` (`DD_OT_simulate`), `devil_designer/garment.py` (`compile_garment`), `devil_designer/placement.py` (`BVHTree.FromObject`) | **S** | **NONE** |
| **6. Seam repair** | **BUILD WITH CHANGES** | `devil_designer/core.py` (`prune_seams`, `validate_seams`, `commit`, `split_edge`), `devil_designer/editor.py` (`last_repairs`) | **M** | **YES** (`core.py` seam validation lifecycle) |
| **7. Placement nudge** | **BUILD WITH CHANGES** | `devil_designer/placement.py` (`place`), `AGENTS.md` (Minimal Contextual UX Contract), `devil_designer/ui.py` (`dd_clearance`) | **M** | **YES** (`placement.py` coordinate math) |
| **8. Reference photo behind 2D grid** | **ALREADY EXISTS** | `devil_designer/tracing.py` (`calibrate`, `calibrated_width`, `draw_reference`), `devil_designer/draw.py` (line 336), `tests/blender_tracing.py` | **S** | **NONE** |
| **9. Persistent undo** | **ALREADY EXISTS** | `devil_designer/history.py` (`store`, `restore`), `devil_designer/ui.py` (`Scene.dd_history`), `devil_designer/editor.py` (lines 45, 295, 542), `tests/test_history.py` | **S** | **NONE** |

- **Duplicates / Exists:** #8 (tracing & calibration) in `tracing.py`; #9 (persistent undo) in `history.py`.
- **False Premise (2 & 3):** Sewing springs cannot cross objects; baking to a collider breaks cross-piece seams unless pinned in-mesh or isolated by layer.
- **False Premise (6):** `split_edge` already remaps; auto-reattaching deleted seams to "nearest" edge is a flawed heuristic that misconnects anatomy.
- **False Premise (7):** Exposing per-piece clearance sliders violates `AGENTS.md` UX contract; must be a discrete contextual nudge action instead.
- **Recommended Build Order:** #1 Seam preview (S, high UX win) -> #5 Collision precheck (S, prevents blowups) -> #4 Mirror refresh (M, symmetry) -> #2 Piece freeze (M, drape foundation) -> #3 Layered passes (L, multi-garment outfits).
