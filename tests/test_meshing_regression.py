import hashlib
import json
import unittest
from devil_designer.core import Document, Session
from devil_designer.meshing import edge_counts
from devil_designer.starters import (
    create_tee_starter,
    create_tank_starter,
    create_skirt_starter,
)

try:
    import bpy
    from devil_designer.meshing import fabric_mesh
except ModuleNotFoundError:
    bpy = None
    fabric_mesh = None

BASELINE = {
    'tee': {
        'Tee front': {
            'n_verts': 967,
            'n_faces': 1801,
            'n_uvs': 5403,
            'sha256': '65b3ff0480a4f17308bfe5be8a2437cc5ffb7795ce642a32c38b30b94c353344',
        },
        'Tee back': {
            'n_verts': 980,
            'n_faces': 1830,
            'n_uvs': 5490,
            'sha256': '4d00762b1d9a76e6acf00d622839c2c1edf3504f5d3cd6a3b4a6510892783369',
        },
    },
    'tank': {
        'Tank front': {
            'n_verts': 687,
            'n_faces': 1272,
            'n_uvs': 3816,
            'sha256': '909b605787cd8fc1060d69fbbf74bb3390da797affa2731fbd9ebb3ce61e8250',
        },
        'Tank back': {
            'n_verts': 720,
            'n_faces': 1341,
            'n_uvs': 4023,
            'sha256': '089f0e23df5521363cbe97f61c188370353b9c6f313213ca82d44aa8e1922f10',
        },
    },
    'skirt': {
        'Skirt front': {
            'n_verts': 788,
            'n_faces': 1471,
            'n_uvs': 4413,
            'sha256': '87926d2309767aecbdffe510854140f6f1400f9297af37c871a194fe187abdd4',
        },
        'Skirt back': {
            'n_verts': 788,
            'n_faces': 1471,
            'n_uvs': 4413,
            'sha256': 'b0f12f17a198a78459df313c26c17df71a9ccc4b62b3dc45dd9ac516c1230cec',
        },
    },
    'ellipse': {
        'Ellipse': {
            'n_verts': 459,
            'n_faces': 796,
            'n_uvs': 2388,
            'sha256': '4b2c06e9564c43edbba7c2420ca55d2786983462b5d20dd76a091c9cc74c6e22',
        },
    },
}


def get_saved_designs():
    designs = {
        'tee': create_tee_starter(None),
        'tank': create_tank_starter(None),
        'skirt': create_skirt_starter(None),
    }
    s = Session()
    s.add_ellipse((0, 0), (0.4, 0.4))
    s.document.patterns[0].name = 'Ellipse'
    designs['ellipse'] = s.document
    return {name: Document.loads(doc.dumps()) for name, doc in designs.items()}


class MeshingRegressionTests(unittest.TestCase):
    def test_saved_designs_structure(self):
        designs = get_saved_designs()
        self.assertEqual(set(designs.keys()), {'tee', 'tank', 'skirt', 'ellipse'})
        for name, doc in designs.items():
            self.assertTrue(doc.patterns)
            for p in doc.patterns:
                self.assertIn(p.name, BASELINE[name])

    @unittest.skipUnless(bpy is not None, 'Requires Blender')
    def test_meshing_output_matches_baseline(self):
        designs = get_saved_designs()
        for name, doc in designs.items():
            counts = edge_counts(doc, 0.02)
            all_points = [pt for p in doc.patterns for pt in p.outline()]
            minx, miny = min(p[0] for p in all_points), min(p[1] for p in all_points)
            extent = max(max(p[0] for p in all_points) - minx, max(p[1] for p in all_points) - miny, 0.001)
            for p in doc.patterns:
                coords, faces, bounds = fabric_mesh(doc, p, 0.02, counts)
                verts_rounded = [(round(x, 6), round(y, 6)) for x, y in coords]
                faces_list = [list(f) for f in faces]
                uvs_rounded = [(round((coords[i][0] - minx) / extent, 6), round((coords[i][1] - miny) / extent, 6)) for f in faces for i in f]
                payload = json.dumps({'verts': verts_rounded, 'faces': faces_list, 'uvs': uvs_rounded}, sort_keys=True)
                h = hashlib.sha256(payload.encode('utf-8')).hexdigest()
                expected = BASELINE[name][p.name]
                self.assertEqual(len(verts_rounded), expected['n_verts'])
                self.assertEqual(len(faces_list), expected['n_faces'])
                self.assertEqual(len(uvs_rounded), expected['n_uvs'])
                self.assertEqual(h, expected['sha256'])
