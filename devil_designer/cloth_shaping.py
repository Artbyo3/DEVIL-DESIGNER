import hashlib
import heapq
import json
import math
from dataclasses import dataclass, field
from enum import Enum

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


_targets = {}
_sessions = {}


def _driver_strength(identity, frame):
    if not math.isfinite(frame) or identity not in _targets:
        return 0.0
    start, initial, target = _targets[identity]
    fraction = max(0.0, min(1.0, (frame - start) / 10.0))
    return initial + (target - initial) * fraction


def _observe(scene, graph):
    for identity, session in tuple(_sessions.items()):
        try:
            if session.source.name not in scene.objects:
                continue
            if session.source.hide_get():
                _sessions.pop(identity, None)
                continue
            with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
                if not session.monitor(bpy.context):
                    from . import garment
                    garment.stop(bpy.context)
        except (ValueError, RuntimeError, ReferenceError) as failure:
            session.detach()
            session.phase = Phase.BLOCKED
            session.message = str(failure)
            from . import garment
            garment.stop(bpy.context)


def forget(source):
    _targets.pop(source.as_pointer(), None)
    _sessions.pop(source.as_pointer(), None)
    if not _sessions and _observe in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_observe)


def keep_guard(context, source, candidate=None):
    if source.get('dd_shape_held') or source.vertex_groups.get('DD Shape Hold'):
        raise ValueError('Release or cancel the shaping stroke before keeping the mesh.')
    session = _sessions.get(source.as_pointer())
    if session and (session.phase == Phase.BLOCKED or not session.monitor(context)):
        raise ValueError(session.message)
    if source.get('dd_shape_topology') and source['dd_shape_topology'] != _fingerprint(source):
        raise ValueError('The shaped mesh topology changed. Reset the drape before keeping it.')
    target = candidate if candidate is not None else source
    evaluated = target.evaluated_get(context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        coordinates = [target.matrix_world @ vertex.co for vertex in mesh.vertices]
        if not all(math.isfinite(component) for point in coordinates for component in point):
            raise ValueError('The shaped mesh has non-finite coordinates. Reset the drape before keeping it.')
        guard = CollisionGuard.capture(context, source, 0)
        if any(guard.contains(point) for point in coordinates):
            raise ValueError('The shaped mesh is inside a collider. Restore clearance before keeping it.')
        mesh.calc_loop_triangles()
        faces = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        obstacles = [point for entry in guard.triangles for point in entry[0]]
        if faces and obstacles:
            collider_faces = [(index, index + 1, index + 2) for index in range(0, len(obstacles), 3)]
            cloth_tree = BVHTree.FromPolygons(coordinates, faces, all_triangles=True)
            collider_tree = BVHTree.FromPolygons(obstacles, collider_faces, all_triangles=True)
            if cloth_tree.overlap(collider_tree):
                raise ValueError('The shaped mesh intersects a collider. Restore clearance before keeping it.')
    finally:
        evaluated.to_mesh_clear()


def clear():
    _targets.clear()
    _sessions.clear()
    if _observe in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_observe)
    if bpy.app.driver_namespace.get('dd_shape_strength') is _driver_strength:
        del bpy.app.driver_namespace['dd_shape_strength']


def recover_loaded(context):
    from . import garment
    for source in garment.generated(context.scene, 'simulation'):
        if source.get('dd_shape_held'):
            session = ShapingSession(source)
            session.reset(context, interrupted=True)
            context.scene['dd_shaping_recovery'] = 'An interrupted shaping stroke was cancelled on load. The previous drape and original pins were restored.'


class Phase(Enum):
    IDLE = "Idle"
    HELD = "Held"
    RELEASED = "Released"
    BLOCKED = "Blocked"


def points(source):
    evaluated = source.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [vertex.co.copy() for vertex in evaluated.data.vertices]


