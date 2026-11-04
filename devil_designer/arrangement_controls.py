import math
import time
from dataclasses import dataclass
from functools import lru_cache
import blf
import bpy
import gpu
from mathutils import Vector
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from . import arrangement,live_panels,ui_system


_draw_handle=None
_preview_handle=None
_keymaps=[]
_world_cache=None
_projection_cache=None
_batch_cache=None
_visibility_cache=None
_shader=None
DISK_SEGMENTS=24
OCCLUSION_MARGIN=1e-4
OCCLUSION_PASSES=16


@dataclass
class PointInteraction:
    state:str='IDLE'
    point:tuple=None
    origin:tuple=(0,0)
    last:tuple=(0,0)
    setup:dict=None
    angle:float=0.0
    height:float=0.0
    preview:dict=None
    preview_key:tuple=None
    preview_time:float=0.0
    length:float=0.0


_interaction=PointInteraction()


def display_setup():
    return _interaction.setup if _interaction.state=='DRAGGING' else None


def display_world_points(context):
    global _world_cache
    arrangement._volume_avatar(context)
    setup=display_setup()
    key=(context.scene.as_pointer(),context.view_layer.as_pointer(),live_panels.avatar_signature(context),
         (_interaction.point,_interaction.angle,_interaction.height) if setup else None)
    if _world_cache is None or _world_cache[0]!=key:
        points=[dict(point,slot=slot) for slot,point in enumerate(arrangement.world_points(context,setup,wait=False))]
        _world_cache=(key,points,arrangement._volume_frame(context)[1][2])
    return _world_cache[1]


def display_panel(context):
    from . import editor
    active=editor._active
    return active.canvas_layout.panel if active is not None and active._area==context.area else None


def display_shader():
    interface=gpu.types.GPUShaderCreateInfo()
    interface.vertex_in(0,'VEC3','position')
    interface.vertex_in(1,'VEC2','offset')
    interface.vertex_in(2,'VEC3','normal')
    interface.vertex_in(3,'FLOAT','coverage')
    interface.vertex_in(4,'FLOAT','slot')
    interface.push_constant('MAT4','viewProjection')
    interface.push_constant('VEC2','viewport')
    interface.push_constant('VEC4','panel')
    interface.push_constant('VEC4','color')
    interface.push_constant('VEC4','eye')
    interface.push_constant('FLOAT','markerWorld')
    interface.sampler(0,'FLOAT_2D','visibilityMap')
    interface.push_constant('BOOL','srgbTarget')
    stage=gpu.types.GPUStageInterfaceInfo('dd_arrangement_interface')
    stage.smooth('FLOAT','edgeCoverage')
    interface.vertex_out(stage)
    interface.fragment_out(0,'VEC4','fragColor')
    interface.vertex_source('''
bool covered(vec4 clip) {
    vec2 pixel = (clip.xy / clip.w + vec2(1.0)) * viewport * 0.5;
    return all(greaterThanEqual(pixel, panel.xy)) && all(lessThanEqual(pixel, panel.zw));
}
void main() {
    vec3 toward = eye.w > 0.5 ? eye.xyz - position : eye.xyz;
    vec3 view = normalize(toward);
    vec3 surface = normalize(normal);
    float facing = dot(surface, view);
    edgeCoverage = coverage;
    vec3 disc = normalize(surface + view * (facing < 0.0 ? -0.18 : 0.18));
    vec3 side = normalize(cross(disc, abs(disc.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
    vec3 across = side * offset.x + cross(disc, side) * offset.y;
    vec3 screenRight = vec3(viewProjection[0][0], viewProjection[1][0], viewProjection[2][0]);
    screenRight = normalize(screenRight - view * dot(screenRight, view));
    vec2 flattened = vec2(dot(across, screenRight), dot(across, cross(view, screenRight)));
    vec4 clip = viewProjection * vec4(position, 1.0);
    if (clip.w <= 0.0 || covered(clip) || texelFetch(visibilityMap, ivec2(int(slot + 0.5), 0), 0).r < 0.5) {
        gl_Position = vec4(2.0, 2.0, 0.0, 1.0);
    } else {
        float pixelsPerUnit = length(vec3(viewProjection[0][1], viewProjection[1][1], viewProjection[2][1])) * viewport.y * 0.5 / clip.w;
        float zoom = clamp(markerWorld * pixelsPerUnit, 0.55, 2.0);
        gl_Position = vec4(clip.xy / clip.w + 2.0 * flattened * zoom / viewport, 0.0, 1.0);
    }
}
''')
    interface.fragment_source('''
void main() {
    fragColor = vec4(color.rgb, color.a * edgeCoverage);
    if (srgbTarget) {
        vec3 channels = max(color.rgb, vec3(0.0));
        fragColor.rgb = mix(pow((channels + 0.055) / 1.055, vec3(2.4)), channels / 12.92,
                           lessThan(channels, vec3(0.04045)));
    }
}
''')
    return gpu.shader.create_from_info(interface)


