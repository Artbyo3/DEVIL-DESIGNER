import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import urllib.request


def rasterize_dat(content):
    if len(content) <= 8 or content[:4] != b'VCO\x00' or (len(content) - 8) % 18:
        raise ValueError('Invalid Blender toolbar icon geometry.')
    if content[4:8] != bytes((255, 255, 0, 0)):
        raise ValueError('Unsupported Blender toolbar icon coordinate frame.')
    from PIL import Image, ImageDraw
    n = (len(content) - 8) // 18
    coords = content[8:8 + 6 * n]
    cols = content[8 + 6 * n:]
    scale = 4
    size = 256 * scale
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for t in range(n):
        x0, y0 = coords[6 * t] * scale, (255 - coords[6 * t + 1]) * scale
        x1, y1 = coords[6 * t + 2] * scale, (255 - coords[6 * t + 3]) * scale
        x2, y2 = coords[6 * t + 4] * scale, (255 - coords[6 * t + 5]) * scale
        alpha = cols[12 * t + 3]
        draw.polygon([(x0, y0), (x1, y1), (x2, y2)], fill=(255, 255, 255, alpha))
    return img.resize((64, 64), Image.Resampling.LANCZOS)


def fetch_dat(revision, filename):
    path = 'release/datafiles/icons/' + filename
    response = json.loads(subprocess.check_output(['gh', 'api', f'repos/blender/blender/contents/{path}?ref={revision}'], text=True))
    content = base64.b64decode(response['content'])
    if content.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
        pointer = dict(line.split(' ', 1) for line in content.decode('ascii').splitlines())
        algorithm, expected_hash = pointer['oid'].split(':', 1)
        if algorithm != 'sha256':
            raise ValueError('Unsupported toolbar icon LFS hash.')
        payload = json.dumps({'operation': 'download', 'transfers': ['basic'], 'objects': [{'oid': expected_hash, 'size': int(pointer['size'])}]}).encode()
        request = urllib.request.Request('https://projects.blender.org/blender/blender.git/info/lfs/objects/batch', data=payload, headers={'Accept': 'application/vnd.git-lfs+json', 'Content-Type': 'application/vnd.git-lfs+json', 'User-Agent': 'devil-designer-icon-preparer'})
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        action = result['objects'][0]['actions']['download']
        request = urllib.request.Request(action['href'], headers=action.get('header', {}))
        with urllib.request.urlopen(request, timeout=30) as download:
            content = download.read()
        if len(content) != int(pointer['size']) or hashlib.sha256(content).hexdigest() != expected_hash:
            raise ValueError('Blender toolbar icon does not match its pinned LFS object.')
    return content


def rasterize_svg(resvg_py, content):
    from PIL import Image
    b = resvg_py.svg_to_bytes(svg_string=content.decode(), width=64, height=64)
    im = Image.open(io.BytesIO(b)).convert('RGBA')
    canvas = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    canvas.paste(im, ((64 - im.width) // 2, (64 - im.height) // 2))
    return canvas


def make_spans(canvas):
    alpha = canvas.getchannel('A')
    spans = []
    for row in range(64):
        column = 0
        while column < 64:
            level = round(alpha.getpixel((column, row)) / 255 * 8)
            end = column + 1
            while end < 64 and round(alpha.getpixel((end, row)) / 255 * 8) == level:
                end += 1
            if level:
                spans.append([column, 63 - row, end - column, level])
            column = end
    return spans


def prepare():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scratch' / 'icon_vendor'))
    import resvg_py
    destination = root / 'devil_designer' / 'assets' / 'icons'
    revision = 'e13b728c6880d3084d9d57c30031ed5df8b39dee'
    geometry = json.loads((destination / 'geometry.json').read_text(encoding='utf-8'))
    sources = json.loads((destination / 'sources.json').read_text(encoding='utf-8'))
    svg_mappings = {
        'UNDO': 'loop_back', 'REDO': 'loop_forwards',
        'LIBRARY': 'asset_manager', 'GRID': 'asset_manager', 'CLOSE': 'x', 'PLAY': 'play', 'PAUSE': 'pause',
        'FIT': 'zoom_selected', 'SAVE': 'file_tick', 'CHEVRON': 'tria_up',
        'DISCLOSURE': 'disclosure_tri_right', 'EXPAND': 'fullscreen_enter',
        'DOWN': 'tria_down', 'SETTINGS': 'settings', 'CHECK': 'checkmark', 'PIN': 'pinned',
        'SNAP_ON': 'snap_on', 'SNAP_OFF': 'snap_off',
        'HIDE_OFF': 'hide_off', 'HIDE_ON': 'hide_on'
    }
    dat_mappings = {
        'SELECT': 'ops.generic.select.dat',
        'RECTANGLE': 'ops.gpencil.primitive_box.dat',
        'ELLIPSE': 'ops.gpencil.primitive_circle.dat',
        'POLYGON': 'ops.gpencil.primitive_polyline.dat',
        'INTERNAL': 'ops.curve.draw.dat',
        'KNIFE': 'ops.mesh.knife_tool.dat',
        'RULER': 'ops.view3d.ruler.dat'
    }
    for key, filename in svg_mappings.items():
        path = 'release/datafiles/icons_svg/' + filename + '.svg'
        response = json.loads(subprocess.check_output(['gh', 'api', f'repos/blender/blender/contents/{path}?ref={revision}'], text=True))
        content = base64.b64decode(response['content'])
        canvas = rasterize_svg(resvg_py, content)
        canvas.save(destination / (key.lower() + '.png'))
        geometry[key] = make_spans(canvas)
        sources[key] = dict(collection='Blender built-in icons', icon=filename.upper(),
                            url=f'https://raw.githubusercontent.com/blender/blender/{revision}/{path}',
                            sha256=hashlib.sha256(content).hexdigest(), license='GPL-2.0-or-later')

    for key, filename in dat_mappings.items():
        content = fetch_dat(revision, filename)
        canvas = rasterize_dat(content)
        canvas.save(destination / (key.lower() + '.png'))
        geometry[key] = make_spans(canvas)
        sources[key] = dict(collection='Blender built-in icons', icon=filename.upper().replace('.DAT', ''),
                            url=f'https://raw.githubusercontent.com/blender/blender/{revision}/release/datafiles/icons/{filename}',
                            sha256=hashlib.sha256(content).hexdigest(), license='GPL-2.0-or-later')

    license_path = 'doc/license/GPL-license.txt'
    response = json.loads(subprocess.check_output(['gh', 'api', f'repos/blender/blender/contents/{license_path}?ref={revision}'], text=True))
    (destination / 'BLENDER-LICENSE.txt').write_bytes(base64.b64decode(response['content']))
    (destination / 'geometry.json').write_text(json.dumps(geometry, separators=(',', ':')), encoding='utf-8')
    (destination / 'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    print('Prepared', len(svg_mappings) + len(dat_mappings), 'stock Blender icon glyphs at', revision)


if __name__ == '__main__':
    prepare()
