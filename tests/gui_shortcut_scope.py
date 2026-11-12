import json
import math
import sys
import traceback
from pathlib import Path
import bpy
from mathutils import Quaternion

bpy.context.preferences.view.show_splash=False
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import arrangement,editor,garment
from devil_designer.core import Session

REPORT=ROOT/'scratch'/'shortcut_scope-report.json'
state=dict(stage=0,passed=[])


def check(condition,message):
    if not condition:raise AssertionError(message)
    state['passed'].append(message)


def areas():
    area=next(area for area in bpy.context.screen.areas if area.type=='VIEW_3D')
    return area,next(region for region in area.regions if region.type=='WINDOW')


def workspace():
    active=editor._active
    return active if active is not None and not active._closed else None


def key(kind,position,**modifiers):
    window=bpy.context.window
    window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(position[0]),y=int(position[1]))
    for value in ('PRESS','RELEASE'):window.event_simulate(type=kind,value=value,x=int(position[0]),y=int(position[1]),**modifiers)


def outside():
    _,region=areas()
    panel=workspace().canvas_layout.panel
    return region.x+max(140,panel.x*.45),region.y+region.height*.45


def inside():
    _,region=areas()
    panel=workspace().canvas_layout.panel
    return region.x+panel.x+panel.w*.5,region.y+panel.y+panel.h*.5


def probe():
    return bpy.data.objects.get('ScopeProbe')


def select_only(obj):
    for other in bpy.context.view_layer.objects:other.select_set(False)
    obj.select_set(True);bpy.context.view_layer.objects.active=obj


def seam():
    seams=workspace().session.document.seams
    return seams[0] if seams else None


def run():
    try:
        scene=bpy.context.scene
        area,region=areas()
        stage=state['stage']
        if stage==0:
            devil_designer.register()
            for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.3,location=(0,0,1.2))
            body=bpy.context.object
            session=Session()
            session.add([(-.15,.1),(.15,.1),(.15,.4),(-.15,.4)])
            session.add([(.3,.1),(.6,.1),(.6,.4),(.3,.4)])
            document=session.document
            session.sew(document.edges(document.patterns[0].id)[1],document.edges(document.patterns[1].id)[3])
            scene.dd_document=session.document.dumps();scene.dd_avatar=body
            view=area.spaces.active.region_3d
            view.view_location=(0,0,1.1);view.view_rotation=Quaternion((1,0,0),math.pi/2)
            view.view_distance=6;view.view_perspective='ORTHO';view.update()
            with bpy.context.temp_override(area=area,region=region):
                arrangement.ensure_volumes(bpy.context)
                garment.build_panels(bpy.context)
                bpy.ops.mesh.primitive_cube_add(size=.2,location=(-1.5,0,1))
                bpy.context.object.name='ScopeProbe'
                bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            active=workspace()
            check(active is not None,'pattern editor opens as a real modal operator')
            active.reveal_3d()
            active.canvas_layout=active.make_layout()
            active.choose_tool('SELECT')
            scene.dd_reference_visible=True
            check(seam() is not None and active.tool=='SELECT','the scope scene has one seam and the Select tool')
            select_only(probe())
            key('A',outside())
        elif stage==1:
            selectable=[obj for obj in bpy.context.view_layer.objects if obj.visible_get()]
            check(all(obj.select_get() for obj in selectable),'outside the editor, A selects every object as in stock Blender')
            key('A',outside(),alt=True)
        elif stage==2:
            check(not bpy.context.selected_objects,'outside the editor, Alt+A deselects every object as in stock Blender')
            select_only(probe())
            key('TAB',outside())
        elif stage==3:
            check(probe().mode=='EDIT','outside the editor, Tab enters Edit Mode as in stock Blender')
            key('TAB',outside())
        elif stage==4:
            check(probe().mode=='OBJECT','outside the editor, Tab returns to Object Mode as in stock Blender')
            key('I',outside())
        elif stage==5:
            data=probe().animation_data
            check(data is not None and data.action is not None,'outside the editor, I inserts a keyframe as in stock Blender')
            check(workspace().tool=='SELECT','outside the editor, I leaves the editor tool unchanged')
            state['probe_action']=data.action.name
            key('I',inside())
        elif stage==6:
            active=workspace()
            check(active.tool=='INTERNAL','over the editor, I picks the Internal tool')
            check(probe().animation_data.action.name==state['probe_action'],'over the editor, I inserts no Blender keyframe')
            active.choose_tool('SELECT')
            select_only(probe())
            scene.dd_reference_visible=True
            key('H',outside())
        elif stage==7:
            check(probe().hide_get(),'outside the editor, H hides the selected object as in stock Blender')
            check(scene.dd_reference_visible,'outside the editor, H leaves the body guide as it was')
            probe().hide_set(False)
            key('H',inside())
        elif stage==8:
            check(not scene.dd_reference_visible,'over the editor, H hides the body guide')
            check(not probe().hide_get(),'over the editor, H hides no Blender object')
            scene.dd_reference_visible=True
            key('SPACE',outside())
        elif stage==9:
            playing=bpy.context.screen.is_animation_playing
            with bpy.context.temp_override(area=area,region=region):bpy.ops.screen.animation_cancel(restore_frame=True)
            check(playing,'outside the editor, Space plays the timeline as in stock Blender')
            check(not garment.generated(scene,'simulation'),'outside the editor, Space starts no drape')
            select_only(probe())
            key('DEL',outside())
        elif stage==10:
            check(probe() is None,'outside the editor, Delete removes the selected object as in stock Blender')
            active=workspace()
            active.seam_selected=seam().id
            state['reverse']=seam().reverse
            key('B',outside())
        elif stage==11:
            check(seam().reverse!=state['reverse'],'listed special: B reverses the selected seam with the pointer outside')
            key('X',outside())
        elif stage==12:
            check(seam() is None,'listed special: X removes the selected seam with the pointer outside')
            key('Z',outside(),ctrl=True)
        elif stage==13:
            check(seam() is not None,'listed special: Ctrl+Z undoes the editor change with the pointer outside')
            active=workspace()
            active.pending_edge=active.session.document.edges(active.session.document.patterns[0].id)[0]
            key('ESC',outside())
        elif stage==14:
            check(workspace().pending_edge is None,'listed special: Escape cancels a pending seam step with the pointer outside')
            check(workspace() is not None,'the editor stays open through the whole scope audit')
            REPORT.write_text(json.dumps(dict(passed=state['passed'])),encoding='utf-8')
            return None
        state['stage']+=1
        return .5
    except Exception:
        REPORT.write_text(json.dumps(dict(passed=state['passed'],error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
        return None


bpy.app.timers.register(run,first_interval=1)
