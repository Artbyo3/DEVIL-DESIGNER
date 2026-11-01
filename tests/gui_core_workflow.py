import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False


def run():
    passed = []

    def check(ok, label):
        if not ok:
            raise AssertionError(label)
        passed.append(label)

    try:
        import devil_designer
        from devil_designer import editor, garment
        from devil_designer.core import Document, Session

        devil_designer.register()
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        scene = bpy.context.scene

        body = scene.objects.get('Cube')
        if not body:
            bpy.ops.mesh.primitive_cube_add()
            body = bpy.context.object
            body.name = 'Cube'
        scene.dd_avatar = body
        scene.dd_spacing = 0.04

        def cleanup_garments():
            garment.stop(bpy.context)
            for obj in list(scene.objects):
                if obj.get('dd_kind') in {'final', 'simulation', 'anchor', 'panel'}:
                    bpy.data.objects.remove(obj, do_unlink=True)
            scene.frame_set(scene.frame_start)

        cleanup_garments()

        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace = editor._active
            check(workspace is not None and not workspace._closed, 'pattern editor active with minimal UI')
            check(workspace.minimal_ui, 'minimal UI is active')

            def event(kind, point, value='PRESS'):
                return SimpleNamespace(type=kind, value=value, mouse_x=point[0] + region.x,
                    mouse_y=point[1] + region.y, ctrl=False, shift=False, alt=False)

            def click(point, kind='LEFTMOUSE'):
                workspace.handle_event(bpy.context, event(kind, point))
                workspace.handle_event(bpy.context, event(kind, point, 'RELEASE'))

            def button(key):
                workspace.canvas_layout = workspace.make_layout()
                rect = workspace.canvas_layout.buttons[key][0]
                click((rect.x + rect.w / 2, rect.y + rect.h / 2))

            from tests.gui_folding import run as run_folds
            run_folds(workspace, event, click, button, check, cleanup_garments)
            workspace.session = Session(Document())
            workspace.persist()
            workspace.perform_action('START_PANEL')
            check(len(workspace.session.document.patterns) == 1 and not workspace.session.document.seams,
                  'single pattern piece drafted with zero seams')
            button('KEEP')
            check(workspace.message == 'Start a drape before keeping or resetting it.',
                  'single piece pre-simulation Keep blocked with guidance message')
            check(not garment.generated(scene, 'final'), 'no final mesh created before simulation')
            button('SIMULATE')
            check(bpy.context.screen.is_animation_playing, 'single piece simulation starts')
            button('SIMULATE')
            check(not bpy.context.screen.is_animation_playing, 'single piece simulation pauses cleanly')
            button('KEEP')
            kept = garment.generated(scene, 'final')
            check(bool(kept), 'Keep creates real final mesh for single piece')
            check(kept[0].name.startswith('DD Garment'), 'single piece final mesh named DD Garment')
            check(len(kept[0].data.vertices) > 0, 'single piece final mesh has vertices')
            check('Pattern UV' in kept[0].data.uv_layers, 'single piece final mesh has Pattern UV layer')

            cleanup_garments()
            workspace.session = Session(Document())
            workspace.persist()
            workspace.session.add([(-0.2, 0), (0.2, 0), (0.2, 0.4), (-0.2, 0.4)])
            workspace.session.add([(0.3, 0), (0.7, 0), (0.7, 0.4), (0.3, 0.4)])
            p1, p2 = workspace.session.document.patterns
            edge_a = workspace.session.document.edge(p1.id, 1)
            edge_b = workspace.session.document.edge(p2.id, 3)
            workspace.session.sew(edge_a, edge_b)
            workspace.persist()
            check(len(workspace.session.document.patterns) == 2 and len(workspace.session.document.seams) == 1,
                  'two pieces created and sewn')
            button('KEEP')
            check(workspace.message == 'Start a drape before keeping or resetting it.',
                  'multi-piece pre-simulation Keep blocked with guidance message')
            button('SIMULATE')
            check(bpy.context.screen.is_animation_playing, 'multi-piece simulation starts')
            button('SIMULATE')
            check(not bpy.context.screen.is_animation_playing, 'multi-piece simulation pauses cleanly')
            button('KEEP')
            kept_multi = garment.generated(scene, 'final')
            check(bool(kept_multi), 'Keep creates real final mesh for multi-piece sewn garment')
            check(len(kept_multi[0].data.vertices) > 0, 'multi-piece final mesh has vertices')

            for starter_key in ('STARTER_TEE', 'STARTER_TANK', 'STARTER_SKIRT'):
                cleanup_garments()
                workspace.session = Session(Document())
                workspace.persist()
                workspace.perform_action(starter_key, confirmed=True)
                check(len(workspace.session.document.patterns) > 0, f'{starter_key} patterns loaded')
                button('KEEP')
                check(workspace.message == 'Start a drape before keeping or resetting it.',
                      f'{starter_key} pre-simulation Keep blocked')
                button('SIMULATE')
                check(bpy.context.screen.is_animation_playing, f'{starter_key} simulation starts')
                button('SIMULATE')
                check(not bpy.context.screen.is_animation_playing, f'{starter_key} simulation pauses')
                button('KEEP')
                kept_starter = garment.generated(scene, 'final')
                check(bool(kept_starter), f'{starter_key} finalized into kept mesh')
                check(len(kept_starter[0].data.vertices) > 0, f'{starter_key} final mesh has geometry')

            cleanup_garments()
            workspace.session = Session(Document())
            workspace.persist()
            workspace.perform_action('START_PANEL')
            button('SIMULATE')
            button('SIMULATE')
            check(bool(garment.generated(scene, 'simulation')), 'simulation ready for regression fault injection')

            original_keep = garment.keep_drape

            def faulty_keep(ctx):
                raise TypeError('Simulated unexpected geometry error in keep_drape')

            try:
                garment.keep_drape = faulty_keep
                action_result = workspace.workflow_action('KEEP')
                check(action_result is False, 'workflow_action returns False when Keep raises unexpected exception')
                check('Unexpected error' in workspace.message and 'TypeError' in workspace.message,
                      'unexpected exception reported in workspace.message with error type')
                check(not workspace._closed and editor._active is workspace,
                      'editor session survives unexpected exception in Keep')
                workspace.choose_tool('SELECT')
                check(workspace.tool == 'SELECT',
                      'editor remains responsive and interactive after trapped Keep exception')

                direct_res = None
                direct_msg = ''
                try:
                    direct_res = bpy.ops.devil_designer.keep_drape('EXEC_DEFAULT')
                    direct_msg = scene.get('dd_last_error', '')
                except RuntimeError as op_err:
                    direct_res = {'CANCELLED'}
                    direct_msg = str(op_err)
                check(direct_res == {'CANCELLED'} and 'Unexpected error' in direct_msg and 'TypeError' in direct_msg,
                      'direct Keep operator call intercepts unexpected exception without crashing Blender')
            finally:
                garment.keep_drape = original_keep

            workspace.cleanup()
            check(editor._active is None, 'pattern editor cleaned up successfully')

        report = {'passed': passed}
    except Exception:
        report = {'passed': passed, 'error': traceback.format_exc()}
        traceback.print_exc()

    (ROOT / 'scratch').mkdir(exist_ok=True)
    (ROOT / 'scratch' / 'core_workflow-report.json').write_text(json.dumps(report, indent=2))
    return None


bpy.app.timers.register(run, first_interval=2)
