import math
import numpy
try:
    import bpy
except ImportError:
    bpy = None


ARMS_OUT_RATIO = 1.6
SHOULDER_TO_CHEST = 1.45
ARMPIT_JUMP = 1.15
OPEN_SECTION_GAP = math.pi / 2
ARM_STATION = (0.03, 0.10)
ARM_MAX_THICKNESS = 0.12
NECK_SEARCH = 0.15
NECK_BIN = 0.01


def surrounds(segments, center_x):
    if not len(segments):
        return False
    ends = numpy.asarray(segments, dtype=float).reshape(len(segments), 2, -1)[:, :, :2]
    points = ends.reshape(-1, 2)
    if not points[:, 0].min() < center_x < points[:, 0].max():
        return False
    center_y = (points[:, 1].min() + points[:, 1].max()) / 2
    angles = numpy.arctan2(ends[:, :, 1] - center_y, ends[:, :, 0] - center_x) % math.tau
    start, end = angles.min(axis=1), angles.max(axis=1)
    wrap = end - start > math.pi
    starts = numpy.concatenate((start[~wrap], end[wrap], numpy.zeros(int(wrap.sum()))))
    finishes = numpy.concatenate((end[~wrap], numpy.full(int(wrap.sum()), math.tau), start[wrap]))
    order = numpy.argsort(starts)
    starts, finishes = starts[order], numpy.maximum.accumulate(finishes[order])
    gaps = numpy.append(starts[1:] - finishes[:-1], starts[0] + math.tau - finishes[-1])
    return bool(gaps.max() < OPEN_SECTION_GAP)


def slice_mesh_z(mesh, matrix, z, world_verts=None):
    if world_verts is None:
        world_verts = [(matrix @ v.co) for v in mesh.vertices]
    segments = []
    for poly in mesh.polygons:
        poly_zs = [world_verts[i].z for i in poly.vertices]
        min_pz = min(poly_zs)
        max_pz = max(poly_zs)
        if min_pz > z or max_pz < z or abs(max_pz - min_pz) < 1e-7:
            continue
        pts = [world_verts[i] for i in poly.vertices]
        n = len(pts)
        intersections = []
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            if (p1.z <= z <= p2.z) or (p2.z <= z <= p1.z):
                if abs(p2.z - p1.z) > 1e-7:
                    t = (z - p1.z) / (p2.z - p1.z)
                    ix = p1.x + t * (p2.x - p1.x)
                    iy = p1.y + t * (p2.y - p1.y)
                    intersections.append((ix, iy))
        if len(intersections) == 2:
            segments.append((intersections[0], intersections[1]))
    return segments


def get_connected_loops(segments, tol=1e-3):
    points = []
    def pt_idx(pt):
        for idx, p in enumerate(points):
            if math.hypot(p[0] - pt[0], p[1] - pt[1]) < tol:
                return idx
        points.append(pt)
        return len(points) - 1

    edges = []
    for s in segments:
        i1 = pt_idx(s[0])
        i2 = pt_idx(s[1])
        if i1 != i2:
            edges.append((i1, i2))

    adj = {i: [] for i in range(len(points))}
    for i1, i2 in edges:
        adj[i1].append(i2)
        adj[i2].append(i1)

    visited = set()
    components = []
    for start in range(len(points)):
        if start in visited or not adj[start]:
            continue
        comp = []
        queue = [start]
        visited.add(start)
        while queue:
            curr = queue.pop(0)
            comp.append(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(comp)

    return components, points, edges


def component_segments(component, points, edges):
    members = set(component)
    return [(points[first], points[second]) for first, second in edges if first in members]


def torso_loop_circumference(segments, center_x=0.0):
    if not segments:
        return 0.0
    components, points, edges = get_connected_loops(segments)
    if not components:
        return 0.0

    components = [comp for comp in components if surrounds(component_segments(comp, points, edges), center_x)]
    if not components:
        return 0.0
    best_comp = min(components, key=lambda comp: abs((min(points[i][0] for i in comp) + max(points[i][0] for i in comp)) / 2 - center_x))
    return tape_length([points[i] for i in best_comp])


def tape_length(points):
    ordered = sorted(set(points))
    if len(ordered) < 3:
        return 0.0
    def turn(origin, first, second):
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])
    def half(sequence):
        hull = []
        for point in sequence:
            while len(hull) >= 2 and turn(hull[-2], hull[-1], point) <= 0:
                hull.pop()
            hull.append(point)
        return hull[:-1]
    hull = half(ordered) + half(ordered[::-1])
    return sum(math.dist(first, second) for first, second in zip(hull, hull[1:] + hull[:1]))


