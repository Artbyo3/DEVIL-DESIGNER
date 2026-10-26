"""Launch with blender --factory-startup --python tests/gui_preview.py.

Uses a separate factory scene; no user file or preferences are changed.
A timer defers invocation until Blender has a real window event loop.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import traceback
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
bpy.context.preferences.view.show_splash = False
import devil_designer
from devil_designer.core import Session
from devil_designer import editor, garment

def run():
    report = []
    def check(ok,label):
        if not ok:
            raise AssertionError(label)
        report.append(label)
    try:
        devil_designer.register()
        area = next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
        area.spaces.active.show_region_ui = False
        region = next(r for r in area.regions if r.type=='WINDOW')
        with bpy.context.temp_override(area=area,region=region):
            result = bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            check('RUNNING_MODAL' in result,'overlay invokes in Blender 5.2.3')
            op = editor._active
            def event(kind,value='PRESS',point=None,**kw):
                c=op.canvas_layout.canvas
                x,y=point or (c.x+c.w/2,c.y+c.h/2)
                values=dict(type=kind,value=value,mouse_x=x+region.x,mouse_y=y+region.y,
                            ctrl=False,shift=False,alt=False)
                values.update(kw)
                return SimpleNamespace(**values)
            c=op.canvas_layout.canvas
            a,b=(c.x+55,c.y+55),(c.x+155,c.y+205)
            op.handle_event(bpy.context,event('R'))
            op.handle_event(bpy.context,event('LEFTMOUSE',point=a))
            op.handle_event(bpy.context,event('MOUSEMOVE',point=b))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=b))
            check(len(op.session.document.patterns)==1,'rectangle pointer sequence commits')
            op.handle_event(bpy.context,event('Z',ctrl=True))
            check(len(op.session.document.patterns)==0,'overlay undo')
            op.handle_event(bpy.context,event('Z',ctrl=True,shift=True))
            check(len(op.session.document.patterns)==1,'overlay redo')
            op.choose_tool('POLYGON')
            for pt in [a,(a[0]+90,a[1]),(a[0]+50,a[1]+90)]:
                op.handle_event(bpy.context,event('LEFTMOUSE',point=pt))
            check(len(op.draft)==3,'polygon draft input')
            op.handle_event(bpy.context,event('ESC'))
            check(not op.draft and not op._closed,'Escape cancels draft without closing editor')
            # Actual valid polygon creation via Enter.
            for pt in [a,(a[0]+90,a[1]),(a[0]+50,a[1]+90)]:
                op.handle_event(bpy.context,event('LEFTMOUSE',point=pt))
            op.handle_event(bpy.context,event('RET'))
            check(len(op.session.document.patterns)==2,'polygon completion commits')
            op.choose_tool('SELECT')
            selected = op.session.document.patterns[-1]
            old_corner = selected.points[0]
            start = op.view.screen(old_corner,c)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=start))
            op.handle_event(bpy.context,event('MOUSEMOVE',point=(start[0]-20,start[1]-20)))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=(start[0]-20,start[1]-20)))
            check(op.session.document.patterns[-1].points[0]!=old_corner,'corner drag completes')
            op.cleanup()
            check(editor._active is None and op._handle is None and op._timer is None,'draw handler and timer cleanup')
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            op=editor._active
            check(op is not None,'editor reopens')
            # Pair real edges through the overlay input path.
            s=Session()
            s.add([(-.45,-.2),(-.15,-.2),(-.15,.2),(-.45,.2)])
            s.add([(.15,-.2),(.45,-.2),(.45,.2),(.15,.2)])
            op.session=s
            op.persist()
            op.fit()
            op.choose_tool('SEW')
            for point in [(-.15,0),(.15,0)]:
                op.handle_event(bpy.context,event('LEFTMOUSE',point=op.view.screen(point,op.canvas_layout.canvas)))
            check(len(op.session.document.seams)==1,'Sew tool pairs two selected edges')
            op.handle_event(bpy.context,event('B'))
            check(not op.session.document.seams[0].reverse,'B reverses sewing direction')
            op.handle_event(bpy.context,event('X'))
            check(not op.session.document.seams,'X removes selected seam')
            op.handle_event(bpy.context,event('Z',ctrl=True))
            check(len(op.session.document.seams)==1,'undo restores removed seam')
            # Build the same practical sewing demo used by the simulation integration test.
            op.session=Session()
            op.persist()
            bpy.context.scene.dd_spacing=.025
            bpy.ops.devil_designer.demo()
            op.session=Session(garment.document(bpy.context.scene))
            op._stored=bpy.context.scene.dd_document
            op.fit()
            op.choose_tool('SEW')
            for obj in bpy.context.scene.objects:
                if obj.name in {'Cube','Camera','Light'}:
                    obj.hide_set(True)
            obj=garment.compile_garment(bpy.context)
            for frame in range(1,61):
                bpy.context.scene.frame_set(frame)
                obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices[0].co
            result,unclosed=garment.keep_drape(bpy.context)
            check(unclosed==0,'demo drapes with all sewing pairs weldable')
            check(result.data.uv_layers.active is not None,'draped preview has UVs')
            from mathutils import Vector
            area.spaces.active.region_3d.view_rotation=Vector((.8,-4,1.4)).to_track_quat('Z','Y')
            area.spaces.active.region_3d.view_location=Vector((.48,0,1.25))
            area.spaces.active.region_3d.view_distance=2.1
            check(op.canvas_layout.panel.w<region.width,'side-by-side layout leaves scene visible')
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'build'/'devil-designer-preview.blend'))
            # Exercise real GPU drawing in the next window redraw.
        (ROOT/'build'/'gui-report.json').write_text(json.dumps({'passed':report},indent=2))
        print('GUI CHECKS:',report)
    except Exception:
        (ROOT/'build'/'gui-report.json').write_text(json.dumps({'passed':report,'error':traceback.format_exc()},indent=2))
        traceback.print_exc()
    return None

(ROOT/'build').mkdir(exist_ok=True)
bpy.app.timers.register(run,first_interval=2.0)
