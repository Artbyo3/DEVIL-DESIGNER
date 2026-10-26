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
            op.minimal_ui = False
            op.full = False
            op.canvas_layout = op.make_layout()
            op.refresh_controls()
            def event(kind,value='PRESS',point=None,**kw):
                c=op.canvas_layout.canvas
                x,y=point or (c.x+c.w/2,c.y+c.h/2)
                values=dict(type=kind,value=value,mouse_x=x+region.x,mouse_y=y+region.y,
                            ctrl=False,shift=False,alt=False)
                values.update(kw)
                return SimpleNamespace(**values)
            check(not hasattr(bpy.types,'DD_PT_patterns'),'no N-panel registered')
            from devil_designer import ui
            check(bool(ui.KEYMAPS) and ui.KEYMAPS[0][1].ctrl and ui.KEYMAPS[0][1].alt,'Ctrl Alt D launcher registered')
            def click_rect(rect):
                point=(rect.x+rect.w/2,rect.y+rect.h/2)
                op.handle_event(bpy.context,event('LEFTMOUSE',point=point))
                op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=point))
            click_rect(op.canvas_layout.buttons['RECTANGLE'][0])
            check(op.tool == 'RECTANGLE' and not op.session.document.patterns,
                  'drawing tools are directly available without creating hidden geometry')
            op.choose_tool('POLYGON')
            op.draft = [(0, 0), (.2, 0)]
            op.handle_event(bpy.context,event('J'))
            check(op.tool == 'POLYGON' and len(op.draft) == 2,
                  'direct tool switches preserve unfinished drafts')
            op.handle_event(bpy.context,event('D',ctrl=True,alt=True))
            check(editor._active is op and len(op.draft) == 2,
                  'close shortcut preserves unfinished drafts')
            op.handle_event(bpy.context,event('Q'))
            check(len(op.draft) == 2,'geometry shortcuts preserve unfinished drafts')
            click_rect(op.canvas_layout.buttons['CANCEL_DRAFT'][0])
            check(not op.draft and not op.session.document.patterns,
                  'visible cancellation preserves committed garment data')
            click_rect(op.canvas_layout.buttons['MORE_TOOLS'][0])
            check(op.advanced_tools,'advanced tools expand only when requested')
            original=op.canvas_layout.panel
            header=(original.x+60,op.canvas_layout.header.y+25)
            destination=(header[0]-120,header[1]-20)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=header))
            op.handle_event(bpy.context,event('MOUSEMOVE',point=destination))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=destination))
            moved=op.canvas_layout.panel
            check(abs(moved.x-original.x+120)<.01 and abs(moved.y-original.y+20)<.01,'header drag repositions window')
            check(not op.session.document.patterns,'moving window does not draw pattern points')
            start=(moved.x+moved.w-5,moved.y+5)
            target=(start[0]-60,start[1]+40)
            op.handle_event(bpy.context,event('LEFTMOUSE',point=start))
            op.handle_event(bpy.context,event('MOUSEMOVE',point=target))
            op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=target))
            resized=op.canvas_layout.panel
            check(abs(resized.w-moved.w+60)<.01 and abs(resized.h-moved.h+40)<.01,'corner drag resizes window')
            op.handle_event(bpy.context,event('TAB'))
            check(op.full,'expand mode')
            op.handle_event(bpy.context,event('TAB'))
            check(not op.full and abs(op.canvas_layout.panel.x-resized.x)<.01,'restore preserves floating position')
            def control(key):
                if op.inspector is None:
                    op.open_section('DESIGN')
                op.inspector_details.update(('DESIGN', 'SEW', 'AVATAR', 'CLOTH', 'LIBRARY'))
                op.refresh_controls()
                if not any(c.key==key for c in op.inspector.controls):
                    from devil_designer.controls import TABS,Inspector
                    for tab in TABS:
                        if any(c.key==key for c in Inspector(op.inspector.rect,op.canvas_layout.scale,0,op.session.document.seams,tab).controls):
                            op.open_section(tab);break
                for _ in range(100):
                    item=next(c for c in op.inspector.controls if c.key==key)
                    center=(item.rect.x+item.rect.w/2,item.rect.y+item.rect.h/2)
                    r=op.inspector.content
                    if r.y+5<center[1]<r.y+r.h-5:
                        return item
                    kind='WHEELDOWNMOUSE' if center[1]<r.y+5 else 'WHEELUPMOUSE'
                    op.handle_event(bpy.context,event(kind,point=(r.x+r.w/2,r.y+r.h/2)))
                raise AssertionError('Control not reachable: '+key)
            original_stage = op.stage
            op.handle_event(bpy.context,event('F',ctrl=True))
            for character in 'sew two edges':
                op.handle_event(bpy.context,event('TEXT',unicode=character))
            op.handle_event(bpy.context,event('RET'))
            sewing_action = next(item for item in op.inspector.controls if item.key == 'SEW')
            click_rect(sewing_action.rect)
            check(op.tool == 'SEW' and op.stage == original_stage,
                  'search result invokes Sew directly without stage navigation')
            op.handle_event(bpy.context,event('F',ctrl=True))
            for character in 'quality':
                op.handle_event(bpy.context,event('TEXT',unicode=character))
            check(op.search_query == 'quality' and op.stage == original_stage,
                  'search receives text without firing tool shortcuts or changing workspace')
            op.handle_event(bpy.context,event('RET'))
            click_rect(control('dd_quality').value_rect)
            op.handle_event(bpy.context,event('ONE',unicode='1'))
            op.handle_event(bpy.context,event('FOUR',unicode='4'))
            op.handle_event(bpy.context,event('RET'))
            check(bpy.context.scene.dd_quality==14,'custom numeric field edits quality')
            click_rect(control('dd_quality').value_rect)
            for _ in range(3): op.handle_event(bpy.context,event('NINE',unicode='9'))
            op.handle_event(bpy.context,event('RET'))
            check(bpy.context.scene.dd_quality==14 and op.numeric is not None,'invalid numeric value does not change setting')
            op.handle_event(bpy.context,event('ESC'))
            check(op.numeric is None and not op._closed,'Escape cancels numeric edit without closing editor')
            item=control('dd_self_collision')
            previous=bpy.context.scene.dd_self_collision
            click_rect(item.rect)
            check(bpy.context.scene.dd_self_collision!=previous,'custom self-collision toggle')
            click_rect(control('dd_self_collision').rect)
            click_rect(control('BODY').value_rect)
            check(op.body_menu is not None,'body picker opens inside floating editor')
            body_row=next(r for r,obj,_ in op.body_menu.rows if obj and obj.name=='Cube')
            click_rect(body_row)
            check(bpy.context.scene.dd_avatar.name=='Cube','body selected through custom picker')
            click_rect(control('BODY').value_rect)
            clear=next(r for r,obj,_ in op.body_menu.rows if obj is None)
            click_rect(clear)
            check(bpy.context.scene.dd_avatar is None,'custom picker clears body selection')
            for key in ('dd_spacing','dd_clearance','dd_quality','dd_frames','dd_weld_distance','dd_thickness'):
                control(key)
            check(True,'all garment numeric settings reachable inside editor')
            op.close_context()
            op.inspector_scroll=0
            op.refresh_controls()
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
            op.minimal_ui = False
            op.full = False
            op.canvas_layout = op.make_layout()
            op.refresh_controls()
            check(op is not None,'editor reopens')
            check(abs(op.canvas_layout.panel.x-resized.x)<.01 and abs(op.canvas_layout.panel.w-resized.w)<.01,'floating geometry persists after reopen')
            op.handle_event(bpy.context,event('D',ctrl=True,alt=True))
            check(editor._active is None,'Ctrl Alt D closes the floating editor')
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            op=editor._active
            op.minimal_ui = False
            op.full = False
            op.canvas_layout = op.make_layout()
            op.refresh_controls()
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
            seam=op.session.document.seams[0]
            previous=seam.reverse
            row=control(seam.id).rect
            from devil_designer.canvas import Rect
            click_rect(Rect(row.x+row.w-65,row.y+5,38,28))
            check(op.session.document.seams[0].reverse!=previous,'custom seam list reverses direction')
            row=control(seam.id).rect
            click_rect(Rect(row.x+row.w-23,row.y+5,23,28))
            check(not op.session.document.seams,'custom seam list removes a pair')
            op.session=Session()
            op.persist()
            bpy.context.scene.dd_spacing=.025
            bpy.context.scene.dd_quality=10
            click_rect(control('DEMO').rect)
            check(len(op.session.document.patterns)==2,'sewing demo created from custom UI')
            op.session=Session(garment.document(bpy.context.scene))
            op._stored=bpy.context.scene.dd_document
            op.fit()
            op.advanced_tools = True
            op.canvas_layout = op.make_layout()
            op.choose_tool('SEW')
            for obj in bpy.context.scene.objects:
                if obj.name in {'Cube','Camera','Light'}:
                    obj.hide_set(True)
            original_stage = op.stage
            click_rect(op.canvas_layout.buttons['SEW'][0])
            check(op.tool == 'SEW' and op.stage == original_stage,
                  'direct sewing does not require stage navigation')
            click_rect(op.canvas_layout.buttons['FREE_SEW'][0])
            check(op._scene.dd_free_sewing, 'range sewing is directly accessible')
            op.free_clicks = [('pending',)]
            click_rect(op.canvas_layout.buttons['SEW'][0])
            check(not op._scene.dd_free_sewing, 'basic Sew resets free sewing mode')
            check(not op.free_clicks,'basic Sew clears incompatible range picks')
            op.chain_stage = 'A'
            op.chain_a = [('pending',)]
            click_rect(op.canvas_layout.buttons['FREE_SEW'][0])
            check(op.chain_stage is None and not op.chain_a,'free Sew clears incompatible chain picks')
            click_rect(op.canvas_layout.buttons['SEW'][0])
            op.open_section('CLOTH')
            check(op.stage == original_stage, 'inspector sections do not change workspace state')
            op.toggle_full()
            document_before = op.session.document.dumps()
            click_rect(op.canvas_layout.buttons['VIEW_3D'][0])
            check(not op.full and op.canvas_layout.panel.w <= op.canvas_layout.available.w * .5,
                  'Show 3D restores a narrow floating workspace')
            check(op.session.document.dumps() == document_before,
                  'revealing the viewport preserves garment data')
            click_rect(op.canvas_layout.buttons['SIMULATE'][0])
            check(bpy.context.screen.is_animation_playing,'custom Simulate starts playback')
            op.draft = [(0, 0), (.1, .1)]
            op.canvas_layout = op.make_layout()
            click_rect(op.canvas_layout.buttons['STOP'][0])
            check(not bpy.context.screen.is_animation_playing and len(op.draft) == 2,
                  'Pause remains available without discarding unfinished drawing')
            op.perform_action('CANCEL_DRAFT')
            op.canvas_layout = op.make_layout()
            click_rect(op.canvas_layout.buttons['SIMULATE'][0])
            click_rect(op.canvas_layout.buttons['SIMULATE'][0])
            check(not bpy.context.screen.is_animation_playing,'custom Stop pauses playback')
            document_before_reset = op.session.document.dumps()
            click_rect(op.canvas_layout.buttons['RESET'][0])
            check(op.confirm_action == 'RESET','reset requires an explicit discard decision')
            op.handle_event(bpy.context,event('ESC'))
            check(op.confirm_action is None and op.session.document.dumps() == document_before_reset,
                  'Escape cancels reset without altering garment data')
            obj=garment.generated(bpy.context.scene,'simulation')[0]
            for frame in range(1,61):
                bpy.context.scene.frame_set(frame)
                obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices[0].co
            click_rect(op.canvas_layout.buttons['KEEP'][0])
            result=garment.generated(bpy.context.scene,'final')[0]
            check(result is not None,'custom Keep mesh retains draped garment')
            check(result.data.uv_layers.active is not None,'draped preview has UVs')
            from mathutils import Vector
            area.spaces.active.region_3d.view_rotation=Vector((.8,-4,1.4)).to_track_quat('Z','Y')
            area.spaces.active.region_3d.view_location=Vector((.85,0,1.25))
            area.spaces.active.region_3d.view_distance=2.1
            check(op.canvas_layout.panel.w<region.width,'side-by-side layout leaves scene visible')
            op.inspector_scroll=0
            op.inspector_tab='AVATAR'
            op.refresh_controls()
            op.save_window()
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'build'/'floating-editor-preview.blend'))
        (ROOT/'build'/'gui-report.json').write_text(json.dumps({'passed':report},indent=2))
        print('GUI CHECKS:',report)
    except Exception:
        (ROOT/'build'/'gui-report.json').write_text(json.dumps({'passed':report,'error':traceback.format_exc()},indent=2))
        traceback.print_exc()
    return None

(ROOT/'build').mkdir(exist_ok=True)
bpy.app.timers.register(run,first_interval=2.0)
