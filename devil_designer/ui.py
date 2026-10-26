import bpy
from bpy.app.handlers import persistent
from .editor import DD_OT_pattern_editor, close_active
from .operators import CLASSES
from .core import Document
from .garment import cancel_playback


def avatar_poll(self,obj):
    return obj.type=='MESH' and obj.get('dd_kind') not in {'panel','simulation','final'}


class DD_PT_patterns(bpy.types.Panel):
    bl_label = 'Devil Designer'
    bl_idname = 'DD_PT_patterns'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Devil Designer'

    def draw(self,context):
        layout,scene = self.layout,context.scene
        layout.operator(DD_OT_pattern_editor.bl_idname,icon='WINDOW')
        try:
            doc = Document.loads(scene.dd_document)
        except ValueError as exc:
            layout.label(text=str(exc),icon='ERROR')
            return
        layout.label(text=f'{len(doc.patterns)} patterns / {len(doc.seams)} seams')
        if not doc.patterns:
            layout.operator('devil_designer.demo',icon='MOD_CLOTH')
        box = layout.box()
        box.label(text='1. Fabric panels')
        box.prop(scene,'dd_spacing')
        box.label(text=f'{scene.dd_spacing*100:g} cm between mesh samples')
        box.operator('devil_designer.build_panels',icon='MESH_GRID')
        box = layout.box()
        box.label(text='2. Body and arrangement')
        box.prop(scene,'dd_avatar')
        box.prop(scene,'dd_clearance')
        box.operator('devil_designer.arrange',icon='ORIENTATION_GLOBAL')
        box.label(text='Adjust panels with G / R in 3D.')
        if doc.seams:
            box = layout.box()
            box.label(text='Sewing pairs')
            for index,seam in enumerate(doc.seams):
                a,b = doc.find(seam.a.pattern),doc.find(seam.b.pattern)
                row = box.row(align=True)
                row.label(text=f'{index+1}: {a.name} / {b.name}')
                op = row.operator('devil_designer.seam',text='',icon='ARROW_LEFTRIGHT')
                op.seam_id = seam.id
                op = row.operator('devil_designer.seam',text='',icon='X')
                op.seam_id,op.remove = seam.id,True
        else:
            layout.label(text='Use Sew (J) in the 2D editor to pair edges.')
        box = layout.box()
        box.label(text='3. Drape')
        box.prop(scene,'dd_quality')
        box.prop(scene,'dd_frames')
        box.prop(scene,'dd_self_collision')
        box.prop(scene,'dd_pin_top')
        row = box.row(align=True)
        row.operator('devil_designer.simulate',icon='PLAY')
        row.operator('devil_designer.stop',icon='PAUSE')
        box.operator('devil_designer.reset',icon='LOOP_BACK')
        box = layout.box()
        box.label(text='4. Keep the shape')
        box.prop(scene,'dd_weld_distance')
        box.prop(scene,'dd_thickness')
        box.operator('devil_designer.keep_drape',icon='CHECKMARK')


@persistent
def on_load(_):
    close_active()
    cancel_playback()


classes = (DD_OT_pattern_editor,)+CLASSES+(DD_PT_patterns,)
PROPERTIES = ('dd_document','dd_collection','dd_avatar','dd_spacing','dd_clearance',
              'dd_quality','dd_frames','dd_self_collision','dd_pin_top','dd_weld_distance','dd_thickness')


def register():
    Scene = bpy.types.Scene
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


def unregister():
    close_active()
    cancel_playback()
    if on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(on_load)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    for name in PROPERTIES:
        delattr(bpy.types.Scene,name)
