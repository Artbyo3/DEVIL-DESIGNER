import bisect
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import devil_designer
from devil_designer import arrangement, garment, live_panels
from devil_designer.core import Session, arrangement_record
from tools.check_comments import check_source
from tools.workspace import prepare_scratch


def fitted_section(points, center):
    horizontal = max(abs(point[0] - center[0]) for point in points)
    depth = max(abs(point[1] - center[1]) for point in points)
    enclosure = max(math.hypot((point[0] - center[0]) / horizontal,
                               (point[1] - center[1]) / depth) for point in points)
    return horizontal * enclosure, depth * enclosure


def uniform_loop(points, center, count=256):
    ordered = sorted(points, key=lambda point: math.atan2(point[1] - center[1], point[0] - center[0]))
    ordered.append(ordered[0])
    lengths = [0.0]
    for start, end in zip(ordered, ordered[1:]):
        lengths.append(lengths[-1] + math.dist(start, end))
    result = []
    for index in range(count):
        distance = lengths[-1] * index / count
        segment = min(bisect.bisect_right(lengths, distance) - 1, len(ordered) - 2)
        factor = (distance - lengths[segment]) / (lengths[segment + 1] - lengths[segment])
        result.append(tuple(start + factor * (end - start)
                            for start, end in zip(ordered[segment], ordered[segment + 1])))
    return result


def ellipse_gap(point, center, radii):
    horizontal, depth = point[0] - center[0], point[1] - center[1]
    def distance(angle):
        return math.hypot(radii[0] * math.cos(angle) - horizontal,
                          radii[1] * math.sin(angle) - depth)
    step = math.tau / 128
    minimum = min(range(128), key=lambda index: distance(index * step)) * step
    lower, upper = minimum - step, minimum + step
    for iteration in range(60):
        first = lower + (upper - lower) / 3
        second = upper - (upper - lower) / 3
        if distance(first) < distance(second):
            upper = second
        else:
            lower = first
    return distance((lower + upper) / 2)


def intersection_counts(vertices, triangles, body_tree):
    overlaps = body_tree.overlap(BVHTree.FromPolygons(vertices, triangles, all_triangles=True))
    inside = 0
    for point in vertices:
        location, normal, face, distance = body_tree.find_nearest(Vector(point))
        if location is not None and (Vector(point) - location).dot(normal) < -1e-6:
            inside += 1
    return dict(triangle_pairs=len(overlaps), panel_triangles=len({pair[1] for pair in overlaps}),
                inside_vertices=inside, total_vertices=len(vertices))


def wrapped_ellipse(flat_vertices, center, radii, clearance):
    perimeter = []
    lengths = [0.0]
    for index in range(16385):
        angle = index * math.tau / 16384
        radius = 1 / math.hypot(math.sin(angle) / radii[0], math.cos(angle) / radii[1]) + clearance
        perimeter.append((radius * math.sin(angle), -radius * math.cos(angle)))
    for start, end in zip(perimeter, perimeter[1:]):
        lengths.append(lengths[-1] + math.dist(start, end))
    assert max(point[0] for point in flat_vertices) - min(point[0] for point in flat_vertices) < lengths[-1]
    positions = []
    for horizontal, vertical, unused_depth in flat_vertices:
        distance = horizontal % lengths[-1]
        segment = min(bisect.bisect_right(lengths, distance) - 1, len(perimeter) - 2)
        factor = (distance - lengths[segment]) / (lengths[segment + 1] - lengths[segment])
        offset = tuple(start + factor * (end - start)
                       for start, end in zip(perimeter[segment], perimeter[segment + 1]))
        positions.append((center[0] + offset[0], center[1] + offset[1], center[2] + vertical))
    return positions


def angular_ellipse(flat_vertices, center, radii, clearance):
    positions = []
    for horizontal, vertical, unused_depth in flat_vertices:
        angle = horizontal / (radii[1] + clearance)
        radius = 1 / math.hypot(math.sin(angle) / radii[0], math.cos(angle) / radii[1]) + clearance
        positions.append((center[0] + radius * math.sin(angle), center[1] - radius * math.cos(angle),
                          center[2] + vertical))
    return positions


