import json
import math
from types import SimpleNamespace
import unittest
try:
    import bpy
except ImportError:
    from unittest.mock import MagicMock
    import sys
    sys.modules['bpy'] = MagicMock()
from devil_designer.construction import sew_reverse
from devil_designer.core import Document, Session
from devil_designer.design_tools import DesignTools
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

    def test_newly_created_free_and_chain_seam_direction(self):
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
        self.s.document.seams.clear()
        scene.dd_free_sewing = False
        editor.chain_a = [edge_a]
        editor.chain_b = [edge_b]
        editor.design_action('CHAIN_SEW')
        self.assertEqual(len(self.s.document.seams), 1)
        chain_seam = self.s.document.seams[-1]
        self.assertFalse(chain_seam.reverse)
        self.assertEqual(chain_seam.reverse, sew_reverse(doc, chain_seam.side(0), chain_seam.side(1), scene.dd_sew_reverse))


class DummyScene(SimpleNamespace):
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

    def refresh_controls(self):
        pass

if __name__=='__main__':
    unittest.main()
