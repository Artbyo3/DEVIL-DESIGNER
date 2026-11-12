import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
report = ROOT / 'scratch' / 'refit-report.json'
state = {'step': 0, 'passed': []}


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    state['passed'].append(label)


def skin_body(name, scale, location):
    from mathutils import Vector

    def capsule(radius, start, end):
        start, end = Vector(start), Vector(end)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=(end - start).length, location=(start + end) / 2)
        part = bpy.context.object
        part.rotation_mode = 'QUATERNION'
        part.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(end - start)
        return part

    def ellipsoid(radii, centre):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=centre)
        part = bpy.context.object
        part.scale = radii
        return part

    bpy.ops.object.select_all(action='DESELECT')
    parts = [ellipsoid((.15, .11, .30), (0, 0, 1.18)), ellipsoid((.17, .12, .16), (0, 0, .92)),
             ellipsoid((.09, .1, .12), (0, 0, 1.62)), capsule(.05, (0, 0, 1.40), (0, 0, 1.55)),
             capsule(.075, (.09, 0, .90), (.09, 0, .05)), capsule(.075, (-.09, 0, .90), (-.09, 0, .05)),
             capsule(.045, (.17, 0, 1.40), (.40, 0, 1.00)), capsule(.045, (-.17, 0, 1.40), (-.40, 0, 1.00)),
             ellipsoid((.18, .08, .06), (0, 0, 1.40))]
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    remesh = body.modifiers.new('Skin', 'REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = .012
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    body.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    body.location = location
    body.name = name
    return body


def override():
    return bpy.context.temp_override(window=state['window'], area=state['area'], region=state['region'], screen=state['window'].screen)


def button(key):
    workspace = state['workspace']
    workspace.canvas_layout = workspace.make_layout()
    rect = workspace.canvas_layout.buttons[key][0]
    region = state['region']
    for value in ('PRESS', 'RELEASE'):
        workspace.handle_event(bpy.context, SimpleNamespace(type='LEFTMOUSE', value=value, mouse_x=int(rect.x + rect.w / 2 + region.x),
                                                            mouse_y=int(rect.y + rect.h / 2 + region.y), ctrl=False, shift=False, alt=False))


def sizes(document):
    result = {}
    for pattern in document.patterns:
        xs, ys = [v.x for v in pattern.vertices], [v.y for v in pattern.vertices]
        result[pattern.id] = (round(max(xs) - min(xs), 9), round(max(ys) - min(ys), 9))
    return result


def seam_ratios(document):
    return [document.chain_length(seam.side(0)) / max(1e-9, document.chain_length(seam.side(1))) for seam in document.seams]


def setup():
    import devil_designer
    from devil_designer import editor, starters
    from devil_designer.measurements import estimate_body_measurements
    devil_designer.register()
    window = bpy.context.window_manager.windows[0]
    area = next(item for item in window.screen.areas if item.type == 'VIEW_3D')
    region = next(item for item in area.regions if item.type == 'WINDOW')
    scene = bpy.context.scene
    state.update(window=window, area=area, region=region, scene=scene)
    scene.render.fps = 30
    scene.dd_spacing = .03
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    first = skin_body('First base', (1, 1, 1), (0, 0, 0))
    second = skin_body('Second base', (1.15, 1.12, 1.07), (2.5, 0, 0))
    bpy.context.view_layer.update()
    state.update(first=first, second=second)
    scene.dd_avatar = first
    scene.dd_document = starters.create_tee_starter(estimate_body_measurements(first, scene), 'COTTON').dumps()
    with override():
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    state['workspace'] = editor._active
    check(state['workspace'] is not None, 'pattern editor opens on the first base')


def advance():
    from devil_designer import garment
    from devil_designer.core import Document
    from devil_designer.measurements import estimate_body_measurements
    workspace = state['workspace']
    scene = state['scene']
    step = state['step']
    state['step'] += 1
    with override():
        if step == 0:
            button('SIMULATE')
            simulation = garment.generated(scene, 'simulation')
            check(bool(simulation), 'the tee drapes on the first base')
            state['drape'] = simulation[0].session_uid
            return 1.5
        if step == 1:
            garment.stop(bpy.context)
            before = Document.loads(scene.dd_document)
            state['before'] = scene.dd_document
            old = estimate_body_measurements(state['first'], scene)
            new = estimate_body_measurements(state['second'], scene)
            workspace.choose_body(state['second'], bpy.context)
            check(scene.dd_avatar == state['second'], 'the artist picks the second base in the editor')
            check(workspace.message.startswith('Garment refit to Second base'), 'the refit is reported to the artist: ' + workspace.message)
            after = Document.loads(scene.dd_document)
            grown, wide = sizes(before), sizes(after)
            height = new['height'] / old['height']
            check(all(abs(wide[key][1] / grown[key][1] - height) < .02 for key in grown), 'every piece takes the new body length')
            ratios = [new_seam / old_seam for old_seam, new_seam in zip(seam_ratios(before), seam_ratios(after))]
            check(all(abs(ratio - 1) < .03 for ratio in ratios), 'every sewn pair keeps its matched length: ' + str([round(r, 3) for r in ratios]))
            widths = [wide[key][0] / grown[key][0] for key in grown]
            lowest = min(new[band] / old[band] for band in ('chest', 'waist', 'hip'))
            check(max(widths) > 1.05 and min(widths) >= lowest - .05,
                  'pieces grow across by the girth of their own body region: ' + str([round(w, 3) for w in widths]))
            return 2.0
        if step == 2:
            simulation = garment.generated(scene, 'simulation')
            if (not simulation or simulation[0].session_uid == state['drape']) and state.setdefault('waits', 0) < 40:
                state['waits'] += 1
                state['step'] = 2
                return .5
            check(bool(simulation) and simulation[0].session_uid != state['drape'], 'the garment re-drapes on the second base')
            check(workspace.message.startswith('Garment refit and re-draped on Second base') and 'inside' not in workspace.message,
                  'the re-drape waits for the new arrangement points and starts clear of the body: ' + workspace.message)
            low, high = garment.bounds(state['second'])
            centres = [sum((panel.matrix_world @ v.co).x for v in panel.data.vertices) / len(panel.data.vertices) for panel in garment.generated(scene, 'panel')]
            check(centres and all(low.x - .3 < centre < high.x + .3 for centre in centres), 'every piece is re-placed on the second base')
            garment.stop(bpy.context)
            check(bool(workspace.session.undo_stack), 'the refit is one undo step')
            workspace.perform_action('UNDO')
            check(sizes(Document.loads(scene.dd_document)) == sizes(Document.loads(state['before'])), 'Ctrl+Z restores the garment size from before the refit')
            workspace.draw_overlay()
            check(not workspace.error_message, 'the editor draws cleanly after the refit')
            report.write_text(json.dumps(dict(passed=state['passed'])), encoding='utf-8')
            return None


def tick():
    try:
        if 'workspace' not in state:
            setup()
            return .3
        return advance()
    except Exception:
        traceback.print_exc()
        report.write_text(json.dumps(dict(error=traceback.format_exc())), encoding='utf-8')
        return None


report.parent.mkdir(exist_ok=True)
bpy.app.timers.register(tick, first_interval=.5)
