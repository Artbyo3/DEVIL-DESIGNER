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
            workspace.cleanup()
        report = {'passed': passed}
    except Exception:
        report = {'passed': passed, 'error': traceback.format_exc()}
        traceback.print_exc()
    (ROOT / 'scratch').mkdir(exist_ok=True)
    (ROOT / 'scratch' / 'drafting_tools-report.json').write_text(json.dumps(report, indent=2))
    return None


bpy.app.timers.register(run, first_interval=2)
