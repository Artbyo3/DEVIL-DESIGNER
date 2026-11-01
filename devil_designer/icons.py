import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def icon_geometry():
    return json.loads((Path(__file__).parent / 'assets' / 'icons' / 'geometry.json').read_text(encoding='utf-8'))


ICON_ALIASES = {
    'FREE_SEW': 'SEW', 'FULL': 'EXPAND',
    'WORKSPACE_PANEL': 'SETTINGS', 'WORKSPACE_CLOSE': 'CLOSE',
    'WORKSPACE_PIN': 'PIN', 'SIMULATE': 'PLAY', 'DRAW': 'RECTANGLE',
    'DRAW_RECTANGLE': 'RECTANGLE', 'DRAW_ELLIPSE': 'ELLIPSE', 'DRAW_POLYGON': 'POLYGON',
    'INSPECTOR_COLLAPSE': 'CHEVRON', 'INSPECTOR_TOGGLE': 'SETTINGS',
    'LENGTHS': 'RULER', 'GRID': 'LIBRARY'
}


def icon_spans(name):
    return icon_geometry().get(ICON_ALIASES.get(name, name))
