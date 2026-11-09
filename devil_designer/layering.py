import json


def kept_garments(scene):
    from . import garment
    return sorted((obj for obj in garment.generated(scene,'final') if obj.type=='MESH'),key=lambda obj:obj.name)


def current_pieces(scene):
    from . import garment
    return {panel.get('dd_pattern_id') for panel in garment.generated(scene,'panel')}


def worn(obj,current):
    chosen=obj.get('dd_wear_over')
    if chosen is not None:
        return bool(chosen)
    return not (current and current.intersection(json.loads(obj.get('dd_piece_ids','[]'))))


def worn_garments(scene):
    kept=kept_garments(scene)
    current=current_pieces(scene) if kept else set()
    return [(obj,worn(obj,current)) for obj in kept]


def wear_over_selection(scene):
    return [(obj.name,enabled) for obj,enabled in worn_garments(scene)]


def collision_bodies(scene):
    worn=[obj for obj,enabled in worn_garments(scene) if enabled]
    extras=[obj for obj in scene.objects if obj.type=='MESH' and obj is not scene.dd_avatar and not obj.get('dd_kind')
            and any(modifier.type=='COLLISION' and modifier.show_viewport for modifier in obj.modifiers)]
    return [scene.dd_avatar,*worn,*extras]
