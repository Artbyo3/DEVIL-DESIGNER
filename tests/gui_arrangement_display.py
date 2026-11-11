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
from mathutils import Matrix, Quaternion, Vector


ROOT=Path(__file__).resolve().parents[1]
PREVIEW_CEILING_MS=150
PREVIEW_REFERENCE_RATIO=6
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import arrangement,arrangement_controls,editor,live_panels,ui_system
from devil_designer.canvas import Rect
from devil_designer.core import Session,arrangement_record


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


def named_point(area,region,view,volume,identity):
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        points=arrangement_controls.projected_points(bpy.context)
    return next(point for point in points if point['volume']==volume and point['point']==identity)


def footprint(raster,point,reach):
    x,y=(int(round(value)) for value in point['screen'])
    def run(line,center):
        if not line[center]:return 0.0
        low=center
        while low>max(center-reach,0) and line[low-1]:low-=1
        high=center
        while high<min(center+reach,len(line)-1) and line[high+1]:high+=1
        return float(high-low+1)
    covered=raster[:,:,3]>.5
    return run(covered[y,:],x),run(covered[:,x],y)


def facing_view(view,avatar,distance=4):
    view.view_perspective='PERSP';view.view_distance=distance
    view.view_rotation=Quaternion((1,0,0),math.pi/2);view.view_location=avatar.matrix_world.translation;view.update()


def render(area,region,view):
    return render_offscreen(bpy.context,area,region,view,region.width,region.height,arrangement_controls.draw_points)


def check_zoom(check,area,region,view,avatar,evidence):
    widths=[]
    scale=ui_system.interface_scale()
    base=ui_system.ARRANGEMENT_POINT_DIAMETER*scale
    target=Vector(named_point(area,region,view,'chest','front')['position'])
    for distance in (.3,4,60):
        facing_view(view,avatar,distance)
        view.view_location=target;view.update()
        point=named_point(area,region,view,'chest','front')
        widths.append(footprint(render(area,region,view),point,int(base*1.5))[0])
    facing_view(view,avatar)
    evidence['zoom_widths_px']=widths
    check(widths[0]>widths[2],'points are larger zoomed in than zoomed out '+str(widths))
    check(widths[0]<=base*2+2,'points stop growing at the zoomed-in limit '+str(widths))
    check(widths[2]>=base*.55-2,'points stop shrinking at the zoomed-out limit '+str(widths))


def check_surface_alignment(check,area,region,view,evidence):
    front=named_point(area,region,view,'chest','front')
    side=named_point(area,region,view,'chest','side')
    raster=render(area,region,view)
    reach=int(ui_system.ARRANGEMENT_POINT_DIAMETER*ui_system.interface_scale()*1.5)
    shapes=dict(front=footprint(raster,front,reach),side=footprint(raster,side,reach))
    evidence['surface_shapes_px']=shapes
    check(abs(shapes['front'][0]-shapes['front'][1])<=2,'a point facing the camera is round '+str(shapes))
    check(shapes['side'][0]<shapes['side'][1]*.5,'a point on the body edge flattens into a sliver instead of facing the camera '+str(shapes))


