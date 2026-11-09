import math
import time
try:
    import blf
except ImportError:
    blf = None
import bpy
from .canvas import Rect
from . import budget, layering
from .ui_system import MENU_CARDS, MinimalMetrics
from .localization import translate
from .controls import CONTROL_SETTINGS
from .avatar_field import AvatarField, LABEL


SEAM_QUIET, SEAM_CONNECTED, SEAM_ACTIVE = 'QUIET', 'CONNECTED', 'ACTIVE'


def text_unscaled_width(text, size=11):
    if not text:
        return 0.0
    if blf:
        try:
            blf.size(0, size)
            return blf.dimensions(0, translate(str(text)))[0]
        except Exception:
            pass
    return len(str(text)) * (size * 0.6)


DENSITY = {'Coarse': .04, 'Standard': .02, 'Fine': .01, 'Ultra': .005}
def heading_to(start, point, rect, margin):
    edge = rect.x if rect.x >= start[0] else rect.x + rect.w
    run, step = edge - start[0], point[0] - start[0]
    if run * step <= 0:
        return False
    reach = start[1] + (point[1] - start[1]) * run / step
    return rect.y - margin <= reach <= rect.y + rect.h + margin


HOVER_MENUS = {'PIECE_FABRIC_MENU': 'PIECE_FABRIC', 'PIECE_DENSITY_MENU': 'PIECE_DENSITY', 'PIECE_SIMULATION_MENU': 'PIECE_SIMULATION',
               'PIECE_PLACEMENT_MENU': 'PIECE_PLACEMENT', 'PIECE_CLONE_MENU': 'PIECE_CLONE', 'TRANSFORM_MENU': 'TRANSFORM_MENU',
               'STARTERS_MENU': 'STARTERS', 'FOLD_MENU': 'FOLD', 'GARMENT_FABRIC_MENU': 'GARMENT_FABRIC'}
STRIP_KEYS = {'SELECT': 'V', 'SELECT_ALL': 'A', 'SELECT_INVERT': 'Ctrl I', 'SET_DRAW_RECTANGLE': 'R', 'SET_DRAW_POLYGON': 'P', 'SET_DRAW_ELLIPSE': 'E',
              'SET_INTERNAL_PATH': 'I', 'SET_INTERNAL_DART': 'D', 'KNIFE_MODE_SEW': 'N', 'SET_SEW_SEGMENT': 'J', 'SET_SEW_FREE': 'Shift J',
              'SET_PIN_FABRIC': 'K', 'SET_PIN_BODY': 'T'}
FLYOUT_TOOLS = ('SELECT', 'DRAW', 'INTERNAL', 'SEW', 'PIN', 'SHAPE')
SKIN_OFFSET = {'1 mm': .001, '3 mm': .003, '6 mm': .006}
FRICTION = {'Slippery': .1, 'Normal': .3, 'Grippy': .6}
SPLIT_PARTS = ('3 parts', '4 parts', 'Every 2 cm', 'Every 5 cm')
GRAIN_SETTINGS = {'dd_fabric_weft': 'weft', 'dd_fabric_bias': 'bias', 'dd_fabric_shrink_warp': 'shrink_warp', 'dd_fabric_shrink_weft': 'shrink_weft'}
QUALITY = {'Draft': 12, 'Standard': 24, 'High': 36}
THICKNESS = {'None': 0, 'Thin': .0005, 'Standard': .001}
FABRICS = ('COTTON', 'LINEN', 'DENIM', 'SILK', 'LEATHER', 'KNIT')
GUIDE_OPACITY = {'Light': .15, 'Medium': .30, 'Strong': .50}
PLACEMENT_DISTANCE = {'Body': None, '1 cm': .01, '2 cm': .02, '5 cm': .05}
PLACEMENT_OVERLAP = {'Off': (False, 1), 'Right on top': (True, 1), 'Left on top': (True, -1)}
IMAGE_OPACITY = {'Light': .2, 'Medium': .35, 'Strong': .6}
SUBMENUS = {'TRANSFORM_MENU': 'TRANSFORM_MENU', 'PIECE_PLACEMENT_MENU': 'PIECE_PLACEMENT',
            'PIECE_CLONE_MENU': 'PIECE_CLONE', 'STARTERS_MENU': 'STARTERS'}


def minimal_layout(layout, pending=False, confirmation=False, playing=False, kept=False, stale=False):
    scale = layout.scale
    panel = layout.panel
    layout.metrics = MinimalMetrics.resolve()
    tool_count = 9
    group_gap = round(6 * scale)
    chip_h = round(19 * scale)
    tool_pitch = min(35, max(20, (panel.h / scale - 120) / tool_count))
    btn_h = round(tool_pitch * scale)
    dock_width = round(40 * scale)
    dock_height = tool_count * btn_h + 4 * group_gap + group_gap + 2 * chip_h + round(2 * scale)
    dock_x = round(panel.x + 8 * scale)
    dock_y = round(panel.y + (panel.h - dock_height) / 2)
    layout.rail = Rect(dock_x, dock_y, dock_width, dock_height)
    layout.buttons = {}
    groups = ((('SELECT', 'Select'),),
              (('DRAW', 'Draw'), ('INTERNAL', 'Internal'), ('SEW', 'Sew'), ('PIN', 'Pin')),
              (('SHAPE', 'Grab'),),
              (('UNDO', 'Undo'), ('REDO', 'Redo')),
              (('LIBRARY', 'Library'),))
    layout.tool_groups = []
    tool_x = dock_x
    y = dock_y + dock_height
    for group in groups:
        top = y
        for key, label in group:
            y -= btn_h
            layout.buttons[key] = (Rect(tool_x, y, dock_width, btn_h), label)
        layout.tool_groups.append(Rect(tool_x, y, dock_width, top - y))
        y -= group_gap
    ind_w = round((dock_width - 2 * scale) / 2)
    ind_h = chip_h
    chip_y1 = round(dock_y + ind_h + 2 * scale)
    chip_y0 = dock_y
    layout.buttons['TOGGLE_SNAP'] = (Rect(tool_x, chip_y1, ind_w, ind_h), 'Snap')
    layout.buttons['TOGGLE_GUIDE'] = (Rect(round(tool_x + ind_w + 2 * scale), chip_y1, ind_w, ind_h), 'Guide')
    layout.buttons['TOGGLE_LENGTHS'] = (Rect(tool_x, chip_y0, ind_w, ind_h), 'Lengths')
    layout.buttons['TOGGLE_FIT_MAP'] = (Rect(round(tool_x + ind_w + 2 * scale), chip_y0, ind_w, ind_h), 'Fit map')
    right = round(panel.x + panel.w - 14 * scale)
    layout.buttons['CLOSE'] = (Rect(round(right - 24 * scale), round(panel.y + panel.h - 30 * scale), round(24 * scale), round(24 * scale)), 'Close')
    right -= round(28 * scale)
    right -= round(88 * scale)
    if layout.full:
        layout.buttons['SHOW_3D'] = (Rect(right, round(panel.y + panel.h - 30 * scale), round(82 * scale), round(24 * scale)), '3D view')
    else:
        layout.buttons['RESTORE_CANVAS'] = (Rect(right, round(panel.y + panel.h - 30 * scale), round(82 * scale), round(24 * scale)), 'Full canvas')
    layout.buttons['GARMENT'] = (Rect(tool_x, round(panel.y + panel.h - 38 * scale), dock_width, round(30 * scale)), 'Garment')
    layout.canvas = Rect(round(panel.x + 4 * scale), round(panel.y + 4 * scale), round(panel.w - 8 * scale), round(panel.h - 8 * scale))
    bottom = round(panel.y + 14 * scale)
    right = round(panel.x + panel.w - 14 * scale)
    specs = [('SIMULATE', 'Pause' if playing else 'Re-drape' if stale else 'Simulate'), ('KEEP', 'Keep mesh')]
    if pending:
        specs = [('FINISH_DRAFT', 'Finish'), ('CANCEL_DRAFT', 'Cancel')]
    if confirmation:
        specs = [('CONFIRM_ACTION', 'Confirm'), ('CANCEL_ACTION', 'Cancel')]
    for key, label in specs:
        width = round(128 * scale)
        right -= width
        layout.buttons[key] = (Rect(right, bottom, width, round(24 * scale)), label)
        if key == 'KEEP':
            layout.buttons['KEEP_OPTIONS'] = (Rect(right + 104 * scale, bottom, 24 * scale, 24 * scale), 'Options')
            layout.buttons['KEEP'] = (Rect(right, bottom, 104 * scale, 24 * scale), label)
        elif key == 'SIMULATE' and kept:
            layout.buttons['SIMULATE_OPTIONS'] = (Rect(right + 104 * scale, bottom, 24 * scale, 24 * scale), 'Wear over')
            layout.buttons['SIMULATE'] = (Rect(right, bottom, 104 * scale, 24 * scale), label)
        right -= 4 * scale


