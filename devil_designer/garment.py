import hashlib
import json
import math
import bpy
import bmesh
from mathutils import Vector
from .core import Document
from .meshing import fabric_mesh
from .density import boundary_plan,effective_spacing
from .core import area
from .native_features import decorate_mesh,apply_presets,add_anchors
from .live_panels import build_guard
from . import layering, seam_shrink
from .sewing_preview import resolve_sewing

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
    remove_objects(generated(context.scene,'anchor'))
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


@build_guard
def build_panels(context):
    scene = context.scene
    scene['dd_arrangement_message']=''
    doc = document(scene)
    if not doc.patterns:
        raise ValueError("Draw at least one closed pattern first.")
    doc.validate_seams()
    counts = boundary_plan(doc,scene.dd_spacing)
    unit = metres_per_unit(scene)
    all_points = [pt for p in doc.patterns for pt in p.outline()]
    minx,miny = min(p[0] for p in all_points),min(p[1] for p in all_points)
    extent = max(max(p[0] for p in all_points)-minx,max(p[1] for p in all_points)-miny,.001)
    if doc.uv_layout:
        (minx,miny),extent=doc.uv_layout['origin'],doc.uv_layout['scale']
    else:
        doc.uv_layout=dict(origin=[minx,miny],scale=extent)
        scene.dd_document=doc.dumps()
    prepared = []
    try:
        for piece_index,p in enumerate(doc.patterns):
            coords,faces,boundaries = fabric_mesh(doc,p,effective_spacing(p,scene.dd_spacing),counts)
            cx = (min(v[0] for v in p.points)+max(v[0] for v in p.points))/2
            cy = (min(v[1] for v in p.points)+max(v[1] for v in p.points))/2
            if p.panel_origin and (p.placement_mode=='LEGACY' or p.arrangement):
                left,bottom,right,top=p.panel_origin['bounds'];cx=(left+right)/2;cy=(bottom+top)/2
            mesh = bpy.data.meshes.new('DD '+p.name)
            prepared.append((p,mesh,boundaries,(cx,cy),None))
            def position(x,y):
                x,y=x-cx,y-cy
                if p.wrap_radius>0 and p.placement_mode=='LEGACY' and p.arrangement is None:
                    angle=x/p.wrap_radius
                    return (math.sin(angle)*p.wrap_radius/unit,y/unit,(1-math.cos(angle))*p.wrap_radius/unit)
                return (x/unit,y/unit,0)
            mesh.from_pydata([position(x,y) for x,y in coords],[],faces)
            uv = mesh.uv_layers.new(name='Pattern UV')
            for loop in mesh.loops:
                x,y = coords[loop.vertex_index]
                uv.data[loop.index].uv = ((x-minx)/extent,(y-miny)/extent)
            mesh.update()
            metadata=decorate_mesh(mesh,piece_index,coords,counts.outputs[p.id])
            prepared[-1]=(p,mesh,boundaries,(cx,cy),metadata)
    except Exception:
        for _,mesh,_,_,_ in prepared:
            bpy.data.meshes.remove(mesh)
        raise
    reset(context)
    old = {o.get('dd_pattern_id'):o for o in generated(scene,'panel')}
    avatar = scene.dd_avatar
    has_avatar = (avatar is not None and getattr(avatar, 'type', None) == 'MESH' and avatar in list(scene.objects)
                  and avatar.get('dd_kind') not in {'panel', 'simulation', 'final', 'anchor'}
                  and bool(avatar.data.vertices))
    if has_avatar:
        low, high = bounds(avatar)
        center_3d = (low + high) / 2
        body_height = high.z - low.z
        gap = scene.dd_clearance / unit
        ref_x = getattr(scene, 'dd_reference_x', 0.0)
        ref_y = getattr(scene, 'dd_reference_y', 0.0)
        placed = getattr(scene, 'dd_reference_placed', False)
    coll = collection(scene)
    result = []
    source_matrices={identity:obj.matrix_world.copy() for identity,obj in old.items()}
    for index,(p,mesh,boundaries,center,metadata) in enumerate(prepared):
        obj = old.pop(p.id,None)
        created=obj is None
        if obj is None:
            obj = bpy.data.objects.new(p.name,mesh)
            coll.objects.link(obj)
            if has_avatar and p.placement_mode=='LEGACY' and p.arrangement is None:
                is_back = 'back' in p.name.casefold() or (index == 1 and len(prepared) == 2)
                side = 1 if is_back else -1
                pan_x = center_3d.x if is_back else (center_3d.x + (center[0] - ref_x) / unit)
                pan_y = high.y + gap if side > 0 else low.y - gap
                pan_z = (low.z + (center[1] - ref_y) / unit) if (placed and center[1] > ref_y) else (low.z + body_height * (.72 if body_height * unit > 1 else .68))
                obj.location = (pan_x, pan_y, pan_z)
                obj.rotation_euler = (math.pi/2, 0, math.pi if side > 0 else 0)
            else:
                obj.location = (center[0]/unit, 0, center[1]/unit)
                obj.rotation_euler = (math.pi/2, 0, 0)
        else:
            previous = obj.data
            obj.data = mesh
            if previous.users==0:
                bpy.data.meshes.remove(previous)
        if p.placement_mode!='LEGACY' or p.arrangement:
            from .live_panels import position_panel
            warning=position_panel(context,p,obj,center)
            if warning:scene['dd_arrangement_message']=(scene['dd_arrangement_message']+' '+warning).strip()
        elif created and p.panel_origin and p.panel_origin['source']!=p.id and p.panel_origin['source'] in source_matrices:
            obj.matrix_world=source_matrices[p.panel_origin['source']]
        context.view_layer.update()
        source_matrices[p.id]=obj.matrix_world.copy()
        tag(obj,'panel')
        obj['dd_pattern_id'] = p.id
        obj['dd_edge_samples']=json.dumps(metadata['samples'],separators=(',',':'))
        obj['dd_anchor_indices']=json.dumps(metadata['anchors'],separators=(',',':'))
        boundaries={key:[i for _,i in values] for key,values in metadata['samples'].items()}
        obj['dd_boundaries'] = json.dumps(boundaries,separators=(',',':'))
        for group in list(obj.vertex_groups):obj.vertex_groups.remove(group)
        group=obj.vertex_groups.new(name='Piece '+p.name)
        group.add(list(range(len(mesh.vertices))),1,'REPLACE')
        obj['dd_document'] = doc.dumps()
        obj['dd_spacing'] = scene.dd_spacing
        obj['dd_units'] = unit
        obj.name = p.name
        obj.data.materials.append(material(index))
        obj.color = material(index).diffuse_color
        result.append(obj)
    remove_objects(list(old.values()))
    from .live_panels import avatar_signature
    frame=avatar_signature(context)
    for obj in result:obj['dd_avatar_frame']=frame
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
    body_height = high.z-low.z
    default_z = low.z+body_height*(.72 if body_height*unit>1 else .68)
    gap = scene.dd_clearance/unit
    doc = document(scene)
    placed = getattr(scene, 'dd_reference_placed', False)
    ref_y = getattr(scene, 'dd_reference_y', 0.0)
    for index,obj in enumerate(panels):
        side = -1 if index==0 else 1
        pattern = doc.find(obj.get('dd_pattern_id'))
        cy = (min(v[1] for v in pattern.points)+max(v[1] for v in pattern.points))/2 if pattern and pattern.points else None
        panel_z = (low.z + (cy - ref_y) / unit) if (cy is not None and placed and cy > ref_y) else default_z
        obj.location = (center.x,(low.y-gap if side<0 else high.y+gap),panel_z)
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
    selection=layering.wear_over_selection(scene)
    if selection:
        data.append(selection)
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
    from . import piece_states
    piece_states.update_display(context,doc)
    if piece_states.required(doc):
        return piece_states.compile_run(context,doc)
    ensure_collision(scene)
    layering.prepare_colliders(context)
    panels = generated(scene,'panel')
    if not panels or any(o.get('dd_document')!=doc.dumps() or o.get('dd_spacing')!=scene.dd_spacing
                         or o.get('dd_units')!=metres_per_unit(scene) for o in panels) or len(panels)!=len(doc.patterns):
        panels = build_panels(context)
        doc=document(scene)
    context.view_layer.update()
    marker = signature(scene,panels)
    old = generated(scene,'simulation')
    old_anchors=generated(scene,'anchor')
    if old and old[0].get('dd_signature')==marker:
        return old[0]
    stop(context)
    scene.frame_set(scene.frame_start)
    verts,faces,uvs,face_materials = [],[],[],[]
    maps = {}
    anchor_indices={}
    pieces=[]
    piece_faces=[]
    materials = []
    pin = []
    for piece_index,panel in enumerate(panels):
        offset = len(verts)
        pattern=doc.find(panel['dd_pattern_id'])
        pieces.append((list(range(offset,offset+len(panel.data.vertices))),abs(area(pattern.outline())),pattern.preset))
        verts.extend([tuple(panel.matrix_world @ v.co) for v in panel.data.vertices])
        uv = panel.data.uv_layers.active
        material_index = len(materials)
        materials.append(panel.data.materials[0])
        for face in panel.data.polygons:
            faces.append(tuple(offset+i for i in face.vertices))
            uvs.append([tuple(uv.data[i].uv) for i in face.loop_indices])
            face_materials.append(material_index)
            piece_faces.append(piece_index+1)
        samples=json.loads(panel['dd_edge_samples'])
        maps[panel['dd_pattern_id']]={key:[[t,offset+i] for t,i in values] for key,values in samples.items()}
        anchor_indices.update({key:offset+i for key,i in json.loads(panel['dd_anchor_indices']).items()})
        if scene.dd_pin_top:
            highest = max(v.co.y for v in panel.data.vertices)
            pin.extend(offset+v.index for v in panel.data.vertices if highest-v.co.y<.002/metres_per_unit(scene))
    plan=boundary_plan(doc,scene.dd_spacing)
    springs,inspection=resolve_sewing(maps,plan)
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
    for name in ('dd_piece','.sculpt_face_set'):
        attr=mesh.attributes.new(name=name,type='INT',domain='FACE')
        for item,value in zip(attr.data,piece_faces):item.value=value
    obj = bpy.data.objects.new('DD Garment Simulation',mesh)
    collection(scene).objects.link(obj)
    tag(obj,'simulation')
    obj['dd_signature'] = marker
    obj['dd_sewing_pairs'] = json.dumps(sorted(springs),separators=(',',':'))
    obj['dd_sewing_inspection'] = json.dumps(inspection,separators=(',',':'))
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
    for ids,_,preset in pieces:
        pattern=doc.patterns[len(obj.vertex_groups)]
        group=obj.vertex_groups.new(name='Piece '+pattern.name)
        group.add(ids,1,'REPLACE')
    obj['dd_piece_ids']=json.dumps([p.id for p in doc.patterns])
    apply_presets(obj,cloth,pieces)
    if any(seam.shrink for seam in doc.seams):
        seam_shrink.apply(doc,obj,cloth,maps,plan)
    cloth.collision_settings.use_collision = True
    cloth.collision_settings.distance_min = .003/metres_per_unit(scene)
    cloth.collision_settings.use_self_collision = scene.dd_self_collision
    cloth.collision_settings.self_distance_min = (.001 if any(seam.shrink for seam in doc.seams) else .003)/metres_per_unit(scene)
    cloth.collision_settings.collision_quality = 4
    cloth.point_cache.frame_start = scene.frame_start
    cloth.point_cache.frame_end = scene.frame_start+scene.dd_frames
    scene.frame_end = max(scene.frame_end,cloth.point_cache.frame_end)
    if pin:
        group = obj.vertex_groups.new(name='DD Pins')
        group.add(pin,1,'REPLACE')
        settings.vertex_group_mass = group.name
    add_anchors(context,obj,cloth,doc,anchor_indices)
    remove_objects(old_anchors)
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
    mesh = bpy.data.meshes.new_from_object(source.evaluated_get(depsgraph),preserve_all_data_layers=True,depsgraph=depsgraph)
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
        bm.verts.index_update()
        deform=bm.verts.layers.deform.active
        weights=[dict(v[deform]) if deform else {} for v in bm.verts]
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
    obj['dd_piece_ids']=source.get('dd_piece_ids','[]')
    for source_group in source.vertex_groups:obj.vertex_groups.new(name=source_group.name)
    for i,values in enumerate(weights):
        for group,weight in values.items():
            if group<len(obj.vertex_groups):obj.vertex_groups[group].add([i],weight,'REPLACE')
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