def widest_torso_loop(mesh, matrix, z, ceiling, world_verts, center_x):
    step = max((ceiling - z) / 12, 1e-4)
    levels = [z + index * step for index in range(12) if z + index * step < ceiling] or [z]
    found = []
    for level in levels:
        segments = slice_mesh_z(mesh, matrix, level, world_verts=world_verts)
        components, points, edges = get_connected_loops(segments)
        if any(surrounds(component_segments(comp, points, edges), center_x) for comp in components):
            found.append((level, torso_loop_circumference(segments, center_x)))
    if found:
        return max(found, key=lambda item: item[1])
    return z, 0.0


def arm_band(points, center_x, shoulder_half, low_z, total_height):
    lateral = numpy.abs(points[:, 0] - center_x)
    inner = shoulder_half + ARM_STATION[0] * total_height
    outer = shoulder_half + ARM_STATION[1] * total_height
    arm = points[(lateral > inner) & (lateral < outer) & (points[:, 2] > low_z + 0.5 * total_height)]
    if not len(arm):
        return None
    bottom, top = float(arm[:, 2].min()), float(arm[:, 2].max())
    if top - bottom > ARM_MAX_THICKNESS * total_height:
        return None
    return bottom, top


def neck_base(points, center_x, shoulder_half, floor, total_height):
    core = points[(numpy.abs(points[:, 0] - center_x) < shoulder_half) & (points[:, 2] > floor)
                  & (points[:, 2] < floor + NECK_SEARCH * total_height)]
    if not len(core):
        return None
    size = NECK_BIN * total_height
    bins = ((core[:, 2] - floor) // size).astype(int)
    widths = []
    for index in numpy.unique(bins).tolist():
        members = core[bins == index]
        if len(members) >= 3:
            widths.append((float(members[:, 0].max() - members[:, 0].min()), floor + (index + 0.5) * size))
    if not widths:
        return None
    return min(widths)[1]


def estimate_body_measurements(body, scene, reference=None):
    if body is None or body.type != 'MESH':
        return None
    if hasattr(bpy, 'context') and hasattr(bpy.context, 'evaluated_depsgraph_get'):
        from .body_surface import revealed
        try:
            with revealed(bpy.context, body) as evaluated:
                mesh = evaluated.to_mesh()
                try:
                    return measure_mesh(body, mesh, scene, reference)
                finally:
                    evaluated.to_mesh_clear()
        except (RuntimeError, ReferenceError):
            pass
    return measure_mesh(body, body.data, scene, reference)


def measure_mesh(body, mesh, scene, reference):
    if not mesh.vertices:
        return None
    matrix = body.matrix_world
    unit = max(1e-6, scene.unit_settings.scale_length)
    world_verts = [(matrix @ v.co) * unit for v in mesh.vertices]
    low_z = min(v.z for v in world_verts)
    high_z = max(v.z for v in world_verts)
    total_height = high_z - low_z
    if total_height <= 1e-4:
        return None

    xs = [v.x for v in world_verts]
    center_x = (min(xs) + max(xs)) / 2

    shoulder_z = low_z + 0.78 * total_height
    upper_verts = [v for v in world_verts if abs(v.z - shoulder_z) < 0.03 * total_height]
    sh_x = [abs(v.x - center_x) for v in upper_verts if abs(v.y) < 0.15]
    shoulder_width = 2 * (max(sh_x) if sh_x else 0.20 * total_height)

    ref_verts = reference.vertices if (reference and getattr(reference, 'vertices', None)) else None
    ref_h = (reference.bounds[1][1] - reference.bounds[0][1]) if (reference and getattr(reference, 'bounds', None)) else total_height
    pts_2d = ref_verts if ref_verts else [(v.x - center_x, v.z - low_z) for v in world_verts]

    n_bins = 30
    bin_data = []
    for i in range(n_bins):
        f = 0.46 + 0.40 * (i / (n_bins - 1))
        y_level = f * ref_h
        bin_pts = [p[0] for p in pts_2d if abs(p[1] - y_level) < 0.02 * ref_h and abs(p[0]) < 0.28 * ref_h]
        w = (max(bin_pts) - min(bin_pts)) if bin_pts else 0.0
        bin_data.append((f, y_level, w))

    waist_cands = [d for d in bin_data if 0.56 <= d[0] <= 0.74 and d[2] > 0]
    has_landmarks = True
    if waist_cands:
        waist_entry = min(waist_cands, key=lambda d: d[2])
        waist_frac, waist_y, waist_w = waist_entry
    else:
        has_landmarks = False
        waist_frac = 0.62
        waist_y = waist_frac * ref_h
        waist_w = 0.0

    hip_cands = [d for d in bin_data if 0.48 <= d[0] < waist_frac and d[2] > 0]
    if hip_cands:
        hip_entry = max(hip_cands, key=lambda d: d[2])
        hip_frac, hip_y, hip_w = hip_entry
    else:
        has_landmarks = False
        hip_frac = 0.53
        hip_y = hip_frac * ref_h
        hip_w = 0.0

    chest_cands = []
    for entry in (d for d in bin_data if waist_frac < d[0] <= 0.84 and d[2] > 0):
        if chest_cands and entry[2] > chest_cands[-1][2] * ARMPIT_JUMP:
            break
        chest_cands.append(entry)
    if chest_cands:
        chest_entry = max(chest_cands, key=lambda d: d[2])
        chest_frac, chest_y, chest_w = chest_entry
    else:
        has_landmarks = False
        chest_frac = 0.70
        chest_y = chest_frac * ref_h
        chest_w = 0.0

    if has_landmarks and (hip_w - waist_w < 0.01 or chest_w - waist_w < 0.01):
        has_landmarks = False

    chest_z = low_z + chest_frac * total_height
    waist_z = low_z + waist_frac * total_height
    hip_z = low_z + hip_frac * total_height

    c_segs = slice_mesh_z(mesh, matrix, chest_z, world_verts=world_verts)
    chest_circ = torso_loop_circumference(c_segs, center_x)
    w_segs = slice_mesh_z(mesh, matrix, waist_z, world_verts=world_verts)
    waist_circ = torso_loop_circumference(w_segs, center_x)
    hip_z, hip_circ = widest_torso_loop(mesh, matrix, hip_z, waist_z, world_verts, center_x)

    if chest_w > 0 and shoulder_width > chest_w * ARMS_OUT_RATIO:
        shoulder_width = chest_w * SHOULDER_TO_CHEST

    if chest_circ <= 0.01 or not has_landmarks:
        chest_circ = 0.58 * total_height
    if waist_circ <= 0.01 or not has_landmarks:
        waist_circ = 0.46 * total_height
    if hip_circ <= 0.01 or not has_landmarks:
        hip_circ = 0.56 * total_height

    crotch_z = low_z + 0.48 * total_height
    for frac in (0.46, 0.49, 0.52):
        z = low_z + frac * total_height
        segs = slice_mesh_z(mesh, matrix, z, world_verts=world_verts)
        components, _, _ = get_connected_loops(segs)
        if len(components) >= 2:
            crotch_z = z
            break
    inseam = crotch_z - low_z

    points = numpy.array([tuple(v) for v in world_verts], dtype=float)
    arm = arm_band(points, center_x, shoulder_width / 2, low_z, total_height)
    measured_neck = neck_base(points, center_x, shoulder_width / 2, arm[1], total_height) if arm else None
    if measured_neck is not None and measured_neck <= chest_z:
        measured_neck = None
    neck_z = low_z + 0.81 * total_height if measured_neck is None else measured_neck
    torso_length = neck_z - waist_z

    arm_verts = [v for v in world_verts if abs(v.x - center_x) > 0.18 and v.z > low_z + 0.45 * total_height]
    if arm_verts:
        outer_arm_x = max(abs(v.x - center_x) for v in arm_verts)
        arm_length = (outer_arm_x - 0.18) * 1.05
    else:
        arm_length = 0.32 * total_height

    def r(val_m):
        return round(val_m * 100 * 2) / 2

    def frame(z):
        return (z - low_z) / total_height * ref_h

    landmarks = {}
    if measured_neck is not None:
        landmarks.update(neck_y=frame(measured_neck), arm_bottom_y=frame(arm[0]), arm_top_y=frame(arm[1]))
    return {
        **landmarks,
        'height': r(total_height),
        'shoulder_width': r(shoulder_width),
        'chest': r(chest_circ),
        'waist': r(waist_circ),
        'hip': r(hip_circ),
        'torso_length': r(torso_length),
        'arm_length': r(arm_length),
        'inseam': r(inseam),
        'chest_z': chest_z,
        'waist_z': waist_z,
        'hip_z': hip_z,
        'chest_y': chest_y,
        'waist_y': waist_y,
        'hip_y': hip_y,
        'low_z': low_z,
        'high_z': high_z,
        'fallback': not has_landmarks,
    }
