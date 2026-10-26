"""Inspector controls inside the floating editor window."""
from dataclasses import dataclass
import math
from .canvas import Rect

@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    factor: float
    unit: str
    step: float
    low: float
    high: float
    integer: bool = False

    def format(self, value):
        value = value * self.factor
        return f"{int(value)}" if self.integer else f"{value:.8g}"

    def parse(self, text):
        try:
            value = float(text.replace(',', '.'))
        except ValueError as exc:
            raise ValueError('Enter a number for ' + self.label.lower() + '.') from exc
        value /= self.factor
        if not math.isfinite(value) or not self.low <= value <= self.high:
            raise ValueError(f'{self.label}: enter {self.low * self.factor:g} to {self.high * self.factor:g} {self.unit}.')
        if self.integer and not value.is_integer():
            raise ValueError(self.label + ' needs a whole number.')
        return int(value) if self.integer else value

SETTINGS = {
    spec.key: spec for spec in (
        Setting('dd_point_x', 'Point X', 100, 'cm', 1, -100, 100),
        Setting('dd_point_y', 'Point Y', 100, 'cm', 1, -100, 100),
        Setting('dd_width', 'Width', 100, 'cm', 1, .001, 100),
        Setting('dd_height', 'Height', 100, 'cm', 1, .001, 100),
        Setting('dd_segment_length', 'Segment length', 100, 'cm', .1, .0001, 100),
        Setting('dd_offset', 'Outline offset', 100, 'cm', .1, -1, 1),
        Setting('dd_wrap_radius', 'Wrap radius', 100, 'cm', .5, 0, 10),
        Setting('dd_sew_a0', 'Side A start', 100, '%', 1, 0, 1),
        Setting('dd_sew_a1', 'Side A end', 100, '%', 1, 0, 1),
        Setting('dd_sew_b0', 'Side B start', 100, '%', 1, 0, 1),
        Setting('dd_sew_b1', 'Side B end', 100, '%', 1, 0, 1),
        Setting('dd_reference_opacity', 'Silhouette opacity', 100, '%', 5, 0, .65),
        Setting('dd_reference_x', 'Reference X', 100, 'cm', 1, -100, 100),
        Setting('dd_reference_y', 'Reference Y', 100, 'cm', 1, -100, 100),
        Setting('dd_spacing', 'Mesh spacing', 100, 'cm', .1, .003, .2),
        Setting('dd_clearance', 'Body clearance', 100, 'cm', .5, .005, .3),
        Setting('dd_quality', 'Quality steps', 1, '', 1, 5, 40, True),
        Setting('dd_frames', 'Frames', 1, '', 10, 10, 1000, True),
        Setting('dd_weld_distance', 'Weld distance', 1000, 'mm', .5, .0001, .05),
        Setting('dd_thickness', 'Thickness', 1000, 'mm', .1, 0, .01),
    )
}

@dataclass
class Control:
    kind: str
    key: str
    rect: Rect
    label: str
    value_rect: Rect = None
    minus: Rect = None
    plus: Rect = None
    meta: str = ''
    sub: str = ''
    swatch: tuple = None
    btn_a: tuple = None
    btn_b: tuple = None

TABS = ('DESIGN', 'AVATAR', 'SEW', 'CLOTH', 'LIBRARY')

@dataclass(frozen=True)
class TextSetting:
    key: str
    label: str
    unit: str = ''
    def format(self, value):
        return value
    def parse(self, text):
        if not text.strip() or len(text) > 80:
            raise ValueError('Use a name between 1 and 80 characters.')
        return text.strip()

SETTINGS['dd_library_name'] = TextSetting('dd_library_name', 'Garment name')


