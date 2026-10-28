import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import devil_designer
from devil_designer import arrangement


def box_mesh(low=(-.3, -.2, 0), high=(.3, .2, 2)):
    vertices = [(horizontal, depth, height) for height in (low[2], high[2])
                for depth in (low[1], high[1]) for horizontal in (low[0], high[0])]
    faces = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    triangles = [(face[0], face[index], face[index + 1]) for face in faces for index in (1, 2)]
    return vertices, triangles


def ring_mesh(rings, count=24):
    vertices = [(center[0] + radius * math.cos(index * math.tau / count),
                 center[1] + radius * math.sin(index * math.tau / count), center[2])
                for center, radius in rings for index in range(count)]
    triangles = []
    for level in range(len(rings) - 1):
        for index in range(count):
            start = level * count + index
            end = level * count + (index + 1) % count
            triangles.extend(((start, end, end + count), (start, end + count, start + count)))
    return vertices, triangles


def joined_mesh(parts):
    vertices, triangles = [], []
    for positions, faces in parts:
        offset = len(vertices)
        vertices.extend(positions)
        triangles.extend(tuple(index + offset for index in face) for face in faces)
    return vertices, triangles


class VolumeMatrix:
    def __init__(self, scale=1, shift=(0, 0, 0), angle=0):
        cosine, sine = math.cos(angle), math.sin(angle)
        self.rows = ((scale * cosine, -scale * sine, 0),
                     (scale * sine, scale * cosine, 0), (0, 0, scale))
        self.shift = shift

    def __getitem__(self, index):
        return self.rows[index]

    def __matmul__(self, point):
        return tuple(sum(self.rows[axis][index] * point[index] for index in range(3)) + self.shift[axis]
                     for axis in range(3))


class VolumeAvatar(dict):
    def __init__(self, vertices, triangles):
        super().__init__()
        self.type = 'MESH'
        self.matrix_world = VolumeMatrix()
        self.mesh = SimpleNamespace(vertices=[SimpleNamespace(co=point) for point in vertices],
                                    loop_triangles=[SimpleNamespace(vertices=face) for face in triangles],
                                    calc_loop_triangles=Mock())
        self.to_mesh_clear = Mock()

    def evaluated_get(self, depsgraph):
        return self

    def to_mesh(self):
        return self.mesh


