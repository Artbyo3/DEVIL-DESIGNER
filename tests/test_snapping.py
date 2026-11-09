import unittest

from devil_designer import snapping
from devil_designer.core import Session

SQUARE = [(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)]
CROSSING = [(0.1, 0.2), (0.4, 0.2), (0.4, 0.5), (0.1, 0.5)]
REACH = .01


class SnappingTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.add(SQUARE)
        self.session.add(CROSSING)
        self.targets = snapping.Targets(self.session.document)

    def near(self, found, spot, kind):
        self.assertIsNotNone(found)
        self.assertEqual(found[1], kind)
        self.assertAlmostEqual(found[0][0], spot[0], places=6)
        self.assertAlmostEqual(found[0][1], spot[1], places=6)

    def test_points_win_over_the_edges_they_sit_on(self):
        self.near(self.targets.snap((.203, .004), REACH), (.2, 0.0), snapping.POINT)

    def test_midpoint_of_an_edge(self):
        self.near(self.targets.snap((.104, -.003), REACH), (.1, 0.0), snapping.MIDPOINT)

    def test_nearest_place_on_an_edge(self):
        self.near(self.targets.snap((.05, .004), REACH), (.05, 0.0), snapping.EDGE)

    def test_crossing_of_two_pieces(self):
        self.near(self.targets.snap((.197, .203), REACH), (.2, .2), snapping.INTERSECTION)
        self.near(self.targets.snap((.103, .297), REACH), (.1, .3), snapping.INTERSECTION)

    def test_nothing_within_reach(self):
        self.assertIsNone(self.targets.snap((.05, .1), REACH))

    def test_moving_points_and_their_edges_are_not_targets(self):
        square = self.session.document.patterns[0]
        moving = frozenset(node.id for node in square.vertices)
        targets = snapping.Targets(self.session.document, moving)
        self.assertIsNone(targets.snap((.203, .004), REACH))
        self.near(targets.snap((.4, .2), REACH), (.4, .2), snapping.POINT)

    def test_one_moving_point_keeps_the_far_edges(self):
        square = self.session.document.patterns[0]
        targets = snapping.Targets(self.session.document, frozenset({square.vertices[0].id}))
        self.assertIsNone(targets.snap((.05, .004), REACH))
        self.near(targets.snap((.2, .15), REACH), (.2, .15), snapping.MIDPOINT)


if __name__ == '__main__':
    unittest.main()
