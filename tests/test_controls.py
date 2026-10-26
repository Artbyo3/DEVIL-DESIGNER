import unittest
from types import SimpleNamespace
from devil_designer.canvas import Layout, Rect, clamp_window
from devil_designer.controls import SETTINGS, Inspector, BodyMenu

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

    def test_moving_window_moves_canvas_and_buttons_equally(self):
        first=Layout(1600,900,position=(500,120,800,600),settings=True)
        moved=Layout(1600,900,position=(350,180,800,600),settings=True)
        self.assertEqual((moved.canvas.x-first.canvas.x,moved.canvas.y-first.canvas.y),(-150,60))
        for key in first.buttons:
            a,b=first.buttons[key][0],moved.buttons[key][0]
            self.assertEqual((b.x-a.x,b.y-a.y),(-150,60))

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
    def test_every_setting_reachable_by_scrolling(self):
        panel=Rect(600,80,248,300)
        seen=set()
        maximum=Inspector(panel,1,0,[]).max_scroll
        for scroll in range(0,int(maximum)+50,20):
            inspector=Inspector(panel,1,scroll,[])
            for control in inspector.controls:
                if control.kind=='number' and panel.contains(control.value_rect.x+2,control.value_rect.y+10):
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
