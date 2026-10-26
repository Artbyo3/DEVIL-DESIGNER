"""Generate panels, assemble sewing springs, and keep evaluated draped meshes."""
import hashlib
import json
import math
import bpy
import bmesh
from mathutils import Matrix, Vector
from .core import Document
from .meshing import edge_counts, fabric_mesh

OWNER = "Artbyo3/DEVIL-DESIGNER"
_playback_window = None


def stop_at_end():
    global _playback_window
    window = _playback_window
    try:
        if window is None or not window.screen.is_animation_playing:
            _playback_window = None
            return None
        objects = generated(window.scene,'simulation')
        if not objects:
            _playback_window = None
            return None
        cloth = next(m for m in objects[0].modifiers if m.type=='CLOTH')
        if window.scene.frame_current>=cloth.point_cache.frame_end:
            with bpy.context.temp_override(window=window):
                stop(bpy.context)
            _playback_window = None
            return None
    except (ReferenceError,RuntimeError,StopIteration):
        _playback_window = None
        return None
    return .15


def start_playback(context):
    global _playback_window
    if not bpy.app.background and context.screen:
        _playback_window = context.window
        if not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        if not bpy.app.timers.is_registered(stop_at_end):
            bpy.app.timers.register(stop_at_end,first_interval=.15)


def cancel_playback():
    global _playback_window
    _playback_window = None
    if bpy.app.timers.is_registered(stop_at_end):
        bpy.app.timers.unregister(stop_at_end)


def document(scene):
    return Document.loads(scene.dd_document)


def generated(scene,kind):
    return [o for o in scene.objects if o.get('dd_owner')==OWNER and o.get('dd_kind')==kind]


def collection(scene):
    c = scene.dd_collection
    if c is None or c.name not in scene.collection.children:
        c = bpy.data.collections.new('Devil Designer')
        scene.collection.children.link(c)
        scene.dd_collection = c
    return c


def tag(obj,kind):
    obj['dd_owner'],obj['dd_kind'] = OWNER,kind


def remove_objects(objects):
    for obj in objects:
        mesh = obj.data if obj.type=='MESH' else None
        bpy.data.objects.remove(obj,do_unlink=True)
        if mesh and mesh.users==0:
            bpy.data.meshes.remove(mesh)


def stop(context):
    if context.screen and context.screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)


def reset(context):
    stop(context)
    remove_objects(generated(context.scene,'simulation'))
    for obj in generated(context.scene,'panel'):
        obj.hide_set(False)
        obj.hide_render = False
    context.scene.frame_set(context.scene.frame_start)


def metres_per_unit(scene):
    return max(1e-6,scene.unit_settings.scale_length)


def material(index):
    colors = [(.22,.52,.66,1),(.49,.32,.65,1),(.65,.43,.19,1),(.23,.52,.34,1)]
    name = 'DD Fabric '+str(index%len(colors)+1)
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.diffuse_color = colors[index%len(colors)]
        m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = m.diffuse_color
        bsdf.inputs['Roughness'].default_value = .8
    return m


def build_panels(context):
    scene = context.scene
    doc = document(scene)
    if not doc.patterns:
        raise ValueError("Draw at least one closed pattern first.")
    doc.validate_seams()
    counts = edge_counts(doc,scene.dd_spacing)
    unit = metres_per_unit(scene)
    all_points = [pt for p in doc.patterns for pt in p.points]
    minx,miny = min(p[0] for p in all_points),min(p[1] for p in all_points)
    extent = max(max(p[0] for p in all_points)-minx,max(p[1] for p in all_points)-miny,.001)
    # Prepare every mesh before mutating the scene: a failed pattern leaves old panels intact.
    prepared = []
    try:
        for p in doc.patterns:
            coords,faces,boundaries = fabric_mesh(doc,p,scene.dd_spacing,counts)
            cx = (min(v[0] for v in p.points)+max(v[0] for v in p.points))/2
            cy = (min(v[1] for v in p.points)+max(v[1] for v in p.points))/2
            mesh = bpy.data.meshes.new('DD '+p.name)
            prepared.append((p,mesh,boundaries,(cx,cy)))
            mesh.from_pydata([((x-cx)/unit,(y-cy)/unit,0) for x,y in coords],[],faces)
            uv = mesh.uv_layers.new(name='Pattern UV')
            for loop in mesh.loops:
                x,y = coords[loop.vertex_index]
                uv.data[loop.index].uv = ((x-minx)/extent,(y-miny)/extent)
            mesh.update()
    except Exception:
        for _,mesh,_,_ in prepared:
            bpy.data.meshes.remove(mesh)
        raise
    reset(context)
    old = {o.get('dd_pattern_id'):o for o in generated(scene,'panel')}
    coll = collection(scene)
    result = []
    for index,(p,mesh,boundaries,center) in enumerate(prepared):
        obj = old.pop(p.id,None)
        if obj is None:
            obj = bpy.data.objects.new(p.name,mesh)
            coll.objects.link(obj)
            obj.location = (center[0]/unit,0,center[1]/unit)
            obj.rotation_euler = (math.pi/2,0,0)
        else:
            previous = obj.data
            obj.data = mesh
            if previous.users==0:
                bpy.data.meshes.remove(previous)
        tag(obj,'panel')
        obj['dd_pattern_id'] = p.id
        obj['dd_boundaries'] = json.dumps(boundaries,separators=(',',':'))
        obj['dd_document'] = doc.dumps()
        obj['dd_spacing'] = scene.dd_spacing
        obj['dd_units'] = unit
        obj.name = p.name
        obj.data.materials.append(material(index))
        obj.color = material(index).diffuse_color
        result.append(obj)
    remove_objects(list(old.values()))
    return result


