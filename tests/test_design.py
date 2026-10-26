import math
import unittest
from devil_designer.core import Session,Document,EdgeRef,area
from devil_designer import curves
from devil_designer.construction import chain_range,path_range
from devil_designer.meshing import edge_counts

class DesignTests(unittest.TestCase):
    def square(self):
        s=Session();s.add([(0,0),(.4,0),(.4,.5),(0,.5)]);return s

    def test_bezier_ellipse_and_length(self):
        s=Session();s.add_ellipse((-.1,-.1),(.1,.1));p=s.document.patterns[0]
        self.assertEqual(len(p.vertices),4)
        length=sum(s.document.edge_length(e) for e in s.document.edges(p.id))
        self.assertAlmostEqual(length,math.tau*.1,delta=.0002)
        self.assertAlmostEqual(abs(area(p.outline())),math.pi*.01,delta=.0001)

    def test_split_curve_preserves_shape_and_sewing(self):
        s=Session();s.add_ellipse((0,0),(.3,.4));a=s.document.patterns[0]
        s.add([(1,0),(1.3,0),(1.3,.4),(1,.4)]);b=s.document.patterns[1]
        edge=s.document.edge(a.id,0);other=s.document.edge(b.id,0)
        s.sew(edge,other);before=s.document.edge_length(edge)
        s.split_segment(edge)
        seam=s.document.seams[0]
        self.assertEqual(len(seam.side(0)),2)
        self.assertAlmostEqual(s.document.chain_length(seam.side(0)),before,delta=.0001)
        Document.loads(s.document.dumps())

    def test_exact_curved_length(self):
        s=Session();s.add_ellipse((0,0),(.3,.4));edge=s.document.edge(s.selected,0)
        s.set_length(edge,.21)
        self.assertAlmostEqual(s.document.edge_length(edge),.21,places=7)

    def test_partial_m_to_n_sewing_and_mismatch(self):
        s=self.square();a=s.document.patterns[0]
        s.add([(1,0),(1.3,0),(1.3,.2),(1,.2)]);b=s.document.patterns[1]
        left=chain_range(s.document,[s.document.edge(a.id,0)],.1,.9)
        right=[s.document.edge(b.id,0),s.document.edge(b.id,1)]
        s.sew_chains(left,right)
        seam=s.document.seams[0]
        self.assertGreater(s.document.seam_stats(seam)[3],1)
        plan=edge_counts(s.document,.03)
        self.assertTrue(plan.seam_pairs[0][1])
        for (edge,t),(other,u) in plan.seam_pairs[0][1]:
            self.assertTrue(any(abs(t-v)<1e-7 for v in plan.samples[edge]))
            self.assertTrue(any(abs(u-v)<1e-7 for v in plan.samples[other]))

    def test_nonoverlapping_ranges_can_share_edge(self):
        s=self.square();a=s.document.patterns[0]
        s.add([(1,0),(1.4,0),(1.4,.5),(1,.5)]);b=s.document.patterns[1]
        ea,eb=s.document.edge(a.id,0),s.document.edge(b.id,0)
        s.sew_chains(chain_range(s.document,[ea],0,.4),chain_range(s.document,[eb],0,.4))
        s.sew_chains(chain_range(s.document,[ea],.6,1),chain_range(s.document,[eb],.6,1))
        self.assertEqual(len(s.document.seams),2)

    def test_free_range_spans_multiple_segments(self):
        s=self.square();edges=s.document.edges(s.selected)
        chain=path_range(s.document,(edges[0],.5),(edges[2],.5))
        self.assertEqual(len(chain),3)
        self.assertAlmostEqual(s.document.chain_length(chain),.2+.5+.2)

    def test_unfold_without_seam(self):
        s=self.square();edge=s.document.edge(s.selected,1)
        before=abs(area(s.document.patterns[0].outline()))
        s.unfold(edge)
        self.assertEqual(len(s.document.patterns),1)
        self.assertAlmostEqual(abs(area(s.document.patterns[0].outline())),before*2)

    def test_mirror_with_seam(self):
        s=self.square();s.unfold(s.document.edge(s.selected,1),True)
        self.assertEqual(len(s.document.patterns),2)
        self.assertEqual(len(s.document.seams),1)
        self.assertFalse(s.document.seams[0].reverse)
        Document.loads(s.document.dumps())

    def test_internal_hole_trace_and_cut(self):
        s=self.square();path=s.add_path([(.1,.1),(.2,.1),(.2,.2),(.1,.2)],True)
        s.cut();self.assertEqual(path.role,'HOLE')
        self.assertFalse(s.document.patterns[0].contains((.15,.15)))
        s.trace();self.assertEqual(len(s.document.patterns),2)

    def test_cut_boundary_to_boundary(self):
        s=self.square();s.add_path([(.2,0),(.2,.5)])
        s.cut()
        self.assertEqual(len(s.document.patterns),2)
        self.assertAlmostEqual(sum(abs(area(p.outline())) for p in s.document.patterns),.2)
        Document.loads(s.document.dumps())

    def test_internal_slit(self):
        s=self.square();path=s.add_path([(.1,.1),(.3,.3)])
        s.cut();self.assertEqual(path.role,'SLIT')

    def test_dart_automatically_closes_itself(self):
        s=self.square();edge=s.document.edge(s.selected,2)
        s.dart(edge,.3,.7,(.2,.3))
        self.assertEqual(len(s.document.seams),1)
        seam=s.document.seams[0]
        self.assertEqual(seam.a.pattern,seam.b.pattern)
        self.assertAlmostEqual(s.document.seam_stats(seam)[2],0)
        Document.loads(s.document.dumps())

    def test_offset_and_merge(self):
        s=self.square();s.offset(.01)
        self.assertAlmostEqual(abs(area(s.document.patterns[1].outline())),.42*.52)
        s.merge_points([0,1]);self.assertEqual(len(s.document.patterns[1].vertices),3)

    def test_duplicate_and_mirror_preserve_dart_sewing(self):
        s=self.square();s.dart(s.document.edge(s.selected,2),.3,.7,(.2,.3))
        source=s.selected
        s.duplicate()
        self.assertEqual(len(s.document.seams),2)
        self.assertTrue(s.document.find(s.selected).features)
        s.selected=source
        s.unfold(s.document.edge(source,0),True)
        self.assertEqual(len(s.document.seams),4)
        Document.loads(s.document.dumps())

    def test_curved_princess_cut_preserves_total_fabric_area(self):
        s=self.square();path=s.add_path([(.2,0),(.25,.25),(.2,.5)])
        s.corner=1;s.curve_point()
        original=abs(area(s.document.patterns[0].outline()))
        s.cut()
        self.assertEqual(len(s.document.patterns),2)
        self.assertAlmostEqual(sum(abs(area(p.outline())) for p in s.document.patterns),original,delta=.0001)
        Document.loads(s.document.dumps())

    def test_pin_and_tack_round_trip(self):
        s=self.square();s.add_anchor((.1,.1));s.add_anchor((.2,.2),'TACK',(.5,.2,.7))
        d=Document.loads(s.document.dumps())
        self.assertEqual([a.kind for a in d.anchors],['PIN','TACK'])
        s.move([(x+.1,y) for x,y in d.patterns[0].points])
        self.assertAlmostEqual(s.document.anchors[0].x,.2)

if __name__=='__main__':unittest.main()
