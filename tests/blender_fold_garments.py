import json
import math
import statistics
from pathlib import Path
import bpy
from devil_designer import garment, xpbd
from devil_designer.core import Session
from devil_designer.folding import author_fold
from tests.blender_folding import _angles, _crease_faces


def _run_trial(document, check):
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
    plain_set = set(range(plain_offset, plain_offset+len(plain.data.vertices)))
    simulation = garment.compile_garment(bpy.context)
    initial = [tuple(vertex.co) for vertex in simulation.data.vertices]
    initial_signed = _angles(simulation.data, creases, signed=True)
    springs = json.loads(simulation['dd_sewing_pairs'])
    edges = [tuple(edge.vertices) for edge in simulation.data.edges if all(index in plain_set for index in edge.vertices)]
    samples = []
    for frame in range(scene.frame_start, scene.frame_start+121):
        scene.frame_set(frame)
        evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
        if frame in (scene.frame_start+60, scene.frame_start+120):
            samples.append(dict(frame=frame, angles=_angles(evaluated.data, creases)))
    xpbd.refine(bpy.context, simulation)
    evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
    final = [tuple(vertex.co) for vertex in evaluated.data.vertices]
    check(all(math.isfinite(value) and abs(value) < 10 for point in final for value in point), 'mixed folded and non-folded garment remains finite after 120 simulated frames')
    sewn = {index for pair in springs for index in pair}
    ratios = [math.dist(final[left], final[right])/math.dist(initial[left], initial[right]) for left,right in edges
              if math.dist(initial[left], initial[right]) > 1e-9 and not {left, right} & sewn]
    seam_gap = max((math.dist(final[left], final[right]) for left,right in springs), default=0)
    print('FOLD_RATIOS', round(max(ratios), 3), round(sorted(ratios)[int(len(ratios)*.99)], 3), round(seam_gap, 4), flush=True)
    check(max(ratios) < 1.3, 'non-fold panel away from the seam stays below 30 percent stretch at Keep quality')
    check(seam_gap < .01, 'mixed garment sewing closes inside the Keep weld distance')
    final_signed = _angles(evaluated.data, creases, signed=True)
    check(all(before*after > 0 for before,after in zip(initial_signed,final_signed)), 'whole-garment simulation preserves each mountain and valley direction')
    check(all(angle >= 105 for sample in samples for angle in sample['angles']), 'whole-garment knife or box pleat retains at least 105 degrees at frames 61 and 121')
    return dict(samples=samples, vertices=len(final), plain_max_edge_ratio=max(ratios), plain_median_edge_ratio=statistics.median(ratios), max_sewing_gap_m=seam_gap)


def run(check):
    scene = bpy.context.scene
    root = Path(__file__).resolve().parents[1]
    scene.dd_pin_top = True
    report = dict(blender=bpy.app.version_string, mocked=False, spacing_m=scene.dd_spacing, quality=scene.dd_quality, garments=[])
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
        report['garments'].append(dict(style=style, trial=_run_trial(session.document.dumps(), check)))
        (root/'scratch'/'fold-mixed-garment-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        check('FINISHED' in bpy.ops.devil_designer.keep_drape(), style + ' mixed garment finalizes through the real Keep operator')
        kept = garment.generated(scene,'final')[-1]
        check(len(kept.data.polygons) > 0 and kept.data.uv_layers.active is not None, style + ' mixed garment Keep retains real faces and UVs')
    garment.reset(bpy.context)
    scene.unit_settings.scale_length = .01
    simulation = garment.compile_garment(bpy.context)
    thickness = simulation.data.attributes['dd_self_thickness'].data[0].value
    check(abs(thickness-.6) < 1e-5, 'self-contact thickness stays physical with scaled scene units')
    garment.reset(bpy.context)
    scene.unit_settings.scale_length = 1
    return report
