import tempfile
import unittest
from pathlib import Path
from tools.check_dead_code import check_dead_code, check_draw_integrity, check_import_integrity, find_dead_code, find_draw_integrity_violations, find_missing_imports


class DeadCodeTests(unittest.TestCase):
    def test_package_has_no_dead_code_or_unused_imports(self):
        root = Path(__file__).resolve().parents[1]
        self.assertGreater(check_dead_code(root), 0)

    def test_detector_clean_on_current_codebase(self):
        root = Path(__file__).resolve().parents[1]
        violations = find_dead_code(root)
        self.assertEqual(violations, [])

    def test_package_import_integrity(self):
        root = Path(__file__).resolve().parents[1]
        self.assertGreater(check_import_integrity(root), 0)
        self.assertEqual(find_missing_imports(root), [])

    def test_package_draw_integrity(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(check_draw_integrity(root), 0)
        self.assertEqual(find_draw_integrity_violations(root), [])

    def test_invalid_draw_attribute_and_key_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / 'devil_designer'
            pkg.mkdir()
            (pkg / 'draw.py').write_text(
                'h_edge = ed.design_hit_edge()\nx = h_edge.edge\npair = pair_for(doc, \"id\")\ny = pair[\"a\"]\n',
                encoding='utf-8'
            )
            violations = find_draw_integrity_violations(Path(tmp))
            self.assertEqual(violations, [
                "draw.py:2: invalid attribute 'edge' on EdgeRef",
                "draw.py:4: invalid key 'a' on linked_pair",
            ])

    def test_missing_import_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / 'devil_designer'
            pkg.mkdir()
            (pkg / 'ui_system.py').write_text('BG_BASE = (0, 0, 0, 1)\n', encoding='utf-8')
            (pkg / 'draw.py').write_text('from .ui_system import BG_BASE, RADIUS_WINDOW\nX = (BG_BASE, RADIUS_WINDOW)\n', encoding='utf-8')
            violations = find_missing_imports(Path(tmp))
            self.assertEqual(violations, ['draw.py:1: missing import RADIUS_WINDOW from ui_system'])
