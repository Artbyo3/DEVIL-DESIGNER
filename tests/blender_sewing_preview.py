import json
import math
import sys
from pathlib import Path
from unittest.mock import patch
import bpy
from mathutils import Matrix

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import garment, sewing_preview
from devil_designer.core import EdgeRef, Session


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def fixture(name):
    session = Session()
    for index in range(3):
        left = index * .4
        height = .27 if index == 1 and name == 'mismatch' else .3
        session.add([(left, 0), (left + .2, 0), (left + .2, height), (left, height)])
    document = session.document
    first, second = [document.edge(pattern.id, edge) for pattern, edge in zip(document.patterns, (1, 3))]
    if name in {'partial', 'middle'}:
        low, high = (.4, .6) if name == 'middle' else (.2, .8)
        first = EdgeRef(first.pattern, first.start, first.end, low, high)
        second = EdgeRef(second.pattern, second.start, second.end, low, high)
    session.sew_chains([first], [second], name != 'reversed')
    if name == 'split':
        document.split_edge(document.edge(document.patterns[0].id, 1), .37)
    return document


def measure(name):
    scene = bpy.context.scene
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'panel'))
    document = fixture(name)
    scene.dd_document = document.dumps()
    scene.dd_spacing = .025
    panels = garment.build_panels(bpy.context)
    document = garment.document(scene)
    for index, panel in enumerate(panels):
        panel.matrix_world = Matrix.Translation((index * .1, index * .06, 1)) @ Matrix.Rotation(.2 * index, 4, 'Z')
    bpy.context.view_layer.update()
    if name == 'frozen_pose':
        simulation = garment.compile_garment(bpy.context)
        for frame in range(1, 4):
            scene.frame_set(frame)
            simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
        document.patterns[0].frozen = True
        scene.dd_document = document.dumps()
    if name in {'frozen', 'deactivated', 'strengthened'}:
        setattr(document.patterns[2 if name == 'deactivated' else 0], name, True)
        scene.dd_document = document.dumps()
    if name == 'inactive_seam':
        document.patterns[0].deactivated = True
        scene.dd_document = document.dumps()
    baseline = (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.collections), scene.dd_document, scene.frame_current, [tuple(tuple(row) for row in panel.matrix_world) for panel in panels])
    preview = sewing_preview.snapshot(bpy.context, document)
    after = (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.collections), scene.dd_document, scene.frame_current, [tuple(tuple(row) for row in panel.matrix_world) for panel in panels])
    check(baseline == after, name + ' inspection leaves live scene and resource counts unchanged')
    if name == 'middle':
        check('Middle-only A 40-60%' in next(iter(preview['records'].values()))['flags'], 'middle-only record is flagged in place')
    simulation = garment.compile_garment(bpy.context)
    check([list(pair) for pair in preview['pairs']] == json.loads(simulation['dd_sewing_pairs']), name + ' exact preview/compiler pairs')
    actual = {identity: {key: record[key] for key in ('pairs', 'rest_lengths')} for identity, record in preview['records'].items()}
    check(actual == json.loads(simulation['dd_sewing_inspection']), name + ' exact compiler rest contract')
    for record in preview['records'].values():
        for pair, points in zip(record['pairs'], record['world']):
            check(all(math.dist(point, simulation.data.vertices[index].co) < 1e-6 for index, point in zip(pair, points)), name + ' correspondence uses compiled arranged vertices')
    garment.reset(bpy.context)
    if name == 'equal':
        document.patterns[0].vertices[2].y += .03
        scene.dd_document = document.dumps()
        try:
            sewing_preview.snapshot(bpy.context, document)
        except ValueError as error:
            check('rebuilt panels' in str(error), 'stale panels are refused rather than approximated')
        else:
            raise AssertionError('Stale panels accepted')
    if name == 'frozen':
        baseline = len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.collections)
        with patch.object(sewing_preview, 'inspect_panels', side_effect=ValueError('probe failure')):
            try:
                sewing_preview.snapshot(bpy.context, document)
            except ValueError:
                pass
        check(baseline == (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.collections)), 'failed inspection cleans temporary resources')


devil_designer.register()
bpy.context.scene.dd_avatar = bpy.context.scene.objects['Cube']
for case in ('equal', 'mismatch', 'partial', 'middle', 'split', 'reversed', 'frozen', 'deactivated', 'strengthened', 'inactive_seam', 'frozen_pose'):
    measure(case)
print('SEWING PREVIEW PARITY PASSED', flush=True)
