from pathlib import Path
from contextlib import nullcontext
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import dev, workspace


class ScratchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=workspace.prepare_scratch())
        self.root = Path(self.temporary.name).resolve()
        self.scratch = self.root / 'scratch'
        self.settings = patch.multiple(workspace, ROOT=self.root, SCRATCH=self.scratch, DIST=self.root / 'dist')
        self.settings.start()

    def tearDown(self):
        self.settings.stop()
        self.temporary.cleanup()

    def linked_directory(self, path, target):
        try:
            path.symlink_to(target, target_is_directory=True)
        except OSError:
            path.mkdir()
            original = workspace.is_link
            return patch.object(workspace, 'is_link', side_effect=lambda candidate: candidate == path or original(candidate))
        return nullcontext()

    def test_clean_is_idempotent_when_missing(self):
        self.assertEqual(workspace.clean_scratch(), 0)
        self.assertFalse(self.scratch.exists())

    def test_cleanup_removes_nested_artifacts_but_preserves_deliverables_and_source(self):
        workspace.prepare_scratch()
        nested = self.scratch / 'reports'
        nested.mkdir()
        (nested / 'test.blend').write_bytes(b'demo')
        (self.scratch / 'screenshot.png').write_bytes(b'image')
        source = self.root / 'source.py'
        source.write_text('important = True', encoding='utf-8')
        archive = self.root / 'dist' / 'extension.zip'
        archive.parent.mkdir()
        archive.write_bytes(b'installable')
        self.assertEqual(workspace.clean_scratch(), 2)
        self.assertFalse(self.scratch.exists())
        self.assertTrue(source.exists())
        self.assertEqual(archive.read_bytes(), b'installable')

    def test_cleanup_refuses_a_different_target(self):
        source = self.root / 'source'
        source.mkdir()
        with patch.object(workspace, 'SCRATCH', source):
            with self.assertRaises(ValueError):
                workspace.clean_scratch()
        self.assertTrue(source.is_dir())

    def test_cleanup_refuses_a_file_as_scratch(self):
        self.scratch.write_text('not disposable', encoding='utf-8')
        with self.assertRaises(ValueError):
            workspace.clean_scratch()
        self.assertEqual(self.scratch.read_text(encoding='utf-8'), 'not disposable')

    def test_cleanup_refuses_nested_links_before_deleting_anything(self):
        workspace.prepare_scratch()
        artifact = self.scratch / 'report.json'
        artifact.write_text('{}', encoding='utf-8')
        outside = self.root / 'source'
        outside.mkdir()
        protected = outside / 'important.py'
        protected.write_text('important = True', encoding='utf-8')
        with self.linked_directory(self.scratch / 'linked', outside):
            with self.assertRaises(ValueError):
                workspace.clean_scratch()
        self.assertTrue(protected.exists())
        self.assertTrue(artifact.exists())

    def test_cleanup_refuses_linked_scratch_root(self):
        outside = self.root / 'source'
        outside.mkdir()
        protected = outside / 'important.py'
        protected.write_text('important = True', encoding='utf-8')
        with self.linked_directory(self.scratch, outside):
            with self.assertRaises(ValueError):
                workspace.clean_scratch()
        self.assertTrue(protected.exists())

    def test_windows_reparse_attribute_is_detected_without_symlink_privileges(self):
        with patch.object(Path, 'is_symlink', return_value=False), patch.object(Path, 'lstat', return_value=SimpleNamespace(st_file_attributes=0x400)):
            self.assertTrue(workspace.is_link(self.root / 'junction'))

    def test_archive_location_uses_manifest_version_and_is_not_scratch(self):
        source = self.root / 'devil_designer'
        source.mkdir()
        (source / 'blender_manifest.toml').write_text('id = "extension"\nversion = "1.2.3"\n', encoding='utf-8')
        self.assertEqual(workspace.extension_archive(), self.root / 'dist' / 'extension-1.2.3.zip')

    def test_developer_scripts_do_not_write_to_legacy_build_directory(self):
        project_root = Path(__file__).resolve().parents[1]
        for directory in ('tests', 'tools'):
            for source in (project_root / directory).glob('*.py'):
                text = source.read_text(encoding='utf-8')
                self.assertNotRegex(text, r"ROOT\s*/\s*['\"]build['\"]", str(source.relative_to(project_root)))

    def test_cleanup_reports_locked_files_without_removing_the_directory(self):
        workspace.prepare_scratch()
        artifact = self.scratch / 'preview.log'
        artifact.write_text('preview', encoding='utf-8')
        with patch.object(Path, 'unlink', side_effect=PermissionError('locked')):
            with self.assertRaisesRegex(OSError, 'close its owner'):
                workspace.clean_scratch()
        self.assertTrue(artifact.exists())

    def test_successful_runner_cleans_scratch(self):
        workspace.prepare_scratch()
        (self.scratch / 'report.json').write_text('{}', encoding='utf-8')
        with patch.object(dev, 'do_quick_tests', return_value=True), patch('builtins.print'):
            self.assertEqual(dev.main(['--quick']), 0)
        self.assertFalse(self.scratch.exists())

    def test_failed_runner_preserves_diagnostics(self):
        workspace.prepare_scratch()
        report = self.scratch / 'report.json'
        report.write_text('{}', encoding='utf-8')
        with patch.object(dev, 'do_quick_tests', return_value=False), patch('builtins.print'):
            self.assertEqual(dev.main(['--quick']), 1)
        self.assertTrue(report.exists())

    def test_keep_scratch_retains_successful_run_artifacts(self):
        with patch.object(dev, 'do_quick_tests', return_value=True), patch('builtins.print'):
            self.assertEqual(dev.main(['--quick', '--keep-scratch']), 0)
        self.assertTrue(self.scratch.exists())

    def test_explicit_clean_does_not_run_tests_or_build(self):
        workspace.prepare_scratch()
        with patch.object(dev, 'do_tests') as tests, patch.object(dev, 'do_build') as build, patch('builtins.print'):
            self.assertEqual(dev.main(['--clean']), 0)
        tests.assert_not_called()
        build.assert_not_called()
        self.assertFalse(self.scratch.exists())

    def test_runner_reports_cleanup_failure_and_retains_diagnostics(self):
        with patch.object(dev, 'do_quick_tests', return_value=True), patch.object(dev, 'clean_scratch', side_effect=PermissionError('locked')), patch('builtins.print'):
            self.assertEqual(dev.main(['--quick']), 1)
        self.assertTrue(self.scratch.exists())

    def test_combined_run_cleans_only_after_build_finishes(self):
        report = self.scratch / 'test-report.json'
        archive = self.root / 'dist' / 'extension.zip'

        def tests():
            report.write_text('{}', encoding='utf-8')
            return True

        def build():
            self.assertTrue(report.exists())
            archive.parent.mkdir()
            archive.write_bytes(b'installable')
            return True

        with patch.object(dev, 'do_tests', side_effect=tests), patch.object(dev, 'do_build', side_effect=build), patch('builtins.print'):
            self.assertEqual(dev.main(['--test', '--build']), 0)
        self.assertFalse(self.scratch.exists())
        self.assertEqual(archive.read_bytes(), b'installable')
