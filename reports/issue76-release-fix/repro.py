import json
import os
import math
import sys
import traceback
from pathlib import Path
import bpy
from mathutils import Quaternion

bpy.context.preferences.view.show_splash=False
ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True
SOURCE=Path(os.environ.get('DD_SOURCE',str(ROOT)))
sys.path.insert(0,str(SOURCE))
import os
import importlib
import importlib.util
import shutil
TAG=os.environ.get('DD_REPRO_TAG','single')
import devil_designer
devil_designer.register()
if TAG=='double':
    second=ROOT/'scratch'/'repro76'/'second'/'devil_designer'
    if second.exists():shutil.rmtree(second)
    shutil.copytree(SOURCE/'devil_designer',second,ignore=shutil.ignore_patterns('__pycache__'))
    spec=importlib.util.spec_from_file_location('dd_second',second/'__init__.py',submodule_search_locations=[str(second)])
    module=importlib.util.module_from_spec(spec);sys.modules['dd_second']=module;spec.loader.exec_module(module)
    try:module.register()
    except Exception:
        log_second=traceback.format_exc();print('SECOND REGISTER FAILED');print(log_second)
    PACKAGE='dd_second' if 'dd_second.editor' in sys.modules and getattr(bpy.types,'DEVIL_DESIGNER_OT_pattern_editor',None) and bpy.types.DEVIL_DESIGNER_OT_pattern_editor.__module__.startswith('dd_second') else 'devil_designer'
else:
    PACKAGE='devil_designer'
arrangement=importlib.import_module(PACKAGE+'.arrangement')
arrangement_controls=importlib.import_module(PACKAGE+'.arrangement_controls')
editor=importlib.import_module(PACKAGE+'.editor')
garment=importlib.import_module(PACKAGE+'.garment')
Session=importlib.import_module(PACKAGE+'.core').Session
OUT=ROOT/'scratch'/'repro76'/('result-'+TAG+os.environ.get('DD_SUFFIX','')+'.json')
log=dict(errors=[],steps=[],package=None)
state=dict(stage=0)
original_handle=editor.DD_OT_pattern_editor.handle_event
original_cleanup=editor.DD_OT_pattern_editor.cleanup


def logged_handle(self,context,event):
    try:return original_handle(self,context,event)
    except BaseException:
        log['errors'].append(dict(stage=state['stage'],event=(event.type,event.value),trace=traceback.format_exc()))
        raise


def logged_cleanup(self):
    if not self._closed:log['steps'].append(dict(stage=state['stage'],closed=True,stack=''.join(traceback.format_stack(limit=6))))
    return original_cleanup(self)


editor.DD_OT_pattern_editor.handle_event=logged_handle
editor.DD_OT_pattern_editor.cleanup=logged_cleanup


def build_body():
    parts=[]
    for position,scale in (((0,0,1.15),(.26,.15,.4)),((0,0,1.7),(.12,.12,.16)),((-.42,0,1.38),(.27,.08,.08)),
                           ((.42,0,1.38),(.27,.08,.08)),((-.13,0,.45),(.105,.11,.45)),((.13,0,.45),(.105,.11,.45))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=32,location=position)
        parts.append(bpy.context.object);bpy.context.object.scale=scale
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:part.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    bpy.context.object.name='Body'
    return bpy.context.object


def areas():
    area=next(area for area in bpy.context.screen.areas if area.type=='VIEW_3D')
    return area,next(region for region in area.regions if region.type=='WINDOW')


def alive():
    workspace=editor._active
    return workspace is not None and not workspace._closed


def open_editor():
    area,region=areas()
    with bpy.context.temp_override(area=area,region=region):
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    workspace=editor._active
    workspace.reveal_3d()
    workspace.session.selected=workspace.session.document.patterns[0].id
    workspace.sync_selection()
    bpy.context.scene.dd_reference_visible=True
    return workspace


def point_screen(volume='chest',identity='front'):
    area,region=areas()
    with bpy.context.temp_override(area=area,region=region):
        points=arrangement_controls.projected_points(bpy.context)
        log['diag']=dict(visible=bpy.context.scene.dd_reference_visible,region=(region.width,region.height),panel=str(arrangement_controls.display_panel(bpy.context).__dict__ if arrangement_controls.display_panel(bpy.context) else None),world=len(arrangement_controls.display_world_points(bpy.context)))
    log.setdefault('points',[(point['volume'],point['point'],point.get('facing',True),point['screen']) for point in points])
    target=next(point for point in points if point.get('facing',True) and point['volume']=='chest' and 30<point['screen'][0]<region.width-30 and 30<point['screen'][1]<region.height-60)
    return region.x+target['screen'][0],region.y+target['screen'][1]


