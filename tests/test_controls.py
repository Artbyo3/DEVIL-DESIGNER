import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from devil_designer.canvas import Layout, Rect, clamp_window
from devil_designer.controls import SETTINGS, Inspector, BodyMenu, TABS
from devil_designer.icons import icon_geometry, icon_spans


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
                     'PIN', 'DART', 'UNDO', 'REDO', 'LIBRARY', 'GARMENT', 'FULL', 'CLOSE'):
            self.assertIsNotNone(icon_spans(name), name)

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
    def test_simple_workspace_has_three_primary_actions(self):
        layout = Layout(1400, 900)
        for key in ('RECTANGLE', 'SEW', 'SIMULATE'):
            self.assertIn(key, layout.buttons)
            self.assertTrue(layout.workflow.contains(layout.buttons[key][0].x, layout.buttons[key][0].y))
        for key in ('FREE_SEW', 'BUILD', 'RESET', 'KEEP', 'VIEW_3D'):
            self.assertNotIn(key, layout.buttons)
        self.assertIn('MORE_TOOLS', layout.buttons)

    def test_pause_remains_available_during_drawing_and_confirmation(self):
        for state in ({'pending': True}, {'confirmation': True}):
            layout = Layout(1000, 700, playing=True, **state)
            self.assertIn('STOP', layout.buttons)

    def test_workflow_layout_has_no_canvas_or_tool_overlap(self):
        for width, height, scale in ((620, 440, 1), (1600, 900, 1), (2400, 1350, 1.5)):
            for stage in ('DRAFT', 'SEW', 'ARRANGE', 'SIMULATE', 'LIBRARY'):
                layout = Layout(width, height, scale, settings=True, stage=stage)
                self.assertGreaterEqual(layout.ruler_left.x, layout.rail.x + layout.rail.w)
                self.assertLessEqual(layout.ruler_top.y + layout.ruler_top.h, layout.workflow.y)
                for rect in layout.starters:
                    self.assertTrue(layout.canvas.contains(rect.x, rect.y))
                    self.assertTrue(layout.canvas.contains(rect.x + rect.w, rect.y + rect.h))
                for name, (rect, label) in layout.buttons.items():
                    self.assertEqual(layout.button(rect.x + rect.w / 2, rect.y + rect.h / 2), name)

    def test_every_tool_and_transport_is_available_in_every_workspace(self):
        from devil_designer.canvas import ALL_TOOLS
        for stage in ('DRAFT', 'SEW', 'ARRANGE', 'SIMULATE', 'LIBRARY'):
            layout = Layout(1000, 700, stage=stage, advanced=True)
            for key in [tool[0] for tool in ALL_TOOLS] + ['SIMULATE', 'KEEP', 'RESET', 'BUILD', 'VIEW_3D']:
                self.assertIn(key, layout.buttons)
            self.assertNotIn('STAGE_NEXT', layout.buttons)

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

    def test_moving_window_moves_canvas_and_buttons_equally(self):
        first=Layout(1600,900,position=(500,120,800,600),settings=True)
        moved=Layout(1600,900,position=(350,180,800,600),settings=True)
        self.assertAlmostEqual(moved.canvas.x-first.canvas.x,-150)
        self.assertAlmostEqual(moved.canvas.y-first.canvas.y,60)
        for key in first.buttons:
            a,b=first.buttons[key][0],moved.buttons[key][0]
            self.assertAlmostEqual(b.x-a.x,-150)
            self.assertAlmostEqual(b.y-a.y,60)

    def test_settings_do_not_cover_the_canvas_or_toolbars(self):
        for scale in (1,1.5,2):
            l=Layout(1600*scale,900*scale,scale,settings=True)
            self.assertLessEqual(l.canvas.x+l.canvas.w,l.inspector.x)
            self.assertLessEqual(l.toolbar.x+l.toolbar.w,l.inspector.x)
            self.assertLessEqual(l.workflow.x+l.workflow.w,l.inspector.x)
            for name,(r,_) in l.buttons.items():
                self.assertTrue(l.panel.contains(r.x,r.y),name)
                self.assertLessEqual(r.x+r.w,l.panel.x+l.panel.w,name)

