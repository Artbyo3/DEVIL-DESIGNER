import json
import math
import unittest
from devil_designer.core import Document, Session, area, triangulate, validate_polygon, contains
from devil_designer.canvas import Layout, View, grid_step

SQUARE = [(0,0),(.3,0),(.3,.4),(0,.4)]
CONCAVE = [(0,0),(.4,0),(.4,.4),(.2,.1),(0,.4)]

class GeometryTests(unittest.TestCase):
    def test_concave_fill_in_both_directions(self):
        for pts in (CONCAVE,list(reversed(CONCAVE))):
            triangles = triangulate(pts)
            self.assertEqual(len(triangles),len(pts)-2)
            self.assertAlmostEqual(sum(abs(area([pts[i] for i in t])) for t in triangles),abs(area(pts)))
            for t in triangles:
                center = tuple(sum(pts[i][a] for i in t)/3 for a in (0,1))
                self.assertTrue(contains(center,pts))

    def test_collinear_corners_fill(self):
        pts = [(0,0),(.15,0),(.3,0),(.3,.4),(0,.4)]
        self.assertAlmostEqual(sum(abs(area([pts[i] for i in t])) for t in triangulate(pts)),.12)

    def test_reject_invalid_polygons(self):
        invalid = [[(0,0),(1,1),(0,1),(1,0)],[(0,0),(1,0),(0,0)],
                   [(0,0),(1,0),(1,0),(0,1)],[(0,0),(2,0),(1,0),(1,1),(0,1)],
                   [(0,0),(math.inf,0),(0,1)],[(0,0),(math.nan,1),(1,0)],
                   [(0,0),(1,0),(2,0)],[(0,0),(1,0),(1,1),(.5,0),(0,1)]]
        for points in invalid:
            with self.subTest(points=points), self.assertRaises(ValueError):
                validate_polygon(points)

    def test_concave_hit_test(self):
        self.assertTrue(contains((.05,.05),CONCAVE))
        self.assertFalse(contains((.2,.3),CONCAVE))
        self.assertTrue(contains((0,0),SQUARE))

class EditingTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.add(SQUARE)

    def test_save_round_trip_preserves_corner_identity(self):
        d = Document.loads(self.s.document.dumps())
        self.assertEqual(d.dumps(),self.s.document.dumps())
        self.assertEqual(d.patterns[0].points,SQUARE)

    def test_duplicate_allocates_all_new_ids(self):
        before = self.s.document.patterns[0]
        self.s.duplicate()
        after = self.s.document.patterns[1]
        self.assertNotEqual(before.id,after.id)
        self.assertFalse({v.id for v in before.vertices}&{v.id for v in after.vertices})
        self.s.move([(x+.2,y) for x,y in after.points])
        self.assertEqual(self.s.document.patterns[0].points,SQUARE)

    def test_invalid_drag_does_not_mutate_or_add_history(self):
        original = self.s.document.dumps()
        count = len(self.s.undo_stack)
        with self.assertRaises(ValueError):
            self.s.move([(0,0),(1,1),(0,1),(1,0)])
        self.assertEqual(self.s.document.dumps(),original)
        self.assertEqual(len(self.s.undo_stack),count)

    def test_minimum_corners_and_delete_rollback(self):
        self.s.corner = 0
        self.s.delete()
        self.assertEqual(len(self.s.document.patterns[0].vertices),3)
        self.s.corner = 0
        original = self.s.document.dumps()
        with self.assertRaises(ValueError):
            self.s.delete()
        self.assertEqual(self.s.document.dumps(),original)
        self.s.history()
        self.assertEqual(self.s.document.patterns[0].points,SQUARE)

    def test_undo_redo_and_branch_history(self):
        self.s.move([(x+.2,y) for x,y in SQUARE])
        moved = self.s.document.dumps()
        self.s.history()
        self.assertEqual(self.s.document.patterns[0].points,SQUARE)
        self.s.history(True)
        self.assertEqual(self.s.document.dumps(),moved)
        self.s.history()
        self.s.duplicate()
        self.assertFalse(self.s.history(True))

    def test_noop_movement_keeps_history(self):
        count = len(self.s.undo_stack)
        self.assertFalse(self.s.move(SQUARE))
        self.assertEqual(len(self.s.undo_stack),count)

    def test_delete_piece_can_be_undone(self):
        self.s.delete()
        self.assertEqual(len(self.s.document.patterns),0)
        self.s.history()
        self.assertEqual(self.s.document.patterns[0].points,SQUARE)

    def test_corrupt_document_rejected(self):
        good = json.loads(self.s.document.dumps())
        bad = json.loads(json.dumps(good))
        bad['patterns'][0]['vertices'][0]['id'] = bad['patterns'][0]['id']
        cases = ['{',json.dumps({'version':99,'patterns':[]}),json.dumps(bad),
                 json.dumps({'version':1,'patterns':[{}]}),'null']
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Document.loads(value)

class CanvasTests(unittest.TestCase):
    def test_zoom_keeps_cursor_world_coordinate(self):
        v = View()
        rect = Layout(1600,900,left=40,right=300).canvas
        cursor = (rect.x+100,rect.y+170)
        initial = v.world(cursor,rect)
        for factor in [1.15,.3,100000,.000001]:
            v.zoom_at(cursor,rect,factor)
            self.assertAlmostEqual(v.world(cursor,rect)[0],initial[0])
            self.assertAlmostEqual(v.world(cursor,rect)[1],initial[1])

    def test_screen_world_round_trip_after_pan(self):
        v = View()
        c = Layout(1200,800).canvas
        v.pan(53,-72)
        for p in SQUARE:
            q = v.world(v.screen(p,c),c)
            self.assertAlmostEqual(q[0],p[0])
            self.assertAlmostEqual(q[1],p[1])

    def test_layout_respects_native_panels_and_leaves_scene_visible(self):
        for scale in (1,1.5,2):
            l = Layout(1600*scale,900*scale,scale,left=40*scale,right=300*scale)
            self.assertGreater(l.panel.x,40*scale+200*scale)
            self.assertLessEqual(l.panel.x+l.panel.w,1300*scale)
            self.assertLess(l.canvas.y+l.canvas.h,l.toolbar.y)
            for name,(button,_) in l.buttons.items():
                self.assertTrue(l.panel.contains(button.x,button.y),name)
                self.assertLessEqual(button.x+button.w,l.panel.x+l.panel.w)
                self.assertEqual(l.button(button.x+button.w/2,button.y+button.h/2),name)

    def test_native_header_shelf_and_small_viewports(self):
        for width in (640,800,1100,1600):
            l = Layout(width,700,left=56,right=280,top=52,bottom=60)
            self.assertLessEqual(l.panel.y+l.panel.h,700-52)
            self.assertGreaterEqual(l.panel.y,60)
            for name,(r,_) in l.buttons.items():
                self.assertLessEqual(r.x+r.w,l.panel.x+l.panel.w,name)
                self.assertGreaterEqual(r.x,l.panel.x,name)

    def test_fit_and_grid_are_finite(self):
        v = View()
        c = Layout(1200,800).canvas
        v.fit(CONCAVE,c)
        for point in CONCAVE:
            self.assertTrue(c.contains(*v.screen(point,c)))
        for zoom in (20,800,80000):
            self.assertGreaterEqual(grid_step(zoom)*zoom,55-1e-8)

if __name__=='__main__':
    unittest.main()
