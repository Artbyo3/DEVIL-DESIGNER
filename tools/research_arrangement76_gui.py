import cProfile
import io
import json
from pathlib import Path
import pstats
import statistics
import sys
import time
import traceback
import bpy

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import editor
from tools.workspace import prepare_scratch

output = prepare_scratch()
result = dict(blender=bpy.app.version_string, errors=[], fresh_seconds=[], cached_seconds=[], redraw_seconds=[])
devil_designer.register()


def measure():
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        parts = []
        for position, scale in (((0, 0, 1.15), (.26, .15, .4)), ((0, 0, 1.7), (.12, .12, .16)),
                                ((-.42, 0, 1.38), (.27, .08, .08)), ((.42, 0, 1.38), (.27, .08, .08)),
                                ((-.13, 0, .45), (.105, .11, .45)), ((.13, 0, .45), (.105, .11, .45))):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, location=position)
            body_part = bpy.context.object
            body_part.scale = scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            parts.append(body_part)
        bpy.ops.object.select_all(action='DESELECT')
        for body_part in parts:
            body_part.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        avatar = bpy.context.object
        avatar.data.calc_loop_triangles()
        result['vertices'] = len(avatar.data.vertices)
        result['triangles'] = len(avatar.data.loop_triangles)
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace = editor._active
            assert workspace is not None and workspace.minimal_ui
            for repeat in range(5):
                workspace.choose_body(None, bpy.context)
                if 'dd_arrangement_volumes' in avatar:
                    del avatar['dd_arrangement_volumes']
                started = time.perf_counter()
                workspace.choose_body(avatar, bpy.context)
                result['fresh_seconds'].append(time.perf_counter() - started)
                assert len(json.loads(avatar['dd_arrangement_volumes'])['volumes']) == 12
                redraw = time.perf_counter()
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                result['redraw_seconds'].append(time.perf_counter() - redraw)
                workspace.choose_body(None, bpy.context)
                started = time.perf_counter()
                workspace.choose_body(avatar, bpy.context)
                result['cached_seconds'].append(time.perf_counter() - started)
            workspace.choose_body(None, bpy.context)
            del avatar['dd_arrangement_volumes']
            profiler = cProfile.Profile()
            profiler.runcall(workspace.choose_body, avatar, bpy.context)
            profile_text = io.StringIO()
            pstats.Stats(profiler, stream=profile_text).sort_stats('cumulative').print_stats(24)
            result['profile'] = profile_text.getvalue()
            result['median_fresh_seconds'] = statistics.median(result['fresh_seconds'])
            result['median_cached_seconds'] = statistics.median(result['cached_seconds'])
    except Exception:
        result['errors'].append(traceback.format_exc())
    finally:
        (output / 'issue76-gui-evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('ISSUE76 GUI ' + json.dumps(result), flush=True)
        bpy.ops.wm.quit_blender()


bpy.app.timers.register(measure, first_interval=2)
