import math
import bpy
from devil_designer import garment
from devil_designer.core import Document, Session
from devil_designer.folding import fold_records


def run(workspace, event, click, button, check, cleanup):
    scene = bpy.context.scene
    scene.dd_spacing = .025
    scene.dd_pin_top = True
    body = scene.dd_avatar
    previous_scale = body.scale.copy()
    body.scale = (.01, .01, .01)
    bpy.context.view_layer.update()
    try:
        for style in ('MOUNTAIN', 'VALLEY', 'KNIFE', 'BOX'):
            cleanup()
            workspace.clear_interaction_references()
            workspace.session = Session(Document())
            workspace.session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
            workspace.persist()
            workspace.stage = 'DRAFT'
            workspace.card_kind = None
            workspace.fit()
            workspace.choose_tool('INTERNAL')
            canvas = workspace.canvas_layout.canvas
            for point in ((.2, 0), (.2, .5)):
                click(workspace.view.screen(point, canvas))
            workspace.handle_event(bpy.context, event('RET', workspace.view.screen((.2, .25), canvas)))
            pattern = workspace.session.document.find(workspace.session.selected)
            check(len(pattern.paths) == 1, style + ' fold source is drawn through the existing Internal tool')
            workspace.choose_tool('SELECT')
            workspace.session.path = pattern.paths[0].id
            workspace.session.segment = workspace.session.document.edges(pattern.id, pattern.paths[0].id)[0]
            workspace.show_card('INTERNAL_EDGE')
            workspace.error_message = None
            workspace.renderer.draw(workspace)
            check(not workspace.error_message, style + ' internal-edge contextual entry draws')
            workspace.minimal_action('FOLD_MENU')
            workspace.renderer.draw(workspace)
            check(not workspace.error_message and workspace.card_kind == 'FOLD', style + ' creation menu draws')
            workspace.minimal_action('FOLD_ADD_' + style + '_2')
            check(not workspace.error_message and workspace.card_kind is None, style + ' contextual creation dismisses back to canvas')
            pattern = workspace.session.document.find(workspace.session.selected)
            count = 4 if style == 'BOX' else 2 if style == 'KNIFE' else 1
            check(len(fold_records(pattern)) == count, style + ' creates persistent folds through minimal UI')
            for tool in ('SELECT', 'RECTANGLE', 'POLYGON', 'ELLIPSE', 'INTERNAL', 'DART', 'KNIFE', 'SEW', 'PIN'):
                workspace.choose_tool(tool)
                workspace.error_message = None
                workspace.renderer.draw(workspace)
                check(not workspace.error_message, style + ' arrows render in ' + tool)
            workspace.choose_tool('SEW')
            workspace.pending_edge = workspace.session.document.edge(pattern.id, 0)
            workspace.renderer.draw(workspace)
            check(not workspace.error_message, style + ' pending sew renders with fold arrows')
            workspace.pending_edge = None
            workspace.choose_tool('SELECT')
            canvas = workspace.canvas_layout.canvas
            workspace.gesture = dict(mode='BOX_SELECT', start=(canvas.x+20, canvas.y+20))
            workspace.pointer = (canvas.x+150, canvas.y+150)
            workspace.renderer.draw(workspace)
            check(not workspace.error_message, style + ' fold arrows render during active box selection')
            workspace.gesture = None
            for stage in ('DRAFT', 'SEW', 'ARRANGE', 'LIBRARY'):
                workspace.stage = stage
                workspace.renderer.draw(workspace)
                check(not workspace.error_message, style + ' folded content draws in ' + stage)
            workspace.stage = 'DRAFT'
            workspace.minimal_action('FOLD_MENU')
            workspace.renderer.draw(workspace)
            check(not workspace.error_message, style + ' existing-fold settings menu draws')
            before = workspace.session.document.dumps()
            workspace.minimal_action('FOLD_EDIT_REVERSE')
            check(workspace.session.document.dumps() != before and workspace.card_kind is None, style + ' reverses direction through UI')
            workspace.perform_action('UNDO')
            check(workspace.session.document.dumps() == before, style + ' fold reversal is undoable')
            workspace.perform_action('REDO')
            workspace.perform_action('UNDO')
            for angle in ('60', '120', '150'):
                workspace.minimal_action('FOLD_EDIT_' + angle)
                workspace.renderer.draw(workspace)
                check(not workspace.error_message, style + ' angle state ' + angle + ' draws cleanly')
            workspace.minimal_action('FOLD_EDIT_REMOVE')
            workspace.renderer.draw(workspace)
            check(not workspace.error_message and not fold_records(workspace.session.document.find(workspace.session.selected)), style + ' removed-fold state returns to plain internal paths')
            workspace.perform_action('UNDO')
            workspace.stage = 'ARRANGE'
            workspace.persist()
            workspace.renderer.draw(workspace)
            check(not workspace.error_message and bool(garment.generated(scene, 'panel')), style + ' arranged real folded geometry draws')
            button('SIMULATE')
            button('SIMULATE')
            check(bool(garment.generated(scene, 'simulation')), style + ' starts classic cloth through minimal UI')
            simulation = garment.generated(scene, 'simulation')[0]
            for frame in range(scene.frame_start, scene.frame_start+4):
                scene.frame_set(frame)
                evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
            check(all(math.isfinite(value) for vertex in evaluated.data.vertices for value in vertex.co), style + ' simulated mesh is finite')
            workspace.renderer.draw(workspace)
            check(not workspace.error_message, style + ' simulation-state draw is clean')
            button('KEEP')
            kept = garment.generated(scene, 'final')
            check(bool(kept) and len(kept[0].data.polygons) > 0, style + ' completes minimal UI draft to Keep on real geometry')
        cleanup()
        workspace.clear_interaction_references()
        workspace.session = Session(Document())
        workspace.persist()
        workspace.choose_tool('SELECT')
        workspace.stage = 'DRAFT'
    finally:
        body.scale = previous_scale
        scene.dd_spacing = .04
        bpy.context.view_layer.update()
