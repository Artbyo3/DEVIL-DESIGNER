import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False


def internal_paths(workspace, send, click, screen, check):
    from devil_designer.core import Document, Session

    def drawn_line():
        workspace.clear_interaction_references()
        workspace.session = Session(Document())
        workspace.session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        workspace.persist()
        workspace.card_kind = None
        workspace.fit()
        workspace.choose_tool('INTERNAL')
        for point in ((.1, .1), (.3, .1), (.3, .4)):
            send('MOUSEMOVE', screen(point))
            click(screen(point))
        send('RET', screen((.2, .2)))
        pattern = workspace.session.document.patterns[0]
        check(len(pattern.paths) == 1 and len(pattern.paths[0].vertices) == 3, 'Internal tool draws a three-point line')
        return pattern

    def line_points():
        return [(round(v.x, 4), round(v.y, 4)) for v in workspace.session.document.patterns[0].paths[0].vertices]

    pattern = drawn_line()
    send('MOUSEMOVE', screen((.3, .1)))
    send('LEFTMOUSE', screen((.3, .1)))
    send('MOUSEMOVE', screen((.31, .11)))
    send('MOUSEMOVE', screen((.32, .12)))
    workspace.error_message = None
    workspace.renderer.draw(workspace)
    check(not workspace.error_message, 'a point drag on a drawn line draws while it moves')
    send('LEFTMOUSE', screen((.32, .12)), 'RELEASE')
    check(line_points() == [(.1, .1), (.32, .12), (.3, .4)], 'dragging a line point in the Internal tool moves it in place')
    check(not workspace.draft and workspace.tool == 'INTERNAL', 'moving a point starts no new line and keeps the Internal tool')
    send('DEL', screen((.32, .12)))
    check(len(workspace.session.document.patterns[0].paths[0].vertices) == 2, 'Delete removes the moved point without a tool switch')
    workspace.perform_action('UNDO')
    workspace.perform_action('UNDO')
    check(line_points() == [(.1, .1), (.3, .1), (.3, .4)], 'point move and delete undo back to the drawn line')

    pattern = drawn_line()
    send('MOUSEMOVE', screen((.3, .1)))
    click(screen((.3, .1)))
    check(len(workspace.draft) == 1 and math_close(workspace.draft[0], (.3, .1)), 'a plain click on a line point still starts a new line there')
    send('MOUSEMOVE', screen((.3, .3)))
    click(screen((.2, .3)))
    send('RET', screen((.2, .3)))
    check(len(workspace.session.document.patterns[0].paths) == 2, 'a line started on another line point finishes as before')

    pattern = drawn_line()
    along = (.16, .1)
    click(screen(along), 'RIGHTMOUSE')
    check(workspace.card_kind == 'INTERNAL_EDGE' and workspace.session.path == pattern.paths[0].id,
          'right-click anywhere along a line in the Internal tool opens its actions')
    workspace.card_kind = None
    workspace.choose_tool('SELECT')
    for fraction in (.03, .5, .97):
        workspace.session.clear_selection()
        click(screen((.1 + .2 * fraction, .104)))
        check(workspace.session.path == pattern.paths[0].id, f'a click {fraction:.0%} along the line selects it')
    workspace.choose_tool('INTERNAL')
    send('MOUSEMOVE', screen(along))
    send('LEFTMOUSE', screen(along))
    send('LEFTMOUSE', screen(along), 'RELEASE')
    send('LEFTMOUSE', screen(along), 'DOUBLE_CLICK')
    check(len(workspace.session.document.patterns[0].paths[0].vertices) == 4 and not workspace.draft,
          'double-click on a line in the Internal tool inserts a point')
    send('MOUSEMOVE', screen((.05, .3)))
    click(screen((.05, .3)))
    send('MOUSEMOVE', screen((.302, .402)))
    check(workspace.snap_marker and workspace.snap_marker[1] == 'POINT', 'drawing shows the snap target on a line point')
    workspace.error_message = None
    workspace.renderer.draw(workspace)
    check(not workspace.error_message, 'drawing with snap feedback renders')
    workspace.cancel_gesture()


