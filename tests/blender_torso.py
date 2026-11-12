from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import arrangement, body_guard, garment, starters, xpbd_live

TORSO_GUIDANCE = ('no torso surface', 'full body', 'Collision modifier')
DRAPE_FRAMES = 120
STAYS_UP = 1.0


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


def capsule(radius, start, end):
    start, end = Vector(start), Vector(end)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=(end - start).length, location=(start + end) / 2)
    part = bpy.context.object
    part.rotation_mode = 'QUATERNION'
    part.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(end - start)
    return part


def ellipsoid(radii, location):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=location)
    part = bpy.context.object
    part.scale = radii
    return part


def skin_body():
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
    body.name = 'Skin body'
    return body


def t_pose_body(height):
    bpy.ops.object.select_all(action='DESELECT')
    parts = [ellipsoid((.15, .11, .30), (0, 0, 1.18)), ellipsoid((.17, .12, .16), (0, 0, .92)),
             ellipsoid((.09, .1, .12), (0, 0, 1.62)), capsule(.05, (0, 0, 1.40), (0, 0, 1.55)),
             capsule(.075, (.09, 0, .90), (.09, 0, .05)), capsule(.075, (-.09, 0, .90), (-.09, 0, .05)),
             capsule(.045, (.17, 0, 1.40), (.78, 0, 1.40)), capsule(.045, (-.17, 0, 1.40), (-.78, 0, 1.40)),
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
    top = max(vertex.co.z for vertex in body.data.vertices)
    body.scale = (height / top,) * 3
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    body.name = 'T-pose body'
    return body


def in_torso(co):
    return .80 < co.z < 1.38 and abs(co.x) < .19


def delete_torso(body):
    mesh = body.data
    surface = bmesh.new()
    surface.from_mesh(mesh)
    bmesh.ops.delete(surface, geom=[vertex for vertex in surface.verts if in_torso(vertex.co)], context='VERTS')
    surface.to_mesh(mesh)
    surface.free()


def mask_torso(body):
    group = body.vertex_groups.new(name='Torso')
    group.add([vertex.index for vertex in body.data.vertices if in_torso(vertex.co)], 1, 'REPLACE')
    mask = body.modifiers.new('Hide torso', 'MASK')
    mask.vertex_group = 'Torso'
    mask.invert_vertex_group = True


def shrink_torso(body):
    body.shape_key_add(name='Basis')
    shrink = body.shape_key_add(name='Shrink_Torso')
    for vertex in body.data.vertices:
        if in_torso(vertex.co):
            shrink.data[vertex.index].co = (vertex.co.x * .05, vertex.co.y * .05, vertex.co.z)
    shrink.value = 1


def collision_outfit():
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.165, depth=.6, location=(0, 0, 1.1))
    outfit = bpy.context.object
    outfit.scale = (1, .75, 1)
    outfit.name = 'Outfit shirt'
    outfit.modifiers.new('Collision', 'COLLISION')
    return outfit


def fresh(scene, prepare=None):
    garment.forget_drape()
    garment.reset(bpy.context)
    arrangement.cancel_fits()
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.frame_set(scene.frame_start)
    body = skin_body()
    if prepare:
        prepare(body)
    bpy.context.view_layer.objects.active = body
    bpy.context.view_layer.update()
    scene.dd_avatar = body
    return body


def chest_samples(scene):
    setup = arrangement.ensure_volumes(bpy.context)
    chest = next(volume for volume in setup['volumes'] if volume['id'] == 'chest')
    width = setup['aspect'][0]
    return [(sample['center'][0] * width, sample['radius']) for sample in chest['samples']]


def load_starter(scene, generator):
    from devil_designer.measurements import estimate_body_measurements
    scene.dd_document = generator(estimate_body_measurements(scene.dd_avatar, scene), 'COTTON').dumps()


def operate(scene, operator):
    scene.pop('dd_last_error', None)
    try:
        result = operator('EXEC_DEFAULT')
    except RuntimeError:
        result = {'CANCELLED'}
    return result, scene.get('dd_last_error', '')


def simulate(scene):
    return operate(scene, bpy.ops.devil_designer.simulate)


def drape(scene):
    for frame in range(scene.frame_current + 1, scene.frame_current + DRAPE_FRAMES + 1):
        scene.frame_set(frame)
    return xpbd_live.evaluated_points(bpy.context, garment.generated(scene, 'simulation')[0])


def leftovers():
    return (sorted(obj.name for obj in bpy.data.objects), sorted(mesh.name for mesh in bpy.data.meshes),
            sorted(key.name for key in bpy.data.shape_keys))


def keep(scene):
    _, error = operate(scene, bpy.ops.devil_designer.keep_drape)
    return garment.generated(scene, 'final'), error


def test_intact_control(scene):
    fresh(scene)
    samples = chest_samples(scene)
    middle = arrangement.ensure_volumes(bpy.context)['aspect'][0] / 2
    check(all(abs(x - middle) < .01 and radius > .06 for x, radius in samples), 'intact chest fit is centred and torso sized')
    load_starter(scene, starters.create_tank_starter)
    result, error = simulate(scene)
    check(result == {'FINISHED'} and not error, 'intact avatar simulates: ' + error)
    points = drape(scene)
    check(points[:, 2].min() > STAYS_UP, 'intact drape stays on the body')
    kept, error = keep(scene)
    check(len(kept) == 1 and not error, 'intact drape is kept: ' + error)
    return samples


