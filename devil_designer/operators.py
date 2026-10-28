import bpy
from . import garment
from .core import Session


def run(operator, action):
    try:
        return action()
    except (ValueError,RuntimeError) as exc:
        operator.report({'ERROR'},str(exc))
        return {'CANCELLED'}


class DD_OT_build_panels(bpy.types.Operator):
    bl_idname = 'devil_designer.build_panels'
    bl_label = 'Build / Update 3D Panels'
    bl_description = 'Create fabric meshes while keeping existing panel positions; resets simulation'
    bl_options = {'REGISTER','UNDO'}
    def execute(self,context):
        def action():
            panels = garment.build_panels(context)
            self.report({'INFO'},f'Built {len(panels)} fabric panels. Position them with Blender transforms.')
            return {'FINISHED'}
        return run(self,action)


class DD_OT_arrange(bpy.types.Operator):
    bl_idname = 'devil_designer.arrange'
    bl_label = 'Arrange Front / Back'
    bl_description = 'Place exactly two panels in front of and behind the selected avatar body'
    bl_options = {'REGISTER','UNDO'}
    def execute(self,context):
        def action():
            if context.scene.dd_avatar is None and context.object and context.object.type=='MESH' and not context.object.get('dd_kind'):
                context.scene.dd_avatar = context.object
            if any(piece.placement_mode!='LEGACY' or piece.arrangement for piece in garment.document(context.scene).patterns):
                raise ValueError('Select a piece and click an arrangement point. Front/back guessing is only for older designs.')
            garment.arrange(context)
            self.report({'INFO'},'Panels arranged. Adjust their placement in the 3D viewport before simulating.')
            return {'FINISHED'}
        return run(self,action)


class DD_OT_simulate(bpy.types.Operator):
    bl_idname = 'devil_designer.simulate'
    bl_label = 'Simulate'
    bl_description = 'Assemble sewn panels and play Blender cloth simulation'
    def execute(self,context):
        def action():
            obj = garment.compile_garment(context)
            obj.hide_set(False)
            obj.hide_render = False
            garment.start_playback(context)
            from .live_panels import intersection_warnings
            warnings=intersection_warnings(context)
            context.scene['dd_arrangement_message']=' '.join(warnings) or context.scene.get('dd_arrangement_message','')
            self.report({'WARNING'} if warnings else {'INFO'},' '.join(warnings) or 'Simulation ready. Stop on a frame you want to keep.')
            return {'FINISHED'}
        return run(self,action)


class DD_OT_stop(bpy.types.Operator):
    bl_idname = 'devil_designer.stop'
    bl_label = 'Stop'
    bl_description = 'Pause playback without discarding the current draped shape'
    def execute(self,context):
        garment.stop(context)
        return {'FINISHED'}


class DD_OT_reset(bpy.types.Operator):
    bl_idname = 'devil_designer.reset'
    bl_label = 'Reset to Arrangement'
    bl_description = 'Discard the simulation cache and show the original positioned panels'
    bl_options = {'REGISTER','UNDO'}
    def execute(self,context):
        garment.reset(context)
        return {'FINISHED'}


class DD_OT_keep_drape(bpy.types.Operator):
    bl_idname = 'devil_designer.keep_drape'
    bl_label = 'Keep Draped Mesh'
    bl_description = 'Copy the current cloth shape, remove sewing springs, and weld matched seam vertices within tolerance'
    bl_options = {'REGISTER','UNDO'}
    def execute(self,context):
        def action():
            obj,open_seams = garment.keep_drape(context)
            context.scene['dd_unwelded_seams'] = open_seams
            if open_seams:
                self.report({'WARNING'},f'Kept {obj.name}; {open_seams} seam pairs remain open. Simulate longer or adjust weld distance.')
            else:
                self.report({'INFO'},'Kept draped mesh with pattern UVs. Ready for mesh cleanup and rigging.')
            return {'FINISHED'}
        return run(self,action)


class DD_OT_seam(bpy.types.Operator):
    bl_idname = 'devil_designer.seam'
    bl_label = 'Edit Seam'
    bl_options = {'REGISTER','UNDO'}
    seam_id: bpy.props.StringProperty()
    remove: bpy.props.BoolProperty(default=False)
    def execute(self,context):
        def action():
            session = Session(garment.document(context.scene))
            if self.remove:
                session.remove_seam(self.seam_id)
            else:
                session.reverse_seam(self.seam_id)
            context.scene.dd_document = session.document.dumps()
            return {'FINISHED'}
        return run(self,action)


class DD_OT_demo(bpy.types.Operator):
    bl_idname = 'devil_designer.demo'
    bl_label = 'Create Two-Piece Sewing Demo'
    bl_description = 'Create two sewn bodice patterns and a procedural torso collider in an empty pattern document'
    bl_options = {'REGISTER','UNDO'}
    def execute(self,context):
        def action():
            scene = context.scene
            if garment.document(scene).patterns:
                raise ValueError('The demo requires an empty pattern document. Use a new scene to try it.')
            front = [(-.22,0),(.22,0),(.22,.32),(.19,.45),(.10,.49),(.08,.43),(-.08,.43),(-.10,.49),(-.19,.45),(-.22,.32)]
            back = [(x+.62,y) for x,y in front]
            s = Session()
            s.add(front)
            s.document.patterns[-1].name = 'Bodice front'
            s.add(back)
            s.document.patterns[-1].name = 'Bodice back'
            a,b = s.document.patterns
            for pattern in s.document.patterns:pattern.placement_mode='LEGACY'
            for i,j in [(1,9),(9,1),(3,7),(7,3)]:
                s.sew(s.document.edge(a.id,i),s.document.edge(b.id,j))
            scene.dd_document = s.document.dumps()
            unit = garment.metres_per_unit(scene)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=(0,0,1.25/unit))
            torso = context.object
            torso.name = 'DD Demo Torso'
            torso.scale = (.17/unit,.095/unit,.28/unit)
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            garment.tag(torso,'demo')
            scene.dd_avatar = torso
            garment.arrange(context)
            self.report({'INFO'},'Demo ready. Open the pattern editor or press Simulate in the garment panel.')
            return {'FINISHED'}
        return run(self,action)


CLASSES = (DD_OT_build_panels,DD_OT_arrange,DD_OT_simulate,DD_OT_stop,DD_OT_reset,
           DD_OT_keep_drape,DD_OT_seam,DD_OT_demo)
