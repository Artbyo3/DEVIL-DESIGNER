import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import body_guard, garment, starters, tack_binding, xpbd, xpbd_live, xpbd_nodes
from devil_designer.core import Anchor, Session


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def points(simulation):
    return xpbd_live.evaluated_points(bpy.context, simulation)


def run_frames(scene, count):
    for frame in range(scene.frame_current + 1, scene.frame_current + count + 1):
        scene.frame_set(frame)


def fresh(scene):
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'final') + garment.generated(scene, 'panel'))
    scene.frame_set(scene.frame_start)


def seam_gap(simulation):
    coordinates = points(simulation)
    return max(math.dist(coordinates[first], coordinates[second]) for first, second in json.loads(simulation['dd_sewing_pairs']))


def stretch(simulation):
    coordinates = points(simulation)
    rest = simulation.data.attributes['rest_length'].data
    ratios = sorted(math.dist(coordinates[edge.vertices[0]], coordinates[edge.vertices[1]]) / rest[edge.index].value
                    for edge in simulation.data.edges if not edge.is_loose and rest[edge.index].value > 1e-6)
    return ratios[int(len(ratios) * .99)]


def open_body():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=.3, location=(0, 0, 1))
    body = bpy.context.object
    mesh = body.data
    cut = [polygon.index for polygon in mesh.polygons if polygon.center.z < -.15]
    import bmesh
    edit = bmesh.new()
    edit.from_mesh(mesh)
    edit.faces.ensure_lookup_table()
    bmesh.ops.delete(edit, geom=[edit.faces[index] for index in cut], context='FACES')
    edit.to_mesh(mesh)
    edit.free()
    return body


def panel_over(scene, width, height):
    session = Session()
    session.add([(-width, 0), (width, 0), (width, 2 * width), (-width, 2 * width)])
    session.document.patterns[0].placement_mode = 'LEGACY'
    scene.dd_document = session.document.dumps()
    panel = garment.build_panels(bpy.context)[0]
    panel.location = (0, 0, height)
    panel.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    return panel


def test_groups_and_modifier(scene):
    simulation = garment.compile_garment(bpy.context)
    modifier = simulation.modifiers['DD XPBD']
    check(modifier.type == 'NODES' and modifier.node_group.name == xpbd_nodes.CLOTH_GROUP, 'garment compiles to the GN XPBD modifier')
    check(not simulation.use_simulation_cache, 'simulation runs in realtime mode with no frame cache')
    check({'dd_seam', 'rest_length', 'mass', 'dd_bend_rest', 'dd_partner'} <= set(simulation.data.attributes.keys()), 'compile writes solver attributes')
    kinds = {obj.name.split('.')[0] for obj in garment.generated(scene, 'collider')}
    check({'DD Collision Body', 'DD Collision Shell'} <= kinds, 'collision body and watertight shell are baked')
    return simulation


def test_open_avatar_collision(scene):
    fresh(scene)
    scene.dd_avatar = open_body()
    panel_over(scene, .35, 1.34)
    simulation = garment.compile_garment(bpy.context)
    run_frames(scene, 70)
    highest = float(points(simulation)[:, 2].max())
    check(highest > 1.2, 'cloth rests on an open, non-watertight body')
    bpy.data.objects.remove(scene.dd_avatar, do_unlink=True)


def test_pins_and_tacks(scene, body):
    fresh(scene)
    scene.dd_avatar = body
    session = Session()
    session.add([(-.2, 0), (.2, 0), (.2, .4), (-.2, .4)])
    pattern = session.document.patterns[0]
    pattern.placement_mode = 'LEGACY'
    nearest = body_guard.surface_tree(bpy.context, body).ray_cast(Vector((0, -1, 1.2)), Vector((0, 1, 0)))[0]
    surface = tuple(nearest)
    binding = tack_binding.bind_target(bpy.context, body, surface)
    session.document.anchors.append(Anchor(pattern.id, 0, .2, 'TACK', surface, binding=binding))
    session.document.anchors.append(Anchor(pattern.id, .12, .2, 'PIN'))
    scene.dd_document = session.document.dumps()
    panel = garment.build_panels(bpy.context)[0]
    panel.location = (0, nearest.y - .12, 1.0)
    panel.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.view_layer.update()
    simulation = garment.compile_garment(bpy.context)
    held = [item.value for item in simulation.data.attributes['dd_pinned'].data]
    tacked = [item.value for item in simulation.data.attributes['dd_tacked'].data]
    start = [vertex.co.copy() for vertex in simulation.data.vertices]
    check(sum(tacked) == 1 and sum(held) == 2, 'one tack and one pin reach the solver')
    run_frames(scene, 60)
    coordinates = points(simulation)
    tack = tacked.index(True)
    pin = next(index for index, value in enumerate(held) if value and not tacked[index])
    check(math.dist(coordinates[pin], start[pin]) < 1e-5, 'pin holds its position exactly')
    check(math.dist(coordinates[tack], surface) < .005, 'tack glues the cloth to the body surface')
    moving = max(math.dist(coordinates[index], start[index]) for index in range(len(start)) if not held[index])
    check(moving > .03, 'cloth around pins and tacks keeps simulating')


