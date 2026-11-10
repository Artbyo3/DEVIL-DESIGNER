import json
import math
from contextlib import contextmanager
from functools import wraps
import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix,Vector,Euler
from .core import Document,arrangement_record
from .panel_cache import wrapped_positions


_busy=False


@contextmanager
def quiet():
    global _busy
    previous=_busy;_busy=True
    try:yield
    finally:_busy=previous


def build_guard(operation):
    @wraps(operation)
    def guarded(*args,**kwargs):
        with quiet():return operation(*args,**kwargs)
    return guarded


def effective_clearance(context,record):
    from . import garment
    value=record.get('clearance') if record['version']==3 else None
    return (context.scene.dd_clearance if value is None else value)/garment.metres_per_unit(context.scene)


def point_frame(context,record,setup=None):
    from .arrangement import resolve_point
    clearance=effective_clearance(context,record) if record['version']==3 else None
    resolved=resolve_point(context,record['volume'],record['point'],record['version'],clearance,setup)
    tangent=Vector(resolved['tangent']);up=Vector(resolved['up']);normal=Vector(resolved['normal'])
    frame=Matrix((tangent,up,normal)).transposed().to_4x4()
    frame.translation=resolved['point']
    return frame,resolved


def flat_vertices(pattern,obj,unit):
    import numpy
    cx=(min(v[0] for v in pattern.points)+max(v[0] for v in pattern.points))/2
    cy=(min(v[1] for v in pattern.points)+max(v[1] for v in pattern.points))/2
    if pattern.panel_origin:
        left,bottom,right,top=pattern.panel_origin['bounds'];cx=(left+right)/2;cy=(bottom+top)/2
    rest=numpy.zeros(len(obj.data.vertices)*3,dtype=numpy.float32)
    obj.data.attributes['dd_rest'].data.foreach_get('vector',rest)
    rest=rest.reshape(-1,3).astype(float)
    rest[:,0]=(rest[:,0]-cx)/unit;rest[:,1]=(rest[:,1]-cy)/unit;rest[:,2]=0
    return rest


def mesh_arrays(obj):
    import numpy
    mesh=obj.data
    mesh.calc_loop_triangles()
    triangles=numpy.zeros(len(mesh.loop_triangles)*3,dtype=numpy.int32)
    mesh.loop_triangles.foreach_get('vertices',triangles)
    edges=numpy.zeros(len(mesh.edges)*2,dtype=numpy.int32)
    mesh.edges.foreach_get('vertices',edges)
    return triangles.reshape(-1,3),edges.reshape(-1,2)


def enclosed(tree,origin):
    direction=Vector((.811,.317,.491)).normalized();crossings=0
    for _ in range(4096):
        hit,_,_,_=tree.ray_cast(origin,direction)
        if hit is None:break
        crossings+=1;origin=hit+direction*1e-6
    return crossings%2==1


def body_separation(tree,positions,triangles):
    import numpy
    from mathutils.bvhtree import BVHTree
    corners=positions.tolist()
    separations=[]
    for sample in corners:
        location,normal,_,distance=tree.find_nearest(sample)
        if location is None:continue
        separations.append(-distance if (Vector(sample)-location).dot(normal)<0 and enclosed(tree,Vector(sample)) else distance)
    overlaps=tree.overlap(BVHTree.FromPolygons(corners,triangles.tolist(),all_triangles=True)) if len(triangles) else []
    return numpy.asarray(separations),len({pair[1] for pair in overlaps})


def relax_strain(final,edges,rest,tree,target,iterations=800):
    import numpy
    start,end=edges[:,0],edges[:,1]
    count=numpy.maximum(numpy.bincount(edges.ravel(),minlength=len(final)).astype(float),1)[:,None]
    anchors=numpy.zeros_like(final);normals=numpy.zeros_like(final)
    for iteration in range(iterations):
        delta=final[end]-final[start]
        length=numpy.maximum(numpy.linalg.norm(delta,axis=1),1e-12)
        strain=length/rest
        if strain.max()<=1.1 and strain.min()>=.9:break
        if iteration%10==0:
            for index,point in enumerate(final.tolist()):
                location,_,_,_=tree.find_nearest(point)
                if location is None:continue
                outward=Vector(point)-location
                if outward.length>1e-12:anchors[index]=location;normals[index]=outward.normalized()
        correction=(.5*(1-rest/length))[:,None]*delta
        moves=numpy.zeros_like(final)
        numpy.add.at(moves,start,correction);numpy.add.at(moves,end,-correction)
        final=final+1.6*moves/count
        depth=target-numpy.einsum('ij,ij->i',final-anchors,normals)
        final=final+numpy.maximum(depth,0)[:,None]*normals
    return final


