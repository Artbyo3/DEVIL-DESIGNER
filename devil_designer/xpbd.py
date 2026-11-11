import bmesh
import bpy
import numpy as np

from . import seam_shrink, xpbd_nodes
from .presets import air_damping, resolve_preset

MODIFIER = 'DD XPBD'
MASS_SCALE = 1000.0
STRETCH_COMPLIANCE = 1.0e-8
BEND_COMPLIANCE = 5.0e-4
SEAM_COMPLIANCE = 0.0
PIN_COMPLIANCE = 0.0
TACK_COMPLIANCE = 0.0
SHRINK_GAIN = 1.9
SHRINK_RINGS = 8
SHRINK_FALLOFF = .9
PIECE_SPACING = 100.0
SIMULATION_ATTRIBUTES = {'rest_length', 'mass', 'radius', 'velocity', 'external_force', 'static_friction', 'dynamic_friction'}
BODY_STEP = .01
LINK_MIN_BENDING = 6.0
LINK_COMPLIANCE = 1.0e-3
LINK_STRAIGHTNESS = -.85
MIN_SUBSTEPS = 10
SIM_FPS = 30
LIVE_SUBSTEPS = 12
REFINE_FRAMES = 40
REFINE_ITERATIONS = 4
CONTACT_RADIUS = .006
GRAB_STRIDE = .05
GRAB_REACH = .4
WELD_REACH = .06
SHELL_VOXEL = .005
SHELL_THICKNESS = .015


def modifier(obj):
    return obj.modifiers.get(MODIFIER)


def current(obj):
    mod = modifier(obj)
    return mod is not None and mod.node_group is not None and mod.node_group.get('dd_group_version') == xpbd_nodes.GROUP_VERSION


def input_slot(obj, name):
    mod = modifier(obj)
    return getattr(mod.properties.inputs, xpbd_nodes.input_identifier(mod.node_group, name))


def set_input(obj, name, value):
    input_slot(obj, name).value = value


def write(mesh, name, kind, domain, values):
    existing = mesh.attributes.get(name)
    if existing is not None:
        mesh.attributes.remove(existing)
    attribute = mesh.attributes.new(name=name, type=kind, domain=domain)
    field = {'FLOAT': 'value', 'BOOLEAN': 'value', 'INT': 'value', 'FLOAT_VECTOR': 'vector'}[kind]
    attribute.data.foreach_set(field, np.ascontiguousarray(values).ravel())


def flat_positions(panels, doc, unit):
    extent = doc.uv_layout['scale']
    rows = []
    for index, panel in enumerate(panels):
        mesh = panel.data
        loops = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', loops)
        uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        mesh.uv_layers.active.data.foreach_get('uv', uv)
        flat = np.zeros((len(mesh.vertices), 3), dtype=np.float64)
        flat[loops, :2] = uv.reshape(-1, 2) * extent / unit
        flat[:, 0] += index * PIECE_SPACING / unit
        rows.append(flat)
    return np.concatenate(rows)


def bend_rest_positions(panels, doc, flat, unit):
    shapes = flat.copy()
    offset = 0
    for index, panel in enumerate(panels):
        count = len(panel.data.vertices)
        pattern = doc.find(panel['dd_pattern_id'])
        if any(feature.get('type') == 'FOLD' for feature in pattern.features):
            shape = np.empty(count * 3, dtype=np.float32)
            panel.data.vertices.foreach_get('co', shape)
            shapes[offset:offset + count] = shape.reshape(-1, 3)
            shapes[offset:offset + count, 0] += index * PIECE_SPACING / unit
        offset += count
    return shapes


def face_masses(mesh, rest, densities):
    counts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', counts)
    starts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_start', starts)
    loops = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loops)
    mass = np.zeros(len(rest))
    for corners in np.unique(counts):
        chosen = counts == corners
        indices = loops[starts[chosen, None] + np.arange(corners)]
        area = np.zeros(len(indices))
        for corner in range(1, corners - 1):
            first = rest[indices[:, corner]] - rest[indices[:, 0]]
            second = rest[indices[:, corner + 1]] - rest[indices[:, 0]]
            area += np.linalg.norm(np.cross(first, second), axis=1) * .5
        share = area * densities[indices[:, 0]] / corners
        for corner in range(corners):
            np.add.at(mass, indices[:, corner], share)
    return mass


