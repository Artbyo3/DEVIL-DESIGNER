import unittest
from devil_designer.core import Document, Session
from devil_designer.presets import PRESETS, resolve_preset

SQUARE = [(0, 0), (.3, 0), (.3, .4), (0, .4)]


class FabricPresetTests(unittest.TestCase):
    def test_resolve_preset_builtin(self):
        for name, expected in PRESETS.items():
            self.assertEqual(resolve_preset(name), expected)

    def test_resolve_preset_custom(self):
        custom = {'Chiffon': dict(structural=5.0, shear=3.0, bending=0.05, density=0.05)}
        self.assertEqual(resolve_preset('Chiffon', custom), custom['Chiffon'])
        self.assertEqual(resolve_preset('COTTON', custom), PRESETS['COTTON'])

    def test_document_round_trip_with_custom_presets(self):
        s = Session()
        s.add(SQUARE)
        custom_vals = dict(structural=30.0, shear=18.0, bending=0.8, density=0.28)
        s.set_custom_preset('Heavy Cotton', custom_vals)
        s.set_document_preset('Heavy Cotton')
        s.set_fabric_override('Heavy Cotton')

        dumps = s.document.dumps()
        doc = Document.loads(dumps)

        self.assertEqual(doc.preset, 'Heavy Cotton')
        self.assertEqual(doc.patterns[0].preset, 'Heavy Cotton')
        self.assertTrue(doc.patterns[0].fabric_override)
        self.assertIn('Heavy Cotton', doc.custom_presets)
        self.assertEqual(doc.custom_presets['Heavy Cotton'], custom_vals)

    def test_invalid_custom_preset_rejected(self):
        s = Session()
        with self.assertRaises(ValueError):
            s.set_custom_preset('', dict(structural=10.0, shear=5.0, bending=0.1, density=0.2))
        with self.assertRaises(ValueError):
            s.set_custom_preset('Bad', dict(structural=-1.0, shear=5.0, bending=0.1, density=0.2))
        with self.assertRaises(ValueError):
            s.set_custom_preset('Missing', dict(structural=10.0, shear=5.0, bending=0.1))

    def test_delete_custom_preset(self):
        s = Session()
        s.add(SQUARE)
        custom_vals = dict(structural=40.0, shear=20.0, bending=1.0, density=0.3)
        s.set_custom_preset('Tweed', custom_vals)
        s.set_document_preset('Tweed')
        s.delete_custom_preset('Tweed')
        self.assertEqual(s.document.preset, 'COTTON')
        self.assertNotIn('Tweed', s.document.custom_presets)
        self.assertEqual(s.document.patterns[0].preset, 'COTTON')
        self.assertFalse(s.document.patterns[0].fabric_override)

    def test_calibrated_preset_bounds_and_relationships(self):
        expected_density = {'SILK': 0.07, 'KNIT': 0.17, 'COTTON': 0.14, 'LINEN': 0.19, 'DENIM': 0.40, 'LEATHER': 0.60}
        structural_windows = {
            'SILK': (9.0, 14.0),
            'KNIT': (5.5, 9.0),
            'COTTON': (22.0, 32.0),
            'LINEN': (45.0, 65.0),
            'DENIM': (75.0, 120.0),
            'LEATHER': (110.0, 180.0),
        }
        bending_windows = {
            'SILK': (0.45, 0.85),
            'KNIT': (0.65, 1.15),
            'COTTON': (1.50, 2.50),
            'LINEN': (4.20, 7.00),
            'DENIM': (16.0, 70.0),
            'LEATHER': (35.0, 120.0),
        }
        for name, preset in PRESETS.items():
            self.assertEqual(preset['density'], expected_density[name])
            self.assertEqual(preset['shear'], round(0.5 * preset['structural'], 1))
            st_low, st_high = structural_windows[name]
            self.assertGreaterEqual(preset['structural'], st_low)
            self.assertLessEqual(preset['structural'], st_high)
            b_low, b_high = bending_windows[name]
            self.assertGreaterEqual(preset['bending'], b_low)
            self.assertLessEqual(preset['bending'], b_high)
            self.assertLessEqual(preset['bending'], 120.0)

    def test_custom_preset_above_fifty_bending_round_trip(self):
        s = Session()
        s.add(SQUARE)
        high_bend_vals = dict(structural=180.0, shear=90.0, bending=115.0, density=0.60)
        s.set_custom_preset('Heavy Leather', high_bend_vals)
        s.set_document_preset('Heavy Leather')
        s.set_fabric_override('Heavy Leather')
        dumps = s.document.dumps()
        doc = Document.loads(dumps)
        self.assertEqual(doc.preset, 'Heavy Leather')
        self.assertEqual(doc.patterns[0].preset, 'Heavy Leather')
        self.assertTrue(doc.patterns[0].fabric_override)
        self.assertIn('Heavy Leather', doc.custom_presets)
        self.assertEqual(doc.custom_presets['Heavy Leather']['bending'], 115.0)
        self.assertEqual(doc.custom_presets['Heavy Leather'], high_bend_vals)
