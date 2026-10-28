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
