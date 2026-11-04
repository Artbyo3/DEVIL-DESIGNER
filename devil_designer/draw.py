import math
import bpy
import time
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix
from .canvas import Rect, grid_step
from .core import area, triangulate, contains, Vertex, sample_path
from . import curves
from .controls import CONTROL_SETTINGS as SETTINGS
from .icons import icon_spans
from .construction import sew_reverse
from .minimal import SEAM_ACTIVE, SEAM_CONNECTED, SEAM_QUIET
from .avatar_field import EYEDROPPER, SEARCH, TEXT_OFFSET, TEXT_SIZE

from .ui_system import (
    BG_BASE, BG_ELEVATED, BG_WELL, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, ACCENT_BG, ACCENT_BORDER, ACCENT_HOVER, BORDER, BORDER_SUBTLE, RADIUS_WINDOW, RADIUS_BADGE, Tooltip, ComponentRenderer, SURFACE_FLOATING, SURFACE_OUTLINE, SELECTION, TEXT_ON_ACCENT, MinimalMetrics,
    NATIVE_FIELD, NATIVE_FIELD_HOVER, NATIVE_FIELD_EDIT, NATIVE_POPUP, NATIVE_ROW_ACTIVE, NATIVE_TEXT, NATIVE_PLACEHOLDER, NATIVE_SELECTION, NATIVE_CURSOR,
    TRANSFORM_FRAME, TRANSFORM_HANDLE, TRANSFORM_HANDLE_HOVER, TRANSFORM_PIVOT, TRANSFORM_PREVIEW_OK,
    TRANSFORM_PREVIEW_WARN, TRANSFORM_PREVIEW_BLOCK, TRANSFORM_HANDLE_SIZE, TRANSFORM_KNOB_RADIUS, TRANSFORM_HIT_RADIUS
)

BG = BG_BASE
SHELL = BG_BASE
FIELD_BG = BG_WELL
ELEVATED = BG_ELEVATED
BORDER = BORDER
BORDER_SUBTLE = BORDER_SUBTLE
TEXT = TEXT_PRIMARY
TEXT_SUB = TEXT_SECONDARY
MUTED = TEXT_MUTED
ACCENT = ACCENT
ACCENT_BG = ACCENT_BG
ACCENT_BORDER = ACCENT_BORDER


SEAM_PAIR_TONES = [
    (0.42, 0.66, 0.65),
    (0.68, 0.58, 0.44),
    (0.56, 0.54, 0.72),
    (0.46, 0.66, 0.54),
    (0.68, 0.50, 0.56),
    (0.48, 0.62, 0.74),
]
SEAM_LINK_STEPS = {SEAM_QUIET: (), SEAM_CONNECTED: (2,), SEAM_ACTIVE: (0, 1, 2, 3, 4)}


