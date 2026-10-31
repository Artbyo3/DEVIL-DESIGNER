PRESETS = {
    'SILK': dict(structural=12.3, shear=6.2, bending=0.55, density=0.07),
    'KNIT': dict(structural=7.1, shear=3.5, bending=0.95, density=0.17),
    'COTTON': dict(structural=32.0, shear=16.0, bending=2.2, density=0.14),
    'LINEN': dict(structural=65.0, shear=32.5, bending=6.0, density=0.19),
    'DENIM': dict(structural=120.0, shear=60.0, bending=68.0, density=0.40),
    'LEATHER': dict(structural=180.0, shear=90.0, bending=115.0, density=0.60),
}


def resolve_preset(name, custom_presets=None):
    if custom_presets and name in custom_presets:
        return dict(custom_presets[name])
    return dict(PRESETS.get(name, PRESETS['COTTON']))
