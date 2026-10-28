import json
import math
import runpy
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer import garment, fit_display
from devil_designer.fit_map import vertex_ratios, surface_edges
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
original_vertices = [tuple(vertex.co) for vertex in obj.data.vertices]
original_edges = [tuple(edge.vertices) for edge in obj.data.edges]
original_faces = [tuple(face.vertices) for face in obj.data.polygons]
original_attributes = [(attribute.name, attribute.domain, attribute.data_type) for attribute in obj.data.attributes]
original_materials = list(obj.data.materials)
original_material_state = [(material.diffuse_color[:], material.node_tree.as_pointer()) for material in obj.data.materials]
original_panel_state = [(panel.data.as_pointer(), [tuple(vertex.co) for vertex in panel.data.vertices],
                         [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data])
                        for panel in garment.generated(scene, 'panel')]
original_mesh_count = len(bpy.data.meshes)
for trial in range(3):
    display_mesh, fit_ratios = fit_display.snapshot(obj, context.evaluated_depsgraph_get(), scene)
    check(display_mesh != obj.data and display_mesh.users == 0, 'fit colors live only on an unlinked temporary mesh')
    check(len(display_mesh.color_attributes['DD Fit Map'].data) == len(coords), 'fit color attribute has one color per simulated vertex')
    check(all(math.isfinite(value) and value >= 0 for value in fit_ratios), 'real drape produces finite fit ratios')
    rest = [tuple(item.vector) for panel in garment.generated(scene, 'panel') for item in panel.data.attributes['dd_rest'].data]
    measured = vertex_ratios(rest, [tuple(point * garment.metres_per_unit(scene)) for point in coords], surface_edges(original_faces))
    check(max(abs(first - second) for first, second in zip(fit_ratios, measured)) < 1e-6, 'fit map uses flat-panel rest distances and excludes loose sewing bridges')
    bpy.data.meshes.remove(display_mesh)
check(len(bpy.data.meshes) == original_mesh_count, 'fit sampling leaves no temporary mesh datablocks')
check([tuple(vertex.co) for vertex in obj.data.vertices] == original_vertices and
      [tuple(edge.vertices) for edge in obj.data.edges] == original_edges and
      [tuple(face.vertices) for face in obj.data.polygons] == original_faces, 'fit map leaves original simulated topology and positions untouched')
check([(attribute.name, attribute.domain, attribute.data_type) for attribute in obj.data.attributes] == original_attributes,
      'fit map adds no attributes to the simulated mesh')
check(list(obj.data.materials) == original_materials and
      [(material.diffuse_color[:], material.node_tree.as_pointer()) for material in obj.data.materials] == original_material_state,
      'fit map leaves simulated materials and shader trees untouched')
check([(panel.data.as_pointer(), [tuple(vertex.co) for vertex in panel.data.vertices],
        [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data])
       for panel in garment.generated(scene, 'panel')] == original_panel_state, 'fit map leaves flat panels and rest coordinates untouched')
previous_spacing = scene.dd_spacing
scene.dd_spacing += .001
try:
    fit_display.snapshot(obj, context.evaluated_depsgraph_get(), scene)
except ValueError:
    check(True, 'fit map rejects changed pattern settings instead of showing stale data')
else:
    raise AssertionError('Fit map accepted changed source settings')
finally:
    scene.dd_spacing = previous_spacing
extra_modifier = obj.modifiers.new('Fit topology refusal test', 'SUBSURF')
try:
    fit_display.snapshot(obj, context.evaluated_depsgraph_get(), scene)
except ValueError:
    check(True, 'fit map rejects evaluated topology changes instead of mismatching vertices')
else:
    raise AssertionError('Fit map accepted changed evaluated topology')
finally:
    obj.modifiers.remove(extra_modifier)
check(len(bpy.data.meshes) == original_mesh_count, 'fit refusal paths release evaluated meshes')
result,unclosed = garment.keep_drape(context)
check('DD Fit Map' not in result.data.color_attributes, 'Keep mesh never inherits the transient fit color attribute')
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
output = ROOT/'scratch'/'garment-test.blend'
output.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
bpy.ops.wm.open_mainfile(filepath=str(output))
check(bpy.context.scene.dd_document==expected,'garment document survives save/reopen')
check(len(Document.loads(expected).seams)==4,'seams survive save/reopen')
check(len(garment.generated(bpy.context.scene,'final'))==1,'finished garment survives save/reopen')
report = dict(blender=bpy.app.version_string,checks=checks,initial_seam_gap=initial,
              final_seam_gap=final,unclosed_pairs=unclosed,vertices=len(coords))
(ROOT/'scratch'/'garment-report.json').write_text(json.dumps(report,indent=2))
runpy.run_path(str(ROOT/'tests'/'blender_seam_shrink.py'))['run'](check)
devil_designer.unregister()
print('ALL GARMENT CHECKS PASSED',flush=True)
