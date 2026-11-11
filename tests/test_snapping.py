import unittest

from devil_designer import snapping
from devil_designer.core import Session
from devil_designer.linked_editing import clone_twin

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


class LinkedTwinSnapTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        self.source = self.session.document.find(self.session.selected)
        self.twin = clone_twin(self.session)
        pair = self.session.document.linked_pairs[0]
        self.partner = next(node for node in self.twin.vertices if node.id == pair['mapping'][self.source.vertices[1].id])

    def targets(self):
        return snapping.Targets(self.session.document, self.session.moving_vertex_ids())

    def test_twin_point_that_follows_a_dragged_point_is_not_a_target(self):
        self.session.clear_selection()
        self.session.select_point(self.source.id, self.source.loops()[0][0], 1)
        old = (self.partner.x, self.partner.y)
        self.assertIn(self.partner.id, self.session.moving_vertex_ids())
        found = self.targets().snap((old[0] + .004, old[1] + .003), REACH)
        self.assertIsNone(found)

    def test_twin_points_that_stay_remain_targets(self):
        self.session.clear_selection()
        self.session.select_point(self.source.id, self.source.loops()[0][0], 1)
        still = next(node for node in self.twin.vertices if node.id != self.partner.id and node.y > .4 and abs(node.x - self.partner.x) < 1e-9)
        found = self.targets().snap((still.x + .003, still.y - .002), REACH)
        self.assertEqual(found[1], snapping.POINT)
        self.assertAlmostEqual(found[0][0], still.x, places=6)
        self.assertAlmostEqual(found[0][1], still.y, places=6)

    def test_twin_stays_a_target_while_its_whole_partner_moves(self):
        self.session.clear_selection()
        self.session.selected = self.source.id
        moving = self.session.moving_vertex_ids()
        self.assertEqual(moving, frozenset(node.id for node in self.source.vertices))
        found = self.targets().snap((self.partner.x + .004, self.partner.y + .003), REACH)
        self.assertEqual(found[1], snapping.POINT)

    def test_unlinked_selection_moves_only_itself(self):
        session = Session()
        session.add(SQUARE)
        session.add(CROSSING)
        square = session.document.patterns[0]
        session.clear_selection()
        session.select_point(square.id, square.loops()[0][0], 0)
        self.assertEqual(session.moving_vertex_ids(), frozenset({square.vertices[0].id}))


if __name__ == '__main__':
    unittest.main()
