import json
import math
from pathlib import Path
import sys
import time
import traceback
from types import SimpleNamespace
import bpy
import numpy as np
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False
state = dict(step=0, passed=[], metrics={}, frames=[])
report = ROOT / 'scratch' / 'live_brush-report.json'
STROKE_HALF = .08
HEM_GAP = .06
BACK_DEPTH = .02
STROKE_STEPS = 17


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    state['passed'].append(label)


def event(kind, point, value='PRESS', ctrl=False, shift=False):
    region = state['region']
    return SimpleNamespace(type=kind, value=value, mouse_x=int(point[0] + region.x), mouse_y=int(point[1] + region.y),
                           ctrl=ctrl, shift=shift, alt=False)


def click(point):
    workspace = state['workspace']
    workspace.handle_event(bpy.context, event('LEFTMOUSE', point))
    workspace.handle_event(bpy.context, event('LEFTMOUSE', point, 'RELEASE'))


def button(key):
    workspace = state['workspace']
    workspace.canvas_layout = workspace.make_layout()
    rect = workspace.canvas_layout.buttons[key][0]
    click((rect.x + rect.w / 2, rect.y + rect.h / 2))


def center(rect):
    return rect.x + rect.w / 2, rect.y + rect.h / 2


def override():
    return bpy.context.temp_override(window=state['window'], area=state['area'], region=state['region'], screen=state['window'].screen)


def snapshot():
    from devil_designer import xpbd_live
    return xpbd_live.evaluated_points(bpy.context, state['simulation']).astype(np.float64)


def stroke_pixels():
    from bpy_extras import view3d_utils
    points = snapshot()
    height = points[:, 2].min() + HEM_GAP
    index = max(range(len(points)), key=lambda item: -points[item][1] - abs(points[item][2] - height) - abs(points[item][0]))
    middle = state['simulation'].matrix_world @ Vector(points[index].tolist())
    view = state['area'].spaces.active.region_3d
    ends = [view3d_utils.location_3d_to_region_2d(state['region'], view, middle + Vector((side * STROKE_HALF, 0, 0))) for side in (-1, 1)]
    return [tuple(ends[0].lerp(ends[1], step / (STROKE_STEPS - 1))) for step in range(STROKE_STEPS)]


def reach(points, line):
    nearest = np.full(len(points), np.inf)
    for first, second in zip(line[:-1], line[1:]):
        span = second - first
        share = np.clip((points - first) @ span / max(span @ span, 1e-12), 0, 1)
        nearest = np.minimum(nearest, np.linalg.norm(points - (first + share[:, None] * span), axis=1))
    return nearest


def count_frame(scene, depsgraph=None):
    state['frames'].append(time.perf_counter())


def frames_per_second():
    frames = state['frames']
    rate = (len(frames) - 1) / (frames[-1] - frames[0]) if len(frames) > 1 else 0.0
    state['frames'] = []
    return rate


def choose(mode):
    workspace = state['workspace']
    workspace.open_flyout('SHAPE')
    click(center(workspace.canvas_layout.buttons['STRIP_GRAB_' + mode][0]))
    check(workspace.shaping.mode == mode and workspace.tool == 'SHAPE' and workspace.flyout is None, 'flyout selects ' + mode.title())


def press_stroke():
    workspace = state['workspace']
    state['path'] = stroke_pixels()
    state['line'] = []
    state['cursor'] = 1
    state['before'] = snapshot()
    workspace.handle_event(bpy.context, event('MOUSEMOVE', state['path'][0], 'NOTHING'))
    workspace.handle_event(bpy.context, event('LEFTMOUSE', state['path'][0]))
    check(workspace.shaping.brushing and not workspace.shaping.held, workspace.shaping.mode.title() + ' press starts a stroke without grabbing')
    check(bpy.context.screen.is_animation_playing, workspace.shaping.mode.title() + ' stroke runs on the playing drape')


def stroke_step():
    from devil_designer import xpbd
    workspace = state['workspace']
    if state['cursor'] >= len(state['path']):
        return False
    workspace.handle_event(bpy.context, event('MOUSEMOVE', state['path'][state['cursor']], 'NOTHING'))
    state['line'].append(np.array(tuple(xpbd.input_slot(state['simulation'], 'Brush End').value), dtype=np.float64))
    state['cursor'] += 1
    return True


