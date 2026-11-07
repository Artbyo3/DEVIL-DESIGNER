import math
import unittest

from devil_designer import folding, starters
from devil_designer.core import Document, Session
from devil_designer.linked_editing import clone_twin


def square(session, x=0.0, size=.2):
    session.add([(x, 0), (x + size, 0), (x + size, size), (x, size)])
    return session.document.patterns[-1]


class PatternOperations(unittest.TestCase):
    def test_offset_path_adds_a_parallel_line(self):
        session = Session()
        square(session)
        session.add_path([(.05, .02), (.05, .18)])
        path = session.offset_path(.02)
        self.assertAlmostEqual(abs(path.vertices[0].x - .05), .02)
        self.assertEqual(len(session.document.patterns[0].paths), 2)

    def test_round_corner_replaces_the_corner_with_a_curve(self):
        session = Session()
        piece = square(session)
        session.selected, session.corner = piece.id, 2
        session.round_corner(.03)
        self.assertEqual(len(piece.vertices), 5)
        self.assertFalse(any(math.dist((v.x, v.y), (.2, .2)) < 1e-6 for v in piece.vertices))
        self.assertTrue(any(v.outgoing is not None for v in piece.vertices))

    def test_round_corner_refuses_a_radius_that_does_not_fit(self):
        session = Session()
        piece = square(session)
        session.selected, session.corner = piece.id, 0
        with self.assertRaises(ValueError):
            session.round_corner(.15)

    def test_layer_clone_sews_only_free_edges(self):
        session = Session()
        first = square(session)
        second = square(session, .4)
        session.sew(session.document.edge(first.id, 1), session.document.edge(second.id, 3))
        session.selected = first.id
        session.layer_clone()
        self.assertEqual(len(session.document.patterns), 3)
        self.assertEqual(len(session.document.seams), 4)

    def test_merge_joins_two_sewn_pieces_and_keeps_other_seams(self):
        session = Session()
        first = square(session)
        second = square(session, .4)
        third = square(session, .8)
        document = session.document
        session.sew_chains([document.edge(first.id, 1)], [document.edge(second.id, 3)], True)
        session.sew_chains([document.edge(second.id, 1)], [document.edge(third.id, 3)], True)
        session.merge_pieces(document.edge(first.id, 1))
        merged = session.document.find(first.id)
        self.assertEqual(len(session.document.patterns), 2)
        self.assertEqual(len(merged.vertices), 6)
        self.assertAlmostEqual(max(v.x for v in merged.vertices) - min(v.x for v in merged.vertices), .4)
        self.assertEqual(len(session.document.seams), 1)
        self.assertEqual(session.document.seams[0].side(0)[0].pattern, first.id)
        Document.loads(session.document.dumps())

    def test_merge_refuses_different_lengths(self):
        session = Session()
        first = square(session)
        second = square(session, .4, .3)
        document = session.document
        session.sew_chains([document.edge(first.id, 1)], [document.edge(second.id, 3)], True)
        with self.assertRaises(ValueError):
            session.merge_pieces(document.edge(first.id, 1))