def panel_measurement(context, avatar, setup, radii, width, height, label):
    session = Session()
    session.add([(-width / 2, -height / 2), (width / 2, -height / 2),
                 (width / 2, height / 2), (-width / 2, height / 2)])
    pattern = session.document.patterns[0]
    pattern.arrangement = arrangement_record('chest', 'front', flat=True)
    context.scene.dd_document = session.document.dumps()
    panel = garment.build_panels(context)[0]
    flat_vertices = [tuple(vertex.co) for vertex in panel.data.vertices]
    pattern.arrangement['flat'] = False
    live_panels.position_panel(context, pattern, panel, (0, 0))
    panel.data.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in panel.data.loop_triangles]
    circle_vertices = [tuple(panel.matrix_world @ vertex.co) for vertex in panel.data.vertices]
    evaluated = avatar.evaluated_get(context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        body_tree = BVHTree.FromPolygons([evaluated.matrix_world @ vertex.co for vertex in mesh.vertices],
                                         [tuple(face.vertices) for face in mesh.loop_triangles], all_triangles=True)
    finally:
        evaluated.to_mesh_clear()
    resolved = arrangement.resolve_point(context, 'chest', 'front')
    low, extent, axes = arrangement._volume_frame(context)
    ellipse_vertices = wrapped_ellipse(flat_vertices, resolved['volume']['center'], radii, setup['clearance'] * extent[2])
    angular_vertices = angular_ellipse(flat_vertices, resolved['volume']['center'], radii,
                                       setup['clearance'] * extent[2])
    middle = min(range(len(flat_vertices)), key=lambda index: math.hypot(*flat_vertices[index][:2]))
    return dict(piece=label, width_m=width, height_m=height,
                geometry_sha256={name: hashlib.sha256(json.dumps([positions, triangles]).encode('utf-8')).hexdigest()
                                 for name, positions in (('circle', circle_vertices), ('ellipse', ellipse_vertices),
                                                         ('ellipse_existing_angle', angular_vertices))},
                circle=intersection_counts(circle_vertices, triangles, body_tree),
                ellipse=intersection_counts(ellipse_vertices, triangles, body_tree),
                ellipse_existing_angle=intersection_counts(angular_vertices, triangles, body_tree),
                center_vertex_surface_gap_mm=dict(circle=body_tree.find_nearest(Vector(circle_vertices[middle]))[3] * 1000,
                                                  ellipse=body_tree.find_nearest(Vector(ellipse_vertices[middle]))[3] * 1000))


def measure_body(context, label, scale, location):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, location=location)
    avatar = context.object
    avatar.name = label
    avatar.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    context.scene.dd_avatar = avatar
    context.view_layer.update()
    setup = arrangement.ensure_volumes(context, force=True)
    vertices, triangles, axes = arrangement._volume_mesh(context, avatar)
    low, extent = arrangement._volume_bounds(vertices)
    normalized = [tuple((point[axis] - low[axis]) / extent[2] for axis in range(3)) for point in vertices]
    samples = []
    chest_radii = None
    for volume in setup['volumes']:
        if volume['id'] not in ('chest', 'waist', 'hip'):
            continue
        for index, sample in enumerate(volume['samples']):
            center = tuple(sample['center'][axis] * extent[axis] / extent[2] for axis in range(3))
            groups = arrangement._volume_sections(normalized, triangles, (0, 0, 1), center[2])
            loop = min(groups, key=lambda group: math.dist(arrangement._volume_center(group), center))
            radii = fitted_section(loop, center)
            points = uniform_loop(loop, center)
            circle_gaps = [abs(math.dist(point, center) - sample['radius']) * extent[2] * 1000 for point in points]
            ellipse_gaps = [ellipse_gap(point, center, radii) * extent[2] * 1000 for point in points]
            samples.append(dict(volume=volume['id'], sample=index, t=sample['t'], height_m=center[2] * extent[2],
                                radii_m=[radius * extent[2] for radius in radii],
                                circle_mean_mm=sum(circle_gaps) / len(circle_gaps), circle_max_mm=max(circle_gaps),
                                ellipse_mean_mm=sum(ellipse_gaps) / len(ellipse_gaps), ellipse_max_mm=max(ellipse_gaps)))
            if volume['id'] == 'chest' and sample['t'] == .5:
                chest_radii = tuple(radius * extent[2] for radius in radii)
    assert chest_radii is not None
    dimensions = ((.4, .45, 'bodice_front'), (extent[0] * 1.2, extent[2] * .8, 'tall_front'))
    panels = [panel_measurement(context, avatar, setup, chest_radii, *values) for values in dimensions]
    bare_resolved = arrangement.world_points(context)
    bpy.ops.object.armature_add(location=location)
    rig = context.object
    modifier = avatar.modifiers.new(name='Prototype inert rig', type='ARMATURE')
    modifier.object = rig
    context.view_layer.update()
    rigged_setup = arrangement.ensure_volumes(context, force=True)
    assert rigged_setup == setup and arrangement.world_points(context) == bare_resolved
    assert [panel_measurement(context, avatar, rigged_setup, chest_radii, *values) for values in dimensions] == panels
    return dict(body=label, source_fixture='tests/blender_advanced.py refit mesh, same 16x12 sphere topology',
                scale=list(scale), location=list(location), armature_invariant=True, samples=samples, panels=panels)


