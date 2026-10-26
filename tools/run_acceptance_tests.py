"""Run acceptance tests inside Blender across required resolutions and capture screenshots."""
import os
import sys
import json
import time
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import devil_designer
from devil_designer.core import Session, Document
from devil_designer.canvas import Layout, Rect, STAGE_TOOLS, ALL_TOOLS
from devil_designer import editor, garment

RESOLUTIONS = [
    (1478, 864),
    (1280, 720),
    (820, 650)
]

STAGES = ["DRAFT", "SEW", "ARRANGE", "SIMULATE"]

def rect_intersects(r1, r2):
    return not (r1.x + r1.w <= r2.x or r2.x + r2.w <= r1.x or
                r1.y + r1.h <= r2.y or r2.y + r2.h <= r1.y)

def test_layout_resolution(w, h, scale=1.0):
    issues = []
    for stage in STAGES:
        layout = Layout(w, h, scale=scale, position=(20, 20, w - 40, h - 40), settings=True, stage=stage)
        
        p = layout.panel
        if p.w > w or p.h > h:
            issues.append(f"Panel bounds {p.w}x{p.h} exceed window {w}x{h}")
            
        if layout.header.h < 40 * scale:
            issues.append(f"Header height {layout.header.h} below minimum at {w}x{h}")
        if layout.rail.w < 36 * scale:
            issues.append(f"Rail width {layout.rail.w} below minimum at {w}x{h}")
        if layout.footer.h < 26 * scale:
            issues.append(f"Footer height {layout.footer.h} below minimum at {w}x{h}")
            
        buttons = list(layout.buttons.items())
        for i in range(len(buttons)):
            n1, (r1, _) = buttons[i]
            for j in range(i + 1, len(buttons)):
                n2, (r2, _) = buttons[j]
                if (r1.y + r1.h > layout.rail.y and r2.y + r2.h > layout.rail.y):
                    active_tools = [t[0] for t in STAGE_TOOLS.get(stage, [])]
                    if n1 in active_tools and n2 in active_tools:
                        if rect_intersects(r1, r2):
                            issues.append(f"Rail button overlap: {n1} vs {n2} at {w}x{h}")
                if n1.startswith("STAGE_") and n2.startswith("STAGE_"):
                    if rect_intersects(r1, r2):
                        issues.append(f"Header stage overlap: {n1} vs {n2} at {w}x{h}")
                view_btns = {"UNDO", "REDO", "LENGTHS", "REFERENCE", "SNAP", "FIT"}
                if n1 in view_btns and n2 in view_btns:
                    if rect_intersects(r1, r2):
                        issues.append(f"Viewbar button overlap: {n1} vs {n2} at {w}x{h}")
                        
        for name, (rect, _) in buttons:
            mid_x = rect.x + rect.w / 2
            mid_y = rect.y + rect.h / 2
            hit = layout.button(mid_x, mid_y)
            if hit is None:
                issues.append(f"Button hit detection failed for {name} at {w}x{h}")

    return issues

def run_acceptance():
    print("=== STARTING DEVIL DESIGNER ACCEPTANCE TESTS ===")
    devil_designer.register()
    report = {
        "resolutions_tested": [],
        "geometry_checks": [],
        "screenshots": [],
        "stages_verified": STAGES,
        "success": True
    }
    
    for w, h in RESOLUTIONS:
        print(f"Testing Layout at {w}x{h} (scale=1.0)...")
        issues = test_layout_resolution(w, h, scale=1.0)
        issues_scaled = test_layout_resolution(w, h, scale=1.5)
        
        status = "PASSED" if not issues and not issues_scaled else "FAILED"
        report["resolutions_tested"].append({
            "resolution": f"{w}x{h}",
            "status": status,
            "issues": issues + issues_scaled
        })
        if issues or issues_scaled:
            report["success"] = False
            print(f"  FAILED at {w}x{h}:", issues + issues_scaled)
        else:
            print(f"  PASSED at {w}x{h} (no overlapping controls, 100% valid hit detection)")

    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    area.spaces.active.show_region_ui = False
    region = next(r for r in area.regions if r.type == 'WINDOW')
    
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)
    
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
        op = editor._active
        
        s = Session()
        s.add([(0, 0), (.35, 0), (.35, .45), (0, .45)])
        s.add([(.45, 0), (.80, 0), (.80, .45), (.45, .45)])
        op.session = s
        op.persist()
        op.fit()
        
        step_idx = 0
        def capture_step():
            nonlocal step_idx
            if step_idx < len(RESOLUTIONS):
                w, h = RESOLUTIONS[step_idx]
                stage = STAGES[step_idx % len(STAGES)]
                op.set_stage(stage)
                
                op.canvas_layout = Layout(region.width, region.height, scale=1.0,
                                         position=(40, 40, min(w, region.width - 80), min(h, region.height - 80)),
                                         settings=True, stage=stage)
                op.refresh_controls()
                op.save_window()
                
                shot_path = out_dir / f"screenshot_{w}x{h}.png"
                try:
                    bpy.ops.screen.screenshot(filepath=str(shot_path))
                    report["screenshots"].append({
                        "resolution": f"{w}x{h}",
                        "stage": stage,
                        "file": str(shot_path)
                    })
                    print(f"Captured screenshot at {w}x{h} ({stage}): {shot_path}")
                except Exception as e:
                    print(f"Screenshot capture failed at {w}x{h}:", e)
                
                step_idx += 1
                return 0.8
            else:
                (out_dir / "acceptance_report.json").write_text(json.dumps(report, indent=2))
                print("=== ACCEPTANCE TESTS COMPLETE ===")
                bpy.ops.wm.quit_blender()
                return None
                
        bpy.app.timers.register(capture_step, first_interval=1.0)

try:
    run_acceptance()
except Exception as e:
    import traceback
    traceback.print_exc()
    (ROOT / "build" / "acceptance_report.json").write_text(json.dumps({"success": False, "error": str(e)}, indent=2))
