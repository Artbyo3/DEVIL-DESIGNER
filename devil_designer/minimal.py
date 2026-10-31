import math
import bpy
from .canvas import Rect
from . import layering


DENSITY = {'Coarse': .04, 'Standard': .02, 'Fine': .01}
QUALITY = {'Draft': 6, 'Standard': 12, 'High': 24}
THICKNESS = {'None': 0, 'Thin': .0005, 'Standard': .001}
FABRICS = ('COTTON', 'LINEN', 'DENIM', 'SILK', 'LEATHER', 'KNIT')
GUIDE_OPACITY = {'Light': .15, 'Medium': .30, 'Strong': .50}
IMAGE_OPACITY = {'Light': .2, 'Medium': .35, 'Strong': .6}


def minimal_layout(layout, pending=False, confirmation=False, playing=False, kept=False):
    scale = layout.scale
    panel = layout.panel
    layout.minimal = True
    layout.inspector = None
    layout.inspector_collapsed = True
    layout.header = Rect(panel.x, panel.y + panel.h - 32 * scale, panel.w, 32 * scale)
    layout.footer = Rect(panel.x, panel.y, panel.w, 0)
    dock_height = min(540 * scale, panel.h - 112 * scale)
    dock_width = 72 * scale
    layout.rail = Rect(panel.x + 14 * scale, panel.y + (panel.h - dock_height) / 2, dock_width, dock_height)
    layout.buttons = {}
    tools = [('SELECT', 'Select'), ('DRAW', 'Draw'), ('INTERNAL', 'Internal'), ('SEW', 'Sew'),
             ('PIN', 'Pin'), ('UNDO', 'Undo'), ('REDO', 'Redo'), ('LIBRARY', 'Library')]
    indicator_h = 22 * scale
    tools_h = dock_height - indicator_h - 10 * scale
    row_height = tools_h / len(tools)
    for index, (key, label) in enumerate(tools):
        layout.buttons[key] = (Rect(layout.rail.x + 4 * scale,
            layout.rail.y + dock_height - (index + 1) * row_height + 2 * scale,
            dock_width - 8 * scale, row_height - 4 * scale), label)
    chip_w = (dock_width - 14 * scale) / 4
    chip_y = layout.rail.y + 4 * scale
    layout.buttons['TOGGLE_SNAP'] = (Rect(layout.rail.x + 4 * scale, chip_y, chip_w, indicator_h), 'Snap')
    layout.buttons['TOGGLE_GUIDE'] = (Rect(layout.rail.x + 4 * scale + chip_w + 2 * scale, chip_y, chip_w, indicator_h), 'Guide')
    layout.buttons['TOGGLE_LENGTHS'] = (Rect(layout.rail.x + 4 * scale + (chip_w + 2 * scale) * 2, chip_y, chip_w, indicator_h), 'Lengths')
    layout.buttons['TOGGLE_FIT_MAP'] = (Rect(layout.rail.x + 4 * scale + (chip_w + 2 * scale) * 3, chip_y, chip_w, indicator_h), 'Fit map')
    right = panel.x + panel.w - 14 * scale
    layout.buttons['CLOSE'] = (Rect(right - 24 * scale, panel.y + panel.h - 30 * scale, 24 * scale, 24 * scale), 'Close')
    right -= 28 * scale
    if not layout.full:
        right -= 88 * scale
        layout.buttons['RESTORE_CANVAS'] = (Rect(right, panel.y + panel.h - 30 * scale, 82 * scale, 24 * scale), 'Full canvas')
    layout.buttons['GARMENT'] = (Rect(panel.x + 14 * scale, panel.y + panel.h - 36 * scale, min(220 * scale, panel.w * .40), 30 * scale), 'Garment')
    layout.canvas = Rect(panel.x + 4 * scale, panel.y + 4 * scale, panel.w - 8 * scale, panel.h - 8 * scale)
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
        if key == 'KEEP':
            layout.buttons['KEEP_OPTIONS'] = (Rect(right + 112 * scale, bottom, 30 * scale, 40 * scale), 'Options')
            layout.buttons['KEEP'] = (Rect(right, bottom, 112 * scale, 40 * scale), label)
        elif key == 'SIMULATE' and kept:
            layout.buttons['SIMULATE_OPTIONS'] = (Rect(right + 112 * scale, bottom, 30 * scale, 40 * scale), 'Wear over')
            layout.buttons['SIMULATE'] = (Rect(right, bottom, 112 * scale, 40 * scale), label)
        right -= 8 * scale


