import ast
import hashlib
import unittest
from pathlib import Path


class ClothIntegrityTests(unittest.TestCase):
    def test_original_cloth_setup_collision_and_reset_are_unchanged(self):
        source=(Path(__file__).resolve().parents[1]/'devil_designer'/'garment.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        expected={'compile_garment':'ebb09a306f3d5bfc7cf6406e71a35f31ee90f1f473f72e16f0b25cbc35ff0907',
                  'ensure_collision':'90e3c90bb45b093c83704320ab573978a797914b3da08a1990b16f4114a0c9e8',
                  'reset':'4b6e15c5578b6969e4c86ac78e9ea1999e62dc448e870dd17abe92eee4ab89be'}
        actual={node.name:hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()
                for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in expected}
        self.assertEqual(actual,expected)
