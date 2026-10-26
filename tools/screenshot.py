"""One-command screenshot utility for Devil Designer inside Blender.

Usage:
  python tools/screenshot.py [--stage DRAFT|SEW|ARRANGE|SIMULATE] [--output filename.png] [--full]
"""
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BLENDER_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
if not os.path.exists(BLENDER_PATH):
    for p in [r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
              r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"]:
        if os.path.exists(p):
            BLENDER_PATH = p
            break

def capture(stage="DRAFT", output_name="screenshot_app.png", full_mode=False):
    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    full_path = build_dir / "screenshot_full_raw.png"
    rect_path = build_dir / "screenshot_rect.json"
    
    if full_path.exists():
        full_path.unlink()
    if rect_path.exists():
        rect_path.unlink()

    script = f"""
import sys, os, time, json
from pathlib import Path
import bpy

# Disable Blender splash screen immediately before window creation
bpy.context.preferences.view.show_splash = False

ROOT = Path(r'{str(ROOT)}')
sys.path.insert(0, str(ROOT))
import devil_designer
devil_designer.register()
from devil_designer.core import Session
from devil_designer import editor

# Hide default Blender scene objects (Cube, Light, Camera)
for obj in bpy.context.scene.objects:
    if obj.name in {{'Cube', 'Camera', 'Light'}}:
        obj.hide_set(True)

area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
area.spaces.active.show_region_ui = False
area.spaces.active.show_region_header = False
area.spaces.active.show_region_tool_header = False
region = next(r for r in area.regions if r.type == 'WINDOW')

# Maximize 3D Viewport to hide all other Blender editor panels (Outliner, Properties, Timeline)
try:
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
except Exception as e:
    print('Fullscreen area exception:', e)

# Re-fetch area and region after maximization
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')

with bpy.context.temp_override(area=area, region=region):
    bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    op = editor._active
    op.set_stage('{stage}')
    
    # Toggle full expanded mode if requested
    if {full_mode} and not op.full:
        op.toggle_full()
    
    # Create sample garments if empty
    if not op.session.document.patterns:
        s = Session()
        s.add([(0, 0), (.35, 0), (.35, .42), (0, .42)])
        s.add([(.45, 0), (.80, 0), (.80, .42), (.45, .42)])
        s.add([(.90, 0), (1.15, 0), (1.02, .35)])
        op.session = s
        op.persist()
        op.fit()
        
    p = op.canvas_layout.panel
    rect_data = {{
        'window_w': bpy.context.window.width,
        'window_h': bpy.context.window.height,
        'region_x': region.x,
        'region_y': region.y,
        'panel_x': p.x + region.x,
        'panel_y': p.y + region.y,
        'panel_w': p.w,
        'panel_h': p.h,
    }}
    (ROOT / 'build' / 'screenshot_rect.json').write_text(json.dumps(rect_data, indent=2))
    
    def do_shot():
        try:
            bpy.ops.screen.screenshot(filepath=r'{str(full_path)}')
            print('Screenshot taken.')
        except Exception as e:
            print('Screenshot error:', e)
        bpy.ops.wm.quit_blender()
        return None
        
    bpy.app.timers.register(do_shot, first_interval=1.2)
"""
    tmp_script = build_dir / "_tmp_shot.py"
    tmp_script.write_text(script, encoding="utf-8")
    
    cmd = [BLENDER_PATH, "--factory-startup", "--python", str(tmp_script)]
    print(f"Launching Blender to capture {stage} interface (splash disabled, clean viewport)...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if not full_path.exists():
        print("Failed to capture screenshot. Blender output:")
        print(res.stdout)
        print(res.stderr)
        return None
        
    try:
        rect = json.loads(rect_path.read_text(encoding="utf-8"))
        img = Image.open(full_path)
        win_w, win_h = img.size
        x = max(0, int(rect['panel_x']))
        w = min(win_w - x, int(rect['panel_w']))
        h = int(rect['panel_h'])
        y_bottom = int(rect['panel_y'])
        y_top = max(0, win_h - (y_bottom + h))
        
        margin = 4
        crop_box = (
            max(0, x - margin),
            max(0, y_top - margin),
            min(win_w, x + w + margin),
            min(win_h, y_top + h + margin)
        )
        cropped = img.crop(crop_box)
        
        out_app = build_dir / output_name
        cropped.save(out_app)
        print(f"Saved clean app screenshot: {out_app} ({cropped.size[0]}x{cropped.size[1]})")
        return out_app
    except Exception as e:
        print("Cropping error:", e)
        return full_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="DRAFT", choices=["DRAFT", "SEW", "ARRANGE", "SIMULATE"])
    parser.add_argument("--output", default="screenshot_app.png")
    parser.add_argument("--full", action="store_true", help="Capture in expanded full mode")
    args = parser.parse_args()
    capture(stage=args.stage, output_name=args.output, full_mode=args.full)
