import json
import math
import sys
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
from devil_designer import arrangement_controls,garment,live_panels
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
                check(bpy.ops.devil_designer.arrangement_guide.poll(),'arrangement guide shortcut is available after arranging')
                dispatch('H',center)
            elif stage==3:
                panel=garment.generated(scene,'panel')[0]
                check(not scene.dd_reference_visible and not panel.hide_get(),'native arrangement H hides guides rather than the selected panel')
                panel.select_set(False);body.select_set(True);bpy.context.view_layer.objects.active=body
                bpy.ops.object.mode_set(mode='EDIT')
                check(not bpy.ops.devil_designer.arrangement_pick.poll(),'point picking is inactive in mesh Edit Mode')
                dispatch('H',center)
            elif stage==4:
                mesh=bmesh.from_edit_mesh(body.data)
                check(all(vertex.hide for vertex in mesh.verts),'native H hides edit vertices without arrangement interception')
                bpy.ops.mesh.reveal();bpy.ops.object.mode_set(mode='OBJECT')
                scene.dd_document='';scene.dd_avatar=None
                garment.remove_objects(garment.generated(scene,'panel'))
                check(not bpy.ops.devil_designer.arrangement_pick.poll(),'point picking passes through again when garment context is gone')
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
