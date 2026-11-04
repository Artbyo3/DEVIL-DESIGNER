import unittest
import json
from pathlib import Path
from devil_designer.canvas import Layout, Rect, clamp_window
from devil_designer.controls import SETTINGS
from devil_designer.icons import icon_geometry, icon_spans
from devil_designer.ui_system import VIEWPORT_LEVELS, viewport_level


class IconTests(unittest.TestCase):
    def test_public_icons_are_sourced_and_bounded(self):
        geometry = icon_geometry()
        sources = json.loads((Path(__file__).resolve().parents[1] / 'devil_designer' / 'assets' / 'icons' / 'sources.json').read_text())
        self.assertEqual(set(geometry), set(sources))
        for name, spans in geometry.items():
            self.assertTrue(spans, name)
            self.assertEqual(len(sources[name]['sha256']), 64)
            for column, row, width, level in spans:
                self.assertTrue(0 <= column < column + width <= 64, name)
                self.assertTrue(0 <= row < 64 and 1 <= level <= 8, name)
        for name in ('SELECT', 'POLYGON', 'RECTANGLE', 'ELLIPSE', 'INTERNAL', 'SEW',
                     'PIN', 'DART', 'UNDO', 'REDO', 'LIBRARY', 'GARMENT', 'CLOSE'):
            self.assertIsNotNone(icon_spans(name), name)

    def test_viewport_level_undoes_the_measured_dark_lift(self):
        for sent, shown in VIEWPORT_LEVELS:
            self.assertAlmostEqual(viewport_level(shown / 255), sent / 255)

    def test_icon_data_is_cached(self):
        self.assertIs(icon_geometry(), icon_geometry())

    def test_packaging_excludes_artwork_sources(self):
        root = Path(__file__).resolve().parents[1]
        manifest = (root / 'devil_designer' / 'blender_manifest.toml').read_text(encoding='utf-8')
        self.assertIn('"assets/icons/*.png"', manifest)
        self.assertIn('"assets/icons/*.svg"', manifest)
        archive_path = root / 'dist' / 'devil_designer-0.11.0.zip'
        if archive_path.exists():
            from zipfile import ZipFile
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
            self.assertIn('assets/icons/geometry.json', names)
            self.assertIn('assets/icons/sources.json', names)
            self.assertFalse(any(name.startswith('assets/icons/') and (name.endswith('.png') or name.endswith('.svg')) for name in names))


class WindowTests(unittest.TestCase):
    def test_drag_clamps_every_edge_to_viewport(self):
        available=Rect(40,60,1200,700)
        for x,y in [(-10000,-10000),(10000,10000),(500,200)]:
            r=clamp_window((x,y,600,400),available,1)
            self.assertGreaterEqual(r.x,available.x)
            self.assertGreaterEqual(r.y,available.y)
            self.assertLessEqual(r.x+r.w,available.x+available.w)
            self.assertLessEqual(r.y+r.h,available.y+available.h)

    def test_oversized_saved_window_recovers_on_smaller_display(self):
        l=Layout(800,600,position=(1800,900,1500,1200),top=52)
        self.assertLessEqual(l.panel.x+l.panel.w,800)
        self.assertLessEqual(l.panel.y+l.panel.h,548)
        self.assertGreaterEqual(l.panel.y,l.available.y)

    def test_moving_window_moves_panel_equally(self):
        first=Layout(1600,900,position=(500,120,800,600))
        moved=Layout(1600,900,position=(350,180,800,600))
        self.assertAlmostEqual(moved.panel.x-first.panel.x,-150)
        self.assertAlmostEqual(moved.panel.y-first.panel.y,60)

class SettingTests(unittest.TestCase):
    def test_display_units_round_trip(self):
        for key,spec in SETTINGS.items():
            if not hasattr(spec,'low'):continue
            value=(spec.low+spec.high)/2
            self.assertAlmostEqual(spec.parse(spec.format(value)),value,places=5)

    def test_range_validation(self):
        for key,value in [('dd_point_x','20000'),('dd_segment_length','0'),('dd_weld_distance','infinity'),
                          ('dd_segment_length','NaN'),('dd_point_y','bad')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                SETTINGS[key].parse(value)

    def test_cm_and_mm_conversions(self):
        self.assertAlmostEqual(SETTINGS['dd_segment_length'].parse('2.5'),.025)
        self.assertAlmostEqual(SETTINGS['dd_point_x'].parse('3,5'),.035)
        self.assertAlmostEqual(SETTINGS['dd_weld_distance'].parse('5'),.005)

    def test_readable_display_keeps_precise_edit_value(self):
        setting = SETTINGS['dd_segment_length']
        value = .30000001192092896
        self.assertEqual(setting.display(value), '30')
        self.assertAlmostEqual(setting.parse(setting.format(value)), value, places=14)


if __name__ == '__main__':
    unittest.main()
