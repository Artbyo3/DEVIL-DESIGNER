import json
import math
import unittest
from devil_designer.core import Anchor,Document,Session
from devil_designer.construction import chain_range
from devil_designer.density import boundary_plan,effective_spacing
from devil_designer.meshing import edge_counts

try:
    import bpy
except ModuleNotFoundError:
    bpy=None


def density_session():
    session=Session()
    session.add([(0,0),(.3,0),(.3,.4),(0,.4)])
    session.add([(.5,0),(.9,0),(.9,.5),(.5,.5)])
    return session


class DensityTests(unittest.TestCase):
    def setUp(self):
        self.session=density_session()

    def test_named_spacing_and_limits(self):
        pattern=self.session.document.patterns[0]
        for name,multiplier in (('AUTO',1),('COARSE',2),('STANDARD',1),('FINE',.5)):
            pattern.mesh_density=name
            self.assertAlmostEqual(effective_spacing(pattern,.02),.02*multiplier)
        self.assertEqual(effective_spacing(pattern,.003),.003)
        pattern.mesh_density='COARSE'
        self.assertEqual(effective_spacing(pattern,.2),.2)

    def test_invalid_spacing_and_density(self):
        pattern=self.session.document.patterns[0]
        for spacing in (0,.002,.201,math.nan,math.inf):
            with self.subTest(spacing=spacing),self.assertRaises(ValueError):
                effective_spacing(pattern,spacing)
        pattern.mesh_density='UNKNOWN'
        with self.assertRaises(ValueError):
            effective_spacing(pattern,.02)

    def test_density_is_selected_piece_only_and_undoable(self):
        first,second=self.session.document.patterns
        self.assertTrue(self.session.set_mesh_density('FINE'))
        self.assertEqual(first.mesh_density,'AUTO')
        self.assertEqual(second.mesh_density,'FINE')
        self.assertFalse(self.session.set_mesh_density('FINE'))
        self.session.history()
        self.assertEqual(self.session.document.find(second.id).mesh_density,'AUTO')
        self.session.history(redo=True)
        self.assertEqual(self.session.document.find(second.id).mesh_density,'FINE')

    def test_density_rejects_invalid_name_or_selection_without_changes(self):
        before=self.session.document.dumps()
        for name in ('fine','',None,[],{}):
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.session.set_mesh_density(name)
        self.session.selected=None
        with self.assertRaises(ValueError):
            self.session.set_mesh_density('FINE')
        self.assertEqual(before,self.session.document.dumps())

    def test_density_roundtrip_and_legacy_default(self):
        for version in (1,2,3):
            value=json.loads(self.session.document.dumps())
            value['version']=version
            for pattern in value['patterns']:
                pattern.pop('mesh_density')
            loaded=Document.loads(json.dumps(value))
            self.assertTrue(all(pattern.mesh_density=='AUTO' for pattern in loaded.patterns))
        for name in ('AUTO','COARSE','STANDARD','FINE'):
            self.session.set_mesh_density(name)
            loaded=Document.loads(self.session.document.dumps())
            self.assertEqual(loaded.find(self.session.selected).mesh_density,name)

    def test_invalid_saved_density_is_rejected(self):
        for name in ('UNKNOWN',None,[],{}):
            value=json.loads(self.session.document.dumps())
            value['patterns'][0]['mesh_density']=name
            with self.subTest(name=name),self.assertRaises(ValueError):
                Document.loads(json.dumps(value))

    def test_duplicate_preserves_density(self):
        self.session.set_mesh_density('COARSE')
        self.session.duplicate()
        self.assertEqual(self.session.document.find(self.session.selected).mesh_density,'COARSE')

    def test_unset_plan_matches_existing_plan(self):
        document=self.session.document
        expected=edge_counts(document,.02)
        actual=boundary_plan(document,.02)
        self.assertEqual(actual,expected)
        self.assertEqual(actual.samples,expected.samples)
        self.assertEqual(actual.seam_pairs,expected.seam_pairs)

    def test_mixed_density_uses_shared_finest_plan(self):
        document=self.session.document
        first,second=document.patterns
        first.mesh_density='COARSE'
        second.mesh_density='FINE'
        first_edge=document.edge(first.id,1)
        second_edge=document.edge(second.id,3)
        self.session.sew(first_edge,second_edge)
        for reverse in (True,False):
            document.seams[0].reverse=reverse
            plan=boundary_plan(document,.02)
            expected=edge_counts(document,.01)
            self.assertEqual(plan.samples,expected.samples)
            self.assertEqual(plan.seam_pairs,expected.seam_pairs)
            self.assertEqual(plan[first_edge],plan[second_edge])
            for _,pairs in plan.seam_pairs:
                for side in pairs:
                    for edge,fraction in side:
                        self.assertLess(min(abs(fraction-sample) for sample in plan.samples[edge]),1e-8)

    def test_unrelated_coarse_piece_does_not_inherit_fine_boundaries(self):
        document=self.session.document
        first,second=document.patterns
        first.mesh_density='COARSE'
        second.mesh_density='FINE'
        plan=boundary_plan(document,.02)
        for edge in document.edges(first.id):
            self.assertEqual(plan.samples[edge],edge_counts(document,.04).samples[edge])
            self.assertLess(plan[edge],edge_counts(document,.01)[edge])
        for edge in document.edges(second.id):
            self.assertEqual(plan.samples[edge],edge_counts(document,.01).samples[edge])

    def test_finest_boundaries_propagate_only_through_seam_components(self):
        self.session.add([(1,0),(1.3,0),(1.3,.4),(1,.4)])
        self.session.add([(1.5,0),(1.8,0),(1.8,.4),(1.5,.4)])
        document=self.session.document
        first,second,third,unrelated=document.patterns
        first.mesh_density='FINE'
        second.mesh_density=third.mesh_density=unrelated.mesh_density='COARSE'
        self.session.sew(document.edge(first.id,1),document.edge(second.id,3))
        self.session.sew(document.edge(second.id,1),document.edge(third.id,3))
        plan=boundary_plan(document,.02)
        fine=edge_counts(document,.01)
        coarse=edge_counts(document,.04)
        for pattern in (first,second,third):
            for edge in document.edges(pattern.id):
                self.assertEqual(plan.samples[edge],fine.samples[edge])
        for edge in document.edges(unrelated.id):
            self.assertEqual(plan.samples[edge],coarse.samples[edge])
        self.assertEqual(plan.seam_pairs,fine.seam_pairs)

    def test_anchor_binding_roundtrip_and_positional_compatibility(self):
        pattern=self.session.document.patterns[0]
        anchor=Anchor(pattern.id,.1,.1,'TACK',(0,0,0),'stable-anchor')
        self.assertEqual(anchor.id,'stable-anchor')
        self.assertIsNone(anchor.binding)
        binding=dict(version=1,avatar='a'*32,topology='b'*64,vertices=[1,2,3],weights=[.2,.3,.5])
        added=self.session.add_anchor((.6,.1),'TACK',(0,0,0),binding=binding)
        self.assertEqual(added.binding,binding)
        loaded=Document.loads(self.session.document.dumps())
        self.assertEqual(loaded.anchors[0].binding,binding)
        value=json.loads(loaded.dumps())
        value['anchors'][0].pop('binding')
        self.assertIsNone(Document.loads(json.dumps(value)).anchors[0].binding)

    def test_malformed_anchor_binding_is_rejected_by_helper(self):
        from unittest.mock import patch
        for binding in ({},[],True,'invalid'):
            before=self.session.document.dumps()
            with self.subTest(binding=binding),self.assertRaises(ValueError):
                self.session.add_anchor((.6,.1),'TACK',binding=binding)
            self.assertEqual(self.session.document.dumps(),before)
        with patch('devil_designer.tack_binding.validate_binding',side_effect=ValueError('Invalid tack binding.')) as validate:
            with self.assertRaisesRegex(ValueError,'Invalid tack binding'):
                self.session.add_anchor((.6,.1),'TACK',binding={})
            validate.assert_called_once_with({})

    def test_curved_partial_chain_seams_use_existing_finest_plan(self):
        session=Session()
        session.add_ellipse((0,0),(.3,.4))
        first=session.document.patterns[0]
        session.add([(.5,0),(.9,0),(.9,.5),(.5,.5)])
        second=session.document.patterns[1]
        first.mesh_density='FINE'
        second.mesh_density='COARSE'
        document=session.document
        left=chain_range(document,[document.edge(first.id,0)],.1,.9)
        right=[document.edge(second.id,0),document.edge(second.id,1)]
        session.sew_chains(left,right)
        for reverse in (True,False):
            document.seams[0].reverse=reverse
            actual=boundary_plan(document,.02)
            expected=edge_counts(document,.01)
            self.assertEqual(actual.samples,expected.samples)
            self.assertEqual(actual.seam_pairs,expected.seam_pairs)


