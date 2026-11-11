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

REPORT=ROOT/'scratch'/'timeline_release-report.json'
state=dict(stage=0,passed=[])
original_handle=editor.DD_OT_pattern_editor.handle_event


def check(condition,message):
    if not condition:raise AssertionError(message)
    state['passed'].append(message)


def areas():
    area=next(area for area in bpy.context.screen.areas if area.type=='VIEW_3D')
    return area,next(region for region in area.regions if region.type=='WINDOW')


def workspace():
    active=editor._active
    return active if active is not None and not active._closed else None


def body_mesh():
    parts=[]
    for position,scale in (((0,0,1.15),(.26,.15,.4)),((0,0,1.7),(.12,.12,.16)),((-.42,0,1.38),(.27,.08,.08)),
                           ((.42,0,1.38),(.27,.08,.08)),((-.13,0,.45),(.105,.11,.45)),((.13,0,.45),(.105,.11,.45))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=position)
        parts.append(bpy.context.object);bpy.context.object.scale=scale
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:part.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    return bpy.context.object


def timeline(scene):
    return (scene.frame_end,scene.render.fps,scene.render.fps_base,scene.sync_mode)


def restored(scene,label):
    check(not bpy.context.screen.is_animation_playing,label+' stops the drape playing')
    check(timeline(scene)==state['timeline'] and 'dd_timeline' not in scene,
          label+' restores frame end, frame rate and sync mode: '+str(timeline(scene)))


def press(kind,**modifiers):
    window=bpy.context.window
    _,region=areas()
    x,y=region.x+region.width//2,region.y+region.height//2
    window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
    for value in ('PRESS','RELEASE'):window.event_simulate(type=kind,value=value,x=x,y=y,**modifiers)


def open_editor():
    area,region=areas()
    with bpy.context.temp_override(area=area,region=region):
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    active=workspace()
    check(active is not None,'the pattern editor opens as a real modal operator')
    return active


def play_drape():
    area,region=areas()
    with bpy.context.temp_override(area=area,region=region):
        garment.start_playback(bpy.context)


def event_at_centre():
    _,region=areas()
    return type('Event',(),dict(type='MOUSEMOVE',value='NOTHING',mouse_x=region.x+region.width//2,mouse_y=region.y+region.height//2,
                                ctrl=False,shift=False,alt=False))()


def enclosing_collider(scene):
    mesh=bpy.data.meshes.new('Enclosure')
    corners=[(x,y,z) for x in (-3,3) for y in (-3,3) for z in (-3,5)]
    faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    mesh.from_pydata(corners,[],faces);mesh.update()
    obj=bpy.data.objects.new('Enclosure',mesh)
    scene.collection.objects.link(obj)
    obj.modifiers.new('Collision','COLLISION')
    bpy.context.view_layer.update()
    return obj


def run():
    try:
        scene=bpy.context.scene
        hidden=state.pop('area_type',None)
        if hidden:next(item for item in bpy.context.screen.areas if item.type=='PROPERTIES').type=hidden
        area,region=areas()
        stage=state['stage']
        if stage==0:
            devil_designer.register()
            for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
            scene.frame_end=250;scene.render.fps=24;scene.render.fps_base=1;scene.sync_mode='AUDIO_SYNC'
            state['timeline']=timeline(scene)
            body=body_mesh()
            session=Session()
            session.add([(-.15,.1),(.15,.1),(.15,.4),(-.15,.4)])
            scene.dd_document=session.document.dumps();scene.dd_avatar=body
            view=area.spaces.active.region_3d
            view.view_location=(.9,0,1.1);view.view_rotation=Quaternion((1,0,0),math.pi/2)
            view.view_distance=3;view.view_perspective='ORTHO';view.update()
            with bpy.context.temp_override(area=area,region=region):
                arrangement.ensure_volumes(bpy.context)
            active=open_editor()
            check(active.workflow_action('SIMULATE'),'Simulate starts the drape: '+str(active.message))
        elif stage==1:
            check(bpy.context.screen.is_animation_playing and 'dd_timeline' in scene,'Simulate locks the timeline while the drape plays')
            press('D',ctrl=True,alt=True)
        elif stage==2:
            check(workspace() is None,'Ctrl+Alt+D closes the editor mid-drape')
            restored(scene,'closing with Ctrl+Alt+D mid-drape')
            open_editor()
            play_drape()
        elif stage==3:
            check(bpy.context.screen.is_animation_playing and 'dd_timeline' in scene,'the drape plays again with the timeline locked')
            state['area_type']=area.type
            x,y=region.x+region.width//2,region.y+region.height//2
            area.type='PROPERTIES'
            bpy.context.window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
        elif stage==4:
            check(workspace() is None,'the editor closes when its 3D view goes away mid-drape')
            restored(scene,'closing because the 3D view went away mid-drape')
            active=open_editor()
            play_drape()
            def vanished(self,context,event):raise ReferenceError('probe view gone')
            editor.DD_OT_pattern_editor.handle_event=vanished
            try:result=active.modal(bpy.context,event_at_centre())
            finally:editor.DD_OT_pattern_editor.handle_event=original_handle
            check(result=={'CANCELLED'} and workspace() is None,'an editor error that ends the operator closes it mid-drape')
            restored(scene,'closing on an operator-ending error mid-drape')
            active=open_editor()
            enclosure=enclosing_collider(scene)
            active.workflow_action('KEEP')
            refusal=active.message or ''
            check(not garment.generated(scene,'final'),'Keep is refused after reopening: '+refusal)
            check('fell off' in refusal or 'inside' in refusal,'the refusal comes from the body check after the clock is locked: '+refusal)
            check('changed' not in refusal,'Keep after reopening is not refused as a stale design: '+refusal)
            check(timeline(scene)==state['timeline'] and 'dd_timeline' not in scene,
                  'a refused Keep after reopening restores the timeline it found: '+str(timeline(scene)))
            play_drape()
            garment.stop(bpy.context)
            active.workflow_action('KEEP')
            check(not garment.generated(scene,'final'),'Keep is refused again while the paused drape holds the clock: '+str(active.message))
            check('dd_timeline' in scene and scene.render.fps!=state['timeline'][1],
                  'a refused Keep leaves a clock it found locked still locked for the paused drape')
            bpy.data.objects.remove(enclosure,do_unlink=True)
            active.cleanup()
            REPORT.write_text(json.dumps(dict(passed=state['passed'])),encoding='utf-8')
            return None
        state['stage']+=1
        return .5
    except Exception:
        editor.DD_OT_pattern_editor.handle_event=original_handle
        REPORT.write_text(json.dumps(dict(passed=state['passed'],error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
        return None


bpy.app.timers.register(run,first_interval=1)
