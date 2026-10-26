"""Actual Blender checks for curved/holed fabric, slits, M:N sewing, anchors, UVs, presets and refits."""
from pathlib import Path
import sys,json,math
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer.core import Session,Document,area
from devil_designer import garment,library
from devil_designer.meshing import edge_counts,fabric_mesh

seen=set()
def check(ok,message):
    if not ok:raise AssertionError(message)
    if message not in seen:
        print('PASS:',message,flush=True);seen.add(message)

devil_designer.register()
scene=bpy.context.scene
scene.dd_library_dir=str(ROOT/'build'/'test-library')
scene.dd_spacing=.04
s=Session();s.add_ellipse((0,0),(.6,.8));first=s.document.find(s.selected)
s.add_ellipse((.2,.3),(.4,.5),True);s.cut()
s.add_path([(.15,.2),(.45,.25)]);s.cut()
s.add_anchor((.3,.15));s.add_anchor((.3,.6),'TACK',(.5,0,.75))
s.add([(1,0),(1.5,0),(1.5,.7),(1,.7)]);second=s.document.find(s.selected)
first.preset='DENIM';second.preset='SILK';second.wrap_radius=.2
s.sew_chains(s.document.edges(first.id)[:2],[s.document.edge(second.id,3)])
check(s.document.seam_stats(s.document.seams[0])[3]>1,'length mismatch is retained as intentional sewing')
scene.dd_document=s.document.dumps()
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=12,location=(0,0,1.2))
body=bpy.context.object;body.name='Refit body';body.scale=(.25,.15,.5)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
scene.dd_avatar=body
panels=garment.build_panels(bpy.context)
check(len(panels)==2,'curved and rectangular panels generated')
first_obj=next(p for p in panels if p['dd_pattern_id']==first.id)
second_obj=next(p for p in panels if p['dd_pattern_id']==second.id)
check(max(v.co.z for v in second_obj.data.vertices)-min(v.co.z for v in second_obj.data.vertices)>.02,'wrap helper bends panel without editing the 2D path')
check(all(p.data.attributes.get('dd_piece') and p.data.attributes.get('.sculpt_face_set') for p in panels),'per-piece face identifiers exist')
check(all(len(p.vertex_groups)==1 for p in panels),'source panel vertex groups exist')
check(len({tuple(round(x,7) for x in v.vector) for v in first_obj.data.attributes['dd_rest'].data})<len(first_obj.data.vertices),
      'slit creates distinct vertices on the two fabric lips')
rest=first_obj.data.attributes['dd_rest'].data
for face in first_obj.data.polygons:
    center=tuple(sum(rest[i].vector[a] for i in face.vertices)/len(face.vertices) for a in (0,1))
    check(not (.3-.08<center[0]<.3+.08 and .4-.06<center[1]<.4+.06),'no face fills the hole')
original_uv={tuple(round(x,6) for x in rest[loop.vertex_index].vector[:2]):tuple(first_obj.data.uv_layers.active.data[loop.index].uv)
             for loop in first_obj.data.loops}
scene.dd_spacing=.025
garment.build_panels(bpy.context)
new=next(p for p in garment.generated(scene,'panel') if p['dd_pattern_id']==first.id)
rest=new.data.attributes['dd_rest'].data
for loop in new.data.loops:
    key=tuple(round(x,6) for x in rest[loop.vertex_index].vector[:2])
    if key in original_uv:
        check(all(abs(a-b)<1e-5 for a,b in zip(original_uv[key],new.data.uv_layers.active.data[loop.index].uv)),
              'density rebuild preserves source UV mapping')
obj=garment.compile_garment(bpy.context)
cloth=next(m for m in obj.modifiers if m.type=='CLOTH')
check(bool(json.loads(obj['dd_sewing_pairs'])),'M:N ranges compile to real sewing springs')
check(len(garment.generated(scene,'anchor'))==1,'tack creates an avatar-bound target')
check(bool(cloth.settings.vertex_group_mass),'pins and tacks feed the cloth pin group')
scene.frame_set(scene.frame_start)
deps=bpy.context.evaluated_depsgraph_get()
for hook in [m for m in obj.modifiers if m.type=='HOOK']:
    index=list(hook.vertex_indices)[0]
    actual=obj.evaluated_get(deps).data.vertices[index].co
    target=hook.object.evaluated_get(deps).matrix_world.translation
    check((actual-target).length<.002,'tack moves the pinned fabric vertex to the actual avatar target')
check(bool(cloth.settings.vertex_group_structural_stiffness) and bool(cloth.settings.vertex_group_bending),'per-pattern presets use native stiffness groups')
check(obj.data.attributes.get('dd_piece') is not None,'combined garment preserves piece face sets')
scene.frame_set(scene.frame_start)
obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices[0].co
result,_=garment.keep_drape(bpy.context)
check(result.data.uv_layers.active is not None and result.data.attributes.get('dd_piece') is not None,'finalize retains UVs and piece face identifiers')
check(len(result.vertex_groups)>=2,'finalize retains per-piece vertex groups')
path=library.save(bpy.context,'Curve sample')
data=json.loads(path.read_text())
check('body_height_m' in data and 'document' in data,'portable garment contains design and refit metadata')
check('Refit body' not in path.read_text(),'library does not bundle avatar names or meshes')
old_height=garment.bounds(body)[1].z-garment.bounds(body)[0].z
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=12,location=(2,0,1.8))
new_body=bpy.context.object;new_body.name='Different refit body';new_body.scale=(.4,.2,.75)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
scene.dd_avatar=new_body
bpy.context.view_layer.update()
loaded=library.load(bpy.context,scene.dd_library_selected)
check(len(loaded.patterns)==2 and len(loaded.seams)==1 and len(loaded.anchors)==2,'library restores patterns, sewing and anchors')
check(abs(loaded.patterns[0].vertices[0].x-first.vertices[0].x*1.5)<1e-5,'refitting scales source design by new body height')
check(loaded.uv_layout['scale']>0,'library preserves a reusable UV layout transform')
print('ALL ADVANCED BLENDER CHECKS PASSED',flush=True)
devil_designer.unregister()