def has_opposite_piece(context,pattern,record):
    from . import garment
    return any(other.id!=pattern.id and other.arrangement and other.arrangement['volume']==record['volume']
               and other.arrangement['point']!=record['point'] for other in garment.document(context.scene).patterns)


def checked_positions(context,pattern,vertices,triangles,edges,record,frame,resolved,unit):
    import numpy
    from .ellipse_volumes import surface_positions
    from .panel_cache import body_tree
    tree=body_tree(context)
    delta=Matrix.Translation(Vector(record['translation'])/unit) @ Euler(record['rotation'],'XYZ').to_matrix().to_4x4()
    motion=numpy.array(frame @ delta @ frame.inverted_safe())
    target=resolved['clearance']-.001/unit
    flat=numpy.asarray(vertices,dtype=float)
    rest=numpy.maximum(numpy.linalg.norm(flat[edges[:,1]]-flat[edges[:,0]],axis=1),1e-12)
    inverse=numpy.linalg.inv(motion)
    extra=0.0;report=None
    half_wrap=has_opposite_piece(context,pattern,record)
    for _ in range(5):
        positions=surface_positions(vertices,resolved,.003/unit,.001/unit,record['overwrap'],record['direction'],extra,half_wrap)
        final=positions@motion[:3,:3].T+motion[:3,3]
        if len(edges):
            final=relax_strain(final,edges,rest,tree,resolved['clearance'])
            positions=final@inverse[:3,:3].T+inverse[:3,3]
        separations,overlaps=body_separation(tree,final,triangles)
        closest=float(separations.min()) if len(separations) else target
        report=dict(closest=closest*unit,overlaps=overlaps,inside=int((separations<-1e-6/unit).sum()),extra=extra*unit)
        if closest>=target and not overlaps:return positions,report,''
        extra+=max(target-closest,0)+(.002/unit if overlaps else .0005/unit)
    return positions,report,pattern.name+': could not keep '+format(resolved['clearance']*unit*100,'.1f')+' cm from the body here (closest '+format(report['closest']*100,'.1f')+' cm). Try Flat, a larger distance or finer mesh density.'


def position_panel(context,pattern,obj,center):
    from . import garment
    unit=garment.metres_per_unit(context.scene)
    avatar=context.scene.dd_avatar
    warning=''
    has_folds = any(feature.get('type') == 'FOLD' for feature in pattern.features)
    if pattern.arrangement:
        try:
            frame,resolved=point_frame(context,pattern.arrangement)
            radius=resolved['radius']
            if not pattern.arrangement['flat'] and not has_folds:
                clearance=context.scene.dd_clearance/unit
                left=min(point[0] for point in pattern.points);right=max(point[0] for point in pattern.points)
                if pattern.panel_origin:left,_,right,_=pattern.panel_origin['bounds']
                width=(right-left)/unit
                spiral=width>math.tau*radius
                minimum=(left-center[0])/unit
                if pattern.arrangement['version']==3:
                    import numpy
                    from .panel_cache import checked_surface
                    triangles,edges=mesh_arrays(obj)
                    flat=numpy.zeros(len(obj.data.vertices)*3,dtype=numpy.float32)
                    obj.data.vertices.foreach_get('co',flat)
                    positions,report,warning=checked_surface(context,pattern,flat.reshape(-1,3).astype(float),triangles,edges,frame,resolved,unit,pattern.arrangement)
                    inverse=frame.inverted_safe()
                    for vertex,position in zip(obj.data.vertices,positions):
                        vertex.co=inverse @ Vector(position)
                    obj['dd_body_check']=json.dumps(report)
                elif 'stack' in resolved:
                    payload=json.dumps(([tuple(vertex.co) for vertex in obj.data.vertices],resolved,width,minimum,.001/unit),separators=(',',':'))
                    positions=wrapped_positions(payload)
                    inverse=frame.inverted_safe()
                    for vertex,position in zip(obj.data.vertices,positions):
                        vertex.co=inverse @ Vector(position)
                else:
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
            if has_folds and not pattern.arrangement['flat']:return pattern.name + ': Folded panels use flat placement to preserve their creases.'
            return warning
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


