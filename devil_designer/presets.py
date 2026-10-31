PRESETS = {
    'SILK': dict(structural=10.0, shear=5.0, bending=.08, density=.08),
    'KNIT': dict(structural=7.0, shear=4.0, bending=.12, density=.25),
    'COTTON': dict(structural=25.0, shear=15.0, bending=.5, density=.30),
    'LINEN': dict(structural=35.0, shear=20.0, bending=1.0, density=.25),
    'DENIM': dict(structural=65.0, shear=35.0, bending=3.0, density=.5),
    'LEATHER': dict(structural=85.0, shear=55.0, bending=5.0, density=.7),
}


def resolve_preset(name, custom_presets=None):
    if custom_presets and name in custom_presets:
        return dict(custom_presets[name])
    return dict(PRESETS.get(name, PRESETS['COTTON']))
