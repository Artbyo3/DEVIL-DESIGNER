import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import garment,layering
from devil_designer.core import Session


def check(condition,message):
    if not condition:
        raise AssertionError(message)
    print('PASS:',message,flush=True)


def collision_snapshot(obj):
    settings=obj.collision
    values={}
    for prop in settings.bl_rna.properties:
        if prop.type in {'BOOLEAN','INT','FLOAT','ENUM','STRING'}:
            value=getattr(settings,prop.identifier)
            values[prop.identifier]=tuple(value) if prop.is_array else value
    return tuple((modifier.as_pointer(),modifier.type,modifier.name) for modifier in obj.modifiers),values


def evaluate(simulation,frame):
    bpy.context.scene.frame_set(frame)
    evaluated=simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices]


def segment_distance(point,start,end):
    direction=end-start
    fraction=max(0,min(1,(point-start).dot(direction)/max(direction.length_squared,1e-20)))
    return (point-start-direction*fraction).length


def torso_penetration(point,tree,near_boundary):
    radial=Vector((point.x,point.y,0))
    if radial.length<1e-8:
        return None
    hit,normal,face_index,distance=tree.ray_cast(Vector((0,0,point.z)),radial.normalized(),1)
    if hit is None or near_boundary(hit):
        return None
    if radial.length>=distance:
        return 0.0
    nearest,normal,face_index,distance=tree.find_nearest(point)
    return distance


def check_penetration_measurement():
    vertices=[Vector((x,y,z)) for x in (-.1,.1) for y in (-.1,.1) for z in (-.1,.1)]
    faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    tree=BVHTree.FromPolygons(vertices,faces)
    check(abs(torso_penetration(Vector((.09,0,0)),tree,lambda point:False)-.01)<1e-6,
          'penetration classifier measures known 10 mm interior depth independently of face winding')
    check(torso_penetration(Vector((.11,0,0)),tree,lambda point:False)==0,
          'penetration classifier does not label exterior points as penetration')
    check(torso_penetration(Vector((.09,0,.2)),tree,lambda point:False) is None,
          'penetration classifier skips samples beyond the shirt cross-section')


