import math
import random
import unittest
from unittest.mock import patch

from devil_designer import core
from devil_designer.core import Session, cross, intersects, on_segment, EPS, area

POINTS = 2000


def circle(count):
    return [(.3 + .3 * math.cos(math.tau * i / count), .3 + .3 * math.sin(math.tau * i / count)) for i in range(count)]


def reference_validate(points):
    if len(points) < 3:
        raise ValueError("A pattern needs at least three corners.")
    if any(not math.isfinite(v) or abs(v) > 10000 for p in points for v in p):
        raise ValueError("Coordinates must be finite and within 10 km.")
    n = len(points)
    for i in range(n):
        a, b, c = points[i - 1], points[i], points[(i + 1) % n]
        if math.dist(b, c) < 1e-6:
            raise ValueError("Two neighbouring corners are too close.")
        if abs(cross(a, b, c)) <= EPS and (on_segment(c, a, b) or on_segment(a, b, c)):
            raise ValueError("An edge doubles back on itself.")
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if intersects(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n]):
                raise ValueError("Pattern edges cannot cross or touch each other.")
    if abs(area(points)) < 1e-8:
        raise ValueError("This pattern has no usable area.")


def reference_triangulate(points):
    reference_validate(points)
    indices = list(range(len(points)))
    if area(points) < 0:
        indices.reverse()
    while len(indices) > 3:
        flat = next((k for k in range(len(indices)) if abs(cross(
            points[indices[k - 1]], points[indices[k]], points[indices[(k + 1) % len(indices)]])) <= EPS), None)
        if flat is None:
            break
        indices.pop(flat)
    triangles = []
    while len(indices) > 3:
        for k, b in enumerate(indices):
            a, c = indices[k - 1], indices[(k + 1) % len(indices)]
            if cross(points[a], points[b], points[c]) <= EPS:
                continue
            if any(cross(points[a], points[b], points[p]) >= -EPS and
                   cross(points[b], points[c], points[p]) >= -EPS and
                   cross(points[c], points[a], points[p]) >= -EPS
                   for p in indices if p not in (a, b, c)):
                continue
            triangles.append((a, b, c))
            indices.pop(k)
            break
        else:
            raise ValueError("Cannot fill this pattern; check its corners.")
    triangles.append(tuple(indices))
    return triangles


def outcome(function, points):
    try:
        return 'filled', function(points)
    except ValueError as error:
        return 'refused', str(error)


def polygons():
    rng = random.Random(5)
    for _ in range(1500):
        count = rng.randint(3, 50)
        kind = rng.randrange(6)
        if kind == 0:
            yield [((1 + rng.random()) * math.cos(math.tau * i / count), (1 + rng.random()) * math.sin(math.tau * i / count)) for i in range(count)]
        elif kind == 1:
            yield [(rng.random(), rng.random()) for _ in range(count)]
        elif kind == 2:
            yield [(rng.randint(0, 4) * .1, rng.randint(0, 4) * .1) for _ in range(count)]
        elif kind == 3:
            yield [(i / count, rng.choice((0, 1e-9, 1e-11, 3e-10)) * rng.random()) for i in range(count)] + [(1, .5), (0, .5)]
        elif kind == 4:
            half = max(1, count // 2)
            yield [(0, 0)] + [point for i in range(half) for point in (((i + .5) / half, rng.choice((.2, .9, .5))), ((i + 1) / half, 0))] + [(1, -1), (0, -1)]
        else:
            yield [(0, 0), (2, 0), (2, 2), (1, 2), (1, rng.choice((0, 1e-11, 1e-9, 1e-7))), (1.2, 1), (0, 2)]


class LargePieceTests(unittest.TestCase):
    def test_outline_checks_and_fill_match_the_reference_on_varied_shapes(self):
        for points in polygons():
            with self.subTest(points=points):
                self.assertEqual(outcome(core.validate_polygon, points), outcome(reference_validate, points))
                self.assertEqual(outcome(core.triangulate, points), outcome(reference_triangulate, points))
        dense = circle(600)
        self.assertEqual(core.triangulate(dense), reference_triangulate(dense))

    def test_outline_check_work_grows_linearly_with_point_count(self):
        calls = []
        def counted(*segments):
            calls.append(1)
            return intersects(*segments)
        with patch.object(core, 'intersects', counted):
            core.validate_polygon(circle(POINTS))
        self.assertLess(len(calls), 40 * POINTS)

    def test_fill_work_stays_far_below_every_point_against_every_ear(self):
        calls = []
        def counted(a, b, c):
            calls.append(1)
            return cross(a, b, c)
        with patch.object(core, 'cross', counted):
            core.triangulate(circle(POINTS))
        self.assertLess(len(calls), 400 * POINTS)

    def test_segment_lookups_do_not_rescan_the_outline(self):
        class CountingList(list):
            reads = 0
            def __getitem__(self, index):
                CountingList.reads += 1
                return list.__getitem__(self, index)
        session = Session()
        session.add(circle(POINTS))
        piece = session.document.patterns[0]
        piece.vertices = CountingList(piece.vertices)
        edges = session.document.edges(piece.id)
        CountingList.reads = 0
        for edge in edges:
            first, second = session.document.edge_vertices(edge)
            self.assertEqual((first.id, second.id), (edge.start, edge.end))
        self.assertLess(CountingList.reads, 10 * POINTS)

    def test_segment_lookups_follow_inserted_and_removed_points(self):
        session = Session()
        session.add(circle(40))
        piece = session.document.patterns[0]
        document = session.document
        edge = document.edge(piece.id, 30)
        document.edge_vertices(edge)
        piece.vertices.insert(5, core.Vertex(.3, .3))
        self.assertEqual([vertex.id for vertex in document.edge_vertices(edge)], [edge.start, edge.end])
        self.assertEqual(piece.vertices.pop(32).id, edge.end)
        with self.assertRaisesRegex(ValueError, 'segment was removed'):
            document.edge_vertices(edge)


if __name__ == '__main__':
    unittest.main()
