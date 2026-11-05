import bisect
import math
import numpy
from .arrangement import _volume_cross, _volume_dot, _volume_unit


def section_basis(up):
    up = _volume_unit(up)
    reference = (0, -1, 0) if abs(up[1]) < .99 else (0, 0, 1)
    projection = _volume_dot(reference, up)
    front = _volume_unit(tuple(reference[axis] - projection * up[axis] for axis in range(3)))
    return _volume_cross(up, front), front


def fit_section(points, center, up):
    side, front = section_basis(up)
    offsets = numpy.asarray(points, dtype=float) - numpy.asarray(center, dtype=float)
    coordinates = offsets @ numpy.array((side, front), dtype=float).T
    radii = numpy.maximum(numpy.abs(coordinates).max(axis=0), 1e-8)
    scale = float(numpy.hypot(coordinates[:, 0] / radii[0], coordinates[:, 1] / radii[1]).max())
    return [float(radius) * max(scale, 1) for radius in radii], [list(side), list(front)]


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
            scales = (neighbor.get('width_scale', neighbor['radius_scale']), neighbor.get('depth_scale', neighbor['radius_scale']))
            vectors = [world(tuple(basis[axis] * radius * extent[axis] / aspect[axis] * scale
                                   for axis in range(3))) for basis, radius, scale in zip(sample['basis'], sample['radii'], scales)]
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


def resolve_ellipse(setup, volume, point, low, extent, axes, clearance=None):
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
    clearance = setup['clearance'] * extent[2] if clearance is None else clearance
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


SURFACE_ANGLES = 512
SURFACE_SLOPE = 2.5


def _row_sections(entries, heights, up, right, front):
    up = numpy.asarray(up, dtype=float)
    ordered = sorted(entries, key=lambda entry: _volume_dot(entry['center'], tuple(up)))
    levels = numpy.array([_volume_dot(entry['center'], tuple(up)) for entry in ordered])
    centers = numpy.array([entry['center'] for entry in ordered], dtype=float)
    vectors = numpy.array([entry['vectors'] for entry in ordered], dtype=float)
    upper = numpy.searchsorted(levels, heights, side='right')
    first = numpy.maximum(upper - 1, 0)
    second = numpy.minimum(upper, len(ordered) - 1)
    difference = levels[second] - levels[first]
    usable = difference > 1e-12
    factor = numpy.where(usable, (heights - levels[first]) / numpy.where(usable, difference, 1), 0)
    center = centers[first] + factor[:, None] * (centers[second] - centers[first])
    center += (heights - center @ up)[:, None] * up
    vector = vectors[first] + factor[:, None, None] * (vectors[second] - vectors[first])
    vector -= (vector @ up)[:, :, None] * up
    side, depth = vector[:, 0], vector[:, 1]
    side_square, depth_square = (side * side).sum(axis=1), (depth * depth).sum(axis=1)
    product = (side * depth).sum(axis=1)
    determinant = side_square * depth_square - product * product
    if (determinant <= 1e-24).any():
        raise ValueError('Avatar ellipse has a degenerate section.')
    coordinates = []
    for direction in (right, front):
        direction = numpy.asarray(direction, dtype=float)
        side_dot, depth_dot = side @ direction, depth @ direction
        coordinates.append(((depth_square * side_dot - product * depth_dot) / determinant,
                            (side_square * depth_dot - product * side_dot) / determinant))
    metrics = numpy.stack((coordinates[0][0] ** 2 + coordinates[0][1] ** 2,
                           2 * (coordinates[0][0] * coordinates[1][0] + coordinates[0][1] * coordinates[1][1]),
                           coordinates[1][0] ** 2 + coordinates[1][1] ** 2), axis=1)
    return center, metrics