class SettingTests(unittest.TestCase):
    def test_display_units_round_trip(self):
        for key,spec in SETTINGS.items():
            if not hasattr(spec,'low'):continue
            value=(spec.low+spec.high)/2
            if spec.integer: value=round(value)
            self.assertAlmostEqual(spec.parse(spec.format(value)),value,places=5)

    def test_integer_and_range_validation(self):
        for key,value in [('dd_quality','12.5'),('dd_quality','0'),('dd_spacing','0.1'),
                          ('dd_thickness','infinity'),('dd_frames','NaN'),('dd_frames','bad')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                SETTINGS[key].parse(value)

    def test_cm_and_mm_conversions(self):
        self.assertAlmostEqual(SETTINGS['dd_spacing'].parse('2.5'),.025)
        self.assertAlmostEqual(SETTINGS['dd_clearance'].parse('3,5'),.035)
        self.assertAlmostEqual(SETTINGS['dd_weld_distance'].parse('5'),.005)
        self.assertEqual(SETTINGS['dd_thickness'].parse('0'),0)

class InspectorTests(unittest.TestCase):
    def test_search_reaches_every_setting_without_opening_a_section(self):
        for key in SETTINGS:
            inspector = Inspector(Rect(0, 0, 280, 600), 1, 0, [], 'ALL',
                                  context={'query': key, 'sections': []})
            self.assertTrue(any(item.key == key for item in inspector.controls), key)
            self.assertFalse(inspector.tabs)

    def test_search_reaches_every_direct_action(self):
        from devil_designer.controls import DIRECT_ACTIONS
        for key, label in DIRECT_ACTIONS:
            inspector = Inspector(Rect(0, 0, 280, 600), 1, 0, [], 'ALL',
                                  context={'query': key, 'sections': []})
            self.assertTrue(any(item.key == key for item in inspector.controls), key)

    def test_collapsed_sections_retain_clickable_headers(self):
        inspector = Inspector(Rect(0, 0, 280, 600), 1, 0, [], 'ALL', context={'sections': []})
        for item in inspector.controls:
            self.assertEqual(item.kind, 'fold')
            self.assertEqual(inspector.hit((item.rect.x + 4, item.rect.y + 10)), ('SECTION', item.key))

    def test_readable_display_keeps_precise_edit_value(self):
        setting = SETTINGS['dd_width']
        value = .30000001192092896
        self.assertEqual(setting.display(value), '30')
        self.assertAlmostEqual(setting.parse(setting.format(value)), value, places=14)

    def test_every_setting_reachable_by_scrolling(self):
        panel=Rect(600,80,248,300)
        seen=set()
        for tab in TABS:
            maximum=Inspector(panel,1,0,[],tab).max_scroll
            for scroll in range(0,int(maximum)+50,20):
                inspector=Inspector(panel,1,scroll,[],tab)
                for control in inspector.controls:
                    if control.kind in {'number','text'} and inspector.content.y<control.value_rect.y+10<inspector.content.y+inspector.content.h:
                        seen.add(control.key)
                        self.assertEqual(inspector.hit((control.value_rect.x+2,control.value_rect.y+10)),('EDIT',control.key))
        self.assertEqual(seen,set(SETTINGS))

    def test_scroll_limits_and_thumb(self):
        r=Rect(100,50,248,400)
        first,last=Inspector(r,1,-100,[]),Inspector(r,1,1e8,[])
        self.assertEqual(first.scroll,0)
        self.assertEqual(last.scroll,last.max_scroll)
        self.assertGreater(first.thumb.y,last.thumb.y)
        self.assertGreaterEqual(last.thumb.y,last.scrollbar.y)

    def test_cursor_controls_cover_every_setting_and_section(self):
        seen = set()
        rect = Rect(10, 10, 340, 440)
        for section in TABS:
            inspector = Inspector(rect, 1, 0, [], 'ALL', context={
                'sections': [section], 'details': {section}})
            seen.update(control.key for control in inspector.controls if control.key in SETTINGS)
        self.assertEqual(seen, set(SETTINGS))

    def test_local_actions_precede_optional_sections(self):
        inspector = Inspector(Rect(0, 0, 340, 620), 1, 0, [], 'ALL', context={
            'sections': [], 'local_rows': [('button', 'CURVE', 'Corner / curve')]})
        control = inspector.controls[0]
        self.assertEqual(control.key, 'CURVE')
        self.assertEqual(inspector.hit((control.rect.x + 10, control.rect.y + 10)), ('CURVE', 'CURVE'))

    def test_body_picker_paginates_without_missing_objects(self):
        objects=[SimpleNamespace(name='Body '+str(i)) for i in range(10)]
        panel,anchor=Rect(0,0,900,750),Rect(650,600,210,27)
        found=set()
        for offset in range(5):
            menu=BodyMenu(panel,anchor,1,objects,offset)
            for rect,obj,label in menu.rows:
                self.assertTrue(panel.contains(rect.x,rect.y))
                if obj: found.add(obj.name)
        self.assertEqual(found,{o.name for o in objects})

if __name__=='__main__':
    unittest.main()
