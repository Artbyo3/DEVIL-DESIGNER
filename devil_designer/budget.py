PC_RANKS = (('Excellent', 32000), ('Good', 70000))
QUEST_RANKS = (('Excellent', 7500), ('Good', 10000), ('Medium', 15000), ('Poor', 20000))


def rank(count, ranks):
    return next((name for name, limit in ranks if count <= limit), 'Very Poor')


def mesh_triangles(mesh):
    return len(mesh.loops) - 2 * len(mesh.polygons)


def summary(scene, objects):
    def doubled(obj):
        return bool(obj.modifiers.get('Fabric Thickness')) or (obj.get('dd_kind') == 'simulation' and scene.dd_thickness > 0)
    garment = sum(mesh_triangles(obj.data) * (2 if doubled(obj) else 1) for obj in objects)
    body = scene.dd_avatar
    total = garment + (mesh_triangles(body.data) if body is not None and body.type == 'MESH' else 0)
    return dict(garment=garment, estimated=any(doubled(obj) for obj in objects), total=total, body=body is not None,
                pc=rank(total, PC_RANKS), quest=rank(total, QUEST_RANKS))