class SewingOperations(unittest.TestCase):
    def sewn(self):
        session = Session()
        first = square(session)
        second = square(session, .4)
        document = session.document
        session.sew_chains([document.edge(first.id, 1)], [document.edge(second.id, 3)], True)
        return session, document.seams[0]

    def test_seam_end_slides_and_survives_a_round_trip(self):
        session, seam = self.sewn()
        session.set_seam_end(seam.id, 0, True, .5)
        loaded = Document.loads(session.document.dumps())
        self.assertAlmostEqual(loaded.seams[0].side(0)[-1].t1, .5)

    def test_exact_seam_length(self):
        session, seam = self.sewn()
        session.set_seam_length(seam.id, 0, .05)
        self.assertAlmostEqual(session.document.chain_length(session.document.seams[0].side(0)), .05)

    def test_seam_ease_side_persists(self):
        session, seam = self.sewn()
        session.set_seam_ease(seam.id, 2)
        self.assertEqual(Document.loads(session.document.dumps()).seams[0].ease_side, 2)

    def test_new_seam_is_copied_to_the_linked_twin(self):
        session = Session()
        first = square(session)
        other = square(session, .4)
        session.selected = first.id
        clone_twin(session)
        twin = next(p for p in session.document.patterns if p.id not in {first.id, other.id})
        session.selected = other.id
        clone_twin(session)
        document = session.document
        session.sew_chains([document.edge(first.id, 0)], [document.edge(other.id, 0)], True)
        self.assertEqual(len(document.seams), 2)
        self.assertTrue(any(edge.pattern == twin.id for seam in document.seams for edge in seam.side(0)))

    def test_auto_sew_pairs_side_edges_and_leaves_hems(self):
        session = Session()
        square(session)
        square(session, .4)
        self.assertEqual(session.auto_sew(), 2)
        self.assertEqual(len(session.document.seams), 2)

    def test_pleats_sew_closed(self):
        session = Session()
        piece = square(session, 0.0, .4)
        session.selected = piece.id
        session.add_path([(.1, 0), (.1, .4)])
        session.selected = piece.id
        folding.author_fold(session, 'KNIFE', .02)
        session.segment = session.document.edge(piece.id, 0)
        self.assertEqual(folding.sew_pleats(session), 1)
        seam = session.document.seams[0]
        self.assertEqual(seam.side(0)[0].pattern, seam.side(1)[0].pattern)

    def test_accordion_pleat_makes_four_folds(self):
        session = Session()
        piece = square(session, 0.0, .4)
        session.selected = piece.id
        session.add_path([(.1, 0), (.1, .4)])
        session.selected = piece.id
        folding.author_fold(session, 'ACCORDION', .02)
        self.assertEqual(len(folding.fold_records(session.document.find(piece.id))), 4)


class SlashAndSteam(unittest.TestCase):
    def test_slash_and_spread_opens_a_wedge(self):
        session = Session()
        piece = square(session, 0.0, .4)
        session.selected = piece.id
        session.add_path([(.2, 0), (.2, .4)])
        session.selected = piece.id
        before = max(v.x for v in piece.vertices)
        session.slash_spread(15)
        self.assertEqual(len(piece.vertices), 7)
        self.assertGreater(max(v.x for v in piece.vertices), before)
        self.assertFalse(piece.paths)
        Document.loads(session.document.dumps())

    def test_steam_persists_and_clears(self):
        session = Session()
        piece = square(session)
        session.add_steam([dict(pattern=piece.id, x=.1, y=.1, radius=.05, amount=.12)])
        self.assertEqual(len(Document.loads(session.document.dumps()).steam), 1)
        session.clear_steam(piece.id)
        self.assertFalse(session.document.steam)


class PinsAndElastic(unittest.TestCase):
    def test_pins_in_box_stay_on_fabric(self):
        session = Session()
        square(session)
        session.pins_in_box((-.1, .05), (.1, .1))
        self.assertTrue(session.document.anchors)
        self.assertTrue(all(anchor.x >= 0 for anchor in session.document.anchors))

    def test_fabric_tack_persists_and_removing_one_end_removes_both(self):
        session = Session()
        first = square(session)
        second = square(session, .4)
        session.add_join((first.id, .1, .1), (second.id, .5, .1))
        loaded = Document.loads(session.document.dumps())
        self.assertEqual(len(loaded.joins), 1)
        session.commit(lambda: session.document.anchors.pop())
        self.assertFalse(session.document.joins)
        self.assertFalse(session.document.anchors)

    def test_elastic_persists_and_clears(self):
        session = Session()
        piece = square(session)
        edge = session.document.edge(piece.id, 0)
        session.set_elastic(edge, 20)
        self.assertEqual(Document.loads(session.document.dumps()).elastics[0]['shrink'], 20)
        session.set_elastic(edge, 0)
        self.assertFalse(session.document.elastics)


class Starters(unittest.TestCase):
    def test_every_starter_builds_a_valid_sewn_document(self):
        measurements = dict(chest=96.0, waist=80.0, hip=96.0, torso_length=40.0, shoulder_width=44.0, inseam=76.0, height=170.0)
        for key, (label, generator, _) in starters.STARTER_GENERATORS.items():
            document = generator(measurements, 'COTTON')
            document.validate()
            self.assertTrue(document.seams, label)
            for seam in document.seams:
                first, second, difference, _ = document.seam_stats(seam)
                self.assertLess(difference, .02, f'{label} seam lengths differ')


if __name__ == '__main__':
    unittest.main()