def marker_size(value):
    return value*ui_system.interface_scale()


@lru_cache(maxsize=None)
def disk_vertices(radius,inner):
    feather=ui_system.ARRANGEMENT_EDGE_FEATHER/2
    rim=((radius-feather,1.0),(radius+feather,0.0))
    bands=((inner-feather,0.0),(inner+feather,1.0),*rim) if inner else ((0.0,1.0),*rim)
    offsets=[];coverages=[]
    for index in range(DISK_SEGMENTS):
        first=math.tau*index/DISK_SEGMENTS;second=math.tau*(index+1)/DISK_SEGMENTS
        for (near,near_coverage),(far,far_coverage) in zip(bands,bands[1:]):
            corners=[((distance*math.cos(angle),distance*math.sin(angle)),coverage)
                     for distance,coverage in ((near,near_coverage),(far,far_coverage)) for angle in (first,second)]
            for offset,coverage in (corners[0],corners[2],corners[3],corners[0],corners[3],corners[1]):
                offsets.append(offset);coverages.append(coverage)
    return offsets,coverages


def shape_batch(shader,shapes):
    positions=[];offsets=[];normals=[];coverages=[];slots=[]
    for point,radius,inner in shapes:
        shape_offsets,shape_coverages=disk_vertices(radius,inner)
        positions.extend((point['position'],)*len(shape_offsets));normals.extend((point['normal'],)*len(shape_offsets))
        offsets.extend(shape_offsets);coverages.extend(shape_coverages);slots.extend((float(point['slot']),)*len(shape_offsets))
    return batch_for_shader(shader,'TRIS',{'position':positions,'offset':offsets,'normal':normals,'coverage':coverages,'slot':slots}) if positions else None


def display_batches(shader,occupied):
    global _batch_cache
    key=(_world_cache[0],ui_system.interface_scale(),occupied)
    if _batch_cache is None or _batch_cache[0]!=key:
        radius=marker_size(ui_system.ARRANGEMENT_POINT_DIAMETER)/2;width=marker_size(ui_system.ARRANGEMENT_EDGE_WIDTH)
        points=_world_cache[1]
        free=[point for point in points if (point['volume'],point['point']) not in occupied]
        groups=(([point for point in free if not point['mirrored']],ui_system.ARRANGEMENT_FILL),
                ([point for point in free if point['mirrored']],ui_system.ARRANGEMENT_MIRRORED),
                ([point for point in points if (point['volume'],point['point']) in occupied],ui_system.ARRANGEMENT_ATTACHED))
        layers=(*((shape_batch(shader,[(point,radius,0) for point in group]),color) for group,color in groups),
                (shape_batch(shader,[(point,radius,radius-width) for point in points]),(*ui_system.TEXT_PRIMARY[:3],.55)))
        _batch_cache=(key,layers,{})
    return _batch_cache[1]


