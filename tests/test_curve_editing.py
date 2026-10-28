import unittest
from devil_designer.core import (
    Session,
    Vertex,
    EdgeRef,
    compute_auto_handles,
    align_smooth_handles,
)
from devil_designer import curves


class TestCurveEditing(unittest.TestCase):
    def test_point_type_defaults_and_legacy_migration(self):
        v = Vertex(x=10.0, y=20.0)
        self.assertEqual(v.point_type, "CORNER")

        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        nodes = session.document.patterns[0].vertices
        for node in nodes:
            self.assertEqual(node.point_type, "CORNER")

    def test_cycle_and_set_point_type(self):
        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        pid = session.document.patterns[0].id
        session.select_point(pid, "OUTER", 0)

        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "CORNER")
        session.cycle_point_type()
        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "SMOOTH")
        session.cycle_point_type()
        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "AUTO")
        session.cycle_point_type()
        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "CORNER")

        session.clear_selection()
        for i in [0, 1, 2]:
            session.select_point(pid, "OUTER", i, toggle=True)
        session.set_point_type("SMOOTH")
        for i in [0, 1, 2]:
            self.assertEqual(session.document.patterns[0].vertices[i].point_type, "SMOOTH")

        session.cycle_point_type()
        for i in [0, 1, 2]:
            self.assertEqual(session.document.patterns[0].vertices[i].point_type, "AUTO")

    def test_auto_handles_computation_and_updates(self):
        v0 = Vertex(x=0.0, y=0.0)
        v1 = Vertex(x=0.5, y=0.5, point_type="AUTO")
        v2 = Vertex(x=1.0, y=0.0)
        nodes = [v0, v1, v2]
        hin, hout = compute_auto_handles(nodes, 1, closed=True)
        self.assertIsNotNone(hin)
        self.assertIsNotNone(hout)
        self.assertGreater(hout[0], 0.0)
        self.assertLess(hin[0], 0.0)

        session = Session()
        session.add([(0.0, 0.0), (0.5, 0.5), (1.0, 0.0)])
        pid = session.document.patterns[0].id
        session.select_point(pid, "OUTER", 1)
        session.set_point_type("AUTO")

        node = session.document.patterns[0].vertices[1]
        orig_hin = node.incoming
        orig_hout = node.outgoing
        self.assertIsNotNone(orig_hin)
        self.assertIsNotNone(orig_hout)

        session.select_point(pid, "OUTER", 2)
        session.move_selection(0.2, 0.1)

        updated_node = session.document.patterns[0].vertices[1]
        self.assertNotEqual(updated_node.incoming, orig_hin)
        self.assertNotEqual(updated_node.outgoing, orig_hout)

    def test_smooth_handles_alignment_opposite_handle(self):
        v = Vertex(x=0.5, y=0.5, point_type="SMOOTH", incoming=(-0.1, 0.0), outgoing=(0.2, 0.1))
        align_smooth_handles(v)
        self.assertAlmostEqual(v.incoming[0], 2.0 * v.incoming[1])

        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        pid = session.document.patterns[0].id

        node = session.document.patterns[0].vertices[0]
        node.point_type = "SMOOTH"
        session.set_handle(0, "outgoing", (0.2, 0.0), other_which="incoming", other_value=(-0.1, 0.0), pattern_id=pid, path_id="OUTER")

        self.assertEqual(node.outgoing, (0.2, 0.0))
        self.assertEqual(node.incoming, (-0.1, 0.0))

    def test_corner_handles_independent(self):
        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        pid = session.document.patterns[0].id

        node = session.document.patterns[0].vertices[0]
        node.point_type = "CORNER"
        session.set_handle(0, "outgoing", (0.2, -0.05), pattern_id=pid, path_id="OUTER")
        session.set_handle(0, "incoming", (-0.05, -0.2), pattern_id=pid, path_id="OUTER")

        session.set_handle(0, "outgoing", (0.3, -0.05), pattern_id=pid, path_id="OUTER")
        cur_node = session.document.patterns[0].vertices[0]
        self.assertEqual(cur_node.incoming, (-0.05, -0.2))

    def test_edge_bend_updates_only_own_handles(self):
        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        pid = session.document.patterns[0].id
        vertices = session.document.patterns[0].vertices

        n0 = vertices[0]
        n1 = vertices[1]
        n2 = vertices[2]

        self.assertIsNone(n0.outgoing)
        self.assertIsNone(n1.incoming)
        self.assertIsNone(n1.outgoing)
        self.assertIsNone(n2.incoming)

        p0 = (n0.x, n0.y)
        p3 = (n1.x, n1.y)
        cursor = (0.5, -0.1)
        t = 0.5
        w1 = 3 * ((1 - t) ** 2) * t
        w2 = 3 * (1 - t) * (t ** 2)
        d1 = 1 - t
        d2 = t
        denom = w1 * d1 + w2 * d2
        k = 1.0 / denom
        orig_p = ((1 - t) * p0[0] + t * p3[0], (1 - t) * p0[1] + t * p3[1])
        delta = (cursor[0] - orig_p[0], cursor[1] - orig_p[1])
        dp1 = (k * d1 * delta[0], k * d1 * delta[1])
        dp2 = (k * d2 * delta[0], k * d2 * delta[1])
        orig_c1 = (p0[0] + (p3[0] - p0[0]) / 3, p0[1] + (p3[1] - p0[1]) / 3)
        orig_c2 = (p0[0] + 2 * (p3[0] - p0[0]) / 3, p0[1] + 2 * (p3[1] - p0[1]) / 3)
        c1 = (orig_c1[0] + dp1[0], orig_c1[1] + dp1[1])
        c2 = (orig_c2[0] + dp2[0], orig_c2[1] + dp2[1])
        h1 = (c1[0] - p0[0], c1[1] - p0[1])
        h2 = (c2[0] - p3[0], c2[1] - p3[1])

        session.set_handle(0, "outgoing", h1, pattern_id=pid, path_id="OUTER")
        session.set_handle(1, "incoming", h2, pattern_id=pid, path_id="OUTER")

        c = (p0, (p0[0] + h1[0], p0[1] + h1[1]), (p3[0] + h2[0], p3[1] + h2[1]), p3)
        curve_pt = curves.evaluate(c, 0.5)
        self.assertAlmostEqual(curve_pt[0], cursor[0], places=4)
        self.assertAlmostEqual(curve_pt[1], cursor[1], places=4)

        self.assertIsNone(vertices[1].outgoing)
        self.assertIsNone(vertices[2].incoming)

    def test_split_edge_at_arbitrary_t_preserves_curve(self):
        p0 = (0.0, 0.0)
        p1 = (0.3, 0.6)
        p2 = (0.7, -0.2)
        p3 = (1.0, 0.1)
        control = (p0, p1, p2, p3)
        t = 0.35

        left, right = curves.split(control, t)
        for check_t in [0.1, 0.2, 0.35, 0.6, 0.9]:
            expected = curves.evaluate(control, check_t)
            if check_t <= t:
                tau = check_t / t
                actual = curves.evaluate(left, tau)
            else:
                tau = (check_t - t) / (1.0 - t)
                actual = curves.evaluate(right, tau)
            self.assertAlmostEqual(expected[0], actual[0], places=5)
            self.assertAlmostEqual(expected[1], actual[1], places=5)

    def test_split_edge_session_and_closest_t(self):
        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        pid = session.document.patterns[0].id

        vertices = session.document.patterns[0].vertices
        n0 = vertices[0]
        n1 = vertices[1]
        edge = EdgeRef(pid, n0.id, n1.id)

        frac, _ = curves.closest_fraction(session.document.edge_curve(edge), (0.4, 0.05))
        self.assertAlmostEqual(frac, 0.4, places=2)

        session.split_segment(edge, fraction=frac)
        self.assertEqual(len(session.document.patterns[0].vertices), 5)
        self.assertAlmostEqual(session.document.patterns[0].vertices[1].x, 0.4, places=1)
        self.assertAlmostEqual(session.document.patterns[0].vertices[1].y, 0.0, places=1)
        self.assertEqual(session.document.patterns[0].vertices[1].point_type, "CORNER")

    def test_undo_redo_point_type(self):
        session = Session()
        session.add([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        pid = session.document.patterns[0].id
        session.select_point(pid, "OUTER", 0)

        session.set_point_type("SMOOTH")
        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "SMOOTH")
        session.history(redo=False)
        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "CORNER")
        session.history(redo=True)
        self.assertEqual(session.document.patterns[0].vertices[0].point_type, "SMOOTH")


if __name__ == "__main__":
    unittest.main()
