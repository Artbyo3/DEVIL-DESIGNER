bl_info = {
    "name": "Devil Designer", "author": "Artbyo3", "version": (0, 12, 0),
    "blender": (5, 2, 0), "location": "View3D > View > Devil Designer; Ctrl+Alt+D",
    "description": "Draft, sew, and drape clothing patterns", "category": "3D View",
}

def other_installed_copy():
    import sys
    import bpy
    registered = getattr(bpy.types, 'DEVIL_DESIGNER_OT_pattern_editor', None)
    owner = registered.__module__.rpartition('.')[0] if registered is not None else __package__
    if owner == __package__:
        return None
    return getattr(sys.modules.get(owner), '__file__', None) or owner

def register():
    other = other_installed_copy()
    if other is not None:
        raise RuntimeError('Devil Designer is already enabled from ' + str(other) + '. Two installed copies break the editor and simulation. Disable or remove one copy in Preferences > Get Extensions, then restart Blender.')
    from . import ui
    ui.register()

def unregister():
    if other_installed_copy() is not None:
        return
    from . import ui
    ui.unregister()
