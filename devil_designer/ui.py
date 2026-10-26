import bpy
from bpy.app.handlers import persistent
from .editor import DD_OT_pattern_editor, close_active
from .operators import CLASSES
from .garment import cancel_playback


def avatar_poll(self,obj):
    return obj.type=='MESH' and obj.get('dd_kind') not in {'panel','simulation','final'}


def launch_menu(self,context):
    self.layout.separator()
    self.layout.operator(DD_OT_pattern_editor.bl_idname,text='Devil Designer',icon='MOD_CLOTH')

KEYMAPS = []


@persistent
def on_load(_):
    close_active()
    cancel_playback()


classes = (DD_OT_pattern_editor,)+CLASSES
PROPERTIES = ('dd_document','dd_collection','dd_avatar','dd_spacing','dd_clearance',
              'dd_quality','dd_frames','dd_self_collision','dd_pin_top','dd_weld_distance','dd_thickness',
              'dd_ui_rect','dd_ui_settings')


def register():
    Scene = bpy.types.Scene
    Scene.dd_ui_rect = bpy.props.FloatVectorProperty(name='Editor window bounds',size=4,default=(-1,-1,0,0))
    Scene.dd_ui_settings = bpy.props.BoolProperty(name='Editor settings visible',default=True)
    Scene.dd_document = bpy.props.StringProperty(name='Pattern document',default='')
    Scene.dd_collection = bpy.props.PointerProperty(type=bpy.types.Collection)
    Scene.dd_avatar = bpy.props.PointerProperty(type=bpy.types.Object,name='Avatar body',poll=avatar_poll)
    Scene.dd_spacing = bpy.props.FloatProperty(name='Mesh spacing (m)',default=.02,min=.003,max=.2,precision=3)
    Scene.dd_clearance = bpy.props.FloatProperty(name='Body clearance (m)',default=.03,min=.005,max=.3,precision=3)
    Scene.dd_quality = bpy.props.IntProperty(name='Quality steps',default=10,min=5,max=40)
    Scene.dd_frames = bpy.props.IntProperty(name='Simulation frames',default=120,min=10,max=1000)
    Scene.dd_self_collision = bpy.props.BoolProperty(name='Self collision',default=True)
    Scene.dd_pin_top = bpy.props.BoolProperty(name='Pin highest panel points',default=False)
    Scene.dd_weld_distance = bpy.props.FloatProperty(name='Seam weld distance (m)',default=.01,min=.0001,max=.05,precision=4)
    Scene.dd_thickness = bpy.props.FloatProperty(name='Final thickness (m)',default=.001,min=0,max=.01,precision=4)
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_pre.append(on_load)
    bpy.types.VIEW3D_MT_view.append(launch_menu)
    config=bpy.context.window_manager.keyconfigs.addon
    if config:
        keymap=config.keymaps.new(name='3D View',space_type='VIEW_3D')
        item=keymap.keymap_items.new(DD_OT_pattern_editor.bl_idname,'D','PRESS',ctrl=True,alt=True)
        KEYMAPS.append((keymap,item))


def unregister():
    close_active()
    cancel_playback()
    if on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(on_load)
    bpy.types.VIEW3D_MT_view.remove(launch_menu)
    for keymap,item in KEYMAPS:
        keymap.keymap_items.remove(item)
    KEYMAPS.clear()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    for name in PROPERTIES:
        delattr(bpy.types.Scene,name)
