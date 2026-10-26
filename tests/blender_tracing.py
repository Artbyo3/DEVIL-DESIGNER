import math
import sys
import tempfile
from pathlib import Path

import bpy

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from devil_designer import tracing
from tools.workspace import prepare_scratch


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


tracing.register()
tracing.register()
scene = bpy.context.scene
check(all(hasattr(scene, name) for name in tracing.PROPERTIES), 'all tracing scene properties register')
check(math.isclose(scene.dd_trace_length, 0.1, rel_tol=1e-6), 'measured distance defaults to ten centimeters')

with tempfile.TemporaryDirectory(prefix='tracing-', dir=prepare_scratch()) as directory:
    image_path = str(Path(directory) / 'fixture.png')
    blend_path = str(Path(directory) / 'fixture.blend')
    fixture = bpy.data.images.new('Tracing fixture', width=8, height=4, alpha=True)
    fixture.generated_color = (0.8, 0.2, 0.1, 0.5)
    fixture.filepath_raw = image_path
    fixture.file_format = 'PNG'
    fixture.save()
    bpy.data.images.remove(fixture)
    result = bpy.ops.devil.load_trace_image(filepath=image_path)
    check(result == {'FINISHED'}, 'file browser operator loads a generated still image')
    check(scene.dd_trace_path == image_path and scene.dd_trace_visible, 'image path and visibility are stored')
    scene.dd_trace_width = 2
    scene.dd_trace_x = -1
    scene.dd_trace_y = 3
    scene.dd_trace_opacity = 0.6
    scene.dd_trace_length = 0.25
    scene.unit_settings.scale_length = 0.01
    check(tracing.reference_corners(scene) == ((-1, 3), (1, 3), (1, 4), (-1, 4)), 'fit corners preserve image aspect in canvas meters')
    check(math.isclose(tracing.calibrate(scene, (0, 3), (0, 3.5)), 1), 'measured calibration ignores Blender display unit scaling')
    check(math.isclose(scene.dd_trace_x, -0.5), 'calibration keeps first picked endpoint fixed')
    scene.dd_trace_visible = False
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    tracing._images.clear()
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    check(scene.dd_trace_path == image_path and not scene.dd_trace_visible, 'path and visibility survive reopening the blend file')
    check(math.isclose(scene.dd_trace_width, 1) and math.isclose(scene.dd_trace_x, -0.5) and math.isclose(scene.dd_trace_y, 3), 'size and position survive reopening')
    check(math.isclose(scene.dd_trace_opacity, 0.6, rel_tol=1e-6) and math.isclose(scene.dd_trace_length, 0.25), 'opacity and measured distance survive reopening')
    check(tracing.load_image(scene.dd_trace_path).size[:] == (8, 4), 'image is restored from path with an empty runtime cache')
    scene.dd_trace_path = str(Path(directory) / 'missing.png')
    check(not tracing.reference_corners(scene) and 'not found' in scene.dd_trace_error, 'missing reference presents a recoverable artist message')
    for image in list(bpy.data.images):
        if image.filepath == image_path:
            bpy.data.images.remove(image)
    bpy.ops.wm.read_factory_settings(use_empty=True)

tracing.unregister()
tracing.unregister()
check(not any(hasattr(bpy.types.Scene, name) for name in tracing.PROPERTIES), 'unregister removes every tracing property')
check(not tracing._images and not tracing._classes, 'unregister releases runtime caches')
tracing.register()
tracing.unregister()
print('TRACING TESTS PASSED', flush=True)
