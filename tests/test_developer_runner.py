import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools.dev import do_action_performance, run_cmd


class DeveloperRunnerTests(unittest.TestCase):
    def test_action_profile_requires_complete_matrix(self):
        with patch('tools.dev.SCRATCH') as scratch, patch('tools.dev.run_cmd', return_value=True), patch('builtins.print'):
            report = scratch.__truediv__.return_value
            report.is_file.return_value = True
            report.read_text.return_value = '{"records":[],"error":"profile interrupted"}'
            self.assertFalse(do_action_performance('baseline'))
            report.read_text.return_value = '{"records":[],"complete":true}'
            self.assertTrue(do_action_performance('baseline'))
            report.is_file.return_value = False
            self.assertFalse(do_action_performance('baseline'))

    def test_blender_gui_failure_is_not_a_successful_test(self):
        result = SimpleNamespace(returncode=0, stdout='GUI TEST FAILED: assertion', stderr='')
        with patch('tools.dev.subprocess.run', return_value=result), patch('builtins.print'):
            self.assertFalse(run_cmd(['blender', 'tools/run_blender_gui.py']))

    def test_child_processes_do_not_create_bytecode_caches(self):
        result = SimpleNamespace(returncode=0, stdout='', stderr='')
        with patch('tools.dev.subprocess.run', return_value=result) as command, patch('builtins.print'):
            self.assertTrue(run_cmd(['python', 'tools/build.py']))
        self.assertEqual(command.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')

    def test_blender_gui_timeout_is_not_a_successful_test(self):
        result = SimpleNamespace(returncode=0, stdout='GUI TEST TIMED OUT waiting for report', stderr='')
        with patch('tools.dev.subprocess.run', return_value=result), patch('builtins.print'):
            self.assertFalse(run_cmd(['blender', 'tools/run_blender_gui.py']))
