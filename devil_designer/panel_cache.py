import json
import hashlib
from dataclasses import asdict
from functools import lru_cache
from .ellipse_volumes import wrap_positions


def panel_inputs(document, pattern, index, counts, spacing, unit):
    samples = [[edge.start, edge.end, counts.samples[edge]]
               for path, _, _, _ in pattern.loops() for edge in document.edges(pattern.id, path)]
    anchors = [asdict(anchor) for anchor in document.anchors if anchor.pattern == pattern.id]
    return json.dumps([1, asdict(pattern), index, samples, anchors, spacing, unit, document.uv_layout],
                      sort_keys=True, separators=(',', ':'))


def panel_pose(context, pattern):
    from . import garment, live_panels
    scene = context.scene
    avatar = scene.dd_avatar
    if pattern.arrangement:
        try:
            _, resolved = live_panels.point_frame(context, pattern.arrangement)
            return json.dumps([resolved, scene.dd_clearance, live_panels.has_opposite_piece(context, pattern, pattern.arrangement)], sort_keys=True, separators=(',', ':'))
        except ValueError:
            return None
    if pattern.placement_mode == 'LEGACY':
        return ''
    return json.dumps([list(vector) for vector in garment.bounds(avatar)] if avatar else None,
                      separators=(',', ':')) + str(scene.dd_clearance)


def panel_output(obj):
    from array import array
    mesh = obj.data
    payload = [[len(mesh.vertices), len(mesh.edges), len(mesh.loops), len(mesh.polygons),
                mesh.shape_keys is not None, mesh.has_custom_normals],
               [obj.get(key) for key in ('dd_edge_samples', 'dd_anchor_indices', 'dd_boundaries',
                                       'dd_arrangement_base', 'dd_arrangement_key')],
               [[attribute.name, attribute.data_type, attribute.domain] for attribute in mesh.attributes],
               [[layer.name, layer.active_render] for layer in mesh.uv_layers]]
    digest = hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode())
    def include(items, property_name, width, code):
        values = array(code, [0]) * (len(items) * width)
        items.foreach_get(property_name, values)
        digest.update(values.tobytes())
    include(mesh.vertices, 'co', 3, 'f')
    include(mesh.edges, 'vertices', 2, 'i')
    include(mesh.loops, 'vertex_index', 1, 'i')
    include(mesh.polygons, 'loop_start', 1, 'i')
    include(mesh.polygons, 'loop_total', 1, 'i')
    include(mesh.polygons, 'material_index', 1, 'i')
    include(mesh.polygons, 'use_smooth', 1, 'b')
    for layer in mesh.uv_layers:
        include(layer.data, 'uv', 2, 'f')
    for attribute in mesh.attributes:
        if attribute.name == 'dd_rest':include(attribute.data, 'vector', 3, 'f')
        if attribute.name in {'dd_piece', '.sculpt_face_set'}:include(attribute.data, 'value', 1, 'i')
    return digest.hexdigest()


@lru_cache(maxsize=16)
def wrapped_positions(payload):
    vertices, resolved, width, minimum, minimum_clearance = json.loads(payload)
    return tuple(wrap_positions(vertices, resolved, width, minimum, minimum_clearance))


_body_trees = {}
_surfaces = {}


def body_tree(context):
    import numpy
    from mathutils.bvhtree import BVHTree
    from .live_panels import avatar_signature
    signature = avatar_signature(context)
    if signature not in _body_trees:
        avatar = context.scene.dd_avatar
        evaluated = avatar.evaluated_get(context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            local = numpy.zeros(len(mesh.vertices) * 3, dtype=numpy.float32)
            mesh.vertices.foreach_get('co', local)
            faces = numpy.zeros(len(mesh.loop_triangles) * 3, dtype=numpy.int32)
            mesh.loop_triangles.foreach_get('vertices', faces)
            matrix = numpy.array(evaluated.matrix_world)
            world = local.reshape(-1, 3).astype(float) @ matrix[:3, :3].T + matrix[:3, 3]
            tree = BVHTree.FromPolygons(world.tolist(), faces.reshape(-1, 3).tolist(), all_triangles=True)
        finally:
            evaluated.to_mesh_clear()
        _body_trees.clear()
        _body_trees[signature] = tree
    return _body_trees[signature]


def checked_surface(context, pattern, vertices, triangles, edges, frame, resolved, unit, record):
    import numpy
    from .live_panels import avatar_signature, checked_positions
    vertices = numpy.ascontiguousarray(vertices, dtype=float)
    digest = hashlib.sha256(json.dumps([resolved, record, unit, avatar_signature(context)], separators=(',', ':')).encode())
    for array in (vertices, numpy.ascontiguousarray(triangles, dtype=numpy.int32), numpy.ascontiguousarray(edges, dtype=numpy.int32)):
        digest.update(array.tobytes())
    key = digest.hexdigest()
    if key not in _surfaces:
        if len(_surfaces) >= 32:
            del _surfaces[next(iter(_surfaces))]
        _surfaces[key] = checked_positions(context, pattern, vertices, triangles, edges, record, frame, resolved, unit)
    return _surfaces[key]


def clear_arrangement_caches():
    _body_trees.clear()
    _surfaces.clear()
