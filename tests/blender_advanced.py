from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
import sys,json,math
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
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
scene.dd_library_dir=str(ROOT/'scratch'/'test-library')
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
state_keys=('dd_document','dd_spacing','dd_quality','dd_frames','dd_self_collision','dd_pin_top','dd_weld_distance','dd_thickness','dd_library_name','dd_library_selected','dd_avatar')
def library_state():
    return (
        tuple(getattr(scene,key) for key in state_keys),
        tuple((obj.as_pointer(),obj.data.as_pointer() if obj.data else None,
               tuple(tuple(row) for row in obj.matrix_world),tuple(sorted((key,repr(value)) for key,value in obj.items())),
               tuple(tuple(vertex.co) for vertex in obj.data.vertices) if obj.type=='MESH' else (),
               tuple(modifier.as_pointer() for modifier in obj.modifiers),obj.hide_get(),obj.select_get())
              for obj in scene.objects),
        bpy.context.view_layer.objects.active,scene.frame_current)

invalid_designs=[]
for value in (None,[],True,1,'garment'):
    invalid_designs.append(('root '+repr(value),value))
for key,values in (
    ('version',(True,'1',2)),
    ('name',(None,{},12)),
    ('body_height_m',(None,'1',True,-1,float('nan'),float('inf'))),
    ('settings',(None,[],1,'settings')),
    ('panels',(None,{},1,'panels')),
    ('document',(None,[],{},dict(version=3,patterns=[])))):
    for value in values:
        invalid=deepcopy(data);invalid[key]=value
        invalid_designs.append((key+' '+repr(value),invalid))
valid_pose=dict(pattern=data['document']['patterns'][0]['id'],position=[.5,0,.5],orientation=[[1,0,0],[0,1,0],[0,0,1]])
for value in (None,[],1,'pose',{},dict(valid_pose,pattern=[]),dict(valid_pose,pattern=None),dict(valid_pose,pattern=1),
              dict(valid_pose,position=None),dict(valid_pose,position=[True,0,0]),dict(valid_pose,position=['0',0,0]),
              dict(valid_pose,position=[float('inf'),0,0]),dict(valid_pose,position=[1e300,0,0]),
              dict(valid_pose,orientation=[1,2,3]),dict(valid_pose,orientation=[[1,0,0],None,[0,0,1]]),
              dict(valid_pose,orientation=[[1,0,0],[0,'1',0],[0,0,1]]),
              dict(valid_pose,orientation=[[1,0,0],[0,1,0],[0,0,float('nan')]])):
    invalid=deepcopy(data);invalid['panels']=[value]
    invalid_designs.append(('pose '+repr(value),invalid))
for value in (dict(valid_pose,pattern='stale',position=None),
              dict(valid_pose,pattern='stale',orientation=[1,2,3]),
              dict(valid_pose,pattern='stale',position=[float('inf'),0,0])):
    invalid=deepcopy(data);invalid['panels']=[value]
    invalid_designs.append(('malformed stale pose '+repr(value),invalid))
invalid=deepcopy(data);invalid['panels']=[valid_pose,valid_pose]
invalid_designs.append(('duplicate placement',invalid))
for key in state_keys[1:8]:
    prop=scene.bl_rna.properties[key]
    values=(None,'bad',[],{})
    if prop.type=='BOOLEAN':values+=(0,1)
    else:
        values+=(True,float('nan'),float('inf'),prop.hard_min-1,prop.hard_max+1,10**400)
        if prop.type=='INT':values+=(10.5,10.0)
    for value in values:
        invalid=deepcopy(data);invalid['settings'][key]=value
        invalid_designs.append(('setting '+key+' '+repr(value),invalid))
original_bytes=path.read_bytes()
original_build=garment.build_panels
build_calls=[]
def forbidden_build(context):
    build_calls.append(context)
    raise AssertionError('Invalid library data reached panel construction.')

