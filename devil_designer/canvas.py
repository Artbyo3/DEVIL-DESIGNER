"""Viewport-local layout shared by drawing and input handling."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    def contains(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h


def clamp_window(bounds, available, scale):
    """Keep every window edge accessible after dragging, resizing, or changing monitors."""
    x, y, w, h = bounds
    minimum_w = min(420 * scale, available.w)
    minimum_h = min(420 * scale, available.h)
    w = min(available.w, max(minimum_w, w))
    h = min(available.h, max(minimum_h, h))
    x = max(available.x, min(available.x + available.w - w, x))
    y = max(available.y, min(available.y + available.h - h, y))
    return Rect(x, y, w, h)


class Layout:
    def __init__(self, width, height, scale=1.0, full=False, left=0, right=0, top=0, bottom=0,
                 position=None, settings=False, stage="DRAFT"):
        self.scale = s = scale
        self.full = full
        self.stage = stage
        self.settings = settings
        usable_h = max(1.0, height - top - bottom)
        usable_w = max(1.0, width - left - right)
        margin = min(12 * s, usable_w / 20, usable_h / 20)
        self.available = available = Rect(left + margin, bottom + margin,
                                         max(1.0, usable_w - 2 * margin), max(1.0, usable_h - 2 * margin))
        if full:
            self.panel = available
        else:
            w = min(available.w, max(620 * s, available.w * .65))
            h = min(available.h, max(440 * s, available.h * .86))
            default = (available.x + available.w - w, available.y + (available.h - h) / 2, w, h)
            self.panel = clamp_window(position or default, available, s)
        p = self.panel

        inspector_w = min(248 * s, p.w * 0.40) if settings else 0
        content_w = max(1.0, p.w - inspector_w)
        self.header = Rect(p.x, p.y + p.h - 54 * s, p.w, 54 * s)
        self.inspector = Rect(p.x + content_w, p.y + 48 * s, inspector_w, max(1.0, p.h - 102 * s)) if settings else None
        if self.inspector:
            self.inspector_head = Rect(self.inspector.x, self.inspector.y + self.inspector.h - 48 * s, self.inspector.w, 48 * s)
            self.inspector_foot = Rect(self.inspector.x, self.inspector.y, self.inspector.w, 64 * s)
            self.inspector_content = Rect(self.inspector.x, self.inspector.y + 64 * s,
                                          self.inspector.w, max(1.0, self.inspector.h - 112 * s))
        else:
            self.inspector_head = self.inspector_foot = self.inspector_content = None

        self.toolbar = Rect(p.x, self.header.y - 68 * s, content_w, 68 * s)
        self.workflow = Rect(p.x, self.toolbar.y - 36 * s, content_w, 36 * s)
        self.utility = Rect(p.x, self.workflow.y - 30 * s, content_w, 30 * s)
        self.viewbar = self.toolbar
        self.footer = Rect(p.x, p.y, p.w, 48 * s)
        self.rail = Rect(p.x, self.footer.y + self.footer.h, 25 * s, max(1.0, p.h - 261 * s))
        self.canvas = Rect(p.x + 25 * s, self.footer.y + self.footer.h,
                           max(1.0, content_w - 25 * s), max(1.0, p.h - 261 * s))
        self.ruler_top = Rect(self.canvas.x, self.canvas.y + self.canvas.h, self.canvas.w, 25 * s)
        self.ruler_left = Rect(p.x, self.canvas.y, 25 * s, self.canvas.h)
        self.resize = Rect(p.x + p.w - 18 * s, p.y, 18 * s, 18 * s)

        # Register non-overlapping interactive buttons
        self.buttons = {}

        # 1. Header controls: close, full, settings, library, and 4 workflow stage pills
        h_right_specs = [
            ("CLOSE", "X", 26),
            ("FULL", "Restore" if full else "Expand", 54),
            ("SETTINGS", "...", 32),
            ("LIBRARY", "Library", 62),
        ]
        h_factor = min(1.0, max(0.35, (p.w * 0.45) / (sum(w + 4 for _, _, w in h_right_specs) * s)))
        hx = p.x + p.w - 6 * s
        for name, label, bw in h_right_specs:
            w_act = bw * s * h_factor
            hx -= (w_act + 4 * s)
            self.buttons[name] = (Rect(hx, self.header.y + 14 * s, w_act, 28 * s), label)

        # Stage pills in header
        brand_w = min(120 * s, max(36 * s, p.w * 0.22))
        pill_avail = max(40 * s, hx - (p.x + brand_w + 10 * s))
        pills = [
            ("STAGE_DRAFT", "01 Draft"),
            ("STAGE_SEW", "02 Sew"),
            ("STAGE_ARRANGE", "03 Arrange"),
            ("STAGE_SIMULATE", "04 Simulate"),
        ]
        step_factor = min(1.0, pill_avail / (4 * 72 * s))
        step_w = 70 * s * step_factor
        step_start = p.x + brand_w + 8 * s + (pill_avail - 4 * (step_w + 2 * s)) / 2
        for i, (name, label) in enumerate(pills):
            px = step_start + i * (step_w + 2 * s)
            self.buttons[name] = (Rect(px, self.header.y + 13 * s, step_w, 30 * s), label)

        # 2. Toolbar & workflow buttons (preserving exact button_row structure from b3dd195)
        self.button_row([('SELECT', 'Select V', 70), ('POLYGON', 'Polygon P', 75),
                         ('RECTANGLE', 'Rect R', 62), ('ELLIPSE', 'Ellipse E', 72)], self.toolbar, 37, 26)
        self.button_row([('INTERNAL', 'Internal I', 75), ('SEW', 'Sew J', 62),
                         ('PIN', 'Pin K', 62), ('TACK', 'Tack T', 62), ('DART', 'Dart D', 62)], self.toolbar, 6, 26)
        self.button_row([('BUILD', 'Build 3D', 70), ('ARRANGE', 'Arrange', 62), ('SIMULATE', 'Simulate', 65),
                         ('STOP', 'Stop', 39), ('RESET', 'Reset', 44), ('KEEP', 'Keep mesh', 74)], self.workflow, 5, 26)
        self.button_row([('SNAP', 'Snap S', 58), ('FIT', 'Fit F', 45), ('REFERENCE', 'Body H', 58),
                         ('LENGTHS', 'Lengths L', 70), ('UNDO', '<', 24), ('REDO', '>', 24)], self.utility, 3, 24)

    def button_row(self, specs, region, offset, height):
        s = self.scale
        factor = min(1.0, max(0.05, (region.w - 24 * s) / (sum(item[2] + 5 for item in specs) * s)))
        x = region.x + 12 * s
        for name, label, units in specs:
            self.buttons[name] = (Rect(x, region.y + offset * s, units * s * factor, height * s), label)
            x += (units + 5) * s * factor

    def button(self, x, y):
        return next((name for name, (r, _) in self.buttons.items() if r.contains(x, y)), None)


class View:
    def __init__(self):
        self.cx = self.cy = 0.0
        self.zoom = 800.0

    def screen(self, point, rect):
        return (rect.x + rect.w / 2 + (point[0] - self.cx) * self.zoom,
                rect.y + rect.h / 2 + (point[1] - self.cy) * self.zoom)

    def world(self, point, rect):
        return ((point[0] - rect.x - rect.w / 2) / self.zoom + self.cx,
                (point[1] - rect.y - rect.h / 2) / self.zoom + self.cy)

    def pan(self, dx, dy):
        self.cx -= dx / self.zoom
        self.cy -= dy / self.zoom

    def zoom_at(self, point, rect, factor):
        before = self.world(point, rect)
        self.zoom = min(80000, max(20, self.zoom * factor))
        after = self.world(point, rect)
        self.cx += before[0] - after[0]
        self.cy += before[1] - after[1]

    def fit(self, points, rect):
        if not points:
            self.cx = self.cy = 0
            self.zoom = min(rect.w, rect.h) / .65
            return
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self.cx, self.cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        self.zoom = min(80000, max(20, min(rect.w / max(.03, max(xs) - min(xs)),
                                       rect.h / max(.03, max(ys) - min(ys))) * .72))


def grid_step(zoom):
    target = 55 / zoom
    power = 10 ** math.floor(math.log10(target))
    return next(v * power for v in (1, 2, 5, 10) if v * power >= target)