def visibility_texture(points):
    global _visibility_cache
    flags=[0.0]*len(_world_cache[1])
    for point in points:
        if point['visible']:flags[point['slot']]=1.0
    if _visibility_cache is None or _visibility_cache[0]!=flags:
        _visibility_cache=(flags,gpu.types.GPUTexture((len(flags),1),format='R32F',data=gpu.types.Buffer('FLOAT',len(flags),flags)))
    return _visibility_cache[1]


def overlay_batch(shader,kind,point):
    overlays=_batch_cache[2]
    key=(kind,point['volume'],point['point'])
    if key not in overlays:
        halo=marker_size(ui_system.ARRANGEMENT_ACTIVE_DIAMETER)/2;edge=marker_size(ui_system.ARRANGEMENT_POINT_DIAMETER)/2
        width=marker_size(ui_system.ARRANGEMENT_EDGE_WIDTH)
        radius,inner={'HALO':(halo,halo-width),'PRESSED':(edge-width,0)}[kind]
        overlays[key]=shape_batch(shader,[(point,radius,inner)])
    return overlays[key]


def arrangement_context(context):
    if context.area is None or context.area.type!='VIEW_3D' or context.mode!='OBJECT':return False
    if context.scene.dd_avatar is None or not context.scene.dd_document:return False
    from . import editor
    active=editor._active
    return (active is not None and active._scene==context.scene) or selected_piece(context) is not None


def selected_piece(context):
    from . import editor
    active=editor._active
    if active is not None and active._scene==context.scene:return active.session.selected
    obj=context.view_layer.objects.active
    return obj.get('dd_pattern_id') if obj is not None else None


def occupied_points(context):
    from . import editor,garment
    active=editor._active
    document=active.session.document if active is not None and active._scene==context.scene else garment.document(context.scene)
    return frozenset((pattern.arrangement['volume'],pattern.arrangement['point']) for pattern in document.patterns if pattern.arrangement)


def point_visible(context,position):
    region_view=context.region_data
    target=Vector(position)
    origin=view3d_utils.region_2d_to_origin_3d(context.region,region_view,view3d_utils.location_3d_to_region_2d(context.region,region_view,target))
    direction=target-origin
    remaining=direction.length-OCCLUSION_MARGIN
    direction.normalize()
    depsgraph=context.view_layer.depsgraph
    for attempt in range(OCCLUSION_PASSES):
        hit,location,unused_normal,unused_index,obj,unused_matrix=context.scene.ray_cast(depsgraph,origin,direction,distance=remaining)
        if not hit:return True
        if not obj.original.get('dd_kind'):return False
        step=(location-origin).length+OCCLUSION_MARGIN
        origin=location+direction*OCCLUSION_MARGIN;remaining-=step
        if remaining<=0:return True
    return True


def projected_points(context):
    global _projection_cache
    if not context.scene.dd_reference_visible or context.scene.dd_avatar is None or context.region_data is None:return []
    world=display_world_points(context)
    panel=display_panel(context)
    key=(_world_cache[0],context.region.as_pointer(),context.region.width,context.region.height,
         tuple(tuple(row) for row in context.region_data.perspective_matrix),
         (panel.x,panel.y,panel.w,panel.h) if panel is not None else None)
    if _projection_cache is not None and _projection_cache[0]==key:return _projection_cache[1]
    points=[]
    for point in world:
        screen=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,Vector(point['position']))
        if screen is None:continue
        if panel is not None and panel.contains(*screen):continue
        view=view3d_utils.region_2d_to_vector_3d(context.region,context.region_data,screen)
        points.append(dict(point,screen=tuple(screen),facing=Vector(point['normal']).dot(view)<0,visible=point_visible(context,point['position'])))
    _projection_cache=(key,points)
    return points


def hit_point(context,mouse):
    eye=context.region_data.view_matrix.inverted().translation if context.region_data else Vector((0,0,0))
    reach=marker_size(ui_system.ARRANGEMENT_HIT_DIAMETER)/2
    candidates=[point for point in projected_points(context) if math.dist(mouse,point['screen'])<=reach]
    return min(candidates,key=lambda point:(not point['facing'],math.dist(mouse,point['screen']),(Vector(point['position'])-eye).length)) if candidates else None


