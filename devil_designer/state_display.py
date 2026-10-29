import bpy
from . import garment
from .piece_states import label, piece_indices


class StateOverlay:
    def __init__(self, editor):
        self.editor = editor
        self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_PIXEL')

    def close(self):
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            self.handle = None

    def draw(self):
        from mathutils import Vector
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        import blf
        from .ui_system import ACCENT, TEXT_MUTED, SELECTION
        context = bpy.context
        editor = self.editor
        if editor._closed or editor.full or context.area != editor._area or context.region != editor._region or context.scene != editor._scene:
            return
        doc = editor.session.document
        simulations = garment.generated(context.scene, 'simulation')
        simulation = simulations[0] if simulations else None
        groups = piece_indices(simulation) if simulation else {}
        evaluated = simulation.evaluated_get(context.evaluated_depsgraph_get()) if simulation else None
        panels = {panel['dd_pattern_id']: panel for panel in garment.generated(context.scene, 'panel')}
        for pattern in doc.patterns:
            text = label(pattern)
            if not text:
                continue
            indices = groups.get(pattern.id)
            if not pattern.deactivated and evaluated is not None and indices:
                center = sum((simulation.matrix_world @ evaluated.data.vertices[index].co for index in indices), Vector()) / len(indices)
            else:
                panel = panels.get(pattern.id)
                if panel is None or not panel.data.vertices:
                    continue
                center = sum((panel.matrix_world @ vertex.co for vertex in panel.data.vertices), Vector()) / len(panel.data.vertices)
            point = location_3d_to_region_2d(context.region, context.region_data, center)
            if point is None:
                continue
            blf.size(0, 12 * editor.canvas_layout.scale)
            blf.position(0, point.x, point.y, 0)
            blf.color(0, *(TEXT_MUTED if pattern.deactivated else ACCENT if pattern.frozen else SELECTION))
            blf.draw(0, pattern.name + ' · ' + text)