def seam_rings(edges, seam, count, rings=1):
    reach = np.zeros(count, dtype=bool)
    reach[edges[seam].ravel()] = True
    structural = edges[~seam]
    for _ in range(rings):
        grown = reach.copy()
        grown[structural[reach[structural[:, 0]], 1]] = True
        grown[structural[reach[structural[:, 1]], 0]] = True
        reach = grown
    return reach


def world_surface(context, source):
    from .body_surface import revealed
    with revealed(context, source) as evaluated:
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=context.evaluated_depsgraph_get())
    mesh.transform(source.matrix_world)
    return mesh


def bake_collider(context):
    from . import garment, layering
    scene = context.scene
    bodies = layering.collision_bodies(scene)
    merged = bmesh.new()
    for source in bodies:
        surface = world_surface(context, source)
        merged.from_mesh(surface)
        bpy.data.meshes.remove(surface)
    mesh = bpy.data.meshes.new('DD Collision Body')
    merged.to_mesh(mesh)
    merged.free()
    collider = bpy.data.objects.new('DD Collision Body', mesh)
    garment.collection(scene).objects.link(collider)
    garment.tag(collider, 'collider')
    collider.hide_render = True
    collider.hide_set(True)
    return collider


def bake_shell(context, collider):
    from . import garment
    scene = context.scene
    unit = max(1e-6, scene.unit_settings.scale_length)
    solid = collider.modifiers.new('DD Shell Solid', 'SOLIDIFY')
    solid.thickness = SHELL_THICKNESS / unit
    solid.offset = -1
    remesh = collider.modifiers.new('DD Shell', 'REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = SHELL_VOXEL / unit
    remesh.use_smooth_shade = False
    collider.hide_set(False)
    context.view_layer.update()
    graph = context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(collider.evaluated_get(graph), depsgraph=graph)
    collider.modifiers.remove(remesh)
    collider.modifiers.remove(solid)
    collider.hide_set(True)
    shell = bpy.data.objects.new('DD Collision Shell', mesh)
    garment.collection(scene).objects.link(shell)
    garment.tag(shell, 'collider')
    shell.hide_render = True
    shell.hide_set(True)
    return shell


def restart_from_pose(obj):
    mesh = obj.data
    start = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', start)
    start = start.reshape(-1, 3)
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', edges)
    edges = edges.reshape(-1, 2)
    write(mesh, 'dd_seam_start', 'FLOAT', 'EDGE', np.linalg.norm(start[edges[:, 0]] - start[edges[:, 1]], axis=1))
    write(mesh, 'dd_pin_target', 'FLOAT_VECTOR', 'POINT', start)


def hold(obj, vertices):
    mesh = obj.data
    held = np.zeros(len(mesh.vertices), dtype=bool)
    mesh.attributes['dd_pinned'].data.foreach_get('value', held)
    held[list(vertices)] = True
    start = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', start)
    write(mesh, 'dd_pinned', 'BOOLEAN', 'POINT', held)
    write(mesh, 'dd_pin_target', 'FLOAT_VECTOR', 'POINT', start)
    tacked = np.zeros(len(mesh.vertices), dtype=bool)
    mesh.attributes['dd_tacked'].data.foreach_get('value', tacked)
    tacked[list(vertices)] = False
    write(mesh, 'dd_tacked', 'BOOLEAN', 'POINT', tacked)


def strengthen(obj, vertices, multiplier):
    mesh = obj.data
    chosen = np.zeros(len(mesh.vertices), dtype=bool)
    chosen[list(vertices)] = True
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', edges)
    compliance = np.empty(len(mesh.edges), dtype=np.float32)
    mesh.attributes['dd_edge_compliance'].data.foreach_get('value', compliance)
    linked = np.zeros(len(mesh.edges), dtype=bool)
    link_attribute = mesh.attributes.get('dd_bend_link')
    if link_attribute is not None:
        link_attribute.data.foreach_get('value', linked)
    touched = chosen[edges.reshape(-1, 2)].any(axis=1)
    compliance[touched & ~linked] /= multiplier
    compliance[touched & linked] /= multiplier ** 2
    write(mesh, 'dd_edge_compliance', 'FLOAT', 'EDGE', compliance)
    bending = np.empty(len(mesh.vertices), dtype=np.float32)
    mesh.attributes['dd_bend_compliance'].data.foreach_get('value', bending)
    bending[chosen] /= multiplier ** 2
    write(mesh, 'dd_bend_compliance', 'FLOAT', 'POINT', bending)


def refine(context, obj):
    scene = context.scene
    live = input_slot(obj, 'Inner Substeps').value
    iterations = input_slot(obj, 'Iterations').value
    set_input(obj, 'Inner Substeps', max(live, scene.dd_quality))
    set_input(obj, 'Iterations', max(iterations, REFINE_ITERATIONS))
    obj.update_tag()
    for _ in range(REFINE_FRAMES):
        scene.frame_set(scene.frame_current + 1)
    set_input(obj, 'Inner Substeps', live)
    set_input(obj, 'Iterations', iterations)
    obj.update_tag()


def strip_attributes(mesh):
    for name in [attribute.name for attribute in mesh.attributes]:
        if name in SIMULATION_ATTRIBUTES or (name.startswith('dd_') and name != 'dd_piece') or name.startswith('sim:'):
            mesh.attributes.remove(mesh.attributes[name])


def bend_links(rest, edges, stiff):
    neighbors = {}
    for first, second in edges.tolist():
        if stiff[first] and stiff[second]:
            neighbors.setdefault(first, []).append(second)
            neighbors.setdefault(second, []).append(first)
    links = set()
    for center, around in neighbors.items():
        directions = rest[around] - rest[center]
        directions /= np.maximum(np.linalg.norm(directions, axis=1), 1e-12)[:, None]
        for row in range(len(around)):
            partner = int(np.argmin(directions[row + 1:] @ directions[row])) + row + 1 if row + 1 < len(around) else None
            if partner is not None and directions[partner] @ directions[row] < LINK_STRAIGHTNESS:
                links.add((min(around[row], around[partner]), max(around[row], around[partner])))
    return np.array(sorted(links), dtype=np.int32).reshape(-1, 2)


def seam_frame(flat, neighbors, partners, first, second):
    for ahead in neighbors[first]:
        behind = next((item for item in partners.get(ahead, ()) if item in neighbors[second]), None)
        if behind is None:
            continue
        along_first = flat[ahead] - flat[first]
        along_second = flat[behind] - flat[second]
        turn = np.arctan2(along_first[1], along_first[0]) - np.arctan2(along_second[1], along_second[0])
        rotation = np.array(((np.cos(turn), -np.sin(turn)), (np.sin(turn), np.cos(turn))))
        sides = []
        for center, along in ((first, along_first), (second, along_second)):
            inside = [flat[item] - flat[center] for item in neighbors[center] if item not in partners]
            if not inside:
                return None
            spread = np.mean(inside, axis=0)
            sides.append(np.sign(along[0] * spread[1] - along[1] * spread[0]))
        if sides[0] != sides[1]:
            return rotation
        axis = along_second / max(np.linalg.norm(along_second), 1e-12)
        return rotation @ (2 * np.outer(axis, axis) - np.eye(2))
    return None


def seam_links(rest, edges, loose):
    flat = rest[:, :2]
    neighbors = [set() for _ in range(len(rest))]
    for first, second in edges[~loose].tolist():
        neighbors[first].add(second)
        neighbors[second].add(first)
    partners = {}
    for first, second in edges[loose].tolist():
        partners.setdefault(first, set()).add(second)
        partners.setdefault(second, set()).add(first)
    links = {}
    for first, second in edges[loose].tolist():
        frame = seam_frame(flat, neighbors, partners, first, second)
        if frame is None:
            continue
        for near in neighbors[first] - partners.keys():
            ahead = flat[near] - flat[first]
            for far in neighbors[second] - partners.keys():
                behind = frame @ (flat[far] - flat[second])
                if ahead @ behind < LINK_STRAIGHTNESS * np.linalg.norm(ahead) * np.linalg.norm(behind):
                    links.setdefault((min(near, far), max(near, far)), np.linalg.norm(ahead - behind))
    pairs = sorted(links)
    return np.array(pairs, dtype=np.int32).reshape(-1, 2), np.array([links[pair] for pair in pairs], dtype=float)


def add_edges(mesh, links):
    start = len(mesh.edges)
    mesh.edges.add(len(links))
    flat = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', flat)
    flat[start * 2:] = links.ravel()
    mesh.edges.foreach_set('vertices', flat)
    mesh.update()


def attach(context, obj, doc, panels, pieces, maps, plan, pinned, tacks):
    from .garment import collection as garment_collection, tag as tag_generated
    scene = context.scene
    mesh = obj.data
    unit = max(1e-6, scene.unit_settings.scale_length)
    count = len(mesh.vertices)
    start = np.empty(count * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', start)
    start = start.reshape(-1, 3).astype(np.float64)
    rest = flat_positions(panels, doc, unit)
    custom = getattr(doc, 'custom_presets', None)
    structural = np.empty(count)
    bending = np.empty(count)
    density = np.empty(count)
    damping = np.empty(count)
    grain = np.empty((count, 4))
    for ids, _, preset in pieces:
        values = resolve_preset(preset, custom)
        structural[ids] = values['structural']
        bending[ids] = values['bending']
        density[ids] = values['density']
        damping[ids] = air_damping(values['density'])
        grain[ids] = values['weft'], values['bias'], values['shrink_weft'], values['shrink_warp']
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', edges)
    edges = edges.reshape(-1, 2)
    loose = np.array([edge.is_loose for edge in mesh.edges], dtype=bool)
    near_seam = seam_rings(edges, loose, count)
    bridges, bridge_length = seam_links(rest, edges, loose)
    links = np.concatenate((bend_links(rest, edges[~loose], bending >= LINK_MIN_BENDING), bridges))
    add_edges(mesh, links)
    edges = np.concatenate((edges, links))
    linked = np.concatenate((np.zeros(len(loose), dtype=bool), np.ones(len(links), dtype=bool)))
    bridged = np.arange(len(edges)) >= len(edges) - len(bridges)
    loose = np.concatenate((loose, np.zeros(len(links), dtype=bool)))
    shrink = np.zeros(count)
    elastics = [record for record in doc.elastics if record['pattern'] in maps]
    sewn = [seam for seam in doc.seams if seam.active]
    if elastics or any(seam.shrink for seam in sewn):
        for vertex, weight in seam_shrink.boundary_weights(sewn, maps, plan).items():
            shrink[vertex] = weight * SHRINK_GAIN
        for record in elastics:
            for _, vertex in maps[record['pattern']].get(record['start'], []):
                shrink[vertex] = max(shrink[vertex], record['shrink'] / 100 * SHRINK_GAIN)
        spread = edges[~loose]
        for _ in range(SHRINK_RINGS):
            np.maximum.at(shrink, spread[:, 0], shrink[spread[:, 1]] * SHRINK_FALLOFF)
            np.maximum.at(shrink, spread[:, 1], shrink[spread[:, 0]] * SHRINK_FALLOFF)
    for record in doc.steam:
        for (ids, _, _), panel in zip(pieces, panels):
            if panel['dd_pattern_id'] == record['pattern']:
                flat = np.array([tuple(item.vector)[:2] for item in panel.data.attributes['dd_rest'].data])
                reach = np.linalg.norm(flat - (record['x'], record['y']), axis=1) / record['radius']
                shrink[ids] += np.clip(1 - reach, 0, 1) ** 2 * record['amount'] * SHRINK_GAIN
    pair_grain = (grain[edges[:, 0]] + grain[edges[:, 1]]) * .5
    span = (rest[edges[:, 1]] - rest[edges[:, 0]])[:, :2] * (1 - pair_grain[:, 2:])
    length = np.linalg.norm(span, axis=1)
    across, along = (np.square(span / np.maximum(length, 1e-12)[:, None])).T
    length[bridged] = bridge_length
    grain_stiffness = along ** 2 + pair_grain[:, 0] * across ** 2 + pair_grain[:, 1] * (1 + pair_grain[:, 0]) * across * along
    length *= 1 - (shrink[edges[:, 0]] + shrink[edges[:, 1]]) * .5
    length[loose] = 0.0
    seam_start = np.linalg.norm(start[edges[:, 0]] - start[edges[:, 1]], axis=1)
    pair_stiffness = (structural[edges[:, 0]] + structural[edges[:, 1]]) * .5
    compliance = STRETCH_COMPLIANCE * 32.0 / (pair_stiffness * np.maximum(grain_stiffness, 1e-3))
    compliance[loose] = SEAM_COMPLIANCE
    compliance[linked] = LINK_COMPLIANCE * (LINK_MIN_BENDING / np.minimum(bending[edges[linked, 0]], bending[edges[linked, 1]])) ** 2
    compliance[bridged] = LINK_COMPLIANCE * (LINK_MIN_BENDING / np.maximum(np.minimum(bending[bridges[:, 0]], bending[bridges[:, 1]]), LINK_MIN_BENDING)) ** 2
    write(mesh, 'rest_length', 'FLOAT', 'EDGE', length)
    write(mesh, 'dd_seam_start', 'FLOAT', 'EDGE', seam_start)
    write(mesh, 'dd_seam', 'BOOLEAN', 'EDGE', loose | bridged)
    write(mesh, 'dd_bend_link', 'BOOLEAN', 'EDGE', linked)
    write(mesh, 'dd_edge_compliance', 'FLOAT', 'EDGE', compliance)
    write(mesh, 'dd_rest_position', 'FLOAT_VECTOR', 'POINT', rest)
    write(mesh, 'dd_bend_rest', 'FLOAT_VECTOR', 'POINT', bend_rest_positions(panels, doc, rest, unit))
    write(mesh, 'dd_bend_compliance', 'FLOAT', 'POINT', BEND_COMPLIANCE * (2.2 / bending) ** 2)
    write(mesh, 'mass', 'FLOAT', 'POINT', np.maximum(face_masses(mesh, rest, density) * MASS_SCALE, 1e-5))
    write(mesh, 'dd_damping', 'FLOAT', 'POINT', damping)
    write(mesh, 'radius', 'FLOAT', 'POINT', np.full(count, CONTACT_RADIUS / unit))
    write(mesh, 'dd_contact_weight', 'FLOAT', 'POINT', np.where(near_seam, 0.0, 1.0))
    write(mesh, 'dd_body_margin', 'FLOAT', 'POINT', np.full(count, scene.dd_skin_offset / unit))
    write(mesh, 'dd_body_grip', 'FLOAT', 'POINT', np.full(count, scene.dd_friction))
    write(mesh, 'dd_body_step', 'FLOAT', 'POINT', np.full(count, BODY_STEP / unit))
    partner = np.full(count, -1, dtype=np.int32)
    partner[edges[loose, 0]] = edges[loose, 1]
    partner[edges[loose, 1]] = edges[loose, 0]
    write(mesh, 'dd_partner', 'INT', 'POINT', partner)
    write(mesh, 'dd_weld_reach', 'FLOAT', 'POINT', np.full(count, WELD_REACH / unit))
    thickness = .006 / unit if scene.dd_self_collision else 0.0
    write(mesh, 'dd_self_thickness', 'FLOAT', 'POINT', np.full(count, thickness))
    write(mesh, xpbd_nodes.SIDE_SIGN, 'FLOAT', 'POINT', np.zeros(count))
    write(mesh, xpbd_nodes.SIDE_REST, 'FLOAT_VECTOR', 'POINT', np.zeros((count, 3)))
    write(mesh, 'dd_frame_time', 'FLOAT', 'POINT', np.full(count, 1 / SIM_FPS))
    write(mesh, 'dd_time_zero', 'FLOAT', 'POINT', np.full(count, scene.frame_start / SIM_FPS))
    held = np.zeros(count, dtype=bool)
    held[list(pinned)] = True
    tacked = np.zeros(count, dtype=bool)
    surface = np.zeros((count, 3))
    shares = np.zeros((count, 3))
    for vertex, binding in tacks.items():
        held[vertex] = True
        tacked[vertex] = True
        surface[vertex] = binding['vertices']
        shares[vertex] = binding['weights']
    write(mesh, 'dd_pinned', 'BOOLEAN', 'POINT', held)
    write(mesh, 'dd_tacked', 'BOOLEAN', 'POINT', tacked)
    write(mesh, 'dd_hold', 'BOOLEAN', 'POINT', np.zeros(count, dtype=bool))
    write(mesh, 'dd_pin_target', 'FLOAT_VECTOR', 'POINT', start)
    write(mesh, 'dd_tack_vertices', 'FLOAT_VECTOR', 'POINT', surface)
    write(mesh, 'dd_tack_weights', 'FLOAT_VECTOR', 'POINT', shares)
    write(mesh, 'dd_pin_compliance', 'FLOAT', 'POINT', np.where(tacked, TACK_COMPLIANCE, PIN_COMPLIANCE))
    mod = obj.modifiers.new(MODIFIER, 'NODES')
    mod.node_group = xpbd_nodes.cloth_group()
    obj.use_simulation_cache = False
    handle = bpy.data.objects.new('DD Grab Handle', None)
    garment_collection(scene).objects.link(handle)
    handle.hide_set(True)
    handle.hide_render = True
    set_input(obj, 'Grab Handle', handle)
    tag_generated(handle, 'collider')
    collider = bake_collider(context)
    set_input(obj, 'Body', collider)
    set_input(obj, 'Body Shell', bake_shell(context, collider))
    set_input(obj, 'Gravity', tuple(component / unit for component in scene.gravity))
    set_input(obj, 'Inner Substeps', LIVE_SUBSTEPS)
    set_input(obj, 'Grab Stride', GRAB_STRIDE / unit)
    set_input(obj, 'Grab Reach', GRAB_REACH / unit)
    obj.update_tag()
    return mod
