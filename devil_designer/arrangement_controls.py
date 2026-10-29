import math
import bpy
import gpu
from mathutils import Vector
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from . import arrangement,live_panels


_draw_handle=None
_keymaps=[]
_world_cache=None
_projection_cache=None
_batch_cache=None
_shader=None


def display_world_points(context):
    global _world_cache
    arrangement._volume_avatar(context)
    key=(context.scene.as_pointer(),context.view_layer.as_pointer(),live_panels.avatar_signature(context))
    if _world_cache is None or _world_cache[0]!=key:
        points=arrangement.world_points(context)
        rings={}
        for point in points:
            normal=Vector(point['normal']);tangent=Vector(point['tangent'])
            rings[(point['volume'],point['point'])]=[
                [Vector(sample['center'])+sample['radius']*(normal*math.cos(math.tau*index/32)+tangent*math.sin(math.tau*index/32))
                 for index in range(33)]
                for sample in (point['geometry']['samples'][0],point['geometry']['samples'][-1])]
        _world_cache=(key,points,rings)
    return _world_cache[1]


def display_panel(context):
    from . import editor
    active=editor._active
    return active.canvas_layout.panel if active is not None and active._area==context.area else None


def display_shader():
    interface=gpu.types.GPUShaderCreateInfo()
    interface.vertex_in(0,'VEC3','position')
    interface.vertex_in(1,'VEC3','peer')
    interface.vertex_in(2,'VEC2','offset')
    interface.push_constant('MAT4','viewProjection')
    interface.push_constant('VEC2','viewport')
    interface.push_constant('VEC4','panel')
    interface.push_constant('VEC4','color')
    interface.push_constant('BOOL','srgbTarget')
    interface.fragment_out(0,'VEC4','fragColor')
    interface.vertex_source('''
bool covered(vec4 clip) {
    vec2 pixel = (clip.xy / clip.w + vec2(1.0)) * viewport * 0.5;
    return all(greaterThanEqual(pixel, panel.xy)) && all(lessThanEqual(pixel, panel.zw));
}
void main() {
    vec4 clip = viewProjection * vec4(position, 1.0);
    vec4 other = viewProjection * vec4(peer, 1.0);
    if (clip.w <= 0.0 || other.w <= 0.0 || covered(clip) || covered(other)) {
        gl_Position = vec4(2.0, 2.0, 0.0, 1.0);
    } else {
        gl_Position = vec4(clip.xy / clip.w + 2.0 * offset / viewport, 0.0, 1.0);
    }
}
''')
    interface.fragment_source('''
void main() {
    fragColor = color;
    if (srgbTarget) {
        vec3 channels = max(color.rgb, vec3(0.0));
        fragColor.rgb = mix(pow((channels + 0.055) / 1.055, vec3(2.4)), channels / 12.92,
                           lessThan(channels, vec3(0.04045)));
    }
}
''')
    return gpu.shader.create_from_info(interface)


def display_batches(shader,points):
    global _batch_cache
    key=_world_cache[0]
    if _batch_cache is None or _batch_cache[0]!=key:
        positions=[];offsets=[]
        for point in _world_cache[1]:
            for index in range(16):
                first=math.tau*index/16;second=math.tau*(index+1)/16
                positions.extend((point['position'],)*3)
                offsets.extend(((0,0),(5*math.cos(first),5*math.sin(first)),(5*math.cos(second),5*math.sin(second))))
        _batch_cache=[key,batch_for_shader(shader,'TRIS',{'position':positions,'peer':positions,'offset':offsets}),None,None]
    volumes=set();selected=[]
    for point in points:
        if point['volume'] not in volumes:
            volumes.add(point['volume']);selected.append((point['volume'],point['point']))
    ring_key=tuple(selected)
    if _batch_cache[2]!=ring_key:
        positions=[];peers=[]
        for identity in selected:
            for ring in _world_cache[2][identity]:
                for first,second in zip(ring,ring[1:]):
                    positions.extend((first,second));peers.extend((second,first))
        _batch_cache[2]=ring_key
        _batch_cache[3]=batch_for_shader(shader,'LINES',{'position':positions,'peer':peers,'offset':[(0,0)]*len(positions)}) if positions else None
    return _batch_cache[1],_batch_cache[3]


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
        points.append(dict(point,screen=tuple(screen)))
    _projection_cache=(key,points)
    return points


def hit_point(context,mouse):
    eye=context.region_data.view_matrix.inverted().translation if context.region_data else Vector((0,0,0))
    candidates=[point for point in projected_points(context) if math.dist(mouse,point['screen'])<=10]
    return min(candidates,key=lambda point:(round(math.dist(mouse,point['screen'])/4),(Vector(point['position'])-eye).length)) if candidates else None


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
        markers,rings=display_batches(shader,points)
        panel=display_panel(context)
        shader.bind()
        shader.uniform_float('viewProjection',context.region_data.perspective_matrix)
        shader.uniform_float('viewport',(context.region.width,context.region.height))
        shader.uniform_float('panel',(panel.x,panel.y,panel.x+panel.w,panel.y+panel.h) if panel is not None else (0,0,-1,-1))
        if rings is not None:
            shader.uniform_float('color',(.28,.78,1,.22));rings.draw(shader)
        shader.uniform_float('color',(.28,.78,1,1));markers.draw(shader)
    finally:gpu.state.blend_set('NONE')


