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
from devil_designer import garment, starters, xpbd_live
from devil_designer.core import Document, Session


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def run_frames(scene, count):
    for frame in range(scene.frame_current + 1, scene.frame_current + count + 1):
        scene.frame_set(frame)


def fresh(scene):
    garment.forget_drape()
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'final') + garment.generated(scene, 'panel'))
    scene.frame_set(scene.frame_start)


def build_body():
    parts = []
    for radius, depth, location in ((.13, .62, (0, 0, 1.15)), (.075, .85, (.09, 0, .43)), (.075, .85, (-.09, 0, .43)), (.09, .2, (0, 0, 1.58))):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=depth, location=location)
        parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=.175, location=(0, 0, .86))
    bpy.context.object.scale = (1, .8, .75)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=.16, location=(0, 0, 1.32))
    bpy.context.object.scale = (1, .8, .8)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=.05, depth=1.5, location=(0, 0, 1.39), rotation=(0, math.pi / 2, 0))
    parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=.19, location=(0, 0, 1.38))
    bpy.context.object.scale = (1, .6, .35)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(bpy.context.object)
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = 'Matrix body'
    return body


def simulation_points(simulation):
    return xpbd_live.evaluated_points(bpy.context, simulation)


def test_drape_carries_across_an_edit(scene):
    fresh(scene)
    scene.dd_document = starters.create_tank_starter(None, 'COTTON').dumps()
    first = garment.compile_garment(bpy.context)
    flat = np.array([tuple(vertex.co) for vertex in first.data.vertices])
    run_frames(scene, 60)
    draped = simulation_points(first).copy()
    document = Document.loads(scene.dd_document)
    document.patterns[0].preset = 'DENIM'
    document.patterns[0].fabric_override = True
    scene.dd_document = document.dumps()
    garment.build_panels(bpy.context)
    check(not garment.generated(scene, 'simulation'), 'an edit removes the old drape')
    second = garment.compile_garment(bpy.context)
    start = np.array([tuple(vertex.co) for vertex in second.data.vertices])
    shift = float(np.linalg.norm(start - draped, axis=1).mean())
    moved = float(np.linalg.norm(draped - flat, axis=1).mean())
    print('CARRY', round(shift, 5), 'drape moved', round(moved, 5), flush=True)
    check(shift < 1e-3, 'Re-drape starts from the previous drape after a fabric edit')
    run_frames(scene, 20)
    check(np.isfinite(simulation_points(second)).all(), 'Re-drape keeps simulating')
    coarse_count = len(second.data.vertices)
    scene.dd_spacing = .0125
    garment.build_panels(bpy.context)
    finer = garment.compile_garment(bpy.context)
    check(len(finer.data.vertices) > coarse_count, 'a density change rebuilds a denser mesh')
    start = np.array([tuple(vertex.co) for vertex in finer.data.vertices])
    print('FINER height range', round(float(start[:, 2].min()), 3), round(float(start[:, 2].max()), 3), flush=True)
    check(start[:, 1].std() > 1e-3, 'the denser mesh starts draped, not flat')
    scene.dd_spacing = .025


def test_frozen_redrape_carries_drape_and_pins(scene):
    fresh(scene)
    scene.dd_document = starters.create_tee_starter(None, 'COTTON').dumps()
    first = garment.compile_garment(bpy.context)
    run_frames(scene, 60)
    points = simulation_points(first)
    index = int(np.argmin(points[:, 1]))
    grab = xpbd_live.ClothGrab(first)
    grab.radius = .05
    grab.arm()
    grab.begin(bpy.context, index, first.matrix_world @ Vector(points[index].tolist()), Vector((0, -1, 0)), Vector((0, 1, 0)))
    pinned = grab.pin(bpy.context)
    grab.disarm()
    run_frames(scene, 2)
    draped = simulation_points(first).copy()
    document = Document.loads(scene.dd_document)
    document.patterns[-1].frozen = True
    scene.dd_document = document.dumps()
    garment.build_panels(bpy.context)
    second = garment.compile_garment(bpy.context)
    check(second.get('dd_state_run'), 'a frozen piece re-drapes through the piece state path')
    check(pinned > 0 and len(xpbd_live.pinned_vertices(second)) == pinned, 'cloth pins carry through a Re-drape with a frozen piece')
    start = np.array([tuple(vertex.co) for vertex in second.data.vertices])
    shift = float(np.linalg.norm(start - draped, axis=1).mean()) if len(start) == len(draped) else float('inf')
    print('FROZEN CARRY', round(shift, 5), flush=True)
    check(shift < 1e-3, 'a Re-drape with a frozen piece starts from the previous drape')


