"""A pattern drafting workspace inside Blender."""
bl_info = {
    "name": "Devil Designer", "author": "Artbyo3", "version": (0, 3, 0),
    "blender": (5, 2, 0), "location": "View3D > View > Devil Designer; Ctrl+Alt+D",
    "description": "Draft, sew, and drape clothing patterns", "category": "3D View",
}

def register():
    from . import ui
    ui.register()

def unregister():
    from . import ui
    ui.unregister()
