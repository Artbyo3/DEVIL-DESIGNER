import json
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch
try:
    import bpy
except ImportError:
    from unittest.mock import MagicMock
    import sys
    sys.modules['bpy'] = MagicMock()
from devil_designer.construction import chain_range,sew_reverse
from devil_designer.core import Document, Session, EdgeRef
from devil_designer.linked_editing import clone_twin, toggle_link
from devil_designer.design_tools import DesignTools
from devil_designer.meshing import edge_counts

class SeamTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.add([(0,0),(.3,0),(.3,.4),(0,.4)])
        self.s.add([(.5,0),(.9,0),(.9,.5),(.5,.5)])
        a,b = self.s.document.patterns
        self.a,self.b = self.s.document.edge(a.id,1),self.s.document.edge(b.id,3)

    def test_mn_sewing_orders_reverse_clicks_and_wraparound(self):
        for indices in ((1,0),(0,3),(3,2,1,0)):
            with self.subTest(indices=indices):
                editor=DummyEditor(self.s,DummyScene(dd_sew_reverse=True))
                doc=self.s.document
                first,second=doc.patterns
                editor.mn_chain=[doc.edge(first.id,i) for i in indices]
                editor.mn_commit()
                expected=([3,0] if indices==(0,3) else sorted(indices))
                self.assertEqual(editor.mn_first,[doc.edge(first.id,i) for i in expected])
                editor.mn_chain=[doc.edge(second.id,i) for i in indices]
                editor.mn_commit()
                seam=doc.seams[-1]
                for side in (0,1):
                    chain=seam.side(side)
                    self.assertTrue(all(a.end==b.start for a,b in zip(chain,chain[1:])))
                self.s.remove_seam(seam.id)

    def test_full_chain_range_stays_inside_each_edge_despite_float_rounding(self):
        doc=self.s.document
        first=doc.patterns[0]
        chain=[doc.edge(first.id,0),doc.edge(first.id,1)]
        lengths={chain[0].full():0.30000000000000004,chain[1].full():0.4000000000000001}
        with patch.object(doc,'edge_length',lambda edge:lengths[edge.full()]),patch.object(doc,'chain_length',lambda edges:sum(lengths[e.full()] for e in edges)):
            for start,end in ((0,1),(1,0)):
                with self.subTest(start=start,end=end):
                    result=chain_range(doc,chain,start,end)
                    self.assertTrue(all(0<=t<=1 for edge in result for t in (edge.t0,edge.t1)))
                    self.assertEqual(sorted((result[-1 if start==0 else 0].t0,result[-1 if start==0 else 0].t1)),[0.0,1.0])

    def test_mn_sewing_refuses_disconnected_edges_on_either_side(self):
        for bad_first in (True,False):
            with self.subTest(bad_first=bad_first):
                editor=DummyEditor(self.s,DummyScene(dd_sew_reverse=True))
                doc=self.s.document
                first,second=doc.patterns
                before=doc.dumps()
                editor.mn_chain=[doc.edge(first.id,i) for i in ((0,2) if bad_first else (1,0))]
                editor.mn_commit()
                if not bad_first:
                    editor.mn_chain=[doc.edge(second.id,i) for i in (0,2)]
                    editor.mn_commit()
                self.assertIn('contiguous',editor.message)
                self.assertEqual(doc.dumps(),before)

    def test_document_load_clears_every_old_selection_and_restores_history(self):
        for action in ('STARTER_TANK','LIBRARY_LOAD'):
            for kind in ('PIECES','POINTS','EDGES','PATHS'):
                with self.subTest(action=action,kind=kind):
                    session=Session()
                    session.add([(0,0),(.2,0),(.2,.3),(0,.3)])
                    session.add([(.4,0),(.6,0),(.6,.3),(.4,.3)])
                    session.add_path([(.45,.1),(.55,.2)])
                    session.acquisition_target=kind;session.select_all()
                    session.placed_pivot=(5,5)
                    before=session.document.dumps();selection=session.get_selection_state()
                    scene=DummyScene(dd_avatar=None,dd_document=before,dd_library_selected=0)
                    editor=DummyEditor(session,scene)
                    for method in ('clear_interaction_references','update_reference','fit','choose_tool','refresh_library'):
                        setattr(editor,method,lambda *args,**kwargs:None)
                    editor.library_items=['saved']
                    editor.library_previews={'saved':{'tags':[]}}
                    loaded=Session();loaded.add([(1,0),(1.2,0),(1.2,.3),(1,.3)])
                    library=SimpleNamespace(load=lambda *args:loaded.document)
                    with patch.dict('sys.modules',{'devil_designer.library':library}),patch('devil_designer.library',library,create=True):
                        self.assertTrue(editor.design_action(action),editor.message)
                    new_id=session.document.patterns[0].id
                    self.assertEqual(session.selected_patterns,{new_id})
                    self.assertEqual(session.active_entity,('PIECE',new_id))
                    self.assertFalse(session.selected_points or session.selected_edges or session.selected_paths)
                    self.assertIsNone(session.placed_pivot)
                    self.assertIsNotNone(session.selection_bounds())
                    session.history()
                    self.assertEqual(session.document.dumps(),before)
                    restored=session.get_selection_state()
                    self.assertEqual(set(restored.pop('point_selection')),set(selection.pop('point_selection')))
                    self.assertEqual(restored,selection)
                    session.history(True)
                    self.assertEqual(session.selected_patterns,{new_id})
                    count=len(session.document.patterns)
                    session.delete()
                    self.assertEqual(len(session.document.patterns),count-1)

    def test_version_one_migrates_without_losing_ids(self):
        old = json.loads(self.s.document.dumps())
        old['version'] = 1
        del old['seams']
        d = Document.loads(json.dumps(old))
        self.assertEqual(d.patterns[0].id,self.s.document.patterns[0].id)
        self.assertEqual(d.seams,[])
        self.assertEqual(json.loads(d.dumps())['version'],4)

    def test_sewing_round_trip_and_direction(self):
        self.s.sew(self.a,self.b)
        seam = self.s.document.seams[0]
        self.s.reverse_seam(seam.id)
        loaded = Document.loads(self.s.document.dumps())
        self.assertFalse(loaded.seams[0].reverse)
        self.assertEqual(loaded.seams[0].a,self.a)
        self.assertEqual(loaded.seams[0].b,self.b)

    def test_overlapping_ranges_rejected_and_same_piece_sewing_allowed(self):
        self.s.sew(self.a,self.b)
        before = self.s.document.dumps()
        with self.assertRaises(ValueError):
            self.s.sew(self.a,self.b)
        self.assertEqual(self.s.document.dumps(),before)
        self.s.remove_seam(self.s.document.seams[0].id)
        self.s.sew(self.a,self.s.document.edge(self.a.pattern,0))
        self.assertEqual(len(self.s.document.seams),1)

    def test_seams_survive_reshape_and_undo(self):
        self.s.sew(self.a,self.b)
        identity = self.s.document.seams[0].id
        self.s.selected = self.a.pattern
        p = self.s.document.find(self.a.pattern)
        self.s.move([(x+.02,y) for x,y in p.points])
        self.assertEqual(self.s.document.seams[0].id,identity)
        self.s.history()
        self.assertEqual(self.s.document.seams[0].a,self.a)

    def test_removed_corner_removes_only_affected_seams(self):
        self.s.sew(self.a,self.b)
        self.s.selected,self.s.corner = self.a.pattern,1
        self.s.delete()
        self.assertEqual(self.s.document.seams,[])
        self.s.history()
        self.assertEqual(len(self.s.document.seams),1)

    def test_unequal_edges_get_matching_samples(self):
        self.s.sew(self.a,self.b)
        counts = edge_counts(self.s.document,.03)
        self.assertEqual(counts[self.a],counts[self.b])
        self.assertGreaterEqual(counts[self.a],math.ceil(.5/.03))

    def test_references_to_removed_edges_are_rejected_on_load(self):
        self.s.sew(self.a,self.b)
        value = json.loads(self.s.document.dumps())
        value['seams'][0]['a']['start'] = 'missing'
        with self.assertRaises(ValueError):
            Document.loads(json.dumps(value))

    def test_sew_reverse_matches_preview_orientation(self):
        doc = self.s.document
        a, b = doc.patterns
        edge_a1 = doc.edge(a.id, 1)
        edge_b1 = doc.edge(b.id, 1)
        edge_b3 = doc.edge(b.id, 3)
        pa0 = doc.edge_point(edge_a1, edge_a1.t0)
        pa1 = doc.edge_point(edge_a1, edge_a1.t1)
        pb0 = doc.edge_point(edge_b1, edge_b1.t0)
        pb1 = doc.edge_point(edge_b1, edge_b1.t1)
        same_dir = ((pa1[0] - pa0[0]) * (pb1[0] - pb0[0]) + (pa1[1] - pa0[1]) * (pb1[1] - pb0[1])) >= 0
        self.assertTrue(same_dir)
        preview_rev_default = not True if same_dir else True
        self.assertFalse(preview_rev_default)
        self.assertEqual(sew_reverse(doc, edge_a1, edge_b1, True), preview_rev_default)
        preview_rev_flipped = not False if same_dir else False
        self.assertTrue(preview_rev_flipped)
        self.assertEqual(sew_reverse(doc, edge_a1, edge_b1, False), preview_rev_flipped)
        po0 = doc.edge_point(edge_b3, edge_b3.t0)
        po1 = doc.edge_point(edge_b3, edge_b3.t1)
        opp_dir = ((pa1[0] - pa0[0]) * (po1[0] - po0[0]) + (pa1[1] - pa0[1]) * (po1[1] - po0[1])) >= 0
        self.assertFalse(opp_dir)
        preview_opp_default = not True if opp_dir else True
        self.assertTrue(preview_opp_default)
        self.assertEqual(sew_reverse(doc, edge_a1, edge_b3, True), preview_opp_default)
        preview_opp_flipped = not False if opp_dir else False
        self.assertFalse(preview_opp_flipped)
        self.assertEqual(sew_reverse(doc, edge_a1, edge_b3, False), preview_opp_flipped)

    def test_newly_created_seam_direction_matches_preview_calculation(self):
        doc = self.s.document
        a, b = doc.patterns
        edge_a = doc.edge(a.id, 1)
        edge_b_same = doc.edge(b.id, 1)
        edge_b_opp = doc.edge(b.id, 3)
        scene = DummyScene(
            dd_free_sewing=False,
            dd_sew_reverse=True,
            dd_sew_a0=0.0,
            dd_sew_a1=1.0,
            dd_sew_b0=0.0,
            dd_sew_b1=1.0,
        )
        editor = DummyEditor(self.s, scene)
        editor.design_sew_click(viewport_hit=(edge_a, 0.5))
        self.assertEqual(editor.pending_edge, edge_a)
        editor.design_sew_click(viewport_hit=(edge_b_same, 0.5))
        self.assertEqual(len(self.s.document.seams), 1)
        seam_same = self.s.document.seams[-1]
        self.assertFalse(seam_same.reverse)
        self.assertEqual(seam_same.reverse, sew_reverse(doc, edge_a, edge_b_same, scene.dd_sew_reverse))
        self.s.document.seams.clear()
        scene.dd_sew_reverse = False
        editor.design_sew_click(viewport_hit=(edge_a, 0.5))
        editor.design_sew_click(viewport_hit=(edge_b_same, 0.5))
        seam_flipped = self.s.document.seams[-1]
        self.assertTrue(seam_flipped.reverse)
        self.assertEqual(seam_flipped.reverse, sew_reverse(doc, edge_a, edge_b_same, scene.dd_sew_reverse))
        self.s.document.seams.clear()
        scene.dd_sew_reverse = True
        editor.design_sew_click(viewport_hit=(edge_a, 0.5))
        editor.design_sew_click(viewport_hit=(edge_b_opp, 0.5))
        seam_opp = self.s.document.seams[-1]
        self.assertTrue(seam_opp.reverse)
        self.assertEqual(seam_opp.reverse, sew_reverse(doc, edge_a, edge_b_opp, scene.dd_sew_reverse))

    def test_newly_created_free_seam_direction(self):
        doc = self.s.document
        a, b = doc.patterns
        edge_a = doc.edge(a.id, 1)
        edge_b = doc.edge(b.id, 1)
        scene = DummyScene(
            dd_free_sewing=True,
            dd_sew_reverse=True,
            dd_sew_a0=0.0,
            dd_sew_a1=1.0,
            dd_sew_b0=0.0,
            dd_sew_b1=1.0,
        )
        editor = DummyEditor(self.s, scene)
        editor.design_sew_click(viewport_hit=(edge_a, 0.2))
        editor.design_sew_click(viewport_hit=(edge_a, 0.8))
        editor.design_sew_click(viewport_hit=(edge_b, 0.2))
        editor.design_sew_click(viewport_hit=(edge_b, 0.8))
        self.assertEqual(len(self.s.document.seams), 1)
        free_seam = self.s.document.seams[-1]
        self.assertFalse(free_seam.reverse)
        self.assertEqual(free_seam.reverse, sew_reverse(doc, free_seam.side(0), free_seam.side(1), scene.dd_sew_reverse))

    def test_seam_warning_30_to_35_fixture(self):
        s = Session()
        s.add([(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)])
        s.add([(0.3, 0.0), (0.5, 0.0), (0.5, 0.3), (0.3, 0.3)])
        p1, p2 = s.document.patterns
        e1 = s.document.edge(p1.id, 1)
        e2 = s.document.edge(p2.id, 3)
        s.sew(e1, e2)
        s.select_point(p1.id, 'OUTER', 2)
        doc_before = s.document.dumps()
        u_before = len(s.undo_stack)
        warn = s.move_selection(0.0, 0.05, confirm=False)
        self.assertIsInstance(warn, dict)
        self.assertEqual(warn['status'], 'WARN')
        self.assertAlmostEqual(warn['diff_cm'], 5.0, delta=1e-4)
        self.assertAlmostEqual(warn['percent'], 14.285714, delta=1e-4)
        self.assertEqual(s.document.dumps(), doc_before)
        self.assertEqual(len(s.undo_stack), u_before)
        s.move_selection(0.0, 0.05, confirm=True)
        self.assertEqual(len(s.undo_stack), u_before + 1)
        self.assertEqual(len(s.document.seams), 1)
        self.assertAlmostEqual(s.document.edge_length(s.document.edge(p1.id, 1)), 0.35, delta=1e-4)

    def test_section9_check10_seam_follow_rigid_and_scale_ease_preservation(self):
        s = Session()
        s.add([(0.0, 0.0), (0.4, 0.0), (0.4, 0.5), (0.0, 0.5)])
        p1 = s.document.patterns[0]
        s.split_segment(s.document.edge(p1.id, 1), 0.5)
        s.add([(0.6, 0.0), (1.0, 0.0), (1.0, 0.4), (0.6, 0.4)])
        p2 = s.document.patterns[1]
        s.add([(1.5, 0.0), (1.8, 0.0), (1.8, 0.4), (1.5, 0.4)])
        p3 = s.document.patterns[2]

        p1_edges = [s.document.edge(p1.id, 1), s.document.edge(p1.id, 2)]
        p2_edge = s.document.edge(p2.id, 3)
        p2_span = EdgeRef(p2_edge.pattern, p2_edge.start, p2_edge.end, t0=0.1, t1=0.9, path=p2_edge.path)
        s.sew_chains(p1_edges, [p2_span], reverse=False)
        seam = s.document.seams[0]
        s.set_seam_shrink(seam.id, 10)

        s.selected = p1.id
        clone_twin(s)

        seam = s.document.seams[0]
        init_seam_id = seam.id
        init_chain_a = [(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(0)]
        init_chain_b = [(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(1)]
        init_reverse = seam.reverse
        init_shrink = seam.shrink
        init_len0 = sum(s.document.edge_length(e) for e in seam.side(0))
        init_len1 = sum(s.document.edge_length(e) for e in seam.side(1))
        init_ease = init_len0 / init_len1

        p2_verts_init = [(v.x, v.y) for v in s.document.find(p2.id).vertices]
        p3_verts_init = [(v.x, v.y) for v in s.document.find(p3.id).vertices]

        s.select_piece(p1.id)
        self.assertTrue(s.move_selection(0.05, 0.02, confirm=True))

        p2_verts = [(v.x, v.y) for v in s.document.find(p2.id).vertices]
        p3_verts = [(v.x, v.y) for v in s.document.find(p3.id).vertices]
        self.assertEqual(p2_verts, p2_verts_init)
        self.assertEqual(p3_verts, p3_verts_init)

        seam = s.document.seams[0]
        self.assertEqual(seam.id, init_seam_id)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(0)], init_chain_a)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(1)], init_chain_b)
        self.assertEqual(seam.reverse, init_reverse)
        self.assertEqual(seam.shrink, init_shrink)
        len0 = sum(s.document.edge_length(e) for e in seam.side(0))
        len1 = sum(s.document.edge_length(e) for e in seam.side(1))
        self.assertAlmostEqual(len0, init_len0, delta=1e-6)
        self.assertAlmostEqual(len1, init_len1, delta=1e-6)
        self.assertAlmostEqual(len0 / len1, init_ease, delta=1e-6)

        self.assertTrue(s.rotate(30.0, pivot=(0.2, 0.2), confirm=True))
        p2_verts = [(v.x, v.y) for v in s.document.find(p2.id).vertices]
        p3_verts = [(v.x, v.y) for v in s.document.find(p3.id).vertices]
        self.assertEqual(p2_verts, p2_verts_init)
        self.assertEqual(p3_verts, p3_verts_init)
        seam = s.document.seams[0]
        self.assertEqual(seam.id, init_seam_id)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(0)], init_chain_a)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(1)], init_chain_b)
        self.assertEqual(seam.reverse, init_reverse)
        self.assertEqual(seam.shrink, init_shrink)
        len0 = sum(s.document.edge_length(e) for e in seam.side(0))
        len1 = sum(s.document.edge_length(e) for e in seam.side(1))
        self.assertAlmostEqual(len0, init_len0, delta=1e-6)
        self.assertAlmostEqual(len1, init_len1, delta=1e-6)
        self.assertAlmostEqual(len0 / len1, init_ease, delta=1e-6)

        toggle_link(s)

        s.select_piece(p1.id)
        s.select_piece(p2.id, toggle=True)
        self.assertTrue(s.move_selection(0.03, -0.01, confirm=True))
        p3_verts = [(v.x, v.y) for v in s.document.find(p3.id).vertices]
        self.assertEqual(p3_verts, p3_verts_init)
        seam = s.document.seams[0]
        self.assertEqual(seam.id, init_seam_id)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(0)], init_chain_a)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(1)], init_chain_b)
        self.assertEqual(seam.reverse, init_reverse)
        self.assertEqual(seam.shrink, init_shrink)
        len0 = sum(s.document.edge_length(e) for e in seam.side(0))
        len1 = sum(s.document.edge_length(e) for e in seam.side(1))
        self.assertAlmostEqual(len0, init_len0, delta=1e-6)
        self.assertAlmostEqual(len1, init_len1, delta=1e-6)
        self.assertAlmostEqual(len0 / len1, init_ease, delta=1e-6)

        self.assertTrue(s.rotate(-20.0, pivot=(0.5, 0.2), confirm=True))
        p3_verts = [(v.x, v.y) for v in s.document.find(p3.id).vertices]
        self.assertEqual(p3_verts, p3_verts_init)
        seam = s.document.seams[0]
        self.assertEqual(seam.id, init_seam_id)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(0)], init_chain_a)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(1)], init_chain_b)
        self.assertEqual(seam.reverse, init_reverse)
        self.assertEqual(seam.shrink, init_shrink)
        len0 = sum(s.document.edge_length(e) for e in seam.side(0))
        len1 = sum(s.document.edge_length(e) for e in seam.side(1))
        self.assertAlmostEqual(len0, init_len0, delta=1e-6)
        self.assertAlmostEqual(len1, init_len1, delta=1e-6)
        self.assertAlmostEqual(len0 / len1, init_ease, delta=1e-6)

        cand_doc, pre = s.build_transform_candidate('SCALE', 1.1, pivot=(0.5, 0.2))
        self.assertEqual(pre['status'], 'OK')
        self.assertTrue(s.scale(1.1, pivot=(0.5, 0.2), confirm=True))
        p3_verts = [(v.x, v.y) for v in s.document.find(p3.id).vertices]
        self.assertEqual(p3_verts, p3_verts_init)
        seam = s.document.seams[0]
        self.assertEqual(seam.id, init_seam_id)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(0)], init_chain_a)
        self.assertEqual([(e.pattern, e.path, e.start, e.end, e.t0, e.t1) for e in seam.side(1)], init_chain_b)
        self.assertEqual(seam.reverse, init_reverse)
        self.assertEqual(seam.shrink, init_shrink)
        len0 = sum(s.document.edge_length(e) for e in seam.side(0))
        len1 = sum(s.document.edge_length(e) for e in seam.side(1))
        self.assertAlmostEqual(len0, 1.1 * init_len0, delta=1e-5)
        self.assertAlmostEqual(len1, 1.1 * init_len1, delta=1e-5)
        self.assertAlmostEqual(len0 / len1, init_ease, delta=1e-5)

    def test_section9_check12_chain_breakpoint_shift_warns(self):
        s = Session()
        s.add([(0.0, 0.0), (0.2, 0.0), (0.5, 0.0), (0.5, 0.4), (0.0, 0.4)])
        p1 = s.document.patterns[0]
        s.add([(0.7, 0.0), (1.2, 0.0), (1.2, 0.4), (0.7, 0.4)])
        p2 = s.document.patterns[1]
        e1a = s.document.edge(p1.id, 0)
        e1b = s.document.edge(p1.id, 1)
        e2 = s.document.edge(p2.id, 0)
        s.sew_chains([e1a, e1b], [e2], reverse=False)
        s.select_point(p1.id, 'OUTER', 1)
        cand, pre = s.build_transform_candidate('MOVE', (0.15, 0.0))
        self.assertIsInstance(pre, dict)
        self.assertEqual(pre['status'], 'WARN')

    def test_section9_check12_invalid_references_prune_and_near_zero_block(self):
        s = Session()
        s.add([(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)])
        s.add([(0.3, 0.0), (0.5, 0.0), (0.5, 0.3), (0.3, 0.3)])
        p1, p2 = s.document.patterns
        s.sew(s.document.edge(p1.id, 1), s.document.edge(p2.id, 3))
        s.select_point(p1.id, 'OUTER', 2)
        doc_before = s.document.dumps()
        u_before = len(s.undo_stack)
        sel_patterns_before = set(s.selected_patterns)
        sel_points_before = set(s.selected_points)
        cand, pre = s.build_transform_candidate('MOVE', (-0.3, -0.2))
        self.assertEqual(pre['status'], 'BLOCK')
        self.assertNotIn('can_proceed', pre)
        with self.assertRaises(ValueError):
            s.move_selection(-0.3, -0.2, confirm=True)
        self.assertEqual(s.document.dumps(), doc_before)
        self.assertEqual(len(s.undo_stack), u_before)
        self.assertEqual(s.selected_patterns, sel_patterns_before)
        self.assertEqual(s.selected_points, sel_points_before)

        cand_doc_prune = Document.loads(doc_before)
        cand_doc_prune.seams.clear()
        pre_prune = s.preflight_transform(cand_doc_prune, set(), {})
        self.assertEqual(pre_prune['status'], 'BLOCK')
        self.assertNotIn('can_proceed', pre_prune)
        self.assertEqual(s.document.dumps(), doc_before)
        self.assertEqual(len(s.undo_stack), u_before)
        self.assertEqual(s.selected_patterns, sel_patterns_before)
        self.assertEqual(s.selected_points, sel_points_before)

        cand_doc_inv = Document.loads(doc_before)
        cand_doc_inv.seams[0].a = EdgeRef(p1.id, 'missing', 'missing')
        pre_inv = s.preflight_transform(cand_doc_inv, set(), {})
        self.assertEqual(pre_inv['status'], 'BLOCK')
        self.assertNotIn('can_proceed', pre_inv)
        self.assertEqual(s.document.dumps(), doc_before)
        self.assertEqual(len(s.undo_stack), u_before)
        self.assertEqual(s.selected_patterns, sel_patterns_before)
        self.assertEqual(s.selected_points, sel_points_before)

        s_tiny = Session()
        s_tiny.add([(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)])
        s_tiny.add([(0.3, 0.0), (0.5, 0.0), (0.5, 0.3), (0.3, 0.3)])
        pt1, pt2 = s_tiny.document.patterns
        e1 = s_tiny.document.edge(pt1.id, 1)
        e2 = s_tiny.document.edge(pt2.id, 3)
        tiny_span = EdgeRef(e1.pattern, e1.start, e1.end, 0.1, 0.10001, e1.path)
        s_tiny.sew(tiny_span, e2)
        s_tiny.select_piece(pt1.id)
        doc_tiny_before = s_tiny.document.dumps()
        u_tiny_before = len(s_tiny.undo_stack)
        sel_tiny_patterns = set(s_tiny.selected_patterns)
        sel_tiny_points = set(s_tiny.selected_points)
        cand_tiny, pre_tiny = s_tiny.build_transform_candidate('MOVE', (0.01, 0.01))
        self.assertEqual(pre_tiny['status'], 'BLOCK')
        self.assertIn('near zero', pre_tiny['reason'].lower())
        self.assertNotIn('can_proceed', pre_tiny)
        with self.assertRaises(ValueError):
            s_tiny.move_selection(0.01, 0.01, confirm=True)
        self.assertEqual(s_tiny.document.dumps(), doc_tiny_before)
        self.assertEqual(len(s_tiny.undo_stack), u_tiny_before)
        self.assertEqual(s_tiny.selected_patterns, sel_tiny_patterns)
        self.assertEqual(s_tiny.selected_points, sel_tiny_points)

        s_chain = Session()
        s_chain.add([(0.0, 0.0), (0.2, 0.0), (0.5, 0.0), (0.5, 0.4), (0.0, 0.4)])
        pc1 = s_chain.document.patterns[0]
        s_chain.add([(0.7, 0.0), (1.2, 0.0), (1.2, 0.4), (0.7, 0.4)])
        pc2 = s_chain.document.patterns[1]
        ec1a = s_chain.document.edge(pc1.id, 0)
        ec1b = s_chain.document.edge(pc1.id, 1)
        ec1b_tiny = EdgeRef(ec1b.pattern, ec1b.start, ec1b.end, 0.0, 1e-6, ec1b.path)
        ec2 = s_chain.document.edge(pc2.id, 0)
        s_chain.sew_chains([ec1a, ec1b_tiny], [ec2], reverse=False)
        s_chain.select_piece(pc1.id)
        doc_chain_before = s_chain.document.dumps()
        u_chain_before = len(s_chain.undo_stack)
        sel_chain_patterns = set(s_chain.selected_patterns)
        sel_chain_points = set(s_chain.selected_points)
        cand_chain_tiny, pre_chain_tiny = s_chain.build_transform_candidate('MOVE', (0.02, 0.01))
        self.assertEqual(pre_chain_tiny['status'], 'BLOCK')
        self.assertIn('near zero', pre_chain_tiny['reason'].lower())
        self.assertNotIn('can_proceed', pre_chain_tiny)
        with self.assertRaises(ValueError):
            s_chain.move_selection(0.02, 0.01, confirm=True)
        self.assertEqual(s_chain.document.dumps(), doc_chain_before)
        self.assertEqual(len(s_chain.undo_stack), u_chain_before)
        self.assertEqual(s_chain.selected_patterns, sel_chain_patterns)
        self.assertEqual(s_chain.selected_points, sel_chain_points)

        s_order = Session()
        s_order.add([(0.0, 0.0), (0.2, 0.0), (0.5, 0.0), (0.5, 0.4), (0.0, 0.4)])
        po1 = s_order.document.patterns[0]
        s_order.add([(0.7, 0.0), (1.2, 0.0), (1.2, 0.4), (0.7, 0.4)])
        po2 = s_order.document.patterns[1]
        eo1a = s_order.document.edge(po1.id, 0)
        eo1b = s_order.document.edge(po1.id, 1)
        eo2 = s_order.document.edge(po2.id, 0)
        s_order.sew_chains([eo1a, eo1b], [eo2], reverse=False)
        s_order.select_piece(po1.id)
        doc_order_before = s_order.document.dumps()
        u_order_before = len(s_order.undo_stack)
        sel_order_patterns = set(s_order.selected_patterns)
        sel_order_points = set(s_order.selected_points)

        cand_doc_reorder = Document.loads(doc_order_before)
        cand_doc_reorder.seams[0].chain_a = (eo1b, eo1a)
        cand_doc_reorder.seams[0].a = eo1b
        pre_reorder = s_order.preflight_transform(cand_doc_reorder, {po1.id}, {})
        self.assertEqual(pre_reorder['status'], 'BLOCK')
        self.assertIn('reorder', pre_reorder['reason'].lower())
        self.assertNotIn('can_proceed', pre_reorder)
        self.assertEqual(s_order.document.dumps(), doc_order_before)
        self.assertEqual(len(s_order.undo_stack), u_order_before)
        self.assertEqual(s_order.selected_patterns, sel_order_patterns)
        self.assertEqual(s_order.selected_points, sel_order_points)

        cand_doc_span = Document.loads(doc_order_before)
        new_eo2 = EdgeRef(eo2.pattern, eo2.start, eo2.end, 0.1, 0.9, eo2.path)
        cand_doc_span.seams[0].chain_b = (new_eo2,)
        cand_doc_span.seams[0].b = new_eo2
        pre_span = s_order.preflight_transform(cand_doc_span, {po1.id}, {})
        self.assertEqual(pre_span['status'], 'BLOCK')
        self.assertNotIn('can_proceed', pre_span)
        self.assertEqual(s_order.document.dumps(), doc_order_before)
        self.assertEqual(len(s_order.undo_stack), u_order_before)
        self.assertEqual(s_order.selected_patterns, sel_order_patterns)
        self.assertEqual(s_order.selected_points, sel_order_points)


class DummyScene(SimpleNamespace):
    def __setitem__(self,key,value):
        setattr(self,key,value)

    def get(self, key, default=None):
        return getattr(self, key, default)


class DummyEditor(DesignTools):
    def __init__(self, session, scene):
        self.session = session
        self._scene = scene
        self.initialize_design()
        self.pending_edge = None
        self.seam_selected = None
        self.message = ''

    def persist(self):
        pass

    def design_hit_edge(self):
        return None

    def sync_selection(self):
        pass

if __name__=='__main__':
    unittest.main()
