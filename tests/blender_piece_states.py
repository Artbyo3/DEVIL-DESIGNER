import copy
import ast
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import devil_designer
from devil_designer import fit_display, garment, layering, library, piece_states
from devil_designer.core import Document
from devil_designer.presets import PRESETS


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def coordinates(simulation, frame):
    bpy.context.scene.frame_set(frame)
    evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [tuple(vertex.co) for vertex in evaluated.data.vertices]


def layering_checks():
    scene = bpy.context.scene
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'panel') + garment.generated(scene, 'final') + garment.generated(scene, 'demo'))
    scene.dd_document = Document().dumps()
    scene.dd_spacing = .025
    scene.dd_quality = 12
    scene.dd_pin_top = False
    bpy.ops.devil_designer.demo()
    normal = scene.dd_document
    simulation = garment.compile_garment(bpy.context)
    for frame in range(1, 81):
        coordinates(simulation, frame)
    evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pose = [vertex.co.copy() for vertex in evaluated.data.vertices]
    baseline, open_pairs = garment.keep_drape(bpy.context)
    check(open_pairs == 0, 'layering baseline shirt welds every seam')
    baseline.name = 'Normal kept shirt'
    simulation.hide_set(False)
    simulation.hide_render = False
    document = garment.document(scene)
    for pattern in document.patterns:
        pattern.frozen = True
    scene.dd_document = document.dumps()
    frozen = garment.compile_garment(bpy.context)
    check(coordinates(frozen, 1) == [tuple(point) for point in pose], 'whole frozen base receives the exact current pose')
    maximum = 0
    for frame in range(1, 122):
        current = coordinates(frozen, frame)
        displacement = max(math.dist(first, second) for first, second in zip(current, pose))
        maximum = max(maximum, displacement)
    print('FROZEN_BASE_DISPLACEMENT ' + json.dumps(dict(frames=121, maximum_m=maximum)), flush=True)
    check(maximum <= 1e-6, 'all frozen base vertices stay within the predefined 0.001 mm freeze tolerance')
    frozen_base, open_pairs = garment.keep_drape(bpy.context)
    frozen_base.name = 'Frozen kept shirt'
    check(not any(attribute.name.startswith('dd_frozen_') for attribute in frozen_base.data.attributes), 'run-only exact-hold attributes never enter the kept mesh')
    check(open_pairs == 0, 'frozen base retains the original Keep weld behavior')
    geometry_delta = max((first.co - second.co).length for first, second in zip(frozen_base.data.vertices, baseline.data.vertices))
    check(geometry_delta <= 1e-6 and [tuple(face.vertices) for face in frozen_base.data.polygons] == [tuple(face.vertices) for face in baseline.data.polygons], 'Keep retains identical topology and geometry within the predefined freeze tolerance')
    frozen_base['dd_wear_over'] = False
    layering.prepare_colliders(bpy.context)
    bpy.ops.mesh.primitive_cube_add(size=.1, location=(2, 0, 0))
    extra = bpy.context.object
    extra.modifiers.new('Artist collision', 'COLLISION')
    extra.collision.thickness_outer = .009
    namespace = dict(globals(), extra_collider=extra)
    original = (ROOT / 'tests' / 'blender_layering.py').read_text(encoding='utf-8')
    for node in ast.parse(original).body:
        if isinstance(node, ast.FunctionDef):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / 'tests' / 'blender_layering.py'), 'exec'), namespace)
    snapshots = {obj.name: namespace['collision_snapshot'](obj) for obj in (baseline, scene.dd_avatar, extra)}
    document = Document.loads(normal)
    for pattern in document.patterns:
        pattern.name = pattern.name.replace('Bodice', 'Jacket')
    scene.dd_document = document.dumps()
    scene.dd_pin_top = True
    panels = garment.build_panels(bpy.context)
    offset = 0
    for panel in panels:
        inverse = panel.matrix_world.inverted()
        for vertex in panel.data.vertices:
            position = pose[offset + vertex.index]
            vertex.co = inverse @ (position + Vector((position.x, position.y, 0)).normalized() * .03 + Vector((0, 0, .005)))
        offset += len(panel.data.vertices)
    bpy.context.view_layer.update()
    report = dict(frozen_base_max_displacement_m=maximum, kept_geometry_delta_m=geometry_delta)
    for quality in (12, 24):
        scene.dd_quality = quality
        baseline['dd_wear_over'] = True
        frozen_base['dd_wear_over'] = False
        reference = namespace['penetration_trial'](baseline, True)
        baseline['dd_wear_over'] = False
        measured = namespace['penetration_trial'](frozen_base, True)
        check(measured['max_penetration_m'] <= reference['max_penetration_m'] + 1e-6 and measured['max_penetration_m'] <= .002,
              'production frozen-base Wear over is no worse than shipped baseline at quality ' + str(quality))
        report[str(quality)] = dict(baseline=reference, frozen=measured)
    for obj in (baseline, scene.dd_avatar, extra):
        check(namespace['collision_snapshot'](obj) == snapshots[obj.name], 'production states preserve existing collider settings: ' + obj.name)
    (ROOT / 'scratch' / 'piece-states-production-layering.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


devil_designer.register()
scene = bpy.context.scene
scene.dd_spacing = .025
scene.dd_quality = 24
scene.dd_frames = 120
scene.dd_thickness = 0
bpy.ops.devil_designer.demo()
normal_document = scene.dd_document
simulation = garment.compile_garment(bpy.context)
for frame in range(1, 81):
    pose = coordinates(simulation, frame)
normal_pose = pose
source = (ROOT / 'devil_designer' / 'garment.py').read_text(encoding='utf-8')
node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'compile_garment')
baseline_source = ast.get_source_segment(source, node).replace('    from . import piece_states\n    piece_states.update_display(context,doc)\n    if piece_states.required(doc):\n        return piece_states.compile_run(context,doc)\n', '', 1)
namespace = dict(vars(garment))
exec(baseline_source, namespace)
garment.reset(bpy.context)
simulation = namespace['compile_garment'](bpy.context)
for frame in range(1, 81):
    pose = coordinates(simulation, frame)
