"""Run: blender --background --factory-startup --python tests/blender_smoke.py"""
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import devil_designer
from devil_designer.core import Session, Document

def check(condition,message):
    if not condition:
        raise AssertionError(message)
    print('PASS:',message)

devil_designer.register()
check(bpy.ops.devil_designer.pattern_editor.get_rna_type().identifier == 'DEVIL_DESIGNER_OT_pattern_editor','operator registration')
check(hasattr(bpy.types.Scene,'dd_document'),'scene storage registration')
scene = bpy.context.scene
original_objects = set(scene.objects.keys())
s = Session()
s.add([(0,0),(.3,0),(.3,.4),(0,.4)])
s.add([(.5,0),(.9,0),(.9,.4),(.7,.1),(.5,.4)])
scene.dd_document = s.document.dumps()
expected = scene.dd_document
check(len(Document.loads(scene.dd_document).patterns)==2,'pattern document in Blender')
output = ROOT / 'build' / 'smoke.blend'
output.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
bpy.ops.wm.open_mainfile(filepath=str(output))
check(bpy.context.scene.dd_document==expected,'patterns survive saving and reopening a .blend')
check(set(bpy.context.scene.objects.keys())==original_objects,'drafting does not change 3D objects')
devil_designer.unregister()
check(not hasattr(bpy.types.Scene,'dd_document'),'unregister cleanup')
print('ALL BLENDER SMOKE CHECKS PASSED',bpy.app.version_string)
