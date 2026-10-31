from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys

root = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(root))
from tools.workspace import extension_archive
from tools.check_comments import check_repository
from tools.check_dead_code import check_dead_code, check_import_integrity


EXCLUDE_PATTERNS = ('assets/icons/*.png', 'assets/icons/*.svg')


def build_extension():
    check_repository(root)
    check_import_integrity(root)
    check_dead_code(root)
    source = root / 'devil_designer'
    output = extension_archive()
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for file in sorted(source.rglob('*')):
            rel = file.relative_to(source)
            if file.is_file() and '__pycache__' not in file.parts and not any(rel.match(pattern) for pattern in EXCLUDE_PATTERNS) and file.suffix in {'.py','.toml','.md','.txt','.json','.svg','.png'}:
                archive.write(file,rel.as_posix())
        for name in ('README.md','LICENSE','SPEC.md'):
            archive.write(root/name,name)
    print(output)
    return output


if __name__ == '__main__':
    build_extension()