class Renderer:
    def __init__(self):
        self.shader = None
        self.seam_levels = {}
        self.line_shader = None
        self.s = 1
        self.offset = (0, 0)
        self.triangle_cache = {}
        self.icon_batches = {}
        self.reference_batch = None
        self.reference_revision = -1

    def triangles(self, points, color, indices=None):
        if not points:
            return
        if self.shader is None:
            self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        batch = batch_for_shader(self.shader, 'TRIS', {"pos": points}, indices=indices)
        self.shader.bind()
        self.shader.uniform_float("color", color)
        batch.draw(self.shader)

    def rect(self, r, color):
        x = round(r.x)
        y = round(r.y)
        w = round(r.w)
        h = round(r.h)
        self.triangles([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                       color, [(0, 1, 2), (0, 2, 3)])

    def round_rect(self, r, color, radius=8):
        x = round(r.x)
        y = round(r.y)
        w = round(r.w)
        h = round(r.h)
        rad = min(radius * self.s, w / 2, h / 2)
        if rad <= 1.5:
            self.rect(Rect(x, y, w, h), color)
            return
        pts = [
            (x + rad, y), (x + w - rad, y), (x + w - rad, y + h), (x + rad, y + h),
            (x, y + rad), (x + rad, y + rad), (x + rad, y + h - rad), (x, y + h - rad),
            (x + w - rad, y + rad), (x + w, y + rad), (x + w, y + h - rad), (x + w - rad, y + h - rad),
        ]
        indices = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (8, 9, 10), (8, 10, 11)]
        corners = [
            (x + rad, y + rad, math.pi, 1.5 * math.pi),
            (x + w - rad, y + rad, 1.5 * math.pi, 2 * math.pi),
            (x + w - rad, y + h - rad, 0, 0.5 * math.pi),
            (x + rad, y + h - rad, 0.5 * math.pi, math.pi),
        ]
        n = max(6, min(12, int(rad)))
        for cx, cy, a0, a1 in corners:
            pts.append((cx, cy))
            c_idx = len(pts) - 1
            for i in range(n + 1):
                angle = a0 + (a1 - a0) * i / n
                pts.append((cx + math.cos(angle) * rad, cy + math.sin(angle) * rad))
                if i > 0:
                    indices.append((c_idx, len(pts) - 2, len(pts) - 1))
        self.triangles(pts, color, indices)

    def round_rect_outline(self, r, color, radius=8, width=1):
        x = round(r.x)
        y = round(r.y)
        w = round(r.w)
        h = round(r.h)
        rad = min(radius * self.s, w / 2, h / 2)
        line_w = (1.0 / max(1.0, self.s)) if width <= 1.2 else width
        if width <= 1.2:
            x_out = x + 0.5
            y_out = y + 0.5
            w_out = max(0.0, w - 1.0)
            h_out = max(0.0, h - 1.0)
            rad_out = max(0.0, rad - 0.5)
        else:
            x_out, y_out, w_out, h_out, rad_out = x, y, w, h, rad

        if rad_out <= 1.0:
            self.lines([(x_out, y_out), (x_out + w_out, y_out),
                        (x_out + w_out, y_out + h_out), (x_out, y_out + h_out),
                        (x_out, y_out)],
                       color, line_w, strip=True)
            return

        corners = [
            (x_out + rad_out, y_out + rad_out, math.pi, 1.5 * math.pi),
            (x_out + w_out - rad_out, y_out + rad_out, 1.5 * math.pi, 2 * math.pi),
            (x_out + w_out - rad_out, y_out + h_out - rad_out, 0, 0.5 * math.pi),
            (x_out + rad_out, y_out + h_out - rad_out, 0.5 * math.pi, math.pi),
        ]
        pts = []
        n = max(6, min(12, int(rad_out)))
        for cx, cy, a0, a1 in corners:
            for i in range(n + 1):
                angle = a0 + (a1 - a0) * i / n
                pts.append((cx + math.cos(angle) * rad_out, cy + math.sin(angle) * rad_out))
        self.lines(pts + pts[:1], color, line_w, strip=True)

    def lines(self, points, color, width=1, strip=False):
        if len(points) < 2:
            return
        if self.line_shader is None:
            self.line_shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        sh = self.line_shader
        is_1px = (width * self.s <= 1.2)
        if is_1px and len(points) == 2:
            p0, p1 = points
            if abs(p0[1] - p1[1]) < 1e-4:
                y = math.floor(p0[1]) + 0.5
                points = [(round(p0[0]), y), (round(p1[0]), y)]
            elif abs(p0[0] - p1[0]) < 1e-4:
                x = math.floor(p0[0]) + 0.5
                points = [(x, round(p0[1])), (x, round(p1[1]))]
        batch = batch_for_shader(sh, 'LINE_STRIP' if strip else 'LINES', {"pos": points})
        sh.bind()
        sh.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        sh.uniform_float("lineWidth", width * self.s)
        sh.uniform_float("color", color)
        batch.draw(sh)

    def dot(self, point, radius, color):
        x, y = round(point[0]), round(point[1])
        n = 16
        pts = [(x, y)] + [(x + math.cos(i * math.tau / n) * radius * self.s,
                           y + math.sin(i * math.tau / n) * radius * self.s) for i in range(n)]
        self.triangles(pts, color, [(0, i + 1, (i + 1) % n + 1) for i in range(n)])

    def text(self, x, y, label, size=11, color=TEXT, center=False, max_width=None):
        blf.size(0, size * self.s)
        if max_width is not None:
            original = label
            while label and blf.dimensions(0, label)[0] > max_width:
                original = original[:-1]
                label = original + "..." if original else ""
        if center:
            x -= blf.dimensions(0, label)[0] / 2
        blf.color(0, *color)
        blf.position(0, round(x), round(y), 0)
        blf.draw(0, label)

    def clip(self, r):
        x, y, w, h = round(r.x), round(r.y), round(r.w), round(r.h)
        gpu.state.scissor_set(int(self.offset[0] + x), int(self.offset[1] + y), max(1, int(w)), max(1, int(h)))
        blf.enable(0, blf.CLIPPING)
        blf.clipping(0, x, y, x + w, y + h)

    def draw_icon(self, name, cx, cy, size, color):
        spans = icon_spans(name)
        px_size = max(1, round(size * self.s))
        left_px = round(cx - px_size / 2.0)
        bottom_px = round(cy - px_size / 2.0)
        snap_cx = left_px + px_size / 2.0
        snap_cy = bottom_px + px_size / 2.0
        if spans is not None:
            if self.shader is None:
                self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            if name not in self.icon_batches:
                batches = []
                for level in range(1, 9):
                    vertices = []
                    for column, row, width, opacity in spans:
                        if opacity != level:
                            continue
                        left, bottom = (column - 32) / 64, (row - 32) / 64
                        right, top = left + width / 64, bottom + 1 / 64
                        vertices.extend([(left, bottom), (right, bottom), (right, top),
                                         (left, bottom), (right, top), (left, top)])
                    if vertices:
                        batches.append((level, batch_for_shader(self.shader, 'TRIS', {'pos': vertices})))
                self.icon_batches[name] = batches
            with gpu.matrix.push_pop():
                gpu.matrix.translate((snap_cx, snap_cy, 0))
                gpu.matrix.scale((px_size, px_size, 1))
                self.shader.bind()
                for level, batch in self.icon_batches[name]:
                    self.shader.uniform_float('color', (*color[:3], color[3] * level / 8))
                    batch.draw(self.shader)
            return
        s = px_size
        cx, cy = snap_cx, snap_cy
        if name == 'SHAPE':
            pts = [(cx + math.cos(i * math.tau / 16) * 0.35 * s,
                    cy + math.sin(i * math.tau / 16) * 0.35 * s) for i in range(17)]
            self.lines(pts, color, 1.4, strip=True)
            self.lines([(cx - 0.22 * s, cy), (cx + 0.22 * s, cy)], color, 1.2)
            self.lines([(cx, cy - 0.22 * s), (cx, cy + 0.22 * s)], color, 1.2)

    def avatar_field(self, ed, control, label, metrics):
        field = ed.avatar_field
        scale = self.s
        box = field.box(control)
        editing = field.mode == SEARCH
        text_y = box.y + (box.h - 8 * scale) / 2
        blf.size(0, TEXT_SIZE * scale)
        self.text(box.x - 8 * scale - blf.dimensions(0, label)[0], text_y, label, TEXT_SIZE, NATIVE_TEXT)
        hover = box.contains(*ed.pointer)
        self.round_rect(box, NATIVE_FIELD_EDIT if editing else NATIVE_FIELD_HOVER if hover else NATIVE_FIELD, radius=metrics.text)
        self.draw_icon('OBJECT_DATA', box.x + 11 * scale, box.y + box.h / 2, 14, NATIVE_TEXT)
        extra = field.extra_rect(box)
        self.draw_icon('CLOSE' if field.avatar else 'EYEDROPPER', extra.x + extra.w / 2, extra.y + extra.h / 2, 11 if field.avatar else 14, NATIVE_TEXT)
        left = box.x + TEXT_OFFSET * scale
        room = extra.x - left
        value = field.text if editing else field.avatar.name if field.avatar else ''
        ink = NATIVE_TEXT if value else NATIVE_PLACEHOLDER
        if not editing:
            self.text(left, text_y, value or label, TEXT_SIZE, ink, max_width=room)
            return
        blf.size(0, TEXT_SIZE * scale)
        start, end = field.selection()
        cursor_x = blf.dimensions(0, value[:field.cursor])[0]
        shift = max(0, cursor_x - room + 2 * scale)
        self.clip(Rect(left, box.y, room, box.h))
        if start != end:
            low = left - shift + blf.dimensions(0, value[:start])[0]
            self.rect(Rect(low, box.y + 1 * scale, blf.dimensions(0, value[start:end])[0], box.h - 2 * scale), NATIVE_SELECTION)
        self.text(left - shift, text_y, value or label, TEXT_SIZE, ink)
        self.rect(Rect(left - shift + cursor_x, box.y + 1 * scale, max(1, 1.5 * scale), box.h - 2 * scale), NATIVE_CURSOR)
        self.clip(ed.canvas_layout.panel)

    def avatar_overlay(self, ed, metrics):
        field = ed.avatar_field
        scale = self.s
        if field.mode == EYEDROPPER and field.sample is not None:
            blf.size(0, TEXT_SIZE * scale)
            name = field.sample.name
            tip = Rect(ed.pointer[0] + 14 * scale, ed.pointer[1] - 22 * scale, blf.dimensions(0, name)[0] + 12 * scale, 18 * scale)
            self.clip(Rect(0, 0, ed._region.width, ed._region.height))
            self.round_rect(tip, NATIVE_POPUP, radius=metrics.tooltip)
            self.text(tip.x + 6 * scale, tip.y + 5 * scale, name, TEXT_SIZE, NATIVE_TEXT)
            self.clip(ed.canvas_layout.panel)
        control = field.control() if field.mode == SEARCH else None
        if control is None:
            return
        popup, rows = field.popup(field.box(control))
        self.round_rect(popup, NATIVE_POPUP, radius=metrics.menu_back)
        for index, obj in enumerate(field.results[field.offset:field.offset + rows]):
            row = field.row_rect(popup, index)
            if field.offset + index == field.active:
                self.round_rect(row, NATIVE_ROW_ACTIVE, radius=metrics.menu_item)
            self.draw_icon('OUTLINER_OB_MESH', row.x + 9 * scale, row.y + row.h / 2, 14, NATIVE_TEXT)
            self.text(popup.x + 36 * scale, row.y + 5 * scale, obj.name, TEXT_SIZE, NATIVE_TEXT, max_width=popup.w - 42 * scale)
        if not field.results:
            self.text(popup.x + 7 * scale, field.row_rect(popup, 0).y + 5 * scale, 'No results found', TEXT_SIZE, NATIVE_TEXT)
        middle = popup.x + popup.w / 2
        if field.offset > 0:
            self.draw_icon('CHEVRON', middle, popup.y + popup.h - 6 * scale, 10, NATIVE_TEXT)
        if field.offset + rows < len(field.results):
            self.draw_icon('DOWN', middle, popup.y + 6 * scale, 10, NATIVE_TEXT)

    def fill_pattern(self, identity, world, screen, color, holes=(), view=None, canvas=None):
        key = (identity, tuple(world), tuple(tuple(loop) for loop in holes))
        if key not in self.triangle_cache:
            try:
                if holes:
                    from mathutils import Vector
                    from mathutils.geometry import delaunay_2d_cdt
                    coords = list(world)
                    edges = []
                    outer = list(range(len(coords)))
                    for loop in [world] + list(holes):
                        start = 0 if loop is world else len(coords)
                        if loop is not world:
                            coords.extend(loop)
                        edges.extend((start + i, start + (i + 1) % len(loop)) for i in range(len(loop)))
                    if area(world) < 0:
                        outer.reverse()
                    out, _, faces, _, _, _ = delaunay_2d_cdt([Vector(v) for v in coords], edges, [outer], 1, 1e-7, False)
                    points = [tuple(v) for v in out]
                    faces = [tuple(f) for f in faces if not any(contains(tuple(sum(points[i][j] for i in f) / len(f) for j in (0, 1)), hole) for hole in holes)]
                    self.triangle_cache[key] = (points, faces)
                else:
                    self.triangle_cache[key] = (list(world), triangulate(world))
            except ValueError:
                return False
        points, indices = self.triangle_cache[key]
        projected = [view.screen(pt, canvas) for pt in points] if view else screen
        self.triangles(projected, color, indices)
        return True

    def draw_shaping_strip(self, ed):
        rects = getattr(ed, 'shaping_strip_rects', None) or {}
        bounds = rects.get('STRIP_BOUNDS')
        if not bounds:
            return
        scale = min(self.s, bounds.w / 280)
        self.round_rect(bounds, SURFACE_FLOATING, radius=6)
        self.round_rect_outline(bounds, SURFACE_OUTLINE, radius=6)
        mode_rect = rects.get('MODE_TOGGLE')
        if mode_rect:
            mode = getattr(ed, 'shape_mode', 'PULL')
            hover = mode_rect.contains(*ed.pointer)
            self.round_rect(mode_rect, ACCENT if mode == 'PULL' else ELEVATED if hover else BG_WELL, radius=4)
            self.text(mode_rect.x + mode_rect.w / 2, mode_rect.y + 8 * scale, mode.title(), 11, TEXT_ON_ACCENT if mode == 'PULL' else TEXT, True)
        rm_rect = rects.get('RADIUS_MINUS')
        if rm_rect:
            hover = rm_rect.contains(*ed.pointer)
            self.round_rect(rm_rect, ELEVATED if hover else BG_WELL, radius=4)
            self.text(rm_rect.x + rm_rect.w / 2, rm_rect.y + 7 * scale, '-', 13, TEXT, True)
        rv_rect = rects.get('RADIUS_VALUE')
        if rv_rect and ed.shaping is not None:
            r_mm = ed.shaping.radius * 1000
            self.text(rv_rect.x + rv_rect.w / 2, rv_rect.y + 8 * scale, f'{r_mm:.0f} mm', 10, TEXT_SUB, True)
        rp_rect = rects.get('RADIUS_PLUS')
        if rp_rect:
            hover = rp_rect.contains(*ed.pointer)
            self.round_rect(rp_rect, ELEVATED if hover else BG_WELL, radius=4)
            self.text(rp_rect.x + rp_rect.w / 2, rp_rect.y + 7 * scale, '+', 13, TEXT, True)
        rst_rect = rects.get('RESET')
        if rst_rect:
            hover = rst_rect.contains(*ed.pointer)
            self.round_rect(rst_rect, ELEVATED if hover else BG_WELL, radius=4)
            self.text(rst_rect.x + rst_rect.w / 2, rst_rect.y + 8 * scale, 'Reset', 10, TEXT, True)
        self.text(bounds.x + 4 * scale, bounds.y - 18 * scale, ed.message, 10, TEXT,
                  max_width=bounds.w - 8 * scale)

    def draw(self, ed):
        self.s = s = ed.canvas_layout.scale
        l, view = ed.canvas_layout, ed.view
        metrics = l.metrics
        p, c = l.panel, l.canvas
        blend = gpu.state.blend_get()
        depth = gpu.state.depth_test_get()
        scissor = gpu.state.scissor_get()
        viewport = gpu.state.viewport_get()
        self.offset = viewport[:2]
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        gpu.state.scissor_test_set(True)

        try:
            self.clip(p)
            self.round_rect(p, SHELL, radius=metrics.box if metrics else RADIUS_WINDOW)
            self.round_rect_outline(p, BORDER, radius=metrics.box if metrics else RADIUS_WINDOW, width=1.0)

            self.round_rect(c, BG, radius=0 if metrics else 8)
            self.clip(c)
            try:
                from . import tracing
                tracing.draw_reference(ed, self)
                self.body_reference(ed)
                self.grid(view, c)

                if not ed.session.document.patterns and not ed.draft and not ed.card_kind:
                    self.text(c.x + c.w / 2, c.y + c.h / 2 + 12 * s, 'Drag to draw your first panel', 17, TEXT, True, max_width=c.w - 32 * s)
                    self.text(c.x + c.w / 2, c.y + c.h / 2 - 14 * s, 'Then pick Sew, pair the edges, and Simulate.', 11, TEXT_SUB, True, max_width=c.w - 32 * s)

                ed.measurement_rects = []
                from .linked_editing import pair_for
                hovered_edge = ed.design_hit_edge() if ed.tool == 'SELECT' and not ed.gesture and not ed.card_kind else None
                twin_pairs = list(getattr(ed.session.document, 'linked_pairs', []))
                piece_labels=[]
                pointer_world=view.world(ed.pointer,c)
                hovered_piece=next((pattern for pattern in reversed(ed.session.document.patterns) if pattern.contains(pointer_world)),None) if not ed.card_kind and not ed.gesture else None
                ed.twin_tethers=[]
                for pair in twin_pairs:
                    if not pair['enabled']:continue
                    outlines=[ed.preview_pattern(ed.session.document.find(identity)).outline() for identity in pair['members']]
                    centers=[view.screen(((min(point[0] for point in outline)+max(point[0] for point in outline))/2,
                                          (min(point[1] for point in outline)+max(point[1] for point in outline))/2),c) for outline in outlines]
                    ed.twin_tethers.append(centers)
                    self.lines(centers,(*ACCENT[:3],.25),1/max(1,s))
                for index, source in enumerate(ed.session.document.patterns):
                    pat = ed.preview_pattern(source)
                    selected = (pat.id in ed.session.selected_patterns) if ed.session.selected_patterns else (ed.session.selected == pat.id)
                    pair = pair_for(ed.session.document, source.id)
                    is_twin = bool(pair and pair.get('enabled'))
                    partner_selected = False
                    if is_twin and not selected:
                        partner_id = pair['members'][1] if pair['members'][0] == source.id else pair['members'][0]
                        partner_selected = (partner_id in ed.session.selected_patterns) if ed.session.selected_patterns else (ed.session.selected == partner_id)
                    world = pat.outline()
                    outline = [view.screen(point, c) for point in world]
                    holes = [path.outline() for path in pat.paths if path.role == 'HOLE']
                    color = (.70, .76, .82)
                    opacity = .10 if selected else .055
                    self.fill_pattern(pat.id, world, outline, (*color, opacity), holes, view, c)

                    for path, nodes, closed, role in pat.loops():
                        points = world if path == 'OUTER' else pat.path(path).outline()
                        screen = [view.screen(point, c) for point in points]
                        active = selected and ed.session.path == path
                        line_color = ACCENT if active else (0.9, 0.48, 0.48, 0.9) if role in {'HOLE', 'SLIT'} else (*ACCENT[:3], 0.55) if (partner_selected and path == 'OUTER') else (*color, 0.95)
                        self.lines(screen + (screen[:1] if closed else []), line_color, 2.2 if (active or selected) else 1.5, True)
                        fold = next((feature for feature in pat.features if feature.get('type') == 'FOLD' and nodes and feature.get('apex') == nodes[0].id), None)
                        if fold and len(screen) >= 2:
                            start, end = screen[0], screen[-1]
                            length = math.dist(start, end)
                            if length > 1:
                                sign = 1 if fold.get('angle', 0) > 0 else -1
                                normal = (-(end[1]-start[1])/length*sign, (end[0]-start[0])/length*sign)
                                middle = ((start[0]+end[0])/2, (start[1]+end[1])/2)
                                tip = (middle[0]+normal[0]*18*s, middle[1]+normal[1]*18*s)
                                self.lines([middle, tip], ACCENT, 2)
                                for side in (-1, 1):
                                    self.lines([tip, (tip[0]-normal[0]*6*s-normal[1]*side*4*s, tip[1]-normal[1]*6*s+normal[0]*side*4*s)], ACCENT, 2)
                                label = ('Mountain' if sign > 0 else 'Valley') + f" {abs(fold.get('angle', 0)):g} deg"
                                self.text(tip[0]+5*s, tip[1]+5*s, label, 9, TEXT)

                        if hovered_edge and hovered_edge.pattern == source.id and hovered_edge.path == path and hovered_edge != ed.session.segment:
                            hv_a = next((v for v in nodes if v.id == hovered_edge.start), None)
                            hv_b = next((v for v in nodes if v.id == hovered_edge.end), None)
                            if hv_a and hv_b:
                                hv_ctrl = curves.controls(hv_a, hv_b)
                                hv_screen = [view.screen(curves.evaluate(hv_ctrl, t / 16.0), c) for t in range(17)]
                                self.lines(hv_screen, (*ACCENT[:3], 0.85), 2.4, True)

                        for edge in ed.session.selected_edges:
                            if edge.pattern == source.id and edge.path == path:
                                ea = next((v for v in nodes if v.id == edge.start), None)
                                eb = next((v for v in nodes if v.id == edge.end), None)
                                if ea and eb:
                                    ectrl = curves.controls(ea, eb)
                                    escr = [view.screen(curves.evaluate(ectrl, t / 16.0), c) for t in range(17)]
                                    self.lines(escr, SELECTION, 3.6, True)
                                    self.dot(escr[0], 4.6, SELECTION)
                                    self.dot(escr[-1], 4.6, SELECTION)

                        if ed.session.segment and ed.session.segment.pattern == source.id and ed.session.segment.path == path and ed.session.segment not in ed.session.selected_edges:
                            seg = ed.session.segment
                            v_start = next((v for v in nodes if v.id == seg.start), None)
                            v_end = next((v for v in nodes if v.id == seg.end), None)
                            if v_start and v_end:
                                ctrl = curves.controls(v_start, v_end)
                                seg_screen = [view.screen(curves.evaluate(ctrl, t / 16.0), c) for t in range(17)]
                                self.lines(seg_screen, SELECTION, 3.6, True)
                                self.dot(seg_screen[0], 4.6, SELECTION)
                                self.dot(seg_screen[-1], 4.6, SELECTION)

                        if ed.gesture and ed.gesture.get('mode') in {'MOVE', 'TRANSFORM'}:
                            for edge in ed.session.document.edges(source.id, path):
                                if edge not in ed.session.selected_edges:
                                    ea = next((v for v in nodes if v.id == edge.start), None)
                                    eb = next((v for v in nodes if v.id == edge.end), None)
                                    if ea and eb:
                                        ea_sel = (source.id, path, nodes.index(ea)) in ed.session.selected_points
                                        eb_sel = (source.id, path, nodes.index(eb)) in ed.session.selected_points
                                        if ea_sel != eb_sel:
                                            nctrl = curves.controls(ea, eb)
                                            nscr = [view.screen(curves.evaluate(nctrl, t / 16.0), c) for t in range(17)]
                                            self.lines(nscr, (*ACCENT[:3], 0.75), 2.2, True)

                        for i, v in enumerate(nodes):
                            point = view.screen((v.x, v.y), c)
                            chosen = (source.id, path, i) in ed.session.selected_points or (active and (ed.session.corner == i or i in ed.session.point_selection))
                            edge_endpoint = bool(ed.session.segment and ed.session.segment.pattern == source.id and ed.session.segment.path == path and v.id in (ed.session.segment.start, ed.session.segment.end))
                            show_handles = (chosen or edge_endpoint) and getattr(v, 'point_type', 'CORNER') != 'AUTO'
                            if chosen:
                                ring = [(point[0] + math.cos(step * math.tau / 16) * 7.5 * s,
                                         point[1] + math.sin(step * math.tau / 16) * 7.5 * s) for step in range(17)]
                                self.lines(ring, SELECTION, 1.4, True)
                                self.lines([(point[0] - 11 * s, point[1]), (point[0] - 7.5 * s, point[1])], SELECTION, 1.6)
                                self.lines([(point[0] + 7.5 * s, point[1]), (point[0] + 11 * s, point[1])], SELECTION, 1.6)
                                self.lines([(point[0], point[1] - 11 * s), (point[0], point[1] - 7.5 * s)], SELECTION, 1.6)
                                self.lines([(point[0], point[1] + 7.5 * s), (point[0], point[1] + 11 * s)], SELECTION, 1.6)
                                self.dot(point, 4.2, ACCENT)
                            elif selected:
                                self.dot(point, 3.6, (*color, 1))
                            if show_handles:
                                for name in ('incoming', 'outgoing'):
                                    handle = getattr(v, name)
                                    if handle is not None:
                                        end = view.screen(curves.add((v.x, v.y), handle), c)
                                        self.lines([point, end], (0.65, 0.75, 0.8, 0.75), 1.2)
                                        self.dot(end, 4, (0.98, 0.73, 0.32, 1))

                        if selected and ed._scene.dd_lengths_visible:
                            for edge in ed.session.document.edges(source.id, path):
                                a = next((v for v in nodes if v.id == edge.start), None)
                                b = next((v for v in nodes if v.id == edge.end), None)
                                if not (a and b):
                                    continue
                                control = curves.controls(a, b)
                                if (edge != ed.session.segment and
                                        math.dist(view.screen((a.x, a.y), c), view.screen((b.x, b.y), c)) < 80 * s):
                                    continue
                                mid = view.screen(curves.at_length(control, 0.5), c)
                                length_cm = curves.length(control) * 100
                                dim_str = f"{length_cm:.1f} cm"
                                blf.size(0, 10 * s)
                                dw, dh = blf.dimensions(0, dim_str)
                                dim_r = Rect(mid[0] + 4 * s, mid[1] + 4 * s, dw + 6 * s, dh + 4 * s)
                                ed.measurement_rects.append(dim_r)
                                self.round_rect(dim_r, (0.08, 0.10, 0.13, 0.88), radius=metrics.box if metrics else RADIUS_BADGE)
                                self.round_rect_outline(dim_r, BORDER_SUBTLE, radius=metrics.box if metrics else RADIUS_BADGE, width=0.8)
                                self.text(dim_r.x + 3 * s, dim_r.y + 2 * s, dim_str, 10, TEXT_SUB)

                    xs, ys = [pt[0] for pt in outline], [pt[1] for pt in outline]
                    label_txt = pat.name
                    from .piece_states import label
                    state_label = label(pat)
                    if state_label:
                        label_txt += ' · ' + state_label
                    show_twin=is_twin and (selected or partner_selected or hovered_piece and hovered_piece.id in pair['members'])
                    if show_twin:
                        p_idx = next((idx for idx, lp in enumerate(twin_pairs) if lp is pair), 0)
                        label_txt+=f" | Twin {chr(65+(p_idx%26))}"
                    piece_labels.append((min(xs),max(xs),min(ys),max(ys),label_txt,selected,source.id,bool(show_twin)))

                self.piece_labels(ed,piece_labels)

                for anchor in ed.session.document.anchors:
                    point = view.screen((anchor.x, anchor.y), c)
                    color = (1, 0.42, 0.3, 1) if anchor.kind == 'PIN' else (1, 0.78, 0.3, 1)
                    self.dot(point, 6 if ed.selected_anchor == anchor.id else 4.5, color)
                    self.lines([(point[0] - 3 * s, point[1] - 3 * s), (point[0] + 3 * s, point[1] + 3 * s),
                                (point[0] - 3 * s, point[1] + 3 * s), (point[0] + 3 * s, point[1] - 3 * s)], BG)

                self.seams(ed)

                if ed.gesture and ed.gesture.get('mode') == 'BOX_SELECT':
                    p0 = ed.gesture['start']
                    p1 = ed.pointer
                    rx, ry = min(p0[0], p1[0]), min(p0[1], p1[1])
                    rw, rh = abs(p1[0] - p0[0]), abs(p1[1] - p0[1])
                    if rw > 1 and rh > 1:
                        box_rect = Rect(rx, ry, rw, rh)
                        self.round_rect(box_rect, (*ACCENT[:3], 0.12), radius=0 if metrics else 3)
                        self.round_rect_outline(box_rect, (*ACCENT[:3], 0.65), radius=0 if metrics else 3, width=1.0)

                if ed.gesture and ed.gesture.get('mode') == 'LASSO_SELECT':
                    scr_pts = ed.gesture.get('screen_points', [])
                    if len(scr_pts) >= 2:
                        self.lines(scr_pts + [ed.pointer], ACCENT, 1.5, True)

                if ed.gesture and ed.gesture.get('mode') == 'SET_PIVOT':
                    chosen = ed.gesture.get('chosen')
                    if chosen:
                        pt = view.screen(chosen, c)
                        self.dot(pt, 5 * s, SELECTION)
                        ring = [(pt[0] + math.cos(step * math.tau / 16) * 8 * s,
                                 pt[1] + math.sin(step * math.tau / 16) * 8 * s) for step in range(17)]
                        self.lines(ring, SELECTION, 1.5, True)
                        lbl = ed.gesture.get('label', 'Pivot')
                        self.text(pt[0] + 10 * s, pt[1] + 5 * s, lbl, 10, TEXT_PRIMARY)

                gesture = ed.gesture
                preview_doc = gesture.get('candidate') if gesture and gesture.get('mode') in {'MOVE', 'TRANSFORM'} else None
                preflight = (gesture.get('preflight') or {}) if preview_doc is not None else {}
                if preview_doc is not None:
                    status = preflight.get('status', 'OK')
                    tone = TRANSFORM_PREVIEW_BLOCK if status == 'BLOCK' else TRANSFORM_PREVIEW_WARN if status == 'WARN' else TRANSFORM_PREVIEW_OK
                    for pid in {key[0] for key in ed.session.resolve_selection()[0]}:
                        ghost = preview_doc.find(pid)
                        if ghost is None:
                            continue
                        for _, nodes, closed, _ in ghost.loops():
                            ghost_points = [view.screen(point, c) for point in sample_path(nodes, closed)]
                            if closed and ghost_points:
                                ghost_points.append(ghost_points[0])
                            self.lines(ghost_points, tone, 2.0, True)

                frame = ed.transform_frame()
                hover = ed.transform_frame_hit(frame) if frame is not None else None
                if frame is not None:
                    self.round_rect_outline(frame['rect'], TRANSFORM_FRAME, radius=0, width=1.0)
                    self.lines([frame['stem'], frame['knob']], TRANSFORM_FRAME, 1.0)
                    half = TRANSFORM_HANDLE_SIZE * s / 2
                    for corner in frame['corners']:
                        hot = hover == 'SCALE' and math.dist(ed.pointer, corner) <= TRANSFORM_HIT_RADIUS * s
                        square = Rect(corner[0] - half, corner[1] - half, 2 * half, 2 * half)
                        self.round_rect(square, TRANSFORM_HANDLE_HOVER if hot else TRANSFORM_HANDLE, radius=1)
                        self.round_rect_outline(square, TRANSFORM_FRAME, radius=1, width=1.0)
                    self.dot(frame['knob'], TRANSFORM_KNOB_RADIUS, TRANSFORM_HANDLE_HOVER if hover == 'ROTATE' else TRANSFORM_HANDLE)
                    knob_ring = [(frame['knob'][0] + math.cos(step * math.tau / 20) * (TRANSFORM_KNOB_RADIUS + 1.5) * s,
                                  frame['knob'][1] + math.sin(step * math.tau / 20) * (TRANSFORM_KNOB_RADIUS + 1.5) * s) for step in range(21)]
                    self.lines(knob_ring, TRANSFORM_FRAME, 1.0, True)

                if ed.session.has_selection() and not (gesture and gesture.get('mode') == 'SET_PIVOT'):
                    p_screen = view.screen(ed.session.get_pivot(), c)
                    arm = (9 if hover == 'PIVOT' else 6) * s
                    self.dot(p_screen, 4.5 if hover == 'PIVOT' else 3.0, TRANSFORM_PIVOT)
                    self.lines([(p_screen[0] - arm, p_screen[1]), (p_screen[0] + arm, p_screen[1])], TRANSFORM_PIVOT, 1.2)
                    self.lines([(p_screen[0], p_screen[1] - arm), (p_screen[0], p_screen[1] + arm)], TRANSFORM_PIVOT, 1.2)

                readout = None
                if gesture and gesture.get('mode') == 'TRANSFORM':
                    kind = gesture.get('kind', 'MOVE')
                    param = gesture.get('param')
                    typed = gesture.get('numeric_text', '')
                    if param is None:
                        readout = ('Type a value or drag' if not typed else f'{kind.title()}: {typed}')
                    elif kind == 'ROTATE':
                        readout = f'Rotate {param:.1f}Â°'
                    elif kind == 'SCALE':
                        readout = f'Scale {param * 100:.1f}%'
                    else:
                        readout = f'Move {param[0] * 100:.1f}, {param[1] * 100:.1f} cm'
                elif gesture and gesture.get('mode') == 'MOVE' and preview_doc is not None:
                    delta = gesture.get('delta', (0.0, 0.0))
                    readout = f'Move {delta[0] * 100:.1f}, {delta[1] * 100:.1f} cm'
                elif hover:
                    readout = {'ROTATE': 'Drag to rotate  Â·  Shift snaps 15Â°',
                               'SCALE': 'Drag to scale  Â·  Shift snaps 10%',
                               'PIVOT': 'Alt+drag to move the pivot'}[hover]
                if readout:
                    if preflight.get('status') == 'WARN':
                        readout += '  Â·  asks before applying'
                    elif preflight.get('status') == 'BLOCK':
                        readout += '  Â·  blocked'
                    blf.size(0, 10 * s)
                    badge_w = blf.dimensions(0, readout)[0] + 14 * s
                    bx, by = ed.pointer[0] + 16 * s, ed.pointer[1] - 30 * s
                    badge = Rect(bx, by, badge_w, 20 * s)
                    self.round_rect(badge, SURFACE_FLOATING, radius=3)
                    self.round_rect_outline(badge, SURFACE_OUTLINE, radius=3, width=1.0)
                    self.text(bx + 7 * s, by + 6 * s, readout, 10, TEXT_PRIMARY)

                if ed.tool == 'SEW' and ed.pending_edge:
                    doc = ed.session.document
                    try:
                        len_a = doc.chain_length([ed.pending_edge]) * 100
                        h_edge = ed.design_hit_edge()
                        if h_edge and (h_edge.pattern != ed.pending_edge.pattern or (h_edge.start, h_edge.end) != (ed.pending_edge.start, ed.pending_edge.end)):
                            len_b = doc.chain_length([h_edge]) * 100
                            diff = abs(len_a - len_b)
                            ratio = (min(len_a, len_b) / max(1e-5, max(len_a, len_b))) * 100
                            is_match = diff <= 0.6
                            rev = sew_reverse(doc, ed.pending_edge, h_edge, ed._scene.dd_sew_reverse)
                            rev_label = "rev" if rev else "direct"
                            msg = f"Match: {len_a:.1f} cm ↔ {len_b:.1f} cm ({ratio:.0f}%) [{rev_label}] · B flip" if is_match else f"Mismatch: {len_a:.1f} cm vs {len_b:.1f} cm (Δ {diff:.1f} cm) [{rev_label}] · B flip"
                            badge_bg = (0.08, 0.25, 0.16, 0.95) if is_match else (0.28, 0.18, 0.08, 0.95)
                            badge_border = (0.2, 0.7, 0.4, 0.9) if is_match else (0.8, 0.5, 0.2, 0.9)
                            px, py = ed.pointer
                            blf.size(0, 10 * s)
                            bw, bh = blf.dimensions(0, msg)
                            hud_box = Rect(min(c.x + c.w - bw - 20 * s, max(c.x + 10 * s, px + 14 * s)),
                                           min(c.y + c.h - 32 * s, max(c.y + 10 * s, py - 14 * s)),
                                           bw + 16 * s, 26 * s)
                            self.round_rect(hud_box, badge_bg, radius=metrics.tooltip if metrics else 5)
                            self.round_rect_outline(hud_box, badge_border, radius=metrics.tooltip if metrics else 5, width=1.0)
                            self.text(hud_box.x + 8 * s, hud_box.y + 7 * s, msg, 10, (1, 1, 1, 1))
                    except Exception:
                        pass

                if len(self.triangle_cache) > 250:
                    self.triangle_cache.clear()

                if ed.draft:
                    raw_coords = [(v.x, v.y) if hasattr(v, 'x') else v for v in ed.draft]
                    pts = [view.screen(pt, c) for pt in raw_coords]
                    for i in range(len(ed.draft) - 1):
                        v0 = ed.draft[i]
                        v1 = ed.draft[i + 1]
                        if getattr(v0, 'outgoing', None) is not None or getattr(v1, 'incoming', None) is not None:
                            ctrl = curves.controls(v0, v1)
                            seg_pts = [view.screen(pt, c) for _, pt in curves.table(ctrl)]
                            self.lines(seg_pts, ACCENT, 2.2, True)
                        else:
                            self.lines([pts[i], pts[i + 1]], ACCENT, 2.2, True)
                    if ed.preview:
                        end_pt = ed.preview[-1]
                        end_scr = view.screen(end_pt, c)
                        last_v = ed.draft[-1]
                        if getattr(last_v, 'outgoing', None) is not None:
                            dummy = Vertex(end_pt[0], end_pt[1])
                            ctrl = curves.controls(last_v, dummy)
                            prev_pts = [view.screen(pt, c) for _, pt in curves.table(ctrl)]
                            self.lines(prev_pts, (*ACCENT[:3], 0.6), 1.4)
                            length = curves.length(ctrl) * 100
                        else:
                            self.lines([pts[-1], end_scr], (*ACCENT[:3], 0.6), 1.4)
                            length = math.dist(raw_coords[-1], end_pt) * 100
                        self.text(end_scr[0] + 10 * s, end_scr[1] + 10 * s, f"{length:.1f} cm", 10, ACCENT)
                    for i, v in enumerate(ed.draft):
                        point = pts[i]
                        self.dot(point, 4, ACCENT)
                        for name in ('incoming', 'outgoing'):
                            handle = getattr(v, name, None)
                            if handle is not None:
                                h_end = view.screen(curves.add(raw_coords[i], handle), c)
                                self.lines([point, h_end], (0.65, 0.75, 0.8, 0.75), 1.2)
                                self.dot(h_end, 4, (0.98, 0.73, 0.32, 1))
                    self.dot(pts[0], 7, (*ACCENT[:3], 0.25))
                    self.dot(pts[0], 3.5, ACCENT)
                    if ed.tool == 'KNIFE':
                        knife_points = raw_coords + ([ed.preview[-1]] if ed.preview and math.dist(raw_coords[-1], ed.preview[-1]) > 1e-8 else [])
                        for result in ed.session.knife_preview(knife_points):
                            color = (0.98, 0.45, 0.28, 1) if result['reason'] else ACCENT
                            for crossing in result['hits']:
                                self.dot(view.screen(crossing, c), 6 * s, color)
                elif ed.gesture and ed.gesture['mode'] in {'RECT', 'ELLIPSE'} and ed.preview:
                    pts = [view.screen(point, c) for point in ed.preview]
                    if ed.gesture['mode'] == 'ELLIPSE':
                        a, b = pts[0], pts[2]
                        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                        rx, ry = abs(b[0] - a[0]) / 2, abs(b[1] - a[1]) / 2
                        shape = [(cx + math.cos(i * math.tau / 64) * rx, cy + math.sin(i * math.tau / 64) * ry) for i in range(65)]
                        self.lines(shape, ACCENT, 2, True)
                    else:
                        self.lines(pts + pts[:1], ACCENT, 2, True)
                    a, b = ed.preview[0], ed.preview[2]
                    self.text(pts[2][0] + 10 * s, pts[2][1] + 10 * s,
                              f"{abs(b[0] - a[0]) * 100:.1f} x {abs(b[1] - a[1]) * 100:.1f} cm", 11, ACCENT)
            except Exception as exc:
                ed.error_message = f"Render error: {exc}"

            self.minimal_workspace(ed)
        finally:
            blf.disable(0, blf.CLIPPING)
            gpu.state.scissor_set(*scissor)
            gpu.state.scissor_test_set(False)
            gpu.state.depth_test_set(depth)
            gpu.state.blend_set(blend)

    def piece_labels(self,ed,labels):
        scale=self.s
        radius=ed.canvas_layout.metrics.box
        canvas=ed.canvas_layout.canvas
        reserved=list(ed.measurement_rects)
        ed.piece_label_rects=[]
        ed.twin_label_ids=[]
        for low_x,high_x,low_y,high_y,text,selected,identity,twin in labels:
            blf.size(0,11*scale)
            maximum=min(240*scale,canvas.w-16*scale)
            if twin and blf.dimensions(0,text)[0]>maximum-12*scale:
                base,marker=text.rsplit(' | Twin ',1)
                while len(base)>1 and blf.dimensions(0,base+'... | Twin '+marker)[0]>maximum-12*scale:base=base[:-1]
                text=base+'... | Twin '+marker
            measured_width,height=blf.dimensions(0,text)
            width=min(measured_width+12*scale,maximum)
            left=max(canvas.x+8*scale,min((low_x+high_x-width)/2,canvas.x+canvas.w-width-8*scale))
            positions=[high_y+22*scale+step*22*scale for step in range(8)]
            positions.extend(low_y-(height+18*scale)-step*22*scale for step in range(8))
            for bottom in positions:
                bounds=Rect(left,bottom,width,height+8*scale)
                if bounds.y<canvas.y+8*scale or bounds.y+bounds.h>canvas.y+canvas.h-40*scale:continue
                if any(bounds.x<other.x+other.w+6*scale and bounds.x+bounds.w>other.x-6*scale and
                       bounds.y<other.y+other.h+6*scale and bounds.y+bounds.h>other.y-6*scale for other in reserved):continue
                self.round_rect(bounds,BG_WELL,radius=radius)
                self.round_rect_outline(bounds,ACCENT_BORDER if selected else BORDER_SUBTLE,radius=radius,width=1)
                self.text(bounds.x+6*scale,bounds.y+4*scale,text,11,TEXT if selected else MUTED,max_width=width-12*scale)
                reserved.append(bounds)
                ed.piece_label_rects.append(bounds)
                if twin:ed.twin_label_ids.append(identity)
                break

    def minimal_workspace(self, ed):
        layout = ed.canvas_layout
        scale = self.s
        metrics = getattr(layout, 'metrics', None) or MinimalMetrics.resolve()
        self.clip(layout.panel)
        self.round_rect(layout.rail, SURFACE_FLOATING, radius=metrics.menu_back)
        self.round_rect_outline(layout.rail, SURFACE_OUTLINE, radius=metrics.menu_back)
        icons = {'LIBRARY': 'LIBRARY', 'DRAW': 'RECTANGLE', 'INTERNAL': 'INTERNAL', 'PIN': 'PIN',
                 'SELECT': 'SELECT', 'SEW': 'SEW', 'SHAPE': 'SHAPE', 'UNDO': 'UNDO', 'REDO': 'REDO'}
        draw_shape = getattr(ed, 'draw_shape', 'RECTANGLE')
        icons['DRAW'] = 'POLYGON' if draw_shape == 'POLYGON' else 'ELLIPSE' if draw_shape == 'ELLIPSE' else 'RECTANGLE'
        icons['INTERNAL'] = ed.tool if ed.tool in {'DART', 'KNIFE'} else 'INTERNAL'
        shortcuts = {'SELECT': 'V', 'DRAW': 'R', 'INTERNAL': 'I', 'SEW': 'J', 'PIN': 'K',
                     'SHAPE': 'Live shaping correction',
                     'UNDO': 'Ctrl Z', 'REDO': 'Ctrl Shift Z',
                     'CLOSE': 'Esc',
                     'GARMENT': 'Garment & Body settings',
                     'RESTORE_CANVAS': 'Expand'}
        if ed.tool == 'KNIFE':
            shortcuts['INTERNAL'] = 'N'
        tooltip = None
        for key, (rect, label) in layout.buttons.items():
            hover = rect.contains(*ed.pointer)
            blocker = ed.action_blocker(key) if key in {'SIMULATE', 'KEEP'} else ''
            if key in {'SIMULATE', 'KEEP', 'FINISH_DRAFT', 'CANCEL_DRAFT', 'CONFIRM_ACTION', 'CANCEL_ACTION'}:
                primary = key in {'SIMULATE', 'FINISH_DRAFT', 'CONFIRM_ACTION'}
                surface = SURFACE_FLOATING if blocker else ACCENT_HOVER if hover else ACCENT
                joined = Rect(rect.x, rect.y, rect.w + (30 * scale if key+'_OPTIONS' in layout.buttons else 0), rect.h)
                self.round_rect(joined, surface if primary else ELEVATED if hover else SURFACE_FLOATING, radius=metrics.regular)
                self.round_rect_outline(joined, ACCENT_BORDER if primary else SURFACE_OUTLINE, radius=metrics.regular)
                ink = MUTED if blocker else TEXT_ON_ACCENT if primary else TEXT
                if key in {'SIMULATE', 'KEEP'}:
                    self.draw_icon('PAUSE' if label == 'Pause' else 'PLAY' if key == 'SIMULATE' else 'CHECK',
                                   rect.x + 18 * scale, rect.y + rect.h / 2, 16, ink)
                    self.text(rect.x + 34 * scale, rect.y + (rect.h-11*scale)/2, label, 11, ink)
                else:
                    self.text(rect.x + rect.w / 2, rect.y + (rect.h-11*scale)/2, label, 11, ink, True)
            elif key == 'RESTORE_CANVAS':
                self.round_rect(rect, ELEVATED if hover else FIELD_BG, radius=metrics.regular)
                self.text(rect.x + rect.w / 2, rect.y + 8 * scale, label, 10, TEXT_SUB, True)
            elif key.startswith('TOGGLE_'):
                active = ed.snap if key == 'TOGGLE_SNAP' else ed._scene.dd_reference_visible if key == 'TOGGLE_GUIDE' else ed.fit_overlay.enabled if key == 'TOGGLE_FIT_MAP' else ed._scene.dd_lengths_visible
                self.round_rect(rect, ACCENT_BG if active else (ELEVATED if hover else BG_WELL), radius=metrics.toolbar_item)
                if key == 'TOGGLE_SNAP':
                    self.draw_icon('SNAP_ON' if ed.snap else 'SNAP_OFF', rect.x + rect.w / 2, rect.y + rect.h / 2, 12, ACCENT if active else TEXT_SUB)
                elif key == 'TOGGLE_GUIDE':
                    self.draw_icon('HIDE_OFF' if ed._scene.dd_reference_visible else 'HIDE_ON', rect.x + rect.w / 2, rect.y + rect.h / 2, 12, ACCENT if active else TEXT_SUB)
                elif key == 'TOGGLE_LENGTHS':
                    self.draw_icon('RULER', rect.x + rect.w / 2, rect.y + rect.h / 2, 12, ACCENT if active else TEXT_SUB)
                elif key == 'TOGGLE_FIT_MAP':
                    self.text(rect.x + rect.w / 2, rect.y + (rect.h - 9 * scale) / 2, 'F', 9, ACCENT if active else TEXT_SUB, True)
            elif key.endswith('_OPTIONS'):
                self.lines([(rect.x, rect.y + 10 * scale), (rect.x, rect.y + rect.h - 10 * scale)], SURFACE_OUTLINE, 1.0 / max(1.0, scale))
                self.draw_icon('CHEVRON', rect.x + rect.w / 2, rect.y + rect.h / 2, 12,
                               TEXT_ON_ACCENT if key=='SIMULATE_OPTIONS' else TEXT_SUB)
            elif key == 'GARMENT':
                is_open = ed.card_kind in {'GARMENT', 'BODY'}
                self.round_rect(rect, ACCENT_BG if is_open else (ELEVATED if hover else BG_WELL), radius=metrics.toolbar_item)
                self.draw_icon('GARMENT', rect.x + rect.w / 2, rect.y + rect.h / 2, 18, ACCENT if is_open else TEXT_SUB)
            else:
                is_active = (key == ed.tool or
                             (key == 'DRAW' and ed.tool in {'RECTANGLE', 'POLYGON', 'ELLIPSE'}) or
                             (key == 'INTERNAL' and ed.tool in {'INTERNAL', 'DART', 'KNIFE'}) or
                             (key == 'PIN' and ed.tool in {'PIN', 'TACK'}))
                if is_active or hover:
                    self.round_rect(rect, ACCENT_BG if is_active else ELEVATED, radius=metrics.toolbar_item)
                self.draw_icon(icons.get(key, key), rect.x + rect.w / 2, rect.y + rect.h / 2, min(rect.w/scale*.8,rect.h/scale-1), ACCENT if is_active else TEXT_SUB)
            if hover:
                position = (rect.x + rect.w + 8 * scale, rect.y + rect.h / 2)
                if key in {'SIMULATE', 'KEEP'}:
                    position = (max(layout.panel.x + 8 * scale, rect.x - (220 if blocker else 60) * scale), rect.y + rect.h + 20 * scale)
                elif key in {'CLOSE', 'RESTORE_CANVAS'}:
                    position = (rect.x - 70 * scale, rect.y - 18 * scale)
                elif key == 'GARMENT':
                    position = (rect.x + 20 * scale, rect.y - 18 * scale)
                elif key == 'SHAPE':
                    tip_label = 'Shape cloth'
                    tip_shortcut = 'Live shaping correction'
                tip_label = ('Snap: On' if ed.snap else 'Snap: Off') if key == 'TOGGLE_SNAP' else \
                            ('Body guide: On' if ed._scene.dd_reference_visible else 'Body guide: Off') if key == 'TOGGLE_GUIDE' else \
                            ('Lengths: On' if ed._scene.dd_lengths_visible else 'Lengths: Off') if key == 'TOGGLE_LENGTHS' else blocker or label
                if key == 'TOGGLE_FIT_MAP':
                    tip_label = 'Fit map: On' if ed.fit_overlay.enabled else 'Fit map: Off'
                tip_shortcut = 'S' if key == 'TOGGLE_SNAP' else 'H' if key == 'TOGGLE_GUIDE' else 'L' if key == 'TOGGLE_LENGTHS' else 'F' if key == 'TOGGLE_FIT_MAP' else shortcuts.get(key, 'Right-click for options' if key in {'DRAW', 'INTERNAL', 'PIN', 'SEW'} else '')
                tooltip = (tip_label, tip_shortcut, position)
        seam_order = {sm.id: idx for idx, sm in enumerate(ed.session.document.seams)}
        for rect, identity, label in ed.seam_badges():
            s_idx = seam_order.get(identity, 0)
            tone = SEAM_PAIR_TONES[s_idx % len(SEAM_PAIR_TONES)]
            level = self.seam_levels.get(identity, SEAM_QUIET)
            active_badge = level == SEAM_ACTIVE
            if level == SEAM_QUIET and not self.seam_mismatch(ed, ed.session.document.seams[s_idx]):
                bg_col = (*BG_ELEVATED[:3], 0.50)
                border_col = (*BORDER_SUBTLE[:3], 0.70)
                text_col = TEXT_MUTED
            else:
                bg_col = (*tone, 0.42) if active_badge else (*tone, 0.18)
                border_col = (*tone, 0.92) if active_badge else (*tone, 0.48)
                text_col = TEXT
            self.round_rect(rect, bg_col, radius=metrics.box)
            self.round_rect_outline(rect, border_col, radius=metrics.box)
            self.text(rect.x + rect.w / 2, rect.y + 5 * scale, label, 10, text_col, True)
        cards = ed.visible_cards()
        card_tooltip = None
        for card in cards:
            rect, title, controls = card
            is_menu = ed.card_kind in {'CANVAS_MENU', 'DRAW_CHOOSER', 'INTERNAL_CHOOSER', 'PIN_CHOOSER', 'PIECE_SIMULATION', 'PIECE_DENSITY', 'LIBRARY_TAGS'} or (bool(ed.card_kind) and ed.card_kind.endswith('_MENU'))
            self.round_rect(rect, SURFACE_FLOATING, radius=metrics.menu_back)
            self.round_rect_outline(rect, SURFACE_OUTLINE, radius=metrics.menu_back)
            mode_rects = ed.card_mode_rects(rect)
            mode_items = list(mode_rects.items())
            if not mode_items:
                self.text(rect.x + (8 if is_menu else 14) * scale, rect.y + rect.h - (19 if is_menu else 26) * scale, title, 11 if is_menu else 13, TEXT, max_width=rect.w - 52 * scale)
            if mode_items:
                m_first = mode_items[0][1]
                m_last = mode_items[-1][1]
                m_track = Rect(m_first.x - 2 * scale, m_first.y - 2 * scale, (m_last.x + m_last.w - m_first.x) + 4 * scale, m_first.h + 4 * scale)
                self.round_rect(m_track, BG_WELL, radius=metrics.box)
                for m_kind, m_rect in mode_items:
                    m_active = ed.card_kind == m_kind
                    m_hover = m_rect.contains(*ed.pointer)
                    if m_active:
                        self.round_rect(m_rect, ACCENT_BG, radius=metrics.regular)
                    elif m_hover:
                        self.round_rect(m_rect, ELEVATED, radius=metrics.regular)
                    self.text(m_rect.x + m_rect.w / 2, m_rect.y + 5 * scale, m_kind.title(), 9,
                              ACCENT if m_active else (TEXT if m_hover else TEXT_SUB), True)
            self.lines([(rect.x + (4 if is_menu else 12) * scale, rect.y + rect.h - (28 if is_menu else 38) * scale),
                        (rect.x + rect.w - (4 if is_menu else 12) * scale, rect.y + rect.h - (28 if is_menu else 38) * scale)],
                       BORDER_SUBTLE, 1.0 / max(1.0, scale))
            close = ed.card_close_rect(rect)
            if close.contains(*ed.pointer):
                self.round_rect(close, ELEVATED, radius=metrics.regular)
                card_tooltip = Tooltip(text='Close card', pos=(rect.x, close.y - 18 * scale), visible=True)
            self.draw_icon('CLOSE', close.x + close.w / 2, close.y + close.h / 2, 12, TEXT_SUB)
            for control, row in controls:
                key = row[0]
                hover = control.contains(*ed.pointer)
                if key in {'LIBRARY_SEARCH', 'LIBRARY_NAME', 'LIBRARY_TAG_EDIT'}:
                    field = {'LIBRARY_SEARCH': 'library_query', 'LIBRARY_NAME': 'dd_library_name', 'LIBRARY_TAG_EDIT': 'library_tags'}[key]
                    editing = ed.library_edit and ed.library_edit['key'] == field
                    if editing:
                        cursor = ed.library_edit['cursor']
                        value = ed.library_edit['text'][:cursor] + '|' + ed.library_edit['text'][cursor:]
                    else:
                        value = row[2]
                    self.round_rect(control, BG_WELL, radius=metrics.text)
                    self.round_rect_outline(control, ACCENT_BORDER if editing else BORDER_SUBTLE, radius=metrics.text)
                    if key == 'LIBRARY_SEARCH':
                        self.text(control.x + 8 * scale, control.y + 10 * scale, 'Search', 10, TEXT_SUB)
                        self.text(control.x + 62 * scale, control.y + 10 * scale, value or 'Name, tag or body', 10, TEXT if value else MUTED, max_width=control.w - 72 * scale)
                    else:
                        self.text(control.x + 8 * scale, control.y + control.h - 15 * scale, row[1], 9, TEXT_SUB)
                        self.text(control.x + 8 * scale, control.y + 8 * scale, value, 11, TEXT, max_width=control.w - 16 * scale)
                elif key == 'AVATAR_FIELD':
                    self.avatar_field(ed, control, row[1], metrics)
                    if hover and not ed.avatar_field.mode:
                        card_tooltip = Tooltip(text='Avatar body used for arrangement, points and fit', pos=(control.x, control.y - 18 * scale), visible=True)
                elif key in {'CHOICES', 'CHOICES_FABRIC'}:
                    label, value = row[1], row[2]
                    prefix, choices, active = value
                    self.text(control.x + 4 * scale, control.y + control.h - 14 * scale, label, 10, TEXT_SUB)
                    choices_list = list(choices)
                    track_rect = Rect(control.x, control.y + 2 * scale, control.w, control.h - 19 * scale)
                    self.round_rect(track_rect, BG_WELL, radius=metrics.box)
                    if len(choices_list) <= 4:
                        choice_width = (control.w - 4 * scale) / max(1, len(choices_list))
                        for index, choice in enumerate(choices_list):
                            chip = Rect(control.x + 2 * scale + index * choice_width + 1 * scale, control.y + 4 * scale, choice_width - 2 * scale, 22 * scale)
                            c_active = choice == active
                            c_hover = chip.contains(*ed.pointer)
                            if c_active:
                                self.round_rect(chip, ACCENT_BG, radius=metrics.regular)
                            elif c_hover:
                                self.round_rect(chip, ELEVATED, radius=metrics.regular)
                            disp = choice.title() if (key == 'CHOICES_FABRIC' and str(choice).isupper()) else str(choice)
                            self.text(chip.x + chip.w / 2, chip.y + 6 * scale, disp, 10, ACCENT if c_active else (TEXT if c_hover else TEXT_SUB), True, max_width=chip.w - 4 * scale)
                    else:
                        cols = 3
                        choice_w = (control.w - 4 * scale) / cols
                        row_h = 20 * scale
                        num_rows = math.ceil(len(choices_list) / cols)
                        for index, choice in enumerate(choices_list):
                            r_idx = index // cols
                            c_idx = index % cols
                            chip = Rect(control.x + 2 * scale + c_idx * choice_w + 1 * scale, control.y + (num_rows - 1 - r_idx) * (row_h + 3 * scale) + 4 * scale, choice_w - 2 * scale, row_h)
                            c_active = choice == active
                            c_hover = chip.contains(*ed.pointer)
                            if c_active:
                                self.round_rect(chip, ACCENT_BG, radius=metrics.regular)
                            elif c_hover:
                                self.round_rect(chip, ELEVATED, radius=metrics.regular)
                            disp = choice.title() if (key == 'CHOICES_FABRIC' and str(choice).isupper()) else str(choice)
                            self.text(chip.x + chip.w / 2, chip.y + 5 * scale, disp, 9, ACCENT if c_active else (TEXT if c_hover else TEXT_SUB), True, max_width=chip.w - 4 * scale)
                elif key == 'PAIR_ACTIONS':
                    action1, action2, label1, label2 = row[1], row[2], row[3], row[4]
                    w2 = (control.w - 6 * scale) / 2
                    r1 = Rect(control.x, control.y + 2 * scale, w2, control.h - 4 * scale)
                    r2 = Rect(control.x + w2 + 6 * scale, control.y + 2 * scale, w2, control.h - 4 * scale)
                    h1 = r1.contains(*ed.pointer)
                    h2 = r2.contains(*ed.pointer)
                    dest1 = action1 in {'DELETE_PIECE', 'REMOVE_SEAM', 'REMOVE_ANCHOR'}
                    dest2 = action2 in {'DELETE_PIECE', 'REMOVE_SEAM', 'REMOVE_ANCHOR'}
                    ink1 = (1, .55, .49, 1) if dest1 else ACCENT if h1 else TEXT
                    ink2 = (1, .55, .49, 1) if dest2 else ACCENT if h2 else TEXT
                    self.round_rect(r1, ACCENT_BG if h1 else ELEVATED, radius=metrics.menu_item if is_menu else metrics.regular)
                    self.round_rect(r2, ACCENT_BG if h2 else ELEVATED, radius=metrics.menu_item if is_menu else metrics.regular)
                    self.text(r1.x + r1.w / 2, r1.y + 7 * scale, label1, 10, ink1, True, max_width=r1.w - 8 * scale)
                    self.text(r2.x + r2.w / 2, r2.y + 7 * scale, label2, 10, ink2, True, max_width=r2.w - 8 * scale)
                elif key.startswith(('LOAD_', 'PREVIEW_')):
                    preview_only = key.startswith('PREVIEW_')
                    idx_key = key.split('_', 1)[1]
                    display_name = row[1] if len(row) > 1 and row[1] else idx_key
                    self.round_rect(control, ACCENT_BG if hover else BG_WELL, radius=metrics.box)
                    thumb_pad = 6 * scale
                    compact_tile = control.h < 84 * scale
                    thumb_h = control.h - 12 * scale if preview_only else max(8 * scale, control.h - (30 if compact_tile else 48) * scale)
                    thumb = Rect(control.x + thumb_pad, control.y + control.h - thumb_h - thumb_pad,
                                 control.w - 2 * thumb_pad, thumb_h)
                    self.round_rect(thumb, ELEVATED if hover else BG_BASE, radius=metrics.box)
                    meta = ed.library_previews[ed.library_items[int(idx_key)]]
                    previews = meta.get('loops', meta.get('polys', [])) if isinstance(meta, dict) else (meta or [])
                    if previews:
                        all_x = [pt[0] for poly in previews for pt in poly]
                        all_y = [pt[1] for poly in previews for pt in poly]
                        if all_x and all_y:
                            min_x, max_x = min(all_x), max(all_x)
                            min_y, max_y = min(all_y), max(all_y)
                            span_x = max(1e-4, max_x - min_x)
                            span_y = max(1e-4, max_y - min_y)
                            preview_pad = min(4 * scale, thumb.h * .15)
                            fit_scale = min((thumb.w - 2 * preview_pad) / span_x, (thumb.h - 2 * preview_pad) / span_y)
                            off_x = thumb.x + (thumb.w - span_x * fit_scale) / 2 - min_x * fit_scale
                            off_y = thumb.y + (thumb.h - span_y * fit_scale) / 2 - min_y * fit_scale
                            for poly in previews:
                                pts = [(off_x + pt[0] * fit_scale, off_y + pt[1] * fit_scale) for pt in poly]
                                try:
                                    tris = triangulate(poly)
                                    self.triangles(pts, (*ACCENT[:3], 0.28 if hover else 0.16), tris)
                                except Exception:
                                    pass
                                self.lines(pts + pts[:1], ACCENT if hover else (*TEXT_SUB[:3], 0.85), 1.2, True)
                    else:
                        self.draw_icon('GARMENT', thumb.x + thumb.w / 2, thumb.y + thumb.h / 2, 20, MUTED)
                    name_max_w = control.w - 12 * scale
                    if preview_only:
                        continue
                    self.text(control.x + 6 * scale, control.y + (8 if compact_tile else 20) * scale, display_name, 11, ACCENT if hover else TEXT, max_width=name_max_w)
                    p_cnt = meta['pieces']
                    if not compact_tile:
                        self.text(control.x + 6 * scale, control.y + 6 * scale, f"{p_cnt} {'piece' if p_cnt == 1 else 'pieces'} \u00b7 {meta['body']}", 9, TEXT_MUTED, max_width=name_max_w)
                elif key == 'MENU':
                    menu_key, label = row[1], row[2]
                    value = row[3] if len(row) > 3 else ''
                    if hover or not is_menu:
                        self.round_rect(control, ACCENT_BG if hover else ELEVATED, radius=metrics.menu_item if is_menu else metrics.regular)
                    val_str = str(value) if value else ''
                    blf.size(0, 10 * scale)
                    val_w = blf.dimensions(0, val_str)[0] if val_str else 0
                    icon_w = 22 * scale
                    val_x = control.x + control.w - icon_w - val_w
                    lbl_max = max(40 * scale, val_x - control.x - 8 * scale) if val_str else control.w - icon_w
                    self.text(control.x + 8 * scale, control.y + (control.h - 10 * scale) / 2, label, 11, ACCENT if hover else TEXT, max_width=lbl_max)
                    if val_str:
                        self.text(val_x, control.y + (control.h - 10 * scale) / 2, val_str, 10, TEXT_SUB)
                    self.draw_icon('DISCLOSURE', control.x + control.w - 14 * scale, control.y + control.h / 2, 14, MUTED)
                elif key == 'SLIDER':
                    label, value = row[1], row[2]
                    spec = SETTINGS[label]
                    editing = bool(ed.numeric and ed.numeric['key'] == label)
                    text = (ed.numeric['text'] + '|') if editing else (spec.display(getattr(ed._scene, label)) + ' ' + spec.unit)
                    self.round_rect(control, ELEVATED, radius=metrics.regular)
                    blf.size(0, 11 * scale)
                    val_w = blf.dimensions(0, text)[0]
                    val_x = control.x + control.w - 10 * scale - val_w
                    lbl_max = max(40 * scale, val_x - control.x - 8 * scale)
                    self.text(control.x + 8 * scale, control.y + 16 * scale, value, 10, TEXT_SUB, max_width=lbl_max)
                    self.text(val_x, control.y + 16 * scale, text, 11, TEXT)
                    start = control.x + 8 * scale
                    end = control.x + control.w - 8 * scale
                    middle = control.y + 6 * scale
                    raw_val = getattr(ed._scene, label, spec.low)
                    span = max(1e-9, spec.high - spec.low)
                    fraction = max(0.0, min(1.0, (raw_val - spec.low) / span))
                    fill_x = start + (end - start) * fraction
                    self.lines([(start, middle), (end, middle)], BORDER_SUBTLE, 1.4)
                    if fill_x > start:
                        self.lines([(start, middle), (fill_x, middle)], ACCENT, 1.8)
                    self.dot((fill_x, middle), 3.0, ACCENT)
                else:
                    label = row[1] if len(row) > 1 else ''
                    value = row[2] if len(row) > 2 else ''
                    active = value == 'Selected'
                    reason = ed.action_blocker(key) if key not in {'INFO', 'NAME'} else ''
                    if hover and reason:
                        card_tooltip = Tooltip(text=reason, pos=(max(layout.panel.x + 10 * scale, rect.x - 180 * scale), control.y - 18 * scale), visible=True)
                    if key != 'INFO' and (not is_menu or active or hover):
                        self.round_rect(control, ACCENT_BG if active or (is_menu and hover) else ELEVATED, radius=metrics.menu_item if is_menu else metrics.regular)
                    text = label
                    if key == 'NAME' and ed.numeric and ed.numeric['key'] == 'dd_library_name':
                        text = ed.numeric['text'] + '|'
                    destructive = key in {'DELETE', 'REMOVE_SEAM', 'REMOVE_ANCHOR', 'RESET', 'DELETE_PIECE'}
                    ink = MUTED if reason else (1, .55, .49, 1) if destructive else TEXT_MUTED if key == 'INFO' else (ACCENT if (active or hover) else TEXT)
                    is_nav = key == 'MENU' or key.endswith('_MENU') or key.startswith('PAGE_') or key in {'LIBRARY_SAVE', 'LIBRARY_TAGS', 'MENU_LIBRARY', 'MENU_GARMENT'}
                    has_icon = active or is_nav
                    icon_w = 22 * scale if has_icon else 10 * scale
                    val_str = str(value) if value and not active else ''
                    if control.h >= 38 * scale and val_str and not active:
                        self.text(control.x + 8 * scale, control.y + control.h - 16 * scale, text, 11, ink, max_width=control.w - 16 * scale)
                        self.text(control.x + 8 * scale, control.y + 7 * scale, val_str, 9, TEXT_MUTED, max_width=control.w - 16 * scale)
                    else:
                        blf.size(0, 10 * scale)
                        val_w = min(control.w * .62, blf.dimensions(0, val_str)[0]) if val_str else 0
                        val_x = control.x + control.w - icon_w - val_w
                        lbl_max = max(40 * scale, val_x - control.x - 8 * scale) if val_str else control.w - icon_w
                        row_y = control.y + (control.h - 10 * scale) / 2
                        self.text(control.x + 8 * scale, row_y, text, 11 if key != 'INFO' else 10, ink, max_width=lbl_max)
                        if active:
                            self.draw_icon('CHECK', control.x + control.w - 16 * scale, control.y + control.h / 2, 16, ACCENT)
                        elif val_str:
                            self.text(val_x, row_y, val_str, 10, TEXT_SECONDARY if key == 'INFO' else TEXT_MUTED, max_width=val_w)
                        elif is_nav:
                            self.draw_icon('DISCLOSURE', control.x + control.w - 14 * scale, control.y + control.h / 2, 14, MUTED)
        if ed.confirm_action or ed.pending_edge or ed.pending_place or ed.pending_tack or ed.dart_base:
            panel = layout.panel
            message = ed.confirm_message if ed.confirm_action else ed.message
            self.text(panel.x + 76 * scale, panel.y + 28 * scale, message, 11, TEXT_SUB, max_width=panel.w - 360 * scale)
        elif getattr(ed, 'error_message', None):
            panel = layout.panel
            width = min(460 * scale, max(120 * scale, panel.w - 360 * scale))
            toast = Rect(panel.x + 76 * scale, panel.y + 15 * scale, width, 30 * scale)
            self.round_rect(toast, (.45, .12, .12, .96), radius=metrics.tooltip)
            self.text(toast.x + 12 * scale, toast.y + 10 * scale, ed.error_message, 10, (1.0, .85, .85, 1.0), max_width=toast.w - 24 * scale)
        elif ed.message and ed.tool != 'SHAPE':
            if getattr(ed, 'toast_text', None) != ed.message:
                ed.toast_text = ed.message
                ed.toast_until = time.monotonic() + 3
            if time.monotonic() < getattr(ed, 'toast_until', 0):
                panel = layout.panel
                width = min(420 * scale, max(80 * scale, panel.w - 390 * scale))
                toast = Rect(panel.x + 76 * scale, panel.y + 15 * scale, width, 30 * scale)
                self.round_rect(toast, (.105, .11, .115, .96), radius=metrics.tooltip)
                self.text(toast.x + 12 * scale, toast.y + 10 * scale, ed.toast_text, 10, TEXT_SUB, max_width=toast.w - 24 * scale)
        panel = layout.panel
        hint_clear = not any(rect.y <= panel.y + 78 * scale and rect.y + rect.h >= panel.y + 60 * scale
                             for rect, title, controls in cards)
        if panel.w > 850 * scale and not ed.confirm_action and hint_clear and ed.tool != 'SHAPE':
            self.text(panel.x + 90 * scale, panel.y + 65 * scale, ed.tool_hint(), 11, MUTED,
                      max_width=panel.w - 440 * scale)
        self.avatar_overlay(ed, metrics)
        if tooltip and not any(card[0].contains(*ed.pointer) for card in cards):
            ComponentRenderer.draw_tooltip(self, Tooltip(text=tooltip[0], shortcut=tooltip[1], pos=tooltip[2], visible=True), scale, metrics)
        if card_tooltip:
            ComponentRenderer.draw_tooltip(self, card_tooltip, scale, metrics)
        if ed.tool == 'SHAPE':
            self.clip(ed.shaping_view_bounds())
            if not layout.panel.contains(*ed.pointer) and ed.shape_hover is not None:
                center, radius = ed.shape_hover
                ring = [(center[0] + math.cos(index * math.tau / 32) * radius,
                         center[1] + math.sin(index * math.tau / 32) * radius) for index in range(33)]
                self.lines(ring, (*ACCENT[:3], 0.35), 1.2, strip=True)
            self.draw_shaping_strip(ed)

    def grid(self, view, c):
        step = grid_step(view.zoom)
        low, high = view.world((c.x, c.y), c), view.world((c.x + c.w, c.y + c.h), c)
        minor, major = [], []
        for axis in (0, 1):
            for i in range(math.floor(low[axis] / step), math.ceil(high[axis] / step) + 1):
                val = i * step
                if axis == 0:
                    x = view.screen((val, 0), c)[0]
                    pts = [(x, c.y), (x, c.y + c.h)]
                else:
                    y = view.screen((0, val), c)[1]
                    pts = [(c.x, y), (c.x + c.w, y)]
                (major if i % 5 == 0 else minor).extend(pts)
        self.lines(minor, (0.15, 0.18, 0.22, 0.28))
        self.lines(major, (0.22, 0.27, 0.32, 0.42))
        origin = view.screen((0, 0), c)
        self.lines([(origin[0], c.y), (origin[0], c.y + c.h),
                    (c.x, origin[1]), (c.x + c.w, origin[1])], (0.29, 0.44, 0.42, 0.6))

    def seam_mismatch(self, ed, seam):
        preview = ed.viewport_sewing
        record = preview.truth['records'].get(seam.id) if preview.truth else None
        return ed.session.document.seam_stats(seam)[3] > 1 or bool(record and any(flag != 'B reversed' for flag in record['flags']))

    def seams(self, ed):
        doc = ed.session.document
        c = ed.canvas_layout.canvas
        preview = ed.viewport_sewing
        preview.request_truth(bpy.context)
        self.seam_levels = ed.seam_focus_levels()
        badges = {identity: rect for rect, identity, _ in ed.seam_badges()}
        for index, seam in enumerate(doc.seams):
            mids = []
            tone = SEAM_PAIR_TONES[index % len(SEAM_PAIR_TONES)]
            level = self.seam_levels.get(seam.id, SEAM_QUIET)
            selected = level == SEAM_ACTIVE
            connected = level == SEAM_CONNECTED
            record = preview.truth['records'].get(seam.id) if preview.truth else None
            mismatch = self.seam_mismatch(ed, seam)
            color = SELECTION if mismatch else (*tone, 0.75) if connected else (*TEXT_SUB[:3], 0.55 if selected else 0.20)
            notch_col = SELECTION if mismatch else (*tone, 0.92 if selected else 0.65)
            seam_width = 2.6 if (selected or mismatch) else 1.8 if connected else 1.2
            dot_rad = 4.6 if (selected or mismatch) else 3.0
            for side in (0, 1):
                chain = seam.side(side)
                total = doc.chain_length(chain)
                n = max(8, min(160, int(total * ed.view.zoom / 8)))
                points = []
                for i in range(n + 1):
                    edge, fraction = doc.chain_position(chain, i / n)
                    points.append(ed.view.screen(doc.edge_point(edge, fraction), c))
                self.lines(points, color, seam_width, True)
                middle = points[len(points) // 2]
                mids.append(middle)
                if level == SEAM_QUIET and not mismatch:
                    continue
                is_rev_side = (side == 1 and seam.reverse)
                first = points[-1] if is_rev_side else points[0]
                second = points[-2] if is_rev_side and len(points) > 1 else (points[1] if len(points) > 1 else first)
                seg_len = math.dist(first, second)
                if seg_len > 1e-5:
                    nx = -(second[1] - first[1]) / seg_len
                    ny = (second[0] - first[0]) / seg_len
                    tick_len = (6.0 if selected else 4.8) * self.s
                    self.lines([(first[0] - nx * tick_len, first[1] - ny * tick_len),
                                (first[0] + nx * tick_len, first[1] + ny * tick_len)],
                               notch_col, 2.0 if selected else 1.5)
                self.dot(first, dot_rad, notch_col)
            chain_0, chain_1 = seam.side(0), seam.side(1)
            for step_i in SEAM_LINK_STEPS[level]:
                u = step_i / 4.0
                v = (1.0 - u) if seam.reverse else u
                edge_a, frac_a = doc.chain_position(chain_0, u)
                edge_b, frac_b = doc.chain_position(chain_1, v)
                pa = ed.view.screen(doc.edge_point(edge_a, frac_a), c)
                pb = ed.view.screen(doc.edge_point(edge_b, frac_b), c)
                is_mid = step_i == 2
                if mismatch:
                    band_col = (*SELECTION[:3], 0.72 if is_mid else 0.50)
                    band_w = 1.6 if is_mid else 1.1
                elif selected:
                    band_col = (*tone, 0.70 if is_mid else 0.52)
                    band_w = 1.6 if is_mid else 1.1
                else:
                    band_col = (*tone, 0.45)
                    band_w = 1.2
                self.lines([pa, pb], band_col, band_w)
            if selected and record:
                for pair in record['flat']:
                    endpoints = [ed.view.screen(point, c) for point in pair]
                    self.lines(endpoints, (*notch_col[:3], 0.35), 1.2)
                    for point in endpoints:
                        self.dot(point, 1.8 * self.s, notch_col)
                for side in (0, 1):
                    samples = [ed.view.screen(pair[side], c) for pair in record['flat']]
                    for sample in sorted({len(samples) // 3, 2 * len(samples) // 3}):
                        if sample < 1 or sample >= len(samples):
                            continue
                        before, after = samples[sample - 1], samples[sample]
                        length = math.dist(before, after)
                        if length < 1e-6:
                            continue
                        direction = ((after[0] - before[0]) / length, (after[1] - before[1]) / length)
                        wings = [(after[0] - direction[0] * 8 * self.s - direction[1] * sign * 4 * self.s, after[1] - direction[1] * 8 * self.s + direction[0] * sign * 4 * self.s) for sign in (-1, 1)]
                        self.lines([wings[0], after, wings[1]], notch_col, 2)
            if selected:
                label = f'Seam {index + 1} · ' + (record['readout'] if record else preview.truth_error)
                badge = badges.get(seam.id)
                label_x, label_y = (badge.x + badge.w + 6 * self.s, badge.y + badge.h / 2 + 3 * self.s) if badge else (mids[0][0] + 10 * self.s, mids[0][1] + 16 * self.s)
                meas = getattr(ed, 'measurement_rects', [])
                while any(abs(label_x - mr.x) < mr.w + 12 * self.s and abs(label_y - mr.y) < mr.h + 12 * self.s for mr in meas):
                    label_y += 18 * self.s
                self.text(label_x, label_y, label, 10, notch_col, max_width=max(80 * self.s, c.x + c.w - label_x - 8 * self.s))
                if record and record['flags']:
                    self.text(label_x, label_y - 12 * self.s, ' · '.join(record['flags']), 10, notch_col, max_width=max(80 * self.s, c.x + c.w - label_x - 8 * self.s))
        if ed.tool == 'SEW':
            h_edge = ed.design_hit_edge()
            if ed.pending_edge:
                edge_a = ed.pending_edge
                pts_a = [ed.view.screen(doc.edge_point(edge_a, edge_a.t0 + (edge_a.t1 - edge_a.t0) * i / 16), c) for i in range(17)]
                self.lines(pts_a, (1, 0.82, 0.3, 1), 3.2, True)
                self.dot(pts_a[0], 5.5, (1, 0.82, 0.3, 1))
                mid_a = pts_a[8]
                if h_edge and (h_edge.pattern != edge_a.pattern or (h_edge.start, h_edge.end) != (edge_a.start, edge_a.end)):
                    len_a = doc.chain_length([edge_a]) * 100
                    len_b = doc.chain_length([h_edge]) * 100
                    diff = abs(len_a - len_b)
                    is_match = diff <= 0.6
                    prev_col = (0.22, 0.82, 0.48, 0.95) if is_match else (1.0, 0.65, 0.25, 0.95)
                    pts_b = [ed.view.screen(doc.edge_point(h_edge, h_edge.t0 + (h_edge.t1 - h_edge.t0) * i / 16), c) for i in range(17)]
                    self.lines(pts_b, prev_col, 3.2, True)
                    rev = sew_reverse(doc, edge_a, h_edge, ed._scene.dd_sew_reverse)
                    dot_b = pts_b[-1] if rev else pts_b[0]
                    self.dot(dot_b, 5.5, prev_col)
                    for s_idx in range(5):
                        u = (s_idx + 0.5) / 5.0
                        v = (1.0 - u) if rev else u
                        pa = ed.view.screen(doc.edge_point(edge_a, edge_a.t0 + (edge_a.t1 - edge_a.t0) * u), c)
                        pb = ed.view.screen(doc.edge_point(h_edge, h_edge.t0 + (h_edge.t1 - h_edge.t0) * v), c)
                        st_steps = max(2, int(math.dist(pa, pb) / (8 * self.s)))
                        col_alpha = 0.55 if s_idx == 2 else 0.32
                        width = 1.4 if s_idx == 2 else 1.0
                        for st_i in range(0, st_steps, 2):
                            self.lines([curves.mix(pa, pb, st_i / st_steps), curves.mix(pa, pb, min(st_i + 1, st_steps) / st_steps)], (*prev_col[:3], col_alpha), width)
                else:
                    dist_to_cursor = math.dist(mid_a, ed.pointer)
                    if dist_to_cursor > 12 * self.s:
                        st_steps = max(2, int(dist_to_cursor / (10 * self.s)))
                        for st_i in range(0, st_steps, 2):
                            self.lines([curves.mix(mid_a, ed.pointer, st_i / st_steps), curves.mix(mid_a, ed.pointer, min(st_i + 1, st_steps) / st_steps)], (1, 0.82, 0.3, 0.35), 1.2)
            elif h_edge:
                pts_h = [ed.view.screen(doc.edge_point(h_edge, h_edge.t0 + (h_edge.t1 - h_edge.t0) * i / 16), c) for i in range(17)]
                self.lines(pts_h, (0.35, 0.75, 0.95, 0.75), 2.5, True)
                self.dot(pts_h[0], 4.5, (0.35, 0.75, 0.95, 0.75))
        elif ed.pending_edge:
            points = [ed.view.screen(doc.edge_point(ed.pending_edge, ed.pending_edge.t0 + (ed.pending_edge.t1-ed.pending_edge.t0) * i / 16), c) for i in range(17)]
            self.lines(points, (1, 0.82, 0.3, 1), 3, True)
        for edge, t in ed.free_clicks + ed.dart_base:
            self.dot(ed.view.screen(doc.edge_point(edge, t), c), 6, (1, 0.82, 0.3, 1))

    def body_reference(self, ed):
        scene = ed._scene
        reference = ed.reference
        show_guide = getattr(scene, 'dd_measure_visible', False)
        if (not scene.dd_reference_visible and not show_guide) or not reference.vertices:
            return
        c = ed.canvas_layout.canvas
        if self.reference_revision != reference.revision:
            self.reference_batch = batch_for_shader(self.shader, 'TRIS', {'pos': reference.vertices}, indices=reference.triangles)
            self.reference_revision = reference.revision
        if scene.dd_reference_visible and scene.dd_reference_opacity > 0:
            alpha = scene.dd_reference_opacity
            tint = (0.48, 0.56, 0.64)
            color = tuple(BG[i] * (1 - alpha) + tint[i] * alpha for i in range(3)) + (1,)
            origin = ed.view.screen((scene.dd_reference_x, scene.dd_reference_y), c)
            zoom = ed.view.zoom
            transform = Matrix(((zoom, 0, 0, origin[0]), (0, zoom, 0, origin[1]), (0, 0, 1, 0), (0, 0, 0, 1)))
            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(transform)
                self.shader.bind()
                self.shader.uniform_float('color', color)
                self.reference_batch.draw(self.shader)
        if show_guide and getattr(reference, 'measurements', None) and reference.bounds:
            m = reference.measurements
            line_color = (0.35, 0.65, 0.90, 0.85)
            text_color = (0.85, 0.92, 0.98, 0.95)
            ref_h = reference.bounds[1][1] - reference.bounds[0][1]
            landmarks = (
                ('Chest', m['chest'], m.get('chest_y', m['chest_z'] - m['low_z'])),
                ('Waist', m['waist'], m.get('waist_y', m['waist_z'] - m['low_z'])),
                ('Hips', m['hip'], m.get('hip_y', m['hip_z'] - m['low_z'])),
            )
            for label, val, ly in landmarks:
                wy = scene.dd_reference_y + ly
                sy = ed.view.screen((0, wy), c)[1]
                if c.y <= sy <= c.y + c.h:
                    near_xs = [p[0] for p in reference.vertices if abs(p[1] - ly) < 0.025 and abs(p[0]) < 0.28 * ref_h]
                    if near_xs:
                        lx = min(near_xs) - 0.02
                        rx = max(near_xs) + 0.02
                    else:
                        lx = -0.16
                        rx = 0.16
                    sx_left = ed.view.screen((scene.dd_reference_x + lx, 0), c)[0]
                    sx_right = ed.view.screen((scene.dd_reference_x + rx, 0), c)[0]
                    self.lines([(sx_left, sy), (sx_right, sy)], line_color, 1.2)
                    self.dot((sx_left, sy), 2.5 * self.s, line_color)
                    self.dot((sx_right, sy), 2.5 * self.s, line_color)
                    self.text(sx_right + 6 * self.s, sy - 5 * self.s, f"{label} {val:.1f} cm", 9, text_color)
        if reference.bounds:
            height = reference.bounds[1][1] - reference.bounds[0][1]
            self.text(c.x + 10 * self.s, c.y + c.h - 18 * self.s,
                      f"{scene.dd_reference_view.title()} body reference / {height * 100:.1f} cm", 9, MUTED, max_width=c.w - 20 * self.s)
