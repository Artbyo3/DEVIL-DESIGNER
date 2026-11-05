def kept_garments(scene):
    from . import garment
    return sorted((obj for obj in garment.generated(scene,'final') if obj.type=='MESH'),key=lambda obj:obj.name)


def wear_over_selection(scene):
    return [(obj.name,bool(obj.get('dd_wear_over',True))) for obj in kept_garments(scene)]


def collision_bodies(scene):
    kept=kept_garments(scene)
    worn=[obj for obj in kept if obj.get('dd_wear_over',True)]
    extras=[obj for obj in scene.objects if obj.type=='MESH' and obj is not scene.dd_avatar and not obj.get('dd_kind')
            and any(modifier.type=='COLLISION' and modifier.show_viewport for modifier in obj.modifiers)]
    return [scene.dd_avatar,*worn,*extras]
