from pathlib import Path
from types import SimpleNamespace
import json,traceback
import bpy
from mathutils import Vector
from bpy_extras import view3d_utils
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT))
bpy.context.preferences.view.show_splash=False
import devil_designer
from devil_designer import editor,garment
from devil_designer.core import Document
from devil_designer.controls import TABS,Inspector


def run():
    passed=[]
    def check(ok,message):
        if not ok:raise AssertionError(message)
        passed.append(message)
        print('PASS:',message,flush=True)
    try:
        devil_designer.register()
        scene=bpy.context.scene
        scene.dd_library_dir=str(ROOT/'scratch'/'gui-library')
        scene.dd_spacing=.04
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=(0,0,1.2))
        body=bpy.context.object;body.name='Authoring test body';body.scale=(.18,.13,.4)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        scene.dd_avatar=body
        for obj in scene.objects:
            if obj.name in {'Cube','Camera','Light'}:obj.hide_set(True)
        scene.dd_ui_rect=(600,80,950,760)
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');area.spaces.active.show_region_ui=False
        region=next(r for r in area.regions if r.type=='WINDOW')
        area.spaces.active.region_3d.view_rotation=Vector((0,-1,0)).to_track_quat('Z','Y')
        area.spaces.active.region_3d.view_location=Vector((.65,0,1.2));area.spaces.active.region_3d.view_distance=2.8
        bpy.context.view_layer.update()
        with bpy.context.temp_override(area=area,region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT');op=editor._active
            op.minimal_ui = False
            scene.dd_reference_visible = True
            op.full = False
            op.advanced_tools = True
            op.canvas_layout = op.make_layout()
            def event(kind,value='PRESS',point=None,**extra):
                c=op.canvas_layout.canvas;x,y=point or (c.x+c.w/2,c.y+c.h/2)
                data=dict(type=kind,value=value,mouse_x=x+region.x,mouse_y=y+region.y,shift=False,ctrl=False,alt=False)
                data.update(extra);return SimpleNamespace(**data)
            def click_at(point,**extra):
                op.handle_event(bpy.context,event('LEFTMOUSE',point=point,**extra))
                op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=point,**extra))
            def click_rect(r):click_at((r.x+r.w/2,r.y+r.h/2))
            def control(key):
                if op.inspector is None:
                    op.open_section('DESIGN')
                op.inspector_details.update(('DESIGN', 'SEW', 'AVATAR', 'CLOTH', 'LIBRARY'))
                op.refresh_controls()
                if not any(c.key==key for c in op.inspector.controls):
                    for tab in TABS:
                        if any(c.key==key for c in Inspector(op.inspector.rect,op.canvas_layout.scale,0,op.session.document.seams,tab).controls):
                            op.open_section(tab);break
                for _ in range(120):
                    item=next(c for c in op.inspector.controls if c.key==key);r=op.inspector.content
                    y=item.rect.y+item.rect.h/2
                    if r.y+8<y<r.y+r.h-8:return item
                    op.handle_event(bpy.context,event('WHEELDOWNMOUSE' if y<r.y+8 else 'WHEELUPMOUSE',point=(r.x+r.w/2,r.y+r.h/2)))
                raise AssertionError('Control unreachable: '+key)
            def action(key):click_rect(control(key).rect)
            def world(point,**extra):click_at(op.view.screen(point,op.canvas_layout.canvas),**extra)
            scene.dd_width=.3;scene.dd_height=.4
            action('NUM_RECT');check(len(op.session.document.patterns)==1,'numeric rectangle creates centimetre-sized pattern')
            rectangle=op.session.selected
            op.fit();op.choose_tool('SELECT')
            world((0,0),shift=True);world((.3,0),shift=True)
            action('MERGE');check(len(op.session.document.find(rectangle).vertices)==3,'Shift point selection and Merge work')
            op.handle_event(bpy.context,event('Z',ctrl=True));check(len(op.session.document.find(rectangle).vertices)==4,'merge has transactional undo')
            op.choose_tool('SELECT');world((.3,.4));op.handle_event(bpy.context,event('C'))
            p=op.session.document.find(rectangle);check(p.vertices[2].outgoing is not None,'corner converts to editable Bezier point')
            v=p.vertices[2];handle=(v.x+v.outgoing[0],v.y+v.outgoing[1]);start=op.view.screen(handle,op.canvas_layout.canvas)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=start));op.handle_event(bpy.context,event('MOUSEMOVE',point=(start[0]+10,start[1]+5)))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=(start[0]+10,start[1]+5)))
            check(op.handle_preview is None and not op.gesture,'Bezier handle drag commits without stale previews')
            edge=op.session.document.edge(rectangle,2);mid=op.session.document.edge_point(edge,.5)
            op.choose_tool('SELECT');world(mid)
            scene.dd_segment_length=op.session.document.edge_length(op.session.segment)*1.02
            action('SET_LENGTH');check(abs(op.session.document.edge_length(op.session.segment)-scene.dd_segment_length)<.0001,'custom exact segment length action works')
            before=len(op.session.document.find(rectangle).vertices);op.handle_event(bpy.context,event('Q'))
            check(len(op.session.document.find(rectangle).vertices)==before+1,'Q splits a curved segment')
            op.choose_tool('ELLIPSE');a=op.view.screen((.5,.05),op.canvas_layout.canvas);b=op.view.screen((.8,.35),op.canvas_layout.canvas)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=a));op.handle_event(bpy.context,event('MOUSEMOVE',point=b));op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=b))
            ellipse=op.session.selected;check(len(op.session.document.find(ellipse).vertices)==4,'ellipse tool creates four Bezier anchors')
            op.session.selected=rectangle;op.session.path='OUTER';scene.dd_internal_mode=True
            scene.dd_point_x=.1;scene.dd_point_y=.14;scene.dd_width=.07;scene.dd_height=.08
            action('NUM_ELLIPSE');hole=op.session.path;action('CUT')
            check(op.session.document.find(rectangle).path(hole).role=='HOLE','internal ellipse cuts a real hole')
            action('TRACE');check(len(op.session.document.patterns)==3,'trace creates an independent pattern')
            scene.dd_internal_mode=False;op.session.selected=rectangle;op.session.path='OUTER';op.choose_tool('INTERNAL')
            world((.04,.05));world((.08,.1));op.handle_event(bpy.context,event('RET'));action('CUT')
            check(op.session.document.find(rectangle).path(op.session.path).role=='SLIT','internal polyline can become a slit')
            op.session.selected=ellipse;op.session.path='OUTER';op.fit();op.choose_tool('DART')
            edge=op.session.document.edge(ellipse,0)
            world(op.session.document.edge_point(edge,.25));world(op.session.document.edge_point(edge,.65));world((.65,.2))
            check(any(f.get('type')=='DART' for f in op.session.document.find(ellipse).features),'three-click dart adds automatic same-piece sewing')
            op.session.selected=rectangle;op.session.path='OUTER';op.session.segment=op.session.document.edge(rectangle,0)
            action('MIRROR_SEW');check(len(op.session.document.patterns)==4,'mirror with seam produces a paired reflected pattern')
            op.session.selected=rectangle;op.session.segment=op.session.document.edge(rectangle,0);action('UNFOLD')
            check(len(op.session.document.patterns)==4,'seamless Unfold replaces the source outline')
            scene.dd_offset=.005;action('OFFSET');check(len(op.session.document.patterns)==5,'outline offset produces a new editable piece')
            op.session.add([(1.3,0),(1.6,0),(1.6,.4),(1.3,.4)]);square_a=op.session.selected
            op.session.add([(1.9,0),(2.3,0),(2.3,.3),(1.9,.3)]);square_b=op.session.selected
            op.persist();op.fit()
            old=len(op.session.document.seams);action('CHAIN_A')
            for i in (0,1):world(op.session.document.edge_point(op.session.document.edge(square_a,i),.5))
            op.handle_event(bpy.context,event('RET'));world(op.session.document.edge_point(op.session.document.edge(square_b,0),.5));op.handle_event(bpy.context,event('RET'))
            check(len(op.session.document.seams)==old+1,'custom M:N chain sewing creates a pair')
            check('warning' in op.message.lower(),'unequal chain lengths show a nonblocking warning')
            click_rect(control('dd_free_sewing').rect)
            for owner,i,t in [(square_a,2,.2),(square_a,2,.8),(square_b,2,.1),(square_b,2,.9)]:
                world(op.session.document.edge_point(op.session.document.edge(owner,i),t))
            check(len(op.session.document.seams)==old+2,'four-click free sewing stores partial ranges')
            op.choose_tool('PIN');world((1.45,.2));check(len(op.session.document.anchors)==1,'pin tool creates a fabric anchor')
            op.choose_tool('TACK');world((1.56,.32));check(op.pending_tack is not None,'tack tool waits for an avatar target')
            area.spaces.active.region_3d.update()
            target=view3d_utils.location_3d_to_region_2d(region,area.spaces.active.region_3d,Vector((0,-.13,1.2)))
            if target is not None and op.canvas_layout.panel.contains(*target):
                area.spaces.active.region_3d.view_location.x+=.7
                area.spaces.active.region_3d.update()
                target=view3d_utils.location_3d_to_region_2d(region,area.spaces.active.region_3d,Vector((0,-.13,1.2)))
            check(target is not None and not op.canvas_layout.panel.contains(*target),'avatar target is visible outside floating editor')
            click_at(tuple(target));check(len(op.session.document.anchors)==2 and op.pending_tack is None,'tack ray-picks the chosen avatar')
            op.session.selected=square_a
            op.session.document.find(square_a).placement_mode='LEGACY';op.persist()
            action('PLACE');click_at(tuple(target))
            panels=garment.generated(scene,'panel');check(any(o.get('dd_pattern_id')==square_a for o in panels),'click placement generates and places selected panel')
            op.session.selected=square_a;scene.dd_wrap_radius=.1;before_points=op.session.document.find(square_a).points;action('WRAP')
            panel=next(o for o in garment.generated(scene,'panel') if o['dd_pattern_id']==square_a)
            check(max(v.co.z for v in panel.data.vertices)>.01 and op.session.document.find(square_a).points==before_points,'wrap bends 3D fabric while preserving flat source')
            old_preset=op.session.document.find(square_a).preset;action('PRESET')
            check(op.session.document.find(square_a).preset!=old_preset,'per-pattern preset changes in the custom Cloth tab')
            click_rect(control('dd_library_name').value_rect)
            for char in 'UI outfit':op.handle_event(bpy.context,event('TEXT',unicode=char))
            op.handle_event(bpy.context,event('RET'));action('LIBRARY_SAVE')
            if op.confirm_action == 'LIBRARY_SAVE':
                click_rect(op.make_layout().buttons['CANCEL_ACTION'][0])
                check(op.confirm_action is None,'library overwrite can be cancelled')
                action('LIBRARY_SAVE')
                click_rect(op.make_layout().buttons['CONFIRM_ACTION'][0])
            check(bool(op.library_items),'custom library saves the editable design')
            original=op.session.document.find(square_a).points[0]
            body.scale*=1.2;bpy.context.view_layer.update();action('LIBRARY_LOAD')
            check(op.confirm_action == 'LIBRARY_LOAD', 'loading over a garment requires explicit confirmation')
            selected_piece = op.session.selected
            op.handle_event(bpy.context,event('X'))
            check(op.session.selected == selected_piece and op.session.document.find(selected_piece) is not None,
                  'confirmation blocks unrelated destructive shortcuts')
            click_rect(op.make_layout().buttons['CANCEL_ACTION'][0])
            check(op.session.document.find(square_a).points[0] == original,'cancelled library load preserves the garment')
            action('LIBRARY_LOAD')
            click_rect(op.make_layout().buttons['CONFIRM_ACTION'][0])
            check(abs(op.session.document.find(square_a).points[0][0]-original[0]*1.2)<1e-4,'custom library loads and scales design for another body size')
            op.session.selected=rectangle;op.session.path='OUTER';op.inspector_tab='DESIGN';op.inspector_scroll=0
            op.refresh_controls();op.fit();op.save_window()
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'scratch'/'devil-designer-0.5-preview.blend'))
        def after_draw():
            try:
                check(editor._active is not None and not op._closed,'all advanced curves and holes draw without GPU callback failure')
                (ROOT/'scratch'/'design-gui-report.json').write_text(json.dumps({'passed':passed},indent=2))
            except Exception:
                (ROOT/'scratch'/'design-gui-report.json').write_text(json.dumps({'passed':passed,'error':traceback.format_exc()},indent=2))
            return None
        bpy.app.timers.register(after_draw,first_interval=1)
        (ROOT/'scratch'/'design-gui-report.json').write_text(json.dumps({'passed':passed},indent=2))
    except Exception:
        (ROOT/'scratch'/'design-gui-report.json').write_text(json.dumps({'passed':passed,'error':traceback.format_exc()},indent=2))
        traceback.print_exc()
    return None

(ROOT/'scratch').mkdir(exist_ok=True)
bpy.app.timers.register(run,first_interval=2)
