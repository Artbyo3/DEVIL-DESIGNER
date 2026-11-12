import math
import unittest
import numpy
from devil_designer.measurements import (
    arm_band,
    neck_base,
    widest_torso_loop,
    slice_mesh_z,
    get_connected_loops,
    torso_loop_circumference,
    estimate_body_measurements,
    outstretched_arms,
    tape_length,
    surrounds,
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


def tube(verts, polys, centre_x, radius, levels, sides=16):
    first = len(verts)
    for z in levels:
        for i in range(sides):
            angle = i * math.tau / sides
            verts.append(MockVertex(centre_x + radius * math.cos(angle), radius * math.sin(angle), z))
    for layer in range(len(levels) - 1):
        for i in range(sides):
            low = first + layer * sides
            high = low + sides
            polys.append(MockPolygon([low + i, low + (i + 1) % sides, high + (i + 1) % sides, high + i]))


def lathe(verts, polys, profile, sides=16):
    first = len(verts)
    for z, radius in profile:
        for i in range(sides):
            angle = i * math.tau / sides
            verts.append(MockVertex(radius * math.cos(angle), 0.8 * radius * math.sin(angle), z))
    for layer in range(len(profile) - 1):
        for i in range(sides):
            low = first + layer * sides
            high = low + sides
            polys.append(MockPolygon([low + i, low + (i + 1) % sides, high + (i + 1) % sides, high + i]))


def sideways_tube(verts, polys, x_from, x_to, z, radius, sides=8, steps=6):
    first = len(verts)
    for x in numpy.linspace(x_from, x_to, steps):
        for i in range(sides):
            angle = i * math.tau / sides
            verts.append(MockVertex(float(x), radius * math.cos(angle), z + radius * math.sin(angle)))
    for layer in range(steps - 1):
        for i in range(sides):
            low = first + layer * sides
            high = low + sides
            polys.append(MockPolygon([low + i, low + (i + 1) % sides, high + (i + 1) % sides, high + i]))


def headless_body():
    verts, polys = [], []
    for side in (-0.06, 0.06):
        tube(verts, polys, side, 0.05, [0.0, 0.62])
    lathe(verts, polys, [(0.60, 0.15), (0.66, 0.16), (0.72, 0.13), (0.80, 0.10), (0.86, 0.12), (0.92, 0.135),
                         (0.98, 0.13), (1.01, 0.04), (1.08, 0.04), (1.10, 0.01)])
    for sign in (-1, 1):
        sideways_tube(verts, polys, sign * 0.12, sign * 0.55, 0.995, 0.02)
    return MockMesh(verts, polys)


def fused_sleeve_outfit():
    verts, polys = [], []
    for side in (-0.08, 0.08):
        tube(verts, polys, side, 0.06, [0.0, 0.74])
    lathe(verts, polys, [(0.72, 0.17), (0.80, 0.19), (0.90, 0.18), (1.01, 0.17), (1.035, 0.21), (1.055, 0.235),
                         (1.075, 0.27), (1.10, 0.42), (1.16, 0.43), (1.22, 0.40), (1.26, 0.06), (1.32, 0.06),
                         (1.36, 0.10), (1.45, 0.11), (1.55, 0.01)])
    for sign in (-1, 1):
        sideways_tube(verts, polys, sign * 0.40, sign * 0.75, 1.20, 0.04)
    return MockMesh(verts, polys)


def t_pose_points(height, neck_z, arm_bottom, arm_top):
    rows = []
    for z in numpy.linspace(0.5 * height, neck_z - 0.02, 30):
        rows += [(x, 0.0, z) for x in numpy.linspace(-0.12, 0.12, 9)]
    for z in numpy.linspace(neck_z - 0.01, neck_z + 0.01, 3):
        rows += [(x, 0.0, z) for x in numpy.linspace(-0.03, 0.03, 5)]
    for z in numpy.linspace(neck_z + 0.03, height, 20):
        rows += [(x, 0.0, z) for x in numpy.linspace(-0.08, 0.08, 7)]
    for x in numpy.linspace(0.13, 0.48, 40):
        for z in numpy.linspace(arm_bottom, arm_top, 5):
            rows += [(x, 0.0, z), (-x, 0.0, z)]
    return numpy.array(rows)


class MeasurementsTests(unittest.TestCase):
    def test_short_avatar_arm_band_and_neck_come_from_the_body(self):
        height = 1.07
        points = t_pose_points(height, 0.865, 0.79, 0.83)
        band = arm_band(points, 0.0, 0.13, 0.0, height)
        self.assertAlmostEqual(band[0], 0.79, places=3)
        self.assertAlmostEqual(band[1], 0.83, places=3)
        self.assertAlmostEqual(neck_base(points, 0.0, 0.13, band[1], height), 0.865, delta=0.011)

    def test_layered_outfit_girth_is_read_on_one_layer_the_outermost(self):
        def ring(centre, radius):
            points = [(centre + radius * math.cos(i * math.tau / 24), radius * math.sin(i * math.tau / 24)) for i in range(24)]
            return list(zip(points, points[1:] + points[:1]))
        body, outfit = ring(0.0, 0.12), ring(0.004, 0.16)
        self.assertAlmostEqual(torso_loop_circumference(body + outfit, center_x=0.0), tape_length([p for p, _ in outfit]), places=6)
        self.assertAlmostEqual(torso_loop_circumference(outfit + body, center_x=0.0), tape_length([p for p, _ in outfit]), places=6)

    def test_headless_body_measures_shoulders_and_neck_from_its_arms(self):
        mesh = headless_body()
        m = estimate_body_measurements(MockBody(mesh), MockScene())
        points = numpy.array([tuple(v.co) for v in mesh.vertices])
        arms = outstretched_arms(points, 0.0, 0.0, 1.10)
        self.assertLess(arms[0], 0.995)
        self.assertGreater(arms[1], 0.995)
        self.assertGreater(m['shoulder_width'], 26.0)
        self.assertGreater(m['neck_y'], 1.0)
        self.assertLess(m['neck_y'], 1.09)

    def test_sleeves_fused_to_the_torso_cannot_inflate_the_shoulders(self):
        m = estimate_body_measurements(MockBody(fused_sleeve_outfit()), MockScene())
        self.assertLessEqual(m['shoulder_width'], 0.25 * m['height'] + 0.5)
        self.assertGreater(m['shoulder_width'], 0.20 * m['height'])

    def test_neck_search_never_takes_the_cut_top_of_a_headless_stump(self):
        rows = [(x, 0.0, z) for z in numpy.linspace(0.80, 0.95, 16) for x in numpy.linspace(-0.12, 0.12, 9)]
        rows += [(x, 0.0, z) for z in numpy.linspace(0.97, 1.05, 9) for x in numpy.linspace(-0.04, 0.04, 5)]
        rows += [(x, 0.0, 1.06) for x in numpy.linspace(-0.01, 0.01, 3)]
        neck = neck_base(numpy.array(rows), 0.0, 0.13, 0.95, 1.06)
        self.assertLess(neck, 1.055)

    def test_lowered_arms_are_not_read_as_a_sleeve_band(self):
        height = 1.07
        points = t_pose_points(height, 0.865, 0.45, 0.83)
        self.assertIsNone(arm_band(points, 0.0, 0.13, 0.0, height))

    def test_hip_is_the_widest_torso_loop_not_a_small_outline_below_it(self):
        verts, polys = [], []
        tube(verts, polys, 0.0, 0.07, [0.70, 0.80])
        tube(verts, polys, 0.0, 0.15, [0.78, 1.00])
        tube(verts, polys, -0.12, 0.06, [0.40, 0.80])
        tube(verts, polys, 0.12, 0.06, [0.40, 0.80])
        mesh = MockMesh(verts, polys)
        world = [MockMatrix() @ v.co for v in verts]
        level, girth = widest_torso_loop(mesh, MockMatrix(), 0.72, 0.98, world, 0.0)
        self.assertGreater(level, 0.78)
        self.assertGreater(girth, 0.9)

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

    def test_arm_loops_beside_the_centre_are_not_a_torso(self):
        arms = []
        for centre in (-0.4, 0.4):
            ring = [(centre + 0.05 * math.cos(i * math.tau / 12), 0.05 * math.sin(i * math.tau / 12)) for i in range(12)]
            arms.extend(zip(ring, ring[1:] + ring[:1]))
        self.assertEqual(torso_loop_circumference(arms, center_x=0.0), 0.0)

    def test_surrounds_accepts_closed_rings_and_rejects_open_arcs(self):
        def loop(points, closed=True):
            return list(zip(points, points[1:] + (points[:1] if closed else [])))
        square = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        ring = [(0.15 * math.cos(i * math.tau / 24), 0.1 * math.sin(i * math.tau / 24)) for i in range(24)]
        back = [(0.15 * math.cos(i * math.pi / 12), 0.1 * math.sin(i * math.pi / 12)) for i in range(13)]
        arm = [(0.4 + 0.05 * math.cos(i * math.tau / 12), 0.05 * math.sin(i * math.tau / 12)) for i in range(12)]
        holed = ring[:22]
        self.assertTrue(surrounds(loop(square), 0.0))
        self.assertTrue(surrounds(loop(ring), 0.0))
        self.assertTrue(surrounds(loop(holed, closed=False), 0.0))
        self.assertFalse(surrounds(loop(back, closed=False), 0.0))
        self.assertFalse(surrounds(loop(arm), 0.0))
        self.assertFalse(surrounds(loop(arm) + loop([(-x, y) for x, y in arm]), 0.0))
        self.assertFalse(surrounds([], 0.0))

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

    def test_tape_goes_around_the_outside_of_a_crease(self):
        crease = [(0, 0), (4, 0), (4, 3), (2, .5), (0, 3)]
        self.assertAlmostEqual(tape_length(crease), 14.0)

    def test_estimate_body_measurements_invalid_inputs(self):
        scene = MockScene()
        self.assertIsNone(estimate_body_measurements(None, scene))
        empty_mesh = MockMesh([], [])
        self.assertIsNone(estimate_body_measurements(MockBody(empty_mesh), scene))


if __name__ == '__main__':
    unittest.main()
