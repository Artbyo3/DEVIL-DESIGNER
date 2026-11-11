import unittest
from devil_designer.core import Document
from devil_designer.starters import (
    ARM_CLEARANCE,
    create_tee_starter,
    create_tank_starter,
    create_skirt_starter,
    STARTER_GENERATORS,
)


class StarterTests(unittest.TestCase):
    def test_tee_sleeves_and_neck_scale_down_for_small_avatars(self):
        measurements = dict(chest=60.0, waist=48.0, hip=70.0, torso_length=25.0, shoulder_width=28.0, arm_length=40.0)
        adult = create_tee_starter(dict(measurements, height=150.0)).patterns[0].outline()
        small = create_tee_starter(dict(measurements, height=100.0, waist_y=.93)).patterns[0].outline()
        width = lambda points: max(x for x, _ in points) - min(x for x, _ in points)
        self.assertLess(width(small), width(adult))

    def test_short_avatar_tee_stops_at_the_neck_and_its_sleeves_clear_the_arm(self):
        measurements = dict(chest=48.5, waist=44.5, hip=61.0, torso_length=16.0, shoulder_width=26.0, arm_length=31.5,
                            height=107.5, waist_y=.703, neck_y=.865, arm_bottom_y=.782, arm_top_y=.827)
        points = create_tee_starter(measurements).patterns[0].points
        armpit, sleeve_bottom, sleeve_top = points[2][1], points[3][1], points[4][1]
        self.assertLessEqual(max(y for _, y in points), .865)
        self.assertGreaterEqual(sleeve_top, .827 + ARM_CLEARANCE - 1e-9)
        self.assertLessEqual(sleeve_bottom, .782 - ARM_CLEARANCE + 1e-9)
        self.assertLessEqual(armpit, sleeve_bottom)

    def test_body_landmarks_that_already_clear_the_tee_leave_it_unchanged(self):
        measurements = dict(chest=60.0, waist=47.0, hip=73.0, torso_length=17.5, shoulder_width=29.0, arm_length=50.5,
                            height=151.0, waist_y=1.047)
        plain = create_tee_starter(measurements).patterns[0].points
        landmarks = create_tee_starter(dict(measurements, neck_y=1.40, arm_bottom_y=1.18, arm_top_y=1.22)).patterns[0].points
        self.assertEqual(plain, landmarks)

    def test_starter_registry_completeness(self):
        self.assertIn('STARTER_TEE', STARTER_GENERATORS)
        self.assertIn('STARTER_TANK', STARTER_GENERATORS)
        self.assertIn('STARTER_SKIRT', STARTER_GENERATORS)
        for key in ('STARTER_TEE', 'STARTER_TANK', 'STARTER_SKIRT'):
            label, gen, mode = STARTER_GENERATORS[key]
            self.assertTrue(callable(gen))
            self.assertIn(mode, ('BODICE', 'SKIRT', 'SLEEVES'))

    def test_tee_starter_structure_and_seams(self):
        doc = create_tee_starter(None)
        self.assertEqual(len(doc.patterns), 2)
        names = [p.name for p in doc.patterns]
        self.assertIn('Tee front', names)
        self.assertIn('Tee back', names)
        doc.validate()
        doc.validate_seams()
        self.assertGreater(len(doc.seams), 0)
        for seam in doc.seams:
            a, b, diff, pct = doc.seam_stats(seam)
            self.assertLess(diff, 0.005)

    def test_tank_starter_structure_and_seams(self):
        doc = create_tank_starter(None)
        self.assertEqual(len(doc.patterns), 2)
        names = [p.name for p in doc.patterns]
        self.assertIn('Tank front', names)
        self.assertIn('Tank back', names)
        doc.validate()
        doc.validate_seams()
        self.assertEqual(len(doc.seams), 4)
        for seam in doc.seams:
            a, b, diff, pct = doc.seam_stats(seam)
            self.assertLess(diff, 0.005)

    def test_skirt_starter_structure_and_seams(self):
        doc = create_skirt_starter(None)
        self.assertEqual(len(doc.patterns), 2)
        names = [p.name for p in doc.patterns]
        self.assertIn('Skirt front', names)
        self.assertIn('Skirt back', names)
        doc.validate()
        doc.validate_seams()
        self.assertEqual(len(doc.seams), 2)
        for seam in doc.seams:
            a, b, diff, pct = doc.seam_stats(seam)
            self.assertLess(diff, 0.005)

    def test_skirt_panels_hang_level_and_clear_the_hips(self):
        bodies = (None, dict(waist=38.0, hip=64.5, height=110.5, waist_y=.815, hip_y=.601),
                  dict(waist=80.0, hip=45.0, height=154.0, waist_y=1.01, hip_y=.75))
        for measurements in bodies:
            doc = create_skirt_starter(measurements)
            for pattern in doc.patterns:
                hem, side, waist, other_side = (doc.edge_length(doc.edge(pattern.id, index)) for index in range(4))
                self.assertAlmostEqual(side, other_side, places=6)
                self.assertAlmostEqual(side, 0.48, delta=.001)
                hem_curve = doc.edge_curve(doc.edge(pattern.id, 0))
                side_curve = doc.edge_curve(doc.edge(pattern.id, 1))
                hem_end = (hem_curve[3][0] - hem_curve[2][0], hem_curve[3][1] - hem_curve[2][1])
                side_start = (side_curve[1][0] - side_curve[0][0], side_curve[1][1] - side_curve[0][1])
                self.assertAlmostEqual(hem_end[0] * side_start[0] + hem_end[1] * side_start[1], 0.0, places=6)
            body = measurements or dict(waist=80.0, hip=96.0, waist_y=1.054, hip_y=.854)
            waist_girth = 2 * doc.edge_length(doc.edge(doc.patterns[0].id, 2)) * 100
            hem_girth = 2 * doc.edge_length(doc.edge(doc.patterns[0].id, 0)) * 100
            hip_girth = waist_girth + (hem_girth - waist_girth) * (body['waist_y'] - body['hip_y']) / .48
            self.assertGreaterEqual(hip_girth, max(body['hip'], body['waist']) + 7.9)

    def test_side_seams_start_at_matching_height(self):
        for gen in (create_tee_starter, create_tank_starter, create_skirt_starter):
            doc = gen(None)
            seam_a, seam_b = doc.seams[0], doc.seams[1]
            p_a0 = doc.chain_position(seam_a.chain_a, 0.0)
            p_b0 = doc.chain_position(seam_b.chain_a, 0.0)
            pt_a = doc.edge_point(p_a0[0], p_a0[1])
            pt_b = doc.edge_point(p_b0[0], p_b0[1])
            self.assertAlmostEqual(pt_a[1], pt_b[1], places=3)

    def test_custom_measurements_scale_patterns(self):
        m_small = {'chest': 80.0, 'waist': 64.0, 'hip': 84.0, 'torso_length': 36.0, 'shoulder_width': 38.0}
        m_large = {'chest': 110.0, 'waist': 95.0, 'hip': 115.0, 'torso_length': 46.0, 'shoulder_width': 50.0}
        doc_small = create_tank_starter(m_small)
        doc_large = create_tank_starter(m_large)
        front_small = doc_small.patterns[0]
        front_large = doc_large.patterns[0]
        w_small = max(p[0] for p in front_small.points) - min(p[0] for p in front_small.points)
        w_large = max(p[0] for p in front_large.points) - min(p[0] for p in front_large.points)
        self.assertGreater(w_large, w_small)

    def test_starters_roundtrip_json_serialization(self):
        for gen in (create_tee_starter, create_tank_starter, create_skirt_starter):
            doc = gen(None)
            serialized = doc.dumps()
            restored = Document.loads(serialized)
            self.assertEqual(len(doc.patterns), len(restored.patterns))
            self.assertEqual(len(doc.seams), len(restored.seams))

    def test_placement_height_matches_2d_reference(self):
        doc = create_skirt_starter(None)
        p = doc.patterns[0]
        cy = (min(v[1] for v in p.points) + max(v[1] for v in p.points)) / 2
        ref_y = 0.0
        low_z = 0.0
        unit = 1.0
        z_3d = low_z + (cy - ref_y) / unit
        self.assertAlmostEqual(z_3d, cy, places=4)
        self.assertGreater(z_3d, 0.40)
        self.assertLess(z_3d, 1.20)


if __name__ == '__main__':
    unittest.main()
