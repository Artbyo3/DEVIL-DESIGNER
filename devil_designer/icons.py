import json
from functools import lru_cache
from pathlib import Path

ICON_GRID = 64
ICON_LEVELS = 32


@lru_cache(maxsize=1)
def icon_geometry():
    return json.loads((Path(__file__).parent / 'assets' / 'icons' / 'geometry.json').read_text(encoding='utf-8'))


def icon_spans(name):
    return icon_geometry().get(name)


def overlaps(start, ratio, pixels):
    low, high = start * ratio, (start + 1) * ratio
    first = int(low)
    return [(cell, min(high, cell + 1) - max(low, cell)) for cell in range(first, min(pixels, int(high) + 1)) if min(high, cell + 1) > max(low, cell)]


@lru_cache(maxsize=None)
def icon_pixels(name, pixels):
    ratio = pixels / ICON_GRID
    coverage = {}
    for column, row, width, level in icon_spans(name):
        for source_x in range(column, column + width):
            for x, share_x in overlaps(source_x, ratio, pixels):
                for y, share_y in overlaps(row, ratio, pixels):
                    coverage[x, y] = coverage.get((x, y), 0) + share_x * share_y * level / 8
    levels = {}
    for cell, amount in coverage.items():
        step = min(ICON_LEVELS, round(amount * ICON_LEVELS))
        if step:
            levels.setdefault(step, []).append(cell)
    return levels
