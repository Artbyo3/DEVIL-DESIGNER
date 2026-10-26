import math
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from devil_designer import tracing
from devil_designer.canvas import Rect, View


class CalibrationTests(unittest.TestCase):
    def test_known_canvas_distance_sets_width_in_meters(self):
        self.assertAlmostEqual(tracing.calibrated_width(2, (1, 2), (1.3, 2.4), 0.25), 1)

    def test_endpoint_order_and_translation_do_not_change_scale(self):
        self.assertEqual(tracing.calibrated_width(1, (8, 9), (8, 10), 2), 2)
        self.assertEqual(tracing.calibrated_width(1, (8, 10), (8, 9), 2), 2)

    def test_invalid_measurements_are_artist_facing(self):
        cases = (
            (0, (0, 0), (1, 0), 1), (1, (0, 0), (1, 0), -1),
            (1, (0, 0), (0, 0), 1), (1, (0, 0), (1e-12, 0), 1),
            (1, (0, 0), (math.inf, 0), 1), (math.nan, (0, 0), (1, 0), 1),
            (1, (0, 0), (1, 0), math.inf), (1, (0,), (1, 0), 1),
            (1e308, (0, 0), (1, 0), 1e308),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                tracing.calibrated_width(*arguments)

    def test_calibrate_keeps_first_endpoint_fixed(self):
        scene = SimpleNamespace(dd_trace_width=2, dd_trace_length=0.25, dd_trace_x=0, dd_trace_y=1, dd_trace_error='old')
        self.assertAlmostEqual(tracing.calibrate(scene, (1, 2), (1.3, 2.4)), 1)
        self.assertAlmostEqual(scene.dd_trace_x, 0.5)
        self.assertAlmostEqual(scene.dd_trace_y, 1.5)
        self.assertEqual(scene.dd_trace_error, '')

    def test_invalid_calibration_does_not_mutate_scene(self):
        scene = SimpleNamespace(dd_trace_width=2, dd_trace_length=0, dd_trace_x=0, dd_trace_y=1)
        before = vars(scene).copy()
        with self.assertRaises(ValueError):
            tracing.calibrate(scene, (0, 0), (1, 0))
        self.assertEqual(vars(scene), before)

    def test_image_aspect_ratio_and_bottom_left_origin(self):
        self.assertEqual(tracing.image_corners(2, (400, 200), (-1, 3)), ((-1, 3), (1, 3), (1, 4), (-1, 4)))
        self.assertEqual(tracing.image_corners(1, (100, 300), (0, 0))[-1], (0, 3))

    def test_invalid_image_geometry_is_rejected(self):
        for width, size, position in ((0, (1, 1), (0, 0)), (1, (0, 1), (0, 0)), (1, (1, 1), (math.nan, 0))):
            with self.subTest(size=size), self.assertRaises(ValueError):
                tracing.image_corners(width, size, position)


class ImageLoadingTests(unittest.TestCase):
    def setUp(self):
        tracing._images.clear()
        self.image = SimpleNamespace(size=(400, 200), source='FILE')
        self.bpy = SimpleNamespace(
            path=SimpleNamespace(abspath=lambda path: '/resolved/' + path.removeprefix('//')),
            data=SimpleNamespace(images=SimpleNamespace(load=MagicMock(return_value=self.image))),
        )
        self.modules = patch.dict('sys.modules', {'bpy': self.bpy})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.addCleanup(tracing._images.clear)

    def test_relative_saved_path_restores_without_runtime_pointer(self):
        with patch.object(tracing.Path, 'is_file', return_value=True):
            self.assertIs(tracing.load_image('//reference.png'), self.image)
            self.assertIs(tracing.load_image('//reference.png'), self.image)
        self.bpy.data.images.load.assert_called_once_with('/resolved/reference.png', check_existing=True)

    def test_missing_file_error_is_cached_and_explicit_retry_recovers(self):
        with patch.object(tracing.Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(ValueError, 'not found'):
                tracing.load_image('missing.png')
        with patch.object(tracing.Path, 'is_file', return_value=True):
            with self.assertRaisesRegex(ValueError, 'not found'):
                tracing.load_image('missing.png')
            self.assertIs(tracing.load_image('missing.png', retry=True), self.image)

    def test_bad_file_reports_action_without_raw_blender_error(self):
        self.bpy.data.images.load.side_effect = RuntimeError('internal diagnostic')
        with patch.object(tracing.Path, 'is_file', return_value=True):
            with self.assertRaisesRegex(ValueError, 'readable PNG or JPEG'):
                tracing.load_image('invalid.png')

    def test_movie_and_empty_image_are_rejected(self):
        for image in (SimpleNamespace(size=(0, 0), source='FILE'), SimpleNamespace(size=(400, 200), source='MOVIE')):
            self.bpy.data.images.load.return_value = image
            with patch.object(tracing.Path, 'is_file', return_value=True):
                with self.assertRaises(ValueError):
                    tracing.load_image('invalid.png', retry=True)

    def test_removed_datablock_is_reloaded(self):
        invalid = MagicMock()
        type(invalid).size = property(lambda image: (_ for _ in ()).throw(ReferenceError()))
        tracing._images['/resolved/reference.png'] = (invalid, '')
        with patch.object(tracing.Path, 'is_file', return_value=True):
            self.assertIs(tracing.load_image('reference.png'), self.image)

    def test_fit_corners_load_from_scene_and_report_missing_files(self):
        scene = SimpleNamespace(dd_trace_path='reference.png', dd_trace_width=2, dd_trace_x=-1, dd_trace_y=3, dd_trace_error='')
        with patch.object(tracing.Path, 'is_file', return_value=True):
            self.assertEqual(tracing.reference_corners(scene), ((-1, 3), (1, 3), (1, 4), (-1, 4)))
        scene.dd_trace_path = 'missing.png'
        with patch.object(tracing.Path, 'is_file', return_value=False):
            self.assertEqual(tracing.reference_corners(scene), ())
        self.assertIn('not found', scene.dd_trace_error)
        scene.dd_trace_path = ''
        self.assertEqual(tracing.reference_corners(scene), ())


class DrawingTests(unittest.TestCase):
    def setUp(self):
        self.scene = SimpleNamespace(
            dd_trace_path='reference.png', dd_trace_visible=True, dd_trace_opacity=0.4,
            dd_trace_width=2, dd_trace_x=-1, dd_trace_y=3, dd_trace_error='',
        )
        self.ed = SimpleNamespace(_scene=self.scene, view=View(), canvas_layout=SimpleNamespace(canvas=Rect(30, 40, 800, 600)))
        self.renderer = SimpleNamespace()
        self.gpu = MagicMock()
        self.gpu.state.blend_get.return_value = 'NONE'
        self.batch_factory = MagicMock()
        self.modules = patch.dict('sys.modules', {
            'gpu': self.gpu,
            'gpu_extras.batch': SimpleNamespace(batch_for_shader=self.batch_factory),
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.loader = patch.object(tracing, 'load_image', return_value=SimpleNamespace(size=(400, 200)))
        self.load = self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_draw_uses_native_shader_alpha_and_canvas_transform(self):
        self.assertTrue(tracing.draw_reference(self.ed, self.renderer))
        self.gpu.shader.from_builtin.assert_called_once_with('IMAGE_COLOR')
        shader = self.gpu.shader.from_builtin.return_value
        shader.uniform_float.assert_called_once_with('color', (1, 1, 1, 0.4))
        shader.uniform_sampler.assert_called_once_with('image', self.gpu.texture.from_image.return_value)
        arguments = self.batch_factory.call_args
        expected = [self.ed.view.screen(point, self.ed.canvas_layout.canvas) for point in ((-1, 3), (1, 3), (1, 4), (-1, 4))]
        self.assertEqual(arguments.args[2]['pos'], expected)
        self.assertEqual(arguments.args[2]['texCoord'], [(0, 0), (1, 0), (1, 1), (0, 1)])
        self.assertEqual(self.gpu.state.blend_set.call_args_list[-1].args, ('NONE',))
        self.gpu.state.scissor_set.assert_not_called()
        self.gpu.state.scissor_test_set.assert_not_called()
        self.assertTrue(tracing.draw_reference(self.ed, self.renderer))
        self.gpu.shader.from_builtin.assert_called_once()

    def test_hidden_transparent_or_unset_images_do_not_load(self):
        for field, value in (('dd_trace_visible', False), ('dd_trace_opacity', 0), ('dd_trace_path', '')):
            original = getattr(self.scene, field)
            setattr(self.scene, field, value)
            self.assertFalse(tracing.draw_reference(self.ed, self.renderer))
            setattr(self.scene, field, original)
        self.load.assert_not_called()

    def test_load_failure_is_reported_without_breaking_canvas(self):
        self.load.side_effect = ValueError('Reference image not found. Choose the file again.')
        self.assertFalse(tracing.draw_reference(self.ed, self.renderer))
        self.assertIn('Choose the file again', self.scene.dd_trace_error)

    def test_gpu_failure_restores_blend_and_success_clears_error(self):
        self.batch_factory.return_value.draw.side_effect = RuntimeError('GPU error')
        self.assertFalse(tracing.draw_reference(self.ed, self.renderer))
        self.assertIn('Try Load image again', self.scene.dd_trace_error)
        self.assertEqual(self.gpu.state.blend_set.call_args_list[-1].args, ('NONE',))
        self.batch_factory.return_value.draw.side_effect = None
        self.assertTrue(tracing.draw_reference(self.ed, self.renderer))
        self.assertEqual(self.scene.dd_trace_error, '')


if __name__ == '__main__':
    unittest.main()
