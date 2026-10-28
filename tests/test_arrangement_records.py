import copy
import json
import unittest
from devil_designer.core import Document,Session,arrangement_record
from devil_designer.starters import create_tee_starter,create_tank_starter,create_skirt_starter


class ArrangementRecordTests(unittest.TestCase):
    def document(self):
        session=Session()
        session.add([(0,0),(.3,0),(.3,.4),(0,.4)])
        return session.document

    def test_new_designs_default_to_layout_and_roundtrip_portable_deltas(self):
        document=self.document();pattern=document.patterns[0]
        self.assertEqual(pattern.placement_mode,'LAYOUT');self.assertIsNone(pattern.arrangement)
        pattern.arrangement=arrangement_record('chest','back',True)
        pattern.arrangement['translation']=[.01,.02,.03]
        pattern.arrangement['rotation']=[.1,.2,.3]
        payload=document.dumps();loaded=Document.loads(payload)
        self.assertEqual(json.loads(payload)['version'],4)
        self.assertEqual(loaded.dumps(),payload)
        self.assertEqual(set(loaded.patterns[0].arrangement),{'version','volume','point','flat','translation','rotation'})
        self.assertNotIn('dd_arrangement_volumes',payload)

    def test_versions_one_two_three_migrate_to_legacy_without_placement_guess_changes(self):
        for version in (1,2,3):
            payload=json.loads(self.document().dumps());payload['version']=version
            payload['patterns'][0].pop('placement_mode');payload['patterns'][0].pop('arrangement')
            migrated=Document.loads(json.dumps(payload))
            self.assertEqual(migrated.patterns[0].placement_mode,'LEGACY')
            self.assertIsNone(migrated.patterns[0].arrangement)
            self.assertEqual(Document.loads(migrated.dumps()).patterns[0].placement_mode,'LEGACY')

    def test_corrupt_records_are_refused(self):
        valid=arrangement_record('chest','front')
        for key,value in (('version',2),('volume',''),('point',3),('flat',1),('translation',[0,0]),('rotation',[0,float('inf'),0])):
            document=self.document();record=copy.deepcopy(valid);record[key]=value
            document.patterns[0].arrangement=record
            with self.subTest(key=key),self.assertRaises(ValueError):document.validate()

    def test_starters_use_explicit_points_not_name_or_piece_order(self):
        for generator,volume in ((create_tee_starter,'chest'),(create_tank_starter,'chest'),(create_skirt_starter,'waist')):
            document=generator(None)
            self.assertEqual([(pattern.arrangement['volume'],pattern.arrangement['point']) for pattern in document.patterns],[(volume,'front'),(volume,'back')])
            for pattern in document.patterns:pattern.name='Renamed'
            document.patterns.reverse()
            self.assertEqual(Document.loads(document.dumps()).patterns[0].arrangement['point'],'back')

    def test_cut_copies_portable_placement_and_source_origin_transactionally(self):
        for legacy in (False,True):
            session=Session(self.document());pattern=session.document.patterns[0]
            pattern.placement_mode='LEGACY' if legacy else 'LAYOUT'
            if not legacy:pattern.arrangement=arrangement_record('chest','front')
            before=session.document.dumps();session.knife_cut([(-.1,.2),(.4,.2)])
            first,second=session.document.patterns
            self.assertEqual(first.placement_mode,second.placement_mode)
            self.assertEqual(first.arrangement,second.arrangement)
            self.assertEqual(first.panel_origin,second.panel_origin)
            self.assertEqual(first.panel_origin['bounds'],[0,0,.3,.4])
            self.assertIsNot(first.panel_origin,second.panel_origin)
            self.assertEqual(Document.loads(session.document.dumps()).dumps(),session.document.dumps())
            session.history();self.assertEqual(session.document.dumps(),before)
