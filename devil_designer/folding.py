import math
from . import curves


def fold_records(pattern):
    result = []
    for feature in pattern.features:
        if feature.get('type') != 'FOLD':
            continue
        path = next((path for path in pattern.paths if path.vertices and path.vertices[0].id == feature.get('apex')), None)
        if path is None:
            raise ValueError('A fold line is missing. Undo the path edit or remove its fold first.')
        angle = feature.get('angle')
        if type(angle) not in (int, float) or not math.isfinite(angle) or not 10 <= abs(angle) <= 160:
            raise ValueError('Fold angles must be between 10 and 160 degrees.')
        if feature.get('style') not in ('LINE', 'KNIFE', 'BOX'):
            raise ValueError('Unknown fold style.')
        _validate_line(pattern, path)
        result.append((path, feature))
    if result:
        first = result[0][0]
        direction = curves.sub(first.points[-1], first.points[0])
        length = math.hypot(*direction)
        for path, _ in result[1:]:
            other = curves.sub(path.points[-1], path.points[0])
            if abs(direction[0] * other[1] - direction[1] * other[0]) > 1e-7 * length * math.hypot(*other):
                raise ValueError('This version supports parallel fold lines on each piece.')
    return result


def _validate_line(pattern, path):
    from .core import on_segment
    if path.closed or path.role != 'INTERNAL' or len(path.vertices) < 2:
        raise ValueError('Use a straight, open internal path for a fold.')
    start, end = path.points[0], path.points[-1]
    length = math.dist(start, end)
    if length < .003:
        raise ValueError('A fold line must be at least 3 mm long.')
    for vertex in path.vertices:
        if vertex.incoming is not None or vertex.outgoing is not None or not on_segment((vertex.x, vertex.y), start, end):
            raise ValueError('Fold lines must stay straight. Remove the fold before curving its path.')
    outline = pattern.outline()
    edges = list(zip(outline, outline[1:] + outline[:1]))
    if not all(any(on_segment(point, left, right) for left, right in edges) for point in (start, end)):
        raise ValueError('Extend the fold line from one boundary of the piece to the other.')
    for left, right in edges:
        direction = curves.sub(end, start)
        values = [direction[0] * (point[1] - start[1]) - direction[1] * (point[0] - start[0]) for point in (left, right)]
        if max(abs(value) for value in values) < 1e-9:
            raise ValueError('A fold must cross the fabric, not follow its outer edge.')
        if values[0] * values[1] < -1e-14:
            fraction = values[0] / (values[0] - values[1])
            crossing = curves.mix(left, right, fraction)
            if math.dist(crossing, start) > 1e-6 and math.dist(crossing, end) > 1e-6:
                raise ValueError('A fold cannot cross a gap in a concave piece.')
    for hole in pattern.paths:
        if hole.role != 'HOLE':
            continue
        points = hole.outline()
        direction = curves.sub(end, start)
        values = [direction[0] * (point[1] - start[1]) - direction[1] * (point[0] - start[0]) for point in points]
        if min(values) <= 0 <= max(values):
            raise ValueError('A fold cannot cross a hole.')


def _parallel_path(pattern, path, offset):
    from .core import Path, Vertex
    start, end = path.points[0], path.points[-1]
    direction = curves.sub(end, start)
    length = math.hypot(*direction)
    normal = (-direction[1] / length, direction[0] / length)
    origin = (start[0] + normal[0] * offset, start[1] + normal[1] * offset)
    outline = pattern.outline()
    hits = []
    for left, right in zip(outline, outline[1:] + outline[:1]):
        values = [direction[0] * (point[1] - origin[1]) - direction[1] * (point[0] - origin[0]) for point in (left, right)]
        if abs(values[0]) < 1e-10:
            hits.append(left)
        if values[0] * values[1] < 0:
            hits.append(curves.mix(left, right, values[0] / (values[0] - values[1])))
    unique = []
    for point in hits:
        if not any(math.dist(point, other) < 1e-6 for other in unique):
            unique.append(point)
    if len(unique) != 2:
        raise ValueError('There is not enough uninterrupted fabric for this pleat depth.')
    unique.sort(key=lambda point: sum(value * axis for value, axis in zip(curves.sub(point, origin), direction)))
    result = Path('Pleat fold', [Vertex(*point) for point in unique])
    _validate_line(pattern, result)
    return result