def bounds(obj):
    points = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
    return Vector(tuple(min(p[a] for p in points) for a in range(3))),Vector(tuple(max(p[a] for p in points) for a in range(3)))


def arrange(context):
    scene = context.scene
    avatar = scene.dd_avatar
    if avatar is None:
        raise ValueError("Choose your avatar body mesh first.")
    if avatar.type!='MESH' or avatar not in list(scene.objects) or avatar.get('dd_kind') in {'panel','simulation','final'}:
        raise ValueError("Choose an avatar mesh in the current scene.")
    if len(document(scene).patterns)!=2:
        raise ValueError("Front/back arrangement needs exactly two patterns. Other layouts can be positioned manually.")
    panels = build_panels(context)
    low,high = bounds(avatar)
    unit = metres_per_unit(scene)
    center = (low+high)/2
    # A torso is near the upper quarter of a full avatar. For a torso-only collider use its centre.
    body_height = high.z-low.z
    z = low.z+body_height*(.72 if body_height*unit>1 else .68)
    gap = scene.dd_clearance/unit
    for index,obj in enumerate(panels):
        side = -1 if index==0 else 1
        obj.location = (center.x,(low.y-gap if side<0 else high.y+gap),z)
        obj.rotation_euler = (math.pi/2,0,0 if index==0 else math.pi)
    context.view_layer.update()
    return panels


def signature(scene,panels):
    data = [scene.dd_document,scene.dd_spacing,scene.dd_quality,scene.dd_frames,
            scene.dd_self_collision,scene.dd_pin_top,metres_per_unit(scene),
            [[p.get('dd_pattern_id'),[v for row in p.matrix_world for v in row]] for p in panels]]
    avatar = scene.dd_avatar
    if avatar:
        data += [avatar.name,[v for row in avatar.matrix_world for v in row]]
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def ensure_collision(scene):
    avatar = scene.dd_avatar
    if avatar is None or avatar.type!='MESH' or avatar not in list(scene.objects):
        raise ValueError("Choose an avatar body mesh in the current scene.")
    if avatar.library and not avatar.override_library:
        raise ValueError("Make the avatar editable or create a library override before adding collision.")
    if avatar.get('dd_kind') in {'panel','simulation','final'}:
        raise ValueError("The collider must be your avatar body, not generated clothing.")
    if not any(m.type=='COLLISION' for m in avatar.modifiers):
        avatar.modifiers.new('DD Body Collision','COLLISION')
        avatar.collision.thickness_outer = .003/metres_per_unit(scene)
        avatar.collision.thickness_inner = .001/metres_per_unit(scene)


