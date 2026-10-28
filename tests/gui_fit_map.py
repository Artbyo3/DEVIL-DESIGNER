import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
import bpy
import gpu
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.context.preferences.view.show_splash = False
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import editor, garment


def run():
    passed = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        passed.append(label)

    try:
        devil_designer.register()
        bpy.ops.devil_designer.demo()
        scene = bpy.context.scene
        scene.dd_spacing = .03
        garment.arrange(bpy.context)
        source = garment.compile_garment(bpy.context)
        for frame in range(1, 31):
            scene.frame_set(frame)
            source.evaluated_get(bpy.context.evaluated_depsgraph_get())
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace = editor._active
            workspace.reveal_3d()
            view = area.spaces.active.region_3d
            view.view_location = Vector((.45, 0, 1.25))
            view.view_distance = 1.5
            view.view_rotation = Vector((0, -1, .1)).to_track_quat('Z', 'Y')
            view.view_perspective = 'ORTHO'
            original = (area.spaces.active.shading.type, area.spaces.active.shading.color_type,
                        area.spaces.active.overlay.show_overlays, source.hide_get(), source.hide_render,
                        source.display_type, source.data.as_pointer(), scene.dd_document,
                        tuple((material.as_pointer(), tuple(material.diffuse_color)) for material in source.data.materials))
            original_mesh_count = len(bpy.data.meshes)
            check('TOGGLE_FIT_MAP' in workspace.canvas_layout.buttons, 'F chip is next to S, H and L')
            point = workspace.canvas_layout.buttons['TOGGLE_FIT_MAP'][0]
            event = SimpleNamespace(type='LEFTMOUSE', value='PRESS', mouse_x=region.x + point.x + point.w / 2,
                                    mouse_y=region.y + point.y + point.h / 2, ctrl=False, alt=False, shift=False)
            workspace.handle_event(bpy.context, event)
            check(workspace.fit_overlay.enabled and workspace.fit_overlay.handle is not None, 'dock chip enables a viewport draw handler')
            state = (gpu.state.depth_test_get(), gpu.state.depth_mask_get(), gpu.state.blend_get())
            workspace.fit_overlay.draw()
            check(not workspace.fit_overlay.message, 'native GPU fit map renders a real simulated garment')
            check((gpu.state.depth_test_get(), gpu.state.depth_mask_get(), gpu.state.blend_get()) == state, 'GPU depth and blend states restore exactly')
            workspace.draw_overlay()
            workspace.fit_overlay.legend(workspace.renderer)
            for mode in ('SOLID', 'MATERIAL', 'RENDERED', 'WIREFRAME'):
                area.spaces.active.shading.type = mode
                workspace.fit_overlay.draw()
                check(not workspace.fit_overlay.message, mode + ' display supports the fit map without changing shading')
            area.spaces.active.shading.type = original[0]
            check(len(bpy.data.meshes) == original_mesh_count, 'drawing releases all temporary color meshes')
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
            bpy.ops.screen.screenshot(filepath=str(ROOT / 'scratch' / 'fit-map-viewport.png'))
            workspace.handle_event(bpy.context, SimpleNamespace(type='F', value='PRESS', mouse_x=region.x + 10,
                                   mouse_y=region.y + region.height / 2, ctrl=False, alt=False, shift=False))
            check(not workspace.fit_overlay.enabled and workspace.fit_overlay.handle is None, 'F shortcut removes the handler and disables the overlay')
            actual = (area.spaces.active.shading.type, area.spaces.active.shading.color_type,
                      area.spaces.active.overlay.show_overlays, source.hide_get(), source.hide_render,
                      source.display_type, source.data.as_pointer(), scene.dd_document,
                      tuple((material.as_pointer(), tuple(material.diffuse_color)) for material in source.data.materials))
            check(actual == original, 'toggle off restores the exact original viewport, document, mesh and materials')
            workspace.fit_overlay.toggle()
            workspace.cleanup()
            check(not workspace.fit_overlay.enabled and workspace.fit_overlay.handle is None, 'closing the editor removes the fit handler')
        devil_designer.unregister()
        (ROOT / 'scratch' / 'fit_map-report.json').write_text(json.dumps(dict(passed=passed), indent=2))
    except Exception:
        (ROOT / 'scratch' / 'fit_map-report.json').write_text(json.dumps(dict(error=traceback.format_exc(), passed=passed), indent=2))


bpy.app.timers.register(run, first_interval=.5)
