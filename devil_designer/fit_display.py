import json
import bpy
from . import garment
from .fit_map import vertex_ratios, ratio_color, surface_edges


def snapshot(source, depsgraph, scene):
    panels = garment.generated(scene, 'panel')
    if source.get('dd_signature') != garment.signature(scene, panels):
        raise ValueError('Fit map unavailable: reset and simulate the current patterns first.')
    rest = [tuple(item.vector) for panel in panels for item in panel.data.attributes['dd_rest'].data]
    flat_faces = []
    offset = 0
    for panel in panels:
        flat_faces.extend(tuple(offset + index for index in face.vertices) for face in panel.data.polygons)
        offset += len(panel.data.vertices)
    if source.get('dd_run_rest'):
        saved = json.loads(source['dd_run_rest'])
        rest = [point for identity in json.loads(source['dd_piece_ids']) for point in saved[identity]]
        flat_faces = [tuple(face.vertices) for face in source.data.polygons]
    evaluated = source.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        faces = [tuple(face.vertices) for face in source.data.polygons]
        if len(mesh.vertices) != len(rest) or faces != flat_faces or [tuple(face.vertices) for face in mesh.polygons] != faces:
            raise ValueError('Fit map unavailable: simulation topology no longer matches flat panels.')
        unit = garment.metres_per_unit(scene)
        current = [tuple((source.matrix_world @ vertex.co) * unit) for vertex in mesh.vertices]
        ratios = vertex_ratios(rest, current, surface_edges(faces))
        result = mesh.copy()
    finally:
        evaluated.to_mesh_clear()
    existing = result.color_attributes.get('DD Fit Map')
    if existing is not None:
        result.color_attributes.remove(existing)
    colors = result.color_attributes.new(name='DD Fit Map', type='FLOAT_COLOR', domain='POINT')
    for item, ratio in zip(colors.data, ratios):
        item.color = ratio_color(ratio)
    return result, ratios


class FitOverlay:
    def __init__(self, editor):
        self.editor = editor
        self.enabled = False
        self.handle = None
        self.message = ''

    def toggle(self):
        if self.enabled:
            self.close()
        else:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_VIEW')
            self.enabled = True
            self.message = 'Simulate to see the fit map.'

    def close(self):
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            self.handle = None
        self.enabled = False
        self.message = ''

    def draw(self):
        context = bpy.context
        editor = self.editor
        if not self.enabled or editor._closed or editor.full or context.area != editor._area or context.region != editor._region or context.scene != editor._scene:
            return
        from gpu_extras.batch import batch_for_shader
        import gpu
        sources = [source for source in garment.generated(context.scene, 'simulation')
                   if source.visible_get(view_layer=context.view_layer)]
        self.message = '' if sources else 'Simulate to see the fit map.'
        for source in sources:
            mesh = None
            try:
                mesh, _ = snapshot(source, context.evaluated_depsgraph_get(), context.scene)
                mesh.calc_loop_triangles()
                shader = gpu.shader.from_builtin('SMOOTH_COLOR')
                towards_eye = context.region_data.view_matrix.inverted().to_3x3().col[2].normalized()
                bias = towards_eye * max(1e-6, context.region_data.view_distance * 1e-4)
                positions = [source.matrix_world @ vertex.co + bias for vertex in mesh.vertices]
                colors = [tuple(item.color) for item in mesh.color_attributes['DD Fit Map'].data]
                triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
                batch = batch_for_shader(shader, 'TRIS', {'pos': positions, 'color': colors}, indices=triangles)
                depth_test = gpu.state.depth_test_get()
                depth_mask = gpu.state.depth_mask_get()
                blend = gpu.state.blend_get()
                try:
                    gpu.state.depth_test_set('LESS_EQUAL')
                    gpu.state.depth_mask_set(False)
                    gpu.state.blend_set('NONE')
                    shader.bind()
                    batch.draw(shader)
                finally:
                    gpu.state.depth_test_set(depth_test)
                    gpu.state.depth_mask_set(depth_mask)
                    gpu.state.blend_set(blend)
            except (ValueError, KeyError, ReferenceError, RuntimeError) as error:
                self.message = str(error)
            finally:
                if mesh is not None:
                    bpy.data.meshes.remove(mesh)

    def legend(self, renderer):
        if not self.enabled or self.editor.full:
            return
        from .canvas import Rect
        from .ui_system import SURFACE_FLOATING, TEXT_PRIMARY
        scale = self.editor.canvas_layout.scale
        right = self.editor.canvas_layout.panel.x - 12 * scale
        if right < 225 * scale:
            return
        left = max(12 * scale, right - 330 * scale)
        width = right - left
        bottom = self.editor.canvas_layout.available.y + 18 * scale
        renderer.round_rect(Rect(left, bottom, width, 62 * scale), SURFACE_FLOATING, radius=7)
        if self.message:
            renderer.text(left + 8 * scale, bottom + 27 * scale, self.message, 10, TEXT_PRIMARY, max_width=width - 16 * scale)
            return
        for index in range(60):
            renderer.rect(Rect(left + 8 * scale + (width - 16 * scale) * index / 60,
                               bottom + 29 * scale, (width - 16 * scale) / 60 + .5, 9 * scale),
                          ratio_color(.85 + .30 * index / 59))
        renderer.text(left + 8 * scale, bottom + 46 * scale, 'Fit map: edge deformation', 10, TEXT_PRIMARY)
        renderer.text(left + 8 * scale, bottom + 10 * scale, '-15% loose', 9, (.8, .85, 1, 1))
        renderer.text(left + width / 2, bottom + 10 * scale, '±3% neutral', 9, (1, 1, 1, 1), True)
        renderer.text(right - 84 * scale, bottom + 10 * scale, '+15% stretch', 9, (1, .8, .8, 1))
