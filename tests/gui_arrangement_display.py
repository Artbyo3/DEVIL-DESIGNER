import json
import math
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
from unittest.mock import patch

import bpy
import gpu
import numpy as np
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Quaternion, Vector


ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import arrangement,arrangement_controls,editor,live_panels
from devil_designer.canvas import Rect
from devil_designer.core import Session


def reference_draw(context):
    panel=arrangement_controls.display_panel(context)
    points=[]
    for point in arrangement.world_points(context):
        screen=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,Vector(point['position']))
        if screen is not None and (panel is None or not panel.contains(*screen)):
            points.append(dict(point,screen=tuple(screen)))
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    volumes=set();lines=[]
    for point in points:
        if point['volume'] in volumes:continue
        volumes.add(point['volume'])
        normal=Vector(point['normal']);tangent=Vector(point['tangent'])
        for sample in (point['geometry']['samples'][0],point['geometry']['samples'][-1]):
            ring=[view3d_utils.location_3d_to_region_2d(context.region,context.region_data,
                  Vector(sample['center'])+sample['radius']*(normal*math.cos(math.tau*index/32)+tangent*math.sin(math.tau*index/32))) for index in range(33)]
            for first,second in zip(ring,ring[1:]):
                if first is None or second is None:continue
                if panel is not None and any(panel.contains(*value) for value in (first,second)):continue
                lines.extend((tuple(first),tuple(second)))
    gpu.state.blend_set('ALPHA')
    if lines:
        shader.bind();shader.uniform_float('color',(.28,.78,1,.22))
        batch_for_shader(shader,'LINES',{'pos':lines}).draw(shader)
    for point in points:
        horizontal,vertical=point['screen'];vertices=[]
        for index in range(16):
            first=math.tau*index/16;second=math.tau*(index+1)/16
            vertices.extend(((horizontal,vertical),(horizontal+5*math.cos(first),vertical+5*math.sin(first)),
                             (horizontal+5*math.cos(second),vertical+5*math.sin(second))))
        shader.bind();shader.uniform_float('color',(.28,.78,1,1))
        batch_for_shader(shader,'TRIS',{'pos':vertices}).draw(shader)
    gpu.state.blend_set('NONE')
    return points


