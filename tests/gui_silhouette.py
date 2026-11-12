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
            check(scene.dd_reference_visible and scene.dd_points_visible,'opening the editor shows both the silhouette and the arrangement points')
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
            before=scene.dd_document
            op.pointer=op.view.screen((scene.dd_reference_x,scene.dd_reference_y+.2),op.canvas_layout.canvas)
            check(op.hit()==(None,None),'body reference cannot be selected as a pattern')
            click(op.canvas_layout.buttons['TOGGLE_GUIDE'][0])
            check(not scene.dd_reference_visible,'dock Guide toggle hides body silhouette')
            op.handle_event(bpy.context,event('H'))
            check(scene.dd_reference_visible,'H restores body silhouette')
            op.handle_event(bpy.context,event('H'))
            check(not scene.dd_reference_visible and scene.dd_points_visible,'H hides the silhouette and leaves the arrangement points shown')
            op.handle_event(bpy.context,event('H'))
            op.show_card('BODY',None)
            labels=[row[1] for row in op.card_rows('BODY')[1] if row[0]=='CHOICES']
            check({'Silhouette','Arrangement points'}<=set(labels),'the Body menu has separate Silhouette and Arrangement points toggles: '+str(labels))
            op.renderer.draw(op)
            check(not op.error_message,'the Body menu with both toggles draws without a render error: '+str(op.error_message))
            op.minimal_action('INSP_POINTS_Hidden')
            check(not scene.dd_points_visible and scene.dd_reference_visible,'the Body menu hides the arrangement points and leaves the silhouette shown')
            op.minimal_action('INSP_SILHOUETTE_Hidden')
            check(not scene.dd_reference_visible and not scene.dd_points_visible,'the Body menu hides the silhouette on its own toggle')
            op.minimal_action('INSP_POINTS_Shown')
            check(scene.dd_points_visible and not scene.dd_reference_visible,'the Body menu shows the arrangement points while the silhouette stays hidden')
            op.minimal_action('INSP_SILHOUETTE_Shown')
            check(scene.dd_reference_visible and scene.dd_points_visible,'the Body menu shows the silhouette again')
            from devil_designer import ui_system
            check(ui_system.ARRANGEMENT_FILL==ui_system.ACCENT,'arrangement points use the accent color')
            tint=ui_system.SILHOUETTE_TINT
            check(max(tint)-min(tint)<.06,'the silhouette tint is a neutral grey, not a hue shared with the points')
            op.card_kind=None
            for choice,value in (('Light',.15),('Strong',.50),('Medium',.30)):
                op.minimal_action('INSP_OPACITY_'+choice)
                check(abs(scene.dd_reference_opacity-value)<1e-5,'guide opacity chip '+choice.lower())
            check(scene.dd_document==before,'reference controls do not modify pattern data')
            op.fit()
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
