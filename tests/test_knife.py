import copy
import math
import unittest
from unittest.mock import patch

from devil_designer.core import Document,Session,Seam,area


class KnifeTests(unittest.TestCase):
    def square(self):
        session=Session()
        session.add([(0,0),(1,0),(1,1),(0,1)])
        session.document.patterns[0].name='Front'
        return session

    def state(self,session):
        return (session.document.dumps(),copy.deepcopy(session.get_selection_state()),
                list(session.undo_stack),list(session.redo_stack),
                copy.deepcopy(session._undo_selections),copy.deepcopy(session._redo_selections),session.last_repairs)

    def assert_unchanged_failure(self,session,points,message):
        before=self.state(session);document=session.document
        with self.assertRaisesRegex(ValueError,message):session.knife_cut(points)
        self.assertEqual(self.state(session),before)
        self.assertIs(session.document,document)

    def test_horizontal_diagonal_vertical_and_multi_point(self):
        for points in ([(-1,.5),(2,.5)],[(-1,-.2),(2,1.2)],[(.5,-1),(.5,2)],
                       [(-1,.2),(.3,.2),(.6,.7),(2,.7)],[(0,.5),(1,.5)],
                       [(-1,-1),(0,0),(.5,.5),(1,1),(2,2)]):
            with self.subTest(points=points):
                session=self.square();session.knife_cut(points)
                self.assertEqual([piece.name for piece in session.document.patterns],['Front 1','Front 2'])
                self.assertAlmostEqual(sum(abs(area(piece.outline())) for piece in session.document.patterns),1)
                self.assertEqual(len(session.document.seams),1)
                seam=session.document.seams[0]
                self.assertAlmostEqual(session.document.seam_stats(seam)[2],0)
                first=session.document.chain_position(seam.side(0),.25)
                second=session.document.chain_position(seam.side(1),.75)
                self.assertLess(math.dist(session.document.edge_point(*first),session.document.edge_point(*second)),1e-7)
                session.document.validate()

    def test_cut_only_and_removable_cut_seam(self):
        session=self.square();session.knife_cut([(-1,.5),(2,.5)],False)
        self.assertFalse(session.document.seams)
        session=self.square();session.knife_cut([(-1,.5),(2,.5)])
        session.remove_seam(session.document.seams[0].id)
        self.assertFalse(session.document.seams)
        self.assertEqual(len(session.document.patterns),2)

    def test_attributes_and_uv_positions_are_preserved_without_repack_or_overlap(self):
        for layout in (None,dict(origin=[-2,-3],scale=7)):
            session=self.square();original=session.document.patterns[0]
            original.preset='SILK';original.fabric_override=True;original.mesh_density='FINE';original.wrap_radius=.3
            session.document.uv_layout=copy.deepcopy(layout)
            session.knife_cut([(-1,.4),(.3,.4),(.7,.6),(2,.6)])
            self.assertEqual(session.document.uv_layout,layout or dict(origin=[0,0],scale=1))
            for piece in session.document.patterns:
                self.assertEqual((piece.preset,piece.fabric_override,piece.mesh_density,piece.wrap_radius),('SILK',True,'FINE',.3))
                self.assertTrue(all(-1e-8<=value<=1+1e-8 for point in piece.points for value in point))
            for column in range(1,20):
                for row in range(1,20):
                    point=(column/20,row/20)
                    if any(abs(point[1]-height)<1e-7 for height in (.4,.6)) or abs(point[1]-(.4+(point[0]-.3)/2))<1e-7:continue
                    self.assertEqual(sum(piece.contains(point) for piece in session.document.patterns),1)

    def test_selected_pieces_and_unselected_fully_crossed_pieces(self):
        for selected in (True,False):
            session=self.square();first=session.selected
            session.add([(2,0),(3,0),(3,1),(2,1)]);second=session.selected
            session.add([(4,0),(5,0),(5,1),(4,1)]);untouched=session.selected
            untouched_name=session.document.find(untouched).name
            session.clear_selection()
            if selected:session.selected_patterns={first,second};session._selected=first
            session.knife_cut([(-1,.5),(3.5,.5)])
            self.assertEqual(len(session.document.patterns),5)
            self.assertEqual(session.document.find(untouched).name,untouched_name)
            self.assertEqual(len(session.document.seams),2)

    def test_unselected_partial_piece_is_not_cut(self):
        session=self.square()
        session.add([(2,0),(3,0),(3,1),(2,1)]);partial=session.selected
        session.clear_selection();session.knife_cut([(-1,.5),(2.5,.5)])
        self.assertEqual(len(session.document.patterns),3)
        self.assertEqual(session.document.find(partial).points,[(2,0),(3,0),(3,1),(2,1)])

    def test_failed_second_target_is_atomic(self):
        session=self.square();first=session.selected
        session.add([(2,0),(3,0),(3,1),(2,1)]);second=session.selected
        session.add_path([(2.5,.1),(2.5,.9)])
        session.selected_patterns={first,second};session._selected=first
        self.assert_unchanged_failure(session,[(-1,.5),(4,.5)],'crosses another internal shape')

    def test_wrong_crossing_counts_and_tangencies_are_atomic(self):
        for points in ([(-1,.2),(-.5,.2)],[(-1,.5),(.5,.5)],[(.1,.1),(.9,.9)],
                       [(-1,0),(2,0)],[(-1,1),(0,1),(-1,2)],[(.5,-1),(.5,.5),(.5,-1)]):
            with self.subTest(points=points):
                self.assert_unchanged_failure(self.square(),points,'cross|overlap|distinct|touch')
        session=Session();session.add([(0,0),(3,0),(3,3),(2,3),(2,1),(1,1),(1,3),(0,3)])
        self.assertEqual(len(session.knife_preview([(-1,2),(4,2)])[0]['hits']),4)
        self.assert_unchanged_failure(session,[(-1,2),(4,2)],'exactly twice; found 4')

    def test_one_undo_step_and_redo_restore_entire_operation(self):
        session=self.square();before=session.document.dumps();selection=session.get_selection_state()
        undo_count=len(session.undo_stack)
        session.knife_cut([(-1,.5),(.5,.4),(2,.5)])
        after=session.document.dumps();after_selection=session.get_selection_state()
        self.assertEqual(len(session.undo_stack),undo_count+1)
        session.history();self.assertEqual(session.document.dumps(),before)
        self.assertEqual(session.get_selection_state(),selection)
        session.history(True);self.assertEqual(session.document.dumps(),after)
        self.assertEqual(session.get_selection_state(),after_selection)

    def test_outer_sewing_ranges_survive_both_halves_and_split_edges(self):
        session=self.square();original=session.selected
        session.add([(2,0),(3,0),(3,1),(2,1)]);partner=session.selected
        session.document.seams=[Seam(session.document.edge(original,index),session.document.edge(partner,index)) for index in (0,1,2)]
        identifiers={seam.id for seam in session.document.seams}
        session.selected=original
        session.knife_cut([(-1,.4),(1.5,.4)])
        self.assertTrue(identifiers.issubset({seam.id for seam in session.document.seams}))
        self.assertEqual(session.last_repairs,0)
        session.document.validate()
        for seam in session.document.seams:
            if seam.id in identifiers:self.assertAlmostEqual(session.document.seam_stats(seam)[2],0)

    def test_curved_outline_and_preview_leave_document_unchanged(self):
        session=Session();session.add_ellipse((0,0),(1,1))
        before=self.state(session)
        preview=session.knife_preview([(-1,.37),(2,.37)])
        self.assertFalse(preview[0]['reason']);self.assertEqual(len(preview[0]['hits']),2)
        self.assertEqual(self.state(session),before)
        session.knife_cut([(-1,.37),(2,.37)])
        self.assertEqual(len(session.document.patterns),2)
        self.assertEqual(len(session.document.seams),1)
        session.document.validate()

    def test_reuses_existing_cut_and_propagates_repairs(self):
        session=self.square();original_cut=Session.cut
        with patch.object(Session,'cut',autospec=True,side_effect=original_cut) as existing_cut:
            session.knife_cut([(-1,.5),(2,.5)])
        self.assertEqual(existing_cut.call_count,1)

    def test_late_failure_preserves_history_and_selection(self):
        session=self.square();original_cut=Session.cut
        session.corner=0;session.last_repairs=3
        before=self.state(session)
        def fail_after_cut(staged):
            original_cut(staged)
            raise ValueError('Simulated cut failure')
        with patch.object(Session,'cut',fail_after_cut),self.assertRaisesRegex(ValueError,'Simulated'):
            session.knife_cut([(-1,.5),(2,.5)])
        self.assertEqual(self.state(session),before)

    def test_holes_slits_and_internal_cuts_keep_existing_behavior(self):
        for closed,points,role in ((True,[(.2,.2),(.4,.2),(.3,.4)],'HOLE'),
                                   (False,[(.2,.2),(.4,.3)],'SLIT')):
            session=self.square();path=session.add_path(points,closed);session.cut()
            self.assertEqual(session.document.find(session.selected).path(path.id).role,role)
        session=self.square();session.add_path([(0,.5),(1,.5)]);session.cut()
        self.assertEqual(len(session.document.patterns),2)
        self.assertFalse(session.document.seams)

    def test_knife_refuses_holes_and_preserves_non_crossing_internal_paths(self):
        session=self.square();session.add_path([(.3,.3),(.7,.3),(.7,.7),(.3,.7)],True);session.cut()
        self.assert_unchanged_failure(session,[(-1,.5),(2,.5)],'holes|touch')
        session=self.square();path=session.add_path([(.1,.2),(.9,.2)])
        session.knife_cut([(-1,.5),(2,.5)])
        self.assertEqual(sum(path.id==internal.id for piece in session.document.patterns for internal in piece.paths),1)

    def test_older_designs_load_without_schema_change(self):
        from test_meshing_regression import LEGACY_DESIGN_JSON
        legacy=Document.loads(LEGACY_DESIGN_JSON)
        before=legacy.dumps();session=Session(legacy)
        session.knife_preview([(-1,100),(2,100)])
        self.assertEqual(legacy.dumps(),before)
        self.assertEqual(Document.loads(before).dumps(),before)
