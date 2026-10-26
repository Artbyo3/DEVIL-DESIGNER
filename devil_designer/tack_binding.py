import hashlib
import json
import math
import uuid


def topology_signature(mesh):
    topology=[len(mesh.vertices),[list(face.vertices) for face in mesh.polygons]]
    return hashlib.sha256(json.dumps(topology,separators=(',',':')).encode()).hexdigest()


def validate_binding(binding):
    if not isinstance(binding,dict) or type(binding.get('version')) is not int or binding['version']!=1:
        raise ValueError('Invalid tack binding. Reattach this tack to the avatar.')
    vertices=binding.get('vertices')
    weights=binding.get('weights')
    if not isinstance(vertices,(list,tuple)) or len(vertices)!=3 or any(type(index) is not int or index<0 for index in vertices) or len(set(vertices))!=3:
        raise ValueError('Invalid tack triangle. Reattach this tack to the avatar.')
    if not isinstance(weights,(list,tuple)) or len(weights)!=3 or any(type(weight) not in (int,float) or not math.isfinite(weight) or not 0<=weight<=1 for weight in weights) or abs(sum(weights)-1)>1e-6:
        raise ValueError('Invalid tack weights. Reattach this tack to the avatar.')
    for key,length in (('topology',64),('avatar',32)):
        value=binding.get(key)
        if not isinstance(value,str) or len(value)!=length or any(character not in '0123456789abcdef' for character in value):
            raise ValueError('Invalid tack identity. Reattach this tack to the avatar.')
    return binding


def evaluated_surface(context,avatar):
    if avatar is None or avatar.type!='MESH':
        raise ValueError('Choose an avatar body mesh first.')
    evaluated=avatar.evaluated_get(context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    try:
        signature=topology_signature(avatar.data)
        if topology_signature(mesh)!=signature:
            raise ValueError('Tacks need stable avatar topology. Disable topology-changing avatar modifiers, then reattach the tack.')
        mesh.calc_loop_triangles()
        points=[evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        triangles=[tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        return points,triangles,signature
    finally:
        evaluated.to_mesh_clear()


def bind_target(context,avatar,world_point):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    point=Vector(world_point)
    if len(point)!=3 or any(not math.isfinite(value) for value in point):
        raise ValueError('Invalid tack location. Click on the avatar again.')
    points,triangles,signature=evaluated_surface(context,avatar)
    triangles=[triangle for triangle in triangles if (points[triangle[1]]-points[triangle[0]]).cross(points[triangle[2]]-points[triangle[0]]).length_squared>1e-20]
    if not triangles:
        raise ValueError('The avatar has no usable surface for a tack.')
    tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
    nearest,normal,index,distance=tree.find_nearest(point)
    if nearest is None:
        raise ValueError('Click on the avatar surface to attach the tack.')
    vertices=triangles[index]
    origin,second,third=(points[vertex] for vertex in vertices)
    edge_second=second-origin
    edge_third=third-origin
    displacement=nearest-origin
    second_squared=edge_second.dot(edge_second)
    third_squared=edge_third.dot(edge_third)
    product=edge_second.dot(edge_third)
    denominator=second_squared*third_squared-product*product
    if denominator<=0:
        raise ValueError('The avatar triangle is too small for a stable tack.')
    second_weight=(third_squared*displacement.dot(edge_second)-product*displacement.dot(edge_third))/denominator
    third_weight=(second_squared*displacement.dot(edge_third)-product*displacement.dot(edge_second))/denominator
    weights=[max(0,min(1,weight)) for weight in (1-second_weight-third_weight,second_weight,third_weight)]
    total=sum(weights)
    identity=avatar.get('dd_tack_identity')
    if not isinstance(identity,str) or len(identity)!=32 or any(character not in '0123456789abcdef' for character in identity):
        identity=uuid.uuid4().hex
        avatar['dd_tack_identity']=identity
    return dict(version=1,vertices=list(vertices),weights=[weight/total for weight in weights],topology=signature,avatar=identity)


def resolve_binding(context,avatar,anchor):
    if avatar is None or avatar.type!='MESH':
        raise ValueError('Choose an avatar body mesh and reattach the tack.')
    binding=getattr(anchor,'binding',None)
    if binding is not None:
        validate_binding(binding)
        if binding['avatar']==avatar.get('dd_tack_identity'):
            points,triangles,signature=evaluated_surface(context,avatar)
            if binding['topology']!=signature or max(binding['vertices'])>=len(points) or not any(set(binding['vertices']).issubset(face.vertices) for face in avatar.data.polygons):
                raise ValueError('The avatar topology changed. Reattach this tack to the avatar.')
            return binding
    target=anchor.target
    if target is None or len(target)!=3 or any(not math.isfinite(value) for value in target):
        raise ValueError('Choose an avatar and reattach the tack.')
    from mathutils import Vector
    corners=[avatar.matrix_world @ Vector(corner) for corner in avatar.bound_box]
    low=[min(corner[axis] for corner in corners) for axis in range(3)]
    high=[max(corner[axis] for corner in corners) for axis in range(3)]
    point=[low[axis]+(high[axis]-low[axis])*target[axis] for axis in range(3)]
    return bind_target(context,avatar,point)


def migrate_anchors(context,document):
    updates=[]
    for anchor in document.anchors:
        if anchor.kind!='TACK':
            continue
        binding=resolve_binding(context,context.scene.dd_avatar,anchor)
        if binding!=getattr(anchor,'binding',None):
            updates.append((anchor,binding))
    for anchor,binding in updates:
        anchor.binding=binding
    return bool(updates)


def create_target(context,avatar,binding,collection,tag):
    import bpy
    from mathutils import Matrix
    validate_binding(binding)
    target=bpy.data.objects.new('DD Tack',None)
    collection.objects.link(target)
    tag(target,'anchor')
    target.empty_display_type='SPHERE'
    target['dd_tack_binding']=json.dumps(binding,separators=(',',':'))
    accumulated=0
    for index,weight in zip(binding['vertices'],binding['weights']):
        if weight<=0:
            continue
        vertex=bpy.data.objects.new('DD Tack Vertex',None)
        collection.objects.link(vertex)
        tag(vertex,'anchor')
        vertex.empty_display_size=0
        vertex.hide_render=True
        vertex.parent=avatar
        vertex.parent_type='VERTEX'
        vertex.parent_vertices=(index,index,index)
        vertex.matrix_parent_inverse=Matrix.Identity(4)
        vertex.location=(0,0,0)
        constraint=target.constraints.new('COPY_LOCATION')
        constraint.target=vertex
        constraint.owner_space='WORLD'
        constraint.target_space='WORLD'
        accumulated+=weight
        constraint.influence=weight/accumulated
    return target
