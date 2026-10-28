import unittest
from devil_designer.core import Document, Session

SQUARE_A = [(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)]
SQUARE_B = [(0.3, 0.0), (0.5, 0.0), (0.5, 0.3), (0.3, 0.3)]

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.add(SQUARE_A)

    def test_box_select_picks_points(self):
        p = self.s.document.patterns[0]
        kind, count = self.s.box_select(-0.05, -0.05, 0.05, 0.05)
        self.assertEqual(kind, 'POINTS')
        self.assertEqual(count, 1)
        self.assertIn((p.id, 'OUTER', 0), self.s.selected_points)

    def test_box_select_picks_pieces_when_no_points(self):
        p = self.s.document.patterns[0]
        kind, count = self.s.box_select(0.05, 0.05, 0.15, 0.15)
        self.assertEqual(kind, 'PIECES')
        self.assertEqual(count, 1)
        self.assertIn(p.id, self.s.selected_patterns)

    def test_box_select_shift_retains_existing(self):
        p = self.s.document.patterns[0]
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
        self.s.move_selection(0.01, 0.01)
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
        self.assertEqual(len(self.s.selected_patterns), 0)

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
        s.rotate_90(clockwise=True)
        s.document.validate()
        s.rotate_90(clockwise=False)
        s.document.validate()

    def test_rotate_multi_piece(self):
        self.s.add(SQUARE_B)
        self.s.select_all()
        self.s.rotate_90(clockwise=True)
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

        self.s.rotate_90(clockwise=True)
        self.s.history()
        self.s.document.validate()

if __name__ == '__main__':
    unittest.main()
