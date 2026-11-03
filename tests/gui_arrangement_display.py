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
from devil_designer import arrangement,arrangement_controls,editor,live_panels,ui_system
from devil_designer.canvas import Rect
from devil_designer.core import Session,arrangement_record


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
            if 'vectors' in sample:
                from devil_designer.ellipse_volumes import ellipse_ring
                positions=[Vector(position) for position in ellipse_ring(sample,point['geometry']['clearance'],point['geometry']['axis'])]
            else:
                positions=[Vector(sample['center'])+sample['radius']*(normal*math.cos(math.tau*index/32)+tangent*math.sin(math.tau*index/32)) for index in range(33)]
            ring=[view3d_utils.location_3d_to_region_2d(context.region,context.region_data,position) for position in positions]
            for first,second in zip(ring,ring[1:]):
                if first is None or second is None:continue
                if panel is not None and any(panel.contains(*value) for value in (first,second)):continue
                lines.extend((tuple(first),tuple(second)))
    gpu.state.blend_set('ALPHA')
    if lines:
        shader.bind();shader.uniform_float('color',ui_system.ARRANGEMENT_RING)
        batch_for_shader(shader,'LINES',{'pos':lines}).draw(shader)
    view=context.region_data;camera=view.view_matrix.inverted()
    scale=ui_system.interface_scale()
    edge=ui_system.ARRANGEMENT_POINT_DIAMETER*scale/2
    for radius,color in ((edge,ui_system.ARRANGEMENT_EDGE),(edge-ui_system.ARRANGEMENT_EDGE_WIDTH*scale,ui_system.ARRANGEMENT_FILL)):
        for point in points:
            toward=(camera.translation-Vector(point['position'])) if view.is_perspective else camera.col[2].xyz
            alpha=ui_system.ARRANGEMENT_HIDDEN_ALPHA if Vector(point['normal']).dot(toward)<0 else 1
            horizontal,vertical=point['screen'];vertices=[]
            for index in range(20):
                first=math.tau*index/20;second=math.tau*(index+1)/20
                vertices.extend(((horizontal,vertical),(horizontal+radius*math.cos(first),vertical+radius*math.sin(first)),
                                 (horizontal+radius*math.cos(second),vertical+radius*math.sin(second))))
            shader.bind();shader.uniform_float('color',(*color[:3],color[3]*alpha))
            batch_for_shader(shader,'TRIS',{'pos':vertices}).draw(shader)
    gpu.state.blend_set('NONE')
    return points


def luminance(color):
    channels=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in color[:3]]
    return .2126*channels[0]+.7152*channels[1]+.0722*channels[2]


def contrast(first,second):
    high,low=sorted((luminance(first),luminance(second)),reverse=True)
    return (high+.05)/(low+.05)


def render_offscreen(context,area,region,view,width,height,draw):
    target=gpu.types.GPUOffScreen(width,height)
    try:
        with bpy.context.temp_override(area=area,region=region,region_data=view),target.bind(),gpu.matrix.push_pop():
            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(Matrix(((2/width,0,0,-1),(0,2/height,0,-1),(0,0,-1,0),(0,0,0,1))))
            gpu.state.depth_test_set('NONE')
            framebuffer=gpu.state.active_framebuffer_get()
            framebuffer.clear(color=(0,0,0,0))
            draw()
            return np.array(framebuffer.read_color(0,0,width,height,4,0,'FLOAT').to_list())
    finally:target.free()


def isolated_point(points,spacing):
    for point in points:
        if point['facing'] and all(other is point or math.dist(point['screen'],other['screen'])>spacing for other in points):
            return point
    return None