def penetration_trial(shirt,enabled):
    scene=bpy.context.scene
    garment.reset(bpy.context)
    shirt['dd_wear_over']=enabled
    check('FINISHED' in bpy.ops.devil_designer.simulate(),'simulation operator starts Wear over '+str(enabled))
    simulation=garment.generated(scene,'simulation')[0]
    cloth=next(modifier for modifier in simulation.modifiers if modifier.type=='CLOTH')
    members=set(cloth.collision_settings.collection.objects)
    check(scene.dd_avatar in members,'body always belongs to the simulation collision collection')
    check(extra_collider in members,'pre-existing unrelated collider remains included')
    check((shirt in members)==enabled,'shirt collection membership follows Wear over')
    depsgraph=bpy.context.evaluated_depsgraph_get()
    shirt_mesh=shirt.evaluated_get(depsgraph).data
    vertices=[shirt.matrix_world @ vertex.co for vertex in shirt_mesh.vertices]
    polygons=[list(face.vertices) for face in shirt_mesh.polygons]
    tree=BVHTree.FromPolygons(vertices,polygons,all_triangles=True)
    edge_faces={}
    for face in polygons:
        for index,vertex in enumerate(face):
            edge=tuple(sorted((vertex,face[(index+1)%len(face)])))
            edge_faces[edge]=edge_faces.get(edge,0)+1
    boundaries=[(vertices[start],vertices[end]) for (start,end),count in edge_faces.items() if count==1]
    boundary_samples=[]
    for index,(start,end) in enumerate(boundaries):
        steps=max(1,math.ceil((end-start).length/.004))
        boundary_samples.extend((start.lerp(end,step/steps),index) for step in range(steps+1))
    boundary_tree=KDTree(len(boundary_samples))
    for index,(point,segment) in enumerate(boundary_samples):
        boundary_tree.insert(point,index)
    boundary_tree.balance()
    def near_boundary(point):
        nearby={boundary_samples[index][1] for location,index,dist in boundary_tree.find_range(point,.014)}
        return any(segment_distance(point,*boundaries[index])<.012 for index in nearby)
    max_penetration=0.0
    final_penetration=0.0
    checked=0
    deepest_frame=scene.frame_start
    minimum_frame_samples=None
    surface_edges=sorted({tuple(sorted((vertex,face.vertices[(index+1)%len(face.vertices)])))
                          for face in simulation.data.polygons for index,vertex in enumerate(face.vertices)})
    for frame in range(scene.frame_start,scene.frame_start+121):
        coords=evaluate(simulation,frame)
        check_finite=all(math.isfinite(component) for point in coords for component in point)
        if not check_finite or max(point.length for point in coords)>5:
            raise AssertionError('Jacket geometry is non-finite or has exploded.')
        samples=coords+[sum((coords[index] for index in face.vertices),Vector())/len(face.vertices) for face in simulation.data.polygons]
        samples.extend((coords[start]+coords[end])/2 for start,end in surface_edges)
        frame_penetration=0.0
        frame_checked=0
        for point in samples:
            depth=torso_penetration(point,tree,near_boundary)
            if depth is None:
                continue
            if not math.isfinite(depth):
                raise AssertionError('Non-finite jacket position.')
            checked+=1
            frame_checked+=1
            frame_penetration=max(frame_penetration,depth)
        minimum_frame_samples=frame_checked if minimum_frame_samples is None else min(minimum_frame_samples,frame_checked)
        if frame_penetration>max_penetration:
            max_penetration=frame_penetration
            deepest_frame=frame
        final_penetration=frame_penetration
    result=dict(wear_over=enabled,max_penetration_m=max_penetration,final_penetration_m=final_penetration,
                deepest_frame=deepest_frame,checked_samples=checked,minimum_frame_samples=minimum_frame_samples,
                frames=121,boundary_exclusion_m=.012,quality=scene.dd_quality,
                final_bounds=[[min(point[axis] for point in coords) for axis in range(3)],
                              [max(point[axis] for point in coords) for axis in range(3)]],
                shirt_collision=dict(thickness_outer=shirt.collision.thickness_outer,thickness_inner=shirt.collision.thickness_inner),
                sampling='evaluated jacket vertices, surface-edge midpoints and face centroids; torso-axis ray classifies inside/outside, then nearest-surface distance measures interior depth; not a general open-mesh signed-distance test')
    print('LAYERING_TRIAL '+json.dumps(result),flush=True)
    check(checked>10000,'penetration measurement contains a non-vacuous sample set')
    check(minimum_frame_samples>=50,'every frame has at least 50 interior-region samples')
    return result


check_penetration_measurement()
devil_designer.register()
scene=bpy.context.scene
scene.dd_spacing=.025
scene.dd_quality=12
scene.dd_frames=120
scene.dd_thickness=0
check('FINISHED' in bpy.ops.devil_designer.demo(),'procedural shirt patterns and body created')
check('FINISHED' in bpy.ops.devil_designer.simulate(),'first garment starts through the unchanged simulation path')
simulation=garment.generated(scene,'simulation')[0]
check(next(modifier for modifier in simulation.modifiers if modifier.type=='CLOTH').collision_settings.collection is None,
      'no-kept-garment path does not assign a collision collection')
for frame in range(scene.frame_start,scene.frame_start+81):
    evaluate(simulation,frame)
shirt_pose=evaluate(simulation,scene.frame_start+80)
shirt,open_pairs=garment.keep_drape(bpy.context)
shirt.name='Kept shirt'
check(open_pairs==0,'kept shirt begins with every sewing pair welded')
shirt_coords=[tuple(vertex.co) for vertex in shirt.data.vertices]
layering.prepare_colliders(bpy.context)
check(any(modifier.type=='COLLISION' for modifier in shirt.modifiers),'kept shirt automatically gets collision')
bpy.ops.mesh.primitive_cube_add(size=.1,location=(2,0,0))
extra_collider=bpy.context.object
extra_collider.name='Existing scene collider'
extra_collider.modifiers.new('Artist collision','COLLISION')
extra_collider.collision.thickness_outer=.009
snapshots={obj.name:collision_snapshot(obj) for obj in (shirt,scene.dd_avatar,extra_collider)}
session=Session(garment.document(scene))
for pattern in session.document.patterns:
    pattern.name=pattern.name.replace('Bodice','Jacket')
