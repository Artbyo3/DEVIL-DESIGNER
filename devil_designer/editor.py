import math
import bpy
from .core import Document, Session, Vertex
from . import curves
from .canvas import Layout, View, Rect
from .interaction import OverlayControls
from .minimal import MinimalCards, minimal_layout
from .design_tools import DesignTools
from .silhouette import BodyReference, torso_alignment, VIEWS
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
        self.stage = 'DRAFT'
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
        self.fit_overlay = FitOverlay(self)
        from .state_display import StateOverlay
        self.state_overlay = StateOverlay(self)
        from .viewport_sewing import ViewportSewing
        self.seam_hover = None
        self.viewport_sewing = ViewportSewing(self)
        self.canvas_layout = self.make_layout()
        self.refresh_controls()
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

    def set_stage(self, stage):
        if self.draft or self.gesture:
            self.message = "Finish or cancel the current draft before changing stages."
            return False
        stage_to_tab = {
            'DRAFT': 'DESIGN',
            'SEW': 'SEW',
            'ARRANGE': 'AVATAR',
            'SIMULATE': 'CLOTH',
            'LIBRARY': 'LIBRARY'
        }
        self.stage = stage
        self.inspector_tab = stage_to_tab.get(stage, 'DESIGN')
        if stage == 'DRAFT':
            if self.tool not in {'SELECT', 'POLYGON', 'RECTANGLE', 'ELLIPSE', 'INTERNAL', 'DART'}:
                self.choose_tool('SELECT')
        elif stage == 'SEW':
            self.choose_tool('SEW')
        elif stage == 'ARRANGE':
            if self.tool not in {'SELECT', 'PLACE', 'PIN', 'TACK'}:
                self.choose_tool('SELECT')
        elif stage == 'SIMULATE':
            self.choose_tool('SELECT')
        elif stage == 'LIBRARY':
            self.choose_tool('SELECT')
            self.refresh_library()
        self.canvas_layout = self.make_layout()
        self.refresh_controls()
        self.message = {
            'DRAFT': "Drafting workspace. Reshape, add points, or draw pieces.",
            'SEW': "Sewing workspace. Pair edges to create seams before arranging.",
            'ARRANGE': "Arrangement workspace. Position panels in 3D around the avatar.",
            'SIMULATE': "Simulation workspace. Drape clothing with Blender cloth physics.",
            'LIBRARY': "Library workspace. Save and load editable garments."
        }.get(stage, "Ready.")
        return True

    def advance_stage(self):
        if self.draft or self.gesture:
            self.message = 'Finish or cancel the current draft before continuing.'
            return
        if not self.session.document.patterns:
            self.set_stage('DRAFT')
            self.choose_tool('RECTANGLE')
            self.message = 'Drag across the canvas to draw your first rectangle.'
            return
        if self.stage == 'DRAFT':
            self.set_stage('SEW')
        elif self.stage == 'SEW':
            if self.workflow_action('BUILD'):
                self.set_stage('ARRANGE')
        elif self.stage == 'ARRANGE':
            self.set_stage('SIMULATE')
        elif self.stage == 'SIMULATE':
            if bpy.context.screen.is_animation_playing:
                self.workflow_action('STOP')
            else:
                self.workflow_action('SIMULATE')
        elif self.stage == 'LIBRARY':
            self.design_action('LIBRARY_SAVE')

    def workflow_guidance(self):
        if self.draft or self.gesture:
            return 'Finish or cancel your draft before continuing.', 'Finish draft', False
        if not self.session.document.patterns:
            return 'Start with a rectangle or use a template on the canvas.', 'Draw rectangle', True
        if self.stage == 'SIMULATE' and self._scene.dd_avatar is None:
            return 'Choose an avatar body in Arrange before starting the drape.', 'Choose body first', False
        return {
            'DRAFT': ('1 / 4  Draw and refine pieces, then pair their edges.', 'Next: Sew', True),
            'SEW': ('2 / 4  Pair edges. Unsewn pieces can continue too.', 'Build & arrange', True),
            'ARRANGE': ('3 / 4  Choose a body; position panels in the 3D viewport.', 'Next: Simulate', True),
            'SIMULATE': ('4 / 4  Simulate, stop at the desired frame, then Keep mesh.',
                         'Pause drape' if bpy.context.screen.is_animation_playing else 'Start drape', True),
            'LIBRARY': ('Save this editable garment to your library.', 'Save garment', True),
        }[self.stage]

    def workspace_hint(self):
        if self.confirm_action:
            return self.confirm_message
        if self.draft:
            return 'Drawing in progress. Finish to keep it, or cancel. Your other pieces stay editable.'
        if self.pending_place or self.pending_tack:
            return 'Pick a target in the 3D viewport. Escape cancels.'
        if self.tool == 'SEW':
            return f'Sew directly: pick an edge and its partner. {len(self.session.document.seams)} sewing pairs.'
        return 'Draw panels. Sew edges. Simulate. Right-click for local controls.'

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
        scale = max(.5, bpy.context.preferences.system.ui_scale)
        position = tuple(v * scale for v in self.window_rect) if self.window_rect else None
        stage = getattr(self, 'stage', 'DRAFT')
        layout = Layout(region.width, region.height, scale, self.full, max(0, left), max(0, right), top, bottom,
                      position=position, settings=self.settings_open, stage=stage,
                      pending=bool(self.draft), confirmation=bool(self.confirm_action),
                      playing=bpy.context.screen.is_animation_playing, advanced=self.advanced_tools)
        if self.minimal_ui:
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

    def align_reference(self):
        points = self.reference_pattern_points()
        if not self.reference.bounds:
            self.message = 'Choose an avatar body before aligning its silhouette.'
            return
        x, y = torso_alignment(self.reference.bounds, points)
        self._scene.dd_reference_x, self._scene.dd_reference_y = x, y
        self._scene.dd_reference_placed = True
        self.message = 'Body reference aligned to the pattern torso area.'

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
        if self.minimal_ui and points:
            left = max(canvas.x, layout.rail.x + layout.rail.w + 16 * layout.scale)
            right = canvas.x + canvas.w - 16 * layout.scale
            if right > left:
                fit_rect = Rect(left, canvas.y, right - left, canvas.h)
        self.view.fit(points, fit_rect)
        self.view.cx += (canvas.x + canvas.w / 2 - fit_rect.x - fit_rect.w / 2) / self.view.zoom
        self.view.cy += (canvas.y + canvas.h / 2 - fit_rect.y - fit_rect.h / 2) / self.view.zoom

    def reference_action(self, action):
        if action == 'REFERENCE_VIEW':
            current = VIEWS.index(self._scene.dd_reference_view)
            self._scene.dd_reference_view = VIEWS[(current + 1) % len(VIEWS)]
            self.update_reference(bpy.context)
        elif action == 'REFERENCE_ALIGN':
            self.align_reference()
        elif action == 'REFERENCE_FRAME':
            if self.reference.bounds:
                self._scene.dd_reference_visible = True
                self.view.fit(self.reference_corners(), self.canvas_layout.canvas)
                self.message = 'Framed the body at its real-world scale.'
            else:
                self.message = 'Choose an avatar body to display its silhouette.'
        elif action == 'REFERENCE_REFRESH':
            self.update_reference(bpy.context, force=True)
            self.message = self.reference.error or 'Body reference refreshed from the current evaluated mesh.'

    def choose_body(self, body, context):
        self._scene.dd_avatar = body
        if body is None:
            self.pending_simulation = False
        self.update_reference(context, align=True)
        if body:
            self.fit()
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
        self.refresh_controls()

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
        self.chain_a = []
        self.chain_b = []
        self.chain_stage = None
        self.free_clicks = []
        self.dart_base = []
        self.pending_place = self.pending_tack = None
        self.pending_simulation = False
        self.numeric = None
        self.setting_drag = None

    def choose_tool(self, name):
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
            self.chain_stage = None
            self.chain_a = []
            self.chain_b = []
            self.free_clicks = []
        if name == 'SEW':
            self._scene.dd_free_sewing = free
        self.pending_place = self.pending_tack = None
        if name != 'SEW':
            self.chain_stage = None
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
        section = 'SEW' if name == 'SEW' else 'AVATAR' if name in {'PLACE', 'PIN', 'TACK'} else 'DESIGN'
        self.inspector_tab = section
        self.sidebar_sections = [section]
        self.inspector_scroll = 0
        self.search_query = ''
        self.search_active = False
        self.refresh_controls()
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
        if button in {'BUILD', 'ARRANGE', 'SIMULATE'} and not self.session.document.patterns:
            return 'Create a pattern before building or simulating clothing.'
        if button == 'ARRANGE' and self._scene.dd_avatar is None:
            return 'Choose an avatar in Body & placement first, or search for Avatar body.'
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
                if self.minimal_ui:
                    self.show_card('BODY')
                    self.message = 'Choose the body. Simulation will start automatically.'
                    return False
                self.open_context('AVATAR', select=False)
                self.body_open = True
                self.refresh_controls()
                self.message = 'Choose the body once. Simulation will start automatically.'
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
        names = {'BUILD': 'build_panels', 'ARRANGE': 'arrange', 'SIMULATE': 'simulate',
                 'STOP': 'stop', 'RESET': 'reset', 'KEEP': 'keep_drape', 'DEMO': 'demo'}
        try:
            if button == 'SIMULATE':
                from . import tack_binding
                self.session.commit(lambda: tack_binding.migrate_anchors(bpy.context, self.session.document))
                self.persist()
            if button == 'ARRANGE':
                self.show_card('ARRANGEMENT')
                self.message = 'Choose a named starting layout; adjust placements before simulation.'
                return True
            op = getattr(bpy.ops.devil_designer, names[button])
            result = op('EXEC_DEFAULT')
            if 'FINISHED' in result:
                if self._scene.dd_document != self._stored:
                    self.reconcile_generated_document()
                if button == 'DEMO':
                    self.update_reference(bpy.context, align=True)
                    self.fit()
                if button == 'SIMULATE':
                    self.settings_open = False
                    self.choose_tool('SELECT')
                    self.reveal_3d()
                self.message = {'DEMO': 'Sewing demo ready. Simulate to drape the bodice around the torso.',
                                'BUILD': 'Panels ready. Use G / R in the 3D scene to arrange them.',
                                'ARRANGE': 'Panels arranged around the body. Adjust placement before simulation.',
                                'SIMULATE': 'Simulation running. Stop on the frame you want to keep.',
                                'STOP': 'Simulation paused. Keep mesh saves the current shape.',
                                'RESET': 'Restored the positioned panels. Edit or arrange, then simulate again.',
                                'KEEP': 'Draped mesh kept. Check the Blender report for any open seam pairs.'}[button]
                if button in {'BUILD','SIMULATE'} and self._scene.get('dd_arrangement_message'):
                    self.message+=' '+self._scene['dd_arrangement_message']
                return True
            self.message = 'Action could not finish. Check the Blender report and try again.'
        except (RuntimeError, ValueError) as exc:
            self.message = str(exc).replace('Error: ', '').strip()
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
            self.refresh_controls()
            self.renderer.draw(self)
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
        self.refresh_controls()
        self.pointer = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        panel = self.canvas_layout.panel.contains(*self.pointer)
        canvas = self.canvas_layout.canvas.contains(*self.pointer)
        sewing_result = self.viewport_sewing.event(context, event, panel, canvas)
        if sewing_result is not None:
            return sewing_result
        if not panel and self.tool != 'SEW' and not self.pending_tack and not self.pending_place:
            from .arrangement_controls import point_event
            try:arrangement_result=point_event(context,event)
            except ValueError as failure:
                self.message=str(failure)
                return {'RUNNING_MODAL'}
            if arrangement_result is not None:return arrangement_result
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
        if self.minimal_ui and press and event.type in {'ESC', 'RIGHTMOUSE'} and (self.pending_place or self.pending_tack):
            return self.design_pending_event(context, event, panel)
        if self.confirm_action:
            if press and event.type == 'ESC':
                self.perform_action('CANCEL_ACTION')
                return {'RUNNING_MODAL'}
            if press and event.type == 'LEFTMOUSE':
                action = self.canvas_layout.button(*self.pointer)
                if action in {'CONFIRM_ACTION', 'CANCEL_ACTION', 'STOP'}:
                    self.perform_action(action)
                    return {'RUNNING_MODAL'}
            if press and event.ctrl and event.type in {'Z', 'Y'}:
                redo = event.type == 'Y' or event.shift
                self.perform_action('REDO' if redo else 'UNDO')
                return {'RUNNING_MODAL'}
            if press and event.ctrl and event.type == 'S':
                return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}
        if self.minimal_ui:
            result = self.minimal_event(context, event)
            if result is not None:
                return result
        if not self.minimal_ui and (self.context_anchor is not None or self.setting_drag):
            result = self.controls_event(context, event)
            if result is not None:
                return result
            result = self.search_event(event)
            if result is not None:
                return result
            return {'RUNNING_MODAL'}
        if not self.minimal_ui and not self.numeric and not self.gesture:
            result = self.search_event(event)
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
        if not self.minimal_ui and not self.gesture:
            result = self.controls_event(context, event)
            if result is not None:
                return result
        if event.ctrl and event.type == 'S':
            return {'PASS_THROUGH'}
        if self.gesture and self.gesture.get('mode') == 'DRAFT_POINT':
            if event.type not in {'MOUSEMOVE', 'LEFTMOUSE'} or (event.type == 'LEFTMOUSE' and press):
                self.gesture = None
        if self.gesture:
            mode = self.gesture['mode']
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
                    if 'points' in self.gesture:
                        self.preview = [(x + dx, y + dy) if self.session.corner is None or i == self.session.corner
                                        else (x, y) for i, (x, y) in enumerate(self.gesture['points'])]
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
                            self.run_edit(lambda: self.session.move_selection(dx, dy), "Pattern updated.")
                    elif self.preview:
                        self.run_edit(lambda: self.session.move(self.preview), "Pattern updated.")
                    else:
                        pending = self.gesture.get('pending_single_select')
                        if pending and not event.shift:
                            if pending[0] == 'POINT':
                                self.session.select_point(pending[1], pending[2], pending[3], toggle=False)
                            elif pending[0] == 'PIECE':
                                self.session.select_piece(pending[1], toggle=False)
                            self.sync_selection()
                elif mode == 'BOX_SELECT':
                    if math.dist(self.gesture['start'], self.pointer) < 4 * self.canvas_layout.scale:
                        if not self.gesture.get('shift'):
                            self.session.clear_selection()
                            self.sync_selection()
                            self.message = "Selection cleared."
                    else:
                        w0 = self.gesture['world_start']
                        w1 = self.view.world(self.pointer, self.canvas_layout.canvas)
                        kind, count = self.session.box_select(w0[0], w0[1], w1[0], w1[1], shift=self.gesture.get('shift', False))
                        self.sync_selection()
                        if kind == 'POINTS':
                            self.message = f"{count} points selected." if count != 1 else "1 point selected."
                        elif kind == 'PIECES':
                            self.message = f"{count} pieces selected." if count != 1 else "1 piece selected."
                        else:
                            self.message = "Selection cleared." if not self.gesture.get('shift') else "No items selected."
                self.gesture, self.preview, self.handle_preview = None, None, None
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}
        if press and event.type == 'F' and not event.ctrl and not event.alt and not self.numeric:
            self.fit_overlay.toggle()
            return {'RUNNING_MODAL'}
        if not panel:
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
        if press and event.type == 'LEFTMOUSE':
            button = self.canvas_layout.button(*self.pointer)
            if button:
                if button == 'CLOSE':
                    if self.draft or self.gesture:
                        self.cancel_gesture()
                    self.cleanup()
                    return {'FINISHED'}
                if button == 'STAGE_NEXT':
                    guidance, label, enabled = self.workflow_guidance()
                    if enabled:
                        self.advance_stage()
                    else:
                        self.message = guidance
                    return {'RUNNING_MODAL'}
                if button.startswith('STAGE_'):
                    st = {'STAGE_DRAFT': 'DRAFT', 'STAGE_SEW': 'SEW', 'STAGE_ARRANGE': 'ARRANGE', 'STAGE_SIMULATE': 'SIMULATE'}.get(button)
                    if st:
                        self.set_stage(st)
                    return {'RUNNING_MODAL'}
                if button == 'LIBRARY':
                    self.open_context('LIBRARY', select=False)
                    return {'RUNNING_MODAL'}
                if button == 'MORE_TOOLS':
                    self.advanced_tools = not self.advanced_tools
                    self.canvas_layout = self.make_layout()
                    self.refresh_controls()
                    return {'RUNNING_MODAL'}
                if button == 'SEARCH':
                    self.open_context(select=False)
                    self.search_active = True
                    self.canvas_layout = self.make_layout()
                    self.refresh_controls()
                    return {'RUNNING_MODAL'}
                if button in {'FINISH_DRAFT', 'CANCEL_DRAFT', 'CONFIRM_ACTION', 'CANCEL_ACTION'}:
                    self.perform_action(button)
                    return {'RUNNING_MODAL'}
                if button == 'VIEW_3D':
                    self.reveal_3d()
                    return {'RUNNING_MODAL'}
                if button in {'SETTINGS', 'INSPECTOR'}:
                    self.settings_open = not self.settings_open
                    self.canvas_layout = self.make_layout()
                    self.refresh_controls()
                    self.save_window()
                    return {'RUNNING_MODAL'}
                if button in {'SELECT', 'POLYGON', 'RECTANGLE', 'ELLIPSE', 'INTERNAL', 'SEW', 'PIN', 'TACK', 'DART', 'PLACE', 'FREE_SEW'}:
                    self.choose_tool(button)
                    return {'RUNNING_MODAL'}
                if button in {'BUILD', 'ARRANGE', 'SIMULATE', 'STOP', 'RESET', 'KEEP'}:
                    self.perform_action(button)
                    return {'RUNNING_MODAL'}
                if button in {'UNDO', 'REDO'}:
                    self.perform_action(button)
                    return {'RUNNING_MODAL'}
                if button == 'LENGTHS':
                    self._scene.dd_lengths_visible = not self._scene.dd_lengths_visible
                    return {'RUNNING_MODAL'}
                if button == 'REFERENCE':
                    self._scene.dd_reference_visible = not self._scene.dd_reference_visible
                    return {'RUNNING_MODAL'}
                if button == 'SNAP':
                    self.snap = not self.snap
                    return {'RUNNING_MODAL'}
                if button == 'FIT':
                    self.fit()
                    return {'RUNNING_MODAL'}
                if button == 'FULL':
                    if not self.minimal_ui:
                        self.toggle_full()
                    return {'RUNNING_MODAL'}
                if button == 'HELP':
                    self.show_card('HELP')
                    self.message = "Shortcuts: V select, P polygon, R rect, E ellipse, I internal, D dart, N cut, J sew, K pin, T tack, F fit map, Home fit design, S snap, Ctrl+Z undo, Ctrl+Shift+Z redo."
                    return {'RUNNING_MODAL'}
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
            if event.type in {'UP_ARROW', 'DOWN_ARROW', 'LEFT_ARROW', 'RIGHT_ARROW'}:
                if self.session.has_selection():
                    step = 0.10 if event.shift else 0.01
                    dx = step if event.type == 'RIGHT_ARROW' else (-step if event.type == 'LEFT_ARROW' else 0.0)
                    dy = step if event.type == 'UP_ARROW' else (-step if event.type == 'DOWN_ARROW' else 0.0)
                    self.run_edit(lambda: self.session.move_selection(dx, dy), "Selection nudged.")
                    return {'RUNNING_MODAL'}
            if event.type == 'H' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_H')
                return {'RUNNING_MODAL'}
            if event.type == 'V' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_V')
                return {'RUNNING_MODAL'}
            if event.type == 'R' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('ROTATE_CW')
                return {'RUNNING_MODAL'}
            if event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'}:
                self.perform_action('ROTATE_CW' if event.type == 'RIGHT_BRACKET' else 'ROTATE_CCW')
                return {'RUNNING_MODAL'}
        if not self.minimal_ui and event.type == 'TAB' and press:
            self.toggle_full()
            return {'RUNNING_MODAL'}
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
            if self.advanced_tools and not self.session.document.patterns and not self.draft and not self.gesture and not self.reference_corners():
                card1, card2 = self.canvas_layout.starters
                if card1.contains(*self.pointer):
                    self.workflow_action('DEMO')
                    return {'RUNNING_MODAL'}
                elif card2.contains(*self.pointer):
                    ref_bounds = self.reference.bounds
                    ref_h = (ref_bounds[1][1] - ref_bounds[0][1]) if ref_bounds else 0.0
                    ref_y = self._scene.dd_reference_y
                    ref_x = self._scene.dd_reference_x
                    base_y = (ref_y + max(0.20, ref_h * 0.50)) if ref_h > 0 else 0.0
                    base_x = ref_x if ref_h > 0 else 0.0
                    self.session.add([(base_x - 0.20, base_y), (base_x + 0.20, base_y),
                                      (base_x + 0.20, base_y + 0.45), (base_x - 0.20, base_y + 0.45)])
                    self.session.document.patterns[-1].name = "Front panel"
                    self.persist()
                    self.fit()
                    self.choose_tool('SELECT')
                    self.message = "Created basic 40 × 45 cm panel. Drag corners to reshape."
                    return {'RUNNING_MODAL'}
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
                p, corner = self.hit()
                if p is None:
                    if self.tool == 'SELECT':
                        self.gesture = dict(mode='BOX_SELECT', start=self.pointer,
                                            world_start=self.view.world(self.pointer, self.canvas_layout.canvas),
                                            shift=event.shift)
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
                    self.session.path = self.hit_path
                    self.session.segment = self.hit_segment
                    if self.hit_segment and not event.shift:
                        edge = self.hit_segment
                        a, b = self.session.document.edge_vertices(edge)
                        ctrl = self.session.document.edge_curve(edge)
                        click_w = self.view.world(self.pointer, self.canvas_layout.canvas)
                        t_frac, _ = curves.closest_fraction(ctrl, click_w)
                        t0 = max(0.15, min(0.85, curves.parameter(ctrl, t_frac)))
                        p_orig = curves.evaluate(ctrl, t0)
                        self.gesture = dict(
                            mode='EDGE_BEND', edge=edge, start=click_w, t0=t0, p_orig=p_orig,
                            orig_c1=ctrl[1], orig_c2=ctrl[2], anchor_a=(a.x, a.y), anchor_b=(b.x, b.y),
                            moved=False, new_outgoing=a.outgoing, new_incoming=b.incoming
                        )
                        self.session.selected = p.id
                        self.session.selected_patterns = {p.id}
                        self.session.selected_points.clear()
                        self.session.corner = None
                        self.session.point_selection = []
                        self.sync_selection()
                        return {'RUNNING_MODAL'}
                    if event.shift:
                        self.session.select_piece(p.id, toggle=True)
                        self.sync_selection()
                        self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False)
                    else:
                        if p.id in self.session.selected_patterns and not self.session.selected_points:
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False,
                                                pending_single_select=('PIECE', p.id))
                        else:
                            self.session.select_piece(p.id, toggle=False)
                            self.sync_selection()
                            self.gesture = dict(mode='MOVE', start=cursor_world, ref_pos=cursor_world, delta=(0.0, 0.0), moved=False)
        return {'RUNNING_MODAL'}

    def cleanup(self):
        global _active
        if self._closed:
            return
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
