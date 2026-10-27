import math
import unittest
from devil_designer.measurements import (
    slice_mesh_z,
    get_connected_loops,
    torso_loop_circumference,
    estimate_body_measurements,
)


class MockVertex:
    def __init__(self, x, y, z):
        self.co = MockVector(x, y, z)


class MockVector:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __mul__(self, scalar):
        return MockVector(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar):
        return MockVector(self.x * scalar, self.y * scalar, self.z * scalar)


class MockPolygon:
    def __init__(self, vertices):
        self.vertices = vertices


class MockMatrix:
    def __matmul__(self, v):
        return MockVector(v.x, v.y, v.z)


class MockMesh:
    def __init__(self, vertices, polygons):
        self.vertices = vertices
        self.polygons = polygons


class MockBody:
    def __init__(self, mesh, matrix=None):
        self.type = 'MESH'
        self.data = mesh
        self.matrix_world = matrix or MockMatrix()


class MockUnitSettings:
    def __init__(self, scale_length=1.0):
        self.scale_length = scale_length


class MockScene:
    def __init__(self, scale_length=1.0):
        self.unit_settings = MockUnitSettings(scale_length)


class MeasurementsTests(unittest.TestCase):
    def test_slice_mesh_z_box(self):
        verts = [
            MockVertex(-0.5, -0.5, 0.0),
            MockVertex(0.5, -0.5, 0.0),
            MockVertex(0.5, 0.5, 0.0),
            MockVertex(-0.5, 0.5, 0.0),
            MockVertex(-0.5, -0.5, 1.0),
            MockVertex(0.5, -0.5, 1.0),
            MockVertex(0.5, 0.5, 1.0),
            MockVertex(-0.5, 0.5, 1.0),
        ]
        polys = [
            MockPolygon([0, 1, 5, 4]),
            MockPolygon([1, 2, 6, 5]),
            MockPolygon([2, 3, 7, 6]),
            MockPolygon([3, 0, 4, 7]),
        ]
        mesh = MockMesh(verts, polys)
        segs = slice_mesh_z(mesh, MockMatrix(), 0.5)
        self.assertEqual(len(segs), 4)

    def test_torso_loop_circumference_square(self):
        segs = [
            ((-0.5, -0.5), (0.5, -0.5)),
            ((0.5, -0.5), (0.5, 0.5)),
            ((0.5, 0.5), (-0.5, 0.5)),
            ((-0.5, 0.5), (-0.5, -0.5)),
        ]
        c = torso_loop_circumference(segs, center_x=0.0)
        self.assertAlmostEqual(c, 4.0)

    def test_get_connected_loops_two_cylinders(self):
        segs1 = [
            ((-1.2, 0.0), (-1.0, 0.2)),
            ((-1.0, 0.2), (-0.8, 0.0)),
            ((-0.8, 0.0), (-1.0, -0.2)),
            ((-1.0, -0.2), (-1.2, 0.0)),
        ]
        segs2 = [
            ((0.8, 0.0), (1.0, 0.2)),
            ((1.0, 0.2), (1.2, 0.0)),
            ((1.2, 0.0), (1.0, -0.2)),
            ((1.0, -0.2), (0.8, 0.0)),
        ]
        components, points, edges = get_connected_loops(segs1 + segs2)
        self.assertEqual(len(components), 2)

    def test_estimate_body_measurements_fallback_cylinder(self):
        n = 16
        r = 0.20
        height = 1.70
        verts = []
        for z in [0.0, 0.5, 1.0, 1.7]:
            for i in range(n):
                angle = i * math.tau / n
                verts.append(MockVertex(r * math.cos(angle), r * math.sin(angle), z))
        polys = []
        for layer in range(3):
            for i in range(n):
                i1 = layer * n + i
                i2 = layer * n + (i + 1) % n
                i3 = (layer + 1) * n + (i + 1) % n
                i4 = (layer + 1) * n + i
                polys.append(MockPolygon([i1, i2, i3, i4]))
        mesh = MockMesh(verts, polys)
        body = MockBody(mesh)
        scene = MockScene()

        m = estimate_body_measurements(body, scene)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m['height'], 170.0, delta=0.5)
        self.assertTrue(m['fallback'])
        self.assertGreater(m['chest'], 0)
        self.assertGreater(m['waist'], 0)
        self.assertGreater(m['hip'], 0)
        self.assertGreater(m['shoulder_width'], 0)
        self.assertGreater(m['torso_length'], 0)
        self.assertGreater(m['inseam'], 0)

    def test_estimate_body_measurements_invalid_inputs(self):
        scene = MockScene()
        self.assertIsNone(estimate_body_measurements(None, scene))
        empty_mesh = MockMesh([], [])
        self.assertIsNone(estimate_body_measurements(MockBody(empty_mesh), scene))


if __name__ == '__main__':
    unittest.main()
