import json
import csv
import hashlib
import math
import os
import sys
from pathlib import Path
import bpy
from mathutils import Matrix
ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.workspace import prepare_scratch
prepare_scratch()
import devil_designer
from devil_designer import garment
from devil_designer.core import Document, EdgeRef, Session
from devil_designer.density import boundary_plan


def chain_fraction(document, chain, reference, fraction):
    prefix = 0
    for span in chain:
        length = document.edge_length(span)
        if span.full() == reference.full() and min(span.t0, span.t1) - 1e-8 <= fraction <= max(span.t0, span.t1) + 1e-8:
            return (prefix + length * (fraction - span.t0) / (span.t1 - span.t0)) / document.chain_length(chain)
        prefix += length
    raise ValueError('Compiler reference is outside the stored sewing chain.')


def fixture(name):
    session = Session(Document())
    sleeve = name.startswith('sleeve')
    width, height = (.16, .6) if sleeve else (.2, .3)
    if name.startswith('trousers'):
        width, height = .22, .9
    sizes = [(width, height), (width, height * (.9 if name == 'mismatch_10' else 1))]
    if sleeve:
        sizes.extend([(width, .05)] * 2)
    for index, (wide, tall) in enumerate(sizes):
        left = index * .4
        session.add([(left, 0), (left + wide, 0), (left + wide, tall), (left, tall)])
        session.document.patterns[-1].name = ('Front', 'Back', 'Cuff front', 'Cuff back')[index]
    doc = session.document
    first, second = doc.patterns[:2]
    edge_a, edge_b = doc.edge(first.id, 1), doc.edge(second.id, 3)
    if name == 'partial':
        edge_a = EdgeRef(edge_a.pattern, edge_a.start, edge_a.end, .2, .8)
        edge_b = EdgeRef(edge_b.pattern, edge_b.start, edge_b.end, .2, .8)
    if name == 'trousers_middle_record':
        edge_a = EdgeRef(edge_a.pattern, edge_a.start, edge_a.end, .4, .6)
        edge_b = EdgeRef(edge_b.pattern, edge_b.start, edge_b.end, .4, .6)
    if name == 'partial_mn':
        edge_a = EdgeRef(edge_a.pattern, edge_a.start, edge_a.end, .2, 1)
        extra = doc.edge(first.id, 2)
        extra = EdgeRef(extra.pattern, extra.start, extra.end, 0, .3)
        session.sew_chains([edge_a, extra], [edge_b], True)
    elif name != 'sleeve_long_to_cuff':
        session.sew_chains([edge_a], [edge_b], name != 'reversed')
    if sleeve:
        session.sew_chains([doc.edge(first.id, 3)], [doc.edge(second.id, 1)], True)
        for index, (panel, cuff) in enumerate(zip(doc.patterns[:2], doc.patterns[2:])):
            session.sew_chains([doc.edge(panel.id, 1 if name == 'sleeve_long_to_cuff' and index == 0 else 0)], [doc.edge(cuff.id, 2)], True)
        for edge in (1, 3):
            session.sew_chains([doc.edge(doc.patterns[2].id, edge)], [doc.edge(doc.patterns[3].id, 4 - edge)], True)
    doc.validate()
    if name == 'trousers_nonuniform_nodes':
        doc.split_edge(doc.edge(first.id, 1), .13)
        doc.split_edge(doc.edge(first.id, 2), .67)
        doc.validate()
    return doc


