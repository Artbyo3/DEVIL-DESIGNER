import ast
import hashlib
import inspect
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import garment
from devil_designer.core import Document, EdgeRef, Session
from tools.check_comments import check_source
from tools.workspace import prepare_scratch


def boundary_weights(shrinks, maps, plan):
    if any(isinstance(value, bool) or value not in (0, .1, .2, .3) for value in shrinks.values()):
        raise ValueError('Prototype Shrink must be 0, 10, 20 or 30 percent.')
    weights = {}
    for identity, pairs in plan.seam_pairs:
        shrink = shrinks.get(identity, 0)
        if not shrink:
            continue
        for pair in pairs:
            for edge, fraction in pair:
                samples = maps[edge.pattern][edge.start]
                sample_fraction, vertex = min(samples, key=lambda sample: abs(sample[0] - fraction))
                if abs(sample_fraction - fraction) > 1e-6:
                    raise ValueError('Prototype requires unchanged sewing samples.')
                weights[vertex] = max(weights.get(vertex, 0), shrink / .30)
    return weights


def apply_prototype(obj, cloth, maps, plan, shrinks):
    weights = boundary_weights(shrinks, maps, plan)
    group = obj.vertex_groups.new(name='DD Prototype Seam Shrink')
    for vertex, weight in weights.items():
        group.add([vertex], weight, 'REPLACE')
    cloth.settings.shrink_min = 0
    cloth.settings.shrink_max = .30
    cloth.settings.vertex_group_shrink = group.name


def candidate_compiler(shrinks, hook_calls, scratch):
    tree = ast.parse(inspect.getsource(garment.compile_garment))
    function = tree.body[0]
    function.name = 'prototype_compile_garment'
    hooks = []
    for index, statement in enumerate(function.body):
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'apply_presets':
            hooks.append(index)
    if len(hooks) != 1:
        raise AssertionError('Prototype requires exactly one preset hook location.')
    hook = ast.parse('if any(prototype_shrinks.values()):' + chr(10) + '    prototype_hook(obj, cloth, maps, plan)').body[0]
    function.body.insert(hooks[0] + 1, hook)
    ast.fix_missing_locations(tree)
    generated = ast.unparse(tree)
    check_source(generated, 'prototype_compile_garment.py')
    (scratch / 'prototype_compile_garment.py').write_text(generated, encoding='utf-8')

    def execute_hook(obj, cloth, maps, plan):
        hook_calls.append(True)
        apply_prototype(obj, cloth, maps, plan, shrinks)

    namespace = dict(garment.__dict__, prototype_shrinks=shrinks, prototype_hook=execute_hook)
    exec(compile(tree, '<approved-prototype-hook>', 'exec'), namespace)
    return namespace['prototype_compile_garment']


def rna_settings(owner):
    values = {}
    for prop in owner.bl_rna.properties:
        if prop.is_readonly or prop.identifier == 'rna_type':
            continue
        value = getattr(owner, prop.identifier)
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'ENUM', 'STRING'}:
            values[prop.identifier] = list(value) if getattr(prop, 'is_array', False) else sorted(value) if isinstance(value, set) else value
        elif prop.type == 'POINTER':
            if value is None:
                values[prop.identifier] = None
            elif isinstance(value, bpy.types.ID):
                values[prop.identifier] = (value.bl_rna.identifier, value.name_full)
    return values


def compiled_snapshot(obj):
    cloth = next(modifier for modifier in obj.modifiers if modifier.type == 'CLOTH')
    return dict(
        geometry=dict(vertices=[tuple(vertex.co) for vertex in obj.data.vertices],
                      edges=[tuple(edge.vertices) for edge in obj.data.edges],
                      faces=[(tuple(face.vertices), face.material_index, face.use_smooth) for face in obj.data.polygons],
                      matrix=[tuple(row) for row in obj.matrix_world]),
        uvs=[(layer.name, [tuple(item.uv) for item in layer.data]) for layer in obj.data.uv_layers],
        groups=[(group.name, group.index, group.lock_weight,
                 [(vertex.index, item.weight) for vertex in obj.data.vertices for item in vertex.groups if item.group == group.index])
                for group in obj.vertex_groups],
        modifiers=[(modifier.name, modifier.type, rna_settings(modifier)) for modifier in obj.modifiers],
        cloth_settings=rna_settings(cloth.settings), collision_settings=rna_settings(cloth.collision_settings),
        effector_weights=rna_settings(cloth.settings.effector_weights), point_cache=rna_settings(cloth.point_cache),
        metadata={name: obj[name] for name in sorted(obj.keys())}, materials=[material.name for material in obj.data.materials])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def evaluate(obj, frame):
    bpy.context.scene.frame_set(frame)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points = [tuple(evaluated.matrix_world @ vertex.co) for vertex in evaluated.data.vertices]
    if not all(math.isfinite(value) for point in points for value in point):
        raise AssertionError('Prototype generated non-finite coordinates.')
    return points