def point_event(context,event):
    if not arrangement_context(context):return None
    if event.type=='H' and event.value=='PRESS' and not (event.ctrl or event.shift or event.alt):
        bpy.ops.devil_designer.arrangement_guide()
        return {'RUNNING_MODAL'}
    if event.value!='PRESS' or event.type not in {'LEFTMOUSE','RIGHTMOUSE'} or context.region_data is None:return None
    mouse=(event.mouse_x-context.region.x,event.mouse_y-context.region.y)
    try:point=hit_point(context,mouse)
    except ValueError as failure:
        context.scene['dd_arrangement_message']=str(failure)
        return None
    if point is None:return None
    if event.type=='RIGHTMOUSE':
        volume=point['volume'];identity=point['point']
        def menu(panel,_):
            panel.layout.label(text=volume.replace('_',' ').title()+' / '+identity.replace('_',' ').title())
            for action,label in (('FLAT','Arrange flat'),('MOVE','Move point'),('ADD','Add point'),('DELETE','Delete point'),('VOLUME','Edit bounding volume')):
                operator=panel.layout.operator(DD_OT_arrangement_edit.bl_idname,text=label)
                operator.action=action;operator.volume=volume;operator.point=identity
        context.window_manager.popup_menu(menu,title='Arrangement point')
    else:
        live_panels.arrange_piece(context,selected_piece(context),point['volume'],point['point'])
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
            return {'FINISHED'} if result else {'PASS_THROUGH'}
        except ValueError as failure:
            self.report({'WARNING'},str(failure))
            return {'CANCELLED'}


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


class DD_OT_arrangement_edit(bpy.types.Operator):
    bl_idname='devil_designer.arrangement_edit'
    bl_label='Arrangement Point'
    bl_options={'REGISTER','UNDO'}
    volume:bpy.props.StringProperty()
    point:bpy.props.StringProperty()
    action:bpy.props.EnumProperty(items=[(value,value.title(),'') for value in ('MOVE','ADD','DELETE','FLAT','VOLUME','REGENERATE')])
    angle:bpy.props.FloatProperty(name='Around volume',subtype='ANGLE')
    height:bpy.props.FloatProperty(name='Height along volume',min=0,max=1,default=.5)
    lower:bpy.props.FloatProperty(name='Lower body height',min=0,max=1)
    upper:bpy.props.FloatProperty(name='Upper body height',min=0,max=1)
    radius_scale:bpy.props.FloatProperty(name='Radius multiplier',min=.1,max=5,default=1)

    def invoke(self,context,event):
        try:
            setup=arrangement.ensure_volumes(context)
            volume=next(volume for volume in setup['volumes'] if volume['id']==self.volume)
            point=next(point for point in volume['points'] if point['id']==self.point)
            self.angle=point['angle'];self.height=point['height']
            self.lower=volume['lower'];self.upper=volume['upper'];self.radius_scale=volume['radius_scale']
            if self.action in {'DELETE','FLAT'}:return self.execute(context)
            return context.window_manager.invoke_props_dialog(self,width=260)
        except (ValueError,StopIteration) as failure:
            self.report({'WARNING'},str(failure) or 'The arrangement point no longer exists.')
            return {'CANCELLED'}

    def draw(self,context):
        if self.action=='VOLUME':
            for key in ('lower','upper','radius_scale'):self.layout.prop(self,key)
        else:
            self.layout.prop(self,'angle');self.layout.prop(self,'height')

    def execute(self,context):
        try:
            if context.mode!='OBJECT':raise ValueError('Return to Object Mode to edit arrangement points.')
            if self.action=='REGENERATE':
                arrangement.ensure_volumes(context,force=True)
            elif self.action=='FLAT':
                live_panels.arrange_piece(context,selected_piece(context),self.volume,self.point,True)
            elif self.action=='VOLUME':
                arrangement.edit_volume(context,self.volume,self.lower,self.upper,self.radius_scale)
            else:
                arrangement.edit_point(context,self.volume,self.point,angle=self.angle,height=self.height,action=self.action)
            if self.action!='FLAT':
                from . import garment
                if garment.document(context.scene).patterns:garment.build_panels(context)
            context.scene['dd_arrangement_message']=context.scene.get('dd_arrangement_message','') or 'Avatar arrangement setup updated.'
            from . import editor
            if editor._active is not None and editor._active._scene==context.scene:editor._active.message=context.scene['dd_arrangement_message']
            for area in context.screen.areas if context.screen else ():
                if area.type=='VIEW_3D':area.tag_redraw()
            return {'FINISHED'}
        except ValueError as failure:
            self.report({'WARNING'},str(failure));return {'CANCELLED'}


def register():
    global _draw_handle
    for operator in (DD_OT_arrangement_pick,DD_OT_arrangement_guide,DD_OT_arrangement_edit):bpy.utils.register_class(operator)
    _draw_handle=bpy.types.SpaceView3D.draw_handler_add(draw_points,(),'WINDOW','POST_PIXEL')
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
    global _draw_handle,_world_cache,_projection_cache,_batch_cache,_shader
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle,'WINDOW');_draw_handle=None
    for keymap,item in _keymaps:keymap.keymap_items.remove(item)
    _keymaps.clear()
    _world_cache=None;_projection_cache=None;_batch_cache=None;_shader=None
    for operator in (DD_OT_arrangement_edit,DD_OT_arrangement_guide,DD_OT_arrangement_pick):bpy.utils.unregister_class(operator)
