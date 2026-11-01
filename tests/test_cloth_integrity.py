import ast
import hashlib
import unittest
from pathlib import Path


class ClothIntegrityTests(unittest.TestCase):
    def test_original_cloth_setup_collision_and_reset_are_unchanged(self):
        source=(Path(__file__).resolve().parents[1]/'devil_designer'/'garment.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        expected={'compile_garment':'8535786a5cd667b4264fa38e4df10b85be309358f5ef47d245c8dfadefd29c3f',
                  'ensure_collision':'90e3c90bb45b093c83704320ab573978a797914b3da08a1990b16f4114a0c9e8',
                  'reset':'4b6e15c5578b6969e4c86ac78e9ea1999e62dc448e870dd17abe92eee4ab89be'}
        actual={}
        for node in tree.body:
            if not isinstance(node,ast.FunctionDef) or node.name not in expected:
                continue
            segment=ast.get_source_segment(source,node)
            if node.name=='compile_garment':
                inspection_hook='    plan=boundary_plan(doc,scene.dd_spacing)\n    springs,inspection=resolve_sewing(maps,plan)\n'
                self.assertEqual(segment.count(inspection_hook),1)
                segment=segment.replace(inspection_hook,"    springs=set()\n    plan=boundary_plan(doc,scene.dd_spacing)\n    def index_of(edge,fraction):\n        values=maps[edge.pattern][edge.start]\n        t,index=min(values,key=lambda value:abs(value[0]-fraction))\n        if abs(t-fraction)>1e-6:raise ValueError('Sewing samples changed. Rebuild the panels.')\n        return index\n    for _,pairs in plan.seam_pairs:\n        for (edge_a,t_a),(edge_b,t_b) in pairs:\n            a,b=index_of(edge_a,t_a),index_of(edge_b,t_b)\n            if a!=b:springs.add(tuple(sorted((a,b))))\n",1)
                metadata_hook="    obj['dd_sewing_inspection'] = json.dumps(inspection,separators=(',',':'))\n"
                self.assertEqual(segment.count(metadata_hook),1)
                segment=segment.replace(metadata_hook,'',1)
                state_hook='    from . import piece_states\n    piece_states.update_display(context,doc)\n    if piece_states.required(doc):\n        return piece_states.compile_run(context,doc)\n'
                self.assertEqual(segment.count(state_hook),1)
                segment=segment.replace(state_hook,'',1)
                hook='    ensure_collision(scene)\n    layering.prepare_colliders(context)\n'
                self.assertEqual(segment.count(hook),1)
                segment=segment.replace(hook,'    ensure_collision(scene)\n',1)
                shrink_hook='    if any(seam.shrink for seam in doc.seams):\n        seam_shrink.apply(doc,obj,cloth,maps,plan)\n'
                self.assertEqual(segment.count(shrink_hook),1)
                segment=segment.replace(shrink_hook,'',1)
                scoped="(.001 if any(seam.shrink for seam in doc.seams) or any(feature.get('type') == 'FOLD' for pattern in doc.patterns for feature in pattern.features) else .003)/metres_per_unit(scene)"
                self.assertEqual(segment.count(scoped),1)
                segment=segment.replace(scoped,'.003/metres_per_unit(scene)',1)
            actual[node.name]=hashlib.sha256(segment.encode()).hexdigest()
        self.assertEqual(actual,expected)
