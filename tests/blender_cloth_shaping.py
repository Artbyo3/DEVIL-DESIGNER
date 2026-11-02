import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import cloth_shaping, garment
from tools.workspace import prepare_scratch


def collision_checks():
    triangle = (Vector((-1, -1, 0)), Vector((1, -1, 0)), Vector((0, 1, 0)))
    guard = cloth_shaping.CollisionGuard([(triangle, Vector((-1, -1, 0)), Vector((1, 1, 0)), .001)])
    before = [Vector((-.1, -.1, .01)), Vector((.1, -.1, .01)), Vector((0, .1, .01))]
    after = [point - Vector((0, 0, .02)) for point in before]
    assert not guard.clear_sweep(before, after, [(0, 1, 2)], Matrix.Identity(4)), 'thin surface tunnelling must be blocked'
    safe = [point + Vector((0, 0, .01)) for point in before]
    assert guard.clear_sweep(before, safe, [(0, 1, 2)], Matrix.Identity(4)), 'clear outward patch is allowed'
    assert not guard.clear_sweep(before, safe, [(0, 1, 2)], Matrix.Translation((0, 0, -.015))), 'world transform participates in collision proof'
    crossing = [Vector((-2, 0, 0)), Vector((2, 0, 0)), Vector((0, 2, 0))]
    assert not guard.clear_sweep(crossing, crossing, [(0, 1, 2)], Matrix.Identity(4)), 'triangle interior intersection is blocked with all vertices outside'
    transition = before + [Vector((0, .2, -.01))]
    assert not guard.clear_sweep(transition, transition, [(1, 2, 3)], Matrix.Identity(4)), 'transition triangles cannot cross the surface'
    mesh = bpy.data.meshes.new('Shape collision fixture')
    mesh.from_pydata([tuple(point) for point in triangle], [], [(0, 1, 2)])
    body = bpy.data.objects.new('Shape thin obstacle', mesh)
    bpy.context.scene.collection.objects.link(body)
    body.modifiers.new('Collision', 'COLLISION')
    body.collision.thickness_outer = .001
    source_mesh = bpy.data.meshes.new('Shape sweep fixture')
    source_mesh.from_pydata([tuple(point) for point in before], [], [(0, 1, 2)])
    source = bpy.data.objects.new('Shape swept patch', source_mesh)
    bpy.context.scene.collection.objects.link(source)
    bpy.context.view_layer.update()
    native = cloth_shaping.CollisionGuard.capture(bpy.context, source, .001)
    assert not native.clear_sweep(before, after, [(0, 1, 2)], source.matrix_world)
    assert native.clear_sweep(before, safe, [(0, 1, 2)], source.matrix_world)
    duplicate = body.copy()
    duplicate.data = mesh.copy()
    bpy.context.scene.collection.objects.link(duplicate)
    duplicate.rotation_euler = (.2, .3, .4)
    duplicate.scale = (-.5, 2, 1)
    duplicate.location = (0, 0, .03)
    bpy.context.view_layer.update()
    transformed = cloth_shaping.CollisionGuard.capture(bpy.context, source, .001)
    assert len(transformed.identity) == 2, 'every active collider is captured'
    far = [point + Vector((0, 0, .2)) for point in before]
    assert not transformed.clear_sweep(before, far, [(0, 1, 2)], source.matrix_world), 'transformed second collider blocks an otherwise clear pull'
    assert native.identity != transformed.identity, 'collider identity tracks transform and geometry changes'
    bpy.ops.mesh.primitive_cube_add(size=2)
    closed = bpy.context.object
    closed.modifiers.new('Closed collision', 'COLLISION')
    bpy.context.view_layer.update()
    enclosed = cloth_shaping.CollisionGuard.capture(bpy.context, source, .001)
    assert not enclosed.clear_sweep(before, before, [(0, 1, 2)], source.matrix_world), 'initially contained triangle is refused inside a closed collider'
    coordinates = [vertex.co.copy() for vertex in closed.data.vertices]
    faces = [tuple(polygon.vertices) for polygon in closed.data.polygons]
    combined = bpy.data.meshes.new('Overlapping closed components')
    combined.from_pydata(coordinates + [point + Vector((.2, 0, 0)) for point in coordinates], [],
                         faces + [tuple(index + len(coordinates) for index in face) for face in faces])
    previous_mesh = closed.data
    closed.data = combined
    bpy.data.meshes.remove(previous_mesh)
    bpy.context.view_layer.update()
    enclosed = cloth_shaping.CollisionGuard.capture(bpy.context, source, .001)
    assert len(enclosed.solids) == 2 and not enclosed.clear_sweep(before, before, [(0, 1, 2)], source.matrix_world), 'overlapping closed components are a union, not an even-parity cavity'
    closed.location = (4, 3, 2)
    closed.rotation_euler = (.2, .3, .4)
    closed.scale = (-.5, 2, 1)
    bpy.context.view_layer.update()
    enclosed = cloth_shaping.CollisionGuard.capture(bpy.context, source, .001)
    assert not enclosed.clear_sweep(before, before, [(0, 1, 2)], closed.matrix_world), 'closed containment respects reflected nonuniform collider and cloth transforms'
    outside = [point + Vector((0, 0, 2)) for point in before]
    outward = [point + Vector((0, 0, .02)) for point in outside]
    assert enclosed.clear_sweep(outside, outward, [(0, 1, 2)], closed.matrix_world), 'outside-to-outside safe sweep remains allowed'
    print('SHAPING_CLOSED_CONTAINMENT_PASS', len(enclosed.solids), flush=True)
    for obj in (source, duplicate, body, closed):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(data)
    devil_designer.register()
    try:
        polygon = [(0, 0), (2, 0), (2, 2), (1.00001, 2), (1.00001, 1), (1, 1), (1, 2), (0, 2)]
        vertices = [(x, y, z) for z in (-.5, .5) for x, y in polygon]
        faces = [tuple(reversed(range(8))), tuple(range(8, 16))]
        faces.extend((index, (index + 1) % 8, (index + 1) % 8 + 8, index + 8) for index in range(8))
        slot_mesh = bpy.data.meshes.new('Closed concave slot collider')
        slot_mesh.from_pydata(vertices, [], faces)
        slot_body = bpy.data.objects.new('Closed concave slot collider', slot_mesh)
        bpy.context.scene.collection.objects.link(slot_body)
        slot_body.modifiers.new('Collision', 'COLLISION')
        patch_mesh = bpy.data.meshes.new('Enclosed slot patch')
        patch_mesh.from_pydata([(.9998, 1.45, 0), (.9999, 1.45, 0), (.99985, 1.55, 0)], [], [(0, 1, 2)])
        slot_source = bpy.data.objects.new('Enclosed slot patch', patch_mesh)
        bpy.context.scene.collection.objects.link(slot_source)
        garment.tag(slot_source, 'simulation')
        slot_source['dd_signature'] = garment.signature(bpy.context.scene, [])
        slot_source['dd_sewing_pairs'] = '[]'
        slot_source['dd_shape_topology'] = cloth_shaping._fingerprint(slot_source)
        bpy.context.scene.dd_thickness = 0
        bpy.context.view_layer.update()
        slot_guard = cloth_shaping.CollisionGuard.capture(bpy.context, slot_source, 0)
        assert slot_guard.contains(Vector((.9999, 1.5, 0))), 'point inside concave narrow-slot wall must be classified inside'
        assert not slot_guard.contains(Vector((1.000005, 1.5, 0))), 'point inside narrow-slot cavity must be classified outside'
        assert not slot_guard.contains(Vector((2.01, 1.5, 0))), 'point outside slot collider must be classified outside'
        for vertex in slot_mesh.vertices:
            if vertex.co.x > 1 and vertex.co.x < 1.01:
                vertex.co.x = 1.000001
        slot_mesh.update()
        bpy.context.view_layer.update()
        narrow_guard = cloth_shaping.CollisionGuard.capture(bpy.context, slot_source, 0)
        assert narrow_guard.contains(Vector((.9999, 1.5, 0))), 'one-micrometre slot must not hide the enclosed patch'
        assert not narrow_guard.contains(Vector((1.0000005, 1.5, 0))), 'resolvable one-micrometre cavity must remain clear'
        directions = cloth_shaping._DIRECTIONS
        try:
            cloth_shaping._DIRECTIONS = (Vector((1, 0, 0)),)
            assert slot_guard.contains(Vector((.5, .5, 0))), 'unresolved edge intersections must fail closed rather than permit Keep'
        finally:
            cloth_shaping._DIRECTIONS = directions
        refused = False
        try:
            cloth_shaping.keep_guard(bpy.context, slot_source)
        except ValueError:
            refused = True
        assert refused, 'registered Keep guard must refuse cloth patch inside concave narrow-slot collider'
        outcome = None
        try:
            outcome = bpy.ops.devil_designer.keep_drape()
        except RuntimeError:
            outcome = {'CANCELLED'}
        assert outcome == {'CANCELLED'}, 'keep_drape operator must refuse cloth inside concave narrow-slot collider'
        assert len(garment.generated(bpy.context.scene, 'final')) == 0, 'refused Keep must not create final mesh'
        assert not slot_source.hide_get(), 'refused Keep must not hide source cloth'
        for obj in (slot_source, slot_body):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(data)
        scene = bpy.context.scene
        bpy.ops.devil_designer.demo()
        scene.dd_spacing = .025
        scene.dd_quality = 12
        scene.dd_frames = 120
        scene.dd_thickness = 0
        garment.arrange(bpy.context)
        garment.compile_garment(bpy.context)
        demo_source = garment.generated(scene, 'simulation')[0]
        torso_guard = cloth_shaping.CollisionGuard.capture(bpy.context, demo_source, 0)
        assert not torso_guard.contains(Vector((-.11064449697732925, .0029469039291143417, 1.4759421348571777))), 'original torso exterior point must not be classified as contained'
        assert torso_guard.contains(Vector((0, 0, 1.25))), 'torso interior point must be classified as contained'
    finally:
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh)
        devil_designer.unregister()


