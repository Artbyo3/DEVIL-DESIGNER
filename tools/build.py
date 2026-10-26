"""Create an installable Blender extension archive from the fresh source."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import tomllib

root = Path(__file__).resolve().parents[1]
source = root / 'devil_designer'
manifest = tomllib.loads((source/'blender_manifest.toml').read_text(encoding='utf-8'))
output = root / 'build' / f"{manifest['id']}-{manifest['version']}.zip"
output.parent.mkdir(exist_ok=True)
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
    for file in sorted(source.rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix in {'.py','.toml','.md','.txt','.json','.svg','.png'}:
            archive.write(file,file.relative_to(source).as_posix())
    for name in ('README.md','LICENSE','SPEC.md'):
        archive.write(root/name,name)
print(output)
