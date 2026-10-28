import json
import math
from functools import wraps
import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix,Vector,Euler
from .core import arrangement_record


_busy=False


def build_guard(operation):
    @wraps(operation)
    def guarded(*args,**kwargs):
        global _busy
        previous=_busy;_busy=True
        try:return operation(*args,**kwargs)
        finally:_busy=previous
    return guarded


def point_frame(context,record):
    from .arrangement import resolve_point
    resolved=resolve_point(context,record['volume'],record['point'])
    tangent=Vector(resolved['tangent']);up=Vector(resolved['up']);normal=Vector(resolved['normal'])
    frame=Matrix((tangent,up,normal)).transposed().to_4x4()
    frame.translation=resolved['point']
    return frame,resolved


def position_panel(context,pattern,obj,center):
    from . import garment
    unit=garment.metres_per_unit(context.scene)
    avatar=context.scene.dd_avatar
    warning=''
    if pattern.arrangement:
        try:
            frame,resolved=point_frame(context,pattern.arrangement)
            radius=resolved['radius']
            if not pattern.arrangement['flat']:
                clearance=context.scene.dd_clearance/unit
                left=min(point[0] for point in pattern.points);right=max(point[0] for point in pattern.points)
                if pattern.panel_origin:left,_,right,_=pattern.panel_origin['bounds']
                width=(right-left)/unit
                spiral=width>math.tau*radius
                minimum=(left-center[0])/unit
                for vertex in obj.data.vertices:
                    horizontal,vertical=vertex.co.x,vertex.co.y
                    angle=horizontal/radius
                    layer=radius+(max(clearance,.001/unit)*(horizontal-minimum)/(math.tau*radius) if spiral else 0)
                    vertex.co=(layer*math.sin(angle),vertical,layer*math.cos(angle)-radius)
                obj.data.update()
            delta=Matrix.Translation(Vector(pattern.arrangement['translation'])/unit) @ Euler(pattern.arrangement['rotation'],'XYZ').to_matrix().to_4x4()
            obj.matrix_world=frame @ delta
            obj['dd_arrangement_base']=json.dumps([list(row) for row in frame])
            obj['dd_arrangement_key']=pattern.arrangement['volume']+'\n'+pattern.arrangement['point']
            return ''
        except ValueError as failure:
            warning=pattern.name+': '+str(failure)+' Using the 2D layout position.'
    if avatar is not None:
        low,high=garment.bounds(avatar)
        obj.location=((low.x+high.x)/2+center[0]/unit,low.y-context.scene.dd_clearance/unit,low.z+center[1]/unit)
    else:
        obj.location=(center[0]/unit,0,center[1]/unit)
    obj.rotation_euler=(math.pi/2,0,0)
    obj.scale=(1,1,1)
    for key in ('dd_arrangement_base','dd_arrangement_key'):
        if key in obj:del obj[key]
    return warning


def capture(context,document=None):
    from . import editor,garment,history
    scene=context.scene
    active=editor._active
    if document is None and active is not None and active._scene==scene and active._stored==scene.dd_document:
        document=active.session.document
    document=document or garment.document(scene)
    changed=False;unit=garment.metres_per_unit(scene)
    for obj in garment.generated(scene,'panel'):
        pattern=document.find(obj.get('dd_pattern_id'))
        if pattern is None or not pattern.arrangement or not obj.get('dd_arrangement_base'):continue
        key=pattern.arrangement['volume']+'\n'+pattern.arrangement['point']
        if obj.get('dd_arrangement_key')!=key:continue
        base=Matrix(json.loads(obj['dd_arrangement_base']))
        delta=base.inverted_safe() @ obj.matrix_world
        translation=[float(value*unit) for value in delta.translation]
        rotation=[float(value) for value in delta.to_euler('XYZ')]
        if any(abs(before-after)>1e-6 for before,after in zip(pattern.arrangement['translation']+pattern.arrangement['rotation'],translation+rotation)):
            pattern.arrangement=dict(pattern.arrangement,translation=translation,rotation=rotation)
            changed=True
    if changed:
        scene.dd_document=document.dumps()
        for panel in garment.generated(scene,'panel'):panel['dd_document']=scene.dd_document
        if active is not None and active._scene==scene and active.session.document is document:
            active._stored=scene.dd_document
            scene.dd_history=history.store(active.session)
    return document


def avatar_signature(context):
    avatar=context.scene.dd_avatar
    if avatar is None:return ''
    evaluated=avatar.evaluated_get(context.evaluated_depsgraph_get())
    return json.dumps([avatar.as_pointer(),[list(row) for row in evaluated.matrix_world],
                       [list(point) for point in evaluated.bound_box],avatar.get('dd_arrangement_volumes',''),
                       context.scene.dd_clearance],separators=(',',':'))


