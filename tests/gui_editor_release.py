import importlib.util
import json
import math
import shutil
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
from devil_designer import arrangement,arrangement_controls,editor,garment,layering,snapping
from devil_designer.core import Session

REPORT=ROOT/'scratch'/'editor_release-report.json'
state=dict(stage=0,passed=[],errors=[])
original_handle=editor.DD_OT_pattern_editor.handle_event


def recording_handle(self,context,event):
    try:return original_handle(self,context,event)
    except Exception:
        state['errors'].append(traceback.format_exc())
        raise


editor.DD_OT_pattern_editor.handle_event=recording_handle


def check(condition,message):
    if not condition:raise AssertionError(message)
    state['passed'].append(message)


def second_copy_refused():
    target=ROOT/'scratch'/'second_install'/'devil_designer'
    if target.exists():shutil.rmtree(target)
    shutil.copytree(ROOT/'devil_designer',target,ignore=shutil.ignore_patterns('__pycache__'))
    spec=importlib.util.spec_from_file_location('dd_second_install',target/'__init__.py',submodule_search_locations=[str(target)])
    module=importlib.util.module_from_spec(spec)
    sys.modules['dd_second_install']=module
    spec.loader.exec_module(module)
    try:module.register()
    except RuntimeError as failure:return 'already enabled' in str(failure)
    return False


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


def chest_point():
    area,region=areas()
    with bpy.context.temp_override(area=area,region=region):
        points=arrangement_controls.projected_points(bpy.context)
    point=next(point for point in points if point['facing'] and point['volume']=='chest'
               and 30<point['screen'][0]<region.width-30 and 30<point['screen'][1]<region.height-60)
    return region.x+point['screen'][0],region.y+point['screen'][1]


def gesture(start,offset,steps=5):
    window=bpy.context.window
    x,y=int(start[0]),int(start[1])
    window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
    window.event_simulate(type='LEFTMOUSE',value='PRESS',x=x,y=y)
    for step in range(1,steps+1):
        window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x+offset[0]*step//steps,y=y+offset[1]*step//steps)
    window.event_simulate(type='LEFTMOUSE',value='RELEASE',x=x+offset[0],y=y+offset[1])


def key(kind,position):
    window=bpy.context.window
    for value in ('PRESS','RELEASE'):window.event_simulate(type=kind,value=value,x=int(position[0]),y=int(position[1]))


def piece_centre(active,index=0):
    _,region=areas()
    active.canvas_layout=active.make_layout()
    pattern=active.session.document.patterns[index]
    xs=[point[0] for point in pattern.points];ys=[point[1] for point in pattern.points]
    x,y=active.view.screen(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2),active.canvas_layout.canvas)
    return region.x+x,region.y+y


def panel_ids(scene):
    return sorted(panel.get('dd_pattern_id') for panel in garment.generated(scene,'panel'))


def survived(label):
    active=workspace()
    check(active is not None,label+' keeps the 2D editor open')
    check(not state['errors'],label+' raises no exception through the real modal handler: '+'\n'.join(state['errors']))
    check('Unexpected error' not in (active.message or ''),label+' reports no unexpected error: '+str(active.message))


