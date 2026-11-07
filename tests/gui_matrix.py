from pathlib import Path
from types import SimpleNamespace
import json
import sys
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False
import devil_designer
from devil_designer import editor, garment, starters

REPORT = ROOT / 'scratch' / 'matrix-report.json'


def run():
    passed = []

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        passed.append(message)
        print('PASS:', message, flush=True)

    try:
        devil_designer.register()
        scene = bpy.context.scene
        scene.dd_spacing = .04
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=(0, 0, 1.2))
        body = bpy.context.object
        body.scale = (.18, .13, .4)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        scene.dd_avatar = body
        for obj in scene.objects:
            if obj.name in {'Cube', 'Camera', 'Light'}:
                obj.hide_set(True)
        area = next(item for item in bpy.context.screen.areas if item.type == 'VIEW_3D')
        region = next(item for item in area.regions if item.type == 'WINDOW')
        area.spaces.active.show_region_ui = False
        view = area.spaces.active.region_3d
        view.view_rotation = Vector((0, -1, 0)).to_track_quat('Z', 'Y')
        view.view_location = Vector((.5, 0, 1.2))
        view.view_distance = 2.4
        bpy.context.view_layer.update()
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            op = editor._active

            def event(kind, point, value='PRESS', **extra):
                data = dict(type=kind, value=value, mouse_x=point[0] + region.x, mouse_y=point[1] + region.y,
                            shift=False, ctrl=False, alt=False, unicode='')
                data.update(extra)
                return SimpleNamespace(**data)

            def drawn(label):
                op.error_message = None
                op.renderer.draw(op)
                check(not op.error_message, label + ' draws without error')

            def pixel(world):
                point = view3d_utils.location_3d_to_region_2d(region, view, Vector(world))
                check(point is not None and not op.canvas_layout.panel.contains(*point), 'target is visible in the 3D view')
                return tuple(point)

            def tap(point, kind='LEFTMOUSE'):
                op.handle_event(bpy.context, event('MOUSEMOVE', point, 'NOTHING'))
                op.handle_event(bpy.context, event(kind, point))
                op.handle_event(bpy.context, event(kind, point, 'RELEASE'))

            rect = op.canvas_layout.buttons['SEW'][0]
            middle = (rect.x + rect.w / 2, rect.y + rect.h / 2)
            check(not any(key.startswith('STRIP_') for key in op.make_layout().buttons), 'tool options stay hidden by default')
            def hover(point):
                op.handle_event(bpy.context, event('MOUSEMOVE', point, 'NOTHING'))
                if op.sub_pending:
                    op.sub_pending['due'] = 0
                    op.handle_event(bpy.context, event('MOUSEMOVE', point, 'NOTHING'))

            hover(middle)
            check(op.flyout == 'SEW' and any(key.startswith('STRIP_') for key in op.canvas_layout.buttons), 'hovering a tool opens its options')
            op.handle_event(bpy.context, event('LEFTMOUSE', middle))
            op.handle_event(bpy.context, event('LEFTMOUSE', middle, 'RELEASE'))
            check(op.tool == 'SEW', 'a click selects the tool')
            canvas_point = (op.canvas_layout.panel.x + op.canvas_layout.panel.w * .6, op.canvas_layout.panel.y + op.canvas_layout.panel.h * .5)
            hover(canvas_point)
            check(op.flyout is None, 'moving away closes the flyout')
            hover(middle)
            check(op.flyout == 'SEW', 'hovering the tool opens it again')
            op.handle_event(bpy.context, event('ESC', middle))
            hover(middle)
            check(op.flyout is None, 'Escape closes the options until the pointer leaves the tool')
            op.choose_tool('SELECT')
            op.reveal_3d()
            panel = op.canvas_layout.panel
            top = (panel.x + panel.w * .5, panel.y + panel.h - 12)
            op.pointer = top
            op.handle_event(bpy.context, event('LEFTMOUSE', top))
            op.handle_event(bpy.context, event('MOUSEMOVE', (top[0] - 120, top[1] - 40), 'NOTHING'))
            op.handle_event(bpy.context, event('LEFTMOUSE', (top[0] - 120, top[1] - 40), 'RELEASE'))
            moved = op.canvas_layout.panel
            check(abs(moved.x - (panel.x - 120)) < 2 and abs(moved.y - (panel.y - 40)) < 2, 'dragging the top bar moves the panel')
            edge = (moved.x, moved.y + moved.h * .5)
            op.handle_event(bpy.context, event('LEFTMOUSE', edge))
            op.handle_event(bpy.context, event('MOUSEMOVE', (edge[0] + 90, edge[1]), 'NOTHING'))
            op.handle_event(bpy.context, event('LEFTMOUSE', (edge[0] + 90, edge[1]), 'RELEASE'))
            sized = op.canvas_layout.panel
            check(abs(sized.w - (moved.w - 90)) < 2 and abs(sized.x - (moved.x + 90)) < 2, 'dragging a border resizes the panel')
            edge = (sized.x, sized.y + sized.h * .5)
            op.handle_event(bpy.context, event('LEFTMOUSE', edge))
            op.handle_event(bpy.context, event('MOUSEMOVE', (edge[0] + 4000, edge[1]), 'NOTHING'))
            op.handle_event(bpy.context, event('LEFTMOUSE', (edge[0] + 4000, edge[1]), 'RELEASE'))
            check(op.canvas_layout.panel.w >= 419 * op.canvas_layout.scale, 'the panel keeps a minimum size')
            kept = op.window_rect
            op.restore_canvas()
            op.reveal_3d()
            check(op.window_rect == kept, 'the 3D view reopens at the chosen panel size')
            op.session.document = starters.create_tank_starter(None, 'COTTON')
            op.session.selected = op.session.document.patterns[0].id
            op.persist()
            op.reveal_3d()
            check(op.perform_action('SIMULATE'), 'the tank simulates through the editor')
            bpy.ops.screen.animation_cancel(restore_frame=False)
            for frame in range(scene.frame_current + 1, scene.frame_current + 25):
                scene.frame_set(frame)
            op.enable_shaping(bpy.context)
            check(op.tool == 'SHAPE', 'Grab opens on the draped cloth')
            cloth = garment.generated(scene, 'simulation')[0]
            vertex = len(cloth.data.vertices) // 4
            op.shaping.mode = 'STEAM'
            op.brush_cloth(op.shaping, vertex, (0, 0, 1), False)
            op.brush_cloth(op.shaping, vertex, (0, 0, 1), True)
            check(len(op.pending_strokes) == 2 and not op.session.document.steam, 'strokes wait for Space')
            op.handle_event(bpy.context, event('SPACE', (region.width * .2, region.height * .5)))
            check(len(op.session.document.steam) == 2 and op.tool == 'SHAPE' and op.shaping.mode == 'STEAM',
                  'Steam records a stroke and stays in Grab')
            check(bool(garment.generated(scene, 'simulation')), 'Steam restarts the drape')
            bpy.ops.screen.animation_cancel(restore_frame=False)
            drawn('Steam')
            op.shaping.mode = 'PINCH'
            cloth = garment.generated(scene, 'simulation')[0]
            op.brush_cloth(op.shaping, vertex, (0, 0, 1), False)
            op.apply_strokes(bpy.context, op.shaping)
            check(len(op.session.document.steam) == 3, 'Pinch records a stroke')
            bpy.ops.screen.animation_cancel(restore_frame=False)
            op.shaping.mode = 'PIN'
            before = len(op.session.document.anchors)
            op.shaping.vertex = vertex
            op.pin_grabbed(bpy.context, op.shaping)
            check(len(op.session.document.anchors) == before + 1 and op.shaping.mode == 'PIN', 'Pin in Grab adds a pin and stays in Grab')
            bpy.ops.screen.animation_cancel(restore_frame=False)
            drawn('Pinned Grab')
            op.choose_tool('SELECT')
            piece = garment.generated(scene, 'simulation')[0]
            front = op.session.document.patterns[0].id
            paths = len(op.session.document.find(front).paths)
            op.minimal_action('PEN_GARMENT')
            check(op.tool == 'PEN' and op.pen_mode == 'GARMENT', 'Draw on garment starts from the Internal chooser')
            from devil_designer.piece_states import piece_indices
            from devil_designer import xpbd_live
            coordinates = xpbd_live.evaluated_points(bpy.context, piece)
            indices = piece_indices(piece)[front]
            nearest = sorted(indices, key=lambda index: coordinates[index][1])[:40]
            targets = [piece.matrix_world @ Vector(coordinates[index].tolist()) for index in (nearest[0], nearest[-1])]
            for target in targets:
                tap(pixel(target))
            check(len(op.pen_points) == 2, 'clicks on the cloth add line points')
            drawn('Draw on garment')
            op.handle_event(bpy.context, event('RET', pixel(targets[0])))
            drawn('Finished garment line')
            check(op.pen_mode is None, 'Enter finishes the line')
            check(sum(len(item.paths) for item in op.session.document.patterns) >= paths + 1, 'the garment line becomes an internal path')
            pieces = len(op.session.document.patterns)
            op.minimal_action('PEN_AVATAR')
            for world in ((-.06, 0, 1.28), (.06, 0, 1.28), (.06, 0, 1.12), (-.06, 0, 1.12)):
                tap(pixel(world))
            check(len(op.pen_points) == 4, 'clicks on the avatar add outline points: ' + op.message + ' ' + str(len(op.pen_points)) + ' ' + op.tool)
            op.handle_event(bpy.context, event('RET', pixel((0, 0, 1.2))))
            check(len(op.session.document.patterns) == pieces + 1, 'the avatar outline becomes a new piece')
            drawn('Avatar piece')
        REPORT.write_text(json.dumps(dict(passed=passed), indent=2), encoding='utf-8')
    except Exception:
        REPORT.write_text(json.dumps(dict(passed=passed, error=traceback.format_exc()), indent=2), encoding='utf-8')
    return None


(ROOT / 'scratch').mkdir(exist_ok=True)
bpy.app.timers.register(run, first_interval=2)