def point_label(identity,dragging):
    text=identity[0].replace('_',' ').title()+' · '+identity[1].replace('_',' ').title()
    if dragging:
        text+=f'  {math.degrees(_interaction.angle)%360:.1f}°  {_interaction.height*_interaction.length*100*bpy.context.scene.unit_settings.scale_length:.1f} cm'
    if _interaction.preview and _interaction.preview.get('warning'):text+='  ·  '+_interaction.preview['warning']
    return text


def draw_points():
    global _shader
    context=bpy.context
    if context.area is None or context.area.type!='VIEW_3D':return
    try:points=projected_points(context)
    except (ValueError,ReferenceError,RuntimeError):return
    if not points:return
    if _shader is None:_shader=display_shader()
    shader=_shader
    gpu.state.blend_set('ALPHA')
    try:
        active=_interaction.point if _interaction.state!='IDLE' else None
        layers=display_batches(shader,occupied_points(context))
        panel=display_panel(context)
        view=context.region_data
        camera=view.view_matrix.inverted()
        shader.bind()
        shader.uniform_float('viewProjection',view.perspective_matrix)
        shader.uniform_float('viewport',(context.region.width,context.region.height))
        shader.uniform_float('panel',(panel.x,panel.y,panel.x+panel.w,panel.y+panel.h) if panel is not None else (0,0,-1,-1))
        shader.uniform_float('eye',(*camera.translation,1.0) if view.is_perspective else (*camera.col[2][:3],0.0))
        shader.uniform_float('markerWorld',ui_system.ARRANGEMENT_POINT_BODY_FRACTION*_world_cache[2]/marker_size(ui_system.ARRANGEMENT_POINT_DIAMETER))
        shader.uniform_sampler('visibilityMap',visibility_texture(points))
        for batch,color in layers:
            if batch is None:continue
            shader.uniform_float('color',color);batch.draw(shader)
        by_identity={(point['volume'],point['point']):point for point in points}
        if active in by_identity:
            shader.uniform_float('color',ui_system.ARRANGEMENT_HALO);overlay_batch(shader,'HALO',by_identity[active]).draw(shader)
            if _interaction.state in {'PRESSED','DRAGGING'}:overlay_batch(shader,'PRESSED',by_identity[active]).draw(shader)
            halo=marker_size(ui_system.ARRANGEMENT_ACTIVE_DIAMETER)/2
            screen=by_identity[active]['screen']
            size=round(ui_system.ARRANGEMENT_LABEL_SIZE*ui_system.interface_scale())
            blf.size(0,size)
            text=point_label(active,_interaction.state=='DRAGGING')
            x,y=screen[0]+halo+4,screen[1]-size/2
            blf.color(0,*ui_system.ARRANGEMENT_EDGE);blf.position(0,x+1,y-1,0);blf.draw(0,text)
            blf.color(0,*ui_system.TEXT_PRIMARY);blf.position(0,x,y,0);blf.draw(0,text)
    finally:gpu.state.blend_set('NONE')


def draw_preview():
    context=bpy.context
    preview=_interaction.preview
    if preview is None or context.area is None or context.area.type!='VIEW_3D' or not context.scene.dd_reference_visible:return
    if 'batch' not in preview:
        shader=gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        lines=[position for edge in preview['edges'] for position in (preview['positions'][edge[0]],preview['positions'][edge[1]])]
        preview['shader']=shader
        preview['batch']=batch_for_shader(shader,'LINES',{'pos':lines}) if lines else None
    if preview['batch'] is None:return
    shader=preview['shader']
    gpu.state.blend_set('ALPHA')
    try:
        shader.bind()
        shader.uniform_float('viewportSize',(context.region.width,context.region.height))
        shader.uniform_float('lineWidth',1.0*ui_system.interface_scale())
        shader.uniform_float('color',ui_system.ARRANGEMENT_PREVIEW)
        preview['batch'].draw(shader)
    finally:gpu.state.blend_set('NONE')