class Inspector:
    def __init__(self, rect, scale, scroll, seams, tab='DESIGN', context=None):
        self.rect, self.scale, self.tab = rect, scale, tab
        self.controls = []
        self.context = context or {}
        s = scale
        self.tabs = {}
        for i, name in enumerate(TABS):
            self.tabs[name] = Rect(rect.x + 6 * s + i * (rect.w - 12 * s) / 5, rect.y + rect.h - 32 * s, (rect.w - 12 * s) / 5, 32 * s)
        self.content = Rect(rect.x, rect.y, rect.w, max(1.0, rect.h - 32 * s))

        ctx_sel = self.context.get('selection_kind')
        pat_name = self.context.get('pattern_name', 'Selected piece')
        pat_swatch = self.context.get('swatch', (0.74, 0.65, 0.91))
        pat_meta = self.context.get('meta', '4 points \u00b7 Cotton')

        if tab == 'DESIGN':
            rows = [
                ('title', '', 'PATTERN DESIGN'),
            ]
            if ctx_sel == 'PATTERN':
                rows += [
                    ('obj_h', pat_name, pat_meta, pat_swatch),
                    ('preset_chips', 'PRESET_CHIP', ''),
                    ('pair_buttons', 'DUPLICATE', 'MIRROR_SEW', 'Duplicate', 'Mirror Sew'),
                ]
            rows += [
                ('info', 'PATTERN_INFO', ''),
                ('number', 'dd_point_x', ''),
                ('number', 'dd_point_y', ''),
                ('button', 'POINT_APPLY', 'Apply / add point'),
                ('number', 'dd_width', ''),
                ('number', 'dd_height', ''),
                ('button', 'NUM_RECT', 'Create rectangle'),
                ('button', 'NUM_ELLIPSE', 'Create ellipse'),
                ('section', '', 'POINTS AND CURVES'),
                ('button', 'CURVE', 'Corner / curve  C'),
                ('button', 'SPLIT', 'Split segment  Q'),
                ('number', 'dd_segment_length', ''),
                ('button', 'SET_LENGTH', 'Apply exact length'),
                ('button', 'MERGE', 'Merge selected points  M'),
                ('number', 'dd_offset', ''),
                ('button', 'OFFSET', 'Offset outline copy'),
                ('section', '', 'SYMMETRY'),
                ('button', 'UNFOLD', 'Unfold across edge  U'),
                ('button', 'MIRROR_SEW', 'Mirror with seam  Shift U'),
                ('section', '', 'INTERNAL FEATURES'),
                ('toggle', 'dd_internal_mode', 'Draw internal shapes'),
                ('button', 'CUT', 'Cut selected internal path'),
                ('button', 'TRACE', 'Trace path as pattern'),
                ('hint', '', 'D: two base clicks, then dart apex.'),
                ('toggle', 'dd_lengths_visible', 'Live segment lengths'),
            ]
        elif tab == 'AVATAR':
            rows = [
                ('title', '', 'AVATAR AND PLACEMENT'),
                ('body', 'BODY', 'Avatar body'),
                ('button', 'BODY_USE', 'Use selected body'),
                ('button', 'PLACE', 'Click-place selected piece'),
                ('number', 'dd_wrap_radius', ''),
                ('button', 'WRAP', 'Wrap / unwrap selected piece'),
                ('hint', '', 'K: pins. T: pick fabric, then body.'),
                ('button', 'REMOVE_ANCHOR', 'Remove selected pin / tack'),
                ('section', '', 'BODY REFERENCE'),
                ('toggle', 'dd_reference_visible', 'Body silhouette'),
                ('cycle', 'REFERENCE_VIEW', 'Reference view'),
                ('number', 'dd_reference_opacity', ''),
                ('button', 'REFERENCE_ALIGN', 'Align torso to pattern'),
                ('button', 'REFERENCE_FRAME', 'Frame body'),
                ('button', 'REFERENCE_REFRESH', 'Refresh body'),
                ('number', 'dd_reference_x', ''),
                ('number', 'dd_reference_y', ''),
            ]
        elif tab == 'SEW':
            rows = [
                ('title', '', 'SEWING'),
                ('info', 'CHAIN_INFO', ''),
                ('toggle', 'dd_free_sewing', 'Free sewing: four clicks'),
                ('toggle', 'dd_sew_reverse', 'Reverse side B'),
                ('number', 'dd_sew_a0', ''),
                ('number', 'dd_sew_a1', ''),
                ('number', 'dd_sew_b0', ''),
                ('number', 'dd_sew_b1', ''),
                ('section', '', 'M:N EDGE CHAINS'),
                ('button', 'CHAIN_A', 'Pick chain A'),
                ('button', 'CHAIN_B', 'Pick chain B'),
                ('button', 'CHAIN_SEW', 'Sew selected chains'),
                ('button', 'CHAIN_CLEAR', 'Clear chain selection'),
                ('hint', '', 'Click edges in order. Enter: next side.'),
                ('section', '', 'SEWING PAIRS'),
            ]
            rows += [('seam', seam.id, str(i + 1)) for i, seam in enumerate(seams)]
            if not seams:
                rows += [('hint', '', 'Use Sew / J to pair edges.')]
        elif tab == 'CLOTH':
            rows = [
                ('title', '', 'FABRIC AND SIMULATION'),
                ('cycle', 'PRESET', 'Selected fabric'),
                ('info', 'PRESET_INFO', ''),
                ('number', 'dd_spacing', ''),
                ('number', 'dd_clearance', ''),
                ('number', 'dd_quality', ''),
                ('number', 'dd_frames', ''),
                ('toggle', 'dd_self_collision', 'Self collision'),
                ('toggle', 'dd_pin_top', 'Pin highest points'),
                ('section', '', 'FINALIZE'),
                ('number', 'dd_weld_distance', ''),
                ('number', 'dd_thickness', ''),
                ('section', '', 'TRY IT'),
                ('button', 'DEMO', 'Create sewing demo'),
            ]
        else:
            rows = [
                ('title', '', 'LOCAL GARMENT LIBRARY'),
                ('text', 'dd_library_name', 'Garment name'),
                ('button', 'LIBRARY_SAVE', 'Save editable garment'),
                ('section', '', 'LOAD AND REFIT'),
                ('info', 'LIBRARY_INFO', ''),
                ('button', 'LIBRARY_PREV', 'Previous garment'),
                ('button', 'LIBRARY_NEXT', 'Next garment'),
                ('toggle', 'dd_library_refit', 'Scale by body height'),
                ('button', 'LIBRARY_LOAD', 'Load onto selected avatar'),
                ('hint', '', 'Source, sewing, UVs and poses saved.'),
                ('hint', '', 'Avatar meshes are never bundled.'),
            ]

        heights = {
            'title': 32, 'body': 54, 'section': 32, 'number': 56, 'text': 56,
            'toggle': 32, 'button': 31, 'hint': 32, 'seam': 64, 'cycle': 32, 'info': 58,
            'obj_h': 46, 'field_pair': 56, 'pair_buttons': 38, 'preset_chips': 32
        }
        self.total = (sum(heights[r[0]] for r in rows) + 12) * s
        self.max_scroll = max(0, self.total - self.content.h)
        self.scroll = max(0, min(self.max_scroll, scroll))
        y = self.content.y + self.content.h + self.scroll - 8 * s

        for entry in rows:
            kind = entry[0]
            key = entry[1]
            label = entry[2] if len(entry) > 2 else ''
            h = heights[kind] * s
            y -= h
            r = Rect(rect.x + 12 * s, y, max(1.0, rect.w - 29 * s), h)
            item = Control(kind, key, r, label)

            if kind in {'number', 'text'}:
                item.label = SETTINGS[key].label
                item.value_rect = Rect(r.x, r.y + 4 * s, max(1.0, r.w - (52 * s if kind == 'number' else 0)), 25 * s)
                if kind == 'number':
                    item.minus = Rect(r.x + r.w - 49 * s, r.y + 4 * s, 23 * s, 25 * s)
                    item.plus = Rect(r.x + r.w - 23 * s, r.y + 4 * s, 23 * s, 25 * s)
            elif kind == 'body':
                item.value_rect = Rect(r.x, r.y + 4 * s, r.w, 27 * s)
            elif kind == 'obj_h':
                item.label = key
                item.meta = label
                item.swatch = entry[3] if len(entry) > 3 else (0.74, 0.65, 0.91)
            elif kind == 'preset_chips':
                presets = ['COTTON', 'SILK', 'DENIM', 'KNIT', 'LINEN']
                n = len(presets)
                chip_gap = 4 * s
                chip_w = (r.w - (n - 1) * chip_gap) / n
                item.chips = []
                for i, p_name in enumerate(presets):
                    chip_rect = Rect(r.x + i * (chip_w + chip_gap), r.y + 4 * s, chip_w, 24 * s)
                    item.chips.append((chip_rect, f'SET_PRESET_{p_name}', p_name.title()))
            elif kind == 'field_pair':
                item.key = key
                item.meta = entry[2]
                item.label = entry[3]
                item.sub = entry[4]
                half_w = (r.w - 8 * s) / 2
                item.value_rect = Rect(r.x, r.y + 4 * s, half_w, 36 * s)
                item.plus = Rect(r.x + half_w + 8 * s, r.y + 4 * s, half_w, 36 * s)
            elif kind == 'pair_buttons':
                key_a = key
                key_b = label
                label_a = entry[3]
                label_b = entry[4]
                half_w = (r.w - 8 * s) / 2
                item.btn_a = (Rect(r.x, r.y + 4 * s, half_w, 28 * s), key_a, label_a)
                item.btn_b = (Rect(r.x + half_w + 8 * s, r.y + 4 * s, half_w, 28 * s), key_b, label_b)

            self.controls.append(item)

        self.scrollbar = Rect(rect.x + rect.w - 7 * s, rect.y + 4 * s, 4 * s, max(1.0, self.content.h - 8 * s))
        track = self.scrollbar
        thumb_h = min(track.h, max(22 * s, track.h * min(1.0, self.content.h / max(1.0, self.total))))
        self.thumb = Rect(track.x, track.y + (track.h - thumb_h) * (1 - self.scroll / max(1.0, self.max_scroll)), track.w, thumb_h)

    def hit(self, point):
        if not self.rect.contains(*point):
            return None
        for name, r in self.tabs.items():
            if r.contains(*point):
                return 'TAB', name
        if not self.content.contains(*point):
            return None
        for item in self.controls:
            if not item.rect.contains(*point):
                continue
            if item.kind in {'number', 'text'}:
                if item.minus and item.minus.contains(*point):
                    return 'STEP_DOWN', item.key
                if item.plus and item.plus.contains(*point):
                    return 'STEP_UP', item.key
                if item.value_rect and item.value_rect.contains(*point):
                    return 'EDIT', item.key
            elif item.kind == 'body' and item.value_rect and item.value_rect.contains(*point):
                return 'BODY', item.key
            elif item.kind in {'button', 'cycle'}:
                return item.key, item.key
            elif item.kind == 'preset_chips':
                for chip_r, chip_act, _ in getattr(item, 'chips', []):
                    if chip_r.contains(*point):
                        return chip_act, chip_act
            elif item.kind == 'pair_buttons':
                if item.btn_a and item.btn_a[0].contains(*point):
                    return item.btn_a[1], item.btn_a[1]
                if item.btn_b and item.btn_b[0].contains(*point):
                    return item.btn_b[1], item.btn_b[1]
            elif item.kind == 'field_pair':
                if item.value_rect and item.value_rect.contains(*point):
                    return 'EDIT', item.key
                if item.plus and item.plus.contains(*point):
                    return 'EDIT', item.meta
            elif item.kind == 'toggle':
                return 'TOGGLE', item.key
            elif item.kind == 'seam':
                if point[0] > item.rect.x + item.rect.w - 25 * self.scale:
                    return 'SEAM_REMOVE', item.key
                if point[0] > item.rect.x + item.rect.w - 68 * self.scale:
                    return 'SEAM_FLIP', item.key
                return 'SEAM_SELECT', item.key
        return None


class BodyMenu:
    def __init__(self, panel, anchor, scale, objects, offset=0):
        self.objects = objects
        self.offset = max(0, min(max(0, len(objects) - 6), offset))
        self.entries = [(None, 'Clear body')] + [(obj, obj.name) for obj in objects[self.offset:self.offset + 6]]
        width = anchor.w
        height = (len(self.entries) * 30 + 8) * scale
        y = max(panel.y + 52 * scale, anchor.y - height)
        height = min(height, panel.y + panel.h - 54 * scale - y)
        self.rect = Rect(anchor.x, y, width, max(1.0, height))
        self.rows = []
        top = y + height - 4 * scale
        for obj, label in self.entries:
            top -= 30 * scale
            if top >= y:
                self.rows.append((Rect(anchor.x + 3 * scale, top, width - 6 * scale, 30 * scale), obj, label))