def test_reopened_file_signature_still_simulates(scene):
    fresh(scene)
    scene.dd_document = starters.create_tank_starter(None, 'COTTON').dumps()
    first = garment.compile_garment(bpy.context)
    run_frames(scene, 30)
    draped = simulation_points(first).copy()
    for panel in garment.generated(scene, 'panel'):
        panel['dd_avatar_frame'] = 'signature from an earlier session'
    document = Document.loads(scene.dd_document)
    document.patterns[0].preset = 'DENIM'
    document.patterns[0].fabric_override = True
    scene.dd_document = document.dumps()
    second = garment.compile_garment(bpy.context)
    check(second is not None and second.name in bpy.data.objects and garment.generated(scene, 'simulation') == [second],
          'Simulate survives panels whose avatar signature is from an earlier session')
    start = np.array([tuple(vertex.co) for vertex in second.data.vertices])
    shift = float(np.linalg.norm(start - draped, axis=1).mean()) if len(start) == len(draped) else float('inf')
    check(shift < 1e-3, 'that Simulate starts from the previous drape')
    run_frames(scene, 10)
    check(np.isfinite(simulation_points(second)).all(), 'that drape keeps simulating')


def test_reset_forgets_the_drape(scene):
    fresh(scene)
    scene.dd_document = starters.create_tank_starter(None, 'COTTON').dumps()
    garment.compile_garment(bpy.context)
    run_frames(scene, 20)
    garment.remember_drape(bpy.context)
    garment.forget_drape()
    garment.reset(bpy.context)
    first = garment.compile_garment(bpy.context)
    panels = garment.generated(scene, 'panel')
    check(len(first.data.vertices) == sum(len(panel.data.vertices) for panel in panels), 'a reset simulation rebuilds from the panels')


def elastic_width(scene, shrink):
    fresh(scene)
    session = Session()
    session.add([(-.2, 0), (.2, 0), (.2, .3), (-.2, .3)])
    piece = session.document.patterns[0]
    piece.placement_mode = 'LEGACY'
    if shrink:
        session.set_elastic(session.document.edge(piece.id, 0), shrink)
    session.selected = piece.id
    session.add_pins([(piece.id, x / 100, .29) for x in range(-18, 19, 4)])
    scene.dd_document = session.document.dumps()
    panel = garment.build_panels(bpy.context)[0]
    panel.location = (1.5, 0, 1.6)
    bpy.context.view_layer.update()
    simulation = garment.compile_garment(bpy.context)
    run_frames(scene, 70)
    points = simulation_points(simulation)
    bottom = points[points[:, 2] < np.percentile(points[:, 2], 8)]
    return float(bottom[:, 0].max() - bottom[:, 0].min())


def test_elastic_narrows_the_edge(scene):
    plain, tight = elastic_width(scene, 0), elastic_width(scene, 30)
    print('ELASTIC', round(plain, 4), round(tight, 4), flush=True)
    check(tight < plain * .92, 'elastic shortens an unsewn edge')


