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
                 position=None, stage="DRAFT"):
        self.scale = s = scale
        self.full = full
        self.stage = stage
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
        self.buttons = {}

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