def reference_images(workspace, send, click, screen, check):
    import math
    import tempfile
    from devil_designer import tracing
    from devil_designer.core import Document, Session
    from tools.workspace import prepare_scratch
    scene = bpy.context.scene
    folder = Path(tempfile.mkdtemp(prefix='references-', dir=prepare_scratch()))
    files = []
    for name, size in (('front.png', (8, 4)), ('back.png', (6, 3))):
        image = bpy.data.images.new(name, width=size[0], height=size[1], alpha=True)
        image.generated_color = (.8, .3, .2, 1)
        image.filepath_raw = str(folder / name)
        image.file_format = 'PNG'
        image.save()
        bpy.data.images.remove(image)
        files.append(str(folder / name))
    workspace.clear_interaction_references()
    workspace.session = Session(Document())
    workspace.session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
    workspace.persist()
    workspace.choose_tool('SELECT')
    check(bpy.ops.devil.load_trace_image(filepath=files[0]) == {'FINISHED'}, 'a reference image loads')
    scene.dd_trace_width, scene.dd_trace_x, scene.dd_trace_y, scene.dd_trace_rotation = .4, -.1, .05, 0.0
    workspace.fit()

    def world_center():
        corners = tracing.reference_corners(scene)
        return (sum(x for x, _ in corners) / 4, sum(y for _, y in corners) / 4)

    def drag(start, end, **modifiers):
        send('MOUSEMOVE', start, **modifiers)
        send('LEFTMOUSE', start, **modifiers)
        middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        send('MOUSEMOVE', middle, **modifiers)
        send('MOUSEMOVE', end, **modifiers)
        workspace.error_message = None
        workspace.renderer.draw(workspace)
        check(not workspace.error_message, 'the reference image draws while a placement handle is dragged')
        send('LEFTMOUSE', end, 'RELEASE', **modifiers)

    workspace.minimal_action('TRACE_DRAG')
    frame = workspace.trace_frame()
    check(workspace.trace_drag == 'ARMED' and frame is not None, 'Place on canvas shows a frame with handles around the image')
    workspace.error_message = None
    workspace.renderer.draw(workspace)
    check(not workspace.error_message, 'the placement frame draws')
    before_center = world_center()
    corner, center = frame['corners'][2], frame['center']
    drag(corner, (center[0] + (corner[0] - center[0]) * 1.5, center[1] + (corner[1] - center[1]) * 1.5))
    check(abs(scene.dd_trace_width - .6) < .004, 'dragging a corner scales the image directly')
    check(math.dist(world_center(), before_center) < 1e-3, 'corner scaling keeps the image centered')
    frame = workspace.trace_frame()
    knob, center = frame['knob'], frame['center']
    turned = (center[0] - (knob[1] - center[1]), center[1] + (knob[0] - center[0]))
    drag(knob, turned)
    check(abs(scene.dd_trace_rotation - 90) < 1, 'dragging the knob rotates the image directly')
    frame = workspace.trace_frame()
    knob, center = frame['knob'], frame['center']
    tilt = math.radians(37)
    offset = (knob[0] - center[0], knob[1] - center[1])
    drag(knob, (center[0] + offset[0] * math.cos(tilt) - offset[1] * math.sin(tilt),
                center[1] + offset[0] * math.sin(tilt) + offset[1] * math.cos(tilt)), shift=True)
    check(abs(scene.dd_trace_rotation % 15) < 1e-6 or abs(scene.dd_trace_rotation % 15 - 15) < 1e-6,
          'Shift snaps knob rotation to 15 degree steps')
    before = (scene.dd_trace_x, scene.dd_trace_y)
    center = workspace.trace_frame()['center']
    drag(center, (center[0] + 40, center[1] + 20))
    check(scene.dd_trace_x > before[0] and scene.dd_trace_y > before[1], 'dragging inside the image still moves it')
    send('ESC', center)
    check(workspace.trace_drag is None and workspace.trace_frame() is None, 'Escape finishes placement and hides the handles')
    scene.dd_trace_locked = True
    workspace.minimal_action('TRACE_DRAG')
    width = scene.dd_trace_width
    drag(center, (center[0] + 60, center[1]))
    check(workspace.trace_frame() is None and scene.dd_trace_width == width, 'a locked image shows no handles and does not move')
    scene.dd_trace_locked = False
    workspace.trace_drag = None
    placement = (scene.dd_trace_x, scene.dd_trace_y, scene.dd_trace_width, scene.dd_trace_rotation)
    check(bpy.ops.devil.load_trace_image(filepath=files[1]) == {'FINISHED'}, 'Replace image loads another file')
    check(scene.dd_trace_path == files[1] and (scene.dd_trace_x, scene.dd_trace_y, scene.dd_trace_width, scene.dd_trace_rotation) == placement,
          'replacing the image keeps its position, scale and rotation')
    scene.dd_trace_stack = json.dumps([dict(tracing.ENTRY_FIELDS, path=str(folder / 'moved-away.png'))])
    workspace.error_message = None
    workspace.renderer.draw(workspace)
    check('moved-away.png' in scene.dd_trace_error, 'a missing second image is reported, not skipped')
    send('TIMER', center)
    check('moved-away.png' in workspace.message, 'the missing image is announced on the canvas without opening the image menu')
    scene.dd_trace_stack = '[]'
    scene.dd_trace_path = ''
    workspace.renderer.draw(workspace)


def math_close(vertex, point):
    return abs(vertex.x - point[0]) < 1e-6 and abs(vertex.y - point[1]) < 1e-6


def run():
    passed = []

    def check(ok, label):
        if not ok:
            raise AssertionError(label)
        passed.append(label)

    try:
        import devil_designer
        from devil_designer import editor
        devil_designer.register()
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace = editor._active
            check(workspace is not None, 'pattern editor opens')

            def send(kind, point, value='PRESS', **modifiers):
                return workspace.handle_event(bpy.context, SimpleNamespace(
                    type=kind, value=value, mouse_x=point[0] + region.x, mouse_y=point[1] + region.y,
                    ctrl=modifiers.get('ctrl', False), shift=modifiers.get('shift', False), alt=modifiers.get('alt', False)))

            def click(point, kind='LEFTMOUSE'):
                send(kind, point)
                send(kind, point, 'RELEASE')

            def screen(point):
                return workspace.view.screen(point, workspace.canvas_layout.canvas)

            internal_paths(workspace, send, click, screen, check)
            reference_images(workspace, send, click, screen, check)
            workspace.cleanup()
        report = {'passed': passed}
    except Exception:
        report = {'passed': passed, 'error': traceback.format_exc()}
        traceback.print_exc()
    (ROOT / 'scratch').mkdir(exist_ok=True)
    (ROOT / 'scratch' / 'drafting_tools-report.json').write_text(json.dumps(report, indent=2))
    return None


bpy.app.timers.register(run, first_interval=2)
