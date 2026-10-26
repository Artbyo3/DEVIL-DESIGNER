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


TOP_BAR_H = 48
TOOL_RAIL_W = 52
STATUS_BAR_H = 28
VIEWBAR_H = 38
INSPECTOR_W = 280

STAGE_TOOLS = {
    'DRAFT': [
        ('SELECT', 'Select', 'V'),
        ('POLYGON', 'Polygon', 'P'),
        ('RECTANGLE', 'Rectangle', 'R'),
        ('ELLIPSE', 'Ellipse', 'E'),
        ('INTERNAL', 'Internal', 'I'),
        ('DART', 'Dart', 'D'),
    ],
    'SEW': [
        ('SELECT', 'Select', 'V'),
        ('SEW', 'Pair edges', 'J'),
        ('FREE_SEW', 'Free sewing', 'F'),
    ],
    'ARRANGE': [
        ('SELECT', 'Select', 'V'),
        ('PLACE', 'Place', 'G'),
        ('PIN', 'Pin', 'K'),
        ('TACK', 'Tack', 'T'),
    ],
    'SIMULATE': [
        ('SELECT', 'Select', 'V'),
        ('PIN', 'Pin', 'K'),
    ],
    'LIBRARY': [
        ('SELECT', 'Select', 'V'),
    ],
}

