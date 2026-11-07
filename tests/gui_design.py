from pathlib import Path
from types import SimpleNamespace
import json,traceback
import bpy
from mathutils import Vector
from bpy_extras import view3d_utils
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT))
bpy.context.preferences.view.show_splash=False
import devil_designer
from devil_designer import editor,garment


def run_selection_native(op, passed):
    import math
    from devil_designer import curves, arrangement, arrangement_controls, live_panels
    from devil_designer.core import Session, point_in_lasso

    failures = []
    cases = []
    window = op._window
    report_path = ROOT / 'scratch' / 'design-gui-report.json'

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        passed.append('Native: ' + message)

    def fixture(sewn=False):
        bpy.context.preferences.view.ui_scale = 1.0
        op.clear_interaction_references()
        op.cancel_transform()
        op.session = Session()
        op.session.add([(0, 0), (.2, 0), (.2, .3), (0, .3)])
        op.session.add([(.3, 0), (.5, 0), (.5, .3), (.3, .3)])
        first, second = op.session.document.patterns
        if sewn:
            op.session.sew(op.session.document.edge(first.id, 1),
                           op.session.document.edge(second.id, 3))
        op.session.clear_selection()
        op.full = True
        op.tool = 'SELECT'
        op.snap = False
        op._nudge_burst = None
        op.card_kind = None
        op._scene.dd_document = op.session.document.dumps()
        op._stored = op._scene.dd_document
        op.canvas_layout = op.make_layout()
        op.view.zoom = 600
        op.view.cx, op.view.cy = .25, .15
        op.sync_selection()
        op.persist()
        return first, second

    def screen(world):
        local = op.view.screen(world, op.canvas_layout.canvas)
        return round(local[0] + op._region.x), round(local[1] + op._region.y)

    def post(kind, value='PRESS', world=None, local=None, **modifiers):
        if world is not None:
            position = screen(world)
        elif local is not None:
            position = round(local[0] + op._region.x), round(local[1] + op._region.y)
        else:
            position = screen((.1, .15))
        window.event_simulate(type=kind, value=value, x=position[0], y=position[1], **modifiers)

    def key(kind, **modifiers):
        post(kind, **modifiers)
        post(kind, 'RELEASE', **modifiers)

    def drag(start, finish, **modifiers):
        post('MOUSEMOVE', 'NOTHING', world=start)
        post('LEFTMOUSE', world=start, **modifiers)
        post('MOUSEMOVE', 'NOTHING', world=finish, **modifiers)
        post('LEFTMOUSE', 'RELEASE', world=finish, **modifiers)

    def click_action(action):
        card = op.minimal_card()
        if card is None:
            raise AssertionError('Missing contextual card for ' + action)
        rect, row = next((rect, row) for rect, row in card[2] if action in row)
        fraction = (.75 if row[2] == action else .25) if row[0] == 'PAIR_ACTIONS' else .5
        point = rect.x + rect.w * fraction, rect.y + rect.h / 2
        post('LEFTMOUSE', local=point)
        post('LEFTMOUSE', 'RELEASE', local=point)

    def numeric(kind, text):
        op.show_card('TRANSFORM_MENU', op.view.screen((.1, .15), op.canvas_layout.canvas))
        click_action('TRANSFORM_' + kind)
        yield
        check(op.gesture is not None and op.gesture['mode'] == 'TRANSFORM',
              kind + ' menu arms a transform through the opening mouse release')
        for character in text:
            post('A', unicode=character)
        yield
        key('RET')
        yield

    def draw(label):
        op.error_message = None
        op.renderer.draw(op)
        check(not op.error_message, label + ' renders without errors')

    def sewn_endpoint():
        first, second = fixture(sewn=True)
        partner_before = list(second.points)
        original = op.session.document.dumps()
        undo_count = len(op.session.undo_stack)
        seam_id = op.session.document.seams[0].id
        drag((.2, .3), (.2, .35))
        yield
        check(op.card_kind == 'SEAM_WARNING', '30 to 35 cm endpoint drag warns before commit')
        check(op.session.document.dumps() == original and len(op.session.undo_stack) == undo_count,
              'unconfirmed endpoint drag preserves exact document and undo count')
        card_text = ' '.join(str(value) for _, row in op.minimal_card()[2] for value in row)
        check('5.00' in card_text and ('14.2857' in card_text or '14.29' in card_text),
              'warning displays 5 cm and 14.2857 percent within display rounding')
        draw('Endpoint seam warning')
        key('ESC')
        yield
        check(op.card_kind is None and not getattr(op, 'pending_transform', None) and
              op.session.document.dumps() == original, 'Escape cancels the frozen seam candidate')
        drag((.2, .3), (.2, .35))
        yield
        click_action('APPLY_MISMATCH')
        yield
        check(abs(op.session.document.find(first.id).vertices[2].y - .35) < 1e-8 and
              len(op.session.undo_stack) == undo_count + 1,
              'explicit mismatch confirmation commits the endpoint once')
        check(op.session.document.seams[0].id == seam_id and
              op.session.document.find(second.id).points == partner_before,
              'confirmed endpoint mismatch retains seam and unselected partner')
        key('Z', ctrl=True)
        yield
        check(op.session.document.dumps() == original, 'endpoint undo restores exact geometry')
        key('Z', ctrl=True, shift=True)
        yield
        check(abs(op.session.document.find(first.id).vertices[2].y - .35) < 1e-8,
              'endpoint redo restores confirmed geometry')

    def nudge_steps():
        first, second = fixture()
        op.session.selected = second.id
        internal = op.session.add_path([(.34, .1), (.44, .2)])
        op.session.select_piece(first.id)
        op.session.select_point(first.id, 'OUTER', 0, toggle=True)
        op.session.select_point(second.id, 'OUTER', 0, toggle=True)
        op.session.select_edge(op.session.document.edge(second.id, 2), toggle=True)
        op.session.select_path(second.id, internal.id, toggle=True)
        op.sync_selection()
        op.persist()
        selected_keys = [(first.id, 'OUTER', index) for index in range(4)]
        selected_keys += [(second.id, 'OUTER', index) for index in (0, 2, 3)]
        selected_keys += [(second.id, internal.id, index) for index in range(2)]
        for modifiers, step in (({}, .01), ({'shift': True}, .1), ({'alt': True}, .001)):
            before = op.session.document.dumps()
            selection = op.session.get_selection_state()
            selected_before = {}
            for pid, path, index in selected_keys:
                vertex = op.session.document.find(pid).path(path).vertices[index]
                selected_before[(pid, path, index)] = (vertex.x, vertex.y)
            start_first = op.session.document.find(first.id).points[0]
            start_point = op.session.document.find(second.id).points[0]
            history_count = len(op.session.undo_stack)
            key('RIGHT_ARROW', **modifiers)
            yield
            check(abs(op.session.document.find(first.id).points[0][0] - start_first[0] - step) < 1e-8 and
                  abs(op.session.document.find(second.id).points[0][0] - start_point[0] - step) < 1e-8,
                  f'mixed nudge is exactly {step * 1000:g} mm with {modifiers}')
            check(len(op.session.undo_stack) == history_count + 1, 'single nudge records one undo step')
            for (pid, path, index), point in selected_before.items():
                vertex = op.session.document.find(pid).path(path).vertices[index]
                check(abs(vertex.x - point[0] - step) < 1e-8 and abs(vertex.y - point[1]) < 1e-8,
                      'piece, point, edge, path and redundant-node nudge use one displacement')
            key('Z', ctrl=True)
            yield
            check(op.session.document.dumps() == before and op.session.get_selection_state() == selection,
                  'nudge undo restores exact mixed geometry and selection')
            key('Z', ctrl=True, shift=True)
            yield
            check(abs(op.session.document.find(first.id).points[0][0] - start_first[0] - step) < 1e-8,
                  'nudge redo restores displacement')
        before_burst = op.session.document.dumps()
        history_count = len(op.session.undo_stack)
        before_x = op.session.document.find(first.id).vertices[0].x
        for _ in range(5):
            post('RIGHT_ARROW')
        yield
        post('RIGHT_ARROW', 'RELEASE')
        yield
        check(len(op.session.undo_stack) == history_count + 1 and
              abs(op.session.document.find(first.id).vertices[0].x - before_x - .05) < 1e-8,
              'five held nudge presses move five centimeters in one undo step')
        key('Z', ctrl=True)
        yield
        check(op.session.document.dumps() == before_burst, 'one undo reverses the whole repeat burst')
        key('Z', ctrl=True, shift=True)
        yield
        key('RIGHT_ARROW')
        yield
        check(len(op.session.undo_stack) == history_count + 2,
              'a released and restarted nudge creates a separate transaction')

    def paused_nudge():
        first, _ = fixture(sewn=True)
        op.session.select_point(first.id, 'OUTER', 2)
        before = op.session.document.dumps()
        history_count = len(op.session.undo_stack)
        for _ in range(3):
            post('UP_ARROW')
        post('UP_ARROW', 'RELEASE')
        yield
        check(op.card_kind == 'SEAM_WARNING' and op.session.document.dumps() == before and
              len(op.session.undo_stack) == history_count,
              'seam warning pauses all nudge repeats before any mutation')
        draw('Paused nudge warning')
        key('ESC')
        yield
        check(op.session.document.dumps() == before, 'cancelled nudge warning leaves source intact')

    def mixed_rotation():
        first, second = fixture()
        op.session.selected = second.id
        internal = op.session.add_path([(.34, .1), (.44, .2)])
        op.session.add([(.6, 0), (.8, 0), (.8, .3), (.6, .3)])
        third = op.session.document.patterns[-1]
        selected_edge = op.session.document.edge(second.id, 2)
        second.vertices[2].outgoing = (-.03, .04)
        second.vertices[3].incoming = (.04, .02)
        op.session.select_piece(first.id)
        op.session.select_point(first.id, 'OUTER', 0, toggle=True)
        op.session.select_point(second.id, 'OUTER', 0, toggle=True)
        op.session.select_edge(selected_edge, toggle=True)
        op.session.select_path(second.id, internal.id, toggle=True)
        pivot = (third.vertices[0].x, third.vertices[0].y)
        op.start_set_pivot()
        post('MOUSEMOVE', 'NOTHING', world=pivot)
        yield
        drag(pivot, pivot)
        yield
        check(op.session.get_pivot() == pivot, 'mixed rotation pivot snaps to the third piece vertex')
        selected_keys = [(first.id, 'OUTER', index) for index in range(4)]
        selected_keys += [(second.id, 'OUTER', index) for index in (0, 2, 3)]
        selected_keys += [(second.id, internal.id, index) for index in range(2)]
        before = {}
        for pid, path, index in selected_keys:
            vertex = op.session.document.find(pid).path(path).vertices[index]
            before[(pid, path, index)] = (vertex.x, vertex.y)
        selected_curves = list(op.session.document.edges(first.id)) + [selected_edge]
        selected_curves += list(op.session.document.edges(second.id, internal.id))
        controls = {edge: op.session.document.edge_curve(edge) for edge in selected_curves}
        angle = math.radians(37.5)

        def rotated(point):
            dx, dy = point[0] - pivot[0], point[1] - pivot[1]
            return pivot[0] + math.cos(angle) * dx - math.sin(angle) * dy, \
                   pivot[1] + math.sin(angle) * dx + math.cos(angle) * dy

        yield from numeric('ROTATE', '+37.5')
        for (pid, path, index), point in before.items():
            vertex = op.session.document.find(pid).path(path).vertices[index]
            check(math.dist((vertex.x, vertex.y), rotated(point)) < 1e-8,
                  'mixed +37.5 degree transform moves each resolved node once')
        for edge, original_controls in controls.items():
            transformed_controls = op.session.document.edge_curve(edge)
            for sample in range(101):
                check(math.dist(curves.evaluate(transformed_controls, sample / 100),
                                rotated(curves.evaluate(original_controls, sample / 100))) < .0001,
                      'mixed rotation Bezier sample matches common affine result')
        check(op.session.get_pivot() == pivot, 'rotation keeps the placed pivot fixed')
        draw('Committed mixed rotation')

    def scale_and_cancel():
        results = []
        for text in ('1.1', '110%'):
            first, second = fixture()
            op.session.select_piece(first.id)
            op.session.select_point(second.id, 'OUTER', 0, toggle=True)
            op.session.set_pivot(0, 0)
            yield from numeric('SCALE', text)
            values = [point for piece in op.session.document.patterns for point in piece.points]
            results.append(values)
            check(abs(values[2][0] - .22) < 1e-8 and abs(values[2][1] - .33) < 1e-8,
                  text + ' scales the mixed fixture around the fixed pivot')
        check(results[0] == results[1], 'factor and percentage scale produce identical coordinates')
        for text in ('0', '-1', 'NaN', 'inf', '1..2'):
            first, _ = fixture()
            op.session.select_piece(first.id)
            before = op.session.document.dumps()
            history_count = len(op.session.undo_stack)
            yield from numeric('SCALE', text)
            check(op.session.document.dumps() == before and len(op.session.undo_stack) == history_count,
                  'invalid scale ' + text + ' leaves geometry and undo untouched')
            key('ESC')
            yield
        for cancel_key in ('ESC', 'RIGHTMOUSE'):
            first, _ = fixture()
            op.session.select_piece(first.id)
            before = op.session.document.dumps()
            history_count = len(op.session.undo_stack)
            op.start_transform('ROTATE')
            post('A', unicode='3')
            post('A', unicode='7')
            yield
            draw('Numeric transform before cancellation')
            key(cancel_key)
            yield
            check(op.gesture is None and op.session.document.dumps() == before and
                  len(op.session.undo_stack) == history_count, cancel_key + ' cancels the transform without history')
            draw('Cancelled numeric transform')

    def region_and_clicks():
        first, second = fixture()
        drag((.1, .15), (.1, .15))
        yield
        check(len(op.session.selected_patterns) == 1 and op.card_kind is None,
              'piece click selects cleanly without a menu')
        drag((.4, .15), (.4, .15), shift=True)
        yield
        check(len(op.session.selected_patterns) == 2, 'Shift click adds the second panel')
        drag((.1, .15), (.1, .15), shift=True)
        yield
        check(len(op.session.selected_patterns) == 1 and second.id in op.session.selected_patterns,
              'Shift click toggles the first panel off')
        op.session.select_point(first.id, 'OUTER', 0)
        drag((0, 0), (0, 0), shift=True)
        yield
        check(not op.session.has_selection() and op.session.selected is None and op.session.corner is None,
              'last point toggle clears effective and legacy selection')
        op.session.select_edge(op.session.document.edge(first.id, 0))
        drag((.1, 0), (.1, 0), shift=True)
        yield
        check(not op.session.has_selection() and op.session.segment is None,
              'last edge toggle clears effective and legacy selection')
        for ui_scale in (1.0, 2.0):
            bpy.context.preferences.view.ui_scale = ui_scale
            yield
            op.canvas_layout = op.make_layout()
            for zoom in (300, 600, 1200):
                for reverse in (False, True):
                    op.session.clear_selection()
                    op.view.zoom = zoom
                    op.session.acquisition_target = 'PIECES'
                    start, finish = ((-.1, -.1), (.6, .4))
                    if reverse:
                        start, finish = finish, start
                    drag(start, finish)
                    yield
                    check(op.session.selected_patterns == {first.id, second.id} and not op.session.selected_points,
                          f'UI scale {ui_scale:g}, zoom {zoom}, {"crossing" if reverse else "enclose"} selects two panels')
        bpy.context.preferences.view.ui_scale = 1.0
        yield
        op.canvas_layout = op.make_layout()
        op.view.zoom = 600
        op.session.clear_selection()
        op.snap = True
        drag((.1, .15), (.137, .172), shift=True)
        yield
        check(abs(op.session.document.find(first.id).vertices[0].x - .04) < 1e-8 and
              abs(op.session.document.find(first.id).vertices[0].y) < 1e-8,
              'existing snapped axis-constrained drag stays +4 cm X and zero Y')

    def mixed_group_drag():
        first, second = fixture()
        op.session.selected = second.id
        internal = op.session.add_path([(.34, .1), (.44, .2)])
        op.session.select_piece(first.id)
        op.session.select_point(second.id, 'OUTER', 0, toggle=True)
        op.session.select_edge(op.session.document.edge(second.id, 2), toggle=True)
        op.session.select_path(second.id, internal.id, toggle=True)
        op.persist()
        prior = op.session.get_selection_state()
        op.snap = True
        post('MOUSEMOVE', 'NOTHING', world=(.1, .15))
        post('LEFTMOUSE', world=(.1, .15))
        yield
        check(op.session.get_selection_state() == prior, 'mixed group drag preserves selection on press')
        post('MOUSEMOVE', 'NOTHING', world=(.137, .172), shift=True)
        yield
        draw('Mixed group constrained move preview')
        post('LEFTMOUSE', 'RELEASE', world=(.137, .172), shift=True)
        yield
        check(abs(op.session.document.find(first.id).vertices[0].x - .04) < 1e-8 and
              abs(op.session.document.find(first.id).vertices[0].y) < 1e-8 and
              abs(op.session.document.find(second.id).vertices[0].x - .34) < 1e-8 and
              abs(op.session.document.find(second.id).vertices[0].y) < 1e-8 and
              abs(op.session.document.find(second.id).path(internal.id).vertices[0].x - .38) < 1e-8,
              'one constrained snapped drag applies +4 cm X and zero Y to all mixed targets')

    def region_targets_and_edges():
        first, second = fixture()
        op.session.selected = first.id
        first_path = op.session.add_path([(.04, .08), (.16, .2)])
        op.session.selected = second.id
        second_path = op.session.add_path([(.34, .08), (.46, .2)])
        collections = {'POINTS': 'selected_points', 'EDGES': 'selected_edges', 'PATHS': 'selected_paths'}
        expected = {
            'POINTS': {(first.id, 'OUTER', index) for index in range(4)} |
                      {(first.id, first_path.id, index) for index in range(2)},
            'EDGES': set(op.session.document.edges(first.id)) |
                     set(op.session.document.edges(first.id, first_path.id)),
            'PATHS': {(first.id, first_path.id)}}
        partner = {
            'POINTS': {(second.id, 'OUTER', index) for index in range(4)} |
                      {(second.id, second_path.id, index) for index in range(2)},
            'EDGES': set(op.session.document.edges(second.id)) |
                     set(op.session.document.edges(second.id, second_path.id)),
            'PATHS': {(second.id, second_path.id)}}
        for target, field in collections.items():
            op.session.clear_selection()
            op.session.acquisition_target = target
            drag((-.05, -.05), (.25, .35))
            yield
            check(getattr(op.session, field) == expected[target], target + ' box selects exact stored identities')
            drag((.27, -.05), (.55, .35), shift=True)
            yield
            check(getattr(op.session, field) == expected[target] | partner[target],
                  target + ' Shift box adds exact identities')
            drag((.27, -.05), (.55, .35), alt=True)
            yield
            check(getattr(op.session, field) == expected[target], target + ' Alt box subtracts only its identities')
            op.session.clear_selection()
            start = (-.05, -.05)
            op.pointer = op.view.screen(start, op.canvas_layout.canvas)
            op.design_action('SELECT_LASSO')
            for point in ((.25, -.05), (.25, .35), (-.05, .35), start):
                post('MOUSEMOVE', 'NOTHING', world=point)
                yield
            draw(target + ' native lasso preview')
            post('LEFTMOUSE', 'RELEASE', world=start)
            yield
            check(getattr(op.session, field) == expected[target],
                  target + ' native lasso selects exact stored identities')
            prior = op.session.get_selection_state()
            op.design_action('SELECT_LASSO')
            post('MOUSEMOVE', 'NOTHING', world=(.5, .3))
            yield
            key('ESC')
            yield
            check(op.session.get_selection_state() == prior, target + ' cancelled lasso preserves selection')
        first, _ = fixture()
        edge = op.session.document.edge(first.id, 0)
        drag((.1, 0), (.1, .03))
        yield
        check(op.session.selected_edges == {edge} and not op.session.selected_patterns,
              'bare edge drag selects edge geometry without its parent piece')
        check(all(abs(op.session.document.find(first.id).vertices[index].y - .03) < 1e-8 for index in (0, 1)) and
              all(abs(op.session.document.find(first.id).vertices[index].y - .3) < 1e-8 for index in (2, 3)),
              'bare edge drag moves only the two shared endpoints')
        op.show_card('EDGE')
        check(any('BEND_EDGE' in row for _, row in op.minimal_card()[2]),
              'edge bending remains an explicit contextual action')
        op.card_kind = None
        op.session.selected = first.id
        path = op.session.add_path([(.04, .1), (.16, .2)])
        boundary = list(op.session.document.find(first.id).points)
        op.session.select_path(first.id, path.id)
        yield from numeric('MOVE', '1cm')
        check(op.session.document.find(first.id).points == boundary,
              'internal-path numeric transform leaves unshared boundary unchanged')

    def sewn_component_follow():
        first, second = fixture(sewn=True)
        op.session.add([(.6, 0), (.8, 0), (.8, .3), (.6, .3)])
        third = op.session.document.patterns[-1]
        op.session.sew(op.session.document.edge(second.id, 1), op.session.document.edge(third.id, 3))
        op.session.select_piece(first.id)
        op.session.set_pivot(0, 0)
        op.persist()
        before = {piece.id: list(piece.points) for piece in op.session.document.patterns}
        seam_ids = [seam.id for seam in op.session.document.seams]
        undo_count = len(op.session.undo_stack)
        yield from numeric('SCALE', '1.1')
        check(op.card_kind == 'SEAM_WARNING', 'single sewn piece scale pauses for a warning')
        check(any('INCLUDE_SEWN' in row for _, row in op.minimal_card()[2]),
              'whole-piece warning offers explicit sewn-component follow')
        click_action('INCLUDE_SEWN')
        yield
        check(op.session.selected_patterns == {first.id, second.id, third.id},
              'explicit sewn-component follow includes the indirectly sewn third piece visibly')
        for piece in op.session.document.patterns:
            check(all(math.dist(point, (old[0] * 1.1, old[1] * 1.1)) < 1e-8
                      for point, old in zip(piece.points, before[piece.id])),
                  'sewn closure scales each vertex once about the original pivot')
        check(len(op.session.undo_stack) == undo_count + 1 and
              [seam.id for seam in op.session.document.seams] == seam_ids,
              'explicit sewn closure commits once and preserves seam identities')
        draw('Explicit sewn-component follow result')

    def pivot_targets():
        first, second = fixture()
        op.session.select_piece(first.id)
        second.vertices[0].outgoing = (.15, .08)
        second.vertices[1].incoming = (-.02, .02)
        curved_midpoint = curves.at_length(op.session.document.edge_curve(op.session.document.edge(second.id, 0)), .5)
        for ui_scale in (1.0, 2.0):
            bpy.context.preferences.view.ui_scale = ui_scale
            yield
            op.canvas_layout = op.make_layout()
            for zoom in (300, 600, 1200):
                op.view.zoom = zoom
                targets = (((0, 0), 'Vertex'), ((.1, 0), 'Midpoint'),
                           (curved_midpoint, 'Midpoint'), ((.1, .15), 'Selection center'),
                           ((.25, .38), 'Free'))
                for point, label in targets:
                    op.start_set_pivot()
                    post('MOUSEMOVE', 'NOTHING', world=point)
                    yield
                    check(op.gesture is not None and label in op.gesture.get('label', ''),
                          f'UI scale {ui_scale:g}, zoom {zoom}, pivot is labeled {label}')
                    draw(label + ' native pivot preview')
                    drag(point, point)
                    yield
                    expected = point
                    if label == 'Free':
                        pixel = screen(point)
                        expected = op.view.world((pixel[0] - op._region.x, pixel[1] - op._region.y),
                                                 op.canvas_layout.canvas)
                    check(math.dist(op.session.get_pivot(), expected) < .0001,
                          f'UI scale {ui_scale:g}, zoom {zoom}, {label} pivot is within 0.1 mm')
        bpy.context.preferences.view.ui_scale = 1.0
        op.canvas_layout = op.make_layout()
        op.start_set_pivot()
        post('MOUSEMOVE', 'NOTHING', world=(.17, .17))
        yield
        check(op.gesture.get('label') == 'Free', 'free pivot is labeled before placement')
        drag((.17, .17), (.17, .17))
        yield
        pivot = op.session.get_pivot()
        op.view.pan(35, -20)
        op.view.zoom *= 1.2
        check(op.session.get_pivot() == pivot, 'pan and zoom preserve the placed pivot in world coordinates')
        op.start_set_pivot()
        post('MOUSEMOVE', 'NOTHING', world=second.points[0])
        yield
        check('Vertex' in op.gesture.get('label', ''), 'pivot can snap to an unselected piece vertex')
        key('ESC')
        yield

    def check_numeric_scale():
        results = []
        for text in ('1.1', '110%'):
            first, second = fixture()
            op.session.selected = second.id
            internal = op.session.add_path([(.34, .1), (.44, .2)])
            op.session.add([(.6, 0), (.8, 0), (.8, .3), (.6, .3)])
            third = op.session.document.patterns[-1]
            selected_edge = op.session.document.edge(second.id, 2)
            op.session.select_piece(first.id)
            op.session.select_point(first.id, 'OUTER', 0, toggle=True)
            op.session.select_point(second.id, 'OUTER', 0, toggle=True)
            op.session.select_edge(selected_edge, toggle=True)
            op.session.select_path(second.id, internal.id, toggle=True)
            op.persist()
            pivot = (third.vertices[0].x, third.vertices[0].y)
            op.start_set_pivot()
            post('MOUSEMOVE', 'NOTHING', world=pivot)
            yield
            drag(pivot, pivot)
            yield
            check(op.session.get_pivot() == pivot, 'numeric scale pivot snaps to third piece vertex')
            selected_keys = [(first.id, 'OUTER', index) for index in range(4)]
            selected_keys += [(second.id, 'OUTER', index) for index in (0, 2, 3)]
            selected_keys += [(second.id, internal.id, index) for index in range(2)]
            before = {}
            for pid, path, index in selected_keys:
                vertex = op.session.document.find(pid).path(path).vertices[index]
                before[(pid, path, index)] = (vertex.x, vertex.y)
            op.snap = True
            yield from numeric('SCALE', text)
            for (pid, path, index), point in before.items():
                vertex = op.session.document.find(pid).path(path).vertices[index]
                expected = (pivot[0] + 1.1 * (point[0] - pivot[0]), pivot[1] + 1.1 * (point[1] - pivot[1]))
                check(math.dist((vertex.x, vertex.y), expected) < 1e-8,
                      'numeric scale with snap on moves resolved node by exact 1.1 without grid rounding')
            redundant = op.session.document.find(first.id).vertices[0]
            expected_red = (pivot[0] + 1.1 * (before[(first.id, 'OUTER', 0)][0] - pivot[0]),
                            pivot[1] + 1.1 * (before[(first.id, 'OUTER', 0)][1] - pivot[1]))
            check(math.dist((redundant.x, redundant.y), expected_red) < 1e-8,
                  'redundant point on selected piece scales exactly once')
            values = [(v.x, v.y) for piece in op.session.document.patterns for v in piece.vertices]
            results.append(values)
        check(all(math.dist(p0, p1) < 1e-8 for p0, p1 in zip(results[0], results[1])),
              '1.1 and 110 percent produce identical scaled coordinates within 1e-8 m')
        for text in ('0', '-1', 'NaN', 'inf', '1..2', 'xyz'):
            first, second = fixture()
            op.session.select_piece(first.id)
            before_doc = op.session.document.dumps()
            history_count = len(op.session.undo_stack)
            yield from numeric('SCALE', text)
            check(op.session.document.dumps() == before_doc and len(op.session.undo_stack) == history_count,
                  'invalid scale text ' + text + ' leaves document and undo count untouched')
            key('ESC')
            yield

    def check_panel_marquee():
        for ui_scale in (1.0, 2.0):
            bpy.context.preferences.view.ui_scale = ui_scale
            yield
            op.canvas_layout = op.make_layout()
            for zoom in (300, 600, 1200):
                op.view.zoom = zoom
                for reverse in (False, True):
                    first, second = fixture()
                    op.session.clear_selection()
                    op.session.acquisition_target = 'PIECES'
                    start, finish = ((-.1, -.1), (.6, .4))
                    if reverse:
                        start, finish = finish, start
                    drag(start, finish)
                    yield
                    check(op.session.selected_patterns == {first.id, second.id} and not op.session.selected_points,
                          f'UI scale {ui_scale:g}, zoom {zoom}, {"crossing" if reverse else "enclose"} selects exactly two panels and zero points')
        bpy.context.preferences.view.ui_scale = 1.0
        yield
        op.canvas_layout = op.make_layout()
        op.view.zoom = 600

        fixture()
        op.session.clear_selection()
        op.session.acquisition_target = 'PIECES'
        op.session.add([(0, 0), (.2, 0), (.2, .3), (0, .3)])
        curved = op.session.document.patterns[-1]
        curved.vertices[0].outgoing = (.08, .08)
        curved.vertices[1].incoming = (-.08, .08)
        op.session.add([(.3, 0), (.5, 0), (.5, .1), (.4, .1), (.4, .3), (.3, .3)])
        concave = op.session.document.patterns[-1]
        op.persist()

        drag((-.05, -.05), (.1, .15))
        yield
        check(curved.id not in op.session.selected_patterns, 'enclose partial drag excludes curved piece')
        drag((.1, .15), (-.05, -.05))
        yield
        check(curved.id in op.session.selected_patterns, 'crossing partial drag includes curved piece')

        op.session.clear_selection()
        drag((.25, -.05), (.35, .15))
        yield
        check(concave.id not in op.session.selected_patterns, 'enclose partial drag excludes concave piece')
        drag((.35, .15), (.25, -.05))
        yield
        check(concave.id in op.session.selected_patterns, 'crossing partial drag includes concave piece')

    def check_region_and_lasso():
        first, second = fixture()
        op.session.selected = first.id
        first_path = op.session.add_path([(.04, .08), (.16, .2)])
        op.session.selected = second.id
        second_path = op.session.add_path([(.34, .08), (.46, .2)])
        collections = {'POINTS': 'selected_points', 'EDGES': 'selected_edges', 'PATHS': 'selected_paths'}
        expected = {
            'POINTS': {(first.id, 'OUTER', index) for index in range(4)} |
                      {(first.id, first_path.id, index) for index in range(2)},
            'EDGES': set(op.session.document.edges(first.id)) |
                     set(op.session.document.edges(first.id, first_path.id)),
            'PATHS': {(first.id, first_path.id)}}
        partner = {
            'POINTS': {(second.id, 'OUTER', index) for index in range(4)} |
                      {(second.id, second_path.id, index) for index in range(2)},
            'EDGES': set(op.session.document.edges(second.id)) |
                     set(op.session.document.edges(second.id, second_path.id)),
            'PATHS': {(second.id, second_path.id)}}
        for target, field in collections.items():
            op.session.clear_selection()
            op.session.acquisition_target = target
            drag((-.05, -.05), (.25, .35))
            yield
            check(getattr(op.session, field) == expected[target], target + ' box replace selects exact stored identities')
            drag((.27, -.05), (.55, .35), shift=True)
            yield
            check(getattr(op.session, field) == expected[target] | partner[target], target + ' box shift-add adds exact identities')
            drag((.27, -.05), (.55, .35), alt=True)
            yield
            check(getattr(op.session, field) == expected[target], target + ' box alt-subtract removes exact identities')
            drag((-.05, -.05), (.55, .35), shift=True)
            yield
            check(getattr(op.session, field) == expected[target] | partner[target],
                  target + ' overlapping shift box keeps existing members and adds only new identities')
            drag((.27, -.05), (.55, .35), alt=True)
            yield
            check(getattr(op.session, field) == expected[target], target + ' alt box after overlap removes only the partner identities')
            drag((.65, .65), (.85, .85))
            yield
            check(not getattr(op.session, field), target + ' empty box replace clears selection')
            op.session.clear_selection()
            start = (-.05, -.05)
            op.pointer = op.view.screen(start, op.canvas_layout.canvas)
            op.design_action('SELECT_LASSO')
            for point in ((.25, -.05), (.25, .35), (-.05, .35), start):
                post('MOUSEMOVE', 'NOTHING', world=point)
            post('LEFTMOUSE', 'RELEASE', world=start)
            yield
            check(getattr(op.session, field) == expected[target], target + ' native lasso replace selects exact stored identities')
            partner_start = (.27, -.05)
            op.pointer = op.view.screen(partner_start, op.canvas_layout.canvas)
            op.design_action('SELECT_LASSO')
            for point in ((.55, -.05), (.55, .35), (.27, .35), partner_start):
                post('MOUSEMOVE', 'NOTHING', world=point, shift=True)
            post('LEFTMOUSE', 'RELEASE', world=partner_start, shift=True)
            yield
            check(getattr(op.session, field) == expected[target] | partner[target], target + ' native lasso shift-add adds exact partner identities')
            op.pointer = op.view.screen(partner_start, op.canvas_layout.canvas)
            op.design_action('SELECT_LASSO')
            for point in ((.55, -.05), (.55, .35), (.27, .35), partner_start):
                post('MOUSEMOVE', 'NOTHING', world=point, alt=True)
            post('LEFTMOUSE', 'RELEASE', world=partner_start, alt=True)
            yield
            check(getattr(op.session, field) == expected[target], target + ' native lasso alt-subtract removes exact identities')
            empty_start = (.65, .65)
            op.pointer = op.view.screen(empty_start, op.canvas_layout.canvas)
            op.design_action('SELECT_LASSO')
            for point in ((.85, .65), (.85, .85), (.65, .85), empty_start):
                post('MOUSEMOVE', 'NOTHING', world=point)
            post('LEFTMOUSE', 'RELEASE', world=empty_start)
            yield
            check(not getattr(op.session, field), target + ' empty lasso replace clears selection')
            prior = op.session.get_selection_state()
            op.design_action('SELECT_LASSO')
            post('MOUSEMOVE', 'NOTHING', world=(.5, .3))
            yield
            key('ESC')
            yield
            check(op.session.get_selection_state() == prior, target + ' cancelled lasso preserves prior selection')

        op.session.clear_selection()
        op.session.acquisition_target = 'POINTS'
        drag((-.05, -.05), (.25, .35))
        yield
        pts_before = set(op.session.selected_points)
        op.session.acquisition_target = 'EDGES'
        check(op.session.selected_points == pts_before, 'switching target to EDGES preserves existing selected points')
        drag((.27, -.05), (.55, .35), shift=True)
        yield
        check(op.session.selected_points == pts_before and op.session.selected_edges == partner['EDGES'],
              'shift-adding edges keeps prior points and adds edges')
        op.session.acquisition_target = 'PATHS'
        check(op.session.selected_points == pts_before and op.session.selected_edges == partner['EDGES'],
              'switching target to PATHS preserves points and edges')

        op.session.clear_selection()
        op.session.acquisition_target = 'POINTS'
        selfcross_start = (-.05, -.05)
        op.pointer = op.view.screen(selfcross_start, op.canvas_layout.canvas)
        op.design_action('SELECT_LASSO')
        for point in ((.25, .35), (.25, -.05), (-.05, .35), selfcross_start):
            post('MOUSEMOVE', 'NOTHING', world=point)
        post('LEFTMOUSE', 'RELEASE', world=selfcross_start)
        yield
        poly_pts = [(-.05, -.05), (.25, .35), (.25, -.05), (-.05, .35)]
        expected_evenodd = {k for k in expected['POINTS'] if point_in_lasso(
            (op.session.document.find(k[0]).path(k[1]).vertices[k[2]].x,
             op.session.document.find(k[0]).path(k[1]).vertices[k[2]].y),
            poly_pts)}
        check(op.session.selected_points == expected_evenodd,
              'self-crossing lasso matches even-odd semantics with exact point IDs')

    def check_click_and_toggle():
        first, second = fixture()
        drag((.1, .15), (.1, .15))
        yield
        check(len(op.session.selected_patterns) == 1 and op.card_kind is None,
              'bare piece click selects cleanly with no card')
        drag((.4, .15), (.4, .15), shift=True)
        yield
        check(len(op.session.selected_patterns) == 2, 'shift click adds second panel (piece count 2)')
        drag((.1, .15), (.1, .15), shift=True)
        yield
        check(len(op.session.selected_patterns) == 1 and second.id in op.session.selected_patterns,
              'shift click toggles first panel off (piece count 1)')
        drag((.4, .15), (.4, .15), shift=True)
        yield
        check(not op.session.has_selection(), 'shift click toggles second panel off (piece count 0)')

        drag((0, 0), (0, 0))
        yield
        check(len(op.session.selected_points) == 1 and op.card_kind is None,
              'bare point click selects cleanly with no card')
        drag((0, 0), (0, 0), shift=True)
        yield
        check(not op.session.has_selection() and op.session.selected is None and op.session.corner is None,
              'toggling final point off leaves effective and legacy state empty')

        op.session.select_edge(op.session.document.edge(first.id, 0))
        drag((.1, 0), (.1, 0), shift=True)
        yield
        check(not op.session.has_selection() and op.session.segment is None,
              'toggling final edge off leaves effective and legacy segment empty')

        before_doc = op.session.document.dumps()
        history_count = len(op.session.undo_stack)
        for arrow in ('LEFT_ARROW', 'RIGHT_ARROW', 'UP_ARROW', 'DOWN_ARROW'):
            key(arrow)
            key(arrow, shift=True)
            key(arrow, alt=True)
        yield
        check(op.session.document.dumps() == before_doc and len(op.session.undo_stack) == history_count,
              'arrow keys on empty selection alter no geometry and create no undo')
        drag((.25, .4), (.28, .45))
        yield
        check(op.session.document.dumps() == before_doc and len(op.session.undo_stack) == history_count and
              not op.session.has_selection(),
              'empty-canvas drag with empty selection alters no geometry and creates no undo')

        op.session.select_piece(first.id)
        op.session.select_piece(second.id, toggle=True)
        group_state = op.session.get_selection_state()
        post('LEFTMOUSE', world=(.1, .15))
        yield
        check(op.session.get_selection_state() == group_state, 'group drag press never collapses selection')
        post('LEFTMOUSE', 'RELEASE', world=(.1, .15))
        yield

    def modified_drag(start, finish, **modifiers):
        post('MOUSEMOVE', 'NOTHING', world=start)
        post('LEFTMOUSE', world=start)
        post('MOUSEMOVE', 'NOTHING', world=finish, **modifiers)
        post('LEFTMOUSE', 'RELEASE', world=finish, **modifiers)

    def pixel_world(world):
        position = screen(world)
        return op.view.world((position[0] - op._region.x, position[1] - op._region.y), op.canvas_layout.canvas)

    def check_snap_and_axis():
        grab = (.1, .15)

        def aligned_fixture(select, snap):
            first, second = fixture()
            for ox in (0.0, .5 / op.view.zoom):
                for oy in (0.0, .5 / op.view.zoom):
                    op.view.cx, op.view.cy = .25 + ox, .15 + oy
                    if math.dist(pixel_world(grab), grab) < 1e-9:
                        select(first)
                        op.snap = snap
                        op.sync_selection()
                        return first
            raise AssertionError('no grid-aligned grab pixel at this zoom')

        def vertex(first):
            v = op.session.document.find(first.id).vertices[0]
            return v.x, v.y

        def snapped_case(select, snap, start, finish, expected, label, **modifiers):
            first = aligned_fixture(select, snap)
            before = vertex(first)
            modified_drag(start, finish, **modifiers)
            yield
            after = vertex(first)
            check(abs(after[0] - before[0] - expected[0]) < 1e-8 and abs(after[1] - before[1] - expected[1]) < 1e-8,
                  label)

        def continuous_case(select, snap, finish, label, **modifiers):
            first = aligned_fixture(select, snap)
            before = vertex(first)
            travel = tuple(b - a for a, b in zip(pixel_world(grab), pixel_world(finish)))
            check(any(abs(t * 100 - round(t * 100)) > 1e-3 for t in travel), label + ' fixture travel is off the 1 cm grid')
            modified_drag(grab, finish, **modifiers)
            yield
            after = vertex(first)
            check(abs(after[0] - before[0] - travel[0]) < 1e-8 and abs(after[1] - before[1] - travel[1]) < 1e-8, label)

        piece = lambda first: op.session.select_piece(first.id)
        corner = lambda first: op.session.select_point(first.id, 'OUTER', 0)
        yield from snapped_case(piece, True, grab, (.137, .162), (.04, 0.0), 'panel positive dominant X snapped drag is +4 cm X and zero Y', shift=True)
        yield from snapped_case(piece, True, grab, (.112, .187), (0.0, .04), 'panel positive dominant Y snapped drag is zero X and +4 cm Y', shift=True)
        yield from snapped_case(piece, True, grab, (.063, .138), (-.04, 0.0), 'panel negative dominant X snapped drag reaches negative coordinates at -4 cm X and zero Y', shift=True)
        yield from snapped_case(piece, True, grab, (.088, .113), (0.0, -.04), 'panel negative dominant Y snapped drag reaches negative coordinates at zero X and -4 cm Y', shift=True)
        yield from snapped_case(corner, True, (0, 0), (.037, .012), (.04, 0.0), 'point positive dominant X snapped drag is +4 cm X and zero Y', shift=True)
        yield from snapped_case(corner, True, (0, 0), (-.012, -.037), (0.0, -.04), 'point negative dominant Y snapped drag reaches -4 cm Y and zero X', shift=True)
        yield from continuous_case(piece, False, (.137, .162), 'snap off unconstrained drag follows the cursor continuously')
        yield from continuous_case(piece, True, (.137, .162), 'Ctrl inverts snap on to continuous unconstrained movement', ctrl=True)
        yield from snapped_case(piece, False, grab, (.137, .162), (.04, 0.0), 'Ctrl inverts snap off to snapped dominant axis movement', ctrl=True, shift=True)
        first = aligned_fixture(piece, True)
        before = vertex(first)
        yield from numeric('MOVE', '2.5cm')
        check(abs(vertex(first)[0] - before[0] - .025) < 1e-8 and abs(vertex(first)[1] - before[1]) < 1e-8,
              'numeric input with snap enabled remains exact 2.5 cm without grid rounding')

    def check_connected_and_invert():
        first, second = fixture(sewn=True)
        op.session.add([(.6, 0), (.8, 0), (.8, .3), (.6, .3)])
        third = op.session.document.patterns[-1]
        op.session.sew(op.session.document.edge(second.id, 1), op.session.document.edge(third.id, 3))
        op.session.selected = second.id
        internal = op.session.add_path([(.34, .1), (.44, .2)])
        op.persist()

        for target in ('PIECES', 'POINTS', 'EDGES', 'PATHS'):
            op.session.clear_selection()
            if target == 'PIECES':
                op.session.select_piece(first.id)
            elif target == 'POINTS':
                op.session.select_point(first.id, 'OUTER', 0)
            elif target == 'EDGES':
                op.session.select_edge(op.session.document.edge(first.id, 0))
            elif target == 'PATHS':
                op.session.select_path(second.id, internal.id)
            op.session.acquisition_target = target
            def identities():
                state = op.session.get_selection_state()
                return {name: state[name] for name in ('patterns', 'points', 'edges', 'paths', 'target')}
            initial_state = identities()
            key('I', ctrl=True)
            yield
            check(identities() != initial_state, target + ' Ctrl+I inverts selection')
            changed = [name for name in ('patterns', 'points', 'edges', 'paths') if identities()[name] != initial_state[name]]
            check(changed == [{'PIECES': 'patterns', 'POINTS': 'points', 'EDGES': 'edges', 'PATHS': 'paths'}[target]],
                  target + ' Ctrl+I changes only its own kind')
            key('I', ctrl=True)
            yield
            check(identities() == initial_state, target + ' double invert restores exact IDs')

        op.session.clear_selection()
        op.session.active_entity = ('POINT', (second.id, internal.id, 0))
        op.session.select_point(second.id, internal.id, 0)
        key('L', ctrl=True)
        yield
        check(op.session.selected_points == {(second.id, internal.id, 0), (second.id, internal.id, 1)},
              'connected path selects entire internal stored path')
        check(not any(k[1] == 'OUTER' for k in op.session.selected_points),
              'connected path stays strictly within the seeded stored path')

        op.session.clear_selection()
        op.session.select_piece(first.id)
        op.session.select_connected('SEWN')
        check(op.session.selected_patterns == {first.id, second.id, third.id},
              'sewn pieces follow seam topology transitively across separated geometry')

        op.choose_tool('SELECT')
        key('I')
        yield
        check(op.tool == 'INTERNAL', 'plain I shortcut selects internal tool')
        key('V')
        yield
        check(op.tool == 'SELECT', 'plain V shortcut restores select tool')
        lengths_before = op._scene.dd_lengths_visible
        key('L')
        yield
        check(op._scene.dd_lengths_visible != lengths_before, 'plain L shortcut toggles lengths visibility')
        key('L')
        yield
        check(op._scene.dd_lengths_visible == lengths_before, 'plain L shortcut toggles lengths back')
        op.session.select_piece(first.id)
        key('A', alt=True)
        yield
        check(not op.session.has_selection(), 'plain Alt+A clears selection completely')

    def check_42_nudge():
        first, second = fixture()
        op.session.selected = second.id
        internal = op.session.add_path([(.34, .1), (.44, .2)])
        op.session.select_piece(first.id)
        op.session.select_point(first.id, 'OUTER', 0, toggle=True)
        op.session.select_point(second.id, 'OUTER', 0, toggle=True)
        op.session.select_edge(op.session.document.edge(second.id, 2), toggle=True)
        op.session.select_path(second.id, internal.id, toggle=True)
        op.sync_selection()
        op.persist()

        before = op.session.document.dumps()
        history_count = len(op.session.undo_stack)
        op.numeric = dict(key='test', text='12', cursor=2, selected=False)
        key('RIGHT_ARROW')
        yield
        check(op.session.document.dumps() == before and len(op.session.undo_stack) == history_count,
              'active numeric text field blocks 2D pattern nudge')
        op.numeric = None

        op.library_edit = dict(key='dd_library_name', text='Outfit', original='Outfit', cursor=6, selected=False)
        key('RIGHT_ARROW')
        yield
        check(op.session.document.dumps() == before and len(op.session.undo_stack) == history_count,
              'active library text input blocks 2D pattern nudge')
        op.library_edit = None

        op.reveal_3d()
        yield
        exposed_pt = (round(op.canvas_layout.panel.x - 60 + op._region.x), round(op.canvas_layout.panel.y + 50 + op._region.y))
        check(0 <= op.canvas_layout.panel.x - 60 < op._region.width and not op.canvas_layout.panel.contains(op.canvas_layout.panel.x - 60, op.canvas_layout.panel.y + 50),
              'exposed probe lies in the exposed 3D viewport outside the editor panel')
        window.event_simulate(type='RIGHT_ARROW', value='PRESS', x=exposed_pt[0], y=exposed_pt[1])
        window.event_simulate(type='RIGHT_ARROW', value='RELEASE', x=exposed_pt[0], y=exposed_pt[1])
        yield
        check(op.session.document.dumps() == before and len(op.session.undo_stack) == history_count,
              'pointer in exposed 3D viewport blocks 2D pattern nudge')

    def check_transaction_safety():
        first, second = fixture(sewn=True)
        original = op.session.document.dumps()
        history_count = len(op.session.undo_stack)

        op.session.select_piece(first.id)
        op.session.set_pivot(.05, .05)
        op.sync_selection()
        yield from numeric('MOVE', '1cm')
        check(len(op.session.undo_stack) == history_count + 1, 'confirmed Enter transform adds exactly one undo entry')
        committed_document = op.session.document.dumps()
        committed_selection = op.session.get_selection_state()
        check(committed_selection['placed_pivot'] == (.06, .05), 'confirmed move carries the placed pivot with the selection')
        op.session.clear_selection()
        op.session.select_point(second.id, 'OUTER', 1)
        op.session.set_pivot(.4, .2)
        key('Z', ctrl=True)
        yield
        check(op.session.document.dumps() == original, 'undo restores exact pre-transform source document')
        key('Z', ctrl=True, shift=True)
        yield
        check(op.session.document.dumps() == committed_document and abs(op.session.document.find(first.id).vertices[0].x - .01) < 1e-8,
              'redo restores confirmed transform geometry')
        check(op.session.get_selection_state() == committed_selection,
              'redo restores the committed selection, active entity and pivot rather than a stale one')
        key('Z', ctrl=True)
        yield

        drag((.2, .3), (.2, .35))
        yield
        check(op.card_kind == 'SEAM_WARNING', 'endpoint drag raises seam warning card')
        click_action('APPLY_MISMATCH')
        yield
        check(len(op.session.undo_stack) == history_count + 1, 'confirming click Apply adds exactly one undo entry')
        key('Z', ctrl=True)
        yield

        drag((.2, .3), (.2, .35))
        yield
        post('LEFTMOUSE', world=(.4, .2))
        post('LEFTMOUSE', 'RELEASE', world=(.4, .2))
        yield
        check(op.card_kind is None and not getattr(op, 'pending_transform', None) and
              op.session.document.dumps() == original and len(op.session.undo_stack) == history_count,
              'click outside the warning card cancels frozen transform and records zero undo')

        op.start_transform('MOVE')
        post('A', unicode='3')
        yield
        post('WINDOW_DEACTIVATE', 'NOTHING')
        yield
        check(op.gesture is None and op.session.document.dumps() == original and len(op.session.undo_stack) == history_count,
              'WINDOW_DEACTIVATE focus loss cancels transform cleanly without history')

        op.start_transform('SCALE')
        post('A', unicode='-')
        post('A', unicode='1')
        yield
        key('RET')
        yield
        check(op.session.document.dumps() == original and len(op.session.undo_stack) == history_count,
              'invalid geometry blocks commit and records zero undo')
        key('ESC')
        yield

    def check_3d_arrangement_boundary():
        first, second = fixture()
        scene = op._scene
        body = scene.dd_avatar
        check(body is not None, 'avatar body is present in scene')
        arrangement.ensure_volumes(bpy.context)
        live_panels.sync(bpy.context)
        area = op._area
        area.spaces.active.region_3d.update()
        scene.dd_reference_visible = True

        op.session.selected = first.id
        op.session.select_piece(first.id)
        op.session.select_piece(second.id, toggle=True)
        op.session.select_point(first.id, 'OUTER', 0, toggle=True)
        op.session.select_edge(op.session.document.edge(second.id, 2), toggle=True)
        check(arrangement_controls.selected_piece(bpy.context) == second.id and op.session.active_entity[0] == 'EDGE',
              '2D multiselection bridges only the last-selected active entity piece to 3D arrangement')

        op.reveal_3d()
        yield
        orbit_pt = (round(op.canvas_layout.panel.x - 50 + op._region.x), round(op.canvas_layout.panel.y + 50 + op._region.y))
        check(0 <= op.canvas_layout.panel.x - 50 < op._region.width and not op.canvas_layout.panel.contains(op.canvas_layout.panel.x - 50, op.canvas_layout.panel.y + 50),
              'orbit probe lies in the exposed 3D viewport outside the editor panel')
        view = area.spaces.active.region_3d
        rotation_before = view.view_rotation.copy()
        selection_before = op.session.get_selection_state()
        document_before = op.session.document.dumps()
        window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=orbit_pt[0], y=orbit_pt[1])
        window.event_simulate(type='MIDDLEMOUSE', value='PRESS', x=orbit_pt[0], y=orbit_pt[1])
        for step in range(1, 6):
            window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=orbit_pt[0] + 12 * step, y=orbit_pt[1] + 6 * step)
        window.event_simulate(type='MIDDLEMOUSE', value='RELEASE', x=orbit_pt[0] + 60, y=orbit_pt[1] + 30)
        yield
        yield
        check(view.view_rotation.rotation_difference(rotation_before).angle > 1e-4,
              'native middle-mouse orbit reaches the exposed 3D viewport')
        check(op.session.get_selection_state() == selection_before and op.session.document.dumps() == document_before,
              'viewport orbit leaves 2D selection and pattern unchanged')
        check(arrangement_controls._interaction.state == 'IDLE',
              'viewport orbit in 3D does not activate arrangement drag')
        check(not op.gesture, 'viewport orbit does not leak into 2D editor gesture')

        from mathutils import Quaternion
        view.view_location = body.matrix_world.translation
        view.view_rotation = Quaternion((1, 0, 0), math.pi / 2)
        view.view_distance = 6
        view.view_perspective = 'ORTHO'
        view.update()
        with bpy.context.temp_override(window=window, area=area, region=op._region):
            points = arrangement_controls.projected_points(bpy.context)
        target_pt = next((p for p in points if p.get('facing') and p['volume'] == 'chest'
                          and not op.canvas_layout.panel.contains(p['screen'][0], p['screen'][1])), None)
        if target_pt is None:
            target_pt = next((p for p in points if p.get('facing')), None)
        check(target_pt is not None, 'a facing arrangement point is available outside the 2D panel')
        tscreen = (round(target_pt['screen'][0] + op._region.x), round(target_pt['screen'][1] + op._region.y))
        window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=tscreen[0], y=tscreen[1])
        window.event_simulate(type='LEFTMOUSE', value='PRESS', x=tscreen[0], y=tscreen[1])
        window.event_simulate(type='LEFTMOUSE', value='RELEASE', x=tscreen[0], y=tscreen[1])
        yield
        yield
        arranged = garment.document(scene)
        check(arranged.find(second.id).arrangement is not None,
              'active piece received 3D arrangement placement')
        check(arranged.find(first.id).arrangement is None,
              'other piece in 2D multi-selection remained unarranged')

        box_start = screen((.05, .05))
        window.event_simulate(type='LEFTMOUSE', value='PRESS', x=box_start[0], y=box_start[1])
        window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=box_start[0] + 30, y=box_start[1] + 30)
        yield
        check(arrangement_controls._interaction.state == 'IDLE',
              '2D box marquee does not leak into 3D arrangement interaction')
        window.event_simulate(type='LEFTMOUSE', value='RELEASE', x=box_start[0] + 30, y=box_start[1] + 30)
        yield


    def auto_edge_warning():
        def auto_fixture():
            first, second = fixture()
            op.session.set_point_type('AUTO', [(first.id, 'OUTER', index) for index in range(4)])
            op.session.clear_selection()
            op.persist()
            op.sync_selection()
            return op.session.document.find(first.id)

        def rendered_deviation(edge, source_samples, delta):
            op.session.document.find(edge.pattern).outline()
            control = op.session.document.edge_curve(edge)
            return max(math.dist(curves.evaluate(control, i / 100), (x + delta[0], y + delta[1]))
                       for i, (x, y) in enumerate(source_samples))

        first = auto_fixture()
        edge = op.session.document.edge(first.id, 0)
        first.outline()
        source_control = op.session.document.edge_curve(edge)
        source_samples = [curves.evaluate(source_control, i / 100) for i in range(101)]
        original = op.session.document.dumps()
        undo_count = len(op.session.undo_stack)
        grab = curves.evaluate(source_control, .5)
        lift = (grab[0], grab[1] + .03)
        drag(grab, lift)
        yield
        check(op.card_kind == 'SEAM_WARNING' and op.session.selected_edges == {edge},
              'partial AUTO edge drag stops at a pre-commit curve warning')
        check(op.session.document.dumps() == original and len(op.session.undo_stack) == undo_count,
              'unconfirmed AUTO edge drag leaves document and undo count unchanged')
        report = op.pending_transform['report']
        delta = op.pending_transform['param']
        card = op.minimal_card()
        rows = [row for _, row in card[2]]
        card_text = ' '.join(str(value) for row in rows for value in row)
        check(report['curve_deviation_mm'] > 1e-3 and f"{report['curve_deviation_mm']:.3f} mm" in card_text,
              'curve warning card shows the exact selected-curve deviation in mm')
        check(any(row[0] == 'CONVERT_AUTO' for row in rows) and 'Apply with change' in card_text and 'Cancel' in card_text,
              'curve warning offers Convert to smooth, Apply with change and Cancel')
        draw('AUTO curve warning')
        key('ESC')
        yield
        check(op.card_kind is None and not op.pending_transform and op.session.document.dumps() == original,
              'Escape cancels the AUTO curve candidate exactly')
        drag(grab, lift)
        yield
        delta = op.pending_transform['param']
        click_action('CONVERT_AUTO')
        yield
        check(len(op.session.undo_stack) == undo_count + 1 and op.card_kind is None,
              'Convert to smooth commits the transform in one undo step')
        check(rendered_deviation(edge, source_samples, delta) < 1e-8,
              'converted selected curve equals the exact translation within 1e-8 m over 101 samples')
        check([v.point_type for v in op.session.document.find(first.id).vertices] == ['SMOOTH', 'SMOOTH', 'AUTO', 'AUTO'],
              'only the two selected AUTO endpoints convert to Smooth, visibly and on confirmation')
        key('Z', ctrl=True)
        yield
        check(op.session.document.dumps() == original, 'undo restores the AUTO source exactly')
        drag(grab, lift)
        yield
        reported = op.pending_transform['report']['curve_deviation_mm']
        delta = op.pending_transform['param']
        click_action('APPLY_MISMATCH')
        yield
        check(len(op.session.undo_stack) == undo_count + 1 and
              all(v.point_type == 'AUTO' for v in op.session.document.find(first.id).vertices),
              'Apply with change keeps AUTO points and records one undo step')
        check(abs(rendered_deviation(edge, source_samples, delta) * 1000 - reported) < 1e-6,
              'accepted AUTO change renders exactly the deviation the warning reported')
        whole = auto_fixture()
        before = op.session.document.dumps()
        op.session.select_piece(whole.id)
        op.sync_selection()
        yield from numeric('ROTATE', '37.5')
        check(op.card_kind is None and op.session.document.dumps() != before and len(op.session.undo_stack) == undo_count + 1,
              'whole-piece AUTO rotation commits without a curve warning')

    def selection_frame():
        def local_drag(start, finish, steps=4, press_mods=None, **modifiers):
            post('MOUSEMOVE', 'NOTHING', local=start)
            post('LEFTMOUSE', local=start, **(press_mods or {}))
            for step in range(1, steps + 1):
                t = step / steps
                post('MOUSEMOVE', 'NOTHING', local=(start[0] + (finish[0] - start[0]) * t, start[1] + (finish[1] - start[1]) * t), **modifiers)
            post('LEFTMOUSE', 'RELEASE', local=finish, **modifiers)

        def rotated(point, pivot, degrees):
            c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
            return pivot[0] + c * (point[0] - pivot[0]) - s * (point[1] - pivot[1]), pivot[1] + s * (point[0] - pivot[0]) + c * (point[1] - pivot[1])

        first, second = fixture()
        op.session.select_piece(first.id)
        op.sync_selection()
        frame = op.transform_frame()
        check(frame is not None and frame['knob'][1] > frame['rect'].y + frame['rect'].h,
              'selecting a piece shows a transform frame with a rotate knob above it')
        draw('Selection frame')
        op.pointer = frame['knob']
        check(op.transform_frame_hit() == 'ROTATE', 'hovering the knob targets rotation')
        draw('Hovered rotate knob')
        source = [(v.x, v.y) for v in first.vertices]
        pivot = op.session.get_pivot()
        undo_count = len(op.session.undo_stack)
        knob = frame['knob']
        radius = knob[1] - frame['pivot'][1]
        target = (frame['pivot'][0] + radius, frame['pivot'][1] + 3)
        post('MOUSEMOVE', 'NOTHING', local=knob)
        post('LEFTMOUSE', local=knob)
        post('MOUSEMOVE', 'NOTHING', local=((knob[0] + target[0]) / 2 + 20, (knob[1] + target[1]) / 2 + 20), shift=True)
        yield
        check(op.gesture and op.gesture.get('kind') == 'ROTATE' and op.gesture.get('candidate') is not None,
              'dragging the knob shows a live rotation preview before release')
        draw('Live rotation ghost and readout')
        post('MOUSEMOVE', 'NOTHING', local=target, shift=True)
        post('LEFTMOUSE', 'RELEASE', local=target, shift=True)
        yield
        expected = [rotated(point, pivot, -90) for point in source]
        check(all(math.dist((v.x, v.y), e) < 1e-8 for v, e in zip(op.session.document.find(first.id).vertices, expected)),
              'Shift knob drag rotates exactly -90 degrees around the pivot')
        check(len(op.session.undo_stack) == undo_count + 1, 'frame rotation is one undo step')
        key('Z', ctrl=True)
        yield
        check([(v.x, v.y) for v in op.session.document.find(first.id).vertices] == source, 'undo restores the frame rotation')

        frame = op.transform_frame()
        corner = frame['corners'][2]
        pivot_screen = frame['pivot']
        outward = (pivot_screen[0] + (corner[0] - pivot_screen[0]) * 1.5, pivot_screen[1] + (corner[1] - pivot_screen[1]) * 1.5)
        before = [(v.x, v.y) for v in op.session.document.find(first.id).vertices]
        pivot = op.session.get_pivot()
        local_drag(corner, outward, shift=True)
        yield
        expected = [(pivot[0] + 1.5 * (x - pivot[0]), pivot[1] + 1.5 * (y - pivot[1])) for x, y in before]
        check(all(math.dist((v.x, v.y), e) < 1e-8 for v, e in zip(op.session.document.find(first.id).vertices, expected)),
              'Shift corner drag scales exactly 150 percent around the pivot')
        key('Z', ctrl=True)
        yield

        frame = op.transform_frame()
        before_doc = op.session.document.dumps()
        undo_count = len(op.session.undo_stack)
        post('MOUSEMOVE', 'NOTHING', local=frame['knob'])
        post('LEFTMOUSE', local=frame['knob'])
        post('LEFTMOUSE', 'RELEASE', local=frame['knob'])
        yield
        check(op.gesture is None and op.session.document.dumps() == before_doc and len(op.session.undo_stack) == undo_count,
              'clicking a handle without dragging changes nothing')

        frame = op.transform_frame()
        live_corner = op.session.document.find(first.id).vertices[0]
        corner_world = (live_corner.x, live_corner.y)
        corner_local = op.view.screen(corner_world, op.canvas_layout.canvas)
        local_drag(frame['pivot'], corner_local, press_mods=dict(alt=True), alt=True)
        yield
        check(op.session.get_pivot() == corner_world and op.session.document.dumps() == before_doc,
              'Alt+drag moves the pivot and snaps it to a corner without moving geometry')
        op.session.reset_pivot()
        frame = op.transform_frame()
        local_drag(frame['pivot'], (frame['pivot'][0] + 30, frame['pivot'][1]))
        yield
        check(op.session.document.dumps() != before_doc and op.gesture is None,
              'a plain drag starting on the pivot still moves the piece')

        first, second = fixture(sewn=True)
        op.session.select_point(first.id, 'OUTER', 1)
        op.session.select_point(first.id, 'OUTER', 2, toggle=True)
        op.sync_selection()
        original = op.session.document.dumps()
        undo_count = len(op.session.undo_stack)
        frame = op.transform_frame()
        corner = frame['corners'][2]
        pivot_screen = frame['pivot']
        local_drag(corner, (pivot_screen[0] + (corner[0] - pivot_screen[0]) * 1.5, pivot_screen[1] + (corner[1] - pivot_screen[1]) * 1.5), shift=True)
        yield
        check(op.card_kind == 'SEAM_WARNING' and op.session.document.dumps() == original and len(op.session.undo_stack) == undo_count,
              'scaling a sewn edge with the frame stops at the seam warning before mutation')
        draw('Frame seam warning')
        key('ESC')
        yield
        check(op.session.document.dumps() == original and not op.pending_transform, 'frame seam warning cancels exactly')

    def strip_click(action, owner):
        op.open_flyout(owner)
        rect = op.canvas_layout.buttons['STRIP_' + action][0]
        point = rect.x + rect.w / 2, rect.y + rect.h / 2
        post('LEFTMOUSE', local=point)
        post('LEFTMOUSE', 'RELEASE', local=point)

    def menu_rows():
        first, second = fixture()
        anchor = op.view.screen((.1, .15), op.canvas_layout.canvas)
        for row, opened in (('TRANSFORM_MENU', 'TRANSFORM_MENU'),
                            ('PIECE_CLONE_MENU', 'PIECE_CLONE'), ('PIECE_PLACEMENT_MENU', 'PIECE_PLACEMENT')):
            op.session.select_piece(first.id)
            op.show_card('PIECE', anchor)
            click_action(row)
            yield
            check(op.sub_card == opened, row + ' row opens its submenu beside the card')
            draw(opened + ' opened from the piece menu')
        op.choose_tool('SELECT')
        op.canvas_layout = op.make_layout()
        strip_click('SET_SELECT_TARGET_Points', 'SELECT')
        yield
        check(op.session.acquisition_target == 'POINTS', 'Area target row changes what box select picks')
        op.session.acquisition_target = 'PIECES'
        op.session.clear_selection()
        strip_click('SELECT_LASSO', 'SELECT')
        yield
        check(op.armed_selection == 'SELECT_LASSO' and op.gesture is None, 'Lasso row waits for the next canvas drag')
        start = (-.05, -.05)
        post('MOUSEMOVE', 'NOTHING', world=start)
        post('LEFTMOUSE', world=start)
        yield
        for point in ((.25, -.05), (.25, .35), (-.05, .35), start):
            post('MOUSEMOVE', 'NOTHING', world=point)
            yield
        post('LEFTMOUSE', 'RELEASE', world=start)
        yield
        check(first.id in op.session.selected_patterns and second.id not in op.session.selected_patterns,
              'Lasso row selects the enclosed piece on the next drag')
        op.session.select_piece(second.id, toggle=True)
        op.show_card('MULTI_SELECTION', anchor)
        click_action('DELETE')
        yield
        check(not op.session.document.patterns, 'multi-selection Delete row removes the selected pieces')
        fixture()
        sew = op.canvas_layout.buttons['SEW'][0]
        point = sew.x + sew.w / 2, sew.y + sew.h / 2
        post('LEFTMOUSE', local=point)
        post('LEFTMOUSE', 'RELEASE', local=point)
        yield
        check(op.tool == 'SEW' and op.card_kind is None, 'first dock click chooses the Sew tool')
        op.canvas_layout = op.make_layout()
        strip_click('SET_SEW_FREE', 'SEW')
        yield
        check(op.tool == 'SEW' and op._scene.dd_free_sewing, 'the strip switches to Free sewing on the 2D canvas')
        op.choose_tool('SELECT')
        post('LEFTMOUSE', local=point)
        post('LEFTMOUSE', 'RELEASE', local=point)
        yield
        check(op.tool == 'SEW' and op._scene.dd_free_sewing, 'dock Sew remembers Free sewing')
        op.choose_tool('SEW')
        check(not op._scene.dd_free_sewing, 'Segment sewing clears Free sewing')
        key('J', shift=True)
        yield
        check(op._scene.dd_free_sewing, 'Shift J chooses Free sewing over the 2D canvas')
        op.choose_tool('SEW')
        op.choose_tool('SELECT')

    def sequence():
        for name, procedure in (('Menu rows open and act when clicked', menu_rows),
                                ('Warning before seam damage', sewn_endpoint),
                                ('Nudge steps and transaction safety', nudge_steps),
                                ('Warning pauses repeat', paused_nudge),
                                ('Mixed rotation', mixed_rotation),
                                ('Numeric scale and cancellation', scale_and_cancel),
                                ('Region and click selection', region_and_clicks),
                                ('Mixed group drag and snapping', mixed_group_drag),
                                ('Region targets, lasso, and edge transforms', region_targets_and_edges),
                                ('AUTO edge curve warning', auto_edge_warning),
                                ('Selection frame', selection_frame),
                                ('Explicit sewn-component follow', sewn_component_follow),
                                ('Pivot placement', pivot_targets),
                                ('Numeric scale', check_numeric_scale),
                                ('Reliable panel marquee', check_panel_marquee),
                                ('Region target and lasso', check_region_and_lasso),
                                ('Click and toggle', check_click_and_toggle),
                                ('Existing snap and axis', check_snap_and_axis),
                                ('Connected and invert', check_connected_and_invert),
                                ('#42 nudge', check_42_nudge),
                                ('Transaction safety', check_transaction_safety),
                                ('3D and arrangement boundary', check_3d_arrangement_boundary)):
            try:
                yield from procedure()
                cases.append(dict(check=name, result='PASS'))
            except Exception:
                failure = traceback.format_exc()
                cases.append(dict(check=name, result='FAIL', evidence=failure))
                failures.append(name + ': ' + failure)
        op.cancel_transform()
        op._area.tag_redraw()

    steps = sequence()

    def tick():
        try:
            next(steps)
            return .012
        except StopIteration:
            data = dict(passed=passed, native_cases=cases, native_surface='window.event_simulate, active minimal editor')
            if failures:
                data['error'] = '\n'.join(failures)
            report_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            return None
        except Exception:
            report_path.write_text(json.dumps(dict(passed=passed, native_cases=cases,
                                                   error=traceback.format_exc()), indent=2), encoding='utf-8')
            return None

    bpy.app.timers.register(tick, first_interval=.1)