def redraw(context):
    for area in context.screen.areas if context.screen else ():
        if area.type=='VIEW_3D':area.tag_redraw()


def update_preview(context,identity,force=False):
    piece=selected_piece(context)
    setup=display_setup()
    key=(piece,identity,(_interaction.angle,_interaction.height) if setup else None)
    if piece is None or identity is None:
        _interaction.preview=None;_interaction.preview_key=None;return
    if key==_interaction.preview_key:return
    now=time.perf_counter()
    if not force and setup is not None and now-_interaction.preview_time<.05:return
    _interaction.preview_time=now;_interaction.preview_key=key
    try:_interaction.preview=live_panels.preview_positions(context,piece,identity[0],identity[1],setup)
    except ValueError as failure:_interaction.preview=dict(positions=[],edges=[],warning=str(failure))


def drag_to(context,mouse,fine):
    volume,point=_interaction.point
    target_point=arrangement._volume_find(_interaction.setup,volume,point)[1]
    def screen(angle,height):
        target_point['angle'],target_point['height']=angle,height
        resolved=arrangement.resolve_point(context,volume,point,setup=_interaction.setup)
        return view3d_utils.location_3d_to_region_2d(context.region,context.region_data,Vector(resolved['point']))
    angle,height=_interaction.angle,_interaction.height
    base=screen(angle,height)
    step=.01
    by_angle=screen(angle+step,height);by_height=screen(angle,min(height+step,1) if height<1-step else height-step)
    target_point['angle'],target_point['height']=angle,height
    if None in (base,by_angle,by_height):return
    sign=1 if height<1-step else -1
    columns=[(by_angle-base)/step,(by_height-base)*sign/step]
    determinant=columns[0].x*columns[1].y-columns[1].x*columns[0].y
    if abs(determinant)<1e-6:return
    target=(Vector(mouse)-Vector(_interaction.last))*(.1 if fine else 1)
    _interaction.last=mouse
    change_angle=(target.x*columns[1].y-columns[1].x*target.y)/determinant
    change_height=(columns[0].x*target.y-target.x*columns[0].y)/determinant
    _interaction.angle=angle+max(-.5,min(.5,change_angle))
    _interaction.height=max(0.0,min(1.0,height+max(-.25,min(.25,change_height))))
    target_point['angle'],target_point['height']=_interaction.angle,_interaction.height


def interaction_active():
    return _interaction.state in {'PRESSED','DRAGGING'}


def end_interaction():
    _interaction.state='IDLE';_interaction.point=None;_interaction.setup=None
    _interaction.preview=None;_interaction.preview_key=None


