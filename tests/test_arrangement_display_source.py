import ast
from pathlib import Path
import unittest


class ArrangementDisplayShaderTests(unittest.TestCase):
    def test_embedded_shader_sources_have_no_comments(self):
        source=Path(__file__).resolve().parents[1]/'devil_designer'/'arrangement_controls.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        shaders=[node.args[0].value for node in ast.walk(tree)
                 if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                 and node.func.attr in {'vertex_source','fragment_source'}]
        self.assertEqual(len(shaders),2)
        for shader in shaders:
            for delimiter in ('//','/*','*/'):
                self.assertNotIn(delimiter,shader)