def measure(name):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.dd_collection = None
    scene.frame_set(1)
    scene.dd_spacing = .025
    scene.dd_quality, scene.dd_frames = 8, 35
    scene.dd_pin_top, scene.dd_self_collision = False, True
    sleeve = name.startswith('sleeve')
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.05, depth=.8, location=(0 if sleeve else 5, 0, 1.1))
    scene.dd_avatar = bpy.context.object
    scene.dd_document = fixture(name).dumps()
    panels = garment.build_panels(bpy.context)
    doc = garment.document(scene)
    for index, panel in enumerate(panels):
        pattern = doc.find(panel['dd_pattern_id'])
        center_y = sum(point[1] for point in pattern.points) / len(pattern.points)
        panel.matrix_world = Matrix.Translation((0, -.065 if index % 2 == 0 else .065, (.8 if index < 2 else .75) + center_y)) @ Matrix.Rotation(math.pi if index % 2 else 0, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X')
    bpy.context.view_layer.update()
    original_meshes = [panel.data.as_pointer() for panel in panels]
    if name == 'edited':
        doc.patterns[0].vertices[2].y += .06
    if name == 'split':
        doc.split_edge(doc.edge(doc.patterns[0].id, 1), .37)
    if name == 'remeshed':
        scene.dd_spacing = .018
    scene.dd_document = doc.dumps()
    from devil_designer.sewing_preview import snapshot as preview_snapshot
    preview_before = None
    try:
        preview_before = preview_snapshot(bpy.context, doc)
    except ValueError:
        assert name in {'edited', 'split', 'remeshed'}
    simulation = garment.compile_garment(bpy.context)
    preview = preview_before or preview_snapshot(bpy.context, garment.document(scene))
    inspection = json.loads(simulation['dd_sewing_inspection'])
    compiled_pairs = json.loads(simulation['dd_sewing_pairs'])
    assert [list(pair) for pair in preview['pairs']] == compiled_pairs
    assert {identity: {key: record[key] for key in ('pairs', 'rest_lengths')} for identity, record in preview['records'].items()} == inspection
    native_data = None
    if os.environ.get('DD_NATIVE_PROBE') == '1':
        from tools.sewing_native_probe import modifier_layout, snapshot
        native_data = snapshot(simulation, modifier_layout(ROOT / 'scratch' / 'native-layout.blend'), bpy.context)
        native_join = [spring for spring in native_data['springs'] if spring['type'] & 32]
        assert {tuple(spring['pair']) for spring in native_join} == {tuple(pair) for pair in compiled_pairs}
        assert all(spring['rest_length'] == 0.0 and spring['linear_stiffness'] == 1.0 for spring in native_join)
    panels = garment.generated(scene, 'panel')
    doc = garment.document(scene)
    initial = [panel.matrix_world @ vertex.co for panel in panels for vertex in panel.data.vertices]
    compiled_fingerprint = hashlib.sha256(json.dumps(dict(vertices=[tuple(vertex.co) for vertex in simulation.data.vertices], edges=sorted(tuple(edge.vertices) for edge in simulation.data.edges), faces=[tuple(face.vertices) for face in simulation.data.polygons], pairs=json.loads(simulation['dd_sewing_pairs'])), sort_keys=True).encode()).hexdigest()
    plan = boundary_plan(doc, scene.dd_spacing)
    maps, flat, offset = {}, [], 0
    for panel in panels:
        maps[panel['dd_pattern_id']] = {key: [(fraction, offset + index) for fraction, index in samples] for key, samples in json.loads(panel['dd_edge_samples']).items()}
        flat.extend(tuple(item.vector) for item in panel.data.attributes['dd_rest'].data)
        offset += len(panel.data.vertices)
    predicted, seams = set(), []
    for identity, pairs in plan.seam_pairs:
        seam = next(item for item in doc.seams if item.id == identity)
        indices, errors, drift, distribution = [], [], [], []
        for pair in pairs:
            resolved = []
            for edge, fraction in pair:
                actual, index = min(maps[edge.pattern][edge.start], key=lambda item: abs(item[0] - fraction))
                errors.append(abs(actual - fraction))
                drift.append(math.dist(flat[index][:2], doc.edge_point(edge, fraction)))
                resolved.append(index)
            if resolved[0] != resolved[1] and resolved not in indices:
                indices.append(resolved)
                predicted.add(tuple(sorted(resolved)))
                progress = [chain_fraction(doc, seam.side(side), *pair[side]) for side in (0, 1)]
                distribution.append(dict(a_chain_fraction=progress[0], b_chain_fraction=progress[1],
                                         b_sewing_progress=1 - progress[1] if seam.reverse else progress[1],
                                         a_edge_fraction=pair[0][1], b_edge_fraction=pair[1][1],
                                         vertex_a=resolved[0], vertex_b=resolved[1]))
        intervals = [[math.dist(flat[before[side]], flat[after[side]]) for before, after in zip(indices, indices[1:])] for side in (0, 1)]
        ratios = [second / first for first, second in zip(*intervals) if first > 1e-7 and second > 1e-7]
        gaps = [(initial[first] - initial[second]).length * 1000 for first, second in indices]
        seams.append(dict(identity=identity, names=[doc.find(seam.side(side)[0].pattern).name for side in (0, 1)], reverse=seam.reverse,
                          lengths_m=list(doc.seam_stats(seam)[:2]), mismatch_percent=doc.seam_stats(seam)[3], pairs=indices,
                          flat_drift_max_mm=max(drift, default=0) * 1000, fraction_error=max(errors, default=0),
                          ease_ratio_min=min(ratios, default=0), ease_ratio_max=max(ratios, default=0),
                          unique_targets=[len({pair[side] for pair in indices}) for side in (0, 1)],
                          distribution=distribution,
                          normalized_mapping_error_max=max(abs(row['a_chain_fraction'] - row['b_sewing_progress']) for row in distribution),
                          source_edge_fraction_ranges=[[min(row[key] for row in distribution), max(row[key] for row in distribution)] for key in ('a_edge_fraction', 'b_edge_fraction')],
                          initial_gap_mean_mm=sum(gaps) / len(gaps), initial_gap_max_mm=max(gaps),
                          target_z_range_m=[min(initial[pair[1]].z for pair in indices), max(initial[pair[1]].z for pair in indices)]))
    compiled = {tuple(pair) for pair in json.loads(simulation['dd_sewing_pairs'])}
    surface = {tuple(sorted((first, second))) for face in simulation.data.polygons for first, second in zip(face.vertices, list(face.vertices)[1:] + [face.vertices[0]])}
    rest_errors = [abs((initial[first] - initial[second]).length - math.dist(flat[first], flat[second])) * 1000 for first, second in surface]
    native_structural_errors = [abs(spring['rest_length'] - math.dist(*(flat[index] for index in spring['pair']))) * 1000 for spring in native_data['springs'] if spring['type'] & 2] if native_data else []
    frames = {}
    for frame in range(1, 32):
        scene.frame_set(frame)
        evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
        points = [vertex.co.copy() for vertex in evaluated.data.vertices]
        if frame not in (1, 2, 3, 5, 10, 31):
            continue
        states = []
        for seam in seams:
            gaps = [(points[first] - points[second]).length * 1000 for first, second in seam['pairs']]
            strains = []
            for side in (0, 1):
                for before, after in zip(seam['pairs'], seam['pairs'][1:]):
                    rest = (initial[before[side]] - initial[after[side]]).length
                    if rest > 1e-7:
                        strains.append(abs((points[before[side]] - points[after[side]]).length / rest - 1) * 100)
            signed_bins = []
            for side in (0, 1):
                bins = []
                segments = list(zip(seam['pairs'], seam['pairs'][1:]))
                for third in range(3):
                    subset = segments[len(segments) * third // 3:len(segments) * (third + 1) // 3]
                    rest = sum((initial[before[side]] - initial[after[side]]).length for before, after in subset)
                    length = sum((points[before[side]] - points[after[side]]).length for before, after in subset)
                    bins.append(100 * (length / max(rest, 1e-15) - 1))
                signed_bins.append(bins)
            states.append(dict(gap_mean_mm=sum(gaps) / len(gaps), gap_max_mm=max(gaps), absolute_stretch_mean_percent=sum(strains) / max(1, len(strains)), absolute_stretch_max_percent=max(strains, default=0), side_signed_stretch_thirds_percent=signed_bins))
        spans, offset = [], 0
        for panel in panels[:2]:
            subset = points[offset:offset + len(panel.data.vertices)]
            spans.append(max(point.z for point in subset) - min(point.z for point in subset))
            offset += len(panel.data.vertices)
        frames[str(frame)] = dict(seams=states, panel_z_spans_m=spans, center_z_m=sum(point.z for point in points) / len(points))
        frames[str(frame)]['paired_midpoint_z_ranges_m'] = [[min((points[first].z + points[second].z) / 2 for first, second in seam['pairs']), max((points[first].z + points[second].z) / 2 for first, second in seam['pairs'])] for seam in seams]
    for seam in seams:
        seam['pair_count'] = len(seam.pop('pairs'))
    clearance = [(math.hypot(point.x, point.y) - .05) * 1000 for point in initial]
    return dict(name=name, vertices=len(initial), pair_symmetric_difference=len(predicted ^ compiled), seams=seams, frames=frames,
                native_data=native_data,
                native_structural_rest_max_error_mm=max(native_structural_errors, default=0),
                native_structural_rest_mean_error_mm=sum(native_structural_errors) / max(1, len(native_structural_errors)),
                preview_pair_diff=0, preview_rest_diff=0,
                compiled_fingerprint=compiled_fingerprint,
                panels_rebuilt_on_compile=original_meshes != [panel.data.as_pointer() for panel in panels],
                exposed_rest_properties=[prop.identifier for prop in simulation.modifiers[0].settings.bl_rna.properties if 'rest' in prop.identifier or 'sewing' in prop.identifier],
                structural_rest_distance_error_max_mm=max(rest_errors), structural_rest_distance_error_mean_mm=sum(rest_errors) / len(rest_errors),
                initial_arm_clearance_min_mm=min(clearance) if sleeve else None,
                initial_arm_penetrating_vertices=sum(value < 0 for value in clearance) if sleeve else None,
                native_sewing_rest_lengths_exposed=hasattr(simulation.modifiers[0], 'sewing_rest_lengths'))


def main():
    devil_designer.register()
    if os.environ.get('DD_NATIVE_PROBE') == '1':
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'scratch' / 'native-layout.blend'), compress=False)
    results = []
    for name in ('equal', 'mismatch_10', 'partial', 'partial_mn', 'edited', 'split', 'remeshed', 'reversed', 'sleeve_correct', 'sleeve_long_to_cuff', 'trousers_full', 'trousers_middle_record', 'trousers_nonuniform_nodes'):
        results.append(measure(name))
        (ROOT / 'scratch' / os.environ.get('DD_DIAG_REPORT', 'sewing-diagnosis.json')).write_text(json.dumps(results, indent=2), encoding='utf-8')
        print('MEASURED', name, flush=True)
    with (ROOT / 'scratch' / os.environ.get('DD_DIAG_REPORT', 'sewing-diagnosis.json').replace('.json', '-pairs.csv')).open('w', newline='', encoding='utf-8') as stream:
        fields = ['fixture', 'seam', 'pair', 'a_chain_fraction', 'b_chain_fraction', 'b_sewing_progress', 'a_edge_fraction', 'b_edge_fraction', 'vertex_a', 'vertex_b']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for seam_index, seam in enumerate(result['seams']):
                for pair_index, row in enumerate(seam['distribution']):
                    writer.writerow(dict(fixture=result['name'], seam=seam_index + 1, pair=pair_index + 1, **row))
    bpy.ops.wm.quit_blender()


if __name__ == '__main__':
    main()
