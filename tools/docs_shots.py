import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workspace import child_environment, extension_archive, prepare_scratch

BLENDER_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
DOCS = ROOT / 'docs-site' / 'docs'
SHOTS = DOCS / 'assets' / 'images' / 'shots'
OVERVIEW = DOCS / 'assets' / 'images' / 'editor-overview.png'
WIDTHS = {'16:9': 1280, '4:3': 960}
PAD = .12
FRAME = re.compile(r'(<figure class="dd-shot" id="(?P<id>shot-[a-z0-9-]+)"[^\n]*\n)\s*<div class="dd-shot__frame">.*?</div>\n'
                   r'(?P<caption>\s*<figcaption id="(?P=id)-caption">(?P<text>.*?)</figcaption>)', re.S)


def blender(arguments, environment):
    result = subprocess.run([BLENDER_PATH, *arguments], cwd=str(ROOT), capture_output=True, text=True, env=environment)
    if result.returncode != 0:
        print(result.stdout[-4000:])
        print(result.stderr[-4000:])
        raise SystemExit('Blender step failed: ' + ' '.join(arguments[:3]))
    return result


def isolated_environment(work):
    environment = child_environment()
    environment['BLENDER_USER_RESOURCES'] = str(work / 'user')
    return environment


def install(archive, environment):
    blender(['--background', '--factory-startup', '--command', 'extension', 'install-file', '--repo', 'user_default', '--enable', str(archive)], environment)


def capture(work, environment):
    output = work / 'raw'
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    settings = dict(output=str(output), package='bl_ext.user_default.devil_designer', library=str(work / 'library'))
    blender(['--window-geometry', '0', '0', '1600', '900', '--python', str(ROOT / 'tools' / 'docs_shots_blender.py'), '--', json.dumps(settings)], environment)
    return output, json.loads((output / 'records.json').read_text(encoding='utf-8'))


def frame(focus, aspect, size):
    width, height = size
    left, bottom, wide, tall = focus
    ratio = 16 / 9 if aspect == '16:9' else 4 / 3
    wide, tall = wide * (1 + 2 * PAD), tall * (1 + 2 * PAD)
    if wide / max(tall, 1) < ratio:
        wide = tall * ratio
    else:
        tall = wide / ratio
    wide, tall = min(wide, width, height * ratio), min(tall, height, width / ratio)
    centre_x, centre_y = left + focus[2] / 2, bottom + focus[3] / 2
    left = min(max(0, centre_x - wide / 2), width - wide)
    bottom = min(max(0, centre_y - tall / 2), height - tall)
    top = height - (bottom + tall)
    return round(left), round(top), round(left + wide), round(top + tall)


def crop(raw, records):
    SHOTS.mkdir(parents=True, exist_ok=True)
    written = []
    for name, record in records['records'].items():
        if record['aspect'] not in WIDTHS:
            continue
        image = Image.open(raw / (name + '.png')).convert('RGB')
        box = frame(record['focus'], record['aspect'], image.size)
        piece = image.crop(box)
        target_width = min(WIDTHS[record['aspect']], piece.width)
        piece = piece.resize((target_width, round(target_width * piece.height / piece.width)), Image.LANCZOS)
        bare = Image.frombytes('RGB', piece.size, piece.tobytes())
        target = OVERVIEW if name == 'dd-overview' else SHOTS / (name + '.png')
        bare.save(target, optimize=True)
        written.append(target)
    return written


def wire():
    missing = []
    for page in sorted(DOCS.glob('*.md')):
        text = page.read_text(encoding='utf-8')

        def replace(match):
            identity = match.group('id')
            if not (SHOTS / (identity + '.png')).exists():
                missing.append(identity)
                return match.group(0)
            alt = re.sub(r'<[^>]+>', '', match.group('text')).replace('"', '&quot;')
            return (match.group(1) + f'  <div class="dd-shot__frame"><img src="assets/images/shots/{identity}.png" alt="{alt}" loading="lazy" /></div>\n'
                    + match.group('caption'))
        updated = FRAME.sub(replace, text)
        if updated != text:
            page.write_text(updated, encoding='utf-8')
    return missing


def main():
    parser = argparse.ArgumentParser(description='Capture the documentation screenshots from the current build in an isolated Blender profile.')
    parser.add_argument('--archive', type=Path, default=None)
    parser.add_argument('--crop-only', action='store_true', help='Reuse the last raw captures in scratch.')
    arguments = parser.parse_args()
    work = prepare_scratch() / 'docs_shots'
    if arguments.crop_only:
        raw = work / 'raw'
        records = json.loads((raw / 'records.json').read_text(encoding='utf-8'))
        written = crop(raw, records)
        missing = wire()
        print(f'Wrote {len(written)} images; figures still without a capture: {missing}')
        return 0 if not missing else 1
    archive = arguments.archive or extension_archive()
    if not archive.exists():
        raise SystemExit('Build the extension first with python tools/build.py.')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    environment = isolated_environment(work)
    install(archive, environment)
    raw, records = capture(work, environment)
    if records['errors']:
        print(json.dumps(records['errors'], indent=1))
    written = crop(raw, records)
    missing = wire()
    print(f'Wrote {len(written)} images; figures still without a capture: {missing}')
    return 0 if not records['errors'] and not missing else 1


if __name__ == '__main__':
    raise SystemExit(main())
