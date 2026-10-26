from pathlib import Path
from types import SimpleNamespace
import json
import math
import sys
import traceback
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT))
bpy.context.preferences.view.show_splash=False
import devil_designer
from devil_designer.core import Session
from devil_designer import editor


def mannequin():
    vertices,faces=[],[]
    def ellipsoid(center,scale,rotation=None):
        start=len(vertices)
        segments,rings=20,12
        for row in range(rings+1):
            latitude=math.pi*row/rings
            for col in range(segments):
                longitude=math.tau*col/segments
                p=Vector((math.sin(latitude)*math.cos(longitude)*scale[0],
                          math.sin(latitude)*math.sin(longitude)*scale[1],math.cos(latitude)*scale[2]))
                vertices.append(tuple((rotation @ p if rotation else p)+Vector(center)))
        for row in range(rings):
            for col in range(segments):
                a=start+row*segments+col
                b=start+row*segments+(col+1)%segments
                faces.append((a,b,b+segments,a+segments))
    def limb(a,b,radius):
        delta=Vector(b)-Vector(a)
        ellipsoid((Vector(a)+Vector(b))/2,(radius,radius,delta.length/2+radius),delta.to_track_quat('Z','Y'))
    ellipsoid((0,0,1.23),(.205,.115,.29))
    ellipsoid((0,0,.94),(.175,.12,.17))
    ellipsoid((0,0,1.49),(.055,.055,.09))
    ellipsoid((0,0,1.68),(.095,.09,.135))
    for sign in (-1,1):
        limb((sign*.18,0,1.40),(sign*.36,0,1.15),.065)
        limb((sign*.36,0,1.15),(sign*.49,0,.96),.05)
        ellipsoid((sign*.52,-.005,.90),(.045,.032,.075))
        limb((sign*.09,0,.88),(sign*.13,0,.52),.08)
        limb((sign*.13,0,.52),(sign*.15,0,.16),.055)
        ellipsoid((sign*.15,-.055,.09),(.065,.13,.06))
    mesh=bpy.data.meshes.new('Procedural reference mannequin')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    obj=bpy.data.objects.new('Reference mannequin (procedural)',mesh)
    bpy.context.scene.collection.objects.link(obj)
    for poly in mesh.polygons: poly.use_smooth=True
    return obj