def run():
    passed=[]
    def check(ok,message):
        if not ok:raise AssertionError(message)
        passed.append(message)
        print('PASS:',message,flush=True)
    try:
        devil_designer.register()
        scene=bpy.context.scene
        scene.dd_library_dir=str(ROOT/'scratch'/'gui-library')
        scene.dd_spacing=.04
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=(0,0,1.2))
        body=bpy.context.object;body.name='Authoring test body';body.scale=(.18,.13,.4)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        scene.dd_avatar=body
        for obj in scene.objects:
            if obj.name in {'Cube','Camera','Light'}:obj.hide_set(True)
        scene.dd_ui_rect=(600,80,950,760)
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');area.spaces.active.show_region_ui=False
        region=next(r for r in area.regions if r.type=='WINDOW')
        area.spaces.active.region_3d.view_rotation=Vector((0,-1,0)).to_track_quat('Z','Y')
        area.spaces.active.region_3d.view_location=Vector((.65,0,1.2));area.spaces.active.region_3d.view_distance=2.8
        bpy.context.view_layer.update()
        with bpy.context.temp_override(area=area,region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT');op=editor._active
            op.free_window=None
            scene.dd_reference_visible = True
            op.reveal_3d()
            op.canvas_layout = op.make_layout()
            def event(kind,value='PRESS',point=None,**extra):
                c=op.canvas_layout.canvas;x,y=point or (c.x+c.w/2,c.y+c.h/2)
                data=dict(type=kind,value=value,mouse_x=x+region.x,mouse_y=y+region.y,shift=False,ctrl=False,alt=False)
                data.update(extra);return SimpleNamespace(**data)
            def click_at(point,**extra):
                op.handle_event(bpy.context,event('LEFTMOUSE',point=point,**extra))
                op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=point,**extra))
            def click_rect(r):click_at((r.x+r.w/2,r.y+r.h/2))
            def action(key):op.perform_action(key)
            def world(point,**extra):click_at(op.view.screen(point,op.canvas_layout.canvas),**extra)
            op.session.add([(0,0),(.3,0),(.3,.4),(0,.4)]);op.persist()
            rectangle=op.session.selected
            op.fit();op.choose_tool('SELECT')
            world((0,0),shift=True);world((.3,0),shift=True)
            action('MERGE');check(len(op.session.document.find(rectangle).vertices)==3,'Shift point selection and Merge work')
            op.handle_event(bpy.context,event('Z',ctrl=True));check(len(op.session.document.find(rectangle).vertices)==4,'merge has transactional undo')
            op.choose_tool('SELECT');world((.3,.4));op.handle_event(bpy.context,event('C'))
            p=op.session.document.find(rectangle);check(p.vertices[2].outgoing is not None,'corner converts to editable Bezier point')
            v=p.vertices[2];handle=(v.x+v.outgoing[0],v.y+v.outgoing[1]);start=op.view.screen(handle,op.canvas_layout.canvas)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=start));op.handle_event(bpy.context,event('MOUSEMOVE',point=(start[0]+10,start[1]+5)))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=(start[0]+10,start[1]+5)))
            check(op.handle_preview is None and not op.gesture,'Bezier handle drag commits without stale previews')
            edge=op.session.document.edge(rectangle,2);mid=op.session.document.edge_point(edge,.5)
            op.choose_tool('SELECT');world(mid)
            scene.dd_segment_length=op.session.document.edge_length(op.session.segment)*1.02
            action('SET_LENGTH');check(abs(op.session.document.edge_length(op.session.segment)-scene.dd_segment_length)<.0001,'custom exact segment length action works')
            before=len(op.session.document.find(rectangle).vertices);op.handle_event(bpy.context,event('Q'))
            check(len(op.session.document.find(rectangle).vertices)==before+1,'Q splits a curved segment')
            op.choose_tool('ELLIPSE');a=op.view.screen((.5,.05),op.canvas_layout.canvas);b=op.view.screen((.8,.35),op.canvas_layout.canvas)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=a));op.handle_event(bpy.context,event('MOUSEMOVE',point=b));op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=b))
            ellipse=op.session.selected;check(len(op.session.document.find(ellipse).vertices)==4,'ellipse tool creates four Bezier anchors')
            op.session.selected=rectangle;op.session.path='OUTER'
            op.session.add_ellipse((.1,.14),(.17,.22),True);op.persist();hole=op.session.path;action('CUT')
            check(op.session.document.find(rectangle).path(hole).role=='HOLE','internal ellipse cuts a real hole')
            action('TRACE');check(len(op.session.document.patterns)==3,'trace creates an independent pattern')
            op.session.selected=rectangle;op.session.path='OUTER';op.choose_tool('INTERNAL')
            world((.04,.05));world((.08,.1));op.handle_event(bpy.context,event('RET'));action('CUT')
            check(op.session.document.find(rectangle).path(op.session.path).role=='SLIT','internal polyline can become a slit')
            op.session.selected=ellipse;op.session.path='OUTER';op.fit();op.choose_tool('DART')
            edge=op.session.document.edge(ellipse,0)
            world(op.session.document.edge_point(edge,.25));world(op.session.document.edge_point(edge,.65));world((.65,.2))
            check(any(f.get('type')=='DART' for f in op.session.document.find(ellipse).features),'three-click dart adds automatic same-piece sewing')
            op.session.selected=rectangle;op.session.path='OUTER';op.session.segment=op.session.document.edge(rectangle,0)
            action('MIRROR_SEW');check(len(op.session.document.patterns)==4,'mirror with seam produces a paired reflected pattern')
            op.session.selected=rectangle;op.session.segment=op.session.document.edge(rectangle,0);action('UNFOLD')
            check(len(op.session.document.patterns)==4,'seamless Unfold replaces the source outline')
            op.session.add([(1.3,0),(1.6,0),(1.6,.4),(1.3,.4)]);square_a=op.session.selected
            op.session.add([(1.9,0),(2.3,0),(2.3,.3),(1.9,.3)]);square_b=op.session.selected
            op.persist();op.fit()
            old=len(op.session.document.seams);op.choose_tool('FREE_SEW')
            for owner,i,t in [(square_a,2,.2),(square_a,2,.8),(square_b,2,.1),(square_b,2,.9)]:
                world(op.session.document.edge_point(op.session.document.edge(owner,i),t))
            check(len(op.session.document.seams)==old+1,'four-click free sewing stores partial ranges')
            op.choose_tool('PIN');world((1.45,.2));check(len(op.session.document.anchors)==1,'pin tool creates a fabric anchor')
            op.choose_tool('TACK');world((1.56,.32));check(op.pending_tack is not None,'tack tool waits for an avatar target')
            area.spaces.active.region_3d.update()
            target=view3d_utils.location_3d_to_region_2d(region,area.spaces.active.region_3d,Vector((0,-.13,1.2)))
            if target is not None and op.canvas_layout.panel.contains(*target):
                area.spaces.active.region_3d.view_location.x+=.7
                area.spaces.active.region_3d.update()
                target=view3d_utils.location_3d_to_region_2d(region,area.spaces.active.region_3d,Vector((0,-.13,1.2)))
            check(target is not None and not op.canvas_layout.panel.contains(*target),'avatar target is visible outside floating editor')
            click_at(tuple(target));check(len(op.session.document.anchors)==2 and op.pending_tack is None,'tack ray-picks the chosen avatar')
            op.session.selected=square_a
            op.session.document.find(square_a).placement_mode='LEGACY';op.persist()
            action('PLACE');click_at(tuple(target))
            panels=garment.generated(scene,'panel');check(any(o.get('dd_pattern_id')==square_a for o in panels),'click placement generates and places selected panel')
            scene.dd_library_name='UI outfit';action('LIBRARY_SAVE')
            if op.confirm_action == 'LIBRARY_SAVE':
                click_rect(op.make_layout().buttons['CANCEL_ACTION'][0])
                check(op.confirm_action is None,'library overwrite can be cancelled')
                action('LIBRARY_SAVE')
                click_rect(op.make_layout().buttons['CONFIRM_ACTION'][0])
            check(bool(op.library_items),'custom library saves the editable design')
            original=op.session.document.find(square_a).points[0]
            body.scale*=1.2;bpy.context.view_layer.update();action('LIBRARY_LOAD')
            check(op.confirm_action == 'LIBRARY_LOAD', 'loading over a garment requires explicit confirmation')
            selected_piece = op.session.selected
            op.handle_event(bpy.context,event('X'))
            check(op.session.selected == selected_piece and op.session.document.find(selected_piece) is not None,
                  'confirmation blocks unrelated destructive shortcuts')
            click_rect(op.make_layout().buttons['CANCEL_ACTION'][0])
            check(op.session.document.find(square_a).points[0] == original,'cancelled library load preserves the garment')
            action('LIBRARY_LOAD')
            click_rect(op.make_layout().buttons['CONFIRM_ACTION'][0])
            check(abs(op.session.document.find(square_a).points[0][0]-original[0]*1.2)<1e-4,'custom library loads and scales design for another body size')
            op.session.selected=rectangle;op.session.path='OUTER'
            op.fit();op.save_window()
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'scratch'/'devil-designer-0.5-preview.blend'))
        check(editor._active is not None and not op._closed,
              'all advanced curves and holes draw without GPU callback failure')
        run_selection_native(op, passed)
    except Exception:
        (ROOT/'scratch'/'design-gui-report.json').write_text(json.dumps({'passed':passed,'error':traceback.format_exc()},indent=2))
        traceback.print_exc()
    return None

(ROOT/'scratch').mkdir(exist_ok=True)
bpy.app.timers.register(run,first_interval=2)