def preview_positions(context,identity,volume,point,setup=None):
    from . import editor,garment
    active=editor._active
    document=active.session.document if active is not None and active._scene==context.scene else garment.document(context.scene)
    pattern=document.find(identity)
    obj=next((panel for panel in garment.generated(context.scene,'panel') if panel.get('dd_pattern_id')==identity),None)
    if pattern is None or obj is None:return None
    unit=garment.metres_per_unit(context.scene)
    previous=pattern.arrangement if pattern.arrangement and pattern.arrangement['version']==3 else None
    options={key:previous[key] for key in ('clearance','direction','overwrap')} if previous else {}
    record=arrangement_record(volume,point,previous['flat'] if previous else False,version=3,**options)
    frame,resolved=point_frame(context,record,setup)
    vertices=flat_vertices(pattern,obj,unit)
    has_folds=any(feature.get('type')=='FOLD' for feature in pattern.features)
    warning=''
    if record['flat'] or has_folds:
        positions=[tuple(frame @ Vector(position)) for position in vertices.tolist()]
    else:
        from .panel_cache import checked_surface
        triangles,edges=mesh_arrays(obj)
        positions,_,warning=checked_surface(context,pattern,vertices,triangles,edges,frame,resolved,unit,record)
        positions=positions.tolist()
        return dict(positions=positions,edges=edges.tolist(),warning=warning)
    return dict(positions=positions,edges=mesh_arrays(obj)[1].tolist(),warning=warning)


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
    return json.dumps([avatar.name_full,avatar.data.name_full if avatar.data else '',[list(row) for row in evaluated.matrix_world],
                       [list(point) for point in evaluated.bound_box],
                       context.scene.dd_clearance],separators=(',',':'))+chr(10)+avatar.get('dd_arrangement_volumes','')


def sewing_only_change(document,panels):
    if len(panels)!=len(document.patterns) or not panels:return False
    expected=json.loads(document.dumps())
    seams=expected['seams'];changed=False
    expected['seams']=[]
    for panel in panels:
        try:previous=json.loads(Document.loads(panel.get('dd_document','')).dumps())
        except (ValueError,TypeError,KeyError):return False
        changed=changed or previous['seams']!=seams
        previous['seams']=[]
        if previous!=expected:return False
    return changed


def sync(context,preserve_sewing=False):
    global _busy
    if _busy:return []
    from . import garment
    scene=context.scene
    document=garment.document(scene)
    panels=garment.generated(scene,'panel')
    kept={panel.get('dd_pattern_id'):panel for panel in panels}
    duplicates=[panel for panel in panels if kept[panel.get('dd_pattern_id')]!=panel]
    if duplicates:
        garment.remove_objects(duplicates)
        panels=garment.generated(scene,'panel')
    if not document.patterns:
        if panels:garment.reset(context);garment.remove_objects(panels)
        return []
    if all(pattern.placement_mode=='LEGACY' and not pattern.arrangement for pattern in document.patterns):return panels
    from .arrangement import fit_in_progress
    if any(pattern.arrangement for pattern in document.patterns) and fit_in_progress(context,bool(panels)):return panels
    serialized=document.dumps()
    frame=avatar_signature(context)
    if any(panel.get('dd_document')!=serialized for panel in panels) and all(panel.get('dd_avatar_frame')==frame for panel in panels):
        from .piece_states import synchronize_metadata
        if synchronize_metadata(context,document,panels):return panels
    if len(panels)==len(document.patterns) and all(panel.get('dd_document')==serialized and panel.get('dd_spacing')==scene.dd_spacing and panel.get('dd_units')==garment.metres_per_unit(scene) and panel.get('dd_avatar_frame')==frame for panel in panels):return panels
    preserve=preserve_sewing and sewing_only_change(document,panels) and all(panel.get('dd_avatar_frame')==frame for panel in panels)
    transforms={panel.get('dd_pattern_id'):{name:getattr(panel,name) if name=='rotation_mode' else tuple(getattr(panel,name)) for name in ('location','rotation_mode','rotation_euler','rotation_quaternion','rotation_axis_angle','scale')} for panel in panels} if preserve else {}
    _busy=True
    try:
        result=garment.build_panels(context)
        for panel in result:
            transform=transforms.get(panel.get('dd_pattern_id'))
            if transform is not None:
                for name,value in transform.items():setattr(panel,name,value)
        if transforms:context.view_layer.update()
        return result
    finally:_busy=False