def test_live_grab(scene):
    simulation = garment.generated(scene, 'simulation')[0]
    run_frames(scene, 40)
    coordinates = points(simulation)
    index = max(range(len(coordinates)), key=lambda item: -coordinates[item][1] - abs(coordinates[item][2] - 1.2))
    start = Vector(coordinates[index].tolist())
    grab = xpbd_live.ClothGrab(simulation)
    grab.radius = .9
    grab.scale_radius(2)
    check(abs(grab.radius - xpbd_live.RADIUS_RANGE[1]) < 1e-9, 'grab radius is limited to its range')
    grab.radius = .05
    grab.begin(bpy.context, index, start, Vector((0, -1, 0)), Vector((0, 1, 0)))
    check(grab.held and xpbd.input_slot(simulation, 'Grab Index').value == index, 'grab reaches the solver')
    target = start + Vector((.06, 0, .06))
    grab.drag(target + Vector((0, -2, 0)), Vector((0, 1, 0)))
    run_frames(scene, 25)
    moved = Vector(points(simulation)[index].tolist())
    check((moved - start).length > .03, 'pulled cloth follows the hand')
    grab.release()
    check(not grab.held and xpbd.input_slot(simulation, 'Grab Index').value == -1, 'release hands the cloth back to the solver')
    run_frames(scene, 20)
    check(all(math.isfinite(value) for value in points(simulation).ravel()), 'cloth keeps simulating after release')
    grab = xpbd_live.ClothGrab(simulation)
    grab.toggle_mode()
    check(grab.mode == xpbd_live.PUSH, 'mode toggles to Push')
    press = Vector(points(simulation)[index].tolist())
    grab.begin(bpy.context, index, press, Vector((0, -1, 0)), Vector((0, 1, 0)))
    grab.drag(press + Vector((.05, -2, 0)), Vector((0, 1, 0)))
    handle = xpbd.input_slot(simulation, 'Grab Handle').value.location
    check(handle.y > press.y + .03, 'Push moves the hand into the cloth along its surface normal')
    grab.release()


def test_keep_refine_and_guard(scene, body):
    simulation = garment.generated(scene, 'simulation')[0]
    live_steps = xpbd.input_slot(simulation, 'Inner Substeps').value
    check(live_steps == xpbd.LIVE_SUBSTEPS, 'live handling runs at realtime substeps')
    run_frames(scene, 60)
    live_stretch = stretch(simulation)
    xpbd.refine(bpy.context, simulation)
    refined_stretch = stretch(simulation)
    print('STRETCH', round(live_stretch, 4), round(refined_stretch, 4), flush=True)
    check(refined_stretch < live_stretch, 'Keep refine reduces stretch')
    check(xpbd.input_slot(simulation, 'Inner Substeps').value == live_steps, 'refine restores live substeps')
    original = [vertex.co.copy() for vertex in body.data.vertices]
    for vertex in body.data.vertices:
        vertex.co += vertex.normal * .03
    body.data.update()
    bpy.context.view_layer.update()
    try:
        garment.keep_drape(bpy.context)
        raise AssertionError('Keep accepted cloth inside the true body')
    except ValueError as failure:
        check('inside' in str(failure), 'Keep refuses cloth deep inside the true body')
    check(not garment.generated(scene, 'final'), 'a refused Keep leaves no mesh behind')
    for vertex, point in zip(body.data.vertices, original):
        vertex.co = point
    body.data.update()
    bpy.context.view_layer.update()
    result, open_pairs = garment.keep_drape(bpy.context)
    check(open_pairs == 0, 'Keep welds every seam pair')
    names = set(result.data.attributes.keys())
    check(not {'rest_length', 'mass', 'velocity', 'dd_seam', 'dd_pinned'} & names, 'simulation attributes never reach the kept mesh')
    tree = body_guard.surface_tree(bpy.context, body)
    inside = body_guard.clear_surface(tree, [Vector(vertex.co) for vertex in result.data.vertices], 0, 0)
    check(not inside, 'kept mesh is clear of the true body')