def check_occlusion(check,area,region,view,evidence):
    front=named_point(area,region,view,'chest','front')
    back=named_point(area,region,view,'chest','back')
    check(front['visible'] and not back['visible'],'the avatar hides points behind it')
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        behind=arrangement_controls.hit_point(bpy.context,back['screen'])
    check(behind is None or (behind['volume'],behind['point'])!=('chest','back'),'a point behind the avatar cannot be clicked')
    bpy.ops.mesh.primitive_plane_add(size=.2,location=tuple(Vector(front['position'])+Vector((0,-.2,0))),rotation=(math.pi/2,0,0))
    blocker=bpy.context.object
    bpy.context.view_layer.update()
    results={}
    try:
        for label,kind in (('other mesh',None),('add-on panel','panel')):
            if kind:blocker['dd_kind']=kind
            arrangement_controls._projection_cache=None
            point=named_point(area,region,view,'chest','front')
            raster=render(area,region,view)
            x,y=(int(round(value)) for value in point['screen'])
            with bpy.context.temp_override(area=area,region=region,region_data=view):
                hit=arrangement_controls.hit_point(bpy.context,point['screen'])
            results[label]=dict(visible=point['visible'],alpha=float(raster[y,x,3]),picked=bool(hit) and (hit['volume'],hit['point'])==('chest','front'))
    finally:
        bpy.data.objects.remove(blocker,do_unlink=True)
        bpy.context.view_layer.update()
        arrangement_controls._projection_cache=None
    evidence['occlusion']=results
    check(not results['other mesh']['visible'] and results['other mesh']['alpha']<.1,'another mesh in front hides a point '+str(results))
    check(not results['other mesh']['picked'],'a hidden point cannot be clicked '+str(results))
    check(results['add-on panel']['visible'] and results['add-on panel']['alpha']>.5,'an add-on panel does not hide a point '+str(results))
    check(results['add-on panel']['picked'],'a point under an add-on panel stays clickable '+str(results))


def check_points_only(check,area,region,view,evidence):
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        points=[point for point in arrangement_controls.projected_points(bpy.context) if point['visible']]
    raster=render(area,region,view)
    rows,columns=np.nonzero(raster[:,:,3]>.02)
    screens=np.array([point['screen'] for point in points])
    pixels=np.stack((columns+.5,rows+.5),axis=1)
    distances=np.sqrt(((pixels[:,None,:]-screens[None,:,:])**2).sum(axis=2)).min(axis=1)
    reach=ui_system.ARRANGEMENT_POINT_DIAMETER*ui_system.interface_scale()+2
    evidence['drawn_pixels']=dict(pixels=len(pixels),farthest_from_a_point_px=float(distances.max()),allowed_px=reach)
    check(len(pixels)>0 and distances.max()<=reach,'every drawn pixel belongs to a visible point, so no ring or line surrounds the avatar '+str(evidence['drawn_pixels']))
    colors={}
    for mirrored,expected in ((False,ui_system.ARRANGEMENT_FILL),(True,ui_system.ARRANGEMENT_MIRRORED)):
        point=next(item for item in points if item['mirrored']==mirrored and item['facing'] and
                   all(other is item or math.dist(item['screen'],other['screen'])>24*ui_system.interface_scale() for other in points))
        x,y=(int(point['screen'][axis]) for axis in (0,1))
        colors[str(mirrored)]=raster[y,x,:3].tolist()
    evidence['rendered_point_colors']=colors
    check(math.dist(colors['True'],colors['False'])>.2,'a mirrored point renders in a different color from a single point '+str(colors))


