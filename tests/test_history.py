import ast
import io
import json
from pathlib import Path
import tokenize
import unittest

from devil_designer.core import Document, Session
from devil_designer.history import HISTORY_LIMIT, restore, store


SQUARE = [(0, 0), (.3, 0), (.3, .4), (0, .4)]


class PersistentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.add(SQUARE)
        self.session.duplicate()
        self.session.history()

    def reopened(self):
        return Session(Document.loads(self.session.document.dumps()))

    def assert_rejected(self, raw):
        session = self.reopened()
        session.undo_stack = ['stale undo']
        session.redo_stack = ['stale redo']
        document = session.document
        current = document.dumps()
        session.selected = document.patterns[0].id
        selected = session.selected
        self.assertFalse(restore(session, raw))
        self.assertIs(session.document, document)
        self.assertEqual(session.document.dumps(), current)
        self.assertEqual(session.selected, selected)
        self.assertEqual(session.undo_stack, [])
        self.assertEqual(session.redo_stack, [])
        self.assertIn('keep editing', session.history_message)
        self.assertFalse(session.history())
        self.assertFalse(session.history(True))
        session.add([(1, 0), (1.3, 0), (1.3, .4), (1, .4)])
        self.assertTrue(session.history())
        self.assertEqual(session.document.dumps(), current)

    def test_round_trip_preserves_undo_and_redo_order(self):
        session = self.reopened()
        self.assertTrue(restore(session, store(self.session)))
        self.assertEqual(session.undo_stack, self.session.undo_stack)
        self.assertEqual(session.redo_stack, self.session.redo_stack)
        for redo in (True, False, False, True, True):
            self.assertEqual(session.history(redo), self.session.history(redo))
            self.assertEqual(session.document.dumps(), self.session.document.dumps())

    def test_repeated_close_reopen_preserves_history(self):
        session = self.session
        for unused in range(3):
            raw = json.loads(json.dumps(dict(dd_history=store(session))))['dd_history']
            reopened = Session(Document.loads(session.document.dumps()))
            self.assertTrue(restore(reopened, raw))
            self.assertEqual(reopened.undo_stack, session.undo_stack)
            self.assertEqual(reopened.redo_stack, session.redo_stack)
            session = reopened

    def test_store_does_not_mutate_stacks_or_document(self):
        undo = self.session.undo_stack
        redo = self.session.redo_stack
        document = self.session.document
        raw = store(self.session)
        self.assertEqual(store(self.session), raw)
        self.assertIs(self.session.undo_stack, undo)
        self.assertIs(self.session.redo_stack, redo)
        self.assertIs(self.session.document, document)

    def test_both_stacks_are_bounded_to_latest_hundred(self):
        snapshots = []
        for index in range(HISTORY_LIMIT + 7):
            document = Document.loads(self.session.document.dumps())
            document.patterns[0].name = f'Pattern {index}'
            snapshots.append(document.dumps())
        self.session.undo_stack = snapshots.copy()
        self.session.redo_stack = snapshots[::-1]
        payload = json.loads(store(self.session))
        self.assertEqual(payload['undo'], snapshots[-HISTORY_LIMIT:])
        self.assertEqual(payload['redo'], snapshots[::-1][-HISTORY_LIMIT:])
        payload['undo'] = snapshots
        payload['redo'] = snapshots[::-1]
        session = self.reopened()
        self.assertTrue(restore(session, json.dumps(payload)))
        self.assertEqual(session.undo_stack, snapshots[-HISTORY_LIMIT:])
        self.assertEqual(session.redo_stack, snapshots[::-1][-HISTORY_LIMIT:])

    def test_external_document_replacement_invalidates_history(self):
        raw = store(self.session)
        self.session.document.patterns[0].name = 'External replacement'
        self.assert_rejected(raw)

    def test_matching_is_independent_of_json_key_order(self):
        session = self.reopened()
        session.document = Document.loads(json.dumps(
            json.loads(session.document.dumps()), sort_keys=True, indent=2))
        self.assertTrue(restore(session, store(self.session)))

    def test_selection_is_optional_and_resets_transient_selection(self):
        self.session.selected = self.session.document.patterns[0].id
        session = self.reopened()
        session.corner = 12
        session.path = 'removed path'
        session.segment = 7
        session.point_selection = [99]
        self.assertTrue(restore(session, store(self.session)))
        self.assertEqual(session.selected, self.session.selected)
        self.assertIsNone(session.corner)
        self.assertEqual(session.path, 'OUTER')
        self.assertIsNone(session.segment)
        self.assertEqual(session.point_selection, [])
        payload = json.loads(store(self.session))
        payload.pop('selected')
        session.selected = None
        self.assertTrue(restore(session, json.dumps(payload)))
        self.assertIsNone(session.selected)

    def test_invalid_envelopes_are_recoverable(self):
        for raw in ('{', 'null', '[]', 'true', '0', '"history"', '{}', 8, [], False):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_invalid_fields_are_recoverable(self):
        original = json.loads(store(self.session))
        for field, value in (
            ('version', 99), ('version', True), ('current', None),
            ('current', 'wrong fingerprint'), ('undo', {}), ('redo', None),
            ('selected', []), ('selected', 'missing pattern'),
        ):
            with self.subTest(field=field, value=value):
                payload = dict(original)
                payload[field] = value
                self.assert_rejected(json.dumps(payload))
        for field in ('version', 'current', 'undo', 'redo'):
            with self.subTest(missing=field):
                payload = dict(original)
                del payload[field]
                self.assert_rejected(json.dumps(payload))

    def test_every_retained_snapshot_is_validated_atomically(self):
        original = json.loads(store(self.session))
        document = json.loads(self.session.document.dumps())
        document['patterns'][0]['vertices'][0]['x'] = 'not a coordinate'
        for snapshot in ('', ' ', '{', 'null', '{}', '[]', 'false',
                         json.dumps(document), None, 17, {'version': 3}):
            for field in ('undo', 'redo'):
                with self.subTest(snapshot=snapshot, field=field):
                    payload = dict(original)
                    payload[field] = [self.session.document.dumps(), snapshot]
                    self.assert_rejected(json.dumps(payload))

    def test_invalid_geometry_and_nonfinite_snapshots_are_rejected(self):
        original = json.loads(store(self.session))
        for value in (float('nan'), float('inf'), -float('inf'), 10001):
            with self.subTest(value=value):
                document = json.loads(self.session.document.dumps())
                document['patterns'][0]['vertices'][0]['x'] = value
                payload = dict(original, undo=[json.dumps(document)])
                self.assert_rejected(json.dumps(payload))

    def test_duplicate_json_fields_are_rejected(self):
        raw = store(self.session)
        self.assert_rejected(raw[:-1] + ',"version":1}')
        payload = json.loads(raw)
        payload['undo'] = ['{"version":1,"patterns":[],"patterns":[]}']
        self.assert_rejected(json.dumps(payload))

    def test_malformed_construction_metadata_cannot_poison_editing(self):
        original = json.loads(store(self.session))
        for features in (None, {}, 'features', [None], [7], [{}],
                         [dict(id='feature', type='DART', seam=[])],
                         [dict(id='feature', type='DART', apex={})]):
            with self.subTest(features=features):
                document = json.loads(self.session.document.dumps())
                document['patterns'][0]['features'] = features
                self.assert_rejected(json.dumps(dict(original, undo=[json.dumps(document)])))

    def test_deeply_nested_history_is_recoverable(self):
        self.assert_rejected('[' * 2000 + '0' + ']' * 2000)

    def test_redo_is_cleared_by_edit_after_restore(self):
        session = self.reopened()
        self.assertTrue(restore(session, store(self.session)))
        self.assertTrue(session.redo_stack)
        session.add([(1, 0), (1.3, 0), (1.3, .4), (1, .4)])
        self.assertEqual(session.redo_stack, [])
        reopened = Session(Document.loads(session.document.dumps()))
        self.assertTrue(restore(reopened, store(session)))
        self.assertFalse(reopened.history(True))
        self.assertTrue(reopened.history())

    def test_missing_saved_history_clears_stale_stacks_quietly(self):
        for raw in ('', None):
            session = self.reopened()
            session.undo_stack = ['stale']
            session.redo_stack = ['stale']
            self.assertFalse(restore(session, raw))
            self.assertEqual(session.undo_stack, [])
            self.assertEqual(session.redo_stack, [])
            self.assertEqual(session.history_message, '')

    def test_bad_live_history_cannot_be_persisted_or_used(self):
        for field in ('undo_stack', 'redo_stack'):
            with self.subTest(field=field):
                session = self.reopened()
                current = session.document.dumps()
                setattr(session, field, ['damaged'])
                self.assertEqual(store(session), '')
                self.assertEqual(session.document.dumps(), current)
                self.assertEqual(session.undo_stack, [])
                self.assertEqual(session.redo_stack, [])
                self.assertIn('keep editing', session.history_message)

    def test_new_sources_have_no_comments_or_standalone_strings(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ('devil_designer/history.py', 'tests/test_history.py'):
            source = (root / relative).read_text(encoding='utf-8')
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            self.assertFalse(any(token.type == tokenize.COMMENT for token in tokens))
            tree = ast.parse(source)
            self.assertFalse(any(
                isinstance(node, ast.Expr) and (
                    isinstance(node.value, ast.JoinedStr) or
                    isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
                for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main()
