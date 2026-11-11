import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ARGUMENTS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ROOT = Path(ARGUMENTS[0]).resolve() if ARGUMENTS else Path(__file__).resolve().parents[1]
OUTPUT = Path(ARGUMENTS[1]) if len(ARGUMENTS) > 1 else ROOT / 'scratch' / 'self_collision_bench.json'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import garment, xpbd, xpbd_live
from devil_designer.core import Session

SHEET_HALF = .35
DOME_RADIUS = .6
DOME_HEIGHT = 1.0
DOME_FLATTEN = .3
BODY_SEGMENTS = 256
BODY_RINGS = 140
DRAPE_FRAMES = 60
LIFT_FRAMES = 40
CARRY_FRAMES = 60
PRESS_FRAMES = 40
HOLD_FRAMES = 30
SETTLE_FRAMES = 60
LIFT_CLEARANCE = .15
PRESS_DEPTH = float(ARGUMENTS[2]) if len(ARGUMENTS) > 2 else .05
CORNER = int(ARGUMENTS[3]) if len(ARGUMENTS) > 3 else 0
CORNER_SIGNS = ((1, 1), (-1, 1), (1, -1), (-1, -1))


def dome_body():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=BODY_SEGMENTS, ring_count=BODY_RINGS, radius=DOME_RADIUS, location=(0, 0, DOME_HEIGHT))
    body = bpy.context.object
    body.scale = (1.0, 1.0, DOME_FLATTEN)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    body.data.calc_loop_triangles()
    return body


def sheet(scene):
    session = Session()
    session.add([(-SHEET_HALF, 0), (SHEET_HALF, 0), (SHEET_HALF, 2 * SHEET_HALF), (-SHEET_HALF, 2 * SHEET_HALF)])
    session.document.patterns[0].placement_mode = 'LEGACY'
    scene.dd_document = session.document.dumps()
    panel = garment.build_panels(bpy.context)[0]
    panel.location = (0, -SHEET_HALF, DOME_HEIGHT + DOME_RADIUS * DOME_FLATTEN + .03)
    panel.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()


def triangles(simulation):
    mesh = simulation.data
    mesh.calc_loop_triangles()
    flat = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get('vertices', flat)
    return flat.reshape(-1, 3)


def crossings(simulation, faces):
    coordinates = xpbd_live.evaluated_points(bpy.context, simulation)
    tree = BVHTree.FromPolygons([tuple(row) for row in coordinates.tolist()], faces.tolist(), all_triangles=True)
    pairs = [(first, second) for first, second in tree.overlap(tree)
             if first < second and not set(faces[first]) & set(faces[second])]
    touched = {int(vertex) for pair in pairs for face in pair for vertex in faces[face]}
    return len(pairs), len(touched)


def step(scene, timings=None):
    started = time.perf_counter()
    scene.frame_set(scene.frame_current + 1)
    if timings is not None:
        timings.append((time.perf_counter() - started) * 1000.0)


def travel(scene, handle, start, end, frames, timings, samples, simulation, faces):
    for frame in range(1, frames + 1):
        handle.location = start.lerp(end, frame / frames)
        step(scene, timings)
        samples.append(crossings(simulation, faces)[0])


def main():
    devil_designer.register()
    scene = bpy.context.scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.fps = 30
    scene.dd_spacing = .02
    scene.frame_set(scene.frame_start)
    body = dome_body()
    scene.dd_avatar = body
    sheet(scene)
    simulation = garment.compile_garment(bpy.context)
    faces = triangles(simulation)
    for _ in range(DRAPE_FRAMES):
        step(scene)
    draped = crossings(simulation, faces)
    draped_floor = float(xpbd_live.evaluated_points(bpy.context, simulation)[:, 2].min())
    coordinates = xpbd_live.evaluated_points(bpy.context, simulation)
    signs = CORNER_SIGNS[CORNER]
    corner = int(np.argmin(signs[0] * coordinates[:, 0] + signs[1] * coordinates[:, 1]))
    grab = xpbd_live.ClothGrab(simulation)
    grab.radius = .06
    grab.arm()
    origin = Vector(coordinates[corner].tolist())
    grab.begin(bpy.context, corner, origin, Vector((0, 0, 1)), Vector((0, 0, -1)))
    handle = xpbd.input_slot(simulation, 'Grab Handle').value
    top = float(coordinates[:, 2].max())
    lifted = Vector((origin.x, origin.y, top + LIFT_CLEARANCE))
    above = Vector((0.0, 0.0, top + LIFT_CLEARANCE))
    pressed = Vector((0.0, 0.0, top - PRESS_DEPTH))
    timings = []
    samples = []
    travel(scene, handle, origin, lifted, LIFT_FRAMES, timings, samples, simulation, faces)
    travel(scene, handle, lifted, above, CARRY_FRAMES, timings, samples, simulation, faces)
    travel(scene, handle, above, pressed, PRESS_FRAMES, timings, samples, simulation, faces)
    travel(scene, handle, pressed, pressed, HOLD_FRAMES, timings, samples, simulation, faces)
    held = crossings(simulation, faces)
    grab.release(bpy.context)
    settle = []
    for _ in range(SETTLE_FRAMES):
        step(scene)
        settle.append(crossings(simulation, faces)[0])
    settled = crossings(simulation, faces)
    grab.disarm()
    ordered = sorted(timings)
    result = dict(
        root=str(ROOT), press_depth=PRESS_DEPTH, corner=CORNER, vertices=len(simulation.data.vertices), body_triangles=len(body.data.loop_triangles),
        live_substeps=xpbd.input_slot(simulation, 'Inner Substeps').value,
        draped_pairs=draped[0], draped_floor=draped_floor, peak_pairs_during_grab=max(samples), held_pairs=held[0], held_vertices=held[1],
        settled_pairs=settled[0], settled_vertices=settled[1], mean_pairs_during_grab=float(np.mean(samples)),
        mean_pairs_after_release=float(np.mean(settle)),
        grab_frame_ms_mean=float(np.mean(timings)), grab_frame_ms_median=ordered[len(ordered) // 2],
        grab_frame_ms_p95=ordered[int(len(ordered) * .95)], grab_fps_headless=1000.0 / float(np.mean(timings)),
        min_cloth_height=float(xpbd_live.evaluated_points(bpy.context, simulation)[:, 2].min()))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print('BENCH', json.dumps(result), flush=True)
    devil_designer.unregister()


main()
