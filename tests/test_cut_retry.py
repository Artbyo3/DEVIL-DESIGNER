import copy
import unittest
from unittest.mock import patch

from devil_designer.core import Document,EdgeRef,Seam,Session,area


class CutRetryTests(unittest.TestCase):
    def crossing(self,points=None,cut=None):
        session=Session()
        session.add([(0,0),(1,0),(1,1),(0,1)])
        crossing=session.add_path(points or [(.1,.5),(.9,.5)])
        cutter=session.add_path(cut or [(.5,0),(.5,1)])
        return session,crossing,cutter

    def state(self,session):
        return (session.document.dumps(),session.selected,session.path,session.corner,
                copy.deepcopy(session.undo_stack),copy.deepcopy(session.redo_stack),session.last_repairs)

    def test_existing_cut_refuses_crossing_without_mutation(self):
        session,crossing,cutter=self.crossing()
        before=self.state(session)
        with self.assertRaisesRegex(ValueError,'crosses another internal shape'):
            session.cut()
        self.assertEqual(self.state(session),before)

    def test_preview_is_read_only_and_identifies_crossing(self):
        session,crossing,cutter=self.crossing()
        session.corner=crossing.vertices[0].id
        session.last_repairs=3
        before=self.state(session);document=session.document
        preview=session.preview_cut()
        self.assertEqual(preview['status'],'SPLIT_REQUIRED')
        self.assertTrue(preview['can_retry'])
        self.assertEqual(preview['split_count'],1)
        self.assertEqual(preview['crossing_paths'],[dict(id=crossing.id,name=crossing.name)])
        self.assertEqual(self.state(session),before)
        self.assertIs(session.document,document)

    def test_retry_splits_pieces_and_lines_in_one_undo_step(self):
        session,crossing,cutter=self.crossing()
        before=session.document.dumps();undo_count=len(session.undo_stack)
        self.assertTrue(session.retry_cut(session.preview_cut()))
        after=session.document.dumps()
        self.assertEqual(len(session.document.patterns),2)
        self.assertEqual(sum(len(piece.paths) for piece in session.document.patterns),2)
        self.assertEqual(sum(path.id==crossing.id for piece in session.document.patterns for path in piece.paths),1)
        self.assertAlmostEqual(sum(abs(area(piece.outline())) for piece in session.document.patterns),1)
        self.assertEqual(len(session.undo_stack),undo_count+1)
        self.assertEqual(session.path,'OUTER')
        self.assertIsNone(session.corner)
        Document.loads(after)
        self.assertTrue(session.history())
        self.assertEqual(session.document.dumps(),before)
        self.assertTrue(session.history(True))
        self.assertEqual(session.document.dumps(),after)

    def test_crossing_at_existing_vertex_does_not_duplicate_ids(self):
        session,crossing,cutter=self.crossing([(.1,.5),(.5,.5),(.9,.5)])
        session.retry_cut(session.preview_cut())
        self.assertEqual(sum(len(piece.paths) for piece in session.document.patterns),2)
        session.document.validate()

    def test_multiple_crossings_on_one_segment(self):
        session,crossing,cutter=self.crossing(cut=[(.3,0),(.3,.7),(.7,.7),(.7,.3),(1,.3)])
        preview=session.preview_cut()
        self.assertTrue(preview['can_retry'],preview['reason'])
        self.assertEqual(preview['split_count'],2)
        session.retry_cut(preview)
        self.assertEqual(sum(len(piece.paths) for piece in session.document.patterns),3)
        self.assertAlmostEqual(sum(session.document.edge_length(edge) for piece in session.document.patterns
                                  for path in piece.paths for edge in session.document.edges(piece.id,path.id)),.8)
        session.document.validate()

    def test_multiple_crossing_paths_and_slit_roles(self):
        session,crossing,cutter=self.crossing()
        crossing.role='SLIT'
        other=session.add_path([(.2,.7),(.8,.7)])
        session.path=cutter.id
        preview=session.preview_cut()
        self.assertEqual(preview['split_count'],2)
        self.assertEqual({item['id'] for item in preview['crossing_paths']},{crossing.id,other.id})
        session.retry_cut(preview)
        self.assertEqual(sum(path.role=='SLIT' for piece in session.document.patterns for path in piece.paths),2)
        session.document.validate()

    def test_sewing_ranges_directions_and_cut_boundary_relationships_survive(self):
        session,crossing,cutter=self.crossing()
        original=session.document.patterns[0]
        session.add([(2,0),(3,0),(3,1),(2,1)])
        partner=session.document.patterns[-1]
        line=session.document.edge(original.id,0,crossing.id)
        outer=session.document.edge(original.id,0)
        cut_edge=session.document.edge(original.id,0,cutter.id)
        seams=[Seam(EdgeRef(line.pattern,line.start,line.end,.9,.1,line.path),session.document.edge(partner.id,0),False),
               Seam(outer,session.document.edge(partner.id,1)),
               Seam(cut_edge,session.document.edge(partner.id,2))]
        session.document.seams.extend(seams)
        session.selected=original.id;session.path=cutter.id
        before={seam.id:([[session.document.edge_points(edge) for edge in seam.side(side)] for side in (0,1)],
                              [session.document.chain_length(seam.side(side)) for side in (0,1)],seam.reverse)
                for seam in seams}
        preview=session.preview_cut()
        self.assertTrue(preview['can_retry'],preview['reason'])
        session.retry_cut(preview)
        self.assertEqual({seam.id for seam in session.document.seams},set(before))
        for seam in session.document.seams:
            endpoints,lengths,reverse=before[seam.id]
            self.assertEqual(seam.reverse,reverse)
            for side in (0,1):
                chain=seam.side(side)
                self.assertAlmostEqual(session.document.chain_length(chain),lengths[side])
                for actual,expected in zip(session.document.edge_points(chain[0])[0],endpoints[side][0][0]):
                    self.assertAlmostEqual(actual,expected)
                for actual,expected in zip(session.document.edge_points(chain[-1])[1],endpoints[side][-1][1]):
                    self.assertAlmostEqual(actual,expected)
        self.assertEqual(session.last_repairs,0)
        Document.loads(session.document.dumps())

    def test_pins_tacks_wrap_and_unrelated_piece_survive(self):
        session,crossing,cutter=self.crossing()
        original=session.document.patterns[0]
        original.wrap_radius=.3;original.preset='DENIM'
        session.document.uv_layout=dict(scale=2,origin=[.2,.3])
        left=session.add_anchor((.2,.2))
        right=session.add_anchor((.8,.8),'TACK',(1,2,3))
        session.add([(2,0),(3,0),(3,1),(2,1)])
        unrelated=copy.deepcopy(session.document.patterns[-1])
        session.selected=original.id;session.path=cutter.id
        session.retry_cut(session.preview_cut())
        self.assertEqual(session.document.find(unrelated.id),unrelated)
        anchors={anchor.id:anchor for anchor in session.document.anchors}
        self.assertNotEqual(anchors[left.id].pattern,anchors[right.id].pattern)
        self.assertEqual(anchors[right.id].target,(1,2,3))
        self.assertEqual(anchors[right.id].kind,'TACK')
        self.assertEqual(session.document.uv_layout,dict(scale=2,origin=[.2,.3]))
        for piece in session.document.patterns:
            if piece.id!=unrelated.id:
                self.assertEqual(piece.wrap_radius,.3)
                self.assertEqual(piece.preset,'DENIM')

    def test_stale_document_or_selection_refuses_without_mutation(self):
        for change in ('document','selection','path'):
            with self.subTest(change=change):
                session,crossing,cutter=self.crossing()
                preview=session.preview_cut()
                if change=='document':session.document.patterns[0].name='Renamed'
                elif change=='selection':session.selected=None
                else:session.path=crossing.id
                before=self.state(session)
                with self.assertRaisesRegex(ValueError,'out of date'):
                    session.retry_cut(preview)
                self.assertEqual(self.state(session),before)

    def test_late_failure_keeps_document_identity_and_entire_session(self):
        session,crossing,cutter=self.crossing()
        preview=session.preview_cut();before=self.state(session);document=session.document
        original_cut=Session.cut
        def fail_after_cut(trial):
            original_cut(trial)
            raise ValueError('Late validation failure')
        with patch.object(Session,'cut',fail_after_cut):
            with self.assertRaisesRegex(ValueError,'Late validation failure'):
                session.retry_cut(preview)
        self.assertEqual(self.state(session),before)
        self.assertIs(session.document,document)

    def test_closed_shapes_features_overlaps_and_on_cut_anchors_refuse(self):
        for condition,message in (('closed','closed internal shape'),('hole','closed internal shape'),
                                  ('features','construction features'),('overlap','overlaps'),
                                  ('anchor','pin or tack'),('curve','curved')):
            with self.subTest(condition=condition):
                session,crossing,cutter=self.crossing()
                if condition in ('closed','hole'):
                    session.path=crossing.id
                    session.document.patterns[0].paths.remove(crossing)
                    shape=session.add_path([(.4,.3),(.6,.3),(.6,.7),(.4,.7)],True)
                    if condition=='hole':shape.role='HOLE'
                    session.path=cutter.id
                elif condition=='features':session.document.patterns[0].features.append(dict(id='feature',type='UNFOLD'))
                elif condition=='overlap':session.add_path([(.5,.1),(.5,.9)]);session.path=cutter.id
                elif condition=='anchor':session.add_anchor((.5,.2))
                else:crossing.vertices[0].outgoing=(.2,.1)
                before=self.state(session)
                preview=session.preview_cut()
                self.assertEqual(preview['status'],'REFUSED')
                self.assertFalse(preview['can_retry'])
                self.assertIn(message,preview['reason'])
                with self.assertRaises(ValueError):session.retry_cut(preview)
                self.assertEqual(self.state(session),before)

    def test_ordinary_cut_hole_and_slit_need_no_retry(self):
        for points,closed in (([(.5,0),(.5,1)],False),([(.1,.1),(.3,.3)],False),
                              ([(.1,.1),(.3,.1),(.3,.3),(.1,.3)],True)):
            with self.subTest(points=points):
                session=Session();session.add([(0,0),(1,0),(1,1),(0,1)])
                session.add_path(points,closed)
                before=self.state(session)
                preview=session.preview_cut()
                self.assertEqual(preview['status'],'READY')
                self.assertFalse(preview['can_retry'])
                self.assertEqual(self.state(session),before)

    def test_retry_cannot_be_replayed_and_clears_redo(self):
        session,crossing,cutter=self.crossing()
        session.redo_stack.append(session.document.dumps())
        preview=session.preview_cut()
        session.retry_cut(preview)
        self.assertEqual(session.redo_stack,[])
        before=self.state(session)
        with self.assertRaisesRegex(ValueError,'out of date'):session.retry_cut(preview)
        self.assertEqual(self.state(session),before)

    def test_no_selection_refuses_clearly(self):
        session=Session()
        self.assertEqual(session.preview_cut()['status'],'REFUSED')
        with self.assertRaisesRegex(ValueError,'out of date'):session.retry_cut(None)

    def test_cut_trace_and_retry_preserve_mesh_density_and_fabric_settings(self):
        for action in ('cut','trace','retry'):
            for density in ('AUTO','COARSE','STANDARD','FINE'):
                with self.subTest(action=action,density=density):
                    session=Session();session.add([(0,0),(1,0),(1,1),(0,1)])
                    source=session.document.patterns[0]
                    source.mesh_density=density;source.preset='KNIT';source.wrap_radius=.24
                    if action=='trace':
                        session.add_path([(.1,.1),(.3,.1),(.3,.3),(.1,.3)],True)
                        session.trace()
                    else:
                        if action=='retry':session.add_path([(.1,.5),(.9,.5)])
                        session.add_path([(.5,0),(.5,1)])
                        if action=='retry':session.retry_cut(session.preview_cut())
                        else:session.cut()
                    self.assertEqual(len(session.document.patterns),2)
                    restored=Document.loads(session.document.dumps())
                    for piece in restored.patterns:
                        self.assertEqual(piece.mesh_density,density)
                        self.assertEqual(piece.preset,'KNIT')
                        self.assertEqual(piece.wrap_radius,.24)

    def test_final_commit_failure_restores_repairs_history_and_document_identity(self):
        session,crossing,cutter=self.crossing()
        preview=session.preview_cut();session.last_repairs=4
        before=self.state(session);document=session.document
        original_validate=Document.validate
        def fail_live_commit(candidate):
            if candidate is session.document and candidate is not document:
                raise ValueError('Live commit refused')
            return original_validate(candidate)
        with patch.object(Document,'validate',fail_live_commit):
            with self.assertRaisesRegex(ValueError,'Live commit refused'):
                session.retry_cut(preview)
        self.assertEqual(self.state(session),before)
        self.assertIs(session.document,document)