check(pose == normal_pose, 'all-normal simulated coordinates are bit-identical to the original compiler at frame 80')
panels = garment.generated(scene, 'panel')
source_geometry = [(panel['dd_pattern_id'], [tuple(vertex.co) for vertex in panel.data.vertices], [tuple(row) for row in panel.matrix_world]) for panel in panels]
document = garment.document(scene)
document.patterns[0].frozen = True
scene.dd_document = document.dumps()
simulation = garment.compile_garment(bpy.context)
check(len(bpy.data.scenes) == 1, 'run-only compile leaves no temporary scene')
check(coordinates(simulation, 1) == pose, 'current pose transfers exactly without a panel-coordinate round trip')
indices = piece_states.piece_indices(simulation)
frozen = indices[document.patterns[0].id]
maximum = 0
for frame in range(1, 122):
    current = coordinates(simulation, frame)
    maximum = max(maximum, max(sum((current[index][axis] - pose[index][axis]) ** 2 for axis in range(3)) ** .5 for index in frozen))
check(maximum <= 1e-6, 'frozen vertices stay within 0.001 mm for 121 frames')
check(json.loads(simulation['dd_sewing_pairs']), 'frozen and live pieces retain sewing springs in one mesh')
hold_group = simulation.vertex_groups['DD Pins']
check(all(hold_group.weight(index) == 1 for pair in json.loads(simulation['dd_sewing_pairs']) if any(index in frozen for index in pair) for index in pair), 'both sides of each seam incident to the frozen piece are held')
target = bpy.data.objects.new('Frozen tack test', None)
garment.collection(scene).objects.link(target)
garment.tag(target, 'anchor')
hook = simulation.modifiers.new('Frozen tack test', 'HOOK')
hook.object = target
hook.vertex_indices_set([frozen[0]])
piece_states.apply_states(document, simulation)
check(not any(modifier.type == 'HOOK' for modifier in simulation.modifiers), 'frozen tack hooks cannot animate held vertices')
mesh, ratios = fit_display.snapshot(simulation, bpy.context.evaluated_depsgraph_get(), scene)
check(len(ratios) == len(simulation.data.vertices), 'fit map works with state-aware runs')
bpy.data.meshes.remove(mesh)
check(source_geometry == [(panel['dd_pattern_id'], [tuple(vertex.co) for vertex in panel.data.vertices], [tuple(row) for row in panel.matrix_world]) for panel in panels], 'states never change source panel geometry or placement')
presets = copy.deepcopy(PRESETS)
document = garment.document(scene)
document.patterns[0].frozen = False
document.patterns[0].strengthened = True
scene.dd_document = document.dumps()
simulation = garment.compile_garment(bpy.context)
cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
check(cloth.settings.tension_stiffness == 25 and cloth.settings.tension_stiffness_max == 100, 'Strengthen multiplies Cotton tension by four')
indices = piece_states.piece_indices(simulation)
group = simulation.vertex_groups['DD Structural']
check(all(group.weight(index) == 1 for index in indices[document.patterns[0].id]) and all(group.weight(index) == 0 for index in indices[document.patterns[1].id]), 'shared Cotton preset remains normal on the other piece')
check(PRESETS == presets, 'Strengthen does not mutate any shared preset')
garment.reset(bpy.context)
document.patterns[0].deactivated = True
document.patterns[1].strengthened = True
source = document.dumps()
scene.dd_document = source
inactive_panel = next(panel for panel in garment.generated(scene, 'panel') if panel['dd_pattern_id'] == document.patterns[0].id)
inactive_panel.modifiers.new('Existing panel collision', 'COLLISION')
inactive_panel.collision.thickness_outer = .009
simulation = garment.compile_garment(bpy.context)
check(json.loads(simulation['dd_piece_ids']) == [document.patterns[1].id], 'deactivated piece has no compiled vertices or faces')
check(not json.loads(simulation['dd_sewing_pairs']), 'seams incident to deactivated pieces are inert without errors')
cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
check(inactive_panel not in list(cloth.collision_settings.collection.objects) and abs(inactive_panel.collision.thickness_outer - .009) < 1e-8,
      'deactivation filters an existing collider without changing its Collision settings')
