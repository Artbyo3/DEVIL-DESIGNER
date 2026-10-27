import math
import bpy
from .canvas import Rect


DENSITY = {'Coarse': .04, 'Standard': .02, 'Fine': .01}
QUALITY = {'Draft': 6, 'Standard': 12, 'High': 24}
THICKNESS = {'None': 0, 'Thin': .0005, 'Standard': .001}
FABRICS = ('COTTON', 'LINEN', 'DENIM', 'SILK', 'LEATHER', 'KNIT')
GUIDE_OPACITY = {'Light': .15, 'Medium': .30, 'Strong': .50}
IMAGE_OPACITY = {'Light': .2, 'Medium': .35, 'Strong': .6}


def minimal_layout(layout, pending=False, confirmation=False, playing=False):
    scale = layout.scale
    panel = layout.panel
    layout.minimal = True
    layout.inspector = None
    layout.canvas = Rect(panel.x + 4 * scale, panel.y + 4 * scale,
                         panel.w - 8 * scale, panel.h - 8 * scale)
    layout.header = Rect(panel.x, panel.y + panel.h - 32 * scale, panel.w, 32 * scale)
    layout.footer = Rect(panel.x, panel.y, panel.w, 0)
    dock_height = min(594 * scale, panel.h - 112 * scale)
    dock_width = (60 if dock_height >= 500 * scale else 48) * scale
    layout.rail = Rect(panel.x + 14 * scale, panel.y + (panel.h - dock_height) / 2, dock_width, dock_height)
    layout.buttons = {}
    tools = [('SELECT', 'Select'), ('POLYGON', 'Polygon'), ('RECTANGLE', 'Panel'),
             ('ELLIPSE', 'Ellipse'), ('INTERNAL', 'Internal'), ('SEW', 'Sew'),
             ('PIN', 'Pin'), ('DART', 'Dart'), ('UNDO', 'Undo'), ('REDO', 'Redo'), ('LIBRARY', 'Library')]
    indicator_h = 22 * scale
    tools_h = dock_height - indicator_h - 10 * scale
    row_height = tools_h / len(tools)
    for index, (key, label) in enumerate(tools):
        layout.buttons[key] = (Rect(layout.rail.x + 4 * scale,
            layout.rail.y + dock_height - (index + 1) * row_height + 2 * scale,
            dock_width - 8 * scale, row_height - 4 * scale), label)
    chip_w = (dock_width - 12 * scale) / 3
    chip_y = layout.rail.y + 4 * scale
    layout.buttons['TOGGLE_SNAP'] = (Rect(layout.rail.x + 4 * scale, chip_y, chip_w, indicator_h), 'Snap')
    layout.buttons['TOGGLE_GUIDE'] = (Rect(layout.rail.x + 4 * scale + chip_w + 2 * scale, chip_y, chip_w, indicator_h), 'Guide')
    layout.buttons['TOGGLE_LENGTHS'] = (Rect(layout.rail.x + 4 * scale + (chip_w + 2 * scale) * 2, chip_y, chip_w, indicator_h), 'Lengths')
    right = panel.x + panel.w - 14 * scale
    layout.buttons['CLOSE'] = (Rect(right - 24 * scale, panel.y + panel.h - 30 * scale, 24 * scale, 24 * scale), 'Close')
    right -= 28 * scale
    layout.buttons['WORKSPACE_PANEL'] = (Rect(right - 88 * scale, panel.y + panel.h - 30 * scale, 82 * scale, 24 * scale), 'Workspace')
    if not layout.full:
        right -= 88 * scale
        layout.buttons['RESTORE_CANVAS'] = (Rect(right - 88 * scale, panel.y + panel.h - 30 * scale, 82 * scale, 24 * scale), 'Full canvas')
    layout.buttons['GARMENT'] = (Rect(panel.x + 14 * scale, panel.y + panel.h - 36 * scale, min(220 * scale, panel.w * .40), 30 * scale), 'Garment')
    bottom = panel.y + 14 * scale
    right = panel.x + panel.w - 14 * scale
    specs = [('SIMULATE', 'Pause' if playing else 'Simulate'), ('KEEP', 'Keep mesh')]
    if pending:
        specs = [('FINISH_DRAFT', 'Finish'), ('CANCEL_DRAFT', 'Cancel')]
    if confirmation:
        specs = [('CONFIRM_ACTION', 'Confirm'), ('CANCEL_ACTION', 'Go back')]
    for key, label in specs:
        width = 142 * scale
        right -= width
        layout.buttons[key] = (Rect(right, bottom, width, 40 * scale), label)
        if key in {'SIMULATE', 'KEEP'}:
            layout.buttons[key + '_OPTIONS'] = (Rect(right + 112 * scale, bottom, 30 * scale, 40 * scale), 'Options')
            layout.buttons[key] = (Rect(right, bottom, 112 * scale, 40 * scale), label)
        right -= 8 * scale


