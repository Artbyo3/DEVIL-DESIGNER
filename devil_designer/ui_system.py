from dataclasses import dataclass
from typing import Tuple

try:
    import blf
except ImportError:
    blf = None

try:
    from .canvas import Rect
except ImportError:
    @dataclass(frozen=True)
    class Rect:
        x: float
        y: float
        w: float
        h: float
        def contains(self, x, y):
            return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

BG_BASE = (0.098, 0.114, 0.133, 1.0)
BG_PANEL = (0.137, 0.161, 0.188, 1.0)
BG_ELEVATED = (0.188, 0.220, 0.251, 1.0)
BG_WELL = (0.078, 0.094, 0.110, 1.0)

TEXT_PRIMARY = (0.949, 0.957, 0.965, 1.0)
TEXT_SECONDARY = (0.745, 0.780, 0.816, 1.0)
TEXT_MUTED = (0.600, 0.647, 0.694, 1.0)

ACCENT = (0.439, 0.835, 0.773, 1.0)
ACCENT_BG = (0.118, 0.212, 0.200, 1.0)
ACCENT_BORDER = (0.227, 0.420, 0.388, 1.0)
ACCENT_HOVER = (0.520, 0.890, 0.830, 1.0)

BORDER = (0.176, 0.208, 0.243, 1.0)
BORDER_SUBTLE = (0.227, 0.267, 0.310, 1.0)
SURFACE_FLOATING = (0.118, 0.137, 0.157, .99)
SURFACE_OUTLINE = (0.267, 0.306, 0.345, 1.0)
SELECTION = (1.0, .635, .337, 1.0)
TEXT_ON_ACCENT = (.047, .145, .137, 1.0)

RADIUS_WINDOW = 4.0
RADIUS_DOCK = 4.0
RADIUS_DOCK_ITEM = 3.0
RADIUS_CARD = 4.0
RADIUS_CONTROL = 3.0
RADIUS_BADGE = 2.0
RADIUS_DEFAULT = RADIUS_CONTROL


@dataclass
class Tooltip:
    text: str = ""
    shortcut: str = ""
    pos: Tuple[float, float] = (0.0, 0.0)
    visible: bool = False


class ComponentRenderer:

    @staticmethod
    def draw_tooltip(draw_ctx, tooltip: Tooltip, scale: float):
        if not tooltip.visible or not tooltip.text:
            return
        s = scale
        x, y = tooltip.pos
        if blf:
            blf.size(0, 10 * s)
            tw = blf.dimensions(0, tooltip.text)[0]
            sw = blf.dimensions(0, tooltip.shortcut)[0] + 12 * s if tooltip.shortcut else 0.0
        else:
            tw = len(tooltip.text) * 7 * s
            sw = len(tooltip.shortcut) * 7 * s if tooltip.shortcut else 0.0
        w = tw + sw + 18 * s
        h = 24 * s

        r = Rect(x + 10 * s, y - h / 2, w, h)
        draw_ctx.round_rect(r, (0.08, 0.10, 0.12, 0.95), radius=RADIUS_CONTROL)
        draw_ctx.round_rect_outline(r, BORDER_SUBTLE, radius=RADIUS_CONTROL, width=1.0)
        draw_ctx.text(r.x + 8 * s, r.y + 6 * s, tooltip.text, 10, TEXT_PRIMARY)

        if tooltip.shortcut:
            pill_r = Rect(r.x + r.w - sw - 4 * s, r.y + 3 * s, sw, 18 * s)
            draw_ctx.round_rect(pill_r, BG_ELEVATED, radius=RADIUS_BADGE)
            draw_ctx.text(pill_r.x + pill_r.w / 2, pill_r.y + 4 * s, tooltip.shortcut, 9, ACCENT, center=True)