def run():
    checks=[]
    def check(ok,message):
        if not ok: raise AssertionError(message)
        checks.append(message)
    try:
        devil_designer.register()
        scene=bpy.context.scene
        body=mannequin()
        for obj in scene.objects:
            if obj.name in {'Cube','Camera','Light'}: obj.hide_set(True)
        scene.dd_avatar=body
        scene.dd_ui_rect=(535,80,1000,760)
        s=Session()
        points=[(-.22,0),(.22,0),(.22,.32),(.19,.45),(.1,.49),(.08,.43),(-.08,.43),(-.1,.49),(-.19,.45),(-.22,.32)]
        s.add(points)
        s.document.patterns[-1].name='Bodice front'
        s.add([(x+.64,y) for x,y in points])
        s.document.patterns[-1].name='Bodice back'
        scene.dd_document=s.document.dumps()
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
        area.spaces.active.show_region_ui=False
        region=next(r for r in area.regions if r.type=='WINDOW')
        bpy.context.view_layer.update()
        with bpy.context.temp_override(area=area,region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            op=editor._active
            op.minimal_ui = False
            scene.dd_reference_visible = True
            op.full = False
            op.advanced_tools = True
            op.canvas_layout = op.make_layout()
            check(op is not None and bool(op.reference.vertices),'actual avatar silhouette is available on open')
            check(len(op.reference.triangles)>1000,'reference uses actual mesh surface triangles')
            expected=body.dimensions.z
            check(abs(op.reference.bounds[1][1]-expected)<1e-4,'reference height matches the body in metres')
            def event(kind,value='PRESS',point=None,**kw):
                c=op.canvas_layout.canvas
                x,y=point or (c.x+c.w/2,c.y+c.h/2)
                data=dict(type=kind,value=value,mouse_x=x+region.x,mouse_y=y+region.y,ctrl=False,alt=False,shift=False)
                data.update(kw)
                return SimpleNamespace(**data)
            def click(r):
                point=(r.x+r.w/2,r.y+r.h/2)
                op.handle_event(bpy.context,event('LEFTMOUSE',point=point))
                op.handle_event(bpy.context,event('LEFTMOUSE','RELEASE',point=point))
            def control(key):
                if op.inspector is None:
                    op.open_section('AVATAR')
                op.inspector_details.update(('DESIGN', 'SEW', 'AVATAR', 'CLOTH', 'LIBRARY'))
                op.refresh_controls()
                if not any(c.key==key for c in op.inspector.controls):
                    from devil_designer.controls import TABS,Inspector
                    for tab in TABS:
                        if any(c.key==key for c in Inspector(op.inspector.rect,op.canvas_layout.scale,0,op.session.document.seams,tab).controls):
                            op.open_section(tab);break
                for _ in range(100):
                    item=next(c for c in op.inspector.controls if c.key==key)
                    y=item.rect.y+item.rect.h/2
                    r=op.inspector.content
                    if r.y+5<y<r.y+r.h-5: return item
                    op.handle_event(bpy.context,event('WHEELDOWNMOUSE' if y<r.y else 'WHEELUPMOUSE',point=(r.x+r.w/2,r.y+r.h/2)))
                raise AssertionError('Control not visible: '+key)
            before=scene.dd_document
            op.pointer=op.view.screen((scene.dd_reference_x,scene.dd_reference_y+.2),op.canvas_layout.canvas)
            check(op.hit()==(None,None),'body reference cannot be selected as a pattern')
            click(op.canvas_layout.buttons['REFERENCE'][0])
            check(not scene.dd_reference_visible,'toolbar hides body silhouette')
            op.handle_event(bpy.context,event('H'))
            check(scene.dd_reference_visible,'H restores body silhouette')
            for target in ('BACK','LEFT','RIGHT','FRONT'):
                click(control('REFERENCE_VIEW').rect)
                check(scene.dd_reference_view==target,'custom reference view '+target.lower())
            click(control('dd_reference_opacity').value_rect)
            for char in '30': op.handle_event(bpy.context,event('ZERO',unicode=char))
            op.handle_event(bpy.context,event('RET'))
            check(abs(scene.dd_reference_opacity-.3)<1e-5,'opacity editable inside custom UI')
            click(control('dd_reference_x').plus)
            check(scene.dd_reference_x>0,'reference position adjustable without moving pattern pieces')
            click(control('REFERENCE_ALIGN').rect)
            check(abs(scene.dd_reference_x)<1e-5,'align action uses the first pattern torso position')
            click(control('REFERENCE_FRAME').rect)
            check(all(op.canvas_layout.canvas.contains(*op.view.screen(p,op.canvas_layout.canvas)) for p in op.reference_corners()),
                  'Frame body fits full silhouette')
            revision=op.reference.revision
            click(control('REFERENCE_REFRESH').rect)
            check(op.reference.revision>revision,'Refresh body updates cached evaluated geometry')
            check(scene.dd_document==before,'reference controls do not modify pattern data')
            op.fit()
            op.inspector_scroll=0
            op.inspector_tab='AVATAR'
            op.refresh_controls()
            op.save_window()
            area.spaces.active.region_3d.view_rotation=Vector((.3,-4,1)).to_track_quat('Z','Y')
            area.spaces.active.region_3d.view_location=Vector((1.25,0,.95))
            area.spaces.active.region_3d.view_distance=3.8
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'scratch'/'body-reference-preview.blend'))
        def verify_draw():
            check(editor._active is not None and not op._closed,'reference GPU draw callback stays active')
            check(op.renderer.reference_batch is not None,'reference GPU batch was built and drawn')
            (ROOT/'scratch'/'silhouette-gui-report.json').write_text(json.dumps({'passed':checks},indent=2))
            return None
        bpy.app.timers.register(verify_draw,first_interval=1)
        (ROOT/'scratch'/'silhouette-gui-report.json').write_text(json.dumps({'passed':checks},indent=2))
    except Exception:
        (ROOT/'scratch'/'silhouette-gui-report.json').write_text(json.dumps({'passed':checks,'error':traceback.format_exc()},indent=2))
        traceback.print_exc()
    return None

(ROOT/'scratch').mkdir(exist_ok=True)
bpy.app.timers.register(run,first_interval=2)
