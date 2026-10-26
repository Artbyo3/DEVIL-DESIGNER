from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys

root = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(root))
from tools.workspace import extension_archive
from tools.check_comments import check_repository


def build_extension():
    check_repository(root)
    source = root / 'devil_designer'
    output = extension_archive()
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for file in sorted(source.rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix in {'.py','.toml','.md','.txt','.json','.svg','.png'}:
                archive.write(file,file.relative_to(source).as_posix())
        for name in ('README.md','LICENSE','SPEC.md'):
            archive.write(root/name,name)
    print(output)
    return output


if __name__ == '__main__':
    build_extension()
