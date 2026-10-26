from pathlib import Path
from types import SimpleNamespace
import json
import math
import sys
import unittest
import bpy
from mathutils import Vector

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import devil_designer
from devil_designer import garment,tack_binding
from devil_designer.core import Session,Document
from devil_designer.native_features import add_anchors


class TackDeformationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        devil_designer.register()

    def setUp(self):
        self.existing=set(bpy.data.objects)
        mesh=bpy.data.meshes.new('Tack test body')
        mesh.from_pydata([(0,0,0),(2,0,0),(0,2,0),(20,20,20)],[],[(0,1,2)])
        self.body=bpy.data.objects.new('Tack test body',mesh)
        bpy.context.collection.objects.link(self.body)
        bpy.context.scene.dd_avatar=self.body
        bpy.context.view_layer.update()

    def tearDown(self):
        for obj in list(bpy.data.objects):
            if obj not in self.existing:
                bpy.data.objects.remove(obj,do_unlink=True)

    def target(self,point=(.6,1,0)):
        binding=tack_binding.bind_target(bpy.context,self.body,point)
        target=tack_binding.create_target(bpy.context,self.body,binding,bpy.context.collection,garment.tag)
        bpy.context.view_layer.update()
        return binding,target

    def expected(self,binding):
        evaluated=self.body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return sum((evaluated.matrix_world @ evaluated.data.vertices[index].co*weight for index,weight in zip(binding['vertices'],binding['weights'])),Vector())

    def assert_follows(self,binding,target):
        bpy.context.view_layer.update()
        position=target.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation
        self.assertLess((position-self.expected(binding)).length,1e-5)

    def test_barycentric_target_and_shape_key_pose(self):
        binding,target=self.target()
        self.assert_follows(binding,target)
        self.assertLess((target.matrix_world.translation-Vector((.6,1,0))).length,1e-5)
        self.body.shape_key_add(name='Basis')
        pose=self.body.shape_key_add(name='Pose')
        pose.data[1].co+=Vector((0,0,2))
        pose.data[2].co+=Vector((0,0,-1))
        pose.data[3].co+=Vector((100,200,300))
        pose.value=1
        self.assert_follows(binding,target)
        self.assertAlmostEqual(target.matrix_world.translation.z,.1,places=5)
        self.assertFalse(any(constraint.type=='SHRINKWRAP' for constraint in target.constraints))

    def test_object_transform_and_vertex_binding(self):
        self.body.location=(3,-4,2)
        self.body.scale=(2,.5,3)
        self.body.rotation_euler.z=.7
        bpy.context.view_layer.update()
        point=self.body.matrix_world @ Vector((0,0,0))
        binding,target=self.target(point)
        self.assert_follows(binding,target)
        self.body.location=(-7,5,3)
        self.body.rotation_euler.y=.4
        self.assert_follows(binding,target)

    def test_armature_pose_and_animation(self):
        armature=bpy.data.armatures.new('Tack test rig')
        rig=bpy.data.objects.new('Tack test rig',armature)
        bpy.context.collection.objects.link(rig)
        bpy.context.view_layer.objects.active=rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bone=armature.edit_bones.new('Attach')
        bone.head=(0,0,0)
        bone.tail=(0,2,0)
        bpy.ops.object.mode_set(mode='OBJECT')
        group=self.body.vertex_groups.new(name='Attach')
        group.add([0,1,2],1,'REPLACE')
        modifier=self.body.modifiers.new('Pose','ARMATURE')
        modifier.object=rig
        bpy.context.view_layer.update()
        binding,target=self.target()
        pose=rig.pose.bones['Attach']
        pose.rotation_mode='XYZ'
        pose.rotation_euler.x=0
        pose.keyframe_insert('rotation_euler',frame=1)
        pose.rotation_euler.x=math.pi/2
        pose.keyframe_insert('rotation_euler',frame=10)
        for frame in (1,5,10,1,10):
            bpy.context.scene.frame_set(frame)
            self.assert_follows(binding,target)

    def test_legacy_migration_is_atomic_and_does_not_persist_scene(self):
        anchor=SimpleNamespace(kind='TACK',target=(.03,.05,0),binding=None)
        bad=SimpleNamespace(kind='TACK',target=None,binding=None)
        document=SimpleNamespace(anchors=[anchor,bad])
        before=bpy.context.scene.dd_document
        with self.assertRaises(ValueError):
            tack_binding.migrate_anchors(bpy.context,document)
        self.assertIsNone(anchor.binding)
        document.anchors.pop()
        self.assertTrue(tack_binding.migrate_anchors(bpy.context,document))
        original=json.dumps(anchor.binding,sort_keys=True)
        self.body.data.vertices[3].co*=10
        self.body.data.update()
        bpy.context.view_layer.update()
        self.assertFalse(tack_binding.migrate_anchors(bpy.context,document))
        self.assertEqual(original,json.dumps(anchor.binding,sort_keys=True))
        self.assertEqual(before,bpy.context.scene.dd_document)

    def test_session_migration_roundtrip_and_undo(self):
        session=Session()
        session.add([(0,0),(1,0),(1,1),(0,1)])
        session.add_anchor((.3,.4),'TACK',(.03,.05,0))
        legacy=session.document.dumps()
        self.assertTrue(session.commit(lambda:tack_binding.migrate_anchors(bpy.context,session.document)))
        bound=session.document.dumps()
        self.assertEqual(bound,Document.loads(bound).dumps())
        self.assertIsNotNone(session.document.anchors[0].binding)
        self.assertTrue(session.history())
        self.assertEqual(session.document.dumps(),legacy)
        self.assertTrue(session.history(True))
        self.assertEqual(session.document.dumps(),bound)
        self.assertFalse(session.commit(lambda:tack_binding.migrate_anchors(bpy.context,session.document)))

    def test_topology_changes_fail_without_rebinding(self):
        binding,target=self.target()
        anchor=SimpleNamespace(binding=binding,target=(.03,.05,0))
        self.body.data.polygons[0].vertices=(0,2,1)
        self.body.data.update()
        bpy.context.view_layer.update()
        with self.assertRaisesRegex(ValueError,'topology changed'):
            tack_binding.resolve_binding(bpy.context,self.body,anchor)
        self.assertIs(anchor.binding,binding)

    def test_topology_changing_modifier_fails(self):
        self.body.modifiers.new('Unsafe topology','SUBSURF')
        bpy.context.view_layer.update()
        with self.assertRaisesRegex(ValueError,'stable avatar topology'):
            tack_binding.bind_target(bpy.context,self.body,(.6,1,0))

    def test_binding_on_posed_avatar_uses_evaluated_surface(self):
        self.body.shape_key_add(name='Basis')
        pose=self.body.shape_key_add(name='Pose')
        for index in (0,1,2):
            pose.data[index].co.z=3
        pose.value=1
        bpy.context.view_layer.update()
        binding,target=self.target((.6,1,3))
        self.assert_follows(binding,target)
        self.assertAlmostEqual(target.matrix_world.translation.z,3,places=5)
        pose.value=0
        self.assert_follows(binding,target)
        self.assertAlmostEqual(target.matrix_world.translation.z,0,places=5)

    def test_native_hook_follows_target_and_cleanup_removes_helpers(self):
        binding=tack_binding.bind_target(bpy.context,self.body,(.6,1,0))
        mesh=bpy.data.meshes.new('Tacked fabric')
        mesh.from_pydata([(8,7,6)],[],[])
        fabric=bpy.data.objects.new('Tacked fabric',mesh)
        bpy.context.collection.objects.link(fabric)
        anchor=SimpleNamespace(id='tack',kind='TACK',target=None,binding=binding)
        cloth=SimpleNamespace(settings=SimpleNamespace())
        before=bpy.context.scene.dd_document
        add_anchors(bpy.context,fabric,cloth,SimpleNamespace(anchors=[anchor]),{'tack':0})
        self.assertEqual(before,bpy.context.scene.dd_document)
        hook=next(modifier for modifier in fabric.modifiers if modifier.type=='HOOK')
        self.body.shape_key_add(name='Basis')
        pose=self.body.shape_key_add(name='Pose')
        pose.data[1].co.z=4
        for value in (0,.5,1):
            pose.value=value
            self.assert_follows(binding,hook.object)
            evaluated=fabric.evaluated_get(bpy.context.evaluated_depsgraph_get())
            self.assertLess((evaluated.matrix_world @ evaluated.data.vertices[0].co-self.expected(binding)).length,1e-5)
        self.assertTrue(cloth.settings.vertex_group_mass)
        generated=garment.generated(bpy.context.scene,'anchor')
        self.assertGreater(len(generated),1)
        self.assertEqual(sum('dd_tack_binding' in obj for obj in generated),1)
        names=[obj.name for obj in generated]
        garment.reset(bpy.context)
        self.assertTrue(all(name not in bpy.data.objects for name in names))

    def test_replacement_avatar_migrates_legacy_target(self):
        binding,target=self.target()
        anchor=SimpleNamespace(kind='TACK',target=(.03,.05,0),binding=binding)
        replacement=bpy.data.objects.new('Replacement avatar',self.body.data.copy())
        bpy.context.collection.objects.link(replacement)
        replacement.location=(4,5,6)
        bpy.context.view_layer.update()
        migrated=tack_binding.resolve_binding(bpy.context,replacement,anchor)
        self.assertNotEqual(migrated['avatar'],binding['avatar'])
        self.assertEqual(migrated['topology'],binding['topology'])
        self.assertIs(anchor.binding,binding)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TackDeformationTests))
    if not result.wasSuccessful():
        raise RuntimeError('Tack binding regression tests failed.')