def point_event(context,event):
    if not arrangement_context(context):
        if _interaction.state!='IDLE':end_interaction()
        return None
    if event.type=='H' and event.value=='PRESS' and not (event.ctrl or event.shift or event.alt):
        bpy.ops.devil_designer.arrangement_guide()
        return {'RUNNING_MODAL'}
    if context.region_data is None:return None
    mouse=(event.mouse_x-context.region.x,event.mouse_y-context.region.y)
    state=_interaction.state
    if state in {'PRESSED','DRAGGING'}:
        if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':
            end_interaction();redraw(context);return {'RUNNING_MODAL'}
        if event.type in {'MOUSEMOVE','INBETWEEN_MOUSEMOVE'}:
            if state=='PRESSED' and math.dist(mouse,_interaction.origin)>=marker_size(ui_system.ARRANGEMENT_DRAG_THRESHOLD):
                import json
                _interaction.setup=json.loads(json.dumps(arrangement.ensure_volumes(context)))
                _interaction.state='DRAGGING'
            if _interaction.state=='DRAGGING':
                drag_to(context,mouse,event.shift)
                update_preview(context,_interaction.point)
                redraw(context)
            return {'RUNNING_MODAL'}
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':
            identity=_interaction.point
            if state=='PRESSED':
                end_interaction()
                if selected_piece(context) is None:
                    context.scene['dd_arrangement_message']='Select a piece, then click a body point to place it.'
                    return {'RUNNING_MODAL'}
                live_panels.arrange_piece(context,selected_piece(context),*identity)
            else:
                angle,height=_interaction.angle,_interaction.height
                end_interaction()
                bpy.ops.devil_designer.arrangement_edit('EXEC_DEFAULT',action='MOVE',volume=identity[0],point=identity[1],angle=angle,height=height)
                bpy.ops.ed.undo_push(message='Move arrangement point')
            redraw(context)
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'} if event.type in {'LEFTMOUSE','RIGHTMOUSE'} else None
    if event.type in {'MOUSEMOVE','INBETWEEN_MOUSEMOVE'}:
        try:point=hit_point(context,mouse)
        except ValueError:point=None
        identity=(point['volume'],point['point']) if point else None
        if identity!=_interaction.point:
            _interaction.state='HOVER' if identity else 'IDLE';_interaction.point=identity
            update_preview(context,identity,True)
            redraw(context)
        return None
    if event.value!='PRESS' or event.type not in {'LEFTMOUSE','RIGHTMOUSE'}:return None
    try:point=hit_point(context,mouse)
    except ValueError as failure:
        context.scene['dd_arrangement_message']=str(failure)
        return None
    if point is None:return None
    volume=point['volume'];identity=point['point']
    if event.type=='RIGHTMOUSE':
        def menu(panel,_):
            panel.layout.label(text=volume.replace('_',' ').title()+' / '+identity.replace('_',' ').title())
            for action,label,icon in (('WRAP','Arrange here: Wrap','MOD_CURVE'),('FLAT','Arrange here: Flat','MESH_PLANE'),
                                      ('MOVE','Move point…','ORIENTATION_GIMBAL'),('ADD','Add point','ADD'),
                                      ('DELETE','Delete point','REMOVE'),('VOLUME','Edit bounding volume…','MESH_CYLINDER')):
                operator=panel.layout.operator(DD_OT_arrangement_edit.bl_idname,text=label,icon=icon)
                operator.action=action;operator.volume=volume;operator.point=identity
        context.window_manager.popup_menu(menu,title='Arrangement point')
        return {'RUNNING_MODAL'}
    try:_interaction.length=arrangement.volume_dimensions(context,volume)[0]
    except ValueError:_interaction.length=0.0
    setup=arrangement.ensure_volumes(context)
    stored=arrangement._volume_find(setup,volume,identity)[1]
    _interaction.state='PRESSED';_interaction.point=(volume,identity);_interaction.origin=mouse;_interaction.last=mouse
    _interaction.angle,_interaction.height=stored['angle'],stored['height']
    redraw(context)
    return {'RUNNING_MODAL'}


class DD_OT_arrangement_pick(bpy.types.Operator):
    bl_idname='devil_designer.arrangement_pick'
    bl_label='Arrange at Point'
    bl_options={'INTERNAL'}

    @classmethod
    def poll(cls,context):
        return arrangement_context(context)

    def invoke(self,context,event):
        try:
            result=point_event(context,event)
            if result and interaction_active():
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
            return {'FINISHED'} if result else {'PASS_THROUGH'}
        except ValueError as failure:
            end_interaction()
            self.report({'WARNING'},str(failure))
            return {'CANCELLED'}

    def modal(self,context,event):
        try:point_event(context,event)
        except ValueError as failure:
            end_interaction()
            self.report({'WARNING'},str(failure))
            return {'CANCELLED'}
        return {'RUNNING_MODAL'} if interaction_active() else {'FINISHED'}