def _fingerprint(source):
    mesh = source.data
    payload = [len(mesh.vertices), [list(edge.vertices) for edge in mesh.edges],
               [list(polygon.vertices) for polygon in mesh.polygons]]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _normal_offsets(matrix, normals):
    inverse = matrix.to_3x3().inverted()
    normal_matrix = inverse.transposed()
    return [inverse @ (normal_matrix @ normal).normalized() for normal in normals]


def _triangle_box(triangle, lower, upper):
    center = (lower + upper) * .5
    extent = (upper - lower) * .5
    translated = [point - center for point in triangle]
    edges = [translated[1] - translated[0], translated[2] - translated[1], translated[0] - translated[2]]
    cardinal = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    axes = list(cardinal) + [edges[0].cross(edges[1])]
    axes.extend(edge.cross(axis) for edge in edges for axis in cardinal)
    for axis in axes:
        if axis.length_squared < 1e-24:
            continue
        projections = [point.dot(axis) for point in translated]
        radius = sum(abs(component) * size for component, size in zip(axis, extent))
        if min(projections) > radius + 1e-10 or max(projections) < -radius - 1e-10:
            return False
    return True


_DIRECTIONS = (
    Vector((1.0, 0.371, 0.529)).normalized(),
    Vector((0.193, 1.0, 0.613)).normalized(),
    Vector((0.419, 0.271, 1.0)).normalized(),
    Vector((-0.723, 0.512, 0.463)).normalized(),
    Vector((0.331, -0.812, 0.479)).normalized(),
    Vector((-0.457, -0.389, 0.799)).normalized(),
    Vector((0.612, -0.354, -0.651)).normalized(),
    Vector((-0.211, 0.781, -0.588)).normalized(),
    Vector((0.831, -0.219, 0.511)).normalized(),
    Vector((-0.155, -0.732, -0.663)).normalized(),
)


