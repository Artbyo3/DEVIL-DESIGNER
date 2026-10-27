import math
try:
    import bpy
except ImportError:
    bpy = None


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


def torso_loop_circumference(segments, center_x=0.0):
    if not segments:
        return 0.0
    components, points, edges = get_connected_loops(segments)
    if not components:
        return 0.0

    best_comp = min(components, key=lambda comp: abs((min(points[i][0] for i in comp) + max(points[i][0] for i in comp)) / 2 - center_x))
    comp_set = set(best_comp)
    total_len = 0.0
    for i1, i2 in edges:
        if i1 in comp_set and i2 in comp_set:
            total_len += math.hypot(points[i1][0] - points[i2][0], points[i1][1] - points[i2][1])
    return total_len


def estimate_body_measurements(body, scene, reference=None):
    if body is None or body.type != 'MESH':
        return None
    evaluated = None
    mesh = body.data
    try:
        if hasattr(bpy, 'context') and hasattr(bpy.context, 'evaluated_depsgraph_get'):
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated = body.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
    except (RuntimeError, ValueError, ReferenceError):
        pass

    try:
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

        n_bins = 24
        bin_data = []
        for i in range(n_bins):
            f = 0.46 + 0.32 * (i / (n_bins - 1))
            y_level = f * ref_h
            bin_pts = [p[0] for p in pts_2d if abs(p[1] - y_level) < 0.02 * ref_h and abs(p[0]) < 0.28 * ref_h]
            w = (max(bin_pts) - min(bin_pts)) if bin_pts else 0.0
            bin_data.append((f, y_level, w))

        waist_cands = [d for d in bin_data if 0.56 <= d[0] <= 0.68 and d[2] > 0]
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

        chest_cands = [d for d in bin_data if waist_frac < d[0] <= 0.76 and d[2] > 0]
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
        h_segs = slice_mesh_z(mesh, matrix, hip_z, world_verts=world_verts)
        hip_circ = torso_loop_circumference(h_segs, center_x)

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

        neck_z = low_z + 0.81 * total_height
        torso_length = neck_z - waist_z

        arm_verts = [v for v in world_verts if abs(v.x - center_x) > 0.18 and v.z > low_z + 0.45 * total_height]
        if arm_verts:
            outer_arm_x = max(abs(v.x - center_x) for v in arm_verts)
            arm_length = (outer_arm_x - 0.18) * 1.05
        else:
            arm_length = 0.32 * total_height

        def r(val_m):
            return round(val_m * 100 * 2) / 2

        return {
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
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()
