from contextlib import contextmanager

SHRINK_KEY_NAME = 'shrink'


def hidden_by(source):
    masks = [modifier.name for modifier in getattr(source, 'modifiers', ()) if modifier.type == 'MASK' and modifier.show_viewport]
    data = getattr(source, 'data', None)
    keys = getattr(data, 'shape_keys', None)
    blocks = list(keys.key_blocks)[1:] if keys is not None else []
    shrinks = [block.name for block in blocks if SHRINK_KEY_NAME in block.name.casefold() and not block.mute and block.value != 0]
    return masks, shrinks


def hiding_state(source):
    masks, shrinks = hidden_by(source)
    if not masks and not shrinks:
        return ()
    keys = source.data.shape_keys
    return (tuple(masks), tuple((name, keys.key_blocks[name].value) for name in shrinks))


@contextmanager
def revealed(context, source):
    masks, shrinks = hidden_by(source)
    if not masks and not shrinks:
        yield source.evaluated_get(context.evaluated_depsgraph_get())
        return
    import bpy
    from .live_panels import quiet
    context.evaluated_depsgraph_get()
    with quiet():
        mesh = source.data.copy()
        stand_in = source.copy()
        stand_in.data = mesh
        try:
            for name in masks:
                stand_in.modifiers.remove(stand_in.modifiers[name])
            for name in shrinks:
                mesh.shape_keys.key_blocks[name].mute = True
            context.scene.collection.objects.link(stand_in)
            yield stand_in.evaluated_get(context.evaluated_depsgraph_get())
        finally:
            key = mesh.shape_keys
            bpy.data.objects.remove(stand_in, do_unlink=True)
            bpy.data.meshes.remove(mesh)
            try:
                if key is not None and key.users == 0:
                    bpy.data.batch_remove([key])
            except ReferenceError:
                pass
            context.evaluated_depsgraph_get()