class DD_OT_arrangement_guide(bpy.types.Operator):
    bl_idname='devil_designer.arrangement_guide'
    bl_label='Toggle Body Guide and Arrangement Points'

    @classmethod
    def poll(cls,context):
        return arrangement_context(context)

    def execute(self,context):
        context.scene.dd_reference_visible=not context.scene.dd_reference_visible
        for area in context.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()
        return {'FINISHED'}


def along_get(self):
    return self.height*self.volume_length


def along_set(self,value):
    self.height=max(0.0,min(1.0,value/self.volume_length)) if self.volume_length>0 else self.height


def lower_get(self):
    return self.lower*self.body_height


def lower_set(self,value):
    self.lower=max(0.0,min(1.0,value/self.body_height)) if self.body_height>0 else self.lower


def upper_get(self):
    return self.upper*self.body_height


def upper_set(self,value):
    self.upper=max(0.0,min(1.0,value/self.body_height)) if self.body_height>0 else self.upper


class DD_OT_arrangement_edit(bpy.types.Operator):
    bl_idname='devil_designer.arrangement_edit'
    bl_label='Arrangement Point'
    bl_options={'REGISTER','UNDO'}
    volume:bpy.props.StringProperty()
    point:bpy.props.StringProperty()
    action:bpy.props.EnumProperty(items=[(value,value.title(),'') for value in ('MOVE','ADD','DELETE','WRAP','FLAT','VOLUME','REGENERATE','REFRESH')])
    angle:bpy.props.FloatProperty(name='Around volume',subtype='ANGLE',precision=1,step=10)
    height:bpy.props.FloatProperty(name='Height along volume',min=0,max=1,default=.5)
    lower:bpy.props.FloatProperty(name='Lower body height',min=0,max=1)
    upper:bpy.props.FloatProperty(name='Upper body height',min=0,max=1)
    radius_scale:bpy.props.FloatProperty(name='Radius multiplier',min=.1,max=5,default=1)
    width_scale:bpy.props.FloatProperty(name='Width',subtype='FACTOR',min=.1,max=5,default=1)
    depth_scale:bpy.props.FloatProperty(name='Depth',subtype='FACTOR',min=.1,max=5,default=1)
    reset_fit:bpy.props.BoolProperty(name='Reset fit to the measured body',options={'SKIP_SAVE'})
    volume_length:bpy.props.FloatProperty(options={'HIDDEN','SKIP_SAVE'})
    body_height:bpy.props.FloatProperty(options={'HIDDEN','SKIP_SAVE'})
    along:bpy.props.FloatProperty(name='Height along volume',subtype='DISTANCE',precision=1,get=along_get,set=along_set,options={'SKIP_SAVE'})
    start:bpy.props.FloatProperty(name='Starts at',subtype='DISTANCE',precision=1,get=lower_get,set=lower_set,options={'SKIP_SAVE'})
    end:bpy.props.FloatProperty(name='Ends at',subtype='DISTANCE',precision=1,get=upper_get,set=upper_set,options={'SKIP_SAVE'})

    def invoke(self,context,event):
        try:
            setup=arrangement.ensure_volumes(context)
            volume=next(volume for volume in setup['volumes'] if volume['id']==self.volume)
            point=next(point for point in volume['points'] if point['id']==self.point)
            self.angle=point['angle'];self.height=point['height']
            self.lower=volume['lower'];self.upper=volume['upper'];self.radius_scale=volume['radius_scale']
            self.width_scale=volume.get('width_scale',volume['radius_scale']);self.depth_scale=volume.get('depth_scale',volume['radius_scale'])
            self.volume_length,self.body_height=arrangement.volume_dimensions(context,self.volume)
            if self.action in {'DELETE','FLAT','WRAP'}:return self.execute(context)
            return context.window_manager.invoke_props_dialog(self,width=round(240*ui_system.interface_scale()))
        except (ValueError,StopIteration) as failure:
            self.report({'WARNING'},str(failure) or 'The arrangement point no longer exists.')
            return {'CANCELLED'}

    def draw(self,context):
        layout=self.layout
        layout.use_property_split=True;layout.use_property_decorate=False
        if self.action=='VOLUME':
            column=layout.column(align=True)
            column.prop(self,'start');column.prop(self,'end')
            column=layout.column(align=True)
            column.prop(self,'width_scale');column.prop(self,'depth_scale')
            layout.prop(self,'reset_fit')
        else:
            column=layout.column(align=True)
            column.prop(self,'angle');column.prop(self,'along')

    def execute(self,context):
        try:
            if context.mode!='OBJECT':raise ValueError('Return to Object Mode to edit arrangement points.')
            if self.action in {'REGENERATE','REFRESH'}:
                arrangement.start_fit(context,keep=self.action=='REFRESH',completed=live_panels.fit_completed)
                context.scene['dd_arrangement_message']='Refreshing body fit; points are kept.' if self.action=='REFRESH' else 'Resetting arrangement points to their defaults.'
            elif self.action in {'FLAT','WRAP'}:
                live_panels.arrange_piece(context,selected_piece(context),self.volume,self.point,self.action=='FLAT')
            elif self.action=='VOLUME' and self.reset_fit:
                measured=arrangement._volume_find(arrangement.ensure_volumes(context),self.volume)
                arrangement.edit_volume(context,self.volume,measured['measured_lower'],measured['measured_upper'],1.0,1.0,1.0)
            elif self.action=='VOLUME':
                arrangement.edit_volume(context,self.volume,self.lower,self.upper,self.radius_scale,self.width_scale,self.depth_scale)
            else:
                arrangement.edit_point(context,self.volume,self.point,angle=self.angle,height=self.height,action=self.action)
            if self.action not in {'FLAT','WRAP','REFRESH','REGENERATE'}:
                from . import garment
                if garment.document(context.scene).patterns:garment.build_panels(context)
            context.scene['dd_arrangement_message']=context.scene.get('dd_arrangement_message','') or 'Avatar arrangement setup updated.'
            from . import editor
            if editor._active is not None and editor._active._scene==context.scene:editor._active.message=context.scene['dd_arrangement_message']
            redraw(context)
            return {'FINISHED'}
        except ValueError as failure:
            self.report({'WARNING'},str(failure));return {'CANCELLED'}


