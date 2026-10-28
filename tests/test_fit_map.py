import math
import unittest
from devil_designer.fit_map import vertex_ratios, ratio_color, surface_edges


class FitMapTests(unittest.TestCase):
    def test_known_uniform_stretch_compression_and_neutral(self):
        rest = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        edges = surface_edges([(0, 1, 2), (0, 2, 3)])
        for factor in (.75, .97, 1, 1.03, 1.2):
            current = [tuple(value * factor for value in point) for point in rest]
            for ratio in vertex_ratios(rest, current, edges):
                self.assertAlmostEqual(ratio, factor)

    def test_rigid_motion_does_not_create_strain(self):
        rest = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        current = [(4 - point[1], 7, point[0] + 2) for point in rest]
        self.assertEqual(vertex_ratios(rest, current, surface_edges([(0, 1, 2)])), [1, 1, 1])

    def test_length_weighted_edges_and_isolated_vertices(self):
        rest = [(0, 0), (1, 0), (0, 3), (10, 10)]
        current = [(0, 0), (2, 0), (0, 3), (10, 10)]
        self.assertEqual(vertex_ratios(rest, current, [(0, 1), (0, 2)]), [1.25, 2, 1, 1])

    def test_zero_length_edges_are_skipped(self):
        self.assertEqual(vertex_ratios([(0, 0), (0, 0)], [(0, 0), (1, 0)], [(0, 1)]), [1, 1])

    def test_sewing_bridges_are_not_surface_edges(self):
        self.assertEqual(surface_edges([(0, 1, 2), (3, 4, 5)]),
                         [(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5)])

    def test_shared_edges_are_not_double_weighted(self):
        self.assertEqual(surface_edges([(0, 1, 2), (0, 2, 3)]),
                         [(0, 1), (0, 2), (0, 3), (1, 2), (2, 3)])

    def test_color_deadband_and_saturation(self):
        for ratio in (.97, 1, 1.03):
            for actual, expected in zip(ratio_color(ratio), (1, 1, 1, 1)):
                self.assertAlmostEqual(actual, expected)
        self.assertEqual(ratio_color(.85), (0, 0, 1, 1))
        self.assertEqual(ratio_color(1.15), (1, 0, 0, 1))
        self.assertEqual(ratio_color(0), (0, 0, 1, 1))
        self.assertEqual(ratio_color(3), (1, 0, 0, 1))
        self.assertAlmostEqual(ratio_color(1.09)[1], .5)

    def test_anisotropic_known_triangle(self):
        ratios = vertex_ratios([(0, 0), (1, 0), (0, 1)], [(0, 0), (2, 0), (0, 1)], surface_edges([(0, 1, 2)]))
        self.assertAlmostEqual(ratios[0], 1.5)
        self.assertAlmostEqual(ratios[1], (2 + math.sqrt(5)) / (1 + math.sqrt(2)))

    def test_topology_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            vertex_ratios([(0, 0)], [], [])
