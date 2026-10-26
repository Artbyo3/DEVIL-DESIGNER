import os
from pathlib import Path
import stat
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / 'scratch'
DIST = ROOT / 'dist'


def extension_archive():
    manifest = tomllib.loads((ROOT / 'devil_designer' / 'blender_manifest.toml').read_text(encoding='utf-8'))
    return DIST / f"{manifest['id']}-{manifest['version']}.zip"


def is_link(path):
    return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def checked_scratch():
    expected = ROOT.resolve() / 'scratch'
    if SCRATCH.absolute() != expected:
        raise ValueError('Scratch must be the real scratch directory directly inside the repository.')
    try:
        linked = is_link(SCRATCH)
    except FileNotFoundError:
        return expected
    if linked or not SCRATCH.is_dir():
        raise ValueError('Scratch cannot be a linked directory or a file.')
    return expected


def prepare_scratch():
    directory = checked_scratch()
    directory.mkdir(exist_ok=True)
    return directory


def clean_scratch():
    directory = checked_scratch()
    if not directory.exists():
        return 0
    pending = [directory]
    directories = []
    files = []
    while pending:
        current = pending.pop()
        directories.append(current)
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if is_link(path) or not path.resolve().is_relative_to(directory):
                    raise ValueError('Scratch cleanup refuses links and paths outside scratch.')
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                else:
                    files.append(path)
    for path in files:
        try:
            path.unlink()
        except OSError as error:
            raise OSError(f'Cannot remove scratch artifact {path.relative_to(directory)}; close its owner and run --clean again.') from error
    for path in reversed(directories):
        path.rmdir()
    return len(files)
