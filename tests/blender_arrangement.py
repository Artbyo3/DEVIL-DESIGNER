import math
from pathlib import Path
import sys
from unittest.mock import patch

import bpy
from mathutils import Vector


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import devil_designer
from devil_designer import arrangement, garment, history
from devil_designer.core import Document, Session


devil_designer.register()
scene = bpy.context.scene
bpy.ops.mesh.primitive_cube_add(size=1, location=(3, 4, 1))
avatar = bpy.context.object
avatar.scale = (1.4, .5, 2)
bpy.context.view_layer.update()
scene.dd_avatar = avatar
scene.dd_spacing = .04

for mode, names in (
        ('BODICE', ('Front left', 'Front right', 'Back left', 'Back right')),
        ('SLEEVES', ('Left upper sleeve', 'Left lower sleeve', 'Right upper sleeve', 'Right lower sleeve')),
        ('BODICE', tuple(f'Pattern {index + 1:02}' for index in range(5))),
        ('SLEEVES', tuple(f'Pattern {index + 1:02}' for index in range(5))),
        ('BODICE', ('Pattern 01', 'Pattern 02', 'Z Front 1', 'Z Front 2')),
        ('SLEEVES', ('Pattern 01', 'Pattern 02', 'Z Right 1', 'Z Right 2')),
        ('SKIRT', tuple(f'Skirt panel {index}' for index in range(6)))):
    session = Session()
    for index, name in enumerate(names):
        offset = index * .5
        session.add([(offset, 0), (offset + .2, 0), (offset + .2, .3), (offset, .3)])
        session.document.patterns[-1].name = name
        session.document.patterns[-1].placement_mode = 'LEGACY'
    scene.dd_document = session.document.dumps()
    plan = arrangement.layout_plan(((piece.id, piece.name) for piece in session.document.patterns),
                                   garment.bounds(avatar), mode)
    with patch.object(garment, 'build_panels', wraps=garment.build_panels) as build:
        assert arrangement.arrange(bpy.context, mode) == len(names)
        assert build.call_count == 1
        panels = {panel['dd_pattern_id']: panel for panel in garment.generated(scene, 'panel')}
        meshes = {identity: panel.data for identity, panel in panels.items()}
        for target in plan:
            panel = panels[target.pattern_id]
            normal = Vector(target.normal)
            expected = Vector(target.point) + normal * scene.dd_clearance / garment.metres_per_unit(scene)
            assert (panel.matrix_world.translation - expected).length < 1e-5
            assert (panel.matrix_world.to_3x3() @ Vector((0, 0, 1)) - normal).length < 1e-5
            assert all(math.isfinite(value) for row in panel.matrix_world for value in row)
        assert arrangement.arrange(bpy.context, mode) == len(names)
        assert build.call_count == 1
        assert all(panels[panel['dd_pattern_id']] == panel and meshes[panel['dd_pattern_id']] == panel.data
                   for panel in garment.generated(scene, 'panel'))
    print(f'PASS: {mode}, {len(names)} pieces, real placement, build once, reuse identities', flush=True)

document = garment.document(scene)
document.patterns[-1].name = 'Front back'
scene.dd_document = document.dumps()
before = {panel['dd_pattern_id']: panel.matrix_world.copy() for panel in garment.generated(scene, 'panel')}
try:
    arrangement.arrange(bpy.context, 'BODICE')
except ValueError:
    pass
else:
    raise AssertionError('Contradictory labels must be rejected before placement.')
assert all(panel.matrix_world == before[panel['dd_pattern_id']] for panel in garment.generated(scene, 'panel'))
print('PASS: invalid layout preserves every real panel transform', flush=True)

history_session = Session()
history_session.add([(0, 0), (.4, 0), (.4, .6), (0, .6)])
history_session.add([(.6, 0), (1, 0), (1, .6), (.6, .6)])
history_session.document.patterns[0].name = 'Front panel'
history_session.document.patterns[1].name = 'Back panel'
for piece in history_session.document.patterns:piece.placement_mode='LEGACY'
scene.dd_document = history_session.document.dumps()
scene.dd_history = history.store(history_session)
count = len(history_session.undo_stack)
assert arrangement.arrange(bpy.context, 'BODICE') == 2
history_session.document = Document.loads(scene.dd_document)
scene.dd_history = history.store(history_session)
restored = Session(Document.loads(scene.dd_document))
assert history.restore(restored, scene.dd_history)
assert len(restored.undo_stack) == count and count > 0
assert restored.history()
print('PASS: arrangement preserves persistent history after document reconciliation', flush=True)

import runpy
runpy.run_path(str(Path(__file__).resolve().parent / 'blender_ellipse.py'), run_name='__main__')


def unusable_body(name, vertices, faces, scale=(1, 1, 1)):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    body = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(body)
    body.scale = scale
    return body


from devil_designer import starters
from devil_designer.measurements import estimate_body_measurements

garment.forget_drape()
garment.reset(bpy.context)
arrangement.cancel_fits()
bpy.ops.mesh.primitive_cube_add(size=1)
tee = starters.create_tee_starter(estimate_body_measurements(bpy.context.object, scene), 'COTTON').dumps()
DATA_TERMS = ('triangle', 'vertices', 'vertex', 'bounds', 'degenerate', 'finite', 'three-dimensional')
for label, vertices, faces, scale in (
        ('vertices without faces', [(0, 0, 0), (1, 0, 0), (0, 1, 1), (1, 1, 2)], [], (1, 1, 1)),
        ('no vertices', [], [], (1, 1, 1)),
        ('flat plane', [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2, 3)], (1, 1, 1)),
        ('single triangle', [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], (1, 1, 1)),
        ('vertical wall', [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [(0, 1, 2, 3)], (1, 1, 1)),
        ('scaled to zero', [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)], (0, 0, 0))):
    arrangement.cancel_fits()
    body = unusable_body(label, vertices, faces, scale)
    bpy.context.view_layer.update()
    scene['dd_arrangement_message'] = ''
    scene.dd_avatar = body
    while arrangement.pending_job(bpy.context) is not None:
        arrangement._fit_timer()
    shown = scene.get('dd_arrangement_message', '')
    assert shown == arrangement.UNUSABLE_AVATAR, (label, shown)
    try:
        arrangement.ensure_volumes(bpy.context)
    except ValueError as error:
        assert str(error) == arrangement.UNUSABLE_AVATAR, (label, str(error))
    else:
        raise AssertionError(label + ' must be refused as a body')
    if faces:
        scene.dd_document = tee
        scene.pop('dd_last_error', None)
        try:
            bpy.ops.devil_designer.simulate('EXEC_DEFAULT')
        except RuntimeError:
            pass
        assert scene.get('dd_last_error', '') == arrangement.UNUSABLE_AVATAR, (label, scene.get('dd_last_error', ''))
    assert not any(term in shown.lower() for term in DATA_TERMS), shown
    print('PASS: a ' + label + ' body is refused in plain words when picked and at Simulate', flush=True)
    scene.dd_avatar = None
    bpy.data.objects.remove(body, do_unlink=True)