def test_keep_with_faceless_seam_vertices(scene):
    fresh(scene)
    bpy.ops.devil_designer.simulate()
    simulation = garment.generated(scene, 'simulation')[0]
    mesh = simulation.data
    count = len(mesh.vertices)
    mesh.vertices.add(2)
    mesh.vertices[count].co = mesh.vertices[count + 1].co = mesh.vertices[0].co
    edge = len(mesh.edges)
    mesh.edges.add(1)
    mesh.edges[edge].vertices = (count, count + 1)
    simulation['dd_sewing_pairs'] = json.dumps(json.loads(simulation['dd_sewing_pairs']) + [[count, count + 1]])
    mesh.update()
    simulation.update_tag()
    run_frames(scene, 45)
    result, _ = garment.keep_drape(bpy.context)
    check(len(result.data.polygons) > 0, 'Keep finishes when a sewn pair has no cloth faces')


def test_stiff_fabric_links():
    side = 5
    rest = np.array([(x * .02, y * .02, 0) for y in range(side) for x in range(side)], dtype=float)
    edges = np.array([(y * side + x, y * side + x + 1) for y in range(side) for x in range(side - 1)] +
                     [(y * side + x, (y + 1) * side + x) for y in range(side - 1) for x in range(side)])
    links = xpbd.bend_links(rest, edges, np.ones(len(rest), dtype=bool))
    lengths = np.linalg.norm(rest[links[:, 0]] - rest[links[:, 1]], axis=1)
    check(len(links) > 0 and np.allclose(lengths, .04), 'stiff fabric links span two straight cloth edges')
    check(not len(xpbd.bend_links(rest, edges, np.zeros(len(rest), dtype=bool))), 'soft fabrics get no extra links')


def test_fell_off_guard(scene, body):
    try:
        body_guard.check(bpy.context, [body], np.array([(0, 0, -30.0), (0, 0, -30.5)]), 1)
        raise AssertionError('Keep accepted a garment far below the body')
    except ValueError as failure:
        check('fell off' in str(failure), 'Keep refuses a garment that fell past the feet')


def test_paired_panels_stay_on_their_side(scene, body):
    fresh(scene)
    scene.dd_avatar = body
    wide = dict(waist=70.0, hip=150.0, height=170.0, waist_y=1.2)
    scene.dd_document = starters.create_skirt_starter(wide, 'COTTON').dumps()
    front, back = garment.build_panels(bpy.context)
    center = sum((body.matrix_world @ Vector(corner) for corner in body.bound_box), Vector()) / 8
    front_side = [(front.matrix_world @ vertex.co - center).y for vertex in front.data.vertices]
    back_side = [(back.matrix_world @ vertex.co - center).y for vertex in back.data.vertices]
    print('PANEL SIDES', round(max(front_side), 3), round(min(back_side), 3), flush=True)
    check(max(front_side) < .03 and min(back_side) > -.03, 'wide paired panels stop at the body side instead of crossing')


def test_reset_restores_timeline(scene):
    end = scene.frame_end
    garment.reset(bpy.context)
    bpy.ops.devil_designer.simulate()
    check(scene.frame_end > end, 'Simulate opens an endless timeline')
    garment.reset(bpy.context)
    check(scene.frame_end == end, 'Reset restores the artist timeline')
    check(not garment.generated(scene, 'collider') and not garment.generated(scene, 'simulation'), 'Reset clears generated simulation objects')


devil_designer.register()
scene = bpy.context.scene
scene.dd_spacing = .025
scene.render.fps = 30
scene.frame_set(scene.frame_start)
check('FINISHED' in bpy.ops.devil_designer.demo(), 'demo garment created')
body = scene.dd_avatar
document = scene.dd_document
test_groups_and_modifier(scene)
run_frames(scene, 60)
check(seam_gap(garment.generated(scene, 'simulation')[0]) < .03, 'sewn seams close on the body')
test_live_grab(scene)
test_keep_refine_and_guard(scene, body)
test_keep_with_faceless_seam_vertices(scene)
test_stiff_fabric_links()
test_fell_off_guard(scene, body)
test_reset_restores_timeline(scene)
test_open_avatar_collision(scene)
test_paired_panels_stay_on_their_side(scene, body)
test_pins_and_tacks(scene, body)
devil_designer.unregister()
print('ALL XPBD CHECKS PASSED', flush=True)
