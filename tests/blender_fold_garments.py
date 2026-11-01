import json
import math
import statistics
import time
from pathlib import Path
import bpy
from devil_designer import garment
from devil_designer.core import Session
from devil_designer.folding import author_fold
from tests.blender_folding import _angles, _crease_faces


def _run_trial(document, distance, check):
    scene = bpy.context.scene
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'final'))
    scene.dd_document = document
    panels = garment.build_panels(bpy.context, force_rebuild=True)
    ordered = garment.generated(scene, 'panel')
    folded = next(panel for panel in panels if panel.get('dd_pattern_id') == garment.document(scene).patterns[0].id)
    pattern = garment.document(scene).patterns[0]
    offset = sum(len(panel.data.vertices) for panel in ordered[:ordered.index(folded)])
    creases = [[tuple(tuple(index+offset for index in face) for face in pair) for pair in pairs] for pairs in _crease_faces(folded, pattern)]
    plain = next(panel for panel in ordered if panel != folded)
    plain_offset = sum(len(panel.data.vertices) for panel in ordered[:ordered.index(plain)])
    plain_indices = list(range(plain_offset, plain_offset+len(plain.data.vertices)))
    simulation = garment.compile_garment(bpy.context)
    cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
    check(abs(cloth.collision_settings.self_distance_min-.001) < 1e-8, 'fold-containing whole garment automatically compiles with 1 mm self-collision')
    if distance == .003:
        cloth.collision_settings.self_distance_min = distance
    check(abs(cloth.collision_settings.self_distance_min-distance) < 1e-8, 'timing trial uses its declared whole-garment collision distance')
    faces = [tuple(face.vertices) for face in simulation.data.polygons]
    initial = [tuple(vertex.co) for vertex in simulation.data.vertices]
    initial_signed = _angles(simulation.data, creases, signed=True)
    uv = [tuple(item.uv) for item in simulation.data.uv_layers.active.data]
    springs = json.loads(simulation['dd_sewing_pairs'])
    plain_set = set(plain_indices)
    edges = [tuple(edge.vertices) for edge in simulation.data.edges if all(index in plain_set for index in edge.vertices)]
    samples = []
    started = time.perf_counter()
    for frame in range(scene.frame_start, scene.frame_start+121):
        scene.frame_set(frame)
        evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
        if frame in (scene.frame_start+60, scene.frame_start+120):
            samples.append(dict(frame=frame, angles=_angles(evaluated.data, creases)))
    elapsed = time.perf_counter()-started
    final = [tuple(vertex.co) for vertex in evaluated.data.vertices]
    check(all(math.isfinite(value) and abs(value) < 10 for point in final for value in point), 'mixed folded and non-folded garment remains finite after 120 simulated frames')
    ratios = [math.dist(final[left], final[right])/math.dist(initial[left], initial[right]) for left,right in edges if math.dist(initial[left], initial[right]) > 1e-9]
    seam_gap = max((math.dist(final[left], final[right]) for left,right in springs), default=0)
    record = dict(distance_m=distance, seconds=elapsed, samples=samples, vertices=len(final), plain_vertices=len(plain_indices),
                  plain_max_edge_ratio=max(ratios), plain_median_edge_ratio=statistics.median(ratios), max_sewing_gap_m=seam_gap)
    check(max(ratios) < 1.25, 'non-fold panel in mixed garment stays below 25 percent local edge stretch')
    check(seam_gap < .003, 'mixed garment sewing closes below 3 mm')
    if distance == .001:
        final_signed = _angles(evaluated.data, creases, signed=True)
        check(all(before*after > 0 for before,after in zip(initial_signed,final_signed)), 'whole-garment simulation preserves each mountain and valley direction')
        check(all(angle >= 105 for sample in samples for angle in sample['angles']), 'whole-garment knife or box pleat retains at least 105 degrees at frames 61 and 121')
    return record, dict(initial=initial, faces=faces, uv=uv, springs=springs), [final[index] for index in plain_indices]


def run(check):
    scene = bpy.context.scene
    root = Path(__file__).resolve().parents[1]
    scene.dd_pin_top = True
    scene.dd_frames = 125
    report = dict(blender=bpy.app.version_string, mocked=False, spacing_m=scene.dd_spacing, quality=scene.dd_quality,
                  evaluated_frames=121, repeat_count=3, baseline='same initial geometry and classic cloth, 3 mm whole-garment self-collision', garments=[])
    for style in ('KNIFE', 'BOX'):
        session = Session()
        session.add([(0,0),(.4,0),(.4,.5),(0,.5)])
        folded = session.document.patterns[0]
        session.add_path([(.2,0),(.2,.5)])
        author_fold(session, style)
        session.add([(.4,0),(.65,0),(.65,.5),(.4,.5)])
        plain = session.document.patterns[1]
        session.sew(session.document.edge(folded.id,1),session.document.edge(plain.id,3))
        check(not plain.features and len(session.document.seams) == 1, style + ' fixture sews an ordinary non-fold panel to the folded panel')
        document = session.document.dumps()
        garment_report = dict(style=style, trials=[], plain_displacements=[])
        for repeat in range(3):
            pair = {}
            for distance in ((.003,.001) if repeat%2 == 0 else (.001,.003)):
                record, snapshot, positions = _run_trial(document,distance,check)
                record['repeat'] = repeat+1
                garment_report['trials'].append(record)
                pair[distance] = (snapshot,positions)
            check(pair[.003][0] == pair[.001][0], style + ' comparison preserves initial vertices, faces, UVs and sewing springs exactly')
            displacements = [math.dist(left,right) for left,right in zip(pair[.003][1],pair[.001][1])]
            garment_report['plain_displacements'].append(dict(repeat=repeat+1, maximum_m=max(displacements), rms_m=math.sqrt(statistics.mean(value*value for value in displacements))))
        baseline = statistics.median(trial['seconds'] for trial in garment_report['trials'] if trial['distance_m'] == .003)
        candidate = statistics.median(trial['seconds'] for trial in garment_report['trials'] if trial['distance_m'] == .001)
        garment_report['timing'] = dict(baseline_median_seconds=baseline, candidate_median_seconds=candidate, candidate_to_baseline=candidate/baseline)
        garment_report['candidate_angles_frame_121'] = [trial['samples'][-1]['angles'] for trial in garment_report['trials'] if trial['distance_m'] == .001]
        report['garments'].append(garment_report)
        (root/'scratch'/'fold-mixed-garment-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        garment.reset(bpy.context)
        _run_trial(document,.001,check)
        check('FINISHED' in bpy.ops.devil_designer.keep_drape(), style + ' mixed garment finalizes through the real Keep operator')
        kept = garment.generated(scene,'final')[-1]
        check(len(kept.data.polygons) > 0 and kept.data.uv_layers.active is not None, style + ' mixed garment Keep retains real faces and UVs')
    garment.reset(bpy.context)
    scene.unit_settings.scale_length = .01
    simulation = garment.compile_garment(bpy.context)
    cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
    check(abs(cloth.collision_settings.self_distance_min-.1) < 1e-7, 'fold-containing garment uses one physical millimetre with scaled scene units')
    garment.reset(bpy.context)
    scene.unit_settings.scale_length = 1
    session = Session()
    session.add([(0,0),(.4,0),(.4,.5),(0,.5)])
    scene.dd_document = session.document.dumps()
    simulation = garment.compile_garment(bpy.context)
    cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
    check(abs(cloth.collision_settings.self_distance_min-.003) < 1e-8, 'garments without folds or seam shrink retain 3 mm self-collision')
    return report