try:
    garment.build_panels=forbidden_build
    for avatar in (new_body,None):
        scene.dd_avatar=avatar
        before=library_state()
        for label,invalid in invalid_designs:
            path.write_text(json.dumps(invalid),encoding='utf-8')
            try:library.load(bpy.context,scene.dd_library_selected)
            except ValueError as error:check(bool(str(error)),'invalid library data has a readable error')
            else:raise AssertionError('Accepted invalid library data: '+label)
            check(not build_calls,'invalid library metadata never invokes build')
            check(library_state()==before,'invalid library metadata preserves document, settings and scene objects')
        path.write_bytes(b'\xff\xfeinvalid garment')
        try:library.load(bpy.context,scene.dd_library_selected)
        except ValueError as error:check('UTF-8' in str(error),'invalid UTF-8 has a readable library error')
        else:raise AssertionError('Accepted invalid UTF-8.')
        check(not build_calls and library_state()==before,'invalid UTF-8 preserves the garment without building')
    scene.dd_avatar=new_body
    incoming=deepcopy(data)
    incoming['settings'].update(dd_quality=15,dd_frames=150,dd_self_collision=False,dd_pin_top=True,dd_weld_distance=.02,dd_thickness=.002)
    incoming['name']='Rollback candidate'
    path.write_text(json.dumps(incoming),encoding='utf-8')
    before=library_state()
    def failed_build(context):
        check(context.scene.dd_quality==15 and context.scene.dd_pin_top,'validated settings are applied before building')
        raise ValueError('Injected panel preparation failure.')
    garment.build_panels=failed_build
    try:library.load(bpy.context,scene.dd_library_selected)
    except ValueError as error:check(str(error)=='Injected panel preparation failure.','panel build errors remain readable')
    else:raise AssertionError('Expected injected build failure.')
    check(library_state()==before,'panel preparation failure restores every imported scene value')
    class RejectSetting:
        def __getattr__(self,key):return getattr(scene,key)
        def __setattr__(self,key,value):
            if key=='dd_pin_top' and value is True:raise TypeError('Injected setting assignment failure.')
            setattr(scene,key,value)
    garment.build_panels=forbidden_build
    try:library.load(SimpleNamespace(scene=RejectSetting(),view_layer=bpy.context.view_layer),scene.dd_library_selected)
    except ValueError:pass
    else:raise AssertionError('Expected injected setting assignment failure.')
    check(not build_calls and library_state()==before,'setting assignment failure rolls back earlier assignments without building')
    def accepted_build(context):return []
    garment.build_panels=accepted_build
    for upper in (False,True):
        boundary=deepcopy(data)
        for key in state_keys[1:8]:
            prop=scene.bl_rna.properties[key]
            boundary['settings'][key]=upper if prop.type=='BOOLEAN' else prop.hard_max if upper else prop.hard_min
        boundary['settings']['future_setting']={'ignored':True}
        path.write_text(json.dumps(boundary),encoding='utf-8')
        library.load(bpy.context,scene.dd_library_selected)
        check(all(getattr(scene,key)==boundary['settings'][key] for key in state_keys[1:8]),'RNA setting bounds round-trip without clamping')
    for key in state_keys[1:8]:setattr(scene,key,before[0][state_keys.index(key)])
    boundary=deepcopy(data)
    boundary['settings'].update(dd_spacing=.003,dd_weld_distance=.0001,dd_thickness=.01)
    path.write_text(json.dumps(boundary),encoding='utf-8')
    library.load(bpy.context,scene.dd_library_selected)
    check(abs(scene.dd_spacing-.003)<1e-9 and abs(scene.dd_thickness-.01)<1e-9,'declared decimal setting bounds remain valid')
    optional=deepcopy(data)
    for key in ('settings','panels','name','body_height_m'):optional.pop(key,None)
    path.write_text(json.dumps(optional),encoding='utf-8')
    previous_settings=tuple(getattr(scene,key) for key in state_keys[1:8])
    library.load(bpy.context,scene.dd_library_selected)
    check(tuple(getattr(scene,key) for key in state_keys[1:8])==previous_settings,'omitted settings preserve current supported defaults')
    garment.build_panels=original_build
    incoming['panels']=[valid_pose]
    path.write_text(json.dumps(incoming),encoding='utf-8')
    library.load(bpy.context,scene.dd_library_selected)
    check(scene.dd_quality==15 and scene.dd_frames==150 and scene.dd_pin_top and not scene.dd_self_collision,'valid nondefault library settings round-trip')
    positioned=next(obj for obj in garment.generated(scene,'panel') if obj['dd_pattern_id']==valid_pose['pattern'])
    low,high=garment.bounds(new_body)
    expected=tuple(low[axis]+(high[axis]-low[axis])*valid_pose['position'][axis] for axis in range(3))
    check(all(abs(positioned.matrix_world.translation[axis]-expected[axis])<1e-5 for axis in range(3)),'valid stored placement is restored after refitting')
finally:
    garment.build_panels=original_build
    scene.dd_avatar=new_body
    path.write_bytes(original_bytes)
stale_session=Session()
stale_session.add([(0,0),(.3,0),(.3,.3),(0,.3)])
stale_session.add([(.4,0),(.7,0),(.7,.3),(.4,.3)])
scene.dd_document=stale_session.document.dumps()
stale_panels=garment.build_panels(bpy.context)
check(len(stale_panels)==2,'stale library roundtrip starts with two built panels')
removed=stale_session.document.patterns.pop()
stale_panel=next(obj for obj in stale_panels if obj['dd_pattern_id']==removed.id)
low,high=garment.bounds(new_body)
stale_pose=dict(pattern=removed.id,
                position=[(stale_panel.matrix_world.translation[axis]-low[axis])/max(1e-6,high[axis]-low[axis]) for axis in range(3)],
                orientation=[list(row) for row in stale_panel.matrix_world.to_3x3()])
scene.dd_document=stale_session.document.dumps()
check(len(garment.generated(scene,'panel'))==2,'source-only deletion leaves a stale generated panel before saving')
stale_path=library.save(bpy.context,'Stale panel compatibility')
stale_data=json.loads(stale_path.read_text(encoding='utf-8'))
check(len(stale_data['panels'])==1 and stale_data['panels'][0]['pattern']==stale_session.document.patterns[0].id,
      'library save excludes generated panels deleted from the source document')
stale_loaded=library.load(bpy.context,scene.dd_library_selected)
check(len(stale_loaded.patterns)==1 and len(garment.generated(scene,'panel'))==1,
      'build two, delete source only, save and load roundtrip restores the surviving pattern')
surviving_panel=garment.generated(scene,'panel')[0]
surviving_matrix=tuple(tuple(row) for row in surviving_panel.matrix_world)
stale_data['panels'].extend([stale_pose,deepcopy(stale_pose)])
stale_path.write_text(json.dumps(stale_data),encoding='utf-8')
stale_loaded=library.load(bpy.context,scene.dd_library_selected)
check(len(stale_loaded.patterns)==1 and len(garment.generated(scene,'panel'))==1
      and tuple(tuple(row) for row in garment.generated(scene,'panel')[0].matrix_world)==surviving_matrix,
      'legacy stale string poses are ignored while the matching placement round-trips')
print('ALL ADVANCED BLENDER CHECKS PASSED',flush=True)
devil_designer.unregister()