def check_states(check,area,region,view,scene,avatar,evidence):
    from devil_designer import garment
    width,height=region.width,region.height
    view.view_perspective='PERSP';view.view_distance=4
    view.view_rotation=Quaternion((1,0,0),math.pi/2);view.view_location=avatar.matrix_world.translation;view.update()
    preferences=bpy.context.preferences.view
    original_scale=preferences.ui_scale
    original_system=ui_system.interface_scale()/original_scale
    sizes=[]
    try:
        for scale in (1.0,1.5,2.0):
            preferences.ui_scale=scale
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
            check(abs(ui_system.interface_scale()-scale*original_system)<.01,'Blender applies UI scale '+str((scale,ui_system.interface_scale())))
            arrangement_controls._batch_cache=None
            with bpy.context.temp_override(area=area,region=region,region_data=view):
                points=arrangement_controls.projected_points(bpy.context)
            point=isolated_point(points,60*scale)
            check(point is not None,'an isolated front-facing point exists at UI scale '+str(scale))
            raster=render_offscreen(bpy.context,area,region,view,width,height,arrangement_controls.draw_points)
            row=raster[int(round(point['screen'][1]))]
            covered=np.nonzero(row[:,3]>.5)[0]
            near=covered[np.abs(covered-point['screen'][0])<40*scale]
            diameter=float(near.max()-near.min()+1) if len(near) else 0.0
            sizes.append(dict(ui_scale=scale,system_scale=ui_system.interface_scale(),diameter_px=diameter,
                              hit_diameter_px=ui_system.ARRANGEMENT_HIT_DIAMETER*ui_system.interface_scale(),
                              active_diameter_px=ui_system.ARRANGEMENT_ACTIVE_DIAMETER*ui_system.interface_scale()))
            check(diameter>=14*ui_system.interface_scale()-1,'normal marker is at least 14 px at 100 percent and scales with UI scale '+str(sizes[-1]))
            check(ui_system.ARRANGEMENT_HIT_DIAMETER*ui_system.interface_scale()>=32*scale*original_system-1e-6,'hit diameter is at least 32 px scaled '+str(scale))
    finally:
        preferences.ui_scale=original_scale
        arrangement_controls._batch_cache=None
    evidence['marker_sizes']=sizes
    backgrounds={'light body':(.82,.80,.78,1),'dark background':(.05,.06,.07,1)}
    ratios={name:dict(edge=contrast(ui_system.ARRANGEMENT_EDGE,color),fill=contrast(ui_system.ARRANGEMENT_FILL,color))
            for name,color in backgrounds.items()}
    ratios['edge_to_fill']=contrast(ui_system.ARRANGEMENT_EDGE,ui_system.ARRANGEMENT_FILL)
    evidence['contrast']=ratios
    check(all(max(value['edge'],value['fill'])>=3 for key,value in ratios.items() if key!='edge_to_fill') and ratios['edge_to_fill']>=3,
          'marker edge contrast is at least 3:1 on light and dark fixtures '+str(ratios))
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        points=arrangement_controls.projected_points(bpy.context)
    point=isolated_point(points,60)
    identity=(point['volume'],point['point'])
    patterns={}
    interaction=arrangement_controls._interaction
    session=Session();session.add([(-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1)])
    pattern=session.document.patterns[0]
    for state in ('IDLE','HOVER','PRESSED','BOUND'):
        interaction.state='IDLE' if state=='BOUND' else state
        interaction.point=None if state in {'IDLE','BOUND'} else identity
        pattern.arrangement=arrangement_record(*identity,version=3) if state=='BOUND' else None
        scene.dd_document=session.document.dumps()
        live_panels.sync(bpy.context)
        panel=next(item for item in garment.generated(scene,'panel'))
        for obj in bpy.context.view_layer.objects:obj.select_set(False)
        bpy.context.view_layer.objects.active=panel
        raster=render_offscreen(bpy.context,area,region,view,width,height,arrangement_controls.draw_points)
        x,y=(int(round(value)) for value in point['screen'])
        window=raster[y-12:y+13,x-12:x+13]
        patterns[state]=window[:,:,0]*.2126+window[:,:,1]*.7152+window[:,:,2]*.0722
    arrangement_controls.end_interaction()
    differences={first+'/'+second:float(np.abs(patterns[first]-patterns[second]).mean())
                 for index,first in enumerate(patterns) for second in list(patterns)[index+1:]}
    evidence['grayscale_state_differences']=differences
    check(all(value>.01 for value in differences.values()),'idle, hover, pressed and bound markers differ in grayscale '+str(differences))
    view.view_distance=40;view.update()
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        crowded=arrangement_controls.projected_points(bpy.context)
        unique=[point for point in crowded if point['facing'] and all(other is point or math.dist(point['screen'],other['screen'])>.5 or not other['facing'] for other in crowded)]
        correct=sum(1 for point in unique if (lambda hit:(hit['volume'],hit['point'])==(point['volume'],point['point']))(arrangement_controls.hit_point(bpy.context,point['screen'])))
    evidence['picking']=dict(crowded_points=len(crowded),unique_targets=len(unique),correct=correct)
    check(unique and correct==len(unique),'crowded picking returns the exact identity for every front-facing target')
    view.view_distance=4;view.update()


