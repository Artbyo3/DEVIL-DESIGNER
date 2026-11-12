import json
import math
import time
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
import bpy
import numpy as np
from mathutils import Quaternion

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False
state = dict(step=0, passed=[])
report = ROOT / 'scratch' / 'live_grab-report.json'


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    state['passed'].append(label)


def event(kind, point, value='PRESS', ctrl=False):
    region = state['region']
    return SimpleNamespace(type=kind, value=value, mouse_x=int(point[0] + region.x), mouse_y=int(point[1] + region.y),
                           ctrl=ctrl, shift=False, alt=False)


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


def cloth_pixel():
    from bpy_extras import view3d_utils
    from mathutils import Vector
    from devil_designer import xpbd_live
    points = xpbd_live.evaluated_points(bpy.context, state['simulation'])
    index = max(range(len(points)), key=lambda item: -points[item][1] - abs(points[item][2] - 1.25) - abs(points[item][0]))
    view = state['area'].spaces.active.region_3d
    return tuple(view3d_utils.location_3d_to_region_2d(state['region'], view, Vector(points[index].tolist())))


def track_motion(scene, depsgraph=None):
    from devil_designer import xpbd_live
    points = xpbd_live.evaluated_points(bpy.context, state['simulation'])
    if 'last' in state:
        state['motion'].append(float(np.linalg.norm(points - state['last'], axis=1).max()))
    state['last'] = points


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
    from devil_designer import garment, xpbd
    workspace = state['workspace']
    scene = state['scene']
    step = state['step']
    state['step'] += 1
    with override():
        if step == 0:
            button('SIMULATE')
            check(bpy.context.screen.is_animation_playing, 'Simulate starts endless playback')
            state['simulation'] = garment.generated(scene, 'simulation')[0]
            return 2.5
        if step == 1:
            view = state['area'].spaces.active.region_3d
            view.view_rotation = Quaternion((1, 0, 0), math.pi / 2)
            view.view_location = (.45, 0, 1.2)
            view.view_distance = 2.6
            view.update()
            placed = view.view_location.copy(), view.view_rotation.copy(), view.view_distance
            button('SHAPE')
            check(workspace.tool == 'SHAPE' and not workspace.full, 'Grab tool reveals the 3D cloth')
            check(((view.view_location - placed[0]).length < 1e-6 and view.view_rotation.rotation_difference(placed[1]).angle < 1e-6
                   and abs(view.view_distance - placed[2]) < 1e-6), 'Grab tool leaves the camera where the artist placed it')
            handle = xpbd.input_slot(state['simulation'], 'Grab Handle').value
            check(not handle.visible_get(), 'grab handle is never visible')
            check(workspace.overlay_cache is not None or bpy.context.screen.is_animation_playing, 'overlay is cached during playback')
            state['overlay_time'] = workspace.overlay_cache_time = time.perf_counter()
            return .3
        if step == 2:
            check(workspace.overlay_cache_time > state['overlay_time'], 'the cached overlay refreshes within 0.3 s during playback')
            strip = workspace.shaping_controls_layout()
            check({'RADIUS_MINUS', 'RADIUS_PLUS'} <= set(strip), 'Grab controls are laid out')
            workspace.handle_event(bpy.context, event('MOUSEMOVE', center(strip['RADIUS_VALUE']), 'NOTHING'))
            radius = workspace.shaping.radius
            click(center(strip['RADIUS_PLUS']))
            check(workspace.shaping.radius > radius, 'radius plus enlarges the grab')
            click(center(strip['RADIUS_MINUS']))
            check(abs(workspace.shaping.radius - radius) < 1e-9, 'radius minus restores the grab')
            button('KEEP_OPTIONS')
            check(workspace.card_kind is not None, 'Keep options opens in the Grab tool')
            workspace.handle_event(bpy.context, event('ESC', cloth_pixel()))
            check(workspace.card_kind is None and workspace.tool == 'SHAPE', 'Escape closes a card and stays in Grab')
            zoomed = workspace.handle_event(bpy.context, event('WHEELUPMOUSE', cloth_pixel()))
            check(zoomed == {'PASS_THROUGH'} and abs(workspace.shaping.radius - radius) < 1e-9, 'wheel zooms the 3D view')
            workspace.handle_event(bpy.context, event('WHEELUPMOUSE', cloth_pixel(), ctrl=True))
            check(workspace.shaping.radius > radius, 'Ctrl+wheel changes grab radius')
            for mode in ('PUSH', 'PIN', 'PINCH', 'STEAM', 'PULL'):
                workspace.open_flyout('SHAPE')
                click(center(workspace.canvas_layout.buttons['STRIP_GRAB_' + mode][0]))
                check(workspace.shaping.mode == mode and workspace.tool == 'SHAPE' and workspace.flyout is None, 'flyout selects ' + mode.title() + ' and closes')
            return .2
        if step == 3:
            point = cloth_pixel()
            state['press'] = point
            workspace.handle_event(bpy.context, event('MOUSEMOVE', point, 'NOTHING'))
            workspace.handle_event(bpy.context, event('LEFTMOUSE', point))
            check(workspace.shaping.held, 'pressing the cloth grabs it')
            check(workspace.grab_ring_pixels() > 2, 'grab radius ring is sized from the radius')
            state['motion'] = []
            bpy.app.handlers.frame_change_post.append(track_motion)
            return .4
        if step == 4:
            bpy.app.handlers.frame_change_post.remove(track_motion)
            check(len(state['motion']) >= 3 and max(state['motion']) < .01, 'pressing the cloth does not shake it')
            point = state['press']
            workspace.handle_event(bpy.context, event('MOUSEMOVE', (point[0] + 40, point[1] + 30), 'NOTHING'))
            return 1.0
        if step == 5:
            workspace.handle_event(bpy.context, event('LEFTMOUSE', state['press'], 'RELEASE'))
            check(not workspace.shaping.held, 'releasing hands the cloth back')
            check(workspace.message.startswith('Released'), 'release is reported to the artist')
            return 1.0
        if step == 6:
            from devil_designer import xpbd_live
            point = cloth_pixel()
            moved = (point[0] + 30, point[1] + 20)
            workspace.handle_event(bpy.context, event('MOUSEMOVE', point, 'NOTHING'))
            workspace.handle_event(bpy.context, event('LEFTMOUSE', point))
            workspace.handle_event(bpy.context, event('MOUSEMOVE', moved, 'NOTHING'))
            workspace.handle_event(bpy.context, event('W', moved))
            check(not workspace.shaping.held and len(xpbd_live.pinned_vertices(state['simulation'])) > 0, 'W pins the held cloth while it simulates')
            workspace.handle_event(bpy.context, event('LEFTMOUSE', moved, 'RELEASE'))
            workspace.draw_overlay()
            check(not workspace.error_message and len(workspace.cloth_pin_pixels()) > 0, 'cloth pins are drawn during live simulation')
            view = state['area'].spaces.active.region_3d
            placed = view.view_location.copy(), view.view_rotation.copy(), view.view_distance
            pins = workspace.cloth_pin_pixels()
            check(pins and all(seen for _, seen in pins), 'pins on the side facing the artist draw at full strength: ' + str(pins))
            view.view_rotation = Quaternion((0, 0, 1), math.pi) @ Quaternion((1, 0, 0), math.pi / 2)
            view.view_location = (0, 0, 1.2)
            view.update()
            pins = workspace.cloth_pin_pixels()
            check(pins and not any(seen for _, seen in pins), 'pins behind the body are dimmed instead of drawing over it: ' + str(pins))
            workspace.draw_overlay()
            check(not workspace.error_message, 'dimmed pins draw without a render error')
            view.view_location, view.view_rotation, view.view_distance = placed
            view.update()
            return .6
        if step == 7:
            from devil_designer import xpbd_live
            point = cloth_pixel()
            workspace.handle_event(bpy.context, event('LEFTMOUSE', point, ctrl=True))
            workspace.handle_event(bpy.context, event('LEFTMOUSE', point, 'RELEASE', ctrl=True))
            check(not workspace.shaping.held, 'Ctrl+click does not grab the cloth')
            workspace.open_flyout('SHAPE')
            click(center(workspace.canvas_layout.buttons['STRIP_GRAB_UNPIN'][0]))
            check(len(xpbd_live.pinned_vertices(state['simulation'])) == 0 and workspace.tool == 'SHAPE', 'Remove pins frees every cloth pin and stays in Grab')
            workspace.choose_tool('SELECT')
            check(workspace.tool == 'SELECT', 'the artist leaves Grab')
            workspace.handle_event(bpy.context, event('Z', point, ctrl=True))
            check(len(xpbd_live.pinned_vertices(state['simulation'])) > 0, 'Ctrl+Z outside Grab brings the removed cloth pins back')
            workspace.handle_event(bpy.context, SimpleNamespace(**{**vars(event('Z', point, ctrl=True)), 'shift': True}))
            check(len(xpbd_live.pinned_vertices(state['simulation'])) == 0, 'Ctrl+Shift+Z outside Grab removes them again')
            check('"drape"' in state['scene'].dd_history, 'cloth pin steps are saved with the undo history in the Blender file')
            return .4
        if step == 8:
            workspace.draw_overlay()
            check(not workspace.error_message, 'editor draws without error during live simulation')
            button('SIMULATE')
            check(not bpy.context.screen.is_animation_playing, 'Pause stops playback')
            return .2
        button('KEEP')
        kept = garment.generated(scene, 'final')
        check(bool(kept), 'Keep bakes the grabbed drape')
        check(not workspace.error_message, 'editor stays clean after Keep')
        report.write_text(json.dumps(dict(passed=state['passed'])), encoding='utf-8')
        return None


def tick():
    try:
        if 'workspace' not in state:
            setup()
            return .3
        return advance()
    except Exception as failure:
        traceback.print_exc()
        report.write_text(json.dumps(dict(error=str(failure))), encoding='utf-8')
        return None


report.parent.mkdir(exist_ok=True)
bpy.app.timers.register(tick, first_interval=.5)
