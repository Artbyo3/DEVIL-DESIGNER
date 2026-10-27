import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
from unittest.mock import patch
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False


def check_interaction_regressions(workspace, event, point, check):
    from devil_designer import library
    from devil_designer.canvas import Layout, Rect
    from devil_designer.core import Document, Session
    from devil_designer.minimal import minimal_layout

    original_session = workspace.session
    original_tool = workspace.tool
    original_library_items = workspace.library_items
    original_free_sewing = workspace._scene.dd_free_sewing
    original_view = (workspace.view.cx, workspace.view.cy, workspace.view.zoom)
    original_workspace_open = workspace.workspace_panel_open
    original_workspace_pinned = workspace.workspace_panel_pinned
    original_context_card_hidden = workspace.context_card_hidden
    reference_names = ('gesture', 'preview', 'pending_edge', 'handle_preview', 'seam_selected',
                       'selected_anchor', 'chain_a', 'chain_b', 'chain_stage', 'free_clicks',
                       'dart_base', 'pending_place', 'pending_tack', 'pending_simulation')

    def seed_references(edge):
        workspace.pending_edge = edge
        workspace.seam_selected = 'pending-seam'
        workspace.selected_anchor = 'pending-anchor'
        workspace.chain_a = [edge]
        workspace.chain_b = [edge]
        workspace.chain_stage = 'A'
        workspace.free_clicks = [(edge, .25)]
        workspace.dart_base = [(edge, .5)]
        workspace.pending_place = edge.pattern
        workspace.pending_tack = (edge.pattern, (.1, .1))
        workspace.pending_simulation = True

    try:
        workspace.session = Session(Document())
        workspace.persist()
        workspace.card_kind = None
        workspace.context_card_hidden = False
        starter = workspace.minimal_card()
        check(starter[1] == 'Start garment' and len(starter[2]) == 4 and starter[2][0][1][0] == 'START_PANEL',
              'the empty garment offers a compact one-click starter alongside custom drawing and the library')
        workspace.minimal_action('START_PANEL')
        created = workspace.session.document.patterns[0]
        check(created.name == 'Front panel' and abs(created.points[1][0] - created.points[0][0] - .4) < 1e-6 and
              abs(created.points[2][1] - created.points[1][1] - .45) < 1e-6 and workspace.tool == 'SELECT',
              'one-click starter creates and frames an editable 40 by 45 cm panel ready for selection')
        check(workspace.perform_action('START_PANEL') is False and len(workspace.session.document.patterns) == 1,
              'starter creation cannot silently add another template to an existing garment')
        workspace.perform_action('UNDO')
        check(not workspace.session.document.patterns, 'one Undo removes the complete starter panel')
        workspace.perform_action('REDO')
        check(len(workspace.session.document.patterns) == 1, 'Redo restores the editable starter panel')
        workspace.session = Session(Document())
        workspace.session.add([(0, 0), (.3, 0), (.3, .4), (0, .4)])
        workspace.persist()
        edge = workspace.session.document.edges(workspace.session.selected)[0]
        for action in ('UNDO', 'REDO'):
            seed_references(edge)
            workspace.perform_action(action)
            check(all(not getattr(workspace, name) for name in reference_names),
                  action + ' clears pending sewing dart placement and anchor references before replacing the document')
            check(len(workspace.session.document.patterns) == (action == 'REDO'),
                  action + ' still performs the actual document history change')

        seed_references(edge)
        workspace.draft = [(0, 0), (.1, .1)]
        history = (list(workspace.session.undo_stack), list(workspace.session.redo_stack))
        workspace.perform_action('UNDO')
        workspace.perform_action('REDO')
        check(workspace.draft == [(0, 0)] and workspace.pending_edge == edge and
              history == (workspace.session.undo_stack, workspace.session.redo_stack),
              'draft undo stays local and draft redo never replaces document history or clears pending references')
        workspace.draft = []
        workspace.session.undo_stack.clear()
        workspace.perform_action('UNDO')
        check(workspace.pending_edge == edge and workspace.chain_stage == 'A',
              'an unavailable document undo does not discard pending interaction work')
        workspace.clear_interaction_references()

        workspace.choose_tool('SELECT')
        workspace.session.selected = workspace.session.document.patterns[0].id
        workspace.session.corner = 0
        workspace.session.path = 'OUTER'
        workspace.sync_selection()
        before_numeric = workspace.session.document.dumps()
        history_size = len(workspace.session.undo_stack)
        original_x = workspace._scene.dd_point_x
        workspace.numeric = dict(key='dd_point_x', text='60', cursor=2, selected=False)
        check(workspace.commit_numeric() is False and workspace.numeric is not None and
              workspace.session.document.dumps() == before_numeric and
              abs(workspace._scene.dd_point_x - original_x) < 1e-6 and
              len(workspace.session.undo_stack) == history_size and 'updated' not in workspace.message,
              'invalid numeric geometry retains the editable input and error without changing source or undo history')
        workspace.numeric.update(text='5', cursor=1)
        check(workspace.commit_numeric() and workspace.numeric is None and
              abs(workspace.session.document.patterns[0].vertices[0].x - .05) < 1e-6 and
              len(workspace.session.undo_stack) == history_size + 1,
              'correcting a rejected numeric point applies exactly one undoable edit')
        workspace.perform_action('UNDO')
        workspace.session.selected = workspace.session.document.patterns[0].id
        workspace.session.corner = 0
        workspace.sync_selection()
        workspace.setting_drag = dict(key='dd_point_x', value=original_x, pointer=point, moved=True)
        workspace._scene.dd_point_x = .6
        workspace.pointer = point
        workspace.controls_event(bpy.context, event('LEFTMOUSE', point, 'RELEASE'))
        check(workspace.setting_drag is None and workspace.session.document.dumps() == before_numeric and
              abs(workspace._scene.dd_point_x - original_x) < 1e-6 and 'updated' not in workspace.message,
              'a rejected numeric drag restores the displayed source value and preserves its validation error')

        edge = workspace.session.document.edges(workspace.session.selected)[0]
        seed_references(edge)
        workspace.pending_place = workspace.pending_tack = None
        workspace.handle_event(bpy.context, event('ESC', point))
        check(not workspace.chain_a and not workspace.chain_b and not workspace.chain_stage and
              not workspace.free_clicks and not workspace.dart_base and workspace.pending_edge is None,
              'Escape cancels all pending chain range dart and paired-edge picks together')
        workspace.gesture = dict(mode='HANDLE')
        workspace.handle_preview = (0, 'outgoing', (.1, .1))
        workspace.handle_event(bpy.context, event('ESC', point))
        check(workspace.gesture is None and workspace.handle_preview is None,
              'Escape removes the Bezier handle preview as well as its gesture')

        seed_references(edge)
        workspace.numeric = dict(key='dd_point_x', text='10', cursor=2, selected=True)
        workspace.card_kind = 'POINT'
        workspace.confirm_action = 'LIBRARY_LOAD'
        replacement_source = Session(Document())
        replacement_source.add([(1, 0), (1.3, 0), (1.3, .4), (1, .4)])
        workspace._scene.dd_document = replacement_source.document.dumps()
        workspace.handle_event(bpy.context, event('TIMER', point))
        check(all(not getattr(workspace, name) for name in reference_names) and workspace.numeric is None and
              workspace.confirm_action is None and workspace.card_kind is None,
              'external document replacement clears stale picks numeric edits cards and destructive confirmations')
        workspace.session = Session(Document.loads(before_numeric))
        workspace.session.selected = workspace.session.document.patterns[0].id
        edge = workspace.session.document.edges(workspace.session.selected)[0]
        workspace.persist()

        workspace.session.add([(.5, 0), (.8, 0), (.8, .4), (.5, .4)])
        other_edge = workspace.session.document.edges(workspace.session.selected)[0]
        workspace.session.sew(edge, other_edge)
        seam = workspace.session.document.seams[0]
        workspace.persist()
        workspace.choose_tool('SELECT')
        badge = workspace.seam_badges()[0][0]
        workspace.selected_anchor = 'old-anchor'
        workspace.card_kind = None
        workspace.handle_event(bpy.context, event('LEFTMOUSE', (badge.x + badge.w / 2, badge.y + badge.h / 2)))
        check(workspace.seam_selected == seam.id and workspace.selected_anchor is None and workspace.card_kind == 'SEAM',
              'a seam badge selects the seam instead of retaining a competing anchor selection')
        direction = seam.reverse
        workspace.handle_event(bpy.context, event('B', point))
        check(seam.reverse != direction, 'B reverses the selected seam badge even while the Select tool is active')
        workspace.handle_event(bpy.context, event('DEL', point))
        check(not workspace.session.document.seams and len(workspace.session.document.patterns) == 2,
              'Delete on a seam badge removes its seam rather than destroying the selected garment piece')
        workspace.perform_action('UNDO')
        check(len(workspace.session.document.seams) == 1 and len(workspace.session.document.patterns) == 2,
              'seam badge keyboard removal is undoable independently of the pieces')
        workspace.card_kind = None
        workspace.choose_tool('SEW')
        workspace.pending_edge = edge
        rev_before = workspace._scene.dd_sew_reverse
        workspace.handle_event(bpy.context, event('B', point))
        check(workspace._scene.dd_sew_reverse != rev_before,
              'B toggles sewing direction reverse while pending edge is active before commit')
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', point))
        check(workspace.pending_edge is None,
              'right click cancels pending edge selection before commit')
        workspace.pending_edge = edge
        with patch.object(workspace, 'design_hit_edge', return_value=edge):
            workspace.design_sew_click()
        check(workspace.pending_edge is None,
              'clicking the selected edge again clears pending edge selection')
        workspace.session = Session(Document.loads(before_numeric))
        workspace.session.selected = workspace.session.document.patterns[0].id
        edge = workspace.session.document.edges(workspace.session.selected)[0]
        workspace.clear_interaction_references()
        workspace.card_kind = None
        workspace.persist()

        original_settings = {key: getattr(workspace._scene, key) for key in
                             ('dd_self_collision', 'dd_library_refit', 'dd_clearance', 'dd_spacing', 'dd_quality')}
        try:
            workspace._scene.dd_self_collision = False
            workspace._scene.dd_library_refit = False
            workspace._scene.dd_quality = 15
            before_load = {key: getattr(workspace._scene, key) for key in original_settings}
            workspace.library_items = [Path('regression.garment.json')]
            with patch.object(library, 'load') as load:
                workspace.minimal_action('LOAD_0')
                check(workspace.confirm_action == 'LIBRARY_LOAD' and not load.called and
                      all(getattr(workspace._scene, key) == value for key, value in before_load.items()),
                      'requesting a library load never changes settings before confirmation')
                workspace.perform_action('CANCEL_ACTION')
                check(not load.called and all(getattr(workspace._scene, key) == value for key, value in before_load.items()),
                      'Go back from a library replacement truly leaves the current garment settings unchanged')
        finally:
            for key, value in original_settings.items():
                setattr(workspace._scene, key, value)

        for kind, deletion, tool in (('PIN', 'X', 'PIN'), ('TACK', 'DEL', 'TACK'),
                                     ('PIN', 'DELETE', 'SEW')):
            workspace.choose_tool(tool)
            workspace.session.selected = workspace.session.document.patterns[0].id
            anchor = workspace.session.add_anchor((.1, .1), kind)
            workspace.session.corner = 0
            workspace.session.segment = edge
            workspace.session.point_selection = [0, 1]
            workspace.pointer = workspace.view.screen((anchor.x, anchor.y), workspace.canvas_layout.canvas)
            workspace.tool = kind
            workspace.design_canvas_click(event('LEFTMOUSE', workspace.pointer))
            check(workspace.selected_anchor == anchor.id and workspace.session.selected == anchor.pattern and
                  workspace.session.corner is None and workspace.session.path == 'OUTER' and
                  workspace.session.segment is None and not workspace.session.point_selection,
                  kind + ' picking clears competing point path and segment selection')
            workspace.tool = tool
            workspace.seam_selected = 'pending-seam'
            workspace.persist()
            if deletion == 'DELETE':
                workspace.perform_action('DELETE')
            else:
                workspace.handle_event(bpy.context, event(deletion, point))
            check(not workspace.session.document.anchors and len(workspace.session.document.patterns) == 1,
                  deletion + ' removes the selected ' + kind + ' rather than its piece or a seam')

        workspace.clear_interaction_references()
        workspace.session.selected = workspace.session.document.patterns[0].id
        anchor = workspace.session.add_anchor((.1, .1))
        workspace.select_anchor(anchor)
        workspace.tool = 'PIN'
        workspace.choose_tool('PIN')
        check(workspace.selected_anchor == anchor.id,
              'reselecting the current anchor tool preserves its explicit anchor selection')
        workspace.choose_tool('SELECT')
        check(workspace.selected_anchor is None,
              'changing from an anchor tool to another tool clears stale anchor selection')
        workspace.session.add([(.5, 0), (.7, 0), (.7, .4), (.5, .4)])
        other_piece = workspace.session.selected
        workspace.select_anchor(anchor)
        workspace.context_card_hidden = True
        workspace.card_kind = None
        workspace.persist()
        workspace.fit()
        piece_point = workspace.view.screen((.6, .2), workspace.canvas_layout.canvas)
        workspace.handle_event(bpy.context, event('LEFTMOUSE', piece_point))
        workspace.handle_event(bpy.context, event('LEFTMOUSE', piece_point, 'RELEASE'))
        check(workspace.session.selected == other_piece and workspace.selected_anchor is None,
              'ordinary Select piece picking clears an anchor selected on another piece')
        workspace.perform_action('DELETE')
        check(len(workspace.session.document.patterns) == 1 and
              any(existing.id == anchor.id for existing in workspace.session.document.anchors),
              'Delete after selecting another piece deletes that piece rather than the previous anchor')
        workspace.session.selected = workspace.session.document.patterns[0].id
        workspace.select_anchor(anchor)
        workspace.perform_action('DELETE')
        workspace.clear_interaction_references()
        workspace.choose_tool('SELECT')
        source = workspace.session.document.find(workspace.session.selected)
        source_points = list(source.points)
        duplicate_event = event('D', point)
        duplicate_event.shift = True
        with patch.object(workspace, 'perform_action', wraps=workspace.perform_action) as dispatch:
            workspace.handle_event(bpy.context, duplicate_event)
            check(dispatch.call_args.args == ('DUPLICATE',),
                  'Shift D reaches the shared Duplicate action before unmodified Dart routing')
        duplicate = workspace.session.document.find(workspace.session.selected)
        check(workspace.tool == 'SELECT' and len(workspace.session.document.patterns) == 2 and
              duplicate.id != source.id and source.points == source_points,
              'Shift D duplicates and selects a copy without switching tools or changing the source')
        workspace.perform_action('UNDO')
        check(len(workspace.session.document.patterns) == 1,
              'keyboard Duplicate is one undoable operation')
        workspace.handle_event(bpy.context, event('D', point))
        check(workspace.tool == 'DART', 'unmodified D still selects Dart')

        replacement = Session(Document())
        replacement.add([(-.3, 0), (-.1, 0), (-.1, .4), (-.3, .4)])

        def load_replacement(context, index):
            context.scene.dd_document = replacement.document.dumps()
            return replacement.document

        edge = workspace.session.document.edges(workspace.session.document.patterns[0].id)[0]
        seed_references(edge)
        with patch.object(library, 'entries', return_value=[Path('regression.garment.json')]), \
                patch.object(library, 'load', side_effect=ValueError('Invalid garment')):
            workspace.design_action('LIBRARY_LOAD')
        check(workspace.pending_edge == edge and workspace.chain_stage == 'A',
              'a failed library load preserves the current pending interaction')
        workspace.session.point_selection = [0, 1]
        with patch.object(library, 'entries', return_value=[Path('regression.garment.json')]), \
                patch.object(library, 'load', side_effect=load_replacement), \
                patch.object(workspace, 'update_reference'), patch.object(workspace, 'fit'):
            workspace.design_action('LIBRARY_LOAD')
        check(workspace.session.document is replacement.document and
              all(not getattr(workspace, name) for name in reference_names) and
              not workspace.session.point_selection,
              'successful library replacement clears all old document interaction and point references')
        workspace.perform_action('UNDO')
        check(workspace.session.document.find(edge.pattern) is not None,
              'library replacement retains undo back to the previous garment')

        workspace.choose_tool('SELECT')
        workspace.workspace_panel_open = workspace.workspace_panel_pinned = True
        workspace.card_kind = None
        card = workspace.workspace_card()[0]
        workspace_point = (card.x + 12, card.y + card.h - 12)
        save_event = event('S', workspace_point)
        save_event.ctrl = True
        check(workspace.handle_event(bpy.context, save_event) == {'PASS_THROUGH'},
              'Ctrl S over Workspace passes through to native Blender save')
        before = workspace.session.document.dumps()
        workspace.session.add([(.5, 0), (.7, 0), (.7, .4), (.5, .4)])
        workspace.persist()
        undo_event = event('Z', workspace_point)
        undo_event.ctrl = True
        workspace.handle_event(bpy.context, undo_event)
        check(workspace.session.document.dumps() == before,
              'Ctrl Z over Workspace reaches document undo instead of being swallowed by the card')

        workspace.session = Session(Document())
        workspace.session.add([(-.4, 0), (.4, 0), (.4, .6), (-.4, .6)])
        open_path = workspace.session.add_path([(-.2, .15), (.2, .15)])
        closed_path = workspace.session.add_path([(-.2, .3), (.2, .3), (.2, .45), (-.2, .45)], True)
        owner = workspace.session.selected
        workspace.persist()
        workspace.workspace_panel_open = False
        workspace.fit()
        for internal_path in (open_path, closed_path):
            workspace.card_kind = None
            workspace.context_card_hidden = True
            edge = workspace.session.document.edges(owner, internal_path.id)[0]
            edge_point = workspace.view.screen(workspace.session.document.edge_point(edge, .5), workspace.canvas_layout.canvas)
            workspace.handle_event(bpy.context, event('RIGHTMOUSE', edge_point))
            check(workspace.card_kind == 'INTERNAL_EDGE' and workspace.session.path == internal_path.id,
                  'right click preserves the selected ' + ('closed' if internal_path.closed else 'open') + ' internal edge path')
            controls = {row[0] for rect, row in workspace.minimal_card()[2]}
            check({'SPLIT', 'CUT'} <= controls and ('TRACE' in controls) == internal_path.closed,
                  'internal edge context exposes cut and split with Trace only for a closed shape')
        workspace.perform_action('TRACE')
        check(len(workspace.session.document.patterns) == 2,
              'closed internal edge context retains the path needed to trace an actual piece')

        workspace.show_card('EDIT', point)
        close = workspace.card_close_rect(workspace.minimal_card()[0])
        document_before_close = workspace.session.document.dumps()
        workspace.handle_event(bpy.context, event('LEFTMOUSE', (close.x + close.w / 2, close.y + close.h / 2)))
        check(workspace.card_kind is None and workspace.context_card_hidden and
              workspace.session.document.dumps() == document_before_close,
              'context card close hides the automatic replacement without editing garment data')
        workspace.show_card('EDIT', point)
        dock = workspace.canvas_layout.buttons['RECTANGLE'][0]
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', (dock.x + dock.w / 2, dock.y + dock.h / 2)))
        check(workspace.card_kind is None and workspace.tool == 'SELECT',
              'right click dismisses an explicit popover before dispatching an underlying dock action')
        workspace.context_card_hidden = True
        reopen_point = (workspace.canvas_layout.canvas.x + 100, workspace.canvas_layout.canvas.y + 80)
        workspace.handle_event(bpy.context, event('LEFTMOUSE', reopen_point))
        workspace.handle_event(bpy.context, event('LEFTMOUSE', reopen_point, 'RELEASE'))
        check(not workspace.context_card_hidden,
              'the next canvas click restores automatic contextual card reachability')

        workspace.clear_interaction_references()
        workspace.choose_tool('SELECT')
        workspace.workspace_panel_open = False
        workspace.session = Session(Document())
        workspace.session.add([(0, 0), (.3, 0), (.3, .4), (0, .4)])
        first_piece = workspace.session.selected
        workspace.session.add([(.5, 0), (.8, 0), (.8, .4), (.5, .4)])
        second_piece = workspace.session.selected
        workspace.persist()
        workspace.fit()
        workspace.session.selected = first_piece
        workspace.session.path = 'OUTER'
        workspace.session.point_selection = [0, 1]
        workspace.card_kind = None
        target = workspace.view.screen((.8, .4), workspace.canvas_layout.canvas)
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', target))
        check(workspace.session.selected == second_piece and workspace.session.point_selection == [2],
              'right clicking a different piece never transfers another piece point-selection indices')
        before_merge = workspace.session.document.dumps()
        before_history = list(workspace.session.undo_stack)
        check(workspace.perform_action('MERGE') is False and workspace.session.document.dumps() == before_merge and
              workspace.session.undo_stack == before_history,
              'a cross-piece right click cannot accidentally merge stale selected corners')
        workspace.card_kind = None
        workspace.session.point_selection = [0, 1]
        target = workspace.view.screen((.8, 0), workspace.canvas_layout.canvas)
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', target))
        check(workspace.session.point_selection == [0, 1],
              'right clicking within the same selected point group preserves an intentional merge selection')
        workspace.session.sew(workspace.session.document.edges(first_piece)[0],
                              workspace.session.document.edges(second_piece)[2])
        selected_seam = workspace.session.document.seams[0]
        workspace.seam_selected = selected_seam.id
        workspace.card_kind = None
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', target))
        check(workspace.seam_selected is None and workspace.session.corner == 1,
              'right clicking a point clears the old seam target before keyboard deletion or reversal')
        before_reverse = workspace.session.document.dumps()
        workspace.handle_event(bpy.context, event('B', point))
        check(workspace.session.document.dumps() == before_reverse,
              'B on a newly selected point cannot reverse an old hidden seam')
        workspace.session.point_selection = []
        workspace.perform_action('DELETE')
        check(len(workspace.session.document.seams) == 1 and
              len(workspace.session.document.find(second_piece).vertices) == 3,
              'Delete on the new point removes that corner rather than an unrelated hidden seam')
        workspace.perform_action('UNDO')
        workspace.session.selected = second_piece
        internal = workspace.session.add_path([(.55, .1), (.7, .1), (.7, .2)], True)
        workspace.session.path = 'OUTER'
        workspace.session.point_selection = [0, 1]
        workspace.persist()
        workspace.card_kind = None
        target = workspace.view.screen((.55, .1), workspace.canvas_layout.canvas)
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', target))
        check(workspace.session.path == internal.id and workspace.session.point_selection == [0],
              'right clicking an internal path scopes its point selection separately from the outer boundary')
        for path, corner in (('OUTER', 1), (internal.id, None)):
            workspace.session.selected = second_piece
            workspace.session.path = path
            workspace.session.corner = corner
            workspace.session.point_selection = [0, 1]
            workspace.show_card('EDIT', point)
            check(any(row[0] == 'DELETE_PIECE' and row[1] == 'Delete piece' for rect, row in workspace.minimal_card()[2]),
                  'the piece card exposes an explicit whole-piece deletion action')
            before_delete = workspace.session.document.dumps()
            workspace.minimal_action('DELETE_PIECE')
            check(workspace.session.document.find(second_piece) is None and len(workspace.session.document.patterns) == 1,
                  'Delete piece removes the whole piece even with a corner or internal path selected')
            workspace.perform_action('UNDO')
            check(workspace.session.document.dumps() == before_delete,
                  'one Undo restores the entire deleted piece and its internal paths')
        for mode in ('MOVE', 'HANDLE'):
            workspace.session.selected = first_piece
            workspace.session.path = 'OUTER'
            workspace.session.corner = 0 if mode == 'HANDLE' else None
            pattern = workspace.session.document.find(first_piece)
            workspace.gesture = dict(mode=mode, start=(0, 0), points=pattern.points, anchor=(0, 0))
            workspace.preview = [(x + .03, y) for x, y in pattern.points] if mode == 'MOVE' else None
            workspace.handle_preview = (0, 'outgoing', (.03, .01)) if mode == 'HANDLE' else None
            before_drag = workspace.session.document.dumps()
            history_size = len(workspace.session.undo_stack)
            duplicate_event = event('D', point)
            duplicate_event.shift = True
            workspace.handle_event(bpy.context, duplicate_event)
            check(workspace.session.document.dumps() == before_drag and workspace.session.selected == first_piece and
                  workspace.gesture['mode'] == mode,
                  'Shift D during ' + mode + ' cannot redirect the pending drag onto a duplicate')
            workspace.handle_event(bpy.context, event('LEFTMOUSE', point, 'RELEASE'))
            check(workspace.gesture is None and workspace.session.document.dumps() != before_drag and
                  len(workspace.session.undo_stack) == history_size + 1,
                  mode + ' still completes as one undoable edit after a blocked shortcut')
            workspace.perform_action('UNDO')
            check(workspace.session.document.dumps() == before_drag,
                  'one Undo restores the original source after the completed ' + mode)

        fit_session = Session(Document())
        fit_session.add([(-1.5, 0), (1.5, 0), (1.5, .4), (-1.5, .4)])
        workspace.workspace_panel_open = workspace.workspace_panel_pinned = True
        for scale in (1, 1.5):
            layout = Layout(1600 * scale, 1000 * scale, scale, full=True)
            minimal_layout(layout)
            canvas = layout.canvas
            with patch.object(workspace, 'session', fit_session), \
                    patch.object(workspace, 'canvas_layout', layout), \
                    patch.object(workspace, 'reference_corners', return_value=[]):
                workspace.fit()
                projected = [workspace.view.screen(vertex, canvas) for vertex in fit_session.document.patterns[0].points]
                card = workspace.workspace_card()[0]
                check(min(vertex[0] for vertex in projected) > layout.rail.x + layout.rail.w and
                      max(vertex[0] for vertex in projected) < card.x and layout.canvas is canvas,
                      'minimal Fit clears the dock and pinned Workspace without resizing the canvas at scale ' + str(scale))
                center = workspace.view.screen((0, .2), canvas)
                usable_left = layout.rail.x + layout.rail.w + 16 * scale
                usable_right = card.x - 16 * scale
                check(abs(center[0] - (usable_left + usable_right) / 2) < 1e-6,
                      'minimal Fit compensates world center for the temporary fit rectangle origin')
                workspace.workspace_panel_pinned = False
                workspace.fit()
                center = workspace.view.screen((0, .2), canvas)
                check(abs(center[0] - (usable_left + canvas.x + canvas.w) / 2) < 1e-6 and layout.canvas is canvas,
                      'unpinned Workspace does not reserve permanent design canvas space')
                workspace.workspace_panel_pinned = True
                crowded_card = (Rect(canvas.x + 300 * scale, canvas.y, 210 * scale, 200 * scale), '', [])
                with patch.object(workspace, 'workspace_card', return_value=crowded_card):
                    workspace.fit()
                center = workspace.view.screen((0, .2), canvas)
                check(abs(center[0] - (usable_left + canvas.x + canvas.w) / 2) < 1e-6,
                      'Fit skips Workspace reservation when fewer than 400 scaled pixels remain')
        split = Layout(853, 900, 1, full=True)
        minimal_layout(split)
        with patch.object(workspace, 'session', fit_session), \
                patch.object(workspace, 'canvas_layout', split), \
                patch.object(workspace, 'reference_corners', return_value=[]):
            workspace.fit()
            projected = [workspace.view.screen(vertex, split.canvas) for vertex in fit_session.document.patterns[0].points]
            check(max(vertex[0] for vertex in projected) < workspace.workspace_card()[0].x,
                  '853 pixel split preview reserves the 210 pixel Workspace when at least 400 usable pixels remain')
        compact = Layout(628, 700, 1, full=True)
        minimal_layout(compact)
        with patch.object(workspace, 'session', fit_session), \
                patch.object(workspace, 'canvas_layout', compact), \
                patch.object(workspace, 'reference_corners', return_value=[]):
            workspace.fit()
            center = workspace.view.screen((0, .2), compact.canvas)
            usable_left = compact.rail.x + compact.rail.w + 16
            usable_right = workspace.workspace_card()[0].x - 16
            check(abs(center[0] - (usable_left + usable_right) / 2) < 1e-6 and
                  abs(workspace.view.cy - .2) < 1e-6,
                  '628 pixel compact workspace keeps both dock and pinned Workspace clear when 260 usable pixels remain')
    finally:
        workspace.clear_interaction_references()
        workspace.session = original_session
        workspace.library_items = original_library_items
        workspace.card_kind = None
        workspace.persist()
        workspace.choose_tool(original_tool)
        workspace._scene.dd_free_sewing = original_free_sewing
        workspace.view.cx, workspace.view.cy, workspace.view.zoom = original_view
        workspace.workspace_panel_open = original_workspace_open
        workspace.workspace_panel_pinned = original_workspace_pinned
        workspace.context_card_hidden = original_context_card_hidden


