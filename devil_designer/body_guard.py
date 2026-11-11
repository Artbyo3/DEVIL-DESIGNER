import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .body_surface import revealed

NUDGE_REACH = .012
CLEARANCE = .001
FELL_MARGIN = .2
ALIGNED = .6
NO_TORSO_AT_KEEP = ('This avatar has no torso surface, so the cloth fell through where the torso should be. '
                    'Choose a full body, or add a Collision modifier to its outfit, then Simulate again.')


def surface_tree(context, source):
    with revealed(context, source) as evaluated:
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            points = [source.matrix_world @ vertex.co for vertex in mesh.vertices]
            faces = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
            return BVHTree.FromPolygons(points, faces, all_triangles=True)
        finally:
            evaluated.to_mesh_clear()


def refusal(context, bodies, message):
    from .arrangement import missing_torso
    if missing_torso(context, bodies):
        return ValueError(NO_TORSO_AT_KEEP)
    return ValueError(message)


def clear_surface(tree, points, margin, reach):
    blocked = []
    for index, point in enumerate(points):
        nearest, normal, _, distance = tree.find_nearest(point)
        if nearest is None or distance < 1e-9:
            continue
        height = (point - nearest).dot(normal)
        if height < 0 and -height > distance * ALIGNED:
            if distance > reach:
                blocked.append(distance)
            else:
                points[index] = nearest + normal * margin
    return blocked


def embedded(context, bodies, coordinates, unit):
    points = [Vector(point) for point in coordinates]
    count, depth = 0, 0.0
    for body in bodies:
        tree = surface_tree(context, body)
        for point in points:
            nearest, normal, _, distance = tree.find_nearest(point)
            if nearest is None or distance < NUDGE_REACH / unit:
                continue
            height = (point - nearest).dot(normal)
            if height < 0 and -height > distance * ALIGNED:
                count += 1
                depth = max(depth, distance * unit)
    return count, depth


def check(context, bodies, coordinates, unit):
    points = [Vector(point) for point in np.asarray(coordinates).tolist()]
    lowest_body = min((body.matrix_world @ Vector(corner)).z for body in bodies for corner in body.bound_box)
    if max(point.z for point in points) < lowest_body - FELL_MARGIN / unit:
        raise refusal(context, bodies, 'The garment fell off the body. Reset, then check its fit and placement.')
    for body in bodies:
        blocked = clear_surface(surface_tree(context, body), points, CLEARANCE / unit, NUDGE_REACH / unit)
        if blocked:
            raise refusal(context, bodies, f'{len(blocked)} cloth points are inside {body.name}, up to {max(blocked) * unit * 1000:.1f} mm. '
                          'Let the cloth settle or pull it clear, then Keep again.')
    return np.array([tuple(point) for point in points], dtype=np.float32)
