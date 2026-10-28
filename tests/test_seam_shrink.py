import json
import unittest
from dataclasses import replace
from types import SimpleNamespace

from devil_designer.core import Document, Session
from devil_designer.density import boundary_plan
from devil_designer.history import restore, store
from devil_designer.seam_shrink import CALIBRATED_WEIGHTS, boundary_weights


class SeamShrinkTests(unittest.TestCase):
    def fixture(self, partial=False, chained=False, reverse=True):
        session = Session()
        session.add([(0, 0), (.3, 0), (.3, .4), (0, .4)])
        session.add([(.5, 0), (.8, 0), (.8, .4), (.5, .4)])
        first, second = session.document.patterns
        first_edges = session.document.edges(first.id)
        second_edges = session.document.edges(second.id)
        if partial:
            first_edges = [replace(first_edges[1], t0=.2, t1=.8)]
            second_edges = [replace(second_edges[3], t0=.1, t1=.9)]
        elif chained:
            first_edges, second_edges = first_edges[:2], second_edges[2:]
        else:
            first_edges, second_edges = [first_edges[1]], [second_edges[3]]
        session.sew_chains(first_edges, second_edges, reverse)
        return session

    def maps(self, plan):
        maps = {}
        index = 0
        for edge, samples in plan.samples.items():
            values = []
            for sample in samples:
                values.append((sample, index))
                index += 1
            maps.setdefault(edge.pattern, {})[edge.start] = values
        return maps

    def test_allowed_values_round_trip_and_zero_omission(self):
        session = self.fixture()
        identity = session.document.seams[0].id
        baseline = session.document.dumps()
        self.assertNotIn("shrink", json.loads(baseline)["seams"][0])
        for shrink in (10, 20, 30, 0):
            session.set_seam_shrink(identity, shrink)
            loaded = Document.loads(session.document.dumps())
            self.assertEqual(loaded.seams[0].shrink, shrink)
            self.assertEqual(loaded.dumps(), session.document.dumps())
        self.assertEqual(session.document.dumps(), baseline)

    def test_invalid_values_do_not_modify_document_or_history(self):
        session = self.fixture()
        identity = session.document.seams[0].id
        before = session.document.dumps(), list(session.undo_stack)
        for invalid in (True, False, None, "10", 10.0, .1, -10, 1, 40, float("nan"), float("inf")):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                session.set_seam_shrink(identity, invalid)
            self.assertEqual((session.document.dumps(), session.undo_stack), before)
        with self.assertRaises(ValueError):
            session.set_seam_shrink("missing", 10)

    def test_invalid_saved_values_are_rejected(self):
        payload = json.loads(self.fixture().document.dumps())
        for invalid in (True, False, "20", 20.0, -10, 5, 40, None):
            payload["seams"][0]["shrink"] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                Document.loads(json.dumps(payload))

    def test_legacy_documents_default_to_zero(self):
        payload = json.loads(self.fixture().document.dumps())
        for version in (2, 3, 4):
            payload["version"] = version
            loaded = Document.loads(json.dumps(payload))
            self.assertEqual(loaded.seams[0].shrink, 0)
            self.assertNotIn("shrink", json.loads(loaded.dumps())["seams"][0])
        payload["version"] = 1
        self.assertEqual(Document.loads(json.dumps(payload)).seams, [])

    def test_persistent_undo_redo_and_noop(self):
        session = self.fixture()
        identity = session.document.seams[0].id
        session.set_seam_shrink(identity, 20)
        depth = len(session.undo_stack)
        self.assertFalse(session.set_seam_shrink(identity, 20))
        self.assertEqual(len(session.undo_stack), depth)
        reopened = Session(Document.loads(session.document.dumps()))
        self.assertTrue(restore(reopened, store(session)))
        reopened.history()
        self.assertEqual(reopened.document.seams[0].shrink, 0)
        reopened.history(True)
        self.assertEqual(reopened.document.seams[0].shrink, 20)

    def test_partial_chained_and_reversed_sampling_is_unchanged(self):
        for partial, chained in ((False, False), (True, False), (False, True)):
            for reverse in (False, True):
                with self.subTest(partial=partial, chained=chained, reverse=reverse):
                    session = self.fixture(partial, chained, reverse)
                    baseline = boundary_plan(session.document, .03)
                    seam = session.document.seams[0]
                    session.set_seam_shrink(seam.id, 30)
                    plan = boundary_plan(session.document, .03)
                    self.assertEqual(plan.seam_pairs, baseline.seam_pairs)
                    self.assertEqual(plan.samples, baseline.samples)
                    maps = self.maps(plan)
                    weights = boundary_weights(session.document.seams, maps, plan)
                    expected = set()
                    for _, pairs in plan.seam_pairs:
                        for pair in pairs:
                            for edge, fraction in pair:
                                expected.add(min(maps[edge.pattern][edge.start], key=lambda sample: abs(sample[0] - fraction))[1])
                    self.assertEqual(set(weights), expected)
                    self.assertEqual(set(weights.values()), {CALIBRATED_WEIGHTS[30]})
                    self.assertTrue(all(any(edge.pattern == pattern.id for _, pairs in plan.seam_pairs for pair in pairs for edge, _ in pair) for pattern in session.document.patterns))
                    if partial:
                        edge = session.document.seams[0].a
                        outside = [vertex for fraction, vertex in maps[edge.pattern][edge.start] if fraction < edge.t0 - 1e-8 or fraction > edge.t1 + 1e-8]
                        self.assertTrue(outside)
                        self.assertFalse(set(outside) & set(weights))

    def test_maximum_shrink_wins_shared_vertices_in_both_orders(self):
        edge = SimpleNamespace(pattern="piece", start="edge")
        maps = {"piece": {"edge": [(0, 4), (1, 9)]}}
        pairs = [((edge, 0), (edge, 1))]
        seams = [SimpleNamespace(id="low", shrink=10), SimpleNamespace(id="high", shrink=30), SimpleNamespace(id="zero", shrink=0)]
        for order in (seams, seams[::-1]):
            plan = SimpleNamespace(seam_pairs=[(seam.id, pairs) for seam in order])
            self.assertEqual(boundary_weights(order, maps, plan), {4: CALIBRATED_WEIGHTS[30], 9: CALIBRATED_WEIGHTS[30]})

    def test_zero_has_no_weights_and_changed_samples_refuse(self):
        session = self.fixture()
        plan = boundary_plan(session.document, .03)
        maps = self.maps(plan)
        self.assertEqual(boundary_weights(session.document.seams, maps, plan), {})
        session.set_seam_shrink(session.document.seams[0].id, 10)
        edge, _ = plan.seam_pairs[0][1][0][0]
        maps[edge.pattern][edge.start] = [(9, 0)]
        with self.assertRaises(ValueError):
            boundary_weights(session.document.seams, maps, plan)

    def test_reverse_split_and_duplicate_preserve_shrink(self):
        session = self.fixture()
        identity = session.document.seams[0].id
        session.set_seam_shrink(identity, 20)
        session.reverse_seam(identity)
        session.split_segment(session.document.seams[0].a)
        self.assertEqual(session.document.seams[0].shrink, 20)
        session.selected_patterns = {pattern.id for pattern in session.document.patterns}
        session.duplicate()
        self.assertEqual(len(session.document.seams), 2)
        self.assertTrue(all(seam.shrink == 20 for seam in session.document.seams))
        session.document.validate()


if __name__ == "__main__":
    unittest.main()
