import json
import math
from .density import boundary_plan


JOIN_REST_LENGTH = 0.0


def resolve_sewing(maps, plan):
    springs = set()
    records = {}
    for identity, pairs in plan.seam_pairs:
        resolved = []
        seen = set()
        for pair in pairs:
            vertices = []
            for edge, fraction in pair:
                sample, vertex = min(maps[edge.pattern][edge.start], key=lambda value: abs(value[0] - fraction))
                if abs(sample - fraction) > 1e-6:
                    raise ValueError('Sewing samples changed. Rebuild the panels.')
                vertices.append(vertex)
            first, second = vertices
            if first == second:
                continue
            key = tuple(sorted(vertices))
            springs.add(key)
            if key not in seen:
                seen.add(key)
                resolved.append(vertices)
        records[identity] = dict(pairs=resolved, rest_lengths=[JOIN_REST_LENGTH] * len(resolved))
    return springs, records


def panel_data(panels):
    maps, flat, world = {}, [], []
    for panel in panels:
        offset = len(world)
        maps[panel['dd_pattern_id']] = {key: [[fraction, offset + vertex] for fraction, vertex in values] for key, values in json.loads(panel['dd_edge_samples']).items()}
        flat.extend(tuple(item.vector)[:2] for item in panel.data.attributes['dd_rest'].data)
        world.extend(tuple(panel.matrix_world @ vertex.co) for vertex in panel.data.vertices)
    return maps, flat, world


def status(document, seam):
    mismatch = document.seam_stats(seam)[3]
    flags = []
    for side, name in ((0, 'A'), (1, 'B')):
        chain = seam.side(side)
        if len(chain) == 1:
            span = chain[0]
            low, high = sorted((span.t0, span.t1))
            if low > 1e-8 or high < 1 - 1e-8:
                prefix = 'Middle-only' if low > 1e-8 and high < 1 - 1e-8 else 'Partial'
                flags.append(f'{prefix} {name} {100 * low:.0f}-{100 * high:.0f}%')
        elif any(abs(span.t1 - span.t0) < 1 - 1e-8 for span in chain):
            flags.append('Partial ' + name)
    if seam.reverse:
        flags.append('B reversed')
    return dict(mismatch=mismatch, flags=flags, warning=mismatch > 1,
                readout=f'{mismatch:.1f}% · ' + ('Gather warning; sewing allowed.' if mismatch > 1 else 'Pass'))


def inspect_panels(context, document, panels):
    from . import garment
    maps, flat, world = panel_data(panels)
    plan = boundary_plan(document, context.scene.dd_spacing)
    springs, records = resolve_sewing(maps, plan)
    unit = garment.metres_per_unit(context.scene)
    for seam in document.seams:
        record = records[seam.id]
        record.update(status(document, seam))
        record['flat'] = [[flat[first], flat[second]] for first, second in record['pairs']]
        record['world'] = [[world[first], world[second]] for first, second in record['pairs']]
        ratios = []
        for before, after in zip(record['flat'], record['flat'][1:]):
            first, second = (math.dist(before[side], after[side]) for side in (0, 1))
            if min(first, second) > 1e-7:
                ratios.append(second / first)
        if record['warning'] and ratios and max(ratios) > min(ratios) * 1.1:
            record['flags'].append('Uneven ease risk')
        drift = []
        for pair in plan.seam_pairs:
            if pair[0] != seam.id:
                continue
            for references in pair[1]:
                for edge, fraction in references:
                    sample, vertex = min(maps[edge.pattern][edge.start], key=lambda value: abs(value[0] - fraction))
                    drift.append(math.dist(flat[vertex], document.edge_point(edge, fraction)))
        record['drift_m'] = max(drift, default=0)
        if record['drift_m'] > 1e-6:
            record['flags'].append('Pairing drift; rebuild panels')
        record['join_target_m'] = JOIN_REST_LENGTH * unit
    return dict(records=records, pairs=sorted(springs))


def snapshot(context, document):
    import bpy
    from mathutils import Vector
    from . import garment, piece_states, ui
    from .core import Document
    panels = garment.generated(context.scene, 'panel')
    if len(panels) != len(document.patterns):
        raise ValueError('Build current panels to inspect sewing.')
    expected = piece_states.without_states(document).dumps()
    for panel in panels:
        stored = panel.get('dd_document')
        if not stored or piece_states.without_states(Document.loads(stored)).dumps() != expected or panel.get('dd_spacing') != context.scene.dd_spacing or panel.get('dd_units') != garment.metres_per_unit(context.scene):
            raise ValueError('Patterns changed; sewing preview awaits rebuilt panels.')
    if not piece_states.required(document):
        return inspect_panels(context, document, panels)
    active = piece_states.active_document(document)
    if not active.patterns:
        return dict(records={}, pairs=[])
    poses = piece_states.snapshot(context, panels)
    temporary = bpy.data.scenes.new('DD Sewing Inspection')
    run_panels = []
    owned = None
    try:
        temporary.unit_settings.scale_length = context.scene.unit_settings.scale_length
        for key in ui.PROPERTIES:
            if key not in {'dd_document', 'dd_collection', 'dd_history'}:
                setattr(temporary, key, getattr(context.scene, key))
        temporary.dd_document = active.dumps()
        for obj in context.scene.objects:
            if obj.get('dd_kind') not in {'panel', 'simulation', 'anchor'} or obj.get('dd_owner') != garment.OWNER:
                temporary.collection.objects.link(obj)
        with context.temp_override(scene=temporary, view_layer=temporary.view_layers[0]):
            run_panels = garment.build_panels(context)
            owned = temporary.dd_collection
            for panel in run_panels:
                identity = panel['dd_pattern_id']
                original = next(item for item in panels if item['dd_pattern_id'] == identity)
                source_rest = [tuple(item.vector) for item in original.data.attributes['dd_rest'].data]
                target_rest = [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data]
                if source_rest == target_rest and [tuple(face.vertices) for face in original.data.polygons] == [tuple(face.vertices) for face in panel.data.polygons]:
                    for vertex, source in zip(panel.data.vertices, original.data.vertices):
                        vertex.co = source.co
                panel.matrix_world = original.matrix_world.copy()
            context.view_layer.update()
            result = inspect_panels(context, active, run_panels)
            if poses:
                replacement = {}
                offset = 0
                for panel in run_panels:
                    identity = panel['dd_pattern_id']
                    target = [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data]
                    if identity in poses:
                        replacement.update({offset + index: tuple(Vector(point)) for index, point in enumerate(piece_states.transfer(*poses[identity], target))})
                    offset += len(panel.data.vertices)
                for record in result['records'].values():
                    record['world'] = [[replacement.get(first, points[0]), replacement.get(second, points[1])] for (first, second), points in zip(record['pairs'], record['world'])]
            return result
    finally:
        owned = owned or temporary.dd_collection
        garment.remove_objects(garment.generated(temporary, 'panel'))
        bpy.data.scenes.remove(temporary)
        if owned is not None and owned.users == 0:
            bpy.data.collections.remove(owned)
