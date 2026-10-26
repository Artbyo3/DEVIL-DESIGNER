import math
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import devil_designer
from devil_designer.arrangement import MODES, arrange, layout_plan
from devil_designer.core import Session


BODY_BOUNDS = ((-1, -.25, 0), (1, .25, 2))
BODICE = (('front', 'Front panel'), ('back', 'Back panel'))


class LayoutPlanTests(unittest.TestCase):
    def test_bodice_front_back_and_multiple_panels(self):
        pieces = (('second', 'Front right'), ('back', 'Back'), ('first', 'Front left'))
        plan = layout_plan(pieces, BODY_BOUNDS, 'BODICE')
        self.assertEqual([target.pattern_id for target in plan], ['first', 'second', 'back'])
        self.assertLess(plan[0].point[0], plan[1].point[0])
        self.assertEqual(plan[0].point[1:], (-.25, 1.44))
        self.assertEqual(plan[0].normal, (0, -1, 0))
        self.assertEqual(plan[-1].normal, (0, 1, 0))
        self.assertEqual(plan[-1].point, (0, .25, 1.44))

    def test_sleeves_use_avatar_left_positive_x(self):
        pieces = (('right', 'Right sleeve'), ('left', 'Left sleeve'))
        plan = layout_plan(pieces, BODY_BOUNDS, 'SLEEVES')
        self.assertEqual(plan[0].pattern_id, 'left')
        self.assertEqual(plan[0].point, (.72, -.25, 1.56))
        self.assertEqual(plan[1].point, (-.72, -.25, 1.56))
        self.assertTrue(all(target.normal == (0, -1, 0) for target in plan))

    def test_multiple_sleeve_pieces_have_distinct_targets(self):
        pieces = (('a', 'Left upper'), ('b', 'Left lower'), ('c', 'Right sleeve'))
        plan = layout_plan(pieces, BODY_BOUNDS, 'SLEEVES')
        self.assertEqual(len({target.point for target in plan}), 3)

    def test_skirt_is_radial_with_outward_unit_normals(self):
        pieces = tuple((str(index), f'Panel {index}') for index in range(8))
        plan = layout_plan(pieces, BODY_BOUNDS, 'SKIRT')
        self.assertEqual(len({target.point for target in plan}), 8)
        for target in plan:
            horizontal, depth, height = target.point
            self.assertAlmostEqual(horizontal ** 2 + (depth / .25) ** 2, 1)
            self.assertEqual(height, .86)
            self.assertAlmostEqual(math.hypot(*target.normal), 1)
            self.assertGreater(horizontal * target.normal[0] + depth * target.normal[1], 0)

    def test_plans_are_order_independent_and_preserve_ids(self):
        for mode, pieces in (('BODICE', BODICE),
                             ('SLEEVES', (('left', 'Left'), ('right', 'Right'))),
                             ('SKIRT', (('b', 'Panel'), ('a', 'Panel'), ('c', 'Panel')))):
            with self.subTest(mode=mode):
                self.assertEqual(layout_plan(pieces, BODY_BOUNDS, mode),
                                 layout_plan(reversed(pieces), BODY_BOUNDS, mode))
                self.assertEqual({target.pattern_id for target in layout_plan(pieces, BODY_BOUNDS, mode)},
                                 {piece[0] for piece in pieces})

    def test_bounds_translation_and_scale_are_respected(self):
        original = layout_plan(BODICE, BODY_BOUNDS, 'BODICE')
        transformed = tuple(tuple(value * 3 + shift for value, shift in zip(corner, (7, -4, 9)))
                            for corner in BODY_BOUNDS)
        moved = layout_plan(BODICE, transformed, 'BODICE')
        for before, after in zip(original, moved):
            for actual, expected in zip(after.point, (value * 3 + shift for value, shift in zip(before.point, (7, -4, 9)))):
                self.assertAlmostEqual(actual, expected)
            self.assertEqual(before.normal, after.normal)

    def test_names_use_case_insensitive_whole_tokens(self):
        plan = layout_plan((('a', 'FRONT_panel.001'), ('b', 'back-panel')), BODY_BOUNDS, 'BODICE')
        self.assertEqual(len(plan), 2)
        for name in ('FrontBack', 'Frontier', 'Panel 1'):
            with self.subTest(name=name):
                plan = layout_plan((('a', name), ('b', 'Back')), BODY_BOUNDS, 'BODICE')
                self.assertEqual({target.pattern_id: target.normal for target in plan},
                                 {'a': (0, -1, 0), 'b': (0, 1, 0)})

    def test_contradictory_labels_and_single_skirt_are_rejected(self):
        for mode, pieces in (('BODICE', (('a', 'Front back'), ('b', 'Back'))),
                             ('SLEEVES', (('a', 'Left right'), ('b', 'Right'))),
                             ('SKIRT', (('a', 'Skirt'),))):
            with self.subTest(mode=mode, pieces=pieces), self.assertRaises(ValueError):
                layout_plan(pieces, BODY_BOUNDS, mode)

    def test_default_names_are_balanced_for_even_odd_and_single_piece(self):
        for mode in ('BODICE', 'SLEEVES'):
            for count in range(1, 8):
                with self.subTest(mode=mode, count=count):
                    pieces = tuple((str(index), f'Pattern {index + 1:02}') for index in range(count))
                    original = tuple(pieces)
                    plan = layout_plan(pieces, BODY_BOUNDS, mode)
                    first_side = [target for target in plan if
                                  (target.normal[1] < 0 if mode == 'BODICE' else target.point[0] > 0)]
                    self.assertEqual(len(first_side), (count + 1) // 2)
                    self.assertEqual({target.pattern_id for target in plan}, {piece[0] for piece in pieces})
                    self.assertEqual(len({target.point for target in plan}), count)
                    self.assertEqual(plan, layout_plan(reversed(pieces), BODY_BOUNDS, mode))
                    self.assertEqual(pieces, original)

    def test_explicit_labels_are_assigned_before_balancing_unlabeled_pieces(self):
        for mode, label in (('BODICE', 'Front'), ('SLEEVES', 'Left')):
            with self.subTest(mode=mode):
                pieces = (('a', 'Pattern 01'), ('b', 'Pattern 02'),
                          ('c', f'Z {label} one'), ('d', f'Z {label} two'))
                plan = layout_plan(pieces, BODY_BOUNDS, mode)
                first_side = {target.pattern_id for target in plan if
                              (target.normal[1] < 0 if mode == 'BODICE' else target.point[0] > 0)}
                self.assertEqual(first_side, {'c', 'd'})
                self.assertEqual(plan, layout_plan(reversed(pieces), BODY_BOUNDS, mode))

    def test_duplicate_unlabeled_names_use_identity_tiebreak(self):
        pieces = (('b', 'Pattern'), ('a', 'Pattern'), ('c', 'Pattern'))
        for mode in ('BODICE', 'SLEEVES'):
            with self.subTest(mode=mode):
                plan = layout_plan(pieces, BODY_BOUNDS, mode)
                first_side = {target.pattern_id for target in plan if
                              (target.normal[1] < 0 if mode == 'BODICE' else target.point[0] > 0)}
                self.assertEqual(first_side, {'a', 'c'})
                self.assertEqual(plan, layout_plan(reversed(pieces), BODY_BOUNDS, mode))

    def test_explicit_labels_are_not_reassigned_to_force_balance(self):
        for mode, label in (('BODICE', 'Back'), ('SLEEVES', 'Right')):
            for count in (1, 3):
                with self.subTest(mode=mode, count=count):
                    pieces = tuple((str(index), f'{label} panel {index}') for index in range(count))
                    plan = layout_plan(pieces, BODY_BOUNDS, mode)
                    self.assertEqual(len(plan), count)
                    for target in plan:
                        if mode == 'BODICE':
                            self.assertEqual(target.normal, (0, 1, 0))
                        else:
                            self.assertLess(target.point[0], 0)

    def test_labels_on_the_other_axis_do_not_contradict_the_mode(self):
        for mode, names in (('BODICE', ('Front left right', 'Back')),
                            ('SLEEVES', ('Left front back', 'Right'))):
            with self.subTest(mode=mode):
                self.assertEqual(len(layout_plan(tuple(zip(('a', 'b'), names)), BODY_BOUNDS, mode)), 2)

    def test_invalid_modes_and_piece_identities(self):
        self.assertEqual(MODES, ('BODICE', 'SLEEVES', 'SKIRT'))
        for mode in ('AUTO', 'bodice', '', None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                layout_plan(BODICE, BODY_BOUNDS, mode)
        for pieces in ((), (('a', 'Front'), ('a', 'Back')), (('', 'Front'),), ((None, 'Front'),), (('a', ''),)):
            with self.subTest(pieces=pieces), self.assertRaises(ValueError):
                layout_plan(pieces, BODY_BOUNDS, 'BODICE')

    def test_invalid_bounds_are_rejected(self):
        for bounds in (((0, 0), (1, 1)), ((0, 0, 0), (0, 1, 1)),
                       ((1, 0, 0), (0, 1, 1)), ((0, 0, 0), (1, 1, float('nan'))),
                       ((0, 0, 0), (1, float('inf'), 1)), ((-1e308, 0, 0), (1e308, 1, 1))):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                layout_plan(BODICE, bounds, 'BODICE')


class Panel(dict):
    def __init__(self, identity, serialized):
        super().__init__(dd_pattern_id=identity, dd_document=serialized, dd_spacing=.02, dd_units=1)
        self.type = 'MESH'
        self.data = SimpleNamespace(vertices=[object()])
        self.matrix_world = [identity]


class BatchArrangementTests(unittest.TestCase):
    def setUp(self):
        session = Session()
        for index, name in enumerate(('Front panel', 'Back panel')):
            offset = index * .5
            session.add([(offset, 0), (offset + .3, 0), (offset + .3, .4), (offset, .4)])
            session.document.patterns[-1].name = name
        self.document = session.document
        self.avatar = Panel('avatar', '')
        self.scene = SimpleNamespace(dd_avatar=self.avatar, objects=[self.avatar],
            dd_spacing=.02, dd_clearance=.01, unit_settings=SimpleNamespace(scale_length=1))
        self.context = SimpleNamespace(scene=self.scene, view_layer=SimpleNamespace(update=Mock()))
        self.panels = [Panel(piece.id, self.document.dumps()) for piece in self.document.patterns]
        self.garment = SimpleNamespace(document=Mock(return_value=self.document),
            generated=Mock(side_effect=lambda scene, kind: self.panels),
            bounds=Mock(return_value=BODY_BOUNDS), metres_per_unit=Mock(return_value=1),
            build_panels=Mock(side_effect=self.build))
        self.placement = SimpleNamespace(place=Mock(side_effect=self.place))
        self.modules = patch.dict(sys.modules, {'mathutils': SimpleNamespace(Vector=tuple)})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.dependencies = patch.multiple(devil_designer, garment=self.garment, placement=self.placement, create=True)
        self.dependencies.start()
        self.addCleanup(self.dependencies.stop)

    def build(self, context):
        self.panels = [Panel(piece.id, self.document.dumps()) for piece in self.document.patterns]
        return self.panels

    def place(self, context, identity, point, normal):
        panel = next(panel for panel in self.panels if panel['dd_pattern_id'] == identity)
        panel.matrix_world = [point, normal]
        return panel

    def assert_no_mutation(self):
        self.garment.build_panels.assert_not_called()
        self.placement.place.assert_not_called()
        self.context.view_layer.update.assert_not_called()

    def test_current_panels_are_reused_and_every_piece_is_placed_once(self):
        identities = [id(panel) for panel in self.panels]
        self.assertEqual(arrange(self.context, 'BODICE'), 2)
        self.assertEqual([id(panel) for panel in self.panels], identities)
        self.garment.build_panels.assert_not_called()
        expected = layout_plan(((piece.id, piece.name) for piece in self.document.patterns), BODY_BOUNDS, 'BODICE')
        self.assertEqual(self.placement.place.call_count, 2)
        for call, target in zip(self.placement.place.call_args_list, expected):
            self.assertEqual(call.args, (self.context, target.pattern_id, target.point, target.normal))

    def test_missing_and_stale_panels_build_only_once(self):
        for stale in ('missing', 'document', 'spacing', 'units', 'mesh'):
            with self.subTest(stale=stale):
                self.build(self.context)
                self.garment.build_panels.reset_mock()
                self.placement.place.reset_mock()
                if stale == 'missing':
                    self.panels.pop()
                elif stale == 'mesh':
                    self.panels[0].data.vertices = []
                else:
                    self.panels[0]['dd_' + stale] = 'stale'
                self.assertEqual(arrange(self.context, 'BODICE'), 2)
                self.garment.build_panels.assert_called_once_with(self.context)
                self.assertEqual(self.placement.place.call_count, 2)

    def test_invalid_avatar_is_rejected_without_mutation(self):
        for invalid in ('missing', 'outside', 'type', 'generated', 'empty'):
            with self.subTest(invalid=invalid):
                self.scene.dd_avatar = self.avatar
                self.scene.objects = [self.avatar]
                self.avatar.type = 'MESH'
                self.avatar.data.vertices = [object()]
                self.avatar.pop('dd_kind', None)
                if invalid == 'missing':
                    self.scene.dd_avatar = None
                elif invalid == 'outside':
                    self.scene.objects = []
                elif invalid == 'type':
                    self.avatar.type = 'EMPTY'
                elif invalid == 'generated':
                    self.avatar['dd_kind'] = 'panel'
                else:
                    self.avatar.data.vertices = []
                with self.assertRaises(ValueError):
                    arrange(self.context, 'BODICE')
                self.assert_no_mutation()

    def test_contradictory_late_piece_name_is_rejected_before_build(self):
        self.panels = []
        self.document.patterns[-1].name = 'Front back'
        with self.assertRaises(ValueError):
            arrange(self.context, 'BODICE')
        self.assert_no_mutation()

    def test_default_names_build_once_without_renaming_or_changing_document(self):
        for mode in ('BODICE', 'SLEEVES'):
            with self.subTest(mode=mode):
                for index, piece in enumerate(self.document.patterns):
                    piece.name = f'Pattern {index + 1:02}'
                serialized = self.document.dumps()
                self.panels = []
                self.garment.build_panels.reset_mock()
                self.placement.place.reset_mock()
                self.assertEqual(arrange(self.context, mode), 2)
                self.assertEqual(arrange(self.context, mode), 2)
                self.garment.build_panels.assert_called_once_with(self.context)
                self.assertEqual(self.placement.place.call_count, 4)
                self.assertEqual(self.document.dumps(), serialized)

    def test_invalid_geometry_is_rejected_before_build(self):
        self.document.patterns[-1].vertices[1].x = self.document.patterns[-1].vertices[0].x
        with self.assertRaises(ValueError):
            arrange(self.context, 'BODICE')
        self.assert_no_mutation()

    def test_invalid_seams_are_rejected_before_build(self):
        with patch.object(self.document, 'validate_seams', side_effect=ValueError('Invalid seam')):
            with self.assertRaises(ValueError):
                arrange(self.context, 'BODICE')
        self.assert_no_mutation()

    def test_invalid_scene_settings_are_rejected_without_mutation(self):
        for attribute, invalid in (('dd_spacing', 0), ('dd_spacing', float('nan')),
                                   ('dd_clearance', -1), ('dd_clearance', float('inf'))):
            with self.subTest(attribute=attribute, invalid=invalid):
                with patch.object(self.scene, attribute, invalid):
                    with self.assertRaises(ValueError):
                        arrange(self.context, 'BODICE')
                self.assert_no_mutation()
        with patch.object(self.scene.unit_settings, 'scale_length', 0):
            with self.assertRaises(ValueError):
                arrange(self.context, 'BODICE')
        self.assert_no_mutation()

    def test_duplicate_generated_ids_are_rejected_without_mutation(self):
        self.panels[-1]['dd_pattern_id'] = self.panels[0]['dd_pattern_id']
        with self.assertRaises(ValueError):
            arrange(self.context, 'BODICE')
        self.assert_no_mutation()

    def test_failed_placement_restores_all_panel_transforms(self):
        before = [panel.matrix_world.copy() for panel in self.panels]
        def fail_second(context, identity, point, normal):
            self.place(context, identity, point, normal)
            if identity == self.panels[-1]['dd_pattern_id']:
                raise RuntimeError('Failed')
        self.placement.place.side_effect = fail_second
        with self.assertRaisesRegex(RuntimeError, 'Failed'):
            arrange(self.context, 'BODICE')
        self.assertEqual([panel.matrix_world for panel in self.panels], before)
        self.context.view_layer.update.assert_called_once()

    def test_invalid_mode_and_bounds_do_not_build_or_place(self):
        with self.assertRaises(ValueError):
            arrange(self.context, 'AUTO')
        self.garment.bounds.return_value = ((0, 0, 0), (0, 0, 0))
        with self.assertRaises(ValueError):
            arrange(self.context, 'BODICE')
        self.assert_no_mutation()

    def test_build_failure_does_not_start_placement(self):
        self.panels = []
        self.garment.build_panels.side_effect = ValueError('Invalid mesh')
        with self.assertRaisesRegex(ValueError, 'Invalid mesh'):
            arrange(self.context, 'BODICE')
        self.placement.place.assert_not_called()

    def test_all_modes_place_entire_document(self):
        for mode, names in (('SLEEVES', ('Left sleeve', 'Right sleeve')),
                            ('SKIRT', ('Panel 1', 'Panel 2'))):
            with self.subTest(mode=mode):
                for piece, name in zip(self.document.patterns, names):
                    piece.name = name
                self.placement.place.reset_mock()
                self.assertEqual(arrange(self.context, mode), 2)
                self.assertEqual(self.placement.place.call_count, 2)


if __name__ == '__main__':
    unittest.main()