def compile_garment(context):
    scene = context.scene
    doc = document(scene)
    if not doc.seams:
        raise ValueError("Pair pattern edges with the Sew tool before simulating.")
    ensure_collision(scene)
    panels = generated(scene,'panel')
    if not panels or any(o.get('dd_document')!=doc.dumps() or o.get('dd_spacing')!=scene.dd_spacing
                         or o.get('dd_units')!=metres_per_unit(scene) for o in panels) or len(panels)!=len(doc.patterns):
        panels = build_panels(context)
    context.view_layer.update()
    marker = signature(scene,panels)
    old = generated(scene,'simulation')
    if old and old[0].get('dd_signature')==marker:
        return old[0]
    stop(context)
    scene.frame_set(scene.frame_start)
    verts,faces,uvs,face_materials = [],[],[],[]
    maps = {}
    materials = []
    pin = []
    for panel in panels:
        offset = len(verts)
        verts.extend([tuple(panel.matrix_world @ v.co) for v in panel.data.vertices])
        uv = panel.data.uv_layers.active
        material_index = len(materials)
        materials.append(panel.data.materials[0])
        for face in panel.data.polygons:
            faces.append(tuple(offset+i for i in face.vertices))
            uvs.append([tuple(uv.data[i].uv) for i in face.loop_indices])
            face_materials.append(material_index)
        boundary = json.loads(panel['dd_boundaries'])
        maps[panel['dd_pattern_id']] = {key:[offset+i for i in ids] for key,ids in boundary.items()}
        if scene.dd_pin_top:
            highest = max(v.co.y for v in panel.data.vertices)
            pin.extend(offset+v.index for v in panel.data.vertices if highest-v.co.y<.002/metres_per_unit(scene))
    springs = set()
    for seam in doc.seams:
        a,b = maps[seam.a.pattern][seam.a.start],maps[seam.b.pattern][seam.b.start]
        if len(a)!=len(b):
            raise ValueError("Seam samples do not match. Rebuild the panels.")
        if seam.reverse:
            b = list(reversed(b))
        springs.update(tuple(sorted((x,y))) for x,y in zip(a,b))
    mesh = bpy.data.meshes.new('DD Sewn Fabric')
    mesh.from_pydata(verts,list(springs),faces)
    mesh.update()
    layer = mesh.uv_layers.new(name='Pattern UV')
    for poly,coords,mat in zip(mesh.polygons,uvs,face_materials):
        poly.material_index = mat
        for loop,uv in zip(poly.loop_indices,coords):
            layer.data[loop].uv = uv
    for mat in materials:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new('DD Garment Simulation',mesh)
    collection(scene).objects.link(obj)
    tag(obj,'simulation')
    obj['dd_signature'] = marker
    obj['dd_sewing_pairs'] = json.dumps(sorted(springs),separators=(',',':'))
    cloth = obj.modifiers.new('DD Cloth','CLOTH')
    settings = cloth.settings
    settings.use_sewing_springs = True
    settings.sewing_force_max = 50
    settings.quality = scene.dd_quality
    settings.mass = .3
    settings.tension_stiffness = 25
    settings.compression_stiffness = 25
    settings.shear_stiffness = 15
    settings.bending_stiffness = .5
    cloth.collision_settings.use_collision = True
    cloth.collision_settings.distance_min = .003/metres_per_unit(scene)
    cloth.collision_settings.use_self_collision = scene.dd_self_collision
    cloth.collision_settings.self_distance_min = .003/metres_per_unit(scene)
    cloth.collision_settings.collision_quality = 4
    cloth.point_cache.frame_start = scene.frame_start
    cloth.point_cache.frame_end = scene.frame_start+scene.dd_frames
    scene.frame_end = max(scene.frame_end,cloth.point_cache.frame_end)
    if pin:
        group = obj.vertex_groups.new(name='DD Pins')
        group.add(pin,1,'REPLACE')
        settings.vertex_group_mass = group.name
    remove_objects(old)
    for panel in panels:
        panel.hide_set(True)
        panel.hide_render = True
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    context.view_layer.update()
    return obj


def keep_drape(context):
    scene = context.scene
    stop(context)
    simulations = generated(scene,'simulation')
    if not simulations:
        raise ValueError("Simulate a garment first, then stop on the frame you want to keep.")
    source = simulations[0]
    panels = generated(scene,'panel')
    if source.get('dd_signature')!=signature(scene,panels):
        raise ValueError("The patterns or arrangement changed. Reset and simulate the current version first.")
    depsgraph = context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(source.evaluated_get(depsgraph),depsgraph=depsgraph)
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        pairs = json.loads(source['dd_sewing_pairs'])
        threshold = scene.dd_weld_distance/metres_per_unit(scene)
        parent = list(range(len(bm.verts)))
        def find(i):
            while parent[i]!=i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        unclosed = 0
        for a,b in pairs:
            if (bm.verts[a].co-bm.verts[b].co).length<=threshold:
                parent[find(b)] = find(a)
            else:
                unclosed += 1
        targets = {}
        groups = {}
        for i in range(len(parent)):
            groups.setdefault(find(i),[]).append(i)
        for members in groups.values():
            if len(members)>1:
                target = bm.verts[members[0]]
                target.co = sum((bm.verts[i].co for i in members),Vector())/len(members)
                for i in members[1:]:
                    targets[bm.verts[i]] = target
        bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
        if targets:
            bmesh.ops.weld_verts(bm,targetmap=targets)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(mesh)
    except Exception:
        bpy.data.meshes.remove(mesh)
        raise
    finally:
        bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new('DD Garment',mesh)
    collection(scene).objects.link(obj)
    obj.matrix_world = source.matrix_world.copy()
    tag(obj,'final')
    if scene.dd_thickness>0:
        modifier = obj.modifiers.new('Fabric Thickness','SOLIDIFY')
        modifier.thickness = scene.dd_thickness/metres_per_unit(scene)
        modifier.offset = 0
    source.hide_set(True)
    source.hide_render = True
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj,unclosed