@dataclass
class CollisionGuard:
    triangles: list = field(default_factory=list)
    identity: tuple = ()
    solids: list = field(default_factory=list)

    @classmethod
    def capture(cls, context, source, distance):
        triangles = []
        identity = []
        solids = []
        graph = context.evaluated_depsgraph_get()
        for body in context.scene.objects:
            if body == source:
                continue
            if not any(modifier.type == "COLLISION" and modifier.show_viewport for modifier in body.modifiers):
                continue
            if body.type != 'MESH':
                raise ValueError('Shaping cannot prove clearance against a non-mesh collider. Convert it to a mesh first.')
            evaluated = body.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles()
                coordinates = [body.matrix_world @ vertex.co for vertex in mesh.vertices]
                identity.append((body.as_pointer(), distance, body.collision.thickness_outer, tuple(tuple(row) for row in body.matrix_world),
                                 tuple(tuple(point) for point in coordinates),
                                 tuple(tuple(triangle.vertices) for triangle in mesh.loop_triangles)))
                scale = max(1.0, max(abs(component) for component in body.matrix_world.to_scale()))
                margin = distance + body.collision.thickness_outer * scale
                faces = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
                incidence = {}
                face_edges = []
                for face_index, face in enumerate(faces):
                    links = []
                    for first, second in zip(face, face[1:] + face[:1]):
                        edge = tuple(sorted((first, second)))
                        incidence.setdefault(edge, []).append(face_index)
                        links.append(edge)
                    face_edges.append(links)
                remaining = set(range(len(faces)))
                while remaining:
                    pending = [remaining.pop()]
                    component = []
                    while pending:
                        face_index = pending.pop()
                        component.append(face_index)
                        for edge in face_edges[face_index]:
                            for neighbor in incidence[edge]:
                                if neighbor in remaining:
                                    remaining.remove(neighbor)
                                    pending.append(neighbor)
                    if all(len(incidence[edge]) == 2 for face_index in component for edge in face_edges[face_index]):
                        shell = [faces[face_index] for face_index in component]
                        vertices = [coordinates[index] for index in {index for face in shell for index in face}]
                        lower = Vector(tuple(min(point[axis] for point in vertices) for axis in range(3)))
                        upper = Vector(tuple(max(point[axis] for point in vertices) for axis in range(3)))
                        shell_triangles = tuple(tuple(coordinates[index] for index in face) for face in shell)
                        solids.append((lower, upper, shell_triangles))
                for triangle in mesh.loop_triangles:
                    vertices = tuple(coordinates[index] for index in triangle.vertices)
                    lower = Vector(tuple(min(point[axis] for point in vertices) for axis in range(3)))
                    upper = Vector(tuple(max(point[axis] for point in vertices) for axis in range(3)))
                    triangles.append((vertices, lower, upper, margin))
            finally:
                evaluated.to_mesh_clear()
        return cls(triangles, tuple(identity), solids)

    def contains(self, point):
        for lower, upper, triangles in self.solids:
            if any(point[axis] < lower[axis] or point[axis] > upper[axis] for axis in range(3)):
                continue
            for direction in _DIRECTIONS:
                count = 0
                degenerate = False
                dx, dy, dz = direction
                ox, oy, oz = point
                for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in triangles:
                    e1x, e1y, e1z = bx - ax, by - ay, bz - az
                    e2x, e2y, e2z = cx - ax, cy - ay, cz - az
                    hx = dy * e2z - dz * e2y
                    hy = dz * e2x - dx * e2z
                    hz = dx * e2y - dy * e2x
                    det = e1x * hx + e1y * hy + e1z * hz
                    tolerance = 1e-12 * math.sqrt((e1x * e1x + e1y * e1y + e1z * e1z) * (e2x * e2x + e2y * e2y + e2z * e2z))
                    if abs(det) <= tolerance:
                        continue
                    inv = 1.0 / det
                    sx = ox - ax
                    sy = oy - ay
                    sz = oz - az
                    u = inv * (sx * hx + sy * hy + sz * hz)
                    if u < -1e-9 or u > 1.0 + 1e-9:
                        continue
                    qx = sy * e1z - sz * e1y
                    qy = sz * e1x - sx * e1z
                    qz = sx * e1y - sy * e1x
                    v = inv * (dx * qx + dy * qy + dz * qz)
                    if v < -1e-9 or (u + v) > 1.0 + 1e-9:
                        continue
                    t = inv * (e2x * qx + e2y * qy + e2z * qz)
                    if t < 0:
                        continue
                    if u < 1e-12 or v < 1e-12 or (1.0 - u - v) < 1e-12:
                        degenerate = True
                        break
                    if t == 0:
                        return True
                    count += 1
                if not degenerate:
                    if count % 2 == 1:
                        return True
                    break
            else:
                return True
        return False

    def clear_sweep(self, before, after, triangles, matrix):
        checked = set()
        for indices in triangles:
            swept = [matrix @ positions[index] for positions in (before, after) for index in indices]
            for point in swept:
                coordinates = tuple(point)
                if coordinates not in checked:
                    checked.add(coordinates)
                    if self.contains(point):
                        return False
            minimum = Vector(tuple(min(point[axis] for point in swept) for axis in range(3)))
            maximum = Vector(tuple(max(point[axis] for point in swept) for axis in range(3)))
            for triangle, lower, upper, margin in self.triangles:
                padding = Vector((margin, margin, margin))
                first, last = minimum - padding, maximum + padding
                if any(upper[axis] < first[axis] or lower[axis] > last[axis] for axis in range(3)):
                    continue
                if _triangle_box(triangle, first, last):
                    return False
        return True


