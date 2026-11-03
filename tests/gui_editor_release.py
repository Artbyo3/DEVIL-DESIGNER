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
from devil_designer import arrangement,arrangement_controls,editor,garment,live_panels
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
            garment.stop(bpy.context)
            REPORT.write_text(json.dumps(dict(passed=state['passed'])),encoding='utf-8')
            return None
        state['stage']+=1
        return .5
    except Exception:
        REPORT.write_text(json.dumps(dict(passed=state['passed'],error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
        return None


bpy.app.timers.register(run,first_interval=1)