def check_preview(check,area,region,view,scene,evidence):
    from devil_designer import garment
    from devil_designer.panel_cache import clear_arrangement_caches
    import time
    session=Session();session.add([(-.3,-.3),(.3,-.3),(.3,.3),(-.3,.3)])
    scene.dd_spacing=.009
    scene.dd_document=session.document.dumps()
    panel=live_panels.sync(bpy.context)[0]
    identity=session.document.patterns[0].id
    for obj in bpy.context.view_layer.objects:obj.select_set(False)
    bpy.context.view_layer.objects.active=panel
    vertices=len(panel.data.vertices)
    timings=[]
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        setup=arrangement.ensure_volumes(bpy.context)
        targets=[(volume['id'],point['id']) for volume in setup['volumes'] if volume['id'] in ('chest','waist','hip') for point in volume['points']]
        for volume,point in targets:
            clear_arrangement_caches()
            started=time.perf_counter()
            preview=live_panels.preview_positions(bpy.context,identity,volume,point)
            timings.append((time.perf_counter()-started)*1000)
        volume,point=targets[0]
        preview=live_panels.preview_positions(bpy.context,identity,volume,point)
        live_panels.arrange_piece(bpy.context,identity,volume,point)
        committed=next(item for item in garment.generated(scene,'panel') if item['dd_pattern_id']==identity)
        world=[committed.matrix_world @ vertex.co for vertex in committed.data.vertices]
        agreement=max((Vector(first)-second).length for first,second in zip(preview['positions'],world))
    ordered=sorted(timings)
    evidence['preview']=dict(vertices=vertices,samples=len(timings),p50_ms=ordered[len(ordered)//2],
                             p95_ms=ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))],maximum_ms=ordered[-1],
                             preview_commit_max_mm=agreement*1000)
    check(vertices>=4500,'preview latency is measured on a panel near 5,000 vertices '+str(vertices))
    check(agreement<.001,'preview and committed vertices agree within 1 mm '+str(agreement*1000))
    check(evidence['preview']['p95_ms']<50,'cold preview p95 stays below 50 ms '+str(evidence['preview']))


def run():
    passed=[];comparisons=[]
    def check(condition,message):
        if not condition:raise AssertionError(message)
        passed.append(message)
    try:
        devil_designer.register()
        scene=bpy.context.scene;avatar=scene.objects['Cube']
        scene.dd_avatar=avatar
        arrangement.ensure_volumes(bpy.context)
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
                    active=SimpleNamespace(_area=area,_scene=None,canvas_layout=SimpleNamespace(panel=Rect(width*.45,0,width*.3,height))) if clipped else None
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
                        check([{key:value for key,value in point.items() if key!='facing'} for point in arrangement_controls.projected_points(bpy.context)]==expected,'hit projections identical '+str((perspective,distance,clipped)))
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
            scene.dd_reference_visible=True
            evidence={}
            check_states(check,area,region,view,scene,avatar,evidence)
            check_preview(check,area,region,view,scene,evidence)
            (ROOT/'scratch'/'issue76-display-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        (ROOT/'scratch'/'arrangement_display-report.json').write_text(json.dumps(dict(passed=passed,comparisons=comparisons)),encoding='utf-8')
    except Exception:
        (ROOT/'scratch'/'arrangement_display-report.json').write_text(json.dumps(dict(passed=passed,comparisons=comparisons,error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
    return None


bpy.app.timers.register(run,first_interval=2)
