import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.request
import zipfile
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scratch' / 'icon_vendor'))
import resvg_py


def prepare():
    destination = ROOT / 'devil_designer' / 'assets' / 'icons'
    destination.mkdir(parents=True, exist_ok=True)
    sources = {}
    images = {}
    archive = zipfile.ZipFile(ROOT / 'scratch' / 'kenney_game-icons.zip')
    expansion = zipfile.ZipFile(ROOT / 'scratch' / 'kenney_game-icons-expansion.zip')
    kenney = {'GRID': 'menuGrid', 'CLOSE': 'cross', 'PLAY': 'forward', 'PAUSE': 'pause',
              'FIT': 'zoomDefault', 'MORE': 'barsHorizontal', 'SAVE': 'save',
              'UNDO': 'return', 'CHEVRON': 'up', 'DISCLOSURE': 'arrowRight', 'EXPAND': 'larger',
              'DOWN': 'arrowDown', 'SETTINGS': 'gear', 'CHECK': 'checkmark'}
    for key, filename in kenney.items():
        path = 'PNG/White/2x/' + filename + '.png'
        if path not in archive.namelist():
            path = 'PNG/White/1x/' + filename + '.png'
        content = archive.read(path)
        images[key] = Image.open(io.BytesIO(content)).convert('RGBA')
        sources[key] = {'collection': 'Kenney Game Icons', 'file': path,
                        'sha256': hashlib.sha256(content).hexdigest()}
    for key, filename in {'SELECT': 'pointer', 'POLYGON': 'toolPencil', 'INTERNAL': 'toolBrush'}.items():
        path = 'PNG/White/2x/' + filename + '.png'
        content = expansion.read(path)
        images[key] = Image.open(io.BytesIO(content)).convert('RGBA')
        sources[key] = {'collection': 'Kenney Game Icons Expansion', 'file': path,
                        'sha256': hashlib.sha256(content).hexdigest()}
    for key, repository, filename in [('RECTANGLE', 'mapbox/maki', 'square-stroked'),
                                     ('ELLIPSE', 'mapbox/maki', 'circle-stroked'),
                                     ('DART', 'mapbox/maki', 'triangle-stroked'),
                                     ('GARMENT', 'mapbox/maki', 'clothing-store'),
                                     ('SEW', 'rapideditor/temaki', 'needle_and_spool'),
                                     ('PIN', 'rapideditor/temaki', 'pin')]:
        commit = json.load(urllib.request.urlopen('https://api.github.com/repos/' + repository + '/commits/main'))['sha']
        url = 'https://raw.githubusercontent.com/' + repository + '/' + commit + '/icons/' + filename + '.svg'
        content = urllib.request.urlopen(url).read()
        (destination / (filename + '.svg')).write_bytes(content)
        images[key] = Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=content.decode(), width=96, height=96))).convert('RGBA')
        sources[key] = {'collection': repository, 'url': url, 'sha256': hashlib.sha256(content).hexdigest()}
    images['REDO'] = ImageOps.mirror(images['UNDO'])
    sources['REDO'] = dict(sources['UNDO'], transform='horizontal reflection')
    geometry = {}
    for key, image in images.items():
        image = image.crop(image.getbbox())
        image.thumbnail((56, 56), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (64, 64))
        canvas.paste(image, ((64 - image.width) // 2, (64 - image.height) // 2))
        canvas.save(destination / (key.lower() + '.png'))
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
        geometry[key] = spans
    (destination / 'geometry.json').write_text(json.dumps(geometry, separators=(',', ':')), encoding='utf-8')
    (destination / 'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    (destination / 'KENNEY-LICENSE.txt').write_bytes(archive.read('license.txt'))
    for repository, filename in [('mapbox/maki', 'LICENSE.txt'), ('rapideditor/temaki', 'LICENSE.md')]:
        content = urllib.request.urlopen('https://raw.githubusercontent.com/' + repository + '/main/' + filename).read()
        (destination / (repository.split('/')[1].upper() + '-LICENSE.txt')).write_bytes(content)
    print('Prepared', len(geometry), 'sourced CC0 icons')
    from prepare_blender_icons import prepare as prepare_blender
    prepare_blender()


if __name__ == '__main__':
    prepare()
