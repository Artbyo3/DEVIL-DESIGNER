from dataclasses import dataclass

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_line_plane

from . import xpbd

GRAB_RADIUS = .05
RADIUS_RANGE = (.015, .15)
PULL = 'PULL'
PUSH = 'PUSH'
LIVE_VERTEX_BUDGET = 14000


def evaluated_points(context, source):
    mesh = source.evaluated_get(context.evaluated_depsgraph_get()).data
    points = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', points)
    return points.reshape(-1, 3)


def triangles(source):
    mesh = source.data
    mesh.calc_loop_triangles()
    indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get('vertices', indices)
    return indices.reshape(-1, 3)


@dataclass
class ClothGrab:
    source: object
    vertex: int = -1
    radius: float = GRAB_RADIUS
    mode: str = PULL
    plane_point: object = None
    plane_normal: object = None
    press_normal: object = None
    quality: int = 0
    offset: object = None
    rebase: bool = False

    @property
    def held(self):
        return self.vertex >= 0

    def pick(self, context, origin, direction):
        points = evaluated_points(context, self.source)
        faces = triangles(self.source)
        matrix = self.source.matrix_world
        tree = BVHTree.FromPolygons([matrix @ Vector(point) for point in points.tolist()], faces.tolist(), all_triangles=True)
        hit, normal, face, _ = tree.ray_cast(origin, direction)
        if hit is None:
            return None
        corners = faces[face]
        world = [matrix @ Vector(points[corner].tolist()) for corner in corners]
        nearest = min(range(3), key=lambda index: (world[index] - hit).length_squared)
        return int(corners[nearest]), hit, normal if normal.dot(direction) < 0 else -normal

    def scale_radius(self, factor):
        self.radius = max(RADIUS_RANGE[0], min(RADIUS_RANGE[1], self.radius * factor))

    def begin(self, context, vertex, point, normal, view_direction):
        handle = xpbd.input_slot(self.source, 'Grab Handle').value
        handle.location = point
        self.vertex = vertex
        self.plane_point = point.copy()
        self.plane_normal = view_direction.normalized()
        self.press_normal = normal.normalized()
        self.offset = Vector((0.0, 0.0, 0.0))
        self.rebase = False
        unit = max(1e-6, context.scene.unit_settings.scale_length)
        xpbd.set_input(self.source, 'Grab Radius', self.radius / unit)
        xpbd.set_input(self.source, 'Grab Index', vertex)
        self.quality = xpbd.input_slot(self.source, 'Inner Substeps').value
        live = max(xpbd.MIN_SUBSTEPS, LIVE_VERTEX_BUDGET // len(self.source.data.vertices))
        xpbd.set_input(self.source, 'Inner Substeps', min(self.quality, live))
        self.source.update_tag()

    def drag(self, origin, direction):
        if not self.held:
            return
        target = intersect_line_plane(origin, origin + direction, self.plane_point, self.plane_normal)
        if target is None:
            return
        if self.mode == PUSH:
            target = self.plane_point - self.press_normal * (target - self.plane_point).length
        handle = xpbd.input_slot(self.source, 'Grab Handle').value
        if self.rebase:
            self.offset = handle.location - target
            self.rebase = False
        handle.location = target + self.offset

    def view_changed(self):
        if self.held:
            self.rebase = True

    def release(self):
        if self.held:
            self.vertex = -1
            xpbd.set_input(self.source, 'Grab Index', -1)
            xpbd.set_input(self.source, 'Inner Substeps', self.quality)
            self.source.update_tag()