class MinimalCards:
    def initialize_minimal(self):
        self.minimal_ui = True
        self.advanced_tools = False
        self.weld_manual = False
        self.card_kind = None
        self.card_anchor = None
        self.card_page = 0
        self.wear_over_offset = 0
        self.card_models = []
        self.library_items = []
        self.toast_message = ''
        self.toast_until = 0
        self._scene.dd_reference_visible = False
        self._scene.dd_fabric = getattr(self.session.document, 'preset', 'COTTON')
        self.sync_fabric_settings(self._scene.dd_fabric)
        self.draw_shape = 'RECTANGLE'
        self.internal_tool = 'INTERNAL'
        self.knife_sew = True
        self.pin_tool = 'PIN'

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
        self.wear_over_offset = 0
        self.search_active = False
        self.context_anchor = None
        self.settings_open = False
        if kind == 'LIBRARY':
            self.refresh_library()

    def minimal_card(self):
        kind = self.card_kind
        if not kind:
            return None
        scene = self._scene
        doc = self.session.document
        pattern = doc.find(self.session.selected)
        anchor = next((a for a in doc.anchors if a.id == self.selected_anchor), None)
        rows = []
        title = kind.title()
        if kind == 'GARMENT':
            title = 'Garment'
            rows = [('NAME', scene.dd_library_name, 'Rename'),
                    ('LIBRARY_SAVE', 'Save garment', ''),
                    ('REFERENCE_IMAGE', 'Reference image', 'Trace a photo'),
                    ('TOGGLE_MEASURE', 'Measure guide', 'Hide' if scene.dd_measure_visible else 'Show')]
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
                    rows.append(('INFO', 'Landmarks', 'Estimated by height proportions'))
            elif scene.dd_avatar:
                rows.append(('INFO', 'Measurements', 'Choose body to refresh'))
            else:
                rows.append(('INFO', 'Measurements', 'Choose body first'))
            if not doc.patterns:
                rows.append(('STARTER_TEE', 'Tee starter', 'Fitted top'))
                rows.append(('STARTER_TANK', 'Tank starter', 'Sleeveless top'))
                rows.append(('STARTER_SKIRT', 'Skirt starter', 'A-line skirt'))
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
            if scene.dd_avatar is not None:rows.append(('REGENERATE_VOLUMES','Regenerate body volumes','Resets point edits'))
        elif kind == 'LIBRARY':
            title = 'Garment library'
            rows = [('LOAD_' + str(index), item.stem.replace('.garment', ''), 'Load') for index, item in enumerate(self.library_items) if self.card_page * 8 <= index < (self.card_page + 1) * 8]
            if len(self.library_items) > 8:
                pages = math.ceil(len(self.library_items) / 8)
                rows.append(('PAGE_LIBRARY', f'More garments ({self.card_page + 1}/{pages})', 'Next'))
            rows.append(('LIBRARY_SAVE', 'Save current garment', ''))
        elif kind == 'SIMULATE':
            title = 'Wear over'
            self.card_models = layering.kept_garments(scene)
            if not self.card_models:
                return None
            self.wear_over_offset = max(0,min(self.wear_over_offset,len(self.card_models)-5))
            rows = [('WEAR_OVER_' + str(index), obj.name, 'On' if obj.get('dd_wear_over',True) else 'Off')
                    for index,obj in enumerate(self.card_models) if self.wear_over_offset <= index < self.wear_over_offset+5]
            if len(self.card_models)>5:
                rows.append(('SCROLL_WEAR_OVER',f'{self.wear_over_offset+1}-{min(self.wear_over_offset+5,len(self.card_models))} of {len(self.card_models)} garments','Next'))
        elif kind == 'KEEP':
            title = 'Keep mesh'
            rows = [('WELD_AUTO', 'Weld', 'Manual' if self.weld_manual else 'Auto'),
                    ('CHOICES', 'Thickness', ('THICKNESS', THICKNESS, self.named_choice(scene.dd_thickness, THICKNESS)))]
            if scene.get('dd_unwelded_seams', 0) > 0:
                rows += [('SLIDER', 'dd_weld_distance', 'Weld tolerance'), ('KEEP_RETRY', 'Retry keep', f"{scene['dd_unwelded_seams']} unwelded pairs")]
        elif kind == 'DRAW_CHOOSER':
            title = 'Draw shape'
            rows = [('SET_DRAW_POLYGON', 'Polygon', 'P'),
                    ('SET_DRAW_RECTANGLE', 'Rectangle', 'R'),
                    ('SET_DRAW_ELLIPSE', 'Ellipse', 'E')]
        elif kind == 'INTERNAL_CHOOSER':
            title = 'Internal'
            rows = [('SET_INTERNAL_PATH', 'Internal path', 'I'),
                    ('SET_INTERNAL_DART', 'Dart', 'D'),
                    ('SET_INTERNAL_KNIFE', 'Cut', 'N'),
                    ('KNIFE_MODE_SEW', 'Cut & Sew' + (' (active)' if self.knife_sew else ''), ''),
                    ('KNIFE_MODE_CUT', 'Cut only' + (' (active)' if not self.knife_sew else ''), ''),
                    ('CUT', 'Cut along path', '')]
        elif kind == 'PIN_CHOOSER':
            title = 'Pin or tack'
            rows = [('SET_PIN_FABRIC', 'Pin on fabric', 'K'),
                    ('SET_PIN_BODY', 'Attach to body', 'T')]
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
            rows.append(('SLIDER', 'dd_fabric_shear', 'Shear stiffness'))
            rows.append(('SLIDER', 'dd_fabric_bending', 'Bending stiffness'))
            rows.append(('SLIDER', 'dd_fabric_density', 'Mass density'))
            rows.append(('SAVE_PIECE_CUSTOM_PRESET', 'Save as custom preset', ''))
            if getattr(pattern, 'fabric_override', False) and pattern.preset in getattr(doc, 'custom_presets', {}):
                rows.append(('DELETE_CUSTOM_PRESET', 'Delete preset', ''))
        elif kind == 'GARMENT_FABRIC':
            title = 'Garment fabric'
            customs = list(getattr(doc, 'custom_presets', {}).keys())
            all_presets = list(FABRICS) + customs
            active = getattr(doc, 'preset', 'COTTON')
            rows.append(('CHOICES_FABRIC', 'Default fabric', ('INSP_GARMENT_FABRIC', all_presets, active)))
            rows.append(('SLIDER', 'dd_fabric_structural', 'Stretch stiffness'))
            rows.append(('SLIDER', 'dd_fabric_shear', 'Shear stiffness'))
            rows.append(('SLIDER', 'dd_fabric_bending', 'Bending stiffness'))
            rows.append(('SLIDER', 'dd_fabric_density', 'Mass density'))
            rows.append(('SAVE_GARMENT_CUSTOM_PRESET', 'Save as custom preset', ''))
            if active in getattr(doc, 'custom_presets', {}):
                rows.append(('DELETE_CUSTOM_PRESET', 'Delete preset', ''))
        elif kind == 'PIECE_DENSITY':
            title = 'Mesh density override'
            rows = [('SET_DENSITY_AUTO', 'Garment default', ''),
                    ('SET_DENSITY_COARSE', 'Coarse', ''),
                    ('SET_DENSITY_STANDARD', 'Standard', ''),
                    ('SET_DENSITY_FINE', 'Fine', '')]
        elif kind == 'PIECE_SIMULATION':
            if pattern is None:
                return None
            title = 'Piece simulation'
            rows = [('TOGGLE_STATE_frozen', 'Unfreeze' if pattern.frozen else 'Freeze', 'Held seam'),
                    ('TOGGLE_STATE_deactivated', 'Activate' if pattern.deactivated else 'Deactivate', 'No collision'),
                    ('TOGGLE_STATE_strengthened', 'Remove strengthen' if pattern.strengthened else 'Strengthen', '×4 stiffness')]
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
            density_label = {'AUTO': 'Garment default', 'COARSE': 'Coarse', 'STANDARD': 'Standard', 'FINE': 'Fine'}.get(pattern.mesh_density, pattern.mesh_density.title())
            rows.append(('MENU', 'PIECE_DENSITY_MENU', 'Mesh density', density_label))
            from .piece_states import label
            simulation_label = label(pattern).replace(' · Strengthened ×4', ' +4×')
            rows.append(('MENU', 'PIECE_SIMULATION_MENU', 'Simulation', simulation_label or 'Normal'))
            rows.append(('PAIR_ACTIONS', 'DUPLICATE', 'MIRROR_SEW', 'Duplicate', 'Mirror'))
            rows.append(('CLONE_LINKED', 'Clone as linked twin', ''))
            if pattern.arrangement and pattern.arrangement['point']=='front':
                rows.append(('CLONE_BACK', 'Clone as Back', ''))
            from .linked_editing import pair_for
            linked=pair_for(doc,pattern.id)
            rows.append(('TOGGLE_LINKED', 'Linked twin', 'On' if linked and linked['enabled'] else 'Off'))
            rows.append(('PAIR_ACTIONS', 'FLIP_H', 'FLIP_V', 'Flip H', 'Flip V'))
            rows.append(('PAIR_ACTIONS', 'ROTATE_CW', 'ROTATE_CCW', 'Rotate 90°', 'Rotate -90°'))
            rows.append(('PAIR_ACTIONS', 'UNFOLD', 'DELETE_PIECE', 'Unfold', 'Delete'))
            rows.append(('RESET_LAYOUT', 'Reset to 2D layout', ''))
        elif kind == 'CANVAS_MENU':
            title = 'Garment & View'
            rows.append(('MENU', 'BODY_CHANGE', 'Body', scene.dd_avatar.name if scene.dd_avatar else 'None'))
            if not doc.patterns:
                rows.append(('STARTER_TEE', 'Tee starter', 'Fitted top'))
                rows.append(('STARTER_TANK', 'Tank starter', 'Sleeveless top'))
                rows.append(('STARTER_SKIRT', 'Skirt starter', 'A-line skirt'))
                rows.append(('DEMO_PANEL', 'Create panel', '40 × 45 cm'))
                rows.append(('SET_DRAW_POLYGON', 'Draw your own', 'Tool'))
                rows.append(('MENU_LIBRARY', 'Library', 'Open'))
            customs = list(getattr(doc, 'custom_presets', {}).keys())
            all_fabrics = list(FABRICS) + customs
            rows.append(('CHOICES_FABRIC', 'Default fabric', ('INSP_GARMENT_FABRIC', all_fabrics, getattr(doc, 'preset', 'COTTON'))))
            rows.append(('MENU', 'GARMENT_FABRIC_MENU', 'Fabric behavior', getattr(doc, 'preset', 'COTTON').title()))
            rows.append(('CHOICES', 'Mesh density', ('INSP_GARMENT_DENSITY', DENSITY, self.named_choice(scene.dd_spacing, DENSITY))))
            rows.append(('CHOICES', 'Quality', ('INSP_QUALITY', QUALITY, self.named_choice(scene.dd_quality, QUALITY))))
            rows.append(('CHOICES', 'Guide opacity', ('INSP_OPACITY', GUIDE_OPACITY, self.named_choice(scene.dd_reference_opacity, GUIDE_OPACITY))))
            rows.append(('INSP_FIT', 'Fit design', ''))
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
                    ('SLIDER', 'dd_point_y', 'Y position')]
            if len(self.session.point_selection) > 1:
                rows.append(('MERGE', 'Merge selected points', ''))
        elif kind == 'EDGE':
            title = 'Edge'
            rows = [('SLIDER', 'dd_segment_length', 'Exact length'),
                    ('SPLIT', 'Split edge', ''),
                    ('PAIR_ACTIONS', 'UNFOLD', 'MIRROR_SEW', 'Unfold', 'Mirror')]
        elif kind == 'INTERNAL_EDGE':
            title = 'Internal edge'
            rows = [('SLIDER', 'dd_segment_length', 'Exact length'),
                    ('SPLIT', 'Split edge', ''),
                    ('CUT', 'Cut along path', '')]
            if pattern and pattern.path(self.session.path).closed:
                rows.append(('TRACE', 'Trace as piece', ''))
        elif kind == 'EDIT':
            title = pattern.name if pattern else 'Edit piece'
            rows = [('DUPLICATE', 'Duplicate', ''),
                    ('MIRROR_SEW', 'Mirror and sew', ''),
                    ('UNFOLD', 'Unfold', ''),
                    ('DELETE_PIECE', 'Delete piece', '')]
        elif kind == 'ANCHOR':
            if anchor is None:
                return None
            title = 'Body tack' if anchor.kind == 'TACK' else 'Pin'
            rows = [('INFO', 'Attached to', pattern.name if pattern else 'Pattern'),
                    ('REMOVE_ANCHOR', 'Remove tack' if anchor.kind == 'TACK' else 'Remove pin', 'Delete')]
        elif kind == 'SEAM':
            seam = next((s for s in doc.seams if s.id == self.seam_selected), None)
            title = 'Selected seam'
            if seam:
                _, _, diff, pct = doc.seam_stats(seam)
                rows.append(('INFO', 'Mismatch', f'{diff * 100:.1f} cm ({pct:.1f}%)'))
                rows.append(('CHOICES', 'Shrink', ('SEAM_SHRINK', ('0%', '10%', '20%', '30%'), f'{seam.shrink}%')))
                rows.append(('INFO', 'Nonzero: 1 mm self-collision', ''))
                rows.append(('INFO', 'Other folds may change', ''))
            rows.append(('PAIR_ACTIONS', 'FLIP_SEAM', 'REMOVE_SEAM', 'Reverse', 'Remove'))
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
        elif kind == 'MULTI_SELECTION':
            pieces, points = self.session.selection_counts()
            if pieces > 0 and points > 0:
                title = f'{pieces} pieces, {points} points'
                rows = [('DELETE', 'Delete', 'Del')]
            elif pieces > 0:
                title = f'{pieces} pieces'
                rows = [('DUPLICATE', 'Duplicate', 'Shift+D'),
                        ('PAIR_ACTIONS', 'FLIP_H', 'FLIP_V', 'Flip H', 'Flip V'),
                        ('PAIR_ACTIONS', 'ROTATE_CW', 'ROTATE_CCW', 'Rotate 90°', 'Rotate -90°'),
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
                rows.append(('PAIR_ACTIONS', 'ROTATE_CW', 'ROTATE_CCW', 'Rotate 90°', 'Rotate -90°'))
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
        else:
            return None

        scale = self.canvas_layout.scale
        width = min(220 * scale, self.canvas_layout.panel.w - 24 * scale)
        row_heights = [(math.ceil(len(row[2][1]) / 3) * 24 + 16 if len(row[2][1]) > 4 else 36) if row[0] == 'CHOICES_FABRIC' else 48 if row[0] == 'CHOICES' else 32 for row in rows]
        if kind=='PIECE':
            row_height=min(32,(self.canvas_layout.panel.h/scale-130)/max(1,len(rows)))
            row_heights=[max(24,row_height) for row in rows]
        height = (38 + sum(row_heights)) * scale
        bounds = self.canvas_layout.panel
        anchor_pt = self.card_anchor or (bounds.x + 80 * scale, bounds.y + bounds.h - 100 * scale)
        card_x = max(bounds.x + 8 * scale, min(anchor_pt[0], bounds.x + bounds.w - width - 8 * scale))
        card_y = max(bounds.y + 58 * scale, min(anchor_pt[1] - height, bounds.y + bounds.h - height - 34 * scale))
        rect = Rect(card_x, card_y, width, height)
        controls = []
        top = card_y + height - 36 * scale
        for row, row_h in zip(rows, row_heights):
            top -= row_h * scale
            controls.append((Rect(card_x + 8 * scale, top, width - 16 * scale, row_h * scale), row))
        return rect, title, controls

    def visible_cards(self):
        card = self.minimal_card()
        return [card] if card is not None else []

    def card_close_rect(self, rect):
        scale = self.canvas_layout.scale
        return Rect(rect.x + rect.w - 28 * scale, rect.y + rect.h - 28 * scale, 22 * scale, 22 * scale)

    def tool_hint(self):
        if self.tool == 'KNIFE':
            return ('Cut & Sew' if self.knife_sew else 'Cut') + ' / Click points / Enter or double-click finishes / Shift locks axis / Esc cancels'
        if self.draft:
            return 'Click to add points / Enter to finish / Esc to cancel'
        if self.tool == 'SEW':
            if self.chain_stage:
                return 'Click edges in order'
            return 'Pick the matching edge' if self.pending_edge else 'Click two edges to sew'
        if self.tool == 'SELECT':
            pieces, points = self.session.selection_counts()
            if pieces > 0 and points > 0:
                p_str = f"{pieces} piece{'s' if pieces != 1 else ''}"
                pt_str = f"{points} point{'s' if points != 1 else ''}"
                return f"{p_str}, {pt_str} · Drag to move"
            if pieces > 0:
                p_str = f"{pieces} piece{'s' if pieces != 1 else ''}"
                return f"{p_str} · Drag to move"
            if points > 0:
                pt_types = []
                for pid, path_id, idx in self.session.selected_points:
                    pat = self.session.document.find(pid)
                    if pat:
                        try:
                            v = pat.path(path_id).vertices[idx]
                            pt_types.append(getattr(v, 'point_type', 'CORNER').title())
                        except (IndexError, ValueError):
                            pass
                if not pt_types and self.session.selected and self.session.corner is not None:
                    pat = self.session.document.find(self.session.selected)
                    if pat:
                        try:
                            v = pat.path(self.session.path).vertices[self.session.corner]
                            pt_types.append(getattr(v, 'point_type', 'CORNER').title())
                        except (IndexError, ValueError):
                            pass
                type_str = pt_types[0] if (pt_types and len(set(pt_types)) == 1) else ('Mixed' if len(set(pt_types)) > 1 else 'Corner')
                pt_str = f"{points} point{'s' if points != 1 else ''} ({type_str})"
                return f"{pt_str} · Drag to move"
            return 'Click to select / Drag to box select'
        return {'SELECT': 'Drag points or pieces / Right-click for options',
                'RECTANGLE': 'Drag to draw a panel / Shift for a square',
                'ELLIPSE': 'Drag to draw an ellipse / Shift for a circle',
                'POLYGON': 'Click to draw / Click the first point or Enter to finish',
                'INTERNAL': 'Click to draw an internal path / Enter to finish',
                'PIN': 'Click a pattern point to pin or unpin',
                'DART': 'Pick two base points, then the dart tip',
                'TACK': 'Pick a pattern point, then a point on the body',
                'PLACE': 'Pick a piece, then a point on the body'}.get(self.tool, '')

    def sync_fabric_settings(self, preset_name):
        from .presets import resolve_preset
        vals = resolve_preset(preset_name, getattr(self.session.document, 'custom_presets', None))
        self._scene.dd_fabric_structural = vals['structural']
        self._scene.dd_fabric_shear = vals['shear']
        self._scene.dd_fabric_bending = vals['bending']
        self._scene.dd_fabric_density = vals['density']

    def apply_local_setting(self, key):
        if not self.minimal_ui:
            return super().apply_local_setting(key)
        if key == 'dd_weld_distance':
            self.weld_manual = True
        if key in {'dd_fabric_structural', 'dd_fabric_shear', 'dd_fabric_bending', 'dd_fabric_density'}:
            prop_map = {'dd_fabric_structural': 'structural', 'dd_fabric_shear': 'shear',
                        'dd_fabric_bending': 'bending', 'dd_fabric_density': 'density'}
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
        if key == 'PIECE_SIMULATION_MENU':
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
        elif key=='REGENERATE_VOLUMES':
            result=bpy.ops.devil_designer.arrangement_edit(action='REGENERATE')
            self.message='Body volumes regenerated; point edits reset.' if 'FINISHED' in result else 'Could not regenerate body volumes.'
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
        elif key == 'TOGGLE_MEASURE':
            scene.dd_measure_visible = not scene.dd_measure_visible
            if scene.dd_measure_visible:
                scene.dd_reference_visible = True
        elif key in {'STARTER_TEE', 'STARTER_TANK', 'STARTER_SKIRT'}:
            self.perform_action(key)
            self.card_kind = None
        elif key == 'DEMO_PANEL':
            self.perform_action('DEMO_PANEL')
            self.card_kind = None
        elif key == 'MENU_LIBRARY':
            self.show_card('LIBRARY', self.card_anchor)
        elif key == 'BODY_CHANGE':
            self.show_card('BODY', self.card_anchor)
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
            vals = dict(structural=scene.dd_fabric_structural, shear=scene.dd_fabric_shear,
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
                vals = dict(structural=scene.dd_fabric_structural, shear=scene.dd_fabric_shear,
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
        elif key == 'EDIT_ACTIONS':
            self.show_card('EDIT', self.card_anchor)
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
            tool_name = {'PATH': 'INTERNAL', 'DART': 'DART', 'KNIFE': 'KNIFE'}[sub]
            self.internal_tool = tool_name
            self.choose_tool(tool_name)
            self.card_kind = None
        elif key.startswith('SET_PIN_'):
            sub = key.removeprefix('SET_PIN_')
            tool_name = 'PIN' if sub == 'FABRIC' else 'TACK'
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
        elif key in {'WORKSPACE_FIT', 'INSP_FIT'}:
            self.fit()
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
        elif key == 'CURVE':
            self.perform_action('CURVE')
            self.card_kind = None
        elif key == 'SPLIT':
            self.perform_action('SPLIT')
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
        elif key in {'FLIP_H', 'FLIP_V', 'ROTATE_CW', 'ROTATE_CCW'}:
            self.perform_action(key)
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
        elif key.startswith('BODY_'):
            idx = int(key.removeprefix('BODY_'))
            if 0 <= idx < len(self.card_models):
                self.choose_body(self.card_models[idx], bpy.context)
            self.card_kind = None
        elif key.startswith('LOAD_'):
            idx = int(key.removeprefix('LOAD_'))
            if 0 <= idx < len(self.library_items):
                scene.dd_library_selected = idx
                self.perform_action('LIBRARY_LOAD')
            self.card_kind = None
        elif key == 'PAGE_BODY':
            self.card_page = (self.card_page + 1) % math.ceil(max(1, len(self.card_models)) / 8)
        elif key == 'PAGE_LIBRARY':
            self.card_page = (self.card_page + 1) % math.ceil(max(1, len(self.library_items)) / 8)
        elif key == 'LIBRARY_SAVE':
            self.design_action('LIBRARY_SAVE')
            self.card_kind = None
        elif key == 'RESET':
            self.workflow_action('RESET')
            self.card_kind = None
        elif key == 'NAME':
            self.numeric = dict(key='dd_library_name', text=scene.dd_library_name)
        elif key == 'REFERENCE_IMAGE':
            self.show_card('REFERENCE_IMAGE', self.card_anchor)
        elif key == 'KEEP_RETRY':
            self.perform_action('KEEP')
            self.card_kind = None

    def minimal_event(self, context, event):
        point = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        layout = self.canvas_layout
        if self.numeric:
            result = self.numeric_event(event)
            if result is not None:
                return result
        if self.setting_drag:
            return self.controls_event(context, event)
        card = next((c for c in self.visible_cards() if c[0].contains(*point)), None)
        press = event.value == 'PRESS'
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
        if press and event.type == 'ESC' and self.card_kind:
            self.card_kind = None
            return {'RUNNING_MODAL'}
        pointer_event = event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'MOUSEMOVE',
                                       'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
        if not pointer_event or not layout.panel.contains(*point):
            return None
        if card and self.card_kind=='SIMULATE' and event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
            delta=-1 if event.type=='WHEELUPMOUSE' else 1
            self.wear_over_offset=max(0,min(max(0,len(self.card_models)-5),self.wear_over_offset+delta))
            return {'RUNNING_MODAL'}
        if card and self.card_kind in {'BODY', 'LIBRARY'} and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            delta = -1 if event.type == 'WHEELUPMOUSE' else 1
            max_pages = math.ceil(len(self.card_models if self.card_kind == 'BODY' else self.library_items) / 8)
            if max_pages > 1:
                self.card_page = max(0, min(max_pages - 1, self.card_page + delta))
                return {'RUNNING_MODAL'}
        if self.card_kind and press and event.type == 'RIGHTMOUSE':
            self.card_kind = None
            return {'RUNNING_MODAL'}
        button = layout.button(*point)
        scale = layout.scale
        if button and not card and press and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:
            if self.card_kind:
                self.card_kind = None
                self.pending_simulation = False
            btn_rect = layout.buttons[button][0]
            if button == 'SELECT':
                self.choose_tool('SELECT')
            elif button in {'TOGGLE_SNAP', 'SNAP'}:
                self.snap = not self.snap
            elif button in {'TOGGLE_GUIDE', 'REFERENCE'}:
                self._scene.dd_reference_visible = not self._scene.dd_reference_visible
            elif button in {'TOGGLE_LENGTHS', 'LENGTHS'}:
                self._scene.dd_lengths_visible = not self._scene.dd_lengths_visible
            elif button == 'TOGGLE_FIT_MAP':
                self.fit_overlay.toggle()
            elif button in {'UNDO', 'REDO'}:
                self.perform_action(button)
            elif button == 'SEW':
                self.choose_tool('SEW')
            elif button == 'LIBRARY':
                self.show_card('LIBRARY', (btn_rect.x + btn_rect.w + 10 * scale, btn_rect.y + btn_rect.h / 2))
            elif button == 'CLOSE':
                if self.draft or self.gesture:
                    self.cancel_gesture()
                self.cleanup()
                return {'FINISHED'}
            elif button == 'RESTORE_CANVAS':
                self.restore_canvas()
                return {'RUNNING_MODAL'}
            elif button == 'DRAW':
                if event.type == 'RIGHTMOUSE' or self.tool in {'RECTANGLE', 'POLYGON', 'ELLIPSE'}:
                    self.show_card('DRAW_CHOOSER', (btn_rect.x + btn_rect.w + 10 * scale, btn_rect.y + btn_rect.h / 2))
                else:
                    self.choose_tool(getattr(self, 'draw_shape', 'RECTANGLE'))
            elif button == 'INTERNAL':
                if event.type == 'RIGHTMOUSE' or self.tool in {'INTERNAL', 'DART', 'KNIFE'}:
                    self.show_card('INTERNAL_CHOOSER', (btn_rect.x + btn_rect.w + 10 * scale, btn_rect.y + btn_rect.h / 2))
                else:
                    self.choose_tool(getattr(self, 'internal_tool', 'INTERNAL'))
            elif button == 'PIN':
                if event.type == 'RIGHTMOUSE' or self.tool in {'PIN', 'TACK'}:
                    self.show_card('PIN_CHOOSER', (btn_rect.x + btn_rect.w + 10 * scale, btn_rect.y + btn_rect.h / 2))
                else:
                    self.choose_tool(getattr(self, 'pin_tool', 'PIN'))
            elif button == 'GARMENT':
                self.show_card('GARMENT', (btn_rect.x, btn_rect.y - 10 * scale))
            elif button in {'SIMULATE', 'KEEP'}:
                self.automatic_defaults(finalize=button == 'KEEP')
                self.perform_action(button)
            elif button == 'KEEP_OPTIONS':
                self.show_card('KEEP', (btn_rect.x, btn_rect.y + 45 * scale))
            elif button == 'SIMULATE_OPTIONS':
                self.show_card('SIMULATE', (btn_rect.x, btn_rect.y + 45 * scale))
            else:
                self.minimal_action(button)
            return {'FINISHED'} if self._closed else {'RUNNING_MODAL'}
        if card:
            if press and event.type == 'LEFTMOUSE':
                if self.card_close_rect(card[0]).contains(*point):
                    self.card_kind = None
                    self.pending_simulation = False
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
                        if self.card_kind not in {'GARMENT_FABRIC', 'PIECE_FABRIC'}:
                            self.card_kind = None
                    elif key == 'PAIR_ACTIONS':
                        action1, action2 = row[1], row[2]
                        if point[0] < rect.x + rect.w / 2:
                            self.minimal_action(action1)
                        else:
                            self.minimal_action(action2)
                        self.card_kind = None
                    elif key == 'SLIDER':
                        label = row[1]
                        self.setting_drag = dict(key=label, value=getattr(self._scene, label), pointer=point, moved=False)
                        if label == 'dd_weld_distance':
                            scale = layout.scale
                            self.setting_drag['absolute'] = Rect(rect.x + 6 * scale, rect.y, rect.w - 12 * scale, rect.h)
                    elif key != 'INFO':
                        action = row[1] if key == 'MENU' else key
                        self.minimal_action(action)
                        if action not in {'BODY_CHANGE', 'GARMENT_FABRIC_MENU', 'PIECE_FABRIC_MENU', 'PIECE_DENSITY_MENU', 'PIECE_SIMULATION_MENU', 'EDIT_ACTIONS', 'SCROLL_WEAR_OVER'}:
                            self.card_kind = None
                    break
            return {'RUNNING_MODAL'}
        if self.gesture:
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
            pattern, corner = self.hit()
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