def main():
    check_source(Path(__file__).read_text(encoding='utf-8'), str(Path(__file__).relative_to(ROOT)))
    for angle in (0, .2, 1, 2, 3, 4, 5):
        point = (.4 * math.cos(angle), .4 * math.sin(angle), 0)
        assert abs(ellipse_gap(point, (0, 0, 0), (.5, .5)) - .1) < 1e-9
    assert fitted_section([(-.3, -.2, 0), (-.3, .2, 0), (.3, -.2, 0), (.3, .2, 0)], (0, 0, 0)) == (
        .3 * math.sqrt(2), .2 * math.sqrt(2))
    devil_designer.register()
    context = bpy.context
    context.scene.dd_clearance = .03
    context.scene.dd_spacing = .02
    protected = ('core.py', 'garment.py', 'meshing.py', 'placement.py', 'tack_binding.py')
    checksums = {name: hashlib.sha256((ROOT / 'devil_designer' / name).read_bytes()).hexdigest() for name in protected}
    bodies = [measure_body(context, 'Refit body', (.25, .15, .5), (0, 0, 1.2)),
              measure_body(context, 'Different refit body', (.4, .2, .75), (2, 0, 1.8))]
    improved_gaps = all(sample['ellipse_mean_mm'] < sample['circle_mean_mm'] and sample['ellipse_max_mm'] < sample['circle_max_mm']
                        for body in bodies for sample in body['samples'])
    no_new_intersections = all(panel['ellipse']['triangle_pairs'] <= panel['circle']['triangle_pairs'] and
                               panel['ellipse']['inside_vertices'] <= panel['circle']['inside_vertices']
                               for body in bodies for panel in body['panels'])
    for name, checksum in checksums.items():
        assert hashlib.sha256((ROOT / 'devil_designer' / name).read_bytes()).hexdigest() == checksum
    report = dict(method='256 equal-arc loop samples; absolute nearest Euclidean circle/ellipse distance; clearance excluded from section gaps',
                  fit='axis extrema with enclosing normalized-radius scale; radial 30 mm clearance; fixed-height arc-length and existing-angle wraps',
                  intersections='Blender BVH triangle-pair overlaps and signed-nearest inside vertex count; 1 micrometre tolerance',
                  protected_sha256=checksums, improved_gaps=improved_gaps, no_new_intersections=no_new_intersections,
                  gate_passed=improved_gaps and no_new_intersections, bodies=bodies)
    (prepare_scratch() / 'arrangement-ellipse-prototype.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
