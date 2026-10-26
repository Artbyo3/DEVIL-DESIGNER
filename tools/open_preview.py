import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
bpy.context.preferences.view.show_splash = False


def open_workspace():
    import devil_designer
    from devil_designer import editor

    devil_designer.register()
    for obj in bpy.context.scene.objects:
        if obj.name in {'Cube', 'Camera', 'Light'}:
            obj.hide_set(True)
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    area.spaces.active.show_region_ui = False
    region = next(region for region in area.regions if region.type == 'WINDOW')
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
        workspace = editor._active
        if '--demo' in sys.argv:
            workspace.workflow_action('DEMO')
        if workspace.session.document.patterns:
            workspace.session.selected = workspace.session.document.patterns[0].id
            workspace.sync_selection()
        if '--split' in sys.argv:
            workspace.reveal_3d()
        workspace.choose_tool('SELECT')
        workspace.settings_open = False
        workspace.canvas_layout = workspace.make_layout()
        area.spaces.active.region_3d.view_rotation = Vector((0, -1, 0)).to_track_quat('Z', 'Y')
        area.spaces.active.region_3d.view_location = Vector((.65, 0, 1.2))
        area.spaces.active.region_3d.view_distance = 2.8
        workspace.message = 'Select a piece for its card. Fabric, seams, simulation and finishing stay in context.'
        area.tag_redraw()
        print('DEVIL DESIGNER AUDIT PREVIEW READY', flush=True)
    return None


bpy.app.timers.register(open_workspace, first_interval=1)
