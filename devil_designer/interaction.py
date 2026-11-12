import bpy
from .controls import CONTROL_SETTINGS as SETTINGS

RUNNING = {'RUNNING_MODAL'}


class OverlayControls:
    def initialize_controls(self):
        saved = tuple(self._scene.dd_ui_rect)
        self.window_rect = saved if saved[2] > 0 and saved[3] > 0 else None
        self.pending_simulation = False
        self.redrape_after_fit = False
        self.confirm_action = None
        self.confirm_message = ''
        self.numeric = None
        self.setting_drag = None

    def perform_action(self, action, confirmed=False):
        if action == 'CANCEL_ACTION':
            self.library_load_path=None
            self.confirm_action = None
            self.confirm_message = ''
            self.message = 'Action cancelled. Your work is unchanged.'
            self.canvas_layout = self.make_layout()
            return True
        if action == 'CONFIRM_ACTION':
            pending = self.confirm_action
            self.confirm_action = None
            self.confirm_message = ''
            result=self.perform_action(pending, confirmed=True) if pending else False
            if result and pending=='LIBRARY_SAVE':
                self.library_query='';self.library_filter=''
                self.show_card('LIBRARY')
            return result
        blocker = self.action_blocker(action)
        if blocker:
            self.message = blocker
            return False
        if not confirmed:
            prompt = ''
            if action.startswith('STARTER_') and self.session.document.patterns:
                prompt = 'Replace current garment with this starter? You can undo this change.'
            elif action == 'LIBRARY_LOAD' and self.session.document.patterns:
                prompt = 'Replace this garment with the library item? You can undo the source change.'
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
        if action == 'CANCEL_DRAFT':
            self.cancel_gesture()
            self.free_clicks = []
            self.dart_base = []
            self.pending_place = self.pending_tack = None
            self.message = 'Pending operation cancelled. Your saved pieces are unchanged.'
        elif action == 'FINISH_DRAFT':
            if self.draft:
                self.finish_polygon(self.tool != 'INTERNAL')
        elif action in {'SIMULATE', 'KEEP'}:
            return self.workflow_action(action)
        elif action in {'UNDO', 'REDO'}:
            if self.draft:
                if action == 'UNDO':
                    self.draft.pop()
                self.message = 'Drawing updated. Finish or cancel before document undo.'
            else:
                history_stack = self.session.redo_stack if action == 'REDO' else self.session.undo_stack
                if history_stack:
                    self.clear_interaction_references()
                self.run_edit(lambda: self.session.history(action == 'REDO', self.apply_pin_step), action.title() + '.')
                self.sync_selection()
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
        else:
            if self.design_action(action) is False:
                return False
        return True

    def action_blocker(self, action):
        if self.confirm_action:
            return 'Confirm the pending action or choose Cancel first.'
        if self.gesture and action != 'CANCEL_DRAFT':
            return 'Finish the current drag or press Escape before another edit.'
        if self.draft and action not in {'FINISH_DRAFT', 'CANCEL_DRAFT', 'UNDO', 'REDO', 'POINT_APPLY'}:
            return 'Finish drawing or cancel before editing other garment data.'
        if action in {'SIMULATE', 'KEEP'}:
            from . import garment
            return self.workflow_blocker('STOP' if action == 'SIMULATE' and garment.drape_playing(bpy.context) else action)
        selected = self.session.document.find(self.session.selected)
        if action in {'DELETE_PIECE', 'DUPLICATE', 'UNFOLD', 'MIRROR_SEW', 'CUT', 'TRACE', 'PLACE', 'FLIP_H', 'FLIP_V'}:
            if selected is None and not self.session.selected_patterns and not self.session.selected_points and self.session.corner is None:
                return 'Select a piece on the canvas first.'
        if action == 'CURVE' and self.session.corner is None and not self.session.selected_points:
            return 'Select a point to change its corner or curve.'
        if action in {'SPLIT', 'SET_LENGTH', 'UNFOLD'} and self.session.segment is None:
            return 'Select an edge on the canvas first.'
        if action == 'MERGE' and not self.session.can_merge_selected_points() and len(self.session.point_selection) < 2:
            return 'Shift-click at least two points to merge.'
        if action == 'LIBRARY_SAVE' and not self.session.document.patterns:
            return 'Create a garment before saving it.'
        if action == 'LIBRARY_LOAD' and not self.library_items:
            return 'The local garment library is empty.'
        return ''

    def set_window(self, rect):
        s = self.canvas_layout.scale
        self.window_rect = tuple(value / s for value in (rect.x, rect.y, rect.w, rect.h))
        self.canvas_layout = self.make_layout()

    def save_window(self):
        if not self.full:
            p = self.canvas_layout.panel
            s = self.canvas_layout.scale
            self.window_rect = (p.x / s, p.y / s, p.w / s, p.h / s)
        if self.window_rect is not None:
            self._scene.dd_ui_rect = self.window_rect

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
        if press and char and (not hasattr(SETTINGS[state['key']], 'factor') or all(c in '0123456789.,eE+-*/() ' for c in char)):
            text, cursor = state['text'], state['cursor']
            if state['selected']:
                text, cursor = '', 0
            state.update(text=text[:cursor] + char + text[cursor:], cursor=cursor + len(char), selected=False)
        return RUNNING

    def setting_drag_event(self, event):
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
                setattr(self._scene, key, round(value, 8))
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
        return None
