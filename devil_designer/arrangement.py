import math
import json
import re
from dataclasses import dataclass


def _volume_bounds(vertices):
    if not vertices or any(len(point) != 3 or any(not math.isfinite(value) for value in point)
                           for point in vertices):
        raise ValueError('Avatar vertices must contain finite three-dimensional points.')
    low = tuple(min(point[axis] for point in vertices) for axis in range(3))
    high = tuple(max(point[axis] for point in vertices) for axis in range(3))
    extent = tuple(high[axis] - low[axis] for axis in range(3))
    if min(extent) <= 0 or any(not math.isfinite(value) for value in extent):
        raise ValueError('Avatar bounds must have positive finite width, depth, and height.')
    return low, extent


def _volume_dot(first, second):
    return sum(first[axis] * second[axis] for axis in range(3))


def _volume_unit(vector):
    length = math.hypot(*vector)
    if length <= 1e-12:
        raise ValueError('Avatar volume has a degenerate axis.')
    return tuple(value / length for value in vector)


def _volume_cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _volume_sections(vertices, triangles, normal, offset):
    points = {}
    parents = {}

    def root(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for triangle in triangles:
        corners = [vertices[index] for index in triangle]
        distances = [_volume_dot(point, normal) - offset for point in corners]
        intersections = []
        for first, second in ((0, 1), (1, 2), (2, 0)):
            start, end = corners[first], corners[second]
            start_distance, end_distance = distances[first], distances[second]
            if abs(start_distance) < 1e-9:
                intersections.append(start)
            if start_distance * end_distance < 0:
                factor = start_distance / (start_distance - end_distance)
                intersections.append(tuple(start[axis] + factor * (end[axis] - start[axis])
                                           for axis in range(3)))
        keys = []
        for point in intersections:
            key = tuple(round(value, 8) for value in point)
            points[key] = point
            parents.setdefault(key, key)
            keys.append(key)
        for key in keys[1:]:
            parents[root(key)] = root(keys[0])
    groups = {}
    for key, point in points.items():
        groups.setdefault(root(key), []).append(point)
    return [group for group in groups.values() if len(group) >= 3]


def _volume_center(points):
    return tuple((min(point[axis] for point in points) + max(point[axis] for point in points)) / 2
                 for axis in range(3))


def generate_volumes(vertices, triangles, clearance=0.03):
    vertices = [tuple(point) for point in vertices]
    triangles = [tuple(triangle) for triangle in triangles]
    low, extent = _volume_bounds(vertices)
    if not math.isfinite(clearance) or clearance < 0:
        raise ValueError('Avatar clearance must be nonnegative and finite.')
    if not triangles or any(len(triangle) != 3 or any(
            not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(vertices)
            for index in triangle) for triangle in triangles):
        raise ValueError('Avatar triangles must contain three valid vertex indices.')
    normalized = [tuple((point[axis] - low[axis]) / extent[2] for axis in range(3))
                  for point in vertices]
    if not any(math.hypot(*_volume_cross(
            tuple(normalized[triangle[1]][axis] - normalized[triangle[0]][axis] for axis in range(3)),
            tuple(normalized[triangle[2]][axis] - normalized[triangle[0]][axis] for axis in range(3)))) > 1e-12
            for triangle in triangles):
        raise ValueError('Avatar triangles must contain a nondegenerate surface.')
    width = extent[0] / extent[2]
    middle = width / 2
    specifications = [('neck', .83, .90), ('chest', .66, .80), ('waist', .53, .65),
                      ('hip', .43, .54), ('left_upper_arm', .15, .32),
                      ('right_upper_arm', .15, .32), ('left_forearm', .32, .48),
                      ('right_forearm', .32, .48), ('left_thigh', .25, .45),
                      ('right_thigh', .25, .45), ('left_calf', .04, .25),
                      ('right_calf', .04, .25)]
    volumes = []
    for identity, lower, upper in specifications:
        arm = 'arm' in identity
        side = 1 if identity.startswith('left_') else -1 if identity.startswith('right_') else 0
        samples = []
        for index in range(7):
            parameter = index / 6
            fraction = lower + (upper - lower) * parameter
            offset = middle + side * fraction * width if arm else fraction
            normal = (1, 0, 0) if arm else (0, 0, 1)
            groups = _volume_sections(normalized, triangles, normal, offset)
            if side and not arm:
                lateral = [group for group in groups if side * (_volume_center(group)[0] - middle) > 0]
                groups = lateral or groups
            if not groups:
                continue
            if arm:
                group = max(groups, key=lambda candidate: _volume_center(candidate)[2])
            elif side:
                group = max(groups, key=lambda candidate: side * (_volume_center(candidate)[0] - middle))
            else:
                group = min(groups, key=lambda candidate: abs(_volume_center(candidate)[0] - middle))
            center = _volume_center(group)
            radius = max(math.dist(point, center) for point in group)
            samples.append({'t': parameter, 'center': list(center), 'radius': radius})
        if not samples:
            center = [middle + side * width * .25, extent[1] / extent[2] / 2, (lower + upper) / 2]
            samples = [{'t': 0, 'center': [*center[:2], lower], 'radius': extent[1] / extent[2] / 2},
                       {'t': 1, 'center': [*center[:2], upper], 'radius': extent[1] / extent[2] / 2}]
        if arm and len(samples) > 1:
            direction = _volume_unit(tuple(samples[-1]['center'][axis] - samples[0]['center'][axis]
                                           for axis in range(3)))
            for sample in samples:
                groups = _volume_sections(normalized, triangles, direction,
                                          _volume_dot(sample['center'], direction))
                if groups:
                    group = min(groups, key=lambda candidate: math.dist(_volume_center(candidate), sample['center']))
                    center = _volume_center(group)
                    sample['center'] = list(center)
                    sample['radius'] = max(math.dist(point, center) for point in group)
        start, end = samples[0]['t'], samples[-1]['t']
        if len(samples) == 1:
            duplicate = dict(samples[0], t=1)
            duplicate['center'] = list(samples[0]['center'])
            duplicate['center'][2] += .001
            samples[0]['t'] = 0
            samples.append(duplicate)
        else:
            for sample in samples:
                sample['t'] = (sample['t'] - start) / (end - start)
        for sample in samples:
            sample['center'] = [sample['center'][axis] * extent[2] / extent[axis] for axis in range(3)]
        measured_lower = min(sample['center'][2] for sample in samples)
        measured_upper = max(sample['center'][2] for sample in samples)
        if measured_upper - measured_lower < 1e-6:
            measured_lower = max(0, measured_lower - samples[0]['radius'])
            measured_upper = min(1, measured_upper + samples[0]['radius'])
        names = ('front', 'front_side', 'side', 'back_side', 'back',
                 'opposite_back_side', 'opposite_side', 'opposite_front_side')
        volumes.append({'id': identity, 'lower': measured_lower, 'upper': measured_upper,
                        'measured_lower': measured_lower, 'measured_upper': measured_upper,
                        'radius_scale': 1.0, 'samples': samples,
                        'points': [{'id': name, 'angle': index * math.pi / 4, 'height': .5}
                                   for index, name in enumerate(names)]})
    return {'version': 1, 'clearance': clearance / extent[2],
            'aspect': [extent[0] / extent[2], extent[1] / extent[2]], 'volumes': volumes}


def _volume_validate(setup):
    try:
        if setup['version'] != 1 or not math.isfinite(setup['clearance']) or setup['clearance'] < 0:
            raise ValueError
        if len(setup['aspect']) != 2 or any(not math.isfinite(value) or value <= 0 for value in setup['aspect']):
            raise ValueError
        identities = set()
        for volume in setup['volumes']:
            if not isinstance(volume['id'], str) or not volume['id'] or volume['id'] in identities:
                raise ValueError
            identities.add(volume['id'])
            for prefix in ('', 'measured_'):
                lower, upper = volume[prefix + 'lower'], volume[prefix + 'upper']
                if not 0 <= lower < upper <= 1:
                    raise ValueError
            if not math.isfinite(volume['radius_scale']) or volume['radius_scale'] <= 0:
                raise ValueError
            if not isinstance(volume.get('next_point_id', 1), int) or volume.get('next_point_id', 1) < 1:
                raise ValueError
            previous = -1
            for sample in volume['samples']:
                if not previous < sample['t'] <= 1 or sample['t'] < 0:
                    raise ValueError
                previous = sample['t']
                if len(sample['center']) != 3 or not all(math.isfinite(value) for value in sample['center']):
                    raise ValueError
                if not math.isfinite(sample['radius']) or sample['radius'] <= 0:
                    raise ValueError
            if len(volume['samples']) < 2 or volume['samples'][0]['t'] != 0 or previous != 1:
                raise ValueError
            point_ids = set()
            for point in volume['points']:
                if not isinstance(point['id'], str) or not point['id'] or point['id'] in point_ids:
                    raise ValueError
                point_ids.add(point['id'])
                if not math.isfinite(point['angle']) or not 0 <= point['height'] <= 1:
                    raise ValueError
        if not identities:
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError('Invalid avatar arrangement volumes; explicitly regenerate avatar setup.') from error
    return setup


def _volume_avatar(context):
    avatar = context.scene.dd_avatar
    if avatar is None or avatar.type != 'MESH' or avatar not in list(context.scene.objects):
        raise ValueError('Choose an avatar body mesh in the current scene.')
    if avatar.get('dd_kind') in {'panel', 'simulation', 'final', 'anchor'}:
        raise ValueError('Arrangement volumes belong to an avatar, not a garment.')
    return avatar


def _volume_axes(matrix):
    up = _volume_unit(tuple(matrix[row][2] for row in range(3)))
    horizontal = tuple(matrix[row][0] for row in range(3))
    projection = _volume_dot(horizontal, up)
    right = _volume_unit(tuple(horizontal[axis] - projection * up[axis] for axis in range(3)))
    return (right, _volume_cross(up, right), up)


def _volume_mesh(context, avatar):
    evaluated = avatar.evaluated_get(context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        vertices = [tuple(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        axes = _volume_axes(evaluated.matrix_world)
        vertices = [tuple(_volume_dot(point, axis) for axis in axes) for point in vertices]
        _volume_bounds(vertices)
        return vertices, triangles, axes
    finally:
        evaluated.to_mesh_clear()


def _volume_frame(context):
    avatar=_volume_avatar(context)
    evaluated=avatar.evaluated_get(context.evaluated_depsgraph_get())
    if not hasattr(evaluated,'bound_box'):
        vertices,triangles,axes=_volume_mesh(context,avatar)
        return (*_volume_bounds(vertices),axes)
    from mathutils import Vector
    axes=_volume_axes(evaluated.matrix_world)
    corners=[evaluated.matrix_world @ Vector(point) for point in evaluated.bound_box]
    projected=[tuple(_volume_dot(point,axis) for axis in axes) for point in corners]
    return (*_volume_bounds(projected),axes)


def ensure_volumes(context, force=False):
    avatar = _volume_avatar(context)
    stored = avatar.get('dd_arrangement_volumes')
    if stored is not None and not force:
        try:
            return _volume_validate(json.loads(stored))
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid avatar arrangement volumes JSON; explicitly regenerate avatar setup.') from error
    from . import garment

    unit = garment.metres_per_unit(context.scene)
    clearance = context.scene.dd_clearance
    if not math.isfinite(unit) or unit <= 0 or not math.isfinite(clearance) or clearance < 0:
        raise ValueError('Avatar clearance and scene unit scale must be finite and valid.')
    vertices, triangles, axes = _volume_mesh(context, avatar)
    setup = _volume_validate(generate_volumes(vertices, triangles, clearance / unit))
    avatar['dd_arrangement_volumes'] = json.dumps(setup, allow_nan=False)
    return setup


def _volume_find(setup, volume_id, point_id=None):
    volume = next((item for item in setup['volumes'] if item['id'] == volume_id), None)
    if volume is None:
        raise ValueError(f'Unknown avatar volume: {volume_id}.')
    if point_id is None:
        return volume
    point = next((item for item in volume['points'] if item['id'] == point_id), None)
    if point is None:
        raise ValueError(f'Unknown point {point_id} on avatar volume {volume_id}.')
    return volume, point


def _volume_resolve(setup, volume, point, low, extent, axes):
    parameter = point['height']
    samples = volume['samples']
    first, second = samples[-2:]
    for start, end in zip(samples, samples[1:]):
        if parameter <= end['t']:
            first, second = start, end
            break
    factor = (parameter - first['t']) / (second['t'] - first['t'])

    def world_center(sample):
        center = list(sample['center'])
        center[2] = volume['lower'] + (center[2] - volume['measured_lower']) * (
            volume['upper'] - volume['lower']) / (volume['measured_upper'] - volume['measured_lower'])
        return tuple(low[axis] + center[axis] * extent[axis] for axis in range(3))

    start, end = world_center(first), world_center(second)
    center = tuple(start[axis] + factor * (end[axis] - start[axis]) for axis in range(3))
    up = _volume_unit(tuple(end[axis] - start[axis] for axis in range(3)))
    if up[2] < 0:
        up = tuple(-value for value in up)
    projection = -up[1]
    front = _volume_unit(tuple((0, -1, 0)[axis] - projection * up[axis] for axis in range(3)))
    right = _volume_cross(up, front)
    cosine, sine = math.cos(point['angle']), math.sin(point['angle'])
    normal = tuple(front[axis] * cosine + right[axis] * sine for axis in range(3))
    tangent = tuple(right[axis] * cosine - front[axis] * sine for axis in range(3))
    def sample_radius(sample, neighbor):
        aspect = (*setup['aspect'], 1)
        original_up = _volume_unit(tuple((neighbor['center'][axis] - sample['center'][axis]) * aspect[axis]
                                         for axis in range(3)))
        original_front = _volume_unit(tuple((0, -1, 0)[axis] + original_up[1] * original_up[axis]
                                            for axis in range(3)))
        original_right = _volume_cross(original_up, original_front)
        current_up = _volume_unit(tuple(world_center(neighbor)[axis] - world_center(sample)[axis]
                                        for axis in range(3)))
        transformed = []
        for vector in (original_front, original_right):
            scaled = tuple(vector[axis] * extent[axis] / aspect[axis] for axis in range(3))
            projection = _volume_dot(scaled, current_up)
            transformed.append(tuple(scaled[axis] - projection * current_up[axis] for axis in range(3)))
        first_square = _volume_dot(transformed[0], transformed[0])
        second_square = _volume_dot(transformed[1], transformed[1])
        product = _volume_dot(transformed[0], transformed[1])
        stretch = math.sqrt((first_square + second_square + math.hypot(first_square - second_square, 2 * product)) / 2)
        return sample['radius'] * stretch * volume['radius_scale'] + setup['clearance'] * extent[2]

    first_radius, second_radius = sample_radius(first, second), sample_radius(second, first)
    radius = first_radius + factor * (second_radius - first_radius)
    def world_vector(vector):
        return tuple(sum(vector[index] * axes[index][axis] for index in range(3)) for axis in range(3))

    geometry = {'id': volume['id'], 'lower': volume['lower'], 'upper': volume['upper'],
                'radius_scale': volume['radius_scale'], 'center': world_vector(center), 'axis': world_vector(up),
                'samples': [{'t': sample['t'], 'center': world_vector(world_center(sample)),
                             'radius': sample_radius(sample, samples[index + 1] if index + 1 < len(samples) else samples[index - 1])}
                            for index, sample in enumerate(samples)]}
    return {'point': world_vector(tuple(center[axis] + radius * normal[axis] for axis in range(3))),
            'normal': world_vector(normal), 'tangent': world_vector(tangent), 'up': world_vector(up),
            'radius': radius, 'volume': geometry}


def resolve_point(context, volume_id, point_id):
    setup = ensure_volumes(context)
    volume, point = _volume_find(setup, volume_id, point_id)
    return _volume_resolve(setup, volume, point, *_volume_frame(context))


def world_points(context):
    setup = ensure_volumes(context)
    low,extent,axes=_volume_frame(context)
    result=[]
    for volume in setup['volumes']:
        for point in volume['points']:
            resolved=_volume_resolve(setup,volume,point,low,extent,axes)
            result.append(dict(volume=volume['id'],point=point['id'],position=resolved['point'],
                               geometry=resolved['volume'],normal=resolved['normal'],tangent=resolved['tangent']))
    return result


def edit_point(context, volume_id, point_id, angle=None, height=None, action='MOVE'):
    setup = ensure_volumes(context)
    volume = _volume_find(setup, volume_id)
    if action not in {'MOVE', 'ADD', 'DELETE'}:
        raise ValueError('Choose MOVE, ADD, or DELETE for an avatar point.')
    if angle is not None and not math.isfinite(angle):
        raise ValueError('Point angle must be finite radians.')
    if height is not None and (not math.isfinite(height) or not 0 <= height <= 1):
        raise ValueError('Point height must be a fraction between zero and one.')
    if action == 'ADD':
        point_ids = {point['id'] for point in volume['points']}
        index = volume.get('next_point_id', 1)
        while f'custom_{index}' in point_ids:
            index += 1
        point_id = f'custom_{index}'
        volume['next_point_id'] = index + 1
        point = {'id': point_id, 'angle': 0.0, 'height': .5}
        volume['points'].append(point)
    else:
        volume, point = _volume_find(setup, volume_id, point_id)
    if action == 'DELETE':
        volume['points'].remove(point)
    else:
        if angle is not None:
            point['angle'] = angle % math.tau
        if height is not None:
            point['height'] = height
    _volume_avatar(context)['dd_arrangement_volumes'] = json.dumps(_volume_validate(setup), allow_nan=False)
    return point_id


def edit_volume(context, volume_id, lower, upper, radius_scale):
    if (not all(math.isfinite(value) for value in (lower, upper, radius_scale))
            or not 0 <= lower < upper <= 1 or radius_scale <= 0):
        raise ValueError('Volume bounds must satisfy 0 <= lower < upper <= 1 and radius scale must be positive.')
    setup = ensure_volumes(context)
    volume = _volume_find(setup, volume_id)
    volume.update(lower=lower, upper=upper, radius_scale=radius_scale)
    _volume_avatar(context)['dd_arrangement_volumes'] = json.dumps(_volume_validate(setup), allow_nan=False)
    return setup


MODES = ('BODICE', 'SLEEVES', 'SKIRT')


@dataclass(frozen=True)
class Placement:
    pattern_id: str
    point: tuple
    normal: tuple


def layout_plan(pieces, body_bounds, mode):
    if mode not in MODES:
        raise ValueError('Choose BODICE, SLEEVES, or SKIRT.')
    pieces = tuple(pieces)
    if not pieces:
        raise ValueError('Draw at least one closed pattern first.')
    identities = set()
    for pattern_id, name in pieces:
        if not isinstance(pattern_id, str) or not pattern_id or pattern_id in identities:
            raise ValueError('Every piece needs a unique pattern ID.')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Every piece needs a name.')
        identities.add(pattern_id)
    if len(body_bounds) != 2 or any(len(corner) != 3 for corner in body_bounds):
        raise ValueError('Avatar bounds need two three-dimensional corners.')
    low, high = body_bounds
    if any(not math.isfinite(value) for corner in body_bounds for value in corner):
        raise ValueError('Avatar bounds must be finite.')
    extent = tuple(high[axis] - low[axis] for axis in range(3))
    if any(not math.isfinite(value) or value <= 0 for value in extent):
        raise ValueError('Avatar bounds must have positive width, depth, and height.')
    center = tuple(low[axis] + extent[axis] * .5 for axis in range(3))
    ordered = sorted(pieces, key=lambda piece: (piece[1].casefold(), piece[0]))
    result = []
    if mode == 'SKIRT':
        if len(pieces) < 2:
            raise ValueError('Skirt arrangement needs at least two panels.')
        for index, (pattern_id, name) in enumerate(ordered):
            angle = -math.pi / 2 + math.tau * index / len(ordered)
            horizontal, depth = math.cos(angle), math.sin(angle)
            normal = (horizontal * extent[1], depth * extent[0], 0)
            length = math.hypot(*normal)
            result.append(Placement(pattern_id,
                (center[0] + horizontal * extent[0] * .5,
                 center[1] + depth * extent[1] * .5, low[2] + extent[2] * .43),
                tuple(value / length for value in normal)))
        return tuple(result)
    labels = ('front', 'back') if mode == 'BODICE' else ('left', 'right')
    groups = {label: [] for label in labels}
    unlabeled = []
    for piece in ordered:
        tokens = set(re.findall(r'[a-z]+', piece[1].casefold()))
        matches = tokens.intersection(labels)
        if len(matches) > 1:
            raise ValueError(f'Conflicting {mode.lower()} labels: {", ".join(labels)}. Use at most one per piece.')
        if matches:
            groups[matches.pop()].append(piece)
        else:
            unlabeled.append(piece)
    for piece in unlabeled:
        label = min(labels, key=lambda candidate: len(groups[candidate]))
        groups[label].append(piece)
    for label in labels:
        group = sorted(groups[label], key=lambda piece: (piece[1].casefold(), piece[0]))
        for index, (pattern_id, name) in enumerate(group):
            offset = (index + .5) / len(group) - .5
            if mode == 'BODICE':
                side = -1 if label == 'front' else 1
                point = (center[0] + offset * extent[0] * .4,
                         low[1] if side < 0 else high[1], low[2] + extent[2] * .72)
                normal = (0, side, 0)
            else:
                side = 1 if label == 'left' else -1
                point = (center[0] + side * extent[0] * .36,
                         low[1], low[2] + extent[2] * (.78 + offset * .16))
                normal = (0, -1, 0)
            result.append(Placement(pattern_id, point, normal))
    return tuple(result)


def arrange(context, mode):
    from mathutils import Vector
    from . import garment, placement

    scene = context.scene
    avatar = scene.dd_avatar
    if avatar is None:
        raise ValueError('Choose your avatar body mesh first.')
    if (avatar.type != 'MESH' or avatar not in list(scene.objects)
            or avatar.get('dd_kind') in {'panel', 'simulation', 'final', 'anchor'}
            or not avatar.data.vertices):
        raise ValueError('Choose an avatar body mesh in the current scene.')
    document = garment.document(scene)
    if any(piece.placement_mode!='LEGACY' or piece.arrangement for piece in document.patterns):
        raise ValueError('Select a piece and click an arrangement point. Named layouts are only for older designs.')
    document.validate()
    document.validate_seams()
    for value, label in ((scene.dd_spacing, 'Pattern spacing'),
                         (scene.unit_settings.scale_length, 'Scene unit scale')):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{label} must be positive and finite.')
    if not math.isfinite(scene.dd_clearance) or scene.dd_clearance < 0:
        raise ValueError('Body clearance must be nonnegative and finite.')
    plan = layout_plan(((piece.id, piece.name) for piece in document.patterns),
                       garment.bounds(avatar), mode)
    unit = garment.metres_per_unit(scene)
    gap = scene.dd_clearance / unit
    if not math.isfinite(gap) or any(not math.isfinite(coordinate + normal * gap)
            for target in plan for coordinate, normal in zip(target.point, target.normal)):
        raise ValueError('Arrangement coordinates must be finite.')
    panels = garment.generated(scene, 'panel')
    panel_ids = [panel.get('dd_pattern_id') for panel in panels]
    if len(set(panel_ids)) != len(panel_ids):
        raise ValueError('Generated panels have duplicate pattern IDs; rebuild them first.')
    serialized = document.dumps()
    if (set(panel_ids) != {target.pattern_id for target in plan}
            or any(panel.type != 'MESH' or not panel.data.vertices
                   or panel.get('dd_document') != serialized
                   or panel.get('dd_spacing') != scene.dd_spacing
                   or panel.get('dd_units') != unit for panel in panels)):
        panels = garment.build_panels(context)
    by_id = {panel.get('dd_pattern_id'): panel for panel in panels}
    if len(by_id) != len(plan) or set(by_id) != {target.pattern_id for target in plan}:
        raise ValueError('Generated panels do not match the arrangement pieces.')
    previous = [(panel, panel.matrix_world.copy()) for panel in panels]
    low, high = garment.bounds(avatar)
    ref_y = getattr(scene, 'dd_reference_y', 0.0)
    placed = getattr(scene, 'dd_reference_placed', False)
    try:
        for target in plan:
            target_pt = list(target.point)
            pattern = document.find(target.pattern_id)
            if pattern and pattern.points and placed:
                cy = (min(v[1] for v in pattern.points) + max(v[1] for v in pattern.points)) / 2
                if cy > ref_y:
                    target_pt[2] = low[2] + (cy - ref_y) / unit
            placement.place(context, target.pattern_id, Vector(tuple(target_pt)), Vector(target.normal))
    except Exception:
        for panel, matrix in previous:
            panel.matrix_world = matrix
        context.view_layer.update()
        raise
    return len(plan)
