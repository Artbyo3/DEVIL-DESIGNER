import copy
import unittest
from types import SimpleNamespace
from devil_designer.tack_binding import topology_signature,validate_binding


class TackBindingSchemaTests(unittest.TestCase):
    def setUp(self):
        self.binding=dict(version=1,vertices=[0,1,2],weights=[.2,.3,.5],topology='a'*64,avatar='b'*32)

    def test_valid_binding(self):
        self.assertIs(validate_binding(self.binding),self.binding)

    def test_invalid_bindings(self):
        for key,values in dict(version=[None,2,True],vertices=[[0,0,1],[0,1],[-1,1,2],[True,1,2]],weights=[[0,0,0],[-.1,.6,.5],[float('nan'),0,1],[True,0,0]],topology=['bad',None],avatar=['private name',None]).items():
            for value in values:
                with self.subTest(key=key,value=value):
                    binding=copy.deepcopy(self.binding)
                    binding[key]=value
                    with self.assertRaises(ValueError):
                        validate_binding(binding)

    def test_topology_signature_ignores_pose(self):
        mesh=SimpleNamespace(vertices=[(0,0,0),(1,0,0),(0,1,0)],polygons=[SimpleNamespace(vertices=(0,1,2))])
        initial=topology_signature(mesh)
        mesh.vertices=[(3,0,7),(4,0,7),(3,5,7)]
        self.assertEqual(initial,topology_signature(mesh))
        mesh.polygons[0].vertices=(0,2,1)
        self.assertNotEqual(initial,topology_signature(mesh))


if __name__=='__main__':
    unittest.main()