class MinimalCards:
    def initialize_minimal(self):
        self.minimal_ui = True
        self.workspace_panel_open = True
        self.workspace_panel_pinned = True
        self.card_kind = None
        self.context_card_hidden = False
        self.card_anchor = None
        self.card_page = 0
        self.weld_manual = False
        self.card_models = []
        self.toast_text = ''
        self.toast_until = 0
        self._scene.dd_reference_visible = False

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

    def seam_badges(self):
        badges = []
        for index, seam in enumerate(self.session.document.seams):
            middles = []
            for side in (0, 1):
                edge, fraction = self.session.document.chain_position(seam.side(side), .5)
                middles.append(self.view.screen(self.session.document.edge_point(edge, fraction), self.canvas_layout.canvas))
            center = ((middles[0][0] + middles[1][0]) / 2, (middles[0][1] + middles[1][1]) / 2)
            scale = self.canvas_layout.scale
            while any(abs(center[0] - (rect.x + rect.w / 2)) < 22 * scale and
                      abs(center[1] - (rect.y + rect.h / 2)) < 22 * scale for rect, identity, label in badges):
                center = (center[0], center[1] + 24 * scale)
            badges.append((Rect(center[0] - 10 * scale, center[1] - 10 * scale, 20 * scale, 20 * scale), seam.id, str(index + 1)))
        return badges

    def show_card(self, kind, anchor=None):
        self.card_kind = kind
        self.card_anchor = anchor or self.pointer
        self.card_page = 0
        self.search_active = False
        self.context_anchor = None
        self.settings_open = False
        if kind == 'LIBRARY':
            self.refresh_library()

    def minimal_card(self, kind_override=None):
        if self.confirm_action or ((self.draft or self.gesture) and kind_override != 'WORKSPACE'):
            return None
        pattern = self.session.document.find(self.session.selected)
        kind = kind_override or self.card_kind
        anchor = next((anchor for anchor in self.session.document.anchors if anchor.id == self.selected_anchor), None)
        if kind is None and anchor and self.tool in {'PIN', 'TACK'}:
            kind = 'ANCHOR'
        if kind is None and pattern:
            kind = 'PIECE'
        if kind is None:
            kind = 'GARMENT'
        scene = self._scene
        rows = []
        title = kind.title()
        if kind == 'PIECE':
            if pattern is None:
                return None
            title = pattern.name
            rows = [('FABRIC', 'Fabric', pattern.preset.title()),
                    ('PIECE_DENSITY', 'Mesh density', pattern.mesh_density.title()),
                    ('INFO', f'{len(pattern.points)} edges', f'{sum(edge.pattern == pattern.id for seam in self.session.document.seams for side in (0, 1) for edge in seam.side(side))} sewn'),
                    ('EDIT_CARD', 'Edit piece', 'Right-click')]
        elif kind == 'WORKSPACE':
            title = 'Workspace'
            rows = [('WORKSPACE_SNAP', 'Snapping', 'On' if self.snap else 'Off'),
                    ('WORKSPACE_LENGTHS', 'Measurements', 'Shown' if scene.dd_lengths_visible else 'Hidden'),
                    ('WORKSPACE_GUIDE', 'Body guide', 'Shown' if scene.dd_reference_visible else 'Hidden')]
            if scene.dd_reference_visible:
                rows.append(('CHOICES', 'Guide opacity', ('WORKSPACE_OPACITY', GUIDE_OPACITY,
                            self.named_choice(scene.dd_reference_opacity, GUIDE_OPACITY))))
            rows.append(('WORKSPACE_FIT', 'Fit design', ''))
        elif kind == 'PIECE_DENSITY':
            if pattern is None:
                return None
            title = 'Piece mesh density'
            rows = [('SET_DENSITY_' + name, label, 'Selected' if pattern.mesh_density == name else '')
                    for name, label in [('AUTO', 'Garment default'), ('COARSE', 'Coarse'), ('STANDARD', 'Standard'), ('FINE', 'Fine')]]
        elif kind == 'ARRANGEMENT':
            title = 'Arrange pieces'
            rows = [('ARRANGE_BODICE', 'Bodice panels', 'Front / back'),
                    ('ARRANGE_SLEEVES', 'Sleeves', 'Left / right'),
                    ('ARRANGE_SKIRT', 'Skirt panels', 'Around hips')]
        elif kind == 'REFERENCE_IMAGE':
            title = 'Reference image'
            rows = [('TRACE_LOAD', 'Load image', 'Choose file')]
            if scene.dd_trace_path:
                rows += [('TRACE_CALIBRATION', 'Set measured scale', ''),
                         ('TRACE_POSITION', 'Image placement', ''),
                         ('TRACE_VISIBLE', 'Visibility', 'Shown' if scene.dd_trace_visible else 'Hidden'),
                         ('CHOICES', 'Image opacity', ('TRACE_OPACITY', IMAGE_OPACITY, self.named_choice(scene.dd_trace_opacity, IMAGE_OPACITY)))]
            if scene.dd_trace_error:
                rows.append(('INFO', 'Image unavailable', scene.dd_trace_error))
        elif kind == 'TRACE_CALIBRATION':
            title = 'Measured scale'
            rows = [('SLIDER', 'dd_trace_length', 'Known length'),
                    ('TRACE_PICK', 'Pick length endpoints', 'Two clicks on image'),
                    ('INFO', 'Scale only', 'Cannot correct photo distortion')]
        elif kind == 'TRACE_POSITION':
            title = 'Image placement'
            rows = [('SLIDER', 'dd_trace_width', 'Width'), ('SLIDER', 'dd_trace_x', 'X position'),
                    ('SLIDER', 'dd_trace_y', 'Y position'), ('TRACE_FIT', 'Fit image and pieces', '')]
        elif kind == 'FABRIC':
            if pattern is None:
                return None
            title = 'Fabric'
            rows = [('SET_PRESET_' + name, name.title(), 'Selected' if pattern.preset == name else '') for name in FABRICS]
        elif kind == 'SIMULATE':
            title = 'Simulation'
            rows = [('CHOICES', 'Mesh density', ('DENSITY', DENSITY, self.named_choice(scene.dd_spacing, DENSITY))),
                    ('CHOICES', 'Simulation quality', ('QUALITY', QUALITY, self.named_choice(scene.dd_quality, QUALITY)))]
        elif kind == 'KEEP':
            title = 'Keep mesh'
            rows = [('WELD_AUTO', 'Weld', 'Manual' if self.weld_manual else 'Auto'),
                    ('CHOICES', 'Thickness', ('THICKNESS', THICKNESS, self.named_choice(scene.dd_thickness, THICKNESS)))]
            if scene.get('dd_unwelded_seams', 0) > 0:
                rows += [('SLIDER', 'dd_weld_distance', 'Weld tolerance'), ('KEEP_RETRY', 'Retry keep', f"{scene['dd_unwelded_seams']} unwelded pairs")]
        elif kind == 'SEAM':
            title = 'Selected seam'
            if not any(seam.id == self.seam_selected for seam in self.session.document.seams):
                return None
            rows = [('FLIP_SEAM', 'Reverse direction', ''), ('REMOVE_SEAM', 'Remove seam', '')]
        elif kind == 'GARMENT' and not self.session.document.patterns:
            title = 'Start garment'
            rows = [('START_PANEL', 'Create panel', '40 x 45 cm'),
                    ('RECTANGLE', 'Draw custom panel', 'Drag on canvas'),
                    ('LIBRARY', 'Saved garments', 'Open library'),
                    ('REFERENCE_IMAGE', 'Reference image', 'Trace a photo')]
        elif kind == 'GARMENT':
            title = 'Garment'
            rows = [('NAME', scene.dd_library_name, 'Rename'),
                    ('BODY_CARD', 'Body: ' + scene.dd_avatar.name if scene.dd_avatar else 'Body', 'Change' if scene.dd_avatar else 'Choose'),
                    ('INFO', 'Pieces', str(len(self.session.document.patterns))),
                    ('LIBRARY_SAVE', 'Save garment', '')]
            rows.append(('REFERENCE_IMAGE', 'Reference image', 'Trace a photo'))
            if any(obj.get('dd_kind') == 'simulation' for obj in scene.objects):
                rows.append(('RESET', 'Reset drape', ''))
        elif kind == 'BODY':
            title = 'Choose body'
            self.card_models = sorted((obj for obj in scene.objects if obj.type == 'MESH' and not obj.get('dd_kind')), key=lambda obj: obj.name.casefold())
            rows = [('BODY_' + str(index), obj.name, '') for index, obj in enumerate(self.card_models) if self.card_page * 8 <= index < (self.card_page + 1) * 8]
            if len(self.card_models) > 8:
                pages = math.ceil(len(self.card_models) / 8)
                rows.append(('PAGE_BODY', f'More bodies ({self.card_page + 1}/{pages})', 'Next'))
            if not rows:
                rows = [('INFO', 'No body in scene', 'Add in Blender')]
        elif kind == 'LIBRARY':
            title = 'Garment library'
            rows = [('LOAD_' + str(index), item.stem.replace('.garment', ''), 'Load') for index, item in enumerate(self.library_items) if self.card_page * 8 <= index < (self.card_page + 1) * 8]
            if len(self.library_items) > 8:
                pages = math.ceil(len(self.library_items) / 8)
                rows.append(('PAGE_LIBRARY', f'More garments ({self.card_page + 1}/{pages})', 'Next'))
            rows.append(('LIBRARY_SAVE', 'Save current garment', ''))
        elif kind == 'EDGE':
            title = 'Edge'
            rows = [('SLIDER', 'dd_segment_length', 'Exact length'), ('SPLIT', 'Split edge', ''),
                    ('UNFOLD', 'Unfold', ''), ('MIRROR_SEW', 'Mirror and sew', '')]
        elif kind == 'INTERNAL_EDGE':
            title = 'Internal edge'
            rows = [('SLIDER', 'dd_segment_length', 'Exact length'), ('SPLIT', 'Split edge', ''),
                    ('CUT', 'Cut along path', '')]
            if pattern and pattern.path(self.session.path).closed:
                rows.append(('TRACE', 'Trace as piece', ''))
        elif kind == 'CUT_RECOVERY':
            title = 'Crossing cut'
            preview = self.cut_preview
            if not preview:
                return None
            rows = [('INFO', 'Cut needs attention', preview['reason'])]
            if preview['can_retry']:
                rows.append(('CUT_RETRY', 'Split and retry', f"{preview['split_count']} splits"))
            rows.append(('CANCEL_CUT', 'Back to editing', ''))
        elif kind == 'ANCHOR':
            if anchor is None:
                return None
            title = 'Body tack' if anchor.kind == 'TACK' else 'Pin'
            rows = [('INFO', 'Attached to', pattern.name if pattern else 'Pattern'),
                    ('REMOVE_ANCHOR', 'Remove tack' if anchor.kind == 'TACK' else 'Remove pin', 'Delete')]
        elif kind == 'POINT':
            title = 'Point'
            rows = [('CURVE', 'Corner / curve', ''), ('SLIDER', 'dd_point_x', 'X position'),
                    ('SLIDER', 'dd_point_y', 'Y position'), ('MERGE', 'Merge selected points', '')]
        elif kind == 'EDIT':
            title = pattern.name if pattern else 'Draw'
            rows = ([('DUPLICATE', 'Duplicate', ''), ('MIRROR_SEW', 'Mirror and sew', ''),
                     ('PLACEMENT', 'Placement', ''), ('INTERNAL_EDIT', 'Internal shapes', ''), ('DELETE_PIECE', 'Delete piece', '')]
                    if pattern else [('RECTANGLE', 'Panel', ''), ('POLYGON', 'Polygon', ''), ('ELLIPSE', 'Ellipse', ''), ('INTERNAL', 'Internal path', ''), ('GARMENT', 'Garment', '')])
        elif kind == 'PLACEMENT':
            title = 'Placement'
            rows = [('PLACE', 'Place on body', ''), ('TACK', 'Tack to body', ''), ('PIN', 'Pin', ''), ('REMOVE_ANCHOR', 'Remove selected anchor', ''), ('ARRANGE', 'Arrange pieces', '')]
        elif kind == 'INTERNAL_EDIT':
            title = 'Internal shapes'
            rows = [('INTERNAL', 'Draw internal path', ''), ('DART', 'Dart', ''), ('CUT', 'Cut path', ''), ('TRACE', 'Trace as piece', ''), ('OFFSET_CARD', 'Offset outline', '')]
        elif kind == 'OFFSET':
            title = 'Offset outline'
            rows = [('SLIDER', 'dd_offset', 'Distance'), ('OFFSET', 'Create offset copy', '')]
        elif kind == 'SEWING':
            title = 'Sewing'
            rows = [('SEW', 'Pair edges', ''), ('FREE_SEW', 'Pick range on edges', ''),
                    ('CHAIN_A', 'Collect side A', ''), ('CHAIN_B', 'Collect side B', ''),
                    ('CHAIN_SEW', 'Sew chains', '')]
        elif kind == 'RESULT':
            title = 'Drape'
            rows = [('RESET', 'Reset drape', ''), ('VIEW_3D', 'Show 3D', '')]
        elif kind == 'HELP':
            title = 'Shortcuts'
            rows = [('INFO', 'V / P / R / E', 'Select / Poly / Rect / Ellipse'),
                    ('INFO', 'I / D', 'Internal path / Dart'),
                    ('INFO', 'J / K / T', 'Sew / Pin / Tack'),
                    ('INFO', 'S / H / L', 'Snap / Body guide / Lengths'),
                    ('INFO', 'Ctrl+Z / Ctrl+Shift+Z', 'Undo / Redo'),
                    ('INFO', 'F / Home', 'Fit to design'),
                    ('INFO', 'Esc', 'Step back / Cancel / Exit')]
        scale = self.canvas_layout.scale
        compact = self.canvas_layout.panel.w < 760 * scale
        if compact and kind == 'PIECE':
            rows = [row for row in rows if row[0] != 'INFO']
        width = min((210 if kind == 'WORKSPACE' or compact else 246) * scale, self.canvas_layout.panel.w - 24 * scale)
        row_heights = [64 if row[0] == 'CHOICES' else 40 for row in rows]
        height = (42 + sum(row_heights)) * scale
        bounds = self.canvas_layout.panel
        anchor = self.card_anchor
        if anchor is None:
            anchor = (bounds.x + 76 * scale, bounds.y + 220 * scale)
        card_x = max(bounds.x + 8 * scale, min(anchor[0], bounds.x + bounds.w - width - 8 * scale))
        card_y = max(bounds.y + 58 * scale, min(anchor[1] - height, bounds.y + bounds.h - height - 34 * scale))
        if kind == 'WORKSPACE':
            card_x = bounds.x + bounds.w - width - 14 * scale
            card_y = bounds.y + (bounds.h - height) / 2
        elif kind in {'PIECE', 'EDIT'} and pattern:
            points = [self.view.screen(point, self.canvas_layout.canvas) for point in pattern.points]
            anchor = (max(point[0] for point in points) + 18 * scale, sum(point[1] for point in points) / len(points))
            card_x = max(bounds.x + 8 * scale, min(anchor[0], bounds.x + bounds.w - width - (230 if self.workspace_panel_open else 14) * scale))
            card_y = max(bounds.y + 58 * scale, min(anchor[1] - height / 2, bounds.y + bounds.h - height - 34 * scale))
        elif kind in {'PIECE', 'EDIT'}:
            card_x = bounds.x + bounds.w - width - (230 if self.workspace_panel_open else 14) * scale
            card_y = bounds.y + bounds.h - height - 44 * scale
        elif kind in {'SIMULATE', 'KEEP', 'RESULT'}:
            card_x = bounds.x + bounds.w - width - 14 * scale
            card_y = bounds.y + 58 * scale
        elif kind in {'GARMENT', 'HELP', 'LIBRARY', 'BODY', 'REFERENCE_IMAGE', 'TRACE_CALIBRATION', 'TRACE_POSITION'}:
            card_x = bounds.x + 80 * scale
            card_y = bounds.y + bounds.h - height - 44 * scale
        elif kind == 'FABRIC':
            card_x = bounds.x + bounds.w - width - (230 if self.workspace_panel_open else 14) * scale
            card_y = max(bounds.y + 58 * scale, bounds.y + bounds.h - height - 220 * scale)
        rect = Rect(card_x, card_y, width, height)
        controls = []
        top = card_y + height - 40 * scale
        for row, row_height in zip(rows, row_heights):
            top -= row_height * scale
            controls.append((Rect(card_x + 8 * scale, top, width - 16 * scale, row_height * scale), row))
        return rect, title, controls

    def visible_cards(self):
        cards = [self.workspace_card()]
        if self.card_kind == 'FABRIC':
            cards.append(self.minimal_card('PIECE'))
        if self.card_kind or not self.context_card_hidden:
            cards.append(self.minimal_card())
        return [card for card in cards if card is not None]

    def workspace_card(self):
        return self.minimal_card('WORKSPACE') if self.workspace_panel_open else None

    def workspace_header_controls(self, rect):
        scale = self.canvas_layout.scale
        return [(Rect(rect.x + rect.w - 66 * scale, rect.y + rect.h - 29 * scale, 36 * scale, 24 * scale), 'WORKSPACE_PIN'),
                (Rect(rect.x + rect.w - 28 * scale, rect.y + rect.h - 29 * scale, 22 * scale, 24 * scale), 'WORKSPACE_CLOSE')]

    def card_close_rect(self, rect):
        scale = self.canvas_layout.scale
        return Rect(rect.x + rect.w - 32 * scale, rect.y + rect.h - 32 * scale, 24 * scale, 24 * scale)

    def tool_hint(self):
        if self.draft:
            return 'Click to add points / Enter to finish / Esc to cancel'
        if self.tool == 'SEW':
            if self.chain_stage:
                return 'Click edges in order / Right-click for sewing options'
            return 'Pick the matching edge' if self.pending_edge else 'Click two edges to sew / Right-click for ranges or chains'
        return {'SELECT': 'Drag points or pieces / Right-click a point, edge or piece to edit',
                'RECTANGLE': 'Drag to draw a panel / Shift for a square',
                'ELLIPSE': 'Drag to draw an ellipse / Shift for a circle',
                'POLYGON': 'Click to draw / Click the first point or Enter to finish',
                'INTERNAL': 'Click to draw an internal path / Enter to finish',
                'PIN': 'Click a pattern point to pin or unpin',
                'DART': 'Pick two base points, then the dart tip',
                'TACK': 'Pick a pattern point, then a point on the body',
                'PLACE': 'Pick a piece, then a point on the body'}.get(self.tool, '')

    def apply_local_setting(self, key):
        if not self.minimal_ui:
            return super().apply_local_setting(key)
        if key == 'dd_weld_distance':
            self.weld_manual = True
        action = {'dd_point_x': 'POINT_APPLY', 'dd_point_y': 'POINT_APPLY', 'dd_segment_length': 'SET_LENGTH'}.get(key)
        if action:
            return self.perform_action(action)

    def minimal_action(self, key):
        scene = self._scene
        cards = {'FABRIC': 'FABRIC', 'GARMENT': 'GARMENT', 'BODY_CARD': 'BODY', 'LIBRARY': 'LIBRARY',
                 'PIECE_DENSITY': 'PIECE_DENSITY',
                 'ARRANGE': 'ARRANGEMENT',
                 'REFERENCE_IMAGE': 'REFERENCE_IMAGE', 'TRACE_CALIBRATION': 'TRACE_CALIBRATION',
                 'TRACE_POSITION': 'TRACE_POSITION',
                 'EDIT_CARD': 'EDIT',
                 'PLACEMENT': 'PLACEMENT', 'INTERNAL_EDIT': 'INTERNAL_EDIT', 'OFFSET_CARD': 'OFFSET',
                 'SIMULATE_OPTIONS': 'SIMULATE', 'KEEP_OPTIONS': 'KEEP',
                 'HELP': 'HELP'}
        if key.startswith('WORKSPACE_'):
            if key == 'WORKSPACE_PANEL':
                self.workspace_panel_open = not self.workspace_panel_open
            elif key == 'WORKSPACE_CLOSE':
                self.workspace_panel_open = False
            elif key == 'WORKSPACE_PIN':
                self.workspace_panel_pinned = not self.workspace_panel_pinned
            elif key == 'WORKSPACE_SNAP':
                self.snap = not self.snap
            elif key == 'WORKSPACE_LENGTHS':
                scene.dd_lengths_visible = not scene.dd_lengths_visible
            elif key == 'WORKSPACE_GUIDE':
                scene.dd_reference_visible = not scene.dd_reference_visible
                if scene.dd_reference_visible and scene.dd_avatar is None:
                    self.message = 'Choose a body from the garment card to show its guide.'
                self.update_reference(bpy.context, force=True)
            elif key == 'WORKSPACE_FIT':
                self.fit()
            elif key.startswith('WORKSPACE_OPACITY_'):
                scene.dd_reference_opacity = GUIDE_OPACITY[key.removeprefix('WORKSPACE_OPACITY_')]
        elif key in cards:
            self.show_card(cards[key])
        elif key == 'TRACE_LOAD':
            bpy.ops.devil.load_trace_image('INVOKE_DEFAULT')
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
                self.context_card_hidden = True
                self.message = 'Click the first end of the measured length on the image. Escape cancels.'
        elif key in {'CUT', 'CUT_RETRY'}:
            self.perform_action(key)
        elif key == 'CANCEL_CUT':
            self.cut_preview = None
            self.card_kind = None
        elif key.startswith('SET_DENSITY_'):
            self.run_edit(lambda: self.session.set_mesh_density(key.removeprefix('SET_DENSITY_')), 'Piece mesh density updated.')
        elif key.startswith('ARRANGE_'):
            from . import arrangement
            try:
                self.persist()
                count = arrangement.arrange(bpy.context, key.removeprefix('ARRANGE_'))
                self.card_kind = None
                self.message = f'{count} pieces arranged. Adjust in 3D before simulation.'
            except (ValueError, RuntimeError) as exc:
                self.message = str(exc)
            finally:
                self.reconcile_generated_document()
        elif key.startswith(('DENSITY_', 'QUALITY_', 'THICKNESS_')):
            prefix, choice = key.split('_', 1)
            property_name, choices = {'DENSITY': ('dd_spacing', DENSITY), 'QUALITY': ('dd_quality', QUALITY),
                                      'THICKNESS': ('dd_thickness', THICKNESS)}[prefix]
            setattr(scene, property_name, choices[choice])
        elif key == 'NAME':
            value = scene.dd_library_name
            self.numeric = dict(key='dd_library_name', text=value, cursor=len(value), selected=True)
        elif key == 'WELD_AUTO':
            self.weld_manual = False
            scene.dd_weld_distance = .01
        elif key == 'TOGGLE_SNAP':
            self.snap = not self.snap
            self.message = f"Snap {'enabled' if self.snap else 'disabled'} [S]."
        elif key == 'TOGGLE_GUIDE':
            scene.dd_reference_visible = not scene.dd_reference_visible
            if scene.dd_reference_visible and scene.dd_avatar is None:
                self.message = 'Choose a body from the garment card to show its guide.'
            else:
                self.message = f"Body guide {'shown' if scene.dd_reference_visible else 'hidden'} [H]."
            self.update_reference(bpy.context, force=True)
        elif key == 'TOGGLE_LENGTHS':
            scene.dd_lengths_visible = not scene.dd_lengths_visible
            self.message = f"Edge lengths {'shown' if scene.dd_lengths_visible else 'hidden'} [L]."
        elif key == 'RESTORE_CANVAS':
            self.restore_canvas()
        elif key.startswith('PAGE_'):
            count = len(self.card_models) if key == 'PAGE_BODY' else len(self.library_items)
            self.card_page = (self.card_page + 1) % max(1, math.ceil(count / 8))
        elif key.startswith('BODY_'):
            self.choose_body(self.card_models[int(key[5:])], bpy.context)
            self.card_kind = None
        elif key.startswith('LOAD_'):
            scene.dd_library_selected = int(key[5:])
            self.perform_action('LIBRARY_LOAD')
            self.card_kind = None
        elif key == 'START_PANEL':
            if self.perform_action(key):
                self.choose_tool('SELECT')
                self.fit()
                self.card_kind = None
        elif key in {'FLIP_SEAM', 'REMOVE_SEAM'}:
            identity = self.seam_selected
            if key == 'FLIP_SEAM':
                self.run_edit(lambda: self.session.reverse_seam(identity), 'Seam reversed.')
            else:
                self.run_edit(lambda: self.session.remove_seam(identity), 'Seam removed.')
                self.seam_selected = None
                self.card_kind = None
        elif key in {'FULL', 'CLOSE'}:
            if key == 'CLOSE':
                if self.draft or self.gesture:
                    self.cancel_gesture()
                self.cleanup()
        else:
            if key in {'SIMULATE', 'KEEP', 'KEEP_RETRY'}:
                self.automatic_defaults(finalize=key != 'SIMULATE')
            self.perform_action('KEEP' if key == 'KEEP_RETRY' else key)
            if not self.pending_simulation:
                self.card_kind = None
            if key.startswith('SET_PRESET_'):
                self.card_kind = None

    def minimal_event(self, context, event):
        press = event.value == 'PRESS'
        if self.numeric:
            result = self.numeric_event(event)
            if result is not None:
                return result
        if self.setting_drag:
            return self.controls_event(context, event)
        if self.gesture or (press and event.type == 'ESC' and (self.draft or self.free_clicks)):
            return None
        if press and event.type in {'ESC', 'RIGHTMOUSE'} and self.pending_edge:
            self.pending_edge = None
            self.message = 'Seam selection cancelled.'
            return {'RUNNING_MODAL'}
        point = self.pointer
        button = self.canvas_layout.button(*point)
        if press and event.type == 'ESC' and self.card_kind:
            self.card_kind = None
            self.pending_simulation = False
            return {'RUNNING_MODAL'}
        pointer_event = event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'MOUSEMOVE',
                                     'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}
        if not pointer_event:
            return None
        card = next((card for card in reversed(self.visible_cards()) if card[0].contains(*point)), None)
        if card and self.card_kind in {'BODY', 'LIBRARY'} and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            count = len(self.card_models) if self.card_kind == 'BODY' else len(self.library_items)
            pages = max(1, math.ceil(count / 8))
            delta = -1 if event.type == 'WHEELUPMOUSE' else 1
            self.card_page = (self.card_page + delta) % pages
            return {'RUNNING_MODAL'}
        if self.card_kind and press and event.type == 'RIGHTMOUSE':
            self.card_kind = None
            self.pending_simulation = False
            return {'RUNNING_MODAL'}
        if button and not card and press and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:
            if self.card_kind:
                self.card_kind = None
                self.pending_simulation = False
            if event.type == 'RIGHTMOUSE':
                if button in {'SIMULATE', 'KEEP'}:
                    self.show_card(button)
                elif button == 'SEW':
                    self.show_card('SEWING')
                else:
                    return {'RUNNING_MODAL'}
            else:
                self.minimal_action(button)
            return {'FINISHED'} if self._closed else {'RUNNING_MODAL'}
        if card:
            if press and event.type == 'LEFTMOUSE':
                workspace_card = self.workspace_card()
                if card != workspace_card and self.card_close_rect(card[0]).contains(*point):
                    self.context_card_hidden = True
                    self.card_kind = None
                    self.pending_simulation = False
                    return {'RUNNING_MODAL'}
                if workspace_card and card == workspace_card:
                    for rect, key in self.workspace_header_controls(card[0]):
                        if rect.contains(*point):
                            self.minimal_action(key)
                            return {'RUNNING_MODAL'}
                for rect, row in card[2]:
                    if not rect.contains(*point):
                        continue
                    key, label, value = row
                    if key == 'CHOICES':
                        prefix, choices, active = value
                        index = min(len(choices) - 1, int((point[0] - rect.x) / (rect.w / len(choices))))
                        self.minimal_action(prefix + '_' + list(choices)[index])
                    elif key == 'SLIDER':
                        self.setting_drag = dict(key=label, value=getattr(self._scene, label), pointer=point, moved=False)
                        if label == 'dd_weld_distance':
                            scale = self.canvas_layout.scale
                            self.setting_drag['absolute'] = Rect(rect.x + 6 * scale, rect.y, rect.w - 12 * scale, rect.h)
                    elif key != 'INFO':
                        self.minimal_action(key)
                    break
            return {'RUNNING_MODAL'}
        if self.gesture:
            return None
        if press and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and not self.workspace_panel_pinned:
            self.workspace_panel_open = False
        if press and event.type == 'LEFTMOUSE':
            self.context_card_hidden = False
            for rect, identity, label in self.seam_badges():
                if rect.contains(*point):
                    self.selected_anchor = None
                    self.seam_selected = identity
                    self.show_card('SEAM', (rect.x + rect.w + 6, rect.y + rect.h))
                    return {'RUNNING_MODAL'}
            if self.card_kind:
                self.card_kind = None
                self.pending_simulation = False
                return {'RUNNING_MODAL'}
            self.seam_selected = None
        if press and event.type == 'RIGHTMOUSE' and self.canvas_layout.canvas.contains(*point) and not self.draft:
            scale = self.canvas_layout.scale
            anchor = next((anchor for anchor in self.session.document.anchors
                           if math.dist(self.view.screen((anchor.x, anchor.y), self.canvas_layout.canvas), point) <= 10 * scale), None)
            if anchor:
                self.select_anchor(anchor)
                self.show_card('ANCHOR', point)
                return {'RUNNING_MODAL'}
            if self.pending_edge:
                self.pending_edge = None
                self.message = 'Seam selection cancelled.'
                return {'RUNNING_MODAL'}
            if self.tool == 'SEW':
                self.show_card('SEWING')
            else:
                self.selected_anchor = None
                self.seam_selected = None
                pattern, corner = self.hit()
                if pattern is None:
                    self.session.selected = None
                    self.session.corner = None
                    self.session.segment = None
                    self.session.point_selection = []
                    self.card_kind = None
                    self.sync_selection()
                    return {'RUNNING_MODAL'}
                if (self.session.selected != pattern.id or self.session.path != self.hit_path
                        or corner not in self.session.point_selection):
                    self.session.point_selection = [corner] if corner is not None else []
                self.session.selected = pattern.id
                self.session.corner = corner
                self.session.path = self.hit_path
                self.session.segment = self.hit_edge() if corner is None else None
                self.sync_selection()
                self.show_card('POINT' if corner is not None else
                               'INTERNAL_EDGE' if self.session.segment and self.session.path != 'OUTER' else
                               'EDGE' if self.session.segment else 'EDIT')
            return {'RUNNING_MODAL'}
        return None