def check_states(check,area,region,view,scene,avatar,evidence):
    from devil_designer import garment
    facing_view(view,avatar)
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
            point=named_point(area,region,view,'chest','front')
            base=ui_system.ARRANGEMENT_POINT_DIAMETER*ui_system.interface_scale()
            width=footprint(render(area,region,view),point,int(base*1.5))[0]
            sizes.append(dict(ui_scale=scale,system_scale=ui_system.interface_scale(),width_px=width,
                              hit_diameter_px=ui_system.ARRANGEMENT_HIT_DIAMETER*ui_system.interface_scale()))
            check(base*.55-2<=width<=base*2+2,'marker size stays inside its zoom limits at UI scale '+str(sizes[-1]))
            check(ui_system.ARRANGEMENT_HIT_DIAMETER*ui_system.interface_scale()>=32*scale*original_system-1e-6,'hit diameter is at least 32 px scaled '+str(scale))
    finally:
        preferences.ui_scale=original_scale
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
        arrangement_controls._batch_cache=None
    evidence['marker_sizes']=sizes
    backgrounds={'viewport background':(.25,.25,.25,1),'dark background':(.05,.06,.07,1)}
    colors=dict(fill=ui_system.ARRANGEMENT_FILL,mirrored=ui_system.ARRANGEMENT_MIRRORED,attached=ui_system.ARRANGEMENT_ATTACHED)
    ratios={name:{key:contrast(color,background) for key,color in colors.items()} for name,background in backgrounds.items()}
    evidence['contrast']=ratios
    check(all(min(value.values())>=3 for value in ratios.values()),'every point color keeps 3:1 contrast on viewport and dark fixtures '+str(ratios))
    check_zoom(check,area,region,view,avatar,evidence)
    check_surface_alignment(check,area,region,view,evidence)
    check_occlusion(check,area,region,view,evidence)
    check_points_only(check,area,region,view,evidence)
    point=named_point(area,region,view,'chest','front')
    identity=(point['volume'],point['point'])
    patterns={}
    interaction=arrangement_controls._interaction
    session=Session();session.add([(-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1)])
    pattern=session.document.patterns[0]
    attached_color=None
    for state in ('IDLE','HOVER','PRESSED','ATTACHED'):
        interaction.state='IDLE' if state=='ATTACHED' else state
        interaction.point=None if state in {'IDLE','ATTACHED'} else identity
        pattern.arrangement=arrangement_record(*identity,version=3) if state=='ATTACHED' else None
        scene.dd_document=session.document.dumps()
        live_panels.sync(bpy.context)
        panel=next(item for item in garment.generated(scene,'panel'))
        for obj in bpy.context.view_layer.objects:obj.select_set(False)
        bpy.context.view_layer.objects.active=panel
        raster=render(area,region,view)
        x,y=(int(round(value)) for value in point['screen'])
        window=raster[y-14:y+15,x-14:x+15]
        if state=='ATTACHED':attached_color=raster[y,x,:3].tolist()
        else:patterns[state]=window[:,:,0]*.2126+window[:,:,1]*.7152+window[:,:,2]*.0722
    arrangement_controls.end_interaction()
    pattern.arrangement=None
    scene.dd_document=session.document.dumps()
    live_panels.sync(bpy.context)
    differences={first+'/'+second:float(np.abs(patterns[first]-patterns[second]).mean())
                 for index,first in enumerate(patterns) for second in list(patterns)[index+1:]}
    evidence['grayscale_state_differences']=differences
    check(all(value>.01 for value in differences.values()),'idle, hover and pressed markers differ in grayscale '+str(differences))
    expected=list(ui_system.ARRANGEMENT_ATTACHED[:3])
    evidence['attached_color']=attached_color
    check(math.dist(attached_color,expected)<.12,'a point with a piece on it renders in the attached color '+str((attached_color,expected)))
    view.view_distance=40;view.update()
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        crowded=arrangement_controls.projected_points(bpy.context)
        targets=[point for point in crowded if point['visible'] and point['facing']]
        unique=[point for point in targets if all(other is point or math.dist(point['screen'],other['screen'])>.5 for other in targets)]
        correct=sum(1 for point in unique if (lambda hit:(hit['volume'],hit['point'])==(point['volume'],point['point']))(arrangement_controls.hit_point(bpy.context,point['screen'])))
    evidence['picking']=dict(crowded_points=len(crowded),unique_targets=len(unique),correct=correct)
    check(unique and correct==len(unique),'crowded picking returns the exact identity for every visible front-facing target')
    view.view_distance=4;view.update()


