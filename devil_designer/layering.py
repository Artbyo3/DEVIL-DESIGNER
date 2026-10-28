def kept_garments(scene):
    from . import garment
    return sorted((obj for obj in garment.generated(scene,'final') if obj.type=='MESH'),key=lambda obj:obj.name)


def wear_over_selection(scene):
    return [(obj.name,bool(obj.get('dd_wear_over',True))) for obj in kept_garments(scene)]


def prepare_colliders(context):
    candidates=[obj for obj in kept_garments(context.scene) if obj.get('dd_wear_over',True)]
    missing=[obj for obj in candidates if not any(modifier.type=='COLLISION' for modifier in obj.modifiers)]
    for obj in missing:
        if not obj.is_editable:
            raise ValueError(f'Make kept garment {obj.name} editable before adding collision.')
    for obj in missing:
        obj.modifiers.new('DD Garment Collision','COLLISION')


def configure_collision_collection(context,simulation):
    scene=context.scene
    kept=kept_garments(scene)
    if not kept:
        return
    import bpy
    from . import garment
    cloth=next((modifier for modifier in simulation.modifiers if modifier.type=='CLOTH'),None)
    if cloth is None:
        raise ValueError('The garment simulation has no cloth modifier.')
    excluded={obj for obj in kept if not obj.get('dd_wear_over',True)}
    colliders={obj for obj in scene.objects if obj==scene.dd_avatar or
               (obj not in excluded and any(modifier.type=='COLLISION' for modifier in obj.modifiers))}
    cloth_modifiers=[modifier for obj in bpy.data.objects for modifier in obj.modifiers if modifier.type=='CLOTH']
    target=cloth.collision_settings.collection
    if (target is None or target.get('dd_layering_owner')!=garment.OWNER or target.library or
        target.users!=int(target.use_fake_user) or
        sum(modifier.collision_settings.collection==target for modifier in cloth_modifiers)>1):
        target=bpy.data.collections.new('DD Wear Over')
        target['dd_layering_owner']=garment.OWNER
        target.use_fake_user=True
    for obj in list(target.objects):
        if obj not in colliders:
            target.objects.unlink(obj)
    for obj in colliders:
        if obj.name not in target.objects:
            target.objects.link(obj)
    cloth.collision_settings.collection=target
    referenced={modifier.collision_settings.collection for modifier in cloth_modifiers}
    for candidate in list(bpy.data.collections):
        if (candidate.get('dd_layering_owner')==garment.OWNER and not candidate.library and
            candidate not in referenced and candidate.users==int(candidate.use_fake_user)):
            bpy.data.collections.remove(candidate)
    context.view_layer.update()