scene.dd_document=session.document.dumps()
scene.dd_pin_top=True
scene.dd_quality=24
garment.build_panels(bpy.context)
offset=0
for panel in garment.generated(scene,'panel'):
    inverse=panel.matrix_world.inverted()
    for vertex in panel.data.vertices:
        position=shirt_pose[offset+vertex.index].copy()
        outward=Vector((position.x,position.y,0)).normalized()
        vertex.co=inverse @ (position+outward*.03+Vector((0,0,.005)))
    offset+=len(panel.data.vertices)
check(offset==len(shirt_pose),'jacket fixture uses the same source-pattern sampling as the shirt')
bpy.context.view_layer.update()
on=penetration_trial(shirt,True)
off=penetration_trial(shirt,False)
report=dict(tolerance_m=.002,fixture='Kept two-piece shirt; source-matched jacket panels prearranged 30 mm radially outside and 5 mm above the shirt, with the existing top-pin option supporting the jacket on a headless torso',
            on=on,off=off,quad_conversion=False)
(ROOT/'scratch').mkdir(exist_ok=True)
(ROOT/'scratch'/'layering-report.json').write_text(json.dumps(report,indent=2))
for obj in (shirt,scene.dd_avatar,extra_collider):
    check(collision_snapshot(obj)==snapshots[obj.name],obj.name+' existing Collision modifier and settings stay unchanged')
check([tuple(vertex.co) for vertex in shirt.data.vertices]==shirt_coords,'layering never changes the kept shirt mesh')
simulation=garment.generated(scene,'simulation')[0]
cloth=next(modifier for modifier in simulation.modifiers if modifier.type=='CLOTH')
original_filter=cloth.collision_settings.collection
original_members=set(original_filter.objects)
other_mesh=bpy.data.meshes.new('Other simulation mesh')
other=bpy.data.objects.new('Other simulation',other_mesh)
other_cloth=other.modifiers.new('Other cloth','CLOTH')
other_cloth.collision_settings.collection=original_filter
shirt['dd_wear_over']=True
layering.configure_collision_collection(bpy.context,simulation)
check(cloth.collision_settings.collection!=original_filter,'shared collision filters are copied before changing the current simulation')
check(other_cloth.collision_settings.collection==original_filter and set(original_filter.objects)==original_members,
      'configuring the current simulation leaves another simulation and its filter unchanged')
bpy.data.objects.remove(other,do_unlink=True)
bpy.data.meshes.remove(other_mesh)
shirt['dd_wear_over']=False
layering.configure_collision_collection(bpy.context,simulation)
check(len([collection for collection in bpy.data.collections if collection.get('dd_layering_owner')==garment.OWNER])==1,
      'unused owned filters are pruned without deleting active or artist collections')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'scratch'/'layering-test.blend'))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'scratch'/'layering-test.blend'))
scene=bpy.context.scene
shirt=scene.objects['Kept shirt']
simulation=garment.generated(scene,'simulation')[0]
cloth=next(modifier for modifier in simulation.modifiers if modifier.type=='CLOTH')
check(cloth.collision_settings.collection is not None and scene.dd_avatar in list(cloth.collision_settings.collection.objects),
      'collision filter and body membership survive save/reopen')
check(shirt.get('dd_wear_over') is False and shirt not in list(cloth.collision_settings.collection.objects) and
      scene.objects['Existing scene collider'] in list(cloth.collision_settings.collection.objects),
      'saved Wear over exclusion never drops unrelated scene colliders')
garment.reset(bpy.context)
check(shirt.name in scene.objects and not garment.generated(scene,'simulation'),'Reset removes only the simulation and preserves the kept shirt')
for trial in (on,off):
    check(trial['final_bounds'][0][2]>.8 and trial['final_bounds'][1][2]>1.4,'jacket stays supported with Wear over '+str(trial['wear_over']))
check(on['max_penetration_m']<=report['tolerance_m'],'Wear over on stays outside the shirt within 2 mm throughout the trial')
check(off['final_penetration_m']>report['tolerance_m'],'Wear over off demonstrates measurable shirt bypass while body collision remains enabled')
devil_designer.unregister()
print('ALL LAYERING CHECKS PASSED',flush=True)
