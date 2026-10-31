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
            return json.dumps([resolved, scene.dd_clearance], sort_keys=True, separators=(',', ':'))
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
