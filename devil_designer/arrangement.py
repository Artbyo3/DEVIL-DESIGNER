import hashlib
import math
import json
import re
import time
from dataclasses import dataclass, field
import numpy


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
    points = numpy.asarray(vertices, dtype=float).reshape(-1, 3)
    faces = numpy.asarray(triangles, dtype=numpy.int64).reshape(-1, 3)
    if not len(faces):
        return []
    corners = points[faces]
    distances = corners @ numpy.asarray(normal, dtype=float) - offset
    found = []
    owners = []
    for first, second in ((0, 1), (1, 2), (2, 0)):
        start, end = corners[:, first], corners[:, second]
        start_distance, end_distance = distances[:, first], distances[:, second]
        touching = numpy.abs(start_distance) < 1e-9
        crossing = start_distance * end_distance < 0
        factor = (start_distance[crossing] / (start_distance[crossing] - end_distance[crossing]))[:, None]
        found.extend((start[touching], start[crossing] + factor * (end[crossing] - start[crossing])))
        owners.extend((numpy.nonzero(touching)[0], numpy.nonzero(crossing)[0]))
    found = numpy.concatenate(found)
    owners = numpy.concatenate(owners)
    if not len(found):
        return []
    _, unique, inverse = numpy.unique(numpy.round(found, 8), axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    order = numpy.argsort(owners, kind='stable')
    linked = owners[order][1:] == owners[order][:-1]
    first, second = inverse[order][:-1][linked], inverse[order][1:][linked]
    labels = numpy.arange(len(unique))
    while len(first):
        lowest = numpy.minimum(labels[first], labels[second])
        updated = labels.copy()
        numpy.minimum.at(updated, first, lowest)
        numpy.minimum.at(updated, second, lowest)
        updated = updated[updated]
        if (updated == labels).all():
            break
        labels = updated
    groups = {}
    for index in numpy.argsort(unique, kind='stable').tolist():
        groups.setdefault(int(labels[index]), []).append(unique[index])
    return [found[members] for members in groups.values() if len(members) >= 3]


def _volume_center(points):
    points = numpy.asarray(points, dtype=float)
    return tuple(float(value) for value in (points.min(axis=0) + points.max(axis=0)) / 2)


def _volume_reach(points, center):
    return float(numpy.linalg.norm(numpy.asarray(points, dtype=float) - numpy.asarray(center, dtype=float), axis=1).max())


VOLUME_SPECIFICATIONS = (('neck', .83, .90), ('chest', .66, .80), ('waist', .53, .65),
                         ('hip', .43, .54), ('left_upper_arm', .15, .32),
                         ('right_upper_arm', .15, .32), ('left_forearm', .32, .48),
                         ('right_forearm', .32, .48), ('left_thigh', .25, .45),
                         ('right_thigh', .25, .45), ('left_calf', .04, .25),
                         ('right_calf', .04, .25))
POINT_NAMES = ('front', 'front_side', 'side', 'back_side', 'back',
               'opposite_back_side', 'opposite_side', 'opposite_front_side')
ADAPTIVE_FAMILIES = (('neck', 'chest', 'waist', 'hip'), ('left_thigh', 'left_calf'), ('right_thigh', 'right_calf'))
ADAPTIVE_LIMIT = 24
ADAPTIVE_TOLERANCE = .001
SLICE_SECONDS = .005
MIRROR_TOLERANCE = 1e-4


class FitPending(ValueError):
    pass


def _array_bounds(points):
    if points.ndim != 2 or points.shape[1] != 3 or not len(points) or not numpy.isfinite(points).all():
        raise ValueError('Avatar vertices must contain finite three-dimensional points.')
    low = points.min(axis=0)
    extent = points.max(axis=0) - low
    if extent.min() <= 0 or not numpy.isfinite(extent).all():
        raise ValueError('Avatar bounds must have positive finite width, depth, and height.')
    return tuple(float(value) for value in low), tuple(float(value) for value in extent)


class _BodyIndex:
    def __init__(self, normalized, triangles):
        self.points = normalized
        self.triangles = triangles
        self.ranges = {}
        order = numpy.argsort(normalized[:, 2], kind='stable')
        self.order = order
        self.heights = normalized[order, 2]

    def ensure(self, normal):
        key = tuple(round(value, 12) for value in normal)
        if key not in self.ranges:
            corners = (self.points @ numpy.asarray(normal, dtype=float))[self.triangles]
            self.ranges[key] = corners.min(axis=1), corners.max(axis=1)
        return self.ranges[key]

    def sections(self, normal, offset):
        low, high = self.ensure(normal)
        selected = numpy.nonzero((low <= offset + 1e-9) & (high >= offset - 1e-9))[0]
        return _volume_sections(self.points, self.triangles[selected], normal, offset)

    def slab(self, lower, upper):
        start = int(numpy.searchsorted(self.heights, lower, side='right'))
        end = int(numpy.searchsorted(self.heights, upper, side='left'))
        return self.points[self.order[start:end]]


def _choose_group(groups, identity, middle):
    arm = 'arm' in identity
    side = 1 if identity.startswith('left_') else -1 if identity.startswith('right_') else 0
    if side and not arm:
        lateral = [group for group in groups if side * (_volume_center(group)[0] - middle) > 0]
        groups = lateral or groups
    if not groups:
        return None, []
    if arm:
        group = max(groups, key=lambda candidate: _volume_center(candidate)[2])
    elif side:
        group = max(groups, key=lambda candidate: side * (_volume_center(candidate)[0] - middle))
    else:
        group = min(groups, key=lambda candidate: abs(_volume_center(candidate)[0] - middle))
    return group, [candidate for candidate in groups if candidate is not group]


def _section_sample(body, identity, fraction, middle, width):
    from .ellipse_volumes import fit_section
    arm = 'arm' in identity
    side = 1 if identity.startswith('left_') else -1 if identity.startswith('right_') else 0
    offset = middle + side * fraction * width if arm else fraction
    normal = (1, 0, 0) if arm else (0, 0, 1)
    group, others = _choose_group(body.sections(normal, offset), identity, middle)
    if group is None:
        return None
    center = _volume_center(group)
    radii, basis = fit_section(group, center, normal)
    sample = {'center': list(center), 'radius': _volume_reach(group, center),
              'radii': radii, 'basis': basis}
    if not arm:
        sample['_others'] = [(_volume_center(other), *fit_section(other, _volume_center(other), normal))
                             for other in others]
    return sample


def _ellipse_ratio(points, center, radii, basis):
    offsets = points[:, :2] - numpy.asarray(center[:2], dtype=float)
    side = offsets @ numpy.asarray(basis[0][:2], dtype=float)
    front = offsets @ numpy.asarray(basis[1][:2], dtype=float)
    return numpy.hypot(side / radii[0], front / radii[1]), numpy.hypot(side, front)


def _refine_family(body, raw, family, middle, width):
    from .ellipse_volumes import fit_section
    members = [identity for identity in family if raw[identity] and all('_others' in sample for sample in raw[identity])]
    if len(members) != len(family):
        return
    rejected = []
    for _ in range(ADAPTIVE_LIMIT):
        entries = sorted(((sample['center'][2], sample) for identity in members for sample in raw[identity]),
                         key=lambda entry: entry[0])
        best = None
        for (lower, first), (upper, second) in zip(entries, entries[1:]):
            if upper - lower < 1e-6:
                continue
            points = body.slab(lower, upper)
            if rejected and len(points):
                points = points[numpy.min(numpy.abs(points[:, 2:3] - numpy.asarray(rejected)[None, :]), axis=1) > 1e-6]
            if not len(points):
                continue
            factor = (points[:, 2] - lower) / (upper - lower)
            center = [first['center'][axis] + factor * (second['center'][axis] - first['center'][axis]) for axis in range(2)]
            radii = [first['radii'][axis] + factor * (second['radii'][axis] - first['radii'][axis]) for axis in range(2)]
            offsets = points[:, :2] - numpy.stack(center, axis=1)
            side = offsets @ numpy.asarray(first['basis'][0][:2], dtype=float)
            front = offsets @ numpy.asarray(first['basis'][1][:2], dtype=float)
            ratio = numpy.hypot(side / radii[0], front / radii[1])
            keep = ratio > 1
            for sample in (first, second):
                for other_center, other_radii, other_basis in sample['_others']:
                    other_ratio, _ = _ellipse_ratio(points, other_center, other_radii, other_basis)
                    keep &= ratio <= other_ratio
            escape = numpy.where(keep, (ratio - 1) * numpy.hypot(side, front) / numpy.maximum(ratio, 1e-12), 0)
            index = int(numpy.argmax(escape))
            if escape[index] > ADAPTIVE_TOLERANCE and (best is None or escape[index] > best[0]):
                best = (float(escape[index]), points[index])
        if best is None:
            return
        height = float(best[1][2])
        identity = min(members, key=lambda name: max(min(sample['center'][2] for sample in raw[name]) - height,
                                                     height - max(sample['center'][2] for sample in raw[name]), 0))
        sample = _section_sample(body, identity, height, middle, width)
        yield
        if sample is None:
            rejected.append(height)
            continue
        ratio, _ = _ellipse_ratio(best[1][None, :], sample['center'], sample['radii'], sample['basis'])
        if ratio[0] > 1 + 1e-6:
            rejected.append(height)
            continue
        lower, upper = next((low, high) for name, low, high in VOLUME_SPECIFICATIONS if name == identity)
        sample['t'] = (height - lower) / (upper - lower)
        sample['adaptive'] = True
        raw[identity].append(sample)
        raw[identity].sort(key=lambda item: item['t'])


def _fit_steps(vertices, triangles, clearance=0.03):
    from .ellipse_volumes import fit_section
    try:
        points = numpy.asarray(vertices, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError('Avatar vertices must contain finite three-dimensional points.') from error
    low, extent = _array_bounds(points)
    if not math.isfinite(clearance) or clearance < 0:
        raise ValueError('Avatar clearance must be nonnegative and finite.')
    try:
        faces = numpy.asarray(triangles)
    except ValueError as error:
        raise ValueError('Avatar triangles must contain three valid vertex indices.') from error
    if (faces.ndim != 2 or not len(faces) or faces.shape[1] != 3 or faces.dtype.kind not in 'iu'
            or faces.min() < 0 or faces.max() >= len(points)):
        raise ValueError('Avatar triangles must contain three valid vertex indices.')
    normalized = (points - numpy.asarray(low)) / extent[2]
    yield
    for start in range(0, len(faces), 8192):
        corners = normalized[faces[start:start + 8192]]
        if (numpy.linalg.norm(numpy.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1) > 1e-12).any():
            break
        yield
    else:
        raise ValueError('Avatar triangles must contain a nondegenerate surface.')
    yield
    body = _BodyIndex(normalized, faces)
    yield
    for normal in ((0, 0, 1), (1, 0, 0)):
        body.ensure(normal)
        yield
    width = extent[0] / extent[2]
    middle = width / 2
    raw = {}
    for identity, lower, upper in VOLUME_SPECIFICATIONS:
        raw[identity] = []
        for index in range(7):
            parameter = index / 6
            sample = _section_sample(body, identity, lower + (upper - lower) * parameter, middle, width)
            yield
            if sample is not None:
                sample['t'] = parameter
                raw[identity].append(sample)
    for family in ADAPTIVE_FAMILIES:
        yield from _refine_family(body, raw, family, middle, width)
    volumes = []
    for identity, lower, upper in VOLUME_SPECIFICATIONS:
        arm = 'arm' in identity
        side = 1 if identity.startswith('left_') else -1 if identity.startswith('right_') else 0
        samples = raw[identity]
        for sample in samples:
            sample.pop('_others', None)
        if not samples:
            center = [middle + side * width * .25, extent[1] / extent[2] / 2, (lower + upper) / 2]
            samples = [{'t': 0, 'center': [*center[:2], lower], 'radius': extent[1] / extent[2] / 2},
                       {'t': 1, 'center': [*center[:2], upper], 'radius': extent[1] / extent[2] / 2}]
            for sample in samples:
                sample.update(radii=[width / 2, extent[1] / extent[2] / 2], basis=[[1, 0, 0], [0, -1, 0]])
        if arm and len(samples) > 1:
            direction = _volume_unit(tuple(samples[-1]['center'][axis] - samples[0]['center'][axis]
                                           for axis in range(3)))
            body.ensure(direction)
            yield
            for sample in samples:
                groups = body.sections(direction, _volume_dot(sample['center'], direction))
                yield
                if groups:
                    group = min(groups, key=lambda candidate: math.dist(_volume_center(candidate), sample['center']))
                    center = _volume_center(group)
                    sample['center'] = list(center)
                    sample['radius'] = _volume_reach(group, center)
                    sample['radii'], sample['basis'] = fit_section(group, center, direction)
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
        volumes.append({'id': identity, 'lower': measured_lower, 'upper': measured_upper,
                        'measured_lower': measured_lower, 'measured_upper': measured_upper,
                        'radius_scale': 1.0, 'samples': samples,
                        'points': [{'id': name, 'angle': index * math.pi / 4, 'height': .5}
                                   for index, name in enumerate(POINT_NAMES)]})
    return {'version': 2, 'clearance': clearance / extent[2],
            'aspect': [extent[0] / extent[2], extent[1] / extent[2]], 'volumes': volumes}


def _volume_validate(setup):
    try:
        if type(setup['version']) is not int or setup['version'] not in (1, 2) or not math.isfinite(setup['clearance']) or setup['clearance'] < 0:
            raise ValueError
        if len(setup['aspect']) != 2 or any(not math.isfinite(value) or value <= 0 for value in setup['aspect']):
            raise ValueError
        if not isinstance(setup.get('fingerprint', ''), str):
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
            for key in ('radius_scale', 'width_scale', 'depth_scale'):
                value = volume.get(key, 1.0)
                if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
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
                if setup['version'] == 2:
                    if len(sample['radii']) != 2 or any(not math.isfinite(value) or value <= 0 for value in sample['radii']):
                        raise ValueError
                    if len(sample['basis']) != 2 or any(len(vector) != 3 or any(not math.isfinite(value) for value in vector)
                                                      or abs(math.hypot(*vector) - 1) > 1e-6 for vector in sample['basis']):
                        raise ValueError
                    if abs(_volume_dot(*sample['basis'])) > 1e-6:
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
        if 'legacy' in setup:
            if setup['version'] != 2 or setup['legacy']['version'] != 1 or 'legacy' in setup['legacy']:
                raise ValueError
            _volume_validate(setup['legacy'])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError('Invalid avatar arrangement volumes; explicitly regenerate avatar setup.') from error
    return setup


def _volume_avatar(context):
    avatar = context.scene.dd_avatar
    if avatar is None or avatar.type != 'MESH' or avatar not in list(context.scene.objects):
        raise ValueError('Choose an avatar body mesh in the current scene.')
    if avatar.get('dd_kind') in {'panel', 'simulation', 'final', 'anchor', 'collider'}:
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
        local = numpy.zeros(len(mesh.vertices) * 3, dtype=numpy.float32)
        mesh.vertices.foreach_get('co', local)
        faces = numpy.zeros(len(mesh.loop_triangles) * 3, dtype=numpy.int32)
        mesh.loop_triangles.foreach_get('vertices', faces)
        fingerprint = hashlib.sha256(local.tobytes() + faces.tobytes()).hexdigest()
        matrix = numpy.array([[evaluated.matrix_world[row][column] for column in range(4)] for row in range(3)], dtype=float)
        axes = _volume_axes(evaluated.matrix_world)
        world = local.reshape(-1, 3).astype(float) @ matrix[:, :3].T + matrix[:, 3]
        vertices = world @ numpy.asarray(axes, dtype=float).T
        _array_bounds(vertices)
        return vertices, faces.reshape(-1, 3), axes, fingerprint
    finally:
        evaluated.to_mesh_clear()


def _volume_frame(context):
    avatar=_volume_avatar(context)
    evaluated=avatar.evaluated_get(context.evaluated_depsgraph_get())
    if not hasattr(evaluated,'bound_box'):
        vertices,triangles,axes,_=_volume_mesh(context,avatar)
        return (*_array_bounds(vertices),axes)
    from mathutils import Vector
    axes=_volume_axes(evaluated.matrix_world)
    corners=[evaluated.matrix_world @ Vector(point) for point in evaluated.bound_box]
    projected=[tuple(_volume_dot(point,axis) for axis in axes) for point in corners]
    return (*_volume_bounds(projected),axes)


@dataclass
class FitJob:
    avatar: object
    scene: object
    fingerprint: str
    steps: object
    keep: bool
    completed: object = None
    state: str = 'pending'
    setup: dict = None
    error: str = ''
    slices: list = field(default_factory=list)
    timer_slices: list = field(default_factory=list)


_jobs = {}
_preparing = set()


def _clearance(context):
    from . import garment
    unit = garment.metres_per_unit(context.scene)
    clearance = context.scene.dd_clearance
    if not math.isfinite(unit) or unit <= 0 or not math.isfinite(clearance) or clearance < 0:
        raise ValueError('Avatar clearance and scene unit scale must be finite and valid.')
    return clearance / unit


def _retain_edits(setup, previous):
    for volume in setup['volumes']:
        match = next((item for item in previous['volumes'] if item['id'] == volume['id']), None)
        if match is None:
            continue
        for key in ('points', 'next_point_id', 'radius_scale', 'width_scale', 'depth_scale'):
            if key in match:
                volume[key] = match[key]
        if (match['lower'], match['upper']) != (match['measured_lower'], match['measured_upper']):
            volume['lower'], volume['upper'] = match['lower'], match['upper']
    if 'legacy' in previous:
        setup['legacy'] = previous['legacy']
    return setup


def _install(job):
    avatar = job.avatar
    try:
        if job.scene.dd_avatar != avatar:
            job.state = 'cancelled'
            return
        if job.keep and avatar.get('dd_arrangement_volumes') is not None:
            _retain_edits(job.setup, json.loads(avatar['dd_arrangement_volumes']))
        avatar['dd_arrangement_volumes'] = json.dumps(_volume_validate(job.setup), allow_nan=False)
        job.state = 'ready'
    except ReferenceError:
        job.state = 'cancelled'
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as failure:
        job.state = 'failed'
        job.error = str(failure)


def _advance(job, deadline):
    first = True
    while job.state == 'pending':
        started = time.perf_counter()
        if deadline is not None and not first and started + max(job.slices[-3:]) > deadline:
            break
        first = False
        try:
            next(job.steps)
        except StopIteration as finished:
            job.setup = finished.value
            job.setup['fingerprint'] = job.fingerprint
            _install(job)
        except (ValueError, ReferenceError) as failure:
            job.state = 'failed'
            job.error = str(failure)
        job.slices.append(time.perf_counter() - started)
        if deadline is not None and time.perf_counter() >= deadline:
            break
    if job.state != 'pending':
        if _jobs.get(job_key(job.avatar)) is job:
            del _jobs[job_key(job.avatar)]
        if job.completed is not None:
            job.completed(job)


def _fit_timer():
    started = time.perf_counter()
    deadline = started + SLICE_SECONDS
    for job in list(_jobs.values()):
        _advance(job, deadline)
        job.timer_slices.append(time.perf_counter() - started)
        if time.perf_counter() >= deadline:
            break
    return 0.0 if _jobs else None


def job_key(avatar):
    try:
        return avatar.as_pointer() if hasattr(avatar, 'as_pointer') else id(avatar)
    except ReferenceError:
        return id(avatar)


def pending_job(context):
    avatar = context.scene.dd_avatar
    return _jobs.get(job_key(avatar)) if avatar is not None else None


def fit_in_progress(context, existing=True):
    avatar = context.scene.dd_avatar
    return avatar is not None and (job_key(avatar) in _preparing or existing and job_key(avatar) in _jobs)


def start_fit(context, keep=False, completed=None):
    avatar = _volume_avatar(context)
    for key, job in list(_jobs.items()):
        if key != job_key(avatar):
            job.state = 'cancelled'
            del _jobs[key]
    _preparing.add(job_key(avatar))
    try:
        vertices, triangles, axes, fingerprint = _volume_mesh(context, avatar)
    finally:
        _preparing.discard(job_key(avatar))
    current = _jobs.get(job_key(avatar))
    if current is not None and current.fingerprint == fingerprint and current.keep == keep:
        current.completed = completed or current.completed
        return current
    if current is not None:
        current.state = 'cancelled'
    job = FitJob(avatar, context.scene, fingerprint, _fit_steps(vertices, triangles, _clearance(context)), keep, completed)
    _jobs[job_key(avatar)] = job
    try:
        import bpy
        if not bpy.app.timers.is_registered(_fit_timer):
            bpy.app.timers.register(_fit_timer, first_interval=0)
    except (ImportError, AttributeError):
        pass
    return job


def finish_fit(job):
    job.completed = None
    _advance(job, None)
    if job.state == 'failed':
        raise ValueError(job.error)
    if job.state == 'cancelled':
        raise ValueError('The avatar changed before its arrangement setup was ready.')
    return _volume_validate(json.loads(job.avatar['dd_arrangement_volumes']))


def cancel_fits():
    for job in _jobs.values():
        job.state = 'cancelled'
    _jobs.clear()


def ensure_volumes(context, force=False, wait=True):
    avatar = _volume_avatar(context)
    stored = avatar.get('dd_arrangement_volumes')
    if stored is not None and not force:
        try:
            return _volume_validate(json.loads(stored))
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid avatar arrangement volumes JSON; explicitly regenerate avatar setup.') from error
    if force:
        job = _jobs.pop(job_key(avatar), None)
        if job is not None:
            job.state = 'cancelled'
        return finish_fit(start_fit(context))
    job = _jobs.get(job_key(avatar)) or start_fit(context)
    if not wait:
        raise FitPending('Preparing arrangement points for ' + avatar.name + '…')
    return finish_fit(job)


def stale_fit(context):
    avatar = _volume_avatar(context)
    stored = avatar.get('dd_arrangement_volumes')
    if stored is None or job_key(avatar) in _jobs:
        return False
    try:
        fingerprint = json.loads(stored).get('fingerprint')
    except (TypeError, AttributeError, json.JSONDecodeError):
        return False
    return bool(fingerprint) and fingerprint != _volume_mesh(context, avatar)[3]


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


def _volume_resolve(setup, volume, point, low, extent, axes, clearance=None):
    if setup['version'] == 2:
        from .ellipse_volumes import resolve_ellipse
        return resolve_ellipse(setup, volume, point, low, extent, axes, clearance)
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


def resolve_point(context, volume_id, point_id, version=None, clearance=None, setup=None):
    setup = setup or ensure_volumes(context)
    if version in (2, 3) and setup['version'] == 1:
        setup = upgrade_volumes(context)
    if version == 1 and 'legacy' in setup:
        setup = _volume_validate(setup['legacy'])
    volume, point = _volume_find(setup, volume_id, point_id)
    return _volume_resolve(setup, volume, point, *_volume_frame(context), clearance)


def upgrade_volumes(context):
    setup = ensure_volumes(context)
    if setup['version'] == 2:
        return setup
    avatar = _volume_avatar(context)
    stored = avatar['dd_arrangement_volumes']
    try:
        upgraded = ensure_volumes(context, force=True)
        upgraded['legacy'] = setup
        for volume in upgraded['volumes']:
            previous = _volume_find(setup, volume['id'])
            for key in ('lower', 'upper', 'radius_scale', 'points', 'next_point_id'):
                if key in previous:
                    volume[key] = previous[key]
        avatar['dd_arrangement_volumes'] = json.dumps(_volume_validate(upgraded), allow_nan=False)
        return upgraded
    except Exception:
        avatar['dd_arrangement_volumes'] = stored
        raise


def _mirror_volume(identity):
    for side, other in (('left_', 'right_'), ('right_', 'left_')):
        if identity.startswith(side):
            return other + identity[len(side):]
    return identity


def _mirrors(point, other):
    return (abs(math.remainder(point['angle'] + other['angle'], math.tau)) < MIRROR_TOLERANCE
            and abs(point['height'] - other['height']) < MIRROR_TOLERANCE)


def mirror_point(setup, volume_id, point_id):
    volume, point = _volume_find(setup, volume_id, point_id)
    partner = next((item for item in setup['volumes'] if item['id'] == _mirror_volume(volume_id)), None)
    if partner is None:
        return None
    if partner is volume and abs(math.remainder(2 * point['angle'], math.tau)) < MIRROR_TOLERANCE:
        return None
    other = next((item for item in partner['points'] if _mirrors(point, item)), None)
    return (partner['id'], other['id']) if other is not None else None


def mirrored_points(setup):
    return {(volume['id'], point['id']) for volume in setup['volumes'] for point in volume['points']
            if mirror_point(setup, volume['id'], point['id']) is not None}


def world_points(context, setup=None, wait=True):
    setup = setup or ensure_volumes(context, wait=wait)
    low,extent,axes=_volume_frame(context)
    mirrored=mirrored_points(setup)
    result=[]
    for volume in setup['volumes']:
        for point in volume['points']:
            resolved=_volume_resolve(setup,volume,point,low,extent,axes)
            result.append(dict(volume=volume['id'],point=point['id'],position=resolved['point'],
                               geometry=resolved['volume'],normal=resolved['normal'],tangent=resolved['tangent'],
                               mirrored=(volume['id'],point['id']) in mirrored))
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


def edit_volume(context, volume_id, lower, upper, radius_scale, width_scale=None, depth_scale=None):
    scales = [value for value in (radius_scale, width_scale, depth_scale) if value is not None]
    if (not all(math.isfinite(value) for value in (lower, upper, *scales))
            or not 0 <= lower < upper <= 1 or min(scales) <= 0):
        raise ValueError('Volume bounds must satisfy 0 <= lower < upper <= 1 and radius scale must be positive.')
    setup = ensure_volumes(context)
    volume = _volume_find(setup, volume_id)
    volume.update(lower=lower, upper=upper, radius_scale=radius_scale)
    if width_scale is not None and depth_scale is not None:
        volume.update(width_scale=width_scale, depth_scale=depth_scale)
    _volume_avatar(context)['dd_arrangement_volumes'] = json.dumps(_volume_validate(setup), allow_nan=False)
    return setup


def volume_dimensions(context, volume_id):
    setup = ensure_volumes(context)
    low, extent, axes = _volume_frame(context)
    if setup['version'] == 2:
        from .ellipse_volumes import volume_stack
        centers = [entry['center'] for entry in volume_stack(setup, _volume_find(setup, volume_id), low, extent, axes)
                   if entry['volume'] == volume_id]
    else:
        volume = _volume_find(setup, volume_id)
        centers = [tuple(extent[axis] * sample['center'][axis] for axis in range(3)) for sample in volume['samples']]
    return math.dist(centers[0], centers[-1]), extent[2]


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
            or avatar.get('dd_kind') in {'panel', 'simulation', 'final', 'anchor', 'collider'}
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
