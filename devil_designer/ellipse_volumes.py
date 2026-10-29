import bisect
import math
from .arrangement import _volume_cross, _volume_dot, _volume_unit


def section_basis(up):
    up = _volume_unit(up)
    reference = (0, -1, 0) if abs(up[1]) < .99 else (0, 0, 1)
    projection = _volume_dot(reference, up)
    front = _volume_unit(tuple(reference[axis] - projection * up[axis] for axis in range(3)))
    return _volume_cross(up, front), front


def fit_section(points, center, up):
    side, front = section_basis(up)
    coordinates = [tuple(_volume_dot(tuple(point[axis] - center[axis] for axis in range(3)), basis)
                         for basis in (side, front)) for point in points]
    radii = tuple(max(abs(point[axis]) for point in coordinates) for axis in range(2))
    radii = tuple(max(radius, 1e-8) for radius in radii)
    scale = max(math.hypot(point[0] / radii[0], point[1] / radii[1]) for point in coordinates)
    return [radius * max(scale, 1) for radius in radii], [list(side), list(front)]


def volume_family(identity):
    if 'arm' in identity:
        return identity.split('_')[0] + '_arm'
    if 'thigh' in identity or 'calf' in identity:
        return identity.split('_')[0] + '_leg'
    return 'torso'


def volume_stack(setup, volume, low, extent, axes):
    aspect = (*setup['aspect'], 1)

    def world(vector):
        return tuple(sum(vector[index] * axes[index][axis] for index in range(3)) for axis in range(3))

    entries = []
    for neighbor in setup['volumes']:
        if volume_family(neighbor['id']) != volume_family(volume['id']):
            continue
        for sample in neighbor['samples']:
            center = list(sample['center'])
            center[2] = neighbor['lower'] + (center[2] - neighbor['measured_lower']) * (
                neighbor['upper'] - neighbor['lower']) / (neighbor['measured_upper'] - neighbor['measured_lower'])
            vectors = [world(tuple(basis[axis] * radius * extent[axis] / aspect[axis] * neighbor['radius_scale']
                                   for axis in range(3))) for basis, radius in zip(sample['basis'], sample['radii'])]
            entries.append(dict(center=world(tuple(low[axis] + center[axis] * extent[axis] for axis in range(3))),
                                vectors=vectors, volume=neighbor['id'], t=sample['t']))
    return entries


def section_at_height(entries, height, up):
    ordered = sorted(entries, key=lambda entry: _volume_dot(entry['center'], up))
    heights = [_volume_dot(entry['center'], up) for entry in ordered]
    upper = bisect.bisect_right(heights, height)
    first = ordered[max(0, upper - 1)]
    second = ordered[min(len(ordered) - 1, upper)]
    difference = _volume_dot(second['center'], up) - _volume_dot(first['center'], up)
    factor = (height - _volume_dot(first['center'], up)) / difference if difference > 1e-12 else 0
    center = tuple(first['center'][axis] + factor * (second['center'][axis] - first['center'][axis]) for axis in range(3))
    correction = height - _volume_dot(center, up)
    center = tuple(center[axis] + correction * up[axis] for axis in range(3))
    vectors = []
    for start, end in zip(first['vectors'], second['vectors']):
        vector = tuple(start[axis] + factor * (end[axis] - start[axis]) for axis in range(3))
        projection = _volume_dot(vector, up)
        vectors.append(tuple(vector[axis] - projection * up[axis] for axis in range(3)))
    return dict(center=center, vectors=vectors)


def directional_radius(section, direction):
    side, front = section['vectors']
    side_square = _volume_dot(side, side)
    front_square = _volume_dot(front, front)
    product = _volume_dot(side, front)
    determinant = side_square * front_square - product * product
    if determinant <= 1e-24:
        raise ValueError('Avatar ellipse has a degenerate section.')
    side_dot = _volume_dot(direction, side)
    front_dot = _volume_dot(direction, front)
    side_coordinate = (front_square * side_dot - product * front_dot) / determinant
    front_coordinate = (side_square * front_dot - product * side_dot) / determinant
    return 1 / math.hypot(side_coordinate, front_coordinate)


