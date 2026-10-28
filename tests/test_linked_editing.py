import copy
import json
import unittest

from devil_designer import history
from devil_designer.core import Document,Session,Vertex,arrangement_record
from devil_designer.linked_editing import clone_twin,pair_for,toggle_link


class LinkedEditingTests(unittest.TestCase):
    def paired(self,curved=False):
        session=Session()
        if curved:session.add_ellipse((0,0),(.4,.5))
        else:session.add([(0,0),(.4,0),(.4,.5),(0,.5)])
        source=session.selected
        target=clone_twin(session).id
        return session,source,target

    def assert_mirrored(self,session):
        document=session.document;pair=document.linked_pairs[0]
        source,target=[document.find(member) for member in pair['members']]
        horizontal,vertical=pair['transform']
        for first,second in zip(source.loops(),target.loops()):
            self.assertEqual(first[2:],second[2:])
            self.assertEqual(len(first[1]),len(second[1]))
            for original,twin in zip(first[1],second[1]):
                self.assertEqual(pair['mapping'][original.id],twin.id)
                self.assertAlmostEqual(twin.x,horizontal-original.x)
                self.assertAlmostEqual(twin.y,original.y+vertical)
                self.assertEqual(original.point_type,twin.point_type)
                for key in ('incoming','outgoing'):
                    handle=getattr(original,key);other=getattr(twin,key)
                    if handle is None:self.assertIsNone(other)
                    else:
                        self.assertAlmostEqual(other[0],-handle[0])
                        self.assertAlmostEqual(other[1],handle[1])
        document.validate()

    def test_clone_is_explicit_mirrored_separate_and_one_undo_step(self):
        session=Session();session.add([(0,0),(.4,0),(.3,.5),(0,.5)])
        source=session.document.patterns[0];before=session.document.dumps();count=len(session.undo_stack)
        twin=clone_twin(session)
        self.assertEqual(twin.name,source.name+' twin')
        self.assertGreater(min(point[0] for point in twin.outline()),max(point[0] for point in source.outline()))
        self.assertIsNone(twin.arrangement);self.assertFalse(session.document.seams)
        self.assertEqual(len(session.undo_stack),count+1);self.assert_mirrored(session)
        after=session.document.dumps();self.assertTrue(session.history())
        self.assertEqual(session.document.dumps(),before);self.assertTrue(session.history(True))
        self.assertEqual(session.document.dumps(),after)

    def test_every_edit_type_mirrors_from_either_member(self):
        for index in (0,1):
            for operation in ('move','point_drag','handle','type','split','add','merge','delete','length','position'):
                with self.subTest(member=index,operation=operation):
                    session,source,target=self.paired()
                    session.selected=(source,target)[index];piece=session.document.find(session.selected)
                    if operation=='move':
                        points=piece.points;points[1]=(points[1][0]+.02,points[1][1]+.015);session.move(points)
                    elif operation=='point_drag':
                        session.corner=1;session.selected_patterns.clear();session.move_selection(.02,.015)
                    elif operation=='handle':session.set_handle(1,'outgoing',(.01,.03))
                    elif operation=='type':session.set_point_type('SMOOTH',[(piece.id,'OUTER',1)])
                    elif operation=='split':session.split_segment(session.document.edge(piece.id,0),.3)
                    elif operation=='add':
                        start,end=piece.vertices[:2]
                        session.commit(lambda:piece.vertices.insert(1,Vertex((start.x+end.x)/2,(start.y+end.y)/2)))
                    elif operation=='merge':session.merge_points([0,1])
                    elif operation=='delete':session.corner=1;session.delete()
                    elif operation=='length':session.set_length(session.document.edge(piece.id,0),.38)
                    else:
                        points=piece.points;points[1]=(points[1][0]-.01,.02);session.move(points)
                    self.assert_mirrored(session)

    def test_curved_split_preserves_both_sewing_chains(self):
        for index in (0,1):
            with self.subTest(member=index):
                session,source,target=self.paired(True)
                session.sew(session.document.edge(source,0),session.document.edge(target,0))
                seam_id=session.document.seams[0].id
                session.selected=(source,target)[index]
                session.split_segment(session.document.edge(session.selected,0),.3)
                self.assertEqual([seam.id for seam in session.document.seams],[seam_id])
                self.assertEqual([len(session.document.seams[0].side(side)) for side in (0,1)],[2,2])
                self.assert_mirrored(session)

    def test_internal_paths_and_handles_mirror(self):
        session,source,target=self.paired()
        for identity in (source,target):
            session.selected=identity
            piece=session.document.find(identity)
            low=min(point[0] for point in piece.points)
            session.add_path([(low+.1,.1),(low+.2,.2)])
            self.assert_mirrored(session)
            session.set_handle(0,'outgoing',(.01,.02))
            self.assert_mirrored(session)
            session.split_segment(session.document.edge(identity,0,session.path),.4)
            self.assert_mirrored(session)
            session.path='OUTER'

    def test_unlink_changes_only_enabled_flag_and_relink_uses_selected(self):
        for index in (0,1):
            with self.subTest(member=index):
                session,source,target=self.paired();session.selected=(source,target)[index]
                expected=json.loads(session.document.dumps());expected['linked_pairs'][0]['enabled']=False
                toggle_link(session);self.assertEqual(json.loads(session.document.dumps()),expected)
                piece=session.document.find(session.selected);other=session.document.find((target,source)[index]);unchanged=copy.deepcopy(other.points)
                points=piece.points;points[1]=(points[1][0]-.01,.03);session.move(points)
                self.assertEqual(other.points,unchanged)
                toggle_link(session);self.assert_mirrored(session)
                session.history();self.assertFalse(session.document.linked_pairs[0]['enabled'])
                session.history(True);self.assert_mirrored(session)

    def test_link_existing_pieces_uses_active_outline_and_no_sewing_changes(self):
        session=Session();session.add([(0,0),(.4,0),(.4,.5),(0,.5)]);source=session.selected
        session.add([(1,0),(1.3,0),(1.4,.4),(1,.4)]);target=session.selected
        session.sew(session.document.edge(source,0),session.document.edge(target,0))
        seams=copy.deepcopy(session.document.seams)
        session.selected=source;session.selected_patterns={source,target}
        toggle_link(session);self.assertEqual(session.document.seams,seams);self.assert_mirrored(session)
        toggle_link(session);toggle_link(session);self.assertEqual(session.document.seams,seams)

    def test_incompatible_relink_preserves_existing_sewing_atomically(self):
        session,source,target=self.paired();toggle_link(session)
        session.selected=source;session.corner=1;session.delete()
        session.sew(session.document.edge(source,0),session.document.edge(target,0))
        before=session.document.dumps()
        with self.assertRaisesRegex(ValueError,'existing sewing'):toggle_link(session)
        self.assertEqual(session.document.dumps(),before)

    def test_deleting_member_clears_pair_and_undo_restores_it(self):
        session,source,target=self.paired();before=session.document.dumps()
        session.selected=target;session.delete()
        self.assertIsNone(pair_for(session.document,source));self.assertEqual(len(session.document.patterns),1)
        session.history();self.assertEqual(session.document.dumps(),before);self.assert_mirrored(session)

    def test_duplicate_single_is_independent_and_duplicate_pair_is_a_new_pair(self):
        session,source,target=self.paired();session.selected=target;session.duplicate()
        self.assertIsNone(pair_for(session.document,session.selected));self.assertEqual(len(session.document.linked_pairs),1)
        session.selected=source;session.selected_patterns={source,target};session.duplicate()
        self.assertEqual(len(session.document.linked_pairs),2)
        duplicated=pair_for(session.document,session.selected)
        self.assertEqual(set(duplicated['members']),session.selected_patterns)
        piece=session.document.find(session.selected);points=piece.points;points[1]=(points[1][0]+.01,.02);session.move(points)
        self.assertNotEqual(duplicated['members'],[source,target]);session.document.validate()

    def test_mirror_keeps_original_link_and_only_explicit_mirror_sewing(self):
        session,source,target=self.paired();session.selected=source
        session.unfold(session.document.edge(source,1),True)
        self.assertEqual(len(session.document.linked_pairs),1)
        self.assertEqual(pair_for(session.document,target)['members'],[source,target])
        self.assertIsNone(pair_for(session.document,session.selected))
        self.assertEqual(len(session.document.seams),1)

    def test_layout_translation_is_independent_and_later_edits_still_mirror(self):
        session,source,target=self.paired();original=copy.deepcopy(session.document.find(source).points)
        session.selected=target;session.move_selection(.2,.1)
        self.assertEqual(session.document.find(source).points,original);self.assert_mirrored(session)
        piece=session.document.find(target);points=piece.points;points[1]=(points[1][0]-.01,points[1][1]+.02)
        session.move(points);self.assert_mirrored(session)

    def test_clone_as_back_records_same_volume_and_resets_deltas(self):
        session=Session();session.add([(0,0),(.4,0),(.4,.5),(0,.5)])
        piece=session.document.find(session.selected);piece.arrangement=arrangement_record('chest','front',True)
        piece.arrangement['translation']=[.1,.2,.3]
        target=clone_twin(session,True)
        self.assertEqual(target.arrangement,arrangement_record('chest','back',True));self.assert_mirrored(session)

    def test_clone_as_back_unarranged_falls_back_to_layout(self):
        session=Session();session.add([(0,0),(.4,0),(.4,.5),(0,.5)])
        self.assertIsNone(clone_twin(session,True).arrangement)

    def test_no_automatic_twins_or_cloned_sewing(self):
        session=Session();session.add([(0,0),(.4,0),(.4,.5),(0,.5)]);source=session.selected
        session.add([(1,0),(1.4,0),(1.4,.5),(1,.5)]);target=session.selected
        self.assertFalse(session.document.linked_pairs)
        session.sew(session.document.edge(source,0),session.document.edge(target,0));seams=copy.deepcopy(session.document.seams)
        session.selected=source;clone_twin(session)
        self.assertEqual(session.document.seams,seams)

    def test_roundtrip_and_persistent_undo_restore_links(self):
        session,source,target=self.paired();stored=session.document.dumps();saved=history.store(session)
        reopened=Session(Document.loads(stored));self.assertTrue(history.restore(reopened,saved))
        self.assertEqual(reopened.document.dumps(),stored);self.assert_mirrored(reopened)
        reopened.history();self.assertIsNone(reopened.document.find(target));self.assertFalse(reopened.document.linked_pairs)
        reopened.history(True);self.assertEqual(reopened.document.dumps(),stored)
        reopened.selected=source;reopened.set_length(reopened.document.edge(source,0),.38);self.assert_mirrored(reopened)

    def test_older_documents_load_without_links_or_changed_patterns(self):
        session=Session();session.add([(0,0),(.4,0),(.4,.5),(0,.5)])
        for version in (1,2,3,4):
            data=json.loads(session.document.dumps());data['version']=version;data.pop('linked_pairs',None)
            loaded=Document.loads(json.dumps(data))
            self.assertFalse(loaded.linked_pairs);self.assertEqual(loaded.patterns[0].points,session.document.patterns[0].points)

    def test_invalid_link_records_are_rejected(self):
        session,source,target=self.paired();data=json.loads(session.document.dumps())
        for replacement in (None,{},[{}],[dict(data['linked_pairs'][0],members=[source,source])],
                            [dict(data['linked_pairs'][0],members=[source,'missing'])],
                            [dict(data['linked_pairs'][0],enabled='yes')],
                            [dict(data['linked_pairs'][0],mapping={'a':target,'b':target})]):
            with self.subTest(record=replacement):
                invalid=dict(data,linked_pairs=replacement)
                with self.assertRaises(ValueError):Document.loads(json.dumps(invalid))

    def test_third_member_is_refused_and_invalid_edit_rolls_back_both(self):
        session,source,target=self.paired();before=session.document.dumps()
        with self.assertRaisesRegex(ValueError,'already has a twin'):clone_twin(session)
        self.assertEqual(session.document.dumps(),before)
        session.selected=source;session.selected_points={(source,'OUTER',index) for index in range(4)}
        with self.assertRaises(ValueError):session.delete()
        self.assertEqual(session.document.dumps(),before)

    def test_unlinked_piece_can_form_a_different_pair_or_clone(self):
        for operation in ('clone','link'):
            with self.subTest(operation=operation):
                session,source,target=self.paired();toggle_link(session);session.selected=source
                before=session.document.dumps()
                if operation=='clone':replacement=clone_twin(session).id
                else:
                    session.add([(1,0),(1.4,0),(1.4,.5),(1,.5)]);replacement=session.selected
                    session.selected=source;session.selected_patterns={source,replacement};before=session.document.dumps()
                    toggle_link(session)
                self.assertEqual(len(session.document.linked_pairs),1)
                self.assertIsNone(pair_for(session.document,target))
                self.assertEqual(set(pair_for(session.document,source)['members']),{source,replacement})
                self.assert_mirrored(session)
                session.history();self.assertEqual(session.document.dumps(),before)
