import copy
import json
import struct
import unittest
from unittest.mock import patch

from devil_designer.ellipse_volumes import wrap_positions
from devil_designer.panel_cache import wrapped_positions


class PanelWrapCacheTests(unittest.TestCase):
    def setUp(self):
        wrapped_positions.cache_clear()
        self.vertices = [(-.1, 0, -0.0), (0, .1, 0), (.1, .3, 0)]
        self.resolved = dict(stack=[dict(center=(0, 0, 0), vectors=((.2, 0, 0), (0, -.15, 0))),
                                   dict(center=(.01, .02, .2), vectors=((.3, 0, 0), (0, -.2, 0)))],
                             height=0, up=(0, 0, 1), right=(1, 0, 0), front=(0, -1, 0), clearance=.01, angle=.4)

    def tearDown(self):
        wrapped_positions.cache_clear()

    def payload(self, width=.25):
        return json.dumps((self.vertices, self.resolved, width, -.1, .001), separators=(',', ':'))

    def test_cold_and_warm_results_are_bit_identical_to_original_math(self):
        for width in (.25, 5.0):
            with self.subTest(width=width):
                original = tuple(wrap_positions(self.vertices, self.resolved, width, -.1, .001))
                expected = b''.join(struct.pack('!ddd', *position) for position in original)
                for repeat in range(2):
                    actual = wrapped_positions(self.payload(width))
                    self.assertEqual(b''.join(struct.pack('!ddd', *position) for position in actual), expected)
                    self.assertIsInstance(actual, tuple)
                    self.assertTrue(all(isinstance(position, tuple) for position in actual))

    def test_identical_inputs_do_not_repeat_wrapping(self):
        with patch('devil_designer.panel_cache.wrap_positions', wraps=wrap_positions) as original:
            first = wrapped_positions(self.payload())
            self.assertIs(wrapped_positions(self.payload()), first)
            self.assertEqual(original.call_count, 1)

    def test_every_serialized_input_participates_in_invalidation(self):
        baseline = json.loads(self.payload())
        variants = []
        for index in (0, 2, 3, 4):
            candidate = copy.deepcopy(baseline)
            if index == 0:
                candidate[0][0][0] += .01
            else:
                candidate[index] += .01
            variants.append(candidate)
        for key in self.resolved:
            candidate = copy.deepcopy(baseline)
            if key == 'stack':
                candidate[1][key][0]['vectors'][0][0] += .01
            elif isinstance(candidate[1][key], list):
                candidate[1][key][0] += .01
            else:
                candidate[1][key] += .01
            variants.append(candidate)
        with patch('devil_designer.panel_cache.wrap_positions', return_value=[(0, 0, 0)]) as original:
            wrapped_positions(json.dumps(baseline))
            for candidate in variants:
                wrapped_positions(json.dumps(candidate))
            self.assertEqual(original.call_count, len(variants) + 1)

    def test_signed_zero_is_not_collapsed_in_the_key(self):
        negative = self.payload()
        self.vertices[0] = (-.1, 0, 0.0)
        positive = self.payload()
        with patch('devil_designer.panel_cache.wrap_positions', return_value=[(0, 0, 0)]) as original:
            wrapped_positions(negative)
            wrapped_positions(positive)
            self.assertEqual(original.call_count, 2)

    def test_cache_is_bounded_and_evicted_inputs_recompute(self):
        with patch('devil_designer.panel_cache.wrap_positions', return_value=[(0, 0, 0)]) as original:
            for index in range(20):
                wrapped_positions(self.payload(index + 1))
            self.assertEqual(wrapped_positions.cache_info().currsize, 16)
            wrapped_positions(self.payload(1))
            self.assertEqual(original.call_count, 21)

    def test_failures_are_not_cached(self):
        with patch('devil_designer.panel_cache.wrap_positions', side_effect=ValueError('Invalid wrap')) as original:
            for repeat in range(2):
                with self.assertRaisesRegex(ValueError, 'Invalid wrap'):
                    wrapped_positions(self.payload())
            self.assertEqual(original.call_count, 2)
            self.assertEqual(wrapped_positions.cache_info().currsize, 0)