@dataclass
class ShapingSession:
    source: object
    phase: Phase = Phase.IDLE
    message: str = ""
    radius: float = .07
    strength: float = 0.0
    weights: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    baseline: list = field(default_factory=list)
    previous: list = field(default_factory=list)
    affected_triangles: list = field(default_factory=list)
    guard: CollisionGuard = field(default_factory=CollisionGuard)
    topology: str = ""
    matrix: object = None
    original_group: str = ""
    original_weights: list = field(default_factory=list)
    edge_lengths: list = field(default_factory=list)
    accepted_rest: list = field(default_factory=list)
    maximum: float = .02
    cache_resets: int = 0

    def cloth(self):
        cloth = next((modifier for modifier in self.source.modifiers if modifier.type == 'CLOTH'), None)
        if cloth is None:
            raise ValueError('The cloth simulation was removed. Reset the drape before shaping.')
        return cloth

    def _keys(self):
        return self.source.data.shape_keys.key_blocks

    def _valid(self):
        if self.source.name not in bpy.data.objects or _fingerprint(self.source) != self.topology:
            raise ValueError("The cloth topology changed. Reset the drape before shaping.")
        if self.source.matrix_world != self.matrix:
            raise ValueError("The garment moved during shaping. Cancel the stroke first.")

    def pick(self, context, origin, direction):
        coordinates = points(self.source)
        self.source.data.calc_loop_triangles()
        triangles = [tuple(triangle.vertices) for triangle in self.source.data.loop_triangles]
        world = [self.source.matrix_world @ point for point in coordinates]
        hit, normal, face, distance = BVHTree.FromPolygons(world, triangles, all_triangles=True).ray_cast(origin, direction)
        if hit is None or distance is None or normal.dot(direction) >= 0:
            return None
        from mathutils.geometry import intersect_ray_tri
        for triangle, lower, upper, margin in CollisionGuard.capture(context, self.source, 0).triangles:
            blocker = intersect_ray_tri(*triangle, direction, origin, True)
            if blocker is not None and (blocker - origin).length < distance:
                return None
        return min(triangles[face], key=lambda index: (world[index] - hit).length_squared)

    def begin(self, context, center, radius=None):
        if self.phase == Phase.HELD:
            raise ValueError('Release the current stroke first.')
        source = self.source
        cloth = self.cloth()
        if not cloth.show_viewport or sum(modifier.type == 'CLOTH' for modifier in source.modifiers) != 1:
            raise ValueError('Shaping needs one active cloth simulation. Frozen cloth is unchanged.')
        if context.scene.frame_current <= cloth.point_cache.frame_start:
            raise ValueError('Let the garment drape before shaping.')
        if any(modifier.type == 'HOOK' and modifier.show_viewport for modifier in source.modifiers):
            raise ValueError('Shaping with active tacks is unavailable. Tacks and their targets are unchanged.')
        if any(modifier.type not in {'CLOTH', 'WEIGHTED_NORMAL'} for modifier in source.modifiers):
            raise ValueError('Shaping requires the original cloth topology without additional modifiers.')
        if source.data.shape_keys and 'DD Shape Plain' not in source.data.shape_keys.key_blocks:
            raise ValueError('Existing shape keys are preserved. Shape a fresh drape instead.')
        if source.get('dd_shape_held'):
            raise ValueError('This saved stroke was interrupted. Reset shaping before continuing.')
        self.topology = _fingerprint(source)
        self.matrix = source.matrix_world.copy()
        self.baseline = points(source)
        self.previous = [point.copy() for point in self.baseline]
        if len(self.baseline) != len(source.data.vertices):
            raise ValueError('Shaping cannot change the mesh topology.')
        if center is None or not 0 <= center < len(self.baseline):
            raise ValueError('Press on the visible cloth to begin shaping.')
        units = max(1e-6, context.scene.unit_settings.scale_length)
        self.radius = max(.015, min(.15, radius if radius is not None else self.radius))
        self.maximum = .02 / units
        self.original_group = cloth.settings.vertex_group_mass
        original = source.vertex_groups.get(self.original_group)
        self.original_weights = [next((membership.weight for membership in vertex.groups
                                      if original and membership.group == original.index), 0.0)
                                 for vertex in source.data.vertices]
        evaluated = source.evaluated_get(context.evaluated_depsgraph_get())
        self.normals = _normal_offsets(self.matrix, [vertex.normal for vertex in evaluated.data.vertices])
        adjacency = [[] for point in self.baseline]
        for edge in source.data.edges:
            if not edge.is_loose:
                first, second = edge.vertices
                length = (self.matrix @ self.baseline[first] - self.matrix @ self.baseline[second]).length * units
                adjacency[first].append((second, length))
                adjacency[second].append((first, length))
        distances = {center: 0.0}
        queue = [(0.0, center)]
        while queue:
            distance, index = heapq.heappop(queue)
            if distance != distances[index]:
                continue
            for neighbor, length in adjacency[index]:
                candidate = distance + length
                if candidate < self.radius and candidate < distances.get(neighbor, math.inf):
                    if self.normals[neighbor].dot(self.normals[center]) <= 0:
                        continue
                    distances[neighbor] = candidate
                    heapq.heappush(queue, (candidate, neighbor))
        self.weights = [max(0.0, 1.0 - (distances[index] / self.radius) ** 2) ** 2
                        if index in distances and not self.original_weights[index] else 0.0
                        for index in range(len(self.baseline))]
        if not any(self.weights):
            raise ValueError('This patch is pinned. Original pin targets are preserved.')
        source.data.calc_loop_triangles()
        self.affected_triangles = [tuple(triangle.vertices) for triangle in source.data.loop_triangles
                                   if any(self.weights[index] for index in triangle.vertices)]
        self.edge_lengths = [(tuple(edge.vertices), (self.matrix.to_3x3() @ (self.baseline[edge.vertices[0]] - self.baseline[edge.vertices[1]])).length)
                             for edge in source.data.edges if not edge.is_loose]
        clearance = cloth.collision_settings.distance_min * max(abs(component) for component in self.matrix.to_scale())
        self.guard = CollisionGuard.capture(context, source, clearance)
        if not self.guard.clear_sweep(self.baseline, self.baseline, self.affected_triangles, self.matrix):
            self.phase = Phase.BLOCKED
            raise ValueError('This patch is too close to a collider to prove a safe stroke. Choose a looser patch.')
        if not source.data.shape_keys:
            flat = [vertex.co.copy() for vertex in source.data.vertices]
            material_normals = [vertex.normal.copy() for vertex in source.data.vertices]
            source.shape_key_add(name='DD Shape Basis', from_mix=False)
            for name, coordinates in (('DD Shape Flat', flat), ('DD Shape Plain', self.baseline),
                                      ('DD Shape Rest', flat), ('DD Shape Pins', flat)):
                key = source.shape_key_add(name=name, from_mix=False)
                for item, point in zip(key.data, coordinates):
                    item.co = point
                key.value = 0
            source['dd_shape_material_normals'] = json.dumps([list(normal) for normal in material_normals])
            source['dd_shape_original_group'] = self.original_group
            source['dd_shape_topology'] = self.topology
        self.accepted_rest = [item.co.copy() for item in self._keys()['DD Shape Rest'].data]
        self.strength = 0
        self.phase = Phase.IDLE
        forget(source)
        self._prepare(context, self.baseline, True)
        self.phase = Phase.HELD
        _sessions[source.as_pointer()] = self
        if _observe not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(_observe)
        source['dd_shape_held'] = True
        self.message = 'Drag in any direction using Pull or Push. Starting a stroke resets cloth velocity once.'

    def _prepare(self, context, coordinates, hold):
        from . import garment
        source = self.source
        configuration = garment.shaping_configuration(self.cloth())
        source.modifiers.remove(self.cloth())
        source.data.shape_keys.animation_data_clear()
        context.scene.frame_set(context.scene.frame_start)
        keys = self._keys()
        for retired in list(keys):
            if retired.name.startswith('DD Shape Retired'):
                source.shape_key_remove(retired)
        names = ('DD Shape Basis', 'DD Shape Target', 'DD Shape Stroke') if hold else ('DD Shape Basis', 'DD Shape Target')
        for name in names:
            key = keys.get(name) or source.shape_key_add(name=name, from_mix=False)
            for index, (item, point) in enumerate(zip(key.data, coordinates)):
                item.co = keys['DD Shape Pins'].data[index].co if self.original_weights[index] else point
            key.value = 0
        target = keys['DD Shape Target']
        if hold:
            for index, item in enumerate(target.data):
                item.co += self.normals[index] * self.maximum * self.weights[index]
            target.slider_min = -1
            target.value = 0
            _targets[source.as_pointer()] = (context.scene.frame_start, 0.0, 0.0)
            bpy.app.driver_namespace['dd_shape_strength'] = _driver_strength
            driver = target.driver_add('value').driver
            driver.expression = f'dd_shape_strength({source.as_pointer()},frame)'
        group = source.vertex_groups.get('DD Shape Hold')
        if group:
            source.vertex_groups.remove(group)
        if hold:
            group = source.vertex_groups.new(name='DD Shape Hold')
            for index, weight in enumerate(self.weights):
                combined = max(weight, self.original_weights[index])
                if combined:
                    group.add([index], combined, 'REPLACE')
        normal = source.modifiers.get('DD Shape Rest Evaluation')
        if normal is None:
            source.modifiers.new('DD Shape Rest Evaluation', 'WEIGHTED_NORMAL')
        cloth = garment.shaping_restore(context, source, configuration)
        cloth.settings.rest_shape_key = keys['DD Shape Rest']
        cloth.settings.vertex_group_mass = group.name if hold else self.original_group
        cloth.settings.use_dynamic_mesh = False
        cloth.point_cache.frame_end = max(cloth.point_cache.frame_end, context.scene.frame_start + 1000)
        context.scene.frame_end = max(context.scene.frame_end, cloth.point_cache.frame_end)
        self.cache_resets += 1
        context.view_layer.update()
        points(source)

    def _safe(self, coordinates):
        if not all(math.isfinite(component) for point in coordinates for component in point):
            return False
        if any((self.matrix.to_3x3() @ (coordinates[first] - coordinates[second])).length > length * 1.053 + 1e-9
               for (first, second), length in self.edge_lengths if length > 1e-9):
            return False
        return self.guard.clear_sweep(self.baseline, coordinates, self.affected_triangles, self.matrix)

    def update(self, context, strength):
        self._valid()
        if self.phase != Phase.HELD:
            raise ValueError('Press on cloth before shaping.')
        strength = max(-self.maximum, min(self.maximum, strength))
        requested = strength
        for attempt in range(15):
            target = [point + normal * strength * weight for point, normal, weight
                      in zip(self.baseline, self.normals, self.weights)]
            if self._safe(target):
                break
            strength *= .5
        else:
            strength = 0
        self.strength = strength
        identity = self.source.as_pointer()
        initial = _driver_strength(identity, context.scene.frame_current)
        _targets[identity] = (context.scene.frame_current, initial, strength / self.maximum)
        self.message = f'{"Pull" if strength >= 0 else "Push"} {abs(strength) * context.scene.unit_settings.scale_length * 1000:.1f} mm input'
        if abs(strength - requested) > 1e-9:
            self.message += ' | limited by clearance or fabric stretch'
        return strength

    def monitor(self, context):
        if self.phase not in {Phase.HELD, Phase.RELEASED}:
            return True
        self._valid()
        current = points(self.source)
        guard = CollisionGuard.capture(context, self.source, self.cloth().collision_settings.distance_min * max(abs(component) for component in self.matrix.to_scale()))
        valid = guard.identity == self.guard.identity
        valid = valid and self._safe(current)
        valid = valid and self.guard.clear_sweep(self.previous, current, self.affected_triangles, self.matrix)
        if not valid:
            self.phase = Phase.BLOCKED
            self.cancel(context)
            self.phase = Phase.BLOCKED
            self.message = 'Stroke rolled back. The evaluated cloth could not maintain safe clearance or stretch.'
            return False
        self.previous = current
        return True

    def release(self, context):
        self._valid()
        if self.phase != Phase.HELD:
            return
        source = self.source
        self.strength = _driver_strength(source.as_pointer(), context.scene.frame_current) * self.maximum
        _targets.pop(source.as_pointer(), None)
        source.data.shape_keys.animation_data_clear()
        self.cloth().settings.vertex_group_mass = self.original_group
        group = source.vertex_groups.get('DD Shape Hold')
        if group:
            source.vertex_groups.remove(group)
        self._keys()['DD Shape Target'].value = 0
        normals = _normal_offsets(self.matrix, [Vector(normal) for normal in json.loads(source['dd_shape_material_normals'])])
        rest = source.shape_key_add(name='DD Shape Released Rest', from_mix=False)
        rest.value = 0
        for item, point, normal, weight in zip(rest.data, self.accepted_rest, normals, self.weights):
            item.co = point + normal * self.strength * weight
        previous = self._keys()['DD Shape Rest']
        self.cloth().settings.rest_shape_key = rest
        previous.name = 'DD Shape Retired'
        rest.name = 'DD Shape Rest'
        source['dd_shape_held'] = False
        self.phase = Phase.RELEASED
        self.message = 'Released. The native flat-material rest shape retains the fold. Retention differs for push and pull.'
        context.view_layer.update()

    def detach(self):
        source = self.source
        try:
            forget(source)
            if source.data.shape_keys:
                source.data.shape_keys.animation_data_clear()
                target = source.data.shape_keys.key_blocks.get('DD Shape Target')
                if target:
                    target.value = 0
            cloth = next((modifier for modifier in source.modifiers if modifier.type == 'CLOTH'), None)
            if cloth:
                cloth.settings.vertex_group_mass = self.original_group
            group = source.vertex_groups.get('DD Shape Hold')
            if group:
                source.vertex_groups.remove(group)
            source['dd_shape_held'] = False
        except ReferenceError:
            return

    def cancel(self, context):
        try:
            self._valid()
        except (ValueError, ReferenceError):
            self.detach()
            self.phase = Phase.BLOCKED
            raise
        self.phase = Phase.IDLE
        _targets.pop(self.source.as_pointer(), None)
        for item, point in zip(self._keys()['DD Shape Rest'].data, self.accepted_rest):
            item.co = point
        self._prepare(context, self.baseline, False)
        self.source['dd_shape_held'] = False
        forget(self.source)
        self.phase = Phase.IDLE
        self.message = 'Stroke cancelled. The previous drape is restored with reset velocity.'

    def reset(self, context, interrupted=False):
        source = self.source
        self.phase = Phase.IDLE
        forget(source)
        if not source.data.shape_keys or 'DD Shape Plain' not in source.data.shape_keys.key_blocks:
            raise ValueError('There is no stored plain drape to restore.')
        self.topology = source['dd_shape_topology']
        self.matrix = source.matrix_world.copy()
        self._valid()
        self.original_group = source['dd_shape_original_group']
        group = source.vertex_groups.get(self.original_group)
        self.original_weights = [next((membership.weight for membership in vertex.groups
                                      if group and membership.group == group.index), 0.0)
                                 for vertex in source.data.vertices]
        name = 'DD Shape Stroke' if interrupted else 'DD Shape Plain'
        self.baseline = [item.co.copy() for item in self._keys()[name].data]
        if not interrupted:
            for item, original in zip(self._keys()['DD Shape Rest'].data, self._keys()['DD Shape Flat'].data):
                item.co = original.co
        self._prepare(context, self.baseline, False)
        source['dd_shape_held'] = False
        forget(source)
        self.phase = Phase.IDLE
        self.message = 'Plain drape restored. Shaping removed. Cloth velocity reset.'
