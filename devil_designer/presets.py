import math


PRESETS = {
    'SILK': dict(structural=12.3, bending=0.55, density=0.07),
    'KNIT': dict(structural=7.1, bending=0.95, density=0.17),
    'COTTON': dict(structural=32.0, bending=2.2, density=0.14),
    'LINEN': dict(structural=65.0, bending=6.0, density=0.19),
    'DENIM': dict(structural=120.0, bending=68.0, density=0.40),
    'LEATHER': dict(structural=180.0, bending=115.0, density=0.60),
}


FABRIC_DEFAULTS = dict(weft=1.0, bias=1.0, shrink_warp=0.0, shrink_weft=0.0)
REQUIRED = {'structural', 'bending', 'density'}
SHRINK_LIMIT = .3


def valid_fabric(values):
    if not isinstance(values, dict) or not REQUIRED <= set(values) <= REQUIRED | set(FABRIC_DEFAULTS):
        return False
    for key, value in values.items():
        if type(value) not in (int, float) or not math.isfinite(value):
            return False
        if key.startswith('shrink_') and abs(value) > SHRINK_LIMIT or not key.startswith('shrink_') and value <= 0:
            return False
    return True


def resolve_preset(name, custom_presets=None):
    if custom_presets and name in custom_presets:
        return {**FABRIC_DEFAULTS, **custom_presets[name]}
    return {**FABRIC_DEFAULTS, **PRESETS.get(name, PRESETS['COTTON'])}
