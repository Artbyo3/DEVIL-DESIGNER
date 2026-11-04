import math
import traceback
import bpy
from .core import Document, Session, Vertex
from . import curves
from .canvas import Layout, View, Rect
from .interaction import OverlayControls
from .minimal import MinimalCards, minimal_layout
from .design_tools import DesignTools
from .silhouette import BodyReference, torso_alignment
from . import history,layering
from .fit_display import FitOverlay

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
        self.shape_start = None
        self.shape_cursor = None
        self.shape_hover = None
        self.shape_mode = 'PULL'
        self.pending_release = False
        self.release_frame = None
        self.shape_save_pending = False
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
        width = min(available.w, max(620 * self.canvas_layout.scale, available.w * .45))
        self.set_window(Rect(available.x + available.w - width, panel.y, width, panel.h))
        self.save_window()
        self.fit()
        self.message = '3D viewport revealed on the left. Orbit and position panels there; click Full canvas to return.'

    def restore_canvas(self):
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
                       kept=bool(layering.kept_garments(self._scene)))
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
        if self._scene.dd_trace_visible:
            points += list(tracing.reference_corners(self._scene))
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
        name = 'SEW' if free else name
        if self.draft or self.gesture:
            self.message = 'Finish drawing or cancel before choosing another tool.'
            return False
        if self.numeric and not self.commit_numeric():
            return False
        sewing_mode_changed = self.tool != name or (name == 'SEW' and self._scene.dd_free_sewing != free)
        self.cancel_gesture()
        self.pending_simulation = False
        self.tool = name
        if sewing_mode_changed:
            self.selected_anchor = None
            self.seam_selected = None
            self.free_clicks = []
        if name == 'SEW':
            self._scene.dd_free_sewing = free
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
                        'TACK': 'Click fabric, then click the avatar in 3D to attach a tack.',
                        'DART': 'Click two base positions on one edge, then the dart apex.',
                        'KNIFE': 'Click cut points. Enter or double-click finishes; Esc cancels. Shift locks the segment. Internal options: Cut or Cut & Sew.',
                        'PLACE': 'Click to place the selected garment panel in 3D.',
                        'SEW': "Click an edge, then its partner. Select a seam: B reverses it, X removes it."}.get(name, "Ready.")
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
                if button == 'SIMULATE':
                    self.choose_tool('SELECT')
                    self.reveal_3d()
                self.message = {'SIMULATE': 'Simulation running. Stop on the frame you want to keep.',
                                'STOP': 'Simulation paused. Keep mesh saves the current shape.',
                                'RESET': 'Restored the positioned panels. Edit or arrange, then simulate again.',
                                'KEEP': 'Draped mesh kept. Check the Blender report for any open seam pairs.'}[button]
                if button == 'SIMULATE' and self._scene.get('dd_arrangement_message'):
                    self.message+=' '+self._scene['dd_arrangement_message']
                return True
            err = self._scene.pop('dd_last_error', None)
            self.message = err or 'Action could not finish. Check the Blender report and try again.'
        except (RuntimeError, ValueError) as exc:
            err = self._scene.pop('dd_last_error', None)
            self.message = err or str(exc).replace('Error: ', '').strip() or 'Action could not finish.'
        except Exception as exc:
            traceback.print_exc()
            clean = str(exc).replace('Error: ', '').strip()
            label = f'{type(exc).__name__}: {clean}' if clean else type(exc).__name__
            self.message = f'Unexpected error: {label}'
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
            self.renderer.draw(self)
            if self.tool != 'SHAPE':
                self.fit_overlay.legend(self.renderer)
        except Exception as exc:
            self.error_message = f"Render error: {exc}"
            print("Devil Designer drawing error:", exc)

    def modal(self, context, event):
        if self._closed:
            return {'FINISHED'}
        try:
            return self.handle_event(context, event)
        except (ReferenceError, RuntimeError):
            self.cleanup()
            return {'CANCELLED'}
        except Exception as exc:
            print("Devil Designer modal error:", exc)
            self.error_message = f"Editor error: {exc}"
            self.message = self.error_message
            return {'RUNNING_MODAL'}

    def handle_event(self, context, event):
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
        panel = self.canvas_layout.panel.contains(*self.pointer)
        canvas = self.canvas_layout.canvas.contains(*self.pointer)
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
                if not corners or not (corners[0][0] <= point[0] <= corners[2][0] and corners[0][1] <= point[1] <= corners[2][1]):
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
                elif mode == 'RECT' and self.preview:
                    action = (lambda: self.session.add_path(self.preview, True)) if self._scene.dd_internal_mode else (lambda: self.session.add(self.preview))
                    self.run_edit(action, 'Rectangle created.')
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
        if press and event.type == 'F' and not event.ctrl and not event.alt and not self.numeric:
            self.fit_overlay.toggle()
            return {'RUNNING_MODAL'}
        if not panel:
            self._nudge_burst = None
            return {'PASS_THROUGH'}
        if event.type == 'ESC' and press:
            if self.draft or self.pending_edge or self.free_clicks or self.pending_place or self.pending_tack:
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
            self.cleanup()
            return {'FINISHED'}
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
                         'I': 'INTERNAL', 'D': 'DART', 'J': 'SEW', 'K': 'PIN', 'T': 'TACK', 'N': 'KNIFE'}[event.type]
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
                    if not self.draft or math.dist(point, prev_pt) > 1e-6:
                        v = Vertex(point[0], point[1], point_type='CORNER')
                        self.draft.append(v)
                        self.preview = [point]
                        self.gesture = dict(mode='DRAFT_POINT', vertex=v, start=point, moved=False)
            elif self.tool in {'RECTANGLE', 'ELLIPSE'}:
                self.gesture = {'mode': 'RECT' if self.tool == 'RECTANGLE' else 'ELLIPSE', 'start': self.world_pointer(event)}
            elif self.tool == 'PLACE':
                selected, corner = self.hit()
                if selected:
                    self.session.selected = selected.id
                    self.design_action('PLACE')
                    self.reveal_3d()
            elif self.tool in {'PIN', 'TACK', 'DART'}:
                try:
                    self.design_canvas_click(event)
                    if self.pending_tack:
                        self.reveal_3d()
                except ValueError as exc:
                    self.message = str(exc)
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

    def frame_cloth(self, context):
        from . import garment
        from .cloth_shaping import points
        from bpy_extras import view3d_utils
        from mathutils import Vector
        simulations = garment.generated(context.scene, 'simulation')
        if not simulations:
            return
        coords = [simulations[0].matrix_world @ point for point in points(simulations[0])]
        if not coords:
            return
        center = Vector(tuple((min(point[axis] for point in coords) + max(point[axis] for point in coords)) / 2 for axis in range(3)))
        radius = max((point - center).length for point in coords)
        view = self._area.spaces.active.region_3d
        bounds = self.shaping_view_bounds()
        view.view_location = center
        view.view_distance = max(.3, radius * 3 * self._region.width / max(1, bounds.w))
        view.update()
        target = (bounds.x + bounds.w / 2, bounds.y + bounds.h / 2)
        projected = view3d_utils.region_2d_to_location_3d(self._region, view, target, center)
        view.view_location = center - (projected - center)
        view.update()
        self.message = 'Framed cloth in exposed 3D view.'

    def shaping_view_bounds(self):
        available = self.canvas_layout.available
        return Rect(available.x, available.y, max(0, self.canvas_layout.panel.x - available.x), available.h)

    def shaping_controls_layout(self):
        if self.tool != 'SHAPE':
            return {}
        s = self.canvas_layout.scale
        panel = self.shaping_view_bounds()
        panel_x = panel.w
        rects = {}
        if panel_x < 200 * s:
            return rects
        s = min(s, (panel_x - 24 * s) / 280)
        strip_w = min(panel_x - 24 * s, 280 * s)
        strip_x = round(panel.x + (panel_x - strip_w) / 2)
        strip_y = round(panel.y + panel.h - 44 * s)
        rects['STRIP_BOUNDS'] = Rect(strip_x, strip_y, strip_w, 36 * s)
        mode_w = round(64 * s)
        rects['MODE_TOGGLE'] = Rect(strip_x + 6 * s, strip_y + 4 * s, mode_w, 28 * s)
        btn_w = round(24 * s)
        rminus_x = strip_x + 6 * s + mode_w + 8 * s
        rects['RADIUS_MINUS'] = Rect(rminus_x, strip_y + 4 * s, btn_w, 28 * s)
        val_w = round(60 * s)
        rects['RADIUS_VALUE'] = Rect(rminus_x + btn_w + 2 * s, strip_y + 4 * s, val_w, 28 * s)
        rplus_x = rminus_x + btn_w + 2 * s + val_w + 2 * s
        rects['RADIUS_PLUS'] = Rect(rplus_x, strip_y + 4 * s, btn_w, 28 * s)
        reset_w = round(60 * s)
        rects['RESET'] = Rect(rplus_x + btn_w + 8 * s, strip_y + 4 * s, reset_w, 28 * s)
        return rects

    def enable_shaping(self, context):
        from . import garment
        from .cloth_shaping import ShapingSession
        simulations = garment.generated(context.scene, 'simulation')
        if not simulations or simulations[0].hide_get():
            raise ValueError('Start a drape before shaping it.')
        if self.shaping is None or self.shaping.source != simulations[0]:
            self.shaping = ShapingSession(simulations[0])
        if not self.choose_tool('SHAPE'):
            return
        if self.full:
            self.reveal_3d()
        self.card_kind = None
        self.shape_mode = getattr(self, 'shape_mode', 'PULL')
        self.pending_release = False
        self.release_frame = None
        self._window.cursor_modal_set('HAND')
        self.shape_cursor = 'HAND'
        space = self._area.spaces.active
        view = space.region_3d
        if view.view_distance > 3.0:
            from mathutils import Quaternion
            view.view_rotation = Quaternion((1, 0, 0), 1.5707963267948966)
            view.view_perspective = 'ORTHO'
            self.frame_cloth(context)
        recovery = context.scene.get('dd_shaping_recovery')
        self.message = recovery or 'Use on a settled drape. Drag with Pull or Push. Wheel changes radius. Live retention is not supported.'
        if recovery:
            del context.scene['dd_shaping_recovery']

    def end_shaping(self):
        from .cloth_shaping import Phase
        from . import garment
        try:
            if self.shaping is not None and (self.shaping.phase == Phase.HELD or getattr(self, 'pending_release', False)):
                garment.stop(bpy.context)
                with bpy.context.temp_override(scene=self._scene, view_layer=self._scene.view_layers[0]):
                    try:
                        self.shaping.cancel(bpy.context)
                    except ValueError as failure:
                        self.message = str(failure)
        finally:
            self.pending_release = False
            self.release_frame = None
            self.shape_save_pending = False
            if self.shape_cursor is not None:
                self._window.cursor_modal_restore()
            self.shape_cursor = None
            self.shape_start = None
            self.shape_hover = None

    def shaping_menu(self):
        def draw(menu, context):
            menu.layout.operator('devil_designer.shape_cloth', text='Shape cloth')
            menu.layout.operator('devil_designer.reset_shaping', text='Reset shaping')
            if self.tool == 'SHAPE':
                menu.layout.operator('devil_designer.shape_cloth', text='Done shaping').finish = True
                menu.layout.label(text=f'Radius {self.shaping.radius * 1000:.0f} mm | change with wheel')
                menu.layout.label(text='Normal push / pull on a settled drape')
        bpy.context.window_manager.popup_menu(draw, title='Draped cloth')

    def shaping_event(self, context, event, panel):
        from . import garment
        from .cloth_shaping import Phase, ShapingSession
        from bpy_extras import view3d_utils
        import math
        press = event.value == 'PRESS'
        if self.tool != 'SHAPE':
            if not panel and press and event.type == 'RIGHTMOUSE':
                simulations = garment.generated(context.scene, 'simulation')
                if simulations and not simulations[0].hide_get():
                    probe = ShapingSession(simulations[0])
                    view = self._area.spaces.active.region_3d
                    origin = view3d_utils.region_2d_to_origin_3d(self._region, view, self.pointer)
                    direction = view3d_utils.region_2d_to_vector_3d(self._region, view, self.pointer)
                    if probe.pick(context, origin, direction) is not None:
                        self.shaping_menu()
                        return {'RUNNING_MODAL'}
            return None
        session = self.shaping
        self.shaping_strip_rects = self.shaping_controls_layout()
        self._area.tag_redraw()
        if press and event.ctrl and event.type == 'S':
            if self.pending_release:
                self.shape_save_pending = True
                self.message = 'Applying fold before saving...'
                return {'RUNNING_MODAL'}
            if session.phase == Phase.HELD:
                self.message = 'Release the cloth before saving.'
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}
        if event.type == 'MIDDLEMOUSE' or event.alt:
            return {'PASS_THROUGH'}
        if press and not event.ctrl and not event.alt and event.type in {'S', 'H', 'L'}:
            if event.type == 'H':
                self._scene.dd_reference_visible = not self._scene.dd_reference_visible
            elif event.type == 'S':
                self.snap = not self.snap
            elif event.type == 'L':
                self._scene.dd_lengths_visible = not self._scene.dd_lengths_visible
            return {'RUNNING_MODAL'}
        if press and not event.ctrl and not event.alt and event.type in {'V', 'P', 'R', 'E', 'I', 'D', 'J', 'K', 'T', 'N'}:
            tool_name = {'V': 'SELECT', 'P': 'POLYGON', 'R': 'RECTANGLE', 'E': 'ELLIPSE',
                         'I': 'INTERNAL', 'D': 'DART', 'J': 'SEW', 'K': 'PIN', 'T': 'TACK', 'N': 'KNIFE'}[event.type]
            self.choose_tool(tool_name)
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type in {'Z', 'Y'}:
            self.choose_tool('SELECT')
            return None
        if self.card_kind:
            return self.minimal_event(context, event) or {'RUNNING_MODAL'}
        if session.phase == Phase.BLOCKED:
            if session.message:
                self.message = session.message
            self.pending_release = False
            self.release_frame = None
            self.shape_save_pending = False
            self.shape_start = None
            self._window.cursor_modal_set('HAND')
            self.shape_cursor = 'HAND'
        if press and event.type in {'ESC', 'RIGHTMOUSE'}:
            if session.phase == Phase.HELD or getattr(self, 'pending_release', False):
                garment.stop(context)
                session.cancel(context)
                self.pending_release = False
                self.release_frame = None
                self.shape_start = None
                self.message = session.message
                self._window.cursor_modal_set('HAND')
                self.shape_cursor = 'HAND'
            elif event.type == 'ESC':
                self.choose_tool('SELECT')
            else:
                self.shaping_menu()
            return {'RUNNING_MODAL'}
        if event.type == 'TIMER':
            if getattr(self, 'pending_release', False) and context.scene.frame_current >= (self.release_frame or 0):
                session.release(context)
                self.pending_release = False
                self.release_frame = None
                self.shape_start = None
                self.message = session.message
                self._window.cursor_modal_set('HAND')
                self.shape_cursor = 'HAND'
                if self.shape_save_pending:
                    self.shape_save_pending = False
                    bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')
            elif session.phase == Phase.BLOCKED and session.message:
                self.message = session.message
            return {'RUNNING_MODAL'}
        if self.pending_release:
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and session.phase == Phase.HELD:
            self._window.cursor_modal_set('HAND')
            self.shape_cursor = 'HAND'
            if context.scene.frame_current >= (self.release_frame or 0):
                session.release(context)
                self.pending_release = False
                self.release_frame = None
                self.shape_start = None
                self.message = session.message
            else:
                self.pending_release = True
                self.message = 'Applying fold...'
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and session.phase == Phase.HELD:
            units = garment.metres_per_unit(context.scene)
            dx = self.pointer[0] - self.shape_start[0]
            dy = self.pointer[1] - self.shape_start[1]
            dist = math.hypot(dx, dy)
            sign = 1.0 if getattr(self, 'shape_mode', 'PULL') == 'PULL' else -1.0
            session.update(context, sign * dist * .0002 / units)
            self.release_frame = context.scene.frame_current + 10
            self.message = session.message
            self._area.tag_redraw()
            return {'RUNNING_MODAL'}
        if press and event.type == 'LEFTMOUSE' and session.phase != Phase.HELD and not getattr(self, 'pending_release', False):
            strip_rects = getattr(self, 'shaping_strip_rects', {})
            if strip_rects.get('MODE_TOGGLE', Rect(0, 0, 0, 0)).contains(*self.pointer):
                self.shape_mode = 'PUSH' if getattr(self, 'shape_mode', 'PULL') == 'PULL' else 'PULL'
                self.message = f'Shape mode: {self.shape_mode}'
                return {'RUNNING_MODAL'}
            if strip_rects.get('RADIUS_MINUS', Rect(0, 0, 0, 0)).contains(*self.pointer):
                session.radius = max(0.015, min(0.15, session.radius / 1.15))
                self.message = f'Shape radius {session.radius * 1000:.0f} mm'
                return {'RUNNING_MODAL'}
            if strip_rects.get('RADIUS_PLUS', Rect(0, 0, 0, 0)).contains(*self.pointer):
                session.radius = max(0.015, min(0.15, session.radius * 1.15))
                self.message = f'Shape radius {session.radius * 1000:.0f} mm'
                return {'RUNNING_MODAL'}
            if strip_rects.get('RESET', Rect(0, 0, 0, 0)).contains(*self.pointer):
                bpy.ops.devil_designer.reset_shaping()
                return {'RUNNING_MODAL'}
            if strip_rects.get('STRIP_BOUNDS', Rect(0, 0, 0, 0)).contains(*self.pointer):
                return {'RUNNING_MODAL'}
        if panel and session.phase != Phase.HELD:
            if press and event.type == 'LEFTMOUSE':
                button = self.canvas_layout.button(*self.pointer)
                if button and button not in {'SHAPE', 'KEEP', 'KEEP_OPTIONS', 'SIMULATE', 'SIMULATE_OPTIONS', 'CLOSE'}:
                    self.choose_tool('SELECT')
            return None
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            if session.phase != Phase.HELD and not getattr(self, 'pending_release', False):
                session.radius = max(.015, min(.15, session.radius * (1.1 if event.type == 'WHEELUPMOUSE' else 1 / 1.1)))
                self.message = f'Shape radius {session.radius * 1000:.0f} mm'
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and press and not panel and not getattr(self, 'pending_release', False):
            if not self.shaping_view_bounds().contains(*self.pointer) or event.ctrl or event.shift:
                return {'PASS_THROUGH'}
            view = self._area.spaces.active.region_3d
            origin = view3d_utils.region_2d_to_origin_3d(self._region, view, self.pointer)
            direction = view3d_utils.region_2d_to_vector_3d(self._region, view, self.pointer)
            center = session.pick(context, origin, direction)
            try:
                session.begin(context, center)
            except ValueError as failure:
                self.message = str(failure)
                session.message = self.message
                self._window.cursor_modal_set('HAND')
                self.shape_cursor = 'HAND'
                return {'RUNNING_MODAL'}
            self.shape_start = self.pointer
            self.release_frame = context.scene.frame_current + 10
            self._window.cursor_modal_set('HAND_CLOSED')
            self.shape_cursor = 'HAND_CLOSED'
            self.message = session.message
            garment.start_playback(context)
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and not panel:
            from .cloth_shaping import points
            from mathutils import Vector
            self.shape_hover = None
            view = self._area.spaces.active.region_3d
            origin = view3d_utils.region_2d_to_origin_3d(self._region, view, self.pointer)
            direction = view3d_utils.region_2d_to_vector_3d(self._region, view, self.pointer)
            center = session.pick(context, origin, direction)
            if center is not None:
                point = session.source.matrix_world @ points(session.source)[center]
                units = garment.metres_per_unit(context.scene)
                offset = view.view_rotation @ Vector((session.radius / units, 0, 0))
                first = view3d_utils.location_3d_to_region_2d(self._region, view, point)
                second = view3d_utils.location_3d_to_region_2d(self._region, view, point + offset)
                if first is not None and second is not None:
                    self.shape_hover = (tuple(first), (second - first).length)
            return {'RUNNING_MODAL'}

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
        self.avatar_field.close()
        self.avatar_field.release_surface()
        self.save_window()
        self._closed = True
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
