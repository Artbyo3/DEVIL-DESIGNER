"""Check real evaluated meshes, physical units, deformation, and reference persistence."""
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer.silhouette import BodyReference
from devil_designer.core import contains

def check(ok,message):
    if not ok: raise AssertionError(message)
    print('PASS:',message,flush=True)

devil_designer.register()
scene=bpy.context.scene
mesh=bpy.data.meshes.new('Concave reference fixture')
mesh.from_pydata([(0,0,0),(2,0,0),(2,0,1),(1,0,1),(1,0,3),(0,0,3),(0,0,1)],[],
                 [(0,1,2,3,6),(6,3,4,5)])
body=bpy.data.objects.new('Reference body',mesh)
scene.collection.objects.link(body)
body.location=(6,-4,9)
body.scale=(2,.5,1.5)
scene.dd_avatar=body
bpy.context.view_layer.update()
original=[tuple(v.co) for v in mesh.vertices]
reference=BodyReference()
check(reference.refresh(bpy.context),'body selected and projected')
check(not reference.error and bool(reference.triangles),'evaluated body has drawable reference geometry')
check(abs(reference.bounds[1][1]-4.5)<1e-5,'body height preserves nonuniform object scale')
check(abs(reference.bounds[1][0]-reference.bounds[0][0]-4)<1e-5,'body width preserves object scale')
empty=(1,3)
check(not any(contains(empty,[reference.vertices[i] for i in tri]) for tri in reference.triangles),
      'projection keeps concave gaps empty')
revision=reference.revision
check(not reference.refresh(bpy.context) and reference.revision==revision,'unchanged geometry reuses reference cache')
body.scale.z=2
bpy.context.view_layer.update()
check(reference.refresh(bpy.context),'object transform change invalidates reference')
check(abs(reference.bounds[1][1]-6)<1e-5,'changed transform updates height')
basis=body.shape_key_add(name='Basis')
shape=body.shape_key_add(name='Taller')
for v in shape.data:
    v.co.z*=1.5
shape.value=1
bpy.context.view_layer.update()
check(reference.refresh(bpy.context),'shape-key change invalidates reference')
check(abs(reference.bounds[1][1]-9)<1e-5,'silhouette uses deformed evaluated geometry')
scene.unit_settings.scale_length=.01
reference.refresh(bpy.context)
check(abs(reference.bounds[1][1]-.09)<1e-5,'scene unit scale converts projection to metres')
check([tuple(v.co) for v in mesh.vertices]==original,'reference extraction does not change avatar source mesh')
armature=bpy.data.armatures.new('Reference rig')
rig=bpy.data.objects.new('Reference rig',armature)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bone=armature.edit_bones.new('Body')
bone.head=(0,0,0)
bone.tail=(0,0,1)
bpy.ops.object.mode_set(mode='OBJECT')
group=body.vertex_groups.new(name='Body')
group.add(list(range(len(mesh.vertices))),1,'REPLACE')
modifier=body.modifiers.new('Body deformation','ARMATURE')
modifier.object=rig
bpy.context.view_layer.update()
reference.refresh(bpy.context,force=True)
width=reference.bounds[1][0]-reference.bounds[0][0]
rig.pose.bones['Body'].scale.x=1.5
bpy.context.view_layer.update()
check(reference.refresh(bpy.context),'armature pose change invalidates reference')
check(reference.bounds[1][0]-reference.bounds[0][0]>width*1.4,'reference follows the evaluated armature deformation')
scene.dd_reference_view='RIGHT'
reference.refresh(bpy.context)
check(reference.bounds[1][0]-reference.bounds[0][0]<1e-5,'side view projects depth instead of front width')
scene.dd_avatar=None
reference.refresh(bpy.context)
check(not reference.vertices and not reference.triangles,'clearing avatar removes old reference')
scene.dd_avatar=body
scene.dd_reference_x=.12
scene.dd_reference_y=-.35
scene.dd_reference_opacity=.3
scene.dd_reference_placed=True
path=ROOT/'build'/'silhouette-test.blend'
path.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
check(abs(bpy.context.scene.dd_reference_x-.12)<1e-6 and abs(bpy.context.scene.dd_reference_y+.35)<1e-6,
      'reference position survives save/reopen')
check(abs(bpy.context.scene.dd_reference_opacity-.3)<1e-6 and bpy.context.scene.dd_reference_view=='RIGHT',
      'reference opacity and view survive save/reopen')
devil_designer.unregister()
check(not hasattr(bpy.types.Scene,'dd_reference_visible'),'reference properties unregister cleanly')
print('ALL SILHOUETTE CHECKS PASSED')