def arrange_piece(context,identity,volume,point,flat=False):
    from . import editor,garment
    from .arrangement import ensure_volumes,mirror_point,resolve_point,upgrade_volumes
    from .linked_editing import pair_for
    resolve_point(context,volume,point)
    upgrade_volumes(context)
    mirrored=mirror_point(ensure_volumes(context),volume,point)
    if mirrored is not None:resolve_point(context,*mirrored)
    def record_for(pattern):
        previous=pattern.arrangement if pattern.arrangement and pattern.arrangement['version']==3 else None
        options={key:previous[key] for key in ('clearance','direction','overwrap')} if previous else {}
        return arrangement_record(volume,point,flat,version=3,**options)
    def place(document,pattern):
        record=record_for(pattern)
        pattern.arrangement=record;pattern.panel_origin=None
        pair=pair_for(document,pattern.id)
        if mirrored is None or pair is None or not pair['enabled']:return
        twin=document.find(next(member for member in pair['members'] if member!=pattern.id))
        twin.arrangement=dict(record,volume=mirrored[0],point=mirrored[1]);twin.panel_origin=None
    active=editor._active
    if active is not None and active._scene==context.scene:
        capture(context)
        pattern=active.session.document.find(identity)
        if pattern is None:raise ValueError('Select a piece before choosing an arrangement point.')
        def apply():
            place(active.session.document,pattern)
        active.run_edit(lambda:active.session.commit(apply),
                        pattern.name+' arranged at '+volume+' / '+point+'.')
    else:
        document=capture(context);pattern=document.find(identity)
        if pattern is None:raise ValueError('Select a piece before choosing an arrangement point.')
        place(document,pattern)
        context.scene.dd_document=document.dumps();garment.build_panels(context)


def update_arrangement(session,identity,**changes):
    pattern=session.document.find(identity)
    if pattern is None or not pattern.arrangement:raise ValueError('Arrange the piece at a body point first.')
    record=pattern.arrangement
    if record['version']!=3:
        record=dict(record,version=3,clearance=None,direction=1,overwrap=False)
    updated=dict(record,**changes)
    if updated==pattern.arrangement:return False
    def apply():
        pattern.arrangement=updated
    return session.commit(apply)


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


def rebuild_arranged(context):
    scene=context.scene
    if scene.dd_document:
        from . import garment
        document=capture(context)
        if any(pattern.placement_mode!='LEGACY' for pattern in document.patterns):garment.build_panels(context)


def fit_completed(job):
    from . import editor
    context=bpy.context
    scene=job.scene
    try:
        if job.state=='ready':
            scene['dd_arrangement_message']=''
            if context.scene==scene and not _busy:rebuild_arranged(context)
            message='Arrangement points ready on '+job.avatar.name+'.'
        elif job.state=='failed':
            message=job.error;scene['dd_arrangement_message']=job.error
        else:return
    except (ValueError,RuntimeError,ReferenceError) as failure:
        message=str(failure)
    active=editor._active
    if active is not None and active._scene==scene:active.message=message
    for window in getattr(context.window_manager,'windows',()):
        for area in window.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()


def avatar_changed(scene,context):
    if context is None or scene.dd_avatar is None:return
    from .arrangement import ensure_volumes,start_fit
    try:
        if scene.dd_avatar.get('dd_arrangement_volumes') is None:
            start_fit(context,completed=fit_completed)
            scene['dd_arrangement_message']='Preparing arrangement points for '+scene.dd_avatar.name+'...'
            return
        ensure_volumes(context)
        rebuild_arranged(context)
    except (ValueError,RuntimeError) as failure:
        scene['dd_arrangement_message']=str(failure)


def deformation_check():
    from .arrangement import stale_fit,start_fit
    context=bpy.context
    try:
        if context.scene.dd_avatar is not None and stale_fit(context):
            start_fit(context,keep=True,completed=fit_completed)
    except (ValueError,ReferenceError,AttributeError):pass
    return None


@persistent
def capture_updates(scene,depsgraph):
    if _busy or not getattr(scene,'dd_document','') or not any(update.is_updated_transform or update.is_updated_geometry for update in depsgraph.updates):return
    if bpy.context.scene!=scene:return
    try:
        capture(bpy.context)
        avatar=scene.dd_avatar
        if avatar is not None and any(getattr(update.id,'original',update.id) in (avatar,avatar.data) for update in depsgraph.updates):
            sync(bpy.context)
            if any(update.is_updated_geometry and getattr(update.id,'original',update.id)==avatar for update in depsgraph.updates):
                if bpy.app.timers.is_registered(deformation_check):bpy.app.timers.unregister(deformation_check)
                bpy.app.timers.register(deformation_check,first_interval=.25)
    except (ValueError,ReferenceError):return


@persistent
def before_save(_):
    if getattr(bpy.context.scene,'dd_document',''):capture(bpy.context)


def register():
    bpy.app.handlers.depsgraph_update_post.append(capture_updates)
    bpy.app.handlers.save_pre.append(before_save)


def unregister():
    from .arrangement import cancel_fits
    from .panel_cache import clear_arrangement_caches
    cancel_fits();clear_arrangement_caches()
    if bpy.app.timers.is_registered(deformation_check):bpy.app.timers.unregister(deformation_check)
    wrapped_positions.cache_clear()
    for handlers,callback in ((bpy.app.handlers.depsgraph_update_post,capture_updates),(bpy.app.handlers.save_pre,before_save)):
        if callback in handlers:handlers.remove(callback)