@unittest.skipUnless(bpy is not None,'Requires Blender')
class BlenderDensityTests(unittest.TestCase):
    def test_mesh_interiors_share_boundary_samples(self):
        from devil_designer.meshing import fabric_mesh
        session=density_session()
        document=session.document
        first,second=document.patterns
        first.mesh_density='COARSE'
        second.mesh_density='FINE'
        session.sew(document.edge(first.id,1),document.edge(second.id,3))
        plan=boundary_plan(document,.04)
        sizes=[]
        for pattern in document.patterns:
            coords,faces,boundaries=fabric_mesh(document,pattern,effective_spacing(pattern,.04),plan)
            self.assertTrue(faces)
            sizes.append(len(coords))
            for edge in document.edges(pattern.id):
                self.assertEqual(len(boundaries[edge.start]),len(plan.samples[edge]))
        self.assertGreater(sizes[1],sizes[0])
        for _,pairs in plan.seam_pairs:
            for side in pairs:
                for edge,fraction in side:
                    samples=plan.outputs[edge.pattern]['samples'][edge.start]
                    self.assertLess(min(abs(fraction-sample) for sample,_ in samples),1e-8)

    def test_panel_resolution_seams_and_rebuild(self):
        import devil_designer
        from devil_designer import garment
        devil_designer.register()
        try:
            scene=bpy.context.scene
            scene.dd_avatar=bpy.data.objects['Cube']
            session=density_session()
            first,second=session.document.patterns
            first.mesh_density='COARSE'
            second.mesh_density='FINE'
            session.sew(session.document.edge(first.id,1),session.document.edge(second.id,3))
            scene.dd_spacing=.04
            scene.dd_document=session.document.dumps()
            panels=garment.build_panels(bpy.context)
            by_id={panel['dd_pattern_id']:panel for panel in panels}
            self.assertGreater(len(by_id[second.id].data.vertices),len(by_id[first.id].data.vertices))
            compiled=garment.compile_garment(bpy.context)
            self.assertTrue(json.loads(compiled['dd_sewing_pairs']))
            session.document=Document.loads(scene.dd_document)
            session.selected=first.id
            session.set_mesh_density('FINE')
            scene.dd_document=session.document.dumps()
            before=len(by_id[first.id].data.vertices)
            garment.compile_garment(bpy.context)
            self.assertGreater(len(by_id[first.id].data.vertices),before)
        finally:
            devil_designer.unregister()


if __name__=='__main__':
    unittest.main()