def register():
    global _draw_handle,_preview_handle
    for operator in (DD_OT_arrangement_pick,DD_OT_arrangement_guide,DD_OT_arrangement_edit):bpy.utils.register_class(operator)
    _draw_handle=bpy.types.SpaceView3D.draw_handler_add(draw_points,(),'WINDOW','POST_PIXEL')
    _preview_handle=bpy.types.SpaceView3D.draw_handler_add(draw_preview,(),'WINDOW','POST_VIEW')
    configuration=bpy.context.window_manager.keyconfigs.addon
    if configuration:
        keymap=configuration.keymaps.new(name='3D View',space_type='VIEW_3D')
        for event in ('LEFTMOUSE','RIGHTMOUSE'):
            item=keymap.keymap_items.new(DD_OT_arrangement_pick.bl_idname,event,'PRESS')
            _keymaps.append((keymap,item))
        keymap=configuration.keymaps.new(name='Object Mode',space_type='EMPTY')
        item=keymap.keymap_items.new(DD_OT_arrangement_guide.bl_idname,'H','PRESS')
        _keymaps.append((keymap,item))


def unregister():
    global _draw_handle,_preview_handle,_world_cache,_projection_cache,_batch_cache,_visibility_cache,_shader
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle,'WINDOW');_draw_handle=None
    if _preview_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_preview_handle,'WINDOW');_preview_handle=None
    for keymap,item in _keymaps:keymap.keymap_items.remove(item)
    _keymaps.clear()
    end_interaction()
    _world_cache=None;_projection_cache=None;_batch_cache=None;_visibility_cache=None;_shader=None
    for operator in (DD_OT_arrangement_edit,DD_OT_arrangement_guide,DD_OT_arrangement_pick):bpy.utils.unregister_class(operator)
