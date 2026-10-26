import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools.dev import run_cmd


class DeveloperRunnerTests(unittest.TestCase):
    def test_blender_gui_failure_is_not_a_successful_test(self):
        result = SimpleNamespace(returncode=0, stdout='GUI TEST FAILED: assertion', stderr='')
        with patch('tools.dev.subprocess.run', return_value=result), patch('builtins.print'):
            self.assertFalse(run_cmd(['blender', 'tools/run_blender_gui.py']))

    def test_blender_gui_timeout_is_not_a_successful_test(self):
        result = SimpleNamespace(returncode=0, stdout='GUI TEST TIMED OUT waiting for report', stderr='')
        with patch('tools.dev.subprocess.run', return_value=result), patch('builtins.print'):
            self.assertFalse(run_cmd(['blender', 'tools/run_blender_gui.py']))