def drag(start,offset,steps=5):
    window=bpy.context.window
    x,y=int(start[0]),int(start[1])
    window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x,y=y)
    window.event_simulate(type='LEFTMOUSE',value='PRESS',x=x,y=y)
    for step in range(1,steps+1):
        window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=x+offset[0]*step//steps,y=y+offset[1]*step//steps)
    window.event_simulate(type='LEFTMOUSE',value='RELEASE',x=x+offset[0],y=y+offset[1])


def record(name):
    workspace=editor._active
    log['steps'].append(dict(stage=state['stage'],name=name,alive=alive(),message=getattr(workspace,'message',None) if workspace else None,
                             arrangement=workspace.session.document.patterns[0].arrangement if alive() else None))


def run():
    try:
        scene=bpy.context.scene
        area,region=areas()
        stage=state['stage']
        if stage==0:
            log['package']=PACKAGE
            for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
            body=build_body()
            session=Session()
            session.add([(-.15,.1),(.15,.1),(.15,.4),(-.15,.4)])
            session.add([(.3,.1),(.6,.1),(.6,.4),(.3,.4)])
            scene.dd_document=session.document.dumps();scene.dd_avatar=body
            view=area.spaces.active.region_3d
            view.view_location=(.9,0,1.1);view.view_rotation=Quaternion((1,0,0),math.pi/2)
            view.view_distance=3;view.view_perspective='ORTHO';view.update()
            scene.dd_reference_visible=True
            with bpy.context.temp_override(area=area,region=region):arrangement.ensure_volumes(bpy.context)
            if os.environ.get('DD_SEED_DUPLICATE'):
                with bpy.context.temp_override(area=area,region=region):
                    garment.build_panels(bpy.context)
                    original=garment.generated(scene,'panel')[0]
                    copy=original.copy();copy.data=original.data.copy();original.users_collection[0].objects.link(copy)
                log['seeded_panels']=[(obj.name,obj.get('dd_pattern_id')) for obj in scene.objects if obj.get('dd_kind')=='panel']
        elif stage==1:
            open_editor();record('editor opened')
        elif stage==2:
            state['b']=point_screen()
            drag(state['b'],(0,0),1)
        elif stage==3:
            record('(b) attach panel to point by click')
            if not alive():open_editor()
        elif stage==4:
            drag(point_screen(),(30,24))
        elif stage==5:
            record('(a) drag arrangement point and release')
            if not alive():open_editor()
        elif stage==6:
            workspace=editor._active
            workspace.canvas_layout=workspace.make_layout()
            pattern=workspace.session.document.patterns[0]
            xs=[v[0] for v in pattern.points];ys=[v[1] for v in pattern.points]
            centre=workspace.view.screen(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2),workspace.canvas_layout.canvas)
            state['c']=centre
            log['steps'].append(dict(name='piece centre',centre=centre,panel=[workspace.canvas_layout.panel.x,workspace.canvas_layout.panel.y,workspace.canvas_layout.panel.w,workspace.canvas_layout.panel.h]))
            window=bpy.context.window
            window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(region.x+centre[0]),y=int(region.y+centre[1]))
            window.event_simulate(type='V',value='PRESS',x=int(region.x+centre[0]),y=int(region.y+centre[1]))
            window.event_simulate(type='V',value='RELEASE',x=int(region.x+centre[0]),y=int(region.y+centre[1]))
            log['steps'].append(dict(name='tool',tool=workspace.tool))
            drag((region.x+centre[0],region.y+centre[1]),(25,10))
        elif stage==7:
            record('(c) move panel in 2D and release')
            if not alive():open_editor()
        elif stage==8:
            workspace=editor._active
            with bpy.context.temp_override(area=area,region=region):workspace.perform_action('SIMULATE')
            record('(d) simulate')
        elif stage==9:
            record('(d) after simulate tick')
            log['panels']=[(obj.name,obj.get('dd_pattern_id')) for obj in scene.objects if obj.get('dd_kind')=='panel']
            OUT.write_text(json.dumps(log,indent=2,default=str),encoding='utf-8')
            bpy.ops.wm.quit_blender()
            return None
        state['stage']+=1
        return .6
    except Exception:
        log['fatal']=traceback.format_exc()
        OUT.write_text(json.dumps(log,indent=2,default=str),encoding='utf-8')
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(run,first_interval=2)