active = piece_states.active_document(document)
plan = garment.boundary_plan(active, scene.dd_spacing)
expected_coords, expected_faces, boundaries = garment.fabric_mesh(active, active.patterns[0], scene.dd_spacing, plan)
check(len(simulation.data.vertices) == len(expected_coords) and [tuple(face.vertices) for face in simulation.data.polygons] == expected_faces, 'active mesh sampling is exactly what the absent-piece document produces')
check(scene.dd_document == source, 'run filtering preserves the complete editable design and sewing')
mesh, ratios = fit_display.snapshot(simulation, bpy.context.evaluated_depsgraph_get(), scene)
check(len(ratios) == len(simulation.data.vertices), 'fit map uses active-only sampling')
bpy.data.meshes.remove(mesh)
scene.dd_library_dir = str(ROOT / 'scratch' / 'piece-state-library')
library.save(bpy.context, 'Piece states')
loaded = Document.loads(json.dumps(json.loads(library.entries(scene)[0].read_text(encoding='utf-8'))['document']))
check([(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in loaded.patterns] == [(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in document.patterns], 'library file retains independent piece states')
loaded = library.load(bpy.context, 0)
check([(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in loaded.patterns] == [(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in document.patterns], 'actual library load preserves per-piece states')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'scratch' / 'piece-states.blend'))
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'scratch' / 'piece-states.blend'))
scene = bpy.context.scene
reopened = garment.document(scene)
check([(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in reopened.patterns] == [(pattern.frozen, pattern.deactivated, pattern.strengthened) for pattern in document.patterns], 'piece states survive Blender save and reopen')
scene.dd_document = normal_document
garment.reset(bpy.context)
simulation = garment.compile_garment(bpy.context)
check(not simulation.get('dd_state_run') and len(json.loads(simulation['dd_piece_ids'])) == 2, 'normal states return to the original compile path')
check(all(panel.display_type == 'TEXTURED' and 'dd_state_display' not in panel for panel in garment.generated(scene, 'panel')), 'reactivation restores each source panel display mode')
check(not any(scene.name.startswith('DD State Compile') for scene in bpy.data.scenes), 'state runs leave no temporary scenes')
layering_checks()
devil_designer.unregister()
print('ALL PIECE STATE CHECKS PASSED', flush=True)