def author_fold(session, style, depth=.02):
    from .core import uid
    pattern = session.document.find(session.selected)
    if pattern is None or session.path == 'OUTER':
        raise ValueError('Draw and select a straight internal path first.')
    path = pattern.path(session.path)
    _validate_line(pattern, path)
    if any(record[0].id == path.id for record in fold_records(pattern)):
        raise ValueError('Remove this fold before creating another fold or pleat from it.')
    if style not in ('MOUNTAIN', 'VALLEY', 'KNIFE', 'BOX'):
        raise ValueError('Choose Mountain, Valley, Knife pleat or Box pleat.')
    if not math.isfinite(depth) or not .01 <= depth <= .04:
        raise ValueError('Pleat depth must be between 1 and 4 cm.')
    offsets = [0] if style in ('MOUNTAIN', 'VALLEY') else [0, depth] if style == 'KNIFE' else [-2 * depth, -depth, depth, 2 * depth]
    paths = [path if abs(offset) < 1e-10 else _parallel_path(pattern, path, offset) for offset in offsets]
    angles = [-150] if style == 'VALLEY' else [150] if style == 'MOUNTAIN' else [150, -150] if style == 'KNIFE' else [150, -150, -150, 150]
    group = uid()
    def apply():
        if path not in paths:
            pattern.paths.remove(path)
        for candidate, angle in zip(paths, angles):
            if candidate not in pattern.paths:
                pattern.paths.append(candidate)
            candidate.name = ('Mountain' if angle > 0 else 'Valley') + ' fold'
            pattern.features.append(dict(id=uid(), type='FOLD', apex=candidate.vertices[0].id, angle=angle,
                                         style=style if style in ('KNIFE', 'BOX') else 'LINE', group=group))
        fold_records(pattern)
    result = session.commit(apply)
    session.path = paths[0].id
    session.corner = None
    session.segment = session.document.edges(pattern.id, session.path)[0]
    return result


def edit_fold(session, action):
    pattern = session.document.find(session.selected)
    if pattern is None:
        raise ValueError('Select a fold line first.')
    records = fold_records(pattern)
    selected = next((feature for path, feature in records if path.id == session.path), None)
    if selected is None:
        raise ValueError('Select a fold line first.')
    def apply():
        group = [feature for _, feature in records if feature.get('group') == selected.get('group')]
        if action == 'REMOVE':
            pattern.features = [feature for feature in pattern.features if feature not in group]
        elif action == 'REVERSE':
            for feature in group:
                feature['angle'] = -feature['angle']
        elif action in ('60', '120', '150'):
            for feature in group:
                feature['angle'] = math.copysign(int(action), feature['angle'])
        else:
            raise ValueError('Unknown fold action.')
    return session.commit(apply)


def folded_positions(pattern, coords):
    records = fold_records(pattern)
    if not records:
        return None
    if pattern.wrap_radius > 0 and pattern.placement_mode == 'LEGACY' and pattern.arrangement is None:
        raise ValueError('Reset legacy wrapping before adding fold lines.')
    transforms = []
    def transform(point):
        current = (point[0], point[1], 0.0)
        for start, direction, origin, axis, angle in transforms:
            if direction[0] * (point[1] - start[1]) - direction[1] * (point[0] - start[0]) <= 1e-9:
                continue
            vector = tuple(value - base for value, base in zip(current, origin))
            cosine, sine = math.cos(angle), math.sin(angle)
            product = (axis[1]*vector[2]-axis[2]*vector[1], axis[2]*vector[0]-axis[0]*vector[2], axis[0]*vector[1]-axis[1]*vector[0])
            projection = sum(value * component for value, component in zip(vector, axis))
            current = tuple(base + value*cosine + cross*sine + component*projection*(1-cosine)
                            for base, value, cross, component in zip(origin, vector, product, axis))
        return current
    for path, feature in records:
        start, end = path.points[0], path.points[-1]
        origin, endpoint = transform(start), transform(end)
        length = math.dist(origin, endpoint)
        axis = tuple((value - base) / length for value, base in zip(endpoint, origin))
        transforms.append((start, curves.sub(end, start), origin, axis, math.radians(feature['angle'])))
    return [transform(point) for point in coords]