def run():
    try:
        scene=bpy.context.scene
        area,region=areas()
        stage=state['stage']
        if stage==0:
            devil_designer.register()
            check(second_copy_refused(),'a second installed copy refuses to register with a clear message')
            check(sum(getattr(handler,'__name__','')=='capture_updates' for handler in bpy.app.handlers.depsgraph_update_post)==1,
                  'only one copy listens for scene updates')
            for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
            scene.frame_end=250;scene.render.fps=24;scene.render.fps_base=1;scene.sync_mode='AUDIO_SYNC'
            state['timeline']=(scene.frame_end,scene.render.fps,scene.render.fps_base,scene.sync_mode)
            body=body_mesh()
            session=Session()
            session.add([(-.15,.1),(.15,.1),(.15,.4),(-.15,.4)])
            session.add([(.3,.1),(.6,.1),(.6,.4),(.3,.4)])
            scene.dd_document=session.document.dumps();scene.dd_avatar=body
            view=area.spaces.active.region_3d
            view.view_location=(.9,0,1.1);view.view_rotation=Quaternion((1,0,0),math.pi/2)
            view.view_distance=3;view.view_perspective='ORTHO';view.update()
            with bpy.context.temp_override(area=area,region=region):
                arrangement.ensure_volumes(bpy.context)
                garment.build_panels(bpy.context)
                original=garment.generated(scene,'panel')[0]
                duplicate=original.copy();duplicate.data=original.data.copy()
                original.users_collection[0].objects.link(duplicate)
                bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            active=workspace()
            check(active is not None,'pattern editor opens as a real modal operator')
            active.reveal_3d()
            active.session.selected=active.session.document.patterns[0].id
            active.sync_selection()
            scene.dd_reference_visible=True
            key('V',piece_centre(active))
        elif stage==1:
            check(workspace().tool=='SELECT','V selects the Select tool through a real key event')
            gesture(chest_point(),(0,0),1)
        elif stage==2:
            survived('releasing a click on an arrangement point')
            record=workspace().session.document.patterns[0].arrangement
            check(record is not None and record['volume']=='chest' and record['version']==3,'release attaches the selected panel to the clicked point')
            state['volumes']=scene.dd_avatar['dd_arrangement_volumes']
            gesture(chest_point(),(30,24))
        elif stage==3:
            survived('releasing a dragged arrangement point')
            check(scene.dd_avatar['dd_arrangement_volumes']!=state['volumes'],'release commits the dragged point')
            active=workspace()
            state['points']=[list(point) for point in active.session.document.patterns[0].points]
            gesture(piece_centre(active),(25,10))
        elif stage==4:
            survived('releasing a panel moved in the 2D canvas')
            active=workspace()
            check([list(point) for point in active.session.document.patterns[0].points]!=state['points'],'release commits the 2D panel move')
            ids=panel_ids(scene)
            check(len(ids)==len(set(ids))==len(active.session.document.patterns),'each pattern keeps exactly one live panel: '+str(ids))
            active.canvas_layout=active.make_layout()
            button=active.canvas_layout.buttons['SIMULATE'][0]
            window=bpy.context.window
            x,y=int(region.x+button.x+button.w/2),int(region.y+button.y+button.h/2)
            window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
            key('LEFTMOUSE',(x,y))
        elif stage==5:
            survived('Simulate after arrangement interactions')
            check(bool(garment.generated(scene,'simulation')),'Simulate builds the drape after arrangement interactions')
            check(bpy.context.screen.is_animation_playing and 'dd_timeline' in scene,'Simulate locks the timeline while the drape plays')
            active=workspace()
            def failing(self,context,event):raise RuntimeError('probe failure')
            editor.DD_OT_pattern_editor.handle_event=failing
            try:result=active.modal(bpy.context,type('Event',(),dict(type='MOUSEMOVE',value='NOTHING',mouse_x=region.x+5,mouse_y=region.y+5,ctrl=False,shift=False,alt=False))())
            finally:editor.DD_OT_pattern_editor.handle_event=recording_handle
            check(result=={'RUNNING_MODAL'} and workspace() is active,'a RuntimeError inside the editor keeps it open')
            check('probe failure' in (active.error_message or ''),'the editor reports the RuntimeError instead of closing: '+str(active.error_message))
            active.error_message=None
            active.canvas_layout=active.make_layout()
            button=active.canvas_layout.buttons['CLOSE'][0]
            x,y=int(region.x+button.x+button.w/2),int(region.y+button.y+button.h/2)
            bpy.context.window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
            key('LEFTMOUSE',(x,y))
        elif stage==6:
            check(workspace() is None,'the Close button closes the editor mid-drape')
            check(not bpy.context.screen.is_animation_playing,'closing mid-drape stops the drape playing')
            check((scene.frame_end,scene.render.fps,scene.render.fps_base,scene.sync_mode)==state['timeline'] and 'dd_timeline' not in scene,
                  'closing mid-drape restores frame end, frame rate and sync mode: '+str((scene.frame_end,scene.render.fps,scene.render.fps_base,scene.sync_mode)))
            check(bool(garment.generated(scene,'simulation')),'closing keeps the drape in the scene')
            with bpy.context.temp_override(area=area,region=region):
                bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            active=workspace()
            check(active is not None,'the editor reopens after closing mid-drape')
            active.perform_action('KEEP')
            kept=garment.generated(scene,'final')
            if kept:
                check((scene.frame_end,scene.render.fps,scene.render.fps_base,scene.sync_mode)==state['timeline'] and 'dd_timeline' not in scene,
                      'Keep after reopening finishes and leaves the timeline restored')
            else:
                check((scene.frame_end,scene.render.fps,scene.render.fps_base,scene.sync_mode)==state['timeline'] and 'dd_timeline' not in scene,
                      'a Keep refused after reopening restores the timeline it found: '+str(active.message))
                state['refused']=active.message
        elif stage==7:
            active=workspace()
            kept=garment.generated(scene,'final')
            if not kept:
                REPORT.write_text(json.dumps(dict(passed=state['passed'],error='Keep refused, Wear over checks need a kept mesh: '+str(state.get('refused')))),encoding='utf-8')
                return None
            own=kept[0]
            check(dict(layering.worn_garments(scene))[own] is False,'a kept copy of the current design starts with Wear over off')
            check(own not in layering.collision_bodies(scene),'that kept copy is not a collision body for the next drape')
            other=own.copy();other.data=own.data.copy();own.users_collection[0].objects.link(other)
            other['dd_piece_ids']='["another-design"]'
            check(dict(layering.worn_garments(scene))[other] is True,'a kept mesh of a different design keeps Wear over on')
            own['dd_wear_over']=True
            check(dict(layering.worn_garments(scene))[own] is True and own in layering.collision_bodies(scene),'a manual Wear over choice wins over the default')
            del own['dd_wear_over']
            bpy.data.objects.remove(other,do_unlink=True)
            active.restore_canvas()
            active.tool='POLYGON';active.snap=True;active.draft=[]
            active.canvas_layout=active.make_layout()
            corner=active.session.document.patterns[1].vertices[0]
            spot=active.view.screen((corner.x,corner.y),active.canvas_layout.canvas)
            state['corner']=(corner.x,corner.y)
            bpy.context.window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(region.x+spot[0]+4),y=int(region.y+spot[1]+3))
        elif stage==8:
            active=workspace()
            marker=active.snap_marker
            check(marker is not None and marker[1]==snapping.POINT and math.dist(marker[0],state['corner'])<1e-9,
                  'hovering a drawing tool near a corner shows a point snap marker before the first click: '+str(marker))
            active.renderer.draw(active)
            check(not active.error_message,'the snap marker draws without a render error')
            _,region=areas()
            spot=active.view.screen(state['corner'],active.canvas_layout.canvas)
            key('LEFTMOUSE',(region.x+spot[0]+4,region.y+spot[1]+3))
        elif stage==9:
            active=workspace()
            first=active.draft[0] if active.draft else None
            point=(first.x,first.y) if hasattr(first,'x') else first
            check(point is not None and math.dist(point,state['corner'])<1e-9,'the first polygon click lands exactly on the snapped corner: '+str(point))
            active.cancel_gesture()
            garment.stop(bpy.context)
            area,region=areas()
            with bpy.context.temp_override(area=area,region=region):
                bpy.ops.ed.undo_push(message='Before scene change')
                scene.frame_current=scene.frame_current+7
                body=scene.dd_avatar
                body.location.x+=.25
                bpy.ops.ed.undo_push(message='Scene change')
                state['undo_document']=scene.dd_document
                state['undo_result']=bpy.ops.ed.undo()
            centre=(region.x+region.width//2,region.y+region.height//2)
            bpy.context.window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=centre[0],y=centre[1])
        elif stage==10:
            check(state['undo_result']=={'FINISHED'},"Blender's own undo ran over the 3D view: "+str(state['undo_result']))
            survived("Blender's own undo over the 3D view")
            active=workspace()
            check(active._scene==bpy.context.scene and active._scene.dd_document==state['undo_document'],
                  "after Blender's undo the editor works on the scene Blender restored")
            active.renderer.draw(active)
            check(not active.error_message,"the editor draws after Blender's undo: "+str(active.error_message))
            REPORT.write_text(json.dumps(dict(passed=state['passed'])),encoding='utf-8')
            return None
        state['stage']+=1
        return .5
    except Exception:
        REPORT.write_text(json.dumps(dict(passed=state['passed'],error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
        return None


bpy.app.timers.register(run,first_interval=1)
