import json
from dataclasses import dataclass, field

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_line_plane

from . import xpbd

GRAB_RADIUS = .05
RADIUS_RANGE = (.015, .15)
PULL = 'PULL'
PUSH = 'PUSH'
FOLD = 'FOLD'
SWEEP = 'SWEEP'
BRUSH_TRAIL = {FOLD: 2.0, SWEEP: 1.0}
BRUSH_RATE = .5
BRUSH_WALK = 64
STRENGTH_RANGE = (.2, 1.0)
LIVE_VERTEX_BUDGET = 14000
PIN_UNDO_LIMIT = 32


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


def flags(mesh, name):
    values = np.zeros(len(mesh.vertices), dtype=bool)
    attribute = mesh.attributes.get(name)
    if attribute is not None:
        attribute.data.foreach_get('value', values)
    return values


def vectors(mesh, name):
    values = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.attributes[name].data.foreach_get('vector', values)
    return values.reshape(-1, 3)


def base_points(mesh):
    values = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', values)
    return values.reshape(-1, 3)


def patch(source, vertex, radius):
    rest = vectors(source.data, 'dd_rest_position')
    return np.flatnonzero(np.linalg.norm(rest - rest[vertex], axis=1) <= radius)


def pinned_vertices(source):
    return np.flatnonzero(flags(source.data, 'dd_hold'))


def pinned_world(source):
    mesh = source.data
    held = flags(mesh, 'dd_hold')
    if not held.any():
        return []
    matrix = source.matrix_world
    return [matrix @ Vector(point) for point in vectors(mesh, 'dd_pin_target')[held].tolist()]


def store_pins(source, pinned, held, targets):
    mesh = source.data
    xpbd.write(mesh, 'dd_pinned', 'BOOLEAN', 'POINT', pinned)
    xpbd.write(mesh, 'dd_hold', 'BOOLEAN', 'POINT', held)
    xpbd.write(mesh, 'dd_pin_target', 'FLOAT_VECTOR', 'POINT', targets)
    mesh.update()
    source.update_tag()


def pin_cloth(source, vertices, positions):
    mesh = source.data
    pinned = flags(mesh, 'dd_pinned')
    held = flags(mesh, 'dd_hold')
    chosen = np.zeros(len(pinned), dtype=bool)
    chosen[vertices] = True
    chosen &= held | ~pinned
    if not chosen.any():
        return 0
    targets = vectors(mesh, 'dd_pin_target').copy()
    targets[chosen] = positions[chosen]
    store_pins(source, pinned | chosen, held | chosen, targets)
    return int(chosen.sum())


def unpin_cloth(source, vertices=None):
    mesh = source.data
    held = flags(mesh, 'dd_hold')
    chosen = held.copy()
    if vertices is not None:
        chosen[:] = False
        chosen[vertices] = True
        chosen &= held
    if not chosen.any():
        return 0
    store_pins(source, flags(mesh, 'dd_pinned') & ~chosen, held & ~chosen, vectors(mesh, 'dd_pin_target'))
    return int(chosen.sum())


def pin_records(source):
    from .piece_states import piece_indices
    held = flags(source.data, 'dd_hold')
    if not held.any() or not source.get('dd_run_rest'):
        return {}
    saved = json.loads(source['dd_run_rest'])
    records = {}
    for identity, indices in piece_indices(source).items():
        rest = saved.get(identity, [])
        points = [rest[offset][:2] for offset, index in enumerate(indices) if held[index]] if len(rest) == len(indices) else []
        if points:
            records[identity] = points
    return records