def zero_comparison(scratch):
    scene = bpy.context.scene
    bpy.ops.devil_designer.demo()
    scene.dd_spacing = .025
    scene.dd_quality = 12
    scene.dd_frames = 120
    garment.arrange(bpy.context)
    baseline = garment.compile_garment(bpy.context)
    before = compiled_snapshot(baseline)
    poses = [evaluate(baseline, frame) for frame in range(1, 122)]
    garment.reset(bpy.context)
    shrinks = {seam.id: 0 for seam in garment.document(scene).seams}
    hook_calls = []
    candidate = candidate_compiler(shrinks, hook_calls, scratch)(bpy.context)
    after = compiled_snapshot(candidate)
    components = {name: dict(equal=before[name] == after[name], baseline_sha256=digest(before[name]),
                             candidate_sha256=digest(after[name])) for name in before}
    errors = []
    for frame, expected in enumerate(poses, 1):
        actual = evaluate(candidate, frame)
        if len(actual) != len(expected):
            raise AssertionError('Zero prototype changed evaluated topology.')
        errors.append(max(math.dist(first, second) for first, second in zip(expected, actual)))
    result = dict(frames=121, vertices=len(poses[0]), compiled_components=components,
                  hook_calls=len(hook_calls), per_frame_max_distance=errors,
                  max_distance=max(errors), tolerance_blender_units=1e-6,
                  passed=all(item['equal'] for item in components.values()) and max(errors) <= 1e-6 and not hook_calls)
    print('ZERO_COMPARISON ' + json.dumps(result), flush=True)
    return result


def conflict_comparison():
    first, second = EdgeRef('piece', 'a', 'end_a'), EdgeRef('piece', 'b', 'end_b')
    maps = {'piece': {'a': [(0, 0), (1, 1)], 'b': [(0, 2), (1, 3)]}}
    pairs = [('low', [((first, 0), (second, 0))]), ('high', [((first, 0), (second, 1))])]
    forward = boundary_weights({'low': .1, 'high': .3}, maps, SimpleNamespace(seam_pairs=pairs))
    reverse = boundary_weights({'low': .1, 'high': .3}, maps, SimpleNamespace(seam_pairs=list(reversed(pairs))))
    zero = boundary_weights({'low': 0, 'high': .3}, maps, SimpleNamespace(seam_pairs=pairs))
    if forward != reverse or forward != {0: 1, 2: .1 / .3, 3: 1} or zero != {0: 1, 3: 1}:
        raise AssertionError('Shared vertices must use maximum Shrink independently of seam order.')
    for invalid in (-.1, .05, .4, True, '10', float('nan')):
        try:
            boundary_weights({'low': invalid}, maps, SimpleNamespace(seam_pairs=pairs))
        except ValueError:
            continue
        raise AssertionError('Unsupported Shrink was accepted.')
    for shrink in (0, .1, .2, .3):
        boundary_weights({'low': shrink}, maps, SimpleNamespace(seam_pairs=pairs))
    return dict(rule='Maximum Shrink wins; zero never overrides a nonzero value; seam order has no effect.',
                forward=forward, reverse=reverse, zero=zero, validation_passed=True, passed=True)


def ring_fixture(circumference, height, spacing):
    scene = bpy.context.scene
    garment.reset(bpy.context)
    session = Session(Document())
    session.add([(0, 0), (circumference, 0), (circumference, height), (0, height)])
    first = session.document.patterns[-1]
    session.add([(0, height), (circumference, height), (circumference, 2 * height), (0, 2 * height)])
    second = session.document.patterns[-1]
    for piece in (first, second):
        if not session.sew(session.document.edge(piece.id, 1), session.document.edge(piece.id, 3)):
            raise AssertionError('Could not close prototype ring.')
    if not session.sew(session.document.edge(first.id, 2), session.document.edge(second.id, 0)):
        raise AssertionError('Could not join prototype circumferential seam.')
    identity = session.document.seams[-1].id
    scene.dd_document = session.document.dumps()
    scene.dd_spacing = spacing
    scene.dd_quality = 24
    scene.dd_frames = 240
    scene.gravity = (0, 0, 0)
    scene.dd_avatar.location.x = 4
    panels = garment.build_panels(bpy.context)
    radius = circumference / (2 * math.pi)
    offset = 0
    chains = []
    for panel in panels:
        inverse = panel.matrix_world.inverted()
        for vertex, item in zip(panel.data.vertices, panel.data.attributes['dd_rest'].data):
            angle = item.vector.x / radius
            vertex.co = inverse @ Vector((radius * math.cos(angle), radius * math.sin(angle), 1 + item.vector.y))
        edge = session.document.edge(panel['dd_pattern_id'], 2 if panel['dd_pattern_id'] == first.id else 0)
        samples = json.loads(panel['dd_edge_samples'])[edge.start]
        chains.append([offset + vertex for _, vertex in sorted(samples)])
        offset += len(panel.data.vertices)
    bpy.context.view_layer.update()
    return identity, chains


