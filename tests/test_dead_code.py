import unittest
from pathlib import Path
from tools.check_dead_code import check_dead_code, find_dead_code


class DeadCodeTests(unittest.TestCase):
    def test_package_has_no_dead_code_or_unused_imports(self):
        root = Path(__file__).resolve().parents[1]
        self.assertGreater(check_dead_code(root), 0)

    def test_detector_clean_on_current_codebase(self):
        root = Path(__file__).resolve().parents[1]
        violations = find_dead_code(root)
        self.assertEqual(violations, [])