def run():
    passed = []

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        passed.append(message)

    try:
        import devil_designer
        from devil_designer import editor, garment
        from devil_designer.minimal import FABRICS, DENSITY, QUALITY, THICKNESS
        devil_designer.register()
        scene = bpy.context.scene
        body = scene.objects['Cube']
        body.location = (0, 0, 1.2)
        body.scale = (.18, .13, .4)
        scene.dd_spacing = .04
        scene.dd_avatar = None
        bpy.context.view_layer.update()
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace = editor._active

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

            def card_control(key):
                return next(rect for rect, row in workspace.minimal_card()[2] if row[0] == key)

            def card_click(key):
                rect = card_control(key)
                click((rect.x + rect.w / 2, rect.y + rect.h / 2))

            check(workspace.minimal_ui and workspace.inspector is None and workspace.canvas_layout.inspector is None,
                  'default workspace has no sidebar, search inspector, or universal option popup')
            check(not {'SETTINGS', 'SEARCH', 'MORE_TOOLS', 'BUILD'} & set(workspace.canvas_layout.buttons),
                  'default chrome contains only the tool dock and task transport')
            check(workspace.tool == 'RECTANGLE', 'panel drawing is ready immediately')
            def workspace_click(key):
                card = workspace.workspace_card()
                controls = workspace.workspace_header_controls(card[0])
                controls += [(rect, row[0]) for rect, row in card[2]]
                rect = next(rect for rect, action in controls if action == key)
                click((rect.x + rect.w / 2, rect.y + rect.h / 2))

            panel = workspace.workspace_card()
            original_canvas = workspace.canvas_layout.canvas
            check(panel is not None and workspace.workspace_panel_pinned,
                  'compact Workspace side card starts visible and pinned')
            check(panel[0].w <= 210 * workspace.canvas_layout.scale and len(panel[2]) == 4,
                  'Workspace is a compact card with only relevant existing working preferences')
            bounds = workspace.canvas_layout.panel
            check(abs(panel[0].y + panel[0].h / 2 - (bounds.y + bounds.h / 2)) < 1e-6,
                  'Workspace side panel is vertically centered on the design workspace')
            snapping = workspace.snap
            workspace_click('WORKSPACE_SNAP')
            check(workspace.snap != snapping, 'Workspace snapping changes the actual drawing snap state')
            workspace_click('WORKSPACE_SNAP')
            lengths = scene.dd_lengths_visible
            workspace_click('WORKSPACE_LENGTHS')
            check(scene.dd_lengths_visible != lengths, 'Workspace measurements change actual canvas labels')
            workspace_click('WORKSPACE_LENGTHS')
            workspace_click('WORKSPACE_GUIDE')
            check(scene.dd_reference_visible and len(workspace.workspace_card()[2]) == 5,
                  'body guide reveals its opacity choice only while visible, within five controls')
            expanded_panel = workspace.workspace_card()[0]
            check(abs(expanded_panel.y + expanded_panel.h / 2 - (bounds.y + bounds.h / 2)) < 1e-6,
                  'Workspace stays vertically centered when contextual controls expand it')
            opacity = next(rect for rect, row in workspace.workspace_card()[2] if row[0] == 'CHOICES')
            click((opacity.x + opacity.w * 5 / 6, opacity.y + 16))
            check(abs(scene.dd_reference_opacity - .5) < 1e-6,
                  'named guide opacity changes the existing silhouette opacity')
            workspace_click('WORKSPACE_GUIDE')
            check(not scene.dd_reference_visible and len(workspace.workspace_card()[2]) == 4,
                  'hidden body guide removes its irrelevant opacity control')
            original_view = (workspace.view.cx, workspace.view.cy, workspace.view.zoom)
            workspace.view.cx, workspace.view.cy, workspace.view.zoom = 2, 3, 20
            workspace_click('WORKSPACE_FIT')
            check(workspace.view.cx == 0 and workspace.view.cy == 0 and workspace.view.zoom > 20,
                  'Workspace Fit design uses the actual existing canvas framing operation')
            workspace.view.cx, workspace.view.cy, workspace.view.zoom = original_view
            workspace.show_card('SIMULATE')
            workspace_click('WORKSPACE_SNAP')
            check(workspace.card_kind == 'SIMULATE', 'Workspace changes do not replace the current task card')
            workspace_click('WORKSPACE_SNAP')
            workspace.card_kind = None
            workspace_click('WORKSPACE_CLOSE')
            check(workspace.workspace_card() is None and workspace.make_layout().canvas == original_canvas,
                  'closing the side card leaves the existing canvas layout unchanged')
            button('WORKSPACE_PANEL')
            check(workspace.workspace_card() is not None, 'Workspace button reopens the side card')
            workspace.choose_tool('SELECT')
            canvas_point = (original_canvas.x + original_canvas.w / 2, original_canvas.y + 80)
            click(canvas_point)
            check(workspace.workspace_panel_open, 'pinned card stays open while working on the canvas')
            workspace.handle_event(bpy.context, event('ESC', canvas_point))
            check(not workspace._closed and workspace.workspace_card() is not None,
                  'Escape does not close the minimal workspace or lose its pinned side panel')
            workspace.choose_tool('POLYGON')
            click(canvas_point)
            check(workspace.draft and workspace.workspace_card() in workspace.visible_cards(),
                  'pinned Workspace side panel remains rendered during polygon drafting')
            workspace.handle_event(bpy.context, event('ESC', canvas_point))
            check(not workspace.draft and not workspace._closed and workspace.workspace_card() is not None,
                  'Escape cancels drafting without losing the workspace or side panel')
            workspace.choose_tool('RECTANGLE')
            workspace.handle_event(bpy.context, event('LEFTMOUSE', canvas_point))
            check(workspace.gesture and workspace.workspace_card() in workspace.visible_cards(),
                  'pinned side panel remains rendered during a rectangle gesture')
            workspace.handle_event(bpy.context, event('ESC', canvas_point))
            check(workspace.gesture is None and not workspace._closed,
                  'visible pinned panel does not swallow gesture cancellation')
            workspace.choose_tool('SELECT')
            workspace_click('WORKSPACE_PIN')
            click(canvas_point)
            check(not workspace.workspace_panel_open, 'unpinned card dismisses on canvas input without trapping the artist')
            button('WORKSPACE_PANEL')
            workspace_click('WORKSPACE_PIN')
            workspace_click('WORKSPACE_CLOSE')
            check_interaction_regressions(workspace, event, canvas_point, check)
            workspace.choose_tool('RECTANGLE')
            for start, end in [((-.4, 0), (-.1, .4)), ((.1, 0), (.4, .4))]:
                first = workspace.view.screen(start, workspace.canvas_layout.canvas)
                last = workspace.view.screen(end, workspace.canvas_layout.canvas)
                workspace.handle_event(bpy.context, event('LEFTMOUSE', first))
                workspace.handle_event(bpy.context, event('MOUSEMOVE', last))
                workspace.handle_event(bpy.context, event('LEFTMOUSE', last, 'RELEASE'))
            check(len(workspace.session.document.patterns) == 2, 'two mouse drags create two panels')
            check(workspace.minimal_card()[1] == workspace.session.document.patterns[-1].name,
                  'selection automatically replaces garment information with a piece card')
            card_click('FABRIC')
            check([row[0].removeprefix('SET_PRESET_') for rect, row in workspace.minimal_card()[2]] == list(FABRICS),
                  'Fabric opens exactly Cotton Linen Denim Silk Leather Knit, with no physical fields')
            card_click('SET_PRESET_LEATHER')
            check(workspace.session.document.find(workspace.session.selected).preset == 'LEATHER',
                  'fabric preset applies directly to the selected piece')
            workspace.card_kind = None
            button('SELECT')
            pattern = workspace.session.document.patterns[0]
            original_point = pattern.points[0]
            point = workspace.view.screen(original_point, workspace.canvas_layout.canvas)
            click(point, 'RIGHTMOUSE')
            check(workspace.card_kind == 'POINT', 'right clicking a point reveals only its local editing choices')
            control = next(rect for rect, row in workspace.minimal_card()[2] if row[0] == 'SLIDER' and row[1] == 'dd_point_x')
            handle = (control.x + control.w * .7, control.y + 12)
            workspace.handle_event(bpy.context, event('LEFTMOUSE', handle))
            dragged = (handle[0] + 24, handle[1])
            workspace.handle_event(bpy.context, event('MOUSEMOVE', dragged))
            workspace.handle_event(bpy.context, event('LEFTMOUSE', dragged, 'RELEASE'))
            check(pattern.points[0][0] > original_point[0], 'dragging an exact design value applies the local point edit')
            workspace.card_kind = None
            workspace.perform_action('UNDO')
            check(workspace.session.document.patterns[0].points[0] == original_point,
                  'a local numeric design edit is one undoable operation')
            button('SIMULATE_OPTIONS')
            card = workspace.minimal_card()
            check(len(card[2]) == 2 and all(row[0] == 'CHOICES' for rect, row in card[2]),
                  'Simulate popover contains only two named-choice controls')
            density_rect = card[2][0][0]
            click((density_rect.x + density_rect.w / 6, density_rect.y + 16))
            quality_rect = workspace.minimal_card()[2][1][0]
            click((quality_rect.x + quality_rect.w / 2, quality_rect.y + 16))
            check(abs(scene.dd_spacing - DENSITY['Coarse']) < 1e-6 and scene.dd_quality == QUALITY['Standard'],
                  'named density and quality choices map to their actual implementation values')
            button('KEEP_OPTIONS')
            check(len(workspace.minimal_card()[2]) == 2 and not any(row[0] == 'SLIDER' for rect, row in workspace.minimal_card()[2]),
                  'Keep uses Auto weld and named thickness, without a premature manual tolerance')
            thickness_rect = workspace.minimal_card()[2][1][0]
            click((thickness_rect.x + thickness_rect.w / 6, thickness_rect.y + 16))
            check(scene.dd_thickness == THICKNESS['None'], 'None thickness is a named finalize choice')
            for kind in ('PIECE', 'SIMULATE', 'KEEP', 'GARMENT', 'BODY', 'LIBRARY', 'POINT', 'EDGE', 'EDIT', 'PLACEMENT', 'INTERNAL_EDIT', 'OFFSET', 'SEWING', 'RESULT'):
                workspace.show_card(kind)
                card = workspace.minimal_card()
                check(card is None or sum(row[0] != 'INFO' for rect, row in card[2]) <= 5,
                      kind + ' card stays within the five-control cap')
                check(card is None or not any(row[1] in {'dd_spacing', 'dd_quality', 'dd_self_collision', 'dd_clearance', 'dd_library_refit', 'dd_frames'} for rect, row in card[2]),
                      kind + ' card exposes no raw simulation parameters or automatic-policy toggles')
            workspace.card_kind = None
            button('SEW')
            for point in ((-.25, 0), (.25, 0)):
                click(workspace.view.screen(point, workspace.canvas_layout.canvas))
            check(len(workspace.session.document.seams) == 1, 'Sew pairs the panels directly on canvas')
            badge = workspace.seam_badges()[0][0]
            click((badge.x + badge.w / 2, badge.y + badge.h / 2))
            check(workspace.card_kind == 'SEAM' and len(workspace.minimal_card()[2]) == 2,
                  'selecting the seam badge opens only reverse and remove at that seam')
            before = workspace.session.document.seams[0].reverse
            card_click('FLIP_SEAM')
            check(workspace.session.document.seams[0].reverse != before, 'seam direction changes through its micro-card')
            card_click('FLIP_SEAM')
            workspace.card_kind = None
            check(not garment.generated(scene, 'panel'), 'no separate Build or Arrange action was required')
            scene.dd_self_collision = False
            scene.dd_library_refit = False
            button('SIMULATE')
            check(bpy.context.screen.is_animation_playing and scene.dd_avatar == body,
                  'Simulate detects the body, builds, arranges, and starts actual cloth playback')
            check(scene.dd_self_collision and scene.dd_library_refit,
                  'self collision and library refit are automatic decisions, not controls')
            panels = garment.generated(scene, 'panel')
            check(len(panels) == 2 and panels[0].location.y * panels[1].location.y < 0,
                  'first-time front and back placement uses opposite sides of the body')
            button('SIMULATE')
            check(not bpy.context.screen.is_animation_playing, 'the same transport button pauses playback')
            placement = [panel.matrix_world.copy() for panel in panels]
            button('SIMULATE')
            check(all(panel.matrix_world == matrix for panel, matrix in zip(panels, placement)),
                  'resume preserves authored panel placement')
            button('SIMULATE')
            bpy.ops.mesh.primitive_cube_add(location=(3, 0, 1))
            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            bpy.context.view_layer.objects.active = None
            scene.dd_avatar = None
            button('SIMULATE')
            check(workspace.card_kind == 'BODY' and workspace.pending_simulation and not workspace.settings_open,
                  'ambiguous bodies use a small body card, never a settings panel')
            index = workspace.card_models.index(body) if body in workspace.card_models else None
            if index is None:
                workspace.minimal_card()
                index = workspace.card_models.index(body)
            card_click('BODY_' + str(index))
            check(scene.dd_avatar == body and bpy.context.screen.is_animation_playing,
                  'choosing the body continues simulation without a second transport click')
            button('SIMULATE')
            button('KEEP')
            check(bool(garment.generated(scene, 'final')), 'Keep creates a real final garment through the existing pipeline')
            button('KEEP_OPTIONS')
            scene['dd_unwelded_seams'] = 1
            check(any(row[0] == 'SLIDER' for rect, row in workspace.minimal_card()[2]),
                  'manual weld tolerance appears only after an unwelded-seam report')
            scene['dd_unwelded_seams'] = 0
            check(not any(row[0] == 'SLIDER' for rect, row in workspace.minimal_card()[2]),
                  'manual weld control disappears when no failed seam pairs remain')
        report = {'passed': passed}
    except Exception:
        report = {'passed': passed, 'error': traceback.format_exc()}
        traceback.print_exc()
    (ROOT / 'scratch').mkdir(exist_ok=True)
    (ROOT / 'scratch' / 'fast_flow-report.json').write_text(json.dumps(report, indent=2))
    return None


bpy.app.timers.register(run, first_interval=2)
