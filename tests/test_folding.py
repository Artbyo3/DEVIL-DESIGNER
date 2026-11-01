import math
import unittest
from devil_designer.core import Document, Session
from devil_designer.folding import author_fold, edit_fold, fold_records, folded_positions
from devil_designer.history import restore, store
from devil_designer.linked_editing import clone_twin


class FoldingTests(unittest.TestCase):
    def panel(self):
        session = Session()
        session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        session.add_path([(.2, 0), (.2, .5)])
        return session

    def test_styles_use_internal_constraints_and_persistent_features(self):
        for style, count in (('MOUNTAIN', 1), ('VALLEY', 1), ('KNIFE', 2), ('BOX', 4)):
            with self.subTest(style=style):
                session = self.panel()
                author_fold(session, style)
                reopened = Document.loads(session.document.dumps()).patterns[0]
                self.assertEqual(len(fold_records(reopened)), count)
                self.assertTrue(all(path.role == 'INTERNAL' for path in reopened.paths))
                self.assertTrue(all(len(path.vertices) == 2 for path in reopened.paths))

    def test_direction_reversal_and_angle_edit(self):
        session = self.panel()
        author_fold(session, 'KNIFE')
        before = folded_positions(session.document.patterns[0], [(.1, .2)])[0]
        edit_fold(session, 'REVERSE')
        after = folded_positions(session.document.patterns[0], [(.1, .2)])[0]
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[2], -after[2])
        edit_fold(session, '60')
        self.assertEqual([abs(feature['angle']) for _, feature in fold_records(session.document.patterns[0])], [60, 60])
        edit_fold(session, 'REMOVE')
        self.assertFalse(fold_records(session.document.patterns[0]))
        self.assertEqual(len(session.document.patterns[0].paths), 2)

    def test_fold_is_isometric_on_each_side(self):
        session = self.panel()
        author_fold(session, 'MOUNTAIN')
        coords = [(.05, .1), (.15, .3), (.2, .2), (.3, .3), (.4, .1)]
        positions = folded_positions(session.document.patterns[0], coords)
        for left, right in ((0, 1), (1, 2), (2, 3), (3, 4)):
            self.assertAlmostEqual(math.dist(coords[left], coords[right]), math.dist(positions[left], positions[right]))

    def test_undo_redo_and_saved_history(self):
        session = self.panel()
        before = session.document.dumps()
        author_fold(session, 'BOX')
        folded = session.document.dumps()
        raw = store(session)
        reopened = Session(Document.loads(folded))
        self.assertTrue(restore(reopened, raw))
        reopened.history()
        self.assertEqual(reopened.document.dumps(), before)
        reopened.history(True)
        self.assertEqual(reopened.document.dumps(), folded)

    def test_duplicate_and_mirror_remap_fold_references(self):
        session = self.panel()
        author_fold(session, 'BOX')
        session.duplicate()
        self.assertEqual(len(fold_records(session.document.find(session.selected))), 4)
        source = session.document.patterns[0]
        session.selected = source.id
        session.unfold(session.document.edge(source.id, 0), True)
        self.assertEqual(len(fold_records(session.document.find(session.selected))), 4)

    def test_linked_twin_keeps_fold_settings_and_references(self):
        session = self.panel()
        author_fold(session, 'KNIFE')
        clone_twin(session)
        self.assertEqual(len(fold_records(session.document.find(session.selected))), 2)
        session.path = session.document.find(session.selected).paths[0].id
        edit_fold(session, '60')
        for pattern in session.document.patterns:
            self.assertEqual([abs(feature['angle']) for _, feature in fold_records(pattern)], [60, 60])

    def test_short_internal_line_cannot_fold_entire_half_plane(self):
        session = Session()
        session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        session.add_path([(.2, .1), (.2, .4)])
        before = session.document.dumps()
        with self.assertRaisesRegex(ValueError, 'boundary'):
            author_fold(session, 'MOUNTAIN')
        self.assertEqual(session.document.dumps(), before)

    def test_crossing_fold_and_broken_path_edits_roll_back(self):
        session = self.panel()
        author_fold(session, 'MOUNTAIN')
        fold_path = session.path
        session.add_path([(0, .2), (.4, .2)])
        before = session.document.dumps()
        with self.assertRaisesRegex(ValueError, 'parallel'):
            author_fold(session, 'MOUNTAIN')
        self.assertEqual(session.document.dumps(), before)
        session.path = fold_path
        session.corner = 0
        before = session.document.dumps()
        with self.assertRaises(ValueError):
            session.set_handle(0, 'outgoing', (.03, .1))
        self.assertEqual(session.document.dumps(), before)

    def test_pleat_rejects_insufficient_fabric_without_partial_edits(self):
        session = self.panel()
        session.document.patterns[0].paths[0].vertices[0].x = .01
        session.document.patterns[0].paths[0].vertices[1].x = .01
        before = session.document.dumps()
        with self.assertRaises(ValueError):
            author_fold(session, 'BOX', .04)
        self.assertEqual(session.document.dumps(), before)

    def test_deep_darts_have_no_artificial_depth_cap(self):
        for depth in (.1, .4, .49, .499):
            session = Session()
            session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
            session.dart(session.document.edge(session.selected, 2), .3, .7, (.2, .5-depth))
            reopened = Document.loads(session.document.dumps())
            self.assertEqual(len(reopened.seams), 1)
            self.assertAlmostEqual(reopened.seam_stats(reopened.seams[0])[2], 0)
