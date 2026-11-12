import json
import math
import statistics
import sys
import time
import traceback
from pathlib import Path
import bpy
import bmesh
from mathutils import Quaternion

bpy.context.preferences.view.show_splash=False
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import arrangement,arrangement_controls,garment,live_panels
from devil_designer.core import Session

devil_designer.register()
state=dict(stage=0,passed=[])


def check(condition,message):
    if not condition:raise AssertionError(message)
    state['passed'].append(message)


def dispatch(kind,position):
    window=bpy.context.window
    window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(position[0]),y=int(position[1]))
    for value in ('PRESS','RELEASE'):window.event_simulate(type=kind,value=value,x=int(position[0]),y=int(position[1]))


def run():
    try:
        scene=bpy.context.scene;body=scene.objects['Cube']
        area=next(area for area in bpy.context.screen.areas if area.type=='VIEW_3D')
        region=next(region for region in area.regions if region.type=='WINDOW')
        with bpy.context.temp_override(area=area,region=region):
            center=(region.x+region.width/2,region.y+region.height/2)
            stage=state['stage']
            if stage==0:
                check(not bpy.ops.devil_designer.arrangement_guide.poll(),'arrangement H is inactive without an avatar or garment')
                for obj in bpy.context.selected_objects:obj.select_set(False)
                body.select_set(True);bpy.context.view_layer.objects.active=body
                dispatch('ESC',center)
                dispatch('H',center)
            elif stage==1:
                check(body.hide_get(),'native H still hides a selected object without an arrangement context')
                body.hide_set(False)
                session=Session();session.add([(-.15,.1),(.15,.1),(.15,.4),(-.15,.4)])
                scene.dd_document=session.document.dumps();scene.dd_avatar=body
                arrangement.ensure_volumes(bpy.context)
                panel=live_panels.sync(bpy.context)[0]
                for obj in bpy.context.selected_objects:obj.select_set(False)
                panel.select_set(True);bpy.context.view_layer.objects.active=panel
                view=area.spaces.active.region_3d
                view.view_location=(0,0,0);view.view_rotation=Quaternion((1,0,0),math.pi/2)
                view.view_distance=6;view.view_perspective='ORTHO';view.update()
                scene.dd_reference_visible=True
                point=next(point for point in arrangement_controls.projected_points(bpy.context) if point['volume']=='chest' and point['point']=='front')
                dispatch('LEFTMOUSE',(region.x+point['screen'][0],region.y+point['screen'][1]))
            elif stage==2:
                check(garment.document(scene).patterns[0].arrangement is not None,'native left-click keymap dispatch arranges a selected panel')
                check(arrangement_controls.selected_piece(bpy.context) is not None,
                      'native arrangement click retains panel selection: '+str(bpy.context.view_layer.objects.active))
                dispatch('H',center)
            elif stage==3:
                panel=garment.generated(scene,'panel')[0]
                check(scene.dd_reference_visible and panel.hide_get(),'native H over the 3D view hides the selected panel and leaves the body guide as stock Blender would')
                panel.hide_set(False)
                panel.select_set(False);body.select_set(True);bpy.context.view_layer.objects.active=body
                bpy.ops.object.mode_set(mode='EDIT')
                check(not bpy.ops.devil_designer.arrangement_pick.poll(),'point picking is inactive in mesh Edit Mode')
                dispatch('H',center)
            elif stage==4:
                mesh=bmesh.from_edit_mesh(body.data)
                check(all(vertex.hide for vertex in mesh.verts),'native H hides edit vertices without arrangement interception')
                bpy.ops.mesh.reveal();bpy.ops.object.mode_set(mode='OBJECT')
                scene.dd_reference_visible=True
                panel=garment.generated(scene,'panel')[0]
                for obj in bpy.context.selected_objects:obj.select_set(False)
                panel.select_set(True);bpy.context.view_layer.objects.active=panel
                view=area.spaces.active.region_3d
                view.view_location=(0,0,0);view.view_rotation=Quaternion((1,0,0),math.pi/2)
                view.view_distance=6;view.view_perspective='ORTHO';view.update()
                point=next(point for point in arrangement_controls.projected_points(bpy.context) if point['facing'] and point['volume']=='waist'
                           and 40<point['screen'][0]<region.width-40 and 40<point['screen'][1]<region.height-60)
                state['target']=(point['volume'],point['point']);state['screen']=(region.x+point['screen'][0],region.y+point['screen'][1])
                state['stored']=scene.dd_avatar['dd_arrangement_volumes']
                state['length']=arrangement.volume_dimensions(bpy.context,point['volume'])[0]
                state['matrix']=[list(row) for row in panel.matrix_world]
                bpy.ops.ed.undo_push(message='Before arrangement drag')
                x,y=state['screen']
                window=bpy.context.window
                window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(x),y=int(y))
                window.event_simulate(type='LEFTMOUSE',value='PRESS',x=int(x),y=int(y))
                window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(x),y=int(y)+12)
            elif stage==5:
                interaction=arrangement_controls._interaction
                check(interaction.state=='DRAGGING' and interaction.point==state['target'],'native drag starts after four pixels and keeps the point identity '+str((interaction.state,interaction.point,state['target'],state['screen'],bpy.context.view_layer.objects.active.name)))
                state['height']=interaction.height
                x,y=state['screen']
                bpy.context.window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(x),y=int(y)+13,shift=True)
            elif stage==6:
                interaction=arrangement_controls._interaction
                change=abs(interaction.height-state['height'])*state['length']
                state['fine_step_m']=change
                check(0<change<=.001,'Shift drag moves the point by at most 1 mm per pixel: '+str(change))
                x,y=state['screen']
                bpy.context.window.event_simulate(type='ESC',value='PRESS',x=int(x),y=int(y)+13)
            elif stage==7:
                panel=garment.generated(scene,'panel')[0]
                check(arrangement_controls._interaction.state=='IDLE' and scene.dd_avatar['dd_arrangement_volumes']==state['stored']
                      and [list(row) for row in panel.matrix_world]==state['matrix'],'native Escape restores the exact setup and panel pose')
                x,y=state['screen']
                window=bpy.context.window
                window.event_simulate(type='LEFTMOUSE',value='PRESS',x=int(x),y=int(y))
                window.event_simulate(type='MOUSEMOVE',value='NOTHING',x=int(x),y=int(y)+20)
                window.event_simulate(type='LEFTMOUSE',value='RELEASE',x=int(x),y=int(y)+20)
            elif stage==8:
                check(scene.dd_avatar['dd_arrangement_volumes']!=state['stored'],'native release commits the dragged point')
                bpy.ops.ed.undo()
            elif stage==9:
                scene=bpy.context.scene
                check(scene.dd_avatar['dd_arrangement_volumes']==state['stored'],'one Undo restores the point from before the drag')
                scene.dd_document='';scene.dd_avatar=None
                garment.remove_objects(garment.generated(scene,'panel'))
                check(not bpy.ops.devil_designer.arrangement_pick.poll(),'point picking passes through again when garment context is gone')
                state['selection']=[];state['bodies']=[]
                for segments,rings in ((48,32),(96,64)):
                    parts=[]
                    for position,scale in (((0,0,1.15),(.26,.15,.4)),((0,0,1.7),(.12,.12,.16)),((-.42,0,1.38),(.27,.08,.08)),
                                           ((.42,0,1.38),(.27,.08,.08)),((-.13,0,.45),(.105,.11,.45)),((.13,0,.45),(.105,.11,.45))):
                        bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=position)
                        parts.append(bpy.context.object);bpy.context.object.scale=scale
                        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
                    bpy.ops.object.select_all(action='DESELECT')
                    for part in parts:part.select_set(True)
                    bpy.context.view_layer.objects.active=parts[0]
                    bpy.ops.object.join()
                    bpy.context.object.data.calc_loop_triangles()
                    state['bodies'].append(bpy.context.object.name)
                state['run']=0
            elif stage>=10:
                if 'slice_budget_ms' not in state:
                    calibration=state.setdefault('idle_stamps',[])
                    calibration.append(time.perf_counter())
                    if len(calibration)<8:return .01
                    idle_ms=statistics.median(second-first for first,second in zip(calibration,calibration[1:]))*1000
                    state['idle_cadence_ms']=idle_ms
                    state['slice_budget_ms']=min(50,max(8,2*idle_ms))
                stamps=state.setdefault('stamps',[])
                run=state['run']
                body_object=scene.objects[state['bodies'][run//5]]
                if 'started' not in state:
                    scene.dd_avatar=None
                    if 'dd_arrangement_volumes' in body_object:del body_object['dd_arrangement_volumes']
                    stamps.clear()
                    def probe():
                        stamps.append(time.perf_counter())
                        return 0.0 if 'started' in state else None
                    if state.get('probe') is not None and bpy.app.timers.is_registered(state['probe']):bpy.app.timers.unregister(state['probe'])
                    state['probe']=probe
                    bpy.app.timers.register(probe,first_interval=0)
                    started=time.perf_counter()
                    scene.dd_avatar=body_object
                    state['callback']=time.perf_counter()-started
                    state['job']=arrangement.pending_job(bpy.context)
                    state['started']=started
                    return .02
                if 'dd_arrangement_volumes' not in body_object:return .02
                ready=time.perf_counter()
                window=[stamp for stamp in stamps if stamp>=state['started']]
                gaps=sorted(second-first for first,second in zip(window,window[1:]))
                state['selection'].append(dict(triangles=len(body_object.data.loop_triangles),callback_ms=state['callback']*1000,
                                               ready_s=ready-state['started'],event_samples=len(gaps),
                                               timer_slices=len(state['job'].timer_slices),longest_slice_ms=max(state['job'].timer_slices)*1000,
                                               gap_p95_ms=gaps[int(.95*(len(gaps)-1))]*1000 if gaps else 0,gap_max_ms=gaps[-1]*1000 if gaps else 0))
                del state['started']
                state['run']+=1
                if state['run']<10:return .02
                for record in state['selection']:
                    check(record['callback_ms']<50,'body selection callback stays below 50 ms '+str(record))
                    check(record['gap_p95_ms']<50,'input event gaps stay below 50 ms at the 95th percentile while fitting '+str(record))
                    check(record['ready_s']<(.5 if record['triangles']<20000 else 1),'arrangement points become ready within budget '+str(record))
                for offset in (0,5):
                    records=state['selection'][offset:offset+5]
                    longest_ms=statistics.median(record['longest_slice_ms'] for record in records)
                    check(longest_ms<=state['slice_budget_ms'],
                          'median longest fitting slice stays within calibrated 8?50 ms budget '
                          +str(dict(triangles=records[0]['triangles'],median_longest_slice_ms=longest_ms,
                                    budget_ms=state['slice_budget_ms'],idle_cadence_ms=state['idle_cadence_ms'])))
                (ROOT/'scratch'/'issue76-selection-gui.json').write_text(json.dumps(dict(runs=state['selection'],fine_step_m=state['fine_step_m'],
                    idle_cadence_ms=state['idle_cadence_ms'],slice_budget_ms=state['slice_budget_ms']),indent=2),encoding='utf-8')
                (ROOT/'scratch'/'arrangement-report.json').write_text(json.dumps(dict(passed=state['passed'])),encoding='utf-8')
                return None
            state['stage']+=1
        return .35
    except Exception:
        bpy.ops.screen.screenshot(filepath=str(ROOT/'scratch'/'arrangement-key-error.png'))
        (ROOT/'scratch'/'arrangement-report.json').write_text(json.dumps(dict(passed=state['passed'],error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
        return None


bpy.app.timers.register(run,first_interval=2)