def surface_positions(vertices, resolved, step, minimum_clearance, overwrap=False, direction=1, extra=0.0, half_wrap=False):
    points = numpy.asarray(vertices, dtype=float)
    up, right, front = (tuple(resolved[key]) for key in ('up', 'right', 'front'))
    clearance = resolved['clearance'] + extra
    horizontal, vertical = points[:, 0], points[:, 1]
    below = int(math.ceil((max(-vertical.min(), 0) + clearance) / step)) + 1
    above = int(math.ceil((max(vertical.max(), 0) + clearance) / step)) + 1
    heights = resolved['height'] + step * numpy.arange(-below, above + 1)
    centers, metrics = _row_sections(resolved['stack'], heights, up, right, front)
    count = SURFACE_ANGLES
    angles = numpy.arange(count) * math.tau / count
    sine, cosine = numpy.sin(angles), numpy.cos(angles)
    radius = 1 / numpy.sqrt(metrics[:, :1] * sine * sine + metrics[:, 1:2] * sine * cosine + metrics[:, 2:] * cosine * cosine)
    slope = (numpy.roll(radius, -1, axis=1) - numpy.roll(radius, 1, axis=1)) / (2 * math.tau / count)
    gain = numpy.minimum(numpy.sqrt(1 + (slope / radius) ** 2), 3)
    planar = centers @ numpy.stack((right, front), axis=1)
    required = radius + gain * clearance
    rows = len(heights)
    for offset in range(1, min(int(clearance // step), rows - 1) + 1):
        rise = math.sqrt(max(clearance * clearance - (offset * step) ** 2, 0))
        for target, source in ((slice(0, rows - offset), slice(offset, rows)), (slice(offset, rows), slice(0, rows - offset))):
            delta = planar[source] - planar[target]
            candidate = radius[source] + delta[:, :1] * sine + delta[:, 1:] * cosine + gain[source] * rise
            required[target] = numpy.maximum(required[target], candidate)
    ramp = (SURFACE_SLOPE * step * numpy.arange(rows))[:, None]
    required = numpy.maximum(numpy.maximum.accumulate(required + ramp, axis=0) - ramp,
                             numpy.maximum.accumulate((required - ramp)[::-1], axis=0)[::-1] + ramp)
    directions = sine[:, None] * numpy.asarray(right) + cosine[:, None] * numpy.asarray(front)
    curves = centers[:, None, :] + required[:, :, None] * directions[None, :, :]
    closed = numpy.concatenate((curves, curves[:, :1]), axis=1)
    segments = numpy.linalg.norm(closed[:, 1:] - closed[:, :-1], axis=2)
    lengths = numpy.concatenate((numpy.zeros((rows, 1)), numpy.cumsum(segments, axis=1)), axis=1)
    perimeters = lengths[:, -1]
    phase_index = (resolved['angle'] % math.tau) * count / math.tau
    whole = min(int(phase_index), count - 1)
    phases = lengths[:, whole] + (phase_index - whole) * segments[:, whole]
    columns = numpy.arange(horizontal.min(), horizontal.max() + step, step)
    if len(columns) < 2:
        columns = numpy.array([horizontal.min(), horizontal.min() + step])
    row_numbers = numpy.arange(rows)
    spread = float(perimeters.max()) * 4 + 1
    queries = (columns[None, :] + phases[:, None]) % perimeters[:, None]
    found = numpy.searchsorted((lengths + row_numbers[:, None] * spread).ravel(),
                               (queries + row_numbers[:, None] * spread).ravel(), side='right') - 1
    lower = numpy.clip(found.reshape(rows, -1) - row_numbers[:, None] * (count + 1), 0, count - 1)
    owner = numpy.broadcast_to(row_numbers[:, None], lower.shape)
    weight = ((queries - lengths[owner, lower]) / numpy.maximum(segments[owner, lower], 1e-15))[:, :, None]
    grid = closed[owner, lower] + weight * (closed[owner, lower + 1] - closed[owner, lower])
    meridian = numpy.concatenate((numpy.zeros((1, len(columns))), numpy.cumsum(
        numpy.linalg.norm(grid[1:] - grid[:-1], axis=2), axis=0)), axis=0)
    meridian -= meridian[below]
    place = numpy.clip((horizontal - columns[0]) / step, 0, len(columns) - 1 - 1e-9)
    left = place.astype(int)
    blend = (place - left)[:, None]
    reach = float(numpy.abs(meridian).max()) * 4 + 1
    stacked = (meridian.T + numpy.arange(len(columns))[:, None] * reach).ravel()
    steps = numpy.diff(meridian, axis=0)
    def along(column_indices, heights):
        clamped = numpy.clip(heights, meridian[0, column_indices], meridian[-1, column_indices])
        found = numpy.searchsorted(stacked, clamped + column_indices * reach, side='right') - 1
        lower = numpy.clip(found - column_indices * rows, 0, rows - 2)
        fraction = lower + (clamped - meridian[lower, column_indices]) / numpy.maximum(steps[lower, column_indices], 1e-15)
        lower = numpy.minimum(fraction.astype(int), rows - 2)
        weight = (fraction - lower)[:, None]
        return (grid[lower, column_indices] + weight * (grid[lower + 1, column_indices] - grid[lower, column_indices]),
                lower + weight[:, 0])
    def locate(across, heights):
        place = numpy.clip((across - columns[0]) / step, 0, len(columns) - 1 - 1e-9)
        left = place.astype(int)
        blend = (place - left)[:, None]
        first, first_rows = along(left, heights)
        second, second_rows = along(numpy.minimum(left + 1, len(columns) - 1), heights)
        return first + blend * (second - first), first_rows + blend[:, 0] * (second_rows - first_rows)
    positions, row_position = locate(horizontal, vertical)
    row_index = numpy.clip(numpy.rint(row_position).astype(int), 0, rows - 1)
    if half_wrap:
        limit = perimeters[row_index] / 4
        beyond = numpy.abs(horizontal) > limit
        if beyond.any():
            edge, _ = locate(numpy.sign(horizontal[beyond]) * limit[beyond], vertical[beyond])
            outward = edge - centers[row_index[beyond]]
            outward -= (outward @ numpy.asarray(up))[:, None] * numpy.asarray(up)[None, :]
            outward /= numpy.maximum(numpy.linalg.norm(outward, axis=1), 1e-12)[:, None]
            positions[beyond] = edge + outward * (numpy.abs(horizontal[beyond]) - limit[beyond])[:, None]
    bands = numpy.rint(vertical / step).astype(int)
    starts, ends = {}, {}
    for band, value in zip(bands.tolist(), horizontal.tolist()):
        starts[band] = min(starts.get(band, value), value)
        ends[band] = max(ends.get(band, value), value)
    widths = numpy.array([ends[band] - starts[band] for band in bands.tolist()])
    if (widths > perimeters[row_index] * (1 - 1e-9)).any():
        if not overwrap:
            raise ValueError('The piece is wider than the body around this point. Right-click it and choose Allow overwrap, or arrange it Flat.')
        origin = numpy.array([starts[band] if direction > 0 else ends[band] for band in bands.tolist()])
        layers = numpy.abs(horizontal - origin) / perimeters[row_index]
        center = centers[row_index]
        radial = positions - center
        radial -= (radial @ numpy.asarray(up))[:, None] * numpy.asarray(up)[None, :]
        radial /= numpy.maximum(numpy.linalg.norm(radial, axis=1), 1e-12)[:, None]
        positions = positions + radial * (max(clearance, minimum_clearance) * layers)[:, None]
    return positions
