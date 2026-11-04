from dataclasses import dataclass
from typing import Tuple

try:
    import blf
except ImportError:
    blf = None

try:
    import bpy
except ImportError:
    bpy = None

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
RADIUS_CONTROL = 4.0
RADIUS_BADGE = 2.0


@dataclass
class MinimalMetrics:
    toolbar_item: float = 4.0
    regular: float = 4.0
    menu_back: float = 4.0
    menu_item: float = 4.0
    text: float = 4.0
    box: float = 4.0
    tooltip: float = 4.0

    @classmethod
    def resolve(cls):
        m = cls()
        if bpy is not None:
            try:
                ui = bpy.context.preferences.themes[0].user_interface
                roles = ('toolbar_item', 'regular', 'menu_back', 'menu_item', 'text', 'box', 'tooltip')
                for role in roles:
                    wcol = getattr(ui, 'wcol_' + role, None)
                    if wcol is not None and hasattr(wcol, 'roundness'):
                        setattr(m, role, 0.5 * float(wcol.roundness) * 20.0)
            except Exception:
                pass
        return m


VIEWPORT_LEVELS = ((0, 0), (4, 12), (8, 17), (12, 20), (16, 23), (19, 26), (23, 29), (28, 34), (32, 37), (36, 41),
                   (40, 44), (46, 50), (53, 56), (61, 63), (70, 72), (80, 81), (100, 100), (255, 255))


def viewport_level(value):
    target = value * 255
    for (sent_low, shown_low), (sent_high, shown_high) in zip(VIEWPORT_LEVELS, VIEWPORT_LEVELS[1:]):
        if target <= shown_high:
            return (sent_low + (target - shown_low) * (sent_high - sent_low) / (shown_high - shown_low)) / 255
    return value


def viewport_color(color):
    return (*(viewport_level(channel) for channel in color[:3]), color[3])


def theme_color(value):
    color = tuple(value)
    return color if len(color) == 4 else (*color, 1.0)


def mixed(first, second, amount):
    return tuple(a + (b - a) * amount for a, b in zip(first[:3], second[:3])) + (1.0,)


@dataclass
class NativeField:
    fill: Tuple[float, ...]
    fill_hover: Tuple[float, ...]
    fill_edit: Tuple[float, ...]
    outline: Tuple[float, ...]
    outline_hover: Tuple[float, ...]
    outline_edit: Tuple[float, ...]
    ink: Tuple[float, ...]
    ink_edit: Tuple[float, ...]
    selection: Tuple[float, ...]
    cursor: Tuple[float, ...]
    label: Tuple[float, ...]
    popup: Tuple[float, ...]
    popup_outline: Tuple[float, ...]
    row_ink: Tuple[float, ...]
    row_ink_active: Tuple[float, ...]
    row_active: Tuple[float, ...]
    shadow_width: int
    shadow_alpha: float

    @classmethod
    def resolve(cls):
        theme = bpy.context.preferences.themes[0]
        ui = theme.user_interface
        field, back, item = ui.wcol_text, ui.wcol_menu_back, ui.wcol_menu_item
        fill, outline, ink = theme_color(field.inner), theme_color(field.outline), theme_color(field.text)
        outline_edit = theme_color(field.outline_sel)
        row_ink = theme_color(item.text)
        popup = theme_color(back.inner)
        colors = dict(fill=fill, fill_hover=mixed(fill, ink, .03), fill_edit=theme_color(field.inner_sel),
                      outline=outline, outline_hover=mixed(outline, outline_edit, .5), outline_edit=outline_edit,
                      ink=ink, ink_edit=theme_color(field.text_sel), selection=theme_color(field.item),
                      cursor=theme_color(ui.widget_text_cursor), label=theme_color(theme.properties.space.text),
                      popup=mixed(SURFACE_FLOATING, popup, popup[3]), popup_outline=theme_color(back.outline), row_ink=row_ink,
                      row_ink_active=theme_color(item.text_sel), row_active=mixed(theme_color(item.inner), row_ink, .2))
        return cls(shadow_width=ui.menu_shadow_width, shadow_alpha=ui.menu_shadow_fac / 4,
                   **{name: viewport_color(color) for name, color in colors.items()})


@dataclass
class Tooltip:
    text: str = ""
    shortcut: str = ""
    pos: Tuple[float, float] = (0.0, 0.0)
    visible: bool = False


class ComponentRenderer:

    @staticmethod
    def draw_tooltip(draw_ctx, tooltip: Tooltip, scale: float, metrics=None):
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
        draw_ctx.round_rect(r, (0.08, 0.10, 0.12, 0.95), radius=metrics.tooltip if metrics else RADIUS_CONTROL)
        draw_ctx.round_rect_outline(r, BORDER_SUBTLE, radius=metrics.tooltip if metrics else RADIUS_CONTROL, width=1.0)
        draw_ctx.text(r.x + 8 * s, r.y + 6 * s, tooltip.text, 10, TEXT_PRIMARY)

        if tooltip.shortcut:
            pill_r = Rect(r.x + r.w - sw - 4 * s, r.y + 3 * s, sw, 18 * s)
            draw_ctx.round_rect(pill_r, BG_ELEVATED, radius=metrics.box if metrics else RADIUS_BADGE)
            draw_ctx.text(pill_r.x + pill_r.w / 2, pill_r.y + 4 * s, tooltip.shortcut, 9, ACCENT, center=True)

ARRANGEMENT_POINT_DIAMETER = 18.0
ARRANGEMENT_POINT_BODY_FRACTION = .03
ARRANGEMENT_ACTIVE_DIAMETER = 22.0
ARRANGEMENT_HIT_DIAMETER = 32.0
ARRANGEMENT_EDGE_WIDTH = 1.5
ARRANGEMENT_EDGE_FEATHER = 1.0
ARRANGEMENT_DRAG_THRESHOLD = 4.0
ARRANGEMENT_LABEL_SIZE = 11
ARRANGEMENT_FILL = (.28, .78, 1.0, 1.0)
ARRANGEMENT_MIRRORED = ACCENT
ARRANGEMENT_ATTACHED = SELECTION
ARRANGEMENT_EDGE = (.035, .05, .07, 1.0)
ARRANGEMENT_HALO = (1.0, 1.0, 1.0, 1.0)
ARRANGEMENT_PREVIEW = (1.0, .635, .337, .85)


def interface_scale():
    try:
        return float(bpy.context.preferences.system.ui_scale)
    except (AttributeError, TypeError):
        return 1.0

TRANSFORM_FRAME = (0.439, 0.835, 0.773, 0.75)
TRANSFORM_HANDLE = (0.949, 0.957, 0.965, 1.0)
TRANSFORM_HANDLE_HOVER = (1.0, .635, .337, 1.0)
TRANSFORM_PIVOT = (1.0, 0.85, 0.4, 0.95)
TRANSFORM_PREVIEW_OK = (0.439, 0.835, 0.773, 0.95)
TRANSFORM_PREVIEW_WARN = (0.98, 0.73, 0.32, 0.95)
TRANSFORM_PREVIEW_BLOCK = (0.98, 0.45, 0.28, 0.95)
TRANSFORM_FRAME_PAD = 10.0
TRANSFORM_HANDLE_SIZE = 9.0
TRANSFORM_KNOB_OFFSET = 26.0
TRANSFORM_KNOB_RADIUS = 6.0
TRANSFORM_HIT_RADIUS = 11.0
TRANSFORM_PIVOT_HIT_RADIUS = 8.0