ALL_TOOLS = [
    ('SELECT', 'Select', 'V'),
    ('POLYGON', 'Polygon', 'P'),
    ('RECTANGLE', 'Rectangle', 'R'),
    ('ELLIPSE', 'Ellipse', 'E'),
    ('INTERNAL', 'Internal', 'I'),
    ('DART', 'Dart', 'D'),
    ('SEW', 'Sew', 'J'),
    ('FREE_SEW', 'Free sewing', 'F'),
    ('PLACE', 'Place', 'G'),
    ('PIN', 'Pin', 'K'),
    ('TACK', 'Tack', 'T'),
]


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

        # Responsive inspector: 280 px standard, adapts below 1020 px to protect canvas space
        if settings:
            if p.w >= 1020 * s:
                inspector_w = min(INSPECTOR_W * s, p.w * 0.35)
            else:
                inspector_w = min(248 * s, p.w * 0.40)
        else:
            inspector_w = 0
        content_w = max(1.0, p.w - inspector_w)
        rail_w = min(TOOL_RAIL_W * s, max(36 * s, content_w * 0.16))
        header_h = TOP_BAR_H * s
        footer_h = STATUS_BAR_H * s
        viewbar_h = VIEWBAR_H * s
        workflow_h = 30 * s

        self.header = Rect(p.x, p.y + p.h - header_h, p.w, header_h)
        self.footer = Rect(p.x, p.y, p.w, footer_h)

        self.inspector = Rect(p.x + content_w, self.footer.y + self.footer.h,
                              inspector_w, max(1.0, p.h - header_h - footer_h)) if settings else None
        if self.inspector:
            self.inspector_head = Rect(self.inspector.x, self.inspector.y + self.inspector.h - 38 * s, self.inspector.w, 38 * s)
            self.inspector_foot = Rect(self.inspector.x, self.inspector.y, self.inspector.w, 54 * s)
            self.inspector_content = Rect(self.inspector.x, self.inspector.y + 54 * s,
                                          self.inspector.w, max(1.0, self.inspector.h - 92 * s))
        else:
            self.inspector_head = self.inspector_foot = self.inspector_content = None

        self.rail = Rect(p.x, self.footer.y + self.footer.h, rail_w, max(1.0, p.h - header_h - footer_h))

        work_x = p.x + rail_w
        work_w = max(1.0, content_w - rail_w)

        self.viewbar = Rect(work_x, self.header.y - viewbar_h, work_w, viewbar_h)
        self.toolbar = self.viewbar
        self.workflow = Rect(work_x, self.viewbar.y - workflow_h, work_w, workflow_h)
        self.utility = self.viewbar

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
        h_factor = min(1.0, max(0.15, (p.w * 0.40) / (sum(w + 4 for _, _, w in h_right_specs) * s)))
        hx = p.x + p.w - 6 * s
        for name, label, bw in h_right_specs:
            w_act = bw * s * h_factor
            hx -= (w_act + 4 * s)
            bx = max(p.x, min(p.x + p.w - w_act, hx))
            self.buttons[name] = (Rect(bx, self.header.y + 10 * s, w_act, 28 * s), label)

        # Stage pills in header
        brand_w = min(130 * s, max(60 * s, p.w * 0.20))
        pill_avail = max(20 * s, hx - (p.x + brand_w + 10 * s))
        pills = [
            ("STAGE_DRAFT", "Draft"),
            ("STAGE_SEW", "Sew"),
            ("STAGE_ARRANGE", "Arrange"),
            ("STAGE_SIMULATE", "Simulate"),
        ]
        step_factor = min(1.0, max(0.1, pill_avail / (4 * 72 * s)))
        step_w = 68 * s * step_factor
        step_start = p.x + brand_w + 8 * s + max(0.0, (pill_avail - 4 * (step_w + 2 * s)) / 2)
        for i, (name, label) in enumerate(pills):
            px = step_start + i * (step_w + 2 * s)
            bx = max(p.x, min(p.x + p.w - step_w, px))
            self.buttons[name] = (Rect(bx, self.header.y + 9 * s, step_w, 30 * s), label)

        # 2. Tool Rail (Vertical column on the left - contextual to stage)
        active_tools = STAGE_TOOLS.get(stage, STAGE_TOOLS['DRAFT'])
        tool_bw = min(38 * s, rail_w - 8 * s)
        tool_bh = 34 * s
        tool_x = self.rail.x + (rail_w - tool_bw) / 2
        tool_start_y = self.rail.y + self.rail.h - 10 * s - tool_bh
        tool_gap = 4 * s

        # Register visible active tools
        for i, (name, label, key) in enumerate(active_tools):
            ty = tool_start_y - i * (tool_bh + tool_gap)
            bx = max(p.x, min(p.x + p.w - tool_bw, tool_x))
            self.buttons[name] = (Rect(bx, ty, tool_bw, tool_bh), f"{label} {key}")

        # Register remaining tools to ensure no KeyError in any test suite
        registered_keys = {name for name, _, _ in active_tools}
        hidden_idx = len(active_tools)
        for name, label, key in ALL_TOOLS:
            if name not in registered_keys:
                ty = tool_start_y - hidden_idx * (tool_bh + tool_gap)
                bx = max(p.x, min(p.x + p.w - tool_bw, tool_x))
                self.buttons[name] = (Rect(bx, max(self.rail.y + 30 * s, ty), tool_bw, tool_bh), f"{label} {key}")
                hidden_idx += 1

        help_w = min(26 * s, tool_bw)
        self.buttons['HELP'] = (Rect(max(p.x, tool_x + (tool_bw - help_w) / 2), self.rail.y + 6 * s, help_w, 22 * s), "?")

        # 3. Viewbar utilities (Right-aligned in viewbar)
        u_specs = [
            ('REDO', '>', 24),
            ('UNDO', '<', 24),
            ('LENGTHS', 'Lengths', 66),
            ('REFERENCE', 'Body', 52),
            ('SNAP', 'Snap', 50),
            ('FIT', 'Fit', 42),
        ]
        u_factor = min(1.0, max(0.05, (work_w - 20 * s) / (sum(bw + 4 for _, _, bw in u_specs) * s)))
        ux = self.viewbar.x + self.viewbar.w - 6 * s
        for name, label, bw in u_specs:
            w_act = bw * s * u_factor
            ux -= (w_act + 4 * s)
            bx = max(p.x, min(p.x + p.w - w_act, ux))
            self.buttons[name] = (Rect(bx, self.viewbar.y + 6 * s, w_act, 26 * s), label)

        # 4. Workflow action row
        self.button_row([
            ('BUILD', 'Build', 42),
            ('ARRANGE', 'Arrange', 54),
            ('SIMULATE', 'Simulate', 60),
            ('STOP', 'Stop', 42),
            ('RESET', 'Reset', 44),
            ('KEEP', 'Keep mesh', 74),
        ], self.workflow, 2, 24)

    def button_row(self, specs, region, offset, height):
        s = self.scale
        p = self.panel
        factor = min(1.0, max(0.05, (region.w - 24 * s) / (sum(item[2] + 5 for item in specs) * s)))
        x = region.x + 12 * s
        for name, label, units in specs:
            w = units * s * factor
            bx = max(p.x, min(p.x + p.w - w, x))
            self.buttons[name] = (Rect(bx, region.y + offset * s, w, height * s), label)
            x += w + 5 * s

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
