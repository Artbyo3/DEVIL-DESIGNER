import struct
import unittest
import zlib

from tools.check_public import inspect_payload, inspect_text


def png_chunk(chunk_type, data):
    return struct.pack('>I', len(data)) + chunk_type + data + struct.pack('>I', zlib.crc32(chunk_type + data))


def icon_png(metadata=b''):
    header = struct.pack('>IIBBBBB', 64, 64, 8, 6, 0, 0, 0)
    pixels = zlib.compress(bytes(64 * (1 + 64 * 4)))
    return b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', header) + metadata + png_chunk(b'IDAT', pixels) + png_chunk(b'IEND', b'')


class PublicationTests(unittest.TestCase):
    def test_sourced_icons_are_permitted(self):
        errors = []
        inspect_payload('devil_designer/assets/icons/SELECT.png', icon_png(), errors)
        self.assertEqual(errors, [])

    def test_image_metadata_is_rejected(self):
        errors = []
        inspect_payload('devil_designer/assets/icons/SELECT.png', icon_png(png_chunk(b'tEXt', b'Author\x00local identity')), errors)
        self.assertTrue(any('metadata' in error for error in errors))

    def test_unexpected_binary_is_rejected(self):
        errors = []
        inspect_payload('old-preview.png', icon_png(), errors)
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
