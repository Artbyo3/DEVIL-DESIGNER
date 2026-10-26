from pathlib import Path
import sys
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
