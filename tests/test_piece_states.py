import json
import unittest
from devil_designer import history, piece_states
from devil_designer.core import Document, Session
from devil_designer.linked_editing import clone_twin, toggle_link


class PieceStateTests(unittest.TestCase):
    def session(self):
        session = Session()
        session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        return session

    def test_normal_document_serialization_unchanged(self):
        session = self.session()
        normal = session.document.dumps()
        self.assertNotIn('simulation', json.loads(normal)['patterns'][0])
        for flag in piece_states.FLAGS:
            piece_states.toggle(session, flag)
            piece_states.toggle(session, flag)
        self.assertEqual(session.document.dumps(), normal)
        self.assertFalse(piece_states.required(session.document))

    def test_round_trip_duplicate_and_hundred_edit_history(self):
        session = self.session()
        for flag in piece_states.FLAGS:
            piece_states.toggle(session, flag)
        original = session.document.dumps()
        session.duplicate()
        self.assertTrue(all(getattr(pattern, flag) for pattern in session.document.patterns for flag in piece_states.FLAGS))
        session.history()
        for index in range(100):
            piece_states.toggle(session, piece_states.FLAGS[index % 3])
        saved = history.store(session)
        restored = Session(Document.loads(session.document.dumps()))
        history.restore(restored, saved)
        for index in range(100):
            self.assertTrue(restored.history())
        self.assertEqual(restored.document.dumps(), original)
        for index in range(100):
            self.assertTrue(restored.history(redo=True))
        self.assertEqual(restored.document.dumps(), session.document.dumps())

    def test_invalid_flags_are_rejected(self):
        data = json.loads(self.session().document.dumps())
        for invalid in (None, [], True, {'unknown': True}, {'frozen': 1}, {'deactivated': 'yes'}):
            data['patterns'][0]['simulation'] = invalid
            with self.assertRaises(ValueError):
                Document.loads(json.dumps(data))

    def test_linked_twins_only_share_flags_while_explicitly_linked(self):
        session = self.session()
        original = session.selected
        twin = clone_twin(session)
        session.selected = original
        toggle_link(session)
        piece_states.toggle(session, 'frozen')
        self.assertTrue(session.document.find(original).frozen)
        self.assertFalse(twin.frozen)
        toggle_link(session)
        piece_states.toggle(session, 'strengthened')
        self.assertTrue(all(pattern.strengthened for pattern in session.document.patterns))

    def test_inactive_seams_are_absent_only_in_run_copy(self):
        session = self.session()
        first = session.document.patterns[0]
        session.add([(.5, 0), (.9, 0), (.9, .5), (.5, .5)])
        second = session.document.patterns[1]
        session.sew(session.document.edge(first.id, 1), session.document.edge(second.id, 3))
        first.deactivated = True
        source = session.document.dumps()
        run = piece_states.active_document(session.document)
        self.assertEqual([pattern.id for pattern in run.patterns], [second.id])
        self.assertFalse(run.seams)
        self.assertEqual(session.document.dumps(), source)
        self.assertFalse(any(getattr(pattern, flag) for pattern in run.patterns for flag in piece_states.FLAGS))

    def test_state_labels_are_explicit(self):
        pattern = self.session().document.patterns[0]
        self.assertEqual(piece_states.label(pattern), '')
        pattern.frozen = True
        pattern.strengthened = True
        self.assertEqual(piece_states.label(pattern), 'Frozen · Strengthened ×4')
        pattern.deactivated = True
        self.assertEqual(piece_states.label(pattern), 'Deactivated')

    def test_frozen_outline_remains_editable(self):
        session = self.session()
        piece_states.toggle(session, 'frozen')
        pattern = session.document.patterns[0]
        points = pattern.points
        points[0] = (-.02, 0)
        session.move(points)
        self.assertTrue(session.document.patterns[0].frozen)
        self.assertEqual(session.document.patterns[0].points[0], (-.02, 0))
