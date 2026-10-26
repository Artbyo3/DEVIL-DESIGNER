"""Integration and actual draping test. Run with --background --factory-startup."""
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import garment
from devil_designer.core import Document, Session, area
from devil_designer.meshing import edge_counts, fabric_mesh

checks = []
def check(condition,message):
    if not condition:
        raise AssertionError(message)
    checks.append(message)
    print('PASS:',message,flush=True)

devil_designer.register()
scene = bpy.context.scene
scene.dd_spacing = .02
scene.dd_quality = 8
check('FINISHED' in bpy.ops.devil_designer.demo(),'two-piece demo operator')
doc = garment.document(scene)
check(len(doc.patterns)==2 and len(doc.seams)==4,'bodice has side and shoulder seams')
counts = edge_counts(doc,scene.dd_spacing)
for pattern in doc.patterns:
    coords,faces,boundaries = fabric_mesh(doc,pattern,scene.dd_spacing,counts)
    measured = sum(abs(area([coords[i] for i in f])) for f in faces)
    check(abs(measured-abs(area(pattern.points)))<1e-6,'meshing preserves concave outline area')
    check(len(coords)>len(pattern.points)*5,'fabric has interior resolution')
    for i,v in enumerate(pattern.vertices):
        chain = boundaries[v.id]
        check(len(chain)==counts[doc.edge(pattern.id,i)]+1,'boundary chain sample count')
panels = garment.generated(scene,'panel')
check(all(p.data.uv_layers.active for p in panels),'panel UVs exist')
first = panels[0]
first.location.x += .02
context = bpy.context
context.view_layer.update()
pose = first.matrix_world.copy()
s = Session(doc)
s.selected = doc.patterns[0].id
points = list(doc.patterns[0].points)
points[0] = (points[0][0]-.01,points[0][1])
s.move(points)
scene.dd_document = s.document.dumps()
garment.build_panels(context)
check(all(abs(a-b)<1e-6 for row1,row2 in zip(pose,first.matrix_world) for a,b in zip(row1,row2)),
      'rebuilding edited patterns preserves 3D panel transform')
check(len(garment.document(scene).seams)==4,'pattern revision preserves sewing references')
garment.arrange(context)
obj = garment.compile_garment(context)
cloth = next(m for m in obj.modifiers if m.type=='CLOTH')
pairs = json.loads(obj['dd_sewing_pairs'])
check(bool(pairs) and cloth.settings.use_sewing_springs,'sewing springs compiled')
check(any(m.type=='COLLISION' for m in scene.dd_avatar.modifiers),'avatar collision added')
check(all(p.hide_get() for p in garment.generated(scene,'panel')),'source panels hidden during simulation')
initial = sum((obj.data.vertices[a].co-obj.data.vertices[b].co).length for a,b in pairs)/len(pairs)
for frame in range(scene.frame_start,scene.frame_start+61):
    scene.frame_set(frame)
    depsgraph = context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    coords = [v.co.copy() for v in evaluated.data.vertices]
    if frame%15==0:
        gap = sum((coords[a]-coords[b]).length for a,b in pairs)/len(pairs)
        print(f'DRAPE frame {frame}: mean seam gap {gap:.5f}, bounds {[tuple(round(fun(v[a] for v in coords),3) for a in range(3)) for fun in (min,max)]}',flush=True)
check(all(math.isfinite(x) for v in coords for x in v),'simulation stays finite')
check(max(v.length for v in coords)<5,'simulation does not explode')
check(min(v.z for v in coords)>.8 and max(v.z for v in coords)>1.4,'garment stays supported by the body without pins')
final = sum((coords[a]-coords[b]).length for a,b in pairs)/len(pairs)
check(final<initial*.5,'real cloth simulation pulls paired seams together')
expected_uvs=sorted(tuple(round(x,6) for x in uv.uv) for uv in obj.data.uv_layers.active.data)
result,unclosed = garment.keep_drape(context)
check(not any(m.type=='CLOTH' for m in result.modifiers),'kept garment is an ordinary editable mesh')
check(result.data.uv_layers.active is not None,'kept mesh preserves pattern UVs')
actual_uvs=sorted(tuple(round(x,6) for x in uv.uv) for uv in result.data.uv_layers.active.data)
check(actual_uvs==expected_uvs,'seam welding preserves every source UV loop')
check(all(v.groups for v in result.data.vertices),'finalized vertex groups contain actual memberships')
used = {i for p in result.data.polygons for i in p.vertices}
check(all(a in used and b in used for edge in result.data.edges for a,b in [edge.vertices]),'kept mesh contains no loose spring vertices')
face_edges = {tuple(sorted((p.vertices[i],p.vertices[(i+1)%len(p.vertices)])))
              for p in result.data.polygons for i in range(len(p.vertices))}
check(all(tuple(sorted(e.vertices)) in face_edges for e in result.data.edges),'kept mesh contains no loose sewing edges')
garment.reset(context)
check(result.name in scene.objects,'reset preserves finished garments')
check(all(not p.hide_get() for p in garment.generated(scene,'panel')),'reset restores arranged panels')
check(not garment.generated(scene,'simulation'),'reset discards old cloth cache object')
expected = scene.dd_document
output = ROOT/'build'/'garment-test.blend'
output.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
bpy.ops.wm.open_mainfile(filepath=str(output))
check(bpy.context.scene.dd_document==expected,'garment document survives save/reopen')
check(len(Document.loads(expected).seams)==4,'seams survive save/reopen')
check(len(garment.generated(bpy.context.scene,'final'))==1,'finished garment survives save/reopen')
report = dict(blender=bpy.app.version_string,checks=checks,initial_seam_gap=initial,
              final_seam_gap=final,unclosed_pairs=unclosed,vertices=len(coords))
(ROOT/'build'/'garment-report.json').write_text(json.dumps(report,indent=2))
devil_designer.unregister()
print('ALL GARMENT CHECKS PASSED',flush=True)
