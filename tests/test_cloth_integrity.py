import ast
import hashlib
import unittest
from pathlib import Path


class ClothIntegrityTests(unittest.TestCase):
    def test_original_cloth_setup_collision_and_reset_are_unchanged(self):
        source=Path(__file__).resolve().parents[1]/'devil_designer'/'garment.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        expected={'compile_garment':'5718450cd4c737107ec4f20d0cb9019c2f5725e703127898c6f33da92c66ce57',
                  'ensure_collision':'40dcc90db95c6a6fee4cbb49e6b7d9758c7bdfd372f84f5b44c4cfce6852868d',
                  'reset':'451d4d533d6a242b8951bd06485ad588af0b2cc753229ce09b958aed997babe7'}
        actual={node.name:hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
                for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in expected}
        self.assertEqual(actual,expected)
