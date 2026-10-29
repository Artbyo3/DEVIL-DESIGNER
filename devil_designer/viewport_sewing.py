import json
import bpy
import gpu
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from . import garment


def seam_hits(document, edge, fraction):
    return [seam for seam in document.seams if any(
        reference.full() == edge.full() and min(reference.t0, reference.t1) - 1e-8 <= fraction <= max(reference.t0, reference.t1) + 1e-8
        for side in (0, 1) for reference in seam.side(side))]


class PanelEdges:
    def __init__(self, document, panels):
        self.edges = {}
        self.panels = list(panels)
        self.projection = None
        for panel in self.panels:
            pattern = document.find(panel.get('dd_pattern_id'))
            if pattern is None:
                continue
            samples = json.loads(panel.get('dd_edge_samples', '{}'))
            for path, _, _, _ in pattern.loops():
                for edge in document.edges(pattern.id, path):
                    values = samples.get(edge.start, [])
                    if len(values) < 2:
                        continue
                    self.edges[edge] = [(fraction, panel.matrix_world @ panel.data.vertices[index].co) for fraction, index in values]

    def point(self, edge, fraction):
        samples = self.edges.get(edge.full())
        if not samples:
            raise ValueError('Pattern edge unavailable; rebuild the live panels.')
        for first, second in zip(samples, samples[1:]):
            if first[0] - 1e-8 <= fraction <= second[0] + 1e-8:
                return first[1].lerp(second[1], (fraction - first[0]) / max(1e-20, second[0] - first[0]))
        raise ValueError('Pattern edge fraction unavailable; rebuild the live panels.')

    def project(self, region, view):
        key = (region.as_pointer(), region.width, region.height, tuple(value for row in view.perspective_matrix for value in row))
        if self.projection is not None and self.projection[0] == key:
            return self.projection[1]
        result = []
        for edge, samples in self.edges.items():
            for first, second in zip(samples, samples[1:]):
                first_clip = view.perspective_matrix @ first[1].to_4d()
                second_clip = view.perspective_matrix @ second[1].to_4d()
                if min(first_clip.w, second_clip.w) <= 1e-8:
                    continue
                start = view3d_utils.location_3d_to_region_2d(region, view, first[1])
                end = view3d_utils.location_3d_to_region_2d(region, view, second[1])
                if start is not None and end is not None:
                    result.append((edge, first, second, start, end, first_clip.w, second_clip.w))
        self.projection = key, result
        return result

    def pick(self, region, view, mouse, visibility, tolerance=11):
        candidates = {}
        origin = view3d_utils.region_2d_to_origin_3d(region, view, mouse)
        pointer = Vector(mouse)
        for edge, first, second, start, end, first_w, second_w in self.project(region, view):
            delta = end - start
            along = max(0, min(1, (pointer - start).dot(delta) / max(1e-20, delta.length_squared)))
            distance = (pointer - start - delta * along).length
            if distance > tolerance:
                continue
            weight = (along / second_w) / ((1 - along) / first_w + along / second_w)
            target = first[1].lerp(second[1], weight)
            direction = target - origin
            if direction.length < 1e-8:
                continue
            if visibility is not None:
                _, _, _, depth = visibility.ray_cast(origin, direction.normalized(), direction.length)
                if depth is not None and depth < direction.length - max(1e-6, direction.length * 1e-5):
                    continue
            hit = distance, first[0] + weight * (second[0] - first[0])
            if edge not in candidates or distance < candidates[edge][0]:
                candidates[edge] = hit
        if len(candidates) != 1:
            return None, 'Ambiguous: multiple visible pattern edges within tolerance. Zoom in or orbit; nothing selected.' if candidates else 'Click near a visible live-panel edge.'
        edge, (_, fraction) = next(iter(candidates.items()))
        return (edge, fraction), ''