def test_fabric_tack_pulls_points_together(scene):
    fresh(scene)
    session = Session()
    session.add([(-.2, 0), (.2, 0), (.2, .3), (-.2, .3)])
    piece = session.document.patterns[0]
    piece.placement_mode = 'LEGACY'
    session.add_join((piece.id, -.15, .05), (piece.id, .15, .05))
    session.selected = piece.id
    session.add_pins([(piece.id, x / 100, .29) for x in range(-18, 19, 4)])
    scene.dd_document = session.document.dumps()
    panel = garment.build_panels(bpy.context)[0]
    panel.location = (1.5, 0, 1.6)
    bpy.context.view_layer.update()
    simulation = garment.compile_garment(bpy.context)
    run_frames(scene, 70)
    points = simulation_points(simulation)
    first, second = next((edge.vertices[0], edge.vertices[1]) for edge in simulation.data.edges if edge.is_loose)
    gap = math.dist(points[first], points[second])
    print('TACK gap', round(gap, 4), flush=True)
    check(gap < .03, 'a fabric tack closes two distant points')


def steam_span(scene, amount):
    fresh(scene)
    session = Session()
    session.add([(-.2, 0), (.2, 0), (.2, .3), (-.2, .3)])
    piece = session.document.patterns[0]
    piece.placement_mode = 'LEGACY'
    session.selected = piece.id
    session.add_pins([(piece.id, x / 100, .29) for x in range(-18, 19, 4)])
    if amount:
        session.add_steam([dict(pattern=piece.id, x=0.0, y=.02, radius=.3, amount=amount)])
    scene.dd_document = session.document.dumps()
    panel = garment.build_panels(bpy.context)[0]
    panel.location = (1.5, 0, 1.6)
    bpy.context.view_layer.update()
    simulation = garment.compile_garment(bpy.context)
    run_frames(scene, 60)
    points = simulation_points(simulation)
    bottom = points[points[:, 2] < np.percentile(points[:, 2], 8)]
    return float(bottom[:, 0].max() - bottom[:, 0].min()), float(points[:, 1].max() - points[:, 1].min())


def test_steam_gathers_cloth(scene):
    plain, shrunk, puffed = steam_span(scene, 0), steam_span(scene, .25), steam_span(scene, -.25)
    print('STEAM', plain, shrunk, puffed, flush=True)
    check(shrunk[0] < plain[0] * .9, 'steam shrinks the cloth')
    check(puffed[1] > plain[1] + .01, 'negative steam puffs the cloth out')


def test_starters_drape(scene):
    measurements = dict(chest=96.0, waist=78.0, hip=100.0, torso_length=45.0, shoulder_width=30.0, inseam=74.0, height=168.0, waist_y=1.0)
    results = []
    for key, (label, generator, _) in starters.STARTER_GENERATORS.items():
        fresh(scene)
        scene.dd_document = generator(measurements, 'COTTON').dumps()
        simulation = garment.compile_garment(bpy.context)
        run_frames(scene, 90)
        points = simulation_points(simulation)
        pairs = __import__('json').loads(simulation['dd_sewing_pairs'])
        worst = max(math.dist(points[a], points[b]) for a, b in pairs)
        print('STARTER', label, 'vertices', len(points), 'worst seam gap', round(worst, 4), 'height', round(float(points[:, 2].min()), 3), round(float(points[:, 2].max()), 3), flush=True)
        results.append((label, worst, float(points[:, 2].max())))
    for label, worst, top in results:
        if label == 'Skirt':
            continue
        check(worst < .08, label + ' seams close')
        check(top > .8, label + ' stays on the body')


devil_designer.register()
scene = bpy.context.scene
scene.dd_spacing = .025
scene.render.fps = 30
scene.frame_set(scene.frame_start)
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.dd_avatar = build_body()
test_drape_carries_across_an_edit(scene)
test_frozen_redrape_carries_drape_and_pins(scene)
test_reopened_file_signature_still_simulates(scene)
test_reset_forgets_the_drape(scene)
test_elastic_narrows_the_edge(scene)
test_fabric_tack_pulls_points_together(scene)
test_steam_gathers_cloth(scene)
test_starters_drape(scene)
devil_designer.unregister()
