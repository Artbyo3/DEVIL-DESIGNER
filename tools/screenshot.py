import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from PIL import Image

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workspace import prepare_scratch
from tools.check_comments import check_source
BLENDER_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
if not os.path.exists(BLENDER_PATH):
    for p in [r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
              r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"]:
        if os.path.exists(p):
            BLENDER_PATH = p
            break

def capture(stage="DRAFT", output_name="screenshot_app.png", full_mode=False,
            empty=False, panel_size=None, demo=False, tool=None, section=None, query='', reveal_3d=False, cursor_controls=False, card_kind=None, trace_image=False):
    if Path(output_name).name != output_name or Path(output_name).suffix.lower() != ".png":
        raise ValueError("Screenshot output must be a PNG filename inside scratch.")
    scratch_dir = prepare_scratch()
    full_path = scratch_dir / "screenshot_full_raw.png"
    rect_path = scratch_dir / "screenshot_rect.json"
    
    if full_path.exists():
        full_path.unlink()
    if rect_path.exists():
        rect_path.unlink()

    script = f"""
import sys, os, time, json
from pathlib import Path
import bpy

bpy.context.preferences.view.show_splash = False

sys.dont_write_bytecode = True
ROOT = Path(r'{str(ROOT)}')
sys.path.insert(0, str(ROOT))
import devil_designer
devil_designer.register()
from devil_designer.core import Session
from devil_designer import editor

for obj in bpy.context.scene.objects:
    if obj.name in {{'Cube', 'Camera', 'Light'}}:
        obj.hide_set(True)

area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
area.spaces.active.show_region_ui = False
area.spaces.active.show_region_header = False
area.spaces.active.show_region_tool_header = False
region = next(r for r in area.regions if r.type == 'WINDOW')

try:
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
except Exception as e:
    print('Fullscreen area exception:', e)

area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')

with bpy.context.temp_override(area=area, region=region):
    bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    op = editor._active
    op.set_stage('{stage}')
    if {trace_image}:
        image = bpy.data.images.new('Tracing verification', width=64, height=64)
        image.pixels = [value for row in range(64) for column in range(64)
                        for value in ((.2, .55, .8, 1) if 12 < column < 52 and 8 < row < 56 else (.85, .8, .7, 1))]
        image.filepath_raw = str(ROOT / 'scratch' / 'tracing-verification.png')
        image.file_format = 'PNG'
        image.save()
        bpy.context.scene.dd_trace_path = image.filepath_raw
        bpy.context.scene.dd_trace_width = 1.2
        bpy.context.scene.dd_trace_x = 0
        bpy.context.scene.dd_trace_y = -.2
        bpy.context.scene.dd_trace_opacity = .6
    
    if {full_mode} and not op.full:
        op.toggle_full()

    if {panel_size is not None}:
        from devil_designer.canvas import Rect
        op.full = False
        panel = op.canvas_layout.panel
        requested_size = {panel_size!r}
        op.set_window(Rect(panel.x, panel.y, requested_size[0], requested_size[1]))

    if {demo}:
        op.workflow_action('DEMO')
        if op.session.document.patterns:
            op.session.selected = op.session.document.patterns[0].id
            op.sync_selection()
    
    if not {empty} and not op.session.document.patterns:
        s = Session()
        s.add([(0, 0), (.35, 0), (.35, .42), (0, .42)])
        s.add([(.45, 0), (.80, 0), (.80, .42), (.45, .42)])
        s.add([(.90, 0), (1.15, 0), (1.02, .35)])
        op.session = s
        op.persist()
        op.fit()

    if {tool!r}:
        op.choose_tool({tool!r})
    if {section!r}:
        if op.minimal_ui:
            op.show_card({{'DESIGN': 'EDIT', 'AVATAR': 'GARMENT', 'SEW': 'SEWING', 'CLOTH': 'SIMULATE', 'LIBRARY': 'LIBRARY'}}[{section!r}])
        else:
            op.open_section({section!r})
    if {query!r}:
        op.settings_open = not op.minimal_ui
        op.canvas_layout = op.make_layout()
        op.search_query = {query!r}
        op.inspector_scroll = 0
    if {reveal_3d!r}:
        op.reveal_3d()
        from mathutils import Vector
        area.spaces.active.region_3d.view_rotation = Vector((0, -1, 0)).to_track_quat('Z', 'Y')
        area.spaces.active.region_3d.view_location = Vector((.65, 0, 1.2))
        area.spaces.active.region_3d.view_distance = 2.8
    if {cursor_controls!r}:
        canvas = op.canvas_layout.canvas
        if op.session.document.patterns:
            op.pointer = op.view.screen(op.session.document.patterns[0].points[0], canvas)
        else:
            op.pointer = (canvas.x + canvas.w / 2, canvas.y + canvas.h / 2)
        op.show_card('POINT')
    if {card_kind!r}:
        canvas = op.canvas_layout.canvas
        anchor = (canvas.x + canvas.w * .68, canvas.y + canvas.h * .62)
        if {card_kind!r} == 'SEAM' and op.session.document.seams:
            badge, identity, label = op.seam_badges()[0]
            op.seam_selected = identity
            anchor = (badge.x + badge.w + 6 * op.canvas_layout.scale, badge.y + badge.h)
        if {card_kind!r} in {{'SIMULATE', 'KEEP'}}:
            button = op.canvas_layout.buttons[{card_kind!r} + '_OPTIONS'][0]
            anchor = (button.x, button.y + button.h)
        op.show_card({card_kind!r}, anchor)
    if not {cursor_controls!r}:
        op.pointer = (-100, -100)
    op.refresh_controls()
        
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
    (ROOT / 'scratch' / 'screenshot_rect.json').write_text(json.dumps(rect_data, indent=2))
    
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
    tmp_script = scratch_dir / "_tmp_shot.py"
    check_source(script, str(tmp_script))
    tmp_script.write_text(script, encoding="utf-8")
    
    cmd = [BLENDER_PATH, "--factory-startup", "--python", str(tmp_script)]
    print(f"Launching Blender to capture {stage} interface (splash disabled, clean viewport)...")
    res = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    
    if not full_path.exists():
        print("Failed to capture screenshot. Blender output:")
        print(res.stdout)
        print(res.stderr)
        return None
        
    try:
        rect = json.loads(rect_path.read_text(encoding="utf-8"))
        img = Image.open(full_path)
        img.save(scratch_dir / (Path(output_name).stem + '_workspace.png'))
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
        
        out_app = scratch_dir / output_name
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
