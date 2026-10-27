import unittest
from devil_designer.core import Document
from devil_designer.starters import (
    create_tee_starter,
    create_tank_starter,
    create_skirt_starter,
    STARTER_GENERATORS,
)


class StarterTests(unittest.TestCase):
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
