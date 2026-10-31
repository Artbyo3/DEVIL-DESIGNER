import ast
import importlib
from pathlib import Path
import pkgutil
import shutil
import sys
from zipfile import ZipFile
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer.core import Session, Document

def check(condition,message):
    if not condition:
        raise AssertionError(message)
    print('PASS:',message)

pkg_dir = ROOT / 'devil_designer'
py_files = sorted(pkg_dir.glob('*.py'))
loaded_modules = {'__init__': devil_designer}
for mod_info in sorted(pkgutil.iter_modules([str(pkg_dir)]), key=lambda m: m.name):
    full_name = f'devil_designer.{mod_info.name}'
    loaded_modules[mod_info.name] = importlib.import_module(full_name)
check(len(loaded_modules) == len(py_files), f'full package import in real Blender ({len(loaded_modules)}/{len(py_files)} modules)')

for pf in py_files:
    tree = ast.parse(pf.read_text(encoding='utf-8-sig'))
    imported_submods = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            target_key = node.module or '__init__'
            target_mod = loaded_modules.get(target_key)
            check(target_mod is not None, f'{pf.name}:{node.lineno} target module {target_key} loaded')
            for alias in node.names:
                if alias.name != '*':
                    check(hasattr(target_mod, alias.name), f'{pf.name}:{node.lineno} {target_key}.{alias.name} exists in real Blender')
                    if alias.name in loaded_modules:
                        imported_submods[alias.asname or alias.name] = loaded_modules[alias.name]

    class ScopeVisitor(ast.NodeVisitor):
        def __init__(self):
            self.scopes = [set()]
        def visit_FunctionDef(self, node):
            params = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
            if node.args.vararg: params.add(node.args.vararg.arg)
            if node.args.kwarg: params.add(node.args.kwarg.arg)
            self.scopes.append(set(params))
            self.generic_visit(node)
            self.scopes.pop()
        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)
        def visit_Assign(self, node):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.scopes[-1].add(t.id)
            self.generic_visit(node)
        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name):
                var_name = node.value.id
                is_local = any(var_name in s for s in self.scopes)
                if not is_local and var_name in imported_submods:
                    mod = imported_submods[var_name]
                    check(hasattr(mod, node.attr),
                          f'{pf.name}:{node.lineno} module {var_name}.{node.attr} exists in real Blender')
            self.generic_visit(node)

    ScopeVisitor().visit(tree)

from tools.build import build_extension
zip_path = build_extension()
check(zip_path.is_file(), f'packaged extension zip exists ({zip_path.name})')
ext_root = ROOT / 'scratch' / 'ext_load_check'
shutil.rmtree(ext_root, ignore_errors=True)
pkg_target = ext_root / 'bl_ext' / 'user_default' / 'devil_designer'
pkg_target.mkdir(parents=True, exist_ok=True)
(ext_root / 'bl_ext' / '__init__.py').write_text('', encoding='utf-8')
(ext_root / 'bl_ext' / 'user_default' / '__init__.py').write_text('', encoding='utf-8')
with ZipFile(zip_path, 'r') as zf:
    zf.extractall(pkg_target)
saved_bl_ext = {k: v for k, v in sys.modules.items() if k == 'bl_ext' or k.startswith('bl_ext.')}
for k in list(saved_bl_ext):
    del sys.modules[k]
sys.path.insert(0, str(ext_root))
try:
    bl_ext_mod = importlib.import_module('bl_ext')
    bl_ext_mod.__path__ = [str(ext_root / 'bl_ext')]
    user_def_mod = importlib.import_module('bl_ext.user_default')
    user_def_mod.__path__ = [str(ext_root / 'bl_ext' / 'user_default')]
    ext_pkg = importlib.import_module('bl_ext.user_default.devil_designer')
    check(Path(ext_pkg.__file__).resolve().is_relative_to(pkg_target.resolve()), 'bl_ext.user_default.devil_designer loaded from packaged zip')
    ext_count = 1
    for mod_info in sorted(pkgutil.iter_modules([str(pkg_target)]), key=lambda m: m.name):
        mod_obj = importlib.import_module(f'bl_ext.user_default.devil_designer.{mod_info.name}')
        check(Path(mod_obj.__file__).resolve().is_relative_to(pkg_target.resolve()), f'bl_ext.user_default.devil_designer.{mod_info.name} loaded from packaged zip')
        ext_count += 1
    check(ext_count == len(py_files), f'packaged zip full load as bl_ext.user_default.devil_designer ({ext_count} modules)')
finally:
    sys.path.remove(str(ext_root))
    for k in [k for k in sys.modules if k == 'bl_ext' or k.startswith('bl_ext.')]:
        del sys.modules[k]
    sys.modules.update(saved_bl_ext)
    shutil.rmtree(ext_root, ignore_errors=True)

devil_designer.register()
check(bpy.ops.devil_designer.pattern_editor.get_rna_type().identifier == 'DEVIL_DESIGNER_OT_pattern_editor','operator registration')
check(hasattr(bpy.types.Scene,'dd_document'),'scene storage registration')
check(not hasattr(bpy.types,'DD_PT_patterns'),'no N-panel registered')
scene = bpy.context.scene
original_objects = set(scene.objects.keys())
s = Session()
s.add([(0,0),(.3,0),(.3,.4),(0,.4)])
s.add([(.5,0),(.9,0),(.9,.4),(.7,.1),(.5,.4)])
scene.dd_document = s.document.dumps()
scene.dd_ui_rect=(140,90,680,500)
scene.dd_ui_settings=False
expected = scene.dd_document
check(len(Document.loads(scene.dd_document).patterns)==2,'pattern document in Blender')
output = ROOT / 'scratch' / 'smoke.blend'
output.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
bpy.ops.wm.open_mainfile(filepath=str(output))
check(bpy.context.scene.dd_document==expected,'patterns survive saving and reopening a .blend')
check(tuple(bpy.context.scene.dd_ui_rect)==(140,90,680,500),'window placement survives save/reopen')
check(not bpy.context.scene.dd_ui_settings,'settings visibility survives save/reopen')
check(set(bpy.context.scene.objects.keys())==original_objects,'drafting does not change 3D objects')
devil_designer.unregister()
check(not hasattr(bpy.types.Scene,'dd_document'),'unregister cleanup')
print('ALL BLENDER SMOKE CHECKS PASSED',bpy.app.version_string)