class ViewportSewing:
    def __init__(self, editor):
        self.editor = editor
        self.dirty = True
        self.serialized = None
        self.geometry = None
        self.visibility = None
        self.batches = []
        self.gesture_batch = None
        self.gesture_key = None
        self.shader = None
        self.hover = None
        self.preserve_pose = False
        self.truth = None
        self.truth_key = None
        self.truth_error = ''
        self.baselines = {}
        self.label_positions = {}
        self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_VIEW')
        self.label_handle = bpy.types.SpaceView3D.draw_handler_add(self.labels, (), 'WINDOW', 'POST_PIXEL')
        bpy.app.handlers.depsgraph_update_post.append(self.changed)

    def close(self):
        if bpy.app.timers.is_registered(self.refresh_truth):
            bpy.app.timers.unregister(self.refresh_truth)
        if self.label_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.label_handle, 'WINDOW')
            self.label_handle = None
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            self.handle = None
        if self.changed in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(self.changed)

    def changed(self, scene, depsgraph):
        if scene != self.editor._scene:
            return
        for update in depsgraph.updates:
            source = update.id.original
            if isinstance(source, bpy.types.Mesh) or isinstance(source, bpy.types.Object) and source.type == 'MESH':
                self.dirty = True
                self.truth_key = None
                self.visibility = None
                break

    def request_truth(self, context):
        from . import piece_states
        document = self.editor.session.document
        key = (document.dumps(), context.scene.dd_spacing, garment.metres_per_unit(context.scene))
        if key == self.truth_key:
            return
        self.truth_key = key
        self.truth = None
        self.truth_error = 'Compiling sewing preview'
        if piece_states.required(document):
            if not bpy.app.timers.is_registered(self.refresh_truth):
                bpy.app.timers.register(self.refresh_truth, first_interval=.01)
        else:
            self.read_truth(context)

    def refresh_truth(self):
        if self.editor._closed or self.editor._scene.name not in bpy.data.scenes:
            return None
        scene = self.editor._scene
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            self.read_truth(bpy.context)
        return None

    def read_truth(self, context):
        from .sewing_preview import snapshot, status
        document = self.editor.session.document
        try:
            result = snapshot(context, document)
            for seam in document.seams:
                record = result['records'].get(seam.id)
                if record is None:
                    record = dict(pairs=[], flat=[], world=[], rest_lengths=[], **status(document, seam))
                    record['flags'].append('Inactive seam')
                    result['records'][seam.id] = record
                shape = tuple((edge, document.edge_curve(edge)) for side in (0, 1) for edge in seam.side(side))
                before = self.baselines.setdefault(seam.id, shape)
                if before != shape:
                    record['flags'].append('Edited span; check pairing')
            self.truth = result
            self.truth_error = ''
        except (ValueError, KeyError, RuntimeError) as error:
            self.truth = None
            self.truth_error = str(error)
        self.dirty = True
        self.serialized = None
        if self.editor._area:
            self.editor._area.tag_redraw()

    def labels(self):
        context = bpy.context
        editor = self.editor
        if editor._closed or editor.full or context.area != editor._area or context.region != editor._region or context.scene != editor._scene or context.screen.is_animation_playing:
            return
        self.ensure(context)
        occupied = []
        for identity, position in self.label_positions.items():
            screen = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, position)
            if screen is None:
                continue
            record = self.truth['records'].get(identity) if self.truth else None
            readout = record['readout'] if record else self.truth_error
            flags = ' · '.join(record['flags']) if record else ''
            color = (1, .67, .31, 1) if record and (record['warning'] or record['flags']) else (.75, .95, .92, 1)
            label_x, label_y = screen.x + 8, screen.y + 14
            while any(abs(label_x - before_x) < 320 and abs(label_y - before_y) < 26 for before_x, before_y in occupied):
                label_y += 28
            occupied.append((label_x, label_y))
            editor.renderer.text(label_x, label_y, readout, 10, color, max_width=420)
            if flags:
                editor.renderer.text(label_x, label_y - 12, flags, 10, color, max_width=420)

    def ensure(self, context):
        self.request_truth(context)
        document = self.editor.session.document
        serialized = self.editor._stored
        if not self.dirty and serialized == self.serialized:
            return
        panels = [panel for panel in garment.generated(context.scene, 'panel') if panel.visible_get(view_layer=context.view_layer)]
        self.geometry = PanelEdges(document, panels)
        if self.shader is None:
            self.shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        self.batches = []
        self.label_positions = {}
        unit = garment.metres_per_unit(context.scene)
        for seam in document.seams:
            positions = []
            middles = []
            try:
                for side in (0, 1):
                    points = []
                    for index in range(49):
                        edge, fraction = document.chain_position(seam.side(side), index / 48)
                        points.append(self.geometry.point(edge, fraction))
                    for first, second in zip(points, points[1:]):
                        positions.extend((first, second))
                    start = points[-1] if side == 1 and seam.reverse else points[0]
                    for axis in ((.003, 0, 0), (0, .003, 0), (0, 0, .003)):
                        positions.extend((start - Vector(axis) / unit, start + Vector(axis) / unit))
                    middles.append(points[24])
                self.label_positions[seam.id] = (middles[0] + middles[1]) / 2
                record = self.truth['records'].get(seam.id) if self.truth else None
                if record:
                    for first, second in record['world']:
                        positions.extend((Vector(first), Vector(second)))
                    for side in (0, 1):
                        samples = [Vector(pair[side]) for pair in record['world']]
                        for index in sorted({len(samples) // 3, 2 * len(samples) // 3}):
                            if index < 1 or index >= len(samples):
                                continue
                            direction = (samples[index] - samples[index - 1]).normalized()
                            across = direction.cross(Vector((0, 0, 1)))
                            if across.length < .1:
                                across = direction.cross(Vector((1, 0, 0)))
                            across.normalize()
                            other = direction.cross(across)
                            for wing in (across, other):
                                for sign in (-1, 1):
                                    positions.extend((samples[index], samples[index] - direction * .008 / unit + wing * sign * .004 / unit))
            except ValueError:
                continue
            record = self.truth['records'].get(seam.id) if self.truth else None
            warning = not record or record['warning'] or any(flag != 'B reversed' for flag in record['flags'])
            self.batches.append((seam.id, warning, batch_for_shader(self.shader, 'LINES', {'pos': positions})))
        self.visibility = None
        self.gesture_key = None
        self.serialized = serialized
        self.dirty = False

    def tree(self, context):
        if self.visibility is None:
            vertices = []
            faces = []
            objects = [obj for obj in context.visible_objects if obj.type == 'MESH' and obj.display_type not in {'WIRE', 'BOUNDS'}]
            depsgraph = context.evaluated_depsgraph_get()
            for obj in objects:
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                try:
                    offset = len(vertices)
                    vertices.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
                    faces.extend(tuple(offset + index for index in face.vertices) for face in mesh.polygons)
                finally:
                    evaluated.to_mesh_clear()
            self.visibility = BVHTree.FromPolygons(vertices, faces) if faces else None
        return self.visibility

    def pick(self, context, pointer):
        self.ensure(context)
        return self.geometry.pick(self.editor._region, self.editor._area.spaces.active.region_3d, pointer, self.tree(context), 11 * self.editor.canvas_layout.scale)

    def gestures(self):
        editor = self.editor
        key = (editor.pending_edge, tuple(editor.free_clicks), tuple(editor.chain_a), tuple(editor.chain_b), self.hover, editor.tool)
        if key == self.gesture_key:
            return
        positions = []
        unit = garment.metres_per_unit(editor._scene)
        references = list(editor.chain_a) + list(editor.chain_b)
        if len(editor.free_clicks) >= 2:
            from .construction import path_range
            try:references.extend(path_range(editor.session.document, *editor.free_clicks[:2]))
            except ValueError:pass
        if editor.pending_edge is not None:
            references.append(editor.pending_edge)
        if self.hover is not None and editor.tool == 'SEW':
            references.append(self.hover[0])
        try:
            for edge in references:
                points = [self.geometry.point(edge, edge.t0 + (edge.t1 - edge.t0) * index / 24) for index in range(25)]
                for first, second in zip(points, points[1:]):
                    positions.extend((first, second))
            for edge, fraction in editor.free_clicks:
                point = self.geometry.point(edge, fraction)
                for axis in ((.004, 0, 0), (0, .004, 0), (0, 0, .004)):
                    positions.extend((point - Vector(axis) / unit, point + Vector(axis) / unit))
        except ValueError:
            positions = []
        self.gesture_batch = batch_for_shader(self.shader, 'LINES', {'pos': positions}) if positions else None
        self.gesture_key = key

    def draw(self):
        context = bpy.context
        editor = self.editor
        if editor._closed or editor.full or context.area != editor._area or context.region != editor._region or context.scene != editor._scene or context.screen.is_animation_playing:
            return
        self.ensure(context)
        self.gestures()
        if not self.batches and self.gesture_batch is None:
            return
        blend = gpu.state.blend_get()
        depth = gpu.state.depth_test_get()
        mask = gpu.state.depth_mask_get()
        try:
            gpu.state.blend_set('ALPHA')
            gpu.state.depth_test_set('LESS_EQUAL')
            gpu.state.depth_mask_set(False)
            self.shader.bind()
            projection = context.region_data.perspective_matrix.copy()
            projection[2] = projection[2] - projection[3] * 1e-5
            self.shader.uniform_float('ModelViewProjectionMatrix', projection)
            self.shader.uniform_float('viewportSize', (context.region.width, context.region.height))
            self.shader.uniform_float('lineWidth', 3)
            for identity, mismatch, batch in self.batches:
                highlighted = identity in (editor.seam_selected, editor.seam_hover)
                self.shader.uniform_float('color', (1, .67, .31, 1) if highlighted or mismatch else (.28, .65, .63, .85))
                batch.draw(self.shader)
            if self.gesture_batch is not None:
                self.shader.uniform_float('color', (1, .82, .3, 1))
                self.gesture_batch.draw(self.shader)
        finally:
            gpu.state.depth_mask_set(mask)
            gpu.state.depth_test_set(depth)
            gpu.state.blend_set(blend)

    def event(self, context, event, panel, canvas):
        editor = self.editor
        press = event.value == 'PRESS'
        if panel:
            self.hover = None
            if event.type == 'MOUSEMOVE':
                editor.seam_hover = None
                if canvas and not editor.card_kind:
                    for rect, identity, _ in editor.seam_badges():
                        if rect.contains(*editor.pointer):
                            editor.seam_hover = identity
                            break
                    if editor.seam_hover is None:
                        edge = editor.design_hit_edge()
                        if edge is not None:
                            point = editor.view.world(editor.pointer, editor.canvas_layout.canvas)
                            from . import curves
                            fraction, _ = curves.closest_fraction(editor.session.document.edge_curve(edge), point)
                            matches = seam_hits(editor.session.document, edge, fraction)
                            if len(matches) == 1:
                                editor.seam_hover = matches[0].id
            return None
        if editor.full or not (0 <= editor.pointer[0] < editor._region.width and 0 <= editor.pointer[1] < editor._region.height):
            return None
        if editor.pending_place or editor.pending_tack or editor.confirm_action or editor.gesture or editor.numeric:
            return None
        if context.screen.is_animation_playing:
            if editor.tool == 'SEW' and press and event.type == 'LEFTMOUSE':
                editor.message = 'Pause simulation before sewing live panels.'
                return {'RUNNING_MODAL'}
            return None
        if press and event.ctrl and event.type in {'Z', 'Y'}:
            self.preserve_pose = True
            editor.perform_action('REDO' if event.type == 'Y' or event.shift else 'UNDO')
            return {'RUNNING_MODAL'}
        if press and event.type == 'J' and not (event.ctrl or event.alt):
            editor.choose_tool('FREE_SEW' if event.shift else 'SEW')
            return {'RUNNING_MODAL'}
        if press and event.type == 'H' and not (event.ctrl or event.shift or event.alt):
            bpy.ops.devil_designer.arrangement_guide()
            return {'RUNNING_MODAL'}
        if press and event.type in {'X', 'DEL', 'BACK_SPACE'} and editor.seam_selected:
            self.preserve_pose = True
            editor.perform_action('DELETE')
            return {'RUNNING_MODAL'}
        if press and event.type == 'B' and (editor.tool == 'SEW' or editor.seam_selected):
            if editor.seam_selected:
                self.preserve_pose = True
                editor.run_edit(lambda: editor.session.reverse_seam(editor.seam_selected), 'Seam direction reversed.')
            else:
                editor._scene.dd_sew_reverse = not editor._scene.dd_sew_reverse
                editor.message = 'Sewing direction flipped (reverse: ' + ('on' if editor._scene.dd_sew_reverse else 'off') + ').'
            return {'RUNNING_MODAL'}
        if press and event.type == 'ESC' and editor.tool == 'SEW':
            editor.perform_action('CHAIN_CLEAR')
            editor.seam_hover = None
            return {'RUNNING_MODAL'}
        if press and event.type == 'RIGHTMOUSE' and editor.tool == 'SEW' and (editor.pending_edge or editor.free_clicks or editor.chain_stage):
            editor.perform_action('CHAIN_CLEAR')
            return {'RUNNING_MODAL'}
        if editor.tool not in {'SEW', 'SELECT'} or event.type not in {'MOUSEMOVE', 'LEFTMOUSE', 'RIGHTMOUSE'}:
            return None
        if event.type != 'MOUSEMOVE' and not press or event.alt or event.ctrl or event.shift:
            return None
        hit, reason = self.pick(context, editor.pointer)
        self.hover = hit
        editor.seam_hover = None
        matches = seam_hits(editor.session.document, *hit) if hit else []
        if len(matches) == 1:
            editor.seam_hover = matches[0].id
        editor._area.tag_redraw()
        if event.type == 'MOUSEMOVE':
            return None
        if hit is None:
            if editor.tool == 'SEW':
                editor.seam_selected = None
                editor.message = reason
                return {'RUNNING_MODAL'}
            return None
        choosing = editor.tool == 'SELECT' or event.type == 'RIGHTMOUSE' or editor.tool == 'SEW' and not editor.pending_edge and not editor.free_clicks and not editor._scene.dd_free_sewing and not editor.chain_stage
        if choosing and matches:
            if len(matches) != 1:
                editor.message = 'Ambiguous: multiple seams here. Select a unique sewn span; nothing selected.'
                return {'RUNNING_MODAL'}
            editor.seam_selected = matches[0].id
            editor.message = editor.sewing_message(matches[0]) + ' B flips; X removes; Ctrl+Z undoes.'
            editor.selected_anchor = None
            if event.type == 'RIGHTMOUSE':
                def menu(panel, _):
                    panel.layout.label(text=editor.sewing_message(matches[0]))
                    operator = panel.layout.operator('devil_designer.viewport_seam_action', text='Reverse seam')
                    operator.action = 'REVERSE'
                    operator = panel.layout.operator('devil_designer.viewport_seam_action', text='Remove seam')
                    operator.action = 'DELETE'
                context.window_manager.popup_menu(menu, title='Selected seam')
            return {'RUNNING_MODAL'}
        if editor.tool == 'SEW' and event.type == 'LEFTMOUSE':
            self.preserve_pose = True
            editor.design_sew_click(hit)
            return {'RUNNING_MODAL'}
        if editor.tool == 'SEW' and event.type == 'RIGHTMOUSE':
            editor.perform_action('CHAIN_CLEAR')
            return {'RUNNING_MODAL'}
        return None


class DD_OT_viewport_seam_action(bpy.types.Operator):
    bl_idname = 'devil_designer.viewport_seam_action'
    bl_label = 'Edit selected seam'
    bl_options = {'INTERNAL'}
    action: bpy.props.EnumProperty(items=(('REVERSE', 'Reverse', ''), ('DELETE', 'Delete', '')))

    def execute(self, context):
        from . import editor
        active = editor._active
        if active is None or active._scene != context.scene or not active.seam_selected or context.screen.is_animation_playing:
            return {'CANCELLED'}
        active.viewport_sewing.preserve_pose = True
        if self.action == 'DELETE':
            active.perform_action('DELETE')
        else:
            active.run_edit(lambda: active.session.reverse_seam(active.seam_selected), 'Seam direction reversed.')
        return {'FINISHED'}