def reload_keep_checks(saved):
    bpy.ops.wm.open_mainfile(filepath=str(saved))
    scene = bpy.context.scene
    source = garment.generated(scene, 'simulation')[0]
    before = cloth_shaping.points(source)
    original_document = scene.dd_document
    original_finals = len(garment.generated(scene, 'final'))
    original_frame = scene.frame_current
    original_binding = next(modifier for modifier in source.modifiers if modifier.type == 'CLOTH').settings.vertex_group_mass
    original_weights = [[(group.group, group.weight) for group in vertex.groups] for vertex in source.data.vertices]
    original_rest = [list(item.co) for item in source.data.shape_keys.key_blocks['DD Shape Rest'].data]
    position = source.matrix_world @ before[len(before) // 2]
    bpy.ops.mesh.primitive_cube_add(size=.02, location=position)
    obstacle = bpy.context.object
    obstacle.modifiers.new('Reload collision regression', 'COLLISION')
    rejected = []
    def refuse(label):
        bpy.context.view_layer.update()
        mesh_count = len(bpy.data.meshes)
        try:
            outcome = bpy.ops.devil_designer.keep_drape()
        except RuntimeError as failure:
            assert 'collider' in str(failure).lower(), str(failure)
            outcome = {'CANCELLED'}
        assert outcome == {'CANCELLED'}, 'registered Keep after reopen must refuse a vertex contained in a newly added collider'
        assert len(garment.generated(scene, 'final')) == original_finals, 'unsafe Keep must not leave a final mesh'
        assert len(bpy.data.meshes) == mesh_count, 'rejected finalization must remove its provisional mesh'
        assert not source.hide_get(), 'unsafe Keep must leave the simulation visible'
        assert scene.dd_document == original_document
        assert scene.frame_current == original_frame, 'unsafe Keep must not restart simulation'
        assert next(modifier for modifier in source.modifiers if modifier.type == 'CLOTH').settings.vertex_group_mass == original_binding
        assert [[(group.group, group.weight) for group in vertex.groups] for vertex in source.data.vertices] == original_weights
        assert [list(item.co) for item in source.data.shape_keys.key_blocks['DD Shape Rest'].data] == original_rest
        assert max((point - original).length for point, original in zip(cloth_shaping.points(source), before)) < 1e-7
        rejected.append(label)
    refuse('original')
    obstacle.scale = (-2, .5, 1.25)
    obstacle.rotation_euler = (.2, .3, .4)
    refuse('transformed')
    mesh = obstacle.data
    bpy.data.objects.remove(obstacle, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    evaluated = source.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated.data.calc_loop_triangles()
    triangle = evaluated.data.loop_triangles[0]
    corners = [source.matrix_world @ evaluated.data.vertices[index].co for index in triangle.vertices]
    midpoint = sum(corners, Vector()) / 3
    direction = (corners[1] - corners[0]).normalized()
    perpendicular = (corners[1] - corners[0]).cross(corners[2] - corners[0]).normalized()
    crossing = bpy.data.meshes.new('Reload thin crossing')
    crossing.from_pydata([midpoint + direction * .005 + perpendicular * .005,
                         midpoint + direction * .005 - perpendicular * .005,
                         midpoint - direction * .005], [], [(0, 1, 2)])
    obstacle = bpy.data.objects.new('Reload thin collider', crossing)
    scene.collection.objects.link(obstacle)
    obstacle.modifiers.new('Thin collision regression', 'COLLISION')
    refuse('open_surface_intersection')
    bpy.data.objects.remove(obstacle, do_unlink=True)
    bpy.data.meshes.remove(crossing)
    units = garment.metres_per_unit(scene)
    normal = source.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices[len(before) // 2].normal.copy()
    normal = (source.matrix_world.inverted().transposed().to_3x3() @ normal).normalized()
    thickness = scene.dd_thickness
    scene.dd_thickness = .016
    bpy.ops.mesh.primitive_cube_add(size=.008 / units, location=position + normal * (.008 / units))
    obstacle = bpy.context.object
    obstacle.modifiers.new('Final thickness collision regression', 'COLLISION')
    bpy.context.view_layer.update()
    cloth_shaping.keep_guard(bpy.context, source)
    refuse('final_thickness')
    mesh = obstacle.data
    bpy.data.objects.remove(obstacle, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    scene.dd_thickness = thickness
    assert bpy.ops.devil_designer.keep_drape() == {'FINISHED'}, 'safe reopened shaping still supports registered Keep'
    assert len(garment.generated(scene, 'final')) == original_finals + 1
    bpy.ops.wm.open_mainfile(filepath=str(saved))
    print('SHAPING_RELOADED_KEEP_REGRESSION_PASS', len(rejected), flush=True)
    return dict(rejected_colliders=rejected, safe_keep=True)


def trial(arguments, sign):
    if arguments.fixture:
        bpy.ops.wm.open_mainfile(filepath=arguments.fixture)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=False)
    devil_designer.register()
    scene = bpy.context.scene
    if not arguments.fixture:
        bpy.ops.devil_designer.demo()
        scene.dd_spacing = .025
        scene.dd_quality = 12
        scene.dd_frames = 120
        scene.dd_thickness = 0
        garment.arrange(bpy.context)
        garment.compile_garment(bpy.context)
    source = garment.generated(scene, 'simulation')[0]
    guard = cloth_shaping.CollisionGuard.capture(bpy.context, source, 0)
    assert not guard.contains(Vector((-.11064449697732925, .0029469039291143417, 1.4759421348571777))), 'a shallow ray re-hit must not classify the exterior stage-15 vertex as contained'
    assert guard.contains(Vector((0, 0, 1.25))), 'the torso interior must remain blocked after the shallow-ray correction'
    original_document = scene.dd_document
    original_groups = {group.name: group.index for group in source.vertex_groups}
    flat = [vertex.co.copy() for vertex in source.data.vertices]
    edges = [tuple(edge.vertices) for edge in source.data.edges if not edge.is_loose]
    flat_lengths = [(flat[first] - flat[second]).length for first, second in edges]
    for frame in range(1, 122):
        scene.frame_set(frame)
        cloth_shaping.points(source)
    draped = cloth_shaping.points(source)
    drape_lengths = [(draped[first] - draped[second]).length for first, second in edges]
    desired = Vector((0, -.11, min(point.z for point in draped) +
                      (max(point.z for point in draped) - min(point.z for point in draped)) * .12))
    center = min(range(len(draped)), key=lambda index: (draped[index] - desired).length_squared)
    nearby = min(range(len(draped)), key=lambda index: (draped[index] - Vector((0, -.095, 1.25))).length_squared)
    probe = cloth_shaping.ShapingSession(source)
    modifier_names = [modifier.name for modifier in source.modifiers]
    try:
        probe.begin(bpy.context, nearby)
    except ValueError as failure:
        assert 'too close to a collider' in str(failure)
        assert [modifier.name for modifier in source.modifiers] == modifier_names
        assert source.data.shape_keys is None, 'near-body refusal does not change native shape data'
        assert max((point - before).length for point, before in zip(cloth_shaping.points(source), draped)) < 1e-9
    else:
        raise AssertionError('the tight body fixture must conservatively refuse an unprovable push')
    session = cloth_shaping.ShapingSession(source)
    session.begin(bpy.context, center)
    initial_normal = session.normals[center].copy()
    records = []
    samples = {}
    previous = cloth_shaping.points(source)
    for frame in range(2, 273):
        if frame <= 11:
            session.update(bpy.context, .012 * sign * (frame - 1) / 10)
        if frame == 32:
            session.release(bpy.context)
            assert source.vertex_groups.get('DD Shape Hold') is None
            assert session.cloth().settings.vertex_group_mass == session.original_group
            assert source.data.shape_keys.animation_data is None
            assert all(key.value == 0 for key in source.data.shape_keys.key_blocks)
            assert not session.cloth().settings.use_dynamic_mesh
        scene.frame_set(frame)
        current = cloth_shaping.points(source)
        record = dict(frame=frame, finite=all(math.isfinite(component) for point in current for component in point),
                      max_drape_ratio=max((current[first] - current[second]).length / length
                                          for (first, second), length in zip(edges, drape_lengths)),
                      max_flat_ratio=max((current[first] - current[second]).length / length
                                         for (first, second), length in zip(edges, flat_lengths)),
                      motion_m=max((point - before).length for point, before in zip(current, previous)),
                      cache_outdated=session.cloth().point_cache.is_outdated,
                      phase=session.phase.value)
        records.append(record)
        if frame < 32:
            assert not record['cache_outdated'], f'live target update invalidated cache at frame {frame}'
            if 2 <= frame <= 11 and sign:
                assert record['motion_m'] > .00001, f'live target froze at frame {frame}'
        if frame in (2, 11, 31, 32, 151, 272):
            samples[str(frame)] = [list(point) for point in current]
        if not session.monitor(bpy.context):
            raise AssertionError(f'native live shaping monitor failed at frame {frame}: {session.message}')
        assert session.cache_resets == 1, 'mouse value updates must not restart the solver'
        previous = current
    assert scene.dd_document == original_document, 'saved document schema stays unchanged'
    assert original_groups == {group.name: group.index for group in source.vertex_groups}
    result = dict(sign=sign, center=center, normal=list(initial_normal), samples=samples, frames=records,
                  accepted_input_m=session.strength, weights=session.weights, cache_resets=session.cache_resets,
                  all_finite=all(row['finite'] for row in records),
                  max_drape_ratio=max(row['max_drape_ratio'] for row in records),
                  max_flat_ratio=max(row['max_flat_ratio'] for row in records),
                  tail_motion_m=max(row['motion_m'] for row in records[-10:]))
    assert result['all_finite']
    assert result['max_drape_ratio'] < 1.053
    assert result['tail_motion_m'] < .00063
    if sign == 1:
        directory = prepare_scratch() / 'issue45-shaping'
        saved = directory / 'released.blend'
        before_save = cloth_shaping.points(source)
        rest = [list(item.co) for item in source.data.shape_keys.key_blocks['DD Shape Rest'].data]
        if arguments.bake_cache:
            with bpy.context.temp_override(point_cache=session.cloth().point_cache, object=source, active_object=source):
                bpy.ops.ptcache.bake_from_cache()
            result['cache_baked'] = session.cloth().point_cache.is_baked
            result['bake_pose_delta_m'] = max((point - before).length for point, before in zip(cloth_shaping.points(source), before_save))
        bpy.ops.wm.save_as_mainfile(filepath=str(saved))
        bpy.ops.wm.open_mainfile(filepath=str(saved))
        scene = bpy.context.scene
        source = garment.generated(scene, 'simulation')[0]
        result['loaded_document_equal'] = scene.dd_document == original_document
        result['loaded_rest_equal'] = rest == [list(item.co) for item in source.data.shape_keys.key_blocks['DD Shape Rest'].data]
        result['loaded_pose_delta_m'] = max((point - before).length for point, before in zip(cloth_shaping.points(source), before_save))
        (directory / 'save-load.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        assert result['loaded_document_equal'] and result['loaded_rest_equal'], 'generated shaping data and legacy document survive save/reload unchanged'
        assert result['loaded_pose_delta_m'] < 1e-6, f'released pose changed on save/reload by {result["loaded_pose_delta_m"]} m'
        result['reloaded_keep'] = reload_keep_checks(saved)
        scene = bpy.context.scene
        source = garment.generated(scene, 'simulation')[0]
        session = cloth_shaping.ShapingSession(source)
    plain = [item.co.copy() for item in source.data.shape_keys.key_blocks['DD Shape Plain'].data]
    session.reset(bpy.context)
    restored = cloth_shaping.points(source)
    assert max((point - baseline).length for point, baseline in zip(restored, plain)) < 1e-7
    result['plain_reset'] = True
    if sign == 1:
        for frame in range(2, 12):
            scene.frame_set(frame)
            cloth_shaping.points(source)
        session.begin(bpy.context, center)
        session.update(bpy.context, .006)
        for frame in range(2, 12):
            scene.frame_set(frame)
            cloth_shaping.points(source)
        stroke = [item.co.copy() for item in source.data.shape_keys.key_blocks['DD Shape Stroke'].data]
        accepted = [list(item.co) for item in source.data.shape_keys.key_blocks['DD Shape Rest'].data]
        bpy.ops.wm.save_as_mainfile(filepath=str(directory / 'interrupted.blend'))
        bpy.ops.wm.open_mainfile(filepath=str(directory / 'interrupted.blend'))
        source = garment.generated(bpy.context.scene, 'simulation')[0]
        assert not source.get('dd_shape_held') and source.vertex_groups.get('DD Shape Hold') is None, 'interrupted load removes transient pinning'
        assert source.data.shape_keys.animation_data is None, 'interrupted load removes the live target driver'
        assert accepted == [list(item.co) for item in source.data.shape_keys.key_blocks['DD Shape Rest'].data], 'interrupted load preserves previously accepted material rest'
        assert bpy.context.scene.dd_document == original_document, 'interrupted load preserves the legacy document'
        result['interrupted_pose_delta_m'] = max((point - before).length for point, before in zip(cloth_shaping.points(source), stroke))
        assert result['interrupted_pose_delta_m'] < 1e-7, 'interrupted load restores the previous stroke baseline'
        result['interrupted_load'] = True
    devil_designer.unregister()
    return result


def anchor_guards():
    scene = bpy.context.scene
    mesh = bpy.data.meshes.new('Shaping anchor fixture')
    mesh.from_pydata([(0, 0, 1), (.04, 0, 1), (0, .04, 1)], [], [(0, 1, 2)])
    source = bpy.data.objects.new('Shaping anchor guard', mesh)
    scene.collection.objects.link(source)
    pins = source.vertex_groups.new(name='Original soft pins')
    pins.add([0], .8, 'REPLACE')
    cloth = source.modifiers.new('DD Cloth', 'CLOTH')
    cloth.settings.vertex_group_mass = pins.name
    hook = source.modifiers.new('Original tack', 'HOOK')
    tack_target = bpy.data.objects.new('Original tack target', None)
    scene.collection.objects.link(tack_target)
    tack_target.location = (.01, -.02, .03)
    hook.object = tack_target
    hook.vertex_indices_set([1])
    scene.frame_set(2)
    tack_matrix = tack_target.matrix_world.copy()
    tacked_pose = cloth_shaping.points(source)
    original = [vertex.co.copy() for vertex in mesh.vertices]
    session = cloth_shaping.ShapingSession(source)
    try:
        session.begin(bpy.context, 1)
    except ValueError as failure:
        assert 'active tacks' in str(failure)
    else:
        raise AssertionError('active tacks require an honest refusal, never double-transformed targets')
    assert source.modifiers.get('Original tack') == hook
    assert hook.object == tack_target and tack_target.matrix_world == tack_matrix, 'refused active tacks and their targets remain unchanged'
    assert max((point - previous).length for point, previous in zip(cloth_shaping.points(source), tacked_pose)) < 1e-9
    assert [vertex.co for vertex in mesh.vertices] == original
    assert source.data.shape_keys is None
    source.modifiers.remove(hook)
    cloth.show_viewport = False
    try:
        session.begin(bpy.context, 1)
    except ValueError as failure:
        assert 'Frozen cloth' in str(failure)
    else:
        raise AssertionError('frozen cloth is unchanged')
    cloth.show_viewport = True
    bpy.context.view_layer.update()
    session.begin(bpy.context, 1)
    keys = source.data.shape_keys.key_blocks
    assert keys['DD Shape Basis'].data[0].co == original[0], 'original soft-pin target must not move'
    assert keys['DD Shape Target'].data[0].co == original[0], 'brush must exclude original soft-pin target'
    assert abs(source.vertex_groups['DD Shape Hold'].weight(0) - .8) < 1e-6
    session.release(bpy.context)
    assert source.vertex_groups.get('DD Shape Hold') is None
    assert session.cloth().settings.vertex_group_mass == 'Original soft pins'
    assert abs(pins.weight(0) - .8) < 1e-6
    source.matrix_world = Matrix.Diagonal((2, .5, 1, 1)) @ Matrix.Rotation(.4, 4, 'Y')
    scene.frame_set(2)
    session.begin(bpy.context, 1)
    keys = source.data.shape_keys.key_blocks
    world_delta = source.matrix_world.to_3x3() @ (keys['DD Shape Target'].data[1].co - keys['DD Shape Basis'].data[1].co)
    world_edge = source.matrix_world.to_3x3() @ (session.baseline[1] - session.baseline[0])
    assert abs(world_delta.length - session.maximum * session.weights[1]) < 1e-6, 'transformed target strength is measured in world units'
    assert abs(world_delta.dot(world_edge)) < 1e-7, 'transformed target follows the physical surface normal'
    session.cancel(bpy.context)
    scene.frame_set(2)
    session.begin(bpy.context, 1)
    bpy.ops.mesh.primitive_cube_add(size=.1, location=source.matrix_world @ session.baseline[1])
    obstacle = bpy.context.object
    obstacle.modifiers.new('Moved collider', 'COLLISION')
    bpy.context.view_layer.update()
    assert not session.monitor(bpy.context), 'same-frame collider edits must roll back rather than bypass Keep safety'
    assert session.phase == cloth_shaping.Phase.BLOCKED
    assert source.vertex_groups.get('DD Shape Hold') is None and not source.get('dd_shape_held')
    assert source.data.shape_keys.animation_data is None
    assert session.cloth().settings.vertex_group_mass == pins.name
    obstacle_mesh = obstacle.data
    bpy.data.objects.remove(obstacle, do_unlink=True)
    bpy.data.meshes.remove(obstacle_mesh)
    garment.remove_objects([source])
    print('SHAPING_ANCHOR_GUARDS_PASS', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture')
    parser.add_argument('--sign', type=int, choices=(-1, 0, 1))
    parser.add_argument('--collision-only', action='store_true')
    parser.add_argument('--bake-cache', action='store_true')
    parser.add_argument('--reload-only', action='store_true')
    arguments = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    directory = prepare_scratch() / 'issue45-shaping'
    directory.mkdir(exist_ok=True)
    if arguments.reload_only:
        if not arguments.fixture:
            parser.error('--reload-only requires a released --fixture')
        devil_designer.register()
        result = reload_keep_checks(Path(arguments.fixture))
        (directory / 'reload-keep.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        devil_designer.unregister()
        return
    collision_checks()
    anchor_guards()
    if arguments.collision_only:
        print('SHAPING_COLLISION_MATRIX_PASS', flush=True)
        return
    results = []
    for sign in ((arguments.sign,) if arguments.sign is not None else (0, 1, -1)):
        result = trial(arguments, sign)
        results.append(result)
        (directory / f'trial_{sign}.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        print('SHAPING_TRIAL', sign, result['max_drape_ratio'], result['tail_motion_m'], flush=True)
    if len(results) == 3:
        control = results[0]
        for result in results[1:]:
            center = result['center']
            final = Vector(result['samples']['272'][center]) - Vector(control['samples']['272'][center])
            result['matched_center_m'] = final.dot(Vector(result['normal']))
            assert result['matched_center_m'] * result['sign'] > 0, 'released effect must retain its requested sign against matched control'
        (directory / 'matched.json').write_text(json.dumps(results, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