def resolve_ellipse(setup, volume, point, low, extent, axes):
    entries = volume_stack(setup, volume, low, extent, axes)
    selected = [entry for entry in entries if entry['volume'] == volume['id']]
    first, second = selected[-2:]
    for start, end in zip(selected, selected[1:]):
        if point['height'] <= end['t']:
            first, second = start, end
            break
    factor = (point['height'] - first['t']) / (second['t'] - first['t'])
    center = tuple(first['center'][axis] + factor * (second['center'][axis] - first['center'][axis]) for axis in range(3))
    up = _volume_unit(tuple(second['center'][axis] - first['center'][axis] for axis in range(3)))
    if _volume_dot(up, axes[2]) < 0:
        up = tuple(-value for value in up)
    front_projection = _volume_dot(tuple(-value for value in axes[1]), up)
    front = _volume_unit(tuple(-axes[1][axis] - front_projection * up[axis] for axis in range(3)))
    right = _volume_cross(up, front)
    cosine, sine = math.cos(point['angle']), math.sin(point['angle'])
    normal = tuple(front[axis] * cosine + right[axis] * sine for axis in range(3))
    tangent = tuple(right[axis] * cosine - front[axis] * sine for axis in range(3))
    height = _volume_dot(center, up)
    section = section_at_height(entries, height, up)
    clearance = setup['clearance'] * extent[2]
    radius = directional_radius(section, normal) + clearance
    samples = []
    for entry in selected:
        sample_section = section_at_height(entries, _volume_dot(entry['center'], up), up)
        samples.append(dict(t=entry['t'], center=sample_section['center'], vectors=sample_section['vectors'],
                            radius=directional_radius(sample_section, normal) + clearance))
    geometry = dict(id=volume['id'], lower=volume['lower'], upper=volume['upper'], radius_scale=volume['radius_scale'],
                    center=section['center'], axis=up, samples=samples, clearance=clearance)
    return dict(point=tuple(section['center'][axis] + radius * normal[axis] for axis in range(3)), normal=normal,
                tangent=tangent, up=up, radius=radius, volume=geometry, stack=entries, height=height,
                angle=point['angle'], right=right, front=front, clearance=clearance)


def ellipse_ring(sample, clearance, up, count=32):
    side, front = section_basis(up)
    positions = []
    for index in range(count + 1):
        angle = math.tau * index / count
        direction = tuple(side[axis] * math.sin(angle) + front[axis] * math.cos(angle) for axis in range(3))
        radius = directional_radius(sample, direction) + clearance
        positions.append(tuple(sample['center'][axis] + direction[axis] * radius for axis in range(3)))
    return positions


def wrap_positions(vertices, resolved, width, minimum, minimum_clearance):
    up, right, front = resolved['up'], resolved['right'], resolved['front']
    entries = resolved['stack']
    cache = {}
    positions = []
    for horizontal, vertical, unused_depth in vertices:
        height = resolved['height'] + vertical
        if height not in cache:
            section = section_at_height(entries, height, up)
            side, depth = section['vectors']
            side_square = _volume_dot(side, side)
            depth_square = _volume_dot(depth, depth)
            product = _volume_dot(side, depth)
            determinant = side_square * depth_square - product * product
            if determinant <= 1e-24:
                raise ValueError('Avatar ellipse has a degenerate section.')
            coordinates = []
            for direction in (right, front):
                side_dot, depth_dot = _volume_dot(direction, side), _volume_dot(direction, depth)
                coordinates.append(((depth_square * side_dot - product * depth_dot) / determinant,
                                    (side_square * depth_dot - product * side_dot) / determinant))
            side_metric = math.hypot(*coordinates[0]) ** 2
            depth_metric = math.hypot(*coordinates[1]) ** 2
            mixed_metric = 2 * sum(first * second for first, second in zip(*coordinates))
            curve = []
            lengths = [0.0]
            for index in range(4097):
                angle = math.tau * index / 4096
                sine, cosine = math.sin(angle), math.cos(angle)
                direction = tuple(right[axis] * sine + front[axis] * cosine for axis in range(3))
                radius = 1 / math.sqrt(side_metric * sine * sine + mixed_metric * sine * cosine + depth_metric * cosine * cosine) + resolved['clearance']
                curve.append(tuple(radius * value for value in direction))
            for start, end in zip(curve, curve[1:]):
                lengths.append(lengths[-1] + math.dist(start, end))
            phase_index = (resolved['angle'] % math.tau) * 4096 / math.tau
            index = int(phase_index)
            phase = lengths[index] + (phase_index - index) * (lengths[index + 1] - lengths[index])
            cache[height] = section, curve, lengths, phase
        section, curve, lengths, phase = cache[height]
        distance = (horizontal + phase) % lengths[-1]
        index = min(bisect.bisect_right(lengths, distance) - 1, len(curve) - 2)
        factor = (distance - lengths[index]) / (lengths[index + 1] - lengths[index])
        offset = tuple(start + factor * (end - start) for start, end in zip(curve[index], curve[index + 1]))
        if width > lengths[-1]:
            extra = max(resolved['clearance'], minimum_clearance) * (horizontal - minimum) / lengths[-1]
            length = math.hypot(*offset)
            offset = tuple(value * (1 + extra / length) for value in offset)
        positions.append(tuple(section['center'][axis] + offset[axis] for axis in range(3)))
    return positions
