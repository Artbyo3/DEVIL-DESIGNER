import unittest
from devil_designer.silhouette import project_vertices, torso_alignment

class ProjectionTests(unittest.TestCase):
    def test_body_is_centered_and_grounded_without_resizing(self):
        points=[(8,3,5),(8.5,4,6.8),(9,3.5,5)]
        projected,bounds=project_vertices(points)
        self.assertEqual(projected[0],(-.5,0))
        self.assertEqual(projected[2],(.5,0))
        self.assertAlmostEqual(bounds[1][1],1.8)
        self.assertAlmostEqual(bounds[1][0]-bounds[0][0],1)

    def test_front_back_and_side_views(self):
        points=[(-.3,-.1,0),(.1,.2,1),(.3,.1,1.8)]
        front,_=project_vertices(points,'FRONT')
        back,_=project_vertices(points,'BACK')
        left,_=project_vertices(points,'LEFT')
        right,_=project_vertices(points,'RIGHT')
        for a,b in zip(front,back):
            self.assertAlmostEqual(a[0],-b[0])
            self.assertEqual(a[1],b[1])
        for a,b in zip(left,right):
            self.assertAlmostEqual(a[0],-b[0])
        self.assertNotEqual(front,right)

    def test_projection_preserves_vertices_instead_of_convex_hull(self):
        points=[(-.5,0,0),(0,0,1),(.5,0,0),(.1,0,.1)]
        projected,_=project_vertices(points)
        self.assertEqual(len(projected),4)
        self.assertEqual(projected[-1],(.1,.1))

    def test_empty_and_invalid_geometry(self):
        self.assertEqual(project_vertices([]),([],None))
        for points in [[(0,0,float('inf'))],[(float('nan'),0,1)]]:
            with self.assertRaises(ValueError):
                project_vertices(points)
        with self.assertRaises(ValueError):
            project_vertices([(0,0,0)],'UNKNOWN')

    def test_torso_alignment_uses_real_height(self):
        offset=torso_alignment(((-.4,0),(.4,1.8)),[(0,0),(.4,.5)])
        self.assertAlmostEqual(offset[0],.2)
        self.assertAlmostEqual(offset[1]+1.8*.72,.25)

    def test_no_pattern_alignment_preserves_ground_origin(self):
        self.assertEqual(torso_alignment(((-.5,0),(.5,1.8)),[]),(0,0))

if __name__=='__main__':
    unittest.main()
