import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
from unittest.mock import patch

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

bpy.context.preferences.view.show_splash = False

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import arrangement, editor, garment, history, library, live_panels, piece_states, placement
from devil_designer.core import Document, Session, arrangement_record
from devil_designer.construction import path_range
from devil_designer.viewport_sewing import PanelEdges, seam_hits


def run():
    passed = []
    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        passed.append(message)
    report = ROOT / 'scratch' / 'viewport_sewing-report.json'
    def finish():
        result = json.loads(report.read_text(encoding='utf-8'))
        print('GUI TEST FAILED: ' + result['error'] if 'error' in result else 'GUI TEST PASSED (' + str(len(result['passed'])) + ' checks)', flush=True)
        bpy.ops.wm.quit_blender()
    try:
        devil_designer.register()
        scene = bpy.context.scene
        avatar = scene.objects['Cube']
        avatar.scale = (.3, .16, .9)
        avatar.location.z = .9
        bpy.context.view_layer.update()
        scene.dd_avatar = avatar
        scene.dd_spacing = .035
        arrangement.ensure_volumes(bpy.context)
        session = Session()
        for index, point in enumerate(('front', 'back')):
            horizontal = .4 * index
            session.add([(horizontal, 0), (horizontal + .24, 0), (horizontal + .24, .3), (horizontal, .3)])
            session.document.patterns[-1].arrangement = arrangement_record('chest', point, False, version=2)
        scene.dd_document = session.document.dumps()
        live_panels.sync(bpy.context)
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            active = editor._active
            check(not active.viewport_sewing.preserve_pose, '2D-only sessions keep the original rebuild path')
            with patch.object(live_panels, 'sewing_only_change', side_effect=AssertionError('2D sewing must not enter viewport pose preservation')):
                first = active.session.document.edges(active.session.document.patterns[0].id)[0]
                second = active.session.document.edges(active.session.document.patterns[1].id)[0]
                active.session.sew_chains([first], [second], scene.dd_sew_reverse)
                active.persist()
                check(len(active.session.document.seams) == 1, '2D seam creation bypasses the 3D-only pose guard')
                active.session.history()
                active.persist()
                check(not active.session.document.seams, '2D undo also retains the unchanged rebuild path')
            active.reveal_3d()
            active.choose_tool('SEW')
            view = area.spaces.active.region_3d
            view.view_perspective = 'PERSP'
            def event(kind, pointer, value='PRESS', **options):
                values = dict(type=kind, value=value, mouse_x=pointer[0] + region.x, mouse_y=pointer[1] + region.y, ctrl=False, shift=False, alt=False)
                values.update(options)
                return SimpleNamespace(**values)
            def aim(piece, edge_index, fraction=.5):
                active.viewport_sewing.ensure(bpy.context)
                pattern = active.session.document.patterns[piece]
                edge = active.session.document.edges(pattern.id)[edge_index]
                point = active.viewport_sewing.geometry.point(edge, fraction)
                direction = Vector((0, -1 if piece == 0 else 1, .12))
                view.view_rotation = (-direction).to_track_quat('-Z', 'Y')
                view.view_distance = 1.3
                view.view_location = point
                view.update()
                target = (active.canvas_layout.panel.x * .5, region.height * .5)
                location = view3d_utils.region_2d_to_location_3d(region, view, target, point)
                view.view_location += point - location
                view.update()
                pointer = view3d_utils.location_3d_to_region_2d(region, view, point)
                check(not active.canvas_layout.panel.contains(*pointer), 'target lies in revealed 3D viewport')
                return edge, pointer
            edge, pointer = aim(0, 0)
            before_playback = active.session.document.dumps()
            bpy.ops.screen.animation_play()
            try:
                active.handle_event(bpy.context, event('LEFTMOUSE', pointer))
                check(active.session.document.dumps() == before_playback and active.pending_edge is None and 'Pause simulation' in active.message, '3D sewing refuses edits while playback is running')
            finally:
                bpy.ops.screen.animation_cancel(restore_frame=True)
            for index in range(20):
                edge, pointer = aim(index // 10, index % 4)
                hit, reason = active.viewport_sewing.pick(bpy.context, pointer + Vector((index % 3 - 1, .5)))
                check(hit is not None and hit[0] == edge, 'intended 3D edge ' + str(index + 1) + ': ' + reason)
            for piece in (0, 1):
                edge, pointer = aim(piece, 0, 0)
                hit, reason = active.viewport_sewing.pick(bpy.context, pointer)
                check(hit is None and 'Ambiguous' in reason, 'shared corner refuses both incident edges')
            for piece in (0, 1):
                for edge_index in range(4):
                    view.view_perspective = 'ORTHO'
                    edge, pointer = aim(piece, edge_index)
                    hit, reason = active.viewport_sewing.pick(bpy.context, pointer)
                    check(hit is not None and hit[0] == edge, 'orthographic picking resolves the intended edge: ' + reason)
            view.view_perspective = 'PERSP'
            edge, pointer = aim(0, 0)
            target = active.viewport_sewing.geometry.point(edge, .5)
            direction = (view.view_matrix.inverted().translation - target).normalized()
            previous_active = bpy.context.view_layer.objects.active
            bpy.ops.mesh.primitive_cube_add(size=.12, location=target + direction * .12)
            occluder = bpy.context.object
            garment.tag(occluder, 'final')
            bpy.context.view_layer.update()
            hit, _ = active.viewport_sewing.pick(bpy.context, pointer)
            check(hit is None or hit[0] != edge, 'kept meshes occlude live-panel edge picking and cannot become sewing targets')
            occluder.location.x += 1
            bpy.context.view_layer.update()
            hit, reason = active.viewport_sewing.pick(bpy.context, pointer)
            check(hit is not None and hit[0] == edge, 'moving a kept occluder invalidates the cached visibility: ' + reason)
            bpy.data.objects.remove(occluder, do_unlink=True)
            bpy.context.view_layer.objects.active = previous_active
            bpy.context.view_layer.update()
            overlap = PanelEdges(active.session.document, garment.generated(scene, 'panel'))
            other = active.session.document.edges(active.session.document.patterns[1].id)[0]
            overlap.edges[other] = overlap.edges[edge]
            hit, reason = overlap.pick(region, view, pointer, active.viewport_sewing.tree(bpy.context))
            check(hit is None and 'Ambiguous' in reason, 'coincident visible edges from different pieces select neither')
            initial = Document.loads(active.session.document.dumps())
            poses = {panel['dd_pattern_id']: tuple(tuple(row) for row in panel.matrix_world) for panel in garment.generated(scene, 'panel')}
            for piece in (0, 1):
                edge, pointer = aim(piece, 0)
                active.handle_event(bpy.context, event('LEFTMOUSE', pointer))
            check(len(active.session.document.seams) == 1, 'two viewport clicks create a normal segment seam')
            check(all(tuple(tuple(row) for row in panel.matrix_world) == poses[panel['dd_pattern_id']] for panel in garment.generated(scene, 'panel')), 'segment sewing preserves arranged poses exactly')
            reference = Session(initial)
            reference.sew_chains([reference.document.edges(reference.document.patterns[0].id)[0]], [reference.document.edges(reference.document.patterns[1].id)[0]], scene.dd_sew_reverse)
            reference.document.seams[0].id = active.session.document.seams[0].id
            check(reference.document.dumps() == active.session.document.dumps(), 'segment seam is byte-identical to equivalent 2D records')
            preview = active.viewport_sewing
            preview.read_truth(bpy.context)
            record = next(iter(preview.truth['records'].values()))
            check(len(record['pairs']) > 2 and not preview.truth_error, 'pre-simulation preview resolves every compiled pair')
            from devil_designer import viewport_sewing
            with patch.object(viewport_sewing, 'batch_for_shader', wraps=viewport_sewing.batch_for_shader) as batches:
                preview.dirty = True
                preview.ensure(bpy.context)
                positions = batches.call_args_list[0].args[2]['pos']
                links = [(tuple(positions[index]), tuple(positions[index + 1])) for index in range(0, len(positions), 2)]
                check(all((tuple(first), tuple(second)) in links for first, second in record['world']), '3D batch contains the real correspondence set, not midpoint shorthand')
                check(len(positions) > 2 * len(record['pairs']) + 200, '3D preview retains edge strokes and adds direction arrowheads')
            with patch.object(active.renderer, 'lines') as lines, patch.object(active.renderer, 'dot'), patch.object(active.renderer, 'text') as labels:
                active.renderer.seams(active)
                actual = [call.args[0] for call in lines.call_args_list]
                canvas = active.canvas_layout.canvas
                check(all([active.view.screen(point, canvas) for point in pair] in actual for pair in record['flat']), '2D renderer draws each exact flat-pattern correspondence')
                check(any(record['readout'] in call.args[2] for call in labels.call_args_list), 'mismatch and pass/warn readout is visible before Simulate')
                preview.labels()
                check(any(call.args[2] == record['readout'] for call in labels.call_args_list), 'arranged viewport shows the same seam readout')
            active.choose_tool('FREE_SEW')
            picks = []
            for piece, edge_index, fraction in ((0, 1, .25), (0, 2, .75), (1, 1, .25), (1, 2, .75)):
                edge, pointer = aim(piece, edge_index, fraction)
                hit, _ = active.viewport_sewing.pick(bpy.context, pointer)
                from devil_designer import curves
                value, _ = curves.closest_fraction(active.session.document.edge_curve(edge), active.session.document.edge_point(*hit))
                picks.append((edge, value))
                active.handle_event(bpy.context, event('LEFTMOUSE', pointer))
            check(len(active.session.document.seams) == 2, 'four viewport clicks create free sewing across multiple edges')
            reference.sew_chains(path_range(reference.document, *picks[:2]), path_range(reference.document, *picks[2:]), scene.dd_sew_reverse)
            reference.document.seams[-1].id = active.session.document.seams[-1].id
            check(reference.document.dumps() == active.session.document.dumps(), 'free M:N ranges, direction and ratios match equivalent 2D records exactly')
            seam = active.session.document.seams[-1]
            check(len(seam.side(0)) > 1 and len(seam.side(1)) > 1, 'free sewing retains M:N chains in the one sewing model')
            check(len(seam_hits(active.session.document, picks[0][0], picks[0][1])) == 1, 'partial seam is selectable on its actual sewn range')
            check(not seam_hits(active.session.document, picks[0][0], .05), 'unsewn portion of a partial edge is not a seam hit')
            saved_seams = list(active.session.document.seams)
            active.session.commit(active.session.document.seams.clear)
            active.persist()
            active.choose_tool('SEW')
            for edge_index in (3, 0):
                edge, pointer = aim(0, edge_index)
                active.handle_event(bpy.context, event('LEFTMOUSE', pointer))
            self_seam = active.session.document.seams[-1]
            check(len(active.session.document.seams) == 1 and self_seam.a.pattern == self_seam.b.pattern, 'viewport sewing supports different edges of the same piece')
            check('Gather warning; sewing allowed.' in active.message and active.session.document.seam_stats(self_seam)[3] > 1, '3D mismatch uses identical nonblocking 2D thresholds and wording')
            active.session.commit(lambda: setattr(active.session.document, 'seams', saved_seams))
            active.persist()
            active.seam_selected = None
            active.choose_tool('SELECT')
            edge, pointer = aim(0, 0)
            active.handle_event(bpy.context, event('MOUSEMOVE', pointer, 'NOTHING'))
            check(active.seam_hover == active.session.document.seams[0].id, '3D hover shares the 2D seam highlight identity')
            active.handle_event(bpy.context, event('LEFTMOUSE', pointer))
            check(active.seam_selected == active.session.document.seams[0].id, '3D selection uses the shared selected seam')
            canvas_pointer = active.view.screen(active.session.document.edge_point(edge, .5), active.canvas_layout.canvas)
            active.handle_event(bpy.context, event('MOUSEMOVE', canvas_pointer, 'NOTHING'))
            check(active.seam_hover == active.session.document.seams[0].id, '2D hover shares the 3D seam highlight identity')
            active.viewport_sewing.ensure(bpy.context)
            active.viewport_sewing.gestures()
            batches = active.viewport_sewing.batches
            geometry = active.viewport_sewing.geometry
            tree = active.viewport_sewing.tree(bpy.context)
            with patch.object(active.session.document, 'chain_position', wraps=active.session.document.chain_position) as resolve:
                for index in range(5):
                    view.view_distance += .01
                    view.update()
                    active.viewport_sewing.draw()
                check(resolve.call_count == 0, 'orbit redraw does not re-resolve sewing chains')
            check(active.viewport_sewing.batches is batches and active.viewport_sewing.geometry is geometry and active.viewport_sewing.visibility is tree, 'orbit retains geometry, GPU batches and visibility cache')
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
            bpy.ops.screen.screenshot(filepath=str(ROOT / 'scratch' / 'viewport-sewing.png'))
            active.handle_event(bpy.context, event('DEL', pointer))
            check(len(active.session.document.seams) == 1, '3D delete removes the selected seam')
            active.handle_event(bpy.context, event('Z', pointer, ctrl=True))
            check(len(active.session.document.seams) == 2, '3D delete is restored through persistent undo')
            restored = Session(Document.loads(active.session.document.dumps()))
            check(history.restore(restored, history.store(active.session)), 'viewport-created seams retain persistent saved history')
            check(restored.history() and len(restored.document.seams) == 1, 'restored history can undo the viewport deletion recovery')
            active.choose_tool('SEW')
            edge, pointer = aim(0, 0, 0)
            count = len(active.session.document.seams)
            active.handle_event(bpy.context, event('LEFTMOUSE', pointer))
            check(active.pending_edge is None and active.seam_selected is None and len(active.session.document.seams) == count, 'ambiguous viewport click never guesses or creates a seam')
            document = active.session.document
            before = document.dumps()
            flags = [(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in document.patterns]
            document.patterns[0].deactivated = True
            check(not piece_states.active_document(document).seams, '3D-created seams attached to deactivated pieces remain inert')
            document.patterns[0].deactivated = False
            check([(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in document.patterns] == flags and document.dumps() == before, 'sewing never changes piece simulation states')
            for flat in (True, False):
                document.patterns[0].arrangement['flat'] = flat
                active.persist()
                panel = next(panel for panel in garment.generated(scene, 'panel') if panel['dd_pattern_id'] == document.patterns[0].id)
                pose = tuple(tuple(row) for row in panel.matrix_world)
                active.session.reverse_seam(document.seams[0].id)
                active.persist()
                check(tuple(tuple(row) for row in panel.matrix_world) == pose, 'seam edit preserves ' + ('flat' if flat else 'wrapped') + ' arrangement pose')
            document.patterns[0].arrangement = None
            active.persist()
            panel = placement.place(bpy.context, document.patterns[0].id, Vector((.2, -.2, 1.2)), Vector((.1, -1, .2)).normalized())
            pose = tuple(tuple(row) for row in panel.matrix_world)
            active.session.reverse_seam(document.seams[0].id)
            active.persist()
            check(tuple(tuple(row) for row in panel.matrix_world) == pose, 'seam edit preserves click-placed matrix exactly')
            for mode in ('QUATERNION', 'AXIS_ANGLE'):
                panel.rotation_mode = mode
                if mode == 'QUATERNION':panel.rotation_quaternion = (.9, .1, .2, .3)
                else:panel.rotation_axis_angle = (.4, .3, .6, .5)
                bpy.context.view_layer.update()
                pose = tuple(tuple(row) for row in panel.matrix_world)
                active.session.reverse_seam(document.seams[0].id)
                active.persist()
                check(tuple(tuple(row) for row in panel.matrix_world) == pose, 'seam edits preserve ' + mode + ' transform channels exactly')
            active.session.selected = document.patterns[0].id
            active.session.duplicate()
            check(len(active.session.document.patterns) == 3, 'duplicate works with viewport-created sewing')
            active.session.history()
            active.persist()
            scene.dd_library_dir = str(ROOT / 'scratch' / 'viewport-sewing-library')
            scene.dd_library_refit = False
            saved = library.save(bpy.context, 'Viewport sewn garment')
            stored = json.loads(saved.read_text(encoding='utf-8'))
            check(stored['document']['seams'] == json.loads(document.dumps())['seams'], 'library retains the identical viewport sewing records')
            loaded = library.load(bpy.context, scene.dd_library_selected)
            check(json.loads(loaded.dumps())['seams'] == stored['document']['seams'], 'library round-trip preserves viewport seams')
            active.cleanup()
            document = Document.loads(scene.dd_document)
            simulation = garment.compile_garment(bpy.context)
            actual_mesh = ([tuple(vertex.co) for vertex in simulation.data.vertices], [tuple(edge.vertices) for edge in simulation.data.edges], [tuple(face.vertices) for face in simulation.data.polygons], [tuple(item.uv) for item in simulation.data.uv_layers.active.data])
            garment.reset(bpy.context)
            scene.dd_document = Document.loads(document.dumps()).dumps()
            simulation = garment.compile_garment(bpy.context)
            expected_mesh = ([tuple(vertex.co) for vertex in simulation.data.vertices], [tuple(edge.vertices) for edge in simulation.data.edges], [tuple(face.vertices) for face in simulation.data.polygons], [tuple(item.uv) for item in simulation.data.uv_layers.active.data])
            check(actual_mesh == expected_mesh, 'saved sewing compiles with identical vertices, springs, faces and UVs')
            garment.reset(bpy.context)
            panels = garment.generated(scene, 'panel')
            mapping = PanelEdges(document, panels)
            first = document.edges(document.patterns[0].id)[0]
            check(first in mapping.edges, 'live-panel edge mapping survives compile and reset')
        expected_document = scene.dd_document
        expected_history = scene.dd_history
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'scratch' / 'viewport-sewing.blend'))
        bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'scratch' / 'viewport-sewing.blend'))
        check(bpy.context.scene.dd_document == expected_document and bpy.context.scene.dd_history == expected_history, 'blend save/load preserves exact viewport sewing and persistent history')
        report.write_text(json.dumps(dict(passed=passed), indent=2), encoding='utf-8')
    except Exception:
        report.write_text(json.dumps(dict(passed=passed, error=traceback.format_exc()), indent=2), encoding='utf-8')
        traceback.print_exc()
    bpy.app.timers.register(finish, first_interval=.2)


bpy.app.timers.register(run, first_interval=.5)
