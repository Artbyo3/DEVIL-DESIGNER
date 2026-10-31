import hashlib
import struct
import unittest
import zlib
from unittest.mock import patch

from tools.check_public import ALIAS, EMAIL, ROOT, inspect_commit_metadata, inspect_payload, inspect_text


def png_chunk(chunk_type, data):
    return struct.pack('>I', len(data)) + chunk_type + data + struct.pack('>I', zlib.crc32(chunk_type + data))


def icon_png(metadata=b''):
    header = struct.pack('>IIBBBBB', 64, 64, 8, 6, 0, 0, 0)
    pixels = zlib.compress(bytes(64 * (1 + 64 * 4)))
    return b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', header) + metadata + png_chunk(b'IDAT', pixels) + png_chunk(b'IEND', b'')


class PublicationTests(unittest.TestCase):
    def test_public_author_and_github_merge_committer_are_permitted(self):
        errors = []
        record = '\0'.join(['a' * 40, ALIAS, EMAIL, 'GitHub', 'noreply' + '@' + 'github.com'])
        self.assertEqual(inspect_commit_metadata(record, errors), 0)
        self.assertEqual(errors, [])

    def test_accepted_author_is_metadata_only(self):
        author = ('Accepted author', 'accepted' + '@' + 'example.org')
        fingerprint = hashlib.sha256('\0'.join(author).encode('utf-8')).hexdigest()
        record = '\0'.join(['a' * 40, *author, ALIAS, EMAIL])
        errors = []
        with patch('tools.check_public.APPROVED_AUTHOR_FINGERPRINTS', {fingerprint}):
            self.assertEqual(inspect_commit_metadata(record, errors), 1)
            self.assertEqual(errors, [])
            inspect_text('fixture', author[1], errors)
        self.assertTrue(errors)

    def test_unknown_author_is_rejected_without_exposing_identity(self):
        errors = []
        record = '\0'.join(['b' * 40, 'Other author', 'other' + '@' + 'example.org', 'GitHub', 'noreply' + '@' + 'github.com'])
        inspect_commit_metadata(record, errors)
        self.assertEqual(errors, ['commit bbbbbbbbbbbb: unapproved author identity'])

    def test_github_identity_is_not_allowed_as_an_author(self):
        errors = []
        record = '\0'.join(['a' * 40, 'GitHub', 'noreply' + '@' + 'github.com', ALIAS, EMAIL])
        inspect_commit_metadata(record, errors)
        self.assertEqual(errors, ['commit aaaaaaaaaaaa: unapproved author identity'])

    def test_author_approval_does_not_allow_unknown_committer(self):
        author = ('Accepted author', 'accepted' + '@' + 'example.org')
        fingerprint = hashlib.sha256('\0'.join(author).encode('utf-8')).hexdigest()
        errors = []
        record = '\0'.join(['a' * 40, *author, *author])
        with patch('tools.check_public.APPROVED_AUTHOR_FINGERPRINTS', {fingerprint}):
            inspect_commit_metadata(record, errors)
        self.assertEqual(errors, ['commit aaaaaaaaaaaa: unapproved committer identity'])

    def test_malformed_metadata_is_rejected(self):
        for record in ('invalid', '\0'.join(['invalid', ALIAS, EMAIL, ALIAS, EMAIL])):
            with self.subTest(record=record):
                errors = []
                inspect_commit_metadata(record, errors)
                self.assertEqual(errors, ['commit metadata: malformed identity record'])

    def test_sourced_icons_are_permitted(self):
        errors = []
        inspect_payload('devil_designer/assets/icons/SELECT.png', icon_png(), errors)
        self.assertEqual(errors, [])

    def test_image_metadata_is_rejected(self):
        errors = []
        inspect_payload('devil_designer/assets/icons/SELECT.png', icon_png(png_chunk(b'tEXt', b'Author\x00local identity')), errors)
        self.assertTrue(any('metadata' in error for error in errors))

    def test_docs_site_placeholder_is_permitted(self):
        errors = []
        placeholder = (ROOT / 'docs-site/docs/assets/images/video-placeholder.png').read_bytes()
        inspect_payload('docs-site/docs/assets/images/video-placeholder.png', placeholder, errors)
        self.assertEqual(errors, [])

    def test_docs_site_image_metadata_is_rejected(self):
        errors = []
        inspect_payload('docs-site/docs/assets/images/video-placeholder.png', icon_png(png_chunk(b'tEXt', b'Author\x00local identity')), errors)
        self.assertTrue(any('metadata' in error for error in errors))

    def test_unexpected_binary_is_rejected(self):
        for path in ('old-preview.png', 'devil_designer/preview.png', 'docs/video-placeholder.png'):
            with self.subTest(path=path):
                errors = []
                inspect_payload(path, icon_png(), errors)
                self.assertTrue(errors)

    def test_truncated_icon_is_rejected(self):
        errors = []
        inspect_payload('devil_designer/assets/icons/SELECT.png', icon_png()[:-1], errors)
        self.assertTrue(errors)

    def test_private_paths_and_credentials_are_rejected(self):
        for value in ('C:' + '\\Users\\private-account\\document', 'gh' + 'p_' + 'A' * 36, 'private' + '@' + 'example.org'):
            with self.subTest(value_type=type(value).__name__):
                errors = []
                inspect_text('fixture', value, errors)
                self.assertTrue(errors)

    def test_public_automation_identity_is_permitted(self):
        errors = []
        inspect_text('fixture', 't3code' + '@' + 'users.noreply.github.com', errors)
        self.assertEqual(errors, [])
