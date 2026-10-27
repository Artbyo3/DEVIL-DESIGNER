import math
import time
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix
from .canvas import Rect, grid_step
from .core import area, triangulate, contains
from . import curves
from .controls import CONTROL_SETTINGS as SETTINGS
from .icons import icon_spans

from .ui_system import (
    BG_BASE, BG_PANEL, BG_ELEVATED, BG_WELL,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_BG, ACCENT_BORDER, ACCENT_HOVER,
    BORDER, BORDER_SUBTLE,
    RADIUS_DEFAULT,
    Tooltip, ComponentRenderer, SURFACE_FLOATING, SURFACE_OUTLINE, SELECTION, TEXT_ON_ACCENT
)
from .canvas import ALL_TOOLS

BG = BG_BASE
SHELL = BG_BASE
CHROME = BG_PANEL
RAIL_BG = BG_PANEL
VIEWBAR = (0.120, 0.141, 0.165, 1.0)
INSPECTOR = BG_PANEL
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
STEP_ACTIVE_BG = BG_ELEVATED

PALETTE = [
    (0.741, 0.651, 0.914),
    (0.843, 0.694, 0.482),
    (0.475, 0.733, 0.816),
    (0.486, 0.804, 0.659),
]


class Renderer:
    def __init__(self):
        self.shader = None
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
        self.triangles([(r.x, r.y), (r.x + r.w, r.y), (r.x + r.w, r.y + r.h), (r.x, r.y + r.h)],
                       color, [(0, 1, 2), (0, 2, 3)])

    def round_rect(self, r, color, radius=8):
        rad = min(radius * self.s, r.w / 2, r.h / 2)
        if rad <= 1.5:
            self.rect(r, color)
            return
        x, y, w, h = r.x, r.y, r.w, r.h
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
        for cx, cy, a0, a1 in corners:
            pts.append((cx, cy))
            c_idx = len(pts) - 1
            n = 4
            for i in range(n + 1):
                angle = a0 + (a1 - a0) * i / n
                pts.append((cx + math.cos(angle) * rad, cy + math.sin(angle) * rad))
                if i > 0:
                    indices.append((c_idx, len(pts) - 2, len(pts) - 1))
        self.triangles(pts, color, indices)

    def round_rect_outline(self, r, color, radius=8, width=1):
        rad = min(radius * self.s, r.w / 2, r.h / 2)
        if rad <= 1.5:
            self.lines([(r.x, r.y), (r.x + r.w, r.y), (r.x + r.w, r.y + r.h), (r.x, r.y + r.h)],
                       color, width, strip=True)
            return
        x, y, w, h = r.x, r.y, r.w, r.h
        pts = []
        corners = [
            (x + rad, y + rad, math.pi, 1.5 * math.pi),
            (x + w - rad, y + rad, 1.5 * math.pi, 2 * math.pi),
            (x + w - rad, y + h - rad, 0, 0.5 * math.pi),
            (x + rad, y + h - rad, 0.5 * math.pi, math.pi),
        ]
        for cx, cy, a0, a1 in corners:
            n = 4
            for i in range(n + 1):
                angle = a0 + (a1 - a0) * i / n
                pts.append((cx + math.cos(angle) * rad, cy + math.sin(angle) * rad))
        self.lines(pts + pts[:1], color, width, strip=True)

    def lines(self, points, color, width=1, strip=False):
        if len(points) < 2:
            return
        if self.line_shader is None:
            self.line_shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        sh = self.line_shader
        batch = batch_for_shader(sh, 'LINE_STRIP' if strip else 'LINES', {"pos": points})
        sh.bind()
        sh.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        sh.uniform_float("lineWidth", width * self.s)
        sh.uniform_float("color", color)
        batch.draw(sh)

    def dot(self, point, radius, color):
        x, y = point
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
        blf.position(0, x, y, 0)
        blf.draw(0, label)

    def clip(self, r):
        gpu.state.scissor_set(int(self.offset[0] + r.x), int(self.offset[1] + r.y), max(1, int(r.w)), max(1, int(r.h)))
        blf.enable(0, blf.CLIPPING)
        blf.clipping(0, r.x, r.y, r.x + r.w, r.y + r.h)

    def draw_icon(self, name, cx, cy, size, color):
        spans = icon_spans(name)
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
                gpu.matrix.translate((cx, cy, 0))
                gpu.matrix.scale((size * self.s, size * self.s, 1))
                self.shader.bind()
                for level, batch in self.icon_batches[name]:
                    self.shader.uniform_float('color', (*color[:3], color[3] * level / 8))
                    batch.draw(self.shader)
            return
        s = size * self.s
        if name in {'SELECT', 'cursor'}:
            pts = [(cx - 0.3 * s, cy + 0.45 * s), (cx - 0.3 * s, cy - 0.45 * s),
                   (cx - 0.05 * s, cy - 0.15 * s), (cx + 0.25 * s, cy - 0.45 * s),
                   (cx + 0.38 * s, cy - 0.35 * s), (cx + 0.08 * s, cy - 0.05 * s),
                   (cx + 0.35 * s, cy - 0.05 * s)]
            self.lines(pts + pts[:1], color, 1.4, strip=True)
        elif name in {'POLYGON', 'poly'}:
            pts = [(cx - 0.35 * s, cy - 0.35 * s), (cx + 0.35 * s, cy - 0.30 * s),
                   (cx + 0.20 * s, cy + 0.35 * s), (cx - 0.25 * s, cy + 0.30 * s)]
            self.lines(pts + pts[:1], color, 1.3, strip=True)
            for p in pts:
                self.dot(p, 2.2, color)
        elif name in {'RECTANGLE', 'rect'}:
            r = Rect(cx - 0.38 * s, cy - 0.30 * s, 0.76 * s, 0.60 * s)
            self.round_rect_outline(r, color, radius=3, width=1.3)
            self.dot((r.x, r.y + r.h), 2, color)
            self.dot((r.x + r.w, r.y), 2, color)
        elif name in {'ELLIPSE', 'ellipse'}:
            pts = [(cx + math.cos(i * math.tau / 24) * 0.42 * s,
                    cy + math.sin(i * math.tau / 24) * 0.30 * s) for i in range(25)]
            self.lines(pts, color, 1.4, strip=True)
        elif name in {'INTERNAL', 'internal'}:
            r = Rect(cx - 0.38 * s, cy - 0.38 * s, 0.76 * s, 0.76 * s)
            self.rect(r, (*color[:3], 0.15))
            self.round_rect_outline(r, (*color[:3], 0.5), radius=2, width=1)
            pts = [(cx - 0.25 * s, cy - 0.2 * s), (cx, cy + 0.2 * s), (cx + 0.25 * s, cy)]
            self.lines(pts, color, 1.5, strip=True)
        elif name in {'DART', 'dart'}:
            pts = [(cx - 0.35 * s, cy + 0.35 * s), (cx, cy - 0.40 * s), (cx + 0.35 * s, cy + 0.35 * s)]
            self.lines(pts, color, 1.4, strip=True)
            self.lines([(cx - 0.42 * s, cy + 0.35 * s), (cx + 0.42 * s, cy + 0.35 * s)], color, 1.3)
            self.dot((cx, cy - 0.40 * s), 2.2, color)
        elif name in {'SEW', 'sew', 'FREE_SEW'}:
            self.lines([(cx - 0.35 * s, cy + 0.28 * s), (cx + 0.35 * s, cy + 0.28 * s)], color, 1.3)
            self.lines([(cx - 0.35 * s, cy - 0.28 * s), (cx + 0.35 * s, cy - 0.28 * s)], color, 1.3)
            stitch = [(cx - 0.3 * s, cy + 0.28 * s), (cx - 0.1 * s, cy - 0.28 * s),
                      (cx + 0.1 * s, cy + 0.28 * s), (cx + 0.3 * s, cy - 0.28 * s)]
            self.lines(stitch, (*color[:3], 0.75), 1.2, strip=True)
        elif name in {'PIN', 'pin'}:
            self.round_rect(Rect(cx - 0.25 * s, cy + 0.18 * s, 0.5 * s, 0.18 * s), color, radius=2)
            self.lines([(cx, cy + 0.18 * s), (cx, cy - 0.42 * s)], color, 1.5)
            self.dot((cx, cy - 0.42 * s), 1.5, color)
        elif name in {'TACK', 'tack'}:
            self.dot((cx, cy), 3.5, color)
            self.lines([(cx - 0.35 * s, cy), (cx + 0.35 * s, cy)], color, 1.2)
            self.lines([(cx, cy - 0.35 * s), (cx, cy + 0.35 * s)], color, 1.2)
        elif name in {'PLACE', 'place'}:
            self.round_rect_outline(Rect(cx - 0.35 * s, cy - 0.25 * s, 0.70 * s, 0.65 * s), color, radius=3, width=1.2)
            self.lines([(cx, cy + 0.25 * s), (cx, cy - 0.15 * s)], color, 1.4)
            self.lines([(cx - 0.18 * s, cy - 0.05 * s), (cx, cy - 0.20 * s), (cx + 0.18 * s, cy - 0.05 * s)], color, 1.4, strip=True)
        elif name in {'BODY', 'REFERENCE', 'body'}:
            self.dot((cx, cy + 0.30 * s), 2.5, color)
            body = [(cx, cy + 0.20 * s), (cx, cy - 0.15 * s), (cx - 0.25 * s, cy - 0.42 * s),
                    (cx, cy - 0.15 * s), (cx + 0.25 * s, cy - 0.42 * s)]
            arms = [(cx - 0.35 * s, cy + 0.05 * s), (cx, cy + 0.15 * s), (cx + 0.35 * s, cy + 0.05 * s)]
            self.lines(body, color, 1.3, strip=True)
            self.lines(arms, color, 1.3, strip=True)
        elif name in {'RULER', 'LENGTHS', 'ruler'}:
            self.lines([(cx - 0.35 * s, cy - 0.20 * s), (cx + 0.35 * s, cy + 0.25 * s)], color, 1.4)
            for t in (-0.18, 0.0, 0.18):
                px, py = cx + t * s, cy + (t + 0.05) * s
                self.lines([(px, py), (px - 0.12 * s, py + 0.12 * s)], color, 1.2)
        elif name in {'GRID', 'SNAP', 'grid'}:
            d = 0.25 * s
            self.lines([(cx - d, cy - 0.35 * s), (cx - d, cy + 0.35 * s)], color, 1.2)
            self.lines([(cx + d, cy - 0.35 * s), (cx + d, cy + 0.35 * s)], color, 1.2)
            self.lines([(cx - 0.35 * s, cy - d), (cx + 0.35 * s, cy - d)], color, 1.2)
            self.lines([(cx - 0.35 * s, cy + d), (cx + 0.35 * s, cy + d)], color, 1.2)
        elif name in {'FIT', 'fit'}:
            d = 0.32 * s
            arm = 0.14 * s
            self.lines([(cx - d, cy + d - arm), (cx - d, cy + d), (cx - d + arm, cy + d)], color, 1.3, strip=True)
            self.lines([(cx + d - arm, cy + d), (cx + d, cy + d), (cx + d, cy + d - arm)], color, 1.3, strip=True)
            self.lines([(cx - d, cy - d + arm), (cx - d, cy - d), (cx - d + arm, cy - d)], color, 1.3, strip=True)
            self.lines([(cx + d - arm, cy - d), (cx + d, cy - d), (cx + d, cy - d + arm)], color, 1.3, strip=True)
        elif name in {'BOOK', 'LIBRARY', 'library'}:
            self.lines([(cx, cy - 0.30 * s), (cx, cy + 0.25 * s)], color, 1.3)
            self.lines([(cx - 0.35 * s, cy - 0.22 * s), (cx, cy - 0.30 * s), (cx + 0.35 * s, cy - 0.22 * s)], color, 1.3, strip=True)
            self.lines([(cx - 0.35 * s, cy + 0.32 * s), (cx, cy + 0.25 * s), (cx + 0.35 * s, cy + 0.32 * s)], color, 1.3, strip=True)
            self.lines([(cx - 0.35 * s, cy - 0.22 * s), (cx - 0.35 * s, cy + 0.32 * s)], color, 1.3)
            self.lines([(cx + 0.35 * s, cy - 0.22 * s), (cx + 0.35 * s, cy + 0.32 * s)], color, 1.3)
        elif name in {'MORE', 'SETTINGS', 'dots'}:
            self.dot((cx - 0.25 * s, cy), 1.8, color)
            self.dot((cx, cy), 1.8, color)
            self.dot((cx + 0.25 * s, cy), 1.8, color)
        elif name in {'CLOSE', 'close'}:
            d = 0.26 * s
            self.lines([(cx - d, cy - d), (cx + d, cy + d)], color, 1.5)
            self.lines([(cx - d, cy + d), (cx + d, cy - d)], color, 1.5)
        elif name in {'FULL', 'expand'}:
            r = Rect(cx - 0.28 * s, cy - 0.28 * s, 0.56 * s, 0.56 * s)
            self.round_rect_outline(r, color, radius=2, width=1.3)

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

    def draw(self, ed):
        self.s = s = ed.canvas_layout.scale
        l, view = ed.canvas_layout, ed.view
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
            self.rect(p, SHELL)
            self.round_rect_outline(p, BORDER, radius=12, width=1.2)

            self.rect(c, BG)
            self.clip(c)
            from . import tracing
            tracing.draw_reference(ed, self)
            self.body_reference(ed)
            self.grid(view, c)

            if (not l.advanced and not ed.session.document.patterns and not ed.draft
                    and not (ed.minimal_ui and ed.card_kind)):
                self.text(c.x + c.w / 2, c.y + c.h / 2 + 12 * s, 'Drag to draw your first panel', 17, TEXT, True, max_width=c.w - 32 * s)
                self.text(c.x + c.w / 2, c.y + c.h / 2 - 14 * s, 'Then pick Sew, pair the edges, and Simulate.', 11, TEXT_SUB, True, max_width=c.w - 32 * s)

            if l.advanced and not ed.session.document.patterns and not ed.draft and not ed.gesture and not ed.reference_corners():
                midx, midy = c.x + c.w / 2, c.y + c.h / 2
                title_offset = 92 if l.starter_stacked else 54
                subtitle_offset = 70 if l.starter_stacked else 32
                self.text(midx, midy + title_offset * s, "Start Designing Garments", 15, TEXT, True, max_width=c.w - 32 * s)
                self.text(midx, midy + subtitle_offset * s, "Choose a template or draw from scratch", 11, TEXT_SUB, True, max_width=c.w - 24 * s)

                card1, card2 = l.starters

                h1 = card1.contains(*ed.pointer)
                self.round_rect(card1, ACCENT_BG if h1 else ELEVATED, radius=8)
                self.round_rect_outline(card1, ACCENT_BORDER if h1 else BORDER_SUBTLE, radius=8, width=1.0)
                self.text(card1.x + card1.w / 2, card1.y + 24 * s, "✨ Load Bodice Demo", 11, ACCENT if h1 else TEXT, True)
                self.text(card1.x + card1.w / 2, card1.y + 10 * s, "Two-piece sewn top + avatar", 9, MUTED, True)

                h2 = card2.contains(*ed.pointer)
                self.round_rect(card2, ACCENT_BG if h2 else ELEVATED, radius=8)
                self.round_rect_outline(card2, ACCENT_BORDER if h2 else BORDER_SUBTLE, radius=8, width=1.0)
                self.text(card2.x + card2.w / 2, card2.y + 24 * s, "+ Add Basic Panel", 11, ACCENT if h2 else TEXT, True)
                self.text(card2.x + card2.w / 2, card2.y + 10 * s, "40 × 45 cm rectangle", 9, MUTED, True)

                shortcut_offset = 66 if l.starter_stacked else 52
                self.text(midx, midy - shortcut_offset * s, "P Polygon / R Rectangle / E Ellipse / V Select", 10, MUTED, True, max_width=c.w - 24 * s)

            for index, source in enumerate(ed.session.document.patterns):
                pat = ed.preview_pattern(source)
                selected = ed.session.selected == pat.id
                world = pat.outline()
                outline = [view.screen(point, c) for point in world]
                holes = [path.outline() for path in pat.paths if path.role == 'HOLE']
                color = PALETTE[index % len(PALETTE)]
                if ed.minimal_ui:
                    color = (.70, .76, .82)

                opacity = (.10 if selected else .055) if ed.minimal_ui else (.22 if selected else .12)
                self.fill_pattern(pat.id, world, outline, (*color, opacity), holes, view, c)

                for path, nodes, closed, role in pat.loops():
                    points = world if path == 'OUTER' else pat.path(path).outline()
                    screen = [view.screen(point, c) for point in points]
                    active = selected and ed.session.path == path
                    line_color = ACCENT if active else (0.9, 0.48, 0.48, 0.9) if role in {'HOLE', 'SLIT'} else (*color, 0.95)
                    if ed.minimal_ui and active:
                        line_color = SELECTION
                    self.lines(screen + (screen[:1] if closed else []), line_color, 2.2 if (active or selected) else 1.5, True)

                    for i, v in enumerate(nodes):
                        point = view.screen((v.x, v.y), c)
                        chosen = active and (ed.session.corner == i or i in ed.session.point_selection)
                        if selected or not ed.minimal_ui:
                            self.dot(point, 5.5 if chosen else 3.8, ACCENT if chosen else (*color, 1))
                        if chosen:
                            for name in ('incoming', 'outgoing'):
                                handle = getattr(v, name)
                                if handle is not None:
                                    end = view.screen(curves.add((v.x, v.y), handle), c)
                                    self.lines([point, end], (0.65, 0.75, 0.8, 0.75), 1.2)
                                    self.dot(end, 4, (0.98, 0.73, 0.32, 1))

                    if selected and ed._scene.dd_lengths_visible:
                        for edge in ed.session.document.edges(source.id, path):
                            a = next(v for v in nodes if v.id == edge.start)
                            b = next(v for v in nodes if v.id == edge.end)
                            control = curves.controls(a, b)
                            if (ed.minimal_ui and edge != ed.session.segment and
                                    math.dist(view.screen((a.x, a.y), c), view.screen((b.x, b.y), c)) < 80 * s):
                                continue
                            mid = view.screen(curves.at_length(control, 0.5), c)
                            length_cm = curves.length(control) * 100
                            dim_str = f"{length_cm:.1f} cm"
                            blf.size(0, 10 * s)
                            dw, dh = blf.dimensions(0, dim_str)
                            dim_r = Rect(mid[0] + 4 * s, mid[1] + 4 * s, dw + 6 * s, dh + 4 * s)
                            self.round_rect(dim_r, (0.08, 0.10, 0.13, 0.88), radius=3)
                            self.round_rect_outline(dim_r, BORDER_SUBTLE, radius=3, width=0.8)
                            self.text(dim_r.x + 3 * s, dim_r.y + 2 * s, dim_str, 10, TEXT_SUB)

                xs, ys = [pt[0] for pt in outline], [pt[1] for pt in outline]
                label_txt = pat.name if ed.minimal_ui else pat.name + ' / ' + pat.preset.title()
                blf.size(0, 11 * s)
                lw, dh = blf.dimensions(0, label_txt)
                lx = (min(xs) + max(xs)) / 2
                ly = max(ys) + 14 * s
                lbl_r = Rect(lx - lw / 2 - 6 * s, ly - 2 * s, lw + 12 * s, dh + 6 * s)
                self.round_rect(lbl_r, (0.08, 0.10, 0.13, 0.88), radius=4)
                if selected:
                    self.round_rect_outline(lbl_r, (*color[:3], 0.6), radius=4, width=1.0)
                else:
                    self.round_rect_outline(lbl_r, BORDER_SUBTLE, radius=4, width=0.8)
                self.text(lx, ly + 2 * s, label_txt, 11, TEXT if selected else MUTED, True)

            for anchor in ed.session.document.anchors:
                point = view.screen((anchor.x, anchor.y), c)
                color = (1, 0.42, 0.3, 1) if anchor.kind == 'PIN' else (1, 0.78, 0.3, 1)
                self.dot(point, 6 if ed.selected_anchor == anchor.id else 4.5, color)
                self.lines([(point[0] - 3 * s, point[1] - 3 * s), (point[0] + 3 * s, point[1] + 3 * s),
                            (point[0] - 3 * s, point[1] + 3 * s), (point[0] + 3 * s, point[1] - 3 * s)], BG)

            self.seams(ed)

            if ed.tool == 'SEW' and ed.pending_edge:
                doc = ed.session.document
                try:
                    len_a = doc.chain_length([ed.pending_edge]) * 100
                    h_edge = ed.design_hit_edge()
                    if h_edge and (h_edge.pattern != ed.pending_edge.pattern or h_edge.edge != ed.pending_edge.edge):
                        len_b = doc.chain_length([h_edge]) * 100
                        diff = abs(len_a - len_b)
                        ratio = (min(len_a, len_b) / max(1e-5, max(len_a, len_b))) * 100
                        is_match = diff <= 0.6
                        rev_label = "rev" if ed._scene.dd_sew_reverse else "direct"
                        msg = f"Match: {len_a:.1f} cm ↔ {len_b:.1f} cm ({ratio:.0f}%) [{rev_label}] · B flip" if is_match else f"Mismatch: {len_a:.1f} cm vs {len_b:.1f} cm (Δ {diff:.1f} cm) [{rev_label}] · B flip"
                        badge_bg = (0.08, 0.25, 0.16, 0.95) if is_match else (0.28, 0.18, 0.08, 0.95)
                        badge_border = (0.2, 0.7, 0.4, 0.9) if is_match else (0.8, 0.5, 0.2, 0.9)
                        px, py = ed.pointer
                        blf.size(0, 10 * s)
                        bw, bh = blf.dimensions(0, msg)
                        hud_box = Rect(min(c.x + c.w - bw - 20 * s, max(c.x + 10 * s, px + 14 * s)),
                                       min(c.y + c.h - 32 * s, max(c.y + 10 * s, py - 14 * s)),
                                       bw + 16 * s, 26 * s)
                        self.round_rect(hud_box, badge_bg, radius=5)
                        self.round_rect_outline(hud_box, badge_border, radius=5, width=1.0)
                        self.text(hud_box.x + 8 * s, hud_box.y + 7 * s, msg, 10, (1, 1, 1, 1))
                except Exception:
                    pass

            if len(self.triangle_cache) > 250:
                self.triangle_cache.clear()

            if ed.draft:
                pts = [view.screen(point, c) for point in ed.draft]
                self.lines(pts, ACCENT, 2.2, True)
                if ed.preview:
                    end = view.screen(ed.preview[-1], c)
                    self.lines([pts[-1], end], (*ACCENT[:3], 0.6), 1.4)
                    length = math.dist(ed.draft[-1], ed.preview[-1]) * 100
                    self.text(end[0] + 10 * s, end[1] + 10 * s, f"{length:.1f} cm", 10, ACCENT)
                for point in pts:
                    self.dot(point, 4, ACCENT)
                self.dot(pts[0], 7, (*ACCENT[:3], 0.25))
                self.dot(pts[0], 3.5, ACCENT)
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

            if ed.minimal_ui:
                self.minimal_workspace(ed)
                return

            guide_txt = f"{ed.tool.title()}: {ed.message}" if ed.tool != 'SELECT' else "Drag a point to reshape · Shift to constrain"
            hud_r = Rect(c.x + 16 * s, c.y + 14 * s, min(360 * s, c.w - 32 * s), 28 * s)
            self.round_rect(hud_r, (0.098, 0.129, 0.153, 0.92), radius=6)
            self.round_rect_outline(hud_r, BORDER_SUBTLE, radius=6, width=1)
            key_pill = Rect(hud_r.x + 5 * s, hud_r.y + 4 * s, 18 * s, 20 * s)
            self.round_rect(key_pill, (0.188, 0.231, 0.267, 1.0), radius=4)
            tool_key = {'SELECT': 'V', 'POLYGON': 'P', 'RECTANGLE': 'R', 'ELLIPSE': 'E',
                        'INTERNAL': 'I', 'DART': 'D', 'SEW': 'J', 'PIN': 'K', 'TACK': 'T'}.get(ed.tool, 'V')
            self.text(key_pill.x + key_pill.w / 2, key_pill.y + 5 * s, tool_key, 9, TEXT, True)
            self.text(hud_r.x + 28 * s, hud_r.y + 7 * s, guide_txt, 10, TEXT_SUB, max_width=hud_r.w - 34 * s)

            grid_txt = f"1 cm grid  ·  {int(view.zoom / 8)}%"
            blf.size(0, 10 * s)
            gw = blf.dimensions(0, grid_txt)[0]
            self.text(c.x + c.w - gw - 14 * s, c.y + 18 * s, grid_txt, 10, MUTED)

            if not ed._scene.dd_reference_visible or not ed.reference.vertices:
                self.text(c.x + 14 * s, c.y + c.h - 18 * s, "FRONT VIEW  ·  Centimetres", 9, MUTED)

            self.clip(p)
            self.rulers(ed)

            self.rect(l.viewbar, VIEWBAR)
            self.lines([(l.viewbar.x, l.viewbar.y), (l.viewbar.x + l.viewbar.w, l.viewbar.y)], BORDER_SUBTLE)
            stage_names = {
                'DRAFT': ('Pattern canvas', f"{len(ed.session.document.patterns)} piece{'s' if len(ed.session.document.patterns) != 1 else ''} · Cotton"),
                'SEW': ('Sewing workspace', f"{len(ed.session.document.seams)} seam pair{'s' if len(ed.session.document.seams) != 1 else ''} · {len(ed.session.document.patterns)} pieces"),
                'ARRANGE': ('Arrangement workspace', 'Avatar body · Ready for placement'),
                'SIMULATE': ('Cloth simulation', 'Native Blender cloth'),
                'LIBRARY': ('Pattern library', 'Editable garments stored locally'),
            }
            v_title = 'Pattern workspace'
            v_sub = f'{len(ed.session.document.patterns)} pieces / {len(ed.session.document.seams)} seams'
            utility_start = l.buttons['FIT'][0].x
            title_width = utility_start - l.viewbar.x - 26 * s
            if title_width >= 90 * s:
                self.text(l.viewbar.x + 16 * s, l.viewbar.y + 24 * s, v_title, 13, TEXT, max_width=title_width)
                self.text(l.viewbar.x + 16 * s, l.viewbar.y + 9 * s, v_sub, 10, MUTED, max_width=title_width)

            self.rect(l.workflow, SHELL)
            self.lines([(l.workflow.x, l.workflow.y), (l.workflow.x + l.workflow.w, l.workflow.y)], BORDER_SUBTLE)
            guidance, next_label, next_enabled = ed.workflow_guidance()
            self.text(l.workflow.x + 12 * s, l.workflow.y + l.workflow.h - 20 * s, ed.workspace_hint(), 10, TEXT_SECONDARY,
                      max_width=l.workflow.w - 24 * s)

            self.rect(l.header, CHROME)
            self.lines([(p.x, l.header.y), (p.x + p.w, l.header.y)], BORDER)
            self.text(p.x + 16 * s, l.header.y + (l.header.h - 11 * s) / 2, "DEVIL DESIGNER", 11, TEXT)

            draft_btn = l.buttons.get('STAGE_DRAFT')
            sim_btn = l.buttons.get('STAGE_SIMULATE')
            if draft_btn and sim_btn:
                d_r, _ = draft_btn
                s_r, _ = sim_btn
                seg_w = (s_r.x + s_r.w) - d_r.x
                container = Rect(d_r.x - 3 * s, d_r.y - 2 * s, seg_w + 6 * s, d_r.h + 4 * s)
                self.round_rect(container, (0.07, 0.09, 0.12, 0.95), radius=8)
                self.round_rect_outline(container, BORDER_SUBTLE, radius=8, width=0.8)

            self.rect(l.rail, RAIL_BG)
            self.lines([(l.rail.x + l.rail.w, l.rail.y), (l.rail.x + l.rail.w, l.rail.y + l.rail.h)], BORDER)
            self.text(l.rail.x + l.rail.w / 2, l.rail.y + l.rail.h - 16 * s, "TOOLS", 8, MUTED, center=True)
            self.lines([(l.rail.x + 8 * s, l.rail.y + 34 * s), (l.rail.x + l.rail.w - 8 * s, l.rail.y + 34 * s)], BORDER_SUBTLE)

            cur_stage = getattr(ed, 'stage', 'DRAFT')
            stage_map = {'STAGE_DRAFT': 'DRAFT', 'STAGE_SEW': 'SEW', 'STAGE_ARRANGE': 'ARRANGE', 'STAGE_SIMULATE': 'SIMULATE'}
            stage_active_tools = {tool[0] for tool in ALL_TOOLS}
            active_tooltip = None

            for name, (r, label) in l.buttons.items():
                hover = r.contains(*ed.pointer)
                if name == 'STAGE_NEXT':
                    self.round_rect(r, ACCENT_BG if next_enabled else CHROME, radius=6)
                    self.round_rect_outline(r, ACCENT_BORDER if next_enabled else BORDER_SUBTLE, radius=6, width=1)
                    self.text(r.x + r.w / 2, r.y + 7 * s, next_label, 10,
                              ACCENT if next_enabled else MUTED, True, max_width=r.w - 6 * s)
                elif name.startswith('STAGE_'):
                    active = stage_map.get(name) == cur_stage
                    if active:
                        self.round_rect(r, STEP_ACTIVE_BG, radius=RADIUS_DEFAULT)
                        self.round_rect_outline(r, ACCENT_BORDER, radius=RADIUS_DEFAULT, width=1.0)
                    elif hover:
                        self.round_rect(r, (0.16, 0.19, 0.22, 1.0), radius=RADIUS_DEFAULT)
                    self.text(r.x + r.w / 2, r.y + (r.h - 11 * s) / 2, label, 11, ACCENT if active else (TEXT if hover else TEXT_SUB), center=True)
                elif name in {'LIBRARY', 'CLOSE', 'FULL', 'SETTINGS', 'SEARCH'}:
                    if hover:
                        self.round_rect(r, ELEVATED, radius=7)
                    if name == 'SEARCH':
                        self.round_rect_outline(r, BORDER_SUBTLE, radius=6, width=1)
                        self.text(r.x + r.w / 2, r.y + 8 * s, 'Find anything', 10, TEXT_SUB, True,
                                  max_width=r.w - 6 * s)
                    elif name == 'LIBRARY':
                        self.draw_icon('LIBRARY', r.x + 14 * s, r.y + r.h / 2, 14, TEXT_SUB if not hover else TEXT)
                        self.text(r.x + 28 * s, r.y + 8 * s, "Library", 11, TEXT_SUB if not hover else TEXT)
                    elif name == 'CLOSE':
                        self.draw_icon('CLOSE', r.x + r.w / 2, r.y + r.h / 2, 12, MUTED if not hover else TEXT)
                    elif name == 'FULL':
                        self.draw_icon('FULL', r.x + 14 * s, r.y + r.h / 2, 12, MUTED if not hover else TEXT)
                        self.text(r.x + 24 * s, r.y + 8 * s, "Restore" if ed.full else "Expand", 10, MUTED if not hover else TEXT)
                    elif name == 'SETTINGS':
                        self.text(r.x + r.w / 2, r.y + 8 * s, 'Details', 10, TEXT_SUB if not hover else TEXT, True)
                elif name in {'RECTANGLE', 'SEW', 'BUILD', 'ARRANGE', 'SIMULATE', 'STOP', 'RESET', 'KEEP', 'VIEW_3D',
                              'FINISH_DRAFT', 'CANCEL_DRAFT', 'CONFIRM_ACTION', 'CANCEL_ACTION'}:
                    blocker = '' if name in {'CONFIRM_ACTION', 'CANCEL_ACTION'} else ed.action_blocker(name)
                    is_primary = (name in {'SIMULATE', 'FINISH_DRAFT', 'CONFIRM_ACTION'} or name == ed.tool) and not blocker
                    if is_primary:
                        if hover:
                            self.round_rect(r, ACCENT_HOVER, radius=6)
                        else:
                            self.round_rect(r, ACCENT_BG, radius=6)
                            self.round_rect_outline(r, ACCENT_BORDER, radius=6, width=1.0)
                    else:
                        if hover:
                            self.round_rect(r, ELEVATED, radius=6)
                        else:
                            self.round_rect(r, CHROME, radius=6)
                            self.round_rect_outline(r, BORDER_SUBTLE, radius=6, width=1)
                    playing = False
                    try:
                        import bpy
                        playing = bool(bpy.context.screen.is_animation_playing)
                    except Exception:
                        pass
                    color = ACCENT if (name == 'SIMULATE' and playing) else (TEXT if (is_primary or hover) else TEXT_SUB)
                    if blocker:
                        color = MUTED
                        if hover:
                            active_tooltip = (blocker, '', (r.x, r.y + r.h + 8 * s))
                    display_lbl = ('Pause' if playing else '3  Simulate') if name == 'SIMULATE' else label
                    self.text(r.x + r.w / 2, r.y + 7 * s, display_lbl, 10, color, True,
                              max_width=r.w - 6 * s)
                elif name in {'REFERENCE', 'LENGTHS', 'SNAP', 'FIT', 'INSPECTOR', 'UNDO', 'REDO'}:
                    active = (name == 'SNAP' and ed.snap) or \
                             (name == 'REFERENCE' and ed._scene.dd_reference_visible) or \
                             (name == 'LENGTHS' and ed._scene.dd_lengths_visible) or \
                             (name == 'INSPECTOR' and ed.settings_open)
                    if active:
                        self.round_rect(r, ACCENT_BG, radius=6)
                        self.round_rect_outline(r, ACCENT_BORDER, radius=6, width=1)
                    elif hover:
                        self.round_rect(r, ELEVATED, radius=6)
                    else:
                        self.round_rect_outline(r, BORDER_SUBTLE, radius=6, width=0.8)

                    icon_name = {'REFERENCE': 'BODY', 'LENGTHS': 'RULER', 'SNAP': 'GRID', 'FIT': 'FIT',
                                 'INSPECTOR': 'SETTINGS'}.get(name)
                    color = ACCENT if active else (TEXT if hover else TEXT_SUB)
                    if icon_name and r.w > 40 * s:
                        self.draw_icon(icon_name, r.x + 12 * s, r.y + r.h / 2, 12, color)
                        self.text(r.x + 22 * s, r.y + 8 * s, label.split()[0], 10, color)
                    else:
                        self.text(r.x + r.w / 2, r.y + 8 * s, label.split()[0], 10, color, True)
                elif name in {'SELECT', 'POLYGON', 'RECTANGLE', 'ELLIPSE', 'INTERNAL', 'DART',
                              'SEW', 'PIN', 'TACK', 'PLACE', 'FREE_SEW', 'HELP', 'MORE_TOOLS'}:
                    if name not in {'HELP', 'MORE_TOOLS'} and name not in stage_active_tools:
                        continue
                    active = (name == ed.tool and not (name == 'SEW' and ed._scene.dd_free_sewing)) or (name == 'FREE_SEW' and ed.tool == 'SEW' and ed._scene.dd_free_sewing)
                    if active:
                        self.round_rect(r, ACCENT_BG, radius=RADIUS_DEFAULT)
                        self.round_rect_outline(r, ACCENT_BORDER, radius=RADIUS_DEFAULT, width=1.2)
                    elif hover:
                        self.round_rect(r, ELEVATED, radius=RADIUS_DEFAULT)

                    color = ACCENT if active else (TEXT if hover else TEXT_SUB)
                    if name != 'HELP':
                        self.draw_icon('MORE' if name == 'MORE_TOOLS' else name, r.x + r.w / 2, r.y + 27 * s, 15, color)
                        self.text(r.x + r.w / 2, r.y + 5 * s, label, 8, color, True, max_width=r.w - 2 * s)
                        if hover:
                            tool_lbl = label.split()[0]
                            sc = {'SELECT': 'V', 'POLYGON': 'P', 'RECTANGLE': 'R', 'ELLIPSE': 'E',
                                  'INTERNAL': 'I', 'DART': 'D', 'SEW': 'J', 'PIN': 'K', 'TACK': 'T', 'PLACE': 'G', 'FREE_SEW': ''}.get(name, '')
                            active_tooltip = (tool_lbl, sc, (r.x + r.w + 6 * s, r.y + r.h / 2))
                    else:
                        self.text(r.x + r.w / 2, r.y + 6 * s, "?", 12, color, True)
                        if hover:
                            active_tooltip = ("Shortcuts", "?", (r.x + r.w + 6 * s, r.y + r.h / 2))

            if ed.context_anchor is None:
                self.settings(ed)

            self.clip(p)
            self.rect(l.footer, BG_PANEL)
            self.lines([(p.x, l.footer.y + l.footer.h), (p.x + p.w, l.footer.y + l.footer.h)], BORDER)
            op_msg = ed.message if ed.message else "Ready"
            self.text(p.x + 14 * s, l.footer.y + (l.footer.h - 10 * s) / 2, op_msg, 10, TEXT_SECONDARY, max_width=p.w * 0.55)
            world = view.world(ed.pointer, c)
            count = len(ed.session.document.patterns)
            sel_msg = f"{count} piece{'s' if count != 1 else ''}  ·  X {world[0] * 100:.1f}  Y {world[1] * 100:.1f} cm"
            blf.size(0, 10 * s)
            mw = blf.dimensions(0, sel_msg)[0]
            self.text(p.x + p.w - mw - 14 * s, l.footer.y + (l.footer.h - 10 * s) / 2, sel_msg, 10, TEXT_MUTED)

            if not ed.full:
                for inset in (4, 8, 12):
                    self.lines([(p.x + p.w - inset * s, p.y + 3 * s), (p.x + p.w - 3 * s, p.y + inset * s)], MUTED)

            if ed.context_anchor is not None:
                self.settings(ed)
            self.body_picker(ed)

            if active_tooltip and ed.context_anchor is None:
                txt, sc, pos = active_tooltip
                ComponentRenderer.draw_tooltip(self, Tooltip(text=txt, shortcut=sc, pos=pos, visible=True), s)
        finally:
            blf.disable(0, blf.CLIPPING)
            gpu.state.scissor_set(*scissor)
            gpu.state.scissor_test_set(False)
            gpu.state.depth_test_set(depth)
            gpu.state.blend_set(blend)

    def minimal_workspace(self, ed):
        layout = ed.canvas_layout
        scale = self.s
        self.clip(layout.panel)
        shadow = Rect(layout.rail.x + 3 * scale, layout.rail.y - 4 * scale, layout.rail.w, layout.rail.h)
        self.round_rect(shadow, (0, 0, 0, .18), radius=14)
        self.round_rect(layout.rail, SURFACE_FLOATING, radius=14)
        self.round_rect_outline(layout.rail, SURFACE_OUTLINE, radius=14)
        icons = {'LIBRARY': 'GRID', 'DRAW': 'RECTANGLE', 'INTERNAL': 'INTERNAL', 'PIN': 'PIN',
                 'SELECT': 'SELECT', 'SEW': 'SEW', 'UNDO': 'UNDO', 'REDO': 'REDO'}
        draw_shape = getattr(ed, 'draw_shape', 'RECTANGLE')
        icons['DRAW'] = 'POLYGON' if draw_shape == 'POLYGON' else 'ELLIPSE' if draw_shape == 'ELLIPSE' else 'RECTANGLE'
        icons['INTERNAL'] = 'DART' if ed.tool == 'DART' else 'INTERNAL'
        shortcuts = {'SELECT': 'V', 'DRAW': 'R', 'INTERNAL': 'I', 'SEW': 'J', 'PIN': 'K',
                     'UNDO': 'Ctrl Z', 'REDO': 'Ctrl Shift Z',
                     'CLOSE': 'Esc', 'INSPECTOR_TOGGLE': 'Inspector',
                     'GARMENT': 'Garment settings', 'HELP': '?',
                     'RESTORE_CANVAS': 'Expand'}
        self.lines([(layout.rail.x + 6 * scale, layout.rail.y + 28 * scale),
                    (layout.rail.x + layout.rail.w - 6 * scale, layout.rail.y + 28 * scale)], BORDER_SUBTLE)
        tooltip = None
        for key, (rect, label) in layout.buttons.items():
            hover = rect.contains(*ed.pointer)
            blocker = ed.action_blocker(key) if key in {'SIMULATE', 'KEEP'} else ''
            if key in {'SIMULATE', 'KEEP', 'FINISH_DRAFT', 'CANCEL_DRAFT', 'CONFIRM_ACTION', 'CANCEL_ACTION'}:
                primary = key in {'SIMULATE', 'FINISH_DRAFT', 'CONFIRM_ACTION'}
                surface = SURFACE_FLOATING if blocker else ACCENT_HOVER if hover else ACCENT
                joined = Rect(rect.x, rect.y, rect.w + (30 * scale if key == 'KEEP' else 0), rect.h)
                self.round_rect(joined, surface if primary else ELEVATED if hover else SURFACE_FLOATING, radius=10)
                self.round_rect_outline(joined, ACCENT_BORDER if primary else SURFACE_OUTLINE, radius=10)
                ink = MUTED if blocker else TEXT_ON_ACCENT if primary else TEXT
                if key in {'SIMULATE', 'KEEP'}:
                    self.draw_icon('PAUSE' if label == 'Pause' else 'PLAY' if key == 'SIMULATE' else 'CHECK',
                                   rect.x + 18 * scale, rect.y + rect.h / 2, 17, ink)
                    self.text(rect.x + 34 * scale, rect.y + 14 * scale, label, 12, ink)
                else:
                    self.text(rect.x + rect.w / 2, rect.y + 14 * scale, label, 12, ink, True)
            elif key == 'INSPECTOR_TOGGLE':
                self.round_rect(rect, ELEVATED if hover else FIELD_BG, radius=7)
                self.text(rect.x + rect.w / 2, rect.y + 8 * scale, label, 10, TEXT_SUB, True)
            elif key == 'INSPECTOR_COLLAPSE':
                pass
            elif key == 'RESTORE_CANVAS':
                self.round_rect(rect, ELEVATED if hover else FIELD_BG, radius=7)
                self.text(rect.x + rect.w / 2, rect.y + 8 * scale, label, 10, TEXT_SUB, True)
            elif key.startswith('TOGGLE_'):
                active = ed.snap if key == 'TOGGLE_SNAP' else ed._scene.dd_reference_visible if key == 'TOGGLE_GUIDE' else ed._scene.dd_lengths_visible
                self.round_rect(rect, ACCENT_BG if active else (ELEVATED if hover else FIELD_BG), radius=5)
                char = 'S' if key == 'TOGGLE_SNAP' else 'H' if key == 'TOGGLE_GUIDE' else 'L'
                self.text(rect.x + rect.w / 2, rect.y + 6 * scale, char, 10, ACCENT if active else TEXT_SUB, True)
            elif key.endswith('_OPTIONS'):
                self.lines([(rect.x, rect.y + 10 * scale), (rect.x, rect.y + rect.h - 10 * scale)], SURFACE_OUTLINE)
                self.draw_icon('CHEVRON', rect.x + rect.w / 2, rect.y + rect.h / 2, 12, TEXT_SUB)
            elif key == 'GARMENT':
                self.round_rect(rect, ELEVATED if hover else SURFACE_FLOATING, radius=8)
                self.draw_icon('GARMENT', rect.x + 16 * scale, rect.y + rect.h / 2, 20, TEXT_SUB)
                self.text(rect.x + 33 * scale, rect.y + 10 * scale, ed._scene.dd_library_name or 'Untitled garment',
                          12, TEXT, max_width=rect.w - 52 * scale)
                self.draw_icon('DOWN', rect.x + rect.w - 13 * scale, rect.y + rect.h / 2, 10, MUTED)
            else:
                is_active = (key == ed.tool or
                             (key == 'DRAW' and ed.tool in {'RECTANGLE', 'POLYGON', 'ELLIPSE'}) or
                             (key == 'INTERNAL' and ed.tool in {'INTERNAL', 'DART'}) or
                             (key == 'PIN' and ed.tool in {'PIN', 'TACK'}))
                if is_active or hover:
                    self.round_rect(rect, ACCENT_BG if is_active else ELEVATED, radius=10)
                labelled = layout.rail.w >= 60 * scale and key not in {'FULL', 'CLOSE'}
                icon_y = rect.y + rect.h / 2 + (6 * scale if labelled else 0)
                self.draw_icon(icons.get(key, key), rect.x + rect.w / 2, icon_y, 22 if labelled else 18, ACCENT if is_active else TEXT_SUB)
                if labelled:
                    self.text(rect.x + rect.w / 2, rect.y + 5 * scale, label, 9, ACCENT if is_active else TEXT_SUB, True)
                if key in {'UNDO', 'LIBRARY'}:
                    self.lines([(rect.x + 8 * scale, rect.y + rect.h + 2 * scale),
                                (rect.x + rect.w - 8 * scale, rect.y + rect.h + 2 * scale)], BORDER_SUBTLE)
            if hover and key != 'INSPECTOR_COLLAPSE':
                position = (rect.x + rect.w + 8 * scale, rect.y + rect.h / 2)
                if key in {'SIMULATE', 'KEEP'}:
                    position = (max(layout.panel.x + 8 * scale, rect.x - (220 if blocker else 60) * scale), rect.y + rect.h + 20 * scale)
                elif key in {'CLOSE', 'RESTORE_CANVAS', 'INSPECTOR_TOGGLE'}:
                    position = (rect.x - 70 * scale, rect.y - 18 * scale)
                elif key == 'GARMENT':
                    position = (rect.x + 20 * scale, rect.y - 18 * scale)
                tip_label = ('Snap: On' if ed.snap else 'Snap: Off') if key == 'TOGGLE_SNAP' else                             ('Body guide: On' if ed._scene.dd_reference_visible else 'Body guide: Off') if key == 'TOGGLE_GUIDE' else                             ('Lengths: On' if ed._scene.dd_lengths_visible else 'Lengths: Off') if key == 'TOGGLE_LENGTHS' else blocker or label
                tip_shortcut = 'S' if key == 'TOGGLE_SNAP' else 'H' if key == 'TOGGLE_GUIDE' else 'L' if key == 'TOGGLE_LENGTHS' else shortcuts.get(key, 'Right-click for options' if key in {'DRAW', 'INTERNAL', 'PIN', 'SEW'} else '')
                tooltip = (tip_label, tip_shortcut, position)
        for rect, identity, label in ed.seam_badges():
            self.round_rect(rect, ACCENT_BG, radius=10)
            self.round_rect_outline(rect, ACCENT_BORDER, radius=10)
            self.text(rect.x + rect.w / 2, rect.y + 5 * scale, label, 10, ACCENT, True)
        cards = ed.visible_cards()
        card_tooltip = None
        for card in cards:
            rect, title, controls = card
            self.round_rect(Rect(rect.x + 3 * scale, rect.y - 5 * scale, rect.w, rect.h), (0, 0, 0, .20), radius=12)
            self.round_rect(rect, SURFACE_FLOATING, radius=12)
            self.round_rect_outline(rect, SURFACE_OUTLINE, radius=12)
            self.text(rect.x + 14 * scale, rect.y + rect.h - 26 * scale, title, 13, TEXT, max_width=rect.w - 52 * scale)
            self.lines([(rect.x + 12 * scale, rect.y + rect.h - 39 * scale),
                        (rect.x + rect.w - 12 * scale, rect.y + rect.h - 39 * scale)], BORDER)
            close = ed.card_close_rect(rect)
            if close.contains(*ed.pointer):
                self.round_rect(close, ELEVATED, radius=5)
                card_tooltip = Tooltip(text='Close card', pos=(rect.x, close.y - 18 * scale), visible=True)
            self.draw_icon('CLOSE', close.x + close.w / 2, close.y + close.h / 2, 12, TEXT_SUB)
            for control, row in controls:
                key = row[0]
                hover = control.contains(*ed.pointer)
                if key in {'CHOICES', 'CHOICES_FABRIC'}:
                    label, value = row[1], row[2]
                    prefix, choices, active = value
                    self.text(control.x + 6 * scale, control.y + control.h - 14 * scale, label, 11, TEXT_SUB)
                    choices_list = list(choices)
                    if len(choices_list) <= 4:
                        choice_width = control.w / len(choices_list)
                        for index, choice in enumerate(choices_list):
                            chip = Rect(control.x + index * choice_width + 2 * scale, control.y + 4 * scale, choice_width - 4 * scale, 24 * scale)
                            self.round_rect(chip, ACCENT_BG if choice == active else ELEVATED, radius=6)
                            if choice == active:
                                self.round_rect_outline(chip, ACCENT_BORDER, radius=6)
                            self.text(chip.x + chip.w / 2, chip.y + 7 * scale, choice, 10, ACCENT if choice == active else TEXT_SUB, True)
                    else:
                        cols = 3
                        choice_w = control.w / cols
                        row_h = 20 * scale
                        for index, choice in enumerate(choices_list):
                            r_idx = index // cols
                            c_idx = index % cols
                            chip = Rect(control.x + c_idx * choice_w + 2 * scale, control.y + (1 - r_idx) * (row_h + 3 * scale) + 4 * scale, choice_w - 4 * scale, row_h)
                            self.round_rect(chip, ACCENT_BG if choice == active else ELEVATED, radius=5)
                            if choice == active:
                                self.round_rect_outline(chip, ACCENT_BORDER, radius=5)
                            self.text(chip.x + chip.w / 2, chip.y + 5 * scale, choice, 9, ACCENT if choice == active else TEXT_SUB, True)
                elif key == 'PAIR_ACTIONS':
                    action1, action2, label1, label2 = row[1], row[2], row[3], row[4]
                    w2 = (control.w - 6 * scale) / 2
                    r1 = Rect(control.x, control.y + 2 * scale, w2, control.h - 4 * scale)
                    r2 = Rect(control.x + w2 + 6 * scale, control.y + 2 * scale, w2, control.h - 4 * scale)
                    h1 = r1.contains(*ed.pointer)
                    h2 = r2.contains(*ed.pointer)
                    dest1 = action1 in {'DELETE_PIECE', 'REMOVE_SEAM', 'REMOVE_ANCHOR'}
                    dest2 = action2 in {'DELETE_PIECE', 'REMOVE_SEAM', 'REMOVE_ANCHOR'}
                    ink1 = (1, .55, .49, 1) if dest1 else ACCENT if h1 else TEXT_SUB
                    ink2 = (1, .55, .49, 1) if dest2 else ACCENT if h2 else TEXT_SUB
                    self.round_rect(r1, ACCENT_BG if h1 else ELEVATED, radius=6)
                    self.round_rect(r2, ACCENT_BG if h2 else ELEVATED, radius=6)
                    self.text(r1.x + r1.w / 2, r1.y + 7 * scale, label1, 10, ink1, True)
                    self.text(r2.x + r2.w / 2, r2.y + 7 * scale, label2, 10, ink2, True)
                elif key == 'MENU':
                    menu_key, label = row[1], row[2]
                    value = row[3] if len(row) > 3 else ''
                    self.round_rect(control, ACCENT_BG if hover else ELEVATED, radius=6)
                    label_width = control.w - 12 * scale if not value else control.w * .58
                    self.text(control.x + 6 * scale, control.y + 15 * scale, label, 11, ACCENT if hover else TEXT_SUB, max_width=label_width)
                    if value:
                        self.text(control.x + control.w * .60, control.y + 15 * scale, str(value), 11, TEXT_SUB, max_width=control.w * .38)
                    self.draw_icon('DISCLOSURE', control.x + control.w - 16 * scale, control.y + control.h / 2, 14, MUTED)
                elif key == 'SLIDER':
                    label, value = row[1], row[2]
                    spec = SETTINGS[label]
                    text = spec.display(getattr(ed._scene, label)) + ' ' + spec.unit
                    if ed.numeric and ed.numeric['key'] == label:
                        text = ed.numeric['text'] + '|'
                    self.round_rect(control, ELEVATED, radius=5)
                    self.text(control.x + 8 * scale, control.y + 15 * scale, value, 11, TEXT_SUB)
                    self.text(control.x + control.w * .60, control.y + 15 * scale, text, 11, TEXT, max_width=control.w * .38)
                    if label == 'dd_weld_distance':
                        start = control.x + 6 * scale
                        end = control.x + control.w - 6 * scale
                        middle = control.y + 6 * scale
                        fraction = (ed._scene.dd_weld_distance - spec.low) / (spec.high - spec.low)
                        self.lines([(start, middle), (end, middle)], BORDER_SUBTLE, 2)
                        self.dot((start + (end - start) * fraction, middle), 4, ACCENT)
                else:
                    label = row[1] if len(row) > 1 else ''
                    value = row[2] if len(row) > 2 else ''
                    active = value == 'Selected'
                    reason = ed.action_blocker(key) if key not in {'INFO', 'NAME'} else ''
                    if hover and reason:
                        card_tooltip = Tooltip(text=reason, pos=(max(layout.panel.x + 10 * scale, rect.x - 180 * scale), control.y - 18 * scale), visible=True)
                    if hover and key != 'INFO' or active:
                        self.round_rect(control, ACCENT_BG if active else ELEVATED, radius=6)
                    text = label
                    if key == 'NAME' and ed.numeric and ed.numeric['key'] == 'dd_library_name':
                        text = ed.numeric['text'] + '|'
                    destructive = key in {'DELETE', 'REMOVE_SEAM', 'REMOVE_ANCHOR', 'RESET', 'DELETE_PIECE'}
                    ink = MUTED if reason else (1, .55, .49, 1) if destructive else MUTED if key == 'INFO' else TEXT_SUB
                    label_width = control.w - 12 * scale if not value else control.w * .58
                    self.text(control.x + 6 * scale, control.y + 15 * scale, text, 11, ink, max_width=label_width)
                    if active:
                        self.draw_icon('CHECK', control.x + control.w - 18 * scale, control.y + control.h / 2, 16, ACCENT)
                    elif value:
                        self.text(control.x + control.w * .60, control.y + 15 * scale, str(value), 11, TEXT_SUB, max_width=control.w * .38)
                    elif key not in {'INFO', 'CUT', 'TRACE', 'SPLIT', 'CURVE', 'MERGE', 'DELETE', 'REMOVE_SEAM', 'REMOVE_ANCHOR', 'RESET', 'DELETE_PIECE', 'INSP_FIT', 'DUPLICATE', 'MIRROR_SEW', 'UNFOLD'}:
                        self.draw_icon('DISCLOSURE', control.x + control.w - 16 * scale, control.y + control.h / 2, 14, MUTED)
        if ed.confirm_action or ed.pending_edge or ed.chain_stage or ed.pending_place or ed.pending_tack or ed.dart_base:
            panel = layout.panel
            message = ed.confirm_message if ed.confirm_action else ed.message
            self.text(panel.x + 76 * scale, panel.y + 28 * scale, message, 11, TEXT_SUB, max_width=panel.w - 360 * scale)
        elif getattr(ed, 'error_message', None):
            panel = layout.panel
            width = min(460 * scale, max(120 * scale, panel.w - 360 * scale))
            toast = Rect(panel.x + 76 * scale, panel.y + 15 * scale, width, 30 * scale)
            self.round_rect(toast, (.45, .12, .12, .96), radius=12)
            self.text(toast.x + 12 * scale, toast.y + 10 * scale, ed.error_message, 10, (1.0, .85, .85, 1.0), max_width=toast.w - 24 * scale)
        elif ed.message:
            if getattr(ed, 'toast_text', None) != ed.message:
                ed.toast_text = ed.message
                ed.toast_until = time.monotonic() + 3
            if time.monotonic() < getattr(ed, 'toast_until', 0):
                panel = layout.panel
                width = min(420 * scale, max(80 * scale, panel.w - 390 * scale))
                toast = Rect(panel.x + 76 * scale, panel.y + 15 * scale, width, 30 * scale)
                self.round_rect(toast, (.105, .11, .115, .96), radius=12)
                self.text(toast.x + 12 * scale, toast.y + 10 * scale, ed.toast_text, 10, TEXT_SUB, max_width=toast.w - 24 * scale)
        panel = layout.panel
        hint_clear = not any(rect.y <= panel.y + 78 * scale and rect.y + rect.h >= panel.y + 60 * scale
                             for rect, title, controls in cards)
        if panel.w > 850 * scale and not ed.confirm_action and hint_clear:
            self.text(panel.x + 90 * scale, panel.y + 65 * scale, ed.tool_hint(), 11, MUTED,
                      max_width=panel.w - 440 * scale)
        if tooltip and not any(card[0].contains(*ed.pointer) for card in cards):
            ComponentRenderer.draw_tooltip(self, Tooltip(text=tooltip[0], shortcut=tooltip[1], pos=tooltip[2], visible=True), scale)
        if card_tooltip:
            ComponentRenderer.draw_tooltip(self, card_tooltip, scale)

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

    def rulers(self, ed):
        l, v = ed.canvas_layout, ed.view
        c, p, s = l.canvas, l.panel, self.s
        self.rect(l.ruler_top, (0.09, 0.11, 0.13, 1.0))
        self.rect(l.ruler_left, (0.09, 0.11, 0.13, 1.0))
        step = grid_step(v.zoom)
        low, high = v.world((c.x, c.y), c), v.world((c.x + c.w, c.y + c.h), c)
        self.clip(l.ruler_top)
        for i in range(math.floor(low[0] / step), math.ceil(high[0] / step) + 1):
            x = v.screen((i * step, 0), c)[0]
            self.lines([(x, l.ruler_top.y), (x, l.ruler_top.y + 4 * s)], MUTED)
            self.text(x + 3 * s, l.ruler_top.y + 6 * s, f"{i * step * 100:g}", 8, MUTED)
        self.clip(l.ruler_left)
        for i in range(math.floor(low[1] / step), math.ceil(high[1] / step) + 1):
            y = v.screen((0, i * step), c)[1]
            self.text(l.ruler_left.x + 2 * s, y + 2 * s, f"{i * step * 100:g}", 8, MUTED, max_width=18 * s)
        self.clip(p)
        corner = Rect(l.ruler_left.x, l.ruler_top.y, l.ruler_left.w, l.ruler_top.h)
        self.rect(corner, (0.08, 0.10, 0.12, 1.0))
        self.lines([(corner.x, corner.y), (corner.x + corner.w, corner.y)], BORDER_SUBTLE)
        self.lines([(corner.x + corner.w, corner.y), (corner.x + corner.w, corner.y + corner.h)], BORDER_SUBTLE)
        self.text(corner.x + corner.w / 2, corner.y + 7 * s, "cm", 8, ACCENT, center=True)

    def seams(self, ed):
        doc = ed.session.document
        c = ed.canvas_layout.canvas
        for index, seam in enumerate(doc.seams):
            mids = []
            selected = ed.seam_selected == seam.id
            mismatch = doc.seam_stats(seam)[3] > 1
            color = (1, 0.67, 0.31, 1) if selected or mismatch else (0.83, 0.48, 0.75, 0.85)
            if ed.minimal_ui:
                color = (1, .67, .31, 1) if selected or mismatch else (.28, .65, .63, .85)
            for side in (0, 1):
                chain = seam.side(side)
                total = doc.chain_length(chain)
                n = max(8, min(160, int(total * ed.view.zoom / 8)))
                points = []
                for i in range(n + 1):
                    edge, fraction = doc.chain_position(chain, i / n)
                    points.append(ed.view.screen(doc.edge_point(edge, fraction), c))
                self.lines(points, color, 3, True)
                first = points[-1] if side == 1 and seam.reverse else points[0]
                self.dot(first, 5, color)
                middle = points[len(points) // 2]
                mids.append(middle)
                if ed.tool == 'SEW' and not ed.minimal_ui:
                    self.text(middle[0] + 8 * self.s, middle[1] + 8 * self.s, str(index + 1), 11, color)
            if ed.tool == 'SEW' or ed.minimal_ui:
                a, b = mids
                steps = max(2, int(math.dist(a, b) / (10 * self.s)))
                for i in range(0, steps, 2):
                    self.lines([curves.mix(a, b, i / steps), curves.mix(a, b, min(i + 1, steps) / steps)], (*color[:3], 0.35))
        for edge in ed.chain_a + ed.chain_b:
            points = [ed.view.screen(doc.edge_point(edge, edge.t0 + (edge.t1-edge.t0) * i / 16), c) for i in range(17)]
            self.lines(points, (1, 0.82, 0.3, 1), 3, True)
        if ed.tool == 'SEW':
            h_edge = ed.design_hit_edge()
            if ed.pending_edge:
                edge_a = ed.pending_edge
                pts_a = [ed.view.screen(doc.edge_point(edge_a, edge_a.t0 + (edge_a.t1 - edge_a.t0) * i / 16), c) for i in range(17)]
                self.lines(pts_a, (1, 0.82, 0.3, 1), 3.2, True)
                self.dot(pts_a[0], 5.5, (1, 0.82, 0.3, 1))
                mid_a = pts_a[8]
                if h_edge and (h_edge.pattern != edge_a.pattern or h_edge.edge != edge_a.edge):
                    len_a = doc.chain_length([edge_a]) * 100
                    len_b = doc.chain_length([h_edge]) * 100
                    diff = abs(len_a - len_b)
                    is_match = diff <= 0.6
                    prev_col = (0.22, 0.82, 0.48, 0.95) if is_match else (1.0, 0.65, 0.25, 0.95)
                    pts_b = [ed.view.screen(doc.edge_point(h_edge, h_edge.t0 + (h_edge.t1 - h_edge.t0) * i / 16), c) for i in range(17)]
                    self.lines(pts_b, prev_col, 3.2, True)
                    rev = bool(ed._scene.dd_sew_reverse)
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
            elif not ed.chain_stage and h_edge:
                pts_h = [ed.view.screen(doc.edge_point(h_edge, h_edge.t0 + (h_edge.t1 - h_edge.t0) * i / 16), c) for i in range(17)]
                self.lines(pts_h, (0.35, 0.75, 0.95, 0.75), 2.5, True)
                self.dot(pts_h[0], 4.5, (0.35, 0.75, 0.95, 0.75))
        elif ed.pending_edge:
            points = [ed.view.screen(doc.edge_point(ed.pending_edge, ed.pending_edge.t0 + (ed.pending_edge.t1-ed.pending_edge.t0) * i / 16), c) for i in range(17)]
            self.lines(points, (1, 0.82, 0.3, 1), 3, True)
        for edge, t in ed.free_clicks + ed.dart_base:
            self.dot(ed.view.screen(doc.edge_point(edge, t), c), 6, (1, 0.82, 0.3, 1))

    def settings(self, ed):
        inspector = ed.inspector
        if inspector is None:
            return
        s = self.s
        r = inspector.rect
        self.clip(r)
        self.rect(r, INSPECTOR)
        self.lines([(r.x, r.y), (r.x, r.y + r.h)], BORDER)
        if inspector.tab == 'ALL':
            field = inspector.search
            self.round_rect(field, FIELD_BG, radius=6)
            self.round_rect_outline(field, ACCENT_BORDER if ed.search_active else BORDER_SUBTLE, radius=6, width=1)
            text = ed.search_query + ('|' if ed.search_active else '') if ed.search_query or ed.search_active else 'Find any action or setting...'
            self.text(field.x + 8 * s, field.y + 9 * s, text, 10,
                      TEXT if ed.search_active or ed.search_query else MUTED, max_width=field.w - 16 * s)

        tab_items = list(inspector.tabs.items())
        if tab_items:
            first_tab = tab_items[0][1]
            last_tab = tab_items[-1][1]
            seg_w = (last_tab.x + last_tab.w) - first_tab.x
            seg_box = Rect(first_tab.x - 2 * s, first_tab.y + 3 * s, seg_w + 4 * s, first_tab.h - 6 * s)
            self.round_rect(seg_box, (0.08, 0.10, 0.13, 0.95), radius=7)
            self.round_rect_outline(seg_box, BORDER_SUBTLE, radius=7, width=0.8)

            for name, tab in tab_items:
                active = name == ed.inspector_tab
                hover = tab.contains(*ed.pointer)
                pill = Rect(tab.x, tab.y + 4 * s, tab.w, tab.h - 8 * s)
                if active:
                    self.round_rect(pill, ELEVATED, radius=5)
                    self.round_rect_outline(pill, ACCENT_BORDER, radius=5, width=0.8)
                elif hover:
                    self.round_rect(pill, (0.16, 0.20, 0.24, 0.7), radius=5)
                color = ACCENT if active else (TEXT if hover else TEXT_SECONDARY)
                self.text(pill.x + pill.w / 2, pill.y + 6 * s, name.title(), 9, color, True, max_width=pill.w - 4 * s)

            self.lines([(r.x, first_tab.y - 2 * s), (r.x + r.w, first_tab.y - 2 * s)], BORDER_SUBTLE)

        self.clip(inspector.content)
        cr = inspector.content
        pending_tooltip = None
        for item in inspector.controls:
            box = item.rect
            if box.y > cr.y + cr.h or box.y + box.h < cr.y:
                continue

            if item.kind == 'obj_h':
                swatch_box = Rect(box.x, box.y + 18 * s, 14 * s, 14 * s)
                self.round_rect(swatch_box, (*item.swatch, 0.4), radius=4)
                self.round_rect_outline(swatch_box, (*item.swatch, 1.0), radius=4, width=1.4)
                self.text(box.x + 22 * s, box.y + 18 * s, item.label, 15, TEXT)
                self.text(box.x + 22 * s, box.y + 4 * s, item.meta, 10, MUTED)
            elif item.kind == 'field_pair':
                hw = (box.w - 8 * s) / 2
                for fx, lab, key in [(box.x, item.label, item.key), (box.x + hw + 8 * s, item.sub, item.meta)]:
                    card_r = Rect(fx, box.y + 4 * s, hw, 48 * s)
                    editing = ed.numeric and ed.numeric['key'] == key
                    self.round_rect(card_r, (0.15, 0.26, 0.28, 1.0) if editing else FIELD_BG, radius=7)
                    self.round_rect_outline(card_r, ACCENT_BORDER if editing else BORDER_SUBTLE, radius=7, width=1)
                    self.text(card_r.x + 10 * s, card_r.y + 30 * s, lab, 9, MUTED)
                    spec = SETTINGS[key]
                    val_str = ed.numeric['text'] if editing else spec.format(getattr(ed._scene, key))
                    self.text(card_r.x + 10 * s, card_r.y + 12 * s, val_str, 13, TEXT)
                    self.text(card_r.x + card_r.w - 24 * s, card_r.y + 12 * s, spec.unit, 10, MUTED)
            elif item.kind == 'preset_chips':
                pattern = ed.session.document.find(ed.session.selected)
                active_preset = pattern.preset.upper() if pattern else None
                for chip_r, chip_act, chip_lbl in getattr(item, 'chips', []):
                    p_name = chip_act.replace('SET_PRESET_', '')
                    is_active = (p_name == active_preset)
                    disabled = bool(ed.action_blocker(chip_act))
                    hover = chip_r.contains(*ed.pointer) and not disabled
                    if is_active:
                        self.round_rect(chip_r, ACCENT_BG, radius=5)
                        self.round_rect_outline(chip_r, ACCENT_BORDER, radius=5, width=1.0)
                    elif hover:
                        self.round_rect(chip_r, ELEVATED, radius=5)
                        self.round_rect_outline(chip_r, BORDER_SUBTLE, radius=5, width=0.8)
                    else:
                        self.round_rect(chip_r, (0.12, 0.15, 0.18, 1.0), radius=5)
                        self.round_rect_outline(chip_r, BORDER_SUBTLE, radius=5, width=0.8)
                    color = MUTED if disabled else ACCENT if is_active else (TEXT if hover else TEXT_SUB)
                    self.text(chip_r.x + chip_r.w / 2, chip_r.y + 6 * s, chip_lbl, 9, color, center=True)
            elif item.kind == 'pair_buttons':
                for btn_rect, btn_key, btn_lbl in (item.btn_a, item.btn_b):
                    disabled = bool(ed.action_blocker(btn_key))
                    hover = btn_rect.contains(*ed.pointer) and not disabled
                    self.round_rect(btn_rect, (0.18, 0.23, 0.28, 1.0) if hover else ELEVATED, radius=7)
                    self.round_rect_outline(btn_rect, BORDER, radius=7, width=1)
                    self.text(btn_rect.x + btn_rect.w / 2, btn_rect.y + 8 * s, btn_lbl, 10, MUTED if disabled else TEXT if hover else TEXT_SUB, True)
            elif item.kind == 'fold':
                opened = item.key in ed.inspector_sections or bool(ed.search_query)
                self.round_rect(Rect(box.x, box.y + 3 * s, box.w, box.h - 6 * s), ELEVATED, radius=6)
                self.text(box.x + 8 * s, box.y + 13 * s, ('- ' if opened else '+ ') + item.label,
                          11, ACCENT if opened else TEXT_SUB, max_width=box.w - 16 * s)
            elif item.kind in {'title', 'section'}:
                self.text(box.x, box.y + 9 * s, item.label, 11 if item.kind == 'title' else 9, ACCENT if item.kind == 'title' else MUTED)
                if item.kind == 'section':
                    self.lines([(box.x, box.y + 26 * s), (box.x + box.w, box.y + 26 * s)], BORDER_SUBTLE)
            elif item.kind in {'number', 'text'}:
                self.text(box.x, box.y + 36 * s, item.label, 10, TEXT_SUB, max_width=box.w)
                spec = SETTINGS[item.key]
                field = item.value_rect
                editing = ed.numeric and ed.numeric['key'] == item.key
                self.round_rect(field, (0.16, 0.27, 0.29, 1.0) if editing else FIELD_BG, radius=6)
                self.round_rect_outline(field, ACCENT_BORDER if editing else BORDER_SUBTLE, radius=6, width=1)
                text = ed.numeric['text'] if editing else spec.display(getattr(ed._scene, item.key))
                if editing and ed.numeric['selected']:
                    self.rect(Rect(field.x + 4 * s, field.y + 4 * s, field.w - 8 * s, field.h - 8 * s), (0.23, 0.39, 0.45, 1.0))
                self.text(field.x + 8 * s, field.y + 8 * s, text if editing else text + ' ' + spec.unit, 11, TEXT, max_width=field.w - 12 * s)
                if editing and not ed.numeric['selected']:
                    blf.size(0, 11 * s)
                    cursor_x = field.x + 8 * s + blf.dimensions(0, text[:ed.numeric['cursor']])[0]
                    if cursor_x < field.x + field.w - 3 * s:
                        self.lines([(cursor_x, field.y + 5 * s), (cursor_x, field.y + 20 * s)], ACCENT)
                for button, label in ((item.minus, '-'), (item.plus, '+')):
                    if button is None:
                        continue
                    b_hover = button.contains(*ed.pointer)
                    self.round_rect(button, ELEVATED if b_hover else (0.12, 0.16, 0.20, 1.0), radius=5)
                    self.round_rect_outline(button, BORDER_SUBTLE, radius=5, width=1)
                    self.text(button.x + button.w / 2, button.y + 7 * s, label, 12, TEXT, True)
            elif item.kind == 'body':
                self.text(box.x, box.y + 36 * s, item.label, 10, TEXT_SUB)
                field = item.value_rect
                self.round_rect(field, FIELD_BG, radius=6)
                self.round_rect_outline(field, BORDER_SUBTLE, radius=6, width=1)
                obj = ed._scene.dd_avatar
                self.text(field.x + 8 * s, field.y + 9 * s, obj.name if obj else 'Choose body mesh...', 10, TEXT, max_width=field.w - 25 * s)
                self.text(field.x + field.w - 14 * s, field.y + 9 * s, 'v', 10, MUTED, True)
            elif item.kind == 'button':
                field = Rect(box.x, box.y + 3 * s, box.w, 28 * s)
                disabled = bool(ed.action_blocker(item.key)) or (item.key == 'DEMO' and bool(ed.session.document.patterns))
                b_hover = field.contains(*ed.pointer) and not disabled
                self.round_rect(field, ELEVATED if b_hover else (0.12, 0.16, 0.20, 1.0), radius=7)
                self.round_rect_outline(field, BORDER, radius=7, width=1)
                self.text(field.x + field.w / 2, field.y + 8 * s, item.label, 10, MUTED if disabled else TEXT, True, max_width=field.w - 10 * s)
                if disabled and field.contains(*ed.pointer):
                    reason = ed.action_blocker(item.key) or 'The demo needs an empty document.'
                    pending_tooltip = Tooltip(text=reason, shortcut='',
                                              pos=(field.x, field.y + field.h + 8 * s), visible=True)
            elif item.kind == 'cycle':
                self.text(box.x, box.y + 11 * s, item.label, 10, TEXT_SUB, max_width=box.w - 75 * s)
                chip = Rect(box.x + box.w - 75 * s, box.y + 4 * s, 75 * s, 26 * s)
                self.round_rect(chip, ELEVATED, radius=6)
                self.round_rect_outline(chip, BORDER, radius=6, width=1)
                pattern = ed.session.document.find(ed.session.selected)
                value = ed._scene.dd_reference_view.title() if item.key == 'REFERENCE_VIEW' else pattern.preset.title() if pattern else 'Select'
                self.text(chip.x + chip.w / 2, chip.y + 8 * s, value + ' >', 10, ACCENT, True, max_width=chip.w - 4 * s)
            elif item.kind == 'toggle':
                self.text(box.x, box.y + 11 * s, item.label, 10, TEXT_SUB, max_width=box.w - 48 * s)
                active = getattr(ed._scene, item.key)
                chip = Rect(box.x + box.w - 44 * s, box.y + 4 * s, 44 * s, 25 * s)
                self.round_rect(chip, ACCENT_BG if active else (0.12, 0.16, 0.20, 1.0), radius=6)
                self.round_rect_outline(chip, ACCENT_BORDER if active else BORDER_SUBTLE, radius=6, width=1)
                self.text(chip.x + chip.w / 2, chip.y + 7 * s, 'On' if active else 'Off', 10, ACCENT if active else MUTED, True)
            elif item.kind == 'seam':
                seam = next((seam for seam in ed.session.document.seams if seam.id == item.key), None)
                if seam is None:
                    continue
                a, b = ed.session.document.find(seam.a.pattern), ed.session.document.find(seam.b.pattern)
                card_r = Rect(box.x, box.y + 2 * s, box.w, box.h - 4 * s)
                self.round_rect(card_r, FIELD_BG, radius=7)
                self.round_rect_outline(card_r, BORDER_SUBTLE, radius=7, width=1)
                self.text(card_r.x + 8 * s, card_r.y + 42 * s, f"{item.label}. {a.name}", 10, ACCENT if ed.seam_selected == item.key else TEXT, max_width=card_r.w - 74 * s)
                self.text(card_r.x + 8 * s, card_r.y + 27 * s, b.name, 9, MUTED, max_width=card_r.w - 74 * s)
                lengths = ed.session.document.seam_stats(seam)
                self.text(card_r.x + 8 * s, card_r.y + 9 * s, f"{lengths[0] * 100:.1f} / {lengths[1] * 100:.1f} cm ({lengths[3]:.1f}%)", 9, (1, 0.72, 0.31, 1) if lengths[3] > 1 else MUTED, max_width=card_r.w - 10 * s)
                for rect, lbl in [(Rect(card_r.x + card_r.w - 68 * s, card_r.y + 6 * s, 40 * s, 28 * s), 'Flip'),
                                   (Rect(card_r.x + card_r.w - 24 * s, card_r.y + 6 * s, 22 * s, 28 * s), 'X')]:
                    self.round_rect(rect, ELEVATED, radius=5)
                    self.round_rect_outline(rect, BORDER, radius=5, width=1)
                    self.text(rect.x + rect.w / 2, rect.y + 9 * s, lbl, 9, TEXT, True)
            elif item.kind == 'info':
                first, second = ed.design_info(item.key)
                self.text(box.x, box.y + 34 * s, first, 10, TEXT, max_width=box.w)
                self.text(box.x, box.y + 15 * s, second, 9, MUTED, max_width=box.w)
            elif item.kind == 'hint':
                self.text(box.x, box.y + 10 * s, item.label, 9, MUTED, max_width=box.w)

        if inspector.max_scroll:
            self.round_rect(inspector.scrollbar, (0.11, 0.14, 0.18, 1.0), radius=2)
            self.round_rect(inspector.thumb, (0.35, 0.44, 0.50, 1.0), radius=2)
        if pending_tooltip:
            self.clip(r)
            ComponentRenderer.draw_tooltip(self, pending_tooltip, s)

    def body_picker(self, ed):
        menu = ed.body_menu
        if menu is None:
            return
        self.clip(menu.rect)
        self.round_rect(menu.rect, CHROME, radius=8)
        self.round_rect_outline(menu.rect, BORDER, radius=8, width=1.2)
        for r, obj, label in menu.rows:
            selected = obj == ed._scene.dd_avatar
            if r.contains(*ed.pointer) or selected:
                self.round_rect(r, ACCENT_BG if selected else ELEVATED, radius=5)
            self.text(r.x + 8 * self.s, r.y + 10 * self.s, label, 10, ACCENT if selected else TEXT, max_width=r.w - 16 * self.s)

    def body_reference(self, ed):
        scene = ed._scene
        reference = ed.reference
        if not scene.dd_reference_visible or not reference.vertices or scene.dd_reference_opacity <= 0:
            return
        if self.reference_revision != reference.revision:
            self.reference_batch = batch_for_shader(self.shader, 'TRIS', {'pos': reference.vertices}, indices=reference.triangles)
            self.reference_revision = reference.revision
        alpha = scene.dd_reference_opacity
        tint = (0.48, 0.56, 0.64)
        color = tuple(BG[i] * (1 - alpha) + tint[i] * alpha for i in range(3)) + (1,)
        origin = ed.view.screen((scene.dd_reference_x, scene.dd_reference_y), ed.canvas_layout.canvas)
        zoom = ed.view.zoom
        transform = Matrix(((zoom, 0, 0, origin[0]), (0, zoom, 0, origin[1]), (0, 0, 1, 0), (0, 0, 0, 1)))
        with gpu.matrix.push_pop():
            gpu.matrix.multiply_matrix(transform)
            self.shader.bind()
            self.shader.uniform_float('color', color)
            self.reference_batch.draw(self.shader)
        c = ed.canvas_layout.canvas
        height = reference.bounds[1][1] - reference.bounds[0][1]
        self.text(c.x + 10 * self.s, c.y + c.h - 18 * self.s,
                  f"{scene.dd_reference_view.title()} body reference / {height * 100:.1f} cm", 9, MUTED, max_width=c.w - 20 * self.s)