def release_stroke():
    from devil_designer import xpbd
    workspace = state['workspace']
    workspace.handle_event(bpy.context, event('LEFTMOUSE', state['path'][-1], 'RELEASE'))
    check(not workspace.shaping.brushing, workspace.shaping.mode.title() + ' release ends the stroke')
    check(tuple(xpbd.input_slot(state['simulation'], 'Brush Shape').value)[1] == 0.0, workspace.shaping.mode.title() + ' release switches the brush off in the solver')
    workspace.draw_overlay()
    check(not workspace.error_message, workspace.shaping.mode.title() + ' brush draws without error')


def setup():
    import devil_designer
    from devil_designer import editor
    devil_designer.register()
    window = bpy.context.window_manager.windows[0]
    area = next(item for item in window.screen.areas if item.type == 'VIEW_3D')
    region = next(item for item in area.regions if item.type == 'WINDOW')
    state.update(window=window, area=area, region=region, scene=bpy.context.scene)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.dd_spacing = .03
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    with override():
        check('FINISHED' in bpy.ops.devil_designer.demo(), 'demo garment created')
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    state['workspace'] = editor._active
    check(state['workspace'] is not None, 'pattern editor opens')


def advance():
    from devil_designer import garment, xpbd_live
    workspace = state['workspace']
    scene = state['scene']
    metrics = state['metrics']
    step = state['step']
    state['step'] += 1
    with override():
        if step == 0:
            button('SIMULATE')
            state['simulation'] = garment.generated(scene, 'simulation')[0]
            return 2.0
        if step == 1:
            view = state['area'].spaces.active.region_3d
            view.view_rotation = Quaternion((1, 0, 0), math.pi / 2)
            view.view_location = (.45, 0, 1.2)
            view.view_distance = 2.6
            view.update()
            button('SHAPE')
            hanging = snapshot()
            check(xpbd_live.pin_cloth(state['simulation'], np.flatnonzero(hanging[:, 2] > hanging[:, 2].max() - .04), hanging) > 0, 'shoulders are pinned so the drape hangs still')
            choose('FOLD')
            strip = workspace.shaping_controls_layout()
            check({'STRENGTH_MINUS', 'STRENGTH_VALUE', 'STRENGTH_PLUS', 'RADIUS_MINUS', 'RADIUS_PLUS'} <= set(strip), 'brush strip lays out radius and strength')
            workspace.handle_event(bpy.context, event('MOUSEMOVE', center(strip['STRENGTH_VALUE']), 'NOTHING'))
            strength = workspace.shaping.strength
            click(center(strip['STRENGTH_PLUS']))
            check(workspace.shaping.strength > strength, 'strength plus strengthens the brush')
            click(center(strip['STRENGTH_MINUS']))
            check(abs(workspace.shaping.strength - strength) < 1e-9, 'strength minus restores the brush')
            workspace.handle_event(bpy.context, event('WHEELUPMOUSE', center(strip['STRENGTH_VALUE']), ctrl=True, shift=True))
            check(workspace.shaping.strength > strength, 'Ctrl+Shift+wheel changes brush strength')
            workspace.draw_overlay()
            check(not workspace.error_message, 'brush strip draws without error')
            metrics.update(vertices=len(state['simulation'].data.vertices), strength=workspace.shaping.strength, radius=workspace.shaping.radius)
            bpy.app.handlers.frame_change_post.append(count_frame)
            return 1.5
        if step == 2:
            state['frames'] = []
            state['calm_start'] = snapshot()
            return 1.4
        if step == 3:
            state['calm'] = np.linalg.norm(snapshot() - state['calm_start'], axis=1)
            metrics['idle_fps'] = frames_per_second()
            press_stroke()
            return .06
        if step == 4:
            if stroke_step():
                state['step'] -= 1
                return .06
            return .3
        if step == 5:
            metrics['fold_stroke_fps'] = frames_per_second()
            release_stroke()
            after = snapshot()
            line = state['line']
            unit = max(1e-6, scene.unit_settings.scale_length)
            radius = workspace.shaping.radius / unit
            start = reach(state['before'], line)
            near = (start > radius * .2) & (start < radius * .8)
            far = (start > radius * 4) & (state['before'][:, 1] > BACK_DEPTH / unit)
            feed = (start > radius * 4) & ~far
            state.update(near=near, start=start)
            moved = np.linalg.norm(after - state['before'], axis=1)
            metrics.update(near_vertices=int(near.sum()), far_vertices=int(far.sum()),
                           fold_gathered_m=float((start - reach(after, line))[near].mean() * unit),
                           fold_far_moved_m=float(np.median(moved[far]) * unit), fold_far_moved_max_m=float(moved[far].max() * unit),
                           fold_feed_moved_m=float(np.median(moved[feed]) * unit),
                           calm_far_moved_m=float(np.median(state['calm'][far]) * unit), calm_far_moved_max_m=float(state['calm'][far].max() * unit))
            check(near.sum() >= 4 and far.sum() >= 4, 'stroke has cloth near it and far from it')
            check(metrics['fold_gathered_m'] > .003, 'Fold draws the cloth near the stroke toward the stroke line')
            check(metrics['fold_far_moved_m'] < metrics['fold_gathered_m'] / 2, 'Fold moves far cloth far less than the cloth under the brush')
            return 1.0
        if step == 6:
            unit = max(1e-6, scene.unit_settings.scale_length)
            metrics['fold_kept_after_1s_m'] = float((state['start'] - reach(snapshot(), state['line']))[state['near']].mean() * unit)
            choose('SWEEP')
            state['frames'] = []
            press_stroke()
            return .06
        if step == 7:
            if state['cursor'] == STROKE_STEPS // 2 and 'pinned' not in state:
                workspace.handle_event(bpy.context, event('W', state['path'][state['cursor']]))
                state['pinned'] = xpbd_live.pinned_vertices(state['simulation'])
                state['pinned_at'] = snapshot()[state['pinned']]
                check(len(state['pinned']) > 0 and workspace.shaping.brushing, 'W pins cloth under the brush and the stroke continues')
            if stroke_step():
                state['step'] -= 1
                return .06
            return .3
        metrics['sweep_stroke_fps'] = frames_per_second()
        bpy.app.handlers.frame_change_post.remove(count_frame)
        release_stroke()
        after = snapshot()
        line = state['line']
        unit = max(1e-6, scene.unit_settings.scale_length)
        radius = workspace.shaping.radius / unit
        start = reach(state['before'], line)
        near = start < radius * .8
        near[state['pinned']] = False
        far = (start > radius * 4) & (state['before'][:, 1] > BACK_DEPTH / unit)
        heading = line[-1] - line[0]
        heading /= np.linalg.norm(heading)
        moved = after - state['before']
        metrics.update(sweep_carried_m=float((moved[near] @ heading).mean() * unit),
                       sweep_far_moved_m=float(np.median(np.linalg.norm(moved[far], axis=1)) * unit),
                       pinned_vertices=int(len(state['pinned'])),
                       pinned_drift_m=float(np.linalg.norm(after[state['pinned']] - state['pinned_at'], axis=1).max() * unit))
        check(metrics['sweep_carried_m'] > .003, 'Sweep carries the cloth near the stroke along the stroke')
        check(metrics['sweep_far_moved_m'] < metrics['sweep_carried_m'] / 2, 'Sweep moves far cloth far less than the cloth under the brush')
        check(metrics['pinned_drift_m'] < .002, 'cloth pinned during the stroke stays pinned while the brush keeps working')
        report.write_text(json.dumps(dict(passed=state['passed'], metrics=metrics)), encoding='utf-8')
        return None


def tick():
    try:
        if 'workspace' not in state:
            setup()
            return .3
        return advance()
    except Exception as failure:
        traceback.print_exc()
        report.write_text(json.dumps(dict(error=str(failure), passed=state['passed'], metrics=state['metrics'])), encoding='utf-8')
        return None


report.parent.mkdir(exist_ok=True)
bpy.app.timers.register(tick, first_interval=.5)