class MinimalCards:
    def initialize_minimal(self):
        self.minimal_ui = True
        self.avatar_field = AvatarField(self)
        self.weld_manual = False
        self.card_kind = None
        self.card_anchor = None
        self.card_page = 0
        self.wear_over_offset = 0
        self.card_models = []
        self.library_items = []
        self.library_previews = {}
        self.library_query = ''
        self.library_filter = ''
        self.library_tags = ''
        self.library_edit = None
        self.library_preview_path = None
        self.library_load_path = None
        self.library_load_signature = None
        self.library_error = ''
        self._scene.dd_reference_visible = False
        self._scene.dd_fabric = getattr(self.session.document, 'preset', 'COTTON')
        self.sync_fabric_settings(self._scene.dd_fabric)
        self.draw_shape = 'RECTANGLE'
        self.internal_tool = 'INTERNAL'
        self.knife_sew = True
        self.pin_tool = 'PIN'
        self.sew_tool = 'SEW'
        self.armed_selection = None
        self.flyout = None
        self.flyout_dismissed = None
        self.sub_card = None
        self.sub_owner = None
        self.sub_parent = None
        self.sub_anchor = None
        self.sub_pending = None
        self.sub_timer = None
        self.sub_origin = None
        self.pending_strokes = []
        self.brush_stretch = None
        self.drape_document = None
        self._scene.dd_internal_mode = False

    def named_choice(self, value, choices):
        return min(choices, key=lambda name: abs(choices[name] - value))

    def automatic_defaults(self, finalize=False):
        scene = self._scene
        scene.dd_self_collision = True
        scene.dd_library_refit = True
        scene.dd_clearance = .03
        scene.dd_spacing = DENSITY[self.named_choice(scene.dd_spacing, DENSITY)]
        scene.dd_quality = QUALITY[self.named_choice(scene.dd_quality, QUALITY)]
        if finalize and not self.weld_manual:
            scene.dd_weld_distance = .01
        if finalize:
            scene.dd_thickness = THICKNESS[self.named_choice(scene.dd_thickness, THICKNESS)]

    def seam_focus_levels(self):
        doc = self.session.document
        if not doc.seams:
            return {}
        pieces = set(self.session.selected_patterns) or {self.session.selected}
        if self.pending_edge:
            pieces.add(self.pending_edge.pattern)
        hovered = self.design_hit_edge()
        hovered_key = (hovered.pattern, hovered.start, hovered.end) if hovered else None
        levels = {}
        for seam in doc.seams:
            edges = [*seam.side(0), *seam.side(1)]
            if seam.id in (self.seam_selected, self.seam_hover) or any((edge.pattern, edge.start, edge.end) == hovered_key for edge in edges):
                levels[seam.id] = SEAM_ACTIVE
            elif any(edge.pattern in pieces for edge in edges):
                levels[seam.id] = SEAM_CONNECTED
            else:
                levels[seam.id] = SEAM_QUIET
        return levels

    def seam_badges(self):
        if self.tool == 'SHAPE':
            return []
        badges = []
        scale = self.canvas_layout.scale
        meas = getattr(self, 'measurement_rects', [])
        doc = self.session.document
        canvas = self.canvas_layout.canvas
        for index, seam in enumerate(doc.seams):
            if self.tool != 'SEW' and seam.id not in (self.seam_selected, self.seam_hover):
                continue
            middles = []
            for side in (0, 1):
                edge, fraction = doc.chain_position(seam.side(side), .5)
                middles.append(self.view.screen(doc.edge_point(edge, fraction), canvas))
            for side in (0, 1):
                own = middles[side]
                other = middles[1 - side]
                dx, dy = other[0] - own[0], other[1] - own[1]
                dist = math.hypot(dx, dy)
                if dist > 1e-3:
                    offset = min(14 * scale, dist * 0.32)
                    center = (own[0] + (dx / dist) * offset, own[1] + (dy / dist) * offset)
                else:
                    center = (own[0] + (10 * scale if side else -10 * scale), own[1])
                while any(abs(center[0] - (rect.x + rect.w / 2)) < 20 * scale and
                          abs(center[1] - (rect.y + rect.h / 2)) < 18 * scale for rect, identity, label in badges) or \
                      any(abs(center[0] - (mr.x + mr.w / 2)) < (mr.w / 2 + 12 * scale) and
                          abs(center[1] - (mr.y + mr.h / 2)) < (mr.h / 2 + 12 * scale) for mr in meas):
                    center = (center[0], center[1] + 20 * scale)
                badges.append((Rect(center[0] - 10 * scale, center[1] - 9 * scale, 20 * scale, 18 * scale), seam.id, str(index + 1)))
        return badges

    def show_card(self, kind, anchor=None):
        self.close_sub()
        self.library_edit = None
        self.card_kind = kind
        self.card_anchor = anchor or self.pointer
        self.card_page = 0
        self.wear_over_offset = 0
        if kind.startswith('LIBRARY'):
            self.refresh_library()

    def library_matches(self):
        query=self.library_query.casefold().strip()
        return [(index,path) for index,path in enumerate(self.library_items)
                if (not self.library_filter or self.library_filter in self.library_previews[path]['tags']) and
                (not query or query in ' '.join([self.library_previews[path]['name'],
                    self.library_previews[path]['body'],*self.library_previews[path]['tags']]).casefold())]

    def library_page_size(self):
        return 4 if self.canvas_layout.panel.h/self.canvas_layout.scale>=560 else 2

    def library_text_event(self,event):
        edit=self.library_edit
        if not edit:return None
        if event.value!='PRESS':return None
        if event.type in {'ESC','RIGHTMOUSE'}:
            if edit['key']=='library_query':self.library_query=edit['original']
            self.library_edit=None
            return {'RUNNING_MODAL'}
        if event.type in {'RET','NUMPAD_ENTER','LEFTMOUSE'}:
            target=self._scene if edit['key']=='dd_library_name' else self
            setattr(target,edit['key'],edit['text'])
            self.library_edit=None
            self.card_page=0
            return None if event.type=='LEFTMOUSE' else {'RUNNING_MODAL'}
        if event.ctrl and event.type=='A':edit['selected']=True
        elif event.type in {'LEFT_ARROW','RIGHT_ARROW','HOME','END'}:
            edit['cursor']=0 if event.type=='HOME' else len(edit['text']) if event.type=='END' else max(0,min(len(edit['text']),edit['cursor']+(-1 if event.type=='LEFT_ARROW' else 1)))
            edit['selected']=False
        elif event.type in {'BACK_SPACE','DEL'}:
            text,cursor=edit['text'],edit['cursor']
            if edit['selected']:text='';cursor=0
            elif event.type=='BACK_SPACE' and cursor>0:text=text[:cursor-1]+text[cursor:];cursor-=1
            elif event.type=='DEL':text=text[:cursor]+text[cursor+1:]
            edit.update(text=text,cursor=cursor)
            edit['selected']=False
        elif getattr(event,'unicode','') and not event.ctrl and not event.alt:
            text,cursor=('',0) if edit['selected'] else (edit['text'],edit['cursor'])
            edit.update(text=(text[:cursor]+event.unicode+text[cursor:])[:160],cursor=min(160,cursor+len(event.unicode)),selected=False)
        if edit['key']=='library_query':
            self.library_query=edit['text'];self.card_page=0
        return {'RUNNING_MODAL'}

    def minimal_card(self):
        kind = self.card_kind
        content = self.card_rows(kind) if kind else None
        if content is None:
            return None
        title, rows = content
        return self.card_layout(kind, title, rows)

    def close_sub(self):
        self.sub_card = self.sub_owner = self.sub_parent = self.sub_anchor = None
        self.cancel_pending_sub()

    def cancel_pending_sub(self):
        self.sub_pending = None
        if self.sub_timer is not None:
            bpy.context.window_manager.event_timer_remove(self.sub_timer)
            self.sub_timer = None

    def settle_sub(self, key, rect, parent):
        if key in FLYOUT_TOOLS:
            self.cancel_pending_sub()
            self.open_flyout(key)
        elif key:
            self.open_sub(key, rect, parent)
        else:
            self.close_sub()

    def schedule_sub(self, key, rect, parent):
        if self.sub_pending and self.sub_pending['key'] == key:
            return
        delay = bpy.context.preferences.view.open_sublevel_delay / 10
        if delay <= 0:
            self.settle_sub(key, rect, parent)
            return
        self.sub_pending = dict(key=key, rect=rect, parent=parent, due=time.monotonic() + delay)
        if self.sub_timer is None:
            self.sub_timer = bpy.context.window_manager.event_timer_add(.02, window=self._window)

    def tick_sub(self):
        pending = self.sub_pending
        if pending and time.monotonic() >= pending['due']:
            self.settle_sub(pending['key'], pending['rect'], pending['parent'])
            self._area.tag_redraw()

    def open_sub(self, key, rect, parent):
        target = HOVER_MENUS[key]
        if target in {'PIECE_FABRIC', 'GARMENT_FABRIC'}:
            pattern = self.session.document.find(self.session.selected)
            preset = pattern.preset if target == 'PIECE_FABRIC' and pattern and getattr(pattern, 'fabric_override', False) else getattr(self.session.document, 'preset', 'COTTON')
            self.sync_fabric_settings(preset)
        self.cancel_pending_sub()
        content = self.card_rows(target)
        if content is None:
            return
        scale = self.canvas_layout.scale
        bounds = self.canvas_layout.panel
        room = self.canvas_layout.available
        gap = 2 * scale
        width = self.card_layout(target, *content, anchor=(bounds.x, bounds.y + bounds.h))[0].w
        right = parent.x + parent.w + gap
        left = parent.x - gap - width
        inside = right + width <= bounds.x + bounds.w
        x = right if inside or (left < bounds.x and right + width <= room.x + room.w) else left
        self.sub_card, self.sub_owner, self.sub_parent = target, key, self.card_kind
        self.sub_anchor = (x, rect.y + rect.h + 30 * scale)
        self.sub_origin = self.pointer

    def update_submenu(self, point):
        cards = self.visible_cards()
        if not cards:
            return
        parent = cards[0]
        if not parent[0].contains(*point) or (len(cards) > 1 and cards[1][0].contains(*point)):
            self.cancel_pending_sub()
            return
        hovered = next(((rect, row) for rect, row in parent[2] if rect.contains(*point)), None)
        if hovered is None:
            return
        rect, row = hovered
        key = row[1] if row[0] == 'MENU' and row[1] in HOVER_MENUS else None
        if key == self.sub_owner:
            self.sub_origin = point
            self.cancel_pending_sub()
        elif len(cards) > 1 and heading_to(self.sub_origin, point, cards[1][0], 20 * self.canvas_layout.scale):
            self.sub_pending = None
            self.schedule_sub(key, rect, parent[0])
        else:
            self.close_sub()
            if key:
                self.schedule_sub(key, rect, parent[0])

    def card_rows(self, kind):
        scene = self._scene
        doc = self.session.document
        pattern = doc.find(self.session.selected)
        anchor = next((a for a in doc.anchors if a.id == self.selected_anchor), None)
        rows = []
        title = kind.title()
        if kind == 'GARMENT':
            title = 'Garment'
            customs = list(getattr(doc, 'custom_presets', {}).keys())
            all_fabrics = list(FABRICS) + customs
            has_sim = any(obj.get('dd_kind') == 'simulation' for obj in scene.objects)
            rows = [('NAME', scene.dd_library_name or 'Untitled garment', 'Rename'),
                    ('CHOICES_FABRIC', 'Default fabric', ('INSP_GARMENT_FABRIC', all_fabrics, getattr(doc, 'preset', 'COTTON'))),
                    ('MENU', 'GARMENT_FABRIC_MENU', 'Fabric behavior', getattr(doc, 'preset', 'COTTON').title()),
                    ('CHOICES', 'Mesh density', ('INSP_GARMENT_DENSITY', DENSITY, self.named_choice(scene.dd_spacing, DENSITY)))]
            if not doc.patterns:
                rows.append(('PAIR_ACTIONS', 'STARTER_TEE', 'REFERENCE_IMAGE', 'Tee starter', 'Trace image'))
            elif has_sim:
                rows.append(('PAIR_ACTIONS', 'LIBRARY_SAVE', 'RESET', 'Save As...', 'Reset drape'))
            else:
                rows.append(('PAIR_ACTIONS', 'LIBRARY_SAVE', 'REFERENCE_IMAGE', 'Save As...', 'Trace image'))
        elif kind == 'BODY':
            title = 'Body'
            rows = [('AVATAR_FIELD', LABEL)]
            rows.append(('CHOICES', 'Body opacity', ('INSP_OPACITY', GUIDE_OPACITY, self.named_choice(scene.dd_reference_opacity, GUIDE_OPACITY))))
            measurements = getattr(getattr(self, 'reference', None), 'measurements', None)
            if measurements:
                rows.append(('INFO', 'Height', f"{measurements['height']:.1f} cm"))
                rows.append(('INFO', 'Chest', f"{measurements['chest']:.1f} cm"))
                rows.append(('INFO', 'Waist', f"{measurements['waist']:.1f} cm"))
                rows.append(('INFO', 'Hips', f"{measurements['hip']:.1f} cm"))
                rows.append(('INFO', 'Shoulders', f"{measurements['shoulder_width']:.1f} cm"))
                rows.append(('INFO', 'Torso length', f"{measurements['torso_length']:.1f} cm"))
                rows.append(('INFO', 'Inseam', f"{measurements['inseam']:.1f} cm"))
                if measurements.get('fallback'):
                    rows.append(('INFO', 'Landmarks', 'Estimated by height'))
            elif scene.dd_avatar:
                rows.append(('INFO', 'Measurements', 'Select body to refresh'))
            else:
                rows.append(('INFO', 'Measurements', 'Select a body mesh'))
            if scene.dd_avatar is not None and not self.pending_simulation:
                from .arrangement import pending_job
                if pending_job(bpy.context) is not None:
                    rows.append(('INFO', 'Arrangement points', 'Preparing…'))
                rows.append(('PAIR_ACTIONS', 'REFRESH_FIT', 'RESET_POINTS', 'Refresh fit', 'Reset points'))
        elif kind == 'LIBRARY':
            title = 'Garment library'
            matches=self.library_matches()
            page_size=self.library_page_size()
            max_pages = max(1, math.ceil(len(matches) / page_size))
            self.card_page = max(0, min(self.card_page, max_pages - 1))
            rows=[('LIBRARY_SEARCH','Search',self.library_query),
                  ('MENU','LIBRARY_TAGS','Tags',self.library_filter or 'All tags')]
            rows.extend(('LOAD_'+str(index),self.library_previews[path]['name'],'Preview')
                        for index,path in matches[self.card_page*page_size:(self.card_page+1)*page_size])
            if not matches:rows.append(('INFO','Library unavailable' if self.library_error else 'No matching garments' if self.library_items else 'No saved garments',self.library_error or 'Clear search or save a design'))
            if max_pages>1:rows.append(('PAGE_LIBRARY',f'Page {self.card_page+1} of {max_pages}','Next'))
            rows.append(('LIBRARY_SAVE','Save As...','Choose a name and tags'))
        elif kind == 'LIBRARY_TAGS':
            title='Filter by tag'
            tags=sorted({tag for metadata in self.library_previews.values() for tag in metadata['tags']},key=str.casefold)
            rows=[('LIBRARY_TAG_ALL','All tags','')]
            start=self.card_page*6
            rows.extend(('LIBRARY_TAG_'+str(index),tag,'Selected' if tag==self.library_filter else '')
                        for index,tag in enumerate(tags) if start<=index<start+6)
            if len(tags)>6:rows.append(('PAGE_LIBRARY_TAGS','More tags','Next'))
        elif kind == 'LIBRARY_SAVE':
            title = 'Save garment'
            rows = [('LIBRARY_NAME', 'Garment name', scene.dd_library_name),
                    ('LIBRARY_TAG_EDIT', 'Tags', self.library_tags or 'Comma separated'),
                    ('LIBRARY_WRITE', 'Save', ''),
                    ('MENU_LIBRARY', 'Cancel', '')]
        elif kind == 'LIBRARY_PREVIEW':
            metadata=self.library_previews.get(self.library_preview_path)
            title='Garment preview'
            if metadata:
                index=self.library_items.index(self.library_preview_path)
                rows=[('PREVIEW_'+str(index),metadata['name'],''),
                      ('INFO',metadata['name'],f"{metadata['pieces']} pieces | {metadata['seams']} seams"),
                      ('INFO','Body',metadata['body']),('INFO','Saved',metadata['date']),
                      ('INFO','Tags',', '.join(metadata['tags']) or 'No tags')]
                if metadata['error']:rows.append(('INFO','Cannot load',metadata['error']))
                else:rows.append(('LIBRARY_ACCEPT_LOAD','Load garment','Refit to current body height' if scene.dd_library_refit else 'Keep saved size'))
            else:rows=[('INFO','Garment no longer available','Choose another design')]
            rows.append(('MENU_LIBRARY','Back to library',''))
        elif kind == 'SIMULATE':
            title = 'Simulate'
            self.card_models = layering.kept_garments(scene)
            self.wear_over_offset = max(0,min(self.wear_over_offset,len(self.card_models)-5))
            rows = [('RESET', 'Reset drape', 'Back to panels')]
            rows += [('WEAR_OVER_' + str(index), obj.name, 'On' if obj.get('dd_wear_over',True) else 'Off')
                     for index,obj in enumerate(self.card_models) if self.wear_over_offset <= index < self.wear_over_offset+5]
            if len(self.card_models)>5:
                rows.append(('SCROLL_WEAR_OVER',f'{self.wear_over_offset+1}-{min(self.wear_over_offset+5,len(self.card_models))} of {len(self.card_models)} garments','Next'))
        elif kind == 'KEEP':
            title = 'Keep mesh'
            info = self.triangle_budget()
            rows = []
            if info:
                rows.append(('INFO', 'Triangles', f"{'~' if info['estimated'] else ''}{info['garment']:,}"))
                if info['body']:
                    rows += [('INFO', 'With avatar', f"{info['total']:,}"), ('INFO', 'VRChat PC', info['pc']), ('INFO', 'VRChat Quest', info['quest'])]
            rows += [('WELD_AUTO', 'Weld', 'Manual' if self.weld_manual else 'Auto'),
                    ('CHOICES', 'Thickness', ('THICKNESS', THICKNESS, self.named_choice(scene.dd_thickness, THICKNESS))),
                    ('CHOICES', 'Faces', ('KEEP_FACES', ('Triangles', 'Quads'), 'Quads' if scene.dd_keep_quads else 'Triangles'))]
            if scene.get('dd_unwelded_seams', 0) > 0:
                rows += [('SLIDER', 'dd_weld_distance', 'Weld tolerance'), ('KEEP_RETRY', 'Retry keep', f"{scene['dd_unwelded_seams']} unwelded pairs")]
        elif kind == 'PIECE_FABRIC':
            if pattern is None:
                return None
            title = 'Fabric override'
            rows = [('SET_PIECE_FABRIC_AUTO', 'Garment default', '')]
            customs = list(getattr(doc, 'custom_presets', {}).keys())
            all_presets = list(FABRICS) + customs
            active = pattern.preset if getattr(pattern, 'fabric_override', False) else getattr(doc, 'preset', 'COTTON')
            rows.append(('CHOICES_FABRIC', 'Fabric preset', ('SET_PIECE_FABRIC', all_presets, active)))
            rows.append(('SLIDER', 'dd_fabric_structural', 'Stretch stiffness'))
            rows.append(('SLIDER', 'dd_fabric_bending', 'Bending stiffness'))
            rows.append(('SLIDER', 'dd_fabric_density', 'Mass density'))
            rows.append(('SLIDER', 'dd_fabric_weft', 'Weft stretch'))
            rows.append(('SLIDER', 'dd_fabric_bias', 'Bias stiffness'))
            rows.append(('SLIDER', 'dd_fabric_shrink_warp', 'Shrink lengthwise'))
            rows.append(('SLIDER', 'dd_fabric_shrink_weft', 'Shrink widthwise'))
            rows.append(('SAVE_PIECE_CUSTOM_PRESET', 'Save as custom preset', ''))
            if getattr(pattern, 'fabric_override', False) and pattern.preset in getattr(doc, 'custom_presets', {}):
                rows.append(('DELETE_CUSTOM_PRESET', 'Delete preset', ''))
        elif kind == 'GARMENT_FABRIC':
            title = 'Garment fabric'
            active = getattr(doc, 'preset', 'COTTON')
            rows.append(('INFO', 'Preset', active.title()))
            rows.append(('SLIDER', 'dd_fabric_structural', 'Stretch stiffness'))
            rows.append(('SLIDER', 'dd_fabric_bending', 'Bending stiffness'))
            rows.append(('SLIDER', 'dd_fabric_density', 'Mass density'))
            rows.append(('SLIDER', 'dd_fabric_weft', 'Weft stretch'))
            rows.append(('SLIDER', 'dd_fabric_bias', 'Bias stiffness'))
            rows.append(('SLIDER', 'dd_fabric_shrink_warp', 'Shrink lengthwise'))
            rows.append(('SLIDER', 'dd_fabric_shrink_weft', 'Shrink widthwise'))
            rows.append(('SAVE_GARMENT_CUSTOM_PRESET', 'Save as custom preset', ''))
            if active in getattr(doc, 'custom_presets', {}):
                rows.append(('DELETE_CUSTOM_PRESET', 'Delete preset', ''))
        elif kind == 'PIECE_DENSITY':
            title = 'Mesh density override'
            rows = [('SET_DENSITY_AUTO', 'Garment default', ''),
                    ('SET_DENSITY_COARSE', 'Coarse', ''),
                    ('SET_DENSITY_STANDARD', 'Standard', ''),
                    ('SET_DENSITY_FINE', 'Fine', ''),
                    ('SET_DENSITY_ULTRA', 'Ultra', '')]
        elif kind == 'PIECE_SIMULATION':
            if pattern is None:
                return None
            title = 'Piece simulation'
            rows = [('TOGGLE_STATE_frozen', 'Unfreeze' if pattern.frozen else 'Freeze', 'Hold 3D shape'),
                    ('TOGGLE_STATE_deactivated', 'Activate' if pattern.deactivated else 'Deactivate', 'Skip simulation'),
                    ('TOGGLE_STATE_strengthened', 'Remove strengthen' if pattern.strengthened else 'Strengthen', '4× fabric stiffness'),
                    ('PAIR_ACTIONS', 'PUFF_10', 'PUFF_20', 'Puff 10%', 'Puff 20%'),
                    ('CLEAR_STEAM', 'Clear puff and steam', '')]
        elif kind == 'PIECE':
            if pattern is None:
                return None
            title = pattern.name
            outline = pattern.outline()
            xs = [p[0] for p in outline]
            ys = [p[1] for p in outline]
            pw = (max(xs) - min(xs)) * 100
            ph = (max(ys) - min(ys)) * 100
            rows.append(('INFO', 'Size', f'{pw:.1f} × {ph:.1f} cm'))
            fabric_override = pattern.preset.title() if getattr(pattern, 'fabric_override', False) else 'Garment default'
            rows.append(('MENU', 'PIECE_FABRIC_MENU', 'Fabric', fabric_override))
            density_label = {'AUTO': 'Garment default', 'COARSE': 'Coarse', 'STANDARD': 'Standard', 'FINE': 'Fine', 'ULTRA': 'Ultra'}.get(pattern.mesh_density, pattern.mesh_density.title())
            rows.append(('MENU', 'PIECE_DENSITY_MENU', 'Mesh density', density_label))
            from .piece_states import label
            simulation_label = label(pattern).replace(' · Strengthened ×4', ' +4×')
            rows.append(('MENU', 'PIECE_SIMULATION_MENU', 'Simulation', simulation_label or 'Normal'))
            rows.append(('MENU', 'PIECE_PLACEMENT_MENU', 'Placement', ('Flat' if pattern.arrangement['flat'] else 'Wrap') if pattern.arrangement else '2D layout'))
            rows.append(('MENU', 'PIECE_CLONE_MENU', 'Clone', ''))
            rows.append(('MENU', 'TRANSFORM_MENU', 'Transform', ''))
            rows.append(('DELETE_PIECE', 'Delete', 'Del'))
        elif kind == 'PIECE_PLACEMENT':
            if pattern is None:
                return None
            title = 'Placement'
            record = pattern.arrangement
            if record:
                rows.append(('CHOICES', 'Placement', ('PLACE_SHAPE', ('Wrap', 'Flat'), 'Flat' if record['flat'] else 'Wrap')))
                if record['version'] != 3:
                    rows.append(('PLACE_UPGRADE', 'Use body-checked wrap', 'Keeps point'))
                elif not record['flat']:
                    distance = next(name for name, value in PLACEMENT_DISTANCE.items() if value == record['clearance']) if record['clearance'] in PLACEMENT_DISTANCE.values() else f"{record['clearance'] * 100:.1f} cm"
                    rows.append(('CHOICES', 'Distance from body', ('PLACE_DISTANCE', tuple(PLACEMENT_DISTANCE), distance)))
                    overlap = next(name for name, value in PLACEMENT_OVERLAP.items() if value == (record['overwrap'], record['direction']) or (not record['overwrap'] and not value[0]))
                    rows.append(('CHOICES', 'Overwrap', ('PLACE_OVERLAP', tuple(PLACEMENT_OVERLAP), overlap)))
            rows.append(('PAIR_ACTIONS', 'SUPERIMPOSE_OVER', 'SUPERIMPOSE_UNDER', 'Over sewn piece', 'Under sewn piece'))
            rows.append(('RESET_LAYOUT', 'Reset to 2D layout', ''))
        elif kind == 'PIECE_CLONE':
            if pattern is None:
                return None
            title = 'Clone'
            rows.append(('PAIR_ACTIONS', 'DUPLICATE', 'MIRROR_PICK', 'Duplicate', 'Mirror'))
            rows.append(('PAIR_ACTIONS', 'LAYER_OVER', 'LAYER_UNDER', 'Layer over', 'Layer under'))
            rows.append(('CLONE_LINKED', 'Clone as linked twin', ''))
            if pattern.arrangement and pattern.arrangement['point']=='front':
                rows.append(('CLONE_BACK', 'Clone as Back', ''))
            from .linked_editing import pair_for
            linked=pair_for(doc,pattern.id)
            rows.append(('TOGGLE_LINKED', 'Linked twin', 'On' if linked and linked['enabled'] else 'Off'))
        elif kind == 'CANVAS_MENU':
            title = 'Garment & View'
            if not doc.patterns:
                rows.append(('MENU', 'STARTERS_MENU', 'Starters', ''))
            rows.append(('MENU', 'MENU_GARMENT', 'Garment settings', getattr(doc, 'preset', 'COTTON').title()))
            rows.append(('CHOICES', 'Mesh density', ('INSP_GARMENT_DENSITY', DENSITY, self.named_choice(scene.dd_spacing, DENSITY))))
            rows.append(('CHOICES', 'Quality', ('INSP_QUALITY', QUALITY, self.named_choice(scene.dd_quality, QUALITY))))
            rows.append(('CHOICES', 'Skin offset', ('INSP_SKIN', SKIN_OFFSET, self.named_choice(scene.dd_skin_offset, SKIN_OFFSET))))
            rows.append(('CHOICES', 'Friction', ('INSP_FRICTION', FRICTION, self.named_choice(scene.dd_friction, FRICTION))))
            rows.append(('INSP_FIT', 'Fit design', 'Home'))
        elif kind == 'STARTERS':
            title = 'Starters'
            rows = [('PAIR_ACTIONS', 'STARTER_TEE', 'STARTER_TANK', 'Tee', 'Tank'),
                    ('PAIR_ACTIONS', 'STARTER_LONG_SLEEVE', 'STARTER_HOODIE', 'Long sleeve', 'Hoodie'),
                    ('PAIR_ACTIONS', 'STARTER_JACKET', 'STARTER_DRESS', 'Jacket', 'Dress'),
                    ('PAIR_ACTIONS', 'STARTER_SKIRT', 'STARTER_PANTS', 'Skirt', 'Pants'),
                    ('DEMO_PANEL', 'Create panel', '')]
        elif kind == 'POINT':
            title = 'Point'
            v = None
            if pattern and self.session.corner is not None:
                try:
                    v = pattern.path(self.session.path).vertices[self.session.corner]
                except (IndexError, ValueError):
                    pass
            active_type = getattr(v, 'point_type', 'CORNER').title() if v else 'Corner'
            rows = [('CHOICES', 'Point type', ('POINT_TYPE', ('Corner', 'Smooth', 'Auto'), active_type)),
                    ('SLIDER', 'dd_point_x', 'X position'),
                    ('SLIDER', 'dd_point_y', 'Y position'),
                    ('CHOICES', 'Round corner', ('ROUND_CORNER', ('1 cm', '2 cm', '5 cm'), '')),
                    ('MENU', 'TRANSFORM_MENU', 'Transform', '')]
            if len(self.session.point_selection) > 1:
                rows.append(('MERGE', 'Merge selected points', ''))
            if pattern and self.session.path != 'OUTER':
                rows.append(('PATH_ACTIONS', 'Internal path actions', 'Cut, fold, offset'))
        elif kind == 'EDGE':
            title = 'Edge'
            edge = self.session.segment
            elastic = next((record['shrink'] for record in doc.elastics if edge and (record['pattern'], record['start'], record['end']) == (edge.pattern, edge.start, edge.end)), 0)
            rows = [('SLIDER', 'dd_segment_length', 'Exact length'),
                    ('CHOICES', 'Elastic', ('EDGE_ELASTIC', ('0%', '10%', '20%', '30%'), f'{elastic}%')),
                    ('PAIR_ACTIONS', 'BEND_EDGE', 'SPLIT', 'Bend', 'Split'),
                    ('CHOICES', 'Split into', ('SPLIT_INTO', SPLIT_PARTS, '')),
                    ('PAIR_ACTIONS', 'UNFOLD', 'MIRROR_SEW', 'Unfold', 'Mirror')]
            if edge and any(item.full() == edge.full() for seam in doc.seams for side in (0, 1) for item in seam.side(side)):
                rows.append(('MERGE_PIECES', 'Merge sewn pieces', ''))
            if pattern and any(feature.get('type') == 'FOLD' for feature in pattern.features):
                rows.append(('PLEAT_SEW', 'Sew pleats closed', ''))
        elif kind == 'INTERNAL_EDGE':
            title = 'Internal edge'
            rows = [('SLIDER', 'dd_segment_length', 'Exact length'),
                    ('PAIR_ACTIONS', 'BEND_EDGE', 'SPLIT', 'Bend', 'Split'),
                    ('CHOICES', 'Split into', ('SPLIT_INTO', SPLIT_PARTS, '')),
                    ('MENU', 'FOLD_MENU', 'Fold or pleat', 'Straight boundary-to-boundary path'),
                    ('CHOICES', 'Offset copy', ('OFFSET_PATH', ('-2 cm', '-1 cm', '+1 cm', '+2 cm'), '')),
                    ('CHOICES', 'Slash and spread', ('SLASH_SPREAD', ('5 deg', '10 deg', '15 deg', '30 deg'), '')),
                    ('CUT', 'Cut out hole' if pattern and pattern.path(self.session.path).closed else 'Cut along path', ''),
                    ('MENU', 'TRANSFORM_MENU', 'Transform', '')]
            if pattern and pattern.path(self.session.path).closed:
                rows.append(('TRACE', 'Trace as piece', ''))
        elif kind == 'FOLD':
            title = 'Fold or pleat'
            from .folding import fold_records
            records = fold_records(pattern) if pattern else []
            feature = next((feature for path, feature in records if path.id == self.session.path), None)
            if feature:
                rows = [('INFO', 'Direction', 'Mountain' if feature['angle'] > 0 else 'Valley'),
                        ('FOLD_EDIT_REVERSE', 'Reverse direction', 'Entire pleat'),
                        ('PAIR_ACTIONS', 'FOLD_EDIT_30', 'FOLD_EDIT_90', '30 degrees', '90 degrees'),
                        ('PAIR_ACTIONS', 'FOLD_EDIT_60', 'FOLD_EDIT_120', '60 degrees', '120 degrees'),
                        ('FOLD_EDIT_150', 'Sharp fold', '150 degrees'),
                        ('FOLD_EDIT_REMOVE', 'Remove fold or pleat', 'Keep internal paths')]
            else:
                rows = [('PAIR_ACTIONS', 'FOLD_ADD_MOUNTAIN_2', 'FOLD_ADD_VALLEY_2', 'Mountain', 'Valley'),
                        ('INFO', 'Pleat depth', 'Distance between fold lines'),
                        ('PAIR_ACTIONS', 'FOLD_ADD_KNIFE_1', 'FOLD_ADD_BOX_1', 'Knife 1 cm', 'Box 1 cm'),
                        ('PAIR_ACTIONS', 'FOLD_ADD_KNIFE_2', 'FOLD_ADD_BOX_2', 'Knife 2 cm', 'Box 2 cm'),
                        ('PAIR_ACTIONS', 'FOLD_ADD_KNIFE_4', 'FOLD_ADD_BOX_4', 'Knife 4 cm', 'Box 4 cm'),
                        ('PAIR_ACTIONS', 'FOLD_ADD_ACCORDION_1', 'FOLD_ADD_ACCORDION_2', 'Accordion 1 cm', 'Accordion 2 cm'),
                        ('INFO', 'Straight lines across fabric', 'Parallel folds per piece')]
        elif kind == 'ANCHOR':
            if anchor is None:
                return None
            title = {'TACK': 'Body tack', 'JOIN': 'Fabric tack'}.get(anchor.kind, 'Pin')
            rows = [('INFO', 'Attached to', pattern.name if pattern else 'Pattern'),
                    ('REMOVE_ANCHOR', 'Remove pin' if anchor.kind == 'PIN' else 'Remove tack', 'Delete')]
        elif kind == 'SEAM':
            seam = next((s for s in doc.seams if s.id == self.seam_selected), None)
            title = 'Selected seam'
            if seam:
                _, _, diff, pct = doc.seam_stats(seam)
                rows.append(('INFO', 'Mismatch', f'{diff * 100:.1f} cm ({pct:.1f}%)'))
                rows.append(('CHOICES', 'Sewing', ('SEAM_ACTIVE', ('On', 'Off'), 'On' if seam.active else 'Off')))
                rows.append(('CHOICES', 'Shrink', ('SEAM_SHRINK', ('0%', '10%', '20%', '30%'), f'{seam.shrink}%')))
                if seam.shrink:
                    rows.append(('CHOICES', 'Shrink on', ('SEAM_EASE', ('Both', 'First edge', 'Second edge'), ('Both', 'First edge', 'Second edge')[seam.ease_side])))
                names = [doc.find(seam.side(side)[0].pattern).name[:14] for side in (0, 1)]
                rows.append(('PAIR_ACTIONS', 'SEAM_LENGTH_0', 'SEAM_LENGTH_1', 'Length: ' + names[0], 'Length: ' + names[1]))
            rows.append(('PAIR_ACTIONS', 'FLIP_SEAM', 'REMOVE_SEAM', 'Reverse', 'Remove'))
        elif kind == 'REFERENCE_IMAGE':
            title = 'Reference image'
            from .tracing import reference_count
            count = reference_count(scene)
            if scene.dd_trace_path:
                rows = [('PAIR_ACTIONS', 'TRACE_LOAD', 'TRACE_ADD', 'Replace image', 'Add image')]
                if count > 1:
                    rows.append(('TRACE_NEXT', f'Image 1 of {count}', 'Next image'))
                if not scene.dd_trace_locked:
                    rows += [('TRACE_CALIBRATION', 'Set measured scale', ''),
                             ('TRACE_POSITION', 'Image placement', '')]
                rows += [('PAIR_ACTIONS', 'TRACE_VISIBLE', 'TRACE_LOCK', 'Hide' if scene.dd_trace_visible else 'Show',
                          'Unlock' if scene.dd_trace_locked else 'Lock'),
                         ('CHOICES', 'Image opacity', ('TRACE_OPACITY', IMAGE_OPACITY, self.named_choice(scene.dd_trace_opacity, IMAGE_OPACITY))),
                         ('TRACE_REMOVE', 'Remove image', '')]
            else:
                rows = [('TRACE_LOAD', 'Load image', 'Choose file')]
            if scene.dd_trace_error:
                rows.append(('INFO', 'Image unavailable', scene.dd_trace_error))
        elif kind == 'TRACE_CALIBRATION':
            title = 'Measured scale'
            rows = [('SLIDER', 'dd_trace_length', 'Known length'),
                    ('TRACE_PICK', 'Pick length endpoints', 'Two clicks on image'),
                    ('INFO', 'Scale only', 'Cannot correct photo distortion')]
        elif kind == 'TRACE_POSITION':
            title = 'Image placement'
            rows = [('TRACE_DRAG', 'Move on canvas', 'Drag the image'),
                    ('SLIDER', 'dd_trace_width', 'Width'), ('SLIDER', 'dd_trace_x', 'X position'),
                    ('SLIDER', 'dd_trace_y', 'Y position'), ('SLIDER', 'dd_trace_rotation', 'Rotation'),
                    ('PAIR_ACTIONS', 'TRACE_FLIP_X', 'TRACE_FLIP_Y', 'Mirror H', 'Mirror V'),
                    ('TRACE_FIT', 'Fit image and pieces', '')]
        elif kind == 'MULTI_SELECTION':
            pieces, points = self.session.selection_counts()
            if pieces > 0 and points > 0:
                title = f'{pieces} pieces, {points} points'
                rows = [('MENU', 'TRANSFORM_MENU', 'Transform', ''),
                        ('DELETE', 'Delete', 'Del')]
            elif pieces > 0:
                title = f'{pieces} pieces'
                rows = [('DUPLICATE', 'Duplicate', 'Shift+D'),
                        ('PAIR_ACTIONS', 'FLIP_H', 'FLIP_V', 'Flip H', 'Flip V'),
                        ('MENU', 'TRANSFORM_MENU', 'Transform', ''),
                        ('MENU', 'PIECE_FABRIC_MENU', 'Fabric', ''),
                        ('MENU', 'PIECE_DENSITY_MENU', 'Mesh density', ''),
                        ('DELETE', 'Delete', 'Del')]
                if pieces==2:
                    from .linked_editing import pair_for
                    linked=pair_for(doc,self.session.selected)
                    rows.append(('TOGGLE_LINKED', 'Linked twin', 'On' if linked and linked['enabled'] else 'Off'))
            else:
                title = f'{points} points'
                first_pt = next(iter(self.session.selected_points), None)
                active_type = 'Corner'
                if first_pt:
                    p_pat = doc.find(first_pt[0])
                    if p_pat:
                        try:
                            v = p_pat.path(first_pt[1]).vertices[first_pt[2]]
                            active_type = getattr(v, 'point_type', 'CORNER').title()
                        except (IndexError, ValueError):
                            pass
                rows = [('CHOICES', 'Point type', ('POINT_TYPE', ('Corner', 'Smooth', 'Auto'), active_type))]
                if self.session.can_merge_selected_points():
                    rows.append(('MERGE', 'Merge points', 'M'))
                rows.append(('PAIR_ACTIONS', 'FLIP_H', 'FLIP_V', 'Flip H', 'Flip V'))
                rows.append(('MENU', 'TRANSFORM_MENU', 'Transform', ''))
                rows.append(('DELETE', 'Delete', 'Del'))
        elif kind == 'CUT_RECOVERY':
            title = 'Crossing cut'
            preview = self.cut_preview
            if not preview:
                return None
            rows = [('INFO', 'Cut needs attention', preview['reason'])]
            if preview['can_retry']:
                rows.append(('CUT_RETRY', 'Split and retry', f"{preview['split_count']} splits"))
            rows.append(('CANCEL_CUT', 'Back to editing', ''))
        elif kind == 'TRANSFORM_MENU':
            title = 'Transform'
            rows = [('TRANSFORM_MOVE', 'Move', 'Arrows'),
                    ('TRANSFORM_ROTATE', 'Rotate', 'Degrees'),
                    ('TRANSFORM_SCALE', 'Uniform scale', 'Factor or %'),
                    ('TRANSFORM_SET_PIVOT', 'Set pivot', 'Cursor click'),
                    ('TRANSFORM_RESET_PIVOT', 'Reset pivot', 'Center'),
                    ('PAIR_ACTIONS', 'FLIP_H', 'FLIP_V', 'Flip H', 'Flip V')]
            if pattern and self.session.corner is None and not self.session.selected_points:
                rows.append(('CHOICES', 'Offset copy', ('OFFSET_OUTLINE', ('-1 cm', '+1 cm', '+2 cm', '+5 cm'), '')))
            if len(self.session.selected_patterns) > 1:
                rows.append(('CHOICES', 'Align', ('ALIGN', ('Left', 'Center', 'Right'), '')))
                rows.append(('CHOICES', 'Align vertically', ('ALIGN', ('Top', 'Middle', 'Bottom'), '')))
                if len(self.session.selected_patterns) > 2:
                    rows.append(('PAIR_ACTIONS', 'DISTRIBUTE_X', 'DISTRIBUTE_Y', 'Distribute H', 'Distribute V'))
        elif kind == 'SEAM_WARNING':
            pre = getattr(self, 'pending_transform', None) or {}
            report = pre.get('report') if isinstance(pre, dict) and 'report' in pre else pre
            seam_warning = bool(report.get('details'))
            title = 'Seam warning' if seam_warning else 'Curve warning'
            rows = []
            if seam_warning:
                rows.append(('INFO', 'Mismatch', f"{report.get('diff_cm', 0.0):.2f} cm ({report.get('percent', 0.0):.4f}%)"))
            if report.get('curve_deviation_mm') is not None:
                rows.append(('INFO', 'Curve change', f"{report['curve_deviation_mm']:.3f} mm"))
                if report.get('exact_candidate') is not None:
                    rows.append(('CONVERT_AUTO', 'Convert to smooth', f"{report.get('auto_point_count', 0)} AUTO pts"))
            rows.append(('PAIR_ACTIONS', 'CANCEL_TRANSFORM', 'APPLY_MISMATCH', 'Cancel',
                         'Apply with mismatch' if seam_warning else 'Apply with change'))
            if report.get('can_include_sewn'):
                rows.append(('INCLUDE_SEWN', 'Include sewn pieces', 'Closure'))
        else:
            return None
        return title, rows

    def card_layout(self, kind, title, rows, anchor=None):
        scene = self._scene
        scale = self.canvas_layout.scale
        is_menu = kind in MENU_CARDS or kind == 'SEAM_WARNING' or kind.endswith('_MENU')
        row_widths = []
        for r in rows:
            r_key = r[0]
            label = r[1] if len(r) > 1 else ''
            val = r[2] if len(r) > 2 else ''
            if r_key == 'MENU':
                label = r[2]
                val = r[3] if len(r) > 3 else ''
            elif r_key == 'SLIDER':
                spec = CONTROL_SETTINGS[r[1]]
                label = r[2]
                val = spec.display(getattr(scene, r[1])) + ' ' + spec.unit
            val_str = str(val) if val and val != 'Selected' and not isinstance(val, tuple) else ''
            if r_key == 'CHOICES_FABRIC' and isinstance(val, tuple) and len(val) >= 2:
                row_widths.append(sum(text_unscaled_width(str(c), 10) + 16 for c in val[1][:4]) + 30)
            elif r_key == 'CHOICES' and isinstance(val, tuple) and len(val) >= 2:
                row_widths.append(sum(text_unscaled_width(str(c), 10) + 16 for c in val[1]) + 30)
            elif r_key == 'PAIR_ACTIONS' and len(r) >= 5:
                row_widths.append(text_unscaled_width(r[3], 10) + text_unscaled_width(r[4], 10) + 48)
            elif r_key == 'SLIDER':
                row_widths.append(text_unscaled_width(label, 10) + text_unscaled_width(val_str, 11) + 44)
            elif r_key == 'MENU':
                row_widths.append(text_unscaled_width(label, 11) + text_unscaled_width(val_str, 10) + 58)
            else:
                has_nav = r_key == 'MENU' or r_key.endswith('_MENU') or r_key.startswith('PAGE_') or r_key in {'LIBRARY_SAVE', 'LIBRARY_TAGS', 'MENU_LIBRARY', 'MENU_GARMENT'}
                icon_w = 24 if (val == 'Selected' or has_nav) else 10
                row_widths.append(text_unscaled_width(label, 11) + (text_unscaled_width(val_str, 10) + 16 if val_str else 0) + icon_w + 32)
        if title:
            row_widths.append(text_unscaled_width(title, 13) + 60)

        card_widths = {
            'GARMENT_FABRIC': 304,
            'PIECE_FABRIC': 304,
            'LIBRARY': 480,
            'LIBRARY_PREVIEW': 420,
            'LIBRARY_SAVE': 360,
        }
        nominal = card_widths.get(kind, 180 if is_menu else 280)
        target_w = max(nominal, max(row_widths) if row_widths else nominal)
        width = round(min(target_w * scale, self.canvas_layout.panel.w - 24 * scale))
        bounds = self.canvas_layout.panel
        max_card_h = max(1, math.floor(bounds.h - 16 * scale))
        anchor_pt = anchor or self.card_anchor or (bounds.x + 80 * scale, bounds.y + bounds.h - 100 * scale)

        def card_bounds(height):
            bottom_pad, top_pad = (58, 34) if height <= bounds.h - 92 * scale else (8, 8)
            card_x = round(anchor[0] if anchor else max(bounds.x + 8 * scale, min(anchor_pt[0], bounds.x + bounds.w - width - 8 * scale)))
            card_y = round(max(bounds.y + bottom_pad * scale, min(anchor_pt[1] - height, bounds.y + bounds.h - height - top_pad * scale)))
            return Rect(card_x, card_y, width, height)

        row_heights = []
        row_gaps = []
        if kind == 'LIBRARY':
            bounds = self.canvas_layout.panel
            load_rows = [r for r in rows if r[0].startswith('LOAD_')]
            header_rows = rows[:2]
            other_rows = [r for r in rows[2:] if not r[0].startswith('LOAD_')]
            grid_rows = math.ceil(len(load_rows) / 2)
            tile_nominal_h = 168
            max_card_h = max(1, min(max_card_h, math.floor(bounds.h - 92 * scale)))
            compact = max_card_h / scale < 380
            row_pitch = 26 if compact else 34
            other_h = round(sum(row_pitch * scale for _ in other_rows))
            header_h = round(sum(row_pitch * scale for _ in header_rows))
            fixed_h = round(48 * scale + header_h + other_h)
            avail_grid_h = max(0, max_card_h - fixed_h)
            if grid_rows > 0:
                needed_grid_h = round(grid_rows * tile_nominal_h * scale + (grid_rows - 1) * 6 * scale)
                if needed_grid_h > avail_grid_h:
                    tile_h = max(1, int((avail_grid_h - (grid_rows - 1) * 6 * scale) / grid_rows))
                    grid_h = round(grid_rows * tile_h + (grid_rows - 1) * 6 * scale)
                else:
                    tile_h = round(tile_nominal_h * scale)
                    grid_h = needed_grid_h
            else:
                tile_h = round(tile_nominal_h * scale)
                grid_h = 0
            height = round(fixed_h + grid_h)
            if height > max_card_h:
                height = max_card_h
            rect = card_bounds(height)
            card_x, card_y = rect.x, rect.y
            controls = []
            top = round(card_y + height - 42 * scale)
            inner_w = round(width - 20 * scale)
            for row in header_rows:
                top -= round(row_pitch * scale)
                controls.append((Rect(round(card_x + 10 * scale), top, inner_w, round((row_pitch - 4) * scale)), row))
            col_gap = round(8 * scale)
            col_w = round((inner_w - col_gap) / 2)
            for idx, r in enumerate(load_rows):
                r_idx = idx // 2
                c_idx = idx % 2
                x = round(card_x + 10 * scale + c_idx * (col_w + col_gap))
                y = round(top - (r_idx + 1) * tile_h - r_idx * 6 * scale)
                controls.append((Rect(x, y, col_w, tile_h), r))
            top_other = round((top - grid_h - 6 * scale) if grid_rows > 0 else top)
            for r in other_rows:
                top_other -= round(row_pitch * scale)
                controls.append((Rect(round(card_x + 10 * scale), top_other, inner_w, round((row_pitch - 4) * scale)), r))
            return rect, title, controls
        if is_menu:
            menu_heights = [48 if row[0] == 'CHOICES' else 34 if row[0] == 'SLIDER' else 22 for row in rows]
            gap = 2
            inner_pad = round(4 * scale)
            item_w = round(width - 2 * inner_pad)
            title_h = round(32 * scale)
            content_h = round((sum(menu_heights) + max(0, len(rows) - 1) * gap + 4) * scale)
            height = round(title_h + content_h)
            rect = card_bounds(height)
            card_x, card_y = rect.x, rect.y
            controls = []
            top = round(card_y + height - title_h)
            rg = round(gap * scale)
            for row, row_h in zip(rows, menu_heights):
                rh = round(row_h * scale)
                top -= rh
                controls.append((Rect(round(card_x + inner_pad), top, item_w, rh), row))
                top -= rg
            return rect, title, controls
        for idx, row in enumerate(rows):
            r_key = row[0]
            prev_key = rows[idx - 1][0] if idx > 0 else None
            gap = 4 if idx > 0 and r_key != 'INFO' else (2 if idx > 0 else 0)
            if idx > 0 and (r_key == 'INFO') != (prev_key == 'INFO'):
                gap = 6
            row_gaps.append(gap)
            if r_key == 'CHOICES_FABRIC':
                row_heights.append(math.ceil(len(row[2][1]) / 3) * 24 + 22 if len(row[2][1]) > 4 else 42)
            elif r_key == 'CHOICES':
                row_heights.append(48)
            elif r_key.startswith('PREVIEW_'):
                row_heights.append(180 if self.canvas_layout.panel.h / scale >= 560 else 130)
            elif r_key in {'LIBRARY_NAME', 'LIBRARY_TAG_EDIT'}:
                row_heights.append(46)
            elif r_key in {'INFO', 'AVATAR_FIELD'}:
                row_heights.append(22)
            elif r_key == 'TRACE_PICK':
                row_heights.append(40)
            else:
                row_heights.append(30)
        if kind == 'PIECE':
            choices = sum(r[0] == 'CHOICES' for r in rows)
            avail = self.canvas_layout.panel.h / scale - 130 - sum(row_gaps) - 44 * choices
            row_height = min(30, avail / max(1, len(rows) - choices))
            row_heights = [22 if r[0] == 'INFO' else 44 if r[0] == 'CHOICES' else max(24, row_height) for r in rows]
        excess = max(0, 48 + sum(row_heights) + sum(row_gaps) - max_card_h / scale)
        for index, row in enumerate(rows):
            if row[0].startswith('PREVIEW_'):
                reduction = min(excess, max(0, row_heights[index] - 32))
                row_heights[index] -= reduction
                excess -= reduction
        height = round((48 + sum(row_heights) + sum(row_gaps)) * scale)
        rect = card_bounds(height)
        card_x, card_y = rect.x, rect.y
        controls = []
        top = round(card_y + height - 42 * scale)
        for row, row_h, gap in zip(rows, row_heights, row_gaps):
            rh = round(row_h * scale)
            top -= round((row_h + gap) * scale)
            controls.append((Rect(round(card_x + 10 * scale), top, round(width - 20 * scale), rh), row))
        return rect, title, controls

    def visible_cards(self):
        card = self.minimal_card()
        if card is None:
            return []
        content = self.card_rows(self.sub_card) if self.sub_card and self.sub_parent == self.card_kind else None
        return [card] if content is None else [card, self.card_layout(self.sub_card, *content, anchor=self.sub_anchor)]

    def card_close_rect(self, rect):
        scale = self.canvas_layout.scale
        is_menu = self.card_kind in MENU_CARDS or (bool(self.card_kind) and self.card_kind.endswith('_MENU'))
        if is_menu:
            return Rect(round(rect.x + rect.w - 24 * scale), round(rect.y + rect.h - 24 * scale), round(18 * scale), round(18 * scale))
        return Rect(round(rect.x + rect.w - 30 * scale), round(rect.y + rect.h - 30 * scale), round(22 * scale), round(22 * scale))

    def card_mode_rects(self, rect):
        if self.card_kind not in {'GARMENT', 'BODY'}:
            return {}
        scale = self.canvas_layout.scale
        y = round(rect.y + rect.h - 30 * scale)
        w = round(64 * scale)
        h = round(22 * scale)
        x_garment = round(rect.x + 14 * scale)
        x_body = round(x_garment + w + 2 * scale)
        return {
            'GARMENT': Rect(x_garment, y, w, h),
            'BODY': Rect(x_body, y, w, h),
        }

    def tool_owner(self):
        tool = self.tool
        if self._scene.dd_internal_mode or tool in {'INTERNAL', 'DART', 'KNIFE'} or (tool == 'PEN' and self.pen_mode == 'GARMENT'):
            return 'INTERNAL'
        if tool in {'RECTANGLE', 'POLYGON', 'ELLIPSE', 'PEN'}:
            return 'DRAW'
        if tool in {'PIN', 'PIN_BOX', 'PIN_EDGE', 'TACK', 'TACK_FABRIC'}:
            return 'PIN'
        return {'SELECT': 'SELECT', 'SEW': 'SEW', 'SHAPE': 'SHAPE'}.get(tool)

    def tool_strip(self, owner=None):
        owner = owner or self.tool_owner()
        tool = self.tool
        if owner == 'SELECT':
            target = self.session.acquisition_target
            items = [('SET_SELECT_TARGET_Pieces', 'Pieces', target == 'PIECES'), ('SET_SELECT_TARGET_Points', 'Points', target == 'POINTS'),
                     ('SET_SELECT_TARGET_Edges', 'Edges', target == 'EDGES'), ('SET_SELECT_TARGET_Internal paths', 'Paths', target == 'PATHS'),
                     ('SELECT_LASSO', 'Lasso', self.armed_selection == 'SELECT_LASSO')]
            if self.session.document.patterns:
                items += [('SELECT_ALL', 'All', False), ('SELECT_INVERT', 'Invert', False),
                          ('SELECT_CONNECTED_SEWN', 'Sewn', False)]
            return items
        if owner == 'INTERNAL':
            shape = self._scene.dd_internal_mode and tool
            return [('SET_INTERNAL_PATH', 'Line', tool == 'INTERNAL'), ('SET_INTERNAL_RECT', 'Rectangle', shape == 'RECTANGLE'),
                    ('SET_INTERNAL_ELLIPSE', 'Ellipse', shape == 'ELLIPSE'), ('SET_INTERNAL_DART', 'Dart', tool == 'DART'),
                    ('KNIFE_MODE_SEW', 'Cut and sew', tool == 'KNIFE' and self.knife_sew),
                    ('KNIFE_MODE_CUT', 'Cut', tool == 'KNIFE' and not self.knife_sew), ('PEN_GARMENT', 'On garment', tool == 'PEN')]
        if owner == 'DRAW':
            return [('SET_DRAW_RECTANGLE', 'Rectangle', tool == 'RECTANGLE'), ('SET_DRAW_POLYGON', 'Polygon', tool == 'POLYGON'),
                    ('SET_DRAW_ELLIPSE', 'Ellipse', tool == 'ELLIPSE'), ('PEN_AVATAR', 'On avatar', tool == 'PEN')]
        if owner == 'SEW':
            free = self._scene.dd_free_sewing
            return [('SET_SEW_SEGMENT', 'Segment', not free and not self.mn_sewing), ('SET_SEW_FREE', 'Free', free),
                    ('SET_SEW_MN', 'M:N', self.mn_sewing), ('SET_SEW_AUTO', 'Auto sew', False)]
        if owner == 'SHAPE' and self.shaping is not None:
            return [('GRAB_' + mode, mode.title(), self.shaping.mode == mode) for mode in ('PULL', 'PUSH', 'PIN', 'PINCH', 'STEAM')] + [('GRAB_UNPIN', 'Remove pins', False)]
        if owner == 'PIN':
            return [('SET_PIN_FABRIC', 'Pin', tool == 'PIN'), ('SET_PIN_BOX', 'Box', tool == 'PIN_BOX'), ('SET_PIN_EDGE', 'Edge', tool == 'PIN_EDGE'),
                    ('SET_PIN_BODY', 'Tack to body', tool == 'TACK'), ('SET_PIN_JOIN', 'Tack fabric', tool == 'TACK_FABRIC')]
        return []

    def triangle_budget(self):
        from . import garment
        scene = self._scene
        objects = garment.generated(scene, 'final') + [obj for obj in garment.generated(scene, 'simulation') if not obj.hide_get()]
        return budget.summary(scene, objects) if objects else None

    def triangle_note(self):
        info = self.triangle_budget()
        if info is None:
            return ''
        note = f"{'About ' if info['estimated'] else ''}{info['garment']:,} triangles."
        return note + (f" With avatar: PC {info['pc']}, Quest {info['quest']}." if info['body'] else '')

    def in_flyout(self, point, layout):
        strip = layout.strip_panel
        if strip is None:
            return False
        margin = 12 * layout.scale
        left = layout.rail.x + layout.rail.w
        return Rect(left, strip.y - margin, strip.x + strip.w + margin - left, strip.h + 2 * margin).contains(*point)

    def update_flyout(self, point):
        layout = self.canvas_layout
        button = layout.button(*point)
        if button != self.flyout_dismissed:
            self.flyout_dismissed = None
        if self.card_kind or self.gesture or self.setting_drag:
            return
        if self.in_flyout(point, layout):
            self.cancel_pending_sub()
        elif button in FLYOUT_TOOLS and self.tool_strip(button):
            if button == self.flyout:
                self.cancel_pending_sub()
            elif button != self.flyout_dismissed:
                self.schedule_sub(button, None, None)
        else:
            self.cancel_pending_sub()
            if self.flyout:
                self.flyout = None
                self._area.tag_redraw()

    def open_flyout(self, owner):
        if self.tool_strip(owner):
            self.flyout = owner
            self.canvas_layout = self.make_layout()
            self._area.tag_redraw()

    def place_tool_strip(self, layout):
        if not self.flyout:
            return
        items = self.tool_strip(self.flyout)
        if not items:
            return
        scale = layout.scale
        anchor = layout.buttons[self.flyout][0]
        row = round(22 * scale)
        gap = round(2 * scale)
        pad = round(4 * scale)
        title = layout.buttons[self.flyout][1]
        entries = [(title, STRIP_KEYS.get(self.flyout))] + [(label, STRIP_KEYS.get(key)) for key, label, _ in items]
        width = round(max(text_unscaled_width(label, 10) + (text_unscaled_width(shortcut, 10) + 14 if shortcut else 0) for label, shortcut in entries) * scale + 24 * scale)
        height = (len(items) + 1) * (row + gap) - gap + 2 * pad
        left = layout.rail.x + layout.rail.w + round(4 * scale)
        bottom = max(layout.panel.y + round(60 * scale), anchor.y + anchor.h - height)
        layout.strip_panel = Rect(left, bottom, width + 2 * pad, height)
        y = bottom + height - pad - row
        layout.strip_title = (Rect(left + pad, y, width, row), title, STRIP_KEYS.get(self.flyout))
        y -= row + gap
        for key, label, active in items:
            layout.buttons['STRIP_' + key] = (Rect(left + pad, y, width, row), label)
            if active:
                layout.strip_active.add('STRIP_' + key)
            y -= row + gap

    def status_hint(self):
        if not self.draft and not self.gesture and self.drape_document is not None and self.drape_document != self._scene.dd_document:
            return 'Pattern changed. Re-drape or Space continues from the last drape.'
        if self.draft or self.gesture or self.free_clicks or self.mn_chain or self.mn_first or self.pen_mode or self.armed_selection:
            return self.tool_hint()
        return ''

    def tool_hint(self):
        if self.tool == 'KNIFE':
            return ('Cut & Sew' if self.knife_sew else 'Cut') + ' / Click points / Enter or double-click finishes / Shift locks axis / Esc cancels'
        if self.draft:
            return 'Click to add points / Enter to finish / Esc to cancel'
        if self.tool == 'SEW':
            if self.mn_sewing:
                return ('Click the partner edges / Enter sews' if self.mn_first else 'Click the first side edges / Enter ends the side') + ' / Esc cancels'
            if self._scene.dd_free_sewing:
                return 'Click start and end on the first edge, then on its partner / Esc cancels'
            return 'Pick the matching edge' if self.pending_edge else 'Click two edges to sew'
        if self.tool == 'SELECT':
            tgt = getattr(self.session, 'acquisition_target', 'PIECES').title()
            if self.gesture and self.gesture.get('mode') == 'BOX_SELECT':
                w0 = self.gesture.get('world_start', (0, 0))
                c = self.canvas_layout.canvas
                w1 = self.view.world(self.pointer, c)
                rule = 'Fully inside' if w1[0] >= w0[0] else 'Touching'
                mod = ' (Add)' if self.gesture.get('shift') else (' (Subtract)' if self.gesture.get('alt') else '')
                return f"Box select: {rule}{mod} \u00b7 Target: {tgt}"
            if self.gesture and self.gesture.get('mode') == 'LASSO_SELECT':
                mod = ' (Add)' if self.gesture.get('shift') else (' (Subtract)' if self.gesture.get('alt') else '')
                return f"Lasso select{mod} \u00b7 Target: {tgt}"
            if self.gesture and self.gesture.get('mode') == 'SET_PIVOT':
                label = self.gesture.get('label', 'Cursor')
                return f"Set pivot: {label} \u00b7 Click to place \u00b7 Esc to cancel"
            if self.gesture and self.gesture.get('mode') == 'TRANSFORM':
                kind = self.gesture.get('kind', 'MOVE').title()
                txt = self.gesture.get('numeric_text', '')
                val_info = f": {txt}" if txt else ""
                return f"Transform {kind}{val_info} \u00b7 Enter commits \u00b7 Esc cancels"
            if self.session.has_selection():
                pieces, points = self.session.selection_counts()
                edges = len(self.session.selected_edges)
                paths = len(self.session.selected_paths)
                parts = []
                if pieces: parts.append(f"{pieces} piece{'s' if pieces != 1 else ''}")
                if points: parts.append(f"{points} point{'s' if points != 1 else ''}")
                if edges: parts.append(f"{edges} edge{'s' if edges != 1 else ''}")
                if paths: parts.append(f"{paths} path{'s' if paths != 1 else ''}")
                summary = ', '.join(parts)
                return f"{summary} \u00b7 Drag to move \u00b7 Knob rotates \u00b7 Corners scale \u00b7 Shift snaps \u00b7 Arrows nudge"
            return f"Select: Target {tgt} \u00b7 Drag to box select \u00b7 Right-click for options"
        return {'RECTANGLE': 'Drag to draw a panel / Shift for a square',
                'ELLIPSE': 'Drag to draw an ellipse / Shift for a circle',
                'POLYGON': 'Click to draw / Click the first point or Enter to finish',
                'INTERNAL': 'Click to draw an internal path / Enter to finish',
                'PIN': 'Click a pattern point to pin or unpin',
                'PIN_BOX': 'Drag over fabric to pin an area',
                'PIN_EDGE': 'Click an edge to pin along it',
                'TACK_FABRIC': 'Click two points on the fabric to tie them together',
                'PEN': 'Click in the 3D view / Enter finishes / Esc cancels',
                'DART': 'Pick two base points, then the dart tip',
                'TACK': 'Pick a pattern point, then a point on the body',
                'PLACE': 'Pick a piece, then a point on the body'}.get(self.tool, '')

    def sync_fabric_settings(self, preset_name):
        from .presets import resolve_preset
        vals = resolve_preset(preset_name, getattr(self.session.document, 'custom_presets', None))
        self._scene.dd_fabric_structural = vals['structural']
        self._scene.dd_fabric_bending = vals['bending']
        self._scene.dd_fabric_density = vals['density']
        for prop, name in GRAIN_SETTINGS.items():
            setattr(self._scene, prop, vals[name])

    def apply_local_setting(self, key):
        if key == 'dd_weld_distance':
            self.weld_manual = True
        if key in {'dd_fabric_structural', 'dd_fabric_bending', 'dd_fabric_density'} | set(GRAIN_SETTINGS):
            prop_map = {'dd_fabric_structural': 'structural',
                        'dd_fabric_bending': 'bending', 'dd_fabric_density': 'density', **GRAIN_SETTINGS}
            prop = prop_map[key]
            val = getattr(self._scene, key)
            doc = self.session.document
            pattern = self.session.document.find(self.session.selected)
            if self.card_kind == 'PIECE_FABRIC' and pattern:
                active = pattern.preset if getattr(pattern, 'fabric_override', False) else getattr(doc, 'preset', 'COTTON')
                customs = getattr(doc, 'custom_presets', {})
                if getattr(pattern, 'fabric_override', False) and active in customs:
                    customs[active][prop] = val
                    self.session.commit(lambda: None)
                else:
                    base = f'{pattern.name} Fabric'
                    cand = base
                    existing = set(customs.keys()) | set(FABRICS)
                    idx = 1
                    while cand in existing:
                        idx += 1
                        cand = f'{base} {idx}'
                    from .presets import resolve_preset
                    vals = resolve_preset(active, customs)
                    vals[prop] = val
                    self.run_edit(lambda: (self.session.set_custom_preset(cand, vals), self.session.set_fabric_override(cand)),
                                  f'{pattern.name} fabric override updated.')
            else:
                active = getattr(doc, 'preset', 'COTTON')
                customs = getattr(doc, 'custom_presets', {})
                if active in customs:
                    customs[active][prop] = val
                    self.session.commit(lambda: None)
                else:
                    base = f'{active.title()} Custom'
                    cand = base
                    existing = set(customs.keys()) | set(FABRICS)
                    idx = 1
                    while cand in existing:
                        idx += 1
                        cand = f'{active.title()} Custom {idx}'
                    from .presets import resolve_preset
                    vals = resolve_preset(active, customs)
                    vals[prop] = val
                    self.run_edit(lambda: (self.session.set_custom_preset(cand, vals), self.session.set_document_preset(cand)),
                                  f'Default fabric updated to {cand}.')
                    self._scene.dd_fabric = cand
            return True
        action = {'dd_point_x': 'POINT_APPLY', 'dd_point_y': 'POINT_APPLY', 'dd_segment_length': 'SET_LENGTH'}.get(key)
        if action:
            return self.perform_action(action)

    def minimal_action(self, key):
        scene = self._scene
        if self.confirm_action and key.startswith(('LOAD_','LIBRARY_')):
            self.message='Confirm the pending action or choose Cancel first.'
            return
        if key == 'FOLD_MENU':
            self.card_kind = 'FOLD'
        elif key in SUBMENUS:
            self.card_kind = SUBMENUS[key]
        elif key in {'TRACE_CALIBRATION', 'TRACE_POSITION'}:
            self.show_card(key, self.card_anchor)
        elif key == 'DELETE':
            self.perform_action('DELETE')
            self.card_kind = None
        elif key in {'PEN_AVATAR', 'PEN_GARMENT'}:
            self.choose_tool('PEN')
            self.pen_mode = key.removeprefix('PEN_')
            self.pen_points = []
            if self.full:
                self.reveal_3d()
            self.message = 'Click points in the 3D view. Enter finishes, Esc cancels.'
            self.card_kind = None
        elif key.startswith('PUFF_'):
            pattern = self.session.document.find(self.session.selected)
            outline = pattern.outline()
            center = (sum(point[0] for point in outline) / len(outline), sum(point[1] for point in outline) / len(outline))
            reach = max(math.dist(point, center) for point in outline) * 1.2
            self.run_edit(lambda: self.session.add_steam([dict(pattern=pattern.id, x=center[0], y=center[1], radius=reach, amount=-int(key.removeprefix('PUFF_')) / 100)]), 'Puff added. It shows on the next Simulate.')
            self.card_kind = None
        elif key == 'CLEAR_STEAM':
            self.run_edit(lambda: self.session.clear_steam(self.session.selected), 'Puff and steam cleared.')
            self.card_kind = None
        elif key.startswith('SLASH_SPREAD_'):
            angle = float(key.removeprefix('SLASH_SPREAD_').split()[0])
            self.run_edit(lambda: self.session.slash_spread(angle), 'Pattern spread.')
            self.card_kind = None
        elif key == 'GRAB_UNPIN':
            removed = self.shaping.unpin_all()
            self.message = f'{removed} pinned point(s) freed. The cloth drapes again.' if removed else 'No cloth pins to remove.'
        elif key.startswith('GRAB_'):
            self.shaping.mode = key.removeprefix('GRAB_')
            self.message = {'PIN': 'Drag the cloth and release to pin it there. Ctrl+click frees a pin.', 'PINCH': 'Click or drag along the cloth to gather a fold. Space applies.',
                            'STEAM': 'Drag to shrink, Shift+drag to stretch. Space applies.'}.get(self.shaping.mode, f'Grab mode {self.shaping.mode.title()}')
        elif key == 'SET_SEW_AUTO':
            self.run_edit(self.session.auto_sew, 'Matching edges sewn. Check the seams, Undo removes them.')
            self.card_kind = None
        elif key.startswith('SET_SEW_'):
            self.choose_tool({'SET_SEW_FREE': 'FREE_SEW', 'SET_SEW_MN': 'MN_SEW'}.get(key, 'SEW'))
            self.card_kind = None
        elif key.startswith('EDGE_ELASTIC_'):
            shrink = int(key.removeprefix('EDGE_ELASTIC_').removesuffix('%'))
            self.run_edit(lambda: self.session.set_elastic(self.session.segment, shrink), f'Elastic set to {shrink}%.')
            self.card_kind = None
        elif key == 'MERGE_PIECES':
            self.run_edit(lambda: self.session.merge_pieces(self.session.segment), 'Pieces merged.')
            self.card_kind = None
        elif key == 'PLEAT_SEW':
            from .folding import sew_pleats
            self.run_edit(lambda: sew_pleats(self.session), 'Pleats sewn closed along this edge.')
            self.card_kind = None
        elif key in {'SUPERIMPOSE_OVER', 'SUPERIMPOSE_UNDER'}:
            self.run_edit(lambda: self.session.superimpose(key == 'SUPERIMPOSE_OVER'), 'Placed on the sewn piece. Move it with Blender G if needed.')
            self.card_kind = None
        elif key.startswith('SEAM_EASE_'):
            choice = key.removeprefix('SEAM_EASE_')
            self.run_edit(lambda: self.session.set_seam_ease(self.seam_selected, ('Both', 'First edge', 'Second edge').index(choice)), 'Seam shrink side updated.')
            self.card_kind = None
        elif key.startswith('SEAM_LENGTH_'):
            bpy.ops.devil_designer.seam_length('INVOKE_DEFAULT', side=int(key.removeprefix('SEAM_LENGTH_')))
            self.card_kind = None
        elif key.startswith('INSP_SKIN_'):
            scene.dd_skin_offset = SKIN_OFFSET[key.removeprefix('INSP_SKIN_')]
        elif key.startswith('INSP_FRICTION_'):
            scene.dd_friction = FRICTION[key.removeprefix('INSP_FRICTION_')]
        elif key.startswith('KEEP_FACES_'):
            scene.dd_keep_quads = key == 'KEEP_FACES_Quads'
        elif key.startswith('SEAM_ACTIVE_'):
            active = key == 'SEAM_ACTIVE_On'
            self.run_edit(lambda: self.session.set_seam_active(self.seam_selected, active), 'Seam sewn.' if active else 'Seam left open. It stays in the pattern.')
            self.card_kind = None
        elif key == 'MIRROR_PICK':
            self.choose_tool('SELECT')
            self.armed_selection = 'MIRROR_SEW'
            self.message = 'Click the straight edge to mirror across. Escape cancels.'
            self.card_kind = None
        elif key in {'LAYER_OVER', 'LAYER_UNDER'}:
            self.run_edit(lambda: self.session.layer_clone(key == 'LAYER_OVER'), 'Layer added and sewn around its outline.')
            self.card_kind = None
        elif key.startswith('ROUND_CORNER_'):
            radius = float(key.removeprefix('ROUND_CORNER_').split()[0]) / 100
            self.run_edit(lambda: self.session.round_corner(radius), 'Corner rounded.')
            self.card_kind = None
        elif key.startswith('OFFSET_PATH_'):
            distance = float(key.removeprefix('OFFSET_PATH_').split()[0]) / 100
            self.run_edit(lambda: self.session.offset_path(distance), 'Offset line added.')
            self.card_kind = None
        elif key.startswith('OFFSET_OUTLINE_'):
            distance = float(key.removeprefix('OFFSET_OUTLINE_').split()[0]) / 100
            self.run_edit(lambda: self.session.offset(distance), 'Offset copy added.')
            self.card_kind = None
        elif key in {'SELECT_BOX', 'SELECT_LASSO'}:
            self.choose_tool('SELECT')
            self.armed_selection = key
            self.message = 'Drag on the canvas to select. Escape cancels.'
            self.card_kind = None
        elif key.startswith('FOLD_ADD_'):
            from .folding import author_fold
            style, depth = key.removeprefix('FOLD_ADD_').rsplit('_', 1)
            self.run_edit(lambda: author_fold(self.session, style, int(depth) / 100),
                          'Fold added. Mountain and valley arrows show the direction before Simulate.')
            self.card_kind = None
        elif key.startswith('FOLD_EDIT_'):
            from .folding import edit_fold
            self.run_edit(lambda: edit_fold(self.session, key.removeprefix('FOLD_EDIT_')), 'Fold updated.')
            self.card_kind = None
        elif key == 'PIECE_SIMULATION_MENU':
            self.card_kind = 'PIECE_SIMULATION'
        elif key.startswith('TOGGLE_STATE_'):
            from .piece_states import toggle
            from . import garment
            garment.stop(bpy.context)
            flag = key.removeprefix('TOGGLE_STATE_')
            self.run_edit(lambda: toggle(self.session, flag), 'Piece simulation updated. Click Simulate to apply. Freeze holds both sides of attached seams.')
            self.card_kind = None
        elif key.startswith('WEAR_OVER_'):
            obj=self.card_models[int(key.removeprefix('WEAR_OVER_'))]
            if not obj.is_editable:
                self.error_message=f'Make kept garment "{obj.name}" editable to change Wear over.'
                return
            obj['dd_wear_over']=not obj.get('dd_wear_over',True)
        elif key=='SCROLL_WEAR_OVER':
            self.wear_over_offset=self.wear_over_offset+5 if self.wear_over_offset+5<len(self.card_models) else 0
        elif key in {'CLONE_LINKED','CLONE_BACK','TOGGLE_LINKED'}:
            from .linked_editing import clone_twin,toggle_link
            def apply():
                if key=='TOGGLE_LINKED':return toggle_link(self.session)
                if key=='CLONE_BACK':
                    pattern=self.session.document.find(self.session.selected)
                    if pattern and pattern.arrangement:
                        from .arrangement import resolve_point
                        resolve_point(bpy.context,pattern.arrangement['volume'],'back')
                return clone_twin(self.session,key=='CLONE_BACK')
            self.run_edit(apply,'Linked editing updated. Sewing unchanged.')
            self.card_kind=None
        elif key == 'RESET_LAYOUT':
            from .live_panels import reset_piece
            self.run_edit(lambda:reset_piece(self.session,self.session.selected),'Piece reset to its 2D layout position.')
            self.card_kind=None
        elif key in {'REFRESH_FIT','RESET_POINTS'}:
            result=bpy.ops.devil_designer.arrangement_edit(action='REFRESH' if key=='REFRESH_FIT' else 'REGENERATE')
            self.message=('Refreshing body fit; your points are kept.' if key=='REFRESH_FIT' else 'Resetting arrangement points to their defaults.') if 'FINISHED' in result else 'Could not prepare the body fit.'
            self.card_kind=None
        elif key.startswith('PLACE_'):
            from .live_panels import update_arrangement
            option,_,choice=key.removeprefix('PLACE_').partition('_')
            if option=='SHAPE':changes=dict(flat=choice=='Flat')
            elif option=='DISTANCE':changes=dict(clearance=PLACEMENT_DISTANCE[choice])
            elif option=='OVERLAP':changes=dict(zip(('overwrap','direction'),PLACEMENT_OVERLAP[choice]))
            else:changes={}
            self.run_edit(lambda:update_arrangement(self.session,self.session.selected,**changes),'Placement updated.')
            self.card_kind=None
        elif key.startswith('INSP_GARMENT_FABRIC_'):
            name = key.removeprefix('INSP_GARMENT_FABRIC_')
            self.run_edit(lambda: self.session.set_document_preset(name), f'Default fabric set to {name.title()}.')
            scene.dd_fabric = name
            self.sync_fabric_settings(name)
        elif key == 'GARMENT_FABRIC_MENU':
            self.sync_fabric_settings(getattr(self.session.document, 'preset', 'COTTON'))
            self.show_card('GARMENT_FABRIC', self.card_anchor)
        elif key.startswith('INSP_GARMENT_DENSITY_'):
            choice = key.removeprefix('INSP_GARMENT_DENSITY_')
            scene.dd_spacing = DENSITY[choice]
        elif key.startswith('INSP_QUALITY_'):
            choice = key.removeprefix('INSP_QUALITY_')
            scene.dd_quality = QUALITY[choice]
        elif key.startswith('INSP_OPACITY_'):
            choice = key.removeprefix('INSP_OPACITY_')
            scene.dd_reference_opacity = GUIDE_OPACITY[choice]
        elif key.startswith('STARTER_'):
            self.perform_action(key)
            self.card_kind = None
        elif key == 'DEMO_PANEL':
            self.perform_action('DEMO_PANEL')
            self.card_kind = None
        elif key == 'MENU_LIBRARY':
            self.show_card('LIBRARY', self.card_anchor)
        elif key == 'MENU_GARMENT':
            self.show_card('GARMENT', self.card_anchor)
        elif key == 'PIECE_FABRIC_MENU':
            pattern = self.session.document.find(self.session.selected)
            active = pattern.preset if pattern and getattr(pattern, 'fabric_override', False) else getattr(self.session.document, 'preset', 'COTTON')
            self.sync_fabric_settings(active)
            self.show_card('PIECE_FABRIC', self.card_anchor)
        elif key.startswith('SET_PIECE_FABRIC_'):
            choice = key.removeprefix('SET_PIECE_FABRIC_')
            self.run_edit(lambda: self.session.set_fabric_override(choice),
                          f'Fabric override set to {choice.title() if choice != "AUTO" else "Garment default"}.')
            self.sync_fabric_settings(choice if choice != 'AUTO' else getattr(self.session.document, 'preset', 'COTTON'))
            if self.card_kind != 'PIECE_FABRIC':
                self.card_kind = None
        elif key == 'SAVE_GARMENT_CUSTOM_PRESET':
            doc = self.session.document
            base = getattr(doc, 'preset', 'Custom').split(' ')[0]
            existing = set(getattr(doc, 'custom_presets', {}).keys()) | set(FABRICS)
            idx = 1
            cand = f'{base} {idx}'
            while cand in existing:
                idx += 1
                cand = f'{base} {idx}'
            vals = dict(structural=scene.dd_fabric_structural,
                        bending=scene.dd_fabric_bending, density=scene.dd_fabric_density)
            self.run_edit(lambda: (self.session.set_custom_preset(cand, vals), self.session.set_document_preset(cand)),
                          f'Custom preset "{cand}" saved with garment.')
            scene.dd_fabric = cand
        elif key == 'SAVE_PIECE_CUSTOM_PRESET':
            pattern = self.session.document.find(self.session.selected)
            if pattern:
                doc = self.session.document
                base = f'{pattern.name} Fabric'
                existing = set(getattr(doc, 'custom_presets', {}).keys()) | set(FABRICS)
                idx = 1
                cand = base
                while cand in existing:
                    idx += 1
                    cand = f'{base} {idx}'
                vals = dict(structural=scene.dd_fabric_structural,
                            bending=scene.dd_fabric_bending, density=scene.dd_fabric_density)
                self.run_edit(lambda: (self.session.set_custom_preset(cand, vals), self.session.set_fabric_override(cand)),
                              f'Custom preset "{cand}" saved for {pattern.name}.')
        elif key == 'DELETE_CUSTOM_PRESET':
            doc = self.session.document
            pattern = self.session.document.find(self.session.selected)
            active = pattern.preset if (self.card_kind == 'PIECE_FABRIC' and pattern and getattr(pattern, 'fabric_override', False)) else getattr(doc, 'preset', 'COTTON')
            if active in getattr(doc, 'custom_presets', {}):
                self.run_edit(lambda: self.session.delete_custom_preset(active), f'Preset "{active}" deleted.')
                new_preset = getattr(doc, 'preset', 'COTTON')
                scene.dd_fabric = new_preset
                self.sync_fabric_settings(new_preset)
        elif key == 'PIECE_DENSITY_MENU':
            self.show_card('PIECE_DENSITY', self.card_anchor)
        elif key.startswith('SET_DENSITY_'):
            choice = key.removeprefix('SET_DENSITY_')
            self.run_edit(lambda: self.session.set_mesh_density(choice), 'Piece mesh density updated.')
            self.card_kind = None
        elif key.startswith('SET_DRAW_'):
            tool_name = key.removeprefix('SET_DRAW_')
            self.draw_shape = tool_name
            self.choose_tool(tool_name)
            self.card_kind = None
        elif key.startswith('KNIFE_MODE_'):
            self.knife_sew = key == 'KNIFE_MODE_SEW'
            self.internal_tool = 'KNIFE'
            self.choose_tool('KNIFE')
            self.card_kind = None
        elif key.startswith('SET_INTERNAL_'):
            sub = key.removeprefix('SET_INTERNAL_')
            if sub in {'RECT', 'ELLIPSE'}:
                self.choose_tool('RECTANGLE' if sub == 'RECT' else 'ELLIPSE')
                self._scene.dd_internal_mode = True
                self.message = 'Drag inside a piece to add an internal shape.'
            else:
                tool_name = {'PATH': 'INTERNAL', 'DART': 'DART'}[sub]
                self.internal_tool = tool_name
                self.choose_tool(tool_name)
            self.card_kind = None
        elif key.startswith('SET_PIN_'):
            sub = key.removeprefix('SET_PIN_')
            tool_name = {'FABRIC': 'PIN', 'BOX': 'PIN_BOX', 'EDGE': 'PIN_EDGE', 'JOIN': 'TACK_FABRIC'}.get(sub, 'TACK')
            self.pin_tool = tool_name
            self.choose_tool(tool_name)
            self.card_kind = None
        elif key == 'DELETE_PIECE':
            self.perform_action('DELETE_PIECE')
            self.card_kind = None
        elif key.startswith('THICKNESS_'):
            choice = key.removeprefix('THICKNESS_')
            scene.dd_thickness = THICKNESS[choice]
        elif key == 'WELD_AUTO':
            self.weld_manual = not getattr(self, 'weld_manual', False)
        elif key == 'INSP_FIT':
            self.fit()
        elif key == 'TRACE_LOAD':
            bpy.ops.devil.load_trace_image('INVOKE_DEFAULT')
        elif key == 'TRACE_ADD':
            bpy.ops.devil.load_trace_image('INVOKE_DEFAULT', add=True)
        elif key == 'TRACE_NEXT':
            from .tracing import cycle_reference
            if cycle_reference(scene):
                self.message = 'Next reference image selected for editing.'
        elif key == 'TRACE_REMOVE':
            from .tracing import remove_reference
            remove_reference(scene)
            self.trace_drag = None
            self.message = 'Reference image removed.'
        elif key == 'TRACE_LOCK':
            scene.dd_trace_locked = not scene.dd_trace_locked
            self.trace_drag = None
            self.message = 'Reference image locked.' if scene.dd_trace_locked else 'Reference image unlocked.'
        elif key in {'TRACE_FLIP_X', 'TRACE_FLIP_Y'}:
            name = 'dd_trace_flip_x' if key == 'TRACE_FLIP_X' else 'dd_trace_flip_y'
            setattr(scene, name, not getattr(scene, name))
        elif key == 'TRACE_DRAG':
            if self.draft or self.gesture:
                self.message = 'Finish or cancel drafting before moving the image.'
            else:
                scene.dd_trace_visible = True
                self.trace_drag = 'ARMED'
                self.card_kind = None
                self.message = 'Drag the image on the canvas. Escape or right-click finishes.'
        elif key == 'TRACE_VISIBLE':
            scene.dd_trace_visible = not scene.dd_trace_visible
        elif key.startswith('TRACE_OPACITY_'):
            scene.dd_trace_opacity = IMAGE_OPACITY[key.removeprefix('TRACE_OPACITY_')]
        elif key == 'TRACE_FIT':
            self.fit()
        elif key == 'TRACE_PICK':
            if self.draft or self.gesture:
                self.message = 'Finish or cancel drafting before calibrating the image.'
            else:
                scene.dd_trace_visible = True
                self.trace_points = []
                self.card_kind = None
                self.message = 'Click the first end of the measured length on the image. Escape cancels.'
        elif key in {'CUT', 'CUT_RETRY'}:
            self.design_action(key)
            self.card_kind = None
        elif key == 'CANCEL_CUT':
            self.cut_preview = None
            self.card_kind = None
            self.message = 'Cut cancelled.'
        elif key.startswith('POINT_TYPE_'):
            ptype = key.removeprefix('POINT_TYPE_').upper()
            self.run_edit(lambda: self.session.set_point_type(ptype), f'Point type set to {ptype.title()}.')
            self.card_kind = None
        elif key == 'SPLIT':
            self.perform_action('SPLIT')
            self.card_kind = None
        elif key.startswith('SPLIT_INTO_'):
            choice = key.removeprefix('SPLIT_INTO_')
            edge = self.session.segment
            if edge is None:
                self.message = 'Select a segment to split.'
            else:
                number = int(choice.split()[1 if choice.startswith('Every') else 0])
                parts = max(2, round(self.session.document.edge_length(edge.full()) / (number / 100))) if choice.startswith('Every') else number
                self.run_edit(lambda: self.session.split_segment_into(edge, parts), f'Split into {parts} equal parts.')
                self.session.segment = None
            self.card_kind = None
        elif key == 'MERGE':
            self.perform_action('MERGE')
            self.card_kind = None
        elif key == 'UNFOLD':
            self.perform_action('UNFOLD')
            self.card_kind = None
        elif key == 'MIRROR_SEW':
            self.perform_action('MIRROR_SEW')
            self.card_kind = None
        elif key == 'DUPLICATE':
            self.perform_action('DUPLICATE')
            self.card_kind = None
        elif key == 'TRACE':
            self.perform_action('TRACE')
            self.card_kind = None
        elif key in {'FLIP_H', 'FLIP_V'}:
            self.perform_action(key)
            if not getattr(self, 'pending_transform', None):
                self.card_kind = None
        elif key == 'PATH_ACTIONS':
            pattern = self.session.document.find(self.session.selected)
            if pattern is not None and self.session.corner is not None:
                vertex = pattern.path(self.session.path).vertices[self.session.corner].id
                edge = next((edge for edge in self.session.document.edges(pattern.id, self.session.path)
                             if vertex in (edge.start, edge.end)), None)
                if edge is not None:
                    self.session.segment = edge
                    self.session.corner = None
                    self.session.point_selection = []
                    self.sync_selection()
                    self.show_card('INTERNAL_EDGE', self.card_anchor)
        elif key.startswith('ALIGN_') or key in {'DISTRIBUTE_X', 'DISTRIBUTE_Y'}:
            mode = key.removeprefix('ALIGN_').upper()
            self.run_edit(lambda: self.session.align_pieces(mode), 'Pieces distributed.' if key.startswith('DISTRIBUTE') else 'Pieces aligned.')
            self.card_kind = None
        elif key.startswith('SET_SELECT_TARGET_'):
            choice = key.removeprefix('SET_SELECT_TARGET_')
            tgt = 'PATHS' if choice == 'Internal paths' else choice.upper()
            self.session.acquisition_target = tgt
            self.message = f'Selection target: {choice}.'
            self.card_kind = None
        elif key in {'SELECT_CONNECTED_PATH', 'SELECT_CONNECTED_SEWN',
                     'SELECT_INVERT', 'SELECT_ALL', 'SELECT_CLEAR',
                     'TRANSFORM_MOVE', 'TRANSFORM_ROTATE', 'TRANSFORM_SCALE',
                     'TRANSFORM_SET_PIVOT', 'TRANSFORM_RESET_PIVOT', 'BEND_EDGE',
                     'APPLY_MISMATCH', 'CANCEL_TRANSFORM', 'INCLUDE_SEWN', 'CONVERT_AUTO'}:
            self.design_action(key)
            if not getattr(self, 'pending_transform', None):
                self.card_kind = None
        elif key.startswith('SEAM_SHRINK_'):
            shrink = int(key.removeprefix('SEAM_SHRINK_').removesuffix('%'))
            self.run_edit(lambda: self.session.set_seam_shrink(self.seam_selected, shrink), f'Seam Shrink set to {shrink}%.')
            self.card_kind = None
        elif key == 'FLIP_SEAM':
            if self.seam_selected:
                self.run_edit(lambda: self.session.reverse_seam(self.seam_selected), 'Seam direction reversed.')
            self.card_kind = None
        elif key == 'REMOVE_SEAM':
            if self.seam_selected:
                self.perform_action('DELETE')
            self.card_kind = None
        elif key == 'REMOVE_ANCHOR':
            if self.selected_anchor:
                self.perform_action('DELETE')
            self.card_kind = None
        elif key.startswith('LOAD_'):
            idx = int(key.removeprefix('LOAD_'))
            if 0 <= idx < len(self.library_items):
                self.library_preview_path=self.library_items[idx]
                self.show_card('LIBRARY_PREVIEW',self.card_anchor)
        elif key=='LIBRARY_ACCEPT_LOAD':
            self.refresh_library()
            if self.library_preview_path in self.library_items:
                self.library_load_path=self.library_preview_path
                self.library_load_signature=self.library_previews[self.library_load_path]['signature']
                scene.dd_library_selected=self.library_items.index(self.library_load_path)
                self.perform_action('LIBRARY_LOAD')
                self.card_kind=None
            else:self.message='This garment is no longer available.'
        elif key in {'LIBRARY_SEARCH','LIBRARY_NAME','LIBRARY_TAG_EDIT'}:
            field={'LIBRARY_SEARCH':'library_query','LIBRARY_NAME':'dd_library_name','LIBRARY_TAG_EDIT':'library_tags'}[key]
            text=getattr(scene,field) if field=='dd_library_name' else getattr(self,field)
            self.library_edit=dict(key=field,text=text,original=text,cursor=len(text),selected=True)
        elif key=='LIBRARY_TAGS':
            self.show_card('LIBRARY_TAGS',self.card_anchor)
        elif key.startswith('LIBRARY_TAG_'):
            tags=sorted({tag for metadata in self.library_previews.values() for tag in metadata['tags']},key=str.casefold)
            self.library_filter='' if key=='LIBRARY_TAG_ALL' else tags[int(key.removeprefix('LIBRARY_TAG_'))]
            self.show_card('LIBRARY',self.card_anchor)
        elif key=='PAGE_LIBRARY_TAGS':
            count=len({tag for metadata in self.library_previews.values() for tag in metadata['tags']})
            self.card_page=(self.card_page+1)%max(1,math.ceil(count/6))
        elif key == 'PAGE_LIBRARY':
            self.card_page = (self.card_page + 1) % max(1,math.ceil(len(self.library_matches()) / self.library_page_size()))
        elif key == 'LIBRARY_SAVE':
            self.show_card('LIBRARY_SAVE',self.card_anchor)
        elif key=='LIBRARY_WRITE':
            if self.perform_action('LIBRARY_SAVE'):
                self.library_query='';self.library_filter=''
                self.show_card('LIBRARY',self.card_anchor)
            elif self.confirm_action:self.card_kind=None
        elif key == 'RESET':
            self.workflow_action('RESET')
            self.card_kind = None
        elif key == 'NAME':
            self.numeric = dict(key='dd_library_name', text=scene.dd_library_name,cursor=len(scene.dd_library_name),selected=True)
        elif key == 'REFERENCE_IMAGE':
            self.show_card('REFERENCE_IMAGE', self.card_anchor)
        elif key == 'KEEP_RETRY':
            self.perform_action('KEEP')
            self.card_kind = None
        elif key in {'FINISH_DRAFT', 'CANCEL_DRAFT'}:
            self.perform_action(key)

    def minimal_event(self, context, event):
        if self.library_edit:
            result=self.library_text_event(event)
            if result is not None:return result
        point = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        layout = self.canvas_layout
        if self.numeric:
            result = self.numeric_event(event)
            if result is not None:
                return result
        if self.setting_drag:
            return self.setting_drag_event(event)
        card = next((c for c in self.visible_cards() if c[0].contains(*point)), None)
        press = event.value == 'PRESS'
        if event.type == 'MOUSEMOVE':
            self.update_submenu(point)
        if card and press and event.type == 'LEFTMOUSE' and self.sub_card and card[0] != self.visible_cards()[0][0]:
            self.card_kind = self.sub_card
            self.card_anchor = self.sub_anchor
            self.close_sub()
            card = self.visible_cards()[0]
        if self.gesture or (press and event.type == 'ESC' and (self.draft or self.free_clicks)):
            return None
        if press and event.type in {'ESC', 'RIGHTMOUSE'} and self.pending_edge:
            self.pending_edge = None
            self.message = 'Seam selection cancelled.'
            return {'RUNNING_MODAL'}
        if press and event.ctrl and event.type == 'S':
            return {'PASS_THROUGH'}
        if press and event.ctrl and event.type in {'Z', 'Y'}:
            redo = event.type == 'Y' or event.shift
            self.perform_action('REDO' if redo else 'UNDO')
            return {'RUNNING_MODAL'}
        if press and event.type == 'ESC' and self.flyout:
            self.flyout_dismissed = self.flyout
            self.flyout = None
            return {'RUNNING_MODAL'}
        if press and event.type == 'ESC' and self.card_kind:
            if self.card_kind == 'SEAM_WARNING' or getattr(self, 'pending_transform', None):
                self.cancel_transform()
            else:
                self.card_kind = None
            return {'RUNNING_MODAL'}
        pointer_event = event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'MOUSEMOVE',
                                       'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
        if not pointer_event or not (card or layout.panel.contains(*point)):
            return None
        if card and self.card_kind=='SIMULATE' and event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
            delta=-1 if event.type=='WHEELUPMOUSE' else 1
            self.wear_over_offset=max(0,min(max(0,len(self.card_models)-5),self.wear_over_offset+delta))
            return {'RUNNING_MODAL'}
        if card and self.card_kind == 'LIBRARY' and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            delta = -1 if event.type == 'WHEELUPMOUSE' else 1
            max_pages = math.ceil(len(self.library_matches()) / self.library_page_size())
            if max_pages > 1:
                self.card_page = max(0, min(max_pages - 1, self.card_page + delta))
            return {'RUNNING_MODAL'}
        if self.card_kind and press and event.type == 'RIGHTMOUSE':
            self.card_kind = None
            return {'RUNNING_MODAL'}
        button = layout.button(*point)
        scale = layout.scale
        if self.flyout and press and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and not (button or '').startswith('STRIP_'):
            self.flyout = None
        if button and not card and press and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:
            if self.card_kind:
                self.card_kind = None
                self.pending_simulation = False
            btn_rect = layout.buttons[button][0]
            if button == 'SELECT':
                self.choose_tool('SELECT')
            elif button == 'SHOW_3D':
                self.reveal_3d()
                return {'RUNNING_MODAL'}
            elif button == 'TOGGLE_SNAP':
                self.snap = not self.snap
            elif button == 'TOGGLE_GUIDE':
                self._scene.dd_reference_visible = not self._scene.dd_reference_visible
            elif button == 'TOGGLE_LENGTHS':
                self._scene.dd_lengths_visible = not self._scene.dd_lengths_visible
            elif button == 'TOGGLE_FIT_MAP':
                self.fit_overlay.toggle()
            elif button in {'UNDO', 'REDO'}:
                self.perform_action(button)
            elif button == 'SEW':
                self.choose_tool(self.sew_tool)
            elif button == 'SHAPE':
                try:
                    self.enable_shaping(context)
                except ValueError as failure:
                    self.message = str(failure)
            elif button == 'LIBRARY':
                self.show_card('LIBRARY', (btn_rect.x + btn_rect.w + 10 * scale, btn_rect.y + btn_rect.h / 2))
            elif button == 'CLOSE':
                if self.draft or self.gesture:
                    self.cancel_gesture()
                from . import garment
                if garment.generated(self._scene, 'simulation'):
                    garment.stop(context)
                self.cleanup()
                return {'FINISHED'}
            elif button == 'RESTORE_CANVAS':
                self.restore_canvas()
                return {'RUNNING_MODAL'}
            elif button == 'DRAW':
                self.choose_tool(self.draw_shape)
            elif button == 'INTERNAL':
                self.choose_tool(self.internal_tool)
            elif button == 'PIN':
                self.choose_tool(self.pin_tool)
            elif button == 'GARMENT':
                self.show_card('GARMENT', (btn_rect.x, btn_rect.y - 10 * scale))
            elif button in {'SIMULATE', 'KEEP'}:
                self.automatic_defaults(finalize=button == 'KEEP')
                self.perform_action(button)
            elif button == 'KEEP_OPTIONS':
                self.show_card('KEEP', (btn_rect.x, btn_rect.y + 45 * scale))
            elif button == 'SIMULATE_OPTIONS':
                self.show_card('SIMULATE', (btn_rect.x, btn_rect.y + 45 * scale))
            elif button.startswith('STRIP_'):
                self.flyout = None
                self.minimal_action(button.removeprefix('STRIP_'))
            else:
                self.minimal_action(button)
            if button in FLYOUT_TOOLS:
                self.flyout_dismissed = button
            return {'FINISHED'} if self._closed else {'RUNNING_MODAL'}
        if card:
            if press and event.type == 'LEFTMOUSE':
                if self.card_close_rect(card[0]).contains(*point):
                    self.card_kind = None
                    self.pending_simulation = False
                    return {'RUNNING_MODAL'}
                for mode_key, mode_rect in self.card_mode_rects(card[0]).items():
                    if mode_rect.contains(*point):
                        self.card_kind = mode_key
                        self.card_page = 0
                        return {'RUNNING_MODAL'}
                for rect, row in card[2]:
                    if not rect.contains(*point):
                        continue
                    key = row[0]
                    if key in {'CHOICES', 'CHOICES_FABRIC'}:
                        prefix, choices, active = row[2]
                        choices_list = list(choices)
                        if len(choices_list) <= 4:
                            index = min(len(choices_list) - 1, int((point[0] - rect.x) / (rect.w / len(choices_list))))
                        else:
                            cols = 3
                            c_idx = min(cols - 1, max(0, int((point[0] - rect.x) / (rect.w / cols))))
                            num_rows = math.ceil(len(choices_list) / cols)
                            row_h = 23 * scale
                            r_idx = min(num_rows - 1, max(0, int((rect.y + rect.h - 14 * scale - point[1]) / row_h))) if num_rows > 2 else (0 if point[1] > rect.y + rect.h / 2 else 1)
                            index = min(len(choices_list) - 1, r_idx * cols + c_idx)
                        self.minimal_action(prefix + '_' + choices_list[index])
                        if self.card_kind not in {'GARMENT', 'BODY', 'GARMENT_FABRIC', 'PIECE_FABRIC'}:
                            self.card_kind = None
                    elif key == 'PAIR_ACTIONS':
                        action1, action2 = row[1], row[2]
                        chosen = action1 if point[0] < rect.x + rect.w / 2 else action2
                        self.minimal_action(chosen)
                        if chosen not in {'REFERENCE_IMAGE', 'MENU_LIBRARY', 'LIBRARY_SAVE', *SUBMENUS} and not getattr(self, 'pending_transform', None):
                            self.card_kind = None
                    elif key == 'SLIDER':
                        label = row[1]
                        self.setting_drag = dict(key=label, value=getattr(self._scene, label), pointer=point, moved=False)
                        if label == 'dd_weld_distance':
                            scale = layout.scale
                            self.setting_drag['absolute'] = Rect(rect.x + 6 * scale, rect.y, rect.w - 12 * scale, rect.h)
                    elif key == 'MENU' and row[1] in HOVER_MENUS:
                        self.open_sub(row[1], rect, card[0])
                    elif key == 'INFO':
                        context.window_manager.clipboard = f'{row[1]}: {row[2]}' if row[2] else str(row[1])
                        self.message = 'Row text copied.'
                    elif key != 'AVATAR_FIELD':
                        action = row[1] if key == 'MENU' else key
                        self.minimal_action(action)
                        if not action.startswith(('LOAD_','LIBRARY_','PAGE_LIBRARY')) and action not in {'GARMENT_FABRIC_MENU', 'PIECE_FABRIC_MENU', 'PIECE_DENSITY_MENU', 'PIECE_SIMULATION_MENU', 'SCROLL_WEAR_OVER', 'NAME', 'REFERENCE_IMAGE', 'MENU_LIBRARY', 'MENU_GARMENT', 'TRACE_CALIBRATION', 'TRACE_POSITION', 'PATH_ACTIONS', *SUBMENUS} and not getattr(self, 'pending_transform', None):
                            self.card_kind = None
                    break
            return {'RUNNING_MODAL'}
        if self.gesture:
            return None
        if press and event.type == 'LEFTMOUSE' and self.error_rect is not None and self.error_message and self.error_rect.contains(*point):
            context.window_manager.clipboard = self.error_message
            self.message = 'Message copied.'
            self.error_message = None
            return {'RUNNING_MODAL'}
        if (press and event.type == 'LEFTMOUSE' and self.message_rect is not None and self.message
                and time.monotonic() < getattr(self, 'toast_until', 0) and self.message_rect.contains(*point)):
            context.window_manager.clipboard = self.message
            self.message = 'Message copied.'
            return {'RUNNING_MODAL'}
        if press and event.type == 'LEFTMOUSE' and self.seam_end_hit():
            return None
        if press and event.type == 'LEFTMOUSE':
            self.card_kind = None
            for rect, identity, label in self.seam_badges():
                if rect.contains(*point):
                    self.selected_anchor = None
                    self.session.selected = None
                    self.session.corner = None
                    self.session.segment = None
                    self.session.point_selection = []
                    self.seam_selected = identity
                    return {'RUNNING_MODAL'}
            self.seam_selected = None
        if press and event.type == 'RIGHTMOUSE' and layout.canvas.contains(*point) and not self.draft:
            scale = layout.scale
            anchor = next((a for a in self.session.document.anchors
                           if math.dist(self.view.screen((a.x, a.y), layout.canvas), point) <= 10 * scale), None)
            if anchor:
                self.select_anchor(anchor)
                self.show_card('ANCHOR', point)
                return {'RUNNING_MODAL'}
            pattern, corner = self.hit()
            if corner is None:
                for rect, identity, label in self.seam_badges():
                    if rect.contains(*point):
                        self.selected_anchor = None
                        self.session.selected = None
                        self.session.corner = None
                        self.session.segment = None
                        self.session.point_selection = []
                        self.seam_selected = identity
                        self.show_card('SEAM', point)
                        return {'RUNNING_MODAL'}
            self.seam_selected = None
            self.selected_anchor = None
            if self.pending_edge:
                self.pending_edge = None
                self.message = 'Seam selection cancelled.'
                return {'RUNNING_MODAL'}
            if pattern is None:
                self.session.clear_selection()
                self.sync_selection()
                self.show_card('CANVAS_MENU', point)
                return {'RUNNING_MODAL'}
            if self.session.is_multi_selected():
                hit_in_sel = False
                if corner is not None:
                    if (pattern.id, self.hit_path, corner) in self.session.selected_points:
                        hit_in_sel = True
                else:
                    if pattern.id in self.session.selected_patterns:
                        hit_in_sel = True
                if hit_in_sel:
                    self.show_card('MULTI_SELECTION', point)
                    return {'RUNNING_MODAL'}
            if (self.session.selected != pattern.id or self.session.path != self.hit_path
                    or corner not in self.session.point_selection):
                self.session.point_selection = [corner] if corner is not None else []
            self.session.selected = pattern.id
            self.session.corner = corner
            self.session.path = self.hit_path
            self.session.segment = self.hit_edge() if corner is None else None
            self.sync_selection()
            if corner is not None:
                self.show_card('POINT', point)
            elif self.session.segment:
                if self.session.path != 'OUTER':
                    self.show_card('INTERNAL_EDGE', point)
                else:
                    self.show_card('EDGE', point)
            else:
                self.show_card('PIECE', point)
            return {'RUNNING_MODAL'}
        return None
