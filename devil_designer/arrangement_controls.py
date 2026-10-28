import math
import bpy
import gpu
from mathutils import Vector
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from . import arrangement,live_panels


_draw_handle=None
_keymaps=[]


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
    if not context.scene.dd_reference_visible or context.scene.dd_avatar is None or context.region_data is None:return []
    from . import editor
    active=editor._active
    points=[]
    for point in arrangement.world_points(context):
        screen=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,Vector(point['position']))
        if screen is None:continue
        if active is not None and active._area==context.area and active.canvas_layout.panel.contains(*screen):continue
        points.append(dict(point,screen=tuple(screen)))
    return points


def hit_point(context,mouse):
    eye=context.region_data.view_matrix.inverted().translation if context.region_data else Vector((0,0,0))
    candidates=[point for point in projected_points(context) if math.dist(mouse,point['screen'])<=10]
    return min(candidates,key=lambda point:(round(math.dist(mouse,point['screen'])/4),(Vector(point['position'])-eye).length)) if candidates else None


def draw_points():
    context=bpy.context
    if context.area is None or context.area.type!='VIEW_3D':return
    try:points=projected_points(context)
    except (ValueError,ReferenceError,RuntimeError):return
    if not points:return
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    try:
        volumes=set();lines=[]
        from . import editor
        active=editor._active
        for point in points:
            if point['volume'] in volumes:continue
            volumes.add(point['volume'])
            normal=Vector(point['normal']);tangent=Vector(point['tangent'])
            for sample in (point['geometry']['samples'][0],point['geometry']['samples'][-1]):
                center=Vector(sample['center']);radius=sample['radius']
                ring=[view3d_utils.location_3d_to_region_2d(context.region,context.region_data,
                      center+radius*(normal*math.cos(math.tau*index/32)+tangent*math.sin(math.tau*index/32))) for index in range(33)]
                for first,second in zip(ring,ring[1:]):
                    if first is None or second is None:continue
                    if active is not None and active._area==context.area and any(active.canvas_layout.panel.contains(*value) for value in (first,second)):continue
                    lines.extend((tuple(first),tuple(second)))
        if lines:
            shader.bind();shader.uniform_float('color',(.28,.78,1,.22))
            batch_for_shader(shader,'LINES',{'pos':lines}).draw(shader)
        for point in points:
            horizontal,vertical=point['screen']
            vertices=[]
            for index in range(16):
                first=math.tau*index/16;second=math.tau*(index+1)/16
                vertices.extend(((horizontal,vertical),(horizontal+5*math.cos(first),vertical+5*math.sin(first)),
                                 (horizontal+5*math.cos(second),vertical+5*math.sin(second))))
            shader.bind();shader.uniform_float('color',(.28,.78,1,1))
            batch_for_shader(shader,'TRIS',{'pos':vertices}).draw(shader)
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
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle,'WINDOW');_draw_handle=None
    for keymap,item in _keymaps:keymap.keymap_items.remove(item)
    _keymaps.clear()
    for operator in (DD_OT_arrangement_edit,DD_OT_arrangement_guide,DD_OT_arrangement_pick):bpy.utils.unregister_class(operator)
