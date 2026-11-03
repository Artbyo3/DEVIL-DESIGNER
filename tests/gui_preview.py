from pathlib import Path
from types import SimpleNamespace
import json
import sys
import traceback
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT))
bpy.context.preferences.view.show_splash = False
import devil_designer
from devil_designer.core import Session
from devil_designer import editor

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
            def click_rect(rect):
                point=(rect.x+rect.w/2,rect.y+rect.h/2)
                op.handle_event(bpy.context,event('LEFTMOUSE',point=point))
                op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=point))
            check(not hasattr(bpy.types,'DD_PT_patterns'),'no N-panel registered')
            from devil_designer import ui
            check(bool(ui.KEYMAPS) and ui.KEYMAPS[0][1].ctrl and ui.KEYMAPS[0][1].alt,'Ctrl Alt D launcher registered')
            check(op.canvas_layout.rail.w > 0 and 'SELECT' in op.canvas_layout.buttons and op.canvas_layout.canvas.w >= op.canvas_layout.panel.w - 16,
                  'minimal workspace opens with its dock and a full-width canvas')
            check(not {'SETTINGS', 'SEARCH', 'MORE_TOOLS', 'FULL', 'HELP', 'INSPECTOR'} & set(op.canvas_layout.buttons),
                  'no superseded inspector, search or expand controls exist')
            op.choose_tool('POLYGON')
            op.draft = [(0, 0), (.2, 0)]
            op.canvas_layout = op.make_layout()
            op.handle_event(bpy.context,event('J'))
            check(len(op.draft) == 2,'direct tool switches preserve unfinished drafts')
            op.handle_event(bpy.context,event('D',ctrl=True,alt=True))
            check(editor._active is op and len(op.draft) == 2,'close shortcut preserves unfinished drafts')
            op.handle_event(bpy.context,event('Q'))
            check(len(op.draft) == 2,'geometry shortcuts preserve unfinished drafts')
            op.canvas_layout = op.make_layout()
            check('CANCEL_DRAFT' in op.canvas_layout.buttons,'pending draft shows a visible Cancel action')
            click_rect(op.canvas_layout.buttons['CANCEL_DRAFT'][0])
            check(not op.draft and not op.session.document.patterns,'visible cancellation preserves committed garment data')
            c=op.canvas_layout.canvas
            a,b=(c.x+c.w/2-120,c.y+c.h/2-80),(c.x+c.w/2-20,c.y+c.h/2+70)
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
            start=(c.x+c.w/2+40,c.y+c.h/2-60)
            for pt in [start,(start[0]+90,start[1]),(start[0]+50,start[1]+90)]:
                op.handle_event(bpy.context,event('LEFTMOUSE',point=pt))
            check(len(op.draft)==3,'polygon draft input')
            op.handle_event(bpy.context,event('ESC'))
            check(not op.draft and not op._closed,'Escape cancels draft without closing editor')
            for pt in [start,(start[0]+90,start[1]),(start[0]+50,start[1]+90)]:
                op.handle_event(bpy.context,event('LEFTMOUSE',point=pt))
            op.handle_event(bpy.context,event('RET'))
            check(len(op.session.document.patterns)==2,'polygon completion commits')
            op.choose_tool('SELECT')
            selected = op.session.document.patterns[-1]
            old_corner = selected.points[0]
            corner = op.view.screen(old_corner,c)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=corner))
            op.handle_event(bpy.context,event('MOUSEMOVE',point=(corner[0]-20,corner[1]-20)))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=(corner[0]-20,corner[1]-20)))
            check(op.session.document.patterns[-1].points[0]!=old_corner,'corner drag completes')
            op.cleanup()
            check(editor._active is None and op._handle is None and op._timer is None,'draw handler and timer cleanup')
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            op=editor._active
            check(op is not None and len(op.session.document.patterns)==2,'editor reopens with the saved garment')
            op.handle_event(bpy.context,event('D',ctrl=True,alt=True))
            check(editor._active is None,'Ctrl Alt D closes the editor')
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            op=editor._active
            check(op is not None,'launcher reopens after shortcut toggle')
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
            check(op.canvas_layout.panel.w<=region.width,'workspace stays inside the viewport')
        (ROOT/'scratch'/'gui-report.json').write_text(json.dumps({'passed':report},indent=2))
        print('GUI CHECKS:',report)
    except Exception:
        (ROOT/'scratch'/'gui-report.json').write_text(json.dumps({'passed':report,'error':traceback.format_exc()},indent=2))
        traceback.print_exc()
    return None

(ROOT/'scratch').mkdir(exist_ok=True)
bpy.app.timers.register(run,first_interval=2.0)
