"""Modal overlay lifecycle and input. The native 3D scene stays interactive."""
import math
import bpy
from .core import Document, Session, contains, validate_polygon
from .canvas import Layout, View
from .interaction import OverlayControls

_active = None


def close_active():
    if _active is not None:
        _active.cleanup()


class DD_OT_pattern_editor(OverlayControls,bpy.types.Operator):
    bl_idname = "devil_designer.pattern_editor"
    bl_label = "Devil Designer"
    bl_description = "Open a dedicated 2D pattern canvas beside the 3D scene"
    # Documents use their own transaction history while this overlay has focus.
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
            return {'CANCELLED'}
        self._stored = self._scene.dd_document
        self.initialize_controls()
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
        position=tuple(v*scale for v in self.window_rect) if self.window_rect else None
        return Layout(region.width, region.height, scale, self.full, max(0, left), max(0, right), top, bottom,
                      position=position,settings=self.settings_open)

    def fit(self):
        self.view.fit([p for pat in self.session.document.patterns for p in pat.points], self.canvas_layout.canvas)

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
            return True
        except ValueError as exc:
            self.message = str(exc)
            return False

    def cancel_gesture(self):
        self.gesture = None
        self.preview = None
        self.draft = []
        self.pending_edge = None

    def choose_tool(self, name):
        self.cancel_gesture()
        self.tool = name
        self.session.corner = None
        self.message = {'SELECT': "Drag a corner to reshape, or drag inside a piece to move it.",
                        'POLYGON': "Click corners. Click the first corner or press Enter to close.",
                        'RECTANGLE': "Drag on the canvas to create a rectangular pattern.",
                        'SEW': "Click an edge, then its partner. Select a seam: B reverses it, X removes it."}[name]

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
        pats = list(reversed(self.session.document.patterns))
        for p in pats:
            for i, point in enumerate(p.points):
                if math.dist(self.view.screen(point, self.canvas_layout.canvas), self.pointer) <= 9 * self.canvas_layout.scale:
                    return p, i
        world = self.view.world(self.pointer, self.canvas_layout.canvas)
        for p in pats:
            if contains(world, p.points):
                return p, None
        return None, None

    def hit_edge(self):
        best,nearest = None,11*self.canvas_layout.scale
        for pat in reversed(self.session.document.patterns):
            points = [self.view.screen(p,self.canvas_layout.canvas) for p in pat.points]
            for i,a in enumerate(points):
                b = points[(i+1)%len(points)]
                dx,dy = b[0]-a[0],b[1]-a[1]
                length = dx*dx+dy*dy
                t = max(0,min(1,((self.pointer[0]-a[0])*dx+(self.pointer[1]-a[1])*dy)/length)) if length else 0
                distance = math.dist(self.pointer,(a[0]+t*dx,a[1]+t*dy))
                if distance<nearest:
                    best,nearest = self.session.document.edge(pat.id,i),distance
        return best

    def sew_click(self):
        edge = self.hit_edge()
        if edge is None:
            self.message = "Click close to the pattern edge you want to sew."
            return
        if self.pending_edge is None:
            existing = next((s for s in self.session.document.seams if edge in (s.a,s.b)),None)
            self.seam_selected = existing.id if existing else None
            if existing:
                self.message = "Seam selected. B: reverse direction. X: remove seam."
            else:
                self.pending_edge = edge
                self.message = "First edge selected. Click its partner on another pattern."
            return
        a = self.pending_edge
        if self.run_edit(lambda: self.session.sew(a,edge),"Seam paired. B reverses the selected seam; X removes it."):
            self.pending_edge = None
            self.seam_selected = self.session.document.seams[-1].id

    def workflow_action(self,button):
        if self.draft or self.gesture:
            self.message = "Finish or cancel the current draft before building clothing."
            return
        names = {'BUILD':'build_panels','ARRANGE':'arrange','SIMULATE':'simulate',
                 'STOP':'stop','RESET':'reset','KEEP':'keep_drape','DEMO':'demo'}
        try:
            op = getattr(bpy.ops.devil_designer,names[button])
            result = op('EXEC_DEFAULT')
            if 'FINISHED' in result:
                if button=='DEMO':
                    self.session=Session(Document.loads(self._scene.dd_document))
                    self._stored=self._scene.dd_document
                    self.fit()
                self.message = {'DEMO':'Sewing demo ready. Simulate to drape the bodice around the torso.',
                                'BUILD':'Panels ready. Use G / R in the 3D scene to arrange them.',
                                'ARRANGE':'Panels arranged around the body. Adjust placement before simulation.',
                                'SIMULATE':'Simulation running. Stop on the frame you want to keep.',
                                'STOP':'Simulation paused. Keep mesh saves the current shape.',
                                'RESET':'Restored the positioned panels. Edit or arrange, then simulate again.',
                                'KEEP':'Draped mesh kept. Check the Blender report for any open seam pairs.'}[button]
        except RuntimeError as exc:
            self.message = str(exc).replace('Error: ','').strip()

    def finish_polygon(self):
        points = list(self.draft)
        if self.run_edit(lambda: self.session.add(points), "Pattern created. Press V to edit it, or draw another piece."):
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
            # Never leave a repeatedly failing GPU callback installed.
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
        # Closing/switching editors, files, scenes or windows cannot leave orphan handlers.
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
            return {'PASS_THROUGH'}
        self._area.tag_redraw()
        if press and event.ctrl and event.alt and event.type=='D':
            self.cleanup()
            return {'FINISHED'}
        if not self.gesture:
            result=self.controls_event(context,event)
            if result is not None:
                return result
        # File save and standard nonediting shortcuts still work while drawing.
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
                elif mode == 'RECT':
                    a = self.gesture['start']
                    b = self.world_pointer(event)
                    self.preview = [a, (b[0], a[1]), b, (a[0], b[1])]
                else:
                    target = self.world_pointer(event)
                    source = self.gesture['start']
                    dx, dy = target[0] - source[0], target[1] - source[1]
                    self.preview = [(x + dx, y + dy) if self.session.corner is None or i == self.session.corner
                                    else (x, y) for i, (x, y) in enumerate(self.gesture['points'])]
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE' and event.type == ('MIDDLEMOUSE' if mode == 'PAN' else 'LEFTMOUSE'):
                if mode == 'RECT' and self.preview:
                    self.run_edit(lambda: self.session.add(self.preview), "Rectangle created. Press V to edit its corners.")
                elif mode == 'MOVE' and self.preview:
                    self.run_edit(lambda: self.session.move(self.preview), "Pattern updated.")
                self.gesture, self.preview = None, None
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}
        if not panel:
            return {'PASS_THROUGH'}
        if event.type == 'ESC' and press:
            if self.draft or self.pending_edge:
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
                if button in {'SELECT', 'POLYGON', 'RECTANGLE', 'SEW'}:
                    self.choose_tool(button)
                elif button in {'BUILD','ARRANGE','SIMULATE','STOP','RESET','KEEP'}:
                    self.workflow_action(button)
                elif button in {'UNDO', 'REDO'}:
                    self.cancel_gesture()
                    self.run_edit(lambda: self.session.history(button == 'REDO'), 'Redo.' if button == 'REDO' else 'Undo.')
                elif button == 'SNAP':
                    self.snap = not self.snap
                elif button == 'FIT':
                    self.fit()
                elif button == 'FULL':
                    self.toggle_full()
                return {'RUNNING_MODAL'}
        if event.type == 'TAB' and press:
            self.toggle_full()
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type in {'Z', 'Y'}:
            self.cancel_gesture()
            redo = event.type == 'Y' or event.shift
            self.run_edit(lambda: self.session.history(redo), "Redo." if redo else "Undo.")
            return {'RUNNING_MODAL'}
        if press and event.type == 'S' and not event.ctrl:
            self.snap = not self.snap
            return {'RUNNING_MODAL'}
        if press and event.type in {'V', 'P', 'R', 'J'}:
            self.choose_tool({'V': 'SELECT', 'P': 'POLYGON', 'R': 'RECTANGLE', 'J':'SEW'}[event.type])
            return {'RUNNING_MODAL'}
        if press and event.type in {'HOME', 'F'}:
            self.fit()
            return {'RUNNING_MODAL'}
        if self.draft:
            if press and event.type in {'RET', 'NUMPAD_ENTER'}:
                self.finish_polygon()
            elif press and event.type == 'BACK_SPACE':
                self.draft.pop()
            elif press and event.type == 'RIGHTMOUSE':
                self.cancel_gesture()
                self.message = "Draft cancelled."
            elif event.type == 'MOUSEMOVE':
                self.preview = [self.world_pointer(event, self.draft[-1])]
        if self.tool=='SEW' and self.seam_selected and press and event.type=='B':
            self.run_edit(lambda: self.session.reverse_seam(self.seam_selected),'Seam direction reversed.')
            return {'RUNNING_MODAL'}
        if press and event.type in {'X', 'DEL'} and not self.draft:
            if self.tool=='SEW':
                if self.seam_selected:
                    self.run_edit(lambda: self.session.remove_seam(self.seam_selected),'Seam removed.')
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
            if self.tool == 'SEW':
                self.sew_click()
            elif self.tool == 'POLYGON':
                if len(self.draft) >= 3 and math.dist(self.pointer, self.view.screen(self.draft[0], self.canvas_layout.canvas)) < 12 * self.canvas_layout.scale:
                    self.finish_polygon()
                else:
                    point = self.world_pointer(event, self.draft[-1] if self.draft else None)
                    if not self.draft or math.dist(point, self.draft[-1]) > 1e-6:
                        self.draft.append(point)
                        self.preview = [point]
            elif self.tool == 'RECTANGLE':
                self.gesture = {'mode': 'RECT', 'start': self.world_pointer(event)}
            else:
                p, corner = self.hit()
                self.session.selected, self.session.corner = (p.id if p else None), corner
                if p:
                    self.gesture = {'mode': 'MOVE', 'start': self.world_pointer(event), 'points': p.points}
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