def reference_workload_ms(panel):
    import time
    from mathutils.bvhtree import BVHTree
    positions=[vertex.co.copy() for vertex in panel.data.vertices]
    polygons=[tuple(polygon.vertices) for polygon in panel.data.polygons]
    started=time.perf_counter()
    tree=BVHTree.FromPolygons(positions,polygons)
    nearest=np.array([tuple(tree.find_nearest(position)[0]) for position in positions])
    np.linalg.norm(nearest-nearest.mean(axis=0),axis=1).sum()
    return (time.perf_counter()-started)*1000


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
    timings=[];references=[]
    with bpy.context.temp_override(area=area,region=region,region_data=view):
        setup=arrangement.ensure_volumes(bpy.context)
        targets=[(volume['id'],point['id']) for volume in setup['volumes'] if volume['id'] in ('chest','waist','hip') for point in volume['points']]
        for volume,point in targets:
            references.append(reference_workload_ms(panel))
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
    ratios=sorted(timing/reference for timing,reference in zip(timings,references))
    evidence['preview']=dict(vertices=vertices,samples=len(timings),p50_ms=ordered[len(ordered)//2],
                             p95_ms=ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))],maximum_ms=ordered[-1],
                             reference_p50_ms=sorted(references)[len(references)//2],ratio_p50=ratios[len(ratios)//2],
                             ratio_budget=PREVIEW_REFERENCE_RATIO,ceiling_ms=PREVIEW_CEILING_MS,
                             preview_commit_max_mm=agreement*1000)
    check(vertices>=4500,'preview latency is measured on a panel near 5,000 vertices '+str(vertices))
    check(agreement<.001,'preview and committed vertices agree within 1 mm '+str(agreement*1000))
    check(evidence['preview']['ratio_p50']<=PREVIEW_REFERENCE_RATIO,'cold preview median stays within its calibrated reference budget '+str(evidence['preview']))
    check(evidence['preview']['p95_ms']<PREVIEW_CEILING_MS,'cold preview p95 stays below the 150 ms interaction ceiling '+str(evidence['preview']))


def run():
    passed=[]
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
                check([{key:value for key,value in point.items() if key!='slot'} for point in arrangement_controls.display_world_points(bpy.context)]==arrangement.world_points(bpy.context),'cached points exactly match unchanged arrangement math')
            width,height=region.width,region.height
            view.view_distance=7;view.update()
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
            with bpy.context.temp_override(area=area,region=region,region_data=view):
                for point in arrangement_controls.projected_points(bpy.context):
                    expected=view3d_utils.location_3d_to_region_2d(region,view,Vector(point['position']))
                    check(math.dist(point['screen'],expected)<1e-3,'hit projection follows the resolved point '+point['volume']+' '+point['point'])
                active=SimpleNamespace(_area=area,_scene=None,canvas_layout=SimpleNamespace(panel=Rect(width*.45,0,width*.3,height)))
                with patch.object(editor,'_active',active):
                    panel=active.canvas_layout.panel
                    check(not any(panel.contains(*point['screen']) for point in arrangement_controls.projected_points(bpy.context)),'the open 2D panel excludes points beneath it')
            with patch.object(arrangement_controls,'batch_for_shader',wraps=arrangement_controls.batch_for_shader) as batch:
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                batch.reset_mock()
                for index in range(5):
                    view.view_rotation=Quaternion((0,0,1),index*.1) @ Quaternion((1,0,0),1.3);view.update()
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                check(batch.call_count==0,'orbit changes uniforms without rebuilding GPU batches')
            scene.dd_reference_visible=False
            with patch.object(arrangement_controls,'display_world_points',side_effect=AssertionError('hidden display resolved geometry')):
                with bpy.context.temp_override(area=area,region=region,region_data=view):
                    arrangement_controls.draw_points()
                    check(not arrangement_controls.projected_points(bpy.context),'H off skips all geometry and hit detection')
            scene.dd_reference_visible=True
            evidence={}
            check_states(check,area,region,view,scene,avatar,evidence)
            check_preview(check,area,region,view,scene,evidence)
            (ROOT/'scratch'/'issue76-display-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        (ROOT/'scratch'/'arrangement_display-report.json').write_text(json.dumps(dict(passed=passed)),encoding='utf-8')
    except Exception:
        (ROOT/'scratch'/'arrangement_display-report.json').write_text(json.dumps(dict(passed=passed,error=traceback.format_exc())),encoding='utf-8')
        traceback.print_exc()
    return None


bpy.app.timers.register(run,first_interval=2)
