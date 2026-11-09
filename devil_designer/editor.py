import math
import traceback
import time
import bpy
import gpu
from gpu_extras.presets import draw_texture_2d
from .core import Document, Session, Vertex
from . import curves
from .canvas import Layout, View, Rect
from .interaction import OverlayControls
from .minimal import MinimalCards, minimal_layout
from .design_tools import DesignTools
from .silhouette import BodyReference, torso_alignment
from . import history,layering
from .fit_display import FitOverlay

OVERLAY_REFRESH = .4
RADIUS_STEP = 1.15
BRUSH_SPACING = .6
NON_KEYBOARD_TOKENS = ('MOUSE', 'TRACKPAD', 'TIMER', 'NDOF', 'WINDOW', 'PEN', 'ERASER', 'XR_', 'ACTIONZONE', 'EVT_', 'TEXTINPUT')
_active = None


def close_active():
    if _active is not None:
        _active.cleanup()


class DD_OT_pattern_editor(MinimalCards, DesignTools, OverlayControls, bpy.types.Operator):
    bl_idname = "devil_designer.pattern_editor"
    bl_label = "Devil Designer"
    bl_description = "Open a dedicated 2D pattern canvas beside the 3D scene"
    _closed = True
    _handle = None
    _timer = None

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        global _active
        if _active is not None:
            _active.cleanup()
            return {'FINISHED'}
        self._area, self._window, self._scene = context.area, context.window, context.scene
        self._region = next(r for r in context.area.regions if r.type == 'WINDOW')
        try:
            self.session = Session(Document.loads(self._scene.dd_document))
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}\

        self._stored = self._scene.dd_document
        history.restore(self.session, self._scene.dd_history)
        self.initialize_controls()
        self.initialize_minimal()
        self.initialize_design()
        self.reference = BodyReference()
        self.view = View()
        self.tool, self.snap, self.full = 'RECTANGLE', True, True
        self.draft, self.preview = [], None
        self.gesture = None
        self.pending_edge = self.seam_selected = None
        self.pointer = (0, 0)
        self.message = 'Drag to draw a panel. Sew its edges, then Simulate.'
        self.error_message = None
        self._closed = False
        self.shaping = None
        self.shape_cursor = None
        self.shaping_strip_rects = {}
        self.overlay_cache = None
        self.overlay_cache_size = None
        self.overlay_cache_time = 0.0
        self.free_window = self.window_rect
        self.window_drag = None
        self.window_cursor = 'DEFAULT'
        self.fit_overlay = FitOverlay(self)
        from .state_display import StateOverlay
        self.state_overlay = StateOverlay(self)
        from .viewport_sewing import ViewportSewing
        self.seam_hover = None
        self.viewport_sewing = ViewportSewing(self)
        self.canvas_layout = self.make_layout()
        self.update_reference(context)
        self.fit()
        from .draw import Renderer
        self.renderer = Renderer()
        try:
            self._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_overlay, (), 'WINDOW', 'POST_PIXEL')
            self._timer = context.window_manager.event_timer_add(.3, window=context.window)
            context.window_manager.modal_handler_add(self)
        except Exception:
            self.cleanup()
            raise
        _active = self
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}

    def reveal_3d(self):
        self.full = False
        self.canvas_layout = self.make_layout()
        available = self.canvas_layout.available
        panel = self.canvas_layout.panel
        scale = self.canvas_layout.scale
        if self.free_window:
            self.window_rect = self.free_window
            self.canvas_layout = self.make_layout()
        else:
            width = min(available.w, max(620 * scale, available.w * .45))
            self.set_window(Rect(available.x + available.w - width, panel.y, width, panel.h))
        self.save_window()
        self.fit()
        self.frame_avatar()
        self.message = '3D viewport revealed on the left. Orbit and position panels there; click Full canvas to return.'

    def frame_avatar(self):
        body = self._scene.dd_avatar
        if body is None:
            return
        from bpy_extras import view3d_utils
        from mathutils import Vector
        from . import garment
        view = self._area.spaces.active.region_3d
        low, high = garment.bounds(body)
        center = (Vector(low) + Vector(high)) / 2
        top = view3d_utils.location_3d_to_region_2d(self._region, view, Vector((center.x, center.y, high[2])))
        bottom = view3d_utils.location_3d_to_region_2d(self._region, view, Vector((center.x, center.y, low[2])))
        panel = self.canvas_layout.panel
        if top is not None and bottom is not None and 0 < top.x < self._region.width and not panel.contains(*top) and not panel.contains(*bottom) and (top - bottom).length > self._region.height * .25:
            return
        size = max(high[axis] - low[axis] for axis in range(3))
        view.view_distance = size * 2.4
        side = 1 if panel.x + panel.w / 2 > self._region.width / 2 else -1
        view.view_location = center + view.view_rotation @ Vector((size * .45 * side, 0, 0))

    def window_hit(self):
        if self.full or self.gesture or self.draft:
            return None
        panel = self.canvas_layout.panel
        scale = self.canvas_layout.scale
        x, y = self.pointer
        reach = 5 * scale
        if not (panel.x - reach <= x <= panel.x + panel.w + reach and panel.y - reach <= y <= panel.y + panel.h + reach):
            return None
        edges = ''.join(mark for mark, near in (('L', abs(x - panel.x) <= reach), ('R', abs(x - panel.x - panel.w) <= reach),
                                                ('B', abs(y - panel.y) <= reach), ('T', abs(y - panel.y - panel.h) <= reach)) if near)
        if edges:
            return edges
        if y > panel.y + panel.h - 34 * scale and self.canvas_layout.button(x, y) is None:
            return 'MOVE'
        return None

    def window_event(self, event):
        press = event.value == 'PRESS'
        drag = self.window_drag
        if drag:
            if event.type == 'MOUSEMOVE':
                self.drag_window(drag)
            elif press and event.type in {'ESC', 'RIGHTMOUSE'}:
                self.set_window(drag['rect'])
                self.window_drag = None
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.window_drag = None
                self.save_window()
                self.free_window = self.window_rect
            self._area.tag_redraw()
            return {'RUNNING_MODAL'}
        if self.card_kind and any(card[0].contains(*self.pointer) for card in self.visible_cards()):
            return None
        hit = self.window_hit()
        if press and event.type == 'LEFTMOUSE' and hit:
            self.window_drag = dict(hit=hit, pointer=self.pointer, rect=self.canvas_layout.panel)
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE':
            cursor = 'DEFAULT' if not hit else 'SCROLL_XY' if hit == 'MOVE' or len(hit) > 1 else 'MOVE_X' if hit in {'L', 'R'} else 'MOVE_Y'
            if cursor != self.window_cursor:
                self._window.cursor_set(cursor)
                self.window_cursor = cursor
        return None

    def drag_window(self, drag):
        rect = drag['rect']
        dx = self.pointer[0] - drag['pointer'][0]
        dy = self.pointer[1] - drag['pointer'][1]
        hit = drag['hit']
        least = 420 * self.canvas_layout.scale
        if hit == 'MOVE':
            self.set_window(Rect(rect.x + dx, rect.y + dy, rect.w, rect.h))
            return
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        if 'L' in hit:
            shift = min(dx, w - least)
            x, w = x + shift, w - shift
        if 'R' in hit:
            w = max(least, w + dx)
        if 'B' in hit:
            shift = min(dy, h - least)
            y, h = y + shift, h - shift
        if 'T' in hit:
            h = max(least, h + dy)
        self.set_window(Rect(x, y, w, h))

    def restore_canvas(self):
        self.free_window = self.window_rect
        self.full = True
        self.window_rect = None
        self.canvas_layout = self.make_layout()
        self.save_window()
        self.fit()
        self.message = 'Full canvas restored.'

    def make_layout(self):
        region, space = self._region, self._area.spaces.active
        left = right = top = bottom = 0
        for r in self._area.regions:
            if r.type == 'TOOLS' and space.show_region_toolbar and r.width > 1:
                left = max(left, r.x + r.width - region.x)
            if r.type == 'UI' and space.show_region_ui and r.width > 1:
                right = max(right, region.x + region.width - r.x)
            if r.type in {'HEADER', 'TOOL_HEADER'} and r.height > 1 and r.y >= region.y + region.height / 2:
                if r.y < region.y + region.height:
                    top = max(top, region.y + region.height - r.y)
            if r.type in {'ASSET_SHELF', 'ASSET_SHELF_HEADER'} and r.height > 1:
                if region.y <= r.y < region.y + region.height / 2:
                    bottom = max(bottom, r.y + r.height - region.y)
        system_scale = getattr(bpy.context.preferences.system, 'ui_scale', 0.0)
        if system_scale <= 0.0:
            system_scale = getattr(bpy.context.preferences.view, 'ui_scale', 1.0)
        scale = max(.5, system_scale)
        position = tuple(v * scale for v in self.window_rect) if self.window_rect else None
        layout = Layout(region.width, region.height, scale, self.full, max(0, left), max(0, right), top, bottom,
                        position=position)
        minimal_layout(layout, bool(self.draft), bool(self.confirm_action), bpy.context.screen.is_animation_playing,
                       kept=self.drape_document is not None or bool(layering.kept_garments(self._scene)),
                       stale=self.drape_document is not None and self.drape_document != self._scene.dd_document)
        self.place_tool_strip(layout)
        return layout

    def update_reference(self, context, force=False, align=False):
        changed = self.reference.refresh(context, force)
        if self.reference.bounds and (align or not self._scene.dd_reference_placed):
            points = self.reference_pattern_points()
            x, y = torso_alignment(self.reference.bounds, points)
            self._scene.dd_reference_x, self._scene.dd_reference_y = x, y
            self._scene.dd_reference_placed = True
        return changed

    def reference_pattern_points(self):
        patterns = self.session.document.patterns
        selected = self.session.document.find(self.session.selected)
        pattern = selected or (patterns[0] if patterns else None)
        return pattern.points if pattern else []

    def reference_corners(self):
        if not self._scene.dd_reference_visible:
            return []
        return self.reference.corners(self._scene.dd_reference_x, self._scene.dd_reference_y)

    def fit(self):
        points = [p for pat in self.session.document.patterns for p in pat.points]
        points += self.reference_corners()
        from . import tracing
        points += tracing.all_reference_corners(self._scene)
        layout = self.canvas_layout
        canvas = layout.canvas
        fit_rect = canvas
        if points:
            left = max(canvas.x, layout.rail.x + layout.rail.w + 16 * layout.scale)
            right = canvas.x + canvas.w - 16 * layout.scale
            if right > left:
                fit_rect = Rect(left, canvas.y, right - left, canvas.h)
        self.view.fit(points, fit_rect)
        self.view.cx += (canvas.x + canvas.w / 2 - fit_rect.x - fit_rect.w / 2) / self.view.zoom
        self.view.cy += (canvas.y + canvas.h / 2 - fit_rect.y - fit_rect.h / 2) / self.view.zoom

    def choose_body(self, body, context):
        self._scene.dd_avatar = body
        if body is None:
            self.pending_simulation = False
        self.update_reference(context, align=True)
        if body:
            self.fit()
            from .arrangement import pending_job
            if pending_job(context) is not None:
                self.message = self._scene.get('dd_arrangement_message', '') or 'Preparing arrangement points.'
            if self.pending_simulation:
                self.pending_simulation = False
                self.perform_action('SIMULATE')

    def persist(self):
        from . import live_panels, piece_states
        value = self.session.document.dumps()
        self._scene.dd_document = value
        self._scene.dd_history = history.store(self.session)
        self._stored = value
        live_panels.sync(bpy.context,preserve_sewing=getattr(getattr(self,'viewport_sewing',None),'preserve_pose',False))
        piece_states.update_display(bpy.context,self.session.document)
        if self._scene.dd_document!=value:
            self.session.document.uv_layout=Document.loads(self._scene.dd_document).uv_layout
            self._stored=self._scene.dd_document
            self._scene.dd_history=history.store(self.session)

    def reconcile_generated_document(self):
        if self._scene.dd_document != self._stored:
            self.session.document = Document.loads(self._scene.dd_document)
            self.persist()

    def run_edit(self, action, message):
        try:
            changed = action()
            self.persist()
            self.error_message = None
            self.message = message if changed is not False else "Nothing to change."
            if self._scene.get('dd_arrangement_message'):self.message+=' '+self._scene['dd_arrangement_message']
            if self.session.last_repairs:
                self.message += f" {self.session.last_repairs} affected sewing pair(s) removed; re-pair edited edges."
            return True
        except ValueError as exc:
            self.error_message = str(exc)
            self.message = str(exc)
            return False

    def cancel_gesture(self):
        self.gesture = None
        self.preview = None
        self.draft = []
        self.pending_edge = None
        self.handle_preview = None
        self.armed_selection = None
        self.pending_join = None
        self.mn_chain = []
        self.mn_first = None

    def clear_interaction_references(self):
        self.cancel_gesture()
        self.seam_selected = None
        self.seam_hover = None
        self.selected_anchor = None
        self.free_clicks = []
        self.dart_base = []
        self.pending_place = self.pending_tack = None
        self.pending_simulation = False
        self.numeric = None
        self.setting_drag = None

    def choose_tool(self, name):
        if self.tool == 'SHAPE' and name != 'SHAPE':
            self.end_shaping()
        free = name == 'FREE_SEW'
        matched = name == 'MN_SEW'
        name = 'SEW' if free or matched else name
        if self.draft or self.gesture:
            self.message = 'Finish drawing or cancel before choosing another tool.'
            return False
        if self.numeric and not self.commit_numeric():
            return False
        sewing_mode_changed = self.tool != name or (name == 'SEW' and (self._scene.dd_free_sewing != free or self.mn_sewing != matched))
        self.cancel_gesture()
        self._scene.dd_internal_mode = False
        self.pen_mode = None
        self.pen_points = []
        self.pending_simulation = False
        self.tool = name
        if sewing_mode_changed:
            self.selected_anchor = None
            self.seam_selected = None
            self.free_clicks = []
        if name == 'SEW':
            self._scene.dd_free_sewing = free
            self.sew_tool = 'FREE_SEW' if free else 'MN_SEW' if matched else 'SEW'
        self.mn_sewing = matched
        self.pending_place = self.pending_tack = None
        if name != 'SEW':
            self.free_clicks = []
        if name != 'DART':
            self.dart_base = []
        self.session.corner = None
        self.message = {'SELECT': "Drag a corner to reshape, or drag inside a piece to move it.",
                        'POLYGON': "Click corners. Click the first corner or press Enter to close.",
                        'RECTANGLE': "Drag on the canvas to create a rectangular pattern.",
                        'ELLIPSE': 'Drag an ellipse; edit its Bezier handles with V.',
                        'INTERNAL': 'Click internal points. Enter makes a line; click its first point for a closed shape.',
                        'PIN': 'Click fabric to pin it. Click an existing pin to select it.',
                        'PIN_BOX': 'Drag over fabric to pin an area.',
                        'PIN_EDGE': 'Click an edge to pin along it.',
                        'TACK_FABRIC': 'Click two points on the fabric to tie them together.',
                        'TACK': 'Click fabric, then click the avatar in 3D to attach a tack.',
                        'DART': 'Click two base positions on one edge, then the dart apex.',
                        'KNIFE': 'Click cut points. Enter or double-click finishes; Esc cancels. Shift locks the segment. Internal options: Cut or Cut & Sew.',
                        'PLACE': 'Click to place the selected garment panel in 3D.',
                        'SEW': 'M:N sewing: click the first side edges, then press Enter.' if matched else 'Free sewing: click start and end on one edge, then on its partner.' if free else "Click an edge, then its partner. Select a seam: B reverses it, X removes it."}.get(name, "Ready.")
        if name == 'PLACE' and self.session.selected:
            self.design_action('PLACE')
            self.reveal_3d()
        return True

    def world_pointer(self, event, anchor=None):
        x, y = self.view.world(self.pointer, self.canvas_layout.canvas)
        if self.snap != event.ctrl:
            x, y = round(x / .01) * .01, round(y / .01) * .01
        if anchor is not None and event.shift and self.tool in {'POLYGON', 'KNIFE'}:
            if abs(x - anchor[0]) > abs(y - anchor[1]):
                y = anchor[1]
            else:
                x = anchor[0]
        return x, y

    def hit(self):
        return self.design_hit()

    def hit_edge(self):
        return self.design_hit_edge()

    def sew_click(self):
        self.design_sew_click()

    def workflow_blocker(self, button):
        if button == 'STOP':
            return ''
        if self.draft or self.gesture:
            return 'Finish or cancel the current draft before building clothing.'
        if button == 'SIMULATE' and not self.session.document.patterns:
            return 'Create a pattern before building or simulating clothing.'
        if button in {'KEEP', 'RESET'} and not any(
                obj.get('dd_owner') == 'Artbyo3/DEVIL-DESIGNER' and obj.get('dd_kind') == 'simulation'
                for obj in self._scene.objects):
            return 'Start a drape before keeping or resetting it.'
        return ''

    def prepare_simulation(self):
        from . import garment
        context = bpy.context
        if self._scene.dd_avatar is None:
            active = context.view_layer.objects.active
            candidates = [obj for obj in context.selected_objects
                          if obj.type == 'MESH' and not obj.get('dd_kind')]
            body = active if active in candidates else candidates[0] if len(candidates) == 1 else None
            if body is None:
                candidates = [obj for obj in self._scene.objects
                              if obj.type == 'MESH' and not obj.get('dd_kind') and obj.visible_get()]
                body = candidates[0] if len(candidates) == 1 else None
            if body is None:
                self.pending_simulation = True
                self.show_card('BODY')
                self.message = 'Choose the body. Simulation will start automatically.'
                return False
            self.choose_body(body, context)
        if len(self.session.document.patterns) == 2 and all(pattern.placement_mode=='LEGACY' for pattern in self.session.document.patterns) and not garment.generated(self._scene, 'panel'):
            result = bpy.ops.devil_designer.arrange('EXEC_DEFAULT')
            self.reconcile_generated_document()
            return 'FINISHED' in result
        return True

    def workflow_action(self, button):
        if button == 'SIMULATE' and bpy.context.screen.is_animation_playing:
            button = 'STOP'
        blocker = self.workflow_blocker(button)
        self.error_message = None
        if blocker:
            self.message = blocker
            return False
        if button == 'SIMULATE' and not self.prepare_simulation():
            return False
        names = {'SIMULATE': 'simulate', 'STOP': 'stop', 'RESET': 'reset', 'KEEP': 'keep_drape'}
        try:
            if button == 'SIMULATE':
                from . import tack_binding
                self.session.commit(lambda: tack_binding.migrate_anchors(bpy.context, self.session.document))
                self.persist()
            self._scene.pop('dd_last_error', None)
            op = getattr(bpy.ops.devil_designer, names[button])
            result = op('EXEC_DEFAULT')
            if 'FINISHED' in result:
                if button == 'KEEP' and self.tool == 'SHAPE':
                    self.choose_tool('SELECT')
                    self.shaping = None
                if self._scene.dd_document != self._stored:
                    self.reconcile_generated_document()
                if button in {'KEEP', 'RESET'}:
                    self.drape_document = None
                if button == 'SIMULATE':
                    self.choose_tool('SELECT')
                    self.reveal_3d()
                    self.drape_document = self._scene.dd_document
                self.message = {'SIMULATE': 'Simulating. Space pauses.',
                                'STOP': 'Simulation paused. Keep mesh saves the current shape.',
                                'RESET': 'Restored the positioned panels. Edit or arrange, then simulate again.',
                                'KEEP': f"Mesh kept with {self._scene.get('dd_unwelded_seams', 0)} open seam pairs. Raise the weld in the Keep arrow and retry." if self._scene.get('dd_unwelded_seams', 0) else 'Mesh kept.'}[button]
                if button == 'KEEP':
                    self.message += ' ' + self.triangle_note()
                if button == 'SIMULATE' and self._scene.get('dd_arrangement_message'):
                    self.message+=' '+self._scene['dd_arrangement_message']
                if button == 'SIMULATE' and self._scene.get('dd_collision_warning'):
                    self.message+=' '+self._scene['dd_collision_warning']
                return True
            err = self._scene.pop('dd_last_error', None)
            self.message = self.error_message = err or 'Action could not finish. Check the Blender report and try again.'
        except (RuntimeError, ValueError) as exc:
            err = self._scene.pop('dd_last_error', None)
            self.message = self.error_message = err or str(exc).replace('Error: ', '').strip() or 'Action could not finish.'
        except Exception as exc:
            traceback.print_exc()
            clean = str(exc).replace('Error: ', '').strip()
            label = f'{type(exc).__name__}: {clean}' if clean else type(exc).__name__
            self.message = self.error_message = f'Unexpected error: {label}'
        return False

    def finish_polygon(self, closed=True):
        self.gesture = None
        points = list(self.draft)
        if self.tool == 'KNIFE':
            mode = 'Cut & Sew' if self.knife_sew else 'Cut'
            if self.run_edit(lambda: self.session.knife_cut(points, self.knife_sew), mode + ' complete.'):
                self.draft, self.preview = [], None
            return
        if self.tool == 'INTERNAL' or self._scene.dd_internal_mode:
            action = lambda: self.session.add_path(points, closed)
        else:
            action = lambda: self.session.add(points)
        if self.run_edit(action, 'Shape created. V edits points; C changes corner / curve.'):
            self.draft, self.preview = [], None

    def draw_overlay(self):
        if self._closed:
            return
        context = bpy.context
        if context.area != self._area or context.region != self._region or context.window != self._window:
            return
        try:
            self.canvas_layout = self.make_layout()
            if context.screen.is_animation_playing:
                self.draw_cached_overlay()
            else:
                self.draw_interface()
            self.renderer.draw_cloth_pins(self)
            self.renderer.draw_grab_ring(self)
        except Exception as exc:
            self.error_message = f"Render error: {exc}"
            print("Devil Designer drawing error:", exc)

    def draw_interface(self):
        self.renderer.draw(self)
        if self.tool != 'SHAPE':
            self.fit_overlay.legend(self.renderer)

    def draw_cached_overlay(self):
        region = self._region
        size = (region.width, region.height)
        now = time.perf_counter()
        held = self.shaping is not None and self.shaping.held
        stale = self.overlay_cache is None or self.overlay_cache_size != size
        if stale or (not held and (self.card_kind or self.flyout or now - self.overlay_cache_time > OVERLAY_REFRESH)):
            if stale:
                if self.overlay_cache is not None:
                    self.overlay_cache.free()
                self.overlay_cache = gpu.types.GPUOffScreen(*size)
                self.overlay_cache_size = size
            with self.overlay_cache.bind():
                gpu.state.active_framebuffer_get().clear(color=(0.0, 0.0, 0.0, 0.0))
                self.draw_interface()
            self.overlay_cache_time = now
        gpu.state.blend_set('ALPHA_PREMULT')
        draw_texture_2d(self.overlay_cache.texture_color, (0, 0), *size)
        gpu.state.blend_set('NONE')

    def modal(self, context, event):
        if self._closed:
            return {'FINISHED'}
        try:
            return self.handle_event(context, event)
        except ReferenceError:
            self.cleanup()
            self.report({'WARNING'}, 'Devil Designer closed because the view or scene it was using is gone. Your design is saved in the scene. Reopen it from View > Devil Designer.')
            return {'CANCELLED'}
        except Exception as exc:
            traceback.print_exc()
            self.error_message = f"Editor error: {exc}"
            self.message = self.error_message
            return {'RUNNING_MODAL'}

    def handle_event(self, context, event):
        if event.type == 'MOUSEMOVE' and self.tool == 'SHAPE' and self.shaping is not None and self.shaping.held:
            self.pointer = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
            self.shaping.drag(*self.pointer_ray())
            return {'RUNNING_MODAL'}
        if (self._area not in list(self._window.screen.areas) or self._area.type != 'VIEW_3D'
                or self._window.scene != self._scene):
            self.cleanup()
            return {'FINISHED'}
        if self._scene.dd_document != self._stored:
            self.session = Session(Document.loads(self._scene.dd_document))
            history.restore(self.session, self._scene.dd_history)
            self._stored = self._scene.dd_document
            self.clear_interaction_references()
            self.card_kind = None
            self.confirm_action = None
            self.confirm_message = ''
        self.canvas_layout = self.make_layout()
        self.pointer = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        panel = self.canvas_layout.panel.contains(*self.pointer) or any(card[0].contains(*self.pointer) for card in self.visible_cards())
        canvas = self.canvas_layout.canvas.contains(*self.pointer)
        if self.flyout and event.value == 'PRESS' and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and not panel:
            self.flyout = None
        self.tick_sub()
        if event.type == 'MOUSEMOVE':
            self.update_flyout(self.pointer)
        if event.value == 'PRESS' or (panel and event.type == 'MOUSEMOVE'):
            self.overlay_cache_time = 0.0
        window_result = self.window_event(event)
        if window_result is not None:
            return window_result
        field_result = self.avatar_field.event(context, event)
        if field_result is not None:
            self._area.tag_redraw()
            return field_result
        arrow_keys = {'UP_ARROW', 'DOWN_ARROW', 'LEFT_ARROW', 'RIGHT_ARROW'}
        burst = getattr(self, '_nudge_burst', None)
        if burst and (event.type == 'WINDOW_DEACTIVATE' or not canvas or self.numeric or self.library_edit
                      or self.gesture or self.card_kind or burst['session'] is not self.session
                      or burst['document'] != self.session.document.dumps()
                      or burst['selection'] != self.session.get_selection_state()
                      or (event.value == 'PRESS' and
                          (event.type, event.alt, event.shift, event.ctrl) != burst['key'])
                      or (event.value == 'RELEASE' and event.type == burst['key'][0])):
            self._nudge_burst = None
        pending = getattr(self, 'pending_transform', None)
        if pending and (pending['source'] != self.session.document.dumps()
                        or pending['selection'] != self.session.get_selection_state()
                        or self.card_kind != 'SEAM_WARNING'):
            self.cancel_transform()
            pending = None
        if event.type == 'WINDOW_DEACTIVATE':
            if pending or (self.gesture and self.gesture.get('mode') in
                           {'MOVE', 'BOX_SELECT', 'LASSO_SELECT', 'SET_PIVOT', 'TRANSFORM'}):
                self.cancel_transform()
            return {'PASS_THROUGH'}
        if pending and event.value == 'PRESS':
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                self.cancel_transform()
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE':
                card = self.minimal_card()
                if card is None or not card[0].contains(*self.pointer):
                    self.cancel_transform()
                    return {'RUNNING_MODAL'}
            elif event.ctrl and event.type in {'Z', 'Y'}:
                self.cancel_transform()
            elif not (event.ctrl and event.type == 'S'):
                return {'RUNNING_MODAL'}
        if self.shortcut_belongs_to_blender(event, panel):
            return {'PASS_THROUGH'}
        result = self.shaping_event(context, event, panel)
        if result is not None:
            return result
        from .arrangement_controls import interaction_active,point_event
        if (not panel or interaction_active()) and self.tool != 'SEW' and not self.pending_tack and not self.pending_place:
            try:arrangement_result=point_event(context,event)
            except ValueError as failure:
                self.message=str(failure)
                return {'RUNNING_MODAL'}
            if arrangement_result is not None:return arrangement_result
        sewing_result = self.viewport_sewing.event(context, event, panel, canvas)
        if sewing_result is not None:
            return sewing_result
        if event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK' and canvas and self.tool != 'KNIFE':
            edge = self.design_hit_edge()
            if edge:
                self.cancel_gesture()
                click_pt = self.world_pointer(event)
                control = self.session.document.edge_curve(edge)
                frac, _ = curves.closest_fraction(control, click_pt)
                frac = max(0.01, min(0.99, frac))
                new_v = [None]
                def apply_split():
                    v = self.session.document.split_edge(edge, frac)
                    new_v[0] = v
                if self.run_edit(lambda: self.session.commit(apply_split), "Point added on edge."):
                    if new_v[0]:
                        p = self.session.document.find(edge.pattern)
                        nodes = p.path(edge.path).vertices
                        idx = nodes.index(new_v[0])
                        self.session.select_point(edge.pattern, edge.path, idx, toggle=False)
                        self.sync_selection()
                        self.message = f"Point added ({new_v[0].point_type.title()})."
                return {'RUNNING_MODAL'}
        press = event.value == 'PRESS'
        if event.type == 'TIMER':
            if self.card_kind and self.card_kind.startswith('LIBRARY'):
                self.refresh_library()
                self._area.tag_redraw()
            self._timer_ticks = getattr(self, '_timer_ticks', 0) + 1
            if self._timer_ticks % 10 == 0 and self.update_reference(context):
                self._area.tag_redraw()
            return {'PASS_THROUGH'}
        if panel or canvas or self.gesture or self.draft or self.setting_drag or press or event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self._area.tag_redraw()
        if self.trace_points is not None:
            if press and event.type in {'ESC', 'RIGHTMOUSE'}:
                self.trace_points = None
                self.message = 'Image calibration cancelled.'
                return {'RUNNING_MODAL'}
            if press and event.type == 'LEFTMOUSE' and canvas:
                from . import tracing
                point = self.view.world(self.pointer, self.canvas_layout.canvas)
                corners = tracing.reference_corners(self._scene)
                if not corners or not tracing.inside(corners, point):
                    self.message = 'Pick a point inside the reference image.'
                    return {'RUNNING_MODAL'}
                self.trace_points.append(point)
                if len(self.trace_points) == 2:
                    try:
                        tracing.calibrate(self._scene, *self.trace_points)
                        self.message = 'Image scale set. A measurement cannot correct photo distortion.'
                        self.trace_points = None
                        self.fit()
                    except ValueError as exc:
                        self.trace_points = []
                        self.message = str(exc)
                else:
                    self.message = 'Now click the other end of the measured length.'
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'} if not panel else {'RUNNING_MODAL'}
        if self.trace_drag is not None:
            result = self.trace_drag_event(event, canvas)
            if result is not None:
                return result
        if press and event.type in {'ESC', 'RIGHTMOUSE'} and (self.pending_place or self.pending_tack):
            return self.design_pending_event(context, event, panel)
        if self.confirm_action:
            if press and event.type == 'ESC':
                self.perform_action('CANCEL_ACTION')
                return {'RUNNING_MODAL'}
            if press and event.type == 'LEFTMOUSE':
                action = self.canvas_layout.button(*self.pointer)
                if action in {'CONFIRM_ACTION', 'CANCEL_ACTION'}:
                    self.perform_action(action)
                    return {'RUNNING_MODAL'}
            if press and event.ctrl and event.type in {'Z', 'Y'}:
                redo = event.type == 'Y' or event.shift
                self.perform_action('REDO' if redo else 'UNDO')
                return {'RUNNING_MODAL'}
            if press and event.ctrl and event.type == 'S':
                return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}
        result = self.minimal_event(context, event)
        if result is not None:
            return result
        result = self.design_pending_event(context, event, panel)
        if result is not None:
            return result
        if press and event.ctrl and event.alt and event.type == 'D':
            if self.draft or self.gesture:
                self.message = 'Finish drawing or cancel before closing the workspace.'
                return {'RUNNING_MODAL'}
            self.cleanup()
            return {'FINISHED'}
        if event.ctrl and event.type == 'S':
            return {'PASS_THROUGH'}
        if self.gesture and self.gesture.get('mode') == 'DRAFT_POINT':
            if event.type not in {'MOUSEMOVE', 'LEFTMOUSE'} or (event.type == 'LEFTMOUSE' and press):
                self.gesture = None
        if self.gesture:
            mode = self.gesture['mode']
            if mode == 'TRANSFORM':
                if event.type in {'ESC', 'RIGHTMOUSE'} and press:
                    self.cancel_gesture()
                    self.message = "Transform cancelled."
                    return {'RUNNING_MODAL'}
                if press and event.type in {'RET', 'NUMPAD_ENTER'}:
                    cand = self.gesture.get('candidate')
                    pre = self.gesture.get('preflight')
                    if not cand:
                        if pre and pre.get('status') == 'BLOCK':
                            self.message = f"Cannot apply transform: {pre.get('reason', 'Blocked')}"
                        return {'RUNNING_MODAL'}
                    if pre and pre.get('status') == 'BLOCK':
                        self.message = f"Cannot apply transform: {pre.get('reason', 'Blocked')}"
                        return {'RUNNING_MODAL'}
                    if pre and pre.get('status') == 'WARN':
                        self.pending_transform = dict(candidate=cand, report=pre, op=self.gesture.get('kind', 'MOVE'),
                                                      param=self.gesture.get('param'), pivot=self.session.get_pivot(),
                                                      source=self.session.document.dumps(),
                                                      selection=self.session.get_selection_state())
                        self.card_kind = 'SEAM_WARNING'
                        self.gesture = None
                        return {'RUNNING_MODAL'}
                    self.run_edit(lambda: self.apply_transform_candidate(cand, self.gesture.get('kind', 'MOVE'), self.gesture.get('param')), "Transform applied.")
                    self.gesture = None
                    return {'RUNNING_MODAL'}
                if press and event.type == 'BACK_SPACE':
                    txt = self.gesture.get('numeric_text', '')
                    if txt:
                        self.gesture['numeric_text'] = txt[:-1]
                        self.update_transform_preview(event)
                    return {'RUNNING_MODAL'}
                if press and event.type in {'X', 'Y'} and not event.ctrl and not event.alt:
                    cur = self.gesture.get('axis_lock')
                    self.gesture['axis_lock'] = None if cur == event.type else event.type
                    self.update_transform_preview(event)
                    return {'RUNNING_MODAL'}
                if press and getattr(event, 'unicode', '') and event.unicode in '0123456789.-+%mc':
                    self.gesture['numeric_text'] = self.gesture.get('numeric_text', '') + event.unicode
                    self.update_transform_preview(event)
                    return {'RUNNING_MODAL'}
                if event.type == 'MOUSEMOVE':
                    if math.dist(self.pointer, self.gesture.get('pointer_start', self.pointer)) > 4 * self.canvas_layout.scale:
                        self.gesture['dragged'] = True
                    self.update_transform_preview(event)
                    return {'RUNNING_MODAL'}
                if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                    if not self.gesture.get('dragged', False):
                        if self.gesture.get('handle'):
                            self.cancel_gesture()
                            self.message = 'Drag a handle to rotate or scale around the pivot.'
                        return {'RUNNING_MODAL'}
                    cand = self.gesture.get('candidate')
                    pre = self.gesture.get('preflight')
                    if cand and (not pre or pre.get('status') != 'BLOCK'):
                        if pre and pre.get('status') == 'WARN':
                            self.pending_transform = dict(candidate=cand, report=pre, op=self.gesture.get('kind', 'MOVE'),
                                                          param=self.gesture.get('param'), pivot=self.session.get_pivot(),
                                                          source=self.session.document.dumps(),
                                                          selection=self.session.get_selection_state())
                            self.card_kind = 'SEAM_WARNING'
                            self.gesture = None
                            return {'RUNNING_MODAL'}
                        self.run_edit(lambda: self.apply_transform_candidate(cand, self.gesture.get('kind', 'MOVE'), self.gesture.get('param')), "Transform applied.")
                    self.gesture = None
                    return {'RUNNING_MODAL'}
                return {'RUNNING_MODAL'}
            if event.type in {'ESC', 'RIGHTMOUSE'} and press:
                self.cancel_gesture()
                self.message = "Edit cancelled."
                return {'RUNNING_MODAL'}
            if event.type == 'MOUSEMOVE':
                if mode == 'PAN':
                    previous = self.gesture['last']
                    self.view.pan(self.pointer[0] - previous[0], self.pointer[1] - previous[1])
                    self.gesture['last'] = self.pointer
                elif mode in {'RECT', 'ELLIPSE'}:
                    a = self.gesture['start']
                    b = self.world_pointer(event)
                    if event.shift:
                        side = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
                        b = (a[0] + math.copysign(side, b[0] - a[0]), a[1] + math.copysign(side, b[1] - a[1]))
                    self.preview = [a, (b[0], a[1]), b, (a[0], b[1])]
                elif mode == 'DRAFT_POINT':
                    cur_world = self.view.world(self.pointer, self.canvas_layout.canvas)
                    v = self.gesture['vertex']
                    anchor = (v.x, v.y)
                    raw_dx = cur_world[0] - anchor[0]
                    raw_dy = cur_world[1] - anchor[1]
                    if math.hypot(raw_dx, raw_dy) > 4 * self.canvas_layout.scale / self.view.zoom:
                        self.gesture['moved'] = True
                    if self.gesture.get('moved'):
                        if event.ctrl:
                            dx = round((anchor[0] + raw_dx) / 0.01) * 0.01 - anchor[0]
                            dy = round((anchor[1] + raw_dy) / 0.01) * 0.01 - anchor[1]
                        else:
                            dx, dy = raw_dx, raw_dy
                        if event.shift:
                            dist = math.hypot(dx, dy)
                            if dist > 1e-9:
                                ang = math.atan2(dy, dx)
                                step = math.radians(15)
                                ang = round(ang / step) * step
                                dx = dist * math.cos(ang)
                                dy = dist * math.sin(ang)
                        v.outgoing = (dx, dy)
                        v.incoming = (-dx, -dy)
                        v.point_type = 'SMOOTH'
                elif mode == 'EDGE_BEND':
                    world_now = self.view.world(self.pointer, self.canvas_layout.canvas)
                    if math.dist(self.gesture['start'], world_now) > 2 * self.canvas_layout.scale / self.view.zoom:
                        self.gesture['moved'] = True
                    delta = (world_now[0] - self.gesture['p_orig'][0], world_now[1] - self.gesture['p_orig'][1])
                    t0 = self.gesture['t0']
                    w1 = 3 * ((1 - t0) ** 2) * t0
                    w2 = 3 * (1 - t0) * (t0 ** 2)
                    d1 = 1 - t0
                    d2 = t0
                    denom = w1 * d1 + w2 * d2
                    k = 1.0 / denom if abs(denom) > 1e-12 else 1.0
                    dp1 = (k * d1 * delta[0], k * d1 * delta[1])
                    dp2 = (k * d2 * delta[0], k * d2 * delta[1])
                    c1 = (self.gesture['orig_c1'][0] + dp1[0], self.gesture['orig_c1'][1] + dp1[1])
                    c2 = (self.gesture['orig_c2'][0] + dp2[0], self.gesture['orig_c2'][1] + dp2[1])
                    anchor_a = self.gesture['anchor_a']
                    anchor_b = self.gesture['anchor_b']
                    self.gesture['new_outgoing'] = (c1[0] - anchor_a[0], c1[1] - anchor_a[1])
                    self.gesture['new_incoming'] = (c2[0] - anchor_b[0], c2[1] - anchor_b[1])
                elif mode == 'HANDLE':
                    target = self.view.world(self.pointer, self.canvas_layout.canvas)
                    anchor = self.gesture['anchor']
                    raw_dx = target[0] - anchor[0]
                    raw_dy = target[1] - anchor[1]
                    if event.ctrl:
                        dx = round((anchor[0] + raw_dx) / 0.01) * 0.01 - anchor[0]
                        dy = round((anchor[1] + raw_dy) / 0.01) * 0.01 - anchor[1]
                    else:
                        dx, dy = raw_dx, raw_dy
                    if event.shift:
                        dist = math.hypot(dx, dy)
                        if dist > 1e-9:
                            ang = math.atan2(dy, dx)
                            step = math.radians(15)
                            ang = round(ang / step) * step
                            dx = dist * math.cos(ang)
                            dy = dist * math.sin(ang)
                    pat = self.session.document.find(self.gesture['pattern_id'])
                    if not pat:
                        return {'RUNNING_MODAL'}
                    try:
                        nodes = pat.path(self.gesture['path_id']).vertices
                    except ValueError:
                        return {'RUNNING_MODAL'}
                    if not (0 <= self.gesture['corner'] < len(nodes)):
                        return {'RUNNING_MODAL'}
                    v = nodes[self.gesture['corner']]
                    ptype = getattr(v, 'point_type', 'CORNER')
                    h_name = self.gesture['handle']
                    o_name = 'incoming' if h_name == 'outgoing' else 'outgoing'
                    o_val = None
                    if ptype == 'SMOOTH':
                        o_h = getattr(v, o_name)
                        cur_len = math.hypot(dx, dy)
                        if cur_len > 1e-9:
                            u = (dx / cur_len, dy / cur_len)
                            o_len = math.hypot(*o_h) if o_h is not None else cur_len
                            o_val = (-u[0] * o_len, -u[1] * o_len)
                    self.handle_preview = (self.gesture['corner'], h_name, (dx, dy), o_name, o_val,
                                           self.gesture['pattern_id'], self.gesture['path_id'])
                elif mode == 'MOVE':
                    ref = self.gesture.get('ref_pos', self.gesture['start'])
                    world_now = self.view.world(self.pointer, self.canvas_layout.canvas)
                    world_start = self.gesture['start']
                    raw_x = ref[0] + (world_now[0] - world_start[0])
                    raw_y = ref[1] + (world_now[1] - world_start[1])
                    if self.snap != event.ctrl:
                        snapped_x = round(raw_x / 0.01) * 0.01
                        snapped_y = round(raw_y / 0.01) * 0.01
                    else:
                        snapped_x = raw_x
                        snapped_y = raw_y
                    dx = snapped_x - ref[0]
                    dy = snapped_y - ref[1]
                    if event.shift:
                        if abs(dx) >= abs(dy):
                            dy = 0.0
                        else:
                            dx = 0.0
                    self.gesture['delta'] = (dx, dy)
                    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                        self.gesture['moved'] = True
                    if self.gesture.get('moved') and self.session.has_selection():
                        self.gesture['candidate'], self.gesture['preflight'] = self.session.build_transform_candidate('MOVE', (dx, dy))
                    if 'points' in self.gesture:
                        self.preview = [(x + dx, y + dy) if self.session.corner is None or i == self.session.corner
                                        else (x, y) for i, (x, y) in enumerate(self.gesture['points'])]
                elif mode == 'SEAM_END':
                    world_now = self.view.world(self.pointer, self.canvas_layout.canvas)
                    self.gesture['fraction'] = curves.closest_fraction(self.session.document.edge_curve(self.gesture['edge'].full()), world_now)[0]
                elif mode == 'SET_PIVOT':
                    c = self.canvas_layout.canvas
                    world_now = self.view.world(self.pointer, c)
                    tol = 8 * self.canvas_layout.scale / self.view.zoom
                    cand_pt, cand_lbl = self.session.find_pivot_candidate(world_now, tol)
                    self.gesture['chosen'] = cand_pt
                    self.gesture['label'] = cand_lbl
                elif mode == 'LASSO_SELECT':
                    w = self.view.world(self.pointer, self.canvas_layout.canvas)
                    self.gesture.setdefault('points', []).append(w)
                    self.gesture.setdefault('screen_points', []).append(self.pointer)
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE' and event.type == ('MIDDLEMOUSE' if mode == 'PAN' else 'LEFTMOUSE'):
                if mode == 'ELLIPSE' and self.preview:
                    self.run_edit(lambda: self.session.add_ellipse(self.preview[0], self.preview[2], self._scene.dd_internal_mode), 'Ellipse created.')
                elif mode == 'SEAM_END':
                    gesture = self.gesture
                    if gesture.get('fraction') is not None:
                        self.run_edit(lambda: self.session.set_seam_end(self.seam_selected, gesture['side'], gesture['last'], gesture['fraction']), 'Seam end moved.')
                elif mode == 'RECT' and self.preview and self.tool == 'PIN_BOX':
                    self.run_edit(lambda: self.session.pins_in_box(self.preview[0], self.preview[2]), 'Area pinned.')
                elif mode == 'RECT' and self.preview:
                    action = (lambda: self.session.add_path(self.preview, True)) if self._scene.dd_internal_mode else (lambda: self.session.add(self.preview))
                    self.run_edit(action, 'Rectangle created.')
                elif mode in {'RECT', 'ELLIPSE'} and self.tool in {'RECTANGLE', 'ELLIPSE'} and not self._scene.dd_internal_mode:
                    bpy.ops.devil_designer.exact_shape('INVOKE_DEFAULT', shape=self.tool, x=self.gesture['start'][0], y=self.gesture['start'][1])
                elif mode == 'DRAFT_POINT':
                    v = self.gesture['vertex']
                    if not self.gesture.get('moved'):
                        v.point_type = 'CORNER'
                        v.incoming = None
                        v.outgoing = None
                    self.gesture = None
                    self.preview = [self.world_pointer(event, (v.x, v.y))]
                    return {'RUNNING_MODAL'}
                elif mode == 'EDGE_BEND':
                    if self.gesture.get('moved'):
                        edge = self.gesture['edge']
                        new_out = self.gesture['new_outgoing']
                        new_in = self.gesture['new_incoming']
                        def apply_bend():
                            a, b = self.session.document.edge_vertices(edge)
                            a.outgoing = new_out
                            b.incoming = new_in
                            if getattr(a, 'point_type', 'CORNER') == 'AUTO':
                                a.point_type = 'CORNER'
                            elif getattr(a, 'point_type', 'CORNER') == 'SMOOTH' and a.incoming is not None:
                                a.point_type = 'CORNER'
                            if getattr(b, 'point_type', 'CORNER') == 'AUTO':
                                b.point_type = 'CORNER'
                            elif getattr(b, 'point_type', 'CORNER') == 'SMOOTH' and b.outgoing is not None:
                                b.point_type = 'CORNER'
                        self.run_edit(lambda: self.session.commit(apply_bend), "Edge bent.")
                elif mode == 'HANDLE' and self.handle_preview:
                    self.run_edit(lambda: self.session.set_handle(*self.handle_preview), 'Bezier handle updated.')
                elif mode == 'MOVE':
                    if self.gesture.get('moved'):
                        dx, dy = self.gesture.get('delta', (0.0, 0.0))
                        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                            cand_doc, pre = self.session.build_transform_candidate('MOVE', (dx, dy))
                            if not cand_doc:
                                if pre and pre.get('status') == 'BLOCK':
                                    self.message = f"Cannot apply move: {pre.get('reason', 'Blocked')}"
                            elif pre and pre.get('status') == 'WARN':
                                self.pending_transform = dict(candidate=cand_doc, report=pre, op='MOVE',
                                                              param=(dx, dy), pivot=self.session.get_pivot(),
                                                              source=self.session.document.dumps(),
                                                              selection=self.session.get_selection_state())
                                self.card_kind = 'SEAM_WARNING'
                                self.gesture, self.preview, self.handle_preview = None, None, None
                                return {'RUNNING_MODAL'}
                            else:
                                self.run_edit(lambda: self.session.move_selection(dx, dy, confirm=True), "Pattern updated.")
                    elif self.preview:
                        self.run_edit(lambda: self.session.move(self.preview), "Pattern updated.")
                    else:
                        pending = self.gesture.get('pending_single_select')
                        if pending and not event.shift:
                            if pending[0] == 'POINT':
                                self.session.select_point(pending[1], pending[2], pending[3], toggle=False)
                            elif pending[0] == 'PIECE':
                                self.session.select_piece(pending[1], toggle=False)
                            elif pending[0] == 'EDGE':
                                self.session.select_edge(pending[1], toggle=False)
                            self.sync_selection()
                elif mode == 'SET_PIVOT':
                    tolerance = 8 * self.canvas_layout.scale / self.view.zoom
                    pt, _ = self.session.find_pivot_candidate(self.view.world(self.pointer, self.canvas_layout.canvas), tolerance)
                    self.session.set_pivot(pt[0], pt[1])
                    self.gesture = None
                    self.message = f"Pivot set ({self.session.placed_pivot[0]:.3f}, {self.session.placed_pivot[1]:.3f})."
                    return {'RUNNING_MODAL'}
                elif mode == 'BOX_SELECT':
                    if math.dist(self.gesture['start'], self.pointer) < 4 * self.canvas_layout.scale:
                        if not self.gesture.get('shift') and not self.gesture.get('alt'):
                            self.session.clear_selection()
                            self.sync_selection()
                            self.message = "Selection cleared."
                    else:
                        w0 = self.gesture['world_start']
                        w1 = self.view.world(self.pointer, self.canvas_layout.canvas)
                        kind, count = self.session.box_select(w0[0], w0[1], w1[0], w1[1],
                                                             shift=self.gesture.get('shift', False),
                                                             alt=self.gesture.get('alt', False))
                        self.sync_selection()
                        if count > 0:
                            self.message = f"{count} {kind.lower()} selected."
                        else:
                            self.message = "No items selected."
                elif mode == 'LASSO_SELECT':
                    pts = self.gesture.get('points', [])
                    if len(pts) >= 3:
                        kind, count = self.session.lasso_select(pts,
                                                               shift=self.gesture.get('shift', False) or event.shift,
                                                               alt=self.gesture.get('alt', False) or event.alt,
                                                               rule=self.gesture.get('rule', 'ENCLOSE'))
                        self.sync_selection()
                        if count > 0:
                            self.message = f"{count} {kind.lower()} selected."
                        else:
                            self.message = "No items selected."
                self.gesture, self.preview, self.handle_preview = None, None, None
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}
        if press and event.type in {'RET', 'NUMPAD_ENTER'} and self.mn_sewing:
            self.mn_commit()
            return {'RUNNING_MODAL'}
        if press and event.type == 'SPACE' and not (event.ctrl or event.alt or event.shift or self.draft or self.numeric or self.library_edit):
            self.automatic_defaults()
            self.perform_action('SIMULATE')
            return {'RUNNING_MODAL'}
        if press and event.type == 'F' and not event.ctrl and not event.alt and not self.numeric:
            self.fit_overlay.toggle()
            return {'RUNNING_MODAL'}
        if not panel:
            self._nudge_burst = None
            return {'PASS_THROUGH'}
        if event.type == 'ESC' and press:
            if self.draft or self.pending_edge or self.free_clicks or self.pending_place or self.pending_tack or self.armed_selection or self.mn_chain or self.mn_first:
                self.cancel_gesture()
                self.clear_interaction_references()
                self.message = "Draft cancelled."
                return {'RUNNING_MODAL'}
            if getattr(self, 'card_kind', None):
                self.card_kind = None
                return {'RUNNING_MODAL'}
            if self.session.has_selection():
                self.session.clear_selection()
                self.sync_selection()
                self.message = "Selection cleared."
            return {'RUNNING_MODAL'}
        if press and not self.numeric:
            if event.type == 'A':
                if event.alt and not event.ctrl and not event.shift:
                    self.session.clear_selection()
                    self.sync_selection()
                    self.message = "Selection cleared."
                    return {'RUNNING_MODAL'}
                elif not event.ctrl and not event.alt and not event.shift:
                    self.session.select_all()
                    self.sync_selection()
                    n = len(self.session.selected_patterns)
                    self.message = f"{n} pieces selected." if n != 1 else "1 piece selected."
                    return {'RUNNING_MODAL'}
            if event.type == 'H' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_H')
                return {'RUNNING_MODAL'}
            if event.type == 'V' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_V')
                return {'RUNNING_MODAL'}
        if press and event.alt and event.type == 'A' and not event.ctrl:
            self.session.clear_selection()
            self.sync_selection()
            self.message = "Selection cleared."
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type in {'K', 'H', 'J'} and not event.alt and self.session.document.find(self.session.selected):
            self.minimal_action('TOGGLE_STATE_' + {'K': 'frozen', 'H': 'strengthened', 'J': 'deactivated'}[event.type])
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type == 'I' and not event.alt:
            self.design_action('SELECT_INVERT')
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type == 'L' and not event.alt:
            self.design_action('SELECT_CONNECTED_PATH')
            return {'RUNNING_MODAL'}
        if press and event.type in arrow_keys:
            if not panel or self.numeric or self.library_edit or self.gesture or not self.session.has_selection():
                self._nudge_burst = None
                return {'RUNNING_MODAL'}
            step = 0.001 if event.alt else (0.10 if event.shift else 0.01)
            dx = -step if event.type == 'LEFT_ARROW' else (step if event.type == 'RIGHT_ARROW' else 0.0)
            dy = -step if event.type == 'DOWN_ARROW' else (step if event.type == 'UP_ARROW' else 0.0)
            cand_doc, pre = self.session.build_transform_candidate('MOVE', (dx, dy))
            if not cand_doc:
                self._nudge_burst = None
                if pre and pre.get('status') == 'BLOCK':
                    self.message = f"Cannot nudge: {pre.get('reason', 'Blocked')}"
                return {'RUNNING_MODAL'}
            if pre and pre.get('status') == 'WARN':
                self._nudge_burst = None
                self.pending_transform = dict(candidate=cand_doc, report=pre, op='MOVE',
                                              param=(dx, dy), pivot=self.session.get_pivot(),
                                              source=self.session.document.dumps(),
                                              selection=self.session.get_selection_state())
                self.card_kind = 'SEAM_WARNING'
                self.message = self.transform_warning_message(pre) + ' Burst paused.'
                return {'RUNNING_MODAL'}
            coalesce = bool(getattr(self, '_nudge_burst', None))
            res = self.session.move_selection(dx, dy, confirm=True, coalesce=coalesce)
            if res:
                self.persist()
                self.sync_selection()
                self._nudge_burst = dict(key=(event.type, event.alt, event.shift, event.ctrl),
                                         session=self.session, document=self.session.document.dumps(),
                                         selection=self.session.get_selection_state())
                self.message = f"Nudge ({dx*100:.1f}, {dy*100:.1f}) cm."
            else:
                self._nudge_burst = None
            return {'RUNNING_MODAL'}
        if event.value == 'RELEASE' and event.type in arrow_keys:
            self._nudge_burst = None
        if press and event.type not in arrow_keys:
            self._nudge_burst = None
        if press and event.ctrl and event.type in {'Z', 'Y'}:
            redo = event.type == 'Y' or event.shift
            self.perform_action('REDO' if redo else 'UNDO')
            return {'RUNNING_MODAL'}
        if press and event.type == 'H' and not event.ctrl:
            self._scene.dd_reference_visible = not self._scene.dd_reference_visible
            return {'RUNNING_MODAL'}
        if press and event.type == 'S' and not event.ctrl:
            self.snap = not self.snap
            return {'RUNNING_MODAL'}
        if press and event.type == 'L' and not event.ctrl:
            self._scene.dd_lengths_visible = not self._scene.dd_lengths_visible
            return {'RUNNING_MODAL'}
        if press and not event.ctrl and not event.alt and event.type in {'V', 'P', 'R', 'E', 'I', 'D', 'J', 'K', 'T', 'N'}:
            if event.type in {'P', 'R', 'E'}:
                self.draw_shape = {'P': 'POLYGON', 'R': 'RECTANGLE', 'E': 'ELLIPSE'}[event.type]
            elif event.type in {'I', 'D', 'N'}:
                self.internal_tool = {'I': 'INTERNAL', 'D': 'DART', 'N': 'KNIFE'}[event.type]
            elif event.type in {'K', 'T'}:
                self.pin_tool = {'K': 'PIN', 'T': 'TACK'}[event.type]
            tool_name = {'V': 'SELECT', 'P': 'POLYGON', 'R': 'RECTANGLE', 'E': 'ELLIPSE',
                         'I': 'INTERNAL', 'D': 'DART', 'J': 'FREE_SEW' if event.shift else 'SEW', 'K': 'PIN', 'T': 'TACK', 'N': 'KNIFE'}[event.type]
            self.choose_tool(tool_name)
            return {'RUNNING_MODAL'}
        if press and event.type == 'HOME':
            self.fit()
            return {'RUNNING_MODAL'}
        if self.tool == 'KNIFE' and canvas and event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK':
            self.finish_polygon(False)
            return {'RUNNING_MODAL'}
        if self.draft:
            if press and event.type in {'RET', 'NUMPAD_ENTER'}:
                self.finish_polygon(self.tool != 'INTERNAL')
            elif press and event.type == 'BACK_SPACE':
                self.draft.pop()
                self.gesture = None
            elif press and event.type == 'RIGHTMOUSE':
                self.cancel_gesture()
                self.message = "Draft cancelled."
            elif event.type == 'MOUSEMOVE':
                if not self.gesture or self.gesture.get('mode') != 'DRAFT_POINT':
                    prev_pt = (self.draft[-1].x, self.draft[-1].y) if hasattr(self.draft[-1], 'x') else self.draft[-1]
                    self.preview = [self.world_pointer(event, prev_pt)]
        if self.seam_selected and press and event.type == 'B':
            self.run_edit(lambda: self.session.reverse_seam(self.seam_selected), 'Seam direction reversed.')
            return {'RUNNING_MODAL'}
        if self.pending_edge and press and event.type == 'B':
            self._scene.dd_sew_reverse = not self._scene.dd_sew_reverse
            self.message = 'Sewing direction flipped (reverse: ' + ('on' if self._scene.dd_sew_reverse else 'off') + ').'
            return {'RUNNING_MODAL'}
        if self.pending_edge and press and event.type in {'ESC', 'RIGHTMOUSE'}:
            self.pending_edge = None
            self.message = 'Seam selection cancelled.'
            return {'RUNNING_MODAL'}
        if press and event.type in {'X', 'DEL'} and not self.draft:
            self.perform_action('DELETE')
            return {'RUNNING_MODAL'}
        if not canvas:
            return {'RUNNING_MODAL'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self.view.zoom_at(self.pointer, self.canvas_layout.canvas, 1.15 if event.type == 'WHEELUPMOUSE' else 1 / 1.15)
            return {'RUNNING_MODAL'}
        if event.type == 'MIDDLEMOUSE' and press:
            self.gesture = {'mode': 'PAN', 'last': self.pointer}
        elif event.type == 'LEFTMOUSE' and press and self.seam_end_hit():
            _, side, last, edge = self.seam_end_hit()
            self.gesture = dict(mode='SEAM_END', side=side, last=last, edge=edge, fraction=None)
        elif event.type == 'LEFTMOUSE' and press:
            if self.tool == 'SEW':
                self.sew_click()
            elif self.tool == 'KNIFE':
                anchor = self.draft[-1] if self.draft else None
                point = self.world_pointer(event, anchor)
                if anchor is None or math.dist(point, anchor) > 1e-6:
                    self.draft.append(point)
                    self.preview = [point]
            elif self.tool in {'POLYGON', 'INTERNAL'}:
                if self.tool == 'INTERNAL' and not self.draft and self.session.selected is None:
                    owner, _ = self.hit()
                    if owner:
                        self.session.selected = owner.id
                        self.session.path = 'OUTER'
                first_pt = (self.draft[0].x, self.draft[0].y) if (self.draft and hasattr(self.draft[0], 'x')) else (self.draft[0] if self.draft else None)
                if len(self.draft) >= 3 and first_pt and math.dist(self.pointer, self.view.screen(first_pt, self.canvas_layout.canvas)) < 12 * self.canvas_layout.scale:
                    self.finish_polygon(True)
                else:
                    prev_pt = (self.draft[-1].x, self.draft[-1].y) if (self.draft and hasattr(self.draft[-1], 'x')) else (self.draft[-1] if self.draft else None)
                    point = self.world_pointer(event, prev_pt)
                    outline_edge = self.design_hit_edge() if self.tool == 'INTERNAL' else None
                    if outline_edge is not None and outline_edge.path == 'OUTER':
                        document = self.session.document
                        point = document.edge_point(outline_edge, curves.closest_fraction(document.edge_curve(outline_edge), point)[0])
                    if not self.draft or math.dist(point, prev_pt) > 1e-6:
                        v = Vertex(point[0], point[1], point_type='CORNER')
                        self.draft.append(v)
                        self.preview = [point]
                        self.gesture = dict(mode='DRAFT_POINT', vertex=v, start=point, moved=False)
            elif self.tool in {'RECTANGLE', 'ELLIPSE', 'PIN_BOX'}:
                if self._scene.dd_internal_mode:
                    owner, _ = self.hit()
                    if owner:
                        self.session.selected = owner.id
                        self.session.path = 'OUTER'
                self.gesture = {'mode': 'ELLIPSE' if self.tool == 'ELLIPSE' else 'RECT', 'start': self.world_pointer(event)}
            elif self.tool == 'PLACE':
                selected, corner = self.hit()
                if selected:
                    self.session.selected = selected.id
                    self.design_action('PLACE')
                    self.reveal_3d()
            elif self.tool in {'PIN', 'PIN_EDGE', 'TACK', 'TACK_FABRIC', 'DART'}:
                try:
                    self.design_canvas_click(event)
                    if self.pending_tack:
                        self.reveal_3d()
                except ValueError as exc:
                    self.message = str(exc)
            elif self.armed_selection == 'MIRROR_SEW':
                edge = self.design_hit_edge()
                if edge is None:
                    self.message = 'Click the straight edge to mirror across. Escape cancels.'
                else:
                    self.armed_selection = None
                    self.session.selected = edge.pattern
                    self.session.segment = edge
                    self.perform_action('MIRROR_SEW')
            elif self.armed_selection:
                action = self.armed_selection
                self.armed_selection = None
                self.design_action(action)
            else:
                self.selected_anchor = None
                handle = self.transform_frame_hit()
                if (handle == 'PIVOT' and event.alt and not event.shift and not event.ctrl) or (
                        handle in {'ROTATE', 'SCALE'} and not event.shift and not event.ctrl and not event.alt):
                    self.start_frame_gesture(handle)
                    return {'RUNNING_MODAL'}
                p, corner = self.hit()
                if p is None:
                    if self.tool == 'SELECT':
                        self.gesture = dict(mode='BOX_SELECT', start=self.pointer,
                                            world_start=self.view.world(self.pointer, self.canvas_layout.canvas),
                                            shift=event.shift, alt=event.alt)
                    else:
                        if not event.shift:
                            self.session.clear_selection()
                            self.sync_selection()
                    return {'RUNNING_MODAL'}
                if corner is not None and self.hit_handle:
                    v = p.path(self.hit_path).vertices[corner]
                    self.session.path = self.hit_path
                    self.session.corner = corner
                    self.gesture = dict(mode='HANDLE', handle=self.hit_handle, anchor=(v.x, v.y),
                                        corner=corner, pattern_id=p.id, path_id=self.hit_path)
                    self.sync_selection()
                    return {'RUNNING_MODAL'}
                cursor_world = self.view.world(self.pointer, self.canvas_layout.canvas)
                if corner is not None:
                    v = p.path(self.hit_path).vertices[corner]
                    pt_key = (p.id, self.hit_path, corner)
                    edges = self.session.document.edges(p.id, self.hit_path)
                    if edges:
                        self.session.segment = edges[min(corner, len(edges) - 1)]
                    if event.shift:
                        self.session.select_point(p.id, self.hit_path, corner, toggle=True)
                        self.sync_selection()
                        self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=(v.x, v.y), delta=(0.0, 0.0), moved=False)
                    else:
                        if pt_key in self.session.selected_points:
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=(v.x, v.y), delta=(0.0, 0.0), moved=False,
                                                pending_single_select=('POINT', p.id, self.hit_path, corner))
                        else:
                            self.session.select_point(p.id, self.hit_path, corner, toggle=False)
                            self.sync_selection()
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=(v.x, v.y), delta=(0.0, 0.0), moved=False)
                else:
                    if self.hit_segment:
                        self.session.path = self.hit_path
                        self.session.segment = self.hit_segment
                        edge = self.hit_segment
                        if event.shift:
                            self.session.select_edge(edge, toggle=True)
                            self.sync_selection()
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False)
                        else:
                            if edge in self.session.selected_edges:
                                self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False,
                                                    pending_single_select=('EDGE', edge))
                            else:
                                self.session.select_edge(edge, toggle=False)
                                self.sync_selection()
                                self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False)
                    elif event.shift:
                        self.session.select_piece(p.id, toggle=True)
                        self.sync_selection()
                        self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False)
                    else:
                        if p.id in self.session.selected_patterns:
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False,
                                                pending_single_select=('PIECE', p.id))
                        else:
                            self.session.select_piece(p.id, toggle=False)
                            self.sync_selection()
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False)
        return {'RUNNING_MODAL'}

    def shaping_view_bounds(self):
        available = self.canvas_layout.available
        return Rect(available.x, available.y, max(0, self.canvas_layout.panel.x - available.x), available.h)

    def grab_ring_pixels(self):
        if self.tool != 'SHAPE' or self.shaping is None:
            return None
        strip = self.shaping_strip_rects.get('STRIP_BOUNDS')
        if not self.shaping_view_bounds().contains(*self.pointer) or strip and strip.contains(*self.pointer):
            return None
        from bpy_extras import view3d_utils
        from mathutils import Vector
        grab = self.shaping
        view = self._area.spaces.active.region_3d
        depth = grab.plane_point if grab.held else grab.source.matrix_world @ (sum((Vector(corner) for corner in grab.source.bound_box), Vector()) / 8)
        reach = view.view_rotation @ Vector((grab.radius / max(1e-6, self._scene.unit_settings.scale_length), 0, 0))
        center = view3d_utils.location_3d_to_region_2d(self._region, view, depth)
        edge = view3d_utils.location_3d_to_region_2d(self._region, view, depth + reach)
        return None if center is None or edge is None else (edge - center).length

    def shaping_controls_layout(self):
        if self.tool != 'SHAPE':
            return {}
        s = self.canvas_layout.scale
        panel = self.shaping_view_bounds()
        rects = {}
        if panel.w < 200 * s:
            return rects
        s = min(s, (panel.w - 24 * s) / 186)
        strip_w = min(panel.w - 24 * s, 186 * s)
        strip_x = round(panel.x + (panel.w - strip_w) / 2)
        strip_y = round(panel.y + panel.h - 44 * s)
        rects['STRIP_BOUNDS'] = Rect(strip_x, strip_y, strip_w, 36 * s)
        btn_w = round(24 * s)
        minus_x = strip_x + 6 * s
        rects['RADIUS_MINUS'] = Rect(minus_x, strip_y + 4 * s, btn_w, 28 * s)
        value_w = round(60 * s)
        rects['RADIUS_VALUE'] = Rect(minus_x + btn_w + 2 * s, strip_y + 4 * s, value_w, 28 * s)
        rects['RADIUS_PLUS'] = Rect(minus_x + btn_w + value_w + 4 * s, strip_y + 4 * s, btn_w, 28 * s)
        return rects

    def enable_shaping(self, context):
        from . import garment
        from .xpbd_live import ClothGrab
        simulations = garment.generated(context.scene, 'simulation')
        if not simulations or simulations[0].hide_get():
            raise ValueError('Start a drape before grabbing it.')
        from . import xpbd
        if not xpbd.current(simulations[0]):
            raise ValueError('This drape comes from an older version. Press Simulate once, then grab it.')
        if self.shaping is None or self.shaping.source != simulations[0]:
            self.shaping = ClothGrab(simulations[0])
        if not self.choose_tool('SHAPE'):
            return
        self.shaping.arm()
        if self.full:
            self.reveal_3d()
        self.card_kind = None
        self._window.cursor_modal_set('HAND')
        self.shape_cursor = 'HAND'
        self.message = 'Drag the cloth while it simulates. W pins it where you hold it. Ctrl+wheel changes radius.'

    def end_shaping(self):
        if self.shaping is not None:
            if self.shaping.alive:
                self.shaping.release(bpy.context)
            self.shaping.disarm()
        if self.shape_cursor is not None:
            self._window.cursor_modal_restore()
        self.shape_cursor = None
        self.pending_strokes = []
        self.brush_stretch = None
        self.flyout = None

    def pointer_ray(self):
        from bpy_extras import view3d_utils
        view = self._area.spaces.active.region_3d
        origin = view3d_utils.region_2d_to_origin_3d(self._region, view, self.pointer)
        return origin, view3d_utils.region_2d_to_vector_3d(self._region, view, self.pointer)

    def trace_drag_event(self, event, canvas):
        scene = self._scene
        if not scene.dd_trace_path or scene.dd_trace_locked:
            self.trace_drag = None
            return None
        press = event.value == 'PRESS'
        if press and event.type in {'ESC', 'RIGHTMOUSE'}:
            self.trace_drag = None
            self.message = 'Image placement finished.'
            return {'RUNNING_MODAL'}
        if (press and event.type == 'LEFTMOUSE' and canvas and not self.canvas_layout.rail.contains(*self.pointer)
                and not any(card[0].contains(*self.pointer) for card in self.visible_cards())):
            self.trace_drag = dict(start=self.view.world(self.pointer, self.canvas_layout.canvas),
                                   origin=(scene.dd_trace_x, scene.dd_trace_y))
            return {'RUNNING_MODAL'}
        if isinstance(self.trace_drag, dict):
            if event.type == 'MOUSEMOVE':
                point = self.view.world(self.pointer, self.canvas_layout.canvas)
                scene.dd_trace_x = self.trace_drag['origin'][0] + point[0] - self.trace_drag['start'][0]
                scene.dd_trace_y = self.trace_drag['origin'][1] + point[1] - self.trace_drag['start'][1]
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.trace_drag = 'ARMED'
                self.message = 'Image moved. Drag again, or press Escape to finish.'
                return {'RUNNING_MODAL'}
        return None

    def shortcut_belongs_to_blender(self, event, panel):
        if panel or self.tool in {'SHAPE', 'PEN'} or self.pen_mode or event.type == 'NONE' or any(token in event.type for token in NON_KEYBOARD_TOKENS):
            return False
        if (self.numeric or self.library_edit or self.setting_drag or self.gesture or self.draft or self.confirm_action
                or self.trace_points is not None or self.trace_drag is not None or getattr(self, 'pending_transform', None)):
            return False
        from .arrangement_controls import interaction_active
        if interaction_active():
            return False
        if event.ctrl and event.type in {'Z', 'Y'}:
            return False
        if event.type == 'ESC' and (self.card_kind or self.flyout or self.pending_edge or self.pending_place or self.pending_tack
                                    or self.free_clicks or self.mn_chain or self.mn_first):
            return False
        if event.type == 'B' and (self.seam_selected or self.pending_edge or self.tool == 'SEW'):
            return False
        if event.type in {'RET', 'NUMPAD_ENTER'} and self.mn_sewing:
            return False
        if event.type in {'X', 'DEL', 'BACK_SPACE'} and self.seam_selected and not (event.ctrl or event.alt or event.shift):
            return False
        return True

    def shaping_event(self, context, event, panel):
        from . import garment
        press = event.value == 'PRESS'
        if self.tool != 'SHAPE':
            return None
        grab = self.shaping
        self.shaping_strip_rects = self.shaping_controls_layout()
        if event.type == 'MOUSEMOVE':
            self._area.tag_redraw()
        if event.type == 'MIDDLEMOUSE' or event.alt:
            if grab is not None:
                grab.view_changed()
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            if panel:
                return None
            if not event.ctrl:
                if grab is not None:
                    grab.view_changed()
                return {'PASS_THROUGH'}
            if not grab.held:
                grab.scale_radius(RADIUS_STEP if event.type == 'WHEELUPMOUSE' else 1 / RADIUS_STEP)
                self.message = f'Grab radius {grab.radius * 1000:.0f} mm'
                self.overlay_cache_time = 0.0
            return {'RUNNING_MODAL'}
        if self.card_kind and not grab.held:
            return self.minimal_event(context, event) or {'RUNNING_MODAL'}
        if press and event.type == 'SPACE':
            if self.pending_strokes:
                self.apply_strokes(context, grab)
            elif context.screen.is_animation_playing:
                garment.stop(context)
            else:
                garment.start_playback(context)
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type == 'Z' and grab.undo():
            self.message = 'Cloth pin change undone.'
            return {'RUNNING_MODAL'}
        if press and event.type == 'ESC':
            if grab.held:
                grab.release(context)
                self._window.cursor_modal_set('HAND')
                self.shape_cursor = 'HAND'
            else:
                self.choose_tool('SELECT')
            return {'RUNNING_MODAL'}
        if press and not event.ctrl and event.type in {'V', 'P', 'R', 'E', 'I', 'D', 'J', 'K', 'T', 'N'}:
            self.choose_tool({'V': 'SELECT', 'P': 'POLYGON', 'R': 'RECTANGLE', 'E': 'ELLIPSE', 'I': 'INTERNAL', 'D': 'DART',
                              'J': 'SEW', 'K': 'PIN', 'T': 'TACK', 'N': 'KNIFE'}[event.type])
            return {'RUNNING_MODAL'}
        if grab.held and (press and event.type == 'W' or event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and grab.mode == 'PIN'):
            self.pin_grabbed(context, grab)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and grab.held:
            grab.release(context)
            self._window.cursor_modal_set('HAND')
            self.shape_cursor = 'HAND'
            self.message = 'Released. The cloth settles from where you left it. Press W while holding to pin it instead.'
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and grab.held:
            grab.drag(*self.pointer_ray())
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.brush_stretch is not None:
            self.brush_stretch = None
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and self.brush_stretch is not None:
            hit = grab.pick(context, *self.pointer_ray())
            last = self.pending_strokes[-1] if self.pending_strokes else None
            if hit is not None and (last is None or math.dist(tuple(hit[1]), last['world']) >= last['record']['radius'] * BRUSH_SPACING / max(1e-9, garment.metres_per_unit(context.scene))):
                self.brush_cloth(grab, hit[0], hit[1], self.brush_stretch)
            return {'RUNNING_MODAL'}
        if press and event.type == 'LEFTMOUSE' and not panel:
            strip = self.shaping_strip_rects
            if 'STRIP_BOUNDS' in strip and strip['STRIP_BOUNDS'].contains(*self.pointer):
                if strip['RADIUS_MINUS'].contains(*self.pointer):
                    grab.scale_radius(1 / RADIUS_STEP)
                    self.message = f'Grab radius {grab.radius * 1000:.0f} mm'
                elif strip['RADIUS_PLUS'].contains(*self.pointer):
                    grab.scale_radius(RADIUS_STEP)
                    self.message = f'Grab radius {grab.radius * 1000:.0f} mm'
                self.overlay_cache_time = 0.0
                return {'RUNNING_MODAL'}
            origin, direction = self.pointer_ray()
            hit = grab.pick(context, origin, direction)
            if hit is None:
                self.message = 'Press on the cloth to grab it.'
                return {'RUNNING_MODAL'}
            if event.ctrl:
                self.message = 'Pin removed.' if grab.unpin_near(context, hit[0]) else 'No pin under the ring. Ctrl+click a pinned spot to free it.'
                return {'RUNNING_MODAL'}
            if grab.mode in {'PINCH', 'STEAM'}:
                self.brush_stretch = event.shift
                self.brush_cloth(grab, hit[0], hit[1], event.shift)
                return {'RUNNING_MODAL'}
            if grab.locked(hit[0]):
                self.message = 'This cloth is held by a pattern pin, a tack or a frozen piece, so it cannot be dragged.'
                return {'RUNNING_MODAL'}
            grab.begin(context, hit[0], hit[1], hit[2], direction)
            self._window.cursor_modal_set('HAND_CLOSED')
            self.shape_cursor = 'HAND_CLOSED'
            garment.start_playback(context)
            return {'RUNNING_MODAL'}
        if panel and press and event.type == 'LEFTMOUSE':
            button = self.canvas_layout.button(*self.pointer)
            if button and not button.startswith('STRIP_') and button not in {'SHAPE', 'KEEP', 'KEEP_OPTIONS', 'SIMULATE', 'SIMULATE_OPTIONS', 'CLOSE'}:
                self.choose_tool('SELECT')
        return None

    def pin_grabbed(self, context, grab):
        pinned = grab.pin(context)
        self._window.cursor_modal_set('HAND')
        self.shape_cursor = 'HAND'
        self.message = 'Pinned here. Drag it to move it. Ctrl+click frees it.' if pinned else 'That cloth is already held by a pattern pin, tack or freeze.'

    def cloth_pin_pixels(self):
        from . import garment
        simulations = garment.generated(self._scene, 'simulation')
        if self.full or not simulations or not simulations[0].visible_get():
            return []
        from bpy_extras import view3d_utils
        from .xpbd_live import pinned_world
        view = self._area.spaces.active.region_3d
        bounds = self.shaping_view_bounds()
        pixels = [view3d_utils.location_3d_to_region_2d(self._region, view, point) for point in pinned_world(simulations[0])]
        return [tuple(pixel) for pixel in pixels if pixel is not None and bounds.contains(*pixel)]

    def brush_cloth(self, grab, vertex, world, stretch):
        try:
            identity, placed = self.cloth_point(grab.source, vertex)
        except ValueError as failure:
            self.message = str(failure)
            return
        pinch = grab.mode == 'PINCH'
        self.pending_strokes.append(dict(world=tuple(world), record=dict(pattern=identity, x=placed[0], y=placed[1],
                                         radius=max(.015, grab.radius * .4) if pinch else grab.radius,
                                         amount=(.3 if pinch else .12) * (-1 if stretch else 1))))
        self.message = f'{len(self.pending_strokes)} stroke(s). Space applies them.'

    def apply_strokes(self, context, grab):
        records = [item['record'] for item in self.pending_strokes]
        self.pending_strokes = []
        self.run_edit(lambda: self.session.add_steam(records), 'Strokes applied.')
        self.redrape_in_grab(context, grab.mode, grab.radius)

    def redrape_in_grab(self, context, mode, radius):
        self.shaping = None
        self.perform_action('SIMULATE')
        self.enable_shaping(context)
        self.shaping.mode = mode
        self.shaping.radius = radius

    def _parse_dist(self, s):
        s = s.strip().lower()
        if not s:return None
        factor = 1.0
        if s.endswith('mm'):factor = 0.001;s = s[:-2].strip()
        elif s.endswith('cm'):factor = 0.01;s = s[:-2].strip()
        elif s.endswith('m'):factor = 1.0;s = s[:-1].strip()
        try:
            val = float(s)
            if math.isfinite(val):return val * factor
        except ValueError:pass
        return None

    def _parse_angle(self, s):
        s = s.strip().lower().removesuffix('deg').removesuffix('°').strip()
        if not s:return None
        try:
            val = float(s)
            if math.isfinite(val):return val
        except ValueError:pass
        return None

    def _parse_scale(self, s):
        s = s.strip().lower()
        if not s:return None
        is_pct = False
        if s.endswith('%'):is_pct = True;s = s[:-1].strip()
        try:
            val = float(s)
            if math.isfinite(val) and val > 0:
                return (val / 100.0) if is_pct else val
        except ValueError:pass
        return None

    def update_transform_preview(self, event=None):
        if not self.gesture or self.gesture.get('mode') != 'TRANSFORM':return
        kind = self.gesture.get('kind', 'MOVE')
        txt = self.gesture.get('numeric_text', '').strip()
        c = self.canvas_layout.canvas
        world_now = self.view.world(self.pointer, c)
        world_start = self.gesture.get('start', world_now)
        pivot = self.session.get_pivot()
        px, py = pivot
        axis = self.gesture.get('axis_lock')
        shift = getattr(event, 'shift', False) if event else False
        ctrl = getattr(event, 'ctrl', False) if event else False

        if kind == 'MOVE':
            if txt:
                parsed = self._parse_dist(txt)
                if parsed is None:
                    self.gesture['candidate'] = None
                    self.gesture['preflight'] = {'status': 'BLOCK', 'reason': 'Invalid move distance.'}
                    self.gesture['param'] = None
                    return
                if axis == 'X':dx, dy = parsed, 0.0
                elif axis == 'Y':dx, dy = 0.0, parsed
                else:dx, dy = parsed, 0.0
            else:
                raw_dx = world_now[0] - world_start[0]
                raw_dy = world_now[1] - world_start[1]
                if self.snap != ctrl:
                    raw_dx = round(raw_dx / 0.01) * 0.01
                    raw_dy = round(raw_dy / 0.01) * 0.01
                if shift:
                    if abs(raw_dx) >= abs(raw_dy):raw_dy = 0.0
                    else:raw_dx = 0.0
                if axis == 'X':raw_dy = 0.0
                elif axis == 'Y':raw_dx = 0.0
                dx, dy = raw_dx, raw_dy
            param = (dx, dy)
        elif kind == 'ROTATE':
            if txt:
                parsed = self._parse_angle(txt)
                if parsed is None:
                    self.gesture['candidate'] = None
                    self.gesture['preflight'] = {'status': 'BLOCK', 'reason': 'Invalid rotation angle.'}
                    self.gesture['param'] = None
                    return
                deg = parsed
            else:
                ang_now = math.atan2(world_now[1] - py, world_now[0] - px)
                ang_start = math.atan2(world_start[1] - py, world_start[0] - px)
                deg = math.degrees(ang_now - ang_start)
                if shift:
                    deg = round(deg / 15.0) * 15.0
            param = deg
        elif kind == 'SCALE':
            if txt:
                parsed = self._parse_scale(txt)
                if parsed is None:
                    self.gesture['candidate'] = None
                    self.gesture['preflight'] = {'status': 'BLOCK', 'reason': 'Scale factor must be positive and finite.'}
                    self.gesture['param'] = None
                    return
                factor = parsed
            else:
                d0 = math.hypot(world_start[0] - px, world_start[1] - py)
                d1 = math.hypot(world_now[0] - px, world_now[1] - py)
                factor = (d1 / d0) if d0 > 1e-6 else 1.0
                if shift:
                    factor = round(factor * 10.0) / 10.0
            param = factor
        cand_doc, pre = self.session.build_transform_candidate(kind, param, pivot=pivot)
        self.gesture['candidate'] = cand_doc
        self.gesture['preflight'] = pre
        self.gesture['param'] = param

    def cleanup(self):
        global _active
        if self._closed:
            return
        self.end_shaping()
        self.cancel_pending_sub()
        self.avatar_field.close()
        self.avatar_field.release_surface()
        self.save_window()
        self._closed = True
        if self.overlay_cache is not None:
            self.overlay_cache.free()
            self.overlay_cache = None
        self.fit_overlay.close()
        self.state_overlay.close()
        self.viewport_sewing.close()
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        if self._timer is not None:
            bpy.context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        try:
            self._area.tag_redraw()
        except ReferenceError:
            pass
        if _active is self:
            _active = None

    def cancel(self, context):
        self.cleanup()