def run():
    passed=[];comparisons=[]
    def check(condition,message):
        if not condition:raise AssertionError(message)
        passed.append(message)
    try:
        devil_designer.register()
        scene=bpy.context.scene;avatar=scene.objects['Cube']
        scene.dd_avatar=avatar
        session=Session();session.add([(0,0),(.3,0),(.3,.4),(0,.4)])
        scene.dd_document=session.document.dumps()
        live_panels.sync(bpy.context)
        scene.dd_reference_visible=True
        area=next(area for area in bpy.context.screen.areas if area.type=='VIEW_3D')
        region=next(region for region in area.regions if region.type=='WINDOW')
        with bpy.context.temp_override(area=area,region=region):
            view=area.spaces.active.region_3d
            view.view_location=(0,0,0);view.view_distance=7
            arrangement_controls._world_cache=None
            with patch.object(arrangement,'world_points',wraps=arrangement.world_points) as resolve:
                first=arrangement_controls.display_world_points(bpy.context)
                for index in range(5):
                    view.view_rotation=Quaternion((0,0,1),index*.1) @ Quaternion((1,0,0),1.3)
                    view.update()
                    check(arrangement_controls.display_world_points(bpy.context) is first,'orbit reuses world points '+str(index))
                check(resolve.call_count==1,'unchanged avatar resolves once, not per redraw')
                avatar.location.x+=.2;bpy.context.view_layer.update()
                check(arrangement_controls.display_world_points(bpy.context) is not first,'avatar translation invalidates cache')
                cached=arrangement_controls.display_world_points(bpy.context)
                avatar.scale.z=1.2;bpy.context.view_layer.update()
                check(arrangement_controls.display_world_points(bpy.context) is not cached,'avatar bounds and scale invalidate cache')
                cached=arrangement_controls.display_world_points(bpy.context)
                arrangement.edit_point(bpy.context,'chest','front',angle=.17,height=.6)
                check(arrangement_controls.display_world_points(bpy.context) is not cached,'edited point invalidates cache')
                check(arrangement_controls.display_world_points(bpy.context)==arrangement.world_points(bpy.context),'cached points exactly match unchanged arrangement math')
            width,height=region.width,region.height
            target=gpu.types.GPUOffScreen(width,height)
            try:
                for perspective,distance,clipped in (('PERSP',7,False),('ORTHO',7,False),('PERSP',7,True),('PERSP',.1,False)):
                    view.view_perspective=perspective;view.view_distance=distance;view.update()
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                    active=SimpleNamespace(_area=area,canvas_layout=SimpleNamespace(panel=Rect(width*.45,0,width*.3,height))) if clipped else None
                    with bpy.context.temp_override(area=area,region=region,region_data=view),patch.object(editor,'_active',active),target.bind(),gpu.matrix.push_pop():
                        gpu.matrix.load_matrix(Matrix.Identity(4))
                        gpu.matrix.load_projection_matrix(Matrix(((2/width,0,0,-1),(0,2/height,0,-1),(0,0,-1,0),(0,0,0,1))))
                        gpu.state.depth_test_set('NONE')
                        framebuffer=gpu.state.active_framebuffer_get()
                        framebuffer.clear(color=(0,0,0,0))
                        expected=reference_draw(bpy.context)
                        before=np.array(framebuffer.read_color(0,0,width,height,4,0,'FLOAT').to_list())
                        framebuffer.clear(color=(0,0,0,0))
                        arrangement_controls.draw_points()
                        after=np.array(framebuffer.read_color(0,0,width,height,4,0,'FLOAT').to_list())
                        check(arrangement_controls.projected_points(bpy.context)==expected,'hit projections identical '+str((perspective,distance,clipped)))
                        differences=np.abs(before-after)
                        error=float(differences.mean())
                        comparisons.append(dict(perspective=perspective,distance=distance,clipped=clipped,mean_channel_error=error,changed_channels=int((differences>.01).sum()),coverage_difference=int(((before[:,:,3]>0)!=(after[:,:,3]>0)).sum())))
                        check(error<.0001,'reference raster preserved '+str((perspective,distance,clipped,error)))
                view.view_distance=7;view.update()
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                with patch.object(arrangement_controls,'batch_for_shader',wraps=arrangement_controls.batch_for_shader) as batch:
                    batch.reset_mock()
                    for index in range(5):
                        view.view_rotation=Quaternion((0,0,1),index*.1) @ Quaternion((1,0,0),1.3);view.update()
                        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                    check(batch.call_count==0,'orbit changes uniforms without rebuilding GPU batches')
                    native=[]
                    def compare_native():
                        if bpy.context.area!=area:return
                        framebuffer=gpu.state.active_framebuffer_get()
                        horizontal,vertical,width,height=gpu.state.viewport_get()
                        framebuffer.clear(color=(0,0,0,0))
                        reference_draw(bpy.context)
                        before=np.array(framebuffer.read_color(horizontal,vertical,width,height,4,0,'FLOAT').to_list())
                        framebuffer.clear(color=(0,0,0,0))
                        arrangement_controls.draw_points()
                        after=np.array(framebuffer.read_color(horizontal,vertical,width,height,4,0,'FLOAT').to_list())
                        native.append(dict(error=float(np.abs(before-after).mean()),before_max=before.max(axis=(0,1)).tolist(),after_max=after.max(axis=(0,1)).tolist(),coverage_difference=int(((before[:,:,3]>0)!=(after[:,:,3]>0)).sum())))
                    handle=bpy.types.SpaceView3D.draw_handler_add(compare_native,(),'WINDOW','POST_PIXEL')
                    try:bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                    finally:bpy.types.SpaceView3D.draw_handler_remove(handle,'WINDOW')
                    check(bool(native) and max(item['error'] for item in native)<.0001,'native viewport raster and color parity '+str(native))
                    scene.dd_reference_visible=False
                    with patch.object(arrangement_controls,'display_world_points',side_effect=AssertionError('hidden display resolved geometry')):
                        with bpy.context.temp_override(area=area,region=region,region_data=view):
                            arrangement_controls.draw_points()
                            check(not arrangement_controls.projected_points(bpy.context),'H off skips all geometry and hit detection')
            finally:target.free()
        (ROOT/'scratch'/'arrangement_display-report.json').write_text(json.dumps(dict(passed=passed,comparisons=comparisons)),encoding='utf-8')
    except Exception:
        (ROOT/'scratch'/'arrangement_display-report.json').write_text(json.dumps(dict(passed=passed,comparisons=comparisons,error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
    return None


bpy.app.timers.register(run,first_interval=2)