def perimeter(points, chain):
    return sum(math.dist(points[first], points[second]) for first, second in zip(chain, chain[1:])) + math.dist(points[chain[-1]], points[chain[0]])


def contraction_trial(name, circumference, height, spacing, shrink, scratch):
    scene = bpy.context.scene
    identity, chains = ring_fixture(circumference, height, spacing)
    shrinks = {identity: shrink}
    hook_calls = []
    source = candidate_compiler(shrinks, hook_calls, scratch)(bpy.context)
    cloth = next(modifier for modifier in source.modifiers if modifier.type == 'CLOTH')
    initial = [tuple(source.matrix_world @ vertex.co) for vertex in source.data.vertices]
    initial_lengths = [perimeter(initial, chain) for chain in chains]
    history = []
    final = initial
    for frame in range(1, 242):
        final = evaluate(source, frame)
        lengths = [perimeter(final, chain) for chain in chains]
        history.append([100 * (1 - length / start) for length, start in zip(lengths, initial_lengths)])
    measured = history[-1]
    target = shrink * 100
    errors = [abs(value - target) for value in measured]
    window = history[-61:]
    settling = [max(values[side] for values in window) - min(values[side] for values in window) for side in range(2)]
    pairs = json.loads(source['dd_sewing_pairs'])
    gaps = [math.dist(final[first], final[second]) for first, second in pairs]
    result = dict(fixture=name, target_percent=target, quality=scene.dd_quality, frames=241,
                  vertices=len(initial), boundary_vertices=[len(chain) for chain in chains],
                  flat_circumference_m=circumference, strip_height_m=height, spacing_m=spacing,
                  initial_boundary_m=initial_lengths, final_boundary_m=lengths,
                  measured_contraction_percent=measured, absolute_error_percentage_points=errors,
                  settling_last_61_frames_percentage_points=settling,
                  mean_sewing_gap_m=sum(gaps) / len(gaps), max_sewing_gap_m=max(gaps),
                  sewing_force_max=cloth.settings.sewing_force_max,
                  self_collision=cloth.collision_settings.use_self_collision,
                  shrink_min=cloth.settings.shrink_min, shrink_max=cloth.settings.shrink_max,
                  shrink_group=cloth.settings.vertex_group_shrink, hook_calls=len(hook_calls),
                  tolerance_percentage_points=1.0, settling_tolerance_percentage_points=.25,
                  passed=max(errors) <= 1.0 and max(settling) <= .25,
                  per_frame_contraction_percent=history)
    print('CONTRACTION ' + json.dumps({key: value for key, value in result.items() if key != 'per_frame_contraction_percent'}), flush=True)
    return result


def main():
    scratch = prepare_scratch()
    sources = [ROOT / 'devil_designer' / name for name in ('garment.py', 'meshing.py', 'placement.py', 'tack_binding.py')]
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    package = ROOT / 'dist' / 'devil_designer-0.9.0.zip'
    package_hash = hashlib.sha256(package.read_bytes()).hexdigest()
    devil_designer.register()
    report = dict(prototype_only=True, blender=bpy.app.version_string, contraction_tolerance_percentage_points=1.0,
                  settling_tolerance_percentage_points=.25, zero_tolerance_blender_units=1e-6,
                  fixture='Two unpinned Cotton strips wrapped into closed rings and sewn around their common circumference; gravity zero; body moved 4 m away; unchanged native cloth, sewing and collision settings.',
                  zero=zero_comparison(scratch), conflicts=conflict_comparison(), trials=[])
    for name, circumference, height, spacing in [('waistband', .90, .06, .015), ('cuff', .24, .035, .006)]:
        for shrink in (0, .1, .2, .3):
            report['trials'].append(contraction_trial(name, circumference, height, spacing, shrink, scratch))
            (scratch / 'seam-shrink-prototype.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    report['protected_sources_unchanged'] = before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    report['part_a_zip_sha256'] = package_hash
    report['part_a_zip_unchanged'] = hashlib.sha256(package.read_bytes()).hexdigest() == package_hash
    report['passed'] = report['zero']['passed'] and report['conflicts']['passed'] and all(trial['passed'] for trial in report['trials']) and report['protected_sources_unchanged'] and report['part_a_zip_unchanged']
    (scratch / 'seam-shrink-prototype.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PROTOTYPE_GATE ' + ('PASS' if report['passed'] else 'FAIL'), flush=True)
    devil_designer.unregister()
    if not report['passed']:
        raise AssertionError('Seam shrink prototype failed the declared numerical gate; inspect scratch/seam-shrink-prototype.json.')


if __name__ == '__main__':
    main()