def test_deleted_torso_stops_with_guidance(scene):
    fresh(scene, delete_torso)
    check(all(radius > .06 for _, radius in chest_samples(scene)), 'deleted torso is never fitted to an arm')
    load_starter(scene, starters.create_tee_starter)
    result, error = simulate(scene)
    check(result == {'CANCELLED'}, 'Simulate stops on a torso-removed avatar')
    check(all(words in error for words in TORSO_GUIDANCE), 'Simulate names the missing torso and both ways forward: ' + error)
    check(not garment.generated(scene, 'simulation'), 'no falling drape is started')


def test_hidden_torso_drapes(scene, prepare, label, intact_samples):
    body = fresh(scene, prepare)
    before = leftovers()
    samples = chest_samples(scene)
    check(len(samples) == len(intact_samples) and all(abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6
                                                       for a, b in zip(samples, intact_samples)),
          label + ' fits the chest as the real body')
    load_starter(scene, starters.create_tank_starter)
    result, error = simulate(scene)
    check(result == {'FINISHED'} and not error, label + ' avatar simulates: ' + error)
    points = drape(scene)
    check(points[:, 2].min() > STAYS_UP, label + ' drape stays up on the hidden torso')
    kept, error = keep(scene)
    check(len(kept) == 1 and not error, label + ' drape is kept: ' + error)
    after = leftovers()
    check(set(before[0]) <= set(after[0]) and not any(name.startswith('Skin body.') for name in after[0]),
          label + ' leaves no temporary body object')
    check(not any(name.startswith(body.data.name + '.') for name in after[1]), label + ' leaves no temporary body mesh')
    check(after[2] == before[2], label + ' leaves no temporary shape keys')
    return body


def test_mask_is_left_on(body):
    check(body.modifiers['Hide torso'].show_viewport, 'the artist Mask modifier stays enabled')


def test_shrink_is_left_on(body):
    shrink = body.data.shape_keys.key_blocks['Shrink_Torso']
    check(shrink.value == 1 and not shrink.mute, 'the artist Shrink shape key stays active')


def test_outfit_collision_route(scene):
    fresh(scene, delete_torso)
    collision_outfit()
    bpy.context.view_layer.update()
    samples = chest_samples(scene)
    middle = arrangement.ensure_volumes(bpy.context)['aspect'][0] / 2
    check(all(abs(x - middle) < .01 and radius > .06 for x, radius in samples),
          'a Collision outfit gives the torso-removed avatar a centred chest fit')
    load_starter(scene, starters.create_tee_starter)
    result, error = simulate(scene)
    check(result == {'FINISHED'} and not error, 'a Collision outfit lets the torso-removed avatar simulate: ' + error)
    points = drape(scene)
    check(points[:, 2].min() > STAYS_UP, 'the drape stays up on the Collision outfit')
    check(np.abs(points[:, 0]).max() < .45, 'the drape is placed around the torso, not out on the arms')


def test_outfit_added_later_refits(scene):
    fresh(scene, delete_torso)
    check(all(radius > .06 for _, radius in chest_samples(scene)), 'the hollow fit has no arm-sized chest')
    collision_outfit()
    bpy.context.view_layer.update()
    middle = arrangement.ensure_volumes(bpy.context)['aspect'][0] / 2
    check(all(abs(x - middle) < .01 for x, _ in chest_samples(scene)), 'adding a Collision outfit refits the chest around it')


def test_keep_names_missing_torso(scene):
    fresh(scene, delete_torso)
    fallen = np.array([[0, 0, -5], [.1, 0, -5], [0, .1, -5]], dtype=np.float32)
    try:
        body_guard.check(bpy.context, [scene.dd_avatar], fallen, 1)
    except ValueError as error:
        message = str(error)
    else:
        message = ''
    check(all(words in message for words in TORSO_GUIDANCE) and 'placement' not in message,
          'the Keep refusal names the missing torso: ' + message)
    fresh(scene)
    try:
        body_guard.check(bpy.context, [scene.dd_avatar], fallen, 1)
    except ValueError as error:
        message = str(error)
    check('fell off the body' in message, 'an intact avatar keeps the fit and placement refusal')


def test_hoodie_neck_join(scene):
    spacing = scene.dd_spacing
    scene.dd_spacing = .02
    garment.forget_drape()
    garment.reset(bpy.context)
    arrangement.cancel_fits()
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.frame_set(scene.frame_start)
    body = t_pose_body(1.40)
    bpy.context.view_layer.objects.active = body
    bpy.context.view_layer.update()
    scene.dd_avatar = body
    load_starter(scene, starters.create_hoodie_starter)
    result, error = simulate(scene)
    check(result == {'FINISHED'} and not error, 'the Hoodie simulates on a 1.40 m T-pose body: ' + error)
    drape(scene)
    scene['dd_unwelded_seams'] = -1
    kept, error = keep(scene)
    check(len(kept) == 1 and not error, 'Keep accepts the Hoodie where the hood joins the neckline: ' + error)
    check(scene['dd_unwelded_seams'] == 0, 'the kept Hoodie has no open seam pairs: ' + str(scene['dd_unwelded_seams']))
    scene.dd_spacing = spacing


devil_designer.register()
scene = bpy.context.scene
scene.dd_spacing = .025
scene.render.fps = 30
intact = test_intact_control(scene)
test_deleted_torso_stops_with_guidance(scene)
test_mask_is_left_on(test_hidden_torso_drapes(scene, mask_torso, 'Mask', intact))
test_shrink_is_left_on(test_hidden_torso_drapes(scene, shrink_torso, 'Shrink', intact))
test_outfit_collision_route(scene)
test_outfit_added_later_refits(scene)
test_keep_names_missing_torso(scene)
test_hoodie_neck_join(scene)
devil_designer.unregister()
