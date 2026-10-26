from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils
from . import garment


def ray_body(context,region,space,mouse):
    body=context.scene.dd_avatar
    if body is None:raise ValueError('Choose an avatar body first.')
    direction=view3d_utils.region_2d_to_vector_3d(region,space.region_3d,mouse)
    origin=view3d_utils.region_2d_to_origin_3d(region,space.region_3d,mouse)
    depsgraph=context.evaluated_depsgraph_get()
    tree=BVHTree.FromObject(body,depsgraph)
    inverse=body.matrix_world.inverted()
    point,normal,index,distance=tree.ray_cast(inverse @ origin,(inverse.to_3x3() @ direction).normalized())
    if point is None:raise ValueError('Click on the chosen avatar body.')
    world=body.matrix_world @ point
    normal=(body.matrix_world.inverted().transposed().to_3x3() @ normal).normalized()
    return world,normal,index


def place(context,pattern_id,point,normal):
    panels=garment.generated(context.scene,'panel')
    obj=next((o for o in panels if o.get('dd_pattern_id')==pattern_id),None)
    if obj is None:obj=next(o for o in garment.build_panels(context) if o['dd_pattern_id']==pattern_id)
    garment.reset(context)
    up=Vector((0,0,1));up-=normal*up.dot(normal)
    if up.length<.001:up=Vector((0,1,0));up-=normal*up.dot(normal)
    up.normalize();right=up.cross(normal).normalized()
    matrix=Matrix((right,up,normal)).transposed().to_4x4()
    matrix.translation=point+normal*context.scene.dd_clearance/garment.metres_per_unit(context.scene)
    obj.matrix_world=matrix
    context.view_layer.update()
    return obj


def normalized_target(scene,point):
    low,high=garment.bounds(scene.dd_avatar)
    return tuple((point[i]-low[i])/max(1e-8,high[i]-low[i]) for i in range(3))
