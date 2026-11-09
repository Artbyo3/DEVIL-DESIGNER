import unittest
import math
from dataclasses import replace
from devil_designer.core import Document, Session, Vertex, curves

SQUARE_A = [(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)]
SQUARE_B = [(0.3, 0.0), (0.5, 0.0), (0.5, 0.3), (0.3, 0.3)]

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.add(SQUARE_A)

    def test_box_select_picks_points(self):
        p = self.s.document.patterns[0]
        self.s.acquisition_target = 'POINTS'
        kind, count = self.s.box_select(-0.05, -0.05, 0.05, 0.05)
        self.assertEqual(kind, 'POINTS')
        self.assertEqual(count, 1)
        self.assertIn((p.id, 'OUTER', 0), self.s.selected_points)

    def test_box_select_picks_pieces_when_no_points(self):
        p = self.s.document.patterns[0]
        self.s.acquisition_target = 'PIECES'
        kind, count = self.s.box_select(0.05, 0.05, 0.15, 0.15)
        self.assertEqual(count, 0)
        kind, count = self.s.box_select(0.15, 0.05, 0.05, 0.15)
        self.assertEqual(kind, 'PIECES')
        self.assertEqual(count, 1)
        self.assertIn(p.id, self.s.selected_patterns)

    def test_box_select_shift_retains_existing(self):
        p = self.s.document.patterns[0]
        self.s.acquisition_target = 'POINTS'
        self.s.box_select(-0.05, -0.05, 0.05, 0.05)
        self.assertEqual(len(self.s.selected_points), 1)
        self.s.box_select(0.15, -0.05, 0.25, 0.05, shift=True)
        self.assertEqual(len(self.s.selected_points), 2)
        self.assertIn((p.id, 'OUTER', 0), self.s.selected_points)
        self.assertIn((p.id, 'OUTER', 1), self.s.selected_points)

    def test_shift_toggles_pieces_and_points(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.select_piece(p1.id)
        self.assertEqual(self.s.selected_patterns, {p1.id})
        self.s.select_piece(p2.id, toggle=True)
        self.assertEqual(self.s.selected_patterns, {p1.id, p2.id})
        self.s.select_piece(p1.id, toggle=True)
        self.assertEqual(self.s.selected_patterns, {p2.id})
        self.s.clear_selection()
        self.assertEqual(len(self.s.selected_patterns), 0)

        self.s.select_point(p1.id, 'OUTER', 0)
        self.assertEqual(self.s.selected_points, {(p1.id, 'OUTER', 0)})
        self.s.select_point(p1.id, 'OUTER', 1, toggle=True)
        self.assertEqual(len(self.s.selected_points), 2)
        self.s.select_point(p1.id, 'OUTER', 0, toggle=True)
        self.assertEqual(self.s.selected_points, {(p1.id, 'OUTER', 1)})

    def test_select_all_and_clear(self):
        self.s.add(SQUARE_B)
        self.s.select_all()
        self.assertEqual(len(self.s.selected_patterns), 2)
        self.assertTrue(self.s.is_multi_selected())
        self.s.clear_selection()
        self.assertFalse(self.s.has_selection())
        self.assertEqual(self.s.selection_counts(), (0, 0))

    def test_multi_piece_and_mixed_moves_keep_sewing_intact(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        e1 = self.s.document.edge(p1.id, 1)
        e2 = self.s.document.edge(p2.id, 3)
        self.s.sew(e1, e2)
        self.assertEqual(len(self.s.document.seams), 1)

        self.s.select_all()
        self.s.move_selection(0.05, 0.02)
        self.assertEqual(len(self.s.document.seams), 1)
        self.s.document.validate_seams()
        self.assertAlmostEqual(self.s.document.patterns[0].vertices[0].x, 0.05)
        self.assertAlmostEqual(self.s.document.patterns[0].vertices[0].y, 0.02)
        self.assertAlmostEqual(self.s.document.patterns[1].vertices[0].x, 0.35)
        self.assertAlmostEqual(self.s.document.patterns[1].vertices[0].y, 0.02)

        self.s.clear_selection()
        self.s.select_piece(p1.id)
        self.s.select_point(p2.id, 'OUTER', 0, toggle=True)
        source = self.s.document.dumps()
        self.assertEqual(self.s.move_selection(0.01, 0.01)['status'], 'WARN')
        self.assertEqual(self.s.document.dumps(), source)
        self.assertTrue(self.s.move_selection(0.01, 0.01, confirm=True))
        self.s.document.validate_seams()
        self.assertAlmostEqual(self.s.document.patterns[1].vertices[0].x, 0.36)
        self.assertAlmostEqual(self.s.document.patterns[1].vertices[1].x, 0.55)

    def test_rejected_move_restores_everything_and_no_undo_entry(self):
        p = self.s.document.patterns[0]
        orig_points = list(p.points)
        count_undo = len(self.s.undo_stack)
        self.s.clear_selection()
        self.s.select_point(p.id, 'OUTER', 0)
        with self.assertRaises(ValueError):
            self.s.move_selection(0.3, 0.15)
        self.assertEqual(self.s.document.patterns[0].points, orig_points)
        self.assertEqual(len(self.s.undo_stack), count_undo)

    def test_handle_offsets_survive_group_moves(self):
        s = Session()
        s.add_ellipse((0.0, 0.0), (0.4, 0.4))
        p = s.document.patterns[0]
        orig_handles = [(v.incoming, v.outgoing) for v in p.vertices]
        s.select_all()
        s.move_selection(0.10, -0.05)
        for v, (inc, out) in zip(s.document.patterns[0].vertices, orig_handles):
            self.assertEqual(v.incoming, inc)
            self.assertEqual(v.outgoing, out)

    def test_duplicate_several_pieces_preserves_seams(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        e1 = self.s.document.edge(p1.id, 1)
        e2 = self.s.document.edge(p2.id, 3)
        self.s.sew(e1, e2)
        self.assertEqual(len(self.s.document.seams), 1)

        self.s.select_all()
        self.s.duplicate()
        self.assertEqual(len(self.s.document.patterns), 4)
        self.assertEqual(len(self.s.document.seams), 2)
        self.s.document.validate_seams()
        d1, d2 = self.s.document.patterns[2], self.s.document.patterns[3]
        dup_seam = self.s.document.seams[1]
        dup_pids = {e.pattern for side in (dup_seam.side(0), dup_seam.side(1)) for e in side}
        self.assertEqual(dup_pids, {d1.id, d2.id})

    def test_older_designs_load_unchanged_and_selection_not_saved(self):
        raw = self.s.document.dumps()
        self.assertNotIn('selected', raw)
        self.assertNotIn('selected_patterns', raw)
        self.assertNotIn('selected_points', raw)
        loaded = Document.loads(raw)
        self.assertEqual(len(loaded.patterns), 1)
        self.assertEqual(loaded.patterns[0].points, SQUARE_A)

    def test_undo_redo_restores_selection(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.select_piece(p1.id)
        self.s.move_selection(0.02, 0.0)
        self.s.select_piece(p2.id)
        self.s.move_selection(0.0, 0.02)
        self.s.clear_selection()
        self.assertEqual(len(self.s.selected_patterns), 0)

        self.s.history()
        self.assertEqual(self.s.selected_patterns, {p2.id})

        self.s.history()
        self.assertEqual(self.s.selected_patterns, {p1.id})

        self.s.history(redo=True)
        self.assertEqual(self.s.selected_patterns, {p2.id})

    def test_batch_delete(self):
        self.s.add(SQUARE_B)
        self.s.select_all()
        self.s.delete()
        self.assertEqual(len(self.s.document.patterns), 0)

    def test_mixed_rotation_37_5_degrees(self):
        import math
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.select_piece(p1.id)
        self.s.select_point(p1.id, 'OUTER', 0, toggle=True)
        self.s.select_point(p2.id, 'OUTER', 2, toggle=True)
        e_p2 = self.s.document.edge(p2.id, 0)
        self.s.select_edge(e_p2, toggle=True)
        pivot = (0.3, 0.0)
        self.s.set_pivot(pivot[0], pivot[1])
        orig_nodes, _ = self.s.resolve_selection()
        rad = math.radians(37.5)
        cos_t, sin_t = math.cos(rad), math.sin(rad)
        expected = {}
        for k, v in orig_nodes.items():
            rx, ry = v.x - pivot[0], v.y - pivot[1]
            expected[k] = (pivot[0] + cos_t * rx - sin_t * ry, pivot[1] + sin_t * rx + cos_t * ry)
        self.s.rotate(37.5, pivot=pivot)
        cand_nodes, _ = self.s.resolve_selection()
        for k, (ex, ey) in expected.items():
            self.assertAlmostEqual(cand_nodes[k].x, ex, delta=1e-8)
            self.assertAlmostEqual(cand_nodes[k].y, ey, delta=1e-8)
        self.assertEqual(self.s.placed_pivot, pivot)

    def test_scale_1_1_and_110_percent_parity(self):
        import math
        self.s.add(SQUARE_B)
        p1 = self.s.document.patterns[0]
        self.s.select_piece(p1.id)
        pivot = self.s.get_pivot()
        doc_orig = self.s.document.dumps()
        self.s.scale(1.1, pivot=pivot)
        scaled_doc_float = self.s.document.dumps()
        self.s.history()
        self.assertEqual(self.s.document.dumps(), doc_orig)
        factor = 110.0 / 100.0
        self.s.scale(factor, pivot=pivot)
        scaled_doc_pct = self.s.document.dumps()
        self.assertEqual(scaled_doc_float, scaled_doc_pct)
        for v_orig, v_scaled in zip(Document.loads(doc_orig).patterns[0].vertices, self.s.document.patterns[0].vertices):
            d_orig = math.hypot(v_orig.x - pivot[0], v_orig.y - pivot[1])
            d_scaled = math.hypot(v_scaled.x - pivot[0], v_scaled.y - pivot[1])
            self.assertAlmostEqual(d_scaled, d_orig * 1.1, delta=1e-8)
        with self.assertRaises(ValueError):
            self.s.scale(0.0)
        with self.assertRaises(ValueError):
            self.s.scale(-1.0)
        with self.assertRaises(ValueError):
            self.s.scale(float('nan'))
        with self.assertRaises(ValueError):
            self.s.scale(float('inf'))

    def test_pivot_placement_and_snap(self):
        p1 = self.s.document.patterns[0]
        self.s.select_piece(p1.id)
        center = self.s.get_pivot()
        self.assertAlmostEqual(center[0], 0.1, delta=1e-5)
        self.assertAlmostEqual(center[1], 0.15, delta=1e-5)
        pt, lbl = self.s.find_pivot_candidate((0.005, 0.005), 0.02)
        self.assertEqual(pt, (0.0, 0.0))
        self.assertIn('Vertex', lbl)
        pt_mid, lbl_mid = self.s.find_pivot_candidate((0.102, 0.001), 0.02)
        self.assertEqual(pt_mid, (0.1, 0.0))
        self.assertIn('Midpoint', lbl_mid)
        pt_ctr, lbl_ctr = self.s.find_pivot_candidate((0.101, 0.149), 0.02)
        self.assertEqual(pt_ctr, center)
        self.assertIn('Selection center', lbl_ctr)
        self.s.set_pivot(pt[0], pt[1])
        self.assertEqual(self.s.placed_pivot, (0.0, 0.0))
        self.s.move_selection(0.05, 0.02)
        self.assertEqual(self.s.placed_pivot, (0.05, 0.02))
        self.s.select_point(p1.id, 'OUTER', 0)
        self.assertIsNone(self.s.placed_pivot)

    def test_marquee_enclose_vs_crossing(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.acquisition_target = 'PIECES'
        kind, count = self.s.box_select(-0.05, -0.05, 0.25, 0.35)
        self.assertEqual(count, 1)
        self.assertEqual(self.s.selected_patterns, {p1.id})
        kind, count = self.s.box_select(0.15, -0.05, 0.05, 0.35)
        self.assertEqual(count, 1)
        self.assertEqual(self.s.selected_patterns, {p1.id})
        kind, count = self.s.box_select(0.05, 0.05, 0.15, 0.15)
        self.assertEqual(count, 0)
        self.assertEqual(len(self.s.selected_patterns), 0)
        kind, count = self.s.box_select(0.15, 0.15, 0.05, 0.05)
        self.assertEqual(count, 1)
        self.assertEqual(self.s.selected_patterns, {p1.id})

    def test_acquisition_target_preserves_mixed_members(self):
        p1 = self.s.document.patterns[0]
        self.s.select_piece(p1.id)
        self.s.select_point(p1.id, 'OUTER', 0, toggle=True)
        self.s.acquisition_target = 'POINTS'
        self.assertIn(p1.id, self.s.selected_patterns)
        self.assertIn((p1.id, 'OUTER', 0), self.s.selected_points)
        self.s.acquisition_target = 'EDGES'
        self.assertIn(p1.id, self.s.selected_patterns)
        self.assertIn((p1.id, 'OUTER', 0), self.s.selected_points)

    def test_lasso_selection_and_even_odd(self):
        p1 = self.s.document.patterns[0]
        self.s.acquisition_target = 'POINTS'
        poly = [(-0.05, -0.05), (0.25, -0.05), (0.25, 0.35), (-0.05, 0.35)]
        kind, count = self.s.lasso_select(poly)
        self.assertEqual(count, 4)
        self.assertEqual(len(self.s.selected_points), 4)
        poly_self_intersect = [(0.0, 0.0), (0.2, 0.2), (0.0, 0.2), (0.2, 0.0)]
        kind, count = self.s.lasso_select(poly_self_intersect)
        self.assertEqual(kind, 'POINTS')

    def test_toggle_final_entity_leaves_empty_active_state(self):
        p1 = self.s.document.patterns[0]
        self.s.select_point(p1.id, 'OUTER', 0)
        self.assertEqual(self.s.active_entity, ('POINT', (p1.id, 'OUTER', 0)))
        self.s.select_point(p1.id, 'OUTER', 0, toggle=True)
        self.assertIsNone(self.s.active_entity)
        self.assertFalse(self.s.has_selection())
        self.assertIsNone(self.s.selected)
        self.assertIsNone(self.s.corner)
        e = self.s.document.edge(p1.id, 0)
        self.s.select_edge(e)
        self.assertEqual(self.s.active_entity, ('EDGE', e))
        self.s.select_edge(e, toggle=True)
        self.assertIsNone(self.s.active_entity)
        self.assertFalse(self.s.has_selection())
        self.assertFalse(self.s.move_selection(0.01, 0.01))

    def test_invert_twice_restores_exact_target_ids(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.acquisition_target = 'PIECES'
        self.s.select_piece(p1.id)
        orig = set(self.s.selected_patterns)
        self.s.invert_selection()
        self.assertEqual(self.s.selected_patterns, {p2.id})
        self.s.invert_selection()
        self.assertEqual(self.s.selected_patterns, orig)
        self.s.acquisition_target = 'POINTS'
        self.s.clear_selection()
        self.s.select_point(p1.id, 'OUTER', 0)
        pts_orig = set(self.s.selected_points)
        self.s.invert_selection()
        self.assertEqual(len(self.s.selected_points), 7)
        self.s.invert_selection()
        self.assertEqual(self.s.selected_points, pts_orig)

    def test_edge_endpoint_transform_affects_shared_neighbors(self):
        p1 = self.s.document.patterns[0]
        e = self.s.document.edge(p1.id, 0)
        self.s.select_edge(e)
        self.s.move_selection(0.02, 0.01)
        v0 = p1.vertices[0]
        v1 = p1.vertices[1]
        self.assertAlmostEqual(v0.x, 0.02)
        self.assertAlmostEqual(v0.y, 0.01)
        self.assertAlmostEqual(v1.x, 0.22)
        self.assertAlmostEqual(v1.y, 0.01)
        self.assertAlmostEqual(p1.vertices[2].x, 0.2)
        self.assertAlmostEqual(p1.vertices[2].y, 0.3)

    def test_connected_sewn_transitive_follow(self):
        self.s.add(SQUARE_B)
        SQUARE_C = [(0.6, 0.0), (0.8, 0.0), (0.8, 0.3), (0.6, 0.3)]
        self.s.add(SQUARE_C)
        p1, p2, p3 = self.s.document.patterns[0], self.s.document.patterns[1], self.s.document.patterns[2]
        self.s.sew(self.s.document.edge(p1.id, 1), self.s.document.edge(p2.id, 3))
        self.s.sew(self.s.document.edge(p2.id, 1), self.s.document.edge(p3.id, 3))
        self.s.select_piece(p1.id)
        self.s.select_connected(mode='SEWN')
        self.assertEqual(self.s.selected_patterns, {p1.id, p2.id, p3.id})

    def test_sewn_closure_then_scale_transforms_each_node_once(self):
        self.s.add(SQUARE_B)
        SQUARE_C = [(0.6, 0.0), (0.8, 0.0), (0.8, 0.3), (0.6, 0.3)]
        self.s.add(SQUARE_C)
        p1, p2, p3 = self.s.document.patterns[0], self.s.document.patterns[1], self.s.document.patterns[2]
        self.s.sew(self.s.document.edge(p1.id, 1), self.s.document.edge(p2.id, 3))
        self.s.sew(self.s.document.edge(p2.id, 1), self.s.document.edge(p3.id, 3))
        self.s.select_piece(p1.id)
        pivot = self.s.get_pivot()
        u_count = len(self.s.undo_stack)
        self.s.select_connected(mode='SEWN')
        self.assertEqual(self.s.selected_patterns, {p1.id, p2.id, p3.id})
        self.assertTrue(self.s.scale(1.1, pivot=pivot))
        self.assertEqual(len(self.s.undo_stack), u_count + 1)
        self.assertAlmostEqual(p3.vertices[0].x, pivot[0] + 1.1 * (0.6 - pivot[0]))

    def test_flip_horizontal_piece_and_multi_piece(self):
        p = self.s.document.patterns[0]
        self.s.select_piece(p.id)
        self.s.flip_horizontal()
        self.assertAlmostEqual(p.vertices[0].x, 0.2)
        self.assertAlmostEqual(p.vertices[1].x, 0.0)

        self.s.add(SQUARE_B)
        self.s.select_all()
        self.s.flip_horizontal()
        self.s.document.validate()

    def test_flip_vertical_piece_and_multi_piece(self):
        p = self.s.document.patterns[0]
        self.s.select_piece(p.id)
        self.s.flip_vertical()
        self.assertAlmostEqual(p.vertices[0].y, 0.3)
        self.assertAlmostEqual(p.vertices[2].y, 0.0)

    def test_flip_inverts_seam_reverse_when_one_side_flipped(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        e1 = self.s.document.edge(p1.id, 1)
        e2 = self.s.document.edge(p2.id, 3)
        self.s.sew(e1, e2)
        orig_reverse = self.s.document.seams[0].reverse

        self.s.select_piece(p1.id)
        self.s.flip_horizontal()
        self.assertEqual(self.s.document.seams[0].reverse, not orig_reverse)

        self.s.select_all()
        self.s.flip_horizontal()
        self.assertEqual(self.s.document.seams[0].reverse, not orig_reverse)

    def test_rotate_90_piece_and_handles(self):
        s = Session()
        s.add_ellipse((0.0, 0.0), (0.4, 0.4))
        p = s.document.patterns[0]
        s.select_piece(p.id)
        s.rotate(-90)
        s.document.validate()
        s.rotate(90)
        s.document.validate()

    def test_rotate_multi_piece(self):
        self.s.add(SQUARE_B)
        self.s.select_all()
        self.s.rotate(-90)
        self.s.document.validate()

    def test_undo_redo_flip_rotate(self):
        p = self.s.document.patterns[0]
        orig_x = p.vertices[0].x
        self.s.select_piece(p.id)
        self.s.flip_horizontal()
        self.assertNotEqual(self.s.document.patterns[0].vertices[0].x, orig_x)
        self.s.history()
        self.assertAlmostEqual(self.s.document.patterns[0].vertices[0].x, orig_x)
        self.s.history(redo=True)
        self.assertNotEqual(self.s.document.patterns[0].vertices[0].x, orig_x)

        self.s.rotate(-90)
        self.s.history()
        self.s.document.validate()

    def test_nudge_coalesce_and_undo_cap(self):
        p = self.s.document.patterns[0]
        self.s.select_piece(p.id)
        start_x = p.vertices[0].x
        base_count = len(self.s.undo_stack)
        self.s.move_selection(0.01, 0.0, coalesce=False)
        self.assertEqual(len(self.s.undo_stack), base_count + 1)
        for _ in range(4):
            self.s.move_selection(0.01, 0.0, coalesce=True)
        self.assertEqual(len(self.s.undo_stack), base_count + 1)
        self.assertAlmostEqual(self.s.document.patterns[0].vertices[0].x, start_x + 0.05, delta=1e-8)
        self.s.history()
        self.assertEqual(len(self.s.undo_stack), base_count)
        self.assertAlmostEqual(self.s.document.patterns[0].vertices[0].x, start_x, delta=1e-8)
        self.s.history(redo=True)
        self.assertAlmostEqual(self.s.document.patterns[0].vertices[0].x, start_x + 0.05, delta=1e-8)
        for i in range(105):
            self.s.move_selection(0.001, 0.0, coalesce=False)
        self.assertEqual(len(self.s.undo_stack), 100)
        self.assertEqual(len(self.s._undo_selections), 100)

    def test_pivot_restore_and_unselected_target(self):
        self.s.add(SQUARE_B)
        self.s.add([(0.8, 0.0), (1.0, 0.0), (1.0, 0.3), (0.8, 0.3)])
        p1, p2, p3 = self.s.document.patterns[0], self.s.document.patterns[1], self.s.document.patterns[2]
        self.s.select_piece(p1.id)
        self.s.select_point(p2.id, 'OUTER', 0, toggle=True)
        cand_pt, cand_lbl = self.s.find_pivot_candidate((0.802, 0.001), tolerance=0.02)
        self.assertEqual(cand_pt, (0.8, 0.0))
        self.assertIn('Vertex', cand_lbl)
        self.s.set_pivot(0.8, 0.0)
        orig_pivot = self.s.placed_pivot
        sel_before = self.s.get_selection_state()
        self.s.move_selection(0.02, 0.01)
        self.assertEqual(self.s.placed_pivot, (0.82, 0.01))
        self.s.history()
        self.assertEqual(self.s.placed_pivot, orig_pivot)
        self.assertEqual(self.s.get_selection_state(), sel_before)

    def test_all_four_acquisition_targets_invert_twice_preserving_others(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.selected = p1.id
        internal = self.s.add_path([(0.05, 0.05), (0.15, 0.15)])
        self.s.clear_selection()
        self.s.selected_patterns = {p1.id}
        self.s.selected_points = {(p2.id, 'OUTER', 0)}
        e_p2 = self.s.document.edge(p2.id, 1)
        self.s.selected_edges = {e_p2}
        self.s.selected_paths = {(p1.id, internal.id)}
        orig_pats = set(self.s.selected_patterns)
        orig_pts = set(self.s.selected_points)
        orig_edges = set(self.s.selected_edges)
        orig_paths = set(self.s.selected_paths)
        for tgt in ('PIECES', 'POINTS', 'EDGES', 'PATHS'):
            self.s.acquisition_target = tgt
            self.s.invert_selection()
            if tgt != 'PIECES': self.assertEqual(self.s.selected_patterns, orig_pats)
            if tgt != 'POINTS': self.assertEqual(self.s.selected_points, orig_pts)
            if tgt != 'EDGES': self.assertEqual(self.s.selected_edges, orig_edges)
            if tgt != 'PATHS': self.assertEqual(self.s.selected_paths, orig_paths)
            self.s.invert_selection()
            self.assertEqual(self.s.selected_patterns, orig_pats)
            self.assertEqual(self.s.selected_points, orig_pts)
            self.assertEqual(self.s.selected_edges, orig_edges)
            self.assertEqual(self.s.selected_paths, orig_paths)

    def test_seeded_stored_path_connected_not_coincident(self):
        self.s.add([(0.2, 0.0), (0.4, 0.0), (0.4, 0.3), (0.2, 0.3)])
        pA, pB = self.s.document.patterns[0], self.s.document.patterns[1]
        self.s.clear_selection()
        self.s.select_point(pA.id, 'OUTER', 1)
        self.s.select_connected(mode='PATH')
        for idx in range(4):
            self.assertIn((pA.id, 'OUTER', idx), self.s.selected_points)
        for p, path, idx in self.s.selected_points:
            self.assertNotEqual(p, pB.id)

    def test_sewn_closure_not_coincidence(self):
        self.s.add([(0.2, 0.0), (0.4, 0.0), (0.4, 0.3), (0.2, 0.3)])
        self.s.add([(0.5, 0.0), (0.7, 0.0), (0.7, 0.3), (0.5, 0.3)])
        pA, pB, pC = self.s.document.patterns[0], self.s.document.patterns[1], self.s.document.patterns[2]
        self.s.sew(self.s.document.edge(pA.id, 0), self.s.document.edge(pC.id, 0))
        self.s.clear_selection()
        self.s.select_piece(pA.id)
        self.s.select_connected(mode='SEWN')
        self.assertEqual(self.s.selected_patterns, {pA.id, pC.id})
        self.assertNotIn(pB.id, self.s.selected_patterns)

    def test_marquee_curved_concave_crossing_enclose(self):
        s = Session()
        u_pts = [(0.0, 0.0), (0.3, 0.0), (0.3, 0.3), (0.2, 0.3), (0.2, 0.1), (0.1, 0.1), (0.1, 0.3), (0.0, 0.3)]
        s.add(u_pts)
        p_u = s.document.patterns[0]
        s.acquisition_target = 'PIECES'
        s.clear_selection()
        kind, cnt = s.box_select(0.05, 0.15, 0.25, 0.25)
        self.assertEqual(cnt, 0)
        self.assertNotIn(p_u.id, s.selected_patterns)
        kind, cnt = s.box_select(0.25, 0.25, 0.05, 0.15)
        self.assertEqual(cnt, 1)
        self.assertIn(p_u.id, s.selected_patterns)
        s.add_ellipse((0.4, 0.0), (0.8, 0.4))
        p_ell = s.document.patterns[1]
        s.clear_selection()
        kind, cnt = s.box_select(0.45, 0.05, 0.75, 0.35)
        self.assertEqual(cnt, 0)
        self.assertNotIn(p_ell.id, s.selected_patterns)
        kind, cnt = s.box_select(0.75, 0.35, 0.45, 0.05)
        self.assertEqual(cnt, 1)
        self.assertIn(p_ell.id, s.selected_patterns)

    def test_partial_auto_edge_transforms_warn_with_exact_deviation_or_convert(self):
        def auto_rectangle():
            s = Session()
            s.add([Vertex(x, y, point_type='AUTO') for x, y in [(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)]])
            p = s.document.patterns[0]
            for v in p.vertices:
                v.point_type = 'AUTO'
            p.outline()
            return s, p
        pivot = (0.05, 0.05)
        rad = math.radians(37.5)
        cos_t, sin_t = math.cos(rad), math.sin(rad)
        cases = [('MOVE', (0.02, 0.01), lambda pt: (pt[0] + 0.02, pt[1] + 0.01)),
                 ('ROTATE', 37.5, lambda pt: (pivot[0] + cos_t * (pt[0] - pivot[0]) - sin_t * (pt[1] - pivot[1]),
                                               pivot[1] + sin_t * (pt[0] - pivot[0]) + cos_t * (pt[1] - pivot[1]))),
                 ('SCALE', 1.2, lambda pt: (pivot[0] + 1.2 * (pt[0] - pivot[0]), pivot[1] + 1.2 * (pt[1] - pivot[1])))]
        def deviation(doc, edge, mapper, source_samples):
            doc.find(edge.pattern).outline()
            ctrl = doc.edge_curve(edge)
            return max(math.dist(curves.evaluate(ctrl, i / 100.0), mapper(pt)) for i, pt in enumerate(source_samples))
        for kind, param, mapper in cases:
            s, p = auto_rectangle()
            e0 = s.document.edge(p.id, 0)
            s.select_edge(e0)
            source = s.document.dumps()
            undo = len(s.undo_stack)
            source_ctrl = s.document.edge_curve(e0)
            source_samples = [curves.evaluate(source_ctrl, i / 100.0) for i in range(101)]
            cand, pre = s.build_transform_candidate(kind, param, pivot=pivot)
            self.assertEqual(s.document.dumps(), source)
            self.assertEqual(len(s.undo_stack), undo)
            self.assertEqual(pre['status'], 'WARN')
            self.assertFalse(pre.get('details'))
            self.assertEqual(pre['auto_point_count'], 2)
            rendered = deviation(cand, e0, mapper, source_samples)
            self.assertGreater(rendered, 1e-6)
            self.assertAlmostEqual(pre['curve_deviation_mm'], rendered * 1000, delta=1e-6)
            if kind == 'MOVE':
                self.assertAlmostEqual(pre['curve_deviation_mm'], 2.071184, places=5)
            exact = pre['exact_candidate']
            self.assertLess(deviation(exact, e0, mapper, source_samples), 1e-8)
            self.assertEqual([v.point_type for v in exact.find(p.id).vertices], ['SMOOTH', 'SMOOTH', 'AUTO', 'AUTO'])
            self.assertEqual([v.point_type for v in cand.find(p.id).vertices], ['AUTO'] * 4)
            moved = [mapper((v.x, v.y)) for v in p.vertices[:2]]
            for doc in (cand, exact):
                vertices = doc.find(p.id).vertices
                for (x, y), v in zip(moved, vertices[:2]):
                    self.assertAlmostEqual(v.x, x, delta=1e-12)
                    self.assertAlmostEqual(v.y, y, delta=1e-12)
                self.assertEqual((vertices[2].x, vertices[2].y), (0.2, 0.3))
                self.assertEqual((vertices[3].x, vertices[3].y), (0.0, 0.3))
            unconfirmed = {'MOVE': lambda: s.move_selection(*param), 'ROTATE': lambda: s.rotate(param, pivot=pivot),
                           'SCALE': lambda: s.scale(param, pivot=pivot)}[kind]()
            self.assertEqual(unconfirmed['status'], 'WARN')
            self.assertEqual(s.document.dumps(), source)
            self.assertEqual(len(s.undo_stack), undo)
            self.assertTrue(s.commit_candidate(exact))
            self.assertEqual(len(s.undo_stack), undo + 1)
            self.assertLess(deviation(s.document, e0, mapper, source_samples), 1e-8)
            s.history()
            self.assertEqual(s.document.dumps(), source)
        for kind, param, _ in cases:
            s, p = auto_rectangle()
            s.select_piece(p.id)
            cand, pre = s.build_transform_candidate(kind, param, pivot=pivot)
            self.assertEqual(pre['status'], 'OK')
            self.assertNotIn('curve_deviation_mm', pre)
        s, p = auto_rectangle()
        s.select_point(p.id, 'OUTER', 0)
        cand, pre = s.build_transform_candidate('MOVE', (0.02, 0.01))
        self.assertEqual(pre['status'], 'OK')
        s, p = auto_rectangle()
        s.select_edge(s.document.edge(p.id, 0))
        s.set_point_type('CORNER', [(p.id, 'OUTER', 0), (p.id, 'OUTER', 1)])
        s.select_edge(s.document.edge(p.id, 0))
        cand, pre = s.build_transform_candidate('ROTATE', 37.5, pivot=pivot)
        self.assertEqual(pre['status'], 'OK')

    def test_redo_restores_committed_selection_and_pivot_not_stale_state(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns
        self.s.select_piece(p1.id)
        self.s.set_pivot(0.05, 0.05)
        self.assertTrue(self.s.move_selection(0.01, 0.0))
        committed_document = self.s.document.dumps()
        committed = self.s.get_selection_state()
        self.assertEqual(committed['placed_pivot'], (0.06, 0.05))
        self.s.clear_selection()
        self.s.select_point(p2.id, 'OUTER', 1)
        self.s.set_pivot(0.4, 0.2)
        self.assertTrue(self.s.history())
        self.assertTrue(self.s.history(redo=True))
        self.assertEqual(self.s.document.dumps(), committed_document)
        self.assertEqual(self.s.get_selection_state(), committed)
        self.s.clear_selection()
        self.s.select_point(p2.id, 'OUTER', 1)
        self.s.commit(lambda: setattr(p2, 'name', 'Back'))
        stale = self.s.get_selection_state()
        self.assertTrue(self.s.history())
        self.assertTrue(self.s.history(redo=True))
        self.assertEqual(self.s.get_selection_state(), stale)

    def test_unconfirmed_rotate_keeps_seam_warning_pending(self):
        self.s.add(SQUARE_B)
        p1, p2 = self.s.document.patterns
        self.s.sew(self.s.document.edge(p1.id, 1), self.s.document.edge(p2.id, 3))
        self.s.select_point(p2.id, 'OUTER', 0)
        self.s.set_pivot(0.0, 0.0)
        source = self.s.document.dumps()
        undo = len(self.s.undo_stack)
        result = self.s.rotate(-90)
        self.assertEqual(result['status'], 'WARN')
        self.assertEqual(self.s.document.dumps(), source)
        self.assertEqual(len(self.s.undo_stack), undo)

    def test_preflight_validates_individual_seam_span_nearzero(self):
        s = Session()
        s.add([(0,0),(.2,0),(.2,.15),(.2,.3),(0,.3)])
        s.add([(0.4,0),(.6,0),(.6,.3),(.4,.3)])
        p1, p2 = s.document.patterns
        e1a = s.document.edge(p1.id, 1)
        e1b = s.document.edge(p1.id, 2)
        e2 = s.document.edge(p2.id, 3)
        e1a_sub = replace(e1a, t0=0.0, t1=0.0002)
        s.sew_chains([e1a_sub, e1b], [e2])
        s.select_point(p1.id, 'OUTER', 2)
        cand, pre = s.build_transform_candidate('MOVE', (0, -0.11))
        self.assertEqual(pre['status'], 'BLOCK')
        self.assertEqual(pre['reason'], 'Seam span length is near zero.')

    def test_preflight_rejects_candidate_changes_to_chain_identities_and_fractions(self):
        s = Session()
        s.add([(0,0),(.2,0),(.2,.15),(.2,.3),(0,.3)])
        s.add([(0.4,0),(.6,0),(.6,.3),(.4,.3)])
        p1, p2 = s.document.patterns
        e1a = s.document.edge(p1.id, 1)
        e1b = s.document.edge(p1.id, 2)
        e2 = s.document.edge(p2.id, 3)
        s.sew_chains([e1a, e1b], [e2])
        cand = Document.loads(s.document.dumps())
        cand.seams[0].chain_a = (cand.seams[0].chain_a[1], cand.seams[0].chain_a[0])
        cand.seams[0].a = cand.seams[0].chain_a[0]
        pre = s.preflight_transform(cand, set(), {})
        self.assertEqual(pre['status'], 'BLOCK')
        cand2 = Document.loads(s.document.dumps())
        cand2.seams[0].chain_a = (replace(cand2.seams[0].chain_a[0], t0=0.1), cand2.seams[0].chain_a[1])
        cand2.seams[0].a = cand2.seams[0].chain_a[0]
        pre2 = s.preflight_transform(cand2, set(), {})
        self.assertEqual(pre2['status'], 'BLOCK')
        cand3 = Document.loads(s.document.dumps())
        cand3.seams[0].chain_a = (replace(cand3.seams[0].chain_a[0], path='HOLE'), cand3.seams[0].chain_a[1])
        cand3.seams[0].a = cand3.seams[0].chain_a[0]
        pre3 = s.preflight_transform(cand3, set(), {})
        self.assertEqual(pre3['status'], 'BLOCK')

    def test_align_and_distribute_pieces(self):
        s = Session()
        ids = []
        for x, y, w in ((0.0, 0.0, .2), (.5, .3, .1), (1.2, .1, .3)):
            s.add([(x, y), (x + w, y), (x + w, y + .2), (x, y + .2)])
            ids.append(s.selected)
        s.selected_patterns = set(ids)
        s.align_pieces('LEFT')
        self.assertEqual({round(min(v.x for v in s.document.find(i).vertices), 9) for i in ids}, {0.0})
        s.align_pieces('TOP')
        self.assertEqual({round(max(v.y for v in s.document.find(i).vertices), 9) for i in ids}, {.5})
        for index, identity in enumerate(ids):
            for v in s.document.find(identity).vertices:
                v.x += index * .5
        s.align_pieces('DISTRIBUTE_X')
        boxes = sorted((min(v.x for v in s.document.find(i).vertices), max(v.x for v in s.document.find(i).vertices)) for i in ids)
        self.assertAlmostEqual(boxes[1][0] - boxes[0][1], boxes[2][0] - boxes[1][1])
        s.selected_patterns = set(ids[:1])
        with self.assertRaises(ValueError):
            s.align_pieces('LEFT')

if __name__ == '__main__':
    unittest.main()