def carry_pins(obj, records):
    from .piece_states import piece_indices
    if not records:
        return
    saved = json.loads(obj['dd_run_rest'])
    chosen = []
    for identity, indices in piece_indices(obj).items():
        if identity in records and identity in saved:
            rest = np.array(saved[identity], dtype=np.float64)[:, :2]
            chosen.extend(indices[int(np.argmin(np.linalg.norm(rest - point, axis=1)))] for point in records[identity])
    pin_cloth(obj, chosen, base_points(obj.data))


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
    lifted: object = None
    undo_steps: list = field(default_factory=list)
    strength: float = .6
    stroke_vertex: int = -1
    stroke_trail: object = None
    links: object = None

    @property
    def held(self):
        return self.vertex >= 0

    @property
    def brushing(self):
        return self.stroke_vertex >= 0

    @property
    def live_brush(self):
        return self.mode in BRUSH_TRAIL

    def scale_strength(self, factor):
        self.strength = max(STRENGTH_RANGE[0], min(STRENGTH_RANGE[1], self.strength * factor))

    def neighbours(self, vertex):
        if self.links is None:
            mesh = self.source.data
            edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
            mesh.edges.foreach_get('vertices', edges)
            edges = edges.reshape(-1, 2)
            pairs = np.concatenate((edges, edges[:, ::-1]))
            pairs = pairs[np.argsort(pairs[:, 0], kind='stable')]
            self.links = np.searchsorted(pairs[:, 0], np.arange(len(mesh.vertices) + 1)), pairs[:, 1]
        starts, linked = self.links
        return linked[starts[vertex]:starts[vertex + 1]].tolist()

    def follow(self, context, origin, direction):
        vertices = self.source.evaluated_get(context.evaluated_depsgraph_get()).data.vertices
        matrix = self.source.matrix_world

        def world(vertex):
            return matrix @ vertices[vertex].co

        def miss(vertex):
            return (world(vertex) - origin).cross(direction).length_squared

        vertex, best = self.stroke_vertex, miss(self.stroke_vertex)
        for _ in range(BRUSH_WALK):
            closer = min(((miss(candidate), candidate) for candidate in self.neighbours(vertex)), default=(best, vertex))
            if closer[0] >= best:
                break
            best, vertex = closer
        self.stroke_vertex = vertex
        return origin + direction * (world(vertex) - origin).dot(direction)

    def write_stroke(self, context, head, gain):
        unit = max(1e-6, context.scene.unit_settings.scale_length)
        reach = self.radius / unit
        trail = self.stroke_trail - head
        leash = reach * BRUSH_TRAIL[self.mode]
        if trail.length > leash:
            self.stroke_trail = head + trail * (leash / trail.length)
        local = self.source.matrix_world.inverted()
        xpbd.set_input(self.source, 'Brush Start', tuple(local @ self.stroke_trail))
        xpbd.set_input(self.source, 'Brush End', tuple(local @ head))
        xpbd.set_input(self.source, 'Brush Shape', (reach, gain, float(self.mode == SWEEP)))
        self.source.update_tag()

    def begin_stroke(self, context, vertex, point):
        self.stroke_vertex = vertex
        self.stroke_trail = point.copy()
        self.write_stroke(context, point, self.strength * BRUSH_RATE)

    def stroke_to(self, context, origin, direction):
        if self.brushing:
            self.write_stroke(context, self.follow(context, origin, direction.normalized()), self.strength * BRUSH_RATE)

    def end_stroke(self, context):
        if not self.brushing:
            return
        if self.alive:
            self.write_stroke(context, self.stroke_trail, 0.0)
        self.stroke_vertex = -1
        self.stroke_trail = None

    def pin_stroke(self, context):
        unit = max(1e-6, context.scene.unit_settings.scale_length)
        self.checkpoint()
        count = pin_cloth(self.source, patch(self.source, self.stroke_vertex, self.radius / unit), evaluated_points(context, self.source))
        if not count:
            self.undo_steps.pop()
        return count

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

    @property
    def alive(self):
        try:
            return xpbd.modifier(self.source) is not None
        except ReferenceError:
            return False

    def checkpoint(self):
        mesh = self.source.data
        self.undo_steps.append((flags(mesh, 'dd_pinned'), flags(mesh, 'dd_hold'), vectors(mesh, 'dd_pin_target').copy()))
        del self.undo_steps[:-PIN_UNDO_LIMIT]

    def undo(self):
        if self.held or not self.undo_steps:
            return False
        store_pins(self.source, *self.undo_steps.pop())
        return True

    def locked(self, vertex):
        mesh = self.source.data
        return bool(flags(mesh, 'dd_pinned')[vertex] and not flags(mesh, 'dd_hold')[vertex])

    def arm(self):
        if self.quality:
            return
        self.quality = xpbd.input_slot(self.source, 'Inner Substeps').value
        live = max(xpbd.MIN_SUBSTEPS, LIVE_VERTEX_BUDGET // len(self.source.data.vertices))
        xpbd.set_input(self.source, 'Inner Substeps', min(self.quality, live))
        self.source.update_tag()

    def disarm(self):
        if self.quality and self.alive:
            xpbd.set_input(self.source, 'Inner Substeps', self.quality)
            self.source.update_tag()
        self.quality = 0

    def begin(self, context, vertex, point, normal, view_direction):
        handle = xpbd.input_slot(self.source, 'Grab Handle').value
        held = self.source.matrix_world @ Vector(evaluated_points(context, self.source)[vertex].tolist())
        handle.location = held
        self.vertex = vertex
        self.plane_point = point.copy()
        self.plane_normal = view_direction.normalized()
        self.press_normal = normal.normalized()
        self.offset = held - point
        self.rebase = False
        unit = max(1e-6, context.scene.unit_settings.scale_length)
        self.lifted = np.intersect1d(patch(self.source, vertex, self.radius / unit), pinned_vertices(self.source))
        if len(self.lifted):
            self.checkpoint()
            unpin_cloth(self.source, self.lifted)
        xpbd.set_input(self.source, 'Grab Radius', self.radius / unit)
        xpbd.set_input(self.source, 'Grab Index', vertex)
        xpbd.set_input(self.source, 'Grab Release', -1.0)
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

    def pin(self, context):
        if not self.held:
            return 0
        unit = max(1e-6, context.scene.unit_settings.scale_length)
        if self.lifted is None or not len(self.lifted):
            self.checkpoint()
        count = pin_cloth(self.source, patch(self.source, self.vertex, self.radius / unit), evaluated_points(context, self.source))
        self.lifted = None
        self.drop()
        return count

    def unpin_near(self, context, vertex):
        unit = max(1e-6, context.scene.unit_settings.scale_length)
        self.checkpoint()
        freed = unpin_cloth(self.source, patch(self.source, vertex, self.radius / unit))
        if not freed:
            self.undo_steps.pop()
        return freed

    def unpin_all(self):
        self.checkpoint()
        freed = unpin_cloth(self.source)
        if not freed:
            self.undo_steps.pop()
        return freed

    def drop(self):
        self.vertex = -1
        xpbd.set_input(self.source, 'Grab Index', -1)
        self.source.update_tag()

    def release(self, context):
        if not self.held:
            return
        if self.lifted is not None and len(self.lifted):
            pin_cloth(self.source, self.lifted, evaluated_points(context, self.source))
            self.lifted = None
            self.drop()
            return
        scene = context.scene
        self.vertex = -1
        xpbd.set_input(self.source, 'Grab Release', scene.frame_current * scene.render.fps_base / scene.render.fps)
        self.source.update_tag()
