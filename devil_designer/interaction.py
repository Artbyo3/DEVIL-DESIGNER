import bpy
from .canvas import Rect
from .controls import Inspector, BodyMenu, SETTINGS
from .draw import PALETTE

RUNNING = {'RUNNING_MODAL'}


class OverlayControls:
    def initialize_controls(self):
        saved = tuple(self._scene.dd_ui_rect)
        self.window_rect = saved if saved[2] > 0 and saved[3] > 0 else None
        self.settings_open = False
        self.advanced_tools = False
        self.pending_simulation = False
        self.inspector_scroll = 0
        self.inspector_tab = 'DESIGN'
        self.inspector_sections = ['DESIGN']
        self.inspector_details = set()
        self.search_query = ''
        self.search_active = False
        self.confirm_action = None
        self.confirm_message = ''
        self.stage = 'DRAFT'
        self.inspector = None
        self.numeric = None
        self.window_gesture = None
        self.body_open = False
        self.body_offset = 0
        self.body_menu = None
        self.context_anchor = None
        self.setting_drag = None

    def open_context(self, section=None, select=True):
        if select:
            pattern, corner = self.hit()
            if pattern:
                if (self.session.selected != pattern.id or self.session.path != self.hit_path
                        or corner not in self.session.point_selection):
                    self.session.point_selection = [corner] if corner is not None else []
                self.session.selected = pattern.id
                self.session.path = self.hit_path
                self.session.corner = corner
                self.session.segment = self.hit_edge() if corner is None else None
                self.sync_selection()
            else:
                self.session.selected = None
                self.session.corner = self.session.segment = None
                self.session.point_selection = []
        self.context_anchor = self.pointer
        self.inspector_sections = [section] if section else []
        self.inspector_details = set(self.inspector_sections)
        self.inspector_scroll = 0
        self.search_query = ''
        self.search_active = False
        self.refresh_library()
        self.refresh_controls()
        self.message = 'Controls at your cursor. Drag numeric values; click to type. Click outside to close.'

    def close_context(self):
        self.context_anchor = None
        self.search_active = False
        self.search_query = ''
        self.body_open = False
        self.refresh_controls()

    def local_control_rows(self):
        rows = []
        if self.tool == 'SEW':
            if self.chain_stage:
                rows.append(('button', 'CHAIN_B' if self.chain_stage == 'A' else 'CHAIN_SEW',
                             'Continue to side B' if self.chain_stage == 'A' else 'Sew these chains'))
            if self.seam_selected:
                rows.extend(('seam', seam.id, 'Selected') for seam in self.session.document.seams
                            if seam.id == self.seam_selected)
            rows.append(('button', 'CANCEL_DRAFT', 'Cancel pending sewing'))
            actions = [('SEW', 'Pair edges'), ('FREE_SEW', 'Pick sewing range on edges'),
                       ('CHAIN_A', 'Collect side A'), ('CHAIN_B', 'Collect side B'),
                       ('CHAIN_SEW', 'Sew chains'), ('CHAIN_CLEAR', 'Clear pending sewing')]
            rows.extend(('button', key, label) for key, label in actions)
        elif self.session.selected:
            if self.session.corner is not None:
                rows.extend([('button', 'CURVE', 'Corner / curve'),
                             ('number', 'dd_point_x', ''), ('number', 'dd_point_y', '')])
            elif self.session.segment:
                rows.extend([('button', 'SPLIT', 'Split this edge'),
                             ('number', 'dd_segment_length', ''),
                             ('button', 'UNFOLD', 'Unfold across this edge'),
                             ('button', 'MIRROR_SEW', 'Mirror and sew this edge')])
            rows.extend([('preset_chips', 'PRESET_CHIP', ''),
                         ('pair_buttons', 'DUPLICATE', 'DELETE', 'Duplicate', 'Delete'),
                         ('pair_buttons', 'PLACE', 'PIN', 'Place in 3D', 'Pin'),
                         ('pair_buttons', 'TACK', 'WRAP', 'Tack to body', 'Wrap'),
                         ('pair_buttons', 'CUT', 'TRACE', 'Cut internal path', 'Trace as piece')])
        else:
            rows.extend(('button', key, label) for key, label in (
                ('RECTANGLE', 'Draw panel'), ('POLYGON', 'Draw polygon'),
                ('ELLIPSE', 'Draw ellipse'), ('INTERNAL', 'Draw internal path'),
                ('DART', 'Draw dart'), ('SEW', 'Sew edges')))
        rows.extend([('pair_buttons', 'SIMULATE', 'STOP', 'Simulate / pause', 'Stop'),
                     ('pair_buttons', 'KEEP', 'RESET', 'Keep mesh', 'Reset'),
                     ('pair_buttons', 'SNAP', 'LENGTHS', 'Snap', 'Measurements'),
                     ('pair_buttons', 'UNDO', 'REDO', 'Undo', 'Redo')])
        return rows

    def selection_context(self):
        ctx = {}
        if not hasattr(self, 'session'):
            return ctx
        if self.session.selected:
            pat = self.session.document.find(self.session.selected)
            if pat:
                ctx['selection_kind'] = 'PATTERN'
                ctx['pattern_name'] = pat.name
                ctx['meta'] = f"{len(pat.points)} points · {pat.preset.title()}"
                idx = next((i for i, p in enumerate(self.session.document.patterns) if p.id == pat.id), 0)
                ctx['swatch'] = PALETTE[idx % len(PALETTE)]
                xs = [pt[0] for pt in pat.points]
                ys = [pt[1] for pt in pat.points]
                if xs and ys:
                    ctx['width_str'] = f"{(max(xs) - min(xs)) * 100:.1f}"
                    ctx['height_str'] = f"{(max(ys) - min(ys)) * 100:.1f}"
                    ctx['x_str'] = f"{((min(xs) + max(xs)) / 2) * 100:.1f}"
                    ctx['y_str'] = f"{((min(ys) + max(ys)) / 2) * 100:.1f}"
        return ctx

    def refresh_controls(self):
        self.inspector = None
        self.body_menu = None
        inspector_rect = self.canvas_layout.inspector
        if self.context_anchor is not None:
            bounds = self.canvas_layout.available
            scale = self.canvas_layout.scale
            width = min(340 * scale, bounds.w)
            height = min(620 * scale, bounds.h)
            x = max(bounds.x, min(self.context_anchor[0], bounds.x + bounds.w - width))
            y = max(bounds.y, min(self.context_anchor[1] - height, bounds.y + bounds.h - height))
            inspector_rect = Rect(x, y, width, height)
        if getattr(self, 'minimal_ui', False):
            return
        if inspector_rect:
            ctx = self.selection_context()
            ctx.update(sections=self.inspector_sections, query=self.search_query,
                       corner=self.session.corner, segment=self.session.segment,
                       drawing=bool(self.draft), tool=self.tool, details=self.inspector_details)
            if self.context_anchor is not None and not self.search_query and not self.inspector_sections:
                ctx['local_rows'] = self.local_control_rows()
            self.inspector = Inspector(inspector_rect, self.canvas_layout.scale,
                                       self.inspector_scroll, self.session.document.seams,
                                       'ALL', context=ctx)
            self.inspector_scroll = self.inspector.scroll
            if self.body_open:
                anchor = next((c.value_rect for c in self.inspector.controls if c.kind == 'body'), None)
                if anchor:
                    objects = sorted((o for o in self._scene.objects if o.type == 'MESH' and
                                    o.get('dd_kind') not in {'panel', 'simulation', 'final'}), key=lambda o: o.name.casefold())
                    bounds = self.canvas_layout.available if self.context_anchor is not None else self.canvas_layout.panel
                    self.body_menu = BodyMenu(bounds, anchor, self.canvas_layout.scale, objects, self.body_offset)

    def open_section(self, section):
        self.inspector_tab = section
        self.inspector_sections = [section]
        self.search_query = ''
        self.search_active = False
        self.inspector_scroll = 0
        if self.context_anchor is None:
            self.settings_open = True
        if section == 'LIBRARY':
            self.refresh_library()
        self.canvas_layout = self.make_layout()
        self.refresh_controls()

    def search_event(self, event):
        press = event.value == 'PRESS'
        if press and event.ctrl and event.type == 'F':
            self.open_context(select=False)
            self.search_active = True
            self.canvas_layout = self.make_layout()
            self.refresh_controls()
            return RUNNING
        if not self.search_active:
            return None
        if press and event.type in {'ESC', 'RET', 'NUMPAD_ENTER'}:
            self.search_active = False
            if event.type == 'ESC':
                self.search_query = ''
            self.refresh_controls()
            return RUNNING
        if press and event.type == 'LEFTMOUSE':
            if not self.inspector or not self.inspector.search.contains(*self.pointer):
                self.search_active = False
            return None
        if press and event.ctrl and event.type == 'A':
            self.search_query = ''
        elif press and event.type == 'BACK_SPACE':
            self.search_query = self.search_query[:-1]
        elif press and getattr(event, 'unicode', '') and not event.ctrl and not event.alt:
            self.search_query = (self.search_query + event.unicode)[:80]
        elif event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return None
        else:
            return RUNNING
        self.inspector_scroll = 0
        self.refresh_controls()
        return RUNNING

    def perform_action(self, action, confirmed=False):
        if action == 'CANCEL_ACTION':
            self.confirm_action = None
            self.confirm_message = ''
            self.message = 'Action cancelled. Your work is unchanged.'
            self.canvas_layout = self.make_layout()
            self.refresh_controls()
            return True
        if action == 'CONFIRM_ACTION':
            pending = self.confirm_action
            self.confirm_action = None
            self.confirm_message = ''
            return self.perform_action(pending, confirmed=True) if pending else False
        blocker = self.action_blocker(action)
        if blocker:
            self.message = blocker
            return False
        if not confirmed:
            prompt = ''
            if action == 'LIBRARY_LOAD' and self.session.document.patterns:
                prompt = 'Replace this garment with the library item? You can undo the source change.'
            elif action == 'RESET':
                prompt = 'Discard this drape and restore the positioned panels?'
            elif action == 'LIBRARY_SAVE':
                import re
                from . import library
                safe = re.sub(r'[^A-Za-z0-9_-]+', '-', self._scene.dd_library_name.strip()).strip('-')[:80]
                if (library.directory(self._scene) / (safe + '.garment.json')).exists():
                    prompt = 'Replace the saved garment with this name?'
            if prompt:
                self.confirm_action = action
                self.confirm_message = self.message = prompt
                return False
        tools = {'SELECT', 'POLYGON', 'RECTANGLE', 'ELLIPSE', 'INTERNAL', 'DART',
                 'SEW', 'FREE_SEW', 'PLACE', 'PIN', 'TACK'}
        if action in tools:
            return self.choose_tool(action)
        if action.startswith('DETAIL_'):
            section = action.removeprefix('DETAIL_')
            if section in self.inspector_details:
                self.inspector_details.remove(section)
            else:
                self.inspector_details.add(section)
        elif action == 'CANCEL_DRAFT':
            self.cancel_gesture()
            self.chain_a = []
            self.chain_b = []
            self.chain_stage = None
            self.free_clicks = []
            self.dart_base = []
            self.pending_place = self.pending_tack = None
            self.message = 'Pending operation cancelled. Your saved pieces are unchanged.'
        elif action == 'FINISH_DRAFT':
            if self.draft:
                self.finish_polygon(self.tool != 'INTERNAL')
            elif self.chain_stage:
                self.design_action('CHAIN_SEW')
        elif action in {'BUILD', 'ARRANGE', 'SIMULATE', 'STOP', 'RESET', 'KEEP', 'DEMO'}:
            return self.workflow_action(action)
        elif action == 'VIEW_3D':
            self.reveal_3d()
        elif action in {'UNDO', 'REDO'}:
            if self.draft:
                if action == 'UNDO':
                    self.draft.pop()
                self.message = 'Drawing updated. Finish or cancel before document undo.'
            else:
                history_stack = self.session.redo_stack if action == 'REDO' else self.session.undo_stack
                if history_stack:
                    self.clear_interaction_references()
                self.run_edit(lambda: self.session.history(action == 'REDO'), action.title() + '.')
        elif action == 'DELETE_PIECE':
            self.session.corner = None
            self.session.path = 'OUTER'
            if self.run_edit(self.session.delete, 'Piece deleted.'):
                self.clear_interaction_references()
        elif action == 'DELETE':
            if any(anchor.id == self.selected_anchor for anchor in self.session.document.anchors):
                self.design_action('REMOVE_ANCHOR')
            elif any(seam.id == self.seam_selected for seam in self.session.document.seams):
                self.run_edit(lambda: self.session.remove_seam(self.seam_selected), 'Seam removed.')
                self.seam_selected = None
                self.pending_edge = None
            elif self.tool == 'SEW':
                self.pending_edge = None
            else:
                self.run_edit(self.session.delete, 'Selection deleted.')
        elif action == 'FIT':
            self.fit()
        elif action == 'SNAP':
            self.snap = not self.snap
        elif action in {'REFERENCE', 'LENGTHS'}:
            key = 'dd_reference_visible' if action == 'REFERENCE' else 'dd_lengths_visible'
            setattr(self._scene, key, not getattr(self._scene, key))
        elif action == 'HELP':
            self.message = 'Tools: V P R E I D J K T. Ctrl F finds every action and setting. Escape cancels.'
        elif action == 'GUIDED_NEXT':
            self.advance_stage()
        else:
            if self.design_action(action) is False:
                return False
        self.refresh_controls()
        return True

    def action_blocker(self, action):
        if action == 'STOP':
            return ''
        if self.confirm_action:
            return 'Confirm the pending action or choose Go back first.'
        if self.gesture and action not in {'CANCEL_DRAFT', 'HELP'}:
            return 'Finish the current drag or press Escape before another edit.'
        if action == 'START_PANEL' and self.session.document.patterns:
            return 'The starter panel is available for an empty garment. Draw or duplicate another piece instead.'
        if self.draft and action not in {'FINISH_DRAFT', 'CANCEL_DRAFT', 'UNDO', 'REDO',
                                        'FIT', 'SNAP', 'LENGTHS', 'REFERENCE', 'HELP', 'POINT_APPLY'}:
            return 'Finish drawing or cancel before editing other garment data.'
        if action in {'BUILD', 'ARRANGE', 'SIMULATE', 'STOP', 'RESET', 'KEEP', 'DEMO'}:
            return self.workflow_blocker('STOP' if action == 'SIMULATE' and bpy.context.screen.is_animation_playing else action)
        selected = self.session.document.find(self.session.selected)
        if action in {'DELETE_PIECE', 'DUPLICATE', 'OFFSET', 'UNFOLD', 'MIRROR_SEW', 'CUT', 'TRACE', 'WRAP', 'PLACE', 'PRESET'} or action.startswith('SET_PRESET_'):
            if selected is None:
                return 'Select a piece on the canvas first.'
        if action == 'CURVE' and self.session.corner is None:
            return 'Select a point to change its corner or curve.'
        if action in {'SPLIT', 'SET_LENGTH', 'UNFOLD'} and self.session.segment is None:
            return 'Select an edge on the canvas first.'
        if action == 'MERGE' and len(self.session.point_selection) < 2:
            return 'Shift-click at least two points to merge.'
        if action == 'CHAIN_SEW' and (not self.chain_a or not self.chain_b):
            return 'Pick an edge chain for both side A and side B first.'
        if action == 'LIBRARY_SAVE' and not self.session.document.patterns:
            return 'Create a garment before saving it.'
        if action in {'LIBRARY_LOAD', 'LIBRARY_PREV', 'LIBRARY_NEXT'} and not self.library_items:
            return 'The local garment library is empty.'
        if action == 'REMOVE_ANCHOR' and not any(anchor.id == self.selected_anchor for anchor in self.session.document.anchors):
            return 'Select a pin or tack using K or T first.'
        return ''

    def set_window(self, rect):
        s = self.canvas_layout.scale
        if rect.w < 760 * s:
            self.settings_open = False
        self.window_rect = tuple(value / s for value in (rect.x, rect.y, rect.w, rect.h))
        self.canvas_layout = self.make_layout()
        self.refresh_controls()

    def save_window(self):
        if not self.full:
            p = self.canvas_layout.panel
            s = self.canvas_layout.scale
            self.window_rect = (p.x / s, p.y / s, p.w / s, p.h / s)
        if self.window_rect is not None:
            self._scene.dd_ui_rect = self.window_rect
        self._scene.dd_ui_settings = self.settings_open

    def toggle_full(self):
        if not self.full:
            self.save_window()
        self.full = not self.full
        self.canvas_layout = self.make_layout()
        self.refresh_controls()

    def commit_numeric(self):
        if not self.numeric:
            return True
        key = self.numeric['key']
        try:
            value = SETTINGS[key].parse(self.numeric['text'])
        except ValueError as exc:
            self.message = str(exc)
            return False
        previous = getattr(self._scene, key)
        setattr(self._scene, key, value)
        if self.apply_local_setting(key) is False:
            setattr(self._scene, key, previous)
            self.sync_selection()
            return False
        self.numeric = None
        self.message = SETTINGS[key].label + ' updated.'
        return True

    def apply_local_setting(self, key):
        if self.context_anchor is not None:
            if key in {'dd_point_x', 'dd_point_y'} and self.session.corner is not None:
                return self.perform_action('POINT_APPLY')
            elif key == 'dd_segment_length' and self.session.segment:
                return self.perform_action('SET_LENGTH')

    def step_setting(self, key, direction, event):
        spec = SETTINGS[key]
        amount = spec.step / spec.factor
        if event.shift and not spec.integer:
            amount *= .1
        if event.ctrl:
            amount *= 10
        value = max(spec.low, min(spec.high, getattr(self._scene, key) + direction * amount))
        setattr(self._scene, key, int(round(value)) if spec.integer else round(value, 8))
        self.message = spec.label + ' updated.'

    def numeric_event(self, event):
        if not self.numeric:
            return None
        press = event.value == 'PRESS'
        state = self.numeric
        if press and event.type in {'ESC', 'RIGHTMOUSE'}:
            self.numeric = None
            self.message = 'Setting edit cancelled.'
            return RUNNING
        if press and event.type in {'RET', 'NUMPAD_ENTER'}:
            self.commit_numeric()
            return RUNNING
        if event.ctrl and event.type == 'S' and press:
            return {'PASS_THROUGH'} if self.commit_numeric() else RUNNING
        if press and event.type == 'LEFTMOUSE':
            return None if self.commit_numeric() else RUNNING
        if press and event.ctrl and event.type == 'A':
            state['selected'] = True
            return RUNNING
        if press and event.type in {'LEFT_ARROW', 'RIGHT_ARROW', 'HOME', 'END'}:
            n = len(state['text'])
            state['cursor'] = (0 if event.type == 'HOME' else n if event.type == 'END' else
                             max(0, min(n, state['cursor'] + (-1 if event.type == 'LEFT_ARROW' else 1))))
            state['selected'] = False
            return RUNNING
        if press and event.type in {'BACK_SPACE', 'DEL'}:
            text, cursor = state['text'], state['cursor']
            if state['selected']:
                text, cursor = '', 0
            elif event.type == 'BACK_SPACE' and cursor > 0:
                text, cursor = text[:cursor - 1] + text[cursor:], cursor - 1
            elif event.type == 'DEL':
                text = text[:cursor] + text[cursor + 1:]
            state.update(text=text, cursor=cursor, selected=False)
            return RUNNING
        char = getattr(event, 'unicode', '')
        if press and char and (not hasattr(SETTINGS[state['key']], 'factor') or all(c in '0123456789.,eE+-' for c in char)):
            text, cursor = state['text'], state['cursor']
            if state['selected']:
                text, cursor = '', 0
            state.update(text=text[:cursor] + char + text[cursor:], cursor=cursor + len(char), selected=False)
        return RUNNING

    def controls_event(self, context, event):
        press = event.value == 'PRESS'
        l = self.canvas_layout
        x, y = self.pointer
        if self.setting_drag:
            state = self.setting_drag
            key = state['key']
            spec = SETTINGS[key]
            distance = x - state['pointer'][0]
            if press and event.type in {'ESC', 'RIGHTMOUSE'}:
                setattr(self._scene, key, state['value'])
                self.setting_drag = None
                return RUNNING
            if event.type == 'MOUSEMOVE' and abs(distance) >= 4 * l.scale:
                state['moved'] = True
                increment = spec.step / spec.factor * (.1 if event.shift else 1)
                value = max(spec.low, min(spec.high, state['value'] + distance / (8 * l.scale) * increment))
                if state.get('absolute'):
                    track = state['absolute']
                    value = spec.low + (spec.high - spec.low) * max(0, min(1, (x - track.x) / track.w))
                setattr(self._scene, key, int(round(value)) if spec.integer else round(value, 8))
                return RUNNING
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.setting_drag = None
                if state['moved']:
                    if self.apply_local_setting(key) is False:
                        setattr(self._scene, key, state['value'])
                        self.sync_selection()
                else:
                    text = spec.format(getattr(self._scene, key))
                    self.numeric = dict(key=key, text=text, cursor=len(text), selected=True)
                return RUNNING
            return RUNNING
        if self.context_anchor is not None and not self.body_menu and not self.numeric:
            if press and event.type in {'ESC', 'RIGHTMOUSE'}:
                self.close_context()
                return RUNNING
            if press and event.type == 'LEFTMOUSE' and not self.inspector.rect.contains(x, y):
                self.close_context()
                return RUNNING
        if (self.context_anchor is None and press and event.type == 'RIGHTMOUSE'
                and l.canvas.contains(x, y) and not self.draft and not self.gesture
                ):
            self.open_context(select=not (self.pending_edge or self.free_clicks or self.chain_stage))
            return RUNNING
        if self.window_gesture:
            gesture = self.window_gesture
            if press and event.type in {'ESC', 'RIGHTMOUSE'}:
                self.full = gesture['full']
                if gesture['kind'] == 'SCROLL':
                    self.inspector_scroll = gesture['scroll']
                else:
                    self.window_rect = gesture['placement']
                self.canvas_layout = self.make_layout()
                self.refresh_controls()
                self.window_gesture = None
                self.message = 'Window movement cancelled.'
                return RUNNING
            if event.type == 'MOUSEMOVE':
                dx, dy = x - gesture['pointer'][0], y - gesture['pointer'][1]
                r = gesture['rect']
                if gesture['kind'] == 'MOVE':
                    requested = Rect(r.x + dx, r.y + dy, r.w, r.h)
                elif gesture['kind'] == 'RESIZE':
                    available = l.available
                    w = min(available.x + available.w - r.x, max(min(420 * l.scale, available.w), r.w + dx))
                    h = min(r.y + r.h - available.y, max(min(420 * l.scale, available.h), r.h - dy))
                    requested = Rect(r.x, r.y + r.h - h, w, h)
                else:
                    self.inspector_scroll = max(0, min(self.inspector.max_scroll,
                        gesture['scroll'] - dy * self.inspector.total / max(1.0, self.inspector.content.h)))
                    self.refresh_controls()
                    return RUNNING
                self.set_window(requested)
                return RUNNING
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.window_gesture = None
                self.save_window()
                return RUNNING
            return RUNNING
        if self.numeric:
            result = self.numeric_event(event)
            if result is not None:
                return result
        if self.body_menu:
            if press and event.type in {'ESC', 'RIGHTMOUSE'}:
                resume_requested = self.pending_simulation
                self.body_open = False
                self.pending_simulation = False
                if resume_requested and self.context_anchor is not None:
                    self.close_context()
                self.refresh_controls()
                return RUNNING
            if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                self.body_offset = max(0, min(max(0, len(self.body_menu.objects) - 6),
                    self.body_offset + (-1 if event.type == 'WHEELUPMOUSE' else 1)))
                self.refresh_controls()
                return RUNNING
            if press and event.type == 'LEFTMOUSE':
                resume_requested = self.pending_simulation
                for r, obj, _ in self.body_menu.rows:
                    if r.contains(x, y):
                        self.choose_body(obj, context)
                        self.message = 'Avatar body selected.' if obj else 'Avatar body cleared.'
                        break
                self.body_open = False
                self.pending_simulation = False
                if resume_requested and self.context_anchor is not None:
                    self.close_context()
                self.refresh_controls()
                return RUNNING
            return RUNNING if l.panel.contains(x, y) else None

        button = l.button(x, y)
        if event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK' and l.header.contains(x, y) and not button:
            self.toggle_full()
            return RUNNING
        if press and event.type == 'LEFTMOUSE':
            if button in {'SETTINGS', 'INSPECTOR'}:
                if self.context_anchor is not None:
                    self.close_context()
                self.settings_open = not self.settings_open
                self.body_open = False
                self.canvas_layout = self.make_layout()
                self.refresh_controls()
                self.save_window()
                return RUNNING
            if l.header.contains(x, y) and not button:
                original = l.panel
                placement = self.window_rect
                was_full = self.full
                if self.full:
                    ratio = (x - original.x) / max(1.0, original.w)
                    self.full = False
                    self.canvas_layout = self.make_layout()
                    restored = self.canvas_layout.panel
                    self.set_window(Rect(x - ratio * restored.w, y + 20 * l.scale - restored.h, restored.w, restored.h))
                self.window_gesture = dict(kind='MOVE', pointer=(x, y), rect=self.canvas_layout.panel,
                                         original=original, full=was_full, placement=placement)
                return RUNNING
            if l.resize.contains(x, y) and not self.full:
                self.window_gesture = dict(kind='RESIZE', pointer=(x, y), rect=l.panel, original=l.panel, full=False, placement=self.window_rect)
                return RUNNING
        if self.inspector and self.inspector.rect.contains(x, y):
            if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                self.inspector_scroll += (-38 if event.type == 'WHEELUPMOUSE' else 38) * l.scale
                self.refresh_controls()
                return RUNNING
            if press and event.type == 'LEFTMOUSE':
                if x >= self.inspector.scrollbar.x - 5 * l.scale and self.inspector.max_scroll:
                    self.window_gesture = dict(kind='SCROLL', pointer=(x, y), scroll=self.inspector_scroll,
                                             rect=l.panel, original=l.panel, full=self.full)
                    return RUNNING
                hit = self.inspector.hit((x, y))
                if hit:
                    action, key = hit
                    if action == 'SEARCH':
                        self.search_active = True
                    elif action == 'SECTION':
                        if key in self.inspector_sections:
                            self.inspector_sections.remove(key)
                        else:
                            self.open_section(key)
                    elif action in {'STEP_UP', 'STEP_DOWN'}:
                        self.step_setting(key, 1 if action == 'STEP_UP' else -1, event)
                        self.apply_local_setting(key)
                    elif action == 'EDIT':
                        if self.context_anchor is not None and hasattr(SETTINGS[key], 'factor'):
                            self.setting_drag = dict(key=key, value=getattr(self._scene, key), pointer=self.pointer, moved=False)
                        else:
                            text = SETTINGS[key].format(getattr(self._scene, key))
                            self.numeric = dict(key=key, text=text, cursor=len(text), selected=True)
                        self.message = 'Drag to adjust; click to type. Enter applies; Escape cancels.'
                    elif action == 'TOGGLE':
                        setattr(self._scene, key, not getattr(self._scene, key))
                    elif action == 'BODY':
                        self.body_open = True
                        self.body_offset = 0
                    elif action == 'BODY_USE':
                        obj = context.view_layer.objects.active
                        if obj and obj.type == 'MESH' and obj in list(self._scene.objects) and obj.get('dd_kind') not in {'panel', 'simulation', 'final'}:
                            self.choose_body(obj, context)
                            self.message = 'Selected mesh assigned as avatar body.'
                        else:
                            self.message = 'Select a body mesh in 3D or choose one from the Avatar body list.'
                    elif action in {'REFERENCE_VIEW', 'REFERENCE_ALIGN', 'REFERENCE_FRAME', 'REFERENCE_REFRESH'}:
                        self.reference_action(action)
                    elif action == 'DEMO':
                        if self.session.document.patterns:
                            self.message = 'The demo needs an empty pattern document. Open a new scene to try it.'
                        else:
                            self.workflow_action('DEMO')
                    elif action == 'SEAM_FLIP':
                        self.run_edit(lambda: self.session.reverse_seam(key), 'Seam direction reversed.')
                    elif action == 'SEAM_REMOVE':
                        self.run_edit(lambda: self.session.remove_seam(key), 'Seam removed.')
                    elif action == 'SEAM_SELECT':
                        self.choose_tool('SEW')
                        self.seam_selected = key
                        self.message = 'Seam selected. B: reverse. X: remove.'
                    elif action in {'BUILD', 'ARRANGE', 'SIMULATE', 'STOP', 'RESET', 'KEEP'}:
                        self.perform_action(action)
                    else:
                        self.perform_action(action)
                    direct_canvas_actions = {'PLACE', 'PIN', 'TACK', 'SEW', 'FREE_SEW', 'CHAIN_A', 'CHAIN_B',
                                             'RECTANGLE', 'POLYGON', 'ELLIPSE', 'INTERNAL', 'DART', 'SIMULATE',
                                             'KEEP', 'RESET', 'DELETE', 'LIBRARY_LOAD', 'CURVE', 'SPLIT',
                                             'UNFOLD', 'MIRROR_SEW', 'CUT', 'TRACE', 'MERGE', 'OFFSET'}
                    if self.context_anchor is not None and (action in direct_canvas_actions or self.confirm_action):
                        if not self.body_open:
                            self.close_context()
                    self.refresh_controls()
                    return RUNNING
            if event.type not in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                return None
            return RUNNING
        return None
