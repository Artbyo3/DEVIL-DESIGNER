import json
import math
import unittest
from devil_designer.core import Document, Session
from devil_designer.meshing import edge_counts

class SeamTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.add([(0,0),(.3,0),(.3,.4),(0,.4)])
        self.s.add([(.5,0),(.9,0),(.9,.5),(.5,.5)])
        a,b = self.s.document.patterns
        self.a,self.b = self.s.document.edge(a.id,1),self.s.document.edge(b.id,3)

    def test_version_one_migrates_without_losing_ids(self):
        old = json.loads(self.s.document.dumps())
        old['version'] = 1
        del old['seams']
        d = Document.loads(json.dumps(old))
        self.assertEqual(d.patterns[0].id,self.s.document.patterns[0].id)
        self.assertEqual(d.seams,[])
        self.assertEqual(json.loads(d.dumps())['version'],3)

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
        self.assertEqual(len(self.s.document.seams),1)  # Same-piece sewing is required for darts.

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

if __name__=='__main__':
    unittest.main()