class ArrangementVolumeTests(unittest.TestCase):
    def setUp(self):
        self.vertices, self.triangles = box_mesh()
        self.avatar = VolumeAvatar(self.vertices, self.triangles)
        self.context = SimpleNamespace(scene=SimpleNamespace(dd_avatar=self.avatar, objects=[self.avatar],
                                       dd_clearance=.03, unit_settings=SimpleNamespace(scale_length=1)),
                                       evaluated_depsgraph_get=Mock(return_value=object()))
        self.garment = SimpleNamespace(metres_per_unit=lambda scene: scene.unit_settings.scale_length)
        self.garment_patch = patch.object(devil_designer, 'garment', self.garment, create=True)
        self.garment_patch.start()
        self.addCleanup(self.garment_patch.stop)

    def volume(self, setup, identity='chest'):
        return next(volume for volume in setup['volumes'] if volume['id'] == identity)

    def assert_vector(self, actual, expected):
        for first, second in zip(actual, expected):
            self.assertAlmostEqual(first, second, places=7)

    def test_sparse_box_cross_sections_measure_edges_not_nearby_vertices(self):
        setup = arrangement.generate_volumes(self.vertices, self.triangles)
        self.assertEqual(setup['version'], 1)
        self.assertEqual({volume['id'] for volume in setup['volumes']},
                         {'neck', 'chest', 'waist', 'hip', 'left_upper_arm', 'right_upper_arm',
                          'left_forearm', 'right_forearm', 'left_thigh', 'right_thigh',
                          'left_calf', 'right_calf'})
        chest = self.volume(setup)
        self.assertEqual(len(chest['samples']), 7)
        self.assertAlmostEqual(chest['lower'], .66)
        self.assertAlmostEqual(chest['upper'], .80)
        for sample in chest['samples']:
            self.assertAlmostEqual(sample['radius'] * 2, math.hypot(.3, .2))
            self.assert_vector(sample['center'][:2], (.5, .5))
        self.assertEqual(json.loads(json.dumps(setup)), setup)

    def test_capsule_sections_have_per_height_radii(self):
        vertices, triangles = ring_mesh([((0, 0, height), radius) for height, radius in
                                        ((0, 0), (.1, math.sqrt(.03)), (.2, .2),
                                         (1.8, .2), (1.9, math.sqrt(.03)), (2, 0))])
        setup = arrangement.generate_volumes(vertices, triangles, clearance=0)
        for sample in self.volume(setup)['samples']:
            self.assertAlmostEqual(sample['radius'] * 2, .2)
        calf = self.volume(setup, 'left_calf')
        self.assertAlmostEqual(calf['samples'][0]['radius'] * 2, .8 * math.sqrt(.03))
        self.assertGreater(calf['samples'][-1]['radius'], calf['samples'][0]['radius'])

    def test_separate_lateral_sections_exclude_other_leg_and_torso(self):
        vertices, triangles = joined_mesh([
            box_mesh((-.25, -.15, .8), (.25, .15, 1.65)),
            box_mesh((-.13, -.12, 1.7), (.13, .12, 2)),
            box_mesh((.04, -.1, 0), (.24, .1, .9)),
            box_mesh((-.24, -.1, 0), (-.04, .1, .9))])
        setup = arrangement.generate_volumes(vertices, triangles, 0)
        for side, expected in (('left', .14), ('right', -.14)):
            for sample in self.volume(setup, side + '_calf')['samples']:
                self.assertAlmostEqual(sample['center'][0] * .5 - .25, expected)
                self.assertAlmostEqual(sample['radius'] * 2, math.hypot(.1, .1))
        self.assertAlmostEqual(self.volume(setup)['samples'][0]['radius'] * 2, math.hypot(.25, .15))

    def test_tilted_arm_uses_oblique_cross_sections_and_axis(self):
        arm_vertices, arm_triangles = box_mesh((.3, -.06, -.06), (1, .06, .06))
        arm_vertices = [(horizontal, depth, height + 1.65 - horizontal * .5)
                        for horizontal, depth, height in arm_vertices]
        vertices, triangles = joined_mesh([
            box_mesh((-.25, -.15, 0), (.25, .15, 2)), (arm_vertices, arm_triangles),
            ([(-horizontal, depth, height) for horizontal, depth, height in arm_vertices], arm_triangles)])
        self.avatar = VolumeAvatar(vertices, triangles)
        self.context.scene.dd_avatar = self.avatar
        self.context.scene.objects = [self.avatar]
        resolved = arrangement.resolve_point(self.context, 'left_upper_arm', 'front')
        self.assertGreater(abs(resolved['up'][0]), .7)
        self.assertGreater(resolved['up'][2], .3)
        self.assertLess(resolved['radius'], .2)
        self.assertAlmostEqual(sum(first * second for first, second in zip(resolved['normal'], resolved['up'])), 0)

    def test_default_front_back_frames_are_not_mirrored(self):
        front = arrangement.resolve_point(self.context, 'chest', 'front')
        back = arrangement.resolve_point(self.context, 'chest', 'back')
        self.assert_vector(front['normal'], (0, -1, 0))
        self.assert_vector(front['tangent'], (1, 0, 0))
        self.assert_vector(back['normal'], (0, 1, 0))
        self.assert_vector(back['tangent'], (-1, 0, 0))
        self.assert_vector(front['up'], (0, 0, 1))
        self.assertAlmostEqual(front['radius'], math.hypot(.3, .2) + .03)
        self.assert_vector(front['point'], (0, -front['radius'], 1.46))
        self.assert_vector(front['volume']['center'], (0, 0, 1.46))

    def test_normal_ensure_preserves_edits_force_is_explicit(self):
        arrangement.ensure_volumes(self.context)
        arrangement.edit_point(self.context, 'chest', 'front', angle=.7, height=.2)
        arrangement.edit_volume(self.context, 'chest', .4, .6, 1.7)
        stored = self.avatar['dd_arrangement_volumes']
        self.context.scene.dd_clearance = .5
        setup = arrangement.ensure_volumes(self.context)
        self.assertEqual(self.avatar['dd_arrangement_volumes'], stored)
        self.assertEqual(self.volume(setup)['points'][0]['height'], .2)
        self.assertEqual(self.volume(setup)['radius_scale'], 1.7)
        regenerated = arrangement.ensure_volumes(self.context, force=True)
        self.assertEqual(self.volume(regenerated)['points'][0]['angle'], 0)
        self.assertEqual(self.volume(regenerated)['radius_scale'], 1)
        self.assertAlmostEqual(regenerated['clearance'], .25)

    def test_point_add_move_delete_keep_stable_nonrecycled_ids(self):
        identity = arrangement.edit_point(self.context, 'waist', None, angle=-.3, height=.8, action='ADD')
        self.assertEqual(arrangement.edit_point(self.context, 'waist', identity, height=.1), identity)
        points = self.volume(arrangement.ensure_volumes(self.context), 'waist')['points']
        self.assertAlmostEqual(points[-1]['angle'], math.tau - .3)
        self.assertEqual(points[-1]['height'], .1)
        arrangement.edit_point(self.context, 'waist', identity, action='DELETE')
        with self.assertRaisesRegex(ValueError, 'Unknown point'):
            arrangement.resolve_point(self.context, 'waist', identity)
        replacement = arrangement.edit_point(self.context, 'waist', None, action='ADD')
        self.assertNotEqual(replacement, identity)

    def test_volume_bounds_and_radius_are_absolute_edits_of_measurement(self):
        setup = arrangement.ensure_volumes(self.context)
        original = self.volume(setup)
        arrangement.edit_point(self.context, 'chest', 'front', height=.25)
        arrangement.edit_volume(self.context, 'chest', .2, .4, 2)
        arrangement.edit_volume(self.context, 'chest', .3, .7, 3)
        resolved = arrangement.resolve_point(self.context, 'chest', 'front')
        self.assertAlmostEqual(resolved['point'][2], .8)
        self.assertAlmostEqual(resolved['radius'], math.hypot(.3, .2) * 3 + .03)
        current = self.volume(arrangement.ensure_volumes(self.context))
        self.assertEqual(current['samples'], original['samples'])
        self.assertEqual(current['points'][0]['height'], .25)

    def test_records_follow_live_translation_rotation_and_scale(self):
        original = arrangement.resolve_point(self.context, 'chest', 'front')
        stored = self.avatar['dd_arrangement_volumes']
        self.avatar.matrix_world = VolumeMatrix(scale=3, shift=(7, -4, 9), angle=math.pi / 2)
        moved = arrangement.resolve_point(self.context, 'chest', 'front')
        self.assert_vector(moved['point'], self.avatar.matrix_world @ original['point'])
        self.assert_vector(moved['normal'], (1, 0, 0))
        self.assert_vector(moved['tangent'], (0, 1, 0))
        self.assertAlmostEqual(moved['radius'], original['radius'] * 3)
        self.assertEqual(self.avatar['dd_arrangement_volumes'], stored)

    def test_evaluated_vertex_size_changes_are_live(self):
        original = arrangement.resolve_point(self.context, 'waist', 'front')
        for vertex in self.avatar.mesh.vertices:
            vertex.co = tuple(value * 2 for value in vertex.co)
        moved = arrangement.resolve_point(self.context, 'waist', 'front')
        self.assert_vector(moved['point'], tuple(value * 2 for value in original['point']))
        self.assertAlmostEqual(moved['radius'], original['radius'] * 2)

    def test_nonuniform_body_scale_keeps_cylinders_conservatively_outside(self):
        original = arrangement.resolve_point(self.context, 'chest', 'front')
        self.avatar.matrix_world.rows = ((2, 0, 0), (0, 3, 0), (0, 0, 1))
        resolved = arrangement.resolve_point(self.context, 'chest', 'front')
        self.assertAlmostEqual(resolved['radius'], (original['radius'] - .03) * 3 + .03)
        self.assertAlmostEqual(resolved['point'][2], original['point'][2])
        self.assert_vector(resolved['normal'], original['normal'])
        self.assertTrue(all(sample['radius'] >= resolved['radius'] - 1e-9
                            for sample in resolved['volume']['samples']))

    def test_copied_setup_remains_body_relative(self):
        arrangement.ensure_volumes(self.context)
        arrangement.edit_point(self.context, 'chest', 'front', angle=.5, height=.1)
        stored = self.avatar['dd_arrangement_volumes']
        original = arrangement.resolve_point(self.context, 'chest', 'front')
        other = VolumeAvatar(*box_mesh())
        other.matrix_world = VolumeMatrix(scale=2, shift=(5, 6, 7))
        other['dd_arrangement_volumes'] = stored
        self.context.scene.dd_avatar = other
        self.context.scene.objects = [other]
        resolved = arrangement.resolve_point(self.context, 'chest', 'front')
        self.assert_vector(resolved['point'], other.matrix_world @ original['point'])
        self.assertEqual(other['dd_arrangement_volumes'], stored)

    def test_other_avatar_regenerates_its_geometry_without_garment_data(self):
        arrangement.ensure_volumes(self.context)
        arrangement.edit_point(self.context, 'chest', 'front', angle=.5)
        other = VolumeAvatar(*box_mesh((2, 1, 0), (3, 1.8, 4)))
        self.context.scene.dd_avatar = other
        self.context.scene.objects = [other]
        setup = arrangement.ensure_volumes(self.context)
        resolved = arrangement.resolve_point(self.context, 'chest', 'front')
        self.assertEqual(self.volume(setup)['points'][0]['angle'], 0)
        self.assertAlmostEqual(resolved['radius'], math.hypot(.5, .4) + .03)
        self.assertEqual(set(other), {'dd_arrangement_volumes'})

    def test_clearance_converts_metres_to_scene_units(self):
        self.context.scene.unit_settings.scale_length = .01
        self.assertAlmostEqual(arrangement.resolve_point(self.context, 'waist', 'front')['radius'],
                               math.hypot(.3, .2) + 3)

    def test_overlay_identifies_every_live_point(self):
        points = arrangement.world_points(self.context)
        self.assertEqual(len(points), 96)
        self.assertEqual(len({(point['volume'], point['point']) for point in points}), 96)
        for point in points:
            if point['volume'] == 'chest':
                self.assert_vector(point['position'], arrangement.resolve_point(
                    self.context, point['volume'], point['point'])['point'])

    def test_invalid_geometry_and_clearance_are_rejected(self):
        for vertices, triangles, clearance in (([], [], .03), ([(0, 0, 0)] * 3, [(0, 1, 2)], .03),
                                                ([(math.nan, 0, 0)], [], .03),
                                                (self.vertices, [(0, 1, 99)], .03),
                                                (self.vertices, [(0, 1)], .03),
                                                (self.vertices, [(0, 0, 0)], .03),
                                                (self.vertices, [], .03),
                                                (self.vertices, self.triangles, -1),
                                                (self.vertices, self.triangles, math.inf)):
            with self.subTest(vertices=vertices, triangles=triangles, clearance=clearance), self.assertRaises(ValueError):
                arrangement.generate_volumes(vertices, triangles, clearance)

    def test_bad_edits_do_not_modify_avatar_json(self):
        arrangement.ensure_volumes(self.context)
        stored = self.avatar['dd_arrangement_volumes']
        for arguments in ({'angle': math.nan}, {'height': math.inf}, {'height': -1},
                          {'height': 1.1}, {'action': 'INVALID'}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                arrangement.edit_point(self.context, 'chest', 'front', **arguments)
        for lower, upper, radius in ((.6, .2, 1), (-1, .4, 1), (0, 2, 1),
                                     (.2, .3, 0), (.2, .3, math.nan), (.2, math.inf, 1)):
            with self.subTest(bounds=(lower, upper, radius)), self.assertRaises(ValueError):
                arrangement.edit_volume(self.context, 'chest', lower, upper, radius)
        self.assertEqual(self.avatar['dd_arrangement_volumes'], stored)
        with self.assertRaisesRegex(ValueError, 'Unknown avatar volume'):
            arrangement.resolve_point(self.context, 'missing', 'front')

    def test_corrupt_data_requires_explicit_regeneration(self):
        setup = arrangement.ensure_volumes(self.context)
        for stored in ('{', 'null', '{}', json.dumps(dict(setup, version=2))):
            self.avatar['dd_arrangement_volumes'] = stored
            with self.subTest(stored=stored), self.assertRaisesRegex(ValueError, 'regenerate'):
                arrangement.ensure_volumes(self.context)
            self.assertEqual(self.avatar['dd_arrangement_volumes'], stored)
        self.assertEqual(arrangement.ensure_volumes(self.context, force=True)['version'], 1)

    def test_invalid_sample_and_point_schema_is_not_silently_reset(self):
        setup = arrangement.ensure_volumes(self.context)
        for field, value in (('lower', math.nan), ('radius_scale', 0), ('next_point_id', -1),
                             ('samples', []), ('points', [{'id': 'front', 'height': 2, 'angle': 0}])):
            invalid = json.loads(json.dumps(setup))
            self.volume(invalid)[field] = value
            stored = json.dumps(invalid)
            self.avatar['dd_arrangement_volumes'] = stored
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'regenerate'):
                arrangement.ensure_volumes(self.context)
            self.assertEqual(self.avatar['dd_arrangement_volumes'], stored)

    def test_evaluated_mesh_is_released_after_failure(self):
        self.avatar.mesh.vertices = []
        with self.assertRaises(ValueError):
            arrangement.ensure_volumes(self.context)
        self.avatar.to_mesh_clear.assert_called_once()

    def test_avatar_validation_rejects_garments_and_missing_body(self):
        self.avatar['dd_kind'] = 'panel'
        with self.assertRaisesRegex(ValueError, 'not a garment'):
            arrangement.ensure_volumes(self.context)
        self.context.scene.dd_avatar = None
        with self.assertRaisesRegex(ValueError, 'Choose an avatar'):
            arrangement.ensure_volumes(self.context)
