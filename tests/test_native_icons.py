import base64
import hashlib
import io
import json
import unittest
from unittest.mock import patch
from tools.prepare_blender_icons import fetch_dat, rasterize_dat


class NativeIconSourceTests(unittest.TestCase):
    def test_pinned_lfs_download_returns_verified_artwork(self):
        content = b'VCO\x00\xff\xff\x00\x00' + bytes((20, 20, 240, 20, 20, 240)) + bytes((255, 255, 255, 255)) * 3
        checksum = hashlib.sha256(content).hexdigest()
        pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{checksum}\nsize {len(content)}\n'.encode()
        metadata = json.dumps({'content': base64.b64encode(pointer).decode()})
        batch = json.dumps({'objects': [{'actions': {'download': {'href': 'https://example.invalid/icon'}}}]}).encode()
        with patch('tools.prepare_blender_icons.subprocess.check_output', return_value=metadata), patch(
                'tools.prepare_blender_icons.urllib.request.urlopen', side_effect=[io.BytesIO(batch), io.BytesIO(content)]):
            self.assertEqual(fetch_dat('pinned-revision', 'ops.generic.select.dat'), content)

    def test_pinned_lfs_download_rejects_corrupt_artwork(self):
        checksum = hashlib.sha256(b'expected').hexdigest()
        pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{checksum}\nsize 8\n'.encode()
        metadata = json.dumps({'content': base64.b64encode(pointer).decode()})
        batch = json.dumps({'objects': [{'actions': {'download': {'href': 'https://example.invalid/icon'}}}]}).encode()
        with patch('tools.prepare_blender_icons.subprocess.check_output', return_value=metadata), patch(
                'tools.prepare_blender_icons.urllib.request.urlopen', side_effect=[io.BytesIO(batch), io.BytesIO(b'corrupt!')]):
            with self.assertRaisesRegex(ValueError, 'pinned LFS object'):
                fetch_dat('pinned-revision', 'ops.generic.select.dat')

    def test_lfs_pointer_and_truncated_geometry_cannot_be_rasterized(self):
        for content in (b'version https://git-lfs.github.com/spec/v1\n', b'VCO\x00', b'VCO\x00\xff\xff\x00\x00junk'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                rasterize_dat(content)


if __name__ == '__main__':
    unittest.main()
