"""Modal overlay lifecycle and input. The native 3D scene stays interactive."""
import math
import bpy
from .core import Document, Session, contains, validate_polygon
from .canvas import Layout, View
from .interaction import OverlayControls
from .design_tools import DesignTools
from .silhouette import BodyReference, torso_alignment, VIEWS

_active = None


def close_active():
    if _active is not None:
        _active.cleanup()


class DD_OT_pattern_editor(DesignTools, OverlayControls, bpy.types.Operator):
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
        self.stage = 'DRAFT'
        self.initialize_controls()
        self.initialize_design()
        self.reference = BodyReference()
        self.view = View()
        self.tool, self.snap, self.full = 'POLYGON', True, False
        self.draft, self.preview = [], None
        self.gesture = None
        self.pending_edge = self.seam_selected = None
        self.pointer = (0, 0)
        self.message = "Draw your first pattern. Click corners, then click the first corner to close."
        self._closed = False
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
        if self.draft:
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
        if self.stage == 'DRAFT':
            self.set_stage('SEW')
        elif self.stage == 'SEW':
            self.set_stage('ARRANGE')
            try:
                import bpy
                bpy.ops.devil_designer.build_panels('EXEC_DEFAULT')
            except Exception:
                pass
        elif self.stage == 'ARRANGE':
            self.set_stage('SIMULATE')
        elif self.stage == 'SIMULATE':
            if bpy.context.screen.is_animation_playing:
                self.workflow_action('STOP')
            else:
                self.workflow_action('SIMULATE')
        elif self.stage == 'LIBRARY':
            self.workflow_action('LIBRARY_SAVE')

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
        return Layout(region.width, region.height, scale, self.full, max(0, left), max(0, right), top, bottom,
                      position=position, settings=self.settings_open, stage=stage)

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
        self.view.fit(points + self.reference_corners(), self.canvas_layout.canvas)

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
        self.update_reference(context, align=True)
        if body:
            self.fit()

    def persist(self):
        value = self.session.document.dumps()
        self._scene.dd_document = value
        self._stored = value
        self.refresh_controls()

    def run_edit(self, action, message):
        try:
            changed = action()
            self.persist()
            self.message = message if changed is not False else "Nothing to change."
            if self.session.last_repairs:
                self.message += f" {self.session.last_repairs} affected sewing pair(s) removed; re-pair edited edges."
            return True
        except ValueError as exc:
            self.message = str(exc)
            return False

    def cancel_gesture(self):
        self.gesture = None
        self.preview = None
        self.draft = []
        self.pending_edge = None
        self.handle_preview = None

    def choose_tool(self, name):
        self.cancel_gesture()
        self.tool = name
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
                        'PLACE': 'Click to place the selected garment panel in 3D.',
                        'SEW': "Click an edge, then its partner. Select a seam: B reverses it, X removes it."}.get(name, "Ready.")

    def world_pointer(self, event, anchor=None):
        x, y = self.view.world(self.pointer, self.canvas_layout.canvas)
        if self.snap != event.ctrl:
            x, y = round(x / .01) * .01, round(y / .01) * .01
        if anchor is not None and event.shift and self.tool == 'POLYGON':
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

    def workflow_action(self, button):
        if self.draft or self.gesture:
            self.message = "Finish or cancel the current draft before building clothing."
            return
        names = {'BUILD': 'build_panels', 'ARRANGE': 'arrange', 'SIMULATE': 'simulate',
                 'STOP': 'stop', 'RESET': 'reset', 'KEEP': 'keep_drape', 'DEMO': 'demo'}
        try:
            op = getattr(bpy.ops.devil_designer, names[button])
            result = op('EXEC_DEFAULT')
            if 'FINISHED' in result:
                if self._scene.dd_document != self._stored:
                    self.session.document = Document.loads(self._scene.dd_document)
                    self._stored = self._scene.dd_document
                if button == 'DEMO':
                    self.update_reference(bpy.context, align=True)
                    self.fit()
                self.message = {'DEMO': 'Sewing demo ready. Simulate to drape the bodice around the torso.',
                                'BUILD': 'Panels ready. Use G / R in the 3D scene to arrange them.',
                                'ARRANGE': 'Panels arranged around the body. Adjust placement before simulation.',
                                'SIMULATE': 'Simulation running. Stop on the frame you want to keep.',
                                'STOP': 'Simulation paused. Keep mesh saves the current shape.',
                                'RESET': 'Restored the positioned panels. Edit or arrange, then simulate again.',
                                'KEEP': 'Draped mesh kept. Check the Blender report for any open seam pairs.'}[button]
        except RuntimeError as exc:
            self.message = str(exc).replace('Error: ', '').strip()

    def finish_polygon(self, closed=True):
        points = list(self.draft)
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
        except Exception as exc:
            print("Devil Designer drawing error:", exc)
            self.cleanup()

    def modal(self, context, event):
        if self._closed:
            return {'FINISHED'}
        try:
            return self.handle_event(context, event)
        except (ReferenceError, RuntimeError):
            self.cleanup()
            return {'CANCELLED'}
        except Exception as exc:
            self.report({'ERROR'}, "Pattern editor closed: " + str(exc))
            self.cleanup()
            return {'CANCELLED'}

    def handle_event(self, context, event):
        if (self._area not in list(self._window.screen.areas) or self._area.type != 'VIEW_3D'
                or self._window.scene != self._scene):
            self.cleanup()
            return {'FINISHED'}
        if self._scene.dd_document != self._stored:
            self.session = Session(Document.loads(self._scene.dd_document))
            self._stored = self._scene.dd_document
            self.cancel_gesture()
        self.canvas_layout = self.make_layout()
        self.refresh_controls()
        self.pointer = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        panel = self.canvas_layout.panel.contains(*self.pointer)
        canvas = self.canvas_layout.canvas.contains(*self.pointer)
        press = event.value == 'PRESS'
        if event.type == 'TIMER':
            if self.update_reference(context):
                self._area.tag_redraw()
            return {'PASS_THROUGH'}
        self._area.tag_redraw()
        result = self.design_pending_event(context, event, panel)
        if result is not None:
            return result
        if press and event.ctrl and event.alt and event.type == 'D':
            self.cleanup()
            return {'FINISHED'}
        if not self.gesture:
            result = self.controls_event(context, event)
            if result is not None:
                return result
        if event.ctrl and event.type == 'S':
            return {'PASS_THROUGH'}
        if self.gesture:
            mode = self.gesture['mode']
            if event.type in {'ESC', 'RIGHTMOUSE'} and press:
                self.gesture, self.preview = None, None
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
                elif mode == 'HANDLE':
                    target = self.view.world(self.pointer, self.canvas_layout.canvas)
                    self.handle_preview = (self.session.corner, self.gesture['handle'],
                        (target[0] - self.gesture['anchor'][0], target[1] - self.gesture['anchor'][1]))
                else:
                    target = self.world_pointer(event)
                    source = self.gesture['start']
                    dx, dy = target[0] - source[0], target[1] - source[1]
                    self.preview = [(x + dx, y + dy) if self.session.corner is None or i == self.session.corner
                                    else (x, y) for i, (x, y) in enumerate(self.gesture['points'])]
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE' and event.type == ('MIDDLEMOUSE' if mode == 'PAN' else 'LEFTMOUSE'):
                if mode == 'ELLIPSE' and self.preview:
                    self.run_edit(lambda: self.session.add_ellipse(self.preview[0], self.preview[2], self._scene.dd_internal_mode), 'Ellipse created.')
                elif mode == 'RECT' and self.preview:
                    action = (lambda: self.session.add_path(self.preview, True)) if self._scene.dd_internal_mode else (lambda: self.session.add(self.preview))
                    self.run_edit(action, 'Rectangle created.')
                elif mode == 'HANDLE' and self.handle_preview:
                    self.run_edit(lambda: self.session.set_handle(*self.handle_preview), 'Bezier handle updated.')
                elif mode == 'MOVE' and self.preview:
                    self.run_edit(lambda: self.session.move(self.preview), "Pattern updated.")
                self.gesture, self.preview, self.handle_preview = None, None, None
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}
        if not panel:
            return {'PASS_THROUGH'}
        if event.type == 'ESC' and press:
            if self.draft or self.pending_edge or self.free_clicks:
                self.cancel_gesture()
                self.message = "Draft cancelled."
                return {'RUNNING_MODAL'}
            self.cleanup()
            return {'FINISHED'}
        if press and event.type == 'LEFTMOUSE':
            button = self.canvas_layout.button(*self.pointer)
            if button:
                if button == 'CLOSE':
                    self.cleanup()
                    return {'FINISHED'}
                if button.startswith('STAGE_'):
                    st = {'STAGE_DRAFT': 'DRAFT', 'STAGE_SEW': 'SEW', 'STAGE_ARRANGE': 'ARRANGE', 'STAGE_SIMULATE': 'SIMULATE'}.get(button)
                    if st:
                        self.set_stage(st)
                    return {'RUNNING_MODAL'}
                if button == 'STAGE_NEXT':
                    self.advance_stage()
                    return {'RUNNING_MODAL'}
                if button == 'LIBRARY':
                    self.set_stage('LIBRARY')
                    return {'RUNNING_MODAL'}
                if button in {'SETTINGS', 'INSPECTOR'}:
                    self.settings_open = not self.settings_open
                    self.canvas_layout = self.make_layout()
                    self.refresh_controls()
                    self.save_window()
                    return {'RUNNING_MODAL'}
                if button in {'SELECT', 'POLYGON', 'RECTANGLE', 'ELLIPSE', 'INTERNAL', 'SEW', 'PIN', 'TACK', 'DART', 'PLACE', 'FREE_SEW'}:
                    self.choose_tool(button if button != 'FREE_SEW' else 'SEW')
                    if button == 'FREE_SEW':
                        self._scene.dd_free_sewing = True
                    return {'RUNNING_MODAL'}
                if button in {'BUILD', 'ARRANGE', 'SIMULATE', 'STOP', 'RESET', 'KEEP'}:
                    self.workflow_action(button)
                    return {'RUNNING_MODAL'}
                if button in {'UNDO', 'REDO'}:
                    self.cancel_gesture()
                    self.run_edit(lambda: self.session.history(button == 'REDO'), 'Redo.' if button == 'REDO' else 'Undo.')
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
                    self.toggle_full()
                    return {'RUNNING_MODAL'}
                if button == 'HELP':
                    self.message = "Shortcuts: V select, P polygon, R rect, E ellipse, I internal, D dart, J sew, K pin, T tack, F fit, S snap, Z undo."
                    return {'RUNNING_MODAL'}
                return {'RUNNING_MODAL'}
        if event.type == 'TAB' and press:
            self.toggle_full()
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type in {'Z', 'Y'}:
            self.cancel_gesture()
            redo = event.type == 'Y' or event.shift
            self.run_edit(lambda: self.session.history(redo), "Redo." if redo else "Undo.")
            return {'RUNNING_MODAL'}
        if press and event.type == 'H' and not event.ctrl:
            self._scene.dd_reference_visible = not self._scene.dd_reference_visible
            return {'RUNNING_MODAL'}
        if press and event.type == 'S' and not event.ctrl:
            self.snap = not self.snap
            return {'RUNNING_MODAL'}
        if press and event.type in {'V', 'P', 'R', 'J'}:
            self.choose_tool({'V': 'SELECT', 'P': 'POLYGON', 'R': 'RECTANGLE', 'J': 'SEW'}[event.type])
            return {'RUNNING_MODAL'}
        if press and event.type in {'HOME', 'F'}:
            self.fit()
            return {'RUNNING_MODAL'}
        if self.draft:
            if press and event.type in {'RET', 'NUMPAD_ENTER'}:
                self.finish_polygon(self.tool != 'INTERNAL')
            elif press and event.type == 'BACK_SPACE':
                self.draft.pop()
            elif press and event.type == 'RIGHTMOUSE':
                self.cancel_gesture()
                self.message = "Draft cancelled."
            elif event.type == 'MOUSEMOVE':
                self.preview = [self.world_pointer(event, self.draft[-1])]
        if self.tool == 'SEW' and self.seam_selected and press and event.type == 'B':
            self.run_edit(lambda: self.session.reverse_seam(self.seam_selected), 'Seam direction reversed.')
            return {'RUNNING_MODAL'}
        if press and event.type in {'X', 'DEL'} and not self.draft:
            if self.tool == 'SEW':
                if self.seam_selected:
                    self.run_edit(lambda: self.session.remove_seam(self.seam_selected), 'Seam removed.')
                    self.seam_selected = None
                self.pending_edge = None
                return {'RUNNING_MODAL'}
            self.run_edit(self.session.delete, "Selection deleted.")
            return {'RUNNING_MODAL'}
        if press and event.type == 'D' and event.shift and not self.draft:
            self.run_edit(self.session.duplicate, "Pattern duplicated.")
            return {'RUNNING_MODAL'}
        if not canvas:
            return {'RUNNING_MODAL'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self.view.zoom_at(self.pointer, self.canvas_layout.canvas, 1.15 if event.type == 'WHEELUPMOUSE' else 1 / 1.15)
            return {'RUNNING_MODAL'}
        if event.type == 'MIDDLEMOUSE' and press:
            self.gesture = {'mode': 'PAN', 'last': self.pointer}
        elif event.type == 'LEFTMOUSE' and press:
            # Interactive Empty Canvas Quick-Start Cards
            if not self.session.document.patterns and not self.draft and not self.gesture and not self.reference_corners():
                c = self.canvas_layout.canvas
                midx, midy = c.x + c.w / 2, c.y + c.h / 2
                s = self.canvas_layout.scale
                card1 = Rect(midx - 175 * s, midy - 25 * s, 170 * s, 44 * s)
                card2 = Rect(midx + 5 * s, midy - 25 * s, 170 * s, 44 * s)
                if card1.contains(*self.pointer):
                    self.workflow_action('DEMO')
                    return {'RUNNING_MODAL'}
                elif card2.contains(*self.pointer):
                    self.session.add([(-0.20, 0), (0.20, 0), (0.20, 0.45), (-0.20, 0.45)])
                    self.session.document.patterns[-1].name = "Front panel"
                    self.persist()
                    self.fit()
                    self.choose_tool('SELECT')
                    self.message = "Created basic 40 × 45 cm panel. Drag corners to reshape."
                    return {'RUNNING_MODAL'}
            if self.tool == 'SEW':
                self.sew_click()
            elif self.tool in {'POLYGON', 'INTERNAL'}:
                if self.tool == 'INTERNAL' and not self.draft and self.session.selected is None:
                    owner, _ = self.hit()
                    if owner:
                        self.session.selected = owner.id
                        self.session.path = 'OUTER'
                if len(self.draft) >= 3 and math.dist(self.pointer, self.view.screen(self.draft[0], self.canvas_layout.canvas)) < 12 * self.canvas_layout.scale:
                    self.finish_polygon(True)
                else:
                    point = self.world_pointer(event, self.draft[-1] if self.draft else None)
                    if not self.draft or math.dist(point, self.draft[-1]) > 1e-6:
                        self.draft.append(point)
                        self.preview = [point]
            elif self.tool in {'RECTANGLE', 'ELLIPSE'}:
                self.gesture = {'mode': 'RECT' if self.tool == 'RECTANGLE' else 'ELLIPSE', 'start': self.world_pointer(event)}
            elif self.tool in {'PIN', 'TACK', 'DART'}:
                try:
                    self.design_canvas_click(event)
                except ValueError as exc:
                    self.message = str(exc)
            else:
                p, corner = self.hit()
                if p is None or p.id != self.session.selected:
                    self.session.point_selection = []
                self.session.selected, self.session.corner = (p.id if p else None), corner
                self.session.path = self.hit_path
                self.session.segment = self.hit_segment
                if p:
                    if corner is not None and self.hit_handle:
                        v = p.path(self.session.path).vertices[corner]
                        self.gesture = dict(mode='HANDLE', handle=self.hit_handle, anchor=(v.x, v.y))
                    elif corner is not None and event.shift:
                        if corner in self.session.point_selection:
                            self.session.point_selection.remove(corner)
                        else:
                            self.session.point_selection.append(corner)
                    else:
                        self.session.point_selection = [corner] if corner is not None else []
                        self.gesture = dict(mode='MOVE', start=self.world_pointer(event), points=p.path(self.session.path).points)
                    if corner is not None:
                        edges = self.session.document.edges(p.id, self.session.path)
                        if edges:
                            self.session.segment = edges[min(corner, len(edges) - 1)]
                    self.sync_selection()
        return {'RUNNING_MODAL'}

    def cleanup(self):
        global _active
        if self._closed:
            return
        self.save_window()
        self._closed = True
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
