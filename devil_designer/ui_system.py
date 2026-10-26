"""Reusable  UI system for Devil Designer overlay in Blender.

Implements centralized design tokens, reusable components (Button, IconButton,
Toggle, Dropdown, NumericInput, Slider, Tab, Tooltip, ScrollablePanel, ContextMenu),
and unified layout & hit detection.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, Callable
import math

try:
    import gpu
    from gpu_extras.batch import batch_for_shader
    import blf
except ImportError:
    gpu = None
    batch_for_shader = None
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

SPACE_4 = 4.0
SPACE_8 = 8.0
SPACE_12 = 12.0
SPACE_16 = 16.0
SPACE_24 = 24.0

RADIUS_DEFAULT = 7.0
RADIUS_SMALL = 5.0
RADIUS_LARGE = 10.0

TOP_BAR_H = 48.0
TOOL_RAIL_W = 52.0
INSPECTOR_W = 280.0
STATUS_BAR_H = 28.0
VIEWBAR_H = 38.0


@dataclass
class UIComponent:
    id: str
    rect: Rect
    enabled: bool = True
    visible: bool = True
    hover: bool = False
    focused: bool = False
    tooltip: str = ""
    tooltip_shortcut: str = ""
    on_click: Optional[Callable] = None

    def contains(self, x: float, y: float) -> bool:
        if not self.visible:
            return False
        return self.rect.contains(x, y)


@dataclass
class Button(UIComponent):
    label: str = ""
    kind: str = "standard"
    icon: str = ""
    badge: str = ""
    active: bool = False


@dataclass
class IconButton(UIComponent):
    icon: str = ""
    active: bool = False
    active_color: tuple = ACCENT
    size: float = 18.0


@dataclass
class Toggle(UIComponent):
    value: bool = False
    label: str = ""


@dataclass
class Dropdown(UIComponent):
    label: str = ""
    value: str = ""
    options: List[Tuple[str, str]] = field(default_factory=list)
    open: bool = False
    menu_rect: Optional[Rect] = None


@dataclass
class NumericInput(UIComponent):
    label: str = ""
    value: float = 0.0
    text_value: str = ""
    unit: str = ""
    step: float = 1.0
    low: float = -1000.0
    high: float = 1000.0
    integer: bool = False
    value_rect: Optional[Rect] = None
    minus_rect: Optional[Rect] = None
    plus_rect: Optional[Rect] = None


@dataclass
class Slider(UIComponent):
    label: str = ""
    value: float = 0.0
    unit: str = ""
    low: float = 0.0
    high: float = 1.0
    track_rect: Optional[Rect] = None
    thumb_rect: Optional[Rect] = None


@dataclass
class Tab(UIComponent):
    label: str = ""
    num: str = ""
    active: bool = False


@dataclass
class Tooltip:
    text: str = ""
    shortcut: str = ""
    pos: Tuple[float, float] = (0.0, 0.0)
    visible: bool = False


@dataclass
class ScrollablePanel:
    rect: Rect
    content_height: float = 0.0
    scroll: float = 0.0
    dragging_thumb: bool = False
    drag_start_y: float = 0.0
    drag_start_scroll: float = 0.0

    @property
    def max_scroll(self) -> float:
        return max(0.0, self.content_height - self.rect.h)

    def clamp(self):
        self.scroll = max(0.0, min(self.max_scroll, self.scroll))

    def scroll_by(self, delta: float):
        self.scroll += delta
        self.clamp()

    def thumb_rect(self, scale: float = 1.0) -> Optional[Rect]:
        if self.content_height <= self.rect.h or self.rect.h <= 20:
            return None
        s = scale
        track_h = self.rect.h - 8 * s
        thumb_h = max(24 * s, (self.rect.h / self.content_height) * track_h)
        scroll_ratio = self.scroll / self.max_scroll if self.max_scroll > 0 else 0.0
        thumb_y = (self.rect.y + self.rect.h - 4 * s - thumb_h) - scroll_ratio * (track_h - thumb_h)
        thumb_w = 4 * s
        thumb_x = self.rect.x + self.rect.w - 7 * s
        return Rect(thumb_x, thumb_y, thumb_w, thumb_h)


@dataclass
class ContextMenu:
    rect: Rect
    items: List[Tuple[str, str, Optional[str]]] = field(default_factory=list)
    open: bool = False
    anchor: Tuple[float, float] = (0.0, 0.0)
    item_rects: Dict[str, Rect] = field(default_factory=dict)


class ComponentRenderer:
    """Renders UI components using exact component bounds."""

    @staticmethod
    def draw_button(draw_ctx, btn: Button, scale: float):
        s = scale
        r = btn.rect
        if btn.kind == "primary":
            bg = ACCENT if not btn.hover else ACCENT_HOVER
            text_color = (0.06, 0.16, 0.15, 1.0)
            draw_ctx.round_rect(r, bg, radius=RADIUS_DEFAULT)
            draw_ctx.round_rect_outline(r, (0.58, 0.92, 0.85, 1.0), radius=RADIUS_DEFAULT, width=1.0)
        elif btn.kind == "pill":
            if btn.active:
                draw_ctx.round_rect(r, ACCENT_BG, radius=RADIUS_DEFAULT)
                draw_ctx.round_rect_outline(r, ACCENT_BORDER, radius=RADIUS_DEFAULT, width=1.0)
                text_color = ACCENT
            elif btn.hover:
                draw_ctx.round_rect(r, BG_ELEVATED, radius=RADIUS_DEFAULT)
                draw_ctx.round_rect_outline(r, BORDER_SUBTLE, radius=RADIUS_DEFAULT, width=1.0)
                text_color = TEXT_PRIMARY
            else:
                draw_ctx.round_rect(r, BG_PANEL, radius=RADIUS_DEFAULT)
                draw_ctx.round_rect_outline(r, BORDER, radius=RADIUS_DEFAULT, width=1.0)
                text_color = TEXT_SECONDARY
        elif btn.kind == "ghost":
            if btn.hover:
                draw_ctx.round_rect(r, BG_ELEVATED, radius=RADIUS_DEFAULT)
            text_color = TEXT_PRIMARY if btn.hover else TEXT_SECONDARY
        else:
            bg = BG_ELEVATED if btn.hover else BG_PANEL
            draw_ctx.round_rect(r, bg, radius=RADIUS_DEFAULT)
            draw_ctx.round_rect_outline(r, BORDER_SUBTLE, radius=RADIUS_DEFAULT, width=1.0)
            text_color = TEXT_PRIMARY if btn.hover else TEXT_SECONDARY

        if btn.icon:
            draw_ctx.draw_icon(btn.icon, r.x + 14 * s, r.y + r.h / 2, 14, text_color)
            draw_ctx.text(r.x + 28 * s, r.y + (r.h - 10 * s) / 2, btn.label, 11, text_color)
        else:
            draw_ctx.text(r.x + r.w / 2, r.y + (r.h - 10 * s) / 2, btn.label, 11, text_color, center=True)

    @staticmethod
    def draw_icon_button(draw_ctx, btn: IconButton, scale: float):
        s = scale
        r = btn.rect
        if btn.active:
            draw_ctx.round_rect(r, ACCENT_BG, radius=RADIUS_DEFAULT)
            draw_ctx.round_rect_outline(r, ACCENT_BORDER, radius=RADIUS_DEFAULT, width=1.2)
            color = btn.active_color
        elif btn.hover:
            draw_ctx.round_rect(r, BG_ELEVATED, radius=RADIUS_DEFAULT)
            color = TEXT_PRIMARY
        else:
            color = TEXT_SECONDARY

        draw_ctx.draw_icon(btn.icon, r.x + r.w / 2, r.y + r.h / 2, btn.size, color)

    @staticmethod
    def draw_toggle(draw_ctx, toggle: Toggle, scale: float):
        s = scale
        r = toggle.rect
        pill_w = 34 * s
        pill_h = 18 * s
        pill_x = r.x + r.w - pill_w - 4 * s
        pill_y = r.y + (r.h - pill_h) / 2
        pill_r = Rect(pill_x, pill_y, pill_w, pill_h)

        if toggle.value:
            draw_ctx.round_rect(pill_r, ACCENT, radius=pill_h / 2)
            thumb_cx = pill_x + pill_w - pill_h / 2
            thumb_cy = pill_y + pill_h / 2
            draw_ctx.dot((thumb_cx, thumb_cy), pill_h / 2 - 2 * s, (0.06, 0.16, 0.15, 1.0))
        else:
            draw_ctx.round_rect(pill_r, BG_WELL, radius=pill_h / 2)
            draw_ctx.round_rect_outline(pill_r, BORDER_SUBTLE, radius=pill_h / 2, width=1.0)
            thumb_cx = pill_x + pill_h / 2
            thumb_cy = pill_y + pill_h / 2
            draw_ctx.dot((thumb_cx, thumb_cy), pill_h / 2 - 2 * s, TEXT_MUTED)

        draw_ctx.text(r.x + 4 * s, r.y + (r.h - 10 * s) / 2, toggle.label, 11, TEXT_PRIMARY if toggle.hover else TEXT_SECONDARY)

    @staticmethod
    def draw_numeric_input(draw_ctx, num: NumericInput, scale: float, active_editing: bool = False, active_text: str = ""):
        s = scale
        r = num.rect
        vr = num.value_rect or r
        minus_r = num.minus_rect
        plus_r = num.plus_rect

        draw_ctx.text(r.x, r.y + r.h - 13 * s, num.label, 10, TEXT_SECONDARY)

        well_bg = BG_ELEVATED if active_editing else BG_WELL
        draw_ctx.round_rect(vr, well_bg, radius=RADIUS_SMALL)
        outline_col = ACCENT if active_editing else (BORDER_SUBTLE if not num.hover else (0.35, 0.42, 0.48, 1.0))
        draw_ctx.round_rect_outline(vr, outline_col, radius=RADIUS_SMALL, width=1.2 if active_editing else 1.0)

        disp_text = active_text if active_editing else num.text_value
        draw_ctx.text(vr.x + 8 * s, vr.y + (vr.h - 11 * s) / 2, disp_text, 11, TEXT_PRIMARY if not active_editing else ACCENT)
        if num.unit and not active_editing and blf:
            blf.size(0, 11 * s)
            vw = blf.dimensions(0, disp_text)[0]
            draw_ctx.text(vr.x + 12 * s + vw, vr.y + (vr.h - 10 * s) / 2, num.unit, 10, TEXT_MUTED)

        if minus_r and plus_r:
            for br, symbol in [(minus_r, "–"), (plus_r, "+")]:
                draw_ctx.round_rect(br, BG_PANEL, radius=RADIUS_SMALL)
                draw_ctx.round_rect_outline(br, BORDER_SUBTLE, radius=RADIUS_SMALL, width=1.0)
                draw_ctx.text(br.x + br.w / 2, br.y + (br.h - 10 * s) / 2, symbol, 11, TEXT_SECONDARY, center=True)

    @staticmethod
    def draw_tab(draw_ctx, tab: Tab, scale: float):
        s = scale
        r = tab.rect
        if tab.active:
            draw_ctx.round_rect(r, BG_ELEVATED, radius=RADIUS_DEFAULT)
            draw_ctx.round_rect_outline(r, BORDER_SUBTLE, radius=RADIUS_DEFAULT, width=1.0)
            if tab.num:
                draw_ctx.text(r.x + 10 * s, r.y + (r.h - 10 * s) / 2, tab.num, 9, ACCENT)
                draw_ctx.text(r.x + 28 * s, r.y + (r.h - 11 * s) / 2, tab.label, 11, TEXT_PRIMARY)
            else:
                draw_ctx.text(r.x + r.w / 2, r.y + (r.h - 11 * s) / 2, tab.label, 11, TEXT_PRIMARY, center=True)
        else:
            if tab.hover:
                draw_ctx.round_rect(r, (0.16, 0.19, 0.22, 1.0), radius=RADIUS_DEFAULT)
            if tab.num:
                draw_ctx.text(r.x + 10 * s, r.y + (r.h - 10 * s) / 2, tab.num, 9, TEXT_MUTED)
                draw_ctx.text(r.x + 28 * s, r.y + (r.h - 11 * s) / 2, tab.label, 11, TEXT_SECONDARY if not tab.hover else TEXT_PRIMARY)
            else:
                draw_ctx.text(r.x + r.w / 2, r.y + (r.h - 11 * s) / 2, tab.label, 11, TEXT_SECONDARY if not tab.hover else TEXT_PRIMARY, center=True)

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
        draw_ctx.round_rect(r, (0.08, 0.10, 0.12, 0.95), radius=5.0)
        draw_ctx.round_rect_outline(r, BORDER_SUBTLE, radius=5.0, width=1.0)
        draw_ctx.text(r.x + 8 * s, r.y + 6 * s, tooltip.text, 10, TEXT_PRIMARY)

        if tooltip.shortcut:
            pill_r = Rect(r.x + r.w - sw - 4 * s, r.y + 3 * s, sw, 18 * s)
            draw_ctx.round_rect(pill_r, BG_ELEVATED, radius=3.0)
            draw_ctx.text(pill_r.x + pill_r.w / 2, pill_r.y + 4 * s, tooltip.shortcut, 9, ACCENT, center=True)

    @staticmethod
    def draw_scrollbar(draw_ctx, panel: ScrollablePanel, scale: float):
        thumb = panel.thumb_rect(scale)
        if not thumb:
            return
        draw_ctx.round_rect(thumb, (0.35, 0.42, 0.48, 0.65), radius=2.0)
