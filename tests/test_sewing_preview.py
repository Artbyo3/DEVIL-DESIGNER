import unittest
from types import SimpleNamespace
from devil_designer.core import EdgeRef, Session
from devil_designer.sewing_preview import resolve_sewing, status


class SewingPreviewTests(unittest.TestCase):
    def test_exact_resolution_and_attribution(self):
        session = Session()
        session.add([(0, 0), (.2, 0), (.2, .3), (0, .3)])
        session.add([(.4, 0), (.6, 0), (.6, .3), (.4, .3)])
        document = session.document
        first, second = [document.edge(pattern.id, 1) for pattern in document.patterns]
        maps = {first.pattern: {first.start: [(0, 3), (.5, 6), (1, 8)]}, second.pattern: {second.start: [(0, 11), (.5, 12), (1, 15)]}}
        pairs = [[(first, 0), (second, 1)], [(first, .5), (second, .5)], [(first, 1), (second, 0)]]
        plan = SimpleNamespace(seam_pairs=[('seam', pairs + pairs), ('duplicate', pairs)])
        springs, records = resolve_sewing(maps, plan)
        self.assertEqual(springs, {(3, 15), (6, 12), (8, 11)})
        self.assertEqual(records['seam'], dict(pairs=[[3, 15], [6, 12], [8, 11]], rest_lengths=[0.0] * 3))
        self.assertEqual(records['duplicate'], records['seam'])
        pairs[0][0] = (first, .01)
        with self.assertRaisesRegex(ValueError, 'Rebuild'):
            resolve_sewing(maps, plan)

    def test_middle_coverage_direction_and_existing_threshold(self):
        session = Session()
        session.add([(0, 0), (.2, 0), (.2, .3), (0, .3)])
        session.add([(.4, 0), (.6, 0), (.6, .27), (.4, .27)])
        document = session.document
        spans = []
        for pattern in document.patterns:
            edge = document.edge(pattern.id, 1)
            spans.append(EdgeRef(edge.pattern, edge.start, edge.end, .4, .6))
        session.sew_chains([spans[0]], [spans[1]], True)
        seam = document.seams[0]
        record = status(document, seam)
        self.assertAlmostEqual(record['mismatch'], 10)
        self.assertTrue(record['warning'])
        self.assertIn('Middle-only A 40-60%', record['flags'])
        self.assertIn('B reversed', record['flags'])
        self.assertIn('Gather warning; sewing allowed.', record['readout'])
        seam.b = seam.a
        seam.chain_b = seam.chain_a
        seam.reverse = False
        self.assertEqual(status(document, seam)['readout'], '0.0% · Pass')
