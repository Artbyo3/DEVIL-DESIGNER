import cProfile
import io
import json
import math
import os
from pathlib import Path
import pstats
import statistics
import subprocess
import sys
import time
import traceback

import bpy
from mathutils import Quaternion


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workspace import prepare_scratch
import devil_designer
from devil_designer import arrangement, arrangement_controls, live_panels
from devil_designer.core import Session


def run():
    output = prepare_scratch()
    label = sys.argv[-1] if '--' in sys.argv else 'current'
    try:
        devil_designer.register()
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        parts = []
        for position, scale in (
                ((0, 0, 1.15), (.26, .15, .4)),
                ((0, 0, 1.7), (.12, .12, .16)),
                ((-.42, 0, 1.38), (.27, .08, .08)),
                ((.42, 0, 1.38), (.27, .08, .08)),
                ((-.13, 0, .45), (.105, .11, .45)),
                ((.13, 0, .45), (.105, .11, .45))):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, location=position)
            obj = bpy.context.object
            obj.scale = scale
            parts.append(obj)
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        avatar = bpy.context.object
        avatar.name = 'Arrangement performance avatar'
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        scene = bpy.context.scene
        scene.dd_avatar = avatar
        scene.dd_spacing = .035
        session = Session()
        for index in range(6):
            horizontal = index * .3
            session.add([(horizontal, 0), (horizontal + .25, 0), (horizontal + .25, .4), (horizontal, .4)])
        scene.dd_document = session.document.dumps()
        panels = live_panels.sync(bpy.context)
        arrangement.ensure_volumes(bpy.context)
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        area.spaces.active.shading.type = 'SOLID'
        area.spaces.active.overlay.show_floor = False
        view = area.spaces.active.region_3d
        view.view_location = (0, 0, .9)
        view.view_distance = 3.7
        view.view_perspective = 'PERSP'
        records = []
        draw_times = []
        original_draw = arrangement_controls.draw_points
        bpy.types.SpaceView3D.draw_handler_remove(arrangement_controls._draw_handle, 'WINDOW')
        def timed_draw():
            start = time.perf_counter()
            original_draw()
            draw_times.append((time.perf_counter() - start) * 1000)
        arrangement_controls._draw_handle = bpy.types.SpaceView3D.draw_handler_add(timed_draw, (), 'WINDOW', 'POST_PIXEL')
        with bpy.context.temp_override(area=area, region=region):
            points = arrangement.world_points(bpy.context)
            for repeat in range(3):
                for visible in (False, True):
                    scene.dd_reference_visible = visible
                    for index in range(12):
                        view.view_rotation = Quaternion((0, 0, 1), index * .018) @ Quaternion((1, 0, 0), 1.3)
                        view.update()
                        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                    frames = []
                    draw_times.clear()
                    cpu_start = time.process_time()
                    wall_start = time.perf_counter()
                    for index in range(120):
                        start = time.perf_counter()
                        view.view_rotation = Quaternion((0, 0, 1), index * math.tau / 120) @ Quaternion((1, 0, 0), 1.3)
                        view.update()
                        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                        frames.append((time.perf_counter() - start) * 1000)
                    elapsed = time.perf_counter() - wall_start
                    cpu = time.process_time() - cpu_start
                    gpu_snapshot = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,utilization.memory', '--format=csv,noheader'], capture_output=True, text=True, check=False).stdout.strip()
                    records.append(dict(repeat=repeat, display=visible, fps=120 / elapsed,
                                        mean_ms=statistics.mean(frames), median_ms=statistics.median(frames),
                                        p95_ms=sorted(frames)[113], cpu_core_percent=100 * cpu / elapsed,
                                        cpu_machine_percent=100 * cpu / elapsed / os.cpu_count(),
                                        draw_ms=statistics.mean(draw_times), gpu_snapshot=gpu_snapshot))
            scene.dd_reference_visible = True
            draw_profiler = cProfile.Profile()
            bpy.types.SpaceView3D.draw_handler_remove(arrangement_controls._draw_handle, 'WINDOW')
            def measured_draw():
                draw_profiler.enable()
                try:
                    arrangement_controls.draw_points()
                finally:
                    draw_profiler.disable()
            arrangement_controls._draw_handle = bpy.types.SpaceView3D.draw_handler_add(measured_draw, (), 'WINDOW', 'POST_PIXEL')
            for index in range(40):
                view.view_rotation = Quaternion((0, 0, 1), index * .04) @ Quaternion((1, 0, 0), 1.3)
                view.update()
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            profile_text = io.StringIO()
            pstats.Stats(draw_profiler, stream=profile_text).sort_stats('cumulative').print_stats(30)
            (output / f'arrangement-performance-{label}-profile.txt').write_text(profile_text.getvalue(), encoding='utf-8')
        result = dict(blender=bpy.app.version_string, avatar_vertices=len(avatar.data.vertices),
                      patterns=len(panels), points=len(points), volumes=len({point['volume'] for point in points}),
                      viewport=[region.width, region.height], logical_processors=os.cpu_count(), records=records)
        (output / f'arrangement-performance-{label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('ARRANGEMENT PERFORMANCE ' + json.dumps(result), flush=True)
    except Exception:
        (output / f'arrangement-performance-{label}-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        traceback.print_exc()
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(run, first_interval=2)
