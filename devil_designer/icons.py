import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def icon_geometry():
    return json.loads((Path(__file__).parent / 'assets' / 'icons' / 'geometry.json').read_text(encoding='utf-8'))


def icon_spans(name):
    return icon_geometry().get(name)