def sync(context):
    global _busy
    if _busy:return []
    from . import garment
    scene=context.scene
    document=garment.document(scene)
    panels=garment.generated(scene,'panel')
    if not document.patterns:
        if panels:garment.reset(context);garment.remove_objects(panels)
        return []
    if all(pattern.placement_mode=='LEGACY' and not pattern.arrangement for pattern in document.patterns):return panels
    serialized=document.dumps()
    frame=avatar_signature(context)
    if len(panels)==len(document.patterns) and all(panel.get('dd_document')==serialized and panel.get('dd_spacing')==scene.dd_spacing and panel.get('dd_units')==garment.metres_per_unit(scene) and panel.get('dd_avatar_frame')==frame for panel in panels):return panels
    _busy=True
    try:return garment.build_panels(context)
    finally:_busy=False


def arrange_piece(context,identity,volume,point,flat=False):
    from . import editor,garment
    from .arrangement import resolve_point
    resolve_point(context,volume,point)
    active=editor._active
    if active is not None and active._scene==context.scene:
        capture(context)
        pattern=active.session.document.find(identity)
        if pattern is None:raise ValueError('Select a piece before choosing an arrangement point.')
        def apply():
            pattern.arrangement=arrangement_record(volume,point,flat);pattern.panel_origin=None
        active.run_edit(lambda:active.session.commit(apply),
                        pattern.name+' arranged at '+volume+' / '+point+'.')
    else:
        document=capture(context);pattern=document.find(identity)
        if pattern is None:raise ValueError('Select a piece before choosing an arrangement point.')
        pattern.arrangement=arrangement_record(volume,point,flat)
        pattern.panel_origin=None
        context.scene.dd_document=document.dumps();garment.build_panels(context)


def reset_piece(session,identity):
    pattern=session.document.find(identity)
    if pattern is None:raise ValueError('Select a piece to reset.')
    def apply():
        pattern.arrangement=None;pattern.placement_mode='LAYOUT';pattern.panel_origin=None
    return session.commit(apply)


def intersection_warnings(context):
    from . import garment
    from mathutils.bvhtree import BVHTree
    avatar=context.scene.dd_avatar
    if avatar is None:return []
    document=garment.document(context.scene)
    low,high=garment.bounds(avatar);warnings=[];body_tree=None
    for panel in garment.generated(context.scene,'panel'):
        pattern=document.find(panel.get('dd_pattern_id'))
        if pattern is None or pattern.arrangement or pattern.placement_mode=='LEGACY':continue
        points=[panel.matrix_world @ vertex.co for vertex in panel.data.vertices]
        if any(max(point[axis] for point in points)<low[axis] or min(point[axis] for point in points)>high[axis] for axis in range(3)):continue
        if body_tree is None:
            evaluated=avatar.evaluated_get(context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:body_tree=BVHTree.FromPolygons([evaluated.matrix_world @ vertex.co for vertex in mesh.vertices],
                                             [tuple(face.vertices) for face in mesh.polygons])
            finally:evaluated.to_mesh_clear()
        panel_tree=BVHTree.FromPolygons(points,[tuple(face.vertices) for face in panel.data.polygons])
        intersects=bool(body_tree.overlap(panel_tree))
        if not intersects:
            direction=Vector((.811,.317,.491)).normalized();origin=points[0].copy();crossings=0
            for _ in range(len(avatar.data.polygons)+1):
                hit,normal,index,distance=body_tree.ray_cast(origin,direction)
                if hit is None:break
                crossings+=1;origin=hit+direction*1e-6
            intersects=crossings%2==1
        if intersects:warnings.append(pattern.name+': unarranged panel intersects the body; simulation will still run.')
    return warnings


def avatar_changed(scene,context):
    if context is None or scene.dd_avatar is None:return
    from .arrangement import ensure_volumes
    try:
        ensure_volumes(context)
        if scene.dd_document:
            from . import garment
            document=capture(context)
            if any(pattern.placement_mode!='LEGACY' for pattern in document.patterns):garment.build_panels(context)
    except (ValueError,RuntimeError) as failure:
        scene['dd_arrangement_message']=str(failure)


@persistent
def capture_updates(scene,depsgraph):
    if _busy or not getattr(scene,'dd_document','') or not any(update.is_updated_transform or update.is_updated_geometry for update in depsgraph.updates):return
    if bpy.context.scene!=scene:return
    try:
        capture(bpy.context)
        avatar=scene.dd_avatar
        if avatar is not None and any(getattr(update.id,'original',update.id) in (avatar,avatar.data) for update in depsgraph.updates):sync(bpy.context)
    except (ValueError,ReferenceError):return


@persistent
def before_save(_):
    if getattr(bpy.context.scene,'dd_document',''):capture(bpy.context)


def register():
    bpy.app.handlers.depsgraph_update_post.append(capture_updates)
    bpy.app.handlers.save_pre.append(before_save)


def unregister():
    for handlers,callback in ((bpy.app.handlers.depsgraph_update_post,capture_updates),(bpy.app.handlers.save_pre,before_save)):
        if callback in handlers:handlers.remove(callback)
