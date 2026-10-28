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
        check(workspace.minimal_card() is None,
              'the empty garment offers clean canvas with no overlay')
        workspace.perform_action('START_PANEL')
        created = workspace.session.document.patterns[0]
        check(created.name == 'Front panel' and abs(created.points[1][0] - created.points[0][0] - .4) < 1e-6 and
              abs(created.points[2][1] - created.points[1][1] - .45) < 1e-6,
              'START_PANEL creates an editable 40 by 45 cm panel')
        check(workspace.perform_action('START_PANEL') is False and len(workspace.session.document.patterns) == 1,
              'starter creation cannot silently add another template to an existing garment')
        workspace.perform_action('UNDO')
        check(not workspace.session.document.patterns, 'one Undo removes the complete starter panel')
        workspace.perform_action('REDO')
        check(len(workspace.session.document.patterns) == 1, 'Redo restores the editable starter panel')
        workspace.show_card('PIECE')
        controls={row[0] for rect,row in workspace.minimal_card()[2]}
        check({'CLONE_LINKED','TOGGLE_LINKED'}<=controls and 'CLONE_BACK' not in controls,
              'piece menu offers explicit linked clone and toggle without an unarranged Back action')
        workspace.minimal_action('CLONE_LINKED')
        check(len(workspace.session.document.patterns)==2 and len(workspace.session.document.linked_pairs)==1 and
              not workspace.session.document.seams and workspace.card_kind is None,
              'contextual linked clone creates two live panels without sewing and dismisses immediately')
        before_preview=workspace.session.document.dumps()
        original,twin=workspace.session.document.patterns
        workspace.session.corner=1;workspace.session.selected_patterns.clear()
        workspace.gesture=dict(mode='MOVE',delta=(.02,.01))
        first_preview=workspace.preview_pattern(original);twin_preview=workspace.preview_pattern(twin)
        check(abs(first_preview.vertices[1].x-original.vertices[1].x+.02)<1e-8 and
              abs(twin_preview.vertices[1].x-twin.vertices[1].x-.02)<1e-8 and
              workspace.session.document.dumps()==before_preview,
              'linked point drag previews both outlines without mutating the document')
        workspace.gesture=None
        workspace.handle_preview=(1,'outgoing',(.01,.02),None,None,twin.id,'OUTER')
        first_preview=workspace.preview_pattern(original);twin_preview=workspace.preview_pattern(twin)
        check(first_preview.vertices[1].outgoing==(-.01,.02) and twin_preview.vertices[1].outgoing==(.01,.02) and
              workspace.session.document.dumps()==before_preview,
              'linked handle preview mirrors both ways without changing undo or source geometry')
        workspace.handle_preview=None;workspace.session.corner=None;workspace.session.selected_patterns={twin.id}
        workspace.minimal_action('TOGGLE_LINKED')
        check(not workspace.session.document.linked_pairs[0]['enabled'],'contextual Linked twin Off unlinks the pair')
        workspace.minimal_action('TOGGLE_LINKED')
        check(workspace.session.document.linked_pairs[0]['enabled'],'contextual Linked twin On relinks the pair')
        workspace.perform_action('UNDO');workspace.perform_action('UNDO');workspace.perform_action('UNDO')
        check(len(workspace.session.document.patterns)==1 and not workspace.session.document.linked_pairs,
              'one clone undo removes the complete linked twin after undoing the two toggles')
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
        check(workspace.seam_selected == seam.id and workspace.selected_anchor is None and workspace.card_kind is None,
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

        knife_session=workspace.session
        workspace.session=Session()
        workspace.session.add([(0,0),(1,0),(1,1),(0,1)])
        workspace.persist();workspace.fit()
        workspace.show_card('INTERNAL_CHOOSER')
        knife_rows=[row[0] for rect,row in workspace.minimal_card()[2]]
        check(knife_rows.index('SET_INTERNAL_KNIFE')==knife_rows.index('SET_INTERNAL_DART')+1,
              'Cut sits beside Dart in the existing Internal tool choices')
        workspace.minimal_action('SET_INTERNAL_KNIFE')
        check(workspace.tool=='KNIFE' and workspace.knife_sew and workspace.card_kind is None,
              'Cut starts in Cut and Sew mode and dismisses the menu')
        workspace.choose_tool('SELECT')
        workspace.handle_event(bpy.context,event('N',point))
        check(workspace.tool=='KNIFE','unused N shortcut selects Cut without changing the eight dock tools')
        before=workspace.session.document.dumps();undo_count=len(workspace.session.undo_stack)
        def knife_click(world_point):
            screen_point=workspace.view.screen(world_point,workspace.canvas_layout.canvas)
            workspace.handle_event(bpy.context,event('LEFTMOUSE',screen_point))
            workspace.handle_event(bpy.context,event('LEFTMOUSE',screen_point,'RELEASE'))
        knife_click((-.05,.5))
        move=event('MOUSEMOVE',workspace.view.screen((.8,.7),workspace.canvas_layout.canvas));move.shift=True
        workspace.handle_event(bpy.context,move)
        check(abs(workspace.preview[-1][1]-.5)<1e-7,'Shift locks the knife live preview to the horizontal axis')
        check(len(workspace.session.knife_preview(workspace.draft+workspace.preview)[0]['hits'])==1,
              'live preview detects the outline entry before the line has fully crossed')
        workspace.handle_event(bpy.context,event('ESC',point))
        check(not workspace.draft and workspace.session.document.dumps()==before,
              'Escape cancels the knife without editing the piece or history')
        knife_click((-.05,.5));knife_click((1.05,.5))
        workspace.handle_event(bpy.context,event('LEFTMOUSE',workspace.view.screen((1,.5),workspace.canvas_layout.canvas),'DOUBLE_CLICK'))
        check(len(workspace.session.document.patterns)==2 and len(workspace.session.document.seams)==1 and not workspace.draft,
              'double-click finishes Cut and Sew at an outline without inserting an unrelated point')
        check(len(workspace.session.undo_stack)==undo_count+1,'the knife gesture commits exactly one history entry')
        workspace.perform_action('UNDO');check(workspace.session.document.dumps()==before,'knife undo restores the original piece')
        workspace.perform_action('REDO');check(len(workspace.session.document.seams)==1,'knife redo restores both pieces and their sewing')
        workspace.perform_action('UNDO')
        workspace.minimal_action('KNIFE_MODE_CUT')
        knife_click((-.05,.5));knife_click((1.05,.5))
        workspace.handle_event(bpy.context,event('RET',point))
        check(len(workspace.session.document.patterns)==2 and not workspace.session.document.seams,
              'Enter finishes Cut only without creating a seam')
        workspace.perform_action('UNDO')
        knife_click((-.05,.5));knife_click((.5,.5))
        workspace.handle_event(bpy.context,event('RET',point))
        check(workspace.session.document.dumps()==before and 'exactly twice' in workspace.message,
              'an invalid knife cut is reported on the message line without editing the document')
        workspace.cancel_gesture();workspace.knife_sew=True
        workspace.session=knife_session;workspace.persist();workspace.choose_tool('SELECT')

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
        workspace.card_kind = None
        canvas_point = (workspace.canvas_layout.canvas.x + 12, workspace.canvas_layout.canvas.y + 12)
        save_event = event('S', canvas_point)
        save_event.ctrl = True
        check(workspace.handle_event(bpy.context, save_event) == {'PASS_THROUGH'},
              'Ctrl S passes through to native Blender save')
        before = workspace.session.document.dumps()
        workspace.session.add([(.5, 0), (.7, 0), (.7, .4), (.5, .4)])
        workspace.persist()
        undo_event = event('Z', canvas_point)
        undo_event.ctrl = True
        workspace.handle_event(bpy.context, undo_event)
        check(workspace.session.document.dumps() == before,
              'Ctrl Z reaches document undo instead of being swallowed')

        workspace.session = Session(Document())
        workspace.session.add([(-.4, 0), (.4, 0), (.4, .6), (-.4, .6)])
        open_path = workspace.session.add_path([(-.2, .15), (.2, .15)])
        closed_path = workspace.session.add_path([(-.2, .3), (.2, .3), (.2, .45), (-.2, .45)], True)
        owner = workspace.session.selected
        workspace.persist()
        workspace.fit()
        for internal_path in (open_path, closed_path):
            workspace.card_kind = None
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
        check(workspace.card_kind is None and workspace.session.document.dumps() == document_before_close,
              'popover card close dismisses the popover without editing garment data')
        workspace.show_card('EDIT', point)
        dock = workspace.canvas_layout.buttons['DRAW'][0]
        workspace.handle_event(bpy.context, event('RIGHTMOUSE', (dock.x + dock.w / 2, dock.y + dock.h / 2)))
        check(workspace.card_kind is None and workspace.tool == 'SELECT',
              'right click dismisses an explicit popover before dispatching an underlying dock action')

        workspace.clear_interaction_references()
        workspace.choose_tool('SELECT')
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
        for scale in (1, 1.5):
            layout = Layout(1600 * scale, 1000 * scale, scale, full=True)
            minimal_layout(layout)
            canvas = layout.canvas
            with patch.object(workspace, 'session', fit_session), \
                    patch.object(workspace, 'canvas_layout', layout), \
                    patch.object(workspace, 'reference_corners', return_value=[]):
                workspace.fit()
                projected = [workspace.view.screen(vertex, canvas) for vertex in fit_session.document.patterns[0].points]
                check(min(vertex[0] for vertex in projected) > layout.rail.x + layout.rail.w and
                      max(vertex[0] for vertex in projected) < layout.canvas.x + layout.canvas.w,
                      'minimal Fit clears the dock and fills the canvas at scale ' + str(scale))
        compact = Layout(628, 700, 1, full=True)
        minimal_layout(compact)
        check(compact.inspector is None and compact.canvas.w >= compact.panel.w - 16,
              '628 pixel compact workspace maintains full canvas without sidebars')
    finally:
        workspace.clear_interaction_references()
        workspace.session = original_session
        workspace.library_items = original_library_items
        workspace.card_kind = None
        workspace.persist()
        workspace.choose_tool(original_tool)
        workspace._scene.dd_free_sewing = original_free_sewing
        workspace.view.cx, workspace.view.cy, workspace.view.zoom = original_view


def check_arrangement_controls(workspace,event,check):
    import math
    from mathutils import Quaternion
    from devil_designer import arrangement,arrangement_controls,garment,live_panels
    region=bpy.context.region;view=bpy.context.region_data;scene=bpy.context.scene
    saved=(workspace.full,workspace.window_rect,scene.dd_reference_visible,
           view.view_location.copy(),view.view_rotation.copy(),view.view_distance,view.view_perspective)
    try:
        workspace.full=False;workspace.window_rect=(12,12,420,420)
        workspace.session.selected=workspace.session.document.patterns[0].id
        workspace.canvas_layout=workspace.make_layout()
        scene.dd_reference_visible=True
        view.view_location=scene.dd_avatar.matrix_world.translation
        view.view_rotation=Quaternion((1,0,0),math.pi/2);view.view_distance=3;view.view_perspective='ORTHO'
        bpy.context.view_layer.update()
        points=arrangement_controls.projected_points(bpy.context)
        check(bool(points),'avatar arrangement dots project into the uncovered 3D view')
        target=next(point for point in points if point['volume']=='chest' and point['point']=='front')
        screen=target['screen']
        check(0<screen[0]<region.width and 0<screen[1]<region.height,'chest point is visible outside the drawing window')
        workspace.handle_event(bpy.context,event('H',screen))
        check(not arrangement_controls.projected_points(bpy.context),'H hides arrangement dots along with the body guide')
        workspace.handle_event(bpy.context,event('H',screen))
        workspace.handle_event(bpy.context,event('LEFTMOUSE',screen))
        pattern=workspace.session.document.find(workspace.session.selected)
        check(pattern.arrangement and pattern.arrangement['volume']=='chest','clicking a visible chest dot arranges the selected piece')
        identity=pattern.id;chosen=pattern.arrangement['point']
        workspace.perform_action('UNDO')
        check(workspace.session.document.find(identity).arrangement is None,'Undo removes a point arrangement in one step')
        workspace.perform_action('REDO')
        check(workspace.session.document.find(identity).arrangement['point']==chosen,'Redo restores the recorded point arrangement')
        bpy.ops.devil_designer.arrangement_edit(action='FLAT',volume='chest',point=chosen)
        check(workspace.session.document.find(identity).arrangement['flat'],'point card Arrange flat keeps a tangent panel')
        panel=next(panel for panel in garment.generated(scene,'panel') if panel['dd_pattern_id']==identity)
        panel.location.x+=.02;bpy.context.view_layer.update();live_panels.capture(bpy.context)
        delta=workspace.session.document.find(identity).arrangement['translation'][:]
        check(sum(abs(value) for value in delta)>.019,'native 3D movement updates the active editor arrangement deltas')
        bpy.ops.devil_designer.arrangement_edit(action='FLAT',volume='chest',point=chosen)
        check(workspace.session.document.find(identity).arrangement['translation']==[0.0]*3,
              'choosing the same point again clears previous 3D movement deltas')
        bpy.ops.devil_designer.arrangement_edit(action='MOVE',volume='chest',point=chosen,angle=.25,height=.6)
        setup=arrangement.ensure_volumes(bpy.context);volume=next(volume for volume in setup['volumes'] if volume['id']=='chest')
        moved=next(point for point in volume['points'] if point['id']==chosen)
        check(abs(moved['angle']-.25)<1e-6 and abs(moved['height']-.6)<1e-6,'point card moves a point around and up its volume')
        count=len(volume['points'])
        bpy.ops.devil_designer.arrangement_edit(action='ADD',volume='chest',point=chosen,angle=.75,height=.4)
        volume=next(volume for volume in arrangement.ensure_volumes(bpy.context)['volumes'] if volume['id']=='chest')
        added=volume['points'][-1]['id']
        check(len(volume['points'])==count+1 and added.startswith('custom_'),'point card adds a stable avatar-owned point')
        bpy.ops.devil_designer.arrangement_edit(action='DELETE',volume='chest',point=added)
        volume=next(volume for volume in arrangement.ensure_volumes(bpy.context)['volumes'] if volume['id']=='chest')
        check(len(volume['points'])==count,'point card deletes the chosen avatar point')
        workspace.minimal_action('RESET_LAYOUT')
        check(workspace.session.document.find(identity).arrangement is None,'piece card Reset to 2D layout clears the arrangement')
    finally:
        workspace.full,workspace.window_rect,scene.dd_reference_visible=saved[:3]
        view.view_location,view.view_rotation,view.view_distance,view.view_perspective=saved[3:]
        workspace.canvas_layout=workspace.make_layout()


def run():
    passed = []

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        passed.append(message)

    try:
        import devil_designer
        from devil_designer import editor, garment
        from devil_designer.canvas import Layout
        from devil_designer.minimal import FABRICS, DENSITY, QUALITY, THICKNESS, GUIDE_OPACITY, minimal_layout
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

            check(workspace.minimal_ui and workspace.canvas_layout.inspector is None,
                  'default workspace has pure canvas with zero sidebars')
            check(not {'SETTINGS', 'SEARCH', 'MORE_TOOLS', 'BUILD', 'SIMULATE_OPTIONS', 'WORKSPACE_PANEL'} & set(workspace.canvas_layout.buttons),
                  'default chrome contains reduced tool dock, close, garment, and keep options')
            check(workspace.tool == 'RECTANGLE', 'panel drawing is ready immediately')

            dock_tools = [k for k in ('SELECT', 'DRAW', 'INTERNAL', 'SEW', 'PIN', 'UNDO', 'REDO', 'LIBRARY') if k in workspace.canvas_layout.buttons]
            check(len(dock_tools) == 8, 'reduced left dock has exactly 8 tools')
            check({'TOGGLE_SNAP', 'TOGGLE_GUIDE', 'TOGGLE_LENGTHS'}.issubset(set(workspace.canvas_layout.buttons)),
                  'S, H and L toggles are on the left dock')

            snapping = workspace.snap
            button('TOGGLE_SNAP')
            check(workspace.snap != snapping, 'dock Snap toggle toggles drawing snap state')
            button('TOGGLE_SNAP')

            lengths = scene.dd_lengths_visible
            button('TOGGLE_LENGTHS')
            check(scene.dd_lengths_visible != lengths, 'dock Lengths toggle toggles canvas length labels')
            button('TOGGLE_LENGTHS')

            guides = scene.dd_reference_visible
            button('TOGGLE_GUIDE')
            check(scene.dd_reference_visible != guides, 'dock Guide toggle toggles body reference visibility')
            button('TOGGLE_GUIDE')

            workspace.show_card('CANVAS_MENU')
            card = workspace.minimal_card()
            check(card is not None and card[1] == 'Garment & View',
                  'right click on empty canvas opens Garment & View contextual menu')

            check(scene.dd_fabric == 'COTTON' and workspace.session.document.preset == 'COTTON',
                  'garment default fabric starts as Cotton')
            workspace.minimal_action('INSP_GARMENT_FABRIC_LEATHER')
            check(scene.dd_fabric == 'LEATHER' and workspace.session.document.preset == 'LEATHER',
                  'changing default fabric updates garment-wide preset to Leather')

            workspace.minimal_action('INSP_GARMENT_DENSITY_Coarse')
            check(abs(scene.dd_spacing - DENSITY['Coarse']) < 1e-6,
                  'garment density chip changes scene spacing')

            workspace.minimal_action('INSP_QUALITY_High')
            check(scene.dd_quality == QUALITY['High'],
                  'simulation quality chip changes scene quality')

            workspace.minimal_action('INSP_OPACITY_Strong')
            check(abs(scene.dd_reference_opacity - GUIDE_OPACITY['Strong']) < 1e-6,
                  'guide opacity chip changes silhouette opacity')

            original_view = (workspace.view.cx, workspace.view.cy, workspace.view.zoom)
            workspace.view.cx, workspace.view.cy, workspace.view.zoom = 2, 3, 20
            workspace.minimal_action('INSP_FIT')
            check(workspace.view.cx == 0 and workspace.view.cy == 0 and workspace.view.zoom > 20,
                  'Fit design contextual action uses the canvas framing operation')
            workspace.view.cx, workspace.view.cy, workspace.view.zoom = original_view

            canvas_point = (workspace.canvas_layout.canvas.x + workspace.canvas_layout.canvas.w / 2, workspace.canvas_layout.canvas.y + 80)
            check_interaction_regressions(workspace, event, canvas_point, check)

            workspace.choose_tool('RECTANGLE')
            for start, end in [((-.4, 0), (-.1, .4)), ((.1, 0), (.4, .4))]:
                first = workspace.view.screen(start, workspace.canvas_layout.canvas)
                last = workspace.view.screen(end, workspace.canvas_layout.canvas)
                workspace.handle_event(bpy.context, event('LEFTMOUSE', first))
                workspace.handle_event(bpy.context, event('MOUSEMOVE', last))
                workspace.handle_event(bpy.context, event('LEFTMOUSE', last, 'RELEASE'))
            check(len(workspace.session.document.patterns) == 2, 'two mouse drags create two panels')
            check(workspace.card_kind is None and len(workspace.visible_cards()) == 0,
                  'selecting a piece never opens a canvas overlay')

            pattern = workspace.session.document.patterns[-1]
            check(pattern.preset == 'LEATHER' and pattern.fabric_override is False,
                  'new piece inherits garment default fabric without override')

            workspace.minimal_action('SET_PIECE_FABRIC_SILK')
            check(pattern.preset == 'SILK' and pattern.fabric_override is True,
                  'setting piece fabric creates a fabric override')

            workspace.minimal_action('INSP_GARMENT_FABRIC_COTTON')
            check(pattern.preset == 'SILK',
                  'changing garment default fabric preserves the piece override')

            workspace.minimal_action('SET_DENSITY_COARSE')
            check(pattern.mesh_density == 'COARSE',
                  'setting piece mesh density updates piece spacing')

            button('SELECT')
            pattern0 = workspace.session.document.patterns[0]
            original_point = pattern0.points[0]
            point = workspace.view.screen(original_point, workspace.canvas_layout.canvas)
            click(point, 'RIGHTMOUSE')
            check(workspace.card_kind == 'POINT', 'right clicking a point reveals only its local editing choices')
            control = next(rect for rect, row in workspace.minimal_card()[2] if row[0] == 'SLIDER' and row[1] == 'dd_point_x')
            handle = (control.x + control.w * .7, control.y + 12)
            workspace.handle_event(bpy.context, event('LEFTMOUSE', handle))
            dragged = (handle[0] + 24, handle[1])
            workspace.handle_event(bpy.context, event('MOUSEMOVE', dragged))
            workspace.handle_event(bpy.context, event('LEFTMOUSE', dragged, 'RELEASE'))
            check(pattern0.points[0][0] > original_point[0], 'dragging an exact design value applies the local point edit')
            workspace.card_kind = None
            workspace.perform_action('UNDO')
            check(workspace.session.document.patterns[0].points[0] == original_point,
                  'a local numeric design edit is one undoable operation')

            button('KEEP_OPTIONS')
            check(len(workspace.minimal_card()[2]) == 2 and not any(row[0] == 'SLIDER' for rect, row in workspace.minimal_card()[2]),
                  'Keep uses Auto weld and named thickness, without a premature manual tolerance')
            thickness_rect = workspace.minimal_card()[2][1][0]
            click((thickness_rect.x + thickness_rect.w / 6, thickness_rect.y + 16))
            check(scene.dd_thickness == THICKNESS['None'], 'None thickness is a named finalize choice')

            for kind in ('KEEP', 'GARMENT', 'BODY', 'LIBRARY', 'POINT', 'EDGE', 'EDIT', 'CUT_RECOVERY'):
                workspace.show_card(kind)
                card = workspace.minimal_card()
                check(card is None or sum(row[0] != 'INFO' for rect, row in card[2]) <= 5,
                      kind + ' card stays within the five-control cap')
            workspace.card_kind = None

            canvas_pos = (workspace.canvas_layout.canvas.x + 20, workspace.canvas_layout.canvas.y + 20)
            save_evt = event('S', canvas_pos)
            save_evt.ctrl = True
            check(workspace.handle_event(bpy.context, save_evt) == {'PASS_THROUGH'},
                  'Ctrl+S passes through to native Blender save')
            undo_evt = event('Z', canvas_pos)
            undo_evt.ctrl = True
            check(workspace.handle_event(bpy.context, undo_evt) == {'RUNNING_MODAL'},
                  'Ctrl+Z undo works properly')
            redo_evt = event('Z', canvas_pos)
            redo_evt.ctrl = True
            redo_evt.shift = True
            check(workspace.handle_event(bpy.context, redo_evt) == {'RUNNING_MODAL'},
                  'Ctrl+Shift+Z redo works properly')

            workspace.handle_event(bpy.context, event('P', canvas_point))
            check(workspace.tool == 'POLYGON' and workspace.draw_shape == 'POLYGON', 'P activates polygon draw')
            workspace.handle_event(bpy.context, event('R', canvas_point))
            check(workspace.tool == 'RECTANGLE' and workspace.draw_shape == 'RECTANGLE', 'R activates rectangle draw')
            workspace.handle_event(bpy.context, event('E', canvas_point))
            check(workspace.tool == 'ELLIPSE' and workspace.draw_shape == 'ELLIPSE', 'E activates ellipse draw')
            workspace.handle_event(bpy.context, event('I', canvas_point))
            check(workspace.tool == 'INTERNAL' and workspace.internal_tool == 'INTERNAL', 'I activates internal tool')
            workspace.handle_event(bpy.context, event('D', canvas_point))
            check(workspace.tool == 'DART' and workspace.internal_tool == 'DART', 'D activates dart tool')
            workspace.handle_event(bpy.context, event('K', canvas_point))
            check(workspace.tool == 'PIN' and workspace.pin_tool == 'PIN', 'K activates pin tool')
            workspace.handle_event(bpy.context, event('T', canvas_point))
            check(workspace.tool == 'TACK' and workspace.pin_tool == 'TACK', 'T activates tack tool')
            workspace.handle_event(bpy.context, event('V', canvas_point))
            check(workspace.tool == 'SELECT', 'V activates select tool')

            narrow_layout = Layout(700, 800, 1, full=True)
            minimal_layout(narrow_layout)
            check(narrow_layout.inspector is None and narrow_layout.canvas.w >= narrow_layout.panel.w - 16,
                  'narrow layout maintains clean full canvas without sidebar')

            from devil_designer.core import Document, Session
            legacy_sess = Session(Document())
            legacy_sess.add([(0, 0), (.4, 0), (.4, .4), (0, .4)])
            legacy_sess.document.patterns[0].preset = 'LINEN'
            raw = json.loads(legacy_sess.document.dumps())
            raw.pop('preset', None)
            raw['patterns'][0].pop('fabric_override', None)
            loaded_doc = Document.loads(json.dumps(raw))
            check(loaded_doc.preset == 'COTTON', 'legacy document defaults garment to Cotton')
            check(loaded_doc.patterns[0].preset == 'LINEN' and loaded_doc.patterns[0].fabric_override is True,
                  'legacy document marks non-default pattern preset as override')
            button('SEW')
            for point in ((-.25, 0), (.25, 0)):
                click(workspace.view.screen(point, workspace.canvas_layout.canvas))
            check(len(workspace.session.document.seams) == 1, 'Sew pairs the panels directly on canvas')
            badge = workspace.seam_badges()[0][0]
            click((badge.x + badge.w / 2, badge.y + badge.h / 2))
            check(workspace.seam_selected == workspace.session.document.seams[0].id and workspace.card_kind is None,
                  'selecting seam badge selects seam without auto-opening canvas card')
            click((badge.x + badge.w / 2, badge.y + badge.h / 2), 'RIGHTMOUSE')
            check(workspace.card_kind == 'SEAM' and any(row[1] == 'FLIP_SEAM' for rect, row in workspace.minimal_card()[2]),
                  'right clicking seam badge opens seam menu with reverse and remove')
            for shrink in (10, 20, 30, 0):
                badge = workspace.seam_badges()[0][0]
                if workspace.card_kind != 'SEAM':
                    click((badge.x + badge.w / 2, badge.y + badge.h / 2), 'RIGHTMOUSE')
                rect, row = next((rect, row) for rect, row in workspace.minimal_card()[2] if row[0] == 'CHOICES' and row[1] == 'Shrink')
                check(tuple(row[2][1]) == ('0%', '10%', '20%', '30%'), 'seam menu exposes exactly four Shrink choices')
                warnings = [row for control, row in workspace.minimal_card()[2] if row[0] == 'INFO' and row[1] in ('Nonzero: 1 mm self-collision', 'Other folds may change')]
                check(len(warnings) == 2 and all(not row[2] for row in warnings), 'Shrinks collision cost and fold warning each use a full-width readable row')
                click((rect.x + (shrink / 10 + .5) * rect.w / 4, rect.y + rect.h / 2))
                check(workspace.card_kind is None and workspace.session.document.seams[0].shrink == shrink,
                      f'Shrink {shrink}% executes and dismisses the contextual menu')
                check(Document.loads(scene.dd_document).seams[0].shrink == shrink, 'Shrink persists into the editable scene document')
            workspace.perform_action('UNDO')
            check(workspace.session.document.seams[0].shrink == 30, 'canvas Undo restores seam Shrink')
            workspace.perform_action('REDO')
            check(workspace.session.document.seams[0].shrink == 0, 'canvas Redo restores zero Shrink')
            badge = workspace.seam_badges()[0][0]
            click((badge.x + badge.w / 2, badge.y + badge.h / 2), 'RIGHTMOUSE')
            before = workspace.session.document.seams[0].reverse
            workspace.handle_event(bpy.context, event('B', canvas_point))
            check(workspace.session.document.seams[0].reverse != before, 'seam direction changes')
            workspace.handle_event(bpy.context, event('B', canvas_point))
            check(len(garment.generated(scene, 'panel'))==2, 'committed pieces already have live panels without Build or Arrange')
            scene.dd_self_collision = False
            scene.dd_library_refit = False
            button('SIMULATE')
            check(bpy.context.screen.is_animation_playing and scene.dd_avatar == body,
                  'Simulate detects the body and starts cloth from current live panels')
            check(scene.dd_self_collision and scene.dd_library_refit,
                  'self collision and library refit are automatic decisions, not controls')
            panels = garment.generated(scene, 'panel')
            check(len(panels) == 2 and all(panel.location.y<0 for panel in panels),
                  'unarranged panels simulate in front from their layout without a front/back guess')
            button('SIMULATE')
            check(not bpy.context.screen.is_animation_playing, 'the same transport button pauses playback')
            check_arrangement_controls(workspace,event,check)
            panels=garment.generated(scene,'panel')
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
            kept=garment.generated(scene,'final')[0]
            for index in range(6):
                extra=kept.copy()
                extra.name=f'Kept layer {index+1}'
                scene.collection.objects.link(extra)
            workspace.card_kind=None
            button('SIMULATE_OPTIONS')
            check(workspace.card_kind=='SIMULATE','Simulate arrow opens Wear over only after kept garments exist')
            rows=[row for rect,row in workspace.minimal_card()[2] if row[0].startswith('WEAR_OVER_')]
            check(len(rows)==5 and all(row[2]=='On' for row in rows),'Wear over shows at most five garments and defaults every garment on')
            first_names=[row[1] for row in rows]
            card=workspace.minimal_card()[0]
            inside=(card.x+card.w/2,card.y+card.h/2)
            zoom=workspace.view.zoom
            workspace.handle_event(bpy.context,event('WHEELDOWNMOUSE',inside))
            rows=[row for rect,row in workspace.minimal_card()[2] if row[0].startswith('WEAR_OVER_')]
            check([row[1] for row in rows]!=first_names and workspace.view.zoom==zoom,'Wear over scrolls its five-row list without zooming the canvas')
            target=workspace.card_models[int(rows[-1][0].removeprefix('WEAR_OVER_'))]
            card_click(rows[-1][0])
            check(target.get('dd_wear_over') is False and workspace.card_kind is None,'Wear over toggle persists and immediately dismisses to pure canvas')
            button('SIMULATE_OPTIONS')
            card_click('SCROLL_WEAR_OVER')
            check(workspace.card_kind=='SIMULATE' and len([row for rect,row in workspace.minimal_card()[2] if row[0].startswith('WEAR_OVER_')])==5,
                  'Wear over next control keeps navigation open and never shows more than five garments')
            workspace.handle_event(bpy.context,event('ESC',inside))
            check(workspace.card_kind is None,'Escape dismisses Wear over')
            button('SIMULATE_OPTIONS')
            click((workspace.canvas_layout.canvas.x+100,workspace.canvas_layout.canvas.y+100))
            check(workspace.card_kind is None,'outside click dismisses Wear over without an inspector')
        report = {'passed': passed}
    except Exception:
        report = {'passed': passed, 'error': traceback.format_exc()}
        traceback.print_exc()
    (ROOT / 'scratch').mkdir(exist_ok=True)
    (ROOT / 'scratch' / 'fast_flow-report.json').write_text(json.dumps(report, indent=2))
    return None


bpy.app.timers.register(run, first_interval=2)
